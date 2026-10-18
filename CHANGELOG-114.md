# Issue #114 : Suite #113 - l'avis de Mistral arrivé avant celui de Claude ne doit pas être jeté comme obsolète

## Diagnostic
**Confirmé** : Le défaut décrit dans l'issue existait bien.

Dans l'implémentation de l'issue #113 :
- `exerciseCurrentId` côté client (static/exercise.js) n'était mis à jour **que** lors de la réception du commentaire de Claude (événement `exercise_comment`)
- Le contrôle d'obsolescence pour Mistral (dans le gestionnaire `exercise_mistral_comment`) vérifiait si `exerciseId !== exerciseCurrentId`
- **Problème** : Si Mistral répondait **avant** Claude, `exerciseCurrentId` était encore `null` ou contenait l'ID de l'exercice précédent → la réponse de Mistral était ignorée comme obsolète

## Solution implémentée

### Côté client (static/exercise.js)
1. **Ajout de la génération d'UUID côté navigateur** :
   - Nouvelle fonction `_generateExerciseId()` qui utilise `crypto.randomUUID()` si disponible, avec fallback manuel
   - Génération de l'`exercise_id` **au moment de l'envoi de la réponse** (`socket.emit("exercise_answer", ...)`)
   - Mémorisation **immédiate** dans `exerciseCurrentId` avant l'envoi

2. **Modifications des appels `exercise_answer`** :
   - Premier appel (lignes ~1013) : inclut `exercise_id: newExerciseId` et mémorise dans `exerciseCurrentId`
   - Appel de réessai (lignes ~1071) : réutilise le même `exercise_id: exerciseCurrentId`

3. **Réinitialisation appropriée** :
   - Dans `exercise_position` : `exerciseCurrentId = null` pour chaque nouvel exercice
   - Dans `abandonExerciseGame` : `exerciseCurrentId = null` pour nettoyer l'état
   - **Non réinitialisé** dans `reprendreExerciceCoup` : conserve le même ID pour le même exercice

4. **Suppression de la redondance** :
   - Suppression de la ligne `exerciseCurrentId = exerciseId` dans le gestionnaire `exercise_comment` (devient redondant)

5. **Gestion des erreurs** :
   - Dans `exercise_error` : suppression de l'indicateur "Mistral réfléchit..." si un `exercise_id` est présent

### Côté serveur (app.py)
1. **Extraction de l'`exercise_id` du client** :
   - Dans `on_exercise_answer` : extraction de `exercise_id` des données client
   - Si non fourni (compatibilité avec anciens clients) : génération par le serveur avec `uuid.uuid4()`

2. **Transmission dans tous les événements** :
   - `exercise_comment` : inclut `exercise_id` (déjà présent, vérifié)
   - `exercise_mistral_comment` : inclut `exercise_id` (déjà présent, vérifié)
   - `exercise_error` : inclut `exercise_id` (ajouté)

3. **Modification de `_on_exercise_answer_lichess`** :
   - Signature modifiée pour accepter `exercise_id` comme paramètre
   - Appel modifié pour passer l'`exercise_id` extrait/généré
   - Émission `exercise_comment` inclut `exercise_id`

## Comportement vérifié

### Tests de simulation (test_issue114.py)
Tous les cas demandés dans l'issue ont été vérifiés :

✅ **(a) Mistral répond avant Claude** : Son avis s'affiche correctement
- L'`exercise_id` est généré et mémorisé **avant** l'envoi
- Le contrôle d'obsolescence accepte la réponse de Mistral
- Le contrôle accepte ensuite la réponse de Claude

✅ **(b) Claude répond avant Mistral** : Les deux avis s'affichent
- Même mécanisme : l'`exercise_id` est déjà connu avant toute réponse

✅ **(c) Réponse de Mistral de l'exercice précédent arrive après passage au suivant** : Elle est ignorée
- Le changement d'exercice réinitialise `exerciseCurrentId`
- Le contrôle détecte la différence d'ID et ignore la réponse obsolète

✅ **(d) Cas d'erreur Mistral** : Le message d'erreur s'affiche
- L'`exercise_id` est inclus dans l'événement `exercise_error`
- L'indicateur "Mistral réfléchit..." est correctement nettoyé

### Vérifications supplémentaires

✅ **"Reprendre mon coup"** : L'`exerciseCurrentId` est conservé (même exercice)
✅ **Changement d'exercice** : L'`exerciseCurrentId` est réinitialisé à `null`
✅ **Indicateur "Mistral réfléchit..."** : N'est pas affiché pour un exercice abandonné dans le suivant

## Compatibilité

- **Ancien chemin** : Si un client ancien n'envoie pas d'`exercise_id`, le serveur en génère un comme avant
- **Nouveau chemin** : Les clients modernes (avec cette correction) envoient et utilisent leur propre `exercise_id`
- **Aucune modification** des autres aspects de l'issue #113 (notation 1/0, journalisation, couleurs)

## Fichiers modifiés

- `static/exercise.js` : +45 lignes, -11 lignes
  - Ajout `_generateExerciseId()`
  - Modification des appels `socket.emit("exercise_answer", ...)`
  - Réinitialisation dans `exercise_position` et `abandonExerciseGame`
  - Suppression de la redondance dans `exercise_comment`
  - Gestion dans `exercise_error`

- `app.py` : +12 lignes, -5 lignes
  - Extraction/génération de `exercise_id` dans `on_exercise_answer`
  - Transmission dans `exercise_error`
  - Modification de `_on_exercise_answer_lichess`

## Ce qui n'a pas pu être testé en conditions réelles

- **Intégration complète avec Socket.IO** : Les tests de simulation vérifient la logique, mais l'intégration réelle avec le serveur Socket.IO et les appels API réels à Claude/Mistral n'a pas été testée (nécessite un environnement complet avec clés API)
- **Navigation privée sans crypto.randomUUID** : Le fallback manuel n'a pas été testé dans un navigateur sans support de `crypto.randomUUID`
- **Concurrences réseau extrêmes** : Les délais réseau variables et les conditions de course réelles n'ont pas été testés (seulement simulés)
