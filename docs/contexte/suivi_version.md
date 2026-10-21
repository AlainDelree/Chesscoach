# Suivi de version du code et étiquette de série (issue #124)

Au démarrage de l'application, ChessCoach détecte automatiquement et mémorise
les informations de version du code source depuis le dépôt git du projet :

- **commit_hash** : identifiant court (7 caractères) du commit HEAD
- **commit_message** : première ligne du message de commit
- **modified** : indicateur booléen (True si des fichiers suivis par git ont
des changements non commités)
- **last_issue** : numéro de la dernière issue citée dans l'historique récent
  (recherche parmi les 30 derniers commits pour des mentions de type
  "issue-N", "issue N", "#N" ou "worktree-issue-N")

Si git est absent ou si la détection échoue, toutes les valeurs de version
valent "inconnue" et l'application démarre normalement, sans erreur.

### Étiquette de série (CHESSCOACH_SERIE)

Une étiquette de série optionnelle peut être définie via la variable
d'environnement **CHESSCOACH_SERIE**. Cette étiquette sert à Alain pour nommer un
essai que ni le code ni le journal ne distinguent (par exemple, pour différencier
des séries d'exercices avec les mêmes paramètres mais des objectifs différents).

**Utilisation** : Placer la variable devant la commande de lancement, par exemple :

```bash
CHESSCOACH_SERIE="test-temperature-0.7" coach
```

La valeur est tronquée à 50 caractères. Elle peut être vide ou non définie.

### Enregistrement dans les logs et les notes

Ces informations de version (commit, dernière issue citée, indicateur modifié,
étiquette de série) sont enregistrées dans :

1. **Chaque entrée de coach_calls*.log** : dans un champ `version_info` ajouté
   à chaque appel au coach, pour les deux agents (Claude et Mistral), au moins
   en mode exercices.

2. **Chaque note dans data/coach_ratings.jsonl** : les informations de version
   sont lues depuis l'entrée de journal correspondante (via l'identifiant d'appel
   `log_id`) et enregistrées avec la note. Si l'entrée de journal est
   introuvable (notes anciennes), toutes les valeurs sont enregistrées comme
   "inconnue".

### Rapport avec regroupement par version

Le script `scripts/coach_ratings_report.py` permet désormais de regrouper les
notes par version (commit et dernière issue citée) avec, par agent, le nombre
de 1 et de 0 et la période couverte. Il propose également une option pour filtrer
ou regrouper par étiquette de série.

**Options du script** :
```bash
# Afficher le regroupement par version
python3 scripts/coach_ratings_report.py --group-by-version

# Filtrer par étiquette de série
python3 scripts/coach_ratings_report.py --serie "test-temperature-0.7"

# Combiner les deux
python3 scripts/coach_ratings_report.py --group-by-version --serie "test-temperature-0.7"
```

Les notes sans information de version (anciennes entrées) sont regroupées
sous l'étiquette "inconnue (avant ce suivi)". Le fonctionnement actuel du
script (sans ces options) reste inchangé pour maintenir la compatibilité.
