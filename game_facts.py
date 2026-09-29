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

Ajouté par l'issue #56 :
  - camp_alain_from_pgn_headers : déduction du camp d'Alain depuis les
    en-têtes PGN White/Black (pseudo athanatos123 ou nom "Alain"), reprise du
    module d'explications narratives des coups décisifs (llm_coach.py
    get_move_explanations) qui n'avait jusque-là aucun moyen de savoir quel
    camp est celui d'Alain — cause confirmée d'un coup adverse attribué à
    Alain dans une explication ;
  - camp_label rendu public (au lieu de _camp_label) pour être réutilisé par
    get_move_explanations plutôt que d'y redupliquer la même logique
    d'étiquetage ;
  - build_game_facts_text ajoute désormais la fin de partie (mat, pat, nulle
    par la règle ou abandon) comme dernier moment clé même sans variation
    matérielle d'au moins _SEUIL_MOMENT_CLE points (constat en test réel :
    un mat en 9 coups sans aucune perte de matériel passait inaperçu du
    bloc, le coach ne s'en sortant que grâce au signe "#" du texte PGN).
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

# Pseudo Lichess/Chess.com d'Alain (issue #56) — même constante que
# build_patterns_erreurs.py/build_repertoire_ouvertures.py (scripts autonomes
# non importés par app.py, donc dupliquée ici plutôt que factorisée entre des
# modules qui ne se connaissent pas autrement).
ALAIN_PSEUDO = "athanatos123"


def camp_alain_from_pgn_headers(white: str, black: str) -> str:
    """Déduit le camp d'Alain depuis les en-têtes PGN White/Black (issue #56) :
    pseudo Lichess/Chess.com (ALAIN_PSEUDO, casse ignorée) pour une partie
    importée de la bibliothèque, ou le nom "Alain" pour une partie jouée dans
    l'appli (pédagogique/ouverture/finales taguent déjà "Alain" contre
    "Stockfish"/"Adversaire" dans le PGN transmis à l'analyse, cf.
    pedagogic.js/opening.js/finales.js _*GamePgnForAnalysis).

    Retourne "blancs"/"noirs", ou "" si aucun des deux en-têtes ne correspond
    (partie entre deux tiers, ou mode "partie libre" où les deux camps
    peuvent être joués par Alain) — jamais une devinette."""
    def _est_alain(nom) -> bool:
        nom = (nom or "").strip().lower()
        return nom in (ALAIN_PSEUDO, "alain")

    if _est_alain(white):
        return "blancs"
    if _est_alain(black):
        return "noirs"
    return ""


def _materiel(board: "chess.Board") -> tuple[int, int]:
    """Matériel des Blancs/Noirs en points classiques (pion=1, cavalier=3,
    fou=3, tour=5, dame=9, roi non compté)."""
    blancs = sum(_VALEURS[pt] * len(board.pieces(pt, chess.WHITE)) for pt in _VALEURS)
    noirs  = sum(_VALEURS[pt] * len(board.pieces(pt, chess.BLACK)) for pt in _VALEURS)
    return blancs, noirs


def camp_label(est_blanc: bool, camp_alain: str) -> str:
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
    label_capturant = camp_label(est_blanc_qui_joue, camp_alain)
    label_perdant   = camp_label(not est_blanc_qui_joue, camp_alain)
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


def _decrit_fin_de_partie(numero: str, san: str, est_blanc_qui_joue: bool, camp_alain: str,
                           board_final: "chess.Board", headers) -> str | None:
    """Fin de partie (issue #56, point 4) : mat, pat, nulle par la règle
    (matériel insuffisant, 75 coups, répétition quintuple) calculée
    mécaniquement avec python-chess (jamais déduite du seul signe "#" du
    texte PGN), ou abandon si aucune de ces règles ne s'applique mais que la
    partie s'arrête quand même sur un Result renseigné dans l'en-tête PGN.
    Retourne None si le dernier coup ne termine pas la partie (revue en
    cours d'une partie non terminée)."""
    auteur = camp_label(est_blanc_qui_joue, camp_alain)
    if board_final.is_checkmate():
        return f"Coup {numero} {san} : {auteur} met échec et mat — fin de partie."
    if board_final.is_stalemate():
        return f"Coup {numero} {san} : {auteur} conduit à un pat (nulle) — fin de partie."
    if board_final.is_insufficient_material():
        return (
            f"Coup {numero} {san} ({auteur}) : nulle par matériel insuffisant "
            "pour mater — fin de partie."
        )
    if board_final.is_seventyfive_moves():
        return f"Coup {numero} {san} ({auteur}) : nulle par la règle des 75 coups — fin de partie."
    if board_final.is_fivefold_repetition():
        return f"Coup {numero} {san} ({auteur}) : nulle par répétition quintuple — fin de partie."
    if board_final.is_game_over():
        return f"Coup {numero} {san} ({auteur}) : fin de partie (nulle par la règle)."

    resultat = (headers.get("Result") or "").strip()
    if resultat and resultat != "*":
        return (
            f"Coup {numero} {san} ({auteur}) : dernier coup joué sur l'échiquier ; la "
            f"partie s'est terminée ensuite par abandon ou accord (aucun mat ni pat sur "
            f"l'échiquier), résultat PGN {resultat}."
        )
    return None


def build_game_facts_text(pgn_text: str, camp_alain: str, flagged_moves: list | None = None) -> str:
    """Construit le bloc de faits calculés (issue #55) :
      1. coups numérotés, camp explicite de chacun, bilan matériel après
         chaque coup (point de vue d'Alain, points classiques) ;
      2. moments clés (variation matérielle d'au moins 2 points, qui capture
         quoi, reprise possible ou non) et, en dernier, la fin de partie
         (mat/pat/nulle par la règle/abandon) si la partie est terminée —
         ajoutée même sans aucune variation matérielle (issue #56 point 4) ;
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
    # Coup/auteur du dernier coup effectivement joué (issue #56, point 4) —
    # mis à jour seulement une fois le coup poussé avec succès sur board,
    # jamais sur un coup dont le traitement aurait échoué en cours de route
    # (cf. except ci-dessous), pour ne jamais désigner comme "dernier coup"
    # un coup qui ne s'est pas réellement joué jusqu'au bout.
    dernier_numero = dernier_san = dernier_est_blanc = None

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

            label = camp_label(est_blanc, camp_alain)
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
            dernier_numero, dernier_san, dernier_est_blanc = numero, san, est_blanc
    except Exception as e:
        logger.warning(f"[GAME_FACTS] Rejeu du PGN interrompu : {e}")
        if not lignes_coups:
            return ""

    if dernier_numero is not None:
        moment_fin = _decrit_fin_de_partie(
            dernier_numero, dernier_san, dernier_est_blanc, camp_alain, board, game.headers,
        )
        if moment_fin:
            moments_cles.append(moment_fin)

    w_final, b_final = _materiel(board)
    label_blancs = camp_label(True, camp_alain)
    label_noirs  = camp_label(False, camp_alain)

    parties = [
        "Faits calculés mécaniquement sur cette partie (python-chess, pas "
        "Stockfish) — seule base factuelle fiable pour le déroulement de "
        "cette partie, à utiliser en complément du PGN :",
        "Coups joués, camp explicite et bilan matériel après chaque coup :\n"
        + "\n".join(lignes_coups),
    ]
    if moments_cles:
        parties.append(
            f"Moments clés (variation matérielle d'au moins {_SEUIL_MOMENT_CLE} points, "
            "et fin de partie si la partie est terminée) :\n" + "\n".join(moments_cles)
        )
    else:
        parties.append(
            f"Moments clés : aucune variation matérielle d'au moins {_SEUIL_MOMENT_CLE} "
            "points dans cette partie, qui n'est pas terminée."
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
            camp_txt = camp_label(camp == "blancs", camp_alain) if camp in ("blancs", "noirs") else ""
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
