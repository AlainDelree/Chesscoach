# Changelog — Issue #140

## Issue #140 — Suite #139 : mode série, étape 2 (avis des deux IA en arrière-plan, file d'attente, compteur « avis en cours »)

Remplace le court-circuit temporaire de l'étape 1 (#139 : aucun appel aux
IA en mode série) par de VRAIS appels en arrière-plan, sans jamais les
afficher. En mode série, `app.on_exercise_answer`/`_on_exercise_answer_lichess`
émettent toujours `exercise_serie_verdict` immédiatement après le verdict
Stockfish (comportement de l'étape 1, inchangé), mais ne s'arrêtent plus
là : le court-circuit (`return`) a été déplacé APRÈS la construction
complète du contexte (menace adverse, idées, détail des lignes, faits...),
identique au mode normal — même code, aucune duplication de la construction
du contexte. Une fois `messages`/`context`/`llm_config` prêts, la nouvelle
fonction `_lancer_avis_mode_serie` (`app.py`) soumet l'appel à
`llm_coach.get_coach_response` (toujours) et à `llm_coach.get_mistral_response`
(seulement si la source appelle normalement Mistral et que
`config.MISTRAL_API_KEY` est renseignée — la source « Problèmes Lichess »
n'appelle JAMAIS Mistral, mode série ou pas : préexistant, pas modifié par
cette issue) à un `ThreadPoolExecutor` dédié, `_mode_serie_executor`, borné
par la nouvelle constante nommée `MODE_SERIE_MAX_APPELS_SIMULTANES` (= 2).
Aucune copie de la logique d'appel ni du vérificateur : ce sont les mêmes
fonctions de production que le mode normal, qui gèrent déjà elles-mêmes
erreur/délai dépassé et écrivent déjà elles-mêmes au journal.

`_lancer_avis_mode_serie` ajoute `"mode_serie": True` à une COPIE du
contexte (jamais au contexte du mode normal) avant de le transmettre aux
deux fonctions : ignoré par `llm_coach._build_context_text` (donc sans
aucun effet sur le texte envoyé à l'IA — même mécanisme que le champ
`profondeur_reeval` déjà présent dans ce contexte), mais journalisé tel
quel par `_log_coach_call` (qui enregistre tout `context` reçu sous la clé
`"context"` de chaque entrée). Chaque entrée garde donc exactement les
mêmes champs qu'une entrée hors mode série (mode_origine, fiabilité,
alertes du vérificateur d'affirmations, erreur éventuelle...), plus
`context.mode_serie == True` — lisible sans modification par
`scripts/controle_avis.py`.

Compteur « avis en cours » : `_mode_serie_avis_en_cours` (protégé par
`_mode_serie_lock`) est incrémenté de façon SYNCHRONE, dans le thread qui
traite `exercise_answer`, juste AVANT chaque `_mode_serie_executor.submit(...)`
— jamais depuis le thread d'arrière-plan lui-même, pour fermer la fenêtre
entre soumission et démarrage réel où une tâche déjà promise ne compterait
pas encore comme « en cours » (bug constaté et corrigé pendant l'écriture
des tests ci-dessous : un test qui attendait le retour à 0 juste après
l'émission de `exercise_answer` pouvait croire la tâche terminée alors
qu'elle n'avait pas encore démarré, et son cleanup défaisait alors le
mock AVANT que le thread d'arrière-plan n'appelle réellement l'IA —
provoquant un vrai appel réseau avec une fausse clé, HTTP 401). Décrémenté
dans le bloc `finally` de la tâche, succès ou échec confondus — ne peut
jamais rester bloqué à une valeur positive. Diffusé à tous les clients
connectés via `socketio.emit("exercise_serie_compteur", {"avis_en_cours": N})`
(jamais `emit()`, qui exigerait un contexte de requête HTTP actif, absent
d'un thread d'arrière-plan — même raison que le thread Mistral déjà
existant du mode normal, issue #113 ; pas de salle par session, application
mono-utilisateur). Affiché côté client dans le nouvel élément
`#exercise-serie-compteur` (`templates/index.html`, sous la case « Mode
série »), mis à jour par le nouveau `socket.on("exercise_serie_compteur", ...)`
(`static/exercise.js`).

Les avis du mode série ne sont JAMAIS envoyés au navigateur comme avis
affichables : ni `exercise_comment` ni `exercise_mistral_comment` ne sont
émis pour ces appels (donc aucune bulle, aucun bouton de note, aucun
« Signaler »). Les mécanismes d'obsolescence Mistral de l'issue #114 ne
reçoivent jamais d'événement à leur propos — rien à invalider, aucune
erreur possible au changement d'exercice ou à la désactivation du mode
série. Un avis déjà soumis au `_mode_serie_executor` ne dépend d'aucune
connexion navigateur : passer à l'exercice suivant, désactiver le mode
série ou fermer l'onglet avant sa fin ne l'annule jamais.

Avis en cours à l'arrêt/au redémarrage de l'application (documenté dans
`docs/contexte/mode_serie.md`, non testé en conditions réelles) :
`_mode_serie_executor` vit uniquement en mémoire du processus, pas
persisté sur disque. Un arrêt PROPRE (Ctrl+C, fin normale) devrait laisser
les avis déjà soumis se terminer, grâce au gestionnaire `atexit` interne de
`concurrent.futures.thread` qui attend la fin de toutes les tâches de tout
`ThreadPoolExecutor` avant de quitter. Un arrêt BRUTAL (`kill -9`, crash)
perd tout avis non encore écrit au journal — exactement la même limite que
le thread Mistral déjà existant du mode normal, pas une régression
introduite par cette issue.

### Documentation

`docs/contexte/mode_serie.md` réécrite : retiré tout ce que l'étape 2 rend
faux (le court-circuit total, « état TEMPORAIRE », les numéros d'étape),
ajouté la file d'attente bornée, le compteur, le format exact des entrées
du journal et le sort des avis en cours à l'arrêt de l'application.
`CONTEXTE.md` : le passage « Mode série, étape 1/3 (issue #139...) » (6
lignes, détails d'implémentation) a été ramené à une seule ligne sans
numéro d'issue ni mention d'étape, renvoyant à la fiche ; la ligne de la
liste des fiches a été mise à jour pour refléter le nouveau contenu.

### Tests

Fichier `test_issue139_mode_serie.py` (étape 1) ADAPTÉ (pas remplacé) :
les deux tests qui vérifiaient « zéro appel IA en mode série »
(`test_..._mode_serie_zero_appel_ia`) sont devenus
`test_..._mode_serie_appelle_..._en_arriere_plan` — ils attendent
désormais la fin des appels soumis (nouveau helper
`_attendre_compteur_serie_zero`, limite de temps explicite 10s, jamais un
sleep fixe) avant de vérifier les compteurs d'appels IA (1 Claude + 1
Mistral pour « Mes erreurs », 1 Claude seul pour « Problèmes Lichess » —
Mistral n'étant jamais appelé pour cette source). Le test du cas « coup
joué = meilleur coup » attend lui aussi la fin de son appel en arrière-plan
avant la fin du test, pour ne jamais laisser un mock se défaire avant que
le thread d'arrière-plan ne l'utilise. 9 tests, tous OK.

Nouveau fichier `test_issue140_mode_serie_ia_arriere_plan.py` (4 cas),
réutilisant l'infrastructure d'isolation de `test_issue128.py`/
`test_issue139_mode_serie.py` (chemins de données temporaires), mais avec
Claude/Mistral simulés au niveau RÉSEAU (`llm_coach._call_claude`/
`_call_mistral`, pas les fonctions de plus haut niveau) pour que
`get_coach_response`/`get_mistral_response`/`_log_coach_call`/le
vérificateur d'affirmations s'exécutent réellement de bout en bout :
- cinq réponses enchaînées très vite en mode série, source « Mes erreurs »,
  IA simulées avec un délai de 150ms : le verdict en une ligne apparaît aux
  cinq exercices, le compteur « avis en cours » revient à 0, dix entrées
  apparaissent au journal (cinq par IA, Mistral activé avec une clé
  factice), toutes avec `context.mode_serie == True` et les champs
  habituels (fiabilité, alertes du vérificateur), et le nombre d'appels
  simultanés réellement observés ne dépasse jamais
  `MODE_SERIE_MAX_APPELS_SIMULTANES` ;
- même scénario pour la source « Problèmes Lichess » (cinq exercices) :
  cinq entrées au journal (Claude seul, Mistral jamais appelé pour cette
  source, comme hors mode série) ;
- une IA simulée qui lève une `TimeoutError` (délai dépassé simulé) ne
  bloque jamais le compteur (revient bien à 0) et laisse une entrée
  d'erreur au journal, avec `context.mode_serie == True` ;
- le mode normal (hors mode série) se comporte comme avant : un appel
  Claude (synchrone) + un appel Mistral (thread d'arrière-plan existant,
  issue #113, DISTINCT de `_mode_serie_executor`), avis affiché
  (`exercise_comment`), et le compteur du mode série reste à 0 — le mode
  normal ne le touche jamais.

Aucun test ignoré, désactivé ni conditionné par une variable
d'environnement dans les deux fichiers ci-dessus : Stockfish absent ferait
ÉCHOUER `setUpClass` (`RuntimeError`), jamais sauter les tests.

`pyflakes` sur tous les fichiers Python modifiés/créés (`app.py`,
`test_issue139_mode_serie.py`, `test_issue140_mode_serie_ia_arriere_plan.py`) :
aucun nom indéfini, aucun avertissement.

Régression : `test_issue128.py` (21 tests), `test_issue134.py` (28 tests),
`test_issue135.py` (26 tests), `test_issue137_signe_eval_lichess.py`
(14 tests) repassent sans régression, chacun exécuté séparément comme
l'exige leur propre en-tête — tous OK, 0 ignoré. (`test_issue134.py`
affiche deux avertissements `pyflakes` pré-existants, `re`/`chess` importés
sans usage — fichier non modifié par cette issue, hors périmètre.)

Les processus `python3 -m unittest` de ces six fichiers ne se terminent
pas toujours tout seuls après avoir affiché leur résultat (même
observation que l'étape 1, probablement un thread du client de test
Flask-SocketIO ou du sous-processus Stockfish non proprement joint) —
sortie capturée en arrière-plan avec une limite de temps explicite plutôt
que par un appel bloquant classique ; le résultat affiché (« Ran N tests
... OK ») est cependant sans ambiguïté avant ce nettoyage.

Non testé en conditions réelles : appels réels aux API Claude/Mistral
(aucune clé réelle disponible dans l'environnement de cette session —
toutes les IA sont simulées dans les tests automatisés ci-dessus),
affichage du compteur « avis en cours » sur un vrai téléphone, et
comportement à un VRAI redémarrage du serveur pendant un appel IA en mode
série (cf. section dédiée ci-dessus et `docs/contexte/mode_serie.md` — le
raisonnement sur l'atexit de `concurrent.futures.thread` n'a pas été vérifié
empiriquement, seulement déduit du code de la bibliothèque standard).
