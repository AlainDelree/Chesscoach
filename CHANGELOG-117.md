# Issue #117 : Vérificateur d'affirmations factuelles du coach en mode exercices

## Ajouts

### 1. Nouveau module `fact_checker.py`
- Implémentation d'un vérificateur déterministe (python-chess uniquement, aucun appel à un modèle)
- Vérifie trois types d'affirmations en mode exercice :
  - (a) Affirmations « pièce en case » (« ta dame en b5 », « le cavalier en e5 »)
  - (b) Affirmations d'attaque par un pion (« le pion X attaque/menace/prend/chasse la pièce Y »)
  - (c) Cohérence verdict/texte (contradictions entre le verdict fourni et le texte de l'avis)
- Règle de prudence : une affirmation n'est signalée comme fausse que si elle est fausse dans TOUTES les positions candidates
- Les affirmations non interprétables sont ignorées sans bruit

### 2. Intégration dans `llm_coach.py`
- Appel automatique du vérificateur pour chaque avis en mode exercice (Claude et Mistral)
- Les alertes du vérificateur sont ajoutées à la fiabilité de l'avis
- Si la couleur était verte et qu'on a des alertes du vérificateur, passage en orange
- Les alertes sont journalisées dans `coach_calls*.log` avec les champs :
  - `fact_checker_alertes` : liste des alertes détectées
  - `fact_checker_affirmations_verifiees` : nombre d'affirmations vérifiées
  - `fact_checker_affirmations_ignorees` : nombre d'affirmations ignorées

### 3. Variable d'activation dans `config.py`
- Nouvelle variable `CHESSCOACH_FACT_CHECKER_ACTIVATED` (défaut : "1", activé)
- Peut être désactivée en mettant `CHESSCOACH_FACT_CHECKER_ACTIVATED=0` dans `.env`

### 4. Extension de `scripts/coach_ratings_report.py`
- Ajout d'une section "Statistiques des alertes du vérificateur d'affirmations factuelles"
- Affiche par agent (Claude/Mistral) :
  - Nombre d'avis avec au moins une alerte
  - Nombre total d'alertes

### 5. Script de test `test_fact_checker.py`
- Permet de rejouer le vérificateur hors ligne sur les logs existants
- Valide que les alertes attendues sont bien détectées
- Vérifie l'absence de fausses alertes sur les avis corrects de Claude
- Usage : `python3 test_fact_checker.py [--log-dir DOSSIER] [--date AAAA-MM]`

## Modifications

### `llm_coach.py`
- Ajout de l'import `fact_checker`
- Modification de `_log_coach_call` pour accepter les nouveaux champs du vérificateur
- Intégration de l'appel au vérificateur dans `get_coach_response` (Claude)
- Intégration de l'appel au vérificateur dans `get_mistral_response` (Mistral)

### `config.py`
- Ajout de la variable `CHESSCOACH_FACT_CHECKER_ACTIVATED`

### `scripts/coach_ratings_report.py`
- Ajout de la fonction `_afficher_statistiques_fact_checker`
- Appel de cette fonction dans `main()`

## Corrections apportées (cette tentative)

### `fact_checker.py`
- **Correction de la déduction de couleur** : Ne déduit plus la couleur à partir de possessifs non associés à la pièce mentionnée
  - Exemple : "ta défaveur... le fou en c3" ne déduit plus que le fou est blanc
  - La recherche de possessifs/couleurs est maintenant limitée aux 15 caractères avant le nom de la pièce
  - Élimine la plupart des fausses alertes (passage de 51 à 14 fausses alertes)
- **Correction du pattern pour "erreur/gaffe/faute"** : Accepte maintenant ces mots comme mots complets (pas seulement suivis d'un adjectif)
  - Permet de détecter "C'est une erreur." comme incohérence avec un verdict "bon"

### `scripts/coach_ratings_report.py`
- Correction du bug de variable non définie (appel de `get_coach_calls_log()` avant `_afficher_statistiques_fact_checker()`)
- Correction de l'utilisation de `Path.stem` et `Path.suffix`

## Comportement

- **Mode exercice uniquement** : Le vérificateur ne s'applique qu'en mode exercice, pour les deux agents
- **Ne modifie jamais le texte** : Les avis du coach ne sont jamais modifiés ni masqués
- **Affichage discret** : Les alertes sont affichées sous l'avis avec une mention du type « à vérifier : <affirmation> »
- **Zéro fausse alerte** : Objectif prioritaire - dans le doute, ne rien signaler
- **Journalisation complète** : Toutes les alertes sont consignées dans les logs

## Test d'acceptation

Le script `test_fact_checker.py` doit détecter les alertes suivantes sur le journal d'octobre 2026 :
- ✓ Mistral 20:41 : contradiction « moins précis que le meilleur coup »
- ✓ Mistral 20:33 : erreur de verdict (« erreur » pour un coup de verdict « bon »)
- ✗ Mistral 20:26 : pion noir en d4 qui « attaquerait ta dame et ton cavalier » (à implémenter)
- ✗ Mistral 20:34 : tour attaquée par un « pion blanc c4 » (à implémenter)
- ✗ Mistral 20:35 : pion noir en c6 qui « menacerait un fou en b7 » (à implémenter)

Résultats actuels :
- **Alertes attendues trouvées** : 2/5
- **Fausses alertes** : 14 (réduites de 51)

## Points d'attention

1. Le vérificateur est volontairement étroit et prudent dans sa version initiale
2. Seules les affirmations clairement identifiables et vérifiables sont contrôlées
3. Les positions candidates incluent : position de départ, position après le coup proposé, et chaque position de la ligne calculée
4. Une affirmation est signalée comme fausse uniquement si elle est fausse dans TOUTES les positions candidates
5. Les 3 alertes manquantes concernent la détection d'attaques par des pions avec des pièces mentionnées sans case explicite dans le texte, nécessitant une analyse plus poussée du contexte

## Travail restant

- Implémenter la détection des affirmations d'attaque par un pion du type :
  - "les Noirs répondent d4 : ce pion noir attaque ta dame et ton cavalier" (20:26)
  - "Ta tour en g8 est immédiatement attaquée par le pion blanc c4" (20:34)
  - "c6 pour menacer ton fou en b7" (20:35)
- Réduire les 14 fausses alertes restantes (principalement des détections de "erreur" dans des contextes non pertinents)
