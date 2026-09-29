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
