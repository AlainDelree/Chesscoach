# Issue #125 : Implémentation du verdict officiel Lichess

## Résumé
Implémentation de la classification officielle Lichess basée sur la variation des chances de gain plutôt que sur des seuils fixes en centipions.

## Modifications

### engine_stockfish.py
- Ajout des fonctions `cp_to_win_probability()` et `classify_move_lichess()` pour implémenter la formule Lichess
- Modification de `evaluate_move()` pour retourner un dictionnaire au lieu d'un tuple, incluant :
  - `qualite` : verdict ancien (basé sur des seuils fixes)
  - `qualite_officielle` : verdict officiel Lichess (basé sur la chute de probabilité de gain)
  - `eval_before_cp` : évaluation AVANT le coup (point de vue du joueur)
  - `eval_after_cp` : évaluation APRÈS le coup (point de vue du joueur)
  - `win_prob_drop` : chute de probabilité de gain
  - `analyse_indisponible` : indicateur de panne moteur
  - `pv_coup_propose` et `pv_meilleur_coup` : lignes PV (si `return_pv=True`)

### app.py
- Adaptation de `_evaluate_move_for_coach()` pour utiliser le nouveau format de retour de `evaluate_move()`
- Transmission des nouveaux champs (`verdict_qualite_officiel`, `eval_before_cp`, `eval_after_cp`, `win_prob_drop`) dans le contexte
- Adaptation de l'autre appel direct à `evaluate_move()` (vérification Stockfish des moments clés)

### llm_coach.py
- Modification de la construction du contexte pour inclure les nouveaux champs Lichess
- Adaptation de `_build_context_text()` pour :
  - Utiliser `verdict_qualite_officiel` comme verdict principal
  - Ajouter les évaluations avant/après et la chute de chances dans le prompt système
  - Conserver `verdict_qualite_ancien` pour comparaison

### fact_checker.py
- Modification pour utiliser `verdict_qualite_officiel` comme référence pour la vérification de cohérence
- Chute sur `verdict_qualite` si `verdict_qualite_officiel` n'est pas disponible (compatibilité)

### CONTEXTE.md
- Ajout d'une section "Classification des coups" documentant :
  - La méthode officielle Lichess (formule, seuils)
  - La distinction entre sélection des exercices (seuils fixes) et verdict affiché (méthode Lichess)
  - Les champs transmis au coach

## Formule Lichess

La probabilité de gain est calculée par :
```
chances = 2 / (1 + exp(-0.00368208 × cp)) - 1
```

Où `cp` est l'évaluation en centipawns, plafonnée à ±1000 cp.

Les seuils de classification sont basés sur la **chute** de cette probabilité :
- **bon** : chute < 0.1
- **imprécision** : chute ≥ 0.1
- **erreur** : chute ≥ 0.2
- **gaffe** : chute ≥ 0.3

## Vérification

Les six exemples annotés par Lichess ont été testés et donnent les résultats attendus :
1. 0.27 → 0.96 (Noirs) → imprécision ✓
2. 0.00 → -0.65 (Blancs) → imprécision ✓
3. -0.02 → -1.24 (Blancs) → erreur ✓
4. 1.82 → 0.64 (Blancs) → erreur ✓
5. 4.27 → 0.10 (Blancs) → gaffe ✓
6. -2.88 → -0.21 (Noirs) → gaffe ✓

## Compatibilité

- La sélection des exercices (`build_patterns_erreurs.py`, `erreurs_detectees.json`) reste inchangée
- Les seuils fixes en centipions sont conservés pour la détection des erreurs
- Seul le verdict **affiché et transmis au coach** utilise la méthode officielle Lichess
- Les anciens appels à `evaluate_move()` ont été adaptés pour utiliser le nouveau format de retour
- Correction des appels oubliés dans `non_regression_coach.py` et `engine_stockfish.py` (méthode `get_punishment_line`)

## Points non couverts

- Les scripts de bilan et tableaux des journaux n'ont pas été modifiés (à faire si nécessaire)
- La vérification en conditions réelles avec des parties complètes n'a pas été testée (nécessite un environnement complet)
- Le script `lire_journal_coach.py` affiche déjà automatiquement tous les champs du contexte, y compris les nouveaux champs Lichess (`verdict_qualite_officiel`, `eval_before_cp`, `eval_after_cp`, `win_prob_drop`)
