# CHANGELOG-124 — Issue #124 : Suite #120 : enregistrer la version du code (automatique) et une étiquette de série (optionnelle) avec chaque avis et chaque note

## Résumé

Implémentation complète du suivi de version du code et de l'étiquette de série pour permettre à Alain de comparer Claude et Mistral sur de longues périodes en sachant exactement dans quelles conditions chaque avis a été produit.

## Modifications apportées

### 1. Nouveau module : version_info.py

- **Fonctionnalité** : Détection automatique au démarrage de l'application des informations de version du code source depuis le dépôt git.
- **Informations détectées** :
  - `commit_hash` : identifiant court (7 caractères) du commit HEAD
  - `commit_message` : première ligne du message de commit
  - `modified` : booléen indiquant si des fichiers suivis ont des changements non commités
  - `last_issue` : numéro de la dernière issue citée dans les 30 derniers commits
  - `serie` : étiquette de série depuis la variable d'environnement CHESSCOACH_SERIE
- **Comportement** : Si git est absent ou échoue, toutes les valeurs valent "inconnue" et l'application démarre normalement.
- **Mémorisation** : Les informations sont calculées une fois au démarrage et stockées dans une variable globale `VERSION_INFO`.

### 2. Modifications de llm_coach.py

- **Import ajouté** : `import version_info`
- **Fonction _log_coach_call modifiée** :
  - Ajout du paramètre optionnel `version_info_param`
  - Ajout automatique des informations de version dans chaque entrée de log via un champ `version_info`
  - Si `version_info_param` n'est pas fourni, récupération automatique depuis `version_info.get_version_info()`
  - Le champ `version_info` contient : commit_hash, commit_message, modified, last_issue, serie
- **Compatibilité** : Les appels existants à _log_coach_call continuent de fonctionner sans modification.

### 3. Modifications de app.py

- **Import ajouté** : `import version_info`
- **Initialisation** : Appel à `version_info.get_version_info()` au démarrage, après le chargement de la mémoire du coach
- **Effet** : Les informations de version sont calculées une fois et mémorisées pour toute la durée de vie de l'application

### 4. Modifications de coach_ratings.py

- **Nouvelle fonction** : `_get_version_info_from_log_id(log_id)` pour récupérer les informations de version depuis une entrée de journal
- **Nouvelle fonction** : `_get_coach_calls_files()` pour lister tous les fichiers coach_calls*.log
- **Fonction record_rating modifiée** :
  - Ajout automatique des informations de version depuis l'entrée de journal correspondante (via log_id)
  - Si l'entrée de journal est introuvable (notes anciennes), toutes les valeurs sont enregistrées comme "inconnue"
  - Ajout du champ `version_info` dans chaque note
- **Format** : Le champ `version_info` est un dict avec les mêmes clés que dans les logs

### 5. Modifications de scripts/coach_ratings_report.py

- **Nouveaux imports** : `argparse`, `datetime`
- **Nouveaux arguments de ligne de commande** :
  - `--serie SERIE` : filtre les notes par étiquette de série
  - `--group-by-version` : affiche le regroupement par version
- **Nouvelles fonctions** :
  - `_get_version_key(rating)` : retourne une clé de version pour le regroupement
  - `_get_serie(rating)` : retourne l'étiquette de série d'une note
  - `_get_timestamp(rating)` : retourne le timestamp d'une note
  - `_group_by_version(ratings)` : regroupe les notes par version
  - `_format_period(timestamps)` : formate une période à partir de timestamps
  - `_display_version_grouping(ratings, filter_serie)` : affiche le regroupement par version
- **Fonction main modifiée** :
  - Parsing des arguments de ligne de commande
  - Appel optionnel à `_display_version_grouping` si `--group-by-version` est spécifié
- **Compatibilité** : Le fonctionnement actuel du script (sans ces options) reste inchangé

### 6. Documentation dans CONTEXTE.md

- **Nouvelle section** : "Suivi de version du code et étiquette de série (issue #124)"
- **Contenu** :
  - Description des informations de version détectées
  - Explication de l'étiquette de série CHESSCOACH_SERIE
  - Exemples d'utilisation
  - Description de l'enregistrement dans les logs et les notes
  - Documentation du script de rapport avec les nouvelles options

## Comportement attendu

### Au démarrage de l'application

1. Détection automatique des informations de version depuis le dépôt git
2. Mémorisation des informations pour toute la durée de vie de l'application
3. Si git est absent ou échoue : toutes les valeurs valent "inconnue", pas d'erreur

### Dans les logs (coach_calls*.log)

Chaque entrée contient un nouveau champ `version_info` avec :
```json
{
  "version_info": {
    "commit_hash": "a1b2c3d",
    "commit_message": "fix: correction bug X",
    "modified": false,
    "last_issue": "124",
    "serie": "test-01"
  }
}
```

### Dans les notes (data/coach_ratings.jsonl)

Chaque note contient un champ `version_info` avec les informations de version **au moment où l'avis a été produit** (lues depuis le log correspondant).

### Dans le rapport (scripts/coach_ratings_report.py)

- Sans options : comportement inchangé
- Avec `--group-by-version` : affichage du regroupement par version avec statistiques par agent
- Avec `--serie SERIE` : filtrage des notes par étiquette de série
- Les notes anciennes sans version_info sont regroupées sous "inconnue (avant ce suivi)"

## Utilisation par Alain

### Définir une étiquette de série

```bash
# Dans le terminal, avant de lancer l'application
CHESSCOACH_SERIE="test-temperature-0.7" coach
```

Ou dans le .bashrc, modifier la fonction `coach` pour inclure la variable :
```bash
coach() {
    CHESSCOACH_SERIE="ma-serie" python3 ~/ChessCoach/app.py
}
```

### Générer un rapport avec regroupement par version

```bash
python3 scripts/coach_ratings_report.py --group-by-version
```

### Filtrer par série

```bash
python3 scripts/coach_ratings_report.py --group-by-version --serie "test-temperature-0.7"
```

## Rétrocompatibilité

- Les anciennes entrées de log sans `version_info` sont acceptées et traitées comme "inconnue"
- Les anciennes notes sans `version_info` sont acceptées et traitées comme "inconnue"
- Le script de rapport fonctionne sans les nouvelles options (comportement inchangé)
- Aucun changement n'est apporté au script de lancement personnel d'Alain (fonction shell `coach` dans son .bashrc)

## Tests à effectuer

Voir la section "Tester avec dépôt git temporaire" ci-dessous.

## Fichiers modifiés

- `version_info.py` (nouveau)
- `llm_coach.py` (modifié)
- `app.py` (modifié)
- `coach_ratings.py` (modifié)
- `scripts/coach_ratings_report.py` (modifié)
- `CONTEXTE.md` (modifié)

## Fichiers créés

- `CHANGELOG-124.md` (ce fichier)
