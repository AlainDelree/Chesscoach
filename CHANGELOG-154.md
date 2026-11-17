# Changelog — Issue #154

## Robustesse : captures d'erreur silencieuses, except nus, échec d'écriture avalé, écriture non atomique

- Audit via `ruff check --select S110,S112,E722` (venv Bridge_Agent,
  ruff 0.17.4) : 41 sites de capture silencieuse/except nu dans le code
  applicatif, répartis sur app.py (5), fact_checker.py (19, tous en
  except nu), coach_ratings.py (3), coach_reliability.py (1),
  engine_stockfish.py (3), game_facts.py (2), non_regression_coach.py
  (2), scripts/fiche_dernier_exercice.py (1), version_info.py (4),
  test_issue124.py (1, test). Pour chaque site, une trace `logger.debug`
  a été ajoutée avec le même repli qu'avant (aucun comportement visible
  changé), sauf fact_checker.py dont les except nus (`except:`) ont en
  plus été restreints à `except Exception:` (narrowing explicite des
  rules E722 — plus d'interception des interruptions système
  `KeyboardInterrupt`/`SystemExit`, qui ne sont pas des `Exception`).
  Trois sites supplémentaires signalés par l'issue mais non détectés par
  ruff (déjà typés `ValueError`/`(ValueError, TypeError)`, donc hors
  périmètre de S110/S112 qui ne ciblent que `Exception`/bare) ont aussi
  reçu une trace debug : `scripts/coach_ratings_report.py::_get_timestamp`,
  `scripts/estimer_cout_api.py::parser_date` et
  `::extraire_date_de_fichier`.
- Aucun `noqa` ni `nosec` ajouté sur ces lignes ; les suppressions de
  sécurité déjà présentes (S310/S603/S607/S311, ex. subprocess dans
  version_info.py) n'ont pas été touchées.
- `config.py::set_llm_model` : l'échec d'écriture de
  `LLM_MODEL_CHOICE_PATH` (OSError) est désormais tracé en avertissement
  et la fonction renvoie `False` (avant : l'échec était avalé et la
  fonction renvoyait toujours `True`). Le changement reste appliqué en
  mémoire immédiatement (comportement de `config.LLM_MODEL` inchangé),
  seule la persistance sur disque peut échouer. `_charger_choix_modele_llm`
  (lecture au démarrage, repli légitime déjà avec exception précise)
  réécrit avec `contextlib.suppress` plutôt que try/except/pass, sans
  changement de comportement.
  **Comportement visible modifié** : `app.py::on_set_llm_model` (handler
  SocketIO `set_llm_model`) distingue maintenant `model_id` invalide
  (`llm_model_error`, `error: "modele_invalide"`, inchangé) d'un échec de
  persistance (`llm_model_error`, `error: "echec_sauvegarde"`, nouveau) —
  dans ce second cas le modèle change bien pour la session
  (`llm_model_changed` toujours émis) mais un message est désormais
  affiché dans le chat (`static/llm_model.js::_llmModelRenderEchecSauvegarde`)
  pour qu'Alain ne croie pas à une sauvegarde réussie. Avant cette issue,
  cet échec était totalement invisible (aucune trace, aucun message,
  retour `True`).
- `scripts/fiche_dernier_exercice.py` : écriture du rapport
  (`fiches_dernier_exercice.md`) et de la clé A/B
  (`fiches_dernier_exercice_cle.json`) désormais atomique
  (`_ecrire_atomique` : fichier temporaire `.tmp_*` dans le même dossier,
  écrit puis `os.replace`, nettoyage du temporaire si l'écriture échoue)
  — plus de risque de fichier tronqué en cas de coupure en cours
  d'écriture. Contenu et emplacement des deux fichiers inchangés.
  `lire_jsonl` : l'`except Exception: continue` sur une ligne JSONL
  invalide est devenu `with contextlib.suppress(json.JSONDecodeError)`
  (narrowing, option (c) de l'issue).
- Nouveau fichier `test_issue154.py` (7 tests, aucun import de app.py ni
  de moteur Stockfish, donc pas d'arrêt de moteur requis) : échec
  d'écriture simulé de `set_llm_model` (retour `False` + trace
  avertissement via `assertLogs`, format du fichier et liste des modèles
  inchangés) ; `_ecrire_atomique` ne tronque jamais l'ancien contenu si
  le remplacement final échoue (fichier temporaire nettoyé) et le cas
  normal remplace bien le contenu ; un site représentatif par catégorie
  de correctif (suppress : `config._charger_choix_modele_llm` sur fichier
  corrompu ; exception restreinte : `fiche_dernier_exercice.lire_jsonl`
  sur ligne JSON invalide ; trace debug : `coach_ratings.get_all_ratings`
  sur fichier de notes corrompu).
- Suite complète : `scripts/lancer_tests.py --rapide` puis
  `scripts/lancer_tests.py` (mode complet) — 25/26 réussis dans les deux
  cas, seul échec `test_issue121.py` (4/6, préexistant, étranger à cette
  issue, cf. `docs/contexte/tests.md`), conforme à l'état connu. Aucun
  processus (Python ou Stockfish) resté actif après la suite.
- `docs/contexte/modele_llm.md` mis à jour (persistance : nouveau
  comportement sur échec d'écriture, et distinction `modele_invalide` /
  `echec_sauvegarde` côté SocketIO) — passage rendu faux par cette issue
  corrigé dans le même commit. `CONTEXTE.md` non touché (déjà à
  3995/4000 caractères).
- Fichiers modifiés : app.py, config.py, fact_checker.py,
  coach_ratings.py, coach_reliability.py, engine_stockfish.py,
  game_facts.py, non_regression_coach.py, version_info.py,
  scripts/fiche_dernier_exercice.py, scripts/coach_ratings_report.py,
  scripts/estimer_cout_api.py, static/llm_model.js, test_issue124.py,
  docs/contexte/modele_llm.md. Nouveau fichier : test_issue154.py.
