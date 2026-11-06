# Changelog — Issue #149

## Issue #149 — Les routes du club ne doivent exister que sur l'entrée club, pas sur l'application principale

But : une revue d'authentification en lecture seule avait montré que la
page club et ses trois points d'accès (`/club`, `/api/club/avis`,
`/api/club/eval`, `/api/club/jugement`) restaient enregistrés sur
l'application principale (`app.py`/port 5000, via des décorateurs
`@app.route`), EN PLUS de l'entrée dédiée (`app_club.py`). Conséquence :
tant que `app.py` tournait sur son port habituel, ces quatre routes y
répondaient SANS jeton, avec la clé Anthropic principale (pas la clé
dédiée du club), en consommant le quota quotidien du club, et avec un
second compteur de concurrence (`_club_appels_en_cours`) indépendant de
celui de `app_club.py` — l'invariant « le club n'est accessible qu'avec le
jeton » n'était donc pas respecté sur ce chemin (l'exposition à Internet
via Funnel, derrière `app_club.py`, n'était pas concernée : seul `app.py`,
limité au réseau Tailscale et à la machine par `_FiltreAccesDistant`,
l'était).

**`app.py`** : retrait des quatre décorateurs `@app.route("/club")`/
`@app.route("/api/club/avis", methods=["POST"])`/
`@app.route("/api/club/eval", methods=["POST"])`/
`@app.route("/api/club/jugement", methods=["POST"])`. Les fonctions
`club_page`/`api_club_avis`/`api_club_eval`/`api_club_jugement` elles-mêmes
sont INCHANGÉES (même logique : quota quotidien, limite de concurrence,
refus du contenu non JSON, mode d'origine `"club"`) — elles ne sont plus
enregistrées que par `app_club.creer_app_club` (`add_url_rule`, déjà
réutilisées sans duplication depuis l'issue #144), qui continue de les
servir à l'identique derrière son jeton obligatoire. `app.py`/port 5000
répond désormais le 404 standard de Flask sur ces quatre adresses, comme
n'importe quelle route inexistante — confirmé par test direct (voir
« Tests » ci-dessous) sur un process lancé à part : les quatre routes
renvoient 404, l'entrée club continue de répondre 200 avec un jeton valide.

**Conséquence sur les limites** : `CLUB_MAX_APPELS_SIMULTANES` (toujours 2,
inchangé) ne correspond plus qu'à UN SEUL compteur en mémoire
(`app_club.py` étant désormais le seul processus à servir ces routes),
alors qu'avant cette issue deux processus (`app.py` et `app_club.py`)
pouvaient chacun en consommer 2 indépendamment (jusqu'à 4 appels
simultanés réels, tous processus confondus). `CLUB_MAX_AVIS_PAR_JOUR` (40)
était déjà un compteur persisté sur disque, partagé par construction entre
processus — non affecté par ce changement au-delà du fait qu'un seul
processus le consomme désormais.

**Tests modifiés** :
- `test_issue142_page_club.py` : atteint désormais les 4 routes via
  `app_club.creer_app_club(club_jeton=..., club_api_key=...).test_client()`
  (nouvelle classe utilitaire `_ClientAvecJeton`, qui injecte l'en-tête
  `X-Club-Jeton` à chaque appel) au lieu de `app.app.test_client()`
  directement — ces routes n'existant plus sur `app.py`, un appel direct y
  recevrait 404. Les événements Socket.IO (`exercise_answer`, etc.)
  restent testés directement sur `app.py`/`self.socketio_client`, non
  concernés par cette issue. `setUpClass` importe désormais `app_club`
  (plutôt que `app` directement), comme `test_issue144_club_acces_externe.py`/
  `test_issue146_club_securite_reseau.py`. Toujours 15 tests, toujours 15
  réussis — aucune vérification affaiblie (mêmes assertions de statut/corps
  de réponse, même position de test, même simulation de l'API Claude au
  niveau réseau).
- `test_issue146_club_securite_reseau.py` : `_entrees()` ne retourne plus
  que l'entrée club (`port_5001`, jeton de test) — `app.py`/port 5000 ne
  servant plus ces routes, il n'y avait plus de second cas à boucler.
  Nouveau test `test_routes_club_404_sur_application_principale` (404 sur
  les 4 adresses côté `app.py`, aucune mutation d'état). Renommage des 3
  tests de non-régression (`..._sur_les_deux_entrees` →
  `..._sur_lentree_club`) pour refléter qu'une seule entrée subsiste — sans
  changement de logique de vérification.
- `test_issue144_club_acces_externe.py` : en-tête de fichier corrigé (ne
  mentionnait plus que `test_issue142_page_club.py` utilisait
  `app.app.test_client()`, ce qui n'est plus vrai depuis cette issue) et
  complété avec les fichiers de test additionnels à ne jamais exécuter dans
  le même process. Comportement et assertions de ce fichier inchangés.

**Tests ajoutés** (`test_issue149_club_routes_app_principale.py`, nouveau,
12 tests, 12 réussis, 0 ignoré) :
- 404 standard sur les 4 adresses côté `app.py`/port 5000 (page et 3
  points d'accès), identique octet pour octet à une route réellement
  inexistante.
- Accès normal (200) aux mêmes 4 adresses côté entrée club
  (`app_club.creer_app_club(...)`, jeton de test), et confirmation que
  cette entrée continue de refuser les requêtes sans jeton.
- Non-régression du reste de l'application principale : route `/`
  toujours servie (200), événement Socket.IO `usage_get` toujours suivi
  de `usage_data` (inchangé).

**Fin propre des tests** (point 4 de l'issue) : `tearDownClass` de
`test_issue142_page_club.py`/`test_issue146_club_securite_reseau.py`/
`test_issue149_club_routes_app_principale.py` arrête explicitement
`engine_manager` avant la fin du process (même précaution que
`test_issue144_club_acces_externe.py`, issue #144). Point additionnel
propre à `test_issue142_page_club.py` : son test
`test_z_compteur_persiste_apres_rechargement_du_module` appelle
`importlib.reload(app)`, qui réassigne `app.engine_manager` à une NOUVELLE
instance — sans action, l'ANCIENNE instance (son propre processus
Stockfish) restait orpheline, jamais arrêtée ni par `tearDownClass` (qui
ne quitte que l'engine_manager COURANT) ni par l'`atexit` de `app.py`
(bloqué indéfiniment par les threads non-démons du moteur orphelin tant
que `.quit()` n'a pas déjà été appelé) : confirmé en reproduisant le
blocage avant correctif (processus Python + 2 processus Stockfish
orphelins) puis en vérifiant sa disparition après (capture explicite de
l'ancien `engine_manager` juste avant le `reload`, `.quit()` juste après).
Les 4 fichiers de test de la page club se lancent chacun séparément
(`python3 -m unittest <fichier>`), confirmé par exécution individuelle de
chacun : `test_issue142_page_club` (15 tests, OK, 12.2s), 
`test_issue144_club_acces_externe` (14 tests, OK, 0.8s),
`test_issue146_club_securite_reseau` (12 tests, OK, 4.6s),
`test_issue149_club_routes_app_principale` (12 tests, OK, 5.1s) — aucun
processus Python ni Stockfish laissé en suspens après chacun (vérifié par
`ps aux` juste après la fin de chaque run).

**Documentation** : `CONTEXTE.md` (paragraphe « Page « club » ») et
`docs/contexte/page_club.md` mis à jour — ces quatre routes n'existent plus
que sur l'entrée club, même pour un essai personnel d'Alain ; un seul
compteur de concurrence subsiste (au lieu de deux compteurs indépendants
par processus avant cette issue) ; les passages qui décrivaient ces routes
comme « partagées » entre `app.py` et `app_club.py`, ou l'entrée club comme
un « second » point d'entrée purement externe, ont été corrigés plutôt que
laissés tels quels.

**Hors périmètre, non modifié** : coach, prompts, format des avis,
vérificateur, autres constats de la revue d'authentification (limites de
fréquence des événements SocketIO, états globaux sans verrou, validation
de champs libres), `.env`, `configs/*.conf`.
