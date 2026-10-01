# ChessCoach — Contexte du projet

## Objectif
Application de coaching échecs personnelle pour Alain (pas AlChess, pas Jess).
Plateau virtuel uniquement, import de parties PGN (Chess.com / Lichess), coach
conversationnel via l'API Claude épaulé par Stockfish, mémoire JSON du coach
entre les sessions (comme un vrai coach qui se souvient de la progression).

## Architecture
Projet séparé d'AlChess : dépôt AlainDelree/Chesscoach, périmètre ~/ChessCoach.
Réutilise des modules adaptés d'AlChess, débarrassés de tout ce qui est
spécifique à AlChess (trilingue FR/EN/DE, mode pédagogique débutant, hardware
Chessnut).

## Modules déjà présents (export_chesscoach/)
- library_manager.py — import PGN mono/multi-parties
- socketio_pgn_handlers.py — 6 handlers SocketIO (register_pgn_library_handlers)
- llm_coach.py — adapté de llm_explainer.py AlChess (issue #196) : system
  prompt + appel Claude + conversation multi-tours + load_coach_memory/
  save_coach_memory (fichier mémoire JSON externe)
- engine_stockfish.py — EngineManager (UCI générique), Maia/Rodent IV retirés
- static/board.js, static/board.css — plateau, matériel, flèches, barre
  d'éval, chat coach (renommé coach*) ; i18n, sync Chessnut, sauvegarde
  NicLink retirés

## Données personnelles
Deux fichiers PGN (Chess.com + Lichess, ~1 an de parties d'Alain) déposés dans
data/pgn_import/. DATA_DIR (dossier data/) doit être gitignoré — le dépôt est
public, les données personnelles ne doivent jamais y être committées.

## Tables de finales Syzygy (issue #32)
Chemin exact : `~/ChessCoach/engines/syzygy/` (SYZYGY_PATH dans config.py,
créé automatiquement s'il n'existe pas, gitignoré). Alain y dépose
manuellement les fichiers Syzygy 3-4-5 pièces (depuis
https://tablebase.lichess.ovh/tables/standard/, ~1 Go) — pas de
téléchargement automatisé par CCL. engine_stockfish.py détecte leur présence
au démarrage de chaque instance moteur et configure l'option UCI SyzygyPath
en conséquence ; dossier vide ou absent → dégradation gracieuse (log
informatif, pas d'erreur), même pattern que le livre Polyglot (issue #9).
Le moteur dédié au mode "travail de finales" (jeu normal et démonstration,
`get_move_finales` dans engine_stockfish.py) n'est plus plafonné en Elo
(UCI_LimitStrength désactivé) — avant l'issue #32 il réutilisait par erreur
le moteur Elo limité (~1500) du bouton "Coup Stockfish" du mode partie
libre, ce qui dégradait les techniques de mat longues et précises.

## Mémoire du coach (coach_memory.json, dans DATA_DIR)
Schéma : profil, patterns_erreurs (ouverture / milieu_de_partie / finale),
repertoire_ouvertures (blancs / noirs), historique_sessions (résumés par
session, pas les parties complètes), objectifs_courants.

## Compteur de tokens consommés (usage_tokens.json, dans DATA_DIR — issue #54)
Le solde restant de la clé API n'est pas lisible par programme (il n'existe
que sur la Console platform.claude.com) et Alain préfère ne pas maintenir de
table de prix par modèle côté ChessCoach : le compteur affiche donc
uniquement des tokens bruts, sans aucun prix ni équivalent en argent — à
charge pour lui de rapprocher ce compte du solde réel affiché sur la
Console.

À chaque appel réussi à l'API Claude (tous les chemins : chat du coach,
explications de coups, programme d'entraînement, commentaires des modes
ouverture/finales/pédagogique/exercice), `_call_claude` (llm_coach.py) relève
les tokens d'entrée/de sortie/de cache (création et lecture) déjà présents
dans la réponse de l'API (`usage`, aucun appel supplémentaire) et les cumule
dans `data/usage_tokens.json` via `_record_usage`/`_save_usage`, par modèle
réellement utilisé (`data["model"]` de la réponse, pas le paramètre d'entrée
qui peut être un alias ou vide). Le fichier garde aussi une date de départ du
cumul et le détail du dernier appel ; il survit donc à un redémarrage de
l'appli (comme coach_memory.json), et reste hors du dépôt (sous DATA_DIR,
gitignoré).

Côté interface, l'en-tête affiche un texte discret à côté du lien
« Coût API » (`#usage-tokens-widget` dans templates/index.html, logique dans
static/usage_tokens.js) : tokens du dernier appel et total cumulé depuis la
date de départ, entrée/sortie séparées. Le détail par modèle apparaît au
survol (desktop) ou au tap (mobile, via une bascule de classe CSS) — un token
n'a pas le même « coût » selon le modèle utilisé, ce détail doit donc rester
consultable même si le résumé affiché est compact. Sur écran étroit (media
query `max-width: 900px`), le texte bascule vers une forme courte
(`Σ … in / … out`) pour ne pas déborder de l'en-tête. Un bouton « Remettre le
compteur à zéro » (dans le détail, avec confirmation `confirm()` légère)
réinitialise le fichier entier, y compris la date de départ.

Quand l'API répond que le crédit est épuisé, `_call_claude` lève
`CreditInsuffisantError` plutôt que la `ValueError` générique ; tous les
gestionnaires SocketIO renvoient alors `error: "credit_insuffisant"` et le
client affiche un message clair (bulle dédiée dans le chat coach, ou message
inline selon le mode) avec un lien vers la Console pour recharger, au lieu
d'une erreur technique. Détection tolérante (issue #60) plutôt que basée sur
un unique couple (code HTTP, type) : `error.type == "billing_error"` quel que
soit le code HTTP, ou HTTP 402, ou HTTP 400 `invalid_request_error` dont le
message mentionne le solde/les crédits (ex. « credit balance », « Plans &
Billing »), insensible à la casse — la forme exacte renvoyée par l'API pour
ce cas n'est pas garantie stable dans le temps et ne peut pas être vérifiée
sans épuiser réellement un crédit. Les vraies erreurs de permission (403
`permission_error`) et les vraies requêtes invalides (400 sans mention de
crédit) restent distinguées et ne déclenchent pas ce message.

Chaque appel loggé dans `data/logs/coach_calls.log` porte désormais aussi son
propre champ `usage` (tokens de cet appel précis, ou `null` si l'appel n'a
pas abouti), en complément du compteur cumulé, pour le diagnostic. Depuis
l'issue #61, chaque entrée porte aussi un champ `model` explicite (le
paramètre transmis à cet appel précis), y compris sur les entrées d'erreur où
`usage` est absent — ce qui garde traçable, ligne à ligne, quel modèle a
réellement servi même après un changement de modèle en cours de session.

## Choix du modèle Claude (Haiku/Sonnet) depuis l'interface (issue #61)
Avant l'issue #61, le modèle était fixé une fois pour toutes par
`CHESSCOACH_LLM_MODEL` (.env) — changer de modèle imposait d'éditer le .env
et de relancer l'appli. Un petit sélecteur dans l'en-tête (`#llm-model-selector`
dans templates/index.html, juste avant le compteur de tokens), deux boutons
contigus « Haiku (test) » / « Sonnet (sérieux) » façon *segmented control*,
permet désormais de basculer sans redémarrage, sans interrompre la partie ni
effacer le chat en cours. Libellés complets en desktop, abrégés (premier mot)
sur écran étroit (media query `max-width: 900px`, même seuil que le reste de
l'en-tête) — comportement vérifié à 390×844 (aucun débordement horizontal).

Les deux identifiants de modèle sont définis une seule fois dans config.py :
`LLM_MODEL_HAIKU`/`LLM_MODEL_SONNET` (+ `LLM_MODEL_CHOICES`, le dict
id → libellé qui alimente à la fois le sélecteur et la validation du choix
reçu du client). `config.LLM_MODEL` reste l'attribut lu par tous les appels
API (`app.py` construit `llm_config["llm_model"]` à partir de
`config.LLM_MODEL` à chaque appel, jamais une copie figée au démarrage) —
`config.set_llm_model(model_id)` le réassigne directement en mémoire, d'où
l'effet immédiat sur tous les appels suivants, tous chemins confondus (chat
du coach, explications de coups, programme d'entraînement, commentaires des
modes ouverture/finales/pédagogique/exercice), sans exception à gérer côté
appelants puisque `config.LLM_MODEL` est relu, pas copié.

Persistance : `config.set_llm_model` écrit aussi le choix dans
`data/llm_model_choice.json` (`{"model": "..."}`), un petit fichier séparé du
`.env`, jamais modifié automatiquement — sous DATA_DIR, donc gitignoré comme
le reste des données personnelles. Au démarrage, `config.py` reprend ce
fichier s'il contient un choix valide ; à défaut (premier lancement, fichier
absent ou invalide), reprend `CHESSCOACH_LLM_MODEL` si sa valeur correspond à
l'un des deux choix connus, sinon Sonnet par défaut (jeu sérieux plutôt que
test).

Côté interface, le clic sur un bouton émet l'événement SocketIO
`set_llm_model` (`{"model": "..."}`) ; le serveur répond `llm_model_changed`
(bascule le bouton actif) ou, si `model_id` n'est ni Haiku ni Sonnet,
`llm_model_error` (n'arrive pas en usage normal, les deux boutons envoient
toujours un id connu — filet de sécurité défensif). Logique dans
static/llm_model.js.

Refus par l'API (modèle introuvable ou indisponible, HTTP 404
`not_found_error`) : `_call_claude` (llm_coach.py) lève désormais
`ModeleIndisponibleError`, distinguée de `CreditInsuffisantError` (issue
#54) et remontée par les 4 fonctions publiques (`get_coach_response`,
`get_move_explanations`, `get_opening_moves`, `get_training_program`) comme
`error: "modele_indisponible"`. Les 10 points d'appel API de app.py
partagent tous le même filet (`_handle_llm_model_indisponible_si_besoin`,
appelé au tout début de chaque bloc `if error:`) : comme il n'existe que deux
choix, revenir à « l'autre » est sans ambiguïté le choix précédent — le
serveur y revient seul (`config.set_llm_model`, donc persisté) et prévient le
client via l'événement `llm_model_indisponible`, qui remet à jour le
sélecteur ET affiche un message clair dans le chat (`static/llm_model.js`),
plutôt qu'une erreur technique brute ou un sélecteur resté sur un choix qui
ne répond plus.

Paramètres d'appel (`_call_claude`) : `max_tokens=4096` et
`thinking: {"type": "disabled"}` sont acceptés tels quels par les deux
modèles (vérifié auprès de la documentation API à jour) — Haiku ne raisonne
jamais nativement (`disabled` y est un no-op sans contrainte particulière),
et Sonnet 5 accepte explicitement `{"type": "disabled"}` comme l'omission du
paramètre. `max_tokens=4096` reste très en dessous des plafonds des deux
modèles (64K pour Haiku 4.5, 128K pour Sonnet 5). Aucune adaptation par
modèle n'a donc été nécessaire.

Le compteur de tokens par modèle (`usage_tokens.json`, issue #54) reste
cohérent après un changement de modèle en cours de session : `_record_usage`
cumule déjà par `data["model"]` (le modèle réellement résolu par l'API pour
CET appel, pas le paramètre d'entrée), donc un changement de sélection
n'affecte que les appels suivants — les compteurs déjà accumulés pour
l'ancien modèle restent inchangés dans `par_modele`.

## Source d'exercices « Problèmes Lichess » (issue #78)
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

## État d'avancement
- Issue #252 (projet alchess) : extraction/adaptation des modules — FAIT.
- Issue en cours (projet chesscoach) : squelette Flask minimal, config.py +
  DATA_DIR, câblage des modules entre eux, création de coach_memory.json vide,
  import des 2 PGN via library_manager.py. PAS encore d'analyse Stockfish/
  Claude sur l'historique à ce stade.

## Prochaines étapes prévues
1. Squelette Flask (en cours).
2. Passe d'analyse Stockfish/Claude sur l'historique PGN importé, pour
   préremplir patterns_erreurs et repertoire_ouvertures plutôt que de démarrer
   la mémoire vide.
3. index.html neuf, propre à ChessCoach (l'original AlChess était trop
   imbriqué dans le flux de partie pédagogique pour être réutilisé tel quel).

## Accès distant via Tailscale (issue #49)
L'appli écoute sur toutes les interfaces (`0.0.0.0:5000`) mais un middleware
WSGI (`_FiltreAccesDistant` dans app.py) n'accepte que la boucle locale
(127.0.0.1/::1) et le réseau Tailscale (100.64.0.0/10) ; toute autre origine
(LAN, wifi public) reçoit un 403 explicite. Le port 5000 et le mécanisme de
filtrage sont inchangés côté ThinkPad : l'alias `coach` continue d'ouvrir le
navigateur en local comme avant.

Pour ouvrir l'appli depuis le GSM (Tailscale actif des deux côtés) :
`http://100.92.48.81:5000` (adresse Tailscale du ThinkPad thinkpadcarbon7).
Le chat temps réel (Socket.IO) fonctionne aussi par cette adresse : la
vérification d'origine intégrée à Socket.IO compare l'Origin du navigateur
au Host de la requête, donc elle s'aligne automatiquement sur l'adresse
utilisée (locale ou Tailscale) sans configuration supplémentaire.

Mode debug Flask/Werkzeug désactivé par défaut (issue #51) : le débogueur
interactif expose une console web (protégée par un simple code PIN) qui
pourrait être servie avant `_FiltreAccesDistant` et donc potentiellement
joignable depuis le réseau local ou un wifi public. Conséquence pratique :
**après une modification du code, il faut relancer le coach à la main**
(plus de rechargement automatique). Réactivation volontaire pour le
développement local via `CHESSCOACH_DEBUG_DEV=1` — dans ce cas l'appli
n'écoute plus que sur `127.0.0.1` (jamais combiné avec l'écoute
`0.0.0.0`/Tailscale).

## Conventions spécifiques à ce projet
- Toute modification de code passe par une issue Bridge_Agent
  (PROJET | chesscoach), même petite.
- CCL committe en local uniquement — jamais de push automatique.
- Application personnelle mono-utilisateur : pas de gestion multi-comptes,
  pas de i18n.
