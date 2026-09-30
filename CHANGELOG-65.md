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
