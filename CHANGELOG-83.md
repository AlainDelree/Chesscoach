# Changelog — Issue #83

## Exercice : choix de la catégorie des problèmes Lichess, « Position précise » (FEN) et énoncé visible à côté du plateau

Suite des issues #78 (source « Problèmes Lichess ») et #63/#76 (feuille
« Nouvel exercice » mobile) : `lichess_puzzles.py`, `app.py`,
`static/exercise.js`, `templates/index.html`.

### 1. Choix de la catégorie (`lichess_puzzles.py`, `app.py`)

- `lichess_puzzles.tirer_probleme` accepte un nouveau paramètre
  `categorie_forcee` (une des 16 clés de `CATEGORIES`, ou `None` pour le
  tirage pondéré automatique d'origine, inchangé) et retourne désormais un
  triplet `(entree, categorie, avertissement)` au lieu d'une paire.
  **Combinaison phase/catégorie** : en automatique, la phase filtre d'abord
  l'ensemble des catégories compatibles, puis une catégorie est tirée parmi
  elles (pondérée par niveau) — comportement d'origine inchangé. Catégorie
  imposée : c'est l'inverse — on filtre d'abord par catégorie, puis on tente
  d'appliquer la phase ; si l'intersection catégorie+phase est vide, la
  **phase est ignorée pour ce tirage** et un avertissement d'une phrase est
  renvoyé (`"Aucun problème de catégorie « X » pour cette phase de partie :
  la phase a été ignorée pour ce tirage."`) plutôt que d'échouer le tirage
  ou de rester silencieux sur l'écart. La tranche de note reste choisie
  automatiquement d'après le niveau d'Alain dans la catégorie (imposée ou
  tirée) — seule la catégorie elle-même devient un choix explicite.
- `app.py` : `on_exercise_new` lit `data.categorie` (`"automatique"` par
  défaut) et le transmet à `_on_exercise_new_lichess`, qui ignore
  silencieusement une clé non reconnue (repli sur automatique). L'événement
  `exercise_position` transporte deux champs en plus pour la source
  `"lichess"` : `categorie_demandee` (le choix explicite, pour qu'"Exercice
  suivant" le reproduise) et `avertissement` (la phrase ci-dessus, ou
  `None`).
- `index()` passe au gabarit `lichess_categories_triees` (les 16 catégories
  triées par libellé français) pour générer les `<option>`/pastilles sans
  dupliquer la liste côté client.

### 2. Énoncé visible à côté du plateau (`templates/index.html`, `static/exercise.js`)

- Nouvel élément `#exercise-statement-line`, placé **dans
  `#board-sticky-wrap`** (juste sous le plateau/matériel, avant la barre de
  lecture des lignes du coach) — ce conteneur reste collé en haut de l'écran
  sur mobile (issue #69) et suit le plateau sur grand écran, contrairement à
  l'ancienne ligne `#exercise-lichess-info` (dans l'onglet Exercice) qui,
  elle, finissait **sous le panneau du coach** une fois celui-ci rempli de
  messages (constat d'Alain, GSM 390×750) : hors écran, invisible sans
  défiler. `#exercise-lichess-info` est retirée (remplacée).
- `_exerciseUpdateStatementLine()` (exercise.js) construit une ligne courte :
  camp au trait + `· Problème <note> · <catégorie> · niveau <N>` (source
  Lichess), `· Mes erreurs · <phase>` (source historique), ou `· Position
  libre` (position précise) ; l'avertissement phase/catégorie (point 1),
  rare, est ajouté en fin de ligne. Appelée à chaque tirage et après chaque
  verdict (le niveau affiché reflète alors le résultat).
- `#exercise-status` (ligne d'état transitoire, juste en dessous) ne répète
  plus le camp/la source — simplifié en « Chargement d'une position... » /
  « Fais ton coup. » / messages d'erreur, pour ne pas faire doublon avec
  l'énoncé désormais toujours visible.
- Mesuré à 390×750 et 360×640 (captures ci-dessous) : l'énoncé reste dans le
  viewport sans défiler, sur une seule ligne (~23px de haut), pour les trois
  sources.

### 3. Position précise (`app.py`, `static/exercise.js`, `templates/index.html`)

- Nouvelle source `"position_precise"` : `_valider_fen_position_precise`
  (app.py) valide un FEN collé par Alain — lisible par python-chess, légal
  (mêmes messages que l'éditeur de position, `_EDITOR_STATUS_MESSAGES`), et
  camp au trait **ni mat ni pat** (sans quoi aucun coup n'est possible).
  `_on_exercise_new_position_precise` émet `exercise_position` (succès) ou
  `exercise_error` (`"fen_invalide"` + message prêt à afficher) — **sans
  aucun appel à `exercise_history`** (ni `enregistrer_proposition` au
  tirage, ni `enregistrer_resultat` au verdict dans `on_exercise_answer`,
  gardé par le drapeau `is_position_precise`) : une position collée à la
  main ne fausse donc ni le niveau d'Alain ni l'historique des erreurs, et
  ne peut pas non plus être enregistrée dans « Mes erreurs » (ce mécanisme
  n'existe que pour la source `mes_erreurs`, jamais invoqué ici).
- Le reste du jugement (verdict Stockfish, menace adverse, idées détectées,
  listes de pièces, lignes du coach) réutilise **exactement** le même calcul
  que la source « Mes erreurs » — `coup_reel` est naturellement vide (pas de
  "coup réellement joué" ni de comparaison avec une "partie d'origine"),
  avec un texte d'introduction adapté pour le coach.
- Interface : nouvelle option "Position précise" dans le sélecteur de
  source (desktop + feuille mobile), avec un champ FEN qui apparaît
  seulement pour cette source. Le champ vide est bloqué côté client (la
  feuille mobile reste ouverte avec un message inline) ; toute autre erreur
  (FEN illisible, position illégale, déjà mat/pat) est validée côté serveur
  et affichée dans `#exercise-status`. L'énoncé indique "Position libre".

### Fenêtre « Nouvel exercice » (desktop + feuille mobile)

- Sélecteur `#exercise-categorie-select` (desktop) / pastilles
  `#exercise-categorie-options` (mobile) : "Automatique" + 16 catégories
  triées par libellé français, visibles uniquement pour la source
  "Problèmes Lichess" (`_exerciseUpdateSourceDependentUI`). Dernier choix
  retenu **par appareil** via `localStorage`
  (`chesscoach-exercise-categorie`, même pattern que
  `GAME_BOARD_SIZE_STORAGE_KEY` de `mobile_game.js`) — appliqué au
  chargement de la page et après rechargement (testé).
- La feuille mobile (`#exercise-phase-sheet`) a été restructurée en
  flex-colonne : le contenu (phase/source/catégorie/FEN) défile dans un
  conteneur interne (`#exercise-phase-sheet-scroll`), et le bouton "Lancer
  l'exercice" devient un **pied de feuille fixe**, toujours visible, jamais
  recouvert ni à atteindre en défilant — testé à 360×640 avec les 17
  pastilles de catégorie affichées (dépasse 80vh sans ce changement). Un
  premier essai avec `position: sticky` sur le seul bouton a été rejeté : il
  flottait par-dessus le haut du contenu tant que la feuille n'était pas
  défilée jusqu'en bas (visible sur capture, overlap avec la pastille
  "Automatique").

## Tests

Vrai Stockfish 16 (`/usr/games/stockfish`) et vrai appel API (clé
`ANTHROPIC_API_KEY` du `.env`, modèle Sonnet configuré), via une seconde
instance de l'appli lancée sur le port 5099 (jamais sur le port 5000 où
tourne l'instance réelle d'Alain, laissée intacte) :

- **Backend (script Python direct)** : `tirer_probleme` avec catégorie
  forcée "fork" (automatique de phase) → catégorie bien "fork" et thème
  vérifié sur le problème tiré ; catégorie "pawnEndgame" + phase "opening"
  (incompatible exprès) → avertissement renvoyé, phase ignorée ; automatique
  → comportement inchangé (`avertissement=None`). `_valider_fen_position_precise` :
  FEN vide, FEN illisible, échiquier vide (illégal), FEN de mat (Fool's
  mate) → chacun son message d'erreur ; FEN de l'issue (position donnée,
  `1r1r2k1/4Qpbp/2Bp1n2/3Pp2q/2P1P1p1/2N3PP/PP3PK1/R1B2R2 w - - 0 23`) → validée.
- **Intégration Socket.IO (client `python-socketio`)** : les 6 scénarios
  ci-dessus rejoués via `exercise_new`/`exercise_answer` sur le vrai
  serveur ; pour la position de l'issue, un coup de remplissage (a2a3) a
  déclenché un vrai appel à l'API Claude (Sonnet) — **la menace adverse
  transmise au coach mentionne bien "le pion noir de g4 capture un pion de
  Blancs (Alain) en h3 [...] échec" (gxh3+)**, les listes de pièces sont
  transmises (`pieces_depart_texte` non vide), et la réponse réelle du coach
  cite explicitement **"gxh3+"** et le mat annoncé par Stockfish en suivant
  (+296 puis mentions de Qf3 etc.) — confirmant que le coach reçoit bien la
  menace et les pièces demandées par l'énoncé de tâche.
- **UI (Playwright, émulation tactile)** à 390×750, 360×640 et desktop
  1440×900 : ouverture de la feuille, choix de chaque élément testé
  (catégorie "Fourchette", "Mat"), vérification que le problème tiré
  appartient à la catégorie choisie (via l'énoncé affiché) ; "Automatique"
  conservé comme valeur par défaut ; choix de catégorie mémorisé après
  rechargement de page (`page.reload()`, revérifié) ; feuille sans
  débordement du bouton "Lancer l'exercice" (toujours dans le viewport,
  avant ET après défilement du contenu) ; énoncé visible sans défiler pour
  un exercice Lichess, un exercice "Mes erreurs" et une position précise ;
  FEN vide bloqué avec message inline (feuille reste ouverte) ; FEN valide
  lancé avec succès, "Position libre" affiché. Captures dans
  `/tmp/shots_issue83/` (environnement de l'agent, non committées).
- **Historique/statistiques** : fichiers personnels
  `exercice_historique.json`/`niveau_exercices_lichess.json` sauvegardés
  avant les tests, comparés après (hash MD5) — confirmé qu'aucune entrée
  "position_precise" n'apparaît dans l'historique et que le niveau Lichess
  n'a pas bougé pour ce test ; fichiers restaurés dans leur état exact
  d'avant-test à la fin (les quelques tirages "mes erreurs"/"lichess" faits
  pendant les tests UI, qui enregistrent légitimement une proposition,
  étaient inclus dans cette restauration pour ne rien laisser dans les
  données réelles d'Alain).
- **Non-régression** : tirage "mes erreurs" (`exercise_new` sans catégorie)
  inchangé ; `_on_exercise_answer_lichess` non touché par cette issue
  (aucune ligne modifiée dans cette fonction).
- `python3 -m py_compile app.py lichess_puzzles.py exercise_history.py
  config.py` et `node --check static/exercise.js` : OK.

## Limites

- Le pied de feuille fixe (bouton "Lancer l'exercice") a nécessité de
  restructurer `.phase-sheet` en flex-colonne avec un conteneur de défilement
  interne (`#exercise-phase-sheet-scroll`) — changement de structure plus
  large que le minimum pour une seule issue, mais nécessaire pour éviter le
  chevauchement visuel constaté avec `position: sticky`.
- Pas de test manuel sur un vrai GSM (émulation Playwright tactile
  390×750/360×640 uniquement, comme les issues précédentes sur ce mode).
- L'avertissement phase/catégorie n'a été exercé qu'avec une seule
  combinaison délibérément incompatible (pawnEndgame + ouverture) ; les 16×3
  combinaisons n'ont pas toutes été parcourues.
