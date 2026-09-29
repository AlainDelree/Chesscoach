# Changelog — Issue #61

## Choix du modèle Claude (Haiku/Sonnet) depuis l'interface, sans redémarrage

- Contexte : le modèle était fixé une fois pour toutes par
  `CHESSCOACH_LLM_MODEL` (.env) — passer de Haiku (tests) à Sonnet (jeu
  sérieux) imposait d'éditer le .env et de relancer l'appli.
- `config.py` : `LLM_MODEL_HAIKU`/`LLM_MODEL_SONNET`/`LLM_MODEL_CHOICES`
  (id → libellé) définis en un seul endroit ; `config.set_llm_model(model_id)`
  change `config.LLM_MODEL` en mémoire (effet immédiat sur tous les appels
  suivants, tous chemins confondus) et persiste le choix dans
  `data/llm_model_choice.json` (nouveau fichier, séparé du .env, gitignoré
  comme le reste de data/). Au démarrage, reprend ce fichier s'il est valide,
  sinon `CHESSCOACH_LLM_MODEL` si elle correspond à l'un des deux choix,
  sinon Sonnet par défaut.
- templates/index.html : sélecteur `#llm-model-selector` dans l'en-tête, près
  du compteur de tokens — deux boutons contigus « Haiku (test) » /
  « Sonnet (sérieux) », libellés abrégés sous 900px (comme le reste de
  l'en-tête), vérifié sans débordement à 390×844 (Playwright).
- static/llm_model.js (nouveau) : clic → événement SocketIO `set_llm_model`,
  bascule le bouton actif sur confirmation (`llm_model_changed`), affiche un
  message clair dans le chat en cas de retour automatique
  (`llm_model_indisponible`).
- app.py : handler `set_llm_model` ; `_handle_llm_model_indisponible_si_besoin`
  appelé au début des 10 blocs `if error:` (un par point d'appel API) — si
  l'API refuse le modèle actif (HTTP 404 `not_found_error`, remonté par
  `llm_coach.ModeleIndisponibleError` en `error: "modele_indisponible"`),
  revient seul à l'autre choix (persisté) et prévient le client au lieu
  d'afficher une erreur technique brute.
- llm_coach.py : nouvelle exception `ModeleIndisponibleError` (même pattern
  que `CreditInsuffisantError`, issue #54), détectée dans `_call_claude` et
  propagée par les 4 fonctions publiques d'appel. `_log_coach_call` inscrit
  désormais un champ `model` explicite dans chaque entrée de
  `coach_calls.log` (déjà présent via `usage.model` sur les appels réussis,
  manquant sur les entrées d'erreur).
- Paramètres d'appel (`max_tokens=4096`, `thinking: {"type": "disabled"}`)
  vérifiés acceptés tels quels par les deux modèles — aucune adaptation par
  modèle nécessaire.
- Compteur de tokens par modèle (issue #54) déjà cohérent après un
  changement de modèle en cours de session (`_record_usage` cumule par
  modèle réellement résolu par l'API, indépendamment du sélecteur).
- CONTEXTE.md : nouvelle section « Choix du modèle Claude (Haiku/Sonnet)
  depuis l'interface (issue #61) ».
