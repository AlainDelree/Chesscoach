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
from engine_stockfish import (
    DEPTH_ANALYSE_PARTIE,
    DEPTH_EXERCICE_TEMPS_REEL,
    EngineManager,
    classifier_coup,
    find_stockfish,
)
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


def _finale_restricted_king_squares(board: chess.Board, camp_perdant_color: bool | None) -> list[str]:
    """Cases adjacentes au roi du camp perdant d'une finale (issue #28) qui
    lui sont interdites : attaquées par l'autre camp (board.is_attacked_by,
    indépendamment du trait — pas de génération de coups légaux, qui
    dépendrait de qui doit jouer) ou occupées par une pièce alliée. Retourne
    une liste vide si camp_perdant_color est None (hors mode finales) ou si
    ce roi a disparu du plateau (ne devrait pas arriver en pratique)."""
    if camp_perdant_color is None:
        return []
    king_square = board.king(camp_perdant_color)
    if king_square is None:
        return []
    restricted = []
    for sq in chess.SquareSet(chess.BB_KING_ATTACKS[king_square]):
        piece = board.piece_at(sq)
        if piece is not None and piece.color == camp_perdant_color:
            restricted.append(chess.square_name(sq))
        elif board.is_attacked_by(not camp_perdant_color, sq):
            restricted.append(chess.square_name(sq))
    return restricted


# Noms FR bruts (sans article) des types de pièce python-chess, utilisés par
# _move_details_fr (issue #18) — le mode Exercice les injecte explicitement
# dans le contexte du coach plutôt que de le laisser déduire seul, à partir
# du seul nom SAN/UCI d'un coup, quelle pièce se trouvait sur la case
# capturée (ex. confusion constatée : "tu prends le cavalier" pour la prise
# d'un pion).
_PIECE_FR = {
    chess.PAWN: "pion",
    chess.KNIGHT: "cavalier",
    chess.BISHOP: "fou",
    chess.ROOK: "tour",
    chess.QUEEN: "dame",
    chess.KING: "roi",
}


def _parse_move_flexible(board: chess.Board, move_str: str) -> chess.Move | None:
    """Interprète move_str en SAN ou, à défaut, en UCI (issue #18) : les
    champs coup_joue_san/meilleur_coup_san d'erreurs_detectees.json peuvent
    retomber sur leur équivalent _uci quand le SAN n'a pas été précalculé
    (cf. on_exercise_answer). Retourne None si move_str n'est interprétable
    dans aucun des deux formats, ou n'est pas légal sur `board`."""
    try:
        return board.parse_san(move_str)
    except ValueError:
        pass
    try:
        move = chess.Move.from_uci(move_str)
        return move if move in board.legal_moves else None
    except Exception:
        return None


def _move_details_fr(fen: str, move_str: str) -> tuple[str, str]:
    """(pièce jouée, pièce capturée) en français pour move_str (SAN ou UCI),
    joué depuis la position fen (issue #18) — best-effort : ("", "") si
    move_str est vide ou non interprétable sur cette position. Les trois
    coups comparés dans le mode Exercice (coup proposé, coup réel, meilleur
    coup) partent tous de la même position fen_avant."""
    if not move_str:
        return "", ""
    try:
        board = chess.Board(fen)
        move = _parse_move_flexible(board, move_str)
        if move is None:
            return "", ""
        piece = board.piece_at(move.from_square)
        piece_fr = _PIECE_FR.get(piece.piece_type, "") if piece else ""
        if board.is_en_passant(move):
            capture_fr = _PIECE_FR[chess.PAWN]
        else:
            captured = board.piece_at(move.to_square)
            capture_fr = _PIECE_FR.get(captured.piece_type, "") if captured else ""
        return piece_fr, capture_fr
    except Exception:
        return "", ""


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


def _evaluate_move_for_coach(fen_avant: str, move: chess.Move) -> dict:
    """Évalue un coup avec Stockfish selon le même mécanisme que le mode
    Exercice (verdict + PV à DEPTH_EXERCICE_TEMPS_REEL, issue #17/#19/#20),
    factorisé ici (issue #26) pour que pédagogique, ouverture (hors livre) et
    finales en bénéficient aussi, au lieu de la simple comparaison au
    meilleur coup (evaluate() sans PV) qu'ils utilisaient jusque-là.
    EngineManager.evaluate_move est déjà générique — seuls ses appelants
    étaient limités à l'exercice. `move` doit déjà être légal sur la
    position fen_avant (vérifié par l'appelant).

    Retourne {"meilleur_coup": str, "verdict_qualite": str|None,
    "verdict_delta_cp": int|None, "pv_coup_propose": str,
    "pv_meilleur_coup": str} — clés directement fusionnables dans le context
    de get_coach_response. Best-effort : valeurs vides/None si Stockfish est
    indisponible ou si l'évaluation échoue."""
    result = {
        "meilleur_coup": "",
        "verdict_qualite": None,
        "verdict_delta_cp": None,
        "pv_coup_propose": "",
        "pv_meilleur_coup": "",
    }
    if not engine_manager:
        return result
    try:
        board = chess.Board(fen_avant)
        verdict_qualite, verdict_delta_cp, meilleur_coup_uci, pv_info = engine_manager.evaluate_move(
            board, move, depth=DEPTH_EXERCICE_TEMPS_REEL, always_return_best=True, return_pv=True
        )
        result["verdict_qualite"] = verdict_qualite
        result["verdict_delta_cp"] = verdict_delta_cp
        result["pv_coup_propose"] = pv_info.get("pv_coup_propose", "")
        result["pv_meilleur_coup"] = pv_info.get("pv_meilleur_coup", "")
        if meilleur_coup_uci:
            try:
                result["meilleur_coup"] = board.san(chess.Move.from_uci(meilleur_coup_uci))
            except Exception:
                result["meilleur_coup"] = meilleur_coup_uci
    except Exception:
        pass
    return result


def _analyse_full_game(moves_uci: list) -> list:
    """Analyse chaque demi-coup d'une partie une seule fois avec Stockfish, à
    DEPTH_ANALYSE_PARTIE (issue #41, bouton "Analyser cette partie" du mode
    Bibliothèque/Revue PGN, et point d'entrée depuis la fin d'une partie
    pédagogique/libre) : reprend la technique à passe unique de
    build_patterns_erreurs.py (l'évaluation "après" d'un coup sert
    directement d'évaluation "avant" du suivant, comme dans _eval_blancs_apres
    ci-dessus) plutôt que d'appeler evaluate_move coup par coup (qui
    réévaluerait deux fois chaque position), pour rester synchrone sur une
    partie complète malgré une profondeur plus élevée que celle du lot
    d'amorçage (profondeur 10, choix de vitesse pour 280 parties).

    Purement mécanique — aucun appel au coach ici (issue #41 point 2) :
    l'objectif du programme d'entraînement est qu'Alain réfléchisse d'abord,
    le coach restant disponible à la demande une fois un coup flagué rejoué
    (coach_comment_on_demand, mode partie libre).

    Retourne une liste, un élément par demi-coup (même ordre que moves_uci) :
      {"san", "uci", "color" ("white"/"black"), "coup_plein", "delta_cp",
       "qualite", "best_move" (UCI du meilleur coup si différent du coup
       joué, sinon None), "fen_avant", "phase"}.

    "phase" (issue #42, ajouté pour le module d'explications narratives du
    coach) reprend l'heuristique déjà utilisée par build_patterns_erreurs.py
    (_phase) : numéro de coup plein <= 10 -> "ouverture", sinon <= 12 pièces
    sur l'échiquier -> "finale", sinon "milieu_de_partie" — évaluée sur la
    position AVANT le coup, comme dans build_patterns_erreurs.py. N'affecte
    pas le calcul de delta_cp/qualite (issue #41, inchangé).

    Lève ValueError si un coup de moves_uci n'est pas légal sur la partie
    reconstruite depuis la position de départ standard."""

    def score_val(eval_info: dict) -> int:
        """Valeur unique (mat ou cp) du point de vue du joueur au trait,
        pour pouvoir comparer directement deux évaluations consécutives —
        même convention que evaluate_move (engine_stockfish.py)."""
        if eval_info["mate"] is not None:
            return 100000 if eval_info["mate"] > 0 else -100000
        if eval_info["cp"] is not None:
            return eval_info["cp"]
        return 0

    board = chess.Board()

    eval_courante = engine_manager.evaluate(board, depth=DEPTH_ANALYSE_PARTIE)
    val_avant = score_val(eval_courante)
    pv_avant = eval_courante.get("pv") or []
    meilleur_coup_uci_avant = pv_avant[0].uci() if pv_avant else None

    resultats = []
    for uci in moves_uci:
        move = chess.Move.from_uci(uci)
        if move not in board.legal_moves:
            raise ValueError(f"Coup illégal : {uci}")

        coup_plein = board.fullmove_number
        color = "white" if board.turn == chess.WHITE else "black"
        fen_avant = board.fen()
        san = board.san(move)
        phase = "ouverture" if coup_plein <= 10 else (
            "finale" if chess.popcount(board.occupied) <= 12 else "milieu_de_partie"
        )

        board.push(move)
        eval_apres = engine_manager.evaluate(board, depth=DEPTH_ANALYSE_PARTIE)
        val_apres = score_val(eval_apres)
        pv_apres = eval_apres.get("pv") or []

        # Perte vue du point de vue du joueur qui vient de jouer (val_avant),
        # comparée à l'évaluation après son coup (val_apres, point de vue de
        # l'adversaire désormais au trait, donc inversée) — même formule que
        # evaluate_move. Plafonnée comme dans build_patterns_erreurs.py : au-
        # delà, la magnitude exacte (parfois démesurée à cause du mapping
        # mat->cp) n'apporte plus d'info utile.
        delta_brut = max(0, val_avant - (-val_apres))
        delta_cp = min(delta_brut, 1000)
        qualite = classifier_coup(delta_cp)

        best_move = (
            meilleur_coup_uci_avant
            if meilleur_coup_uci_avant and meilleur_coup_uci_avant != uci
            else None
        )

        resultats.append({
            "san": san,
            "uci": uci,
            "color": color,
            "coup_plein": coup_plein,
            "delta_cp": delta_cp,
            "qualite": qualite,
            "best_move": best_move,
            "fen_avant": fen_avant,
            "phase": phase,
        })

        val_avant = val_apres
        meilleur_coup_uci_avant = pv_apres[0].uci() if pv_apres else None

    return resultats


@socketio.on("analyser_pgn")
def on_analyser_pgn(data):
    """Bouton "Analyser cette partie" (issue #41) : analyse Stockfish
    synchrone de la partie actuellement chargée côté client (reviewMoves, cf.
    board.js lancerAnalyse) — une seule partie à la fois, à la demande, pas
    un traitement par lot (voir build_patterns_erreurs.py pour l'amorçage de
    l'historique complet). Le client envoie la liste des coups UCI de la
    partie en revue ; voir _analyse_full_game pour le détail de l'analyse."""
    if not engine_manager:
        emit("analyser_pgn_error", {"error": "stockfish_indisponible"})
        return

    moves_uci = (data or {}).get("moves") or []
    if not moves_uci:
        emit("analyser_pgn_error", {"error": "partie_vide"})
        return

    try:
        resultats = _analyse_full_game(moves_uci)
    except ValueError:
        emit("analyser_pgn_error", {"error": "partie_invalide"})
        return

    emit("analyser_pgn_response", {"moves": resultats})


def _camp_label(color: str) -> str:
    return "blancs" if color == "white" else "noirs"


def _meilleur_coup_san(move: dict) -> str:
    """Convertit le "best_move" UCI d'un élément du rapport mécanique
    (_analyse_full_game) en SAN, à partir de son "fen_avant" — best-effort,
    chaîne vide si absent ou invalide."""
    fen_avant = (move or {}).get("fen_avant") or ""
    best_move_uci = (move or {}).get("best_move")
    if not fen_avant or not best_move_uci:
        return ""
    try:
        board = chess.Board(fen_avant)
        return board.san(chess.Move.from_uci(best_move_uci))
    except Exception:
        return ""


def _prepare_flagged_moves_for_coach(moves: list) -> list:
    """Convertit les coups flagués du rapport mécanique (issue #41, tels que
    renvoyés au client par on_analyser_pgn) au format attendu par
    llm_coach.get_move_explanations (issue #42) : mêmes champs que ceux
    exposés au client (san/uci/camp/coup_plein/delta_cp/qualite/phase), plus
    meilleur_coup en SAN (calculé ici depuis fen_avant/best_move, pas
    envoyé tel quel par le client) pour ancrer les explications sur une
    donnée réelle plutôt que de laisser le coach en deviner un.

    "id" (position du coup dans la partie, transmise par le client comme
    "idx") sert de seule clé fiable pour réassocier le choix du coach à son
    coup d'origine : un même uci peut réapparaître plusieurs fois dans une
    partie (ex. échecs répétés Rh4+/Rg4+ par shuttle de tour), constaté en
    vérification réelle sur une partie de la bibliothèque — indexer par uci
    seul aurait fait apparaître la même explication sur plusieurs coups
    distincts."""
    prepared = []
    for m in moves or []:
        meilleur_coup = _meilleur_coup_san(m)
        prepared.append({
            "id": (m or {}).get("idx"),
            "uci": (m or {}).get("uci"),
            "san": (m or {}).get("san"),
            "camp": _camp_label((m or {}).get("color")),
            "coup_plein": (m or {}).get("coup_plein"),
            "delta_cp": (m or {}).get("delta_cp"),
            "qualite": (m or {}).get("qualite"),
            "phase": (m or {}).get("phase"),
            "meilleur_coup": meilleur_coup or None,
        })
    return prepared


@socketio.on("analyse_choisir_coups_decisifs")
def on_analyse_choisir_coups_decisifs(data):
    """Étape 1 du module d'explications narratives (issue #42) : transmet au
    coach, en un seul appel dédié (llm_coach.get_move_explanations, même
    pattern que get_opening_moves/get_training_program), la liste complète
    des coups flagués du rapport mécanique (issue #41, inchangé) déjà reçue
    côté client (analyser_pgn_response) — le client la renvoie telle quelle
    ici. Le coach choisit jusqu'à 5 coups qu'il juge réellement décisifs et
    fournit une explication en langage naturel pour chacun ; les coups non
    retenus restent disponibles pour "Expliquer ce coup" à la demande
    (on_analyse_expliquer_coup ci-dessous), sans appel automatique."""
    moves = (data or {}).get("moves") or []
    if not moves:
        emit("analyse_choix_coach_error", {"error": "aucun_coup_flague"})
        return

    prepared = _prepare_flagged_moves_for_coach(moves)
    llm_config = {
        "llm_api_key": config.LLM_API_KEY,
        "llm_model": config.LLM_MODEL,
        "coach_log_path": config.COACH_CALLS_LOG_PATH,
    }
    choix, error = llm_coach.get_move_explanations(prepared, llm_config)
    if error:
        emit("analyse_choix_coach_error", {"error": error})
        return

    # Réassocie chaque choix (id + explication) aux champs d'affichage du
    # coup d'origine (uci/san/camp/coup_plein) via "idx" (position du coup
    # dans la partie) — PAS via uci, qui peut se répéter dans une même
    # partie (voir _prepare_flagged_moves_for_coach).
    par_idx = {m.get("idx"): m for m in moves if m.get("idx") is not None}
    reponse = []
    for c in choix:
        original = par_idx.get(c["id"])
        if not original:
            continue
        reponse.append({
            "idx": c["id"],
            "uci": original.get("uci"),
            "explication": c["explication"],
            "san": original.get("san"),
            "camp": _camp_label(original.get("color")),
            "coup_plein": original.get("coup_plein"),
        })

    emit("analyse_choix_coach_response", {"choix": reponse})


@socketio.on("analyse_expliquer_coup")
def on_analyse_expliquer_coup(data):
    """Étape 2 du module d'explications narratives (issue #42) : bouton
    "Expliquer ce coup" à la demande, pour un coup flagué non retenu par le
    coach à l'étape 1 — appel simple, réutilisant get_coach_response comme
    les autres modes (contexte fen/move/verdict_qualite/verdict_delta_cp/
    meilleur_coup déjà supporté par _build_context_text, issue #17/#20/#26),
    pas de nouvelle logique de prompt dédiée. La réponse est réassociée
    côté client via "idx" (position du coup dans la partie), pas via uci
    (qui peut se répéter dans une même partie, cf.
    _prepare_flagged_moves_for_coach)."""
    move = data or {}
    fen_avant = (move.get("fen_avant") or "").strip()
    san = (move.get("san") or "").strip()
    if not fen_avant or not san:
        emit("analyse_expliquer_coup_error", {
            "error": "coup_invalide", "uci": move.get("uci"), "idx": move.get("idx"),
        })
        return

    context = {
        "fen": fen_avant,
        "move": san,
        "verdict_qualite": move.get("qualite"),
        "verdict_delta_cp": move.get("delta_cp"),
        "meilleur_coup": _meilleur_coup_san(move),
        # Réutilise le garde-fou _EXERCISE_SYSTEM_ADDENDUM (issue #17/#26) :
        # verdict déjà tranché à expliquer (pas à rejuger), jamais de chiffre
        # brut de centipawns ni d'étiquette technique ("blunder"...) cité à
        # Alain — cohérent avec l'objectif de l'issue #42 (explications
        # narratives, pas seulement des chiffres). mode_origine explicite
        # ci-dessous prime sur la déduction "exercice" de llm_coach pour le
        # logging (issue #26), donc sans effet de bord sur celui-ci.
        "mode_exercice": True,
        "mode_origine": "analyse_partie",
    }
    messages = [{
        "role": "user",
        "content": "Explique ce coup.",
    }]
    llm_config = {
        "llm_api_key": config.LLM_API_KEY,
        "llm_model": config.LLM_MODEL,
        "coach_log_path": config.COACH_CALLS_LOG_PATH,
    }

    response, error = llm_coach.get_coach_response(messages, context, coach_memory, llm_config)
    if error:
        emit("analyse_expliquer_coup_error", {"error": error, "uci": move.get("uci"), "idx": move.get("idx")})
    else:
        emit("analyse_expliquer_coup_response", {
            "uci": move.get("uci"), "idx": move.get("idx"), "text": response,
        })


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
    # Mode d'origine transmis par le client (issue #26, cf. static/board.js
    # askCoachOnDemand) — pour le logging uniquement (part. 3), ce handler
    # reste mode-agnostique par ailleurs.
    mode_origine = ((data or {}).get("mode_origine") or "").strip() or "chat_libre"

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
        "mode_origine": mode_origine,
    }
    llm_config = {
        "llm_api_key": config.LLM_API_KEY,
        "llm_model": config.LLM_MODEL,
        "coach_log_path": config.COACH_CALLS_LOG_PATH,
    }

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
    llm_config = {
        "llm_api_key": config.LLM_API_KEY,
        "llm_model": config.LLM_MODEL,
        "coach_log_path": config.COACH_CALLS_LOG_PATH,
    }

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
    llm_config = {
        "llm_api_key": config.LLM_API_KEY,
        "llm_model": config.LLM_MODEL,
        "coach_log_path": config.COACH_CALLS_LOG_PATH,
    }
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

    Issue #34 : détection de fin de partie (voir _game_over_info) vérifiée
    aussi APRÈS le coup de Stockfish, pas seulement avant — sinon un mat
    délivré par Stockfish lui-même n'est jamais signalé côté serveur, comme
    déjà fait dans les autres handlers depuis l'issue #10."""
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

    board.push(move)
    game_over_info = _game_over_info(board)

    emit("free_play_stockfish_move_response", {
        "uci": move.uci(),
        "game_over": game_over_info is not None,
        "game_over_info": game_over_info,
    })


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
    verdict_qualite = None
    verdict_delta_cp = None
    meilleur_coup_recalcule_san = None
    pv_coup_propose = ""
    pv_meilleur_coup = ""
    try:
        board = chess.Board(fen_avant)
        move = chess.Move.from_uci(uci)
        if move in board.legal_moves:
            coup_propose_san = board.san(move)
            # Verdict Stockfish ancré sur le coup exact proposé (issue #17) et
            # meilleur coup recalculé à la volée (issue #19), tous deux issus
            # du même appel evaluate_move, à une profondeur plus élevée que
            # celle du calcul par lot d'origine (depth=10 dans
            # build_patterns_erreurs.py, choix de vitesse pour traiter 280
            # parties d'un coup — non pertinent ici pour une position unique),
            # plus la PV (issue #20) — factorisé dans _evaluate_move_for_coach
            # (issue #26) pour être réutilisé tel quel par les autres modes.
            eval_result = _evaluate_move_for_coach(fen_avant, move)
            verdict_qualite = eval_result["verdict_qualite"]
            verdict_delta_cp = eval_result["verdict_delta_cp"]
            pv_coup_propose = eval_result["pv_coup_propose"]
            pv_meilleur_coup = eval_result["pv_meilleur_coup"]
            meilleur_coup_recalcule_san = eval_result["meilleur_coup"]
            board.push(move)
            eval_blancs_cp, eval_mat = _eval_blancs_apres(board)
    except Exception:
        pass

    coup_reel = _current_exercise.get("coup_joue_san") or _current_exercise.get("coup_joue_uci", "")
    # Meilleur coup recalculé ci-dessus à la même profondeur que le verdict
    # (issue #19) ; repli sur la valeur figée de erreurs_detectees.json
    # (calculée à depth=10 par build_patterns_erreurs.py, potentiellement
    # ancienne) uniquement si Stockfish est indisponible ou le coup proposé
    # illégal.
    meilleur_coup = meilleur_coup_recalcule_san or (
        _current_exercise.get("meilleur_coup_san") or _current_exercise.get("meilleur_coup_uci", "")
    )

    # Pièce jouée/capturée par chacun des trois coups comparés, tous les
    # trois depuis fen_avant (issue #18) — cf. _move_details_fr.
    coup_propose_piece, coup_propose_capture = _move_details_fr(fen_avant, coup_propose_san)
    coup_reel_piece, coup_reel_capture = _move_details_fr(fen_avant, coup_reel)
    meilleur_coup_piece, meilleur_coup_capture = _move_details_fr(fen_avant, meilleur_coup)

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
        "coup_propose_piece": coup_propose_piece,
        "coup_propose_capture": coup_propose_capture,
        "coup_reel": coup_reel,
        "coup_reel_piece": coup_reel_piece,
        "coup_reel_capture": coup_reel_capture,
        "meilleur_coup": meilleur_coup,
        "meilleur_coup_piece": meilleur_coup_piece,
        "meilleur_coup_capture": meilleur_coup_capture,
        # Ligne (PV) réellement calculée par Stockfish (issue #20), en SAN,
        # pour le coup proposé et pour le meilleur coup — cf.
        # llm_coach._build_context_text : sert au coach à justifier une
        # continuation réellement calculée plutôt qu'improviser une
        # explication tactique générique à partir du seul verdict chiffré.
        "pv_coup_propose": pv_coup_propose,
        "pv_meilleur_coup": pv_meilleur_coup,
        "eval_blancs_cp": eval_blancs_cp,
        "eval_mat": eval_mat,
        "verdict_qualite": verdict_qualite,
        "verdict_delta_cp": verdict_delta_cp,
        # Profondeur commune du recalcul à la volée (issue #19) du verdict et
        # du meilleur coup ci-dessus — n'entre pas dans le texte de contexte
        # envoyé au coach (cf. llm_coach._build_context_text, qui ignore les
        # clés qu'elle ne connaît pas), gardée uniquement pour être visible
        # dans data/logs/coach_calls.log (issue #18) et vérifier que les deux
        # évaluations partagent bien la même profondeur.
        "profondeur_reeval": DEPTH_EXERCICE_TEMPS_REEL if meilleur_coup_recalcule_san else None,
        "mode_exercice": True,
        "mode_origine": "exercice",
    }
    llm_config = {
        "llm_api_key": config.LLM_API_KEY,
        "llm_model": config.LLM_MODEL,
        "coach_log_path": config.COACH_CALLS_LOG_PATH,
    }

    response, error = llm_coach.get_coach_response(messages, context, coach_memory, llm_config)
    if error:
        emit("exercise_error", {"error": error})
    else:
        emit("exercise_comment", {
            "text": response,
            "coup_propose": coup_propose_san,
            "coup_reel": coup_reel,
            "meilleur_coup": meilleur_coup,
            # Transmis au client pour qu'il puisse enrichir le contexte d'une
            # question de suivi posée dans le chat libre (issue #17) — jamais
            # affiché tel quel côté UI (cf. exercise.js).
            "verdict_qualite": verdict_qualite,
            "verdict_delta_cp": verdict_delta_cp,
            # Idem pour la ligne (PV) calculée (issue #20) : sans ça, une
            # question de suivi dans le chat libre reperdrait l'ancrage sur
            # la ligne réellement calculée dès le tour suivant.
            "pv_coup_propose": pv_coup_propose,
            "pv_meilleur_coup": pv_meilleur_coup,
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

    # Verdict Stockfish + PV du coup joué (issue #17/#19/#20, mutualisé aux
    # modes hors exercice par l'issue #26) — remplace la simple comparaison
    # au meilleur coup (evaluate() sans PV) utilisée jusque-là ici.
    eval_result = _evaluate_move_for_coach(fen_avant, move)
    meilleur_coup_san = eval_result["meilleur_coup"]

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
        "verdict_qualite": eval_result["verdict_qualite"],
        "verdict_delta_cp": eval_result["verdict_delta_cp"],
        "pv_coup_propose": eval_result["pv_coup_propose"],
        "pv_meilleur_coup": eval_result["pv_meilleur_coup"],
        "mode_origine": "pedagogique",
    }
    llm_config = {
        "llm_api_key": config.LLM_API_KEY,
        "llm_model": config.LLM_MODEL,
        "coach_log_path": config.COACH_CALLS_LOG_PATH,
    }

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


@socketio.on("opening_suggestions")
def on_opening_suggestions(_data):
    """Suggestions rapides de coups d'ouverture populaires à la position de
    départ (issue #27, panneau "Travail d'ouverture") : coups les plus
    pondérés du livre Polyglot réel gm2001.bin, en plus du champ texte libre
    déjà existant — pour proposer un point de départ sans qu'Alain ait à
    connaître un nom d'ouverture avant de commencer."""
    if not opening_book.book_available(config.BOOK_PATH):
        emit("opening_suggestions_response", {"suggestions": []})
        return
    suggestions = opening_book.get_starting_suggestions(config.BOOK_PATH)
    emit("opening_suggestions_response", {"suggestions": suggestions})


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

    llm_config = {
        "llm_api_key": config.LLM_API_KEY,
        "llm_model": config.LLM_MODEL,
        "coach_log_path": config.COACH_CALLS_LOG_PATH,
    }
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
    eval_result = None

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
        # meilleur coup Stockfish, comme le mode pédagogique (issue #8), avec
        # verdict + PV (issue #26) — tant que la position reste dans le
        # livre, la comparaison à la popularité du livre suffit, pas besoin
        # de PV Stockfish (cf. issue #26, hors périmètre pour cette branche).
        eval_result = _evaluate_move_for_coach(fen_avant, move)
        meilleur_coup_san = eval_result["meilleur_coup"]

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
        "mode_origine": "ouverture",
    }
    if eval_result:
        # Verdict + PV (issue #26) uniquement calculés hors livre ci-dessus —
        # absents tant que la position reste dans le livre, comportement
        # inchangé pour cette branche.
        context["verdict_qualite"] = eval_result["verdict_qualite"]
        context["verdict_delta_cp"] = eval_result["verdict_delta_cp"]
        context["pv_coup_propose"] = eval_result["pv_coup_propose"]
        context["pv_meilleur_coup"] = eval_result["pv_meilleur_coup"]
    llm_config = {
        "llm_api_key": config.LLM_API_KEY,
        "llm_model": config.LLM_MODEL,
        "coach_log_path": config.COACH_CALLS_LOG_PATH,
    }

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
#
# _finale_camp_alain : camp qu'Alain contrôle réellement CETTE session — égal
# à finales.json camp_alain sauf en cas de démarrage "camps inversés" (issue
# #28), où c'est le camp normalement tenu par Stockfish. Ne modifie jamais
# data/finales.json, juste un choix ponctuel côté état serveur.
#
# _finale_camp_perdant : couleur python-chess (bool) du camp qui n'a que son
# roi dans cette finale — propriété FIXE de la définition (toujours l'opposé
# du camp_alain déclaré dans finales.json), indépendante de qui le contrôle
# dans la session (jeu normal, camps inversés ou démonstration) : sert de
# référence stable pour les cases hachurées (issue #28,
# _finale_restricted_king_squares).
#
# _finale_demo_active : True pendant une démonstration ("Voir une
# démonstration", issue #28) — Stockfish contrôle les deux camps, un
# demi-coup à la fois via finale_demo_next, sans jamais déclencher de
# commentaire automatique du coach (seul "Demander l'avis du coach" reste
# disponible).
#
# _finale_demo_board : plateau de la démonstration en cours, tenu côté
# serveur plutôt que reconstruit depuis la FEN envoyée par le client à
# chaque appel de finale_demo_next (issue #29) — une FEN seule ne porte pas
# l'historique des positions déjà traversées, indispensable à
# chess.Board.outcome(claim_draw=True) (_game_over_info) pour détecter une
# nulle par répétition : reconstruit à chaque appel, le plateau n'aurait
# jamais pu voir la partie se répéter, seule la règle des 50 coups (portée
# par le seul compteur halfmove_clock de la FEN) aurait fini par arrêter la
# démonstration.
_finale_camp_alain: str | None = None
_finale_camp_perdant: bool | None = None
_finale_nom: str | None = None
_finale_description: str | None = None
_finale_demo_active: bool = False
_finale_demo_board: chess.Board | None = None


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


# Traduction des drapeaux chess.Board.status() en messages compréhensibles
# pour l'éditeur de position (issue #16) — l'éditeur autorise n'importe quel
# placement de pièces, donc plusieurs positions illégales possibles à la fois
# (ex. deux rois blancs ET un pion sur la 1ère rangée) : on les liste toutes
# plutôt que de ne signaler que la première.
_EDITOR_STATUS_MESSAGES = {
    chess.STATUS_EMPTY: "L'échiquier est vide.",
    chess.STATUS_NO_WHITE_KING: "Il manque le roi blanc.",
    chess.STATUS_NO_BLACK_KING: "Il manque le roi noir.",
    chess.STATUS_TOO_MANY_KINGS: "Il y a plus d'un roi pour un même camp.",
    chess.STATUS_TOO_MANY_WHITE_PAWNS: "Trop de pions blancs (maximum 8).",
    chess.STATUS_TOO_MANY_BLACK_PAWNS: "Trop de pions noirs (maximum 8).",
    chess.STATUS_PAWNS_ON_BACKRANK: "Un pion est placé sur la 1ère ou la 8e rangée.",
    chess.STATUS_TOO_MANY_WHITE_PIECES: "Trop de pièces blanches au total.",
    chess.STATUS_TOO_MANY_BLACK_PIECES: "Trop de pièces noires au total.",
    chess.STATUS_BAD_CASTLING_RIGHTS: "Droits de roque incohérents.",
    chess.STATUS_INVALID_EP_SQUARE: "Case de prise en passant invalide.",
    chess.STATUS_OPPOSITE_CHECK: "Le camp qui n'est pas au trait est en échec — position impossible.",
    chess.STATUS_TOO_MANY_CHECKERS: "Trop de pièces donnent échec simultanément — position impossible.",
    chess.STATUS_IMPOSSIBLE_CHECK: "La situation d'échec actuelle est impossible à atteindre.",
}


@socketio.on("editor_validate")
def on_editor_validate(data):
    """Éditeur de position (issue #16) : valide en direct, via python-chess
    (Board.status()), la position en cours de construction — appelé à
    chaque placement/retrait/déplacement de pièce et à chaque changement de
    trait, pour indiquer clairement à Alain pourquoi une position est
    illégale plutôt que d'attendre l'échec silencieux de finale_add."""
    fen = ((data or {}).get("fen") or "").strip()
    try:
        board = chess.Board(fen)
    except Exception:
        emit("editor_validate_response", {"valid": False, "problems": ["FEN invalide."]})
        return

    status = board.status()
    if status == chess.STATUS_VALID:
        emit("editor_validate_response", {"valid": True, "problems": []})
        return

    problems = [msg for flag, msg in _EDITOR_STATUS_MESSAGES.items() if status & flag]
    if not problems:
        problems = ["Position invalide."]
    emit("editor_validate_response", {"valid": False, "problems": problems})


@socketio.on("finale_start")
def on_finale_start(data):
    """Charge une position-type de la bibliothèque de finales (issue #10) et
    fait jouer l'adversaire (Stockfish à pleine force) si la FEN de départ
    laisse le trait à l'adversaire du camp contrôlé par Alain.

    Camps inversés (issue #28, data["inverser"]) : Alain joue alors le camp
    normalement tenu par Stockfish (la défense, camp_alain de la
    position-type inchangé dans data/finales.json — juste un choix ponctuel
    pour cette session), et Stockfish tient automatiquement le camp
    technique via le même mécanisme de réponse automatique qu'en jeu normal
    (on_finale_move ci-dessous, inchangé). Le camp perdant (celui qui n'a
    que son roi, pour les cases hachurées) reste toujours déterminé par la
    définition de la finale, jamais par ce choix."""
    global _finale_camp_alain, _finale_camp_perdant, _finale_nom, _finale_description, _finale_demo_active, _finale_demo_board

    if not engine_manager:
        emit("finale_error", {"error": "stockfish_indisponible"})
        return

    finale_id = (data or {}).get("id", "")
    entry = finales.get_finale_by_id(finale_id)
    if not entry:
        emit("finale_error", {"error": "finale_inconnue"})
        return

    camp_alain_def = entry["camp_alain"]
    inverser = bool((data or {}).get("inverser", False))
    _finale_camp_alain = ("noirs" if camp_alain_def == "blancs" else "blancs") if inverser else camp_alain_def
    _finale_camp_perdant = chess.BLACK if camp_alain_def == "blancs" else chess.WHITE
    _finale_nom = entry["nom"]
    _finale_description = entry["description"]
    _finale_demo_active = False
    _finale_demo_board = None

    board = chess.Board(entry["fen"])
    camp_alain_color = chess.WHITE if _finale_camp_alain == "blancs" else chess.BLACK
    coup_ouverture = None
    if board.turn != camp_alain_color and not board.is_game_over():
        move = engine_manager.get_move_finales(board, think_time=0.5)
        if move:
            board.push(move)
            coup_ouverture = move.uci()

    emit("finale_started", {
        "fen": board.fen(),
        "camp_alain": _finale_camp_alain,
        "nom": _finale_nom,
        "description": _finale_description,
        "coup_ouverture": coup_ouverture,
        "king_restricted_squares": _finale_restricted_king_squares(board, _finale_camp_perdant),
    })


@socketio.on("finale_demo_start")
def on_finale_demo_start(data):
    """Bouton "Voir une démonstration" (issue #28) : Stockfish contrôlera les
    deux camps via finale_demo_next (un demi-coup à la fois, sur clic "Coup
    suivant" — aucun coup n'est joué ici, contrairement à finale_start dont
    le coup d'ouverture automatique n'aurait pas de sens en démonstration
    pure).

    Issue #36 : repart de la position actuellement affichée côté client
    (data["fen"], transmise par startFinaleDemo() dès qu'une partie est déjà
    chargée pour cette finale — coups joués par Alain et/ou par une
    précédente démonstration), pas systématiquement de la position de départ
    de data/finales.json. Le client n'envoie ce champ que lorsqu'une partie
    est effectivement en cours ; sinon (aucune partie encore chargée, ou FEN
    invalide) on retombe sur la FEN de départ de la finale, comportement
    inchangé."""
    global _finale_camp_alain, _finale_camp_perdant, _finale_nom, _finale_description, _finale_demo_active, _finale_demo_board

    if not engine_manager:
        emit("finale_error", {"error": "stockfish_indisponible"})
        return

    finale_id = (data or {}).get("id", "")
    entry = finales.get_finale_by_id(finale_id)
    if not entry:
        emit("finale_error", {"error": "finale_inconnue"})
        return

    camp_alain_def = entry["camp_alain"]
    _finale_camp_alain = camp_alain_def
    _finale_camp_perdant = chess.BLACK if camp_alain_def == "blancs" else chess.WHITE
    _finale_nom = entry["nom"]
    _finale_description = entry["description"]
    _finale_demo_active = True

    board = None
    fen_client = ((data or {}).get("fen") or "").strip()
    if fen_client:
        try:
            board = chess.Board(fen_client)
        except ValueError:
            board = None
    if board is None:
        board = chess.Board(entry["fen"])
    # Issue #29 : plateau tenu côté serveur pour toute la durée de la
    # démonstration (voir le commentaire sur _finale_demo_board ci-dessus),
    # pas reconstruit depuis une FEN client à chaque demi-coup.
    _finale_demo_board = board
    emit("finale_demo_started", {
        "fen": board.fen(),
        "camp_alain": _finale_camp_alain,
        "nom": _finale_nom,
        "description": _finale_description,
        "king_restricted_squares": _finale_restricted_king_squares(board, _finale_camp_perdant),
    })


@socketio.on("finale_demo_next")
def on_finale_demo_next(_data):
    """Bouton "Coup suivant" en démonstration (issue #28) : Stockfish (pleine
    force) joue exactement un demi-coup pour le camp au trait, quel qu'il
    soit — pas d'enchaînement automatique, pas de commentaire du coach
    (aucun coup n'est "celui d'Alain" ici).

    Issue #29 : joue sur _finale_demo_board (plateau tenu côté serveur
    depuis finale_demo_start, avec l'historique complet de la
    démonstration), pas sur une FEN reconstruite depuis le client à chaque
    appel — indispensable pour que _game_over_info puisse détecter une
    nulle par répétition, pas seulement la règle des 50 coups. Dès que la
    partie est terminée (mat, pat ou nulle), on n'interroge plus Stockfish :
    la démonstration s'arrête et le résultat est renvoyé au client."""
    if not engine_manager:
        emit("finale_error", {"error": "stockfish_indisponible"})
        return
    if not _finale_demo_active or _finale_demo_board is None:
        emit("finale_error", {"error": "finale_inconnue"})
        return

    board = _finale_demo_board
    game_over_info = _game_over_info(board)
    move_uci = None
    if game_over_info is None:
        move = engine_manager.get_move_finales(board, think_time=0.5)
        if move:
            board.push(move)
            move_uci = move.uci()
            game_over_info = _game_over_info(board)

    emit("finale_demo_move", {
        "fen": board.fen(),
        "uci": move_uci,
        "game_over": game_over_info is not None,
        "game_over_info": game_over_info,
        "coups_joues": len(board.move_stack),
        "king_restricted_squares": _finale_restricted_king_squares(board, _finale_camp_perdant),
    })


@socketio.on("finale_demo_stop")
def on_finale_demo_stop(_data):
    """Bouton "Arrêter la démonstration" (issue #35) : transforme la
    position atteinte par _finale_demo_board en position de jeu normale du
    mode finales, sans réinitialisation — le client garde intact son
    historique de coups (finaleGame, déjà tenu à jour demi-coup par
    demi-coup pendant la démonstration, voir finales.js). _finale_camp_alain
    et _finale_camp_perdant, propriétés fixes de la finale sélectionnée, ne
    changent pas.

    Si c'est au tour de l'adversaire automatique sur la position atteinte,
    il joue immédiatement (comme le coup d'ouverture de finale_start ou la
    réponse automatique de finale_move) ; sinon la position est simplement
    renvoyée telle quelle et Alain reprend la main normalement."""
    global _finale_demo_active, _finale_demo_board

    if not engine_manager:
        emit("finale_error", {"error": "stockfish_indisponible"})
        return
    if not _finale_demo_active or _finale_demo_board is None:
        emit("finale_error", {"error": "finale_inconnue"})
        return

    board = _finale_demo_board
    _finale_demo_active = False
    _finale_demo_board = None

    camp_alain_color = chess.WHITE if _finale_camp_alain == "blancs" else chess.BLACK
    game_over_info = _game_over_info(board)
    move_uci = None
    if game_over_info is None and board.turn != camp_alain_color:
        move = engine_manager.get_move_finales(board, think_time=0.5)
        if move:
            board.push(move)
            move_uci = move.uci()
            game_over_info = _game_over_info(board)

    emit("finale_demo_stopped", {
        "fen": board.fen(),
        "uci": move_uci,
        "game_over": game_over_info is not None,
        "game_over_info": game_over_info,
        "king_restricted_squares": _finale_restricted_king_squares(board, _finale_camp_perdant),
    })


@socketio.on("finale_abandon")
def on_finale_abandon(_data):
    """Bouton "Abandonner" (issue #11) : retour à un état neutre côté
    serveur, pas de sauvegarde."""
    global _finale_camp_alain, _finale_camp_perdant, _finale_nom, _finale_description, _finale_demo_active, _finale_demo_board
    _finale_camp_alain = None
    _finale_camp_perdant = None
    _finale_nom = None
    _finale_description = None
    _finale_demo_active = False
    _finale_demo_board = None


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

    # Verdict Stockfish + PV du coup joué (issue #17/#19/#20, mutualisé aux
    # modes hors exercice par l'issue #26) — remplace la simple comparaison
    # au meilleur coup (evaluate() sans PV) utilisée jusque-là ici.
    eval_result = _evaluate_move_for_coach(fen_avant, move)
    meilleur_coup_san = eval_result["meilleur_coup"]

    board.push(move)

    # Évaluation Stockfish réelle de la position résultant du coup d'Alain
    # (issue #12 point 3), avant que l'adversaire ne rejoue.
    eval_blancs_cp, eval_mat = _eval_blancs_apres(board)

    # Réponse automatique de l'adversaire à pleine force, sans plafond Elo
    # (issue #32 — instance dédiée get_move_finales, séparée du moteur
    # Elo limité du bouton "Coup Stockfish"/mode partie libre).
    game_over_info = _game_over_info(board)
    stockfish_move_uci = None
    if game_over_info is None:
        reply = engine_manager.get_move_finales(board, think_time=0.5)
        if reply:
            board.push(reply)
            stockfish_move_uci = reply.uci()
            game_over_info = _game_over_info(board)

    emit("finale_stockfish_move", {
        "fen": board.fen(),
        "uci": stockfish_move_uci,
        "game_over": game_over_info is not None,
        "game_over_info": game_over_info,
        "king_restricted_squares": _finale_restricted_king_squares(board, _finale_camp_perdant),
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
        "verdict_qualite": eval_result["verdict_qualite"],
        "verdict_delta_cp": eval_result["verdict_delta_cp"],
        "pv_coup_propose": eval_result["pv_coup_propose"],
        "pv_meilleur_coup": eval_result["pv_meilleur_coup"],
        "mode_origine": "finales",
    }
    llm_config = {
        "llm_api_key": config.LLM_API_KEY,
        "llm_model": config.LLM_MODEL,
        "coach_log_path": config.COACH_CALLS_LOG_PATH,
    }

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
