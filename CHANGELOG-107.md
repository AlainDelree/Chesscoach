# Changelog — Issue #107

## Cercle d'attente au centre de l'échiquier pendant le coach/l'analyse

Retour d'Alain après test GSM de l'issue #105 : sur téléphone il regarde le
plateau, pas le chat, et manquait donc l'indicateur "Le coach réfléchit..."
tant qu'il ne faisait pas défiler la page. Ajout d'un cercle animé centré sur
le plateau, branché sur le même mécanisme d'attente central (aucun second
minuteur).

### Implémentation

- `coachSpinnerBegin()` (`static/board.js`) : nouveau contrôleur `{finish()}`
  symétrique de `_coachThinkingStart`/`coachWaitBegin` (issue #105) — montre
  `#board-spinner` après `CC_SPINNER_SHOW_DELAY_MS` (400 ms, pour ne pas
  clignoter sur une réponse rapide), le cache immédiatement à `finish()`.
- Appelé depuis `_coachThinkingStart()` (seul point d'accroche, déjà partagé
  par `coachWaitBegin` ET par l'appel direct d'`exercise.js` pour le verdict
  Stockfish) : couvre donc automatiquement coach_ask, commentaire sur
  demande (chat libre/pédagogique/ouverture/finales), programme
  d'entraînement, ET l'attente du verdict Stockfish en exercice — sans
  dupliquer aucune logique d'attente.
- `_ccSpinnerForceHide()` appelé depuis `coachNewSegment()` et `coachClear()`
  (déjà déclenchés au démarrage de chaque nouvelle partie/exercice et à tout
  changement d'onglet/mode réel, `switchModeTab`) : le cercle ne reste
  jamais affiché après un changement de mode/nouvelle partie/nouvel exercice,
  même si une requête réseau était encore en cours.
- Coexistence avec la bulle temporaire (`#board-toast`, fin de théorie,
  issue #102) : si le toast est affiché au moment où le cercle devrait
  apparaître, `coachSpinnerBegin()` sonde (150 ms) et attend sa disparition
  plutôt que de superposer les deux — jamais bloqué pour autant, `finish()`
  annule ce sondage à tout moment.

### Apparence (`static/board.css`, classes `.board-spinner*`)

- Même conteneur que `#board-toast` (`#board-file-column`, frère de
  `#board-wrapper`) : pas dans l'élément `overflow:hidden`, pour ne jamais
  être rogné sur les plus petits plateaux mobiles (360/390px).
- Fond circulaire semi-transparent assombri (`color-mix` sur
  `--cc-neutral-800` à 68%, même famille que `.board-toast-bubble` à 82%)
  derrière un anneau clair — jamais de terracotta (`--cc-accent`, réservé au
  cliquable). 48px de diamètre (fourchette demandée 44-56px), lisible sur
  cases claires et foncées (vérifié par capture d'écran).
- `prefers-reduced-motion: reduce` : remplace la rotation continue par un
  anneau fixe (plus de segment plus clair suggérant un sens de rotation) qui
  clignote lentement (opacité, 1.6s).
- Texte alternatif masqué visuellement ("Le coach réfléchit"),
  `role="status"` + `aria-live="polite"` (même convention que `#board-toast`)
  pour une annonce discrète aux lecteurs d'écran.
- `pointer-events: none` à tous les niveaux : aucun toucher/clic intercepté,
  ne déplace rien, ne réduit jamais le plateau (`position:absolute`, aucun
  impact sur le flux de page ni la taille du plateau).

### Tests (Playwright, navigateur réel piloté, émulation tactile+viewport)

Pas d'appel API réel possible dans ce test (pas de backend lancé — DATA_DIR
pointe hors du périmètre du worktree, `~/ChessCoach/data`) : tests faits sur
un harnais HTML isolé chargeant les vrais `board.css`/`board.js` et appelant
directement `coachSpinnerBegin()`/`showBoardToast()`, ce qui couvre fidèlement
le CSS et la logique de minuterie/sondage réellement livrés.

- 390×750, 360×640 (tactile) et 1280×900 : cercle visible, centré, 48px,
  lisible sur cases claires/foncées (captures d'écran).
- Pas affiché avant 400 ms (testé à 150 ms) ; affiché après (testé à 550 ms).
- Réponse rapide (`finish()` à 150 ms, avant le délai) : jamais affiché à
  l'écran — aucun clignotement.
- `finish()` cache immédiatement, à tout moment.
- Toast affiché en même temps que le début d'une attente : le cercle reste
  caché tant que le toast est affiché, apparaît dès sa disparition (jamais
  superposés).
- Tap/clic au centre du plateau pendant que le cercle est affiché : reçu par
  la case du plateau dessous (`pointer-events:none` vérifié via
  `elementFromPoint`/clic réel), jamais par le cercle.
- `prefers-reduced-motion: reduce` : animation effectivement remplacée
  (`animation-name` = `cc-spinner-blink`), anneau uniforme (pas de segment
  plus clair) vérifié par comparaison des couleurs de bordure.
- Taille du plateau identique avant/pendant/après l'affichage du cercle
  (300px dans les trois cas, aucun reflow).

### Limites

- Pas d'appel API Claude réel exercé (voir ci-dessus — hors périmètre du
  worktree). Le branchement passe exclusivement par le point d'accroche
  unique `_coachThinkingStart()`, déjà vérifié fonctionnellement par les
  tests de l'issue #105 ; ce qui est nouveau ici (apparition/disparition du
  cercle, délai, sondage anti-superposition, pointer-events, préférence
  système) est couvert par les tests Playwright ci-dessus sur un harnais
  fidèle aux fichiers réels, pas par un appel serveur bout en bout.
- Le cas inverse (toast déclenché pendant que le cercle est déjà affiché)
  n'a pas de garde symétrique dans `showBoardToast()` — non nécessaire : le
  seul appelant actuel du toast (`_announceOpeningTheoryEnd`, fin de
  théorie) s'exécute toujours avant le `coachWaitBegin()` du commentaire
  automatique associé, jamais après.
