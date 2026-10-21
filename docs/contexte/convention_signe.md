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

**Formulation « qui est mieux » et verdict sous-évalué — issue #134, suite
#128** : une mesure sur les avis réels (21 octobre 2026, 26 avis de la
version #128) a montré que la consigne de l'issue #128 ne suffisait pas :
aucune inversion de signe numérique, mais trois défauts de formulation
subsistaient. (1) « pour toi » restait parfois accolé à un chiffre signé
malgré l'interdiction déjà en place (ex. « position largement gagnante pour
toi (-311) », « (-90, soit toujours un léger avantage pour toi) »).
(2) Sens inversé malgré des chiffres corrects : un avis a écrit « tu restes
légèrement mieux » alors que l'évaluation (+148 puis +297, convention
Lichess) favorisait les Blancs pendant qu'Alain jouait les Noirs — Alain
était en réalité moins bien, et la situation empirait. (3) Verdict
sous-évalué : environ 5 avis sur 26 ouvraient sur « imprécision » alors que
le verdict officiel (`verdict_qualite_officiel`) était « erreur » ou
« gaffe ».

Correctifs (`llm_coach.py`) :
- `_SYSTEM_PROMPT` : interdiction étendue à « en ta faveur »/« tu restes
  mieux » (en plus de « pour toi »/« pour Alain ») à proximité d'un chiffre
  signé ; obligation de nommer le camp mieux placé par sa couleur, chiffre à
  l'appui tel quel, et de réserver « toi »/« tu » à une phrase sans chiffre ;
  deux mini-exemples (un côté Blancs, un côté Noirs) à partir de la même
  paire de valeurs (+148 puis +297) lue dans les deux sens selon le camp
  d'Alain.
- `_EXERCISE_SYSTEM_ADDENDUM` : le mot de qualité qui ouvre l'avis doit
  reprendre exactement le verdict officiel fourni (« bon », « imprécision »,
  « erreur », « gaffe »), sans jamais l'atténuer — nuance permise après ce
  premier mot, jamais en remplacement.

Correctifs (`fact_checker.py`, mécanisme d'alertes `fact_checker_alertes` en
place depuis l'issue #117) — deux contrôles déterministes de plus, sans
appel IA, déclenchant la même alerte/le même niveau de fiabilité que les
autres incohérences :
- `_verifier_pour_toi_chiffre_colle` : alerte si « pour toi » apparaît à
  proximité d'un chiffre signé dans la même phrase, quel que soit le signe du
  chiffre (la formulation est interdite en elle-même, indépendamment de sa
  justesse).
- `_verifier_sens_qui_est_mieux` : alerte si une phrase désignant qui est
  mieux (« pour toi », « tu restes mieux », « en ta faveur », « pour les
  Blancs/Noirs », « en faveur des Blancs/Noirs ») contredit le signe réel de
  l'évaluation du contexte (`eval_before_cp`/`eval_after_cp`) ramené au camp
  d'Alain. Prudence : aucune alerte si l'évaluation est absente, trop proche
  de l'égalité (< 30 cp), ou si avant/après se contredisent (le camp mieux
  placé a changé) ; le chiffre cité par l'avis peut être celui d'avant ou
  d'après le coup, seul le sens compte.
- `_verifier_mot_verdict_premiere_phrase` : alerte si le mot de qualité de la
  première phrase diffère du verdict officiel (`verdict_qualite_officiel`, à
  défaut `verdict_qualite`) — « bon coup » compte comme « bon ».
- Effet de bord : les contrôles (c)/(d)/(e) de `verifier_affirmations`
  (cohérence verdict/texte, sens « qui est mieux », mot de verdict) ne
  dépendent plus de la présence de positions candidates (FEN) — avant cette
  issue, l'absence de toute position candidate faisait sortir la fonction
  avant même d'exécuter ces contrôles, qui n'en ont pourtant pas besoin.

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
