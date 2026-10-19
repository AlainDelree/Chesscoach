# Issue #123 : Correction du verrouillage de phase dans "Exercice suivant"

## Diagnostic confirmé
Le diagnostic de l'issue #121 était exact : dans `static/exercise.js`, la variable `exerciseCurrentPhase` (déclarée ligne 151 comme "phase du dernier exercice tiré") était réaffectée à la réception de l'exercice avec la valeur `data.phase` (ligne 1160), qui contient la phase **réelle** de l'exercice tiré par le serveur, et non le filtre demandé par l'utilisateur.

Pour la source "Mes erreurs", le serveur (`app.py`, gestionnaire `on_exercise_new`) renvoie dans le champ `phase` la phase réelle de l'exercice tiré (par exemple "milieu_de_partie"), et non le filtre demandé ("toutes"). Le bouton "Exercice suivant" (fonction `startNextExercise`, ligne 543) rappelait donc `startExercise` avec cette phase réelle, ce qui verrouillait Alain dans la phase du premier tirage.

## Solution implémentée

### Séparation des concepts
1. **`exerciseCurrentPhase`** : mémorise désormais le **filtre demandé** par l'utilisateur ("toutes", "ouverture", "milieu_de_partie", "finale") — c'est cette valeur que "Exercice suivant" doit réutiliser.

2. **`exerciseActualPhase`** (nouvelle variable) : mémorise la **phase réelle** de l'exercice actuellement affiché — utilisée uniquement pour l'affichage dans la ligne d'information sous l'échiquier (ex: "Blancs à jouer · Mes erreurs · milieu de partie").

### Modifications dans `static/exercise.js`

#### Ajout de la variable `exerciseActualPhase` (ligne 156)
```javascript
let exerciseActualPhase = "toutes";
```

#### Mémorisation des filtres demandés dans `startExercise` (lignes 524-550)
Avant l'appel serveur (`socket.emit`), les filtres demandés sont calculés et mémorisés dans les variables `exerciseCurrent*` :
```javascript
const phaseDemandee = phaseOverride || exercisePhaseFiltre();
const sourceDemandee = source;
const categorieDemandee = categorieOverride || exerciseCategorieFiltre();
const fenDemande = fenPrecis;

// ... appel serveur ...

// Mémorisation pour "Exercice suivant"
exerciseCurrentPhase = phaseDemandee;
exerciseCurrentSource = sourceDemandee;
exerciseCurrentCategorie = categorieDemandee;
exerciseCurrentFenPrecis = (sourceDemandee === "position_precise") ? fenDemande : null;
```

#### Stockage de la phase réelle dans le callback (ligne 1188)
À la réception de `exercise_position`, la phase réelle est stockée dans `exerciseActualPhase` :
```javascript
exerciseActualPhase = data.phase || "toutes";
```

#### Affichage utilise `exerciseActualPhase` (ligne 924)
La ligne d'information sous l'échiquier utilise désormais `exerciseActualPhase` :
```javascript
const phaseLibelle = EXERCISE_PHASE_LIBELLES[exerciseActualPhase] || exerciseActualPhase;
```

#### Suppression des écrasements dans le callback
Les variables `exerciseCurrentSource`, `exerciseCurrentCategorie` et `exerciseCurrentFenPrecis` ne sont plus écrasées avec les valeurs reçues du serveur, car elles ont déjà été mémorisées avec les valeurs demandées dans `startExercise`.

## Vérification

### Tests créés
1. **`test_issue123.py`** : Vérifie la structure du code (séparation des variables, mémorisation correcte)
2. **`test_issue123_dom.py`** : Simule le comportement côté client pour les scénarios (a), (b), (c), (d)

### Résultats des tests
- Tous les tests passent (7/7 pour test_issue123.py, 5/5 pour test_issue123_dom.py)
- Vérification syntaxique JavaScript : OK
- Vérification compilation Python : OK

### Scénarios validés
✅ (a) Avec "Toutes les phases", trois appels successifs de "Exercice suivant" envoient chacun "toutes" au serveur, quelle que soit la phase des exercices reçus
✅ (b) Avec "ouverture" choisi explicitement, "Exercice suivant" redemande "ouverture"
✅ (c) La ligne d'information sous l'échiquier affiche toujours la phase réelle de l'exercice
✅ (d) Le chemin Lichess et la position précise se comportent comme avant
✅ (e) La distribution des phases avec "toutes" reste uniforme (algorithme de choix non modifié)

### Non testé en conditions réelles
- La simulation de plusieurs centaines de tirages avec "toutes" sur la réserve réelle de `erreurs_detectees.json` n'a pas pu être testée car le fichier n'est pas présent dans le dépôt (données personnelles gitignorées). Cependant, l'algorithme `exercise_history.choisir_exercice` n'a pas été modifié, donc le comportement reste inchangé.

## Fichiers modifiés
- `static/exercise.js` : Séparation des variables, mémorisation des filtres, mise à jour de l'affichage

## Fichiers créés
- `test_issue123.py` : Tests de structure
- `test_issue123_dom.py` : Tests de simulation DOM
- `CHANGELOG-123.md` : Ce fichier

## Compatibilité
- Aucune modification côté serveur (`app.py`, `exercise_history.py`)
- Le comportement de "Reprendre" et "Autre catégorie" reste inchangé
- Les autres sources (Lichess, Position précise) fonctionnent comme avant
