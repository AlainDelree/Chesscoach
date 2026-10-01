# Changelog — Issue #74

## Mobile : taille du plateau réglable par l'utilisateur (menu « ... »)

- Nouveau réglage « Taille du plateau » dans le menu « ... » des modes de
  partie mobile (libre/pédagogique/ouverture/finales, `<900px`) : trois
  choix (Compact/Normal/Grand), 3 boutons côte à côte sous un titre de
  section, directement sous « Importer un PGN » (`templates/index.html`,
  `#game-menu-dropdown`). Normal reprend exactement le comportement de
  l'issue #71 (confirmé par mesure : tailles identiques avant/après sur un
  même écran).
- `GAME_BOARD_SIZE_PRESETS` (`static/mobile_game.js`) est l'unique endroit
  où sont définis les 3 pourcentages visés et leur garantie de contenu
  visible sous les onglets : Compact 38 % / 180px, Normal 44 % / 180px,
  Grand 52 % / 120px (garantie abaissée exprès — le choix explicite
  d'Alain prime sur elle). `--bd-size-game-pct` (posée par
  `_applyGameBoardSizeChoice`) remplace le `44dvh` auparavant codé en dur
  dans `--bd-size` (`body.mobile-game-active`, `templates/index.html`) ;
  `_updateGameBoardMaxSize` lit désormais `minVisibleBelowTabs` du préréglage
  actif au lieu d'une constante unique. Le plancher `GAME_BOARD_MIN_SIZE`
  (170px, taille du plateau réduit) reste appliqué quel que soit le
  réglage, pour ne jamais descendre en dessous sur les très petits écrans.
- Choix persisté par appareil via `localStorage`
  (`chesscoach-mobile-board-size`), avec `try/catch` à la lecture et à
  l'écriture (navigation privée stricte, quota) — en cas d'échec, le
  réglage reste actif pour la session en cours mais non persisté, sans
  jamais faire planter l'appli. Valeur par défaut : Normal. Appliqué dès
  `DOMContentLoaded` (avant le premier calcul de `--bd-size-game-max`, pour
  ne pas perdre un cycle de rafraîchissement) et immédiatement au clic
  (`gameBoardSizeSet`, sans recharger la page) ; la mise à jour après
  rotation d'écran repose sur l'écouteur `resize` déjà en place depuis
  l'issue #71 (`--bd-size-game-pct` suit nativement les unités `dvh`, et
  `_updateGameBoardMaxSize` se redéclenche).
- Mode exercice, Bibliothèque/Revue PGN, éditeur de position, plateau
  réduit au défilement et disposition grand écran inchangés : le réglage
  n'agit que sur `--bd-size-game-pct`, consommée uniquement par la règle
  `body.mobile-game-active` ; la règle `.board-compact` (plateau réduit)
  continue d'imposer son propre `clamp(150px, 42vw, 170px)`, prioritaire,
  sans lien avec le nouveau réglage.
- **Bug préexistant corrigé au passage** (issues #63/#70/#71, sans rapport
  direct avec cette tâche mais touchant directement sa zone d'affichage) :
  `#mobile-mode-bar-slot` (pastille de modèle + menu « ... », donc
  désormais aussi les 3 nouveaux boutons) n'était caché par AUCUNE règle
  CSS au-dessus de 900px — seule la media query `<900px` le passait en
  `display:flex` ; un `<div>` étant `display:block` par défaut, tout son
  contenu statique (y compris `#game-menu-dropdown`, dont le `display:none`
  n'était lui aussi posé que dans cette même media query) s'affichait donc
  en pleine page au-dessus de l'en-tête sur grand écran. Repéré en testant
  cette issue (captures d'écran desktop) : sans correctif, les 3 nouveaux
  boutons Compact/Normal/Grand auraient rendu ce défaut plus visible
  encore. Correctif : `#mobile-mode-bar-slot { display: none; }` ajouté
  AVANT la media query `<900px` (`templates/index.html`) — placée après
  cette media query, la même règle aurait annulé le `display:flex` mobile
  (déclaration la plus basse dans le fichier l'emporte à spécificité égale,
  même mécanisme de cascade que
  documenté dans le rapport de clôture de l'issue #71). Vérifié identique
  à l'état d'avant cette issue sur grand écran après correctif (plateau
  560px, aucun élément du menu visible hors media query).

### Tests (émulation Playwright/Chromium headless, pas de serveur Flask réel
disponible hors ligne — voir « Limites » ci-dessous)

- 390×750 et 360×640, mode « partie libre », avant et pendant une partie
  réelle (`startFreeGame()`) :
  - Avant partie, 390×750 : Compact 263px, Normal 263px (identique),
    Grand 323px. Pendant partie (chrome plus grand) : Compact 220px,
    Normal 220px (identique), Grand 280px.
  - Avant partie, 360×640 : Compact/Normal 170px (plancher), Grand 213px.
    Pendant partie : Compact/Normal/Grand tous à 170px (plancher — sur cet
    écran, même la garantie réduite de Grand ne suffit pas à dépasser la
    taille du plateau réduit pendant une partie active, comportement
    voulu).
  - Aucun débordement horizontal détecté (`scrollWidth`/`clientWidth`)
    dans aucune configuration testée.
- Persistance : réglage Grand choisi, rechargement de page (nouvelle
  requête HTTP complète, pas juste un re-render JS) → Grand toujours actif
  et appliqué (323px/213px selon l'écran), bouton actif correctement
  surligné dans le menu.
- Application immédiate : chaque clic Compact/Normal/Grand change la
  taille du plateau sans rechargement, vérifié par mesure directe après
  chaque clic.
- Rotation d'écran (viewport 390×750 → 750×390 avec Grand actif) :
  recalcul automatique sans action manuelle (plateau retombe à 170px, le
  plancher, l'espace disponible en paysage avec le chrome fixe étant plus
  restreint).
- Plateau réduit au défilement, avec Grand actif et une partie en cours :
  `window.scrollTo(0, 300)` déclenche bien `.board-compact`
  (`clamp(150px, 42vw, 170px)`, mesuré 164px à 390px de large et 151px à
  360px, conforme à la formule), la zone à onglets reste défilable
  (`scrollHeight >= clientHeight`), et le tap sur le plateau réduit
  restaure le plateau complet à la taille Grand (280px/170px) — aucune
  régression du comportement de l'issue #71 point 4.
- Menu « ... » : 3 boutons de 100×36px chacun à 360px de large, dropdown
  entièrement contenu dans le viewport (droite à 352px sur 360px),
  lisible, état actif visuellement distinct (fond vert clair, même
  habillage que les autres « items de menu actifs » de l'appli).
- Mode exercice (`mobile-game-active` reste `false`), Bibliothèque
  (`mobile-wide-board` reste `true`, 338px) et grand écran (1400×900,
  560px, slot masqué) : mesurés identiques à l'état attendu, aucune
  régression.
- Captures d'écran prises (menu replié/déployé, Compact/Normal/Grand côte
  à côte, plateau réduit au défilement, comparaison desktop avant/après le
  correctif du bug préexistant).

### Limites

- Aucun appel réel à l'API Claude ni au backend Flask/SocketIO : le
  worktree ne dispose pas de `flask_socketio` installé et la tâche
  indique `RESEAU | non` (pas d'installation de paquet via pip). Les
  tests ont donc porté sur le gabarit `templates/index.html` rendu
  directement par Jinja2 (hors `app.py`, avec un contexte minimal simulé)
  et servi en statique, piloté par Playwright/Chromium headless
  (viewports mobiles, `has_touch=True`, clics réels sur les boutons) —
  clairement une émulation plutôt qu'un vrai appel API, mais qui exerce le
  code CSS/JS réel du dépôt (aucune logique dupliquée ni simulée à la
  main) plutôt qu'une lecture statique du code.
- `demarrerPartieLibre` n'existe pas : la fonction réelle est
  `startFreeGame()` (`static/free_play.js`), utilisée pour les tests
  « pendant une partie ».
- Pas de test sur un véritable appareil physique (GSM/PC) ni dans un
  vrai navigateur mobile (Safari iOS, Chrome Android) — seule l'émulation
  de viewport/tactile de Chromium a été utilisée.
