# Issue #115 : Suite #113 - Corrections des bulles coach et indicateur Mistral

## Problèmes identifiés

1. **Bulles coach écrasées** : Les avis de Mistral et Claude partageaient la même bulle, causant l'affichage de l'auteur "Mistral" avec le modèle "claude" et le texte de Claude.

2. **Indicateur persistant** : L'indicateur "Mistral réfléchit..." n'était jamais retiré quand Mistral répondait avant Claude.

3. **Script de bilan incomplet** : `scripts/coach_ratings_report.py` ne lisait que `coach_calls.log` et non les archives mensuelles.

## Cause racine identifiée

**Bulles écrasées** : Le code original réutilisait la même bulle pour les deux agents. Quand Claude répondait, il affichait son avis dans une bulle, puis quand Mistral répondait, il réécrivait la même bulle avec son texte, mais l'en-tête (auteur) restait celui de la première bulle créée.

**Indicateur persistant** : L'indicateur "Mistral réfléchit..." était affiché à la réception du commentaire de Claude (sans vérifier si Mistral avait déjà répondu), et n'était jamais supprimé si Mistral répondait avant Claude. De plus, il n'y avait pas de timeout pour le supprimer si Mistral ne répondait pas.

**Script de bilan** : La fonction `get_coach_calls_log` ne lisait que le fichier `coach_calls.log` et ignorait les archives mensuelles `coach_calls-AAAA-MM.log`.

## Corrections apportées

### 1. Fichiers JavaScript (static/exercise.js et static/board.js)

#### exercise.js
- **Variables globales** : Ajout de `exerciseMistralResponded` (tracker par exerciseId) et `exerciseMistralThinkingTimeoutId` avec constante `EXERCISE_MISTRAL_THINKING_TIMEOUT_MS = 45000` (45s, cohérent avec timeout HTTP)
- **Fonctions utilitaires** : Ajout de `_exerciseClearMistralThinkingTimeout()` et `_exerciseStartMistralThinkingTimeout(exerciseId)` pour gérer le timeout de l'indicateur
- **Handler `exercise_comment`** (réponse Claude) : Vérification `!exerciseMistralResponded[exerciseId]` avant d'afficher l'indicateur, sinon suppression de l'indicateur existant. Démarrage du timeout si Mistral n'a pas encore répondu.
- **Handler `exercise_mistral_comment`** : Marquage `exerciseMistralResponded[exerciseId] = true`, suppression de l'indicateur et du timeout à la réception de la réponse Mistral
- **Handler `exercise_error`** : Nettoyage de l'indicateur et du timeout en cas d'erreur
- **Fonctions de cycle de vie** : Nettoyage systématique dans `startExercise()`, `reprendreExerciceCoup()`, `abandonExerciseGame()`, `exerciseRetryAnalysis()`

#### board.js
- **`_coachRenderBubbleWithAgent`** : Ajout des datasets `logId`, `fen`, `coupPropose` sur la bulle et les boutons 1/0 pour permettre la notation avec toutes les métadonnées nécessaires
- **`_coachRenderMistralBubbleWithAgent`** : Déjà présente (issue #113), vérifiée pour utiliser correctement tous les paramètres (text, model, exerciseId, logId, fen, coupPropose) et créer une bulle distincte avec en-tête "Mistral" et boutons 1/0
- **`_coachRenderMistralThinking`** : Ajout de `_coachRemoveMistralThinking(exerciseId)` avant création pour éviter les doublons
- **`_coachRemoveMistralThinking`** : Correction pour supprimer par `exerciseId` (déjà fonctionnelle)
- **`_coachRenderMistralTimeoutMessage`** : Nouvelle fonction pour afficher "Mistral n'a pas répondu." après le délai de 45s

### 2. Script Python (scripts/coach_ratings_report.py)

- **Nouvelle fonction `_get_coach_calls_files()`** : Retourne tous les fichiers `coach_calls*.log` (y compris archives mensuelles) via `Path.glob(f"{log_base.stem}*{log_base.suffix}")`
- **Fonction `get_coach_calls_log()`** : Modifiée pour itérer sur tous les fichiers retournés par `_get_coach_calls_files()` au lieu de ne lire que `config.COACH_CALLS_LOG_PATH`. Gère l'absence de fichiers sans échouer.

## Vérifications effectuées (analyse statique du code)

### Structure des bulles
- [x] **Bulles distinctes** : Claude utilise `_coachRenderBubbleWithAgent` (classe `coach-bubble assistant`) et Mistral utilise `_coachRenderMistralBubbleWithAgent` (classe `coach-bubble mistral`) → deux bulles visuellement et structurellement distinctes
- [x] **En-tête correct** : Claude affiche "Claude" ou "Mistral" selon `agent`, Mistral affiche toujours "Mistral" → correspond à l'auteur réel
- [x] **Modèle affiché** : Les deux bulles affichent le modèle dans l'en-tête (ex: "claude-sonnet-5", "mistral-large-latest")

### Boutons de notation 1/0
- [x] **Présents sur les deux bulles** : Les deux fonctions de rendu ajoutent les boutons 1/0 avec la classe `coach-rating`
- [x] **Métadonnées complètes** : Les boutons ont `dataset.agent`, `dataset.model`, `dataset.exerciseId`, `dataset.logId`, `dataset.fen`, `dataset.coupPropose` pour les deux agents
- [x] **Gestionnaire de clic** : `_coachRatingClick` utilise ces datasets pour enregistrer la note avec le bon agent

### Gestion de l'indicateur "Mistral réfléchit..."
- [x] **Pas d'affichage si Mistral a déjà répondu** : Vérification `!exerciseMistralResponded[exerciseId]` avant affichage
- [x] **Suppression à la réponse Mistral** : `exerciseMistralResponded[exerciseId] = true` + `_coachRemoveMistralThinking(exerciseId)` dans le handler `exercise_mistral_comment`
- [x] **Suppression à la réponse Claude (si Mistral déjà répondu)** : Branche `else if` dans le handler `exercise_comment`
- [x] **Suppression en cas d'erreur** : Dans le handler `exercise_error`
- [x] **Suppression au changement d'exercice** : Dans `startExercise()`, `reprendreExerciceCoup()`, `abandonExerciseGame()`
- [x] **Timeout de 45s** : Démarré quand Claude répond et Mistral n'a pas encore répondu, affiche "Mistral n'a pas répondu." si pas de réponse
- [x] **Pas de doublons** : `_coachRenderMistralThinking` appelle `_coachRemoveMistralThinking(exerciseId)` avant création
- [x] **Un seul indicateur à la fois** : Le tracker `exerciseMistralResponded` est par exerciseId, et `_coachRemoveMistralThinking(null)` supprime tous les indicateurs

### Cas d'usage validés par analyse de code

- [x] **(a) Mistral avant Claude** : Mistral répond → `exerciseMistralResponded[exerciseId] = true` → quand Claude répond, l'indicateur n'est pas affiché (car Mistral a déjà répondu) → deux bulles distinctes visibles
- [x] **(b) Claude avant Mistral** : Claude répond → indicateur affiché + timeout démarré → Mistral répond → indicateur supprimé + timeout annulé → deux bulles distinctes visibles
- [x] **(c) Erreur Mistral** : Erreur reçue → `_coachRenderMistralErrorWithAgent` appelé + indicateur et timeout supprimés → bulle d'erreur visible
- [x] **(d) Aucune réponse de Mistral** : Claude répond → indicateur + timeout démarré → après 45s, timeout callback vérifie `!exerciseMistralResponded[exerciseId]` → affiche message "Mistral n'a pas répondu."
- [x] **(e) Changement d'exercice pendant l'attente** : `startExercise()` appelé → `_exerciseClearMistralThinkingTimeout()` + `_coachRemoveMistralThinking(null)` + `exerciseMistralResponded = {}` → tout est nettoyé

### Script de bilan
- [x] **Lecture de tous les fichiers** : `_get_coach_calls_files()` utilise `glob` avec pattern `coach_calls*.log` → match `coach_calls.log` et `coach_calls-AAAA-MM.log`
- [x] **Gestion de l'absence du fichier principal** : Boucle `for log_path in log_files` avec `if os.path.exists(log_path)` → pas d'erreur si `coach_calls.log` est absent
- [x] **Ordre de lecture** : `sorted(..., key=lambda p: p.name)` → lecture dans l'ordre alphabétique (fichiers mensuels avant le fichier principal si nommé différemment)

## Points non testés en conditions réelles

- Exécution réelle du frontend avec Socket.IO pour vérifier le timing exact des événements
- Affichage visuel des bulles dans un navigateur (CSS, responsive design)
- Persistance des données de notation dans `coach_ratings.jsonl`
- Intégration complète avec le backend (appels API Mistral/Claude)

## Fichiers modifiés

- static/exercise.js
- static/board.js  
- scripts/coach_ratings_report.py
