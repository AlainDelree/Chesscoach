# Issue #120 : Affichage des alertes du vérificateur d'affirmations sous les avis

## Contexte
L'issue #117 a ajouté un vérificateur déterministe (`fact_checker.py`) qui contrôle les affirmations factuelles des avis de Claude et Mistral en mode exercices et enregistre ses résultats dans `coach_calls*.log`. Cependant, les alertes n'étaient pas affichées à l'utilisateur dans l'interface.

## Constat initial
- **Claude** : Les alertes du vérificateur étaient ajoutées à `fiabilite["alertes"]` et transmises au client via l'événement `exercise_comment`, mais **n'étaient pas affichées** sous la bulle.
- **Mistral** : Les alertes du vérificateur étaient calculées mais **n'étaient pas transmises au client** (seulement enregistrées dans les logs).

## Modifications apportées

### 1. Backend (Python)

#### `llm_coach.py`
- Modifié `get_mistral_response()` pour retourner un 4ème élément : `fact_checker_alertes`
  - Signature : `(réponse_mistral, erreur_mistral, log_id_mistral, fact_checker_alertes)`
  - En cas d'erreur ou de clé API manquante : retourne `[]` pour les alertes
  - En cas de succès : retourne la liste des alertes calculées par le vérificateur

#### `app.py`
- Modifié `call_mistral_and_emit()` dans `on_exercise_answer()` pour :
  - Recevoir `mistral_fact_checker_alertes` de `get_mistral_response()`
  - Transmettre `fact_checker_alertes` dans l'événement `exercise_mistral_comment`
  - En cas d'exception : transmettre une liste vide `[]`

### 2. Frontend (JavaScript)

#### `static/board.js`
- Ajouté `_coachFormatFactCheckerAlertes(alertes)` : fonction utilitaire qui :
  - Filtre et formate les alertes du vérificateur
  - Gère les deux formats : `fiabilite.alertes` (Claude) et `fact_checker_alertes` direct (Mistral)
  - Retourne un élément DOM `div.coach-fact-checker-alerts` ou `null` si aucune alerte
  - Affiche chaque alerte sous la forme : `"à vérifier ({agent}) : {affirmation}"`

- Modifié `_coachRenderBubbleWithAgent()` pour :
  - Extraire les alertes `fact_checker` de `fiabilite.alertes`
  - Appeler `_coachFormatFactCheckerAlertes()` et insérer le résultat sous le contenu

- Modifié `_coachRenderMistralBubbleWithAgent()` pour :
  - Accepter un nouveau paramètre `factCheckerAlertes`
  - Appeler `_coachFormatFactCheckerAlertes()` et insérer le résultat sous le contenu

#### `static/exercise.js`
- Modifié le handler `socket.on("exercise_mistral_comment")` pour :
  - Extraire `data.fact_checker_alertes`
  - Passer les alertes à `_coachRenderMistralBubbleWithAgent()`

### 3. Styles (CSS)

#### `static/board.css`
- Ajouté les styles pour `.coach-fact-checker-alerts` et `.coach-fact-checker-alert` :
  - Style neutre (gris moyen `#555`, pas de terracotta)
  - Taille légèrement réduite (`0.85rem`)
  - Espacement serré (`margin-top: 4px`, `margin-bottom: 2px`)
  - Lisible sur mobile (`word-break: break-word`, `max-width: 100%`)

## Comportement final

### Affichage des alertes
- **Avec alertes** : Une mention discrète `"à vérifier ({agent}) : {affirmation}"` apparaît sous la bulle de l'avis concerné, une ligne par alerte
- **Sans alertes** : Aucune mention n'apparaît
- **Vérificateur désactivé** : Aucune alerte n'est générée, aucune mention n'apparaît
- **Erreur interne du vérificateur** : L'erreur est consignée dans les logs, aucune mention n'apparaît, l'avis n'est pas affecté

### Ordre d'arrivée
- Les alertes sont calculées **avant** l'émission de l'événement (pas d'appel réseau supplémentaire)
- Le vérificateur ne retarde **pas** l'affichage de l'avis
- L'ordre d'arrivée des avis (Claude puis Mistral, ou inversement) est préservé

### Intégration visuelle
- Les alertes s'insèrent **sous le contenu** de la bulle
- **Ne perturbent pas** : l'étiquette d'auteur, les boutons de note 1/0, ni la pastille de fiabilité
- Style cohérent entre Claude et Mistral

## Tests effectués

### Simulation DOM
- ✓ Avis de Claude avec alertes : 2 alertes affichées sous la bulle
- ✓ Avis de Mistral avec alertes : 1 alerte affichée sous la bulle
- ✓ Avis sans alertes : aucune mention affichée
- ✓ Vérificateur désactivé : aucune alerte générée

### Validation syntaxique
- ✓ Python : `llm_coach.py` et `app.py` compilent sans erreur
- ✓ JavaScript : `static/board.js` et `static/exercise.js` valides
- ✓ HTML : fichier de test valide

## Fichiers modifiés
- `llm_coach.py` : signature et retour de `get_mistral_response()`
- `app.py` : transmission des alertes dans `exercise_mistral_comment`
- `static/board.js` : fonctions d'affichage des alertes
- `static/exercise.js` : passage des alertes à la fonction de rendu
- `static/board.css` : styles pour les alertes

## Points d'attention
- Le vérificateur est **uniquement actif en mode exercice** (`mode_exercice` dans le contexte)
- Le vérificateur peut être **désactivé** via `CHESSCOACH_FACT_CHECKER_ACTIVATED=0` dans `.env`
- Les alertes sont **déterministes** (aucun appel à un modèle, uniquement python-chess)
- Le texte de l'avis **n'est jamais modifié, masqué ni raccourci**
