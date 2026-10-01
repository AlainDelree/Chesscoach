# Changelog — Issue #81

## Mobile : place pour lire le coach, tailles du plateau distinctes, onglets vides, taille du plateau dans tous les modes

Suite de l'issue #80 (corrections après test GSM, 2/2) : `static/mobile_game.js`,
`static/board.js`, `static/exercise.js`, `static/game_coach_lines.js`,
`static/game_analysis.js`, `templates/index.html`.

### Point 1 — Plateau réduit, plus de déclencheurs

- `_updateBoardCompactState()` (`mobile_game.js`) inchangée (scroll/clavier) ;
  nouvelle fonction `_activeTabContentOverflows()` (avec une marge de 24px,
  `BOARD_COMPACT_SCROLL_THRESHOLD`, pour ne pas basculer en réduit sur le
  seul message d'état vide d'un onglet) et `_autoCompactForOverflow()`
  (additive uniquement — ne referme jamais le plateau réduit toute seule),
  appelées après `switchGameTab()` et à l'arrivée de chaque réponse du coach
  (`_mobileGameOnCoachMessage()`, hooké depuis `_coachRenderBubble()`,
  `board.js` — pas pour les annonces automatiques "je joue ...").
- `_forceBoardFull()` + `_mobileGameOnMoveCountChanged()` : un coup
  réellement joué (compte de coups en hausse, mesuré dans `renderHistory()`,
  déjà appelée après chaque coup tous modes confondus) redonne sa taille
  complète au plateau, même si l'onglet affiché reste trop long pour l'écran.
  "Lance une lecture avec Play" était déjà couvert par le garde-fou existant
  (`_linePlaybackActive()`).
- Mesuré (Playwright, 390×750, free play, 1 coup joué) : part de hauteur
  disponible pour le contenu sous le plateau — plateau complet 21% (Compact) /
  13% (Normal) / 8% (Grand) ; plateau réduit **71%** dans les trois cas (taille
  fixe `clamp(150px,42vw,170px)`, indépendante du réglage). À 360×640 :
  19%/16%/9% (complet) contre 68% (réduit).

### Point 2 — Compact/Normal réellement distincts

- `GAME_BOARD_SIZE_PRESETS` (`mobile_game.js`) : `minVisibleBelowTabs`
  désormais distinct par préréglage (150/100/60px au lieu de 180/180/120px
  partagés) — la garantie de contenu visible écrasait Compact et Normal sur
  la même valeur mesurée (`--bd-size-game-max`) sur un téléphone courant.
  Pct également ajusté : Compact 32% (était 38%), Normal 40% (était 44%),
  Grand inchangé (52%, mais garantie abaissée à 60px pour rester le plus
  grand des trois après l'ajustement de Normal).
- Mesuré (Playwright) : à 390×750, Compact=240px (32.0%), Normal=300px
  (40.0%), Grand=340px (45.3%, plafonné par la garantie/la largeur d'écran).
  À 360×640 : Compact=170px (26.6%, plancher `GAME_BOARD_MIN_SIZE`),
  Normal=190px (29.7%), Grand=230px (35.9%) — les trois valeurs restent
  distinctes aux deux largeurs, ordre Grand > Normal > Compact préservé.

### Point 3 — États vides des 4 onglets

- Lignes : nouvel élément statique `#game-tab-lignes-empty` dans
  `game-tab-panel-lignes` (texte « Aucune ligne pour l'instant. Demande au
  coach, par exemple : « Que devais-je jouer au coup 8 ? » »), basculé par
  `renderGameCoachLinesTable()` (`game_coach_lines.js`) selon
  `gameCoachLines.length`.
- Coups : `renderHistory()` (`board.js`) affiche désormais « Aucun coup pour
  l'instant. » (classe `.game-tab-empty-msg`, globale — s'applique aussi à
  `#historique-column` grand écran) au lieu d'une table réduite à sa seule
  ligne d'en-tête quand `total === 0` ; il se remplissait "seulement plus
  tard" simplement parce qu'aucun coup n'avait encore été joué — pas un bug
  de remplissage, confirmé par test.
- Analyse : nouvel élément `#game-analysis-help` + nouvelle fonction
  `_updateGameAnalysisAvailability()` (`game_analysis.js`, appelée depuis
  `onGameUiRefresh()`) — bouton grisé et phrase « Disponible quand la partie
  est terminée. » tant que la partie en cours (un des 4 modes de partie)
  n'est pas terminée ; statut par défaut « Analyse non lancée. » tant
  qu'aucun résultat n'est en mémoire. Toujours disponible hors contexte "en
  place" (Bibliothèque/Revue PGN).

### Point 4 — Taille du plateau dans tous les modes

- `#game-model-pill`/`#game-menu-btn`/`#game-menu-dropdown` (menu "...",
  déjà existant pour les 4 modes de partie) généralisés à TOUS les modes sur
  mobile (`templates/index.html`, CSS dé-préfixée de `body.mobile-game-active`
  vers la media query générale) ; "Extraire le FEN"/"Importer un PGN"
  restent réservés aux modes de partie (classe `.game-menu-item-gameonly`,
  masquée via `body:not(.mobile-game-active)`).
- `HEADER_ALWAYS_RELOCATE` (`mobile_game.js`, nouveau, séparé de
  `GAME_ALWAYS_RELOCATE`) : pastille de modèle + compteur de jetons
  rejoignent le menu dès qu'on est sur mobile, quel que soit le mode —
  `<header>` masqué partout sur mobile (menu commun unique, pas de doublon).
- Deux nouvelles familles de taille, même réglage partagé (une seule clé
  localStorage) que les 4 modes de partie : `EXERCISE_BOARD_SIZE_PCT`
  (22/30/38dvh, classe `body.mobile-size-exercise-active`, coordonnées/barre
  d'éval gardées visibles) et `WIDE_BOARD_SIZE_PCT` (46/58/68dvh, classe
  `body.mobile-wide-board` déjà existante, Bibliothèque/Revue PGN + Éditeur).
  Normal reproduit exactement l'ancienne valeur fixe de chaque mode (30dvh/
  58dvh) — défaut inchangé. Aucun débordement horizontal mesuré à 360px avec
  Grand (vérifié Playwright, les 4 familles de modes).

### Point 5 — Bibliothèque uniquement dans la Bibliothèque

- `#single-pgn-import-block` et `#training-program-panel` déplacés dans
  `templates/index.html` depuis `#board-column`/`#coach-column` (visibles
  dans TOUS les modes, grand écran compris — le vrai bug, pas seulement
  mobile) vers `#tab-panel-library`, aux côtés de `#pgn-lib-browse-block`/
  `#game-analysis-panel` déjà bien scopés eux.
- `mobile-non-library-tab` (nouvelle classe body, `mobile_game.js`,
  `onGameUiRefresh`) masque `#mobile-bottom-slot`/`#mobile-analysis-slot` en
  Exercice/Éditeur sur mobile (les 4 modes de partie l'étaient déjà via
  `mobile-game-active`) — ces slots recevaient ces blocs par
  `_placeMobileRelocatablesForViewport` (`controls.js`, inchangé)
  indépendamment de l'onglet actif, d'où leur présence partout avant ce
  correctif.
- Vérifié (Playwright, 390×750 et grand écran 1400×900) : les 3 blocs ne
  sont visibles qu'en Bibliothèque, dans tous les autres modes testés (Partie
  libre, Exercice, Éditeur).

### Point 6 — Conversation effacée à chaque nouvel exercice

- `exercise.js`, `startExercise()` (appelée par "Nouvel exercice"/"Autre
  catégorie" via `launchExerciseFromSheet()` et par "Exercice suivant" via
  `startNextExercise()`, point d'entrée unique) : remplace
  `coachNewSegment("Nouvel exercice")` (simple trait, historique visible
  conservé) par `coachClear()` (même effet que le bouton "Effacer" — vidage
  intégral messages + segment API). Le tableau "Lignes du coach" de
  l'Exercice était déjà vidé par ailleurs (`_exerciseResetCoachLines()`).
  Les autres modes (partie libre/pédagogique/ouverture/finales) gardent
  `coachNewSegment("Nouvelle partie")`, inchangé.

### Tests

Flask lancé dans le worktree avec `HOME` redirigé vers un répertoire
temporaire isolé (`/tmp/chesscoach-test-home`) — `config.DATA_DIR`/
`ENGINES_DIR` dérivent de `Path.home()`, aucune lecture/écriture dans le
`~/ChessCoach` réel. Playwright (Chromium, émulation tactile 390×750 et
360×640) : mesures de taille/pourcentages, bascule plateau réduit/complet
(coup joué, toucher, réponse simulée du coach), onglets vides/remplis,
réglage de taille dans les 4 modes + Bibliothèque/Éditeur, absence de
débordement horizontal à 360px, grand écran (1400×900) inchangé, et
enchaînement d'exercices (conversation vidée). Aucune clé API disponible
dans cet environnement (`ANTHROPIC_API_KEY` absente) : la "réponse du coach"
du point 1 a été simulée en appelant directement `_coachRenderBubble()`
plutôt qu'un vrai aller-retour API — comportement du déclencheur vérifié,
mais pas le contenu réel d'une réponse Claude. Aucune erreur console/page
JS relevée sur l'ensemble des passages (7 onglets, 4 onglets de jeu, 3
tailles de plateau).

### Limites

- Les pourcentages/garanties de hauteur restent des plafonds mesurés dans un
  état précis (1 coup joué, pas de bandeau de fin de partie ni de repli des
  boutons sur 2 lignes) — comme avant cette issue, l'état réel varie selon
  ce qui entoure le plateau à un instant donné.
- Le seuil de débordement de contenu (point 1) utilise une marge fixe de
  24px ; un contenu dépassant de quelques px seulement (en dessous de cette
  marge) ne déclenche pas le plateau réduit — compromis choisi pour éviter
  qu'un simple message d'état vide ne le déclenche à tort.
