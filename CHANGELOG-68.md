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
