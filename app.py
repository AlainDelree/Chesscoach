"""
app.py — ChessCoach, squelette Flask minimal

Crée l'application Flask + SocketIO, câble les handlers de bibliothèque
PGN (socketio_pgn_handlers.py / library_manager.py), charge la mémoire du
coach (llm_coach.py) et vérifie la présence de Stockfish (engine_stockfish.py)
sans lancer le moteur — l'analyse elle-même est l'objet d'une issue séparée.
"""

import atexit
import json
import logging
import random
from pathlib import Path

import chess
from flask import Flask, render_template
from flask_socketio import SocketIO, emit

import config
import llm_coach
from engine_stockfish import EngineManager, find_stockfish
from socketio_pgn_handlers import register_pgn_library_handlers

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("chesscoach.app")

app = Flask(__name__)
socketio = SocketIO(app)

register_pgn_library_handlers(socketio)

coach_memory = llm_coach.load_coach_memory(config.COACH_MEMORY_PATH)


def _load_erreurs_detectees(path) -> list:
    """Charge le détail individuel des erreurs détectées (issue #7), utilisé
    par le mode "Exercice". Retourne [] si le fichier est absent ou illisible
    (build_patterns_erreurs.py pas encore relancé) : le mode exercice signale
    alors l'indisponibilité plutôt que de planter."""
    path = Path(path)
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Erreurs détectées illisibles ({path}) : {e}")
        return []


erreurs_detectees = _load_erreurs_detectees(config.ERREURS_DETECTEES_PATH)

# État de l'exercice en cours — application locale mono-utilisateur (cf.
# CONTEXTE.md), un seul exercice actif à la fois suffit.
_current_exercise: dict | None = None

# Moteur Stockfish partagé, utilisé par le mode "partie libre" (bouton "Coup
# Stockfish" / case "Stockfish joue auto") — cf. socketio_pgn_handlers.py pour
# la bibliothèque PGN, sans lien avec ce mécanisme.
_stockfish_path = find_stockfish()
engine_manager: EngineManager | None = None
if _stockfish_path:
    try:
        engine_manager = EngineManager(_stockfish_path)
    except Exception as e:
        logger.error(f"Impossible d'initialiser Stockfish : {e}")
else:
    logger.warning("Stockfish introuvable sur ce système (analyse et partie libre indisponibles).")

if engine_manager:
    atexit.register(engine_manager.quit)


@app.route("/")
def index():
    return render_template("index.html")


@socketio.on("coach_ask")
def on_coach_ask(data):
    """Relaie un tour de conversation au coach LLM (llm_coach.py).

    Nom d'événement et clés de payload alignés sur ce qu'émet/attend
    static/board.js (coachSend() émet "coach_ask", et les listeners
    "coach_response"/"coach_error" lisent data.text / data.error).
    """
    messages = data.get("messages", [])
    context = data.get("context", {})
    llm_config = {"llm_api_key": config.LLM_API_KEY, "llm_model": config.LLM_MODEL}

    response, error = llm_coach.get_coach_response(messages, context, coach_memory, llm_config)
    if error:
        emit("coach_error", {"error": error})
    else:
        emit("coach_response", {"text": response})


@socketio.on("free_play_stockfish_move")
def on_free_play_stockfish_move(data):
    """Calcule le meilleur coup Stockfish pour la position (FEN) reçue —
    mode partie libre (bouton "Coup Stockfish" / case "Stockfish joue auto").
    """
    if not engine_manager:
        emit("free_play_stockfish_move_response", {"error": "stockfish_indisponible"})
        return

    fen = data.get("fen", "")
    try:
        board = chess.Board(fen)
    except Exception:
        emit("free_play_stockfish_move_response", {"error": "fen_invalide"})
        return

    move = engine_manager.get_move(board, think_time=0.5)
    if move is None:
        emit("free_play_stockfish_move_response", {"error": "aucun_coup"})
        return

    emit("free_play_stockfish_move_response", {"uci": move.uci()})


@socketio.on("exercise_new")
def on_exercise_new():
    """Tire au sort une entrée de erreurs_detectees.json (mode "Exercice",
    issue #7) et l'envoie au client — tirage uniforme, pas de pondération
    (hors périmètre de cette issue)."""
    global _current_exercise
    if not erreurs_detectees:
        emit("exercise_error", {"error": "aucune_erreur_disponible"})
        return

    _current_exercise = random.choice(erreurs_detectees)
    emit("exercise_position", {
        "fen": _current_exercise["fen_avant"],
        "camp_alain": _current_exercise["camp_alain"],
        "phase": _current_exercise["phase"],
        "sous_type": _current_exercise["sous_type"],
    })


@socketio.on("exercise_answer")
def on_exercise_answer(data):
    """Compare le coup proposé par Alain avec le coup réellement joué dans la
    partie d'origine et le meilleur coup Stockfish, puis demande au coach un
    commentaire (get_coach_response, réutilisé tel quel avec un contexte de
    comparaison plutôt qu'un chat libre — cf. llm_coach._build_context_text)."""
    if not _current_exercise:
        emit("exercise_error", {"error": "aucun_exercice_en_cours"})
        return

    uci = (data or {}).get("uci", "")
    fen_avant = _current_exercise["fen_avant"]
    coup_propose_san = uci
    try:
        board = chess.Board(fen_avant)
        move = chess.Move.from_uci(uci)
        if move in board.legal_moves:
            coup_propose_san = board.san(move)
    except Exception:
        pass

    coup_reel = _current_exercise.get("coup_joue_san") or _current_exercise.get("coup_joue_uci", "")
    meilleur_coup = _current_exercise.get("meilleur_coup_san") or _current_exercise.get("meilleur_coup_uci", "")

    messages = [{
        "role": "user",
        "content": (
            "Je m'entraîne sur une position tirée d'une de mes erreurs passées. "
            "Commente le coup que je propose pour cette position : est-il bon "
            "ou mauvais, et pourquoi ? Si le meilleur coup est différent, "
            "explique-le aussi, en le comparant avec ce que j'avais réellement "
            "joué dans la partie d'origine. Sois concis."
        ),
    }]
    context = {
        "fen": fen_avant,
        "coup_propose": coup_propose_san,
        "coup_reel": coup_reel,
        "meilleur_coup": meilleur_coup,
    }
    llm_config = {"llm_api_key": config.LLM_API_KEY, "llm_model": config.LLM_MODEL}

    response, error = llm_coach.get_coach_response(messages, context, coach_memory, llm_config)
    if error:
        emit("exercise_error", {"error": error})
    else:
        emit("exercise_comment", {
            "text": response,
            "coup_propose": coup_propose_san,
            "coup_reel": coup_reel,
            "meilleur_coup": meilleur_coup,
        })


if __name__ == "__main__":
    # allow_unsafe_werkzeug : serveur de développement uniquement (pas de
    # déploiement en production prévu pour ce squelette).
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)
