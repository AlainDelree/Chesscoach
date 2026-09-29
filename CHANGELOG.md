# Changelog — Issue #47

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

