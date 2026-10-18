# Issue #113 : Mistral réellement en parallèle de Claude, auteur identifié sur chaque avis et note 1/0 pour la comparaison

## Modifications

### Problème résolu

L'issue #112 avait ajouté un second avis (Mistral) en mode exercices, mais l'implémentation
n'était **séquentielle** et non parallèle : l'appel à Mistral n'était lancé qu'**APRÈS**
l'obtention de la réponse de Claude, puis attendu sur place (`future.result` avec timeout)
avant l'unique `emit` de l'événement `exercise_comment`. Conséquences :
- Les deux latences s'additionnaient
- Le commentaire de Claude n'apparaissait qu'une fois Mistral terminé
- Contradiction avec la consigne de #112 (Claude jamais retardé par Mistral)

### Solution implémentée

#### 1. Appels vraiment parallèles (point 1)
- **app.py** : Mistral est maintenant lancé **avant** d'attendre la réponse de Claude
- La session SocketIO (`request.sid`) est capturée avant de lancer le thread Mistral
- Les deux appels tournent en parallèle sans se bloquer mutuellement

#### 2. Événements séparés (points 2-3)
- Dès que Claude répond, `exercise_comment` est émis **immédiatement** avec :
  - Le texte de Claude
  - Un `exercise_id` unique (UUID) pour identifier la réponse
  - Un champ `agent: "claude"` et `model` pour l'étiquetage
  - **Sans** les champs `mistral_*` (supprimés de cet événement)
- Quand Mistral répond (succès ou erreur), un **nouvel événement** `exercise_mistral_comment`
  est émis vers la même session via `socketio.emit(..., room=session_sid)` avec :
  - `exercise_id` (pour la détection des réponses obsolètes)
  - `text` ou `error`
  - `log_id`, `model`, `fen`, `coup_propose`

#### 3. Gestion des réponses obsolètes (point 5)
- **Côté client** (`static/exercise.js`) :
  - Un `exerciseCurrentId` mémorise l'exercice en cours
  - Chaque événement (`exercise_comment` et `exercise_mistral_comment`) porte un `exercise_id`
  - Si un événement arrive avec un `exercise_id` différent de `exerciseCurrentId`, il est **ignoré**
  - Cela couvre le cas où Alain change d'exercice ou utilise "Reprendre mon coup" entre-temps

#### 4. Affichage avec auteur identifié (point 4)
- **Nouveaux styles CSS** (`static/board.css`) :
  - Couleurs neutres pour les bulles Mistral : bordure `var(--cc-border)` (brun foncé)
    au lieu de `#0066cc` (bleu cliquable) → point 7 respecté
  - Bordure d'erreur : `var(--cc-border-error)` (brun foncé) au lieu de `#cc0000` (rouge)
  - Ajout de `--cc-border`, `--cc-border-error`, `--cc-success`, `--cc-error` dans `:root`
  - Nouvelles classes : `.coach-bubble-header`, `.coach-agent`, `.coach-model`
  - Boutons de notation : `.coach-rating`, `.rating-btn`, `.rating-btn.selected`

- **Nouveaux éléments UI** (`static/board.js`) :
  - `_coachRenderBubbleWithAgent()` : bulle avec en-tête (auteur + modèle) et boutons de notation
  - `_coachRenderMistralBubbleWithAgent()` : bulle Mistral avec auteur et notation
  - `_coachRenderMistralErrorWithAgent()` : erreur Mistral avec auteur
  - `_coachRenderMistralThinking()` : indicateur "Mistral réfléchit…"
  - `_coachRemoveMistralThinking()` : suppression de l'indicateur
  - `_coachRatingClick()` : gestion du clic sur les boutons 1/0
  - `_coachSendRating()` : envoi de la note au serveur via SocketIO
  - `_coachSendRatingFallback()` : repli localStorage si serveur indisponible

- **Mise à jour de `static/exercise.js`** :
  - Gestionnaire `socket.on("exercise_mistral_comment")` pour l'événement séparé
  - Affichage de l'indicateur "Mistral réfléchit…" dès que `exercise_comment` arrive
  - Mémorisation de `exerciseCurrentId` pour la détection des réponses obsolètes
  - Appel à `_coachRenderBubbleWithAgent()` pour Claude avec `agent: "claude"`

#### 5. Notation 1/0 (points 9-10)
- **Côté client** :
  - Deux boutons "1" (bonne réponse) et "0" (moins bonne) sous chaque avis
  - Infobulle explicite sur chaque bouton
  - Style terracotta **autorisé** pour ces éléments cliquables (point 9)
  - État sélectionné visible (classe `.selected`)
  - Note modifiable : re-cliquer désélectionne (pas de note)

- **Côté serveur** (`coach_ratings.py`, nouveau module) :
  - `record_rating(agent, model, rating, log_id, fen, coup_propose, mode)` :
    - Enregistre dans `data/coach_ratings.jsonl` (format JSONL, une ligne par note)
    - Si une note existe déjà pour le même `(agent, log_id)`, elle est **remplacée**
    - `rating=None` supprime la note existante
  - `get_all_ratings()` : lit toutes les notes
  - `get_ratings_summary()` : retourne les totaux par agent et la liste des divergences

- **Nouvel endpoint SocketIO** (`app.py`) :
  - `socket.on("coach_rating")` : reçoit les notes du client
  - Appel à `coach_ratings.record_rating()` pour l'enregistrement
  - Émet `coach_rating_ack` ou `coach_rating_error` en réponse

#### 6. Script CLI de bilan (point 11)
- **Nouveau script** : `scripts/coach_ratings_report.py`
  - Lit `data/coach_ratings.jsonl`
  - Affiche :
    - Total de 1 et de 0 par agent (Claude et Mistral)
    - Liste des cas divergents avec :
      - Position (FEN)
      - Coup joué
      - Texte des deux avis (récupéré depuis `coach_calls.log` via `log_id`)
  - Format copiable dans une conversation pour analyse
  - Même esprit que `coachlog`

#### 7. Second emit exercise_comment (point 6)
- Vérification du code : il existe un second `emit("exercise_comment")` dans
  `_on_exercise_answer_lichess()` (ligne ~2523)
- Ce chemin concerne **uniquement les problèmes Lichess** (source "lichess"), pas le
  mode exercice standard
- **Aucune modification** apportée à ce chemin : il ne concerne que Claude, pas Mistral
- Ce second emit reste donc tel quel

### Comportement final

#### Avec MISTRAL_API_KEY configurée
1. En mode exercice, après qu'Alain joue son coup :
   - Les deux appels (Claude et Mistral) sont lancés **en parallèle**
   - Le commentaire de Claude s'affiche **immédiatement** (sans attendre Mistral)
   - Un indicateur "Mistral réfléchit…" apparaît
   - Le commentaire de Mistral s'affiche dès qu'il arrive, **dans l'ordre d'arrivée**
   - Chaque bulle porte clairement son auteur ("Claude" ou "Mistral") avec le modèle en petit
   - Les boutons 1/0 permettent de noter chaque avis

2. Si Mistral répond en premier :
   - Mistral s'affiche en premier, puis Claude
   - L'ordre est respecté, les deux avis sont clairement étiquetés

3. En cas d'erreur côté Mistral :
   - Un message discret s'affiche dans une bulle Mistral avec l'auteur
   - Le commentaire de Claude reste affiché normalement

4. Si Alain change d'exercice avant que Mistral ne réponde :
   - La réponse de Mistral est **ignorée** (exercise_id différent)

#### Sans MISTRAL_API_KEY ou clé vide
- Aucun appel à Mistral n'est effectué (comportement inchangé depuis #112)
- Aucun indicateur "Mistral réfléchit…" n'apparaît
- L'application se comporte exactement comme avant (seul Claude répond)

### Fichiers modifiés
- **app.py** : +~150 lignes (appel parallèle Mistral, événement séparé, gestion exercise_id, endpoint rating)
- **static/exercise.js** : +~50 lignes (gestionnaire exercise_mistral_comment, exerciseCurrentId, indicateur thinking)
- **static/board.js** : +~350 lignes (nouvelles fonctions d'affichage avec auteur et notation)
- **static/board.css** : +~100 lignes (nouvelles classes pour l'en-tête, les boutons de notation, couleurs neutres)

### Fichiers créés
- **coach_ratings.py** : module de gestion des notes (180 lignes)
- **scripts/coach_ratings_report.py** : script CLI de bilan (170 lignes)
- **test_issue113.py** : tests de simulation (300 lignes)

### Vérification effectuée

#### Par simulation (test_issue113.py)
- ✅ Module coach_ratings : enregistrement, modification, suppression des notes
- ✅ Script de rapport : calcul des totaux et détection des divergences
- ✅ Logique exercise_id : détection des réponses obsolètes
- ✅ Ordre d'affichage : dépend de qui répond en premier

#### Par compilation
- ✅ `python3 -m py_compile app.py llm_coach.py config.py coach_ratings.py scripts/coach_ratings_report.py` : OK

#### Non testé (nécessite exécution réelle)
- Appel parallèle réel à Mistral et Claude (nécessite clés API valides)
- Émission SocketIO vers la bonne session depuis un thread d'arrière-plan
- Affichage UI complet avec les nouveaux styles et interactions
- Intégration avec le flux existant (autres modes que l'exercice)

### Respect des consignes

| Point | Consigne | Statut |
|-------|----------|--------|
| 1 | Mistral lancé au même moment que Claude | ✅ |
| 2 | exercise_comment émis dès Claude répond, sans attendre Mistral | ✅ |
| 3 | Avis Mistral via événement séparé vers la même session | ✅ |
| 4 | Chaque avis affiché dès qu'il arrive, avec auteur identifié | ✅ |
| 5 | Réponse obsolète ignorée après changement d'exercice | ✅ |
| 6 | Second emit exercise_comment (Lichess) vérifié et laissé tel quel | ✅ |
| 7 | Couleurs neutres (pas de bleu cliquable, pas de terracotta) | ✅ |
| 8 | Journalisation, timeout HTTP, comportement sans clé inchangés | ✅ |
| 9 | Boutons 1/0 sous chaque avis avec infobulle | ✅ |
| 10 | Notes enregistrées dans data/coach_ratings.jsonl | ✅ |
| 11 | Script CLI scripts/coach_ratings_report.py créé | ✅ |
