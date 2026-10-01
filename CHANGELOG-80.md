# Changelog — Issue #80

## Coach : explique les menaces, les attaques/défenses et les idées du coup au lieu de recopier les FEN

- **Constat de départ** (position `1r1r2k1/4Qpbp/2Bp1n2/3Pp2q/2P1P1p1/2N3PP/PP3PK1/R1B2R2 w - - 0 23`,
  Alain Blancs, coup proposé h4) : le coach n'avait aucune donnée sur la
  menace adverse (`...gxh3+`/`...Qxh3+`) et a présenté un coup purement
  défensif comme « une expansion à l'aile roi » ; relancé sur la menace, il a
  affirmé à tort que le pion g3 protégeait h3 (un pion blanc en g3 attaque
  f4/h4, pas h3), puis a recopié le FEN de mémoire avec une erreur de
  transcription et conclu que le FEN d'Alain était invalide.

### Tâche 1 — Menace adverse (coup nul)

- `engine_stockfish.py`, `EngineManager.get_threats(board, depth, n=2)` :
  joue un coup nul (`chess.Move.null()`, légal seulement hors échec) sur la
  position et redemande au moteur d'évaluation ses `n` meilleurs coups
  (réutilise `get_multipv` tel quel) — ce sont les meilleures menaces de
  l'adversaire si le camp au trait passait son tour. Retourne
  `{"disponible": False, "raison": "en_echec"|"moteur_indisponible"}` si la
  position est en échec ou si Stockfish est indisponible, sinon
  `{"disponible": True, "baseline": {...}, "menaces": [{"move", "cp", "mate",
  "perte_cp"}, ...]}` — `perte_cp` est l'écart entre l'évaluation de la
  position (déjà le meilleur coup du camp au trait) et l'évaluation
  résultant de chaque menace, toujours ≥ 0. Fonction mode-agnostique,
  appelée depuis `app.py` (`_calculer_menace_adverse`, lui-même réutilisable
  par d'autres modes que l'Exercice).
- `game_facts.py`, `describe_menace_adverse(menace_data, fen_avant,
  camp_alain)` : formate ce résultat en texte de contexte — chaque menace
  décrite mécaniquement (`describe_move_mechanically`, donc pièce, case,
  capture, échec, défense, solde net), son évaluation résultante et sa
  perte d'avantage, étiquetée « SIGNIFICATIVE » au-delà de
  `SEUIL_MENACE_SIGNIFICATIVE_CP = 100` centipions (constante unique,
  reprise par le prompt). Toujours un texte explicite, y compris en cas
  d'indisponibilité (échec/moteur en panne) — jamais un bloc silencieusement
  absent.

### Tâche 2 — Attaques et défenses avant/après le coup

- `game_facts._decrit_coup_mecanique` (fonction déjà partagée par
  `describe_move_mechanically`/`describe_pv_mechanically`/
  `describe_pv_with_balance`, donc par TOUS les coups cités — proposé, réel,
  meilleur coup, PV) enrichie de trois nouveaux calculs :
  - `_attaques_defenses_arrivee` : qui attaque/défend la case d'arrivée
    après le coup, et quels anciens attaquants de la case de départ ne
    l'atteignent plus (`chess.Board.attackers`) ;
  - `_resultat_echange_case` : si la pièce qui vient d'arriver est
    attaquée, le résultat si l'adversaire la capture (attaquant le moins
    cher d'abord, puis reprise mécanique comme `_solde_net_apres_capture`) —
    reproduit l'exemple demandé : « Qxh4 gxh4, échange favorable ou
    équilibré pour Blancs » ;
  - `_pieces_amies_changement_attaque` : pièces amies (hors case de
    départ/arrivée) qui gagnent ou perdent l'attaque adverse suite à ce
    coup (attaque découverte, mise à l'abri), limité à 3 par liste.
  - Omis sur un mat (plus aucun coup adverse possible). Limite connue : le
    coup de la tour lors d'un roque n'est pas modélisé séparément (l'objet
    `chess.Move` n'encode que le roi) — ses propres changements d'attaque ne
    sont donc pas détectés.

### Tâche 3 — Listes de pièces + interdiction de citer un FEN

- `game_facts.describe_pieces_lists(fen, camp_alain)` : liste des pièces de
  chaque camp par case pour une position FEN isolée, même présentation que
  le bloc de faits des modes de partie (`_liste_pieces`) — réutilisable pour
  le mode Exercice, qui ne rejoue aucun PGN.
- `app.py` (`on_exercise_answer`/`_on_exercise_answer_lichess`) : jointe au
  contexte pour la position de DÉPART et la position ACTUELLE de
  l'exercice.
- `llm_coach.py`, nouveau bloc de prompt (dans `_EXERCISE_SYSTEM_ADDENDUM`) :
  ne jamais recopier/citer un FEN dans une réponse, ne jamais déclarer un
  FEN invalide ou mal formé, ne s'appuyer que sur les listes/descriptions
  fournies, ne jamais affirmer qu'une pièce en protège une autre sans que
  les données le disent explicitement.

### Tâche 4 — Prompt : la menace d'abord

- `llm_coach.py`, même addendum : quand un bloc de menace marque au moins
  une menace « SIGNIFICATIVE », ou quand la description mécanique d'un coup
  cité indique qu'une pièce amie « n'est plus attaqué(e) » par rapport à
  avant ce coup, le coach doit expliquer la menace d'abord (ce que
  l'adversaire aurait joué et ce que cela aurait provoqué), puis pourquoi le
  coup la pare, puis les points secondaires — et ne jamais présenter un coup
  défensif/préventif comme un plan offensif. Sans menace marquante, consigne
  explicite de ne rien inventer.

### Tâche 5 — Idées du coup (décomposition de l'évaluation Stockfish)

- `engine_stockfish.py`, `EngineManager.get_eval_breakdown(fen, timeout=5s)`
  : lance un sous-processus Stockfish séparé des instances permanentes
  (commande UCI non standard « eval », absente depuis Stockfish 16.1),
  envoie `position fen ...` puis `eval`, parse la table « Contributing terms
  for the classical eval » (colonne Total, MG/EG, par terme). Retourne
  `None` si le binaire est introuvable, si le délai est dépassé, ou si la
  sortie ne contient pas cette table (jamais d'exception).
- `game_facts.py` :
  - `_diff_termes_evaluation` : variation de chaque terme entre AVANT et
    APRÈS un coup, du point de vue d'Alain, au-delà de
    `SEUIL_IDEE_PION = 0.3` pion (constante unique) — phase MG/EG choisie
    selon le matériel restant (`_phase_mg_ou_eg`, ≤ 12 pièces = finale,
    même heuristique que `app._analyse_full_game`). Termes traduits en
    français (`_IDEE_LIBELLES` : King safety → sécurité du roi, Threats →
    menaces sur les pièces adverses, Mobility → activité des pièces, Passed
    → pion passé, Space → espace, Pawns → structure de pions, Knights/
    Bishops/Rooks → meilleur placement du cavalier/fou/tour, Material +
    Imbalance → matériel, fusionnés) ;
  - idées mécaniques complémentaires : `_idee_parade_menace` (la menace la
    plus sévère de la tâche 1 n'est plus légale après ce coup),
    `_idee_developpement_centralisation` (cavalier/fou qui quitte sa case
    de départ, pièce qui rejoint d4/d5/e4/e5), plus échec/mat directement
    dans `build_idees_coup` ;
  - `build_idees_coup(fen_avant, coup, camp_alain, breakdown_avant,
    breakdown_apres, menace_data, max_idees=3)` : combine le tout par
    paliers (mat/échec toujours en tête, puis les idées moteur triées par
    magnitude, puis les idées mécaniques complémentaires triées par
    magnitude) — un mat/échec reste prioritaire sur tout le reste, mais une
    parade de menace ne doit pas éclipser l'idée moteur qui la mesure déjà
    (ex. « sécurité du roi » doit rester en tête sur h4, la parade de
    `...gxh3+` listée ensuite). Retourne `[]` sans erreur visible si la
    décomposition est indisponible et qu'aucune idée mécanique n'est
    détectée ;
  - `format_idees_coup(label, idees)` : texte de contexte, jamais de valeur
    chiffrée.
- `app.py`, `_calculer_idees_coup` (mode-agnostique) : appelle
  `get_eval_breakdown` avant/après, puis `build_idees_coup` — branché pour
  le coup proposé, le coup réellement joué (source « mes erreurs ») et le
  meilleur coup, dans `on_exercise_answer` ET `_on_exercise_answer_lichess`.

### Tâche 6 — Prompt : présenter les idées comme des indications

- `llm_coach.py`, même addendum : le coach énonce les idées dans l'ordre
  fourni, précise pour chacune comment elle se réalise (pièces/cases/
  menaces, à partir des descriptions et listes déjà fournies), n'ajoute
  jamais d'idée absente de la liste, les présente comme des indications du
  moteur (« le moteur indique que... ») et jamais comme des vérités, ne cite
  aucune valeur chiffrée, dit que le coup se justifie surtout par la ligne
  calculée ou la tactique si aucune idée n'est détectée, et compare les
  idées du coup proposé et du meilleur coup quand ils diffèrent.

## Fichiers touchés

- `engine_stockfish.py` : `EngineManager.get_threats`,
  `EngineManager.get_eval_breakdown`.
- `game_facts.py` : `describe_pieces_lists`, `describe_menace_adverse`,
  `_attaques_defenses_arrivee`/`_resultat_echange_case`/
  `_pieces_amies_changement_attaque` (dans `_decrit_coup_mecanique`),
  `build_idees_coup`/`format_idees_coup` + fonctions privées associées,
  nouvelles constantes `SEUIL_MENACE_SIGNIFICATIVE_CP`/`SEUIL_IDEE_PION`.
- `llm_coach.py` : `_build_context_text` (nouveaux champs
  `pieces_depart_texte`/`pieces_actuelles_texte`/`menace_adverse_texte`/
  `idees_coup_propose_texte`/`idees_coup_reel_texte`/
  `idees_meilleur_coup_texte`), nouvel addendum dans
  `_EXERCISE_SYSTEM_ADDENDUM`.
- `app.py` : `_calculer_menace_adverse`/`_calculer_idees_coup` (nouvelles,
  mode-agnostiques), branchées dans `on_exercise_answer`,
  `_on_exercise_answer_lichess` et la liste blanche de
  `on_coach_comment_on_demand`.
- `static/exercise.js` : nouvelles variables mémorisant ces champs reçus
  avec le verdict, réinjectées dans `exerciseChatContextExtra()` pour
  qu'une question de suivi dans le chat libre dispose du même contexte.

## Tests

- Unitaires (sans API, moteur réel `/usr/games/stockfish` 16) : position de
  l'exemple h4 — `get_threats` trouve `gxh3+`/`Qxh3+` (pertes ≈ 194/168cp,
  cohérent avec l'estimation indépendante de l'issue, ≈ 290/410cp de perte
  selon la méthode de calcul) ; `get_eval_breakdown` avant/après h4 confirme
  `King safety` MG +1.07 pion et rien d'autre de marquant (valeur exacte de
  l'issue), Qa7 ne change aucun terme marquant ; `build_idees_coup` place
  « sécurité du roi » en tête pour h4 (avec la parade de `gxh3+` ensuite),
  aucune idée pour Qa7, « menaces sur les pièces adverses » pour `Rc1` sur
  `r2qk2r/ppp2ppp/2n1p3/4P3/2BP2b1/2b1BN2/P4PPP/R2Q1RK1 w kq - 0 11` (les
  trois résultats demandés par l'issue sont vérifiés).
- `describe_move_mechanically(fen, "h4", "blancs")` reproduit exactement
  l'exemple attendu par l'issue : « ... en h4, attaqué(e) par Dame h5,
  défendu(e) par Pion g3 : Qxh4 gxh4, échange favorable ou équilibré pour
  Blancs (Alain) ; n'est plus attaqué(e) par Pion g4 ».
- Cas limites : position en échec → `get_threats` retourne
  `disponible=False, raison="en_echec"`, texte explicite correspondant ;
  mat (`Ra8#`) → idée « échec et mat » en tête ; finale K+P vs K → pipeline
  complet sans erreur, aucune menace marquante détectée ; décomposition
  absente (simulée en forçant `breakdown_avant/apres=None`) → idées
  mécaniques seules (ex. développement), aucune exception ; position calme
  (`4...Nc6` dans une Italienne) → `describe_menace_adverse` ne qualifie
  aucune menace de significative. Régression : `describe_move_mechanically`
  revérifié sur roque, prise en passant et promotion (toujours correct avec
  les nouveaux segments), et sur un contexte de mode partie sans aucun des
  nouveaux champs (aucune section pièces/menace/idées ajoutée à tort).
- Appel réel à l'API Claude (`claude-sonnet-5`, clé lue depuis
  `~/ChessCoach/.env`, jamais modifié) sur la position/coup `h4` de
  l'exemple : la réponse explique la menace adverse (`...gxh3+`/`...Qxh3+`)
  EN PREMIER, explique pourquoi h4 la pare, qualifie explicitement le coup
  de défensif (« Ce coup est donc avant tout défensif... pas une expansion
  offensive à l'aile roi »), et ne recopie ni ne met en cause le FEN. Une
  question de suivi reproduisant l'erreur originale (« mon pion g3 ne
  protège-t-il pas h3 ? ») reçoit une réponse qui corrige correctement
  l'intuition (« Ton pion g3 ne protège pas la case h3... il défendrait une
  pièce noire en h4, pas en h3 ») sans jamais recopier le FEN ni le
  déclarer invalide — le bug source de l'issue ne se reproduit plus.

## Limites connues

- Idées mécaniques de développement/centralisation : heuristiques simples
  (case de départ standard du cavalier/fou, carré central d4/d5/e4/e5), pas
  une détection générale de plans positionnels.
- Le roque n'enrichit les attaques/défenses que pour le roi (la tour qui se
  déplace silencieusement n'est pas analysée séparément).
- `get_eval_breakdown` dépend d'une commande non standard, absente à partir
  de Stockfish 16.1 : dégradation déjà prévue et testée (repli sur les
  idées mécaniques seules), mais aucune décomposition moteur ne sera plus
  disponible le jour où Alain mettra à jour son binaire Stockfish.
- Seule la source « mes erreurs » et la source « Problèmes Lichess » du
  mode Exercice sont couvertes ; les autres modes (pédagogique, ouverture,
  finales, partie libre) ne reçoivent pas encore ces données — hors
  périmètre explicite de l'issue, mais les fonctions ajoutées
  (`_calculer_menace_adverse`/`_calculer_idees_coup`/`describe_pieces_lists`)
  sont déjà mode-agnostiques et réutilisables sans modification.
