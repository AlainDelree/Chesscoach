# Changelog — Issue #146

## Issue #146 — Sécurité du serveur club : liaison locale par défaut et refus des requêtes POST qui ne sont pas du JSON

But : un audit automatique a relevé que `app_club.py` liait son serveur à
toutes les interfaces sans que Funnel (qui n'atteint ce serveur que par
l'adresse locale, port 5001) en ait besoin, et que les 3 routes POST du
club lisaient leur corps avec une lecture tolérante du JSON — protection
reposant sur le comportement des navigateurs, pas sur un refus explicite
du serveur.

**Liaison réseau de `app_club.py`** : nouvelle fonction
`_club_host_par_defaut()` — `127.0.0.1` par défaut, `0.0.0.0` seulement si
`CLUB_OUVRIR_RESEAU=1` (toute autre valeur garde la liaison locale).
`app.py`/port 5000 restent inchangés (liaison large nécessaire à l'accès
depuis le téléphone via Tailscale, derrière `_FiltreAccesDistant`) :
exception correspondante déclarée par identifiant de règle (`SEC-013`,
raison + date) dans `.audit.json`, sans rien y déclarer d'autre.

**Refus explicite des requêtes non JSON** (`app.py`) : nouvelle fonction
`_club_lire_json_requis()`, appelée en tout premier dans `api_club_avis`,
`api_club_eval` et `api_club_jugement` (routes partagées par `app.py` et
`app_club.py`) — remplace `request.get_json(silent=True) or {}` par un
refus explicite AVANT tout calcul Stockfish, appel IA, consommation de la
limite quotidienne ou écriture dans le journal des jugements : 415 si le
`Content-Type` n'est pas JSON, 400 si le corps est vide, illisible, ou si
le JSON lu n'est pas un objet. Les requêtes JSON valides sont inchangées ;
`static/club.html` envoyait déjà `Content-Type: application/json` pour ses
3 appels, aucune modification de cette page.

**Vérification des routes GET** : seules deux routes `@app.route` GET
existent dans `app.py` (`/` et `/club`), ni l'une ni l'autre ne modifie
d'état. Le changement de modèle LLM (qui écrit `config.LLM_MODEL_CHOICE_PATH`)
passe par l'événement SocketIO `set_llm_model`, pas par une route GET —
aucune route GET modifiante trouvée.

**Tests** (`test_issue146_club_securite_reseau.py`) : liaison locale par
défaut et variable d'ouverture (sans lancer de vrai serveur — la fonction
de décision est testée directement), refus 415/400 des 3 routes sur les
deux entrées (Content-Type non JSON, corps vide, JSON illisible, JSON non
objet), absence d'appel IA et de mutation d'état (compteur quotidien,
journal des jugements) pour toute requête refusée, priorité du filtre de
jeton de `app_club.py` sur le refus JSON, non-régression des requêtes
valides sur les 3 routes et les 2 entrées. Arrêt explicite des moteurs
Stockfish en fin de classe de test. `test_issue142_page_club.py` (15 tests)
et `test_issue144_club_acces_externe.py` (14 tests) rejoués sans
régression.

**Documentation** : section « Accès externe protégé » de
`docs/contexte/page_club.md` et paragraphe « Page club » de `CONTEXTE.md`
mis à jour (liaison locale par défaut, `CLUB_OUVRIR_RESEAU`, refus des
requêtes non JSON, renvoi vers l'exception `SEC-013`).

**Hors périmètre respecté** : aucune modification du coach, des prompts,
du format des avis, du vérificateur, ni de `static/club.html` (son
en-tête `Content-Type: application/json` existant pour les 3 appels reste
accepté, rien à ajuster). Aucune écriture dans `.env` ni `configs/*.conf`.
Aucune valeur sensible dans le code, la documentation, les tests ou ce
changelog.
