# Mode série (issue #139, suite #125, étape 1/3)

Besoin d'Alain : pendant une série d'exercices qu'il relit ensuite à
l'ordinateur, attendre les avis des deux IA (Claude + Mistral) coûte une
dizaine de secondes par exercice sans lui servir — il veut quand même le
verdict Stockfish, affiché tout de suite. L'issue #139 (suite de #125) est
découpée en trois étapes successives : celle-ci ne fait que l'interrupteur
et l'affichage du verdict ; les appels aux IA en arrière-plan avec file
d'attente et compteur viennent à l'étape 2, les tests de charge et la fiche
détaillée de bout en bout à l'étape 3 — ce qui suit décrit donc un état
INTERMÉDIAIRE, pas la forme finale du mode série.

## Interrupteur (static/exercise.js)

`exerciseModeSerie` (booléen, désactivé par défaut) — mémorisé par appareil
dans `localStorage` sous la clé `chesscoach-exercise-mode-serie`
(`_exerciseSerieLoad`/`_exerciseSerieSave`/`_exerciseSerieToggle`), appliqué
au chargement de la page (`DOMContentLoaded`) et piloté par la case à cocher
`#exercise-serie-toggle` dans le panneau de l'onglet Exercice
(`templates/index.html`, visible aussi bien sur mobile que sur grand écran —
pas dans le menu "..." global `#game-menu-dropdown`, qui n'existe que pour
les 4 modes de partie, cf. CSS `#mobile-mode-bar-slot`). `submitExerciseAnswer`
transmet sa valeur courante au serveur avec chaque `exercise_answer` (champ
`mode_serie`) et, si actif, n'affiche ni la bulle "Le coach réfléchit..." ni
le minuteur de garde de 30s (`_exerciseStartAnalysisWatchdog`) — tous deux
inutiles puisqu'aucune IA n'est appelée.

## Comportement serveur (app.py)

`on_exercise_answer` (source "mes_erreurs"/"position_precise") et
`_on_exercise_answer_lichess` (source "lichess") lisent `data["mode_serie"]`
et, si vrai, s'arrêtent JUSTE APRÈS avoir calculé le verdict Stockfish du
coup proposé (`_evaluate_move_for_coach`, le même calcul qu'hors mode série)
et AVANT tout le reste (menace adverse, idées détectées, détail des lignes,
construction du contexte envoyé aux IA) : aucun appel à `llm_coach.
get_coach_response` ni `llm_coach.get_mistral_response`, donc aucune entrée
dans `coach_calls.log`. Un seul événement est émis, `exercise_serie_verdict`,
construit par `_construire_ligne_verdict_serie(verdict_qualite_officiel,
verdict_delta_cp, meilleur_coup)` :
- `verdict_qualite_officiel` ("bon"/"imprecision"/"erreur"/"gaffe", méthode
  Lichess — cf. fiche `classification_coups`) et `verdict_delta_cp` (perte en
  centipions du coup joué, **toujours positive**, jamais une évaluation
  signée Blancs/Noirs — cf. invariant de convention de signe, fiche
  `convention_signe`) viennent tous les deux de `_evaluate_move_for_coach`,
  déjà calculés pour construire le contexte hors mode série ;
- `meilleur_coup` est le MÊME champ que celui déjà affiché/transmis hors
  mode série — recalculé par Stockfish pour "mes_erreurs"/"position_precise",
  mais le premier coup de la solution déclarée du problème pour "lichess"
  (jamais recalculé indépendamment, cf. commentaire existant de
  `_on_exercise_answer_lichess` : "la solution fait foi") ;
- si `verdict_delta_cp` vaut 0 (le coup joué EST le meilleur coup), la ligne
  le dit simplement ("c'est le meilleur coup") plutôt que d'afficher
  "(perte de 0 cp)" ;
- si l'analyse Stockfish est indisponible (`verdict_qualite_officiel` ou
  `verdict_delta_cp` absent), la ligne l'indique au lieu d'inventer un
  verdict.

Exemple : `"Verdict : gaffe (perte de 1000 cp) — meilleur coup : Qe4+."`

L'historique des exercices (`exercise_history.enregistrer_resultat`) et le
niveau Elo-like des catégories Lichess (`lichess_puzzles.mettre_a_jour_niveau`)
restent mis à jour en mode série exactement comme hors mode série — seuls les
appels aux IA et le calcul du contexte qui les accompagne sont court-circuités.

## Côté client (static/exercise.js, templates/index.html)

`socket.on("exercise_serie_verdict", ...)` est un gestionnaire DISTINCT de
`exercise_comment` : il n'appelle jamais `_coachRenderBubbleWithAgent` (donc
aucune bulle d'avis, aucun bouton de note, aucun bouton "Signaler"), ne
démarre ni ne nettoie aucun minuteur "réfléchit" (jamais démarrés pour cette
tentative), et affiche la ligne de verdict dans `#exercise-status` — le même
emplacement que les messages d'état transitoires existants ("Fais ton coup.",
"Verdict rendu...") plutôt qu'un élément qui s'accumule indéfiniment comme le
ferait une bulle du chat. Il pose `exerciseExploring`/`exerciseVerdictObtenu`
à vrai comme `exercise_comment`, donc le bouton "Exercice suivant" et le
plateau explorable sont disponibles immédiatement, sans attendre quoi que ce
soit. Désactiver le mode série en cours d'exercice ou passer à l'exercice
suivant n'affecte pas ces gestionnaires : chaque soumission relit la valeur
courante de `exerciseModeSerie`, et `exercise_position` réinitialise déjà tout
l'état par exercice (dont les mécanismes d'obsolescence Mistral de l'issue
#114), qu'un verdict précédent ait été rendu en mode série ou non.

## État temporaire (à remplacer à l'étape 2)

Zéro appel aux IA en mode série n'est PAS le comportement final visé — le
besoin réel reste d'avoir l'avis des IA disponible plus tard (file d'attente
+ compteur "avis en attente", étape 2) sans bloquer la série en cours. Ne pas
construire par-dessus ce court-circuit sans relire l'issue #139 (étape 1)
dans son intégralité.
