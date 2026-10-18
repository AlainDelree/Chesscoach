# Issue #118 : Gestion du refus du paramètre température par l'API

## Résumé
Implémentation complète de la gestion du refus du paramètre température par les API Claude et Mistral, conformément à la tâche demandée.

## Modifications apportées

### 1. llm_coach.py

#### Ajouts de fonctions (issue #118)
- `_TEMPERATURE_REFUSED_MODELS` : mémoire globale (set) des modèles qui refusent le paramètre température, persistante pour la durée de vie du processus
- `_marquer_modele_refuse_temperature(provider, model)` : mémorise qu'un modèle refuse la température
- `_modele_refuse_temperature(provider, model)` : vérifie si un modèle est connu pour refuser la température
- `_est_erreur_temperature_refusee(provider, err_data, model)` : détecte si une erreur API est due au refus du paramètre température
- `_get_temperature_log_value(provider, model, temperature)` : détermine la valeur de température à logger ("refusée par le modèle, défaut API" si refusé)

#### Modifications de _call_claude
- Vérification préalable si le modèle refuse déjà la température (via `_modele_refuse_temperature`)
- Si le modèle n'est pas connu pour refuser la température et qu'une température est fournie, inclusion conditionnelle du paramètre
- Détection des erreurs HTTP 400 de type `invalid_request_error` avec mention de "temperature", "deprecated" ou "not supported"
- En cas de détection :
  - Marquage du modèle comme refusant la température
  - Journalisation unique avec niveau WARNING
  - Réessai UNE fois sans le paramètre température
  - Utilisation de la réponse du réessai si succès
- Si le réessai échoue, propagation de l'erreur originale

#### Modifications de _call_mistral
- Même logique que pour Claude, adaptée à l'API Mistral
- Détection des erreurs avec mention de "temperature" et "not supported"/"invalid"/"deprecated"/"not accepted"

#### Modifications de get_coach_response
- Utilisation de `_get_temperature_log_value` pour déterminer la valeur de température à logger
- La température logguée est maintenant "refusée par le modèle, défaut API" quand le modèle est connu pour refuser ce paramètre

#### Modifications de get_mistral_response
- Même mise à jour que pour Claude

### 2. CONTEXTE.md

#### Documentation mise à jour (section "Température configurable pour les appels LLM")
- Ajout d'une note explicite : le modèle `claude-sonnet-5` n'accepte pas de température personnalisée (paramètre déprécié)
- Précision que avec ce modèle, `CHESSCOACH_CLAUDE_TEMPERATURE` n'a aucun effet
- Avertissement que la comparaison Claude/Mistral ne peut pas être faite à température identique tant que ce modèle est utilisé
- Ajout de la mention pour Mistral : si l'API refuse le paramètre, l'appel est réessayé sans lui

## Comportement vérifié

### Tests de simulation (test_issue_118.py)
Tous les tests passent avec succès :
1. ✓ Premier appel Claude avec température refusée → réessai sans température
2. ✓ Appels suivants avec le même modèle → pas de paramètre température envoyé
3. ✓ Changement de modèle → mémoire réinitialisée, température envoyée à nouveau
4. ✓ Premier appel Mistral avec température refusée → réessai sans température
5. ✓ Comportement sans variable température → inchangé (pas de paramètre envoyé)
6. ✓ Fonction _get_temperature_log_value → retourne les bonnes valeurs

### Journalisation
- Un seul avertissement dans les logs par modèle et par exécution (niveau WARNING)
- Message clair : "Paramètre température refusé par le modèle [provider] [model] (valeur configurée: X), réessai sans ce paramètre"
- Dans coach_calls.log : température logguée comme "refusée par le modèle, défaut API" pour les appels suivants

### Points non testés en conditions réelles
- L'appel réel à l'API Claude avec le modèle claude-sonnet-5 (nécessiterait une clé API valide et un appel qui consomme des tokens)
- L'appel réel à l'API Mistral avec un modèle qui refuse la température
- La vérification que le message d'erreur exact de l'API correspond à nos patterns de détection

## Conformité à la tâche demandée

| Point | Statut | Détails |
|-------|--------|---------|
| 1 | ✓ | Réessai UNE fois sans température si erreur de refus, utilisation de la réponse |
| 2 | ✓ | Mémoire par modèle pour la durée du processus, levée au changement de modèle |
| 3 | ✓ | Journal indique "refusée par le modèle, défaut API", un seul avertissement |
| 4 | ✓ | Même traitement pour Mistral |
| 5 | ✓ | Documentation dans CONTEXTE.md mise à jour |
| 6 | ✓ | Comportement inchangé sans variable (pas de paramètre envoyé) |

## Fichiers modifiés
- `llm_coach.py` : implémentation complète de la logique de gestion des refus de température
- `CONTEXTE.md` : documentation mise à jour

## Fichiers créés
- `test_issue_118.py` : tests de simulation pour vérifier le comportement
- `CHANGELOG-118.md` : ce fichier
