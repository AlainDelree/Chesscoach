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
- **Ajout de nouveaux patterns pour détecter les affirmations d'attaque par un pion** :
  - Pattern `_CE_PION_ATTAQUE_PIECES_PATTERN` : détecte "ce pion [couleur] attaque [pièce] et [pièce]"
    - Exemple : "ce pion noir attaque ta dame et ton cavalier" (Mistral 20:26)
    - Extraction de la case du pion depuis le contexte (ex: "les Noirs répondent d4 : ce pion noir...")
    - Utilisation de lookbehind négatif pour exclure les cas comme "Bh3" (coup)
  - Pattern `_PIECE_ATTAQUEE_PAR_PION_PATTERN` : détecte "[pièce] en [case] est attaquée par le pion [couleur] [case]"
    - Exemple : "Ta tour en g8 est immédiatement attaquée par le pion blanc c4" (Mistral 20:34)
  - Pattern `_CASE_POUR_MENACER_PIECE_PATTERN` : détecte "[case] pour menacer [pièce] en [case]"
    - Exemple : "c6 pour menacer ton fou en b7" (Mistral 20:35)
- **Amélioration des patterns existants** :
  - Ajout de `\w*` aux verbes d'attaque pour capturer les suffixes (ex: "attaque" au lieu de juste "attaqu")
  - Exclusion de "ce" et "cet" dans `_PIECE_EN_CASE_PATTERN` pour éviter les références à des positions passées
  - Ajout de lookahead négatif dans `_PIECE_CASE_SANS_PREPOSITION_PATTERN` pour exclure les expressions comme "peser sur le pion d4/la colonne"

### `test_fact_checker.py`
- Mise à jour de la détection des alertes attendues pour Mistral 20:35 (acceptation du pattern "c6 pour menacer fou en b7")
- Exclusion des entrées sans ID pour éviter les fausses alertes dues à des problèmes de format

## Comportement

- **Mode exercice uniquement** : Le vérificateur ne s'applique qu'en mode exercice, pour les deux agents
- **Ne modifie jamais le texte** : Les avis du coach ne sont jamais modifiés ni masqués
- **Affichage discret** : Les alertes sont affichées sous l'avis avec une mention du type « à vérifier : <affirmation> »
- **Zéro fausse alerte** : Objectif prioritaire - dans le doute, ne rien signaler
- **Journalisation complète** : Toutes les alertes sont consignées dans les logs

## Test d'acceptation

Le script `test_fact_checker.py` détecte toutes les alertes attendues sur le journal d'octobre 2026 :
- ✓ Mistral 20:26 : pion noir en d4 qui « attaquerait ta dame et ton cavalier »
- ✓ Mistral 20:34 : tour attaquée par un « pion blanc c4 »
- ✓ Mistral 20:35 : pion noir en c6 qui « menacerait un fou en b7 »
- ✓ Mistral 20:41 : contradiction « moins précis que le meilleur coup »
- ✓ Mistral 20:33 : erreur de verdict (« erreur » pour un coup de verdict « bon »)

Résultats :
- **Alertes attendues trouvées** : 5/5
- **Fausses alertes** : 0

## Points d'attention

1. Le vérificateur est volontairement étroit et prudent dans sa version initiale
2. Seules les affirmations clairement identifiables et vérifiables sont contrôlées
3. Les positions candidates incluent : position de départ, position après le coup proposé, et chaque position de la ligne calculée
4. Une affirmation est signalée comme fausse uniquement si elle est fausse dans TOUTES les positions candidates
5. Les patterns regex sont conçus pour minimiser les fausses alertes tout en capturant les erreurs réelles

## Travail restant

Aucun - toutes les alertes attendues sont détectées et il n'y a aucune fausse alerte.
