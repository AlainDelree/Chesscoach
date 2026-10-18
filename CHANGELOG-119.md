# Issue #119 : Enregistrement des jetons Mistral et estimation du coût par jour

## Modifications

### 1. Enregistrement de la consommation Mistral (llm_coach.py)
- Modifié `_call_mistral` pour extraire et retourner la consommation de jetons depuis la réponse de l'API Mistral
  - La fonction retourne désormais un tuple `(texte, usage)` au lieu de seulement le texte
  - L'usage est extrait du champ `usage` de la réponse (avec `prompt_tokens` et `completion_tokens`)
  - Si la réponse ne contient pas d'information de consommation, `usage` vaut `None`
- Adapté l'appel à `_call_mistral` dans `get_coach_response` pour gérer le nouveau retour
- Modifié l'appel à `_log_coach_call` pour inclure l'usage de Mistral dans le journal
- **Impact** : Les appels Mistral enregistrent désormais leur consommation dans le champ `usage` de coach_calls.log, avec la même structure que Claude

### 2. Tableau de prix des tokens (data/token_prices.json)
- Créé un nouveau fichier JSON modifiable à la main contenant les prix par modèle
- Structure :
  ```json
  {
    "version": "1.0",
    "derniere_mise_a_jour": "...",
    "note": "...",
    "modeles": {
      "<modele>": {
        "prix_entree": <float>,
        "prix_sortie": <float>,
        "devise": "<devise>",
        "date_verification": "...",
        "verifie": <bool>,
        "source": "..."
      }
    }
  }
  ```
- Pré-rempli avec les modèles connus :
  - claude-sonnet-5 : 2,00 €/1M entrée, 10,00 €/1M sortie (USD)
  - claude-haiku-4-5 : 1,00 €/1M entrée, 5,00 €/1M sortie (USD)
  - mistral-large-latest : 0,50 €/1M entrée, 1,50 €/1M sortie (EUR)
  - mistral-large-2512 : 0,50 €/1M entrée, 1,50 €/1M sortie (EUR)
  - mistral-large-4 : 0,68 €/1M entrée, 2,09 €/1M sortie (EUR)
  - mistral-large-4-0 : 0,68 €/1M entrée, 2,09 €/1M sortie (EUR)
- Tous les prix sont marqués comme non vérifiés (`verifie: false`) initialement
- **Règle** : Un modèle absent du tableau affiche "prix inconnu", jamais 0

### 3. Script d'estimation du coût (scripts/estimer_cout_api.py)
- Nouveau script CLI pour calculer le coût estimé par jour/par période
- Fonctionnalités :
  - Lit tous les fichiers `coach_calls*.log` (avec rotation mensuelle)
  - Filtre par date (aujourd'hui par défaut, ou période avec `--debut`/`--fin`)
  - Affiche par agent (Claude/Mistral) et par modèle :
    - Nombre d'appels
    - Jetons d'entrée et de sortie
    - Coût estimé dans la devise du modèle
  - Affiche les totaux par devise
  - Compte les appels sans consommation enregistrée à part
  - Affiche un avertissement si des prix non vérifiés sont utilisés
  - Rappelle que c'est une estimation, pas la facturation officielle
- Options :
  - `--date` : date spécifique (AAAA-MM-JJ)
  - `--debut`/`--fin` : période
  - `--prix` : chemin vers un fichier de prix personnalisé
  - `--dossier` : dossier où chercher les fichiers journal

### 4. Documentation (CONTEXTE.md)
- Ajout d'une nouvelle section "Enregistrement des jetons Mistral et estimation du coût (issue #119)"
- Décrit :
  - L'enregistrement de la consommation Mistral dans coach_calls.log
  - Le fichier de prix data/token_prices.json
  - Le script scripts/estimer_cout_api.py
  - Les règles (prix inconnu pour les modèles absents, pas de mélange avec le compteur Claude)

## Comportement

### Ce qui a changé
- Les appels Mistral enregistrent désormais leur consommation de jetons dans coach_calls.log
- Le script `estimer_cout_api.py` permet d'estimer le coût par jour/période

### Ce qui n'a PAS changé
- **L'interface utilisateur** : Le compteur affiché dans l'en-tête reste celui de Claude uniquement
- **Le fichier usage_tokens.json** : Continue à ne compter que les jetons Claude
- **Le comportement des appels** : Aucune modification du flux normal, une réponse sans consommation ne casse rien

## Exemple de sortie du script

```
⚠️  AVERTISSEMENT : Les prix pour les modèles suivants ne sont pas vérifiés :
  - claude-haiku-4-5
  - claude-sonnet-5
  - mistral-large-4
  - mistral-large-latest
   Il s'agit d'une ESTIMATION, pas de la facturation officielle.
   Les remises, le cache et les arrondis peuvent différer.

=== Statistiques de consommation API du 2026-10-18 au 2026-10-18 ===

Par agent et par modèle :
----------------------------------------------------------------------------------------------------
Agent      Modèle                           Appels       Entrée       Sortie            Coût     Devise
----------------------------------------------------------------------------------------------------
Claude     claude-sonnet-5                       1        1,000          500          0.0070        USD
Mistral    mistral-large-latest                1        2,000          800          0.0022        EUR
----------------------------------------------------------------------------------------------------

Totaux par devise :
------------------------------------------------------------
Devise       Appels       Entrée       Sortie            Coût
------------------------------------------------------------
EUR               1        2,000          800          0.0022
USD               1        1,000          500          0.0070
------------------------------------------------------------

⚠️  Appels sans consommation enregistrée : 1
   (Ces appels ne sont pas inclus dans les totaux ci-dessus)
```

## Tests effectués

### Simulation
- ✅ Réponse Mistral avec consommation : jetons enregistrés et coût calculé
- ✅ Réponse Mistral sans consommation : `usage` = `null`, compté comme consommation inconnue
- ✅ Modèle absent du tableau de prix : affiche "prix inconnu"
- ✅ Deux devises différentes (USD et EUR) : totaux séparés par devise
- ✅ Appels anciens sans consommation : comptés à part

### Non testé en conditions réelles
- ❌ Appel réel à l'API Mistral avec la nouvelle version du code (nécessite une clé API valide)
- ❌ Vérification que le champ `usage` est correctement écrit dans coach_calls.log avec un appel réel

## Fichiers modifiés
- `llm_coach.py` : Modification de `_call_mistral` et adaptation de l'appel dans `get_coach_response`
- `CONTEXTE.md` : Ajout de la documentation

## Fichiers créés
- `data/token_prices.json` : Tableau de prix des tokens
- `scripts/estimer_cout_api.py` : Script d'estimation du coût
- `CHANGELOG-119.md` : Ce fichier

## Notes
- Le fichier `data/token_prices.json` doit être placé dans le dossier `data/` du projet
- Le script `estimer_cout_api.py` doit être exécuté depuis le répertoire du projet ou avec le bon chemin
- Les prix sont en devise par million de jetons (ex: 2.00 signifie 2,00 € par million de jetons)
