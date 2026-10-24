## Issue #139 — Suite #125 : mode série, étape 1 (interrupteur et verdict Stockfish en une ligne)

Mode série activable/désactivable depuis l'interface de l'onglet Exercice
(case `#exercise-serie-toggle`, visible sur mobile et sur grand écran,
mémorisée par appareil dans `localStorage` — `chesscoach-exercise-mode-serie`
— désactivée par défaut). Hors case cochée, comportement strictement
identique à avant pour les deux sources (« Mes erreurs » et « Problèmes
Lichess ») : aucun changement de code n'a modifié le chemin existant, le
court-circuit série est un `return` ajouté APRÈS le calcul du verdict
Stockfish, jamais avant.

En mode série, `app.on_exercise_answer`/`_on_exercise_answer_lichess`
n'appellent NI Claude NI Mistral — zéro entrée dans `coach_calls.log` — et
émettent un seul événement `exercise_serie_verdict` avec une ligne construite
par la nouvelle fonction `_construire_ligne_verdict_serie` à partir des
données déjà calculées par `_evaluate_move_for_coach` (verdict officiel
Lichess, perte en centipions TOUJOURS positive — jamais une évaluation signée
Blancs/Noirs, pour ne pas rouvrir la question de la convention de signe
#128/#134 — et meilleur coup). Exemple : `"Verdict : gaffe (perte de 1000 cp)
— meilleur coup : Qe4+."`. Si le coup joué est le meilleur coup (perte nulle),
la ligne le dit simplement plutôt que d'afficher "(perte de 0 cp)". Côté
client, `static/exercise.js` a son propre gestionnaire pour cet événement,
distinct de `exercise_comment` : jamais de bulle d'avis, de bouton de note
ni de "Signaler", jamais de bulle "Le coach réfléchit..." ni de minuteur de
garde (aucun des deux n'est démarré pour une soumission en mode série) — la
ligne s'affiche dans `#exercise-status`, déjà l'emplacement des messages
d'état transitoires de l'exercice. L'historique des exercices et le niveau
Elo-like des catégories Lichess restent mis à jour comme hors mode série
(seuls les appels aux IA sont court-circuités).

Correctif connexe découvert en implémentant le court-circuit : dans
`on_exercise_answer`/`_on_exercise_answer_lichess`, les variables
`verdict_qualite_officiel` (et, pour `on_exercise_answer`, `eval_before_cp`/
`eval_after_cp`/`win_prob_drop`) n'étaient initialisées qu'À L'INTÉRIEUR du
bloc `if move in board.legal_moves:` — un coup illégal ou Stockfish
indisponible (ce bloc jamais atteint) aurait levé une `NameError` à leur
première lecture plus bas, au lieu du verdict absent déjà géré proprement
par le reste de ces deux fonctions. Initialisées désormais à `None` au même
niveau que les autres variables de verdict. Aucun comportement visible
changé (ce chemin n'était vraisemblablement jamais atteint en usage normal,
l'interface ne proposant que des coups légaux), mais nécessaire pour que le
nouveau court-circuit du mode série reste robuste même dans ce cas limite.

Comportement TEMPORAIRE et noté comme tel dans le code et dans
`docs/contexte/mode_serie.md` : l'absence d'appel aux IA en mode série n'est
PAS la forme finale voulue — les appels en arrière-plan avec file d'attente
et compteur viennent à l'étape 2 de l'issue #139, les tests de charge et la
fiche détaillée de bout en bout à l'étape 3.

Tests : nouveau fichier `test_issue139_mode_serie.py` (9 cas), exécutant le
VRAI gestionnaire de réponse d'exercice via le client de test Flask-SocketIO
(infrastructure de `test_issue128.py`, chemins de données temporaires, API
Claude/Mistral simulées, Mistral activé avec une clé factice pour prouver
qu'il est lui aussi bloqué) : zéro appel aux IA et un `exercise_serie_verdict`
en mode série (scénario déterministe — Dame laissée en prise par un coup de
Roi, vérifié au préalable directement avec Stockfish : `qualite_officielle=
"gaffe"`, `delta_cp` plafonné à 1000 — et scénario où le coup joué EST le
meilleur coup, `delta_cp=0`), un appel Claude et un `exercise_comment`
classique hors mode série ou si le champ `mode_serie` est absent
(compatibilité avec un ancien client), pour les deux sources. Aucun test
ignoré, désactivé ni conditionné par une variable d'environnement : Stockfish
absent ferait ÉCHOUER `setUpClass` (`RuntimeError`), jamais sauter les tests
— volontairement différent de `@unittest.skipUnless` utilisé par les issues
précédentes. `test_issue128.py`/`test_issue134.py`/`test_issue135.py`/
`test_issue137_signe_eval_lichess.py` repassent sans régression (exécutés
chacun séparément, comme l'exige leur propre en-tête : 21+28+26+14 tests,
tous OK, 0 ignoré). Les processus `python3 -m unittest` de ces cinq fichiers
ne se terminent pas toujours tout seuls après avoir affiché leur résultat
(probablement un thread du client de test Flask-SocketIO ou du sous-processus
Stockfish non proprement joint) — sortie capturée en arrière-plan avec un
délai d'attente plutôt que par un appel bloquant classique, puis processus
nettoyés manuellement ; le résultat affiché (「Ran N tests ... OK」) est
cependant sans ambiguïté avant ce nettoyage.

Non testé en conditions réelles : affichage de la case et de la ligne de
verdict sur un vrai téléphone (taille de police, retour à la ligne de la
ligne de verdict dans `#exercise-status` sur petit écran) — seule la logique
serveur/socket a été vérifiée par les tests automatisés ci-dessus.

Documentation : une ligne dans `CONTEXTE.md` (section Invariants et pièges)
renvoyant à la nouvelle fiche `docs/contexte/mode_serie.md` (interrupteur,
comportement serveur, comportement client, rappel explicite du caractère
temporaire de l'étape 1). Aucun passage existant de `CONTEXTE.md` ou de
`docs/contexte/*.md` n'était rendu faux par cette issue (vérifié).

Hors périmètre, non touché : prompt système, format standard des avis,
contrôles du vérificateur (`fact_checker.py`), convention de signe, file
d'attente/compteur "avis en cours". Aucun push effectué.
