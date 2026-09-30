# Changelog — Issue #69

## Mobile (modes de partie) : plateau toujours visible, panneau réorganisé et lecture des lignes sans redescendre

- Contexte : sur écran étroit, tous les éléments des modes de partie étaient
  empilés dans une seule colonne (issue #50/#63/#65/#68) — plus le panneau du
  coach/les lignes/l'analyse est long, plus le plateau est loin. Constat
  d'Alain sur GSM en partie pédagogique : pour poser une question au coach ou
  lire une ligne avec Play, il fallait descendre loin, puis remonter pour
  revoir le plateau. Correctif intermédiaire volontairement simple — une
  nouvelle maquette de l'écran de partie est demandée en parallèle à Claude
  Design (issue ultérieure). Uniquement sur mobile (<900px) ; disposition
  grand écran strictement inchangée (vérifiée pixel pour pixel à 1440px,
  voir rapport de clôture).

### templates/index.html

- Nouveau `#board-sticky-wrap` : regroupe le bandeau de fin de partie, le
  matériel capturé, le plateau (avec ses lettres/chiffres de coordonnées) et
  la nouvelle barre de lecture des lignes du coach. Sur mobile, ce nœud est
  déplacé par JS comme enfant direct de `#app` (et non laissé imbriqué dans
  `#board-column`, trop court pour qu'un `position: sticky` y reste collé
  jusqu'au bas d'une page mobile bien plus longue) — restauré à sa place
  d'origine dans `#board-column` sur grand écran. `--bd-size` recalculé
  (`min(30vh, 420px, calc(100vw - 76px))`) pour que le plateau tienne dans
  environ 42% de la hauteur d'écran en partie active.
- Nouveau `#board-lines-command-bar` : petite barre Stop/"Revenir à la
  partie" affichée dans la zone collée, juste sous le plateau, pendant et
  après la lecture d'une ligne du tableau "Lignes du coach" — remplie par
  `_updateBoardLinesCommandBar()` (game_coach_lines.js).
- Rangée de navigation (`#review-controls`) rendue compacte sur une seule
  ligne sur mobile (Précédent/Suivant/Retourner/Meilleur coup) ; "Extraire le
  FEN" part dans un nouveau menu "..." (`.review-more-menu`, piloté par
  `toggleReviewMoreMenu()`/`closeReviewMoreMenu()`, controls.js) — même
  `extraireFen()`, aucune logique dupliquée.
- Nouveaux points d'ancrage pour ce qui ne sert pas pendant la partie : le
  bloc PGN unique (`#single-pgn-import-block`), le bloc de navigation dans la
  collection PGN (`#pgn-lib-browse-block` : sélecteur de collection,
  recherche, filtre, liste des parties, import dans la collection) et le
  panneau "Programme d'entraînement" (`#training-program-panel`) sont
  déplacés sur mobile vers `#mobile-bottom-slot` (après l'historique des
  coups) ; le panneau "Analyser cette partie" (`#game-analysis-panel`) est
  déplacé vers `#mobile-analysis-slot`, juste après le tableau "Lignes du
  coach" dans le panneau du coach. Tous ces slots sont `display: contents`
  et sans effet sur grand écran.
- Le sélecteur de mode (`#mobile-mode-bar-slot`) n'est plus collé en haut de
  l'écran (`position: sticky` retirée) — il défile désormais normalement,
  le plateau reprenant ce rôle.
- Messages automatiques de coup joué ("Partie pédagogique — je joue d4" et
  équivalents ouverture/finales) masqués dans le chat sur mobile via une
  nouvelle classe `.coach-bubble-auto-move` — purement présentationnel,
  n'affecte ni `_coachHistory` ni les données envoyées à l'API.

### static/controls.js

- `_registerMobileRelocatable(id, slotId)` / `_placeMobileRelocatablesForViewport(isMobile)` :
  mécanique générique de déplacement de nœud DOM entre son emplacement
  d'origine et un slot mobile dédié (même principe que
  `placeModeTabBarForViewport`, déjà existant depuis l'issue #63), réutilisée
  pour les 4 blocs cités ci-dessus plutôt que de dupliquer cette logique une
  par une.
- `_updateStickyScrollPadding()` + `ResizeObserver` sur `#board-sticky-wrap` :
  synchronise `scroll-padding-top` (`<html>`) sur la hauteur RÉELLEMENT
  rendue du plateau collé, qui varie selon le bandeau de fin de partie, les
  boutons de démarrage rapide du mode pédagogique ou la barre de lecture des
  lignes — sans ça, `scrollIntoView` (rapport d'analyse, réponse du coach à
  une question posée) plaçait sa cible partiellement sous le plateau collé.
- `toggleReviewMoreMenu()`/`closeReviewMoreMenu()` + fermeture au clic
  ailleurs (même principe que le menu déroulant du sélecteur de mode).

### static/game_coach_lines.js

- `_updateBoardLinesCommandBar()` : pilote `#board-lines-command-bar` à
  partir de l'état déjà existant (`gameCoachLinesPlayingIdx`,
  `gameCoachLinesPreviewActive`) — appelle directement `gameLineToggle()`/
  `gameLinesRestore()` (aucune logique de lecture dupliquée), appelée à
  chaque `renderGameCoachLinesTable()`, donc à chaque changement d'état.

### static/board.js

- `_coachRenderBubble(role, text, allowPageScroll, extraClass)` : nouveau
  4e paramètre optionnel pour ajouter une classe CSS à la bulle
  (`coach-bubble-auto-move`), sans toucher au comportement existant des
  3 premiers paramètres.

### static/pedagogic.js, static/opening.js, static/finales.js

- Les 3 messages "je joue ..." passent `"coach-bubble-auto-move"` à
  `_coachRenderBubble`. Le message équivalent du mode exercice
  (`static/exercise.js`) n'est PAS concerné : il alimente aussi
  `_coachHistory` (continuité du chat libre) et reste affiché partout, comme
  demandé (mode exercice hors périmètre de cette issue).

### Bugs corrigés en cours de vérification (jamais visibles en usage normal, détectés par les tests ci-dessous)

- `#review-controls` (flex item d'un parent `flex-direction: column`)
  débordait de 6px à 360px de large — `min-width: auto` implicite des
  éléments flex, corrigé avec `min-width: 0`.
- `#mobile-bottom-slot` étant `display: contents`, l'`order` CSS posé
  dessus n'avait aucun effet (un élément `display: contents` disparaît de
  l'arbre de boîtes) — corrigé en posant `order: 5` directement sur les 3
  éléments déplacés (`#single-pgn-import-block`, `#pgn-lib-browse-block`,
  `#training-program-panel`), qui sans ce correctif s'affichaient AVANT le
  plateau plutôt qu'après l'historique.
- `#training-program-panel` (classe `.panel`, `padding: 14px 16px`)
  débordait de 32px avec `width: 100%` en `box-sizing: content-box` — ajout
  de `box-sizing: border-box` (même motif que `#shared-mode-controls`,
  déjà présent dans le gabarit).

## Tests effectués

Aucun serveur SocketIO disponible dans ce worktree (`flask_socketio` absent
de l'environnement Python accessible, `RESEAU: non` dans l'en-tête de
l'issue — aucune tentative d'installation) : impossible de faire un vrai
appel à l'API Claude ou à Stockfish. Tests faits avec Chromium/Playwright
(déjà en cache local) sur un petit serveur Flask temporaire (jamais commité,
supprimé en fin de tâche) qui rend `templates/index.html` avec un contexte
mocké minimal — vérifie donc la mise en page/le comportement JS réels, pas
les réponses du coach.

- 390×844 et 360×740 (émulation tactile Playwright) : plateau collé visible
  du haut jusqu'au bas de la page (vérifié en forçant un défilement jusqu'à
  `document.body.scrollHeight`) ; aucun débordement horizontal mesuré
  (`scrollWidth <= clientWidth`) sur les deux tailles, y compris pendant/
  après correctifs ; rangée de navigation tient sur une seule ligne sans
  scroll interne sur les deux tailles.
- Hauteur du plateau collé : ~46-48% de l'écran à l'état "repos" (avec les
  boutons "Jouer les Blancs/Noirs" du mode pédagogique, qui s'affichent tant
  qu'aucune partie n'est en cours, issue #65 point 6 — non modifié par cette
  issue) ; ~40% en partie pédagogique active (sans ces boutons) — proche de
  la cible "environ 42%" dans le cas d'usage principal signalé par Alain
  (poser une question/lire une ligne PENDANT une partie).
- Partie pédagogique simulée directement en JS (pas de partie réellement
  démarrée via socket, cf. limite ci-dessus) : messages automatiques
  "je joue ..." bien masqués dans le chat, réponse du coach normalement
  visible.
- Tableau "Lignes du coach" simulé (ligne factice) : barre de commande
  masquée par défaut, affiche "Stop" pendant la lecture (clic réel ->
  `gameLineToggle`), puis "Revenir à la partie" après arrêt (clic réel ->
  `gameLinesRestore`, plateau redessiné sans exception).
- Partie libre RÉELLE (pas de simulation d'état — `startFreeGame()`/
  `onFreePlayBoardClick` sont purement client, aucun aller-retour SocketIO
  nécessaire pour un coup manuel) : deux coups joués par de vrais événements
  `click` (e2-e4, d7-d5) sans que `window.scrollY` ne bouge — confirmé aussi
  sur le code d'avant cette issue (même comportement, pas de régression).
  Note méthodologique : `page.tap()` de Playwright fait lui-même défiler la
  page vers `sq-e2` avant de taper dessus (heuristique d'"actionabilité" de
  l'outil sur un élément `position: sticky`, pas un comportement du site) —
  écarté en dispatchant directement l'événement `click`, qui confirme
  l'absence de saut réel.
- Changement de tous les onglets (bibliothèque/libre/pédagogique/ouverture/
  finales/exercice/éditeur) sans exception JS.
- `scroll-padding-top` dynamique : rapport d'analyse simulé, son haut reste
  sous le plateau collé après `_scrollVersPanneauAnalyse()` (marge
  recalculée par `ResizeObserver`, pas seulement la valeur CSS statique de
  secours).
- Rendu à 1440px : comparaison pixel par pixel (`git stash`/capture d'écran
  avant-après avec Playwright) de `#board-column`/`#coach-column`/
  `#mode-tabs-column`/`#historique-column`/`#board`/`#review-controls`/
  `#shared-mode-controls` — coordonnées strictement identiques, captures
  d'écran identiques au pixel près (`ImageChops.difference` : bbox vide).

## Limites et points pour la future maquette (Claude Design)

- Hauteur du plateau collé à l'état "repos" (~46-48% au lieu de ~42%) tant
  que les boutons "Jouer les Blancs/Noirs" du mode pédagogique (issue #65
  point 6) s'affichent au-dessus — n'a pas semblé justifier de réduire la
  taille du plateau EN PARTIE ACTIVE (le cas d'usage réel signalé par Alain)
  pour ce cas transitoire ; la future maquette pourra reconsidérer ce
  placement.
- Sur le plus petit écran testé (360px), la rangée de navigation compacte
  tient tout juste sur une seule ligne (police 0.72rem, padding réduit à
  6px 5px) — resterait fragile si un futur bouton s'ajoutait à cette rangée
  sans revoir la maquette.
- Les contrôles spécifiques à chaque mode (démarrer une partie d'ouverture,
  choisir une finale, etc., dans `#mode-tabs-column`) n'ont pas été
  réordonnés individuellement — seuls le panneau d'analyse et les 4 blocs de
  navigation/collection listés dans l'issue ont été déplacés ; le reste de
  `#mode-tabs-column` garde sa position (après le chat/lignes/analyse,
  avant l'historique), un compromis pour rester un correctif simple.
- Aucun vrai appel API/Stockfish testé (contrainte de l'environnement, cf.
  section Tests) — comportement du chat/de l'analyse/des lignes vérifié en
  simulant l'état JS, pas en conditions réelles de bout en bout.
