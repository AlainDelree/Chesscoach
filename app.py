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
import finales
import llm_coach
import opening_book
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



# État de la partie pédagogique en cours (issue #8) — application locale
# mono-utilisateur (cf. CONTEXTE.md), une seule partie active à la fois, comme
# _current_exercise.
_pedagogic_camp_alain: str | None = None


@socketio.on("pedagogic_start")
def on_pedagogic_start(data):
    """Démarre une partie pédagogique (issue #8) : Alain choisit son camp,
    position de départ standard. Stockfish (force réduite, cf.
    EngineManager.get_move_pedagogique) joue automatiquement l'autre camp,
    y compris le premier coup si Alain a choisi les Noirs."""
    global _pedagogic_camp_alain
    if not engine_manager:
        emit("pedagogic_error", {"error": "stockfish_indisponible"})
        return

    camp_alain = (data or {}).get("camp", "blancs")
    if camp_alain not in ("blancs", "noirs"):
        camp_alain = "blancs"
    _pedagogic_camp_alain = camp_alain

    board = chess.Board()
    coup_ouverture = None
    if camp_alain == "noirs":
        move = engine_manager.get_move_pedagogique(board)
        if move:
            board.push(move)
            coup_ouverture = move.uci()

    emit("pedagogic_started", {
        "fen": board.fen(),
        "camp_alain": camp_alain,
        "coup_ouverture": coup_ouverture,
    })


@socketio.on("pedagogic_move")
def on_pedagogic_move(data):
    """Traite un coup joué par Alain en partie pédagogique (issue #8) :
    demande au coach un commentaire (get_coach_response, comme le mode
    exercice, sans coup_reel puisqu'il n'y a pas de partie historique de
    référence ici), puis fait jouer Stockfish (force réduite) en réponse."""
    if not engine_manager:
        emit("pedagogic_error", {"error": "stockfish_indisponible"})
        return

    fen_avant = (data or {}).get("fen_avant", "")
    uci = (data or {}).get("uci", "")
    try:
        board = chess.Board(fen_avant)
        move = chess.Move.from_uci(uci)
        if move not in board.legal_moves:
            emit("pedagogic_error", {"error": "coup_illegal"})
            return
    except Exception:
        emit("pedagogic_error", {"error": "fen_ou_coup_invalide"})
        return

    coup_alain_san = board.san(move)

    # Meilleur coup Stockfish pour cette position, à pleine force (moteur
    # d'évaluation partagé, inchangé — cf. EngineManager.evaluate).
    eval_avant = engine_manager.evaluate(board, depth=8)
    meilleur_coup_uci = eval_avant.get("best_move")
    meilleur_coup_san = ""
    if meilleur_coup_uci:
        try:
            meilleur_coup_san = board.san(chess.Move.from_uci(meilleur_coup_uci))
        except Exception:
            meilleur_coup_san = meilleur_coup_uci

    board.push(move)

    # Réponse automatique de Stockfish (force réduite) si la partie continue.
    stockfish_move_uci = None
    if not board.is_game_over():
        reply = engine_manager.get_move_pedagogique(board)
        if reply:
            board.push(reply)
            stockfish_move_uci = reply.uci()

    emit("pedagogic_stockfish_move", {
        "fen": board.fen(),
        "uci": stockfish_move_uci,
        "game_over": board.is_game_over(),
    })

    messages = [{
        "role": "user",
        "content": (
            "Je joue une partie pédagogique complète contre Stockfish (force "
            "réduite pour mon niveau). Commente le coup que je viens de "
            "jouer : est-il bon ou mauvais, et pourquoi ? Si le meilleur coup "
            "était différent, explique-le aussi. Sois concis."
        ),
    }]
    context = {
        "fen": fen_avant,
        "coup_propose": coup_alain_san,
        "meilleur_coup": meilleur_coup_san,
    }
    llm_config = {"llm_api_key": config.LLM_API_KEY, "llm_model": config.LLM_MODEL}

    response, error = llm_coach.get_coach_response(messages, context, coach_memory, llm_config)
    if error:
        emit("pedagogic_error", {"error": error})
    else:
        emit("pedagogic_comment", {
            "text": response,
            "coup_propose": coup_alain_san,
            "meilleur_coup": meilleur_coup_san,
        })


# État du mode "travail d'ouverture" en cours (issue #9) — comme
# _pedagogic_camp_alain, une seule partie active à la fois (application
# locale mono-utilisateur, cf. CONTEXTE.md). _opening_in_book bascule
# définitivement à False dès que la partie sort du livre gm2001.bin (position
# non couverte, ou coup d'Alain absent des entrées) : elle ne revient jamais
# à True, même si une position ultérieure existait par coïncidence dans le
# livre.
_opening_camp_alain: str | None = None
_opening_in_book: bool = False


@socketio.on("opening_start")
def on_opening_start(data):
    """Démarre le mode "travail d'ouverture" (issue #9) : Alain choisit son
    camp et le nom d'une ouverture. Claude identifie d'abord les quelques
    coups caractéristiques de cette ouverture (llm_coach.get_opening_moves,
    appel dédié) pour atteindre la position de départ réelle de
    l'entraînement ; ensuite, l'adversaire automatique suit le livre Polyglot
    réel (gm2001.bin) tant que la position y figure, avec bascule sur
    Stockfish affaibli (comme le mode pédagogique, issue #8) dès la sortie du
    livre."""
    global _opening_camp_alain, _opening_in_book

    if not engine_manager:
        emit("opening_error", {"error": "stockfish_indisponible"})
        return
    if not opening_book.book_available(config.BOOK_PATH):
        emit("opening_error", {"error": "livre_indisponible"})
        return

    camp_alain = (data or {}).get("camp", "blancs")
    if camp_alain not in ("blancs", "noirs"):
        camp_alain = "blancs"

    opening_name = ((data or {}).get("opening_name") or "").strip()
    if not opening_name:
        emit("opening_error", {"error": "nom_ouverture_manquant"})
        return

    llm_config = {"llm_api_key": config.LLM_API_KEY, "llm_model": config.LLM_MODEL}
    moves_san, error = llm_coach.get_opening_moves(opening_name, llm_config)
    if error:
        emit("opening_error", {"error": error})
        return

    board = chess.Board()
    try:
        for san in moves_san:
            move = board.parse_san(san)
            board.push(move)
    except ValueError:
        emit("opening_error", {"error": "sequence_invalide"})
        return

    _opening_camp_alain = camp_alain
    _opening_in_book = True

    # Si la séquence caractéristique laisse la main à l'adversaire (ex. camp
    # Alain = noirs après 1.e4), il joue immédiatement son premier coup,
    # comme le coup d'ouverture du mode pédagogique.
    camp_alain_color = chess.WHITE if camp_alain == "blancs" else chess.BLACK
    coup_ouverture = None
    if board.turn != camp_alain_color and not board.is_game_over():
        move = opening_book.choose_weighted_move(config.BOOK_PATH, board)
        if move is None:
            _opening_in_book = False
            move = engine_manager.get_move_pedagogique(board)
        if move:
            board.push(move)
            coup_ouverture = move.uci()

    emit("opening_started", {
        "fen": board.fen(),
        "camp_alain": camp_alain,
        "opening_name": opening_name,
        "moves_ouverture": moves_san,
        "coup_ouverture": coup_ouverture,
        "in_book": _opening_in_book,
    })


@socketio.on("opening_move")
def on_opening_move(data):
    """Traite un coup joué par Alain en mode "travail d'ouverture" (issue #9).

    Tant que la partie reste dans le livre gm2001.bin : vérifie si le coup
    correspond à une entrée du livre pour cette position (et sa popularité
    relative), et l'adversaire répond lui aussi via le livre (tirage pondéré,
    opening_book.choose_weighted_move). Dès que la position sort du livre
    (plus d'entrée pour la position courante, ou coup d'Alain absent des
    entrées) : bascule définitivement sur le comportement du mode pédagogique
    (issue #8, Stockfish affaibli + comparaison au meilleur coup Stockfish)."""
    global _opening_in_book

    if not engine_manager:
        emit("opening_error", {"error": "stockfish_indisponible"})
        return

    fen_avant = (data or {}).get("fen_avant", "")
    uci = (data or {}).get("uci", "")
    try:
        board = chess.Board(fen_avant)
        move = chess.Move.from_uci(uci)
        if move not in board.legal_moves:
            emit("opening_error", {"error": "coup_illegal"})
            return
    except Exception:
        emit("opening_error", {"error": "fen_ou_coup_invalide"})
        return

    coup_alain_san = board.san(move)

    etait_dans_le_livre = _opening_in_book
    dans_le_livre = False
    popularite_pct = None
    coup_livre_top_san = None
    meilleur_coup_san = ""

    if etait_dans_le_livre:
        entries = opening_book.get_book_entries(config.BOOK_PATH, board)
        if entries:
            total_weight = sum(e["weight"] for e in entries)
            coup_livre_top_san = entries[0]["san"]
            matched = next((e for e in entries if e["uci"] == move.uci()), None)
            if matched:
                dans_le_livre = True
                if total_weight:
                    popularite_pct = round(matched["weight"] / total_weight * 100, 1)
        _opening_in_book = dans_le_livre

    if not dans_le_livre:
        # Hors livre à partir de ce coup (ou déjà avant) : comparaison au
        # meilleur coup Stockfish, comme le mode pédagogique (issue #8).
        eval_avant = engine_manager.evaluate(board, depth=8)
        meilleur_coup_uci = eval_avant.get("best_move")
        if meilleur_coup_uci:
            try:
                meilleur_coup_san = board.san(chess.Move.from_uci(meilleur_coup_uci))
            except Exception:
                meilleur_coup_san = meilleur_coup_uci

    board.push(move)

    # Réponse automatique de l'adversaire : livre tant que la partie y reste,
    # sinon Stockfish affaibli (mode pédagogique).
    stockfish_move_uci = None
    if not board.is_game_over():
        reply = None
        if _opening_in_book:
            reply = opening_book.choose_weighted_move(config.BOOK_PATH, board)
            if reply is None:
                _opening_in_book = False
        if reply is None:
            reply = engine_manager.get_move_pedagogique(board)
        if reply:
            board.push(reply)
            stockfish_move_uci = reply.uci()

    emit("opening_stockfish_move", {
        "fen": board.fen(),
        "uci": stockfish_move_uci,
        "game_over": board.is_game_over(),
        "in_book": _opening_in_book,
    })

    if etait_dans_le_livre and dans_le_livre:
        instruction = (
            "Je m'entraîne sur une ouverture précise à l'aide d'un livre "
            "d'ouvertures réel. Le coup que je viens de jouer correspond à "
            "une entrée du livre pour cette position : confirme que je reste "
            "dans la théorie, commente sa popularité relative si elle est "
            "fournie en contexte, et donne un bref conseil sur l'idée du "
            "coup. Sois concis."
        )
    elif etait_dans_le_livre and not dans_le_livre:
        instruction = (
            "Je m'entraîne sur une ouverture précise à l'aide d'un livre "
            "d'ouvertures réel. Le coup que je viens de jouer n'est pas dans "
            "le livre pour cette position : signale que je sors de la "
            "théorie, propose le coup le plus joué du livre à la place "
            "(fourni en contexte) et explique brièvement pourquoi il est "
            "préférable. Sois concis."
        )
    else:
        instruction = (
            "Je m'entraîne sur une ouverture précise, mais je suis "
            "maintenant sorti de la théorie du livre. Commente le coup que "
            "je viens de jouer comme dans une partie pédagogique normale : "
            "est-il bon ou mauvais, et pourquoi ? Si le meilleur coup selon "
            "Stockfish était différent, explique-le aussi. Sois concis."
        )

    messages = [{"role": "user", "content": instruction}]
    context = {
        "fen": fen_avant,
        "coup_propose": coup_alain_san,
        "meilleur_coup": meilleur_coup_san,
        "dans_le_livre": dans_le_livre,
        "popularite_pct": popularite_pct,
        "coup_livre_recommande": coup_livre_top_san or "",
    }
    llm_config = {"llm_api_key": config.LLM_API_KEY, "llm_model": config.LLM_MODEL}

    response, error = llm_coach.get_coach_response(messages, context, coach_memory, llm_config)
    if error:
        emit("opening_error", {"error": error})
    else:
        emit("opening_comment", {
            "text": response,
            "coup_propose": coup_alain_san,
            "dans_le_livre": dans_le_livre,
            "popularite_pct": popularite_pct,
            "coup_livre_recommande": coup_livre_top_san,
            "meilleur_coup": meilleur_coup_san,
        })


# État du mode "travail de finales" en cours (issue #10) — comme
# _pedagogic_camp_alain/_opening_camp_alain, une seule finale active à la
# fois (application locale mono-utilisateur, cf. CONTEXTE.md). Contrairement
# aux modes pédagogique/ouverture, l'adversaire automatique joue ici à
# pleine force (engine_manager.get_move, réutilisé tel quel du mode partie
# libre — pas le moteur affaibli get_move_pedagogique) : l'objectif est que
# Stockfish défende/attaque correctement pour que l'exercice technique ait
# un sens.
_finale_camp_alain: str | None = None
_finale_nom: str | None = None
_finale_description: str | None = None


@socketio.on("finale_list")
def on_finale_list(_data):
    """Retourne la bibliothèque de positions-types de finales (finales.py),
    pour peupler le menu déroulant du panneau "Travail de finales"."""
    entries = finales.get_finales()
    emit("finale_list_response", {
        "finales": [
            {
                "id": e["id"],
                "nom": e["nom"],
                "description": e["description"],
                "camp_alain": e["camp_alain"],
            }
            for e in entries
        ],
    })


@socketio.on("finale_start")
def on_finale_start(data):
    """Charge une position-type de la bibliothèque de finales (issue #10) et
    fait jouer l'adversaire (Stockfish à pleine force) si la FEN de départ
    laisse le trait à l'adversaire du camp d'Alain (camp_alain est fixé par
    la position-type elle-même, pas choisi librement par Alain)."""
    global _finale_camp_alain, _finale_nom, _finale_description

    if not engine_manager:
        emit("finale_error", {"error": "stockfish_indisponible"})
        return

    finale_id = (data or {}).get("id", "")
    entry = finales.get_finale_by_id(finale_id)
    if not entry:
        emit("finale_error", {"error": "finale_inconnue"})
        return

    board = chess.Board(entry["fen"])
    _finale_camp_alain = entry["camp_alain"]
    _finale_nom = entry["nom"]
    _finale_description = entry["description"]

    camp_alain_color = chess.WHITE if _finale_camp_alain == "blancs" else chess.BLACK
    coup_ouverture = None
    if board.turn != camp_alain_color and not board.is_game_over():
        move = engine_manager.get_move(board, think_time=0.5)
        if move:
            board.push(move)
            coup_ouverture = move.uci()

    emit("finale_started", {
        "fen": board.fen(),
        "camp_alain": _finale_camp_alain,
        "nom": _finale_nom,
        "description": _finale_description,
        "coup_ouverture": coup_ouverture,
    })


@socketio.on("finale_move")
def on_finale_move(data):
    """Traite un coup joué par Alain en mode "travail de finales" (issue
    #10) : comparaison au meilleur coup Stockfish comme les autres modes
    (get_coach_response), en y ajoutant le thème de la position-type
    sélectionnée (contexte "theme_finale"), puis réponse automatique de
    l'adversaire à pleine force (engine_manager.get_move)."""
    if not engine_manager:
        emit("finale_error", {"error": "stockfish_indisponible"})
        return

    fen_avant = (data or {}).get("fen_avant", "")
    uci = (data or {}).get("uci", "")
    try:
        board = chess.Board(fen_avant)
        move = chess.Move.from_uci(uci)
        if move not in board.legal_moves:
            emit("finale_error", {"error": "coup_illegal"})
            return
    except Exception:
        emit("finale_error", {"error": "fen_ou_coup_invalide"})
        return

    coup_alain_san = board.san(move)

    # Meilleur coup Stockfish pour cette position, à pleine force (moteur
    # d'évaluation partagé, inchangé — cf. EngineManager.evaluate).
    eval_avant = engine_manager.evaluate(board, depth=8)
    meilleur_coup_uci = eval_avant.get("best_move")
    meilleur_coup_san = ""
    if meilleur_coup_uci:
        try:
            meilleur_coup_san = board.san(chess.Move.from_uci(meilleur_coup_uci))
        except Exception:
            meilleur_coup_san = meilleur_coup_uci

    board.push(move)

    # Réponse automatique de l'adversaire à pleine force (pas le moteur
    # affaibli des modes pédagogique/ouverture).
    stockfish_move_uci = None
    if not board.is_game_over():
        reply = engine_manager.get_move(board, think_time=0.5)
        if reply:
            board.push(reply)
            stockfish_move_uci = reply.uci()

    emit("finale_stockfish_move", {
        "fen": board.fen(),
        "uci": stockfish_move_uci,
        "game_over": board.is_game_over(),
    })

    messages = [{
        "role": "user",
        "content": (
            "Je m'entraîne sur une finale technique tirée d'une bibliothèque "
            "de positions-types, contre Stockfish à pleine force. Commente "
            "le coup que je viens de jouer en tenant compte du thème "
            "technique de cette finale (fourni en contexte) : est-il bon ou "
            "mauvais, et pourquoi ? Si le meilleur coup selon Stockfish "
            "était différent, explique-le aussi. Sois concis."
        ),
    }]
    context = {
        "fen": fen_avant,
        "coup_propose": coup_alain_san,
        "meilleur_coup": meilleur_coup_san,
        "theme_finale": _finale_description or "",
    }
    llm_config = {"llm_api_key": config.LLM_API_KEY, "llm_model": config.LLM_MODEL}

    response, error = llm_coach.get_coach_response(messages, context, coach_memory, llm_config)
    if error:
        emit("finale_error", {"error": error})
    else:
        emit("finale_comment", {
            "text": response,
            "coup_propose": coup_alain_san,
            "meilleur_coup": meilleur_coup_san,
        })


if __name__ == "__main__":
    # allow_unsafe_werkzeug : serveur de développement uniquement (pas de
    # déploiement en production prévu pour ce squelette).
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)
