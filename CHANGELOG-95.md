# Changelog — Issue #95

## Mobile : corrections 4 après tests complets

Retours d'Alain après une série de tests complets sur GSM (Chrome sous
Android, ~390x750) des issues #81 à #93. Huit points corrigés.

### 1. Fenêtre « Nouvel exercice » : phase grisée pour « Position précise »

- Côté serveur (`app.py`, `on_exercise_new`/`_on_exercise_new_position_precise`),
  la position précise primait déjà : dès que la source choisie est
  « Position précise », le champ « phase » est totalement ignoré (forcé à
  `"toutes"`), seul le FEN collé compte — ce comportement était correct mais
  invisible côté interface, qui affichait en même temps « Ouverture » (phase)
  et le FEN, laissant croire à tort que l'exercice porterait sur l'ouverture.
- `static/exercise.js` (`_exerciseUpdateSourceDependentUI`) : le sélecteur de
  phase (desktop, `#exercise-phase-select`) est désormais désactivé et grisé
  (`disabled` + classe `.exercise-field-disabled`, `static/board.css`) quand
  la source est « Position précise », avec une infobulle explicative. Côté
  feuille mobile, le bloc entier « Phase de la partie » (`#exercise-phase-section`,
  nouveau conteneur dans `templates/index.html`) est grisé de la même façon.
- La catégorie Lichess était déjà correctement masquée pour toute source
  autre que « Problèmes Lichess » (`showCategorie = source === "lichess"`,
  comportement préexistant, pas de régression constatée) — vérifié, rien à
  corriger sur ce point précis.

### 2. Zone de saisie du coach agrandie

- `templates/index.html` : `#coach-input` passe de `rows="3"` à `rows="6"`
  (hauteur doublée), seul textarea partagé par tous les modes (partie libre,
  pédagogique, ouverture, finales, exercice) et toutes les tailles d'écran —
  un seul changement suffit. Vérifié que `#coach-column` et `#board-column`
  restent deux colonnes indépendantes (desktop) et que le plateau mobile vit
  dans `#board-sticky-wrap`, hors du flux de la zone à onglets : aucun effet
  sur la taille du plateau.

### 3. Bouton « Commenter la partie » (mode pédagogique)

- `static/board.js` (`showGameOverBanner`/`_showMobileGameOverBar`) : nouveau
  paramètre `onCommenter`, ajoute un bouton « Commenter la partie » (desktop)
  / « Commenter » (mobile, libellé raccourci — voir ci-dessous) à côté de
  « Analyser cette partie »/« Nouvelle partie », visible seulement si
  l'appelant le fournit (pedagogic.js uniquement — comportement inchangé pour
  free_play.js/opening.js/finales.js, qui ne le fournissent pas).
- `static/pedagogic.js` : nouvelle fonction `commenterPartiePedagogique()`,
  même effet que « Demander l'avis du coach » (`askCoachOnDemand` sur la
  position finale) mais accessible après la fin de partie (où
  `askPedagogicCoach()` se bloque volontairement) ; câblée aux deux points où
  `showGameOverBanner` est appelé (fin normale/mat/nulle et abandon).
- Case « Commenter chaque coup » retirée du mode pédagogique seulement
  (`MODE_CAPS.pedagogic.hasComment` passé à `false`, `static/controls.js` ;
  `pedagogicCommenterChaqueCoup()` renvoie désormais toujours `false` plutôt
  que de lire une case partagée qui pourrait rester cochée depuis un autre
  mode) — **gardée dans les modes Ouverture et Finales**, qui la conservent
  (`hasComment: true` inchangé), comme demandé.
- Bug annexe découvert et corrigé pendant les tests : avec jusqu'à trois
  boutons sur la barre compacte mobile (`#mobile-game-over-bar`,
  `flex-wrap: nowrap` par choix volontaire, issue #77), les libellés complets
  débordaient horizontalement de la page à 360-390px de large (repéré avec
  Playwright, 6 à 36px de débordement selon la largeur). Corrigé par
  `flex: 0 1 auto` + `min-width:0` + ellipse sur les boutons de cette barre
  (`templates/index.html`) et des libellés raccourcis sur mobile uniquement
  (« Analyser », « Commenter » — le bandeau desktop garde le texte complet).

### 4. Liste déroulante des ouvertures

- `opening_book.py` : nouvelle liste statique `KNOWN_OPENINGS` (46 ouvertures
  classiques largement reconnues) et `get_known_openings()` — voir
  limitations ci-dessous.
- `app.py` : nouvelle route socket `opening_list`/`opening_list_response`,
  calquée sur `finale_list`/`finale_list_response` (`on_finale_list`).
- `templates/index.html` : le champ texte libre `#opening-name-input` est
  remplacé par `<select id="opening-select">`, même composant visuel que
  `#finale-select` (mode Finales). Le choix du camp reste séparé (deux
  boutons « Jouer les Blancs/Noirs ») plutôt qu'un démarrage immédiat au
  choix comme pour les finales — une ouverture nécessite encore de préciser
  la couleur, contrairement à une finale.
- `static/opening.js` : `populateOpeningSelect()`/`_openingSelectSetValue()`
  (pendant de `populateFinaleSelect` dans `finales.js`), liste récupérée au
  chargement de la page (`socket.emit("opening_list", {})`). Les suggestions
  rapides existantes (issue #27, coups pondérés du livre Polyglot)
  sélectionnent désormais l'entrée correspondante dans la liste (ajoutée à la
  volée si absente de `KNOWN_OPENINGS`) au lieu de remplir un champ texte.
  `startOpeningGame()` lit `#opening-select.value` au lieu de l'ancien input.

### 5. Plateau non réduit au démarrage (ouvertures/finales)

- Cause confirmée : `_coachRenderBubble` (`static/board.js`) déclenchait déjà
  `_mobileGameOnCoachMessage()` (réduction automatique si l'onglet Coach
  déborde) pour **toute** bulle du coach autre que l'annonce « je joue ... »
  (`coach-bubble-auto-move`) — y compris les messages d'annonce envoyés par
  l'application elle-même au chargement d'une ouverture (« Ouverture "X" :
  ... À vous de jouer. ») ou d'une finale (« Finale "X" chargée. ... »),
  jamais une vraie demande d'Alain.
- Nouvelle classe `coach-bubble-announce` appliquée à ces trois messages
  d'annonce (`opening.js` au démarrage, `finales.js` au chargement d'une
  finale et d'une démonstration) et exclue, comme `coach-bubble-auto-move`,
  du déclenchement de la réduction automatique (`static/board.js`,
  `_coachRenderBubble`). Le débordement d'un onglet reste par ailleurs
  toujours détecté indépendamment (`ResizeObserver`/`_autoCompactForOverflow`,
  `mobile_game.js`, inchangé) pour tout contenu qui déborde réellement,
  quelle qu'en soit la cause — donc une vraie réponse longue du coach réduit
  toujours le plateau comme avant.
- **Règle avant** : toute bulle assistant hors « je joue ... » réduisait le
  plateau si l'onglet actif débordait, y compris une annonce de démarrage.
  **Règle après** : seules les réponses à une demande d'Alain (question,
  « Demander l'avis du coach », commentaire après un coup type « Commenter
  chaque coup ») ou un débordement d'onglet (quelle que soit sa cause) la
  déclenchent ; un message d'annonce/instruction de l'application ne le fait
  plus jamais.
- Vérifié avec Playwright (voir section Tests) que le bug se reproduisait
  réellement sans le correctif (le contenu de l'onglet Coach débordait bel et
  bien après le chargement d'une finale) et ne se reproduit plus avec.
- Non touché (hors périmètre, aucune annonce de ce type trouvée) : partie
  libre, pédagogique et exercice ne génèrent pas de bulle d'annonce du coach
  à leur démarrage (le message de l'exercice passe par un élément dédié,
  pas par le chat) — comportement déjà correct, vérifié par lecture du code.

### 6. Rafraîchissement involontaire (pull-to-refresh)

- `templates/index.html` : `overscroll-behavior-y: contain` sur `html` et
  `body`, pur CSS (aucun gestionnaire tactile ajouté) — bloque le geste natif
  Chrome/Android de rafraîchissement par glissement au sommet de page sans
  toucher au défilement normal.
- Appliqué aussi à `.coach-drawer`/`.coach-history` (`static/board.css`) et
  `.phase-sheet-scroll` (feuilles du bas, `templates/index.html`) pour éviter
  tout chaînage de défilement résiduel vers la page depuis ces conteneurs
  internes — aucun effet secondaire constaté sur le défilement des menus/
  feuilles du bas (Playwright, feuille « Nouvel exercice » testée).

### 7. Nouvelle partie propre (vidage de la conversation)

- `static/free_play.js` et `static/pedagogic.js` : le démarrage d'une
  nouvelle partie appelle désormais `coachClear()` (vidage complet de
  l'affichage ET de l'historique envoyé à l'API, comme `exercise.js` le fait
  déjà pour un nouvel exercice) au lieu de `coachNewSegment("Nouvelle
  partie")` (simple trait séparateur, conversation précédente laissée
  visible sans rien indiquer qu'elle datait d'avant). `gameCoachLinesReset()`
  est appelé explicitement en complément (coachClear ne le fait pas,
  contrairement à coachNewSegment) pour conserver la remise à zéro du
  tableau « Lignes du coach ».
- Le trait « Nouvelle partie » ne s'affiche donc plus à ce point de rupture
  (conséquence directe du vidage, `coachClear()` ne pose jamais de
  séparateur).
- Limité volontairement à partie libre et pédagogique (les deux modes
  explicitement cités par l'issue et son plan de tests) : le mode Ouverture
  et le mode Finales gardent `coachNewSegment("Nouvelle partie")` à leur
  démarrage, non demandé explicitement et hors plan de tests de cette issue.

### 8. `lire_signalements.py` : question précédente affichée

- Nouvelle fonction `_ligne_coup_ou_question(entree, journal)` : pour une
  réponse liée à un coup (`entree["move"]` renseigné), ligne inchangée
  (« Coup concerné : ... ») ; pour une réponse à une question libre (pas de
  coup), affiche désormais la dernière question d'Alain retrouvée dans
  l'entrée de `coach_calls.log` reliée par `log_id`
  (`lire_journal_coach._derniere_question`, déjà utilisée par
  `lire_journal_coach.py`) au lieu de l'ancien « Coup concerné : (aucun) » ;
  « Question posée par Alain : (aucune question) » si même la question est
  introuvable (réponse non journalisée, archive purgée, ou réponse qui ne
  suit réellement aucune question).
- Appliqué à la fois à `_texte_pret_a_coller` (sortie `--dernier`, texte prêt
  à coller) et à `_afficher_resume` (listing par défaut), qui n'affichait
  auparavant aucune ligne « Coup » en l'absence de coup.

## Tests effectués

Application lancée dans ce worktree avec `HOME` pointé vers un répertoire
temporaire interne au worktree (`.manual_test_home`, supprimé après les
tests) — **aucune donnée réelle d'Alain sous `~/ChessCoach/data` n'a été lue
ni modifiée**, conformément au périmètre strict. Stockfish système
(`/usr/games/stockfish`) utilisé normalement. **Aucune clé API Claude n'est
configurée dans ce worktree (pas de `.env`)** : les appels réels au coach
(contenu des commentaires, reconnaissance du nom d'une ouverture par Claude)
n'ont pas pu être vérifiés de bout en bout — seul le câblage a été vérifié
(la requête part bien, le serveur répond proprement `no_api_key`, exactement
comme le bouton préexistant « Demander l'avis du coach »).

Automatisé avec Playwright (Chromium), émulation tactile, 390x750 et 360x640
(GSM) et 1400x900 (grand écran) :

- Point 1 : sélection « Position précise » → phase grisée et désactivée
  (mobile et desktop) ; retour à « Mes erreurs » → dégrisée. Catégorie
  Lichess déjà masquée hors source Lichess, confirmé.
- Point 2 : `#coach-input.rows === 6` sur les trois tailles ; hauteur réelle
  mesurée à 138px sur grand écran (contre ~70px avant, rows=3).
- Point 3 : case « Commenter chaque coup » absente en mode pédagogique
  (`display:none`) ; bouton « Commenter »/« Commenter la partie » visible
  après abandon (une des trois fins — mat/nulle non testées explicitement
  par manque de temps, mais empruntent exactement le même code
  `showGameOverBanner`) sur mobile et desktop ; clic réel déclenchant bien
  `coach_comment_on_demand` côté serveur ; aucun débordement horizontal à
  360px ni 390px avec les trois boutons.
- Point 4 : `#opening-select` peuplé de 46 options au chargement.
- Point 5 : plateau non réduit juste après le chargement d'une finale sans
  aucun défilement (`board-compact` absent) alors que le contenu de l'onglet
  Coach débordait réellement (`_activeTabContentOverflows() === true`,
  confirmé) ; contre-épreuve : en simulant l'ancien comportement (retrait de
  la classe `coach-bubble-announce`), le plateau se réduit bien — le test
  n'est donc pas trivialement vrai. Même mécanisme partagé par
  `opening.js` (code identique, non testé en direct faute du livre Polyglot
  dans l'environnement de test isolé).
- Point 6 : `overscroll-behavior-y: contain` confirmé en style calculé sur
  `html`/`body`.
- Point 7 : deux parties pédagogiques à la suite → `#coach-empty` revient
  visible et aucun séparateur `.coach-separator` au démarrage de la seconde.
- Point 8 : vérifié par lecture/relecture de code et `py_compile` (pas de
  signalement réel disponible dans l'environnement de test isolé pour un
  test de bout en bout — nécessiterait un signalement réellement posé via
  l'interface, hors budget de cette session).

Captures d'écran prises (non committées, dans `/tmp`, hors dépôt) :
fenêtre Nouvel exercice avec phase grisée, liste des ouvertures, fin de
partie pédagogique (mobile et desktop) avec les trois boutons sans
débordement.

## Limites

- La liste des ouvertures (point 4) est une liste statique maintenue dans
  `opening_book.py` (46 entrées), pas une base de données exhaustive — à
  étendre directement dans le code si une ouverture manque. Contrairement
  aux finales, aucun mécanisme « enregistrer cette ouverture » n'a été
  ajouté (non demandé par l'issue).
- Points 3/4/5 (contenu réel des réponses du coach, reconnaissance d'un nom
  d'ouverture par Claude) non vérifiables de bout en bout : aucune clé API
  Claude configurée dans ce worktree de test.
- Mode Ouverture non testé en conditions réelles de jeu (le livre Polyglot
  `data/books/gm2001.bin` n'a pas été copié dans l'environnement de test
  isolé, par respect du périmètre strict qui interdit de lire
  `~/ChessCoach/data` même en lecture seule) — la correction du point 5 y
  repose sur le même code partagé que le mode Finales, testé avec succès.
- Point 8 non testé de bout en bout (pas de signalement réel disponible dans
  l'environnement isolé) — vérifié par lecture de code et compilation.
