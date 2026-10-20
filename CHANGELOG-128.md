# CHANGELOG - Issue #128

## Suite #126 : convention de signe de Lichess pour les évaluations et le solde matériel, détail des lignes sans coupure en échange, tests à jour

### Contexte

Constat réel d'Alain : l'application fournissait aux IA les évaluations et le
solde matériel du point de vue d'Alain (positif = avantage pour lui, quel que
soit son camp) plutôt que la convention de Lichess qu'il utilise lui-même
pour lire une position (+ = avantage Blancs, − = avantage Noirs). Exemple
réel : pour un exercice joué avec les Noirs, le contexte envoyé à l'IA
affichait "+132"/"+12" avant/après le coup alors que Lichess afficherait
"−1,3"/"−0,1" pour la même position.

Cette issue régularise aussi trois correctifs appliqués directement sur
master le 20 octobre 2026, sans tests ni changelog au moment où ils ont été
écrits : calcul « en prise » par échange (`_gain_capture`), numérotation des
coups, noms de roque, et prolongation des lignes calculées jusqu'à la fin
d'un échange.

### Modifications apportées

#### 1. engine_stockfish.py
- `EngineManager.evaluate_move()` rend désormais `eval_before_cp`/
  `eval_after_cp` directement en convention Lichess (+ = avantage Blancs,
  − = avantage Noirs), en réutilisant les valeurs `eval_before_white`/
  `eval_after_white` déjà calculées pour le verdict officiel Lichess (issue
  #125) — aucune conversion supplémentaire, donc aucun risque de double
  conversion. `win_prob_drop` et `verdict_delta_cp` restent inchangés (perte
  positive du joueur qui vient de jouer).

#### 2. app.py
- Suppression de `_vers_point_de_vue_alain` : plus aucune conversion vers
  « le point de vue d'Alain ». Les champs de contexte `eval_alain_cp`/
  `eval_alain_mat` sont renommés `eval_blancs_cp`/`eval_blancs_mat` dans
  tous les handlers concernés (`on_exercise_answer`, `_on_exercise_answer_lichess`,
  `on_coach_comment_on_demand`, `on_pedagogic_move`, `on_opening_move`,
  `on_finale_move`).
- Le chemin « Mes erreurs » et le chemin « Problèmes Lichess »
  (`_on_exercise_answer_lichess`) transmettent désormais tous les deux la
  convention Lichess.
- `on_coach_comment_on_demand` (question de suivi via le bouton, et fusion
  du contexte renvoyé par le client pendant un exercice) relit
  `eval_blancs_cp`/`eval_blancs_mat` du payload client sous le même nom —
  pas de double conversion possible puisqu'aucune conversion ne reste en
  place.

#### 3. game_facts.py
- `_materiel_alain` (solde signé selon `camp_alain`) remplacé par
  `_solde_blancs` (Blancs − Noirs, indépendant du camp joué).
- `describe_eval_alain_cp_clause` renommée `describe_eval_blancs_cp_clause`,
  ne mentionne plus jamais « pour Alain »/« pour toi », nomme le camp
  concerné (Blancs/Noirs) explicitement.
- `format_pv_facts` : l'en-tête du bloc de faits ne garde plus que le camp
  joué par l'utilisateur et la définition de « en prise », et dit désormais
  « Évaluations et soldes : + = avantage Blancs, − = avantage Noirs
  (convention de Lichess) ».
- `describe_pv_with_balance`/`format_pv_with_balance` (détail coup par coup
  des lignes, `pv_coup_propose_detail`/`pv_meilleur_coup_detail`) : le solde
  matériel cumulé (`solde_blancs`) suit la même convention, et la ligne
  n'est plus jamais coupée au milieu d'un échange (prolongation d'au plus 2
  coups tant que le dernier coup retenu est une capture — même règle que
  `engine_stockfish._couper_pv`, dupliquée ici sur la SAN car cette fonction
  travaille sur du texte, pas sur des `chess.Move`).
- `describe_menace_adverse` reconvertit le chiffre interne de
  `EngineManager.get_threats` (point de vue du camp au trait) vers la
  convention Lichess avant de l'inclure dans le texte de contexte.

#### 4. llm_coach.py
- Nouvelle consigne, toujours présente (pas seulement en mode Exercice) :
  tous les chiffres d'évaluation et de solde matériel suivent la convention
  de Lichess ; ne jamais dire « pour toi »/« pour Alain »/« pour
  l'adversaire » ; ne jamais inverser un signe ; position égale (sans
  parler d'avantage) quand la valeur absolue de l'évaluation est inférieure
  à 30 centipions.
- `_build_context_text` lit `eval_blancs_cp`/`eval_blancs_mat` (au lieu de
  `eval_alain_cp`/`eval_alain_mat`), formate "Évaluation avant/après le coup"
  en précisant la convention Lichess dans le texte.

#### 5. static/exercise.js
- Renommage en miroir de `exerciseEvalAlainCp`/`exerciseEvalAlainMat` en
  `exerciseEvalBlancsCp`/`exerciseEvalBlancsMat`, et des clés
  `eval_alain_cp`/`eval_alain_mat` en `eval_blancs_cp`/`eval_blancs_mat` dans
  le contexte renvoyé au serveur pour une question de suivi du chat libre
  pendant un exercice (jamais affiché à l'écran tel quel).

#### 6. non_regression_coach.py
- Script de bilan mis à jour en miroir (clé de contexte
  `eval_blancs_mat`), aucune donnée personnelle concernée (positions
  synthétiques).

#### 7. Tests
- `test_issue126.py` : numérotation attendue mise à jour ("1.e4" au lieu de
  "1e4", conséquence du correctif manuel du 20 octobre sur la numérotation
  des coups).
- `test_issue128.py` (nouveau) :
  - calcul « en prise » par échange : pièce attaquée par une tour mais
    défendue par un pion (pas en prise), même pièce sans défenseur (en
    prise), défenseur cloué qui ne protège pas ;
  - numérotation « 31.R5xe4 »/« 30...R5xe4 » avec désambiguïsation SAN ;
  - noms de roque (petit/grand) ;
  - prolongation des lignes jusqu'à la fin d'un échange, pour
    `engine_stockfish._couper_pv`, `game_facts.describe_pv_with_balance` et
    `game_facts.describe_pv_facts` (exemple réel cité par l'issue : "Bd6 O-O
    O-O exd5" prolongé par "cxd5") ainsi que le garde-fou symétrique (pas de
    prolongation si le dernier coup retenu n'est pas une capture) ;
  - conversion de signe des évaluations (`EngineManager.evaluate_move`) et
    du solde matériel (`_solde_blancs`, `describe_pv_with_balance`,
    `describe_eval_blancs_cp_clause`) pour un exercice Noirs et un exercice
    Blancs ;
  - exécution du VRAI gestionnaire `on_exercise_answer`/
    `_on_exercise_answer_lichess` via le client de test Flask-SocketIO,
    `llm_coach._call_claude` simulé (aucun appel réseau réel), isolation
    complète des chemins `data/` de `config.py` vers un dossier temporaire —
    vérifie le signe de l'évaluation transmise dans le system prompt pour
    les sources « Mes erreurs » et « Problèmes Lichess », exercice Noirs et
    Blancs.

### Hors périmètre (volontairement inchangé)
- L'affichage côté interface (barre d'évaluation) dans les modes autres que
  le mode Exercice n'est pas concerné par cette issue : elle ne touche
  qu'aux chiffres transmis aux IA et au journal.
- `verdict_delta_cp`, le verdict officiel Lichess et `win_prob_drop` ne sont
  pas des évaluations signées Blancs/Noirs et restent inchangés.
