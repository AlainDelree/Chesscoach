# Changelog — Issue #78

## Exercices : nouvelle source « Problèmes Lichess » avec niveau adaptatif par thème

- Nouveau script `preparer_puzzles_lichess.py` (hors-ligne, sans accès
  réseau) : lit le CSV de la base ouverte Lichess (licence CC0, décompressé,
  `.gz` via la stdlib, `.zst` via le module tiers optionnel `zstandard` sinon
  message clair pour décompresser à la main), filtre les problèmes fiables
  (Rating 800-2200, RatingDeviation ≤ 100, NbPlays ≥ 500, Popularity ≥ 80),
  classe chacun dans les 16 catégories de thème et par phase
  (opening/middlegame/endgame), échantillonne au plus 200 problèmes par
  (catégorie, tranche de note de 100 points), affiche un résumé et écrit
  `data/puzzles_lichess.json` (donnée personnelle, hors git). CSV d'essai
  fourni à la racine (`puzzles_lichess_exemple.csv`, 34 lignes, tous thèmes,
  mats en un/plusieurs coups, quelques lignes volontairement hors filtre).
- Nouveau module `lichess_puzzles.py` : les 16 catégories de niveau
  (clouage, attaque à la découverte, coup défensif, coup silencieux,
  zugzwang, finale de tours, finale, finale de pions, roi exposé,
  attraction, attaque sur l'aile roi, pion avancé, sacrifice, mat,
  fourchette, milieu de jeu) avec leur libellé FR ; valeur de départ par
  catégorie pondérée vers 1471 (performance Lichess globale d'Alain) selon
  le nombre de problèmes déjà faits dans cette catégorie
  (`(n*perf+5*1471)/(n+5)`, poids réglable) ; tirage pondéré par catégorie
  (favorise les niveaux bas, `poids=1/niveau`) puis par fenêtre de note
  (±100, élargie par paliers si vide) en réutilisant tel quel
  `exercise_history.choisir_exercice` (clé d'historique
  `"lichess:<PuzzleId>"`, pas une FEN — même fichier
  `exercice_historique.json` que la source "Mes erreurs", sans collision) ;
  mise à jour du niveau selon la formule Elo après chaque résultat (pas
  réglable `PAS_ELO=28`, borné à [400, 3000]), persistée dans
  `data/niveau_exercices_lichess.json`.
- `config.py` : `LICHESS_PUZZLES_PATH`/`LICHESS_NIVEAUX_PATH` (sous
  `DATA_DIR`, gitignorés).
- `app.py` : `exercise_new`/`exercise_answer` acceptent `data.source`
  (`"mes_erreurs"` par défaut, inchangé, ou `"lichess"`). Branche dédiée
  `_on_exercise_new_lichess`/`_on_exercise_answer_lichess` : jugement du
  premier coup (réussi si identique à la solution, s'il donne mat — y
  compris un mat différent de la solution — ou s'il est équivalent d'après
  Stockfish réel : perte < 30cp, `SEUIL_PUZZLE_EQUIVALENT_CP`, plus strict
  que le seuil "bon" 50cp de "Mes erreurs" car la solution Lichess est
  unique par construction, ou garde-fou "position déjà décidée" détecté) ;
  "meilleur coup"/ligne jouable = la solution déclarée du problème (jamais
  une ligne recalculée par Stockfish) ; aucun `coup_reel` transmis pour
  cette source ; met à jour le niveau de la seule catégorie ayant servi au
  tirage, même si le problème porte plusieurs thèmes de catégorie.
- `llm_coach.py` : `_build_context_text` ajoute thèmes/note du problème/
  niveau d'Alain dans la catégorie quand transmis ; nouvel addendum système
  `_EXERCISE_LICHESS_ADDENDUM` (réponse courte, pas de "coup réel à
  l'époque") ajouté en complément de `_EXERCISE_SYSTEM_ADDENDUM` existant.
- `templates/index.html`/`static/exercise.js` : sélecteur de source ("Mes
  erreurs"/"Problèmes Lichess") à côté du sélecteur de phase (desktop) et
  dans la feuille "Nouvel exercice" (mobile, pilote le même `<select>`) —
  désactivé avec une phrase explicite si `data/puzzles_lichess.json` est
  absent (`lichess_puzzles_disponible`, calculé au démarrage, rendu côté
  serveur). "Exercice suivant"/"Autre catégorie" conservent la source
  choisie (`exerciseCurrentSource`, même mécanisme que `exerciseCurrentPhase`
  pour la phase, issue #76). Ligne d'état dédiée `#exercise-lichess-info`
  ("Problème `<note>` · ton niveau en `<catégorie>` `<niveau>`"). La ligne
  "Solution du problème" réutilise le tableau "Lignes du coach"/le mécanisme
  Play existants (`_exerciseAddStockfishLine`, libellé conditionnel selon la
  source). Source "Mes erreurs" inchangée (code intact, juste un paramètre
  `source` supplémentaire par défaut sur sa valeur historique).
- `engine_stockfish.py` : nouvelle constante `SEUIL_PUZZLE_EQUIVALENT_CP`
  (30cp), documentée en regard de `SEUIL_IMPRECISION` pour reconnaître le
  garde-fou "position déjà décidée".
- `CONTEXTE.md` : section dédiée (format du pool, commande de préparation,
  catégories, formule et paramètres du niveau, jugement, interface).

### Tests
Sur `puzzles_lichess_exemple.csv` (34 lignes) :
`preparer_puzzles_lichess.py` → 24 problèmes conservés, 9 écartés par le
filtre de fiabilité, 1 sans catégorie connue, les 16 catégories toutes
représentées après échantillonnage. Tirages directs (`lichess_puzzles`) :
notes toujours dans la fenêtre, thèmes conformes à la phase demandée pour
`toutes`/`opening`/`middlegame`/`endgame`, jamais deux fois le même problème
de suite sur un pool restreint. Mise à jour Elo : 8 réussites font monter le
niveau, 20+500 échecs le font redescendre sans jamais sortir de [400, 3000],
500 réussites ne dépassent jamais 3000. Jugement avec un **vrai moteur
Stockfish** (`/usr/games/stockfish`) : coup identique à la solution (mat en
1, Scholar's mate) → réussi ; mat différent de la solution (position à deux
mats construite pour le test) → réussi ; coup équivalent (double reprise de
cavalier, delta 0cp) → réussi ; coup clairement hors-sujet → raté. Scénario
serveur complet (`app.py`, sans passer par un vrai réseau SocketIO,
handlers appelés directement avec `emit`/`llm_coach.get_coach_response`
interceptés) : tirage, réponse, historique ("déjà fait" après coup),
niveau Elo mis à jour et persisté, source "Mes erreurs" inchangée (pool
vide → erreur propre), source Lichess désactivée proprement si le fichier
est absent même en forçant l'événement socket côté client. Contenu exact
envoyé au coach vérifié (`source_lichess`, `themes_lichess`,
`rating_probleme`, `niveau_categorie`, `categorie_libelle`, absence de la
clé `coup_reel`) — **aucun appel réseau réel à l'API Claude** n'a été fait
(aucune clé API dans le worktree, conformément au périmètre strict : la clé
réelle d'Alain vit dans `~/ChessCoach/.env`, hors périmètre), conformément
au repli prévu par l'énoncé. UI vérifiée avec un vrai navigateur
(Playwright/Chromium) : sélecteur de source et ligne d'état sur desktop et
en émulation mobile 390×750 (aucun débordement horizontal), feuille mobile,
"Exercice suivant" conservant phase+source, désactivation propre de la
source (option et pill grisées, message explicatif, garde-fou serveur même
en forçant l'événement) quand `data/puzzles_lichess.json` est absent.
Toutes les données de test ont été isolées sous `/tmp` (chemins de
configuration redirigés avant import) — aucune donnée personnelle réelle
sous `~/ChessCoach/data` n'a été modifiée par ces tests.
