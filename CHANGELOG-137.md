## Issue #137 — Suite #128 : tests du signe des évaluations pour « Problèmes Lichess »

Ajout de `test_issue137_signe_eval_lichess.py` (14 cas, 7 par camp d'Alain :
avantage Blancs, avantage Noirs, quasi-égalité, mat Blancs, mat Noirs, signes
opposés avant/après coup, avantage matériel évident — les deux derniers avec
le VRAI moteur Stockfish, sans aucune simulation). Chaque cas vérifie que
`eval_blancs_cp`/`eval_blancs_mat` du contexte transmis à l'IA (simulée) a le
signe de Lichess quel que soit le camp d'Alain, et que `coach_calls.log`
enregistre exactement la même valeur. Chemin testé : le VRAI
`app._on_exercise_answer_lichess` via le client de test Flask-SocketIO,
infrastructure réutilisée de `test_issue128.py` (chemins de données
temporaires, aucune donnée réelle de `data/`). Aucun test ignoré.

Tests existants au nom trompeur (listés dans le docstring du nouveau
fichier, fichier `test_issue128.py`) : `test_problemes_lichess_exercice_noir_
eval_negative` et `test_problemes_lichess_exercice_blanc_eval_positive` ne
vérifient que l'absence de « pour toi »/« pour Alain » dans le prompt — aucune
extraction ni comparaison de signe numérique malgré leur nom.

Constat technique (sans impact sur le code de production, documenté dans le
docstring du nouveau fichier) : pour le chemin « Problèmes Lichess »
spécifiquement, `eval_blancs_cp`/`eval_blancs_mat` proviennent de
`app._eval_blancs_apres` (appel direct à `EngineManager.evaluate`), pas de
`engine_stockfish.evaluate_move` — déjà documenté correctement par
`docs/contexte/convention_signe.md` (deux mécanismes distincts), mais pas par
le libellé de contexte de l'issue #137 elle-même. Le contrôle par inversion
(tâche 6) a donc ciblé la vraie source pour ce chemin.

Contrôle par inversion (copie temporaire sous `/tmp`, jamais dans le
worktree) : inversion du signe dans `app._eval_blancs_apres` → 14/14 tests
échouent. Inversion (littérale, pour vérification) dans
`engine_stockfish.evaluate_move` → 0/14 échouent, confirmant que ce chemin
n'utilise pas cette fonction. Copie supprimée après contrôle.

Aucun fichier de production modifié. Aucune modification du prompt ni de
CONTEXTE.md.
