# Changelog — Issue #102

## Bulle temporaire de fin de théorie (mobile et grand écran) et historique des coups affiché deux fois sur grand écran

Retours d'Alain après tests GSM et grand écran de l'issue #100 : le message
« Fin de la théorie » reste cantonné au chat du coach, qu'Alain ne consulte
pas en cours de partie sur téléphone ; sur grand écran (~1826px), le panneau
« Historique des coups » apparaît deux fois (panneau de gauche + second
titre sous les onglets Coach/Lignes/Analyse/Coups), et ces quatre onglets
s'affichaient tous empilés simultanément au lieu d'un seul à la fois.

### 1. Composant de bulle temporaire (toast) réutilisable

Nouveau composant générique, un seul nœud DOM pour toute l'appli
(`#board-toast` dans `#board-file-column`, `templates/index.html`) piloté
par `showBoardToast(text)` (`static/board.js`) :

- **Durée** : `CC_TOAST_DURATION_MS = 4000` (4s), réglable en un seul
  endroit ; fondu de 400ms (`CC_TOAST_FADE_MS`, doit rester cohérent avec la
  transition CSS `.board-toast`).
- **Style** : fond neutre foncé semi-transparent
  (`color-mix(... --cc-neutral-800 82% ...)`), texte blanc, police
  `--cc-font-body` (Figtree), coins arrondis `--cc-radius-md`, ombre
  `--cc-shadow-lg` — jamais `--cc-accent` (terracotta), réservé au cliquable
  d'après la palette de l'appli, puisque rien n'y est cliquable.
- **Positionnement** : ancrée dans `#board-file-column` (pas
  `#board-wrapper`, qui a `overflow:hidden` et aurait clippé la bulle sur
  les plus petits plateaux mobiles — mesuré ~174px de côté à 360×640 en
  mode jeu), centrée par `transform: translate(-50%,-50%)`, largeur fixée
  `min(280px, 88vw)` plutôt que liée à la largeur du plateau : sur les
  plus petits plateaux, la bulle déborde donc légèrement des bords du
  plateau (jamais de l'écran) — nécessaire pour tenir sur deux lignes au
  plus avec un texte même court.
- **N'interfère jamais avec le jeu** : `position:absolute` (aucun impact
  sur le flux de page ni la taille du plateau), `pointer-events:none` à
  tous les niveaux (conteneur + bulle) — un tap sur une case sous la bulle
  sélectionne bien la pièce, vérifié par un test tactile direct.
- **Accessibilité** : `role="status" aria-live="polite"` sur le conteneur
  — annonce discrète, jamais "assertive" (n'interromprait pas une lecture
  de lecteur d'écran en cours).
- **Anti-doublon** : un nouvel appel remplace le texte et relance le
  minuteur plutôt que d'empiler plusieurs bulles ; la responsabilité de ne
  pas re-déclencher pour le même événement métier reste à l'appelant (ex.
  `openingTheoryEndAnnounced`, déjà existant depuis l'issue #100).

### 2. Fin de théorie (mode Ouvertures)

`_announceOpeningTheoryEnd()` (`static/opening.js`) appelle désormais aussi
`showBoardToast(OPENING_THEORY_END_MESSAGE_COURT)`, texte raccourci
dédié : *« Fin de la théorie : la partie continue contre le moteur. »*
(56 caractères, tient sur deux lignes à 360 et 390px de large, vérifié).
Le message complet existant (`OPENING_THEORY_END_MESSAGE`) reste **inchangé**
dans le chat du coach et la ligne d'état `#opening-status` — aucune
suppression, uniquement un ajout.

**Autres messages d'annonce candidats à une bulle (listés pour décision
d'Alain, non modifiés) :**
- `opening.js` : « Ouverture "X" : 1.e4 e5 2.Cf3 ... À vous de jouer. »
  (chargement d'une ouverture, `coach-bubble-announce`).
- `finales.js` : « Finale "X" chargée. [description] » (chargement d'une
  finale).
- `finales.js` : « Démonstration "X" chargée — Stockfish joue les deux
  camps... » (lancement d'une démonstration).
- Résultat de partie (mat/pat/nulle/abandon) : actuellement un bandeau
  persistant dédié (`#game-over-banner`, `showGameOverBanner`, `board.js`)
  directement sur le plateau — déjà visible sans consulter le coach, donc
  priorité probablement plus faible, mais cité par Alain comme exemple
  dans la demande initiale.

### 3. Historique des coups en double sur grand écran

**Constat** : `#game-tabs-column` (onglets Coach/Lignes/Analyse/Coups,
introduits par l'issue #70 pour mobile) n'avait **aucune** règle CSS de
base (hors media query) fixant son `display` — seules deux règles
existaient, toutes deux à l'intérieur de `@media (max-width: 900px)`
(`display:none` par défaut, `display:block` via `body.mobile-game-active`).
Sur grand écran, où cette media query ne s'applique jamais, la colonne
gardait donc le `display:block` par défaut du navigateur et s'affichait en
colonne supplémentaire entre le plateau et `#mode-tabs-column`. Pire : la
règle `.game-tab-panel { display:none } / .active { display:block }` qui
assure qu'un seul onglet est visible à la fois est **elle aussi** scopée à
cette même media query — sur grand écran, les 4 panneaux
(`#game-tab-panel-coach/-lignes/-analyse/-coups`) s'affichaient donc tous
en même temps, empilés verticalement (d'où le texte « Aucune ligne pour
l'instant... » de l'onglet Lignes suivi du second titre « Historique des
coups » de l'onglet Coups, observé par Alain).

**Choix retenu** : masquer `#game-tabs-column` par une règle de base
(`display: none;`, hors media query, posée juste avant `#mode-tabs-column`
dans `templates/index.html`), seulement réaffichée par la règle mobile
existante (`body.mobile-game-active #game-tabs-column { display: block; ...
}`, inchangée). Sur grand écran, le panneau de gauche
(`#historique-column`) redevient ainsi la **seule** référence de
l'historique, comme avant les issues mobiles #69/#70. Les autres onglets
restent utilisables via leurs emplacements d'origine, jamais déplacés sur
grand écran (`isGameUiActive()` y est toujours faux, `GAME_ALWAYS_RELOCATE`
ne s'exécute jamais) : Coach et Lignes via `#coach-column` (toujours
visible, `#game-coach-lines` y est déjà présent par défaut), Analyse via
l'onglet « Bibliothèque / Revue PGN » de `#mode-tabs-column`
(`#game-analysis-panel` y est déjà présent par défaut). Rien n'est perdu,
rien n'est dupliqué. Comportement mobile strictement inchangé (vérifié :
`#game-tabs-column` reste `display:block` en mode jeu mobile, un seul
onglet `.active` à la fois, `#historique-column` reste masqué).

### Fichiers modifiés

- `static/board.css` — composant `.board-toast`/`.board-toast-bubble`,
  `#board-file-column { position: relative; }`.
- `static/board.js` — `showBoardToast()`, `CC_TOAST_DURATION_MS`,
  `CC_TOAST_FADE_MS`.
- `static/opening.js` — `OPENING_THEORY_END_MESSAGE_COURT`, appel à
  `showBoardToast()` dans `_announceOpeningTheoryEnd()`.
- `templates/index.html` — markup `#board-toast`/`#board-toast-bubble`
  (dans `#board-file-column`), règle de base `#game-tabs-column { display:
  none; }`.

### Tests

Voir le rapport de clôture de l'issue pour le détail des tests (émulation
tactile 390×750/360×640, grand écran 1826×900, captures d'écran) et les
limites rencontrées (pas d'exécution de bout en bout via le vrai moteur
Stockfish dans cet environnement — composant et branchement vérifiés par un
rendu statique fidèle du vrai gabarit/CSS/JS + traçage direct du code
serveur).
