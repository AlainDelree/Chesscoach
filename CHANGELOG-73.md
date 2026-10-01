# Changelog — Issue #73

## Mode exercices : questions de suivi avec la bonne position, évaluations du point de vue d'Alain, verdict du coach non contredit

- Cause des trois défauts constatés en usage réel (Haiku, exercice fxg4 sur
  r4rk1/pp2n1pp/8/3p1p2/4p1B1/8/P1R2qPP/3QR2K b - - 3 26) :
  - Le contexte transmis au coach (`llm_coach._build_context_text`) ne
    distinguait jamais la position de DÉPART de l'exercice de la position
    ACTUELLEMENT affichée sur l'échiquier — une question de suivi posée
    dans le chat libre pendant l'exercice (`coach_ask`) transmettait
    uniquement le FEN courant (`exerciseGame.fen()`, déjà après le coup
    proposé), jamais le FEN de départ, ce qui a fait nier au coach la
    présence d'un fou pourtant bien présent avant le coup.
  - Les évaluations centipawns (`eval_blancs_cp`/`eval_mat`) étaient
    transmises "point de vue des Blancs" (positif = avantage Blancs),
    signe ambigu dès qu'Alain joue les Noirs — un -131 a déjà été lu par
    le coach comme "légèrement en faveur des Blancs" alors qu'il
    signifiait +131, un avantage pour Alain.
  - Le mode exercice ne réutilisait pas `game_facts.describe_move_
    mechanically` (issue #66, déjà utilisé par le mode "analyse_partie")
    pour décrire les trois coups comparés (proposé/réel/meilleur) : seule
    une fonction locale `_move_details_fr` (app.py), donnant juste le type
    de pièce jouée/capturée sans défenseur ni solde net, était utilisée.
- Correctifs (app.py, llm_coach.py, static/exercise.js) :
  - `on_exercise_answer` transmet désormais `fen_depart_exercice` (position
    de départ) ET `fen` (position actuelle, après le coup proposé),
    séparément étiquetées dans `_build_context_text` — avec une consigne
    explicite de ne jamais conclure qu'une pièce "n'existe pas" sans
    comparer les deux. Le serveur retransmet ces deux FEN, les descriptions
    mécaniques des trois coups et l'évaluation au client dans le payload
    `exercise_comment` ; `exerciseChatContextExtra()` (exercise.js) les
    réinjecte dans toute question de suivi posée ensuite dans le chat
    libre, verdict compris ou en exploration libre.
  - Nouvelle fonction `_vers_point_de_vue_alain` (app.py), appliquée aux
    5 points de contexte transmettant une évaluation Stockfish (exercice,
    pédagogique, ouverture, finales, "Demander l'avis du coach") : le
    contexte ne transmet plus que `eval_alain_cp`/`eval_alain_mat`
    (positif = avantage pour Alain), plus aucun chiffre dont le signe
    dépend de la couleur.
  - `_move_details_fr`/`_parse_move_flexible`/`_PIECE_FR` (app.py)
    supprimées, remplacées par trois appels à `game_facts.
    describe_move_mechanically` (coup proposé, coup réel, meilleur coup),
    calculés depuis la position de départ — mêmes informations
    (défenseur, solde net après reprise, pièces désormais attaquées) que
    le mode "analyse_partie".
  - `_EXERCISE_SYSTEM_ADDENDUM` (llm_coach.py) renforcé : le verdict fait
    foi et ne doit jamais être présenté comme bon/solide même si Alain
    reste mieux dans l'absolu (consigne explicite de le dire dans ce cas :
    "tu restes mieux, mais tu laisses filer l'essentiel de ton avantage"),
    le coach doit énoncer le verdict en premier, et ne doit jamais
    conclure qu'une pièce/case "n'existe pas" sans comparer position de
    départ et position actuelle.
- Point 4 (examen sans correction, cf. rapport de clôture de l'issue) : le
  coup réellement joué à l'époque (Qh4) sur cette position précise est
  quasi équivalent au meilleur coup à partir de depth=16 (delta ≤ 40cp),
  mais apparaît comme une "erreur" (148cp de perte) à depth=10, la
  profondeur utilisée par `build_patterns_erreurs.py` pour qualifier les
  positions d'exercice — un probable artefact d'instabilité de recherche à
  faible profondeur plutôt qu'une vraie gaffe, jamais revalidé à une
  profondeur plus élevée avant inclusion dans `erreurs_detectees.json`.
