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
