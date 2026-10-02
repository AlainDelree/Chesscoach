# Changelog — Issue #86

## Mobile : plateau réduit stabilisé (hystérésis), bandeau de fin de partie compact, onglets remis en haut, conversation du coach propre à chaque mode, avertissement moteur corrigé

Suite des tests GSM sur l'issue #81 : `static/mobile_game.js`,
`static/board.js`, `static/controls.js`, `templates/index.html`,
`engine_stockfish.py`.

### Point 2 — Règle du plateau réduit (AVANT / APRÈS)

**Règle AVANT cette issue** (`_updateBoardCompactState`, `mobile_game.js`) :
un seul seuil de défilement (`BOARD_COMPACT_SCROLL_THRESHOLD = 24px`)
pilotait les DEUX sens via `wrap.classList.toggle("board-compact", focused
|| scrolled)` — le plateau redevenait complet dès que `scrollY` repassait
sous 24px, pas seulement en remontant tout en haut. Deux conséquences
observées par Alain : (1) aucune hystérésis — un micro-défilement autour du
seuil faisait battre le plateau entre les deux tailles ; (2) cette bascule
changeant elle-même la hauteur de `#board-sticky-wrap` (collé en haut), un
geste de défilement tactile en cours pouvait redéclencher la mesure au tick
suivant — oscillation perçue comme aléatoire. Par ailleurs,
`_isCurrentGameRunning()` excluait aussi bien l'état "avant toute partie" que
l'état "partie terminée" du plateau réduit : juste après un abandon/un mat,
le plateau restait donc toujours forcé en complet, quelle que soit la
hauteur du contenu de l'onglet ouvert.

**Règle APRÈS** :
- `_updateBoardCompactState()` (défilement/clavier) est désormais **purement
  additive** pour le passage en réduit (`wrap.classList.add(...)`, jamais
  `toggle`) : un défilement au-delà de 24px ou le focus du champ de question
  ajoute l'état réduit, mais plus rien ne le retire automatiquement en
  cours de route.
- Le **seul** retrait piloté par le défilement reste `scrollY <= 0` strict
  (remontée tout en haut de la zone) — un seuil différent de celui de
  déclenchement (hystérésis : 24px à l'aller, 0px au retour).
- Les 4 actions de retour prévues par la tâche restent les seules à
  redonner le plateau complet : toucher le plateau réduit
  (`boardCompactExpand`), un coup joué (`_forceBoardFull`, appelée par
  `_mobileGameOnMoveCountChanged`), la lecture d'une ligne ("Play",
  `_linePlaybackActive()` court-circuite tout l'état réduit), et la
  remontée tout en haut ci-dessus. Aucune autre voie ne retire la classe.
- `_isGameSessionActive()` (nouveau) = `_isCurrentGameRunning() ||
  body.classList.contains("game-over-active")` remplace
  `_isCurrentGameRunning()` dans les deux gardes (`_updateBoardCompactState`,
  `_autoCompactForOverflow`) : le plateau réduit redevient utilisable juste
  après la fin d'une partie (abandon/mat), pas seulement pendant qu'elle est
  en cours. `showGameOverBanner()` (`board.js`) appelle désormais
  `_mobileGameOnGameOver()` (nouveau) qui relance tout de suite
  `_autoCompactForOverflow()` : si l'onglet déjà ouvert déborde au moment où
  la partie se termine, le plateau passe en réduit sans attendre un
  défilement ou un changement d'onglet.
- **Contenu qui arrive après coup** (résultats d'analyse qui se chargent,
  tableau des lignes qui se peuple) : un `ResizeObserver` générique sur les
  4 panneaux d'onglets (`_ensureGameTabPanelsObserved`, nouveau) appelle
  `_autoCompactForOverflow()` à chaque changement de taille, plutôt que de
  devoir ajouter un appel explicite dans chaque fichier qui peut faire
  grandir leur contenu. Garde-fou propre à cet observateur (asynchrone, donc
  pouvant se déclencher après la remise à plat d'`onGameUiRefresh()`) : il
  ignore son propre déclenchement tant que `scrollY<=0` ET qu'aucune partie
  n'est terminée — sans ce garde-fou, un test Playwright de cette issue a
  montré qu'il cassait la garantie de l'issue #71 point 2 ("jamais avant
  d'avoir vu le plateau complet une seule fois") en rebasculant le plateau
  en réduit juste après l'arrivée sur un mode de partie, à cause du contenu
  de base (encore vide) de l'onglet Coach qui venait d'être déplacé dans son
  panneau.

### Point 1 — Bandeau de fin de partie compact

- `#mobile-game-over-bar` (`templates/index.html`) : AVANT, le texte de
  résultat était en `flex: 1 1 100%` (sa propre ligne) et les deux boutons se
  répartissaient la largeur sur la ligne suivante — deux lignes dans les
  faits malgré le commentaire de l'issue #77 qui visait une seule ligne.
  APRÈS : `flex-wrap: nowrap`, texte en `flex: 1 1 auto` + `min-width: 0` +
  ellipse (`text-overflow: ellipsis`) plutôt que de forcer sa propre ligne,
  boutons `flex: 0 0 auto` (jamais tronqués, toujours pleinement cliquables)
  avec une police/un remplissage réduits (0.72rem/6px 8px au lieu de
  0.8rem/8px 6px). Mesuré (Playwright, voir plus bas) : hauteur totale
  passée de 105px (3 lignes avec un message long) à 42px (1 ligne, quel que
  soit le message) — compact mais les boutons restent lisibles et cliquables.
- Reste masqué en plateau réduit (règle CSS déjà existante depuis l'issue
  #77, listée avec `#review-controls`/`#shared-mode-controls`) — désormais
  réellement atteignable juste après une fin de partie grâce au point 2
  ci-dessus (avant cette issue, le plateau restait forcé en complet après
  une fin de partie, donc cette règle ne s'appliquait jamais en pratique).
  Choix retenu parmi les deux options de la tâche : rendu compact **et**
  disparition en plateau réduit (pas de sortie de la partie fixe, qui
  aurait demandé de déplacer son nœud DOM hors de `board-sticky-wrap` et
  changé l'ordre d'affichage sans bénéfice supplémentaire une fois la bande
  elle-même compacte).

### Point 3 — Onglets remis en haut à chaque changement

- `switchGameTab()` (`mobile_game.js`) : à chaque VRAI changement d'onglet
  (`tabKey !== _currentGameTab` — pas aux réappels internes
  d'`onGameUiRefresh()` avec le même onglet, par ex. après chaque coup),
  `window.scrollTo(0, 0)` remet la zone de contenu en haut (même principe que
  `switchModeTab`, `controls.js`, issue #71 point 2).
- Le `scrollTo` déclenche un évènement `scroll` natif asynchrone qui repasse
  par `_updateBoardCompactState()` (déjà posé en écouteur au chargement de
  page, donc appelé AVANT tout nouvel écouteur ajouté après coup) et force
  le plateau complet (`scrollY<=0`) — potentiellement par-dessus la décision
  "le nouvel onglet déborde encore" de `_autoCompactForOverflow()`. Pour que
  cette dernière garde le dernier mot sans jamais annuler la remontée en
  haut elle-même, un second appel est différé d'un tick
  (`setTimeout(…, 0)`), qui s'exécute après cet évènement.
- Vérifié (Playwright) : après un onglet Coach rempli de 25 messages longs
  (défilé à 900px), passage successif à Lignes/Analyse/Coups — les trois
  onglets atterrissent à `scrollY = 0` avec le début de leur contenu dans le
  viewport (`panel.getBoundingClientRect().top < innerHeight`), et restent
  défilables (le plateau réduit se réengage immédiatement si le nouveau
  contenu déborde encore, cf. point 2).

### Point 4 — Conversation propre à chaque mode

- `switchModeTab()` (`controls.js`) : appelle désormais `coachClear()`
  (`board.js`, déjà utilisée par le bouton "Effacer") dès que `tabKey !==
  currentModeTab` (évalué AVANT la réaffectation) — un VRAI changement de
  mode (Exercice → Partie pédagogique, Bibliothèque → Éditeur, etc.) vide
  l'affichage (`#coach-history`) ET l'historique envoyé à l'API
  (`_coachHistory = []`, `_coachSegmentStart = 0`). Revisiter l'onglet déjà
  actif (reclic, ou réouverture du menu déroulant mobile, qui rappelle
  `switchModeTab` avec la même clé) ne déclenche rien.
- Les traits de séparation "Nouvelle partie"/"Nouvel exercice"
  (`coachNewSegment`, appelée au démarrage effectif d'une partie/d'un
  exercice, jamais à la navigation) et le comportement déjà en place pour
  les exercices sont inchangés — `coachClear()` remet de toute façon
  `_coachHistory`/`_coachSegmentStart` à zéro, un segment précédent n'a donc
  plus rien à séparer une fois qu'on a changé de mode.
- Vérifié (Playwright) : 2 messages injectés en mode Exercice (affichage +
  `_coachHistory`) → revisite du même onglet Exercice → les 2 messages et les
  2 entrées d'historique restent intacts → changement réel vers Partie
  pédagogique → affichage et historique à 0 dans les deux cas.

### Point 5 — Avertissement moteur (coup nul, issue #80)

- Cause confirmée : `EngineManager.get_threats()` (`engine_stockfish.py`)
  construisait `board_nul` par `board.copy()` (garde tout l'historique de la
  position réelle) `+ push(chess.Move.null())`, puis transmettait ce plateau
  tel quel à `get_multipv()` → `engine.analyse()`. python-chess
  (`chess/engine.py`, `_position()`) refuse de transmettre un historique
  contenant un coup nul au moteur UCI (`safe_history = all(board.move_stack)`,
  un coup nul est "falsy") et journalise `WARNING:chess.engine:Not
  transmitting history with null moves to UCI engine` avant de retomber de
  toute façon sur la position seule (même résultat, juste bruyant).
- Correctif (une ligne ajoutée) : après avoir poussé le coup nul pour obtenir
  la bonne position, reconstruction d'un plateau **neuf à partir du FEN**
  (`board_nul = chess.Board(board_nul.fen())`) avant l'appel à
  `get_multipv()` — `move_stack` vide, donc plus aucun coup nul ne peut
  déclencher l'avertissement ; seule la position compte pour l'évaluation,
  le résultat est donc identique.
- Autre source recherchée (`grep -rn "Move.null()"`) : un seul autre usage,
  dans `game_facts.py` (`describe_menace_adverse`), qui construit déjà un
  plateau neuf depuis un FEN (`chess.Board(fen_avant)`) uniquement pour
  obtenir un FEN texte — aucun appel moteur, donc aucun risque
  d'avertissement là. Pas d'autre source identifiée.
- Vérifié par un script isolé (`EngineManager` réel sur `/usr/games/stockfish
  16`, capture du logger `chess.engine`) : AVANT le correctif (reproduit en
  appelant `get_multipv` directement sur l'ancien `board_nul`), la ligne
  `Not transmitting history with null moves to UCI engine` apparaît bien
  (sanity-check que le test détecte réellement l'avertissement). APRÈS le
  correctif, sur une position avec un historique réel (5 coups joués,
  `get_threats(board, depth=10, n=2)`), le journal capturé est vide et les
  menaces sont calculées normalement (`disponible: true`, 2 coups avec leurs
  `cp`/`perte_cp`).

### Tests (Playwright/Chromium, gabarit réel rendu directement par Jinja2)

Comme pour les issues mobiles précédentes, aucun appel réel à l'API Claude ni
au serveur Flask/SocketIO complet : `templates/index.html` est rendu par un
petit serveur Flask jetable (`_test_harness/serve.py`, non commité) avec un
contexte minimal simulé, servant le CSS/JS réel du dépôt — l'état de partie
(`pedagogicActive`, `pedagogicGame`...) et les messages du coach sont
injectés via `page.evaluate()` en appelant les vraies fonctions
(`switchModeTab`, `setActiveMode`, `showGameOverBanner`, `coachClear`...),
jamais de logique dupliquée à la main. Viewports 390×750 et 360×640,
`is_mobile=True, has_touch=True`.

- **Oscillation au défilement** (390×750 et 360×640, onglet Coach avec 25
  messages longs, partie pédagogique en cours) : défilement pas à pas de 0 à
  1140px puis retour à 0px par incréments de 60px — **0 bascule** pendant
  toute la descente (reste compact du début à la fin, puisque le contenu
  déborde déjà), **1 seule bascule** pendant la remontée, exactement à
  `scrollY = 0` (le retour explicite au plateau complet) — aucune
  oscillation incohérente entre-temps, conforme à la règle corrigée.
- **Part de hauteur disponible pour le contenu, 3 réglages** (pendant une
  partie pédagogique active, plateau non réduit) :

  | Écran | Réglage | Plateau | Contenu visible sous les onglets |
  |---|---|---|---|
  | 390×750 | Compact | 231px | 150px (20,0 %) |
  | 390×750 | Normal | 281px | 100px (13,3 %) |
  | 390×750 | Grand | 321px | 60px (8,0 %) |
  | 360×640 | Compact/Normal/Grand | 170px (plancher) | 52px (8,1 %) |

  À 390×750, les 3 réglages se différencient désormais correctement (avant
  le correctif du point 2, un bug de l'observateur de redimensionnement
  faisait basculer le plateau en réduit dès l'arrivée sur le mode, et les 3
  réglages retombaient tous sur le même plancher `clamp(150px,42vw,170px)` —
  42 % de 390 = 163,8px dans les 3 cas, bug repéré et corrigé pendant cette
  session, cf. point 2). À 360×640, l'écran est trop étroit pour que les 3
  réglages se différencient pendant une partie active (les trois atteignent
  le plancher `GAME_BOARD_MIN_SIZE`), comportement déjà documenté comme
  attendu depuis l'issue #81.
- **Bandeau de fin de partie, une ligne** (isolé des effets du plateau
  réduit, classes appliquées directement) : hauteur mesurée à **42px** à
  390×750 et 360×640, quelle que soit la longueur du message de résultat
  (testé avec un message volontairement long : toujours 42px, texte tronqué
  en ellipse, aucun débordement horizontal
  `document.documentElement.scrollWidth === clientWidth`). AVANT (ancien
  CSS reproduit avec `page.add_style_tag`) : 105px sur le même message long
  (texte sur 3 lignes). Boutons "Analyser cette partie"/"Nouvelle partie"
  toujours visibles et cliquables dans les deux cas (captures d'écran,
  `_test_harness/shot_banner_*`).
- **Onglet Analyse qui déborde après un abandon** (contenu injecté APRÈS la
  fin de partie, simulant des résultats d'analyse qui arrivent en différé) :
  le plateau passe en réduit automatiquement (`board-compact` devient vrai)
  sans action de l'utilisateur, aux deux largeurs testées.
- **Séquence Coach long → Lignes → Analyse → Coups** : les 3 onglets
  atterrissent à `scrollY = 0` avec leur contenu visible dans le viewport.
- **Conversation par mode** : 2 messages (affichage + historique API)
  injectés en mode Exercice → revisite du même onglet → les 2 messages et
  les 2 entrées d'historique restent → changement réel vers Partie
  pédagogique → affichage et historique à 0 dans les deux cas.
- **Actions de retour explicites, non-régression** : toucher le plateau
  réduit (`boardCompactExpand`) le ramène en complet et remonte en haut ;
  jouer un coup (`_mobileGameOnMoveCountChanged`) force le plateau complet
  même en plein défilement ; démarrer la lecture d'une ligne
  (`gameCoachLinesPlayingIdx`) force le plateau complet quel que soit le
  défilement — les 3 vérifiées indépendamment, toutes correctes après le
  correctif.
- Captures d'écran dans `_test_harness/` (non commité, worktree local) :
  plateau complet en partie pédagogique (réglage Grand), bandeau de fin de
  partie compact (une ligne, message long tronqué) avant/après correctif.

### Limites

- Aucun appel réel à l'API Claude ni au serveur Flask/SocketIO complet (pas
  de `RESEAU`, contexte simulé côté Jinja2 comme les issues mobiles
  précédentes) — l'état de partie/les messages du coach sont injectés
  directement en JS plutôt que joués via de vrais échanges réseau.
- `--bd-size-game-max` reste figé (non remesuré) pendant tout l'état "partie
  terminée" (`game-over-active`, limitation déjà en place depuis l'issue
  #77, volontairement conservée) : le plateau peut rester légèrement plus
  petit que nécessaire juste après une fin de partie, jamais plus grand que
  l'espace réellement disponible — sans conséquence pratique puisque la
  bande de fin de partie compacte (point 1) prend de toute façon moins de
  place que les contrôles de partie actifs qu'elle remplace. Si le contenu
  de l'onglet ouvert déborde malgré cette valeur figée,
  `_mobileGameOnGameOver()`/le `ResizeObserver` des panneaux passent de
  toute façon directement en plateau réduit (point 2).
  - Les chiffres de la table "part de hauteur disponible" ci-dessus sont
  mesurés sur le gabarit réel mais avec un contexte minimal simulé (pas de
  vraie conversation, pas de vrai historique de coups) — l'ordre de grandeur
  et les écarts relatifs entre réglages sont fiables, les valeurs absolues
  peuvent différer légèrement d'un appareil réel avec du contenu réel.
- Pas de test sur un véritable appareil physique (GSM/PC) ni dans un vrai
  navigateur mobile (Safari iOS, Chrome Android) — seule l'émulation de
  viewport/tactile de Chromium a été utilisée.
- `.env` non touché ; `_test_harness/` (serveur Flask jetable + script
  Playwright + captures) n'a pas été commité, laissé sur disque pour
  inspection si besoin.
