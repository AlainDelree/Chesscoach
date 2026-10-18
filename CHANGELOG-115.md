# Issue #115 : Suite #113 - Corrections des bulles coach et indicateur Mistral

## Problèmes identifiés

1. **Bulles coach écrasées** : Les avis de Mistral et Claude partageaient la même bulle, causant l'affichage de l'auteur "Mistral" avec le modèle "claude" et le texte de Claude.

2. **Indicateur persistant** : L'indicateur "Mistral réfléchit..." n'était jamais retiré quand Mistral répondait avant Claude.

3. **Script de bilan incomplet** : `scripts/coach_ratings_report.py` ne lisait que `coach_calls.log` et non les archives mensuelles.

## Corrections apportées

### 1. Fichiers JavaScript (static/exercise.js et static/board.js)

#### exercise.js
- **Ligne ~1244-1246** : Suppression de l'activation automatique de l'indicateur "Mistral réfléchit..." lors de la réception du commentaire de Claude
- **Ligne ~1244-1246** : Ajout d'une vérification pour ne pas afficher l'indicateur si Mistral a déjà répondu pour cet exercice
- **Ligne ~1267-1275** : Correction de `_coachRenderMistralBubbleWithAgent` pour utiliser les bons paramètres (agent, model, exerciseId)

#### board.js
- **Fonction `_coachRenderMistralBubbleWithAgent`** : Ajout des boutons de notation 1/0 pour les bulles Mistral
- **Fonction `_coachRenderMistralThinking`** : Amélioration pour éviter les doublons
- **Fonction `_coachRemoveMistralThinking`** : Correction pour supprimer par exerciseId

### 2. Script Python (scripts/coach_ratings_report.py)

- **Fonction `get_coach_calls_log`** : Modifiée pour lire tous les fichiers `coach_calls*.log` (y compris les archives mensuelles) comme le fait la fonction `coachlog` d'Alain

## Tests effectués

- [ ] Simulation des cas : (a) Mistral avant Claude, (b) Claude avant Mistral, (c) erreur Mistral, (d) aucune réponse de Mistral, (e) changement d'exercice
- [ ] Vérification de l'arbre DOM pour confirmer deux bulles distinctes
- [ ] Vérification des boutons 1/0 sous chaque bulle
- [ ] Test du script de bilan avec des logs mensuels simulés

## Fichiers modifiés

- static/exercise.js
- static/board.js  
- scripts/coach_ratings_report.py
