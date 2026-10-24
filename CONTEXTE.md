# ChessCoach — Contexte du projet

## Objectif
Application de coaching échecs personnelle pour Alain (pas AlChess, pas Jess).
Plateau virtuel uniquement, import de parties PGN (Chess.com / Lichess), coach
conversationnel via l'API Claude épaulé par Stockfish, mémoire JSON du coach
entre les sessions (comme un vrai coach qui se souvient de la progression).

## Architecture
Projet séparé d'AlChess : dépôt AlainDelree/Chesscoach, périmètre ~/ChessCoach.
Application mono-utilisateur, sans i18n ni support Chessnut (historique de la
migration/adaptation des modules AlChess : voir CHANGELOG.md).

## Carte des fichiers
Tous les modules sont à la racine du dépôt — le dossier `export_chesscoach/`
évoqué dans d'anciennes notes n'existe pas :
- `app.py` — serveur Flask, routes, handlers SocketIO, logique de jeu
- `engine_stockfish.py` — `EngineManager`, moteurs UCI (jeu, finales, éval)
- `llm_coach.py` — appels Claude/Mistral, construction du contexte, mémoire
  du coach
- `game_facts.py` — faits de position formatés en texte pour le coach
- `lichess_puzzles.py` — pool et niveau adaptatif des problèmes Lichess
- `library_manager.py` — import PGN mono/multi-parties
- `socketio_pgn_handlers.py` — handlers SocketIO (`register_pgn_library_handlers`)
- `config.py` — chemins, variables d'environnement, choix de modèle LLM
- `static/*.js`, `templates/index.html` — plateau, chat coach, interface

(et d'autres scripts utilitaires à la racine : préparation de données,
rapports, tests — voir le dépôt.)

## Données personnelles
Deux fichiers PGN (Chess.com + Lichess, ~1 an de parties d'Alain) déposés dans
data/pgn_import/. DATA_DIR (dossier data/) doit être gitignoré — le dépôt est
public, les données personnelles ne doivent jamais y être committées.

## Conventions spécifiques à ce projet

Règles de rédaction de CE fichier, pour les agents qui l'éditent :
1. N'y écrire que ce dont un agent a besoin AVANT d'écrire du code (invariant,
   convention, interface, piège) ; ce que l'issue a *fait* va au changelog,
   jamais ici.
2. Remplacer, ne pas empiler : une issue qui modifie une fonctionnalité édite
   la section ou la fiche existante, sans ajouter une section « (issue #N) »
   à côté de l'ancienne.
3. Dès qu'un sujet dépasse environ 6 lignes ou décrit une interface, un format
   ou des options, il part dans `docs/contexte/` avec une seule ligne de
   renvoi ici (chemin de la fiche).
4. Une issue qui rend un passage faux le corrige ou le supprime dans le même
   commit, et le dit dans son rapport.
5. Citer des noms réels (fichier et symbole) ; interdiction de « pour toi »/
   « pour Alain » à côté d'un chiffre signé ; un nom de champ n'a qu'un seul
   sens — si deux chemins du code lui donnent un sens différent, le dire
   explicitement.

Conventions du projet :
- Toute modification de code passe par une issue Bridge_Agent
  (PROJET | chesscoach), même petite.
- CCL committe en local uniquement — jamais de push automatique.
- Application personnelle mono-utilisateur : pas de gestion multi-comptes,
  pas de i18n.

## Invariants et pièges

**Convention de signe Lichess (issue #128, formulation précisée par #134)** :
tous les centipions et soldes matériel transmis aux IA et au journal
(contexte du chat, mode Exercice, question de suivi, `non_regression_coach.py`)
suivent la convention de Lichess — + = avantage Blancs, − = avantage Noirs —
SANS conversion vers le camp d'Alain. Ne jamais écrire « pour toi »/« pour
Alain »/« en ta faveur »/« tu restes mieux » à côté ou à proximité d'un
chiffre signé : nommer qui est mieux par la couleur (« les Blancs »/« les
Noirs »), chiffre à l'appui tel quel, et réserver « toi »/« tu » à une phrase
sans aucun chiffre. Position considérée égale si la valeur absolue de
l'évaluation est inférieure à 30 centipions. La barre d'évaluation de
l'affichage reste hors périmètre de l'issue #128 (non retouchée depuis).
Détail, fonctions modifiées et contrôles déterministes du vérificateur
(`fact_checker.py`) : fiche `convention_signe`.

**Classification des coups — double système (issue #125)** : la SÉLECTION
des exercices (`erreurs_detectees.json`, `build_patterns_erreurs.py`) utilise
des seuils fixes en centipions (`engine_stockfish.SEUIL_ERREUR` = 300,
`SEUIL_IMPRECISION` = 100) ; le verdict AFFICHÉ et transmis au coach utilise
la méthode officielle Lichess (chute des chances de gain, cp plafonné à
±1000). Le champ `verdict_qualite` a donc deux sens selon le chemin : verdict
officiel Lichess dans le contexte envoyé aux IA, ancienne méthode (seuils
fixes) dans le journal et dans `non_regression_coach.py` (qui porte aussi
`verdict_qualite_ancien`). Formule et exemples chiffrés : fiche
`classification_coups`.

**Modèle Claude — `config.LLM_MODEL` relu à chaque appel (issue #61)** :
jamais copié au démarrage — `config.set_llm_model(model_id)` le réassigne
directement en mémoire, effet immédiat sur tous les chemins d'appel. Un
modèle devenu indisponible (HTTP 404) lève `ModeleIndisponibleError`, avec
repli automatique sur l'autre modèle connu. Détail : fiche `modele_llm`.

**Température — piège Sonnet 5 (issue #116/#118)** : `claude-sonnet-5`
refuse le paramètre `temperature` (déprécié pour ce modèle) — avec ce
modèle, `CHESSCOACH_CLAUDE_TEMPERATURE` n'a donc aucun effet, et la
comparaison Claude/Mistral à température identique reste impossible tant
qu'il est utilisé. Un refus API (Claude ou Mistral) est géré par un réessai
sans le paramètre. Détail : fiche `temperature_llm`.

**Accès distant et debug (issue #49/#51)** : l'appli écoute sur toutes les
interfaces (`0.0.0.0:5000`) mais `_FiltreAccesDistant` (app.py) n'accepte que
la boucle locale et le réseau Tailscale (`100.64.0.0/10`) — tout le reste
reçoit un 403. Mode debug Flask désactivé par défaut (le débogueur
interactif pourrait être joignable depuis le réseau local) : après une
modification du code, il faut relancer l'appli à la main. `CHESSCOACH_DEBUG_DEV=1`
réactive le rechargement automatique pour le développement local (écoute
alors restreinte à `127.0.0.1`, jamais combinée avec `0.0.0.0`/Tailscale).
Détail (adresse Tailscale, mode d'emploi téléphone) : fiche
`syzygy_tailscale`.

**Tables de finales Syzygy (issue #32)** : chemin `~/ChessCoach/engines/syzygy/`
(`config.SYZYGY_PATH`, créé automatiquement, gitignoré) — Alain y dépose les
fichiers Syzygy à la main, aucun téléchargement automatisé par CCL.
Détection au démarrage de chaque instance moteur, dégradation gracieuse (log
informatif, pas d'erreur) si le dossier est vide ou absent. Le moteur dédié
au mode "travail de finales" (`get_move_finales`, engine_stockfish.py) tourne
en pleine force (`UCI_LimitStrength` désactivé), contrairement au moteur Elo
limité du mode partie libre. Détail : fiche `syzygy_tailscale`.

**Lignes calculées et prises en échange (issues #126/#128)** : une ligne
calculée (PV) présentée au coach est limitée à 4 coups, prolongée d'au plus 2
coups tant que le dernier coup retenu est une capture (`_couper_pv`,
engine_stockfish.py ; même règle côté `game_facts.describe_pv_facts`) — pour
ne jamais arrêter la ligne au milieu d'un échange. « En prise » est un vrai
calcul d'échange sur la case (`game_facts._gain_capture`), clouages compris
— un défenseur cloué ne compte pas.

**Mode série, étape 1/3 (issue #139, suite #125)** : interrupteur côté
client (`static/exercise.js`, `localStorage`, désactivé par défaut),
transmis au serveur dans `exercise_answer.mode_serie` — si vrai,
`app.on_exercise_answer`/`_on_exercise_answer_lichess` s'arrêtent juste
après le verdict Stockfish et émettent `exercise_serie_verdict` (une seule
ligne, `_construire_ligne_verdict_serie`) au lieu d'appeler Claude/Mistral
(aucune entrée dans `coach_calls.log`). État TEMPORAIRE : aucune file
d'attente ni compteur d'avis en cours (prévus à l'étape 2) — ne pas
construire par-dessus sans relire la fiche. Détail : fiche `mode_serie`.

## Mémoire du coach (coach_memory.json, dans DATA_DIR)
Schéma : profil, patterns_erreurs (ouverture / milieu_de_partie / finale),
repertoire_ouvertures (blancs / noirs), historique_sessions (résumés par
session, pas les parties complètes), objectifs_courants.

## Fiches de détail (docs/contexte/)
- `docs/contexte/compteur_tokens.md` — compteur de tokens consommés
  (usage_tokens.json), interface, détection tolérante des erreurs de crédit,
  champs du journal.
- `docs/contexte/modele_llm.md` — sélecteur Haiku/Sonnet depuis
  l'interface, persistance du choix, repli sur `ModeleIndisponibleError`.
- `docs/contexte/jetons_mistral_cout.md` — jetons Mistral dans le journal,
  table de prix par modèle, script `scripts/estimer_cout_api.py`.
- `docs/contexte/temperature_llm.md` — variables de température
  Claude/Mistral, gestion des refus API, journalisation.
- `docs/contexte/exercices_lichess.md` — source d'exercices « Problèmes
  Lichess » : préparation hors-ligne, format du pool, niveau adaptatif,
  jugement du coup, interface.
- `docs/contexte/suivi_version.md` — détection de version du code,
  étiquette de série (CHESSCOACH_SERIE), enregistrement dans les journaux,
  rapport groupé par version.
- `docs/contexte/classification_coups.md` — formule officielle Lichess,
  seuils, exemples chiffrés, champs transmis au coach.
- `docs/contexte/convention_signe.md` — détail de la convention de signe
  Lichess, liste des fonctions modifiées.
- `docs/contexte/syzygy_tailscale.md` — adresse Tailscale, mode d'emploi
  depuis le téléphone, détail de l'accès distant et des tables Syzygy.
- `docs/contexte/mode_serie.md` — interrupteur mémorisé côté navigateur,
  verdict Stockfish en une ligne sans appel aux IA (étape 1/3, issue #139).
