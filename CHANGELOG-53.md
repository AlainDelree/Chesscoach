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
