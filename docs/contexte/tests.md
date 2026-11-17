# Tests — lanceur unique, tests lents, arrêt du moteur

## Commande unique
```
python3 scripts/lancer_tests.py              # suite complète
python3 scripts/lancer_tests.py --rapide     # sans les tests lents
python3 scripts/lancer_tests.py --timeout N  # délai max par fichier (défaut 300s)
```
Chaque `test_*.py` à la racine est lancé dans son **propre process** (un
fichier fait `importlib.reload(app)` en cours de test — partager un
interpréteur casserait les autres fichiers). Détection automatique par
fichier : une classe `unittest.TestCase` → `python3 -m unittest -q
<module>` ; sinon (anciens fichiers sans classe, exécutés via leur propre
`main()`) → `python3 <fichier>.py` directement. Pas de pytest (choix de
l'issue #153 : solution la plus simple, sans dépendance supplémentaire).

Code de sortie non nul si un fichier échoue ou expire. En cas de
dépassement du délai, tout le groupe de process du fichier (Python et le
Stockfish qu'il a pu lancer) est arrêté — jamais de processus laissé
derrière, même après expiration.

## Tests lents
`test_issue143_selection_club.py` (vrai Stockfish sur chaque position,
~3 min) est le seul test lent du dépôt. Isolé derrière la variable
d'environnement `CHESSCOACH_SKIP_SLOW_TESTS` : si elle vaut `"1"`, sa
classe `TestSelectionClub` est sautée via `@unittest.skipIf(...)`, avec un
message clair. `--rapide` sur le lanceur positionne cette variable pour
tous les sous-process ; sans elle (mode complet, par défaut), le fichier
tourne normalement — y compris l'échec explicite (`RuntimeError`, jamais
un skip) si Stockfish est absent de la machine (issue #143, vérification
c, préservée).

Pour ajouter un futur test lent : réutiliser la même variable, jamais une
nouvelle, et ne l'utiliser QUE pour sauter par choix de vitesse — jamais
pour masquer l'absence d'un outil requis (Stockfish doit toujours faire
échouer, pas sauter).

## Règle pour tout nouveau fichier de tests
Tout fichier qui importe `app.py` (ou `app_club.py`, qui importe lui-même
`app.py`) ou crée un `engine_stockfish.EngineManager`/`SimpleEngine` DOIT
arrêter ce moteur explicitement en fin de classe (`tearDownClass`) ou de
module : `if moteur: moteur.quit()`. Sans cet appel, Python attend la fin
des threads non-démons du moteur à la fermeture de l'interpréteur et le
process ne se termine jamais — `atexit.register(...)` dans `app.py` ne
suffit pas, car il ne s'exécute qu'après la fin de ces threads. Si le
fichier fait `importlib.reload(app)` en cours de test, arrêter aussi
l'ANCIEN `engine_manager` juste après le reload (la nouvelle instance
remplace l'ancienne, qui resterait sinon orpheline).

## Limites connues (non corrigées par l'issue #153, hors périmètre)
- `test_issue121.py` échoue (4/6, préexistant, étranger à cette issue :
  deux vérifications statiques sur `static/*.js` ne correspondent plus au
  code actuel).
- `test_lichess_formula.py` et `test_issue114.py` sont des scripts de
  simulation sans réelle assertion d'échec (le premier calcule un
  résultat `all_passed` mais ne le propage pas au code de sortie ; le
  second ne peut structurellement pas échouer) — un échec réel n'y
  déclencherait donc pas toujours un code de sortie non nul.
- `test_fact_checker.py` n'est pas un test unitaire isolé : c'est l'outil
  d'audit du vérificateur, qui lit les vrais logs de production
  (`config.COACH_CALLS_LOG_PATH`) — son code de sortie dépend de la
  présence de ces logs sur la machine, pas d'assertions figées.
