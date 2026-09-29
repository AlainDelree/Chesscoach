"""
game_facts.py — ChessCoach (issue #55)

Bloc de faits factuels calculés côté serveur avec python-chess (aucun appel
à Stockfish, aucun appel API supplémentaire) pour le chat libre du coach
dans les modes interactifs (partie libre, pédagogique, ouverture, finales) :
le modèle reconstituait jusque-là la partie de mémoire à partir du seul
texte du PGN, ce qu'il fait mal (coups attribués au mauvais camp, échanges
inventés, capture décisive manquée — cf. issue #55, même famille que "dame
en b5"/"cavalier inexistant en g6" déjà traitées par les garde-fous anti-
invention des issues #25/#44). Ce module ne remplace pas le PGN transmis au
modèle, il le complète par des faits déjà calculés mécaniquement.

Volontairement PAS branché sur le mode exercice (déjà ancré sur un verdict
Stockfish, cf. _EXERCISE_SYSTEM_ADDENDUM dans llm_coach.py) ni sur la revue
de parties importées de la bibliothèque (hors périmètre de l'issue #55) —
ce choix est fait par l'appelant (app.py), pas ici.
"""

import io
import logging

import chess
import chess.pgn

logger = logging.getLogger("chesscoach.game_facts")

_VALEURS = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0,
}

_NOM_PIECE = {
    chess.PAWN: "le pion",
    chess.KNIGHT: "le cavalier",
    chess.BISHOP: "le fou",
    chess.ROOK: "la tour",
    chess.QUEEN: "la dame",
    chess.KING: "le roi",
}

_NOM_PIECE_MAJ = {
    chess.PAWN: "Pion",
    chess.KNIGHT: "Cavalier",
    chess.BISHOP: "Fou",
    chess.ROOK: "Tour",
    chess.QUEEN: "Dame",
    chess.KING: "Roi",
}

# Seuil de variation matérielle (en points classiques) à partir duquel un
# coup est retenu comme "moment clé" (issue #55, point 2 de la tâche).
_SEUIL_MOMENT_CLE = 2


def _materiel(board: "chess.Board") -> tuple[int, int]:
    """Matériel des Blancs/Noirs en points classiques (pion=1, cavalier=3,
    fou=3, tour=5, dame=9, roi non compté)."""
    blancs = sum(_VALEURS[pt] * len(board.pieces(pt, chess.WHITE)) for pt in _VALEURS)
    noirs  = sum(_VALEURS[pt] * len(board.pieces(pt, chess.BLACK)) for pt in _VALEURS)
    return blancs, noirs


def _camp_label(est_blanc: bool, camp_alain: str) -> str:
    """"Blancs (Alain)"/"Noirs (adversaire)", ou l'inverse selon camp_alain —
    jamais une simple déduction du trait, pour éviter d'attribuer un coup au
    mauvais camp (cause directe du bug de l'issue #55)."""
    camp_txt = "Blancs" if est_blanc else "Noirs"
    if camp_alain not in ("blancs", "noirs"):
        return camp_txt
    est_alain = (est_blanc and camp_alain == "blancs") or (not est_blanc and camp_alain == "noirs")
    return f"{camp_txt} (Alain)" if est_alain else f"{camp_txt} (adversaire)"


def _liste_pieces(board: "chess.Board", est_blanc: bool) -> str:
    pieces = []
    for pt in (chess.KING, chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT, chess.PAWN):
        for square in sorted(board.pieces(pt, est_blanc)):
            pieces.append(f"{_NOM_PIECE_MAJ[pt]} {chess.square_name(square)}")
    return ", ".join(pieces) if pieces else "aucune pièce restante"


def _numero_coup(board: "chess.Board", est_blanc: bool) -> str:
    coup_plein = board.fullmove_number
    return f"{coup_plein}." if est_blanc else f"{coup_plein}..."


def _decrit_moment_cle(numero: str, san: str, est_blanc_qui_joue: bool, camp_alain: str,
                        piece_capturee, case_arrivee: int, board_apres: "chess.Board",
                        variation: int) -> str:
    label_capturant = _camp_label(est_blanc_qui_joue, camp_alain)
    label_perdant   = _camp_label(not est_blanc_qui_joue, camp_alain)
    case_txt = chess.square_name(case_arrivee)
    if piece_capturee is not None:
        nom_piece = _NOM_PIECE.get(piece_capturee.piece_type, "une pièce")
        # nom_piece porte déjà son article ("la dame", "le cavalier"...).
        # Reprise possible = un coup légal de la partie perdante peut, dès
        # maintenant (c'est son trait après ce coup), reprendre sur cette
        # case précise — calculé via les coups légaux réels (échec, clouage,
        # obstruction... tout est déjà pris en compte par python-chess),
        # jamais supposé (c'est exactement ce que le coach a inventé à tort
        # dans l'incident source de l'issue #55, ex. "16.Rxd1" impossible).
        reprise_possible = any(m.to_square == case_arrivee for m in board_apres.legal_moves)
        reprise_txt = "reprise possible" if reprise_possible else "aucune reprise possible"
        return (
            f"Coup {numero} {san} : {label_capturant} capture {nom_piece} de "
            f"{label_perdant} en {case_txt} ({reprise_txt}), variation matérielle "
            f"de {variation} points."
        )
    return (
        f"Coup {numero} {san} : {label_capturant} change le bilan matériel de "
        f"{variation} points en {case_txt} (promotion)."
    )


def build_game_facts_text(pgn_text: str, camp_alain: str, flagged_moves: list | None = None) -> str:
    """Construit le bloc de faits calculés (issue #55) :
      1. coups numérotés, camp explicite de chacun, bilan matériel après
         chaque coup (point de vue d'Alain, points classiques) ;
      2. moments clés (variation matérielle d'au moins 2 points, qui capture
         quoi, reprise possible ou non) ;
      3. position actuelle : pièces par camp avec cases exactes, FEN,
         matériel restant, mention explicite si un camp n'a plus de dame ;
      4. si fourni, les coups flagués par une analyse mécanique Stockfish
         déjà effectuée cette session (bouton "Analyser cette partie").

    Repli silencieux ("") si le PGN est vide/illisible ou si camp_alain n'est
    pas "blancs"/"noirs" : le contexte reste utilisable sans ce bloc plutôt
    que de faire échouer la réponse du coach.
    """
    pgn_text = (pgn_text or "").strip()
    if not pgn_text or camp_alain not in ("blancs", "noirs"):
        return ""

    try:
        game = chess.pgn.read_game(io.StringIO(pgn_text))
        if game is None:
            return ""
        board = game.board()
    except Exception as e:
        logger.warning(f"[GAME_FACTS] PGN illisible : {e}")
        return ""

    lignes_coups = []
    moments_cles = []
    w_avant, b_avant = _materiel(board)

    try:
        for move in game.mainline_moves():
            est_blanc = board.turn == chess.WHITE
            numero = _numero_coup(board, est_blanc)
            try:
                san = board.san(move)
            except Exception:
                san = move.uci()

            case_arrivee = move.to_square
            piece_capturee = None
            if board.is_capture(move):
                piece_capturee = board.piece_at(case_arrivee)
                if piece_capturee is None and board.is_en_passant(move):
                    piece_capturee = chess.Piece(chess.PAWN, not est_blanc)

            board.push(move)
            w_apres, b_apres = _materiel(board)

            label = _camp_label(est_blanc, camp_alain)
            alain_apres = w_apres if camp_alain == "blancs" else b_apres
            adv_apres   = b_apres if camp_alain == "blancs" else w_apres
            lignes_coups.append(
                f"{numero} {san} — {label} — matériel Alain {alain_apres} / adversaire {adv_apres}"
            )

            delta_w = w_apres - w_avant
            delta_b = b_apres - b_avant
            variation = delta_b if abs(delta_b) >= abs(delta_w) else delta_w
            if abs(variation) >= _SEUIL_MOMENT_CLE:
                moments_cles.append(_decrit_moment_cle(
                    numero, san, est_blanc, camp_alain, piece_capturee, case_arrivee,
                    board, abs(variation),
                ))

            w_avant, b_avant = w_apres, b_apres
    except Exception as e:
        logger.warning(f"[GAME_FACTS] Rejeu du PGN interrompu : {e}")
        if not lignes_coups:
            return ""

    w_final, b_final = _materiel(board)
    label_blancs = _camp_label(True, camp_alain)
    label_noirs  = _camp_label(False, camp_alain)

    parties = [
        "Faits calculés mécaniquement sur cette partie (python-chess, pas "
        "Stockfish) — seule base factuelle fiable pour le déroulement de "
        "cette partie, à utiliser en complément du PGN :",
        "Coups joués, camp explicite et bilan matériel après chaque coup :\n"
        + "\n".join(lignes_coups),
    ]
    if moments_cles:
        parties.append(
            f"Moments clés (variation matérielle d'au moins {_SEUIL_MOMENT_CLE} points) :\n"
            + "\n".join(moments_cles)
        )
    else:
        parties.append(
            f"Moments clés : aucune variation matérielle d'au moins {_SEUIL_MOMENT_CLE} "
            "points dans cette partie."
        )

    position_lignes = [
        f"Position actuelle — {label_blancs} : {_liste_pieces(board, True)} (matériel {w_final})",
        f"Position actuelle — {label_noirs} : {_liste_pieces(board, False)} (matériel {b_final})",
        f"FEN : {board.fen()}",
    ]
    if not board.pieces(chess.QUEEN, chess.WHITE):
        position_lignes.append("Les Blancs n'ont plus de dame.")
    if not board.pieces(chess.QUEEN, chess.BLACK):
        position_lignes.append("Les Noirs n'ont plus de dame.")
    parties.append("\n".join(position_lignes))

    if flagged_moves:
        lignes_flag = []
        for m in flagged_moves:
            if not isinstance(m, dict):
                continue
            coup_plein = m.get("coup_plein")
            san        = (m.get("san") or "").strip()
            camp       = (m.get("camp") or "").strip()
            delta_cp   = m.get("delta_cp")
            qualite    = (m.get("qualite") or "").strip()
            if not san or coup_plein is None:
                continue
            camp_txt = _camp_label(camp == "blancs", camp_alain) if camp in ("blancs", "noirs") else ""
            detail_cp = f", perte de {delta_cp} centipawns" if isinstance(delta_cp, (int, float)) else ""
            lignes_flag.append(
                f"Coup {coup_plein} {san}{(' — ' + camp_txt) if camp_txt else ''} — "
                f"{qualite or 'flagué'}{detail_cp}"
            )
        if lignes_flag:
            parties.append(
                "Coups flagués par l'analyse mécanique Stockfish déjà effectuée cette "
                "session (bouton \"Analyser cette partie\") :\n" + "\n".join(lignes_flag)
            )

    return "\n\n".join(parties)
