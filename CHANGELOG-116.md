# Issue #116 : Température configurable pour Claude et Mistral en mode exercices

## Contexte
Pour comparer honnêtement Claude et Mistral sur les exercices, les deux IA doivent tourner dans des conditions connues et, si possible, identiques. Aujourd'hui l'appel à Mistral envoyait une température fixe de 0,0 (écrite en dur dans la requête construite par la fonction d'appel Mistral de llm_coach.py), alors que l'appel à Claude n'envoyait aucune température : il utilisait donc la valeur par défaut de l'API, nettement plus élevée. Le journal coach_calls ne gardait aucune trace de la température utilisée, ce qui rendait les futures séries impossibles à comparer si on change un réglage.

## Modifications apportées

### 1. Configuration (config.py)
- Ajout de `CHESSCOACH_CLAUDE_TEMPERATURE` : variable d'environnement pour configurer la température des appels à Claude en mode exercice. Si absente ou vide, aucun paramètre n'est envoyé (comportement strictement identique à aujourd'hui, l'API utilise sa valeur par défaut).
- Ajout de `CHESSCOACH_MISTRAL_TEMPERATURE` : variable d'environnement pour configurer la température des appels à Mistral. Valeur par défaut : "0.0" (comportement actuel). Une valeur invalide (non numérique, hors plage acceptée) est ignorée avec un avertissement dans les logs, et la valeur par défaut s'applique.

### 2. Appels API (llm_coach.py)

#### _call_claude
- Ajout du paramètre optionnel `temperature: float = None`
- Si `temperature` est fourni (non None), il est inclus dans le body de la requête comme paramètre "temperature"
- Documentation mise à jour pour refléter ce nouveau paramètre

#### _call_mistral
- Modification du paramètre `temperature` de valeur fixe 0.0 à paramètre optionnel avec valeur par défaut 0.0
- La température est maintenant passable depuis l'appelant
- Documentation mise à jour

#### _log_coach_call
- Ajout du paramètre optionnel `temperature: str = None`
- Le champ `temperature` est maintenant inclus dans chaque entrée de journal
- Documentation mise à jour pour expliquer que ce champ permet de tracer les conditions exactes de chaque appel

#### get_coach_response
- Lecture de `config.CHESSCOACH_CLAUDE_TEMPERATURE` si `mode_origine == "exercice"`
- Validation de la valeur : si invalide (non convertible en float), un avertissement est loggé et la température est mise à None
- Passage de la température à `_call_claude` et à `_log_coach_call`
- La température à logger est "defaut API" si None, sinon la valeur numérique

#### get_mistral_response
- Lecture de `config.CHESSCOACH_MISTRAL_TEMPERATURE`
- Validation de la valeur : si invalide, un avertissement est loggé et la valeur par défaut 0.0 est utilisée
- Passage de la température à `_call_mistral` et à `_log_coach_call`

### 3. Script de bilan (scripts/coach_ratings_report.py)
- Modification de `get_text_for_log_id` pour retourner un tuple (texte, temperature)
- Mise à jour de l'affichage des divergences pour inclure la température à côté du modèle (ex: "Claude (claude-sonnet-5, T=0.7)")
- Le champ temperature est lu depuis les entrées de coach_calls.log

### 4. Script de lecture du journal (lire_journal_coach.py)
- Ajout de l'affichage de la température dans l'en-tête de chaque entrée (à côté du modèle)
- Le champ `temperature` est maintenant visible dans la sortie du script

### 5. Documentation (CONTEXTE.md)
- Ajout d'une nouvelle section "Température configurable pour les appels LLM (issue #116)" expliquant :
  - Les deux nouvelles variables d'environnement
  - Leur comportement (défaut, validation, journalisation)
  - L'impact sur la comparabilité des séries d'exercices

## Comportement dans les quatre cas

### 1. Variable Claude absente
- **Comportement** : Aucun paramètre temperature n'est envoyé à l'API Claude
- **Journal** : Le champ `temperature` contient "defaut API"
- **Impact** : L'API utilise sa valeur par défaut (comportement strictement identique à avant l'issue #116)

### 2. Variable Claude renseignée (valide)
- **Comportement** : Le paramètre temperature est envoyé avec la valeur configurée
- **Journal** : Le champ `temperature` contient la valeur numérique (ex: "0.7")
- **Impact** : L'API utilise la température spécifiée
- **Si l'API refuse le paramètre** : L'appel est réessayé sans le paramètre (via la logique existante de gestion d'erreur), un avertissement est loggé, et le journal indique "defaut API"

### 3. Variable Mistral absente
- **Comportement** : La température par défaut 0.0 est utilisée (comportement identique à avant l'issue #116)
- **Journal** : Le champ `temperature` contient "0.0"
- **Impact** : Aucun changement par rapport au comportement actuel

### 4. Variable Mistral invalide
- **Comportement** : Un avertissement est loggé dans l'application, la valeur par défaut 0.0 est utilisée
- **Journal** : Le champ `temperature` contient "0.0"
- **Impact** : La valeur invalide est ignorée, l'appel utilise la température par défaut

## Vérification par simulation

Un script de test `test_issue116.py` a été créé et exécuté avec succès, vérifiant :
- ✅ Les variables de configuration sont correctement définies dans config.py
- ✅ Le paramètre temperature est accepté par _call_claude et _call_mistral
- ✅ La température est correctement stockée dans le journal (y compris None et "defaut API")
- ✅ get_coach_response gère correctement l'absence de clé API
- ✅ La validation des valeurs de température fonctionne correctement

## Ce qui n'a pas pu être testé en conditions réelles

- **Appels API réels** : Aucun appel réel à l'API Claude ou Mistral n'a été effectué (pas de clés API disponibles dans l'environnement de test)
- **Réaction de l'API au paramètre temperature** : Le comportement de l'API Claude quand le paramètre temperature est fourni n'a pas pu être vérifié (refus potentiel, acceptation)
- **Réaction de l'API au paramètre temperature invalide** : Le cas où l'API Claude refuse le paramètre temperature n'a pas pu être testé
- **Intégration complète avec l'interface** : L'impact sur l'interface utilisateur n'a pas été testé (nécessite un navigateur et un serveur Flask en cours d'exécution)

## Fichiers modifiés

1. `config.py` : Ajout des variables CHESSCOACH_CLAUDE_TEMPERATURE et CHESSCOACH_MISTRAL_TEMPERATURE
2. `llm_coach.py` : Modifications de _call_claude, _call_mistral, _log_coach_call, get_coach_response, get_mistral_response
3. `scripts/coach_ratings_report.py` : Mise à jour pour afficher la température
4. `lire_journal_coach.py` : Ajout de l'affichage de la température dans l'en-tête
5. `CONTEXTE.md` : Documentation des nouvelles variables
6. `test_issue116.py` : Script de test (nouveau fichier)

## Rétrocompatibilité

- Tous les appels existants à `_log_coach_call` continuent de fonctionner (le paramètre temperature a une valeur par défaut de None)
- Tous les appels existants à `_call_claude` et `_call_mistral` continuent de fonctionner (le paramètre temperature a une valeur par défaut)
- Le script `coach_ratings_report.py` continue de fonctionner (le champ temperature est optionnel dans les entrées de log)
- La fonction shell `coachlog` d'Alain ne devrait pas être cassée (elle ne lit que des clés explicitement nommées, et temperature est un nouveau champ)
