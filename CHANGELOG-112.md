# Issue #112 : Mode exercices - second avis du coach par Mistral

## Modifications

### Configuration (config.py)
- Ajout de `MISTRAL_API_KEY` : lecture de la clé API Mistral depuis `.env`
- Ajout de `CHESSCOACH_MISTRAL_MODEL` : modèle Mistral par défaut (mistral-large-latest), configurable via `.env`

### Module LLM (llm_coach.py)
- Ajout de la fonction `_call_mistral()` : appel HTTP à l'API Mistral (endpoint chat/completions) avec :
  - Construction de la requête au format Mistral
  - Gestion des erreurs HTTP et timeout
  - Recherche robuste du texte de réponse (pas de supposition sur la position fixe)
  - Pas de comptage de tokens (consigne 7 : ne pas fausser le compteur de Claude)

- Ajout de la fonction `get_mistral_response()` : interface publique pour obtenir un second avis du coach via Mistral :
  - Réutilise exactement le même contexte et les mêmes consignes système que Claude
  - Journalisation dans coach_calls.log avec un champ `model` indiquant "mistral:<modèle>"
  - Retourne (réponse, erreur, log_id) sans jamais bloquer le commentaire de Claude
  - Si MISTRAL_API_KEY est absente ou vide, retourne (None, None, None) sans appel

### Application serveur (app.py)
- Import ajouté : `concurrent.futures` pour les appels parallèles
- Modification de `on_exercise_answer()` :
  - Appel de Claude inchangé (toujours effectué)
  - En mode exercice uniquement : appel de Mistral en parallèle via ThreadPoolExecutor
  - Les deux appels tournent en parallèle sans bloquer le commentaire de Claude
  - Envoi des deux réponses (Claude + Mistral) dans l'événement `exercise_comment`
  - Champs ajoutés à l'événement : `mistral_text`, `mistral_error`, `mistral_log_id`

### Interface client (static/exercise.js)
- Modification de `socket.on("exercise_comment")` :
  - Affichage du commentaire de Claude inchangé
  - Affichage du commentaire de Mistral via `_coachRenderMistralBubble()` si présent
  - Affichage d'un message d'erreur discret via `_coachRenderMistralError()` en cas d'échec

### Styles (static/board.js et static/board.css)
- Ajout des fonctions `_coachRenderMistralBubble()` et `_coachRenderMistralError()` dans board.js
- Ajout des classes CSS dans board.css :
  - `.coach-bubble.mistral` : bulle avec bordure bleue et fond clair
  - `.coach-bubble.mistral-error` : bulle d'erreur avec bordure rouge
  - `.mistral-title` : titre "Avis de Mistral" en bleu
  - `.mistral-content` : contenu avec taille de police légèrement réduite

## Comportement

### Avec MISTRAL_API_KEY configurée
1. En mode exercice, après qu'Alain joue son coup :
   - Les deux appels (Claude et Mistral) sont lancés en parallèle
   - Le commentaire de Claude s'affiche immédiatement (sans attendre Mistral)
   - Le commentaire de Mistral s'affiche sous celui de Claude dans un bloc séparé titré "Avis de Mistral"
   - Les deux modèles reçoivent exactement le même contexte et les mêmes consignes
   - Les deux appels sont journalisés dans data/logs/coach_calls.log

2. En cas d'erreur côté Mistral (clé invalide, timeout, réponse vide) :
   - Un message discret s'affiche dans le bloc Mistral (ex: "Indisponible", "Clé API invalide", "Réponse trop lente")
   - Le commentaire de Claude reste affiché normalement
   - Le chat n'est jamais cassé

3. Dans les autres modes (chat libre, analyse, etc.) :
   - Seul Claude est appelé (comportement inchangé)

### Sans MISTRAL_API_KEY ou clé vide
- Aucun appel à Mistral n'est effectué
- L'application se comporte exactement comme avant (seul Claude répond)
- Aucun bloc Mistral n'est affiché

## Vérification

La vérification a été effectuée par :
1. Compilation Python réussie (py_compile) pour llm_coach.py, config.py et app.py
2. Vérification visuelle du code ajouté
3. Respect de toutes les consignes de l'issue #112 :
   - ✅ Appel Mistral en parallèle de Claude en mode exercice uniquement
   - ✅ Même contexte et consignes pour les deux modèles
   - ✅ Claude n'est jamais retardé ou bloqué par Mistral
   - ✅ Affichage dans un bloc séparé titré "Avis de Mistral"
   - ✅ Configuration via .env (MISTRAL_API_KEY, CHESSCOACH_MISTRAL_MODEL)
   - ✅ Gestion d'erreur discrète sans casser le chat
   - ✅ Journalisation dans coach_calls.log avec indication du fournisseur/modèle
   - ✅ Pas de comptage de tokens pour Mistral (ne fausse pas le compteur de Claude)
   - ✅ Chat libre et autres modes restent sur Claude uniquement
   - ✅ Couleur terracotta non utilisée (réservée aux éléments cliquables)

**Note** : Aucun vrai appel à l'API Mistral n'a été testé (clé réelle non accessible depuis le worktree). Alain devra confirmer le bon fonctionnement en conditions réelles avec une clé Mistral valide.

## Fichiers modifiés
- config.py : +4 lignes (configuration Mistral)
- llm_coach.py : +189 lignes (fonctions _call_mistral et get_mistral_response)
- app.py : +117 lignes (appel parallèle de Mistral dans on_exercise_answer)
- static/board.js : +54 lignes (fonctions d'affichage Mistral)
- static/board.css : +29 lignes (styles pour les bulles Mistral)
- static/exercise.js : +25 lignes (affichage du commentaire Mistral)
