"""
app.py — ChessCoach, squelette Flask minimal

Crée l'application Flask + SocketIO, câble les handlers de bibliothèque
PGN (socketio_pgn_handlers.py / library_manager.py), charge la mémoire du
coach (llm_coach.py) et vérifie la présence de Stockfish (engine_stockfish.py)
sans lancer le moteur — l'analyse elle-même est l'objet d'une issue séparée.
"""

import logging

from flask import Flask, render_template
from flask_socketio import SocketIO, emit

import config
import llm_coach
from engine_stockfish import stockfish_available
from socketio_pgn_handlers import register_pgn_library_handlers

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("chesscoach.app")

app = Flask(__name__)
socketio = SocketIO(app)

register_pgn_library_handlers(socketio)

coach_memory = llm_coach.load_coach_memory(config.COACH_MEMORY_PATH)

if not stockfish_available():
    logger.warning("Stockfish introuvable sur ce système (analyse indisponible pour l'instant).")


@app.route("/")
def index():
    return render_template("index.html")


@socketio.on("coach_message")
def on_coach_message(data):
    """Relaie un tour de conversation au coach LLM (llm_coach.py)."""
    messages = data.get("messages", [])
    context = data.get("context", {})
    llm_config = {"llm_api_key": config.LLM_API_KEY, "llm_model": config.LLM_MODEL}

    response, error = llm_coach.get_coach_response(messages, context, coach_memory, llm_config)
    if error:
        emit("coach_error", {"message": error})
    else:
        emit("coach_response", {"message": response})


if __name__ == "__main__":
    # allow_unsafe_werkzeug : serveur de développement uniquement (pas de
    # déploiement en production prévu pour ce squelette).
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)
