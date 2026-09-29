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

Quand l'API répond que le crédit est épuisé (HTTP 403, `error.type ==
"billing_error"`), `_call_claude` lève `CreditInsuffisantError` plutôt que la
`ValueError` générique ; tous les gestionnaires SocketIO renvoient alors
`error: "credit_insuffisant"` et le client affiche un message clair (bulle
dédiée dans le chat coach, ou message inline selon le mode) avec un lien vers
la Console pour recharger, au lieu d'une erreur technique.

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
