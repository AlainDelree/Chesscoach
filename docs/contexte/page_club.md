# Page « club » et points d'accès HTTP (issue #142, étape 2/4, suite #141)

But : montrer à quelqu'un du club, sur son propre téléphone via Tailscale,
l'avis du coach sur SON coup dans une position donnée, sans toucher au mode
Exercice d'Alain ni mélanger ces avis avec les siens. L'affichage (plateau,
barre d'évaluation, boutons de vue, jugements) est l'objet de l'étape #4 ;
cette issue ne fournit que le serveur.

## Routes

- `GET /club` — sert `static/club.html` tel quel (`app.send_static_file`,
  jamais de gabarit Jinja). Fichier minimal pour l'instant (« Page club : en
  construction »), remplacé à l'étape #4. Aucun code d'accès (décision
  d'Alain : usage uniquement depuis son téléphone sur le réseau Tailscale,
  cf. `syzygy_tailscale`) ; aucun changement de `app.run`/d'interface
  d'écoute.
- `POST /api/club/avis` — `{"fen": str, "coup": str (SAN ou UCI),
  "camp": "blancs"|"noirs" (optionnel, par défaut le camp au trait)}`. Se
  comporte EXACTEMENT comme `on_exercise_answer` pour la source
  `"position_precise"` (aucun coup de l'époque) : même calcul Stockfish
  (`_evaluate_move_for_coach`), même contexte
  (`app._construire_contexte_coup_exercice`, cf. `contexte_coach_exercice` —
  réutilisée sans aucune duplication), même prompt système/addendum
  d'exercice, même vérificateur, même convention de signe Lichess. Seul
  `llm_coach.get_coach_response` est appelé — jamais `get_mistral_response`,
  quelle que soit `config.MISTRAL_API_KEY` (Alain a mis Mistral en pause).
  Réponse JSON : `text`, `avis_sections`, `avis_format_conforme`,
  `avis_format_version`, `verdict_qualite_officiel`, `verdict_delta_cp`,
  `meilleur_coup`, `eval_before_cp`, `eval_after_cp`, `fiabilite` (dont
  `alertes`), `log_id`, `fen`, `camp_alain`, `coup_propose`.
- `POST /api/club/eval` — `{"fen": str}`. Évaluation Stockfish seule, SANS
  aucun appel IA, via `engine_manager` déjà lancé (jamais un nouveau
  processus par requête) : `eval_blancs_cp`/`eval_blancs_mat` (convention de
  Lichess) et `meilleurs_coups` (jusqu'à 3, mêmes champs de signe).
- `POST /api/club/jugement` — `{"log_id": str, "jugement":
  "accord"|"desaccord"|"partiel", "etiquettes": [str, ...] (optionnel),
  "remarque": str (optionnel)}`. Enregistre une ligne JSON dans
  `config.CLUB_JUGEMENTS_LOG_PATH` — jamais dans `coach_ratings.jsonl`
  (réservé aux notes d'Alain sur la comparaison Claude/Mistral).

Validation commune à `/api/club/avis` et `/api/club/eval`, avant tout calcul
Stockfish ou appel IA : FEN syntaxiquement et sémantiquement valide
(`_valider_fen_position_precise`, même fonction et mêmes messages que
l'éditeur de position du mode Exercice), coup légal et non ambigu
(`_club_parser_coup`, détection automatique SAN/UCI). Une requête invalide ne
consomme jamais la limite quotidienne ni les emplacements de concurrence.
Aucune clé d'API ni information de configuration n'apparaît dans une
réponse.

## Limite d'appels au coach

- `app.CLUB_MAX_AVIS_PAR_JOUR` (40) : au-delà, `/api/club/avis` répond 429
  (`erreur: "limite_quotidienne_atteinte"`) SANS appeler l'API. Compteur
  `{"date": "AAAA-MM-JJ", "count": int}` persisté sur disque
  (`config.CLUB_AVIS_COMPTEUR_PATH`, sous `DATA_DIR`, donc gitignoré) —
  survit à un redémarrage du serveur ; remis à zéro dès que la date du jour
  (heure locale, `time.strftime("%Y-%m-%d")`) diffère de celle enregistrée.
- `app.CLUB_MAX_APPELS_SIMULTANES` (2) : au-delà, `/api/club/avis` répond
  503 (`erreur: "occupe"`) SANS appeler l'API. Compteur en mémoire
  (`_club_appels_en_cours`), remis à zéro à chaque redémarrage (pas besoin de
  persistance : la concurrence ne survit pas à un redémarrage par nature).

## Journal

Chaque avis est journalisé par `llm_coach._log_coach_call` comme n'importe
quel appel coach, avec `context["mode_origine"] = "club"` (au lieu de
`"exercice"`) et `context["via_club"] = True`. `scripts/controle_avis.py` ne
retient que `mode_origine == "exercice"` : les avis « club » en sont donc
exclus par construction, et n'apparaissent jamais dans les notes d'Alain
(`coach_ratings.jsonl`, écrites séparément par un point d'accès distinct, cf.
ci-dessus pour les jugements « club »).

## Sélection des exercices (`scripts/selection_club.py`, issue #143)

Script autonome (aucune route, aucun appel IA, aucun réseau) qui choisit,
parmi `data/erreurs_detectees.json` (même fichier et même fonction de
lecture — reproduite localement, cf. docstring du script — que le mode
Exercice), les positions à présenter à la page « club » (étape 4, à venir) :
un mélange de positions ÉVIDENTES (un seul bon coup nettement meilleur) et
DISCUTABLES (plusieurs coups presque équivalents), autant de Blancs que de
Noirs que possible.

Pour chaque candidat, les trois meilleurs coups de Stockfish (multi-lignes,
profondeur `DEPTH_EXERCICE_TEMPS_REEL` — celle du mode Exercice, cf.
`api_club_eval` ci-dessus) sont comparés du point de vue du camp qui a le
trait dans la position de départ. Les scores de mat sont plafonnés à
±`PLAFOND_CP` (1000), le même plafond que la classification officielle
Lichess (issue #125, `engine_stockfish.cp_to_win_probability`).

Catégories (constantes nommées dans le script, modifiables en ligne de
commande — `--help`) :
- « évident » : écart 1er/2e coup >= `SEUIL_EVIDENT_CP` (200).
- « discutable » : écart 1er/2e coup <= `SEUIL_DISCUTABLE_CP` (40) ET
  évaluation de la position dans [-`BORNE_POSITION_INDECISE_CP`,
  +`BORNE_POSITION_INDECISE_CP`] (300) — sinon la position est déjà décidée,
  l'écart faible n'étant alors pas une nuance intéressante.
- exclues des deux : mat forcé annoncé en <= `MAT_MAX_COUPS_EXCLUS` (3)
  coups, position invalide ou partie déjà terminée, doublon de FEN, moins de
  deux coups légaux.

Sélection par défaut : 3 évidentes + 9 discutables (`--n-evidents`/
`--n-discutables`), équilibre Blancs/Noirs en best-effort, mélange des
phases si le champ `phase` existe dans l'entrée, au plus une position par
partie (`collection_id:game_index`) toutes catégories confondues. Jamais de
complément par une position hors critère : une pénurie est signalée dans le
résumé terminal et dans le JSON de sortie (`resume.evidents`/
`resume.discutables`, champs `demande`/`trouve`).

Un seul processus Stockfish est ouvert pour toute l'exécution (jamais un
par position), fermé dans un bloc `finally` (erreur ou interruption
comprise), avec une limite de temps globale configurable
(`--timeout-global`, 1800s par défaut). Déterministe : tri avec départage
explicite par FEN, donc sélection stable entre deux exécutions même si
Stockfish varie légèrement à profondeur fixe (une variation ne change le
résultat que si elle fait franchir un seuil de catégorie).

Sortie : fichier JSON (défaut `data/club_selection.json`, gitignoré comme
le reste de `DATA_DIR`) et résumé lisible dans le terminal. Tests :
`test_issue143_selection_club.py` (jeu de données fabriqué, jamais
`data/erreurs_detectees.json` réel).

## Accès externe protégé (`app_club.py`, issue #144)

Pour montrer la page club à un membre du club via un lien public Tailscale
Funnel (sans exposer tout le reste du coach à Internet), `app_club.py` est
un SECOND point d'entrée HTTP, sur une instance Flask à part — pas le même
`app.py`/port 5000 qu'Alain utilise. Cette instance ne connaît QUE les
quatre routes ci-dessus (`add_url_rule`, vues réutilisées depuis `app.py`
sans duplication, `static_folder=None`) : toute autre URL y reçoit le 404
standard de Flask « par construction », jamais par détection de l'origine
de la requête. `app.py` et le port 5000 restent strictement inchangés —
l'alias `coach` d'Alain continue de fonctionner comme avant.

Deux variables obligatoires dans `.env` (jamais lues/affichées/journalisées
en clair par le code) :
- `CLUB_JETON` : jeton secret partagé dans le lien
  (`https://.../club?t=<jeton>`). Absente ou vide → `app_club.creer_app_club`
  lève `RuntimeError` et l'entrée club refuse de démarrer (jamais d'accès
  ouvert par défaut). Comparé en temps constant (`hmac.compare_digest`) à
  CHAQUE requête (page comprise) via `before_request` ; un jeton absent ou
  faux déclenche `abort(404)` — le même 404 qu'une route inexistante,
  aucune indication de la vraie raison. Repris dans la page par
  `static/club.html` (`URLSearchParams` sur `location.search`) et renvoyé
  dans l'en-tête `X-Club-Jeton` de chaque appel aux 3 points d'accès, pour
  que le visiteur n'ait jamais à le ressaisir et que sa valeur n'apparaisse
  plus dans aucune URL après le chargement initial. Le journal d'accès de
  Werkzeug (qui journalise la ligne de requête complète, donc le `?t=...`
  de la requête initiale) est désactivé sur ce process
  (`logging.getLogger("werkzeug").setLevel(logging.ERROR)`), pour ne jamais
  écrire le jeton dans un journal.
- `CLUB_ANTHROPIC_API_KEY` : clé Anthropic DÉDIÉE aux avis du coach depuis
  cette entrée. Absente ou vide → même refus de démarrage, JAMAIS de repli
  sur `config.LLM_API_KEY` (la clé principale d'Alain, utilisée par
  `app.py`/port 5000). Techniquement : `app._club_llm_api_key` (`None` par
  défaut, donc `app._club_get_llm_api_key()` renvoie `config.LLM_API_KEY`
  comme avant) est réassignée à `CLUB_ANTHROPIC_API_KEY` par
  `creer_app_club` avant de servir la moindre requête ; `api_club_avis`
  relit cette fonction à chaque appel.

Limites existantes (40 avis/jour, 2 appels simultanés, `mode_origine="club"`)
inchangées : ce sont les MÊMES compteurs/fonctions de `app.py` (vues
réutilisées telles quelles). Journal minimal des accès refusés (compteur en
mémoire, aucune donnée sensible) : `logger.warning` dans `app_club.py` à
chaque jeton invalide, avec le nombre cumulé de refus depuis le démarrage
du process — pour qu'Alain voie dans les journaux si le lien est sondé.

Mode debug toujours désactivé sur cette entrée (`club.config["DEBUG"]`/
`["TESTING"]` forcés à `False`, `app_club.run(..., debug=False)`) —
indépendant de `CHESSCOACH_DEBUG_DEV`, qui ne concerne que `app.py`/le port
5000 et n'est jamais lu par `app_club.py`.

Lancement (commande, jamais exécutée par CCL) :
```
CLUB_JETON=... CLUB_ANTHROPIC_API_KEY=... python3 app_club.py
```
(ou valeurs exportées depuis `.env` par le shell, comme pour `app.py` ;
port modifiable via `CLUB_PORT`, 5001 par défaut). Côté Tailscale, commande
lancée par Alain lui-même (jamais par CCL) :
```
tailscale funnel 5001
```
Changer le jeton ou révoquer la clé : modifier `CLUB_JETON`/
`CLUB_ANTHROPIC_API_KEY` dans `.env` puis relancer `app_club.py` (pas de
rechargement à chaud — cohérent avec le mode debug désactivé).

Tests : `test_issue144_club_acces_externe.py` (jeton absent/faux/valide,
404 par construction sur toute route hors club même avec jeton valide,
refus de construire sans `CLUB_JETON`/`CLUB_ANTHROPIC_API_KEY`, clé dédiée
jamais remplacée par la clé principale, mode debug désactivé) — via
`app_club.creer_app_club(...).test_client()`, aucun processus serveur réel
lancé par ces tests.
