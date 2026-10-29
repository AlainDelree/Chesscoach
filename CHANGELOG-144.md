# Changelog — Issue #144

## Issue #144 — Page club : accès externe protégé (jeton, entrée dédiée, clé API dédiée)

But : permettre à Alain d'ouvrir `/club` à un membre du club via un lien
public Tailscale Funnel, sans exposer le reste du coach (qui tourne sur le
port 5000) à Internet.

**`app_club.py`** (nouveau) : second point d'entrée HTTP, sur sa PROPRE
instance Flask (`creer_app_club`), qui ne connaît QUE `/club`,
`/api/club/avis`, `/api/club/eval`, `/api/club/jugement` (`add_url_rule`,
vues réutilisées depuis `app.py` sans duplication, `static_folder=None`) —
toute autre URL y reçoit le 404 standard de Flask « par construction »,
jamais par détection de l'origine de la requête. `app.py`/port 5000
restent strictement inchangés (alias `coach` d'Alain inaffecté).

Jeton obligatoire (`CLUB_JETON` du `.env`) vérifié par un `before_request`
sur CETTE entrée (page comprise), comparé en temps constant
(`hmac.compare_digest`) ; absent ou faux → `abort(404)`, identique à une
route inexistante (aucune indication de la vraie raison). `CLUB_JETON`
absente ou vide → `creer_app_club` lève `RuntimeError`, l'entrée refuse de
démarrer (jamais d'accès ouvert par défaut). Le jeton, transmis dans le
lien (`?t=...`), est repris par `static/club.html` (`location.search`) et
renvoyé dans l'en-tête `X-Club-Jeton` de chaque appel aux 3 points d'accès
— le visiteur ne le ressaisit jamais, et sa valeur n'apparaît plus dans
aucune URL après le chargement initial. Journal d'accès de Werkzeug
désactivé sur ce process (`logging.getLogger("werkzeug").setLevel(ERROR)`)
pour ne jamais écrire le jeton (présent dans la ligne de requête initiale
vers `/club`) dans un journal.

Clé Anthropic dédiée (`CLUB_ANTHROPIC_API_KEY` du `.env`) : absente ou vide
→ même refus de démarrage, JAMAIS de repli sur `config.LLM_API_KEY` (la
clé principale). Côté `app.py` : nouveau `_club_llm_api_key` (`None` par
défaut) et `_club_get_llm_api_key()`, utilisée par `api_club_avis` à la
place de `config.LLM_API_KEY` en dur — sur le port 5000 (app.py lancé
seul), cette variable reste `None` et le comportement est identique à
avant. `creer_app_club` la réassigne à `CLUB_ANTHROPIC_API_KEY` avant de
servir la moindre requête.

Mode debug : `club.config["DEBUG"]`/`["TESTING"]` forcés à `False`,
`app_club.run(..., debug=False)` — indépendant de `CHESSCOACH_DEBUG_DEV`
(jamais lu par `app_club.py`).

Limites existantes conservées à l'identique (mêmes fonctions/compteurs de
`app.py`, vues réutilisées telles quelles) : 40 avis/jour, 2 appels
simultanés, `mode_origine="club"`. Journal minimal des accès refusés
(`logger.warning`, compteur cumulé depuis le démarrage du process, aucune
donnée sensible) pour qu'Alain voie si le lien est sondé.

**`static/club.html`** : lit le jeton depuis `location.search` (`JETON`)
et l'ajoute à l'en-tête `X-Club-Jeton` de chaque appel `fetch` (fonction
`api`) — seul changement apporté à cette page.

**Documentation** : `docs/contexte/page_club.md` complété (nouvelle
section « Accès externe protégé »), paragraphe « Page « club » » de
`CONTEXTE.md` mis à jour (référence à `app_club.py`/`CLUB_JETON`/
`CLUB_ANTHROPIC_API_KEY`) sans empiler de section séparée.

**Tests** (`test_issue144_club_acces_externe.py`, nouveau, 14 tests, 14
réussis, 0 ignoré, via `app_club.creer_app_club(...).test_client()`,
aucun processus serveur réel lancé) : jeton absent/faux/valide (page et
API, en-tête et paramètre d'URL), 404 identique à une route inexistante,
404 par construction sur toute route hors club MÊME avec jeton valide
(y compris `/static/club.html`, qui serait servie par la route statique
implicite de Flask sans `static_folder=None`), refus de construire sans
`CLUB_JETON`/`CLUB_ANTHROPIC_API_KEY` (valeurs vides ou variables
d'environnement absentes), clé API dédiée jamais remplacée par la clé
principale, port 5000 sans override toujours sur la clé principale, mode
debug désactivé. Non-régression : `test_issue142_page_club.py` rejoué
séparément, 15 tests toujours réussis (le changement dans `api_club_avis`
est un simple indirection qui renvoie `config.LLM_API_KEY` par défaut).

**Point d'attention (bug préexistant, hors périmètre, à signaler)** :
`python3 -m unittest <fichier_de_test_qui_importe_app.py>` termine bien
tous les tests (journal « OK » écrit), mais le PROCESS ne se ferme pas
tout seul — `atexit.register(engine_manager.quit)` dans `app.py` s'exécute
trop tard dans la séquence d'arrêt de Python (qui attend la fin des
threads non-démons des moteurs Stockfish AVANT de lancer les callbacks
`atexit`), ce qui bloque indéfiniment tant que `engine_manager.quit()` n'a
pas déjà été appelé explicitement AVANT la fin naturelle du script.
Reproduit aussi avec `test_issue142_page_club.py` (préexistant, pas
introduit par cette issue). Pour `test_issue144_club_acces_externe.py`,
`tearDownClass` appelle désormais `engine_manager.quit()` explicitement
avant la fin du process — ce fichier se termine proprement (confirmé :
aucun processus Python ni Stockfish laissé en suspens, `rc=0`). Une
future issue pourrait appliquer le même correctif à `app.py` lui-même
(ex. déplacer l'arrêt des moteurs dans un signal handler plutôt que
`atexit`) ou aux autres fichiers de test existants — hors périmètre ici
(aucun fichier non lié à l'issue #144 n'a été modifié pour ce point).

**Lancement de l'entrée club** (jamais exécuté par CCL) :
```
CLUB_JETON=... CLUB_ANTHROPIC_API_KEY=... python3 app_club.py
```
(port 5001 par défaut, `CLUB_PORT` pour le changer ; valeurs normalement
exportées depuis `.env` par le shell, comme pour `app.py`). Commande
Tailscale Funnel à lancer par Alain lui-même (jamais par CCL) :
```
tailscale funnel 5001
```
