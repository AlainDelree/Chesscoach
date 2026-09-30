# Changelog — Issue #71

## Mobile : corrections après test de la nouvelle disposition (sélecteur de mode, arrivée dans un mode, plateau plus grand, plateau réduit, écrans mélangés)

- Contexte : Alain a testé sur son GSM les issues #69/#70 et relevé six
  problèmes concrets. Tous corrigés dans le périmètre mobile (<900px)
  existant (`body.mobile-game-active`/nouvelle classe `.mobile-wide-board`,
  `mobile_game.js`/`controls.js`) — grand écran et mode exercice vérifiés
  inchangés (Playwright, cf. tests plus bas).

### Point 1 — Sélecteur de mode toujours accessible
- `#mobile-mode-bar-slot` (contient `.mode-tab-bar`, déplacé par
  `placeModeTabBarForViewport`) redevient `position:sticky; top:0` dans
  **tous** les modes mobiles, pas seulement en mode jeu — l'issue #69 l'avait
  retiré, ce qui privait `.mode-tab-bar.open` (position:absolute) de tout
  ancêtre positionné hors mode jeu : la liste ouverte se positionnait alors
  par rapport à la racine du document entier plutôt que sous le sélecteur
  (symptôme observé : "la liste disparaît, réapparaît au milieu de l'écran
  après défilement").
- Une règle `#mobile-mode-bar-slot { display:block; }` sans media query,
  plus bas dans le fichier, entrait en conflit de cascade avec le nouveau
  `display:flex` (même spécificité, dernière règle du fichier qui gagne) —
  supprimée (un `<div>` est `display:block` par défaut).
- `#board-sticky-wrap` (plateau) se colle désormais juste EN DESSOUS de ce
  sélecteur (`top: var(--mobile-header-h)`, hauteur republiée en continu par
  un `ResizeObserver` dans `controls.js`, même principe que
  `--scroll-padding-top`) plutôt qu'au même niveau.

### Point 2 — Arrivée dans un mode
- `switchModeTab()` (`controls.js`) remonte désormais la page tout en haut
  (`window.scrollTo(0,0)`) à chaque changement d'onglet.
- `_updateBoardCompactState()` (`mobile_game.js`) n'active plus jamais l'état
  réduit tant qu'aucune partie n'est en cours (nouvelle fonction partagée
  `_isCurrentGameRunning()`) ni tant que `window.scrollY <= 0`.
- Capture (390×750, arrivée en partie pédagogique depuis une page défilée) :
  plateau complet, boutons "Jouer les Blancs/Noirs", sélecteur de mode —
  plus d'écran vide.

### Point 3 — Plateau plus grand
- Mode jeu : `--bd-size` (seule variable à ajuster, `templates/index.html`)
  cible jusqu'à 44% de la hauteur dynamique d'écran, sans dépasser
  `calc(100vw - 24px)`. Un 4e terme `var(--bd-size-game-max)`, mesuré en
  continu sur le DOM réel par `_updateGameBoardMaxSize()`
  (`mobile_game.js`, ResizeObserver sur `#board-sticky-wrap`), garantit les
  ~180px de contenu visible sous les onglets demandés — voir "Tailles
  obtenues" et "Limites" plus bas, ce terme est presque toujours la
  contrainte déterminante en pratique.
- `#coord-rank`/`#coord-file` et la barre d'éval Stockfish sont masqués en
  mode jeu ; les coordonnées (lettres/chiffres) sont repliées dans le coin
  haut-gauche de chaque case de bord via `buildBoard()` (`board.js`, nouveaux
  `data-rank-label`/`data-file-label`) + un seul pseudo-élément CSS
  `::before` (`::after` déjà pris par le hachurage `.finale-king-restricted`
  du mode finales).
- Bibliothèque/Revue PGN et Éditeur de position (régression de largeur de
  l'issue #69, `--bd-size` réduit à `30vh` sans ajuster la largeur
  soustraite) : nouvelle classe `.mobile-wide-board` (posée par
  `onGameUiRefresh`) élargit `--bd-size` à `min(58vh, 480px, calc(100vw -
  52px))`, coordonnées repliées dans les cases comme en mode jeu. Mode
  exercice explicitement exclu de cette classe — formule générale (`30vh`)
  inchangée, vérifié identique en px avant/après.

### Point 4 — Plateau réduit au défilement
- L'ancienne bande uniquement textuelle (`#board-compact-strip`) est
  supprimée. `#board-full-view` (le plateau réel, jamais dupliqué) rétrécit
  simplement via un `--bd-size` local (`clamp(150px, 42vw, 170px)`) posé par
  la classe `.board-compact` déjà existante — même rendu, mêmes pièces,
  aucun code de rendu dupliqué. Le matériel capturé est masqué (redondant
  avec `#game-status-line`, qui reste affichée à côté). Les cases
  n'acceptent plus les clics tant que réduit (`pointer-events:none` sur
  `#board`) ; un tap sur `#board-full-view` restaure le plateau complet via
  la nouvelle fonction `_boardFullViewClick()` (vérifie elle-même la classe
  `board-compact`, donc sans effet sur les clics de déplacement de pièce en
  plateau complet).

### Point 5 — Menu "..." sans doublon
- Entrée "Bibliothèque" retirée de `#game-menu-dropdown`
  (`templates/index.html`) — déjà présente dans le sélecteur de mode
  principal.

### Point 6 — Écrans mélangés
- `placePedagogicStartButtonsForViewport`/`placeOpeningStartButtonsForViewport`
  (déjà correctement conditionnées à l'onglet consulté) sont désormais
  appelées à CHAQUE `onGameUiRefresh`, y compris en quittant un mode de
  partie — avant ce correctif, elles n'étaient plus jamais rappelées après
  un passage vers Bibliothèque/Exercice/Éditeur (retour anticipé de
  `onGameUiRefresh` avant leur appel), laissant les boutons "Jouer les
  Blancs/Noirs" coincés dans `#board-column` (visible sur tous les onglets
  mobiles).
- `#shared-mode-controls` ("Contrôles du mode actif") vit hors des onglets
  (issue #15, `#board-column` toujours visible sur mobile) pour rester
  utilisable en arrière-plan sur grand écran — nouvelle classe
  `mode-controls-mismatch` (posée par `_updateModeControlsMismatch()`,
  `mobile_game.js`) le masque sur mobile uniquement quand `activeMode`
  diffère réellement de l'onglet consulté ET que cet onglet est
  Bibliothèque/Exercice/Éditeur (jamais quand il leur appartient lui-même —
  Exercice a besoin de son propre bouton "Demander l'avis du coach", pas
  dupliqué dans la barre du bas mobile).
- `_clearGameAnalysisDisplay()` (nouvelle fonction, `game_analysis.js`) vide
  l'AFFICHAGE du rapport d'analyse (liste, statuts, barre de progression)
  sans toucher au cache `_gameAnalysisResults` (préserve la réutilisation
  automatique de l'issue #59) — appelée au chargement d'une autre partie
  (`parsePgn`, `board.js`), au démarrage de chaque mode de partie/exercice
  (`startFreeGameFromFen`/`startPedagogicGame`/`startOpeningGame`/
  `loadSelectedFinale`/`startFinaleDemo`/`startExercise`) et à chaque
  changement de mode (`switchModeTab`, `controls.js`).

## Tests (Playwright, émulation tactile 390×750 et 360×640)
Aucun vrai appel API/Socket.IO n'était possible depuis ce worktree : lancer
`app.py` charge `config.py`, qui écrit dans `~/ChessCoach/data` (hors
périmètre du worktree). `templates/index.html` a donc été rendu en statique
avec Jinja2 (sans passer par Flask/config.py, aucune donnée personnelle
lue), servi par un simple serveur HTTP local, et piloté par Playwright ;
l'état d'une partie en cours a été simulé en assignant directement les
variables JS globales (`pedagogicActive`, `activeMode`, etc.) plutôt que via
un aller-retour serveur réel — limite documentée, aucun appel Claude/
Stockfish n'a été exercé.

- Point 1 : liste ouverte depuis chaque mode, page défilée (800px) ou non —
  toujours visible entièrement dans le viewport, juste sous le sélecteur ;
  clic en dehors la ferme.
- Point 2 : arrivée en pédagogique depuis une page défilée — scrollY revient
  à 0, plateau complet + boutons "Jouer les Blancs/Noirs" visibles, jamais
  d'état réduit.
- Point 3 — tailles mesurées :
  - Mode jeu (partie pédagogique, avant le premier coup) : 390×750 → plateau
    228px (58,5% largeur / 30,4% hauteur) ; 360×640 → 170px (47,2% largeur /
    26,6% hauteur). En pleine partie (boutons Reprendre/Abandonner affichés,
    passent sur 2 lignes à 360px) : 390×750 → 201px ; 360×640 → 170px
    (plancher `GAME_BOARD_MIN_SIZE`, cf. Limites).
  - Bibliothèque/Éditeur (`.mobile-wide-board`) : 390×750 → 338px (86,7%
    largeur) ; 360×640 → 308px (85,6% largeur) — nettement au-dessus du
    seuil pré-#69 (80,5%).
  - Exercice (formule générale inchangée) : 390×750 → 225px, 360×640 →
    192px — identiques px pour px à la formule d'avant cette issue
    (`min(30vh,420px,calc(100vw-76px))`), confirmant l'absence de
    régression.
  - Plateau réduit (défilement) : 390×750 → 164px ; 360×640 → 151px (cible
    150-170px respectée).
- Point 4 : défilement en onglet Coach → plateau réduit visible (vraie
  mini-vue de la position, plus de bande texte), ligne d'état lisible en
  dessous, boutons masqués, onglets visibles ; tap → retour au plateau
  complet (scrollY=0, classe `board-compact` retirée).
- Point 5 : menu "..." → `["Extraire le FEN", "Importer un PGN", "Coût
  API"]`, pas de "Bibliothèque".
- Point 6 : `activeMode="pedagogic"` + onglet Bibliothèque →
  `#shared-mode-controls` masqué (`display:none`), classe
  `mode-controls-mismatch` posée.
- Aucun débordement horizontal détecté (`scrollWidth <= clientWidth`) sur
  Bibliothèque ni en mode jeu, aux deux largeurs testées.
- Grand écran (1400px) : en-tête visible, `#mobile-mode-bar-slot` vide
  (`display:block`, sans effet), plateau 560px (formule desktop `min(70vh,
  560px)`, inchangée), `mode-tab-bar` reste dans son panneau d'origine,
  `mobile-game-active` jamais posée quel que soit l'onglet — comportement
  desktop intégralement inchangé.
- Aucune erreur JavaScript de page relevée (`page.on("pageerror")`) sur
  l'ensemble des scénarios ci-dessus. `node --check` OK sur les 9 fichiers
  JS modifiés.

## Limites
- La fourchette "44-46% de la hauteur d'écran" demandée pour le plateau des
  modes de partie est un PLAFOND, pas une valeur garantie : sur les
  téléphones courants (~640-800px de haut), la garantie des ~180px de
  contenu visible sous les onglets (elle aussi demandée) est presque
  toujours la contrainte la plus stricte des deux, et donne un plateau plus
  petit que 44% (mesuré : 26,6-30,4% avant la première partie, moins encore
  pendant une partie active sur le plus petit écran testé). Choix assumé :
  la garantie "au moins 180px visibles" a été traitée comme prioritaire sur
  le pourcentage, car sa violation reproduisait un symptôme proche du bug
  d'origine (contenu invisible sans indice de défilement) — seule la valeur
  `GAME_BOARD_MIN_VISIBLE_BELOW_TABS` (`mobile_game.js`) est à ajuster pour
  changer cet arbitrage.
- Sur le plus petit écran testé (360×640), PENDANT une partie active, les 3
  boutons de `#shared-mode-controls` ("Reprendre mon coup"/"Abandonner"/
  "Demander l'avis du coach") passent sur 2 lignes et consomment environ
  128px à eux seuls — dans ce cas précis, ni le plafond des 180px visibles
  ni celui des 44-46% ne sont atteints : le plateau reste bloqué à son
  plancher de sécurité (`GAME_BOARD_MIN_SIZE = 170px`, aligné sur le haut de
  la fourchette du plateau réduit, pour ne jamais devenir plus petit que
  lui) et le contenu visible sous les onglets tombe alors à environ 120px.
  Compromis documenté plutôt que corrigé plus avant (aurait nécessité de
  retravailler la disposition de `#shared-mode-controls` lui-même, hors
  périmètre de cette issue).
- Aucun vrai appel API Claude ni Stockfish n'a été exercé (cf. "Tests"
  ci-dessus) — seul le comportement DOM/CSS/JS a été vérifié. Les captures
  Playwright sont dans `.test_screens/` (non commité, worktree local
  uniquement).
- `.test_render.html` (rendu Jinja2 statique utilisé pour les tests) a été
  supprimé après usage — non commité.
