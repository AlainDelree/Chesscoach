# Changelog — Issue #75

## Mode exercices (suite) : verdict fiable (mats, positions décidées), grands nombres en mots, lignes principales décrites, qualité des positions proposées

Suite de l'issue #73, à partir d'un audit de 18 appels réels du mode
exercices (15 exercices, Haiku) vérifiés avec Stockfish.

- **Grands nombres cités comme des pions** (`engine_stockfish.py`,
  `game_facts.py`, `llm_coach.py`) : `EngineManager.evaluate_move` ne
  plafonnait jamais `delta_cp` (contrairement à `build_patterns_erreurs.py`/
  `_analyse_full_game`), et `_eval_blancs_apres` (app.py) transmet un score
  Stockfish brut, non borné — dans une position de gain forcé pas encore
  détectée comme un mat, Stockfish peut reporter plusieurs milliers de
  centipawns (constat réel : 19974/3456 cp cités "+199,74"/"+34,56" pions).
  `game_facts.describe_eval_alain_cp_clause`/`describe_perte_cp_clause`
  (nouveau seuil `SEUIL_GRANDE_VALEUR_CP = 1000`, même valeur que
  `SEUIL_DEJA_DECISIF`/`SEUIL_DECIDE`) reformulent désormais en mots
  ("position gagnée de façon forcée pour Alain"/"perte d'une ampleur
  extrême...") toute évaluation ou perte au-delà de ce seuil, jamais le
  chiffre brut — utilisées par `_build_context_text` pour `eval_alain_cp`/
  `verdict_delta_cp`, et par `build_game_facts_text` pour `perte_cp`.
  `_EXERCISE_SYSTEM_ADDENDUM` interdit désormais explicitement au coach
  d'inventer un chiffre pour remplacer une formulation en mots, même si
  Alain le demande explicitement.

- **Verdict faux sur un mat** (`engine_stockfish.py`, point 2a) : cause
  racine identifiée dans `EngineManager.evaluate_move` — dès que
  l'évaluation APRÈS le coup était un score de mat (`cp_apres is None`),
  l'ancien code renvoyait toujours `"bon", 0`, sans jamais vérifier de QUEL
  côté était ce mat. Un coup qui permet un mat forcé CONTRE le joueur
  (ex. `Ra8` dans `3Bk3/R6p/8/2pb4/7P/6P1/1r3P2/6K1 w - - 3 31`, qui autorise
  `Rb1+ Kh2 Rh1#`) recevait donc le même verdict `"bon"` qu'un coup qui mate
  l'adversaire. Réécriture complète sur un barème unique mat/cp
  (`_score_valeur_joueur`, formule `mate_score=100000` déjà utilisée par
  `build_patterns_erreurs.py`/`_analyse_full_game`), avec vérification
  explicite du signe du score de mat après coup (`qualite = "blunder"`,
  `delta_cp = DELTA_CP_MAT_CONTRE = 9999`, sentinelle hors échelle).

- **Verdicts trop sévères en position déjà décidée** (`engine_stockfish.py`,
  point 2b) : nouveau seuil `SEUIL_DECIDE = 600` — un coup qui conserve un
  avantage supérieur à ce seuil pour le joueur, avant ET après le coup, est
  désormais ramené à `"imprecision"` au plus, jamais `"erreur"`/`"blunder"`
  (ex. `Rf6+` dans `8/1p3kpp/3rr3/1R3K2/8/8/8/8 b - - 5 48`, position déjà
  +9,1 pour Alain, n'est plus "erreur"). Ce garde-fou ne s'applique JAMAIS
  quand le coup fait basculer vers un mat forcé contre le joueur (point 2a
  prioritaire).

- **Lignes principales racontées de mémoire** (`game_facts.py`, point 3) :
  nouvelles fonctions `describe_pv_with_balance`/`format_pv_with_balance`,
  qui décrivent mécaniquement (`_decrit_coup_mecanique`, déjà utilisée par
  `describe_move_mechanically`) chacun des 4 premiers demi-coups d'une ligne
  principale ET le solde matériel CUMULÉ pour Alain après chaque demi-coup
  (`_materiel_alain`) — ex. `Qh8+ Ke7 Qxd8+ Kxd8` dans
  `3q1k2/5p2/1p6/1P2Q3/8/5P2/6P1/6K1 w - - 7 47` affiche un solde qui revient
  à +1 après le dernier coup, identique à avant la séquence : un échange de
  dames, pas un gain net. `on_exercise_answer` (app.py) calcule ce détail
  pour `pv_coup_propose`/`pv_meilleur_coup` et le transmet dans le contexte
  (`pv_*_detail`) et au client (`exercise_comment`, `exerciseChatContextExtra`
  dans exercise.js). `_EXERCISE_SYSTEM_ADDENDUM` interdit au coach d'annoncer
  un gain/perte de pièce sur une ligne si ce solde cumulé ne le confirme pas.

- **Qualité des positions proposées** (point 4) :
  - `build_patterns_erreurs.py` : nouvelle fonction `_revalider_erreur`,
    appelée sur chaque candidat `"erreur"`/`"blunder"` détecté en première
    passe (profondeur `PROFONDEUR = 10`, choix de vitesse) avant écriture
    dans `erreurs_detectees.json` — réévalue à `DEPTH_ANALYSE_PARTIE` (16,
    déjà utilisée par "Analyser cette partie") et écarte le candidat si le
    coup réel perd moins d'~100cp par rapport au meilleur coup à cette
    profondeur (seuil déjà intégré à `classifier_coup`, pas de constante
    redondante), ou si la position reste décidée dans le MÊME sens avant et
    après le coup (`SEUIL_DECIDE = 600`, gagnant ou perdant). Testé sur la
    position Qh4 citée dans l'issue (`r4rk1/pp2n1pp/8/3p1p2/4p1B1/8/
    P1R2qPP/3QR2K b - - 3 26`) : écartée (confirmé ci-dessous).
  - Nouveau script `revalider_erreurs_detectees.py` (livré, PAS exécuté sur
    les données réelles) : revalide un `erreurs_detectees.json` déjà
    existant avec `build_patterns_erreurs._revalider_erreur`, sauvegarde
    automatique horodatée de l'ancien fichier avant toute écriture, résumé
    conservées/écartées. Commande à lancer (après sauvegarde automatique) :
    `python3 revalider_erreurs_detectees.py`
  - `_EXERCISE_SYSTEM_ADDENDUM` (prompt) : quand le coup réel était
    pratiquement aussi bon que le coup de référence (verdict `"bon"`/
    `"imprecision"`), le texte du contexte le dit déjà explicitement (verdict
    qui "fait foi") — pas de changement de prompt séparé nécessaire, le
    garde-fou de point 2b couvre aussi ce cas en amont (une position qui
    reste décidée identiquement des deux côtés n'est de toute façon plus
    classée erreur par le correctif ci-dessus).

- **Bouton "Demander l'avis du coach" pendant un exercice** (point 5,
  `static/board.js`, `static/exercise.js`, `app.py`) : ce bouton
  (`askExerciseCoach` → `askCoachOnDemand` → `coach_comment_on_demand`) ne
  transmettait que `fen`/`camp_alain`, contrairement à une question posée
  dans le chat libre pendant le même exercice (`coachBuildContext`, qui
  fusionne déjà `exerciseChatContextExtra()`). `askCoachOnDemand` accepte
  désormais un 4e paramètre optionnel `extraContext`, fusionné dans le
  payload envoyé ; `askExerciseCoach` lui passe `exerciseChatContextExtra()`.
  Côté serveur, `on_coach_comment_on_demand` fusionne ces champs
  supplémentaires dans le contexte transmis au coach (`mode_exercice`,
  `fen_depart_exercice`, descriptions mécaniques, verdict, PV détaillées) —
  `meilleur_coup`/`eval_alain_cp`/`eval_alain_mat` de l'exercice (profondeur
  `DEPTH_EXERCICE_TEMPS_REEL`) priment sur le calcul générique du handler
  (profondeur 8) quand disponibles. Les autres modes (pédagogique,
  ouverture, finales) gardent leur comportement inchangé (`extraContext`
  absent).

### Seuils retenus

| Constante | Valeur | Rôle |
|---|---|---|
| `SEUIL_GRANDE_VALEUR_CP` (game_facts.py) | 1000 cp | au-delà, évaluation/perte reformulée en mots |
| `SEUIL_DECIDE` (engine_stockfish.py) | 600 cp | position "déjà décidée" (point 2b), avant ET après |
| `DELTA_CP_PLAFOND` (engine_stockfish.py) | 1000 cp | plafond générique du delta reporté (hors mat) |
| `DELTA_CP_MAT_CONTRE` (engine_stockfish.py) | 9999 cp | sentinelle dédiée : mat forcé contre le joueur |
| seuil de perte "pas une vraie erreur" (build_patterns_erreurs.py) | ~100 cp | déjà intégré à `classifier_coup` (`SEUIL_IMPRECISION`), pas de nouvelle constante |

### Vérifications effectuées (Stockfish réel, `/usr/games/stockfish`, depth=18)

- `3Bk3/R6p/8/2pb4/7P/6P1/1r3P2/6K1 w - - 3 31`, `Ra8` : **avant** `"bon"`,
  `delta=0` → **après** `"blunder"`, `delta=9999`, `eval_alain_mat=-2`
  ("mat forcé en 2 coup(s) en faveur de l'adversaire" dans le texte envoyé
  au coach, jamais un chiffre). `Kh2` (même position) reste `"blunder"`,
  `delta≈403-431` (pas de changement : perte réelle, pas un faux positif).
- `8/1p3kpp/3rr3/1R3K2/8/8/8/8 b - - 5 48`, `Rf6+` : **avant** `"erreur"`,
  `delta=100` → **après** `"imprecision"`, `delta=1000` (position déjà
  décidée, +9,1 avant et après).
- `3q1k2/5p2/1p6/1P2Q3/8/5P2/6P1/6K1 w - - 7 47`, `Qh8+` : `"bon"`,
  `delta=0` (coup déjà correctement classé ; le nouveau détail coup par coup
  montre le solde cumulé pour Alain revenant à +1 après `Qxd8+ Kxd8`,
  confirmant l'échange de dames plutôt qu'un gain).
- `describe_eval_alain_cp_clause(19974)` → "position gagnée de façon forcée
  pour Alain (valeur extrême...)" ; `describe_perte_cp_clause(9999)` →
  "perte d'une ampleur extrême..." (jamais de chiffre).
- `revalider_erreurs_detectees.py` sur un fichier de test à 2 entrées
  (jamais sur les données réelles) : la position Qh4
  (`r4rk1/pp2n1pp/8/3p1p2/4p1B1/8/P1R2qPP/3QR2K b - - 3 26`) est écartée
  (1 conservée, 1 écartée) ; la position `Ra8` (vraie gaffe) est conservée,
  reclassée `"blunder"`.
- Contexte exact envoyé au coach (`llm_coach._build_context_text`) vérifié
  texte par texte pour les cas `Ra8`/`Qh8+` ci-dessus (voir rapport de
  clôture de l'issue) : aucun chiffre brut >1000cp, verdict/solde matériel
  cohérents entre eux.
- Fusion de contexte du bouton "Demander l'avis du coach" pendant un
  exercice (point 5) vérifiée par simulation directe de
  `on_coach_comment_on_demand` : `mode_exercice`/`fen_depart_exercice`/
  descriptions mécaniques/verdict bien fusionnés, `meilleur_coup`/
  `eval_alain_mat` de l'exercice priment sur le calcul générique.

### Limites

- Aucune clé API Claude n'est configurée dans ce worktree (`.env` absent) :
  impossible de faire un appel réel à l'API pour vérifier le texte produit
  par le modèle — seul le contenu exact des données envoyées a été vérifié
  (voir ci-dessus), pas la réponse effective d'Haiku/Sonnet à ce nouveau
  contexte.
- `EngineManager.evaluate_move` calcule désormais systématiquement les deux
  évaluations (avant/après coup), y compris dans le cas, auparavant
  optimisé, où la position était déjà un mat forcé avant le coup et
  `return_pv=False` : un appel moteur de plus dans ce cas précis (rare en
  pratique), nécessaire pour détecter qu'un coup peut transformer un mat
  forcé EN FAVEUR du joueur en mat forcé CONTRE lui.
- Le garde-fou "position déjà décidée" (`SEUIL_DECIDE`) de
  `EngineManager.evaluate_move` est scopé à l'avantage DU JOUEUR évalué
  (conforme à la formulation de l'issue, point 2b) ; `build_patterns_
  erreurs._revalider_erreur` applique une variante symétrique (gagnant OU
  perdant) propre à l'amorçage du mode exercice, documentée dans son
  docstring.
- `revalider_erreurs_detectees.py` est livré mais PAS exécuté sur
  `erreurs_detectees.json` réel, conformément à la consigne — la commande à
  lancer par Alain (sauvegarde automatique horodatée avant toute écriture) :
  `python3 revalider_erreurs_detectees.py`
