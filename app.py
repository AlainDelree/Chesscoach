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
    return render_template("index.html", objectifs_courants=coach_memory.get("objectifs_courants", []))


def _game_over_info(board: chess.Board) -> dict | None:
    """Détection fiable de fin de partie (issue #11), à partir de l'état réel
    du plateau reconstruit pour cet appel — jamais d'état mis en cache côté
    serveur qui pourrait devenir obsolète. `claim_draw=True` couvre aussi les
    nulles revendicables (répétition, règle des 50 coups), pas seulement le
    pat/mat/matériel insuffisant.

    Retourne None si la partie continue, sinon
    {"gagnant": "blancs"|"noirs"|None, "message": <texte prêt à afficher>}.
    """
    outcome = board.outcome(claim_draw=True)
    if outcome is None:
        return None
    if outcome.winner is True:
        return {"gagnant": "blancs", "message": "Échec et mat — les Blancs gagnent la partie."}
    if outcome.winner is False:
        return {"gagnant": "noirs", "message": "Échec et mat — les Noirs gagnent la partie."}
    if outcome.termination == chess.Termination.STALEMATE:
        return {"gagnant": None, "message": "Pat — partie nulle."}
    return {"gagnant": None, "message": "Partie nulle."}


def _eval_blancs_apres(board: chess.Board, depth: int = 8) -> tuple[int | None, int | None]:
    """Évalue une position (déjà jouée, coup d'Alain compris) avec Stockfish et
    convertit le résultat vers le point de vue des Blancs (issue #12 point 3).

    EngineManager.evaluate() retourne cp/mate du point de vue du joueur au
    trait dans `board` (donc l'adversaire d'Alain juste après son coup) : on
    inverse le signe si ce joueur est Noir, pour obtenir une convention non
    ambiguë quel que soit le camp d'Alain ou le mode d'entraînement — la même
    que celle attendue par llm_coach._build_context_text (eval_blancs_cp /
    eval_mat).

    Retourne (eval_blancs_cp, eval_mat) — un seul des deux est non None
    (sauf position déjà terminée, où les deux sont None)."""
    if not engine_manager:
        return None, None
    eval_info = engine_manager.evaluate(board, depth=depth)
    sign = 1 if board.turn == chess.WHITE else -1
    if eval_info["mate"] is not None:
        return None, sign * eval_info["mate"]
    if eval_info["cp"] is not None:
        return sign * eval_info["cp"], None
    return None, None


@socketio.on("coach_comment_on_demand")
def on_coach_comment_on_demand(data):
    """Bouton "Demander l'avis du coach" (issue #11) : commentaire à la
    demande sur la position courante, utilisé dans les modes pédagogique,
    ouverture et finales quand la case "Commenter chaque coup" est décochée.

    Mode-agnostique et réutilisé par les trois modes plutôt que dupliqué :
    le FEN vient du client (l'instance chess.js du mode concerné), garanti à
    jour puisque c'est exactement la position affichée à l'écran au moment
    du clic — pas un état mis en cache côté serveur (cf. issue #11 point 2)."""
    if not engine_manager:
        emit("coach_on_demand_error", {"error": "stockfish_indisponible"})
        return

    fen = (data or {}).get("fen", "")
    try:
        board = chess.Board(fen)
    except Exception:
        emit("coach_on_demand_error", {"error": "fen_invalide"})
        return

    if _game_over_info(board) is not None:
        emit("coach_on_demand_error", {"error": "partie_terminee"})
        return

    eval_now = engine_manager.evaluate(board, depth=8)
    meilleur_coup_uci = eval_now.get("best_move")
    meilleur_coup_san = ""
    if meilleur_coup_uci:
        try:
            meilleur_coup_san = board.san(chess.Move.from_uci(meilleur_coup_uci))
        except Exception:
            meilleur_coup_san = meilleur_coup_uci

    # Point de vue des Blancs (issue #12 point 3), même conversion que
    # _eval_blancs_apres — évite un second appel au moteur puisque eval_now
    # est déjà calculé ci-dessus pour meilleur_coup_san.
    sign = 1 if board.turn == chess.WHITE else -1
    eval_mat       = sign * eval_now["mate"] if eval_now["mate"] is not None else None
    eval_blancs_cp = sign * eval_now["cp"]   if eval_now["cp"]   is not None else None

    # camp_alain (issue #12 point 1) : ce handler est mode-agnostique, le
    # client transmet donc le camp suivi côté JS pour le mode en cours
    # (pedagogicCampAlain / openingCampAlain / finaleCampAlain).
    camp_alain = ((data or {}).get("camp_alain") or "").strip()
    theme_finale = ((data or {}).get("theme_finale") or "").strip()

    messages = [{
        "role": "user",
        "content": (
            "Commente la position actuelle sur l'échiquier (matériel, "
            "activité des pièces, sécurité du roi) et indique le meilleur "
            "coup à jouer maintenant. Sois concis."
        ),
    }]
    context = {
        "fen": fen,
        "camp_alain": camp_alain,
        "meilleur_coup": meilleur_coup_san,
        "eval_blancs_cp": eval_blancs_cp,
        "eval_mat": eval_mat,
        "theme_finale": theme_finale,
    }
    llm_config = {"llm_api_key": config.LLM_API_KEY, "llm_model": config.LLM_MODEL}

    response, error = llm_coach.get_coach_response(messages, context, coach_memory, llm_config)
    if error:
        emit("coach_on_demand_error", {"error": error})
    else:
        emit("coach_on_demand_response", {"text": response, "meilleur_coup": meilleur_coup_san})


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


@socketio.on("training_program_build")
def on_training_program_build(_data=None):
    """Bouton "Établir mon programme d'entraînement" (issue #14) : appel
    dédié au coach (llm_coach.get_training_program, comme get_opening_moves)
    à partir des patterns_erreurs/repertoire_ouvertures de coach_memory.
    Remplace intégralement objectifs_courants — pas d'historique des
    anciens programmes (hors périmètre de l'issue)."""
    llm_config = {"llm_api_key": config.LLM_API_KEY, "llm_model": config.LLM_MODEL}
    objectifs, error = llm_coach.get_training_program(
        coach_memory.get("patterns_erreurs", {}),
        coach_memory.get("repertoire_ouvertures", {}),
        llm_config,
    )
    if error:
        emit("training_program_error", {"error": error})
        return

    coach_memory["objectifs_courants"] = objectifs
    llm_coach.save_coach_memory(config.COACH_MEMORY_PATH, coach_memory)
    emit("training_program_response", {"objectifs": objectifs})


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

    game_over_info = _game_over_info(board)
    if game_over_info is not None:
        emit("free_play_stockfish_move_response", {
            "game_over": True,
            "game_over_info": game_over_info,
        })
        return

    move = engine_manager.get_move(board, think_time=0.5)
    if move is None:
        emit("free_play_stockfish_move_response", {"error": "aucun_coup"})
        return

    emit("free_play_stockfish_move_response", {"uci": move.uci()})


@socketio.on("exercise_new")
def on_exercise_new(data=None):
    """Tire au sort une entrée de erreurs_detectees.json (mode "Exercice",
    issue #7) et l'envoie au client — tirage uniforme parmi les entrées
    retenues, pas de pondération (hors périmètre de cette issue).

    Issue #13 : filtre optionnel par phase (data.phase parmi "ouverture" /
    "milieu_de_partie" / "finale" ; absent ou "toutes" = pas de filtre), pour
    cibler spécifiquement un axe faible identifié par le coach plutôt que de
    tirer uniformément sur toutes les phases confondues."""
    global _current_exercise

    phase = ((data or {}).get("phase") or "toutes").strip()
    pool = erreurs_detectees
    if phase and phase != "toutes":
        pool = [e for e in erreurs_detectees if e.get("phase") == phase]

    if not pool:
        emit("exercise_error", {"error": "aucune_erreur_disponible"})
        return

    _current_exercise = random.choice(pool)
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
    eval_blancs_cp = None
    eval_mat = None
    try:
        board = chess.Board(fen_avant)
        move = chess.Move.from_uci(uci)
        if move in board.legal_moves:
            coup_propose_san = board.san(move)
            board.push(move)
            eval_blancs_cp, eval_mat = _eval_blancs_apres(board)
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
        "camp_alain": _current_exercise.get("camp_alain", ""),
        "coup_propose": coup_propose_san,
        "coup_reel": coup_reel,
        "meilleur_coup": meilleur_coup,
        "eval_blancs_cp": eval_blancs_cp,
        "eval_mat": eval_mat,
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


@socketio.on("pedagogic_abandon")
def on_pedagogic_abandon(_data):
    """Bouton "Abandonner" (issue #11) : retour à un état neutre côté
    serveur, pas de sauvegarde. Le client réinitialise son propre affichage
    de son côté, indépendamment de cet appel."""
    global _pedagogic_camp_alain
    _pedagogic_camp_alain = None


@socketio.on("pedagogic_move")
def on_pedagogic_move(data):
    """Traite un coup joué par Alain en partie pédagogique (issue #8) :
    demande au coach un commentaire (get_coach_response, comme le mode
    exercice, sans coup_reel puisqu'il n'y a pas de partie historique de
    référence ici), puis fait jouer Stockfish (force réduite) en réponse.

    Issue #11 : détection de fin de partie fiable (état réel du plateau,
    voir _game_over_info) — dès que la partie est terminée (par le coup
    d'Alain ou par la réponse de Stockfish), on n'interroge plus ni
    l'adversaire ni le coach, un message de fin clair est émis à la place.
    Le commentaire automatique du coach devient optionnel (case "Commenter
    chaque coup", data["commenter"])."""
    if not engine_manager:
        emit("pedagogic_error", {"error": "stockfish_indisponible"})
        return

    fen_avant = (data or {}).get("fen_avant", "")
    uci = (data or {}).get("uci", "")
    commenter = (data or {}).get("commenter", True)
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

    # Évaluation Stockfish réelle de la position résultant du coup d'Alain
    # (issue #12 point 3), avant que l'adversaire ne rejoue.
    eval_blancs_cp, eval_mat = _eval_blancs_apres(board)

    # Réponse automatique de Stockfish (force réduite) si la partie continue.
    game_over_info = _game_over_info(board)
    stockfish_move_uci = None
    if game_over_info is None:
        reply = engine_manager.get_move_pedagogique(board)
        if reply:
            board.push(reply)
            stockfish_move_uci = reply.uci()
            game_over_info = _game_over_info(board)

    emit("pedagogic_stockfish_move", {
        "fen": board.fen(),
        "uci": stockfish_move_uci,
        "game_over": game_over_info is not None,
        "game_over_info": game_over_info,
    })

    if game_over_info is not None or not commenter:
        return

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
        "camp_alain": _pedagogic_camp_alain or "",
        "coup_propose": coup_alain_san,
        "meilleur_coup": meilleur_coup_san,
        "eval_blancs_cp": eval_blancs_cp,
        "eval_mat": eval_mat,
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


@socketio.on("opening_abandon")
def on_opening_abandon(_data):
    """Bouton "Abandonner" (issue #11) : retour à un état neutre côté
    serveur, pas de sauvegarde."""
    global _opening_camp_alain, _opening_in_book
    _opening_camp_alain = None
    _opening_in_book = False


@socketio.on("opening_undo")
def on_opening_undo(data):
    """Bouton "Reprendre mon coup" (issue #13) : le client revient seul à la
    position précédente (chess.js, pas d'état de partie conservé côté
    serveur pour ce mode) — mais _opening_in_book, lui, est un drapeau
    mutable côté serveur (bascule définitivement à False dès la sortie du
    livre, cf. on_opening_move) qui doit être resynchronisé sur sa valeur
    d'avant le coup annulé, transmise par le client (qui la connaît via le
    dernier "in_book" reçu) ; sans cela, un coup qui redevient dans le livre
    après annulation resterait à tort traité comme hors-livre."""
    global _opening_in_book
    _opening_in_book = bool((data or {}).get("in_book", False))


@socketio.on("opening_move")
def on_opening_move(data):
    """Traite un coup joué par Alain en mode "travail d'ouverture" (issue #9).

    Tant que la partie reste dans le livre gm2001.bin : vérifie si le coup
    correspond à une entrée du livre pour cette position (et sa popularité
    relative), et l'adversaire répond lui aussi via le livre (tirage pondéré,
    opening_book.choose_weighted_move). Dès que la position sort du livre
    (plus d'entrée pour la position courante, ou coup d'Alain absent des
    entrées) : bascule définitivement sur le comportement du mode pédagogique
    (issue #8, Stockfish affaibli + comparaison au meilleur coup Stockfish).

    Issue #11 : détection de fin de partie fiable (état réel du plateau,
    voir _game_over_info) — dès que la partie est terminée, on n'interroge
    plus ni l'adversaire ni le coach, un message de fin clair est émis à la
    place. Le commentaire automatique du coach devient optionnel (case
    "Commenter chaque coup", data["commenter"])."""
    global _opening_in_book

    if not engine_manager:
        emit("opening_error", {"error": "stockfish_indisponible"})
        return

    fen_avant = (data or {}).get("fen_avant", "")
    uci = (data or {}).get("uci", "")
    commenter = (data or {}).get("commenter", True)
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

    # Évaluation Stockfish réelle de la position résultant du coup d'Alain
    # (issue #12 point 3), avant que l'adversaire ne rejoue.
    eval_blancs_cp, eval_mat = _eval_blancs_apres(board)

    # Réponse automatique de l'adversaire : livre tant que la partie y reste,
    # sinon Stockfish affaibli (mode pédagogique).
    game_over_info = _game_over_info(board)
    stockfish_move_uci = None
    if game_over_info is None:
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
            game_over_info = _game_over_info(board)

    emit("opening_stockfish_move", {
        "fen": board.fen(),
        "uci": stockfish_move_uci,
        "game_over": game_over_info is not None,
        "game_over_info": game_over_info,
        "in_book": _opening_in_book,
    })

    if game_over_info is not None or not commenter:
        return

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
        "camp_alain": _opening_camp_alain or "",
        "coup_propose": coup_alain_san,
        "meilleur_coup": meilleur_coup_san,
        "eval_blancs_cp": eval_blancs_cp,
        "eval_mat": eval_mat,
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


@socketio.on("finale_add")
def on_finale_add(data):
    """Bouton "Enregistrer comme finale" du mode "Partie libre" (issue #13) :
    ajoute la position courante (FEN, camp au trait comme camp_alain,
    transmis par le client) à data/finales.json avec le nom/la description
    saisis par Alain, et renvoie la bibliothèque à jour (même forme que
    finale_list_response) pour que le sélecteur du mode "Travail de finales"
    la propose immédiatement, sans redémarrage."""
    fen         = ((data or {}).get("fen") or "").strip()
    camp_alain  = ((data or {}).get("camp_alain") or "").strip()
    nom         = ((data or {}).get("nom") or "").strip()
    description = ((data or {}).get("description") or "").strip()

    if not nom or camp_alain not in ("blancs", "noirs"):
        emit("finale_add_response", {"error": "champs_invalides"})
        return

    entry = finales.add_finale(fen, camp_alain, nom, description)
    if not entry:
        emit("finale_add_response", {"error": "fen_invalide"})
        return

    entries = finales.get_finales()
    emit("finale_add_response", {
        "id": entry["id"],
        "nom": entry["nom"],
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


@socketio.on("finale_abandon")
def on_finale_abandon(_data):
    """Bouton "Abandonner" (issue #11) : retour à un état neutre côté
    serveur, pas de sauvegarde."""
    global _finale_camp_alain, _finale_nom, _finale_description
    _finale_camp_alain = None
    _finale_nom = None
    _finale_description = None


@socketio.on("finale_move")
def on_finale_move(data):
    """Traite un coup joué par Alain en mode "travail de finales" (issue
    #10) : comparaison au meilleur coup Stockfish comme les autres modes
    (get_coach_response), en y ajoutant le thème de la position-type
    sélectionnée (contexte "theme_finale"), puis réponse automatique de
    l'adversaire à pleine force (engine_manager.get_move).

    Issue #11 : détection de fin de partie fiable (état réel du plateau,
    voir _game_over_info) — dès que la partie est terminée, on n'interroge
    plus ni l'adversaire ni le coach, un message de fin clair est émis à la
    place. Le commentaire automatique du coach devient optionnel (case
    "Commenter chaque coup", data["commenter"])."""
    if not engine_manager:
        emit("finale_error", {"error": "stockfish_indisponible"})
        return

    fen_avant = (data or {}).get("fen_avant", "")
    uci = (data or {}).get("uci", "")
    commenter = (data or {}).get("commenter", True)
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

    # Évaluation Stockfish réelle de la position résultant du coup d'Alain
    # (issue #12 point 3), avant que l'adversaire ne rejoue.
    eval_blancs_cp, eval_mat = _eval_blancs_apres(board)

    # Réponse automatique de l'adversaire à pleine force (pas le moteur
    # affaibli des modes pédagogique/ouverture).
    game_over_info = _game_over_info(board)
    stockfish_move_uci = None
    if game_over_info is None:
        reply = engine_manager.get_move(board, think_time=0.5)
        if reply:
            board.push(reply)
            stockfish_move_uci = reply.uci()
            game_over_info = _game_over_info(board)

    emit("finale_stockfish_move", {
        "fen": board.fen(),
        "uci": stockfish_move_uci,
        "game_over": game_over_info is not None,
        "game_over_info": game_over_info,
    })

    if game_over_info is not None or not commenter:
        return

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
        "camp_alain": _finale_camp_alain or "",
        "coup_propose": coup_alain_san,
        "meilleur_coup": meilleur_coup_san,
        "eval_blancs_cp": eval_blancs_cp,
        "eval_mat": eval_mat,
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
