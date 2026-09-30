# Changelog — Issue #47

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

# Changelog — Issue #68

## Lignes du coach rejouables sur l'échiquier dans les modes de partie et en revue

- Contexte : le mode exercice (issue #58) possède un tableau "Lignes du
  coach" qui extrait les lignes de coups citées par le coach et les rejoue
  sur l'échiquier. Ce tableau n'existait que dans ce mode — en usage réel en
  partie pédagogique, Alain a demandé au coach ce qu'il aurait dû jouer au
  coup 8, mais n'a eu aucun moyen de voir cette ligne sur l'échiquier.
  `static/coach_lines.js` avait été conçu réutilisable depuis le départ.

### static/coach_lines.js

- Nouvelle fonction `extractCoachGameLines(text)` : étend
  `extractCoachMoveLines` (inchangée, toujours utilisée telle quelle par le
  mode exercice) en associant chaque ligne trouvée à une éventuelle mention
  de départ "depuis le coup N... (Camp)" / "depuis le coup N (Camp)" qui la
  précède immédiatement dans le texte (`_COACH_LINE_ANCHOR_RE`). Une ligne
  sans mention reconnaissable reste "sans ancre" — jamais de déduction.

### static/game_coach_lines.js (nouveau)

- Tableau "Lignes du coach" mode-agnostique pour les modes de partie (libre,
  pédagogique, ouverture, finales) et la revue de bibliothèque, pendant du
  tableau du mode exercice mais réutilisant directement
  `resolveCoachLineStart`/`playCoachLineSequence`/`extractCoachGameLines`
  (coach_lines.js) plutôt que de les redupliquer.
- `_gameLinesFenForAnchor`/`_gameLinesReplayFen` : résolvent une mention de
  départ ou la position actuelle PAR REJEU (jamais par arithmétique de
  numéro de coup), en comparant à chaque demi-coup le numéro/camp affiché
  par chess.js lui-même (fullmove number + turn du FEN courant) — reste
  correct même pour une partie démarrant à un demi-coup impair (SetUp/FEN
  personnalisé, ex. une finale, ou la partie de test de l'issue).
- `_gameLinesCandidates` : essaie la position juste avant le coup visé par
  la mention (si présente et résoluble), PUIS la position actuelle, jamais
  d'autre repli — `resolveCoachLineStart` retourne "ligne non jouable" (pas
  de bouton Play) si aucun des deux candidats ne rend la ligne légale.
  Aucune ligne de moins de deux coups (hérité de coach_lines.js).
  `gameCoachLinesOnStockfishLine` : bonus "Ligne de Stockfish" en tête de
  tableau quand le serveur en transmet une (voir app.py).
- La lecture (`gameLineToggle`) ne fait QUE redessiner le plateau
  (`renderBoard`) à partir de positions déjà résolues — aucun appel à
  `game.move()` sur l'instance réelle du mode, aucun `socket.emit` : Stop/
  "Revenir à la partie" n'ont donc jamais besoin de restaurer autre chose
  que l'affichage (position, historique, bandeau de fin compris, puisque
  rien d'autre n'a été modifié entre-temps) — `gameLinesRestore` se contente
  de rappeler la fonction de rendu réelle du mode actif (ou `renderReview`).
  `gameCoachLinesPreviewActive` bloque les clics du plateau pendant la
  prévisualisation (guardé dans les 4 handlers de clic, voir plus bas) et la
  navigation de revue (`reviewPrev`/`reviewNext`/`reviewGoTo`, board.js).

### static/board.js

- `coachNewSegment` (point de coupure déjà existant, issue #64) appelle
  aussi `gameCoachLinesReset()` : le tableau est vidé aux mêmes moments que
  l'isolation du chat par partie (nouvelle partie, ou autre partie chargée
  en revue) — un seul point d'entrée pour tous les modes.
  Les handlers `coach_response`/`coach_on_demand_response` alimentent aussi
  ce tableau (`gameCoachLinesOnCoachText`), et `coach_response` transmet la
  "Ligne de Stockfish" bonus si `data.stockfish_line` est présent.
- `reviewPrev`/`reviewNext`/`reviewGoTo` : no-op pendant une prévisualisation
  de ligne du coach en revue de bibliothèque (`gameCoachLinesPreviewActive`).
- `parsePgn` : appelle désormais `setActiveMode(null)` après
  `ensureModeSwitchClean("library")`. Correction nécessaire découverte en
  cours d'implémentation — seuls `abandonExerciseGame`/
  `abandonPositionEditor` remettaient `activeMode` à `null`, jamais les
  modes de partie (libre/pédagogique/ouverture/finales) : charger une partie
  en revue juste après en avoir joué une laissait `activeMode` pointer sur
  l'ancien mode, donc `coachBuildContext()`/`gameCoachLinesOnCoachText`
  continuaient de lire l'ancienne partie interactive au lieu de celle qu'on
  vient de charger (et les boutons Précédent/Suivant/Meilleur coup
  restaient grisés, `updateReviewControlsEnabled`). N'affecte que le chemin
  "charger une partie en revue" — inchangé pour la fin de partie/l'abandon
  d'un mode interactif, qui reste affiché tel quel comme avant.

### static/controls.js, static/free_play.js, static/pedagogic.js, static/opening.js, static/finales.js

- `setActiveMode` : masque immédiatement le tableau au passage vers
  exercice/éditeur (`renderGameCoachLinesTable`).
- `onFreePlayBoardClick`/`onPedagogicBoardClick`/`onOpeningBoardClick`/
  `onFinaleBoardClick` : bloqués pendant une prévisualisation de ligne du
  coach (`gameCoachLinesPreviewActive`) — empêche tout coup d'Alain, donc
  toute réponse de Stockfish déclenchée par la lecture.
- `pedagogic_comment`/`opening_comment`/`finale_comment` (commentaire
  automatique "Commenter chaque coup") alimentent aussi le tableau — ces
  événements ne passent pas par les handlers génériques de board.js.

### templates/index.html

- Nouveau bloc `#game-coach-lines` sous le chat du coach (`.coach-drawer`),
  visible dans tous les modes sauf exercice/éditeur — mêmes classes CSS que
  le tableau du mode exercice (`.coach-line-*`, déjà adaptées mobile depuis
  les issues #63/#65), donc aucun CSS nouveau nécessaire. Sélecteur de
  vitesse (0,5 s / 1 s, 1 s par défaut) et bouton "Revenir à la partie".
  Script `game_coach_lines.js` chargé après `coach_lines.js`.

### llm_coach.py

- Nouveau `_GAME_LINES_ADDENDUM` : demande au coach, pour tous les modes
  hors exercice, le format fixe de mention de départ ("depuis le coup N...
  (Camp)") pour une ligne alternative qui ne part pas de la position
  actuelle — jamais imposé en mode exercice (déjà couvert par
  `_EXERCISE_SYSTEM_ADDENDUM`, une position isolée sans historique).
  `get_coach_response` : ajouté indépendamment du garde-fou
  anti-invention existant (verdict/PV Stockfish), qui reste conditionnel
  comme avant.

### app.py

- `_enrich_context_with_game_facts` retourne désormais `(context,
  stockfish_line)` — `stockfish_line` reprend `fen_avant`/`ligne_principale`
  (déjà calculés par `_stockfish_check_key_moment`, aucun appel moteur
  supplémentaire) du premier moment vérifié qui en a une, ou `None` sinon.
  `on_coach_ask` transmet `stockfish_line` dans la réponse `coach_response`
  sous la clé du même nom, omise si absente.

### Tests effectués

- Logique pure (extraction/ancrage/résolution/lecture), Node.js, en dehors
  du périmètre applicatif (aucune dépendance à Flask/DATA_DIR) : partie de
  test de l'issue (SetUp/FEN personnalisé, abandon, ligne "depuis le coup
  8... (Noirs)" avec la ligne exacte de l'énoncé) → résolue, 6 coups, FEN de
  départ vérifiée ; ligne sans mention légale depuis la position actuelle ;
  ligne illégale (ni depuis l'ancre ni depuis la position actuelle) → "ligne
  non jouable" ; faux positif "c3-d3-e3" → aucune ligne extraite ; mode de
  partie "live" (pédagogique) avec `header().FEN` personnalisé ; bonus
  "Ligne de Stockfish" ; Stop en cours de lecture puis "Revenir à la
  partie" → position/historique de la partie réelle inchangés. 22
  assertions, toutes passées.
- Prompt système (`llm_coach.get_coach_response`), Python, `_call_claude`
  monkeypatché (aucun appel réseau, `coach_log_path`/`usage_path=None` pour
  ne toucher aucun fichier hors du périmètre) : `_GAME_LINES_ADDENDUM`
  présent pour partie libre/pédagogique (avec verdict)/revue de
  bibliothèque, absent en mode exercice (remplacé par
  `_EXERCISE_SYSTEM_ADDENDUM`) ; garde-fou anti-invention toujours combiné
  quand un verdict/une PV est transmis. 8 assertions, toutes passées.
- Bout en bout en navigateur réel (Playwright + Chromium système, un
  serveur Flask minimal servant uniquement `templates/`/`static/` de ce
  worktree — sans jamais importer `app.py` ni `config.py`, donc sans
  toucher `~/ChessCoach/data`, hors périmètre) : scénario de l'issue simulé
  en partie libre (position personnalisée, 16 coups rejoués, bandeau
  d'abandon affiché) puis réponse du coach simulée avec la ligne exacte de
  l'énoncé → tableau affiché avec le bon libellé d'ancre ; clic Play → clics
  du plateau bloqués (vérifié directement) ; en cours de lecture le bouton
  affiche "Stop" ; Stop puis "Revenir à la partie" → position/historique/
  bandeau de fin identiques à avant la lecture (FEN comparée strictement
  égale). Vue mobile 390×844 : tableau lisible, bouton Play mesuré à
  61×46 px (largement au-dessus du minimum tactile recommandé de 44×44).
  Aucune vraie clé API Claude disponible dans ce worktree (pas de `.env`) —
  impossible de vérifier que le VRAI modèle Claude respecte le format de
  mention demandé ; seule la partie client (extraction/résolution/lecture)
  et l'assemblage du system prompt ont pu être vérifiés directement.

### Limites connues

- Le format de mention de départ n'a pu être vérifié qu'en simulant la
  réponse du coach (aucune clé API dans ce worktree) — un vrai appel
  pourrait s'écarter du format malgré la consigne, comme pour toute
  consigne de prompt.
- La "Ligne de Stockfish" bonus (point 5) ne peut apparaître que via le chat
  libre (`coach_ask`), seul point où `_enrich_context_with_game_facts` est
  appelé côté serveur — jamais via le commentaire automatique après un coup
  (`pedagogic_comment`/`opening_comment`/`finale_comment`), qui ne calcule
  pas ce bloc de faits. Elle n'apparaît pas non plus en revue de
  bibliothèque : `camp_alain` n'y est jamais transmis au serveur
  (limitation déjà documentée pour l'issue #55, volontairement pas étendue
  ici).
- Non géré (limite assumée, pas de garde ajoutée) : si une réponse de
  Stockfish était déjà en vol au moment où Alain clique Play (ex. il vient
  de jouer un coup en partie pédagogique, Stockfish n'a pas encore répondu),
  son arrivée continue de redessiner le plateau avec sa propre position dès
  qu'elle arrive (`pedagogic_stockfish_move` et équivalents ne testent pas
  `gameCoachLinesPreviewActive`) — cela interromprait visuellement
  l'aperçu en cours (sans jamais le corrompre : l'état réel de la partie
  reste correct, et la lecture de la ligne reprend son propre affichage au
  coup suivant de son minuteur). N'affecte que cette fenêtre de course très
  étroite (coup d'Alain suivi immédiatement d'un clic Play avant la
  réponse) ; les clics/coups d'Alain eux-mêmes restent bloqués pendant tout
  l'aperçu, comme demandé.

# Changelog — Issue #67

## Mobile : ne plus faire défiler la page vers le chat à chaque coup joué

- Contexte : suite à l'issue #65 (suppression de la zone de défilement
  interne du chat sur mobile), la fonction commune de révélation des
  messages du chat coach s'appuie désormais sur le défilement de la PAGE.
  Or chaque coup joué en partie pédagogique ajoute un message automatique
  d'Alain dans le chat ("Partie pédagogique — je joue ..."), qui déclenchait
  ce défilement — le plateau sortait de l'écran après chaque coup. Constaté
  par Alain sur capture d'écran ; les autres modes de partie (libre,
  ouverture, finales, exercice) présentaient le même défaut pour leurs
  propres messages automatiques (coup joué, commentaire "Commenter chaque
  coup", info, erreur).

### static/board.js

- `_coachScrollReveal(history, el, toStart, allowPageScroll)` : nouveau
  4ᵉ paramètre. La branche "défilement interne" (bureau, ou mobile si un
  CSS venait à réintroduire un `overflow-y:auto`) est strictement
  inchangée — elle défile toujours, quel que soit `allowPageScroll`. La
  branche "page qui défile" (mobile, cas normal depuis l'issue #65) ne
  déclenche `scrollIntoView` que si `allowPageScroll` est vrai.
- `_coachRenderBubble(role, text, allowPageScroll)` : nouveau 3ᵉ paramètre,
  transmis tel quel à `_coachScrollReveal`. Absent (donc `undefined`/faux)
  par défaut sur tous les appels existants — comportement mobile "ne
  défile pas" par défaut.
- Seuls les deux cas où Alain attend activement une réponse passent
  `allowPageScroll = true` explicitement : la réponse du coach à une
  question tapée dans le chat (`coach_response`) et la réponse au bouton
  "Demander l'avis du coach" (`coach_on_demand_response`).
- `_coachRenderCreditInsuffisant` et `coachNewSegment` (séparateur
  "Nouvelle partie") continuent d'appeler `_coachScrollReveal` sans ce
  4ᵉ argument : plus de défilement de page sur mobile pour ces messages
  d'erreur/séparateur, comportement bureau inchangé.

### static/exercise.js

- Verdict d'exercice (`exercise_comment`) : seul appel hors board.js à
  passer `allowPageScroll = true` — comportement voulu par la maquette
  (le début du verdict doit se placer en haut de l'écran).

### Cas qui ne défilent plus la page sur mobile (comportement bureau inchangé)

- Messages automatiques "je joue ..." (pédagogique, ouverture, finales,
  exercice) — `_coachRenderBubble("user", ...)` sans 3ᵉ argument.
- Commentaires "Commenter chaque coup" (`pedagogic_comment`,
  `finale_comment`) et commentaires équivalents d'ouverture
  (`opening_comment`).
- Messages informatifs statiques ("Finale chargée", "Ouverture chargée",
  "Démonstration chargée").
- Messages d'erreur (`_coachRenderCreditInsuffisant`, `no_api_key`, etc.).
- Séparateur "Nouvelle partie"/"Nouvel exercice" (`coachNewSegment`).
- Message d'Alain lui-même envoyé depuis le champ du chat (`coachSend`,
  `_coachRenderBubble("user", question)`) — seule sa réponse déclenche le
  défilement, pas l'envoi de la question.

### Tests effectués

- Lecture complète du code (pas d'environnement mobile réel/émulateur
  tactile disponible dans ce worktree non-interactif ; aucun appel API
  Claude réel effectué — pas de clé/contexte d'exécution serveur monté
  dans cette session). Vérification statique de tous les appelants de
  `_coachRenderBubble`/`_coachScrollReveal` dans board.js, pedagogic.js,
  finales.js, opening.js, exercise.js, free_play.js, llm_model.js :
  chaque site a été classé dans la bonne catégorie (défile / ne défile
  pas) et corrigé en conséquence. `node -c` sur les deux fichiers modifiés
  (syntaxe JS valide) — pas de suite de tests automatisés pour ce module
  front-end dans le dépôt.
- Limite assumée : aucune vérification visuelle réelle (émulation
  tactile 390×844, clic sur les coups, capture d'écran) n'a été faite —
  seule une relecture exhaustive du flux de code garantit le comportement
  attendu. À confirmer par Alain en conditions réelles sur mobile.

# Changelog — Issue #66

## Bloc de faits : décrire mécaniquement chaque coup cité et signaler les pions perdus sans reprise

- Contexte : test réel sur une partie pédagogique (Haiku, Alain Noirs,
  abandonnée après 9.Nxe5). Le bloc de faits (matériel, moment le plus
  grave, meilleur coup Stockfish, perte estimée) était exact, mais la
  réponse du coach attribuait le coup Nxg4 au mauvais cavalier (b6 au lieu
  de f6), disait que Bxe5 capturait un cavalier au lieu d'un pion, et
  plaçait le cavalier blanc "en e5" au lieu de g4 pour 7...h5 — le modèle
  reconstituait de tête, à partir de la seule notation SAN, quelle pièce
  joue et où sont les autres, et se trompait (même famille que "dame en
  b5"/confusion de camp, issues #25/#44/#55). Avec Sonnet sur la même
  partie, aucune erreur de pièce/case, mais 8...Nxg4 était présenté comme
  "pris gratuitement" alors que le cavalier g4 était défendu par le fou e2
  et repris dans la ligne principale Stockfish elle-même. Les chiffres de
  la vérification Stockfish n'étaient de plus pas stables d'un appel à
  l'autre pour la même partie.

### game_facts.py — description mécanique des coups (points 1 et 2)

- Nouvelles fonctions `describe_move_mechanically(fen_avant, coup,
  camp_alain="")` et `describe_pv_mechanically(fen_avant, pv_text,
  camp_alain="", max_plies=2)` (cœur commun `_decrit_coup_mecanique`) :
  calculent avec python-chess, jamais deviné, pour UN coup (SAN ou UCI)
  légal sur une position donnée — quelle pièce joue (type et case de
  départ), case d'arrivée, capture éventuelle (type/case, défendue ou non
  — via un nouveau `_premier_coup_vers` — et solde net après reprise,
  réutilise `_solde_net_apres_capture` de l'issue #57), échec/mat, et
  quelles pièces adverses (hors roi, déjà couvert par l'échec) ce coup
  attaque désormais (`_pieces_attaquees_apres`, `board.attacks`). Nouveaux
  helpers `_couleur_accordee` (accord "blanc"/"blanche") et
  `_nom_piece_capturee` (article indéfini pour un pion générique, défini
  pour les autres pièces).
- `find_stockfish_check_targets` : chaque cible porte désormais
  `uci_reponse_suivante` (le coup réellement joué ensuite dans la partie,
  nécessairement celui de l'adversaire) — nécessite `idx`/`uci` ajoutés à
  chaque entrée de l'historique interne.
- `build_game_facts_text`, section "Vérification Stockfish ciblée" :
  chaque cible reçoit maintenant la position juste avant le coup joué
  (pièce par pièce, comme la position actuelle — point 2), puis la
  description mécanique du coup joué, du meilleur coup, de la réponse
  anticipée par la ligne principale (2e pli, le 1er étant déjà celui du
  meilleur coup) et de la réponse réellement jouée ensuite dans la partie.

### game_facts.py — pions perdus sans reprise (point 4)

- Nouvelle rubrique "Pions perdus sans reprise" dans `build_game_facts_text`
  : capture d'UN pion (variation exactement 1 point, donc sous le seuil des
  "moments clés" de 2 points), sans aucune reprise légale immédiate — les
  `_MAX_PIONS_PERDUS_SANS_REPRISE` (3) plus récents de la partie seulement.
  Sur la partie de test, 6.Nxe5 (pion e5 laissé sans défense par 5...Nb6)
  y apparaît désormais, alors qu'il restait invisible du bloc jusqu'ici.

### app.py — même principe pour "Analyser cette partie" (point 5)

- `_prepare_flagged_moves_for_coach` (appel en lot,
  `get_move_explanations`) et `on_analyse_expliquer_coup` (explication à la
  demande d'un coup unique) ajoutent chacun `description_mecanique`/
  `meilleur_coup_description` (resp. `coup_description_mecanique`/
  `meilleur_coup_description_mecanique` dans le contexte) via
  `game_facts.describe_move_mechanically` — même risque que le chat coach,
  même correctif.

### app.py — reproductibilité de la vérification Stockfish (point 6)

- `STOCKFISH_CHECK_TIME_PAR_POSITION` (limite de temps, movetime) remplacée
  par `STOCKFISH_CHECK_DEPTH = 14` (profondeur fixe) dans
  `_stockfish_eval_cible` : une limite de temps ne garantit pas la
  profondeur réellement atteinte par Stockfish (donc pas le résultat) d'un
  appel à l'autre sur EXACTEMENT la même position, ce qui a fait constater
  des chiffres de perte et des meilleurs coups différents en usage réel.
  `STOCKFISH_CHECK_BUDGET_TOTAL` (garde globale en temps, best-effort)
  inchangée. Le cache par partie `_stockfish_check_cache` (clé
  `(camp_alain, pgn)`) existait déjà depuis l'issue #57 ; combiné à la
  profondeur fixe, deux questions successives sur la même partie reçoivent
  désormais exactement les mêmes chiffres, y compris après un redémarrage
  du process qui aurait vidé le cache (nouveau calcul à la même profondeur
  ⇒ même résultat).

### llm_coach.py — renforcement du prompt (point 3)

- `_GAME_FACTS_ADDENDUM` (chat coach) : règle absolue ajoutée — pour toute
  pièce ou case liée à un coup cité par la "Vérification Stockfish ciblée",
  ne reprendre QUE la description mécanique calculée fournie ; ne jamais
  affirmer soi-même quelle pièce joue, où se trouve une pièce, ou ce qu'un
  coup attaque si cette description est absente (citer alors le coup en
  notation abrégée sans commentaire de position) ; ne jamais qualifier de
  "gratuite" une capture que la description indique défendue et reprise.
  Mention de la nouvelle rubrique "Pions perdus sans reprise".
- `_MOVE_SELECTION_SYSTEM_PROMPT` (choix de coups décisifs en lot) et
  `_ANALYSE_PARTIE_ADDENDUM` (explication d'un coup isolé) : même règle
  absolue, appliquée aux nouveaux champs `description_mecanique`/
  `meilleur_coup_description` (lot) et `coup_description_mecanique`/
  `meilleur_coup_description_mecanique` (contexte, coup isolé) —
  `_build_context_text` les sérialise avant `reponse_suivante`.

### Vérifications faites

- `py_compile` sur `game_facts.py`/`app.py`/`llm_coach.py` : OK.
- Rejeu complet de la partie de test de l'issue (position de départ non
  standard `[FEN ...]`, 1...c6...9.Nxe5, Alain Noirs) avec un venv de test
  temporaire (`python-chess==1.999`, hors dépôt, supprimé après usage) :
  le bloc généré signale bien 9.Nxe5 comme moment clé (capture du fou sans
  reprise, 3 points) et 6.Nxe5 comme pion perdu sans reprise (1 point) ; la
  vérification Stockfish ciblée simulée (meilleur coup 8...Nxg4 injecté à
  la main, sans appel moteur réel à cette étape) produit exactement le
  texte attendu par l'exemple de l'issue : "le fou noir de d6 capture un
  pion de Blancs (adversaire) en e5" pour Bxe5, "le cavalier noir de f6
  capture le cavalier de Blancs (adversaire) en g4 — était défendu(e) par
  le fou blanc de e2 : reprise possible, solde net +0 points" pour Nxg4
  (donc PAS gratuit, corrige l'erreur constatée avec Sonnet), et "le
  cavalier blanc de g4 capture le fou de Noirs (Alain) en e5 — aucune
  reprise possible" pour la réponse réelle 9.Nxe5.
- Reproductibilité (point 6) vérifiée avec le vrai moteur Stockfish
  (`/usr/games/stockfish`, présent sur cette machine) : deux appels
  `analyse(depth=14)` successifs sur EXACTEMENT la même position (les deux
  cibles de la partie de test) renvoient le même meilleur coup et le même
  score centipawns à chaque fois (testé aussi avec `Limit(time=0.7s)`,
  l'ancienne méthode, qui s'est révélée stable sur cette machine idle mais
  reste, par construction, dépendante de la charge machine — la profondeur
  fixe supprime ce risque par nature plutôt que par constat empirique).
- Scénarios supplémentaires testés directement sur `game_facts.py`
  (mat, promotion, `describe_pv_mechanically` sur 3 plis) : pas d'exception,
  texte cohérent ("promotion en dame", "échec et mat"...).
- `describe_move_mechanically`/`describe_pv_mechanically` retournent `None`/
  `[]` sur un coup illégal ou une position illisible plutôt que de lever
  une exception, cohérent avec le reste du module (`describe_reponse_suivante`
  notamment).

### Limites

- **Aucun vrai appel à l'API Claude n'a pu être fait** (ni Haiku ni Sonnet)
  : aucune `ANTHROPIC_API_KEY` dans l'environnement de ce worktree, aucun
  `.env` (non touché, conformément à la consigne). La demande de l'issue
  de comparer la réponse réelle du coach sous les deux modèles n'a donc
  pas pu être exécutée — seul le contenu exact du bloc de faits/contexte/
  system prompt a été vérifié, pas la réponse finale du modèle.
- **Le "fichier de tests de Claude Chat" (quatre parties Alain Blancs)**
  mentionné dans l'issue n'a pas été trouvé dans ce dépôt/worktree (aucun
  fichier PGN ni test correspondant sous `/home/alain/chesscoach-issue66`)
  : probablement des parties testées manuellement par Alain via l'interface
  Claude Chat, externes au dépôt. Non retesté, faute d'accès — à fournir
  par Alain si un nouveau test ciblé est nécessaire.
- `app.py` n'a pas été exécuté en direct (Flask/SocketIO/EngineManager) :
  `config.DATA_DIR` pointe vers `~/ChessCoach/data`, hors du périmètre
  strict de ce worktree (`~/chesscoach-issue66`), et le démarrer aurait pu
  y écrire (logs, cache, connexion moteur). Les nouveaux chemins de code
  d'`app.py` (`_prepare_flagged_moves_for_coach`, `on_analyse_expliquer_coup`)
  ont été vérifiés par lecture et par les fonctions `game_facts.py` sous-
  jacentes qu'ils appellent (déjà testées ci-dessus), pas par un appel réel
  du serveur.
- La description mécanique des "premiers coups de la ligne principale" se
  limite au 2e pli (la réponse anticipée après le meilleur coup) : au-delà,
  la ligne principale reste citée en texte brut sans description
  supplémentaire — jugé suffisant pour l'exemple de l'issue (Nxg4 Bxg4),
  une description plus longue aurait rendu le bloc disproportionné par
  rapport au reste.
- `STOCKFISH_CHECK_DEPTH = 14` est un compromis (temps de calcul par
  position légèrement plus long qu'à `movetime=0.7s` sur une position
  complexe) non mesuré en charge réelle de production — à surveiller si le
  budget global `STOCKFISH_CHECK_BUDGET_TOTAL` (6.0s) commence à tronquer
  des positions plus souvent qu'avant.

# Changelog — Issue #65

## Interface mobile : corrections après test réel sur GSM

- **Colonnes du plateau décalées (`templates/index.html`, `static/board.js`
  inchangé)** — `#coord-file` (lettres a-h) était un frère de `#board-row`
  au lieu d'être groupé avec `#board-wrapper` : centré seul sous toute la
  largeur de `#board-column`, il ignorait que `#board-row` inclut aussi
  `#coord-rank` et la barre d'éval avant le plateau, d'où un décalage
  gauche constant (mesuré ≈-17 à -19px, soit ~45 % d'une case à 390px de
  large comme signalé par Alain, ~25 % à 1440px — même défaut aux deux
  largeurs, seule sa part relative change). Introduction de
  `#board-file-column` (colonne flex centrée regroupant `#board-wrapper` et
  `#coord-file`) : les deux partagent désormais le même repère horizontal,
  et `#coord-file` hérite automatiquement des 2px de bordure de
  `#board-wrapper` de chaque côté. `#coord-rank` (numéros de rangs) : décalé
  de 2px vers le bas (`margin-top`) pour compenser la bordure du haut de
  `#board-wrapper`, dont il ne tenait pas compte (défaut bien plus discret,
  demandé en vérification par Alain). Les deux corrections sont purement
  CSS/DOM, valables dans les deux orientations et à toutes les largeurs.

- **Surbrillance Haiku/Sonnet qui disparaît après un tap (`templates/
  index.html`, `static/board.css`)** — sur écran tactile, un tap déclenche
  `:hover` puis le laisse "collé" (pas de souris pour le faire cesser)
  jusqu'au tap suivant ailleurs. Les règles `:hover` génériques
  (`button:hover:not(:disabled)`, `.btn-filled:hover`,
  `#llm-model-selector .llm-model-btn:hover`, `.opening-suggestion-btn:hover`)
  ont plus de sélecteurs de classe que les règles `.active`/`.playing`
  qu'elles sont censées compléter, donc gagnent la cascade CSS et masquent
  la surbrillance active tant que le survol tactile reste collé — pas
  seulement pour le sélecteur de modèle, mais pour tout bouton combinant un
  état `.active` avec un `:hover` générique (repéré aussi : `.mode-tab-btn`
  en vue desktop et `.phase-pill` de la feuille "Nouvel exercice" en vue
  mobile, tous deux vulnérables en théorie). Toutes ces règles `:hover`
  regroupées derrière `@media (hover: hover) and (pointer: fine)` — un vrai
  pointeur à survol, donc jamais un écran tactile. Le bouton réellement actif
  reste déterminé par `_llmModelSetActive` (llm_model.js, inchangé), piloté
  par la confirmation serveur `llm_model_changed` — déjà correct avant ce
  correctif, seul l'habillage CSS masquait le bon état.

- **Bulles du chat coach (`static/board.css`)** — couleurs inversées par
  rapport à la maquette (`.coach-bubble.assistant` en foncé/texte clair,
  `.coach-bubble.user` en clair/texte foncé) : permutées, l'alignement
  (utilisateur à droite, coach à gauche) étant déjà correct. Zone à
  défilement interne du chat (`.coach-drawer`/`.coach-history`,
  `overflow-y:auto` + `max-height`) supprimée sur mobile (`@media
  (max-width:900px)`) : c'est la page qui défile désormais, comme dans la
  maquette. `_coachRenderBubble`/`_coachRenderCreditInsuffisant`/
  `coachNewSegment` (board.js) : nouvelle fonction commune
  `_coachScrollReveal()` qui détecte si `#coach-history` est encore
  défilable en interne (`scrollHeight > clientHeight`, donc bureau) — dans
  ce cas comportement inchangé (`scrollTop`), sinon (mobile)
  `scrollIntoView()` sur l'élément ajouté, avec `block:"start"` pour une
  réponse du coach (issue #53 : son début visible en haut de l'écran,
  comportement demandé conservé) et `block:"end"` pour un message d'Alain/
  séparateur/erreur.

- **En-tête mobile trop haut (`templates/index.html`)** — `<h1>` masqué sur
  mobile (`display:none`), regroupement du sélecteur de modèle/compteur de
  tokens/lien "Coût API" dans `.header-actions` avec `flex-wrap:nowrap` sur
  la même media query : tient sur une seule ligne d'environ 60px de haut au
  lieu d'un bloc replié sur 2-3 lignes prenant ~1/3 de l'écran.

- **Doublon "Reprendre mon coup" en mode exercice sur mobile
  (`static/controls.js`)** — `updateSharedControlBar()` masque désormais
  `#shared-reprendre-btn` (carte "Contrôles du mode actif") uniquement
  quand `activeMode === "exercise"` ET que le viewport est mobile (`
  _mobileModeBarQuery.matches`, déjà déclaré pour le menu de mode) — la
  barre du bas (`#mobile-exercise-bar`) fournit alors déjà ce bouton. Les
  autres modes à "reprendre" (pédagogique/ouverture/finales), qui n'ont pas
  de barre du bas équivalente, gardent ce bouton sur mobile comme avant.

- **"Demander l'avis du coach" cliquable sans effet visible
  (`static/controls.js`, `static/{free_play,pedagogic,opening,finales}.js`)**
  — `MODE_CAPS` gagne un prédicat `askCoachAvailable` par mode (reflète la
  garde de la fonction `askXCoach` correspondante : partie démarrée, non
  terminée). `updateSharedControlBar()` désactive `#shared-ask-coach-btn`
  quand ce prédicat est faux — grisage via la règle générale
  `button:disabled { opacity:0.5 }` déjà utilisée ailleurs dans l'appli
  (aucune nouvelle règle CSS nécessaire). Rafraîchi à chaque abandon, à
  chaque détection de fin de partie côté serveur (mat/pat/nulle) et à
  chaque "Reprendre mon coup" (qui réactive le bouton). Nouvelle ligne
  `#shared-ask-coach-help` sous les boutons du mode actif : courte phrase
  expliquant ce que fait "Demander l'avis du coach" dans le mode affiché
  (texte dans `MODE_ASK_COACH_HELP`, controls.js). **Ce que fait ce bouton
  dans chaque mode** (pour le rapport, cf. `askXCoach` de chaque fichier) :
  demande un commentaire ponctuel du coach sur la position affichée, sans
  jouer de coup à sa place ni passer par le circuit "verdict" — en mode
  partie libre/pédagogique/ouverture/finales, un aller-retour SocketIO
  générique (`coach_comment_on_demand`, mutualisé via `askCoachOnDemand`,
  board.js), surtout utile quand "Commenter chaque coup" est décoché ; en
  mode exercice, disponible à tout moment (avant le verdict comme pendant
  l'exploration libre après), sans lien avec `exercise_answer`. **Limite
  assumée** : `askCoachAvailable` ne teste pas les courtes fenêtres
  `*Waiting` (coup adverse en cours de traitement côté serveur, ~1s) — un
  clic pile à ce moment reste un no-op silencieux, comme avant ce correctif.
  Le mode Éditeur de position n'a pas ce bouton (inchangé, pas de coach à la
  demande sans partie jouée) ; en mode partie libre, l'abandon reste
  cliquable même une fois la partie terminée (comportement pré-existant,
  non modifié — hors du périmètre explicite de cette demande).

- **"Jouer les Blancs/Noirs" hors de vue en mode partie pédagogique
  (`templates/index.html`, `static/pedagogic.js`)** — nouveau slot
  `#mobile-pedagogic-start-slot` (`display:contents`, donc invisible et
  sans effet tant qu'il est vide) juste avant le plateau dans
  `#board-column`. `placePedagogicStartButtonsForViewport()`
  (pedagogic.js, même mécanique que `placeModeTabBarForViewport` de
  controls.js) y déplace `#pedagogic-start-buttons` sur mobile tant
  qu'aucune partie n'est en cours (jamais démarrée, ou terminée/abandonnée)
  — les boutons reprennent leur emplacement d'origine (bas du panneau
  "Partie pédagogique") dès qu'une partie démarre, ou sur grand écran.
  Appelé au chargement, au redimensionnement franchissant le seuil mobile,
  au démarrage d'une partie, à l'abandon, à la détection de fin de partie et
  à "Reprendre mon coup". **Non étendu au mode Travail d'ouverture** (même
  paire de boutons en bas de panneau) : son démarrage exige un nom
  d'ouverture déjà saisi dans un champ resté, lui, en bas du panneau — les
  en extraire seuls aurait éloigné les boutons de leur champ obligatoire,
  jugé pas assez "simple" pour rester dans le périmètre de cette issue
  (clause "si c'est simple" de la demande). Le mode Travail de finales a un
  schéma différent (sélection dans un menu déroulant, pas de choix de
  camp), hors sujet.

## Vérification

Aucun serveur Flask-SocketIO ni clé API Claude disponibles dans ce worktree
(`flask_socketio`/`anthropic` absents des environnements Python présents,
et `RESEAU: non` sur cette tâche interdit une installation réseau) — un
vrai appel API n'a donc pas pu être exercé, comme demandé de le signaler
clairement le cas échéant.

À la place : page de test autonome (créée temporairement sous `static/`,
supprimée après usage — jamais committée) chargeant les fichiers réellement
livrés (`board.css`, `board.js`, `controls.js`, `pedagogic.js`, etc., sans
aucune copie/modification) avec `socket` réduit à un bouchon `{emit(){},
on(){}}`, servie en local (`python3 -m http.server`) et pilotée par
Playwright (Chromium déjà en cache local, donc sans réseau) :

- Alignement des lettres/chiffres mesuré par `getBoundingClientRect()` aux
  deux orientations (`flipBoard()`) et aux deux largeurs (390px/1440px) :
  écart au centre de chaque case ramené de ≈-17/-19px (structure d'origine,
  reproduite exprès pour comparaison) à moins de 2px (bruit de largeur de
  glyphe entre lettres, pas un défaut structurel) ; rangs à 0px exact dans
  les deux cas.
- Contexte navigateur tactile (`has_touch=True, is_mobile=True`) + un vrai
  `locator.tap()` sur le bouton Sonnet : capture de l'état juste après —
  fond terracotta correct (confirmé aussi en comparant avec la structure
  CSS d'origine rejouée dans la même page, qui affiche bien le fond clair
  de survol collé à la place, `:hover` matchant toujours après le tap) —
  et après un défilement simulé (`mouse.wheel`), sans changement.
- Bulles longues injectées via `_coachRenderBubble` en contexte 390px :
  couleurs/alignement conformes à la maquette, `#coach-history`/
  `.coach-drawer` confirmés non défilables en interne
  (`scrollHeight === clientHeight`), page entière défilable
  (`document.documentElement.scrollHeight > clientHeight`), début de la
  réponse du coach positionné en haut du viewport. Rejoué à 1440px :
  défilement interne toujours actif (`overflow-y:auto`, inchangé).
- En-tête à 390px : hauteur ramenée de ce qu'aurait donné le titre replié
  (non mesuré isolément, mais le nouveau total tient en une ligne) à 61px,
  une seule ligne (`flex-wrap:nowrap` confirmé), titre absent du DOM rendu.
- Mode partie pédagogique simulé par appel direct des fonctions réelles
  (`setActiveMode`, `abandonPedagogicGame`, `reprendrePedagogicCoup`, sans
  passer par un vrai socket) : bouton "Demander l'avis du coach" activé
  pendant la partie, désactivé après abandon, réactivé après "Reprendre mon
  coup" ; phrase d'aide affichée/masquée en cohérence. "Reprendre mon coup"
  confirmé masqué en mode exercice + mobile, visible partout ailleurs
  (desktop, ou mode pédagogique même sur mobile).
- Boutons "Jouer les Blancs/Noirs" confirmés déplacés dans le slot avant le
  plateau sur mobile tant qu'aucune partie n'est en cours, et de retour à
  leur emplacement d'origine dans le panneau une fois `placePedagogic
  StartButtonsForViewport()` rappelée après démarrage — jamais déplacés sur
  desktop (1440px).
- Captures d'écran prises pendant cette session (dossier temporaire, non
  conservées) : en-tête compact + boutons "Jouer les Blancs/Noirs" avant le
  plateau + lettres alignées dans les deux orientations ; bulles de chat
  couleurs/alignement conformes à la maquette ; "Demander l'avis du coach"
  visiblement grisé après abandon, avec sa phrase d'aide.

`.env` non touché. Aucun `git push`.

# Changelog — Issue #64

## Chat coach : isoler chaque partie (ne plus mélanger les échanges de deux parties successives)

- Cause confirmée : `_coachHistory` (tableau JS global, `static/board.js`)
  accumulait tous les échanges du chat depuis le dernier clic sur "Effacer"
  et était renvoyé **en entier** à l'API à chaque question (`coachSend()`),
  quel que soit le nombre de parties/exercices joués entre-temps. Aucun des
  points d'entrée « nouvelle partie » (`startFreeGameFromFen`,
  `startPedagogicGame`, `startOpeningGame`, `loadSelectedFinale`/
  `startFinaleDemo`, chargement d'une autre partie en revue de bibliothèque
  `parsePgn`) ne réinitialisait cet historique — seul `startExercise()` le
  faisait, via `coachClear()`, qui efface aussi tout l'affichage (pas le
  comportement demandé). Reproduit le constat de l'issue : questions/
  réponses de la partie 1 encore présentes dans les messages envoyés à
  l'API pour une question posée sur la partie 2.
- `static/board.js` : nouveau point de coupure `coachNewSegment(label)` —
  insère un séparateur discret (`.coach-separator`, "Nouvelle partie"/
  "Nouvel exercice") dans l'affichage seulement s'il y a déjà des messages
  depuis le précédent segment (pas de trait vide au tout premier segment, ni
  de traits empilés), et avance `_coachSegmentStart` (index dans
  `_coachHistory`) + horodate `_coachSegmentStartedAt`. `coachSend()` ne
  transmet plus que `_coachHistory.slice(_coachSegmentStart)` — l'affichage
  garde tout, l'API ne reçoit que le segment courant. `coachClear()` (bouton
  "Effacer") reste inchangé dans son effet (vide tout, y compris le
  segment). `coachBuildContext()` ajoute `nb_coups`/`debut_partie` au
  contexte (branche mode interactif ET branche revue de bibliothèque).
- `static/controls.js` : `activeModeGameState()` expose désormais `nbCoups`
  (longueur de `game.history()`), lu par `coachBuildContext()`.
- `static/free_play.js`, `pedagogic.js`, `opening.js`, `finales.js`
  (`loadSelectedFinale` ET `startFinaleDemo`) : appel de
  `coachNewSegment("Nouvelle partie")` juste après `ensureModeSwitchClean()`,
  au tout début de chaque fonction de démarrage de partie/finale — c'est le
  point déjà exécuté systématiquement à chaque nouvelle partie, y compris
  quand `activeMode` ne change pas d'un mode à l'autre (`ensureModeSwitchClean`
  seul ne suffisait pas : il ne nettoie l'ancien mode que lors d'une bascule
  vers un mode *différent*, pas quand une 2e partie démarre dans le même
  mode — exactement le scénario de l'issue).
- `static/exercise.js` (`startExercise`) : remplace `coachClear()` par
  `coachNewSegment("Nouvel exercice")` — un nouvel exercice repart avec un
  historique API vide comme avant, mais n'efface plus l'affichage des
  exercices précédents (changement de comportement demandé par l'issue).
- `static/board.js` (`parsePgn`) : `coachNewSegment("Nouvelle partie")`
  ajouté après `ensureModeSwitchClean("library")` — couvre à la fois
  l'import d'un fichier PGN local et le chargement d'une partie de la
  bibliothèque (`pgn_lib_game_loaded`, `pgn_library.js`, qui appelle la même
  fonction `parsePgn`).
- `static/board.css` : nouvelle classe `.coach-separator` (ligne fine de
  chaque côté, texte discret centré, `--cc-text-muted`/`--cc-neutral-200`,
  cohérente avec la palette existante).
- `llm_coach.py` :
  - `_SYSTEM_PROMPT` complété d'une consigne permanente d'isolation : ne
    jamais reprendre un coup/numéro de coup/situation absent du PGN ou du
    bloc de faits de la partie identifiée dans CET appel, même mentionné
    plus tôt dans la conversation affichée ; dire explicitement que
    l'information est absente plutôt que l'inventer.
  - `_build_context_text` : nouveau bloc "Identification de la partie/
    l'exercice actuellement discuté(e)" en tête du contexte (mode, nombre de
    coups déjà joués, heure de début du segment courant — champs
    `mode_origine`/`nb_coups`/`debut_partie` du contexte, désormais transmis
    par `coachBuildContext()`), avec consigne explicite d'ignorer tout
    message affiché plus haut qui évoquerait une partie différente.
- Audit des autres états pouvant fuiter d'une partie à l'autre (point 4 de
  la tâche) :
  - `_stockfish_check_cache` (`app.py`) : déjà clé par `(camp_alain, pgn)` —
    le PGN complet change dès la 1re différence entre deux parties, donc
    déjà isolé par construction. Aucune correction nécessaire.
  - `_gameAnalysisResults`/coups flagués de l'analyse mécanique
    (`game_analysis.js`, `_coachAnalysisFlaggedMoves` dans `board.js`) :
    déjà comparés coup à coup (mêmes SAN, même ordre, même longueur) à la
    partie réellement en cours avant transmission — retourne `[]` en cas de
    moindre différence. Aucune correction nécessaire, comportement déjà
    sûr.
  - État serveur de l'exercice (`_current_exercise`, `app.py`) et état
    client (`exerciseVerdictObtenu`, `_exerciseResetCoachLines()`, etc.,
    `exercise.js`) : déjà réinitialisés à chaque `exercise_new`/
    `startExercise()`. Aucune correction nécessaire.
  - `coach_memory.json` (patterns d'erreurs, objectifs courants) : fuite
    volontaire et documentée (mémoire de progression du coach d'une session
    à l'autre) — hors périmètre de ce bug, pas une régression.
- Tests exécutés (voir détails de la réponse de clôture) : aucun appel API
  réel possible depuis ce worktree (pas de `.env`, `ANTHROPIC_API_KEY` non
  défini) — vérifié à la place via deux harnais hors-réseau chargeant le
  vrai code : (1) `static/board.js` exécuté dans un bac à sable Node (vm)
  avec chess.js réel, scénario partie A (question posée) → partie B
  (question posée) en revue de bibliothèque : messages/contexte envoyés
  pour B ne contiennent aucune trace de A (ni "coup 30", ni le coup `Bb5`
  propre à A), PGN/nb_coups corrects pour B, séparateur "Nouvelle partie"
  bien inséré à l'écran, `coachClear()` remet bien tout à zéro ; (2)
  `llm_coach.get_coach_response`/`_build_context_text` appelés directement
  (venv `~/ChessCoach/venv`, `_call_claude` neutralisé pour éviter tout
  appel réseau) : system prompt + contexte + entrée journalisée dans
  `coach_calls.log` vérifiés champ par champ, rien de la partie A.
  Non testé : un serveur ChessCoach tournait déjà sur le port 5000 au
  moment de la vérification (process pré-existant, pas lancé par cette
  tâche) — pas de vérification visuelle du séparateur en émulation
  mobile/desktop dans un vrai navigateur, pour ne pas risquer d'interférer
  avec une session déjà active d'Alain (parties/exercices réels, compteur
  de tokens, bibliothèque PGN). Le rendu du séparateur a été relu dans le
  CSS/JS mais pas vérifié à l'écran — à confirmer par Alain à l'occasion
  d'un usage normal.

# Changelog — Issue #63

## Style commun (palette/typos/boutons) de la maquette Claude Design + disposition mobile du mode exercice

- Contexte : maquette statique dessinée avec Claude Design
  (`design/exercice.html` + captures d'écran) pour un nouveau look mobile —
  fond crème, plateau vert/beige, typographies Figtree/Caprasimo, boutons en
  pastille terracotta. Analysée en l'ouvrant dans un navigateur headless
  (Playwright) pour relever les styles calculés et la structure affichée
  (le fichier brut n'est qu'un gabarit `{{ ... }}` non rendu) ; contenu
  (textes, exercices, réponses du coach) volontairement ignoré, seuls
  l'apparence et la disposition sont repris.
- `static/board.css` : variables `--cc-*` (palette, `--cc-font-body`
  Figtree/`--cc-font-heading` Caprasimo, rayons, ombres) reprises telles
  quelles des tokens CSS embarqués dans la maquette
  (`--color-bg`/`--color-surface`/`--color-accent`/`--color-accent-2-*`...).
  Règle de conception d'Alain : le terracotta (`--cc-accent`) ne sert qu'au
  cliquable, tout le reste (titres, textes d'état, compteur de tokens,
  avatar du coach) est en brun foncé (`--cc-accent-strong`) ou gris
  (`--cc-text-muted`). Cases du plateau recolorées (beige/vert de la
  maquette) ; dernier coup joué en jaune doux (`--cc-last-move-from/to`,
  nouveauté demandée par Alain — absente de la maquette qui ne montre aucun
  coup en cours). Nouvelles classes `.coach-bubble.user/.assistant/.error`,
  `.coach-line-*` (tableau "Lignes du coach" restylé), `.coach-avatar`,
  historique repliable (`.historique-header-row`, `#historique-column.
  collapsed`).
- `templates/index.html` : police Figtree/Caprasimo chargées depuis Google
  Fonts (pile de secours `system-ui, sans-serif` identique à celle de la
  maquette) ; bouton générique en pastille terracotta appliqué à tous les
  modes (`button { ... }` + `.btn-filled` pour les actions principales) ;
  panneaux (`.panel`) et sélecteur de modèle Claude/compteur de tokens
  recolorés avec les nouvelles variables. Disposition desktop (1440px)
  inchangée (mêmes 4 colonnes) — vérifié sans débordement horizontal, à
  l'identique visuellement hormis la nouvelle palette.
  - Mode exercice, écrans étroits (<900px) : plateau agrandi
    (`--bd-size` mobile augmenté), panneau du coach/lignes du coach/
    historique restylés, feuille "Nouvel exercice" (`#exercise-phase-sheet`)
    qui monte du bas au clic sur le nouveau bouton "Nouvel exercice" de la
    barre fixe du bas, barre fixe (`#mobile-exercise-bar`, visible
    uniquement sur cet onglet) avec "Reprendre mon coup" (appelle
    `sharedReprendreCoup()` existant, jamais désactivé avant verdict comme
    demandé — contrairement à la maquette qui le montre grisé) et "Nouvel
    exercice".
  - Sélecteur de mode en menu déroulant (maquette) réalisé avec les 7
    boutons d'onglets existants (`switchModeTab`, `controls.js`) — aucune
    logique de changement de mode réécrite. `#mode-tab-bar` déplacé par JS
    (`placeModeTabBarForViewport`) entre son emplacement desktop d'origine
    et `#mobile-mode-bar-slot` collé en haut de l'écran sur mobile ; fermé,
    seul le bouton actif est visible (pastille + chevron) ; ouvert (clic
    délégué), les 7 s'affichent en liste, l'actif surligné en vert clair
    comme la maquette.
- `static/controls.js` : relocalisation du sélecteur de mode
  (`placeModeTabBarForViewport`, sur `matchMedia("(max-width:900px)")`),
  ouverture/fermeture du menu déroulant par délégation d'événement (aucun
  `onclick` des 7 boutons modifié), visibilité de la barre du bas liée à
  `switchModeTab`, historique repliable (`toggleHistoriqueCollapsed`,
  replié par défaut sur mobile seulement).
- `static/exercise.js` : feuille de phase mobile
  (`openExercisePhaseSheet`/`exercisePhaseSheetPick`/
  `launchExerciseFromSheet`) qui pilote le `<select id="exercise-phase-
  select">` existant (source de vérité, lu par `exercisePhaseFiltre()`
  inchangée) et appelle `startExercise()` sans le réécrire ; tableau
  "Lignes du coach" restylé en classes CSS (mêmes `<table>`/logique
  Play-Stop, `coach_lines.js` non touché).
- `static/board.js`/`static/llm_model.js` : bulles du chat et messages
  d'erreur (crédit épuisé, modèle indisponible) passés des couleurs codées
  en dur aux nouvelles classes `.coach-bubble.*` — pas de changement de
  comportement.
- Adaptations par rapport à la maquette (et pourquoi) :
  - Menu déroulant du sélecteur de mode : pousse en overlay (position
    absolute) plutôt que d'occuper une place fixe — évite de dupliquer les
    7 boutons.
  - Champ de saisie du coach : coins arrondis modérés (`--cc-radius-md`,
    16px) plutôt qu'une pastille pleine (99px) — la maquette n'a qu'un
    champ une ligne, l'appli utilise un `<textarea rows="3">` ; une pastille
    complète aurait été incongrue sur 3 lignes.
  - Bulle utilisateur du chat : couleur crème claire (`--cc-neutral-200`)
    choisie par cohérence avec la palette — la maquette ne montre aucun
    exemple de bulle utilisateur dans ses captures.
  - Avatar rond "C" du coach : ajouté par cohérence visuelle avec la
    maquette (élément décoratif, non cliquable, CSS pur — aucune image).
  - Sélecteur de phase natif (`<select>`) et bouton "Nouvel exercice"
    d'origine dans l'onglet Exercice : masqués sur mobile (`display:none`,
    jamais retirés du DOM) car remplacés à l'écran par la feuille du bas ;
    restent la source de vérité et fonctionnent tels quels au-dessus de
    900px.
  - Sélecteur de vitesse des lignes du coach : `<select>` d'origine
    restylé en pastille plutôt que remplacé par deux boutons — évite de
    dupliquer un état déjà porté par ce contrôle.
  - Ligne de statut `#exercise-status` : reste dans l'onglet Exercice
    (sous le plateau/coach en ordre mobile) plutôt que déplacée tout en
    haut comme la maquette — la repositionner en tête de page aurait
    nécessité une relocalisation JS supplémentaire pour un gain limité (le
    verdict apparaît de toute façon en premier plan dans le chat du coach).
- Tests (Playwright, émulation iPhone 13/390×844 tactile, + rendu Jinja2 du
  vrai template via un serveur Flask minimal ad hoc car `flask_socketio`/
  `python-chess` ne sont pas installés dans ce worktree et l'installation
  réseau est hors périmètre de cette tâche — **aucun appel API réel possible
  depuis ce worktree : ni `.env`, ni `data/`, ni `flask_socketio`/`chess`
  disponibles sans sortir du périmètre ou du réseau** ; le verdict/la
  réponse du coach n'ont donc pas pu être obtenus réellement, seulement
  simulés côté client pour vérifier le rendu) :
  - Mobile, mode exercice : ouverture de la feuille de phase, sélection
    d'une phase, "Lancer l'exercice" (fond assombri pendant la feuille,
    conforme à la capture `feuille_phase.png`) ; bulles utilisateur/coach et
    tableau "Lignes du coach" (Play/Stop) vérifiés avec des données
    injectées côté client ; dernier coup en jaune doux vérifié
    (`renderBoard` appelé directement) ; plateau côté Noirs déjà vérifié via
    la logique existante (`_boardFlipped`, inchangée) ; changement de mode
    via le menu puis retour à Exercice ; **aucun débordement horizontal
    mesuré** (`scrollWidth === clientWidth`) sur les 7 onglets.
  - Mobile, autres modes (partie libre, pédagogique, ouverture, finales,
    éditeur, bibliothèque) : changement d'onglet, capture d'écran, palette
    appliquée, aucune erreur JS (seuls des 404 attendus : favicon/
    Socket.IO, aucun serveur réel derrière ce test), aucun débordement.
  - Sélecteur de modèle Claude et compteur de tokens : rendu initial serveur
    (via le harnais Flask de test) vérifié fonctionnel avec les nouvelles
    couleurs.
  - Rendu 1440×900 comparé à l'avant : disposition à 4 colonnes inchangée,
    aucun débordement, seule la palette change.
- Limites connues : pas de test avec un vrai backend SocketIO/Stockfish/API
  Claude (indisponibles dans ce worktree sans réseau) — le parcours complet
  "coup → verdict → lecture d'une ligne" n'a été vérifié que par injection
  de données côté client, pas via un aller-retour serveur réel. Ligne de
  statut `#exercise-status` non repositionnée en tête de page (voir
  adaptations ci-dessus). Aucun fichier Python touché.

# Changelog — Issue #62

## Coach : cibler le moment le plus grave (pas seulement le premier) et donner aux explications la réfutation calculée

- Contexte : sur une partie pédagogique réelle perdue par Alain (Blancs), la
  vérification Stockfish ciblée du bloc de faits (issues #55-#57) portait
  sur 6.Nxd5/7.Qxd2 (perte nette de 2 points, le premier accroc) mais jamais
  sur 8.Qf4?? (perte de la dame sans reprise, 9 points, le vrai tournant) —
  le chat et l'analyse manuelle ne s'accordaient pas sur lequel des deux
  était "le vrai tournant". Par ailleurs, l'explication du coup flagué
  8.Qf4 ne mentionnait que "le roque était préférable pour la sécurité du
  roi", jamais la vraie raison (8...Nxf4 capture la dame) : le modèle devait
  la deviner au lieu de la recevoir.
- `game_facts.find_stockfish_check_targets` cible désormais jusqu'à DEUX
  moments (au lieu d'un seul) : "plus_grave" (la plus grande perte nette de
  toute la partie, ou un mat, toujours prioritaire) et
  "premier_significatif" (le premier moment ≥ 2 points nets ou mat, comme
  avant) — le moment le plus grave est toujours listé en premier (donc
  vérifié en priorité par app.py si le budget de temps est dépassé), les
  positions communes aux deux moments sont dédupliquées, et le second moment
  est omis s'il coïncide avec le premier. `build_game_facts_text` étiquette
  les deux groupes explicitement dans le bloc de faits ("Moment le plus
  grave" / "Premier moment significatif").
- `app.py` : `STOCKFISH_CHECK_BUDGET_TOTAL` rehaussé de 4.0s à 6.0s (jusqu'à
  4 positions désormais, contre 2 avant) — reste borné et non bloquant, la
  boucle de vérification traite les cibles dans l'ordre reçu (plus grave
  d'abord). Cache et réutilisation des résultats de "Analyser cette partie"
  inchangés.
- `game_facts.describe_reponse_suivante` (nouvelle fonction, réutilise
  `_materiel`/`_variation_materielle`/`_solde_net_apres_capture`/
  `_NOM_PIECE`/`camp_label` déjà existants) : calcule mécaniquement, depuis
  la position avant un coup flagué et le coup suivant réellement joué dans
  la partie (transmis en UCI par le client), sa conséquence matérielle
  immédiate — par exemple "réponse réellement jouée ensuite dans la partie :
  Nxf4 (Noirs (adversaire)) capture la dame de Blancs (Alain), perte nette
  de 9 points pour Blancs (Alain), aucune reprise possible." `None` si la
  réponse n'est pas une capture.
- `static/game_analysis.js` : chaque coup flagué transmis au serveur (en lot
  via `analyse_choisir_coups_decisifs`, ou à la demande via
  `analyse_expliquer_coup`) porte désormais `uci_suivant` (le coup suivant
  réellement joué, déjà en mémoire côté client) ; `app.py`
  (`_prepare_flagged_moves_for_coach`, `on_analyse_expliquer_coup`) calcule
  `reponse_suivante` via `describe_reponse_suivante` et l'ajoute aux données
  transmises au coach.
- `llm_coach.py` : `_build_context_text` affiche `reponse_suivante` comme
  fait "à expliquer EN PREMIER". `_MOVE_SELECTION_SYSTEM_PROMPT` et
  `_ANALYSE_PARTIE_ADDENDUM` demandent d'expliquer cette réfutation calculée
  en premier et interdisent de proposer une raison stratégique concurrente
  à sa place. Cohérence chat/analyse (point 3) : `_GAME_FACTS_ADDENDUM`
  désigne explicitement le "moment le plus grave" comme LE tournant ;
  `_MOVE_SELECTION_SYSTEM_PROMPT` n'autorise cette qualification que pour le
  coup de plus grosse perte de la liste transmise ; `_ANALYSE_PARTIE_ADDENDUM`
  (explication d'un coup isolé, sans visibilité sur le reste de la partie)
  interdit purement et simplement cette qualification.
- Vérifié avec le vrai python-chess (sans Stockfish, module hors périmètre
  de cet appel) sur les deux PGN de test de l'issue : cibles
  `[7.Qxd2, 8.Qf4 (plus_grave), 6.Nxd5 (premier_significatif)]` pour la
  première partie, `[15.Qb3, 16.Ke2 (plus_grave)]` pour la seconde (moments
  identiques, comme avant) ; `describe_reponse_suivante` sur 8.Qf4 renvoie
  bien la capture de la dame par 8...Nxf4 sans reprise. Pas d'appel API
  Claude réel effectué dans ce worktree (clé API hors périmètre/non
  disponible ici) — à vérifier par Alain en usage réel.

# Changelog — Issue #61

## Choix du modèle Claude (Haiku/Sonnet) depuis l'interface, sans redémarrage

- Contexte : le modèle était fixé une fois pour toutes par
  `CHESSCOACH_LLM_MODEL` (.env) — passer de Haiku (tests) à Sonnet (jeu
  sérieux) imposait d'éditer le .env et de relancer l'appli.
- `config.py` : `LLM_MODEL_HAIKU`/`LLM_MODEL_SONNET`/`LLM_MODEL_CHOICES`
  (id → libellé) définis en un seul endroit ; `config.set_llm_model(model_id)`
  change `config.LLM_MODEL` en mémoire (effet immédiat sur tous les appels
  suivants, tous chemins confondus) et persiste le choix dans
  `data/llm_model_choice.json` (nouveau fichier, séparé du .env, gitignoré
  comme le reste de data/). Au démarrage, reprend ce fichier s'il est valide,
  sinon `CHESSCOACH_LLM_MODEL` si elle correspond à l'un des deux choix,
  sinon Sonnet par défaut.
- templates/index.html : sélecteur `#llm-model-selector` dans l'en-tête, près
  du compteur de tokens — deux boutons contigus « Haiku (test) » /
  « Sonnet (sérieux) », libellés abrégés sous 900px (comme le reste de
  l'en-tête), vérifié sans débordement à 390×844 (Playwright).
- static/llm_model.js (nouveau) : clic → événement SocketIO `set_llm_model`,
  bascule le bouton actif sur confirmation (`llm_model_changed`), affiche un
  message clair dans le chat en cas de retour automatique
  (`llm_model_indisponible`).
- app.py : handler `set_llm_model` ; `_handle_llm_model_indisponible_si_besoin`
  appelé au début des 10 blocs `if error:` (un par point d'appel API) — si
  l'API refuse le modèle actif (HTTP 404 `not_found_error`, remonté par
  `llm_coach.ModeleIndisponibleError` en `error: "modele_indisponible"`),
  revient seul à l'autre choix (persisté) et prévient le client au lieu
  d'afficher une erreur technique brute.
- llm_coach.py : nouvelle exception `ModeleIndisponibleError` (même pattern
  que `CreditInsuffisantError`, issue #54), détectée dans `_call_claude` et
  propagée par les 4 fonctions publiques d'appel. `_log_coach_call` inscrit
  désormais un champ `model` explicite dans chaque entrée de
  `coach_calls.log` (déjà présent via `usage.model` sur les appels réussis,
  manquant sur les entrées d'erreur).
- Paramètres d'appel (`max_tokens=4096`, `thinking: {"type": "disabled"}`)
  vérifiés acceptés tels quels par les deux modèles — aucune adaptation par
  modèle nécessaire.
- Compteur de tokens par modèle (issue #54) déjà cohérent après un
  changement de modèle en cours de session (`_record_usage` cumule par
  modèle réellement résolu par l'API, indépendamment du sélecteur).
- CONTEXTE.md : nouvelle section « Choix du modèle Claude (Haiku/Sonnet)
  depuis l'interface (issue #61) ».

# Changelog — Issue #60

## Détection tolérante de l'erreur « crédit épuisé » de l'API (suite de l'issue #54)

- Contexte : la détection introduite à l'issue #54 ne reconnaissait qu'une
  seule forme exacte (HTTP 403, `error.type == "billing_error"`). Des
  retours d'utilisateurs de l'API (2024-2025, non revérifiables sans
  épuiser réellement un crédit) indiquent qu'un solde insuffisant peut
  aussi se manifester en HTTP 400 `invalid_request_error` avec un message
  du type « Your credit balance is too low to access the Anthropic API.
  Please go to Plans & Billing to upgrade or purchase credits. » — un cas
  qui tombait auparavant dans l'erreur générique, sans le message clair ni
  le lien vers la Console.
- `llm_coach.py` (`_call_claude`, gestion de `urllib.error.HTTPError`) :
  la détection reconnaît désormais trois formes, sans se fier à un unique
  couple (code, type) :
  - `error.type == "billing_error"`, quel que soit le code HTTP ;
  - code HTTP 402, quel que soit `error.type` ;
  - code HTTP 400 avec `error.type == "invalid_request_error"` dont le
    message contient (insensible à la casse) « credit balance »,
    « insufficient credit » ou « plans & billing »/« plans and billing ».
  - Une vraie erreur de permission (403 `permission_error`) et une vraie
    requête invalide (400 sans mention de crédit) continuent de propager
    l'erreur HTTP normale (pas de `CreditInsuffisantError`).
  - Le message affiché à l'utilisateur (bulle dédiée + lien Console) est
    inchangé : tous les appelants attrapent `CreditInsuffisantError` de la
    même façon qu'avant.
- Docstrings de `CreditInsuffisantError` et `_call_claude`, et `CONTEXTE.md`,
  mis à jour pour refléter la détection élargie.
- Vérification par simulation locale (`urllib.request.urlopen` mocké, aucun
  appel réseau réel — voir la section « Limite » ci-dessous) : les 5 cas
  suivants ont été rejoués et donnent le résultat attendu :
  1. HTTP 403 `billing_error` (forme historique) → `CreditInsuffisantError`.
  2. HTTP 402 `invalid_request_error` → `CreditInsuffisantError`.
  3. HTTP 400 `invalid_request_error`, message « Your credit balance is too
     low ... Plans & Billing ... » → `CreditInsuffisantError`.
  4. HTTP 403 `permission_error` (vraie erreur de permission) →
     `HTTPError` propagée normalement, PAS de `CreditInsuffisantError`.
  5. HTTP 400 `invalid_request_error` sans mention de crédit (« messages:
     at least one message is required ») → `HTTPError` propagée
     normalement, PAS de `CreditInsuffisantError`.
- Limite assumée : cette vérification simule le corps de réponse HTTP tel
  que rapporté par des utilisateurs de l'API ; elle ne constitue pas un
  test sur une vraie réponse de crédit épuisé (impossible à provoquer sans
  épuiser réellement le crédit de la clé API). Si la forme réelle
  divergeait encore de ces trois hypothèses, un nouvel ajustement resterait
  possible.

# Changelog — Issue #59

## « Analyser cette partie » depuis le bandeau de fin de partie : un seul clic

- Contexte : le bouton "Analyser cette partie" de la bannière de fin de
  partie (mat/pat/nulle/abandon) basculait vers l'onglet Bibliothèque /
  Revue PGN et y chargeait la partie, mais ne lançait pas l'analyse —
  Alain devait recliquer sur le bouton "Analyser cette partie" de l'onglet,
  placé sous la liste des parties importées (loin en bas sur GSM).
- `static/game_analysis.js` : `analyserPartieDepuisPgn()` (appelée par la
  bannière — `board.js showGameOverBanner`, câblée dans pedagogic.js/
  free_play.js/opening.js/finales.js) appelle désormais
  `_lancerAnalyseAutoDepuisBanniere()` une fois la partie chargée en revue :
  - Si la partie qui vient d'être chargée correspond coup à coup (mêmes SAN,
    même ordre) au dernier rapport en mémoire (`_gameAnalysisResults` — une
    analyse déjà menée cette session, quel que soit l'onglet actif depuis),
    réaffiche directement ce rapport sans relancer Stockfish.
  - Sinon, lance `analyserPartieCourante()` (état "en cours" affiché,
    bouton de l'onglet désactivé pendant l'analyse — comportement déjà
    existant, réutilisé tel quel).
  - Dans les deux cas, fait défiler la page pour amener
    `#game-analysis-panel` en vue (`scrollIntoView`), une fois le résultat
    (ou le rapport en cache) réellement affiché — important en mobile où ce
    panneau est placé sous la longue liste de parties importées.
- `templates/index.html` : ajout de l'id `game-analysis-panel` sur le
  conteneur du bouton/statut/rapport d'analyse (cible du scroll).
- Le bouton de l'onglet Bibliothèque / Revue PGN (`analyserPartieCourante`,
  clic manuel pour une partie chargée à la main) garde son comportement
  actuel — aucun changement de ce chemin, aucun défilement automatique
  ajouté pour lui.
- Vérifié en conditions réelles (Playwright + Stockfish local, viewport
  390×844) : partie pédagogique abandonnée après 1.e4 → un seul clic sur la
  bannière déclenche bien l'état "Analyse Stockfish en cours..." avec bouton
  désactivé, puis "Analyse terminée" avec le panneau ramené dans le
  viewport ; rejouer le même point d'entrée pour la même partie affiche
  directement "Analyse déjà disponible... réalisée plus tôt dans la
  session" sans nouvel appel réseau (0 émission socket `analyser_pgn`
  vérifiée). Même mécanisme revérifié en partie libre. Aucun appel à l'API
  Claude effectué (pas de clé `ANTHROPIC_API_KEY` disponible dans cet
  environnement de test) — seule l'analyse mécanique Stockfish a été
  vérifiée en conditions réelles ; les explications narratives du coach
  (`demanderExplicationsCoach`, appelées après l'analyse) n'ont pas été
  exercées.

# Changelog — Issue #58

## Mode exercices : tableau "Lignes du coach", extraction + lecture des lignes citées sur l'échiquier

- Contexte : en mode exercice, le coach cite souvent une ligne de coups
  dans sa prose (ex. « la ligne logique est Kc3 Ke1 Kd3 Kd1 Ke3 Kc2 »),
  qu'Alain devait jusqu'ici rejouer à la main pour la visualiser.
- `static/coach_lines.js` (nouveau, composant réutilisable mode-agnostique,
  ne dépend que de chess.js) :
  - `extractCoachMoveLines(text)` — repère les suites d'au moins deux coups
    en notation standard (numéros de coups et annotations !?+# tolérés et
    retirés), dédoublonne, et ignore les chemins de cases séparés par des
    tirets (`c3-d3-e3`) qui ne sont pas des coups.
  - `resolveCoachLineStart(candidates, moves)` — détermine la position de
    départ par légalité (jamais par déduction) : essaie chaque candidat
    fourni dans l'ordre et retient le premier où tous les coups sont
    légaux ; retourne `null` si aucun candidat ne convient.
  - `playCoachLineSequence(steps, opts)` — lecture pas à pas avec pause
    configurable, callback de rendu fourni par l'appelant, contrôleur
    `{stop()}` pour interrompre en cours de route.
- `static/exercise.js` : nouveau tableau "Lignes du coach" dans le panneau
  du mode exercice, alimenté à chaque réponse du coach reçue pendant
  l'exercice actif (verdict `exercise_comment`, et questions de suivi
  posées dans le chat libre/à la demande pendant l'exploration après
  verdict, via le nouveau hook générique `exerciseOnCoachText`) :
  - Pour chaque ligne, deux candidats de départ sont essayés dans l'ordre :
    la position d'avant le coup d'Alain (`exerciseFenAvant` — couvre aussi
    le cas où la ligne commence par son propre coup), puis la position
    juste après (`exerciseFenApresCoup`, nouvelle variable capturée dans
    `submitExerciseAnswer`). Le tableau affiche laquelle a été retenue
    (« depuis la position de départ » / « depuis la position après ton
    coup »), ou « ligne non jouable » (discret, sans bouton) si aucune des
    deux ne convient.
  - Bonus : la meilleure ligne déjà calculée par Stockfish
    (`exercisePvMeilleurCoup`, transmise avec le verdict depuis l'issue
    #20) est ajoutée en première ligne, étiquetée « Ligne de Stockfish »,
    dédoublonnée contre une ligne identique citée par le coach en prose.
  - Bouton Play/Stop par ligne, sélecteur de vitesse (0,5 s / 1 s, 1 s par
    défaut) partagé par le tableau. Pendant la lecture, le plateau affiche
    la ligne (surlignage du dernier coup comme d'habitude) sans toucher à
    `exerciseGame`, à l'historique de l'exercice ni au chat, et sans
    déclencher de commentaire automatique — un bouton « Revenir à la
    position de l'exercice » (affiché dès la première lecture, masqué
    après usage) restaure la position réelle de l'exercice. Les clics sur
    le plateau sont bloqués tant que cette prévisualisation est active,
    pour ne jamais mélanger les deux positions.
  - Tableau vidé à chaque nouvel exercice (et à l'abandon), conservé lors
    d'un « Reprendre mon coup » (juste sorti du mode prévisualisation).
- `static/board.js` : `coach_response` et `coach_on_demand_response`
  appellent désormais `exerciseOnCoachText(text)` si cette fonction existe
  (no-op hors mode exercice) — mécanisme générique, pas de dépendance
  directe de board.js à exercise.js.
- `llm_coach.py` (`_EXERCISE_SYSTEM_ADDENDUM`) : consigne courte ajoutée au
  prompt du coach en mode exercice pour écrire toute ligne de coups en
  notation standard, coups séparés par des espaces — fiabilise
  l'extraction côté client.
- `templates/index.html` : inclusion de `coach_lines.js` (avant
  `exercise.js`) et nouveau bloc HTML `#exercise-coach-lines` (titre,
  sélecteur de vitesse, tableau, bouton de retour) dans le panneau du mode
  exercice.

### Tests réalisés

- Tests unitaires Node purs (extraction + résolution de légalité, sans
  navigateur) : exemple de l'issue (ligne démarrant par le coup d'Alain,
  résolue « depuis la position de départ »), ligne légale seulement depuis
  la position après le coup, ligne illégale depuis les deux candidats (→
  `null`, aucun bouton), faux positif `c3-d3-e3` (aucune ligne extraite),
  numéros de coups + annotations `!?+#` correctement nettoyés,
  dédoublonnage de lignes identiques.
- Tests bout en bout avec Playwright (Chromium) contre le serveur Flask du
  worktree, **avec de vrais appels à l'API Claude** (clé lue depuis le
  `.env` existant de `~/ChessCoach`, non modifié, seulement exportée dans
  l'environnement du process de test) :
  - Nouvel exercice → coup joué → verdict reçu → tableau peuplé
    correctement, avec une ligne Stockfish bonus et une ligne citée par le
    coach commençant par son propre coup (« depuis la position de
    départ »).
  - Un second essai a naturellement produit le cas « ligne qui ne démarre
    qu'après le coup d'Alain » (résolue « depuis la position après ton
    coup ») avec un vrai texte de coach.
  - Play → lecture animée visible sur le plateau (capture d'écran) → Stop
    en cours de lecture (bouton repasse à "Play", `exerciseGame.fen()`
    inchangé) → « Revenir à la position de l'exercice » restaure bien la
    position réelle et se masque ensuite ; nombre de bulles du chat
    inchangé après lecture/arrêt/retour (aucun commentaire auto, aucun
    effacement).
  - Ligne illégale injectée (`Qxh7 Rxh7` sur une position sans dame ni
    tour disponibles) → affichée « ligne non jouable », sans bouton ; texte
    contenant un chemin `c3-d3-e3` → aucune ligne fantôme créée.
  - Viewport mobile 390×844 (tactile, `page.tap`) : tableau lisible sans
    débordement horizontal, bouton Play ~52×44 px (cible tactile correcte),
    Play/Stop/retour fonctionnels au toucher.
- `python3 -m py_compile` sur les fichiers Python modifiés, `node --check`
  sur les fichiers JS modifiés/créés.

# Changelog — Issue #57

## Bloc de faits du chat : solde net après reprise, et coup décisif vérifié par Stockfish

- Contexte : test réel du bloc de faits calculés (issues #55/#56) sur une
  partie pédagogique perdue (Alain Blancs). Deux défauts constatés dans la
  réponse réelle du coach : (1) le moment clé « 16...Rxb3 : Noirs capture la
  dame en b3 (reprise possible), variation matérielle de 9 points » a été lu
  par le coach comme une perte sèche de 9 points, en ignorant que la reprise
  (Bxb3/Nxb3/axb3) ramène le solde réel à 4 points ; (2) le bloc ne contenait
  aucune évaluation par un moteur, donc rien ne pouvait mettre le coach sur
  la piste du vrai remède (15...Nxd3+ 16.Qxd3 échappait à la tour) — il s'est
  contenté de suggérer « vérifier ce qui attaquait la dame ».

- `game_facts.py` :
  - `_variation_materielle` : factorise le calcul de la variation matérielle
    signée d'un demi-coup, déjà présent dans la boucle de
    `build_game_facts_text`, pour que le ciblage Stockfish (voir plus bas)
    s'accorde exactement sur les mêmes demi-coups ;
  - `_solde_net_apres_capture` : calcule mécaniquement (python-chess, coups
    légaux réels, aucun moteur) le solde net, du point de vue du camp qui
    vient de perdre une pièce, s'il la reprend immédiatement sur la même
    case (une seule reprise, pas de recherche tactique plus profonde) ;
    retourne `None` si aucune reprise n'est légale ;
  - `_decrit_moment_cle` : un moment clé qui capture une pièce indique
    désormais, quand une reprise est possible, le solde net après cette
    reprise et dit explicitement qu'il s'agit du résultat réel de l'échange
    (pas la variation brute) ; quand aucune reprise n'est possible, dit
    explicitement que la variation brute est bien le résultat final — dans
    les deux cas, plus d'ambiguïté sur lequel des deux chiffres retenir ;
  - nouvelle fonction `find_stockfish_check_targets(pgn_text, camp_alain)` :
    identifie, SANS appeler Stockfish (le module n'en fait toujours aucun
    appel direct), les deux derniers coups d'Alain qui précèdent le premier
    moment où il perd au moins 2 points nets (après reprise mécanique
    éventuelle) ou se fait mater — le coup qui a permis la perte, et celui
    d'avant. Retourne les FEN/SAN de ces positions ; c'est l'appelant
    (`app.py`, qui détient `engine_manager`) qui fait le calcul Stockfish
    lui-même ;
  - `build_game_facts_text` : nouveau paramètre optionnel `stockfish_check`
    (liste de dicts `{numero, san, camp, meilleur_coup, perte_cp,
    ligne_principale}`) qui ajoute une section « Vérification Stockfish
    ciblée » au bloc quand elle est fournie et non vide.

- `engine_stockfish.py` : `EngineManager.evaluate()` et `.evaluate_move()`
  acceptent un nouveau paramètre optionnel `time_limit` (secondes) qui, s'il
  est fourni, borne la recherche Stockfish en TEMPS plutôt qu'en profondeur
  (`chess.engine.Limit(time=...)` au lieu de `Limit(depth=...)`) — une
  profondeur fixe ne borne pas le temps de calcul sur une position complexe,
  alors que Stockfish respecte lui-même un temps de recherche donné
  (movetime), sans thread de timeout externe. Comportement par défaut
  (`time_limit=None`) inchangé pour tous les appelants existants.

- `app.py` :
  - nouvelles fonctions `_cached_stockfish_eval` (réutilise un résultat déjà
    calculé par « Analyser cette partie » cette session si la position
    correspond exactement, via `fen_avant`), `_stockfish_eval_cible` (appel
    Stockfish borné à `STOCKFISH_CHECK_TIME_PAR_POSITION` = 0.7s par
    position) et `_stockfish_check_key_moment` (orchestration : cible via
    `game_facts.find_stockfish_check_targets`, cache ou calcul, budget
    global `STOCKFISH_CHECK_BUDGET_TOTAL` = 4s, jamais d'exception qui
    remonterait jusqu'à la réponse du coach) ;
  - cache mémoire process (`_stockfish_check_cache`, clé
    `(camp_alain, pgn)`) pour ne pas relancer Stockfish à chaque tour du
    chat sur la même position — le PGN change dès qu'un nouveau coup est
    joué, la clé se périme donc naturellement ; purge grossière au-delà de
    50 entrées ;
  - `_enrich_context_with_game_facts` appelle désormais
    `_stockfish_check_key_moment` et transmet son résultat à
    `build_game_facts_text` via `stockfish_check`.

- `static/board.js` : `_coachAnalysisFlaggedMoves()` transmet désormais
  aussi `fen_avant`/`best_move` (déjà présents dans `_gameAnalysisResults`,
  simplement pas encore relayés) pour permettre au serveur de reconnaître une
  position déjà analysée par « Analyser cette partie » cette session, et
  d'éviter un nouvel appel Stockfish pour la vérification ciblée du chat.

- `llm_coach.py` (`_GAME_FACTS_ADDENDUM`) : renforcement du prompt —
  (1) le coach doit citer le solde net (pas la variation brute) quand le
  bloc en fournit un, et ne doit jamais annoncer un chiffre de variation
  matérielle différent de celui du bloc ; (2) le coach ne doit s'appuyer que
  sur le meilleur coup / la ligne principale Stockfish tels qu'ils figurent
  dans la section « Vérification Stockfish ciblée » — jamais d'invention de
  variante si cette section est absente ou ne couvre pas le coup en
  question (Stockfish indisponible/trop lent), auquel cas le coach dit
  qu'il ne sait pas plutôt que d'improviser ; (3) le chiffre brut de
  centipawns de « perte estimée » ne doit jamais être cité tel quel
  (reformulation en langage naturel, même consigne que le mode exercice).

- Test réel (positions rejouées mécaniquement + Stockfish 16 local, PGN de
  l'issue, Alain Blancs) :
  - le solde net calculé au coup 16 est bien **-4** (variation brute 9,
    reprise de la tour possible par Blancs (Alain)) ;
  - les deux positions ciblées automatiquement sont bien 15.Qb3 et 16.Ke2 ;
  - Stockfish (0.7s/position, 2.8s au total dans ce test) trouve **d4**
    (perte 317cp) comme meilleur coup à la place de 15.Qb3, et **Kf1**
    (perte 65cp) à la place de 16.Ke2 ;
  - **écart avec l'énoncé de l'issue** : l'énoncé attendait que Qxd3
    ressorte comme meilleur coup à la place de 16.Ke2. Une analyse Stockfish
    plus poussée (multipv, 3s) montre que Qxd3 est en réalité le PLUS
    mauvais des 4 coups légaux à cette position (-1326cp contre -1066 pour
    Kf1) : le pion noir resté en e4 depuis 3...dxe4 (jamais repris) garde la
    case d3 sous surveillance, donc 16.Qxd3 hangerait la dame à 16...exd3.
    Le bloc reflète donc fidèlement ce que Stockfish calcule réellement
    (Kf1), pas l'hypothèse de l'énoncé — c'est exactement le comportement
    voulu par la consigne « le coach ne doit s'appuyer que sur le meilleur
    coup de Stockfish tel qu'il figure dans le bloc, pas d'invention » ;
    l'énoncé se trompait sur ce point précis d'analyse humaine ;
  - dégradation gracieuse vérifiée : Stockfish indisponible
    (`engine_manager` absent) → bloc sans section Stockfish mais solde net
    toujours présent ; erreur/lenteur simulée pendant l'appel moteur →
    aucune exception ne remonte, la ligne concernée est simplement omise ;
  - réutilisation du cache vérifiée : un résultat déjà présent dans
    `analyse_mecanique_flags` (simulant « Analyser cette partie » déjà
    lancée) est utilisé tel quel, sans second appel Stockfish.

- Pas d'appel réel à l'API Claude dans ce test (clé API non sollicitée pour
  cette vérification) : contenu exact du bloc de faits vérifié directement
  (voir ci-dessus), comportement du coach lui-même non observé en conditions
  réelles — cohérent avec le renforcement de prompt apporté, mais non
  exécuté de bout en bout.

- Limites connues : le solde net ne regarde qu'UNE reprise immédiate (pas de
  recherche tactique plus profonde, ex. un fork qui suivrait la reprise) —
  volontairement mécanique, pas une évaluation Stockfish ; la vérification
  Stockfish ne porte que sur le premier moment clé de perte nette
  d'au moins 2 points ou de mat, jamais sur plusieurs moments de la même
  partie ; le cache de vérification est un simple dict process (pas de
  notion de session à isoler, cohérent avec l'usage mono-utilisateur de
  l'appli).

# Changelog — Issue #56

## Explications de coups de l'analyse post-partie : étiqueter chaque coup par son auteur ; compléter le bloc de faits avec la fin de partie

- Contexte : en usage réel après « Analyser cette partie » sur une partie
  pédagogique abandonnée (Alain Blancs, Stockfish Noirs), l'explication du
  coup flagué « 10. (Noirs) Bf8 » disait « Alain le replie en f8 » — un coup
  des Noirs attribué à Alain — et nommait l'ouverture « Française » alors
  que la partie commençait par 1.c4 Nf6 2.d4 c6 3.Nf3 e6 4.g3 (pas une
  Française). Même famille de bug que l'issue #55 (chat libre), mais sur un
  autre chemin de code : le module d'explications narratives des coups
  décisifs (`get_move_explanations`, appel en lot, issue #42) et
  l'explication à la demande d'un coup unique (`on_analyse_expliquer_coup`)
  ne recevaient jusque-là aucune information sur le camp d'Alain.
- `game_facts.py` :
  - `_camp_label` renommée `camp_label` (fonction publique) pour être
    réutilisée telle quelle par `llm_coach.py`, au lieu d'en redupliquer la
    logique (« Blancs (Alain) »/« Noirs (adversaire) », jamais une simple
    déduction du trait) ;
  - nouvelle fonction `camp_alain_from_pgn_headers(white, black)` : déduit
    le camp d'Alain depuis les en-têtes PGN White/Black — pseudo
    Lichess/Chess.com (`athanatos123`, casse ignorée) pour une partie
    importée de la bibliothèque, ou le nom « Alain » pour une partie jouée
    dans l'appli (pédagogique/ouverture/finales taguent déjà leurs en-têtes
    ainsi avant l'analyse). Retourne `""` si aucun des deux en-têtes ne
    correspond (partie entre deux tiers, partie libre où les deux camps
    peuvent être joués par Alain) — jamais une devinette ;
  - `build_game_facts_text` : la fin de partie (mat, pat, nulle par la
    règle — matériel insuffisant/75 coups/répétition quintuple —, ou
    abandon déduit du `Result` PGN si aucune de ces règles ne s'applique)
    est désormais ajoutée comme dernier moment clé, même sans aucune
    variation matérielle d'au moins 2 points. Constat en test réel : une
    partie perdue par mat en 9 coups (9...Qxh2#) sans la moindre perte de
    matériel ne déclenchait jusque-là aucun moment clé, le coach ne s'en
    sortant que grâce au signe « # » du texte PGN — ce qui n'est plus
    laissé au hasard (calculé mécaniquement avec `board.is_checkmate()`/
    `is_stalemate()`/`is_insufficient_material()`/`is_seventyfive_moves()`/
    `is_fivefold_repetition()`).
- `llm_coach.py` :
  - `get_move_explanations(flagged_moves, camp_alain, config)` — nouveau
    paramètre `camp_alain`. Chaque coup flagué reçoit désormais un champ
    `auteur` déjà calculé (via `game_facts.camp_label`, réutilisé plutôt que
    reduplié) — p. ex. `"Noirs (adversaire)"` — que le prompt système lui
    demande explicitement de recopier tel quel, jamais de redéduire lui-même
    depuis le seul champ `camp`. Le JSON envoyé au coach passe d'une simple
    liste de coups à `{"camp_alain": "blancs"|"noirs"|null, "coups": [...]}}`
    (le format de la réponse attendue, `{"choix": [{"id", "explication"}]}`,
    est inchangé — aucun impact sur la réassociation côté client) ;
  - `_MOVE_SELECTION_SYSTEM_PROMPT` renforcé : un coup dont l'auteur ne
    contient pas « Alain » n'est jamais présenté comme joué par lui ; pour
    l'erreur d'un adversaire, expliquer ce qu'elle offre à Alain plutôt que
    de la commenter comme un coup d'Alain ; si `camp_alain` est `null`, ne
    prêter aucun coup ni à Alain ni à « l'adversaire » (décrire uniquement
    Blancs/Noirs) ; ne jamais nommer une ouverture précise (elle n'est
    jamais fournie dans les données) — décrire la structure sans lui donner
    de nom inventé ;
  - nouvel addendum `_ANALYSE_PARTIE_ADDENDUM`, ajouté par
    `get_coach_response` quand `context.mode_origine == "analyse_partie"`
    (explication à la demande d'un coup unique, `on_analyse_expliquer_coup`) :
    même garde-fou (camp_alain seule source fiable, jamais de nom
    d'ouverture inventé), indépendant et cumulable avec les addenda
    existants (exercice, faits calculés, etc.) ;
  - `_build_context_text` : nouveau cas `camp_alain_inconnu` (distinct de
    l'absence simple de `camp_alain`) — dit explicitement au coach que le
    camp d'Alain a été recherché mais n'a pas pu être déterminé, pour qu'il
    décrive les coups par Blancs/Noirs sans deviner qui est Alain.
- `app.py` :
  - nouvelle fonction `_camp_alain_pour_analyse(data)` : appelle
    `game_facts.camp_alain_from_pgn_headers` sur les champs `white`/`black`
    transmis par le client, et distingue « camp indéterminable » (au moins
    un en-tête transmis, aucun ne correspond à Alain) d'« aucune info
    transmise » ;
  - `on_analyse_choisir_coups_decisifs` et `on_analyse_expliquer_coup`
    l'utilisent pour passer `camp_alain`/`camp_alain_inconnu` au coach.
- `static/board.js` : `reviewWhite`/`reviewBlack` mémorisent les en-têtes
  PGN White/Black de la partie chargée en revue (`parsePgn`), qu'elle vienne
  de la bibliothèque ou du bouton « Analyser cette partie » depuis la
  bannière de fin de partie (pédagogique/ouverture/finales taguent déjà
  leurs en-têtes PGN avec « Alain »/le nom de l'adversaire avant d'appeler
  `analyserPartieDepuisPgn`).
- `static/game_analysis.js` : `demanderExplicationsCoach` et
  `demanderExplicationCoup` transmettent désormais `white`/`black` au
  serveur avec les coups flagués.
- Testé (sans appel API réel — clé API non vérifiée depuis ce worktree,
  cf. rapport de clôture) :
  - PGN de test d'acceptation (1.c4 Nf6 2.d4 c6 3.Nf3 e6 4.g3 ... 18...Qxa4,
    Alain Blancs) : `camp_alain_from_pgn_headers("Alain", "Stockfish")` →
    `"blancs"` ; `build_game_facts_text` étiquette bien 10...Bf8 et
    11...Nxe4 « Noirs (adversaire) » ; aucun nom d'ouverture dans les
    données envoyées au coach (jamais calculé, seulement les coups/camps/
    auteurs) ;
  - PGN de bibliothèque avec en-tête Black = `athanatos123` (Alain aux
    Noirs) : camp déduit `"noirs"` ; avec deux pseudos tiers, camp déduit
    `""` (indéterminable, propagé tel quel) ;
  - partie perdue par mat en 9 coups (matériel intact avant le mat) :
    nouveau moment clé de fin de partie généré mécaniquement, sans dépendre
    du signe « # » du texte PGN.

# Changelog — Issue #55

## Chat coach : bloc de faits calculés (camps, matériel, moments clés) pour ne plus faire relire le PGN au modèle

- Contexte : en usage réel, le chat libre après une partie pédagogique
  abandonnée (Alain Blancs, 18...Qxa4) a attribué à Alain des coups des
  Noirs, inventé un échange de dames inexistant, et manqué l'événement
  décisif (perte de la dame blanche au coup 15, sans reprise possible) —
  le modèle reconstitue mal la partie en relisant lui-même le PGN en texte,
  et l'appli ne lui fournissait jusque-là aucun fait déjà calculé pour ce
  chat (contrairement aux autres modes, déjà ancrés sur des données
  calculées, cf. issues #25/#44).
- `game_facts.py` (nouveau module) : `build_game_facts_text(pgn, camp_alain,
  flagged_moves=None)` calcule mécaniquement, avec python-chess (aucun appel
  à Stockfish, aucun appel API supplémentaire) :
  1. la liste des coups numérotés (`15.`/`15...`) avec le camp explicite de
     chaque coup (« Blancs (Alain) »/« Noirs (adversaire) », ou l'inverse
     selon `camp_alain` — y compris les camps inversés en finales, déjà
     résolus côté client) et le bilan matériel après chaque coup, en points
     classiques, du point de vue d'Alain ;
  2. les « moments clés » : chaque coup où le bilan matériel varie d'au
     moins 2 points, avec qui capture quoi et si une reprise immédiate est
     légale (`board.legal_moves` après le coup — pas une supposition, ce qui
     avait justement fait inventer une reprise impossible dans l'incident
     source) ;
  3. la position actuelle : liste des pièces par camp avec leurs cases
     exactes, FEN, matériel restant, et une ligne explicite dès qu'un camp
     n'a plus de dame ;
  4. si fournis (`flagged_moves`), les coups déjà flagués par une analyse
     mécanique Stockfish faite pendant la session (bouton « Analyser cette
     partie »).
  Repli silencieux (`""`) si le PGN est vide/illisible ou si `camp_alain`
  n'est pas `"blancs"`/`"noirs"` : le chat reste utilisable sans ce bloc.
- `app.py` : nouvelle fonction `_enrich_context_with_game_facts`, appelée
  par le handler `coach_ask` (chat libre) avant `get_coach_response`. N'agit
  que quand le contexte transmis par le client contient à la fois un PGN et
  un `camp_alain` non vide — c'est-à-dire les modes interactifs (partie
  libre, pédagogique, ouverture, finales), jamais la revue de la
  bibliothèque PGN (qui ne transmet pas `camp_alain`, cf. `board.js`) ni le
  mode exercice (déjà ancré sur Stockfish, pas de PGN transmis) ni une
  démonstration Stockfish-contre-Stockfish (`mode_demonstration`, issue
  #29 — aucun camp n'y est réellement « Alain »). Best-effort : une erreur
  de calcul renvoie le contexte inchangé, sans jamais faire échouer la
  réponse du coach.
- `llm_coach.py` : le nouveau champ de contexte `faits_calcules` est
  sérialisé dans `_build_context_text` juste avant le PGN, et déclenche un
  nouvel addendum de prompt système (`_GAME_FACTS_ADDENDUM`, dans
  `get_coach_response`) : appuyer chaque affirmation sur ce bloc et sur le
  PGN, ne jamais citer un coup/une capture/une reprise/une pièce absente de
  ces données, ne jamais attribuer un coup au mauvais camp, dire qu'on n'est
  pas sûr en cas de doute, et commencer par les moments clés pour toute
  question du type « que s'est-il passé ? ». Indépendant des autres
  addenda (exercice/anti-invention/démonstration) : peut se combiner avec
  eux.
- `static/board.js` (`coachBuildContext`) : nouvelle fonction
  `_coachAnalysisFlaggedMoves()` qui rapproche le rapport mécanique de la
  dernière analyse « Analyser cette partie » (`_gameAnalysisResults`,
  `game_analysis.js`, qui reste en mémoire tant que la page n'est pas
  rechargée) de la partie réellement en cours dans le mode interactif actif
  — coup à coup, même longueur et mêmes SAN dans le même ordre — pour
  éviter de transmettre par erreur l'analyse d'une autre partie. Ajouté au
  contexte (`analyse_mecanique_flags`) uniquement pour les modes qui
  transmettent déjà l'historique (`avecHistorique` : libre/pédagogique/
  ouverture/finales).
- Non modifié, volontairement hors périmètre de l'issue : le mode exercice
  (déjà ancré sur Stockfish) et la revue de parties importées de la
  bibliothèque.

### Vérifications faites

- Rejeu exact du PGN de test de l'issue (Alain Blancs, partie abandonnée
  après 18...Qxa4) via `game_facts.build_game_facts_text` : le bloc généré
  signale bien, au coup `15... Qxd1+`, la capture de la dame blanche par
  les Noirs (adversaire) sans reprise possible (variation de 9 points), une
  position finale sans dame blanche, la dame noire en a4, et un matériel de
  24 (Alain) contre 32 (adversaire) — exactement les valeurs attendues par
  le test d'acceptation.
- Contrôle croisé indépendant du matériel final avec un rejeu manuel du même
  PGN en python-chess (script ad hoc, hors du dépôt) : mêmes totaux (24/32),
  même case pour la dame noire (a4), mêmes deux camps sans doublon de pièces.
- `_enrich_context_with_game_facts` (`app.py`) testé directement (venv de
  test hors dépôt, `python-chess`/`Flask`/`Flask-SocketIO` installés
  temporairement) : ajoute bien `faits_calcules` quand `pgn`+`camp_alain`
  sont présents, renvoie le contexte inchangé si `camp_alain` est absent
  (cas de la revue bibliothèque) ou si `mode_exercice` est vrai.
- Pipeline complet `llm_coach.get_coach_response` testé avec `_call_claude`
  intercepté (pas d'appel réseau) : le system prompt final contient bien
  l'addendum `_GAME_FACTS_ADDENDUM` et le bloc de faits calculés, y compris
  la ligne du moment clé du coup 15.
- Cas d'une position de départ non standard (`[SetUp "1"]`/`[FEN ...]`,
  scénario des modes finales/ouverture) : `chess.pgn.read_game` respecte
  bien ces en-têtes (confirmé aussi côté client : `chess.js` les pose
  automatiquement dès que la position de départ diffère de la position
  standard, `static/vendor/chess.js/chess.min.js`), le bloc généré reflète
  la bonne position de départ.
- `py_compile` sur `app.py`/`llm_coach.py`/`game_facts.py` : OK. `node
  --check` sur `static/board.js` : OK.

### Limites

- **Aucun vrai appel à l'API Claude n'a pu être fait** : aucune
  `ANTHROPIC_API_KEY` n'est présente dans l'environnement de ce worktree et
  le `.env` n'a pas été touché (consigne explicite). La vérification s'est
  donc arrêtée au contenu exact du contexte construit et du system prompt
  assemblé (voir ci-dessus), pas à la réponse réelle du coach en conditions
  réelles — à confirmer par Alain en usage réel sur ce cas précis.
- Le rapprochement de l'analyse mécanique à la partie en cours (point 4,
  `_coachAnalysisFlaggedMoves`) est fait par comparaison exacte des SAN —
  toute divergence (partie reprise différemment, coup annulé/rejoué) fait
  disparaître silencieusement les coups flagués du contexte plutôt que de
  risquer un rapprochement erroné ; ce choix n'a pas été testé en conditions
  réelles d'interface (pas de navigateur disponible dans ce worktree).
- « Reprise possible » est calculé comme « un coup légal peut reprendre
  immédiatement sur cette case », ce qui couvre le cas de l'incident source
  (fou c1 bloquant la tour a1) mais ne distingue pas une reprise possible
  mais désavantageuse d'une reprise réellement favorable — hors périmètre
  de la tâche demandée (faits, pas jugement).

# Changelog — Issue #54

## Compteur discret de tokens consommés dans l'en-tête (sans notion de prix)

- Contexte : le solde restant de la clé API n'est pas lisible par
  programme (uniquement sur la Console) et Alain préfère ne pas maintenir
  de table de prix par modèle côté ChessCoach — décision explicite :
  afficher uniquement des tokens bruts, sans aucun prix ni équivalent en
  argent.
- `llm_coach.py` (`_call_claude`) : relève `usage.input_tokens` /
  `output_tokens` / `cache_creation_input_tokens` / `cache_read_input_tokens`
  depuis la réponse de chaque appel réussi à l'API — aucun appel
  supplémentaire, ces informations sont déjà présentes dans la réponse
  normale. Cumulés par modèle réellement utilisé (`data["model"]` de la
  réponse, pas le paramètre d'entrée qui peut être un alias ou vide) dans
  `data/usage_tokens.json` (nouveau `config.USAGE_TOKENS_PATH`, sous
  `DATA_DIR`, donc gitignoré comme le reste de `data/`) via
  `_record_usage`/`_save_usage`/`load_usage`/`get_usage_summary`/
  `reset_usage`. Le fichier garde une date de départ du cumul et le détail
  du dernier appel ; il survit à un redémarrage de l'appli.
  Tous les chemins d'appel sont couverts (`get_coach_response`,
  `get_move_explanations`, `get_opening_moves`, `get_training_program`) —
  donc chat du coach, explications de coups, programme d'entraînement, et
  commentaires des modes ouverture/finales/pédagogique/exercice, tous
  branchés sur `_call_claude`.
- `app.py` : nouveaux handlers SocketIO `usage_get` (demande explicite du
  compteur, utilisé au chargement de la page) et `usage_reset` (remise à
  zéro, bouton discret de l'en-tête). `_emit_usage_update()` pousse le
  compteur à jour après chaque appel au coach (succès ou échec). Rendu
  initial fait côté serveur dans `index()` (`usage_summary`) pour éviter
  un flash "—" avant la première connexion Socket.IO.
- `templates/index.html` / `static/usage_tokens.js` (nouveau fichier) :
  widget discret `#usage-tokens-widget` près du lien "Coût API" existant —
  tokens du dernier appel et total cumulé depuis la date de départ
  (entrée/sortie séparées), détail par modèle au survol (desktop) ou au
  tap (tactile, bascule de classe CSS). Sur écran étroit (media query
  `max-width: 900px`), le texte bascule vers une forme compacte
  (`Σ … in / … out`). Bouton "Remettre le compteur à zéro" dans le détail,
  avec confirmation `confirm()` légère.
  - Bug trouvé et corrigé en testant au rendu réel (Playwright, viewport
    390×844) : le panneau de détail, positionné en `absolute` par rapport
    au widget, débordait d'environ 100 px hors du viewport sur mobile
    dès que le widget se trouvait excentré dans l'en-tête (le titre passe
    sur 3 lignes à cette largeur, ce qui déplace tout le groupe). Corrigé
    en passant `#usage-detail` en `position: fixed` avec des marges liées
    au viewport (`left/right: 8px`) sous 900 px, et en calculant sa
    position verticale (`top`) en JS à l'ouverture (`usage_tokens.js`) —
    `position: fixed` ne peut pas hériter d'un ancrage type
    `top: 100% du parent` comme `absolute`. Texte du détail passé en
    `white-space: normal` (au lieu de `nowrap`) sous 900 px pour permettre
    le retour à la ligne.
- `llm_coach.py` (`_call_claude`) : nouvelle exception
  `CreditInsuffisantError`, levée quand l'API répond HTTP 403 avec
  `error.type == "billing_error"` (distingué de `permission_error`, qui
  partage le même code HTTP mais désigne une clé sans les droits
  nécessaires — testé explicitement pour ne pas confondre les deux).
  Toutes les fonctions publiques (`get_coach_response`,
  `get_move_explanations`, `get_opening_moves`, `get_training_program`)
  la rattrapent et renvoient `error: "credit_insuffisant"` au lieu de la
  chaîne d'erreur technique brute.
- `static/board.js` (nouvelle fonction `_coachRenderCreditInsuffisant`),
  `static/exercise.js`, `static/finales.js`, `static/opening.js`,
  `static/pedagogic.js`, `static/game_analysis.js` : sur
  `error === "credit_insuffisant"`, message clair dans le chat (ou message
  inline selon le mode) avec un lien vers la Console pour recharger, au
  lieu d'une erreur technique générique.
- `llm_coach.py` (`_log_coach_call`) : nouveau champ `usage` dans chaque
  entrée de `data/logs/coach_calls.log` (tokens de cet appel précis, ou
  `null` si l'appel n'a pas abouti), en complément du compteur cumulé.
- `CONTEXTE.md` : nouvelle section documentant le fonctionnement du
  compteur et l'emplacement des données (`data/usage_tokens.json`).

## Tests réalisés

Tests faits sur l'instance réelle d'Alain (port 5000, jamais touchée) :
aucun. Tout ce qui suit tourne sur une instance de test isolée (processus
Flask/SocketIO séparé, port différent, `config.DATA_DIR` redirigé vers un
dossier `/tmp` dédié — jamais `~/ChessCoach/data`), avec l'appel HTTP à
l'API Claude (`urllib.request.urlopen`) simulé (pas de vrai appel API
fait — clé API réelle non nécessaire, `.env` non touché).

- Logique de cumul (`llm_coach.py`) testée directement : réponses d'API
  simulées avec `usage` (deux modèles différents), vérification du cumul
  par modèle et des totaux, `reset_usage` (date de départ ré-initialisée,
  compteurs à 0), distinction `billing_error` (403) vs `permission_error`
  (403, ne doit PAS lever `CreditInsuffisantError`), champ `usage` bien
  écrit dans `coach_calls.log`.
- Bout en bout via un navigateur piloté par Playwright (Chromium, contre
  l'appli Flask/SocketIO réelle tournant en local sur un port de test) :
  - Rendu desktop (1280×900) : widget affichant "Dernier appel" et
    "Total depuis le [date]", détail par modèle au survol.
  - Rendu mobile (390×844) : forme compacte (`Σ … in / … out`), détail au
    tap, **aucun débordement horizontal** (`document.documentElement.
    scrollWidth === window.innerWidth`, vérifié avant et après le bugfix
    ci-dessus).
  - Question envoyée dans le chat du coach (réponse API simulée avec
    usage) : widget mis à jour en direct avec les tokens du nouvel appel.
  - Clic sur "Remettre le compteur à zéro" avec confirmation acceptée :
    compteur à 0, nouvelle date de départ.
  - Simulation d'une réponse HTTP 403 `billing_error` : bulle dédiée dans
    le chat ("Le crédit de l'API Claude est épuisé…") avec lien
    "Recharger sur la Console", au lieu d'une erreur technique.
  - **Persistance après redémarrage** : le processus de test a été
    entièrement arrêté puis relancé (nouveau processus Python, même
    dossier de données sur disque, sans ré-injecter de données) — le
    total cumulé affiché après redémarrage correspond exactement à celui
    d'avant l'arrêt.
- `python3 -m py_compile app.py config.py llm_coach.py` : OK.

Aucun test n'a modifié `.env` ni les données réelles d'Alain
(`~/ChessCoach/data`) ; aucun `git push`.

# Changelog — Issue #53

## Chat coach : afficher le début de la nouvelle réponse, pas sa fin

- Constat : à l'arrivée de chaque bulle (message d'Alain ou réponse du
  coach), `_coachRenderBubble()` (static/board.js) faisait systématiquement
  `history.scrollTop = history.scrollHeight`, donc défilait tout en bas.
  Pour une réponse longue, Alain voyait la fin du message et devait
  remonter pour lire le début — particulièrement gênant sur GSM où
  `.coach-drawer` est plafonné à `55vh` (templates/index.html, media query
  `max-width: 900px`, issue #50).
- `static/board.js` (`_coachRenderBubble`) : comportement désormais
  différencié selon le rôle de la bulle ajoutée.
  - `role === "user"` (message envoyé par Alain) : comportement inchangé,
    défilement tout en bas (`history.scrollTop = history.scrollHeight`).
  - `role === "assistant"` (réponse du coach) : défilement calé sur le
    HAUT de la nouvelle bulle plutôt que sur le bas de la zone, via
    `history.scrollTop += bubbleRect.top - historyRect.top` (delta entre
    les rectangles `getBoundingClientRect()` de la bulle et de la zone de
    défilement). Le message d'Alain qui précède peut sortir de la zone
    (comportement accepté par la demande).
  - `getBoundingClientRect()` plutôt que `bubble.offsetTop` : `#coach-history`
    n'a pas de `position` définie en CSS, donc ses enfants n'ont pas cette
    div comme `offsetParent` — le navigateur remonte jusqu'à `<body>`, ce
    qui aurait rendu `offsetTop` complètement faux pour ce calcul (repéré
    en testant l'implémentation initiale, corrigé avant commit).
  - Cas d'une réponse courte qui tient entièrement dans la zone : le
    navigateur borne nativement `scrollTop` à sa valeur maximale
    (`scrollHeight - clientHeight`), ce qui revient exactement à l'ancien
    comportement (tout en bas) et affiche la réponse en entier sans zone
    vide — aucun cas particulier à coder.
  - S'applique aussi aux réponses du coach déclenchées hors `coachSend()`
    (bouton "Demander l'avis du coach", `coach_on_demand_response`), qui
    passent par la même fonction `_coachRenderBubble("assistant", ...)`.

## Tests réalisés

Le backend (Flask/SocketIO, appel API Claude réel) n'a pas été lancé — test
ciblé sur le comportement de défilement, via une page HTML autonome jetable
(non committée) chargeant le vrai `static/board.css` + `static/board.js` et
reproduisant la structure DOM réelle du panneau coach (`#coach-history`,
`.coach-drawer`, media query `55vh` sous 900px), servie en local et pilotée
par Playwright (Chromium headless) pour simuler l'arrivée d'une bulle
utilisateur puis d'une bulle coach (courte et longue), aux deux résolutions
demandées :

- Mobile (390 × 844, `.coach-drawer` borné à `55vh` ⇒ ~329px de hauteur
  utile pour `#coach-history`) :
  - Réponse longue (~1300 caractères) : le haut de la bulle coach arrive
    en haut de la zone (`scrollTop` == position du haut de la bulle dans
    le contenu défilable) ; le message d'Alain qui précède est sorti de la
    zone visible, conforme à la demande.
  - Réponse courte (une phrase) : `scrollTop` reste à 0 (borné par le
    navigateur), la bulle est entièrement visible sans espace vide.
- Desktop (1440 × 900, pas de contrainte `55vh`, `.coach-drawer` limité à
  `calc(100vh - 60px)`) : mêmes vérifications, mêmes résultats — début de
  réponse visible en haut pour la réponse longue, réponse courte
  entièrement visible. Rendu CSS desktop non modifié (aucune règle CSS
  touchée par ce correctif, uniquement `static/board.js`).
- Message envoyé par Alain (`role: "user"`) : vérifié inchangé aux deux
  résolutions — défilement tout en bas après ajout de sa bulle, dans les
  deux scénarios ci-dessus.

`node --check static/board.js` : syntaxe JS valide.

# Changelog — Issue #52

## Conserve la partie affichée après « Abandonner » pour pouvoir en discuter avec le coach

- Constat : dans les modes partie libre / pédagogique / ouverture / finales,
  cliquer sur « Abandonner » remettait immédiatement le plateau à la
  position de départ (`resetBoardToNeutral()`, `activeMode` remis à `null`).
  Le chat libre sollicité juste après ne recevait donc plus que la FEN de
  départ et un PGN vide — constaté en usage réel sur le GSM (journal
  `coach_calls.log` : FEN de départ, PGN vide, réponse du coach « il n'y a
  pas encore de coup joué »).
- `static/free_play.js` / `static/pedagogic.js` / `static/opening.js` /
  `static/finales.js` (`abandonFreeGame`/`abandonPedagogicGame`/
  `abandonOpeningGame`/`abandonFinaleGame`) : « Abandonner » ne réinitialise
  plus le plateau ni `activeMode` — il fige la position atteinte (nouveaux
  drapeaux `freeGameOver`/`pedagogicGameOver` déjà existant réutilisé/
  `openingGameOver`/`finaleGameOver` mis à `true`, `*Abandonne` nouveau pour
  distinguer explicitement l'abandon d'une fin par mat/pat/nulle), bloque
  les coups suivants (guards déjà en place sur `*GameOver` dans
  `onFreePlayBoardClick`/`onPedagogicBoardClick`/`onOpeningBoardClick`/
  `onFinaleBoardClick`, réutilisés tels quels) et affiche le bandeau de fin
  de partie (`showGameOverBanner`, « défaite » pour les modes à camp
  identifié, message neutre en partie libre) avec le bouton « Analyser
  cette partie » (`analyserPartieDepuisPgn`, déjà utilisé pour les fins par
  mat) — même mécanique que les autres fins de partie, pas de nouveau
  chemin de code.
- `static/board.js` (`coachBuildContext`) : l'historique des coups
  (pgn/move, déjà transmis en pédagogique/ouverture/finales depuis
  l'issue #33) est étendu au mode partie libre — c'était le seul des
  quatre modes concernés par cette issue à en être privé. Nouveau champ
  `abandonne` lu depuis `activeModeGameState()` (`static/controls.js`,
  nouvelle fonction `_activeModeAbandoned()`) ; quand vrai, le contexte
  envoyé au coach porte `partie_terminee: true` et `resultat_partie`
  explicite.
- `llm_coach.py` (`_build_context_text`) : nouveau paragraphe explicite
  dans le contexte envoyé à Claude quand `partie_terminee` est vrai —
  précise qu'Alain ne jouera plus de coup dans cette partie et instruit le
  coach de répondre à partir du PGN complet plutôt que de nier qu'un coup
  ait été joué.
- Le plateau ne redevient vierge qu'au démarrage explicite d'une nouvelle
  partie (chaque `start*Game*`, qui réinitialise les drapeaux `*GameOver`/
  `*Abandonne`) ou à un changement de mode (`ensureModeSwitchClean`,
  inchangé — appelle toujours la fonction `abandon*` du mode quitté pour
  nettoyer l'état serveur, mais celle-ci ne fait plus rien si la partie
  était déjà terminée).
- Vérification : impossible de déclencher un vrai appel API Claude depuis
  ce worktree (pas de `.env`, `ANTHROPIC_API_KEY` absente de
  l'environnement — `DATA_DIR`/`coach_calls.log` pointent d'ailleurs vers
  `~/ChessCoach/data`, hors périmètre de ce worktree). Vérifié à la place :
  (1) simulation Node (chargement réel de `controls.js`/`free_play.js`/
  `pedagogic.js`/`coachBuildContext` dans un contexte `vm`, parties jouées
  via chess.js) confirmant qu'après abandon en mode libre et en mode
  pédagogique, `coachBuildContext()` renvoie bien le PGN complet,
  `partie_terminee: true`, `resultat_partie` mentionnant l'abandon, et que
  `resetBoardToNeutral()`/coups suivants restent bloqués ; (2) appel direct
  de `llm_coach.get_coach_response()` avec `_call_claude` monkeypatché
  (aucune requête réseau réelle, conforme à RESEAU=non) confirmant que
  `_log_coach_call` écrit bien le PGN complet et `partie_terminee: true`
  dans l'entrée journalisée (le format et l'emplacement du log,
  `data/logs/coach_calls.log` sous `DATA_DIR`, sont inchangés par ce
  correctif). `python3 -m py_compile` et `node --check` OK sur tous les
  fichiers modifiés.

# Changelog — Issue #51

## Désactivation du mode debug Flask (écoute sur 0.0.0.0 depuis l'issue #49)

- Constat : `socketio.run(...)` (app.py, démarrage) passait `debug=True` en
  dur alors que l'appli écoute sur toutes les interfaces (`0.0.0.0:5000`,
  issue #49) derrière `_FiltreAccesDistant`. Le débogueur interactif
  Werkzeug (console web, protégée seulement par un code PIN) peut être servi
  avant ce filtre WSGI, donc potentiellement joignable depuis le réseau
  local ou un wifi public — inacceptable pour une appli détenant la clé API
  Claude et des données personnelles.
- `config.py` : nouvelle variable `DEBUG_DEV`, lue depuis la variable
  d'environnement `CHESSCOACH_DEBUG_DEV` (`"1"` pour l'activer), `False` par
  défaut.
- `app.py` (bloc `if __name__ == "__main__":`) :
  - `debug=config.DEBUG_DEV` et `use_reloader=config.DEBUG_DEV` au lieu de
    `debug=True` en dur — désactive aussi le rechargement automatique du
    code par défaut.
  - `host` devient conditionnel : `127.0.0.1` si `DEBUG_DEV` est actif,
    `0.0.0.0` sinon (comportement inchangé pour l'usage normal via
    Tailscale). Le débogueur ne peut donc jamais être actif en même temps
    qu'une écoute ouverte sur les autres interfaces.
  - Port 5000, `allow_unsafe_werkzeug=True` et `_FiltreAccesDistant`
    inchangés.
- `CONTEXTE.md` : section « Accès distant » mise à jour — mention explicite
  qu'après une modification du code il faut désormais relancer le coach à la
  main (plus de rechargement automatique), et documentation de
  `CHESSCOACH_DEBUG_DEV=1` pour le développement local.
- Vérifications effectuées (venv temporaire jetable dans `/tmp`, `.env` non
  touché, port 5000 libéré après coup) :
  - Par défaut : log Werkzeug `Debug mode: off`, écoute confirmée sur
    `0.0.0.0:5000`, `GET /` renvoie 200 (page normale), et une requête vers
    la ressource du débogueur
    (`/?__debugger__=yes&cmd=resource&f=debugger.js`) renvoie la page HTML
    normale de l'appli (`Content-Type: text/html`) au lieu de la ressource
    JS du débogueur — la console n'est donc plus servie du tout (le
    middleware `DebuggedApplication` n'est même pas monté).
  - Avec `CHESSCOACH_DEBUG_DEV=1` : log `Debug mode: on`, `Debugger is
    active!` + PIN affiché, rechargeur actif (`Restarting with stat`),
    écoute confirmée **uniquement** sur `127.0.0.1:5000` (absente de
    `0.0.0.0`), et la même requête de ressource renvoie bien
    `Content-Type: text/javascript` (débogueur actif comme attendu en
    développement local).
- Aucune modification du filtre d'accès distant, du port, du mécanisme
  Tailscale ni de `.env`.

# Changelog — Issue #50

## Interface adaptée au GSM (affichage vertical, déplacement des pièces au toucher)

- Constat : aucune balise viewport dans `templates/index.html` — un mobile
  rendait donc la page comme un "layout viewport" de 980px puis la réduisait
  à l'échelle (plateau minuscule, zoom nécessaire pour jouer). La mise en
  page était par ailleurs figée en colonnes fixes (620/240/420/480px) sans
  aucune adaptation aux écrans étroits.
- `templates/index.html` :
  - Ajout de `<meta name="viewport" content="width=device-width,
    initial-scale=1, maximum-scale=1, viewport-fit=cover">`.
  - Nouvelle règle `@media (max-width: 900px)` (aucun effet au-dessus de ce
    seuil, vérifié par capture d'écran diff pixel-à-pixel à 1440px —
    strictement identique avant/après) :
    - `#app` passe en colonne unique (`flex-direction: column`) ; les 4
      colonnes (`#board-column`, `#coach-column`, `#mode-tabs-column`,
      `#historique-column`) passent à `width:100%` et sont réordonnées via
      `order` : plateau, puis chat du coach, puis onglets de mode, puis
      historique des coups (secondaire sur GSM) en dernier.
    - `--bd-size` (taille du plateau, définie dans `board.css`) reçoit une
      borne supplémentaire `calc(100vw - 92px)` pour tenir compte de la
      largeur écran disponible (auparavant seulement `min(70vh, 560px)`,
      indépendant de la largeur — débordait horizontalement sur un
      téléphone en portrait).
    - `.coach-drawer` : `max-height` réduit à `55vh` (au lieu de
      `calc(100vh - 60px)`) pour garder plateau + chat visibles ensemble
      sans trop défiler, comme souhaité par Alain.
    - `.mode-tab-bar` : défilement horizontal (`overflow-x:auto;
      flex-wrap:nowrap`) plutôt que retour à la ligne, comme demandé.
    - `#review-controls` : `flex-wrap:wrap` ajouté (sans quoi la rangée de 5
      boutons Précédent/Suivant/Retourner/Meilleur coup/Extraire le FEN
      dépassait la largeur de l'écran et provoquait un défilement horizontal
      de toute la page).
    - Cibles tactiles agrandies (`button`/`.mode-tab-btn` : `min-height:
      44px`) et police des champs de saisie forcée à `16px` (empêche le
      zoom automatique au focus sur iOS Safari).
- `static/board.css` : `touch-action: manipulation` ajouté sur `.square`
  (neutralise le double-tap-zoom pendant la séquence des deux taps du
  déplacement tactile ; sans effet visuel, donc neutre pour la souris).
- **Déplacement des pièces au toucher** : déjà entièrement fonctionnel sans
  changement de code JS — les 5 modes interactifs visés (partie libre,
  pédagogique, ouverture, finales, exercices) utilisent tous le même
  gestionnaire `boardEl.onclick = on<Mode>BoardClick`, avec le même schéma
  "tap sur la pièce à déplacer puis tap sur la case d'arrivée" que demandé
  dans l'issue — un tap génère un `click` DOM standard, déjà pris en charge
  par ce code. Le point bloquant était uniquement l'absence de balise
  viewport (rendait le plateau minuscule) et le manque de mise en page
  adaptée, tous deux corrigés ci-dessus.
- Note : le mode "Éditeur de position" utilise du drag-and-drop HTML5
  (`draggable`/`ondragstart`/`ondrop`) pour la palette de pièces, non
  compatible tactile — mais ce mode n'est pas dans la liste des 5 modes visés
  par l'issue, donc hors périmètre ici (limite connue, à traiter séparément
  si besoin).
- Vérification (Playwright, Chromium headless, serveur Flask lancé avec un
  `HOME` de test isolé sous le worktree pour ne pas toucher aux données
  réelles sous `~/ChessCoach/data`) :
  - Desktop 1440px : diff pixel-à-pixel avant/après = aucune différence.
  - Bascule de mise en page vérifiée exactement au seuil : 899px → colonne
    unique, 901px → mise en page desktop (`#app` `flex-direction`).
  - Mobile 390×844 (émulation tactile, `has_touch=True`) : aucun débordement
    horizontal de la page (`scrollWidth === clientWidth === 390`), barre
    d'onglets bien scrollable horizontalement (`scrollWidth` 963px pour un
    `clientWidth` de 356px).
  - Déplacement tactile testé avec deux taps successifs (`locator.tap()`) :
    - Mode "Partie libre" : coup e2-e4 joué avec succès (case de départ
      vidée, pion visible en e4, statut passé à "Trait aux Noirs").
    - Mode "Partie pédagogique" (Blancs) : coup d2-d4 joué avec succès,
      réponse automatique de Stockfish (d7-d5) reçue et affichée.
    - Les 3 autres modes visés (ouverture, finales, exercices) partagent
      strictement le même gestionnaire de clic sur case
      (`sqEl = e.target.closest(".square")` puis
      sélection/déplacement identiques) — non exécutés en bout en bout ici
      faute de données de test (livre d'ouverture, tables Syzygy, historique
      d'erreurs, tous gitignorés et absents de l'environnement de test
      isolé), mais le mécanisme est identique à celui validé sur les deux
      modes testés.
- Limites connues :
  - Éditeur de position non adapté au tactile (drag-and-drop HTML5, hors
    périmètre de l'issue).
  - Pas de test sur un appareil physique réel — seulement émulation
    Playwright/Chromium (viewport + événements tactiles synthétiques).
  - Le zoom pincé (pinch-to-zoom) volontaire reste possible
    (`maximum-scale=1` limite mais ne bloque pas totalement selon les
    navigateurs) ; seul le double-tap-zoom accidentel est neutralisé via
    `touch-action: manipulation`, choix délibéré pour ne pas sacrifier
    l'accessibilité (zoom volontaire toujours possible pour lire un texte
    petit) — bon compromis pratique pour rester conforme aux bonnes
    pratiques mobiles actuelles.

# Changelog — Issue #49

## Accès distant via Tailscale, restreint à la machine locale et au réseau Tailscale

- Contexte : Alain veut ouvrir le coach depuis son GSM via Tailscale (déjà
  installé et connecté des deux côtés). L'appli est strictement personnelle
  (parties, mémoire du coach, clé API) et n'a aucun mot de passe : elle ne
  doit donc jamais être joignable par quelqu'un d'autre.
- `app.py` : le serveur écoute désormais sur toutes les interfaces
  (`socketio.run(app, host="0.0.0.0", port=5000, ...)`, avant : bind
  implicite à `127.0.0.1` uniquement), mais un middleware WSGI
  (`_FiltreAccesDistant`, posé devant `app.wsgi_app` — donc devant les
  routes Flask ET le handshake Socket.IO, puisque flask_socketio remplace
  lui-même `app.wsgi_app`) n'accepte que `127.0.0.1`/`::1` et la plage
  Tailscale `100.64.0.0/10` ; toute autre adresse (LAN, wifi public) reçoit
  un `403 Forbidden` explicite avant d'atteindre la moindre route.
- Chat temps réel (Socket.IO) : aucune configuration CORS explicite
  nécessaire. La vérification d'origine par défaut de python-socketio
  (`cors_allowed_origins=None`) compare l'en-tête `Origin` du navigateur au
  `Host` de la requête — elle s'aligne donc automatiquement sur l'adresse
  utilisée pour ouvrir l'appli (locale ou Tailscale), et rejette avec un
  `400 "Not an accepted origin."` toute origine tierce (vérifié par test
  manuel, cf. rapport de clôture de l'issue).
- `CONTEXTE.md` : section ajoutée expliquant l'adresse à utiliser depuis le
  GSM (`http://100.92.48.81:5000`, adresse Tailscale du ThinkPad
  thinkpadcarbon7) et le mécanisme de filtrage.
- Rien ne change côté ThinkPad : l'alias `coach` continue d'ouvrir le
  navigateur en local (127.0.0.1 reste dans la liste blanche), même port
  5000 qu'avant.
- Non touché : `.env`, clé API Claude.

# Changelog — Issue #48

## Panneau Coach trop étroit et texte trop petit

- Constat (capture d'écran d'Alain) : sur un écran classique, `#coach-column`
  (largeur fixe 320px) laissait un espace vide important à droite de la
  page (~240px sur un viewport 1920px), alors que le texte des réponses du
  coach (`#coach-history`, réponses souvent longues — analyse de partie
  complète) était rendu en 0.85rem, inconfortable à lire.
- `templates/index.html` : largeur de `#coach-column` portée de `320px` à
  `480px` (+160px, absorbe l'essentiel de l'espace vide constaté sans
  toucher aux largeurs de `#board-column` (620px), `#historique-column`
  (240px) ni `#mode-tabs-column` (420px), qui restent inchangées).
- `static/board.js`, fonction `_coachRenderBubble` : taille de police des
  bulles de réponse (utilisateur et coach) portée de `0.85rem` à `1.05rem`,
  avec `line-height:1.45` ajouté pour l'aération du texte sur les réponses
  longues.
- Vérification via navigateur headless (Playwright) : captures avant/après
  à 1920×1080 confirmant l'élargissement du panneau (320→480px, coin droit
  passant de x=1664 à x=1824, toujours dans le viewport) et
  l'agrandissement du texte des bulles (13.6px → 16.8px). Vérifié aussi à
  1440×900 : le passage à la ligne (`flex-wrap`) du panneau Coach sous les
  autres colonnes existait déjà avant la modification à cette largeur (la
  somme des largeurs fixes dépassait déjà 1440px) — seul le seuil de wrap
  se déplace légèrement, pas de régression introduite.

## Chat libre — réponse vide (bloc thinking seul, sans texte) sur claude-sonnet-5

- Cause confirmée (documentation officielle de l'API Messages) : `_call_claude`
  (`llm_coach.py`) omettait le paramètre `thinking` dans le corps de la
  requête. Sur `claude-haiku-4-5`, cela ne change rien (Haiku ne raisonne
  jamais). Sur `claude-sonnet-5` (modèle d'Alain via
  `CHESSCOACH_LLM_MODEL`), omettre `thinking` active le raisonnement
  adaptatif *par défaut* — contrairement aux modèles Opus 4.7/4.8, où
  l'omettre désactive la réflexion. Ce raisonnement consomme une partie du
  budget `max_tokens` (2048) avant même de commencer à écrire la réponse ;
  sur une question simple, il pouvait consommer la totalité du budget et
  s'arrêter (`stop_reason: "max_tokens"`) après un unique bloc
  `{"type": "thinking", "thinking": ""}`, sans aucun bloc `text` — l'erreur
  observée par Alain (`"Aucun bloc de type 'text' dans la réponse Claude"`),
  levée par le parsing robuste ajouté en issue #46 (qui reste nécessaire et
  n'a pas été modifié).
- `llm_coach.py`, fonction `_call_claude` :
  - Ajout de `"thinking": {"type": "disabled"}` dans le corps de la requête
    — désactive explicitement le raisonnement adaptatif plutôt que de
    simplement lui laisser plus de budget, ce qui élimine la classe de
    problème à la racine (option demandée en priorité par l'issue). Un
    commentaire de coach aux échecs n'a pas besoin d'exposer un raisonnement
    séparé de la réponse ; Haiku, utilisé jusqu'à l'issue #44 pour le même
    usage, ne raisonnait jamais et convenait déjà — pas de régression de
    qualité attendue par rapport au comportement déjà validé.
  - `max_tokens` porté de 2048 à 4096 en complément (deuxième option
    demandée par l'issue), pour laisser une marge large même si un futur
    changement de modèle ou d'API réintroduisait un raisonnement consommant
    une partie du budget.
- Commentaires mis à jour en conséquence (rationale du budget de tokens et
  de la recherche défensive du bloc `text`, qui reste utile même avec
  `thinking` désactivé — au cas où l'API renverrait tout de même un bloc
  `thinking` vide).
- Hors périmètre respecté : aucune modification du parsing du bloc `text`
  ajouté par l'issue #46.
- Vérification : `python3 -m py_compile llm_coach.py` → OK. Simulation
  locale de `urllib.request.urlopen` (aucun appel réseau réel) confirmant
  que le corps de requête envoyé contient bien `"thinking": {"type":
  "disabled"}` et `"max_tokens": 4096`, et que la réponse texte est
  correctement extraite même en présence d'un bloc `thinking` vide en tête
  de `content`.
- **Vérification navigateur headless avec appel API réel demandée par
  l'issue : non effectuée.** Aucune `ANTHROPIC_API_KEY` n'est accessible
  dans le périmètre strict de ce worktree (`/home/alain/chesscoach-issue47`)
  — la clé réelle vit dans `~/ChessCoach/.env`, hors périmètre, et je n'ai
  pas le droit d'y accéder même si la tâche le demande explicitement (même
  limitation déjà rencontrée et documentée en issue #46). Alain devra
  confirmer par un échange réel dans l'interface, avec `claude-sonnet-5`
  configuré, qu'une réponse textuelle réelle est bien reçue en chat libre.

# Changelog — Issue #46

## Chat libre — KeyError('text') lors du parsing de la réponse API, apparu après le passage à Sonnet

- Diagnostic : impossible de retrouver l'entrée réelle dans
  `data/logs/coach_calls.log` — ce fichier vit sous `DATA_DIR`
  (`~/ChessCoach/data/logs/`), hors du périmètre strict de ce worktree
  (`/home/alain/chesscoach-issue46`). Le diagnostic s'appuie donc sur la
  documentation officielle de l'API Messages (comportement confirmé,
  non supposé) : sur `claude-sonnet-5`, quand le paramètre `thinking` est
  omis de la requête, le raisonnement adaptatif s'exécute *par défaut* et
  produit un bloc `{"type": "thinking", ...}` dans la liste `content` de la
  réponse — potentiellement avant le bloc `{"type": "text", ...}`. Sur
  Haiku, qui ne pense jamais, `content[0]` est toujours le bloc texte. La
  requête construite dans `_call_claude` (`llm_coach.py`) n'a jamais fixé le
  paramètre `thinking`, donc ce comportement s'active silencieusement dès
  que `CHESSCOACH_LLM_MODEL=claude-sonnet-5` (config d'Alain).
- `llm_coach.py`, fonction `_call_claude` (ligne ~637) : remplace
  `return data["content"][0]["text"]` (suppose une position fixe) par une
  itération sur `data["content"]` qui retourne le premier bloc dont
  `"type" == "text"`, quelle que soit sa position dans la liste. Lève une
  `ValueError` explicite si aucun bloc texte n'est trouvé (au lieu d'un
  `KeyError`/`IndexError` opaque).
- Hors périmètre respecté : aucune modification du paramètre `thinking`
  côté requête — uniquement le parsing de la réponse, comme demandé.
- Vérification fonctionnelle (aucune `ANTHROPIC_API_KEY` disponible dans
  l'environnement de cette session, et le module `anthropic` n'est pas
  installé — un vrai appel réseau à `claude-sonnet-5` n'a donc pas pu être
  effectué depuis ce worktree) : simulation de `urllib.request.urlopen` avec
  les deux formes de réponse possibles — (1) bloc `text` seul en position 0
  (forme Haiku historique) et (2) bloc `thinking` en position 0 suivi du
  bloc `text` en position 1 (forme Sonnet 5 à l'origine du bug) — confirme
  que `_call_claude` retourne le bon texte dans les deux cas, alors que
  l'ancien code levait `KeyError('text')` sur le cas (2). Alain devra
  confirmer par un échange réel dans l'interface avec `claude-sonnet-5`
  configuré.

# Changelog — Issue #45

## Chat libre — timeout de lecture sur l'appel API Claude

- `llm_coach.py` : le timeout HTTP de l'appel à l'API Claude dans
  `_call_claude` était codé en dur à 15s (`urllib.request.urlopen(req,
  timeout=15)`), devenu insuffisant avec un contexte volumineux
  systématiquement transmis (PGN complet + mémoire de progression complète :
  patterns_erreurs, repertoire_ouvertures, objectifs_courants) et depuis le
  passage de `CHESSCOACH_LLM_MODEL` à claude-sonnet-5. Provoquait "the read
  operation timed out" même sur une question triviale ("dis bonjour") en
  mode Bibliothèque/Revue avec une partie longue chargée. Porté à 90s.
- Vérifié qu'aucun autre timeout intermédiaire ne coupe la requête plus tôt :
  `SocketIO(app)` (app.py) n'a pas de `ping_timeout`/`ping_interval` custom,
  et le serveur Flask dev (`socketio.run`) n'a pas de timeout de requête
  configuré. Le seul timeout applicable au chemin `_call_claude` est bien
  celui de la ligne modifiée.
- Vérification fonctionnelle (sans clé API réelle disponible dans
  l'environnement d'exécution) : simulation d'une latence de 20s côté API
  via mock de `urllib.request.urlopen` — confirme qu'avec le nouveau
  timeout=90 la requête réussit (20s < 90s), alors qu'avec l'ancien
  timeout=15 la même latence aurait levé `TimeoutError`. Une vérification
  E2E via navigateur headless avec un vrai appel API n'a pas pu être
  réalisée : aucune `ANTHROPIC_API_KEY` n'était présente dans
  l'environnement de cette session, et `DATA_DIR` (`~/ChessCoach/data`,
  PGN réels + `coach_memory.json`) se situe hors du périmètre strict de ce
  worktree (`/home/alain/chesscoach-issue45`).

