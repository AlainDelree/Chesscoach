# Changelog — Issue #70

## Écran de partie mobile : plateau fixe, onglets Coach/Lignes/Analyse/Coups, bande compacte (maquette Claude Design)

- Contexte : la disposition mobile précédente (issue #69) gardait déjà le
  plateau visible en permanence, mais tout le reste (chat, lignes, analyse,
  historique, contrôles de mode) restait empilé verticalement. Alain a fait
  dessiner une nouvelle disposition avec Claude Design
  (`design/partie_mobile/`, 14 écrans) : plateau fixe ~36-40% d'écran, barre
  de navigation et barre d'actions compactes, quatre onglets internes
  (Coach/Lignes/Analyse/Coups) sous lesquels seule la zone de contenu
  défile, bande compacte du plateau pendant le défilement ou le clavier
  ouvert, pastille de modèle cliquable et menu "...". Uniquement sur mobile
  (<900px) et uniquement pour les modes partie libre/pédagogique/ouverture/
  finales (`body.mobile-game-active`, posée par `mobile_game.js`) — le mode
  exercice, la bibliothèque/revue, l'éditeur de position et le grand écran
  gardent la disposition existante (issues #50/#63/#65/#69), entièrement
  inchangée en dehors de cette classe (vérifié à 1440px, capture dans le
  rapport de clôture).
- Aucune logique de jeu dupliquée ni réécrite : tout le nouveau fichier
  `static/mobile_game.js` déplace des nœuds DOM existants entre leur
  emplacement d'origine et les nouveaux onglets/menu (même principe que
  `placeModeTabBarForViewport`/`_placeMobileRelocatablesForViewport`,
  `controls.js`, issues #63/#69) — `board.js`/`game_coach_lines.js`/
  `game_analysis.js`/`llm_model.js`/`usage_tokens.js` retrouvent leurs
  éléments par id, peu importe leur parent réel.

### static/mobile_game.js (nouveau)

- `isGameUiActive()` : vrai si <900px ET l'onglet de mode affiché
  (`currentModeTab`, `controls.js`) est free/pedagogic/opening/finale.
- `onGameUiRefresh()` : rafraîchissement central, appelé depuis
  `controls.js` (hooks ajoutés en fin de `switchModeTab`/
  `updateSharedControlBar`, cette dernière déjà appelée par tous les modes à
  chaque démarrage/abandon/reprise/fin de partie — un seul point de
  branchement couvre toutes les transitions). Bascule la classe
  `mobile-game-active` sur `<body>`, déplace les blocs existants (panneau du
  coach, tableau "Lignes du coach", panneau d'analyse de partie, historique
  des coups, sélecteur de modèle, compteur de jetons, barre de navigation,
  barre d'actions partagée, boutons "Jouer les Blancs/Noirs" pédagogique/
  ouverture, onglets) vers leur nouvel emplacement, ou les restaure à leur
  place d'origine si le mode jeu n'est plus actif.
- `switchGameTab`/`_gameTabMarkNovelty` : les quatre onglets internes, avec
  point de nouveauté (petit point non cliquable, donc pas en terracotta) sur
  Lignes/Analyse quand du contenu arrive pendant qu'un autre onglet est
  affiché — appelé depuis `game_coach_lines.js`/`game_analysis.js`.
- `gameMenuToggleModelPopup`/`gameMenuToggleDropdown`/`gameMenuClose` :
  pastille de modèle (miroir texte de `#llm-model-selector`, qui reste la
  source de vérité — déplacé tel quel dans le popup) et menu "..." (Extraire
  le FEN, Importer un PGN, Bibliothèque, contrôles propres au mode actif,
  compteur de jetons, Coût API).
- `_updateBoardCompactState`/`boardCompactExpand` : bascule plateau complet/
  bande compacte sur défilement de page (`window.scrollY`) ou focus du champ
  de question (clavier), jamais pendant une lecture/preview de ligne du
  coach (plateau alors affiché en grand, point 6) ; un tap sur la bande
  remonte en haut de page et enlève le focus, ce qui la fait redevenir
  pleine via les mêmes conditions.
- `_updateActionBarState` : avant une partie pédagogique/ouverture (choix de
  camp), affiche les deux gros boutons "Jouer les Blancs/Noirs" + "Choisis
  ta couleur pour commencer" à la place de `#shared-mode-controls` ; pour
  partie libre/finales (pas de choix de camp, voir écarts ci-dessous), un
  message "Utilisez le menu ⋯ pour démarrer une partie." ; pendant une
  partie, `#shared-mode-controls` normal (3 boutons, sans titre ni texte de
  statut) ; en fin de partie, tout est masqué (le bandeau de résultat
  existant, `#game-over-banner`, suffit — voir écart ci-dessous).

### templates/index.html

- En-tête combiné (point 1) : `#mobile-mode-bar-slot` devient une rangée
  flex avec le sélecteur de mode existant (inchangé), `#game-model-pill`
  (pastille, texte initial rendu côté serveur) et `#game-menu-btn`
  (bouton "..."), plus les popups `#game-model-popup`/`#game-menu-dropdown`.
  `<header>` (sélecteur de modèle complet, compteur de jetons, lien Coût
  API) masqué en mode jeu mobile — son contenu utile est déplacé dans
  pastille/menu par JS, rien n'est dupliqué. `position: relative` ajouté à
  `#mobile-mode-bar-slot` (sans quoi les popups, `position: absolute; top:
  100%`, se positionnaient par rapport à un ancêtre bien plus haut que
  l'écran — bug repéré avec Playwright, cf. tests).
- `#board-sticky-wrap` restructuré : `#board-full-view` (matériel, plateau,
  nouvelle ligne d'état `#game-status-line`) et `#board-compact-strip`
  (bande ~56px, basculés par la classe `.board-compact`) ; `--bd-size`
  ramené à `min(36dvh, 400px, calc(100vw - 76px))` en mode jeu mobile
  (dvh pour la hauteur dynamique d'écran, point 10). La barre de navigation
  (`#review-controls`), la barre d'actions (`#shared-mode-controls`), les
  bandes avant-partie (`#mobile-pedagogic-start-slot`/
  `#mobile-opening-start-slot`/`#mobile-game-idle-msg`) et la barre d'onglets
  (`#game-tab-bar`) sont déplacées par JS COMME ENFANTS de
  `#board-sticky-wrap` (déjà collé en haut, issue #69) pour que "tout ce qui
  précède l'onglet actif" reste fixe — masquées ensemble (`!important`,
  au-dessus du `style.display` posé par JS) quand la bande compacte est
  active, conformément au point 5 ("le plateau complet ET les deux barres de
  boutons sont remplacés par une bande").
- Quatre onglets (`#game-tabs-column`, point 1) : `game-tab-panel-coach`
  reçoit le panneau du coach existant (`#coach-drawer-panel`, nouvel id) ;
  `game-tab-panel-lignes` reçoit `#game-coach-lines` ; `game-tab-panel-analyse`
  reçoit `#game-analysis-panel` (voir "Analyse" ci-dessous) ;
  `game-tab-panel-coups` reçoit `#historique` (table restylée par le CSS
  existant, aucune réécriture). Les messages automatiques "je joue ..."
  restent masqués sur mobile (issue #69 point 3, inchangé — la classe
  `.coach-bubble-auto-move` ne dépend pas du mode jeu).
- Contrôles propres à chaque mode (point 8) : `#free-extra-controls`/
  `#pedagogic-extra-controls`/`#opening-extra-controls`/
  `#finale-extra-controls` enveloppent chacun le contenu déjà existant de
  leur panneau (inchangé), déplacés dans `#game-menu-mode-extra` (menu
  "...") pour le mode actuellement affiché — **choix retenu : le menu
  "...", le plus simple à mettre en œuvre** (un seul emplacement suffit
  pour les quatre modes, contre un habillage variable en tête de l'onglet
  Coach). `#opening-start-buttons` (nouveau, mécanique identique à
  `#pedagogic-start-buttons`) sépare le choix de camp des contrôles
  secondaires (nom d'ouverture, suggestions).
- `#review-move-info-row`/`#fen-extract-status` masqués en mode jeu mobile
  (remplacés par `#game-status-line` et le menu) ; `#mobile-bottom-slot`
  (import PGN générique, navigation dans la collection, programme
  d'entraînement) masqué aussi — ces éléments restent dans la Bibliothèque,
  comme demandé (point 3), sans changement pour les autres modes mobiles.
- `#game-analysis-progress` : indicateur d'attente sans compteur pendant
  l'analyse (barre indéterminée, neutralisée par
  `prefers-reduced-motion: reduce`), classe posée/retirée par
  `game_analysis.js`.
- `html { overflow-anchor: none; }` (hors media query, cf. bug ci-dessous).

### static/board.js

- `updateGameStatusLine()` (nouveau) : "Coup N · coup" (même convention de
  numérotation que `review-move-info` existant — nombre de demi-coups joués,
  pas le numéro de coup plein de la maquette, pour rester cohérent avec le
  reste de l'appli) + matériel capturé condensé (pastille de la couleur en
  avance, "=" à égalité) + camp au trait (lu dans le FEN complet pour les
  modes interactifs, par parité pour la revue qui démarre toujours de la
  position standard). Appelée depuis `renderHistory()` (déjà invoquée après
  chaque coup par tous les modes et par la revue) — alimente à la fois
  `#game-status-line` et `#board-compact-strip`.
- `showGameOverBanner`/`hideGameOverBanner` : posent/retirent la classe
  `game-over-active` sur `<body>`, lue par le CSS du mode jeu mobile pour
  masquer la barre d'actions/le bandeau avant-partie quand le bandeau de
  résultat est affiché (point 4).

### static/controls.js

- Deux hooks minimaux (`if (typeof onGameUiRefresh === "function")
  onGameUiRefresh();`) en fin de `switchModeTab`/`updateSharedControlBar` —
  aucune dépendance dure vers `mobile_game.js` (no-op s'il n'est pas chargé).

### static/opening.js, static/pedagogic.js

- `placeOpeningStartButtonsForViewport()` (nouveau, mécanique identique à
  `placePedagogicStartButtonsForViewport()` existant) : déplace
  `#opening-start-buttons` vers `#mobile-opening-start-slot` sur mobile, tant
  qu'aucune partie d'ouverture n'est en cours ET que l'onglet "opening" est
  affiché. `placePedagogicStartButtonsForViewport()` reçoit la même
  condition supplémentaire sur `currentModeTab` (corrige au passage un
  travers pré-existant de l'issue #65 : ces boutons pouvaient apparaître
  au-dessus du plateau même en étant sur un autre onglet, tant qu'aucune
  partie pédagogique n'était active).

### static/game_coach_lines.js, static/game_analysis.js

- Points de nouveauté (point 7) : `_gameTabMarkNovelty("lignes")` après
  ajout d'une ligne (coach ou Stockfish) ; `_gameTabMarkNovelty("analyse")`
  après un rapport d'analyse ou une sélection de coups décisifs par le
  coach.
- `_setReviewControlsHiddenForLinePlayback()` (`game_coach_lines.js`) :
  pendant la lecture/preview d'une ligne, masque `#review-controls`
  uniquement si `body.mobile-game-active` (sans effet sur la bibliothèque/
  revue, dont le comportement mobile existant est inchangé) — la barre
  `#board-lines-command-bar` ("En lecture · Stop · Revenir à la partie")
  la remplace visuellement (point 6).
- `game_analysis.js` : classe `.show` posée/retirée sur
  `#game-analysis-progress` autour de l'appel `lancerAnalyse`.

### static/llm_model.js

- `_llmModelSetActive()` met aussi à jour `#game-model-pill` (premier mot du
  libellé actif, comme `.llm-model-compact` existant dans l'en-tête) — pur
  miroir d'affichage, `#llm-model-selector` reste la seule source de vérité
  et le seul point d'émission de `set_llm_model`.

## Bug de défilement diagnostiqué et corrigé (scroll anchoring)

- Constaté avec Playwright (émulation 390×750) : au passage en bande
  compacte pendant un défilement, la page revenait instantanément tout en
  haut. Cause : `#board-sticky-wrap` (`position: sticky`) rétrécit d'environ
  450-500px (plateau complet + deux barres de boutons + onglets remplacés
  par une bande ~56px) — Chromium/Firefox tentent de compenser ce
  rétrécissement par un ajustement automatique du défilement ("scroll
  anchoring", CSS Scroll Anchoring Module) qui, ici, dépasse la position de
  défilement courante et la ramène à 0. Deux correctifs complémentaires :
  `html { overflow-anchor: none; }` (l'ancre choisie par le navigateur peut
  être n'importe quel enfant de la page, la propriété ne s'hérite pas — une
  règle scopée à `#board-sticky-wrap` seul s'est révélée insuffisante lors
  des tests) et `body.mobile-game-active #app { min-height: 160dvh; }` (sans
  quoi, sur une page encore courte — ex. juste après le début d'une partie,
  onglet Coach vide — rétrécir en dessous de la hauteur de la fenêtre forçait
  quand même un défilement à 0, qui annulait aussitôt le passage en bande
  compacte : va-et-vient observé de façon non déterministe sur plusieurs
  lancements). `overflow-anchor` n'est pas supporté par Safari (l'ajoute
  depuis plusieurs versions de Chrome/Firefox, utilisés dans les tests) —
  limite documentée, résiduelle sur cette plateforme précise.

## Écarts avec la maquette (et raisons)

- **Modes ouverture et finales (point 8)** : contrôles propres (nom
  d'ouverture + suggestions ; sélection de la finale + camps inversés +
  démonstration) placés dans le menu "..." plutôt qu'en tête de l'onglet
  Coach — choix le plus simple (un seul emplacement, pas d'habillage
  variable selon le mode). Conséquence pour l'ouverture : si le nom de
  l'ouverture est vide, le message d'erreur ("Indiquez le nom d'une
  ouverture.") s'affiche dans `#opening-status`, à l'intérieur du menu —
  moins visible que s'il était sur l'écran principal, limite acceptée plutôt
  que dupliquer ce texte ailleurs.
- **Partie libre et travail de finales — pas de "choix de camp" avant-partie
  (point 4)** : la maquette montre deux gros boutons "Jouer les Blancs/
  Noirs" avant toute partie pédagogique, mais ce choix n'a pas de sens pour
  ces deux modes (partie libre : les deux camps sont joués librement, aucun
  `startFreeGame(camp)` ; finales : le camp est fixé par la position-type
  elle-même, "camps inversés" en tient lieu). Remplacé par un message
  "Utilisez le menu ⋯ pour démarrer une partie." — ces deux modes démarrent
  via leurs propres contrôles (désormais dans le menu "..."), pas par un
  choix de couleur.
- **Nouveau numéro de coup vs maquette** : "Coup N" reprend la convention
  déjà utilisée par `review-move-info` (nombre de demi-coups joués), pas le
  numéro de coup plein affiché par la maquette (ex. "Coup 6" pour 6.Nxe4
  dans la maquette correspondrait à "Coup 11" avec la convention de l'appli,
  11 demi-coups joués) — cohérence avec le reste de l'appli plutôt que deux
  numérotations différentes.
- **Bande compacte sans mini-plateau visuel (point 5)** : la maquette montre
  une miniature de l'échiquier dans la bande compacte. Implémenté comme une
  bande de texte (coup, matériel, camp au trait, chevron) sans miniature —
  dupliquer/déplacer le rendu réel du plateau (`#board`, avec ses
  gestionnaires de clic) dans un second conteneur mis à l'échelle aurait
  ajouté un risque de régression (coordonnées de clic, flèches SVG) pour un
  gain visuel jugé secondaire ; fonctionnellement équivalent (coup/matériel/
  trait toujours visibles), visuellement plus simple que la maquette.
- **Bandeau de fin de partie (point 4)** : resté à son emplacement existant
  (au-dessus du plateau, issue #31, déjà très visible et collé en haut) au
  lieu de remplacer la barre d'actions à l'endroit où elle se trouvait — la
  barre d'actions/le bandeau avant-partie sont simplement masqués pendant ce
  temps (classe `game-over-active`), plutôt que de déplacer un composant
  existant et bien établi.
- **Analyse (point 9)** : mécanisme conservé tel quel (l'analyse se lance
  toujours dans la revue de bibliothèque, `analyserPartieCourante()`/
  `reviewMoves`, inchangé) — l'onglet Analyse du mode jeu affiche
  directement `#game-analysis-panel` (bouton, indicateur d'attente, rapport)
  par déplacement du même élément, sans le dupliquer ni reconstruire un
  second chemin d'analyse. Intégrer l'analyse complètement dans l'écran de
  partie (sans passer par la bibliothèque) aurait demandé de dupliquer l'état
  `_gameAnalysisResults`/`reviewMoves` ou de le rendre accessible aux quatre
  modes de partie simultanément — jugé trop invasif pour cette issue.

## Tests

- Émulation Playwright (chromium headless, `is_mobile`/`has_touch`) à
  390×750 puis 360×640 : partie pédagogique en priorité (démarrage réel avec
  Stockfish — pas de clé API nécessaire pour l'adversaire —, un coup joué,
  historique/statut/matériel corrects), contrôle rapide en partie libre
  (message avant-partie), ouverture (boutons + menu), finales (message
  avant-partie + menu) ; onglets Coach/Lignes/Analyse/Coups (bascule,
  contenu réel après chargement d'une partie de 120 demi-coups depuis la
  bibliothèque — historique coloré par qualité de coup, panneau d'analyse
  fonctionnel avec Stockfish réel) ; plateau qui passe en bande compacte au
  défilement (`window.scrollY`) et qui revient (tap sur la bande) ; clavier
  simulé (focus du champ de question + réduction de la hauteur de fenêtre
  d'environ 300px, 750→450) ; Play/Stop/Revenir à la partie non testé avec
  un vrai appel API (voir ci-dessous) mais le câblage
  `_setReviewControlsHiddenForLinePlayback`/bande visible en lecture vérifié
  par lecture de code ; points de nouveauté (appel direct de
  `_gameTabMarkNovelty`, apparition/disparition vérifiées) ; pastille de
  modèle et menu "..." (ouverture, positionnement, Extraire le FEN,
  Bibliothèque) ; fin de partie par abandon (bandeau + barre d'actions
  masquée) — **fin par mat non déclenchée dans les tests** (aucun moyen
  pratique de forcer un mat contre Stockfish dans le temps imparti ; le
  chemin de code est strictement identique à l'abandon,
  `showGameOverBanner`/`hideGameOverBanner`, seul le message diffère) ;
  aucun débordement horizontal mesuré à 360×640 (`scrollWidth -
  clientWidth === 0`) ; exercice/bibliothèque/éditeur et rendu à 1440px
  vérifiés inchangés (captures identiques à avant l'issue, aucune classe
  `mobile-game-active` posée). Comparaison visuelle qualitative avec les
  captures `design/partie_mobile/png/` : disposition proche (en-tête
  combiné, plateau fixe, ligne d'état, nav compacte, barre d'actions,
  onglets), écarts listés ci-dessus.
- Aucune `ANTHROPIC_API_KEY` disponible dans l'environnement de cette
  session (`config.LLM_API_KEY` vide) : les appels au coach (commentaire
  après un coup, sélection de coups décisifs, chat libre) n'ont pas pu être
  exercés avec un vrai modèle — testés en confirmant l'absence d'erreur JS
  et le message de repli attendu ("Clé API Claude manquante"/"Sélection du
  coach indisponible"). Stockfish (adversaire pédagogique/ouverture/finales,
  analyse de partie) a en revanche été exercé réellement (moteur système
  détecté, aucune clé requise).
- Serveur de test lancé sur le port 5051 (le port 5000 sert l'instance
  réelle d'Alain, non touchée) via le venv `~/ChessCoach/venv` ; arrêté en
  fin de session.
- `py_compile` sur les fichiers Python existants : OK (aucun changé par
  cette issue). Vérification de la fermeture des balises de
  `templates/index.html` (parseur HTML tolérant) : aucune balise non
  fermée/mal imbriquée détectée.

## Limites connues

- `#fen-extract-status` (résultat visuel d'"Extraire le FEN") reste masqué
  en mode jeu mobile — la copie presse-papiers fonctionne, mais aucun retour
  visuel n'est affiché dans ce mode (regression mineure par rapport au
  grand écran/aux autres modes mobiles, où ce texte reste visible).
- Le nom de l'ouverture vide affiche son message d'erreur dans le menu
  "..." plutôt que sur l'écran principal (cf. écarts ci-dessus).
- La bande compacte du plateau est un résumé textuel, pas une miniature du
  plateau réel (cf. écarts ci-dessus).
- `overflow-anchor: none` n'a pas d'effet sur Safari — le bug de
  défilement corrigé ici pourrait resurgir sur cette plateforme (non testée,
  hors du navigateur de test disponible dans ce worktree).
- Fin de partie par mat non testée en conditions réelles (voir section
  Tests) — seul le chemin par abandon, identique en code, a été exercé.
