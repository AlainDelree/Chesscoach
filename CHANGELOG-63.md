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
