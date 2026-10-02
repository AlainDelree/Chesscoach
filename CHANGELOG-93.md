# Changelog — Issue #93

## Script de non-régression du coach : rejouer des positions où le coach s'est trompé

Plusieurs explications fausses du coach ont été relevées et corrigées en
série (issues #87, #90, #91...) : tour inexistante citée, coup qualifié
« illégal » à tort, « échange de dames » pour une dame prise contre une
tour, « dame clouée » alors qu'elle ne l'est pas, « équilibre matériel »
annoncé alors qu'un camp est en avance. Jusqu'ici, vérifier qu'une
modification du prompt ou des données n'aggrave pas un de ces cas obligeait
à retester à la main sur le téléphone.

### 1. Fichiers de cas (`tests/cas_coach/*.case`)

- Format texte simple (`clé: valeur` / blocs indentés, commentaires `#`),
  documenté dans `tests/cas_coach/README.md` : identifiant, description,
  source, FEN de départ, camp d'Alain, coup proposé, meilleur coup attendu,
  faits attendus dans les données envoyées au coach, motifs interdits/
  attendus dans la réponse du coach, pastille de fiabilité attendue.
- Trois cas créés : `re3_dame_contre_tour` (issue #91 — gain de dame mal
  qualifié d'« échange », dame non clouée dite « clouée », matériel dit
  « équilibré »), `c4_bxc6_bxc6_reste_verte` (issue #90 — la suite
  « Bxc6+ bxc6 » ne doit plus être signalée illégale), `h4_menace_gxh3_defensif`
  (issue #80 — h4 pare une menace réelle, ne doit pas être présenté comme
  offensif).
- Deux cas supplémentaires tirés de `parties_test_coach.pgn` (parties sans
  erreur connue) étaient prévus par l'issue mais n'ont pas pu être créés :
  ce fichier n'est pas présent dans le périmètre du projet traité ici.

### 2. Script (`non_regression_coach.py`, racine du projet)

- Reconstruit, pour chaque cas, exactement le contexte envoyé au coach par
  le mode « Exercice » (mêmes fonctions que l'application —
  `game_facts.py`, `coach_reliability.py`, `engine_stockfish.py` — avec un
  vrai Stockfish lancé par le script lui-même, jamais via l'interface, une
  connexion SocketIO, ou l'instance de l'application en cours d'exécution).
- Vérifie les faits attendus (`faits_attendus`) sur ce contexte : par
  défaut une sous-chaîne cherchée dans le texte réellement injecté dans le
  system prompt (`llm_coach._build_context_text`), ou une directive dédiée
  (`camp_sans_tour`, `camp_a_une_tour`, `aucune_piece_clouee`,
  `menace_significative_contient`, `reponse_simulee_verte` — ce dernier
  rejoue `coach_reliability.evaluer_fiabilite` sur un texte simulé, sans
  appel API, utile pour les régressions de détection).
- Deux contrôles systématiques, même sans `faits_attendus` : coup proposé
  légal sur le FEN, et meilleur coup recalculé par le vrai Stockfish
  conforme au `meilleur_coup` attendu du cas.
- Option `--api` (désactivée par défaut, pour que la commande de base ne
  dépense rien) : appelle réellement le coach (`llm_coach.get_coach_response`,
  modèle `--modele sonnet|haiku`, défaut = modèle actif de l'application)
  et vérifie sa réponse (aucun motif interdit, motifs attendus présents,
  pastille conforme), répété `--repetitions` fois par cas (3 par défaut —
  la réponse d'un modèle de langage varie d'un appel à l'autre). Affiche
  une estimation du nombre d'appels avant de les lancer.
- Options `--cas ID [ID...]` (sous-ensemble de cas), `--verbose` (détail
  des réponses fautives). Résumé final en tableau (faits OK/KO, réussites
  X/N), liste des échecs avec motif et extrait de réponse, code de sortie
  non nul en cas d'échec.

### 3. Isolation

- Jamais de lecture/écriture de `coach_memory.json`, `erreurs_detectees.json`,
  `exercice_historique.json`, `coach_calls.log` ni `signalements.log` —
  mémoire de progression neutre (`{}`) passée à `get_coach_response`,
  journal dédié `data/logs/non_regression_coach_calls.log` (chemin relatif
  au script lui-même, jamais `config.DATA_DIR`), aucun `usage_path` (le
  compteur de tokens personnel n'est jamais modifié).
- Aucune connexion à une instance de l'application en cours d'exécution :
  instance Stockfish propre au script, jamais `app.py`/Flask/SocketIO.
- Seule exception, en lecture seule et à la demande explicite d'Alain :
  `--depuis-signalement` lit `signalements.log` pour créer un squelette de
  cas (FEN/coup/camp pré-remplis, réponse fautive citée en commentaire).

### 4. Tests réalisés (sans clé API dans l'environnement — `.env` non lu)

- Lancement sans `--api` : faits vérifiés avec succès sur les 3 cas
  (vrai Stockfish).
- Simulation d'une réponse correcte (`llm_coach._call_claude` remplacé) :
  cas réussi, code de sortie 0. Simulation d'une réponse fautive (motif
  interdit présent) : cas échoué, code de sortie 1, extrait affiché avec
  `--verbose`.
- `--cas <id>` (sélection), estimation du nombre d'appels affichée avant
  `--api`, isolation vérifiée par empreinte MD5 de `~/ChessCoach/data`
  avant/après (identique), création d'un squelette depuis un signalement
  factice (fichier temporaire, jamais le vrai `signalements.log`).
- Aucun appel API réel n'était possible dans cet environnement (clé absente,
  `.env` volontairement non lu).
