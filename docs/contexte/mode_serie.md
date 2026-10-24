# Mode série (issue #139/#140, suite #125)

Besoin d'Alain : pendant une série d'exercices qu'il relit ensuite à
l'ordinateur à partir du journal, attendre les avis des deux IA (Claude +
Mistral) coûte une dizaine de secondes par exercice sans lui servir sur le
moment — il veut le verdict Stockfish affiché tout de suite, et les avis des
deux IA enregistrés dans `coach_calls*.log` pour plus tard, sans jamais les
attendre ni les lire pendant la série elle-même.

## Interrupteur (static/exercise.js)

`exerciseModeSerie` (booléen, désactivé par défaut) — mémorisé par appareil
dans `localStorage` sous la clé `chesscoach-exercise-mode-serie`
(`_exerciseSerieLoad`/`_exerciseSerieSave`/`_exerciseSerieToggle`), appliqué
au chargement de la page (`DOMContentLoaded`) et piloté par la case à cocher
`#exercise-serie-toggle` dans le panneau de l'onglet Exercice
(`templates/index.html`, visible aussi bien sur mobile que sur grand écran —
pas dans le menu "..." global `#game-menu-dropdown`, qui n'existe que pour
les 4 modes de partie, cf. CSS `#mobile-mode-bar-slot`). `submitExerciseAnswer`
transmet sa valeur courante au serveur avec chaque `exercise_answer` (champ
`mode_serie`) et, si actif, n'affiche ni la bulle "Le coach réfléchit..." ni
le minuteur de garde de 30s (`_exerciseStartAnalysisWatchdog`) — tous deux
inutiles côté interface puisqu'aucun avis n'y est jamais affiché, même si les
IA sont réellement appelées côté serveur (cf. ci-dessous).

## Comportement serveur (app.py) : verdict immédiat, avis en arrière-plan

`on_exercise_answer` (source "mes_erreurs"/"position_precise") et
`_on_exercise_answer_lichess` (source "lichess") lisent `data["mode_serie"]`
une seule fois, juste après avoir calculé le verdict Stockfish du coup
proposé (`_evaluate_move_for_coach`, le même calcul qu'hors mode série).
S'il est vrai :
1. un seul événement est émis IMMÉDIATEMENT, `exercise_serie_verdict`,
   construit par `_construire_ligne_verdict_serie(verdict_qualite_officiel,
   verdict_delta_cp, meilleur_coup)` (détail des champs ci-dessous) ;
2. le traitement NE s'arrête PAS là : le reste du contexte (menace adverse,
   idées détectées, détail des lignes, faits python-chess...) continue
   d'être construit exactement comme hors mode série — même code, aucune
   duplication ;
3. une fois `messages`/`context`/`llm_config` prêts, `_lancer_avis_mode_serie`
   (défini une seule fois, utilisé par les deux sources) soumet l'appel à
   Claude (`llm_coach.get_coach_response`, toujours) et à Mistral
   (`llm_coach.get_mistral_response`, SEULEMENT si la source appelle
   normalement Mistral ET que `config.MISTRAL_API_KEY` est renseignée — le
   mode série respecte la configuration existante, il ne l'étend pas : la
   source "lichess" n'appelle JAMAIS Mistral, mode série ou pas, c'est
   préexistant et hors périmètre de cette issue) à `_mode_serie_executor`,
   puis retourne sans émettre `exercise_comment` ni
   `exercise_mistral_comment`.

`_lancer_avis_mode_serie` ajoute `"mode_serie": True` à une COPIE du
`context` (jamais au `context` du mode normal) avant de le transmettre aux
deux fonctions ci-dessus : cette clé est ignorée par
`llm_coach._build_context_text` (donc sans aucun effet sur le texte
réellement envoyé à l'IA — même mécanisme que le champ "profondeur_reeval"
du contexte), mais elle est journalisée telle quelle par
`llm_coach._log_coach_call`, qui enregistre tout `context` reçu sous la clé
`"context"` de chaque entrée. Chaque entrée du journal garde donc EXACTEMENT
les mêmes champs qu'une entrée hors mode série (mode_origine, fiabilité,
alertes du vérificateur d'affirmations, erreur éventuelle...), avec en plus
`entry["context"]["mode_serie"] == True` — lisible sans modification par
`scripts/controle_avis.py`, qui ne lit que des clés qu'il nomme
explicitement et ignore les autres.

Aucune copie de la logique d'appel ni du vérificateur : `get_coach_response`/
`get_mistral_response` sont les mêmes fonctions de production que le mode
normal, qui gèrent déjà elles-mêmes erreur et dépassement de délai (elles
catchent `TimeoutError`/`URLError`/`HTTPError`... et écrivent une entrée
d'erreur au journal avant de revenir normalement, jamais de levée
d'exception dans le cas attendu).

### File d'attente bornée et compteur "avis en cours"

`MODE_SERIE_MAX_APPELS_SIMULTANES` (= 2, constante nommée et documentée en
tête de sa définition dans `app.py`) borne le nombre d'appels IA simultanés
exécutés par `_mode_serie_executor` (un `ThreadPoolExecutor`, Claude et
Mistral confondus, toutes sources confondues) — les appels excédentaires
patientent dans sa file FIFO (une tâche soumise à un `ThreadPoolExecutor` en
démarre une autre dans son ordre de soumission dès qu'un emplacement se
libère), jamais annulés, juste retardés.

`_mode_serie_avis_en_cours` (protégé par `_mode_serie_lock`) est incrémenté
de façon SYNCHRONE, dans le thread qui traite `exercise_answer`, juste avant
chaque `_mode_serie_executor.submit(...)` — jamais depuis le thread
d'arrière-plan lui-même : entre la soumission et le premier instant où le
pool exécute réellement la tâche, celle-ci doit déjà compter comme "en
cours", sans quoi un appelant qui attend que le compteur retombe à 0
pourrait conclure à tort que tout est terminé alors qu'une tâche vient
juste d'être mise en file. Il est décrémenté dans le bloc `finally` de la
tâche, succès ou échec confondus, donc il ne peut jamais rester bloqué à une
valeur positive une fois tous les appels soumis réellement terminés — un
appel qui échoue (erreur ou délai dépassé) décrémente le compteur exactement
comme un appel réussi, après avoir laissé son entrée d'erreur au journal
(cf. ci-dessus).

Le compteur est diffusé à tous les clients connectés via
`socketio.emit("exercise_serie_compteur", {"avis_en_cours": N})` (jamais
`emit()`, qui exigerait un contexte de requête HTTP actif, absent d'un
thread d'arrière-plan — même raison que le thread Mistral déjà existant du
mode normal, issue #113) ; aucune salle par session, application
mono-utilisateur (cf. CONTEXTE.md). Affiché côté client dans
`#exercise-serie-compteur` (`templates/index.html`, juste sous la case
"Mode série"), mis à jour par `socket.on("exercise_serie_compteur", ...)`
(`static/exercise.js`) : Alain sait qu'il peut quitter l'application sans
rien perdre quand ce compteur affiche 0.

### Verdict immédiat (champs de `exercise_serie_verdict`, inchangé depuis #139)

- `verdict_qualite_officiel` ("bon"/"imprecision"/"erreur"/"gaffe", méthode
  Lichess — cf. fiche `classification_coups`) et `verdict_delta_cp` (perte en
  centipions du coup joué, **toujours positive**, jamais une évaluation
  signée Blancs/Noirs — cf. invariant de convention de signe, fiche
  `convention_signe`) viennent tous les deux de `_evaluate_move_for_coach`,
  déjà calculés pour construire le contexte hors mode série ;
- `meilleur_coup` est le MÊME champ que celui déjà affiché/transmis hors
  mode série — recalculé par Stockfish pour "mes_erreurs"/"position_precise",
  mais le premier coup de la solution déclarée du problème pour "lichess"
  (jamais recalculé indépendamment, cf. commentaire existant de
  `_on_exercise_answer_lichess` : "la solution fait foi") ;
- si `verdict_delta_cp` vaut 0 (le coup joué EST le meilleur coup), la ligne
  le dit simplement ("c'est le meilleur coup") plutôt que d'afficher
  "(perte de 0 cp)" ;
- si l'analyse Stockfish est indisponible (`verdict_qualite_officiel` ou
  `verdict_delta_cp` absent), la ligne l'indique au lieu d'inventer un
  verdict.

Exemple : `"Verdict : gaffe (perte de 1000 cp) — meilleur coup : Qe4+."`

L'historique des exercices (`exercise_history.enregistrer_resultat`) et le
niveau Elo-like des catégories Lichess (`lichess_puzzles.mettre_a_jour_niveau`)
sont mis à jour en mode série exactement comme hors mode série, et
indépendamment des appels IA en arrière-plan (ils ne dépendent jamais de
leur résultat).

## Côté client (static/exercise.js, templates/index.html)

`socket.on("exercise_serie_verdict", ...)` est un gestionnaire DISTINCT de
`exercise_comment` : il n'appelle jamais `_coachRenderBubbleWithAgent` (donc
aucune bulle d'avis, aucun bouton de note, aucun bouton "Signaler" — les
avis du mode série ne sont JAMAIS envoyés au navigateur comme avis
affichables, cf. ci-dessus), ne démarre ni ne nettoie aucun minuteur
"réfléchit" (jamais démarrés pour cette tentative), et affiche la ligne de
verdict dans `#exercise-status` — le même emplacement que les messages
d'état transitoires existants ("Fais ton coup.", "Verdict rendu...") plutôt
qu'un élément qui s'accumule indéfiniment comme le ferait une bulle du chat.
Il pose `exerciseExploring`/`exerciseVerdictObtenu` à vrai comme
`exercise_comment`, donc le bouton "Exercice suivant" et le plateau
explorable sont disponibles immédiatement, sans attendre quoi que ce soit —
ni le verdict Stockfish (déjà là), ni les avis des IA (qui continuent en
arrière-plan, indépendamment de la navigation d'Alain, cf. ci-dessous).
Désactiver le mode série en cours d'exercice ou passer à l'exercice suivant
n'affecte pas ces gestionnaires : chaque soumission relit la valeur courante
de `exerciseModeSerie`, et `exercise_position` réinitialise déjà tout l'état
par exercice (dont les mécanismes d'obsolescence Mistral de l'issue #114,
qui ne reçoivent jamais d'événement à propos d'un avis de mode série — rien
à invalider, donc aucune erreur possible à ce changement d'exercice).

## Avis en cours à l'arrêt ou au redémarrage de l'application

Un avis en mode série déjà SOUMIS à `_mode_serie_executor` ne dépend
d'aucune connexion navigateur : passer à l'exercice suivant, désactiver le
mode série ou fermer l'onglet avant sa fin ne l'annule jamais — seul l'arrêt
du PROCESSUS serveur lui-même peut l'interrompre.

`_mode_serie_executor` est un `ThreadPoolExecutor` standard, dont l'état
(file d'attente, tâches en cours) vit uniquement en mémoire du processus
Python — il n'est pas persisté sur disque. `concurrent.futures.thread`
enregistre un gestionnaire `atexit` qui attend la fin de toutes les tâches
déjà soumises à TOUT `ThreadPoolExecutor` avant de laisser l'interpréteur
se terminer normalement (Ctrl+C propre, fin normale du script) : un arrêt
PROPRE du serveur devrait donc laisser les avis déjà soumis se terminer
(et s'écrire dans `coach_calls.log`) avant de quitter. Un arrêt BRUTAL
(`kill -9`, coupure d'alimentation, crash du processus) perd en revanche
tout avis non encore écrit au journal au moment de l'arrêt — exactement la
même limite que le thread Mistral déjà existant du mode normal (issue
#113), pas une régression introduite par le mode série. Ce point n'a pas
été vérifié en conditions réelles (pas de redémarrage réel du serveur
pendant un appel IA en mode série, cf. rapport de clôture de l'issue #140).
