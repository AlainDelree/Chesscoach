# Changelog — Issue #153

## Tests : arrêt propre des moteurs, une seule commande, tests lents isolés

- Inventaire des 25 fichiers `test_*.py` : 13 basés sur `unittest.TestCase`
  (12 importent `app.py`/`app_club.py` ou créent un `EngineManager`), 12
  « anciens » fichiers sans classe (script + `main()`), aucun n'important
  `app.py`. Détail dans `docs/contexte/tests.md`.
- Arrêt explicite du moteur ajouté en fin de classe (`tearDownClass`,
  `if app_module.engine_manager: .quit()`) dans 7 fichiers qui en
  manquaient : `test_issue128.py` (classe `TestExerciseAnswerSocketIO`),
  `test_issue134.py`, `test_issue135.py`,
  `test_issue137_signe_eval_lichess.py`, `test_issue139_mode_serie.py`,
  `test_issue140_mode_serie_ia_arriere_plan.py`,
  `test_issue141_golden_master.py`. Mesuré avant/après : chacun restait
  bloqué (process non terminé malgré « Ran N tests ... OK ») ; après le
  correctif, exit=0 et process terminé pour les 7. Aucun rechargement de
  module orphelin trouvé ailleurs (`test_issue142_page_club.py` gérait déjà
  correctement son `importlib.reload(app)`).
- Nouveau script `scripts/lancer_tests.py` : lance chaque `test_*.py` dans
  son propre process (détection automatique `unittest` vs script direct),
  délai maximal configurable (`--timeout`, 300s par défaut), tue tout le
  groupe de process (Python + Stockfish) en cas de dépassement, résumé
  final (réussis/échoués/expirés/durée), code de sortie non nul si échec ou
  expiration. Option `--rapide` pour sauter les tests lents.
- Test lent isolé : `test_issue143_selection_club.py` (~3 min, vrai
  Stockfish) sauté via `@unittest.skipIf(os.environ.get(
  "CHESSCOACH_SKIP_SLOW_TESTS") == "1", ...)`, message clair à l'écran.
  Sans cette variable (mode complet, par défaut), comportement inchangé :
  Stockfish absent fait toujours échouer `setUpClass`, jamais sauter
  (invariant de l'issue #143, vérification c, préservé — docstring du
  fichier mise à jour pour documenter la nuance).
- Exécution complète une fois avec `scripts/lancer_tests.py` : 25
  fichiers, 509.0s, 24 réussis / 1 échoué / 0 expiré, aucun processus
  Python ni Stockfish restant après la fin (vérifié par `ps`). Le seul
  échec, `test_issue121.py` (4/6 assertions), est préexistant et étranger
  à cette issue (deux vérifications statiques sur `static/*.js` obsolètes)
  — signalé, non corrigé (hors périmètre).
- Documentation : nouvelle fiche `docs/contexte/tests.md` (commande
  unique, option rapide/complète, règle d'arrêt explicite pour tout futur
  test, limites connues non corrigées). `CONTEXTE.md` : bullet « suite de
  tests » mise à jour (n'était plus vraie) et ligne d'index ajoutée vers
  la fiche ; fichier à 3995 caractères (sous la limite de 4000).
