"""
socketio_pgn_handlers.py — ChessCoach (extrait/adapté de nicsoft/web/server.py, AlChess)
Handlers SocketIO pour la bibliothèque PGN personnelle (voir library_manager.py).

Contrairement à AlChess (un seul process partagé pour la session de jeu),
ChessCoach n'a pas de machine d'état de partie en cours ni de contexte
multi-mode (pédagogique/humain/exercices) : ces handlers sont donc
autonomes, sans dépendance à un `_app_state` ou des queues inter-threads.

Câblage attendu côté ChessCoach : appeler `register_pgn_library_handlers(socketio)`
une fois l'objet Flask-SocketIO créé.
"""

from flask_socketio import emit

import library_manager


def register_pgn_library_handlers(socketio) -> None:
    """Enregistre les événements SocketIO de la bibliothèque PGN sur `socketio`."""

    @socketio.on("pgn_lib_list_collections")
    def on_pgn_lib_list_collections(_data):
        """Retourne la liste des collections de la bibliothèque PGN personnelle."""
        try:
            emit("pgn_lib_collections", {"collections": library_manager.list_collections()})
        except Exception as e:
            emit("pgn_lib_error", {"message": str(e)})

    @socketio.on("pgn_lib_create_collection")
    def on_pgn_lib_create_collection(data):
        """Crée une nouvelle collection."""
        try:
            library_manager.create_collection(data.get("name", ""))
            emit("pgn_lib_collections", {"collections": library_manager.list_collections()})
        except Exception as e:
            emit("pgn_lib_error", {"message": str(e)})

    @socketio.on("pgn_lib_delete_collection")
    def on_pgn_lib_delete_collection(data):
        """Supprime une collection."""
        try:
            library_manager.delete_collection(data.get("collection_id", ""))
            emit("pgn_lib_collections", {"collections": library_manager.list_collections()})
        except Exception as e:
            emit("pgn_lib_error", {"message": str(e)})

    @socketio.on("pgn_lib_import_pgn")
    def on_pgn_lib_import_pgn(data):
        """Importe un fichier PGN (une ou plusieurs parties, lichess/chess.com) dans une collection."""
        try:
            result = library_manager.import_pgn(data.get("collection_id", ""), data.get("content", ""))
            emit("pgn_lib_games", {
                "collection_id": data.get("collection_id", ""),
                "games":          library_manager.list_games(data.get("collection_id", "")),
                "import_result":  result,
            })
        except Exception as e:
            emit("pgn_lib_error", {"message": str(e)})

    @socketio.on("pgn_lib_list_games")
    def on_pgn_lib_list_games(data):
        """Retourne l'index des parties d'une collection."""
        try:
            collection_id = data.get("collection_id", "")
            emit("pgn_lib_games", {"collection_id": collection_id, "games": library_manager.list_games(collection_id)})
        except Exception as e:
            emit("pgn_lib_error", {"message": str(e)})

    @socketio.on("pgn_lib_load_game")
    def on_pgn_lib_load_game(data):
        """Charge le PGN d'une seule partie d'une collection."""
        try:
            collection_id = data.get("collection_id", "")
            index = data.get("index", -1)
            pgn = library_manager.load_game(collection_id, index)
            emit("pgn_lib_game_loaded", {"collection_id": collection_id, "index": index, "pgn": pgn})
        except Exception as e:
            emit("pgn_lib_error", {"message": str(e)})
