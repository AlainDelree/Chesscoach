# Changelog — Issue #64

## Chat coach : isoler chaque partie (ne plus mélanger les échanges de deux parties successives)

- Cause confirmée : `_coachHistory` (tableau JS global, `static/board.js`)
  accumulait tous les échanges du chat depuis le dernier clic sur "Effacer"
  et était renvoyé **en entier** à l'API à chaque question (`coachSend()`),
  quel que soit le nombre de parties/exercices joués entre-temps. Aucun des
  points d'entrée « nouvelle partie » (`startFreeGameFromFen`,
  `startPedagogicGame`, `startOpeningGame`, `loadSelectedFinale`/
  `startFinaleDemo`, chargement d'une autre partie en revue de bibliothèque
  `parsePgn`) ne réinitialisait cet historique — seul `startExercise()` le
  faisait, via `coachClear()`, qui efface aussi tout l'affichage (pas le
  comportement demandé). Reproduit le constat de l'issue : questions/
  réponses de la partie 1 encore présentes dans les messages envoyés à
  l'API pour une question posée sur la partie 2.
- `static/board.js` : nouveau point de coupure `coachNewSegment(label)` —
  insère un séparateur discret (`.coach-separator`, "Nouvelle partie"/
  "Nouvel exercice") dans l'affichage seulement s'il y a déjà des messages
  depuis le précédent segment (pas de trait vide au tout premier segment, ni
  de traits empilés), et avance `_coachSegmentStart` (index dans
  `_coachHistory`) + horodate `_coachSegmentStartedAt`. `coachSend()` ne
  transmet plus que `_coachHistory.slice(_coachSegmentStart)` — l'affichage
  garde tout, l'API ne reçoit que le segment courant. `coachClear()` (bouton
  "Effacer") reste inchangé dans son effet (vide tout, y compris le
  segment). `coachBuildContext()` ajoute `nb_coups`/`debut_partie` au
  contexte (branche mode interactif ET branche revue de bibliothèque).
- `static/controls.js` : `activeModeGameState()` expose désormais `nbCoups`
  (longueur de `game.history()`), lu par `coachBuildContext()`.
- `static/free_play.js`, `pedagogic.js`, `opening.js`, `finales.js`
  (`loadSelectedFinale` ET `startFinaleDemo`) : appel de
  `coachNewSegment("Nouvelle partie")` juste après `ensureModeSwitchClean()`,
  au tout début de chaque fonction de démarrage de partie/finale — c'est le
  point déjà exécuté systématiquement à chaque nouvelle partie, y compris
  quand `activeMode` ne change pas d'un mode à l'autre (`ensureModeSwitchClean`
  seul ne suffisait pas : il ne nettoie l'ancien mode que lors d'une bascule
  vers un mode *différent*, pas quand une 2e partie démarre dans le même
  mode — exactement le scénario de l'issue).
- `static/exercise.js` (`startExercise`) : remplace `coachClear()` par
  `coachNewSegment("Nouvel exercice")` — un nouvel exercice repart avec un
  historique API vide comme avant, mais n'efface plus l'affichage des
  exercices précédents (changement de comportement demandé par l'issue).
- `static/board.js` (`parsePgn`) : `coachNewSegment("Nouvelle partie")`
  ajouté après `ensureModeSwitchClean("library")` — couvre à la fois
  l'import d'un fichier PGN local et le chargement d'une partie de la
  bibliothèque (`pgn_lib_game_loaded`, `pgn_library.js`, qui appelle la même
  fonction `parsePgn`).
- `static/board.css` : nouvelle classe `.coach-separator` (ligne fine de
  chaque côté, texte discret centré, `--cc-text-muted`/`--cc-neutral-200`,
  cohérente avec la palette existante).
- `llm_coach.py` :
  - `_SYSTEM_PROMPT` complété d'une consigne permanente d'isolation : ne
    jamais reprendre un coup/numéro de coup/situation absent du PGN ou du
    bloc de faits de la partie identifiée dans CET appel, même mentionné
    plus tôt dans la conversation affichée ; dire explicitement que
    l'information est absente plutôt que l'inventer.
  - `_build_context_text` : nouveau bloc "Identification de la partie/
    l'exercice actuellement discuté(e)" en tête du contexte (mode, nombre de
    coups déjà joués, heure de début du segment courant — champs
    `mode_origine`/`nb_coups`/`debut_partie` du contexte, désormais transmis
    par `coachBuildContext()`), avec consigne explicite d'ignorer tout
    message affiché plus haut qui évoquerait une partie différente.
- Audit des autres états pouvant fuiter d'une partie à l'autre (point 4 de
  la tâche) :
  - `_stockfish_check_cache` (`app.py`) : déjà clé par `(camp_alain, pgn)` —
    le PGN complet change dès la 1re différence entre deux parties, donc
    déjà isolé par construction. Aucune correction nécessaire.
  - `_gameAnalysisResults`/coups flagués de l'analyse mécanique
    (`game_analysis.js`, `_coachAnalysisFlaggedMoves` dans `board.js`) :
    déjà comparés coup à coup (mêmes SAN, même ordre, même longueur) à la
    partie réellement en cours avant transmission — retourne `[]` en cas de
    moindre différence. Aucune correction nécessaire, comportement déjà
    sûr.
  - État serveur de l'exercice (`_current_exercise`, `app.py`) et état
    client (`exerciseVerdictObtenu`, `_exerciseResetCoachLines()`, etc.,
    `exercise.js`) : déjà réinitialisés à chaque `exercise_new`/
    `startExercise()`. Aucune correction nécessaire.
  - `coach_memory.json` (patterns d'erreurs, objectifs courants) : fuite
    volontaire et documentée (mémoire de progression du coach d'une session
    à l'autre) — hors périmètre de ce bug, pas une régression.
- Tests exécutés (voir détails de la réponse de clôture) : aucun appel API
  réel possible depuis ce worktree (pas de `.env`, `ANTHROPIC_API_KEY` non
  défini) — vérifié à la place via deux harnais hors-réseau chargeant le
  vrai code : (1) `static/board.js` exécuté dans un bac à sable Node (vm)
  avec chess.js réel, scénario partie A (question posée) → partie B
  (question posée) en revue de bibliothèque : messages/contexte envoyés
  pour B ne contiennent aucune trace de A (ni "coup 30", ni le coup `Bb5`
  propre à A), PGN/nb_coups corrects pour B, séparateur "Nouvelle partie"
  bien inséré à l'écran, `coachClear()` remet bien tout à zéro ; (2)
  `llm_coach.get_coach_response`/`_build_context_text` appelés directement
  (venv `~/ChessCoach/venv`, `_call_claude` neutralisé pour éviter tout
  appel réseau) : system prompt + contexte + entrée journalisée dans
  `coach_calls.log` vérifiés champ par champ, rien de la partie A.
  Non testé : un serveur ChessCoach tournait déjà sur le port 5000 au
  moment de la vérification (process pré-existant, pas lancé par cette
  tâche) — pas de vérification visuelle du séparateur en émulation
  mobile/desktop dans un vrai navigateur, pour ne pas risquer d'interférer
  avec une session déjà active d'Alain (parties/exercices réels, compteur
  de tokens, bibliothèque PGN). Le rendu du séparateur a été relu dans le
  CSS/JS mais pas vérifié à l'écran — à confirmer par Alain à l'occasion
  d'un usage normal.
