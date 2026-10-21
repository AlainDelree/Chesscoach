# Source d'exercices « Problèmes Lichess » (issue #78)

Deuxième source pour le mode "Exercice", en complément de "Mes erreurs"
(erreurs_detectees.json) : des problèmes tirés de la base ouverte Lichess
(licence CC0, ~5 millions de positions, téléchargée MANUELLEMENT par Alain —
CCL n'a pas accès à Internet et ne télécharge jamais rien automatiquement).

**Préparation hors-ligne** : `preparer_puzzles_lichess.py <chemin_csv>`
(option `--sortie` pour changer la destination, défaut
`config.LICHESS_PUZZLES_PATH` = `data/puzzles_lichess.json`). Sans accès
réseau, lit le CSV (colonnes PuzzleId/FEN/Moves/Rating/RatingDeviation/
Popularity/NbPlays/Themes/GameUrl/OpeningTags), décompressé ou en `.gz`
(stdlib) — le `.zst` d'origine nécessite le module tiers `zstandard`, sinon
le script l'indique clairement et s'arrête (décompresser à la main,
`zstd -d fichier.csv.zst`). Filtre les problèmes fiables (Rating 800-2200,
RatingDeviation ≤ 100, NbPlays ≥ 500, Popularity ≥ 80 — constantes en tête de
script), classe chacun dans les 16 catégories de thème ci-dessous et par
phase (opening/middlegame/endgame, mêmes tags Lichess que les thèmes), puis
échantillonne au plus 200 problèmes par (catégorie, tranche de note de 100
points) — réglable (`MAX_PAR_CATEGORIE_ET_TRANCHE`/`TAILLE_TRANCHE`). Affiche
un résumé (comptes avant/après filtre et par catégorie/tranche) et n'écrit
que ce fichier JSON. Un petit CSV d'essai (34 lignes, tous thèmes et
quelques rejets volontaires pour vérifier les filtres) est fourni à la
racine : `puzzles_lichess_exemple.csv` — commande de test :
`python3 preparer_puzzles_lichess.py puzzles_lichess_exemple.csv --sortie /tmp/essai.json`.

**Format d'une entrée du pool** (`data/puzzles_lichess.json`, liste JSON,
donnée personnelle hors git) :
```
{"fen_avant": "lichess:<PuzzleId>",      // clé d'historique, PAS une FEN
 "puzzle_id": "...", "rating": 1512, "rating_deviation": 45,
 "popularity": 92, "nb_plays": 8000,
 "themes": ["middlegame", "fork", ...],  // thèmes Lichess bruts
 "categories": ["fork"],                 // sous-ensemble des 16 catégories
 "phases": ["middlegame"],               // opening/middlegame/endgame présents
 "camp_alain": "blancs", "fen_position": "...",  // position affichée à Alain
 "premier_coup_adverse": "e2e4", "solution": ["e7e5", "g1f3", ...],  // UCI
 "game_url": "...", "opening_tags": "..."}
```
Le FEN du CSV est la position AVANT le premier coup de `Moves` (joué par
l'adversaire) ; `fen_position` est déjà calculée après ce premier coup
(position réellement montrée à Alain) et `solution` ne contient plus que les
coups du joueur/de l'adversaire en alternance après ce premier coup.

**Catégories de niveau** (`lichess_puzzles.CATEGORIES`, thème Lichess →
libellé FR) : pin→clouage, discoveredAttack→attaque à la découverte,
defensiveMove→coup défensif, quietMove→coup silencieux, zugzwang→zugzwang,
rookEndgame→finale de tours, endgame→finale, pawnEndgame→finale de pions,
exposedKing→roi exposé, attraction→attraction, kingsideAttack→attaque sur
l'aile roi, advancedPawn→pion avancé, sacrifice→sacrifice, mate→mat (couvre
aussi mateIn1/mateIn2/...), fork→fourchette, middlegame→milieu de jeu.

**Niveau adaptatif par catégorie** (`data/niveau_exercices_lichess.json`,
donnée personnelle, `{categorie: niveau}`) : valeur de départ pondérée vers
1471 (performance Lichess globale d'Alain, 30 jours, relevée le 2026-10-01)
par `lichess_puzzles.valeur_depart_categorie` — `(n*perf + 5*1471)/(n+5)`,
`n`/`perf` lus dans `PERFORMANCES_INITIALES` (poids 5 et valeurs de repli
réglables en tête de `lichess_puzzles.py`). 1471 sert aussi de repli pour
toute catégorie inconnue (n=0) et, implicitement, pour la phase "ouverture"
(aucune des 16 catégories n'est dédiée à l'ouverture). Tirage
(`lichess_puzzles.tirer_probleme`) : catégories compatibles avec la phase
demandée, tirage pondéré favorisant les niveaux bas (poids = 1/niveau), puis
problème dans la fenêtre [niveau±100] (élargie par paliers de 100 jusqu'à
±700 si vide) via `exercise_history.choisir_exercice` réutilisé tel quel (clé
"lichess:<PuzzleId>" au lieu d'une FEN — le module n'a pas besoin d'une vraie
FEN, juste d'une clé opaque, donc partage le même fichier
`config.EXERCICE_HISTORIQUE_PATH` que "Mes erreurs" sans collision). Mise à
jour Elo après chaque résultat (`lichess_puzzles.mettre_a_jour_niveau`,
formule standard, résultat attendu = 1/(1+10^((note-niveau)/400)), pas de
mise à jour `PAS_ELO` = 28 points, réglable seul à cet endroit), bornée à
[400, 3000]. Seule la catégorie ayant servi au TIRAGE est mise à jour, même
si le problème porte plusieurs thèmes de catégorie.

**Jugement du coup** (`app.py`, `_on_exercise_answer_lichess`) : seul le
premier coup de la solution est jugé — réussi s'il est identique à ce coup,
s'il donne mat (y compris un mat différent de la solution), ou s'il est
« équivalent » d'après Stockfish réel (perte < 30cp,
`engine_stockfish.SEUIL_PUZZLE_EQUIVALENT_CP`, plus strict que le seuil
"bon" de 50cp utilisé par "Mes erreurs" car une solution Lichess est unique
par construction — ou garde-fou "position déjà décidée" déclenché,
équivalent à `qualite=="imprecision"` avec `delta_cp >= SEUIL_IMPRECISION`).
Le "meilleur coup" affiché et la ligne jouable dans le tableau "Lignes du
coach" (« Solution du problème ») sont toujours la solution DÉCLARÉE du
problème, jamais une ligne recalculée indépendamment par Stockfish. Pas de
"coup réellement joué à l'époque" pour cette source (aucune clé `coup_reel`
transmise au coach). Contexte coach enrichi de `themes_lichess`/
`rating_probleme`/`niveau_categorie`/`categorie_libelle`
(`llm_coach._build_context_text`) et d'un addendum système dédié
(`_EXERCISE_LICHESS_ADDENDUM`) demandant une réponse courte.

**Interface** : sélecteur de source ("Mes erreurs"/"Problèmes Lichess") à
côté du sélecteur de phase (desktop) et dans la feuille "Nouvel exercice"
(mobile, pilote le même `<select>`) — désactivé avec une phrase explicite
si `data/puzzles_lichess.json` est absent (`lichess_puzzles_disponible`,
calculé au démarrage de `app.py`, rendu côté serveur). "Exercice suivant" et
"Autre catégorie" conservent la source choisie (`exerciseCurrentSource`,
même mécanisme que `exerciseCurrentPhase` pour la phase, issue #76). Ligne
d'état dédiée (`#exercise-lichess-info`) : "Problème `<note>` · ton niveau
en `<catégorie>` `<niveau>`".
