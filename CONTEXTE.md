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

## Conventions spécifiques à ce projet
- Toute modification de code passe par une issue Bridge_Agent
  (PROJET | chesscoach), même petite.
- CCL committe en local uniquement — jamais de push automatique.
- Application personnelle mono-utilisateur : pas de gestion multi-comptes,
  pas de i18n.
