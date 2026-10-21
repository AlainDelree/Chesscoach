# Choix du modèle Claude (Haiku/Sonnet) depuis l'interface (issue #61)

Avant l'issue #61, le modèle était fixé une fois pour toutes par
`CHESSCOACH_LLM_MODEL` (.env) — changer de modèle imposait d'éditer le .env
et de relancer l'appli. Un petit sélecteur dans l'en-tête (`#llm-model-selector`
dans templates/index.html, juste avant le compteur de tokens), deux boutons
contigus « Haiku (test) » / « Sonnet (sérieux) » façon *segmented control*,
permet désormais de basculer sans redémarrage, sans interrompre la partie ni
effacer le chat en cours. Libellés complets en desktop, abrégés (premier mot)
sur écran étroit (media query `max-width: 900px`, même seuil que le reste de
l'en-tête) — comportement vérifié à 390×844 (aucun débordement horizontal).

Les deux identifiants de modèle sont définis une seule fois dans config.py :
`LLM_MODEL_HAIKU`/`LLM_MODEL_SONNET` (+ `LLM_MODEL_CHOICES`, le dict
id → libellé qui alimente à la fois le sélecteur et la validation du choix
reçu du client). `config.LLM_MODEL` reste l'attribut lu par tous les appels
API (`app.py` construit `llm_config["llm_model"]` à partir de
`config.LLM_MODEL` à chaque appel, jamais une copie figée au démarrage) —
`config.set_llm_model(model_id)` le réassigne directement en mémoire, d'où
l'effet immédiat sur tous les appels suivants, tous chemins confondus (chat
du coach, explications de coups, programme d'entraînement, commentaires des
modes ouverture/finales/pédagogique/exercice), sans exception à gérer côté
appelants puisque `config.LLM_MODEL` est relu, pas copié.

Persistance : `config.set_llm_model` écrit aussi le choix dans
`data/llm_model_choice.json` (`{"model": "..."}`), un petit fichier séparé du
`.env`, jamais modifié automatiquement — sous DATA_DIR, donc gitignoré comme
le reste des données personnelles. Au démarrage, `config.py` reprend ce
fichier s'il contient un choix valide ; à défaut (premier lancement, fichier
absent ou invalide), reprend `CHESSCOACH_LLM_MODEL` si sa valeur correspond à
l'un des deux choix connus, sinon Sonnet par défaut (jeu sérieux plutôt que
test).

Côté interface, le clic sur un bouton émet l'événement SocketIO
`set_llm_model` (`{"model": "..."}`) ; le serveur répond `llm_model_changed`
(bascule le bouton actif) ou, si `model_id` n'est ni Haiku ni Sonnet,
`llm_model_error` (n'arrive pas en usage normal, les deux boutons envoient
toujours un id connu — filet de sécurité défensif). Logique dans
static/llm_model.js.

Refus par l'API (modèle introuvable ou indisponible, HTTP 404
`not_found_error`) : `_call_claude` (llm_coach.py) lève désormais
`ModeleIndisponibleError`, distinguée de `CreditInsuffisantError` (issue
#54) et remontée par les 4 fonctions publiques (`get_coach_response`,
`get_move_explanations`, `get_opening_moves`, `get_training_program`) comme
`error: "modele_indisponible"`. Les 10 points d'appel API de app.py
partagent tous le même filet (`_handle_llm_model_indisponible_si_besoin`,
appelé au tout début de chaque bloc `if error:`) : comme il n'existe que deux
choix, revenir à « l'autre » est sans ambiguïté le choix précédent — le
serveur y revient seul (`config.set_llm_model`, donc persisté) et prévient le
client via l'événement `llm_model_indisponible`, qui remet à jour le
sélecteur ET affiche un message clair dans le chat (`static/llm_model.js`),
plutôt qu'une erreur technique brute ou un sélecteur resté sur un choix qui
ne répond plus.

Paramètres d'appel (`_call_claude`) : `max_tokens=4096` et
`thinking: {"type": "disabled"}` sont acceptés tels quels par les deux
modèles (vérifié auprès de la documentation API à jour) — Haiku ne raisonne
jamais nativement (`disabled` y est un no-op sans contrainte particulière),
et Sonnet 5 accepte explicitement `{"type": "disabled"}` comme l'omission du
paramètre. `max_tokens=4096` reste très en dessous des plafonds des deux
modèles (64K pour Haiku 4.5, 128K pour Sonnet 5). Aucune adaptation par
modèle n'a donc été nécessaire.

Le compteur de tokens par modèle (`usage_tokens.json`, issue #54) reste
cohérent après un changement de modèle en cours de session : `_record_usage`
cumule déjà par `data["model"]` (le modèle réellement résolu par l'API pour
CET appel, pas le paramètre d'entrée), donc un changement de sélection
n'affecte que les appels suivants — les compteurs déjà accumulés pour
l'ancien modèle restent inchangés dans `par_modele`.
