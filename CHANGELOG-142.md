# Changelog — Issue #142

## Issue #142 — Suite #141 : page « club » servie par ChessCoach et points d'accès pour juger un coup quelconque (étape 2/4)

But : montrer à quelqu'un du club, sur son propre téléphone via Tailscale,
une page où la personne joue un coup dans une position et lit l'avis du
coach sur SON coup, pour comparer son raisonnement à celui du coach.
L'affichage (plateau, barre d'évaluation, boutons de vue, jugements) est
l'objet de l'étape #4 ; cette issue fournit seulement le serveur.

**Route de page** : `GET /club` sert `static/club.html`
(`app.send_static_file`) — fichier statique minimal (« Page club : en
construction »), sans gabarit Jinja. Aucun changement d'adresse ni
d'interface d'écoute du serveur.

**`POST /api/club/avis`** : reçoit `{"fen", "coup" (SAN ou UCI), "camp"
(optionnel)}` et se comporte exactement comme `on_exercise_answer` pour la
source « Position précise » (aucun coup de l'époque) — même calcul
Stockfish (`_evaluate_move_for_coach`), même contexte construit par
`app._construire_contexte_coup_exercice` (issue #141, réutilisée sans
aucune duplication), même prompt système et addendum d'exercice, même
format standard des avis, même vérificateur, même convention de signe
Lichess. Seul Claude est appelé (`llm_coach.get_coach_response`) — jamais
Mistral, quelle que soit `config.MISTRAL_API_KEY`. Réponse JSON : avis
complet, sections lues et conformité du format, verdict officiel, perte en
centipions, meilleur coup, évaluations avant/après (convention Lichess),
fiabilité et alertes du vérificateur, identifiant de l'avis dans le
journal.

**`POST /api/club/eval`** : évaluation Stockfish seule (`eval_blancs_cp`/
`eval_blancs_mat`, convention Lichess) et les trois meilleurs coups, sans
aucun appel IA, via le gestionnaire de moteur déjà lancé (`engine_manager`
— jamais un nouveau processus Stockfish par requête).

**`POST /api/club/jugement`** : enregistre `{"log_id", "jugement"
("accord"|"desaccord"|"partiel"), "etiquettes" (optionnel), "remarque"
(optionnel)}` dans `config.CLUB_JUGEMENTS_LOG_PATH` (une ligne JSON par
jugement) — jamais dans `coach_ratings.jsonl`.

**Journal** : chaque avis « club » est journalisé par
`llm_coach._log_coach_call` avec `context["mode_origine"] = "club"` (au
lieu de `"exercice"`) et `context["via_club"] = True`. Vérifié dans le code
de `scripts/controle_avis.py` : son filtre ne retient que
`mode_origine == "exercice"` — les avis « club » en sont donc exclus par
construction, jamais mélangés avec les notes d'Alain.

**Limite d'appels au coach** : `app.CLUB_MAX_AVIS_PAR_JOUR` (40) — compteur
`{"date", "count"}` persisté sur disque (`config.CLUB_AVIS_COMPTEUR_PATH`,
survit à un redémarrage), remis à zéro à minuit heure locale. Au-delà,
`/api/club/avis` répond 429 (« limite_quotidienne_atteinte ») SANS appeler
l'API. `app.CLUB_MAX_APPELS_SIMULTANES` (2) : au-delà, réponse 503
(« occupe ») SANS appel. Les requêtes invalides (FEN invalide, coup
illégal/ambigu) ne consomment ni la limite quotidienne ni les emplacements
de concurrence — validées avant tout calcul Stockfish ou appel IA.

**Tests (`test_issue142_page_club.py`, 15 tests, exécuté séparément des
autres fichiers de test comme `test_issue128.py`)** : route `/club`, avis
pour les deux camps avec contexte strictement identique à celui de
`on_exercise_answer`/« Position précise » pour la même position et le même
coup (seule la ligne citant littéralement « mode club »/« mode exercice »
diffère, par construction), coup illégal, coup ambigu, FEN invalide,
limite quotidienne atteinte (constante réduite temporairement dans le
test — la troisième requête est refusée sans appel simulé), compteur
persistant après rechargement du module (`importlib.reload`), au plus 2
appels simultanés (le troisième répond « occupé » sans appel), Mistral
jamais appelé même avec une clé factice configurée, entrée de journal avec
`mode_origine="club"` absente du filtre de `scripts/controle_avis.py`,
`/api/club/eval` avec signes corrects sur deux positions connues (Blancs
mieux / Noirs mieux), jugement enregistré dans le bon fichier (et absence
dans `coach_ratings.jsonl`).

Vérification de non-régression : `test_issue128.py`, `test_issue134.py`,
`test_issue135.py`, `test_issue137_signe_eval_lichess.py`,
`test_issue139_mode_serie.py`, `test_issue140_mode_serie_ia_arriere_plan.py`
et `test_issue141_golden_master.py`, chacun exécuté séparément — tous OK,
aucun test ignoré ni désactivé (détail des comptes dans le rapport de
clôture).

Documentation : nouvelle fiche `docs/contexte/page_club.md` (routes,
limites, journalisation) ; une ligne ajoutée dans les invariants de
`CONTEXTE.md` (section « Construction du contexte coach... ») renvoyant
vers cette fiche.
