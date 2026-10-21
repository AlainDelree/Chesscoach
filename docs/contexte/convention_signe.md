# Convention de signe Lichess pour toutes les évaluations/soldes (issue #128)

Constat d'Alain (20 octobre 2026) : l'application fournissait aux IA (et au
journal) les évaluations et le solde matériel du point de vue d'Alain
(positif = avantage pour lui, quel que soit son camp) plutôt que la
convention de Lichess qu'il utilise lui-même pour lire une position (+ =
avantage Blancs, − = avantage Noirs). Exemple réel : pour un exercice joué
avec les Noirs, le contexte envoyé à l'IA affichait "+132"/"+12" avant/après
le coup alors que Lichess afficherait "−1,3"/"−0,1" pour la même position —
Alain a été induit en erreur en lisant ce chiffre comme s'il suivait la
convention Lichess.

**Principe retenu** : toutes les évaluations en centipions et tous les
soldes matériel transmis aux IA (contexte du chat, mode Exercice sources
« Mes erreurs » et « Problèmes Lichess », question de suivi du chat libre,
script `non_regression_coach.py`) suivent désormais la convention de
Lichess, SANS AUCUNE conversion vers le camp de l'utilisateur :
- `engine_stockfish.EngineManager.evaluate_move` rend `eval_before_cp`/
  `eval_after_cp` directement en convention Blancs (déjà calculée en
  interne pour la classification officielle Lichess, issue #125 — il
  suffisait de la stocker au lieu de la valeur "point de vue du joueur").
- `app.py` ne convertit plus vers "le point de vue d'Alain" : la fonction
  `_vers_point_de_vue_alain` a été supprimée, les champs de contexte
  `eval_alain_cp`/`eval_alain_mat` sont devenus `eval_blancs_cp`/
  `eval_blancs_mat` (valeur de `_eval_blancs_apres`, transmise telle
  quelle). Même
  renommage côté client (`static/exercise.js`, round-trip du contexte pour
  une question de suivi pendant un exercice — jamais affiché à l'écran,
  uniquement réinjecté dans le contexte envoyé à l'IA).
- `game_facts.py` : `_materiel_alain` (solde signé selon camp_alain) a été
  remplacé par `_solde_blancs` (blancs − noirs, toujours calculable, plus
  aucune dépendance à camp_alain) ; `describe_eval_alain_cp_clause` devient
  `describe_eval_blancs_cp_clause` ; le bloc de faits python-chess par coup
  (`format_pv_facts`) affiche désormais en en-tête « Évaluations et soldes :
  + = avantage Blancs, − = avantage Noirs (convention de Lichess) » au lieu
  de « Solde pour toi » ; `describe_menace_adverse` reconvertit le chiffre
  rendu par `EngineManager.get_threats` (qui reste côté moteur "point de vue
  du camp au trait") vers cette même convention avant de l'inclure dans le
  texte transmis à l'IA.
- Plus aucune formulation « pour toi »/« pour Alain » n'accompagne un
  chiffre signé dans le texte envoyé à l'IA — le camp concerné, s'il doit
  être nommé, est désormais toujours écrit explicitement (« Blancs »/
  « Noirs »).
- `llm_coach.py` : consigne ajoutée dans le system prompt (toujours
  présente, pas seulement en mode Exercice) : tous les chiffres suivent la
  convention de Lichess, ne jamais dire « pour toi »/« pour Alain », ne
  jamais inverser un signe, et considérer la position comme égale (sans
  parler d'avantage) quand la valeur absolue de l'évaluation est inférieure
  à 30 centipions.
- `non_regression_coach.py` (script de bilan/non-régression du coach,
  jamais sur les données personnelles réelles) mis à jour en miroir.

**Affichage de la barre d'évaluation — état revérifié pour l'issue #131** :
le diagnostic initial de l'issue #128 indiquait que `eval_alain_cp`/
`eval_alain_mat` restaient par ailleurs utilisés tels quels pour la barre
d'évaluation (hors mode Exercice). Une revérification du code (2026-10-21)
montre que ces deux noms de champ n'existent plus nulle part dans le dépôt :
la fonction `updateEvalBar(cp, mate)` (static/board.js) qui peuple la barre
(`#eval-black`/`#eval-white`/`#eval-score` dans templates/index.html) existe
toujours mais n'est appelée depuis aucun fichier `static/*.js` ni
`templates/*.html` du dépôt — elle semble orpheline (code mort), sans doute
suite à un refactor ultérieur non documenté. Son code interne traite
désormais un cp positif comme un avantage Blancs (pas "point de vue
d'Alain"). Point non résolu par cette issue (documentation uniquement,
aucune modification de code) : confirmer avec Alain si la barre
d'évaluation est toujours censée fonctionner, et le cas échéant ouvrir une
issue de code pour retrouver/réparer son point d'appel.
