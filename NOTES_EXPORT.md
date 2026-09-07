# Notes d'export — modules réutilisables pour ChessCoach

Extraits d'AlChess le 2026-09-07 (issue #252), à copier manuellement vers
le dépôt ChessCoach. Objectif de cette étape : des modules propres et
autonomes, **pas** une application Flask qui tourne. Rien ici n'a été
exécuté dans le contexte de ChessCoach — seule la syntaxe Python a été
vérifiée (`py_compile`) côté AlChess.

Retiré systématiquement de tous les fichiers : le support trilingue
FR/EN/DE (i18n), le mode pédagogique débutant, toute référence au hardware
Chessnut ou à NicLink.

## `library_manager.py`

- **Origine** : `nicsoft/modes/pgn_library/library_manager.py` (AlChess),
  copié quasiment à l'identique — ce module était déjà mono-utilisateur et
  sans dépendance pédagogique, aucune logique métier à retirer.
- **Dépendances externes** :
  - bibliothèque `python-chess` (`chess.pgn`) ;
  - un module `config` fournissant `DATA_DIR` (`pathlib.Path`) — **à créer
    côté ChessCoach**, l'import `from config import DATA_DIR` est un
    placeholder.
- **Structure de dossier supposée** : `DATA_DIR/pgn_library/manifest.json`
  + un sous-dossier par collection (`games.pgn` + `meta.json`), créés à la
    volée.
- **À finaliser côté ChessCoach** :
  - créer le module `config.py` (ou équivalent) avec `DATA_DIR` ;
  - décider si une seule collection "par défaut" suffit pour un usage
    mono-joueur, ou si le concept de collections multiples (garder tel
    quel) reste utile pour trier lichess/chess.com/parties perso.

## `socketio_pgn_handlers.py`

- **Origine** : les 6 handlers SocketIO `pgn_lib_*` de
  `nicsoft/web/server.py` (AlChess), regroupés dans une fonction
  d'enregistrement `register_pgn_library_handlers(socketio)` (dans AlChess
  ils étaient définis en vrac au niveau module, sur un unique process
  partagé).
- **Dépendances externes** : `flask-socketio`, `library_manager.py`
  (ci-dessus).
- **À finaliser côté ChessCoach** :
  - appeler `register_pgn_library_handlers(socketio)` une fois l'app
    Flask-SocketIO créée (squelette Flask à écrire) ;
  - câbler côté frontend les événements `pgn_lib_list_collections`,
    `pgn_lib_create_collection`, `pgn_lib_delete_collection`,
    `pgn_lib_import_pgn`, `pgn_lib_list_games`, `pgn_lib_load_game`
    (aucun JS de bibliothèque n'a été extrait — seul le rendu de
    l'échiquier/revue l'a été, voir `static/board.js`).

## `llm_coach.py`

- **Origine** : `nicsoft/modes/opening_explorer/llm_explainer.py`
  (AlChess), en particulier la fonction `get_analyse_response` (issue #196
  AlChess — écran "Analyse de partie").
- **Gardé** : le pattern construction du system prompt + prompt utilisateur
  + appel API + conversation multi-tours ; l'appel HTTP brut à l'API Claude
  via `urllib` (pas de SDK Anthropic requis).
- **Retiré** : le provider OpenAI (ChessCoach n'utilise que Claude) ; le
  support trilingue (un seul system prompt, en français) ; tout le code
  spécifique au mode pédagogique débutant de l'explorateur d'ouvertures
  (cache disque par ligne/coup, flèches `[FLECHES: ...]`, `get_explanation`,
  `get_chat_response`, `extract_arrows`) — hors sujet pour un coach
  d'analyse post-partie.
- **Ajouté pour ChessCoach** : `load_coach_memory(path)` /
  `save_coach_memory(path, memory)` pour un fichier de contexte JSON
  externe (mémoire du coach, injectée dans le system prompt via
  `_build_memory_text`). Le **schéma de ce fichier JSON reste à définir
  côté ChessCoach** — ce module le sérialise tel quel (aucune structure
  imposée pour l'instant : progression, erreurs récurrentes, objectifs...).
- **Dépendances externes** : aucune bibliothèque tierce (stdlib
  `json`/`urllib`/`pathlib`) ; une clé API Claude valide dans
  `config["llm_api_key"]`.
- **À finaliser côté ChessCoach** :
  - décider et documenter le schéma JSON de la mémoire du coach (ex.
    `{"sessions": [...], "erreurs_recurrentes": [...], "objectifs": [...]}`);
  - écrire le handler SocketIO (ou route HTTP) qui appelle
    `get_coach_response(messages, context, coach_memory, config)` et relaie
    la réponse au frontend via les événements `coach_response`/`coach_error`
    (déjà attendus par `static/board.js`) ;
  - décider quand/comment la mémoire est mise à jour après une session
    (actuellement seulement lue, jamais écrite automatiquement).

## `engine_stockfish.py`

- **Origine** : `nicsoft/engine/engine_manager.py` (AlChess) — classe
  `EngineManager` copiée **telle quelle** (déjà générique UCI, sans
  dépendance pédagogique ni hardware), plus `find_stockfish()` et
  `stockfish_available()`.
- **Retiré** : `MaiaEngine`, `RodentEngine` et toutes les fonctions de
  détection associées (`find_lc0`, `find_maia_weights`, `maia_available`,
  `find_rodent`, `rodent_available`, `_ensure_executable`,
  `RODENT_PERSONALITIES` et constantes Elo Rodent, `MAIA_LEVELS`) —
  ChessCoach n'a besoin que de Stockfish pour l'analyse assistée.
- **Dépendances externes** :
  - bibliothèque `python-chess` (`chess.engine`) ;
  - binaire Stockfish installé sur le système (`stockfish` dans le PATH,
    ou déposé dans `ENGINES_DIR/stockfish`) ;
  - un module `config` fournissant `ENGINES_DIR` (`pathlib.Path`) — **à
    créer côté ChessCoach**, comme pour `DATA_DIR`.
- **À finaliser côté ChessCoach** :
  - créer `config.ENGINES_DIR` ;
  - la classe garde `get_move()`/`set_elo()` (Elo limité) hérités
    d'AlChess : inutiles pour la seule analyse (`evaluate`,
    `evaluate_move`, `get_multipv`, `analyser_partie`), à ignorer ou
    supprimer si ChessCoach n'offre jamais de "rejouer contre le coach".

## `static/board.js` + `static/board.css`

- **Origine** : extraits et adaptés de `nicsoft/web/static/app.js` (7141
  lignes) et `nicsoft/web/static/css/main.css` (1557 lignes), AlChess.
  Fonctions d'origine reprises : `buildBoard`, `fenToBoard`, `renderBoard`,
  `uciToCoords`, `flipBoard`, `updateMaterial`, `qualiteColor` /
  `qualiteSymbole` / `qualiteAnnotation` / `QUALITE_GLYPH` /
  `showQualiteGlyph` / `removeQualiteGlyph`, `reviewPrev` / `reviewNext` /
  `reviewGoTo` / `renderHistory` / `renderReview` / `showReviewBestMove`,
  `telechargerPgn`, `loadPgnFile` / `parsePgn`, `laboUpdateEvalBar` (renommé
  `updateEvalBar`), `explClearArrows` / `explSquareCenter` /
  `explDrawArrows` (renommés `clearArrows` / `squareCenter` /
  `drawArrows`), et le panneau de chat `analyseLlm*` (issue #196 AlChess,
  renommé `coach*`).
- **Retiré** : tous les attributs/appels i18n (`data-i18n`, `t(...)`) —
  libellés en français en dur ; la synchronisation plateau physique
  (`_boardOk`, `laboSyncPhysique`, `laboRenderBoardWithErrors`) ; la
  sauvegarde vers la bibliothèque AlChess/NicLink (`sauvegarderNicLink`,
  événement `save_pgn_externe`) ; l'inversion des noms de joueurs
  haut/bas dans `flipBoard` (logique de partie live pédagogique, pas
  pertinente pour de l'analyse solo) ; la bibliothèque PGN interne
  (`pgnLib*`, non extraite ici — seul le backend `library_manager.py` /
  `socketio_pgn_handlers.py` l'est, le JS de bibliothèque reste à écrire
  côté ChessCoach).
- **Dépendances externes** :
  - un objet global `socket` (client Socket.IO), déjà connecté ;
  - la librairie `chess.js` exposée en global `Chess` (utilisée par
    `parsePgn` — présente dans AlChess sous
    `nicsoft/web/static/vendor/chess.js/`, à copier séparément si besoin) ;
  - des images de pièces sous `/static/pieces/{w,b}{K,Q,R,B,N,P}.svg`
    (constante `BASE_PIECES` en tête de fichier si l'arborescence diffère).
- **IDs DOM attendus** (à créer côté template ChessCoach, absents ici car
  aucun HTML n'a été extrait) : `#board`, `#coord-rank`, `#coord-file`,
  `#board-wrapper`, `#arrows-svg` (un `<svg>` superposé au plateau,
  idéalement avec un `<marker id="arrowhead">` pour les pointes de flèche —
  non repris tel quel, à redéfinir), `#material-top` / `#material-bottom`,
  `#historique`, `#review-move-info` / `#review-move-san` /
  `#review-best-move-san`, `#eval-black` / `#eval-white` / `#eval-score`,
  `#coach-history` / `#coach-empty` / `#coach-input` / `#coach-send-btn` /
  `#coach-spinner`.
- **À finaliser côté ChessCoach** :
  - écrire le HTML hôte (template) avec les IDs ci-dessus — rien n'a été
    extrait d'`index.html`, la structure d'origine était trop imbriquée
    dans l'écran de fin de partie pédagogique (`#panel-gameover`) pour
    être copiée telle quelle ;
  - définir le `<marker>` SVG `arrowhead` référencé par `drawArrows` (dans
    AlChess il vivait dans le `<defs>` statique du template, non extrait) ;
  - câbler `lancerAnalyse()` à un événement serveur `analyser_pgn` (non
    fourni ici — dans AlChess il était géré par `alchess.py`, spécifique
    à la machine d'état de jeu) : ChessCoach doit écrire son propre
    handler qui appelle `EngineManager.analyser_partie()`
    (`engine_stockfish.py`) et répond avec les qualités de coup ;
  - décider si le drag & drop de pièces est nécessaire (AlChess ne l'a pas
    non plus sur l'écran analyse — navigation uniquement via boutons
    précédent/suivant/clic sur l'historique).

## Points transverses restant à finaliser côté ChessCoach

- Squelette Flask-SocketIO minimal (app factory, route `/`, template hôte
  avec les IDs listés ci-dessus, montage des fichiers statiques).
- Module `config.py` avec `DATA_DIR` et `ENGINES_DIR`.
- Câblage des trois briques entre elles : import PGN (`library_manager`)
  → analyse Stockfish (`engine_stockfish`) → conversation coach
  (`llm_coach`), aujourd'hui indépendantes.
- Schéma et cycle de vie du fichier de mémoire du coach (lecture déjà
  implémentée, écriture/mise à jour à concevoir).
