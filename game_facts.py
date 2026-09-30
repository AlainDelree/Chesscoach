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

Ajouté par l'issue #57, constat sur une partie pédagogique réelle perdue par
Alain (Blancs) :
  - solde net après reprise : un moment clé qui capture une pièce n'indiquait
    jusqu'ici que la variation matérielle BRUTE de ce seul demi-coup (ex.
    "variation matérielle de 9 points" pour 16...Rxb3, qui capture la dame),
    sans jamais dire qu'une reprise immédiate (Bxb3/Nxb3/axb3) ramenait le
    solde réel à 4 points. Le coach a retenu le chiffre brut (9) comme perte
    sèche, sans compensation. _solde_net_apres_capture calcule ce solde
    (mécaniquement, coups légaux réels, pas de recherche en profondeur au-delà
    d'une reprise immédiate) et _decrit_moment_cle l'ajoute explicitement, en
    disant sans ambiguïté lequel des deux chiffres (brut ou net) est le
    résultat réel de l'échange ;
  - find_stockfish_check_targets : identifie (sans appeler Stockfish, voir
    plus bas) les deux derniers coups d'Alain qui précèdent le premier moment
    où il perd au moins _SEUIL_MOMENT_CLE points nets (après reprise
    mécanique éventuelle) ou se fait mater — le coup qui a permis la perte,
    et celui d'avant. L'appelant (app.py, qui détient engine_manager) fait
    évaluer ces deux positions par Stockfish avec un budget de temps court et
    borné, puis transmet le résultat à build_game_facts_text via le
    paramètre stockfish_check. Ce module reste volontairement sans aucun
    appel Stockfish direct (cf. en-tête ci-dessus) : il ne fait que désigner
    QUELLES positions mériteraient une vérification, jamais le calcul
    lui-même.

Ajouté par l'issue #62, constat sur la même partie pédagogique réelle
(Alain Blancs) : le "premier moment significatif" (6...Nxd5/7.Qxd2, perte
nette de 2 points) n'était pas le tournant réel de la partie — 8.Qf4?? perd
ensuite la dame sans aucune reprise (9 points), et le chat comme l'analyse
manuelle ne s'accordaient pas sur lequel des deux était "le vrai tournant" :
  - find_stockfish_check_targets cible désormais AUSSI le moment de plus
    grande perte nette de la partie (ou le mat), pas seulement le premier
    moment qui franchit le seuil — jusqu'à deux moments distincts, le plus
    grave toujours en premier (donc toujours vérifié en priorité si le
    budget de temps de l'appelant est dépassé avant la fin), chaque cible
    étiquetée "plus_grave"/"premier_significatif", en dédupliquant les
    positions communes aux deux moments ;
  - describe_reponse_suivante : pour l'explication d'un coup flagué
    (get_move_explanations/get_coach_response, llm_coach.py), calcule
    mécaniquement la réponse réellement jouée ensuite dans la partie et sa
    conséquence matérielle immédiate (capture, solde net après reprise
    éventuelle) — sans cette donnée, l'explication de 8.Qf4?? se limitait à
    "le roque était préférable pour la sécurité du roi", sans jamais
    mentionner que 8...Nxf4 capture la dame sans reprise possible : le
    modèle devait deviner la réfutation réelle plutôt que la recevoir.

Ajouté par l'issue #66, constat sur une partie pédagogique réelle (Haiku
puis Sonnet, Alain Noirs) : même quand le bloc de faits donnait déjà le bon
matériel, le bon coup et le bon meilleur coup, le modèle reconstituait de
tête quelle pièce joue et où se trouvent les autres pièces au moment d'un
coup cité en seule notation SAN, et se trompait (cavalier b6 au lieu de f6
pour Nxg4, fou capturant un cavalier au lieu d'un pion pour Bxe5, cavalier
blanc "en e5" au lieu de g4 pour 7...h5) — même famille que "dame en b5" et
la confusion de camp déjà traitées par les issues #25/#44. Un second
symptôme, propre à Sonnet sur la même partie : une capture présentée comme
"gratuite" alors que la pièce prise était défendue et reprise dans la ligne
principale de Stockfish elle-même (8...Nxg4, cavalier g4 défendu par le fou
e2) :
  - describe_move_mechanically / _decrit_coup_mecanique : décrit
    mécaniquement UN coup (pièce et case de départ, case d'arrivée, capture
    éventuelle avec type/case/défense/solde net après reprise, échec/mat, et
    pièces adverses désormais attaquées) à partir d'une position FEN et d'un
    coup en SAN ou UCI — jamais deviné, toujours calculé avec python-chess
    sur la position réelle. Réutilise _solde_net_apres_capture (issue #57)
    pour ne jamais présenter comme "gratuite" une capture reprenable ;
  - describe_pv_mechanically : même calcul, coup par coup, sur les premiers
    plis d'une ligne principale (PV) déjà citée dans le bloc de faits ;
  - find_stockfish_check_targets et build_game_facts_text : chaque coup cité
    par la vérification Stockfish ciblée (coup joué, meilleur coup, réponse
    réellement jouée ensuite, premier pli de la ligne principale après le
    meilleur coup) reçoit désormais cette description mécanique, plus la
    position (pièce par pièce) juste avant le coup joué ;
  - build_game_facts_text ajoute une rubrique séparée "pions perdus sans
    reprise" (variation d'exactement 1 point, aucune reprise possible),
    limitée aux 3 plus récents de la partie — ces pertes restent sous le
    seuil de 2 points des "moments clés" (ex. 6.Nxe5 sur la partie de test de
    l'issue #66, pion e5 laissé sans défense par 5...Nb6) et passaient donc
    inaperçues.
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

# Nombre maximal de pions perdus sans reprise conservés dans le bloc de
# faits (issue #66, point 4) — les plus récents de la partie, les autres
# étant omis plutôt que de faire grossir le bloc indéfiniment sur une
# longue partie.
_MAX_PIONS_PERDUS_SANS_REPRISE = 3

# Genre grammatical des pièces (issue #66) : "la dame"/"la tour" sont
# féminines, les autres masculines — nécessaire pour accorder l'adjectif de
# couleur ("blanc"/"blanche") dans les descriptions mécaniques de coups.
_FEMININ = {chess.QUEEN, chess.ROOK}


def _couleur_accordee(piece_type: int, est_blanc: bool) -> str:
    if est_blanc:
        return "blanche" if piece_type in _FEMININ else "blanc"
    return "noire" if piece_type in _FEMININ else "noir"


def _nom_piece_capturee(piece_type: int) -> str:
    """Nom (avec article) d'une pièce CAPTURÉE dans une description
    mécanique (issue #66) — indéfini pour un pion ("un pion", générique,
    jamais individuellement identifié), défini pour les autres pièces
    ("le cavalier", "la dame"...), cohérent avec l'exemple demandé par
    l'issue #66 ("capture un pion blanc" mais "capture le cavalier blanc")."""
    if piece_type == chess.PAWN:
        return "un pion"
    return _NOM_PIECE.get(piece_type, "une pièce")


def _premier_coup_vers(board: "chess.Board", case: int) -> "chess.Move | None":
    """Premier coup légal de `board` qui atterrit sur `case`, ou None — sert
    à identifier QUELLE pièce reprendrait une capture (issue #66), en plus
    de _solde_net_apres_capture qui n'en calcule que le solde chiffré."""
    return next((m for m in board.legal_moves if m.to_square == case), None)


def _pieces_attaquees_apres(board_apres: "chess.Board", case: int) -> list[str]:
    """Pièces adverses (hors roi, déjà signalé séparément via l'échec)
    désormais attaquées par la pièce qui vient de jouer en `case` (issue
    #66, point 1) — calculé mécaniquement (chess.Board.attacks), jamais
    déduit de mémoire."""
    piece = board_apres.piece_at(case)
    if piece is None:
        return []
    cibles = []
    for sq in board_apres.attacks(case):
        cible = board_apres.piece_at(sq)
        if cible is not None and cible.color != piece.color and cible.piece_type != chess.KING:
            cibles.append(f"{_NOM_PIECE_MAJ[cible.piece_type]} {chess.square_name(sq)}")
    return cibles


def _decrit_coup_mecanique(board: "chess.Board", move: "chess.Move", camp_alain: str = "") -> str:
    """Décrit mécaniquement UN coup légal de `board` (position AVANT ce
    coup, non modifiée par cet appel) — issue #66, point 1 : quelle pièce
    joue (type et case de départ), case d'arrivée, capture éventuelle (type
    de pièce ou pion capturé et sa case, défendue ou non, solde net après
    reprise éventuelle — réutilise _solde_net_apres_capture de l'issue #57
    pour ne jamais présenter comme "gratuite" une capture reprenable),
    échec ou mat, et quelles pièces adverses ce coup attaque désormais.
    Jamais deviné : uniquement calculé avec python-chess sur cette position
    réelle."""
    est_blanc = board.turn == chess.WHITE
    piece = board.piece_at(move.from_square)
    origine = chess.square_name(move.from_square)
    arrivee = chess.square_name(move.to_square)
    label_camp = camp_label(est_blanc, camp_alain)
    label_adv = camp_label(not est_blanc, camp_alain)

    est_ep = board.is_en_passant(move)
    piece_capturee = board.piece_at(move.to_square)
    if piece_capturee is None and est_ep:
        piece_capturee = chess.Piece(chess.PAWN, not est_blanc)

    board_apres = board.copy()
    board_apres.push(move)

    piece_txt = f"{_NOM_PIECE[piece.piece_type]} {_couleur_accordee(piece.piece_type, est_blanc)} de {origine}"
    promo_txt = ""
    if move.promotion:
        promo_txt = f" (promotion en {_NOM_PIECE_MAJ[move.promotion].lower()})"

    if piece_capturee is not None:
        variation = _VALEURS.get(piece_capturee.piece_type, 0)
        solde_net = _solde_net_apres_capture(board_apres, move.to_square, variation)
        nom_capturee = _nom_piece_capturee(piece_capturee.piece_type)
        recapture_move = _premier_coup_vers(board_apres, move.to_square)
        if recapture_move is not None and solde_net is not None:
            piece_defenseur = board_apres.piece_at(recapture_move.from_square)
            nom_defenseur = (
                f"{_NOM_PIECE[piece_defenseur.piece_type]} "
                f"{_couleur_accordee(piece_defenseur.piece_type, piece_defenseur.color)} de "
                f"{chess.square_name(recapture_move.from_square)}"
                if piece_defenseur else "une pièce"
            )
            defense_txt = (
                f" — était défendu(e) par {nom_defenseur} : reprise possible, solde net "
                f"{solde_net:+d} points pour {label_adv}"
            )
        else:
            defense_txt = f" — {variation} point(s) gagné(s) net, aucune reprise possible pour {label_adv}"
        segs = [
            f"{label_camp} : {piece_txt}{promo_txt} capture {nom_capturee} de {label_adv} en "
            f"{arrivee}{defense_txt}"
        ]
    else:
        segs = [f"{label_camp} : {piece_txt} joue en {arrivee}{promo_txt}"]

    if board_apres.is_checkmate():
        segs.append("échec et mat")
    elif board_apres.is_check():
        segs.append("échec")

    attaques = _pieces_attaquees_apres(board_apres, move.to_square)
    if attaques:
        segs.append(f"attaque désormais {', '.join(attaques)}")

    return " ; ".join(segs)


def _parse_coup(board: "chess.Board", coup) -> "chess.Move | None":
    """Résout `coup` (SAN ou UCI, ou déjà un chess.Move) en un chess.Move
    légal sur `board`, ou None si illisible ou illégal — jamais une
    exception qui remonterait à l'appelant."""
    if isinstance(coup, chess.Move):
        return coup if coup in board.legal_moves else None
    coup_str = (coup or "").strip()
    if not coup_str:
        return None
    try:
        move = board.parse_san(coup_str)
    except ValueError:
        try:
            move = chess.Move.from_uci(coup_str)
        except Exception:
            return None
    return move if move in board.legal_moves else None


def describe_move_mechanically(fen_avant: str, coup, camp_alain: str = "") -> str | None:
    """API publique (issue #66, point 1) : décrit mécaniquement UN coup
    (SAN ou UCI) légal sur la position `fen_avant` — cf. _decrit_coup_mecanique
    pour le détail. Retourne None si fen_avant/coup sont vides, illisibles,
    ou si le coup n'est pas légal sur cette position (jamais une
    supposition)."""
    fen_avant = (fen_avant or "").strip()
    if not fen_avant or not coup:
        return None
    try:
        board = chess.Board(fen_avant)
        move = _parse_coup(board, coup)
        if move is None:
            return None
        return _decrit_coup_mecanique(board, move, camp_alain)
    except Exception as e:
        logger.warning(f"[GAME_FACTS] describe_move_mechanically a échoué : {e}")
        return None


def describe_pv_mechanically(fen_avant: str, pv_text: str, camp_alain: str = "",
                              max_plies: int = 2) -> list[str]:
    """API publique (issue #66, point 1) : décrit mécaniquement, coup par
    coup, les `max_plies` premiers plis d'une ligne principale (PV) déjà
    citée dans le bloc de faits (SAN, coups séparés par des espaces, depuis
    la position `fen_avant`) — même calcul que describe_move_mechanically,
    rejoué séquentiellement. Retourne une liste vide si fen_avant/pv_text
    sont vides ou illisibles, ou dès le premier coup illégal rencontré
    (liste tronquée, jamais une supposition sur la suite)."""
    fen_avant = (fen_avant or "").strip()
    pv_text = (pv_text or "").strip()
    if not fen_avant or not pv_text:
        return []
    try:
        board = chess.Board(fen_avant)
        descriptions = []
        for san in pv_text.split()[:max_plies]:
            move = _parse_coup(board, san)
            if move is None:
                break
            descriptions.append(_decrit_coup_mecanique(board, move, camp_alain))
            board.push(move)
        return descriptions
    except Exception as e:
        logger.warning(f"[GAME_FACTS] describe_pv_mechanically a échoué : {e}")
        return []

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


def _variation_materielle(w_avant: int, b_avant: int, w_apres: int, b_apres: int) -> int:
    """Variation matérielle (signée) du demi-coup qui vient de mener de
    (w_avant, b_avant) à (w_apres, b_apres) — le camp dont le total a le plus
    bougé (en général le seul des deux qui bouge, sauf promotion). Factorisé
    (issue #57) pour rester identique entre le texte des moments clés
    (build_game_facts_text) et le ciblage Stockfish
    (find_stockfish_check_targets), qui doivent s'accorder sur les mêmes
    demi-coups."""
    delta_w = w_apres - w_avant
    delta_b = b_apres - b_avant
    return delta_b if abs(delta_b) >= abs(delta_w) else delta_w


def _solde_net_apres_capture(board_apres: "chess.Board", case_arrivee: int, variation: int) -> int | None:
    """Solde net (signé, du point de vue du camp qui vient de perdre la pièce
    capturée par ce demi-coup) si ce camp reprend immédiatement sur la case
    de la capture (issue #57, constat réel : 16...Rxb3 avec Bxb3/Nxb3/axb3
    possibles ramène le solde de -9 à -4, pas les -9 retenus à tort par le
    coach). Reprise possible = calculée via les coups légaux réels sur
    board_apres (échec, clouage, obstruction... déjà pris en compte par
    python-chess), jamais supposée. Ne regarde qu'UNE reprise immédiate (pas
    de recherche tactique plus profonde) : reste un calcul mécanique, pas une
    évaluation Stockfish. Retourne None si aucune reprise n'est légale sur
    cette case — dans ce cas, la variation brute est le résultat final.

    Négatif = perte nette malgré la reprise ; positif = le camp qui a
    capturé en premier ressort finalement perdant de l'échange."""
    if not any(m.to_square == case_arrivee for m in board_apres.legal_moves):
        return None
    piece_recapturable = board_apres.piece_at(case_arrivee)
    valeur_recapturable = _VALEURS.get(piece_recapturable.piece_type, 0) if piece_recapturable else 0
    return valeur_recapturable - variation


def _decrit_moment_cle(numero: str, san: str, est_blanc_qui_joue: bool, camp_alain: str,
                        piece_capturee, case_arrivee: int, board_apres: "chess.Board",
                        variation: int) -> str:
    label_capturant = camp_label(est_blanc_qui_joue, camp_alain)
    label_perdant   = camp_label(not est_blanc_qui_joue, camp_alain)
    case_txt = chess.square_name(case_arrivee)
    if piece_capturee is not None:
        nom_piece = _NOM_PIECE.get(piece_capturee.piece_type, "une pièce")
        # nom_piece porte déjà son article ("la dame", "le cavalier"...).
        solde_net = _solde_net_apres_capture(board_apres, case_arrivee, variation)
        if solde_net is not None:
            # Reprise possible (issue #57, point 1) : le solde net après
            # cette reprise est le résultat réel de l'échange, PAS la
            # variation brute ci-dessous — dit explicitement pour éviter que
            # le coach ne retienne le chiffre brut comme perte sèche
            # (incident source : 9 points retenus au lieu du solde net de 4).
            piece_recapturante = board_apres.piece_at(case_arrivee)
            nom_recapturante = (
                _NOM_PIECE.get(piece_recapturante.piece_type, "la pièce qui vient de capturer")
                if piece_recapturante else "la pièce qui vient de capturer"
            )
            reprise_txt = (
                f"reprise de {nom_recapturante} possible par {label_perdant} : solde net "
                f"de {solde_net:+d} points pour {label_perdant} après cette reprise — c'est "
                f"CE solde net qui est le résultat réel de l'échange, pas la seule variation "
                f"brute ci-dessous"
            )
        else:
            reprise_txt = (
                f"aucune reprise possible pour {label_perdant} : la variation brute "
                f"ci-dessous est donc bien le résultat final de cet échange"
            )
        return (
            f"Coup {numero} {san} : {label_capturant} capture {nom_piece} de "
            f"{label_perdant} en {case_txt} ({reprise_txt}) ; variation matérielle brute "
            f"(avant reprise éventuelle) de {variation} points."
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


def describe_reponse_suivante(fen_avant: str, san_coup: str, uci_reponse, camp_alain: str) -> str | None:
    """Calcule mécaniquement (python-chess, jamais Stockfish, issue #62) la
    réponse réellement jouée ensuite dans la partie après un coup flagué, et
    sa conséquence matérielle immédiate si elle en a une — pour que
    l'explication d'un coup flagué (get_move_explanations/get_coach_response,
    llm_coach.py) reçoive la réfutation réelle de la partie plutôt que de
    devoir la deviner (constat réel : l'explication de 8.Qf4?? disait
    seulement que "le roque était préférable pour la sécurité du roi", sans
    jamais mentionner que 8...Nxf4 capture la dame sans reprise possible).

    fen_avant : position AVANT le coup flagué. san_coup : ce coup flagué, en
    notation SAN. uci_reponse : le coup suivant réellement joué dans la
    partie, en UCI (transmis par l'appelant depuis le rapport mécanique
    complet de la partie, PAS recalculé ici) — falsy si le coup flagué est
    le dernier de la partie.

    Retourne None si uci_reponse est absent, si san_coup/uci_reponse ne sont
    pas légaux sur les positions attendues, ou si cette réponse n'est pas
    une capture (pas de conséquence matérielle immédiate à signaler ici, les
    menaces positionnelles restent à l'appréciation du coach) — jamais une
    supposition."""
    fen_avant = (fen_avant or "").strip()
    san_coup = (san_coup or "").strip()
    if not fen_avant or not san_coup or not uci_reponse:
        return None
    try:
        board = chess.Board(fen_avant)
        coup = board.parse_san(san_coup)
        board.push(coup)
        move_reponse = chess.Move.from_uci(uci_reponse)
        if move_reponse not in board.legal_moves or not board.is_capture(move_reponse):
            return None

        est_blanc_reponse = board.turn == chess.WHITE
        w_avant, b_avant = _materiel(board)
        case_arrivee = move_reponse.to_square
        piece_capturee = board.piece_at(case_arrivee)
        if piece_capturee is None and board.is_en_passant(move_reponse):
            piece_capturee = chess.Piece(chess.PAWN, not est_blanc_reponse)
        if piece_capturee is None:
            return None
        san_reponse = board.san(move_reponse)

        board.push(move_reponse)
        w_apres, b_apres = _materiel(board)
        variation = abs(_variation_materielle(w_avant, b_avant, w_apres, b_apres))
        solde_net = _solde_net_apres_capture(board, case_arrivee, variation)
        nom_piece = _NOM_PIECE.get(piece_capturee.piece_type, "une pièce")
        label_qui_joue = camp_label(est_blanc_reponse, camp_alain)
        label_perdant = camp_label(not est_blanc_reponse, camp_alain)
        if solde_net is not None:
            return (
                f"réponse réellement jouée ensuite dans la partie : {san_reponse} "
                f"({label_qui_joue}) capture {nom_piece} de {label_perdant} ; reprise possible "
                f"ensuite pour {label_perdant}, solde net {solde_net:+d} points pour "
                f"{label_perdant} — pas une perte sèche de {variation} points."
            )
        return (
            f"réponse réellement jouée ensuite dans la partie : {san_reponse} "
            f"({label_qui_joue}) capture {nom_piece} de {label_perdant}, perte nette de "
            f"{variation} points pour {label_perdant}, aucune reprise possible."
        )
    except Exception as e:
        logger.warning(f"[GAME_FACTS] describe_reponse_suivante a échoué : {e}")
        return None


def find_stockfish_check_targets(pgn_text: str, camp_alain: str) -> list:
    """Identifie, SANS appeler Stockfish (ce module n'en fait jamais l'appel
    direct, voir en-tête), les positions à vérifier par Stockfish pour
    jusqu'à DEUX moments de la partie (issue #62) :
      - "plus_grave" : le moment où Alain subit la plus grande perte nette
        (après reprise mécanique éventuelle, cf. _solde_net_apres_capture),
        ou un mat (toujours considéré comme le plus grave possible, quelle
        que soit la perte matérielle) — le vrai tournant pédagogique, même
        s'il survient après un premier accroc moins grave ;
      - "premier_significatif" : le premier moment de la partie où Alain
        perd déjà au moins _SEUIL_MOMENT_CLE points nets ou se fait mater —
        la cause racine la plus précoce, utile même quand elle n'est pas la
        plus grave. Omis du résultat s'il coïncide avec le moment le plus
        grave (rien à dédupliquer dans ce cas).
    Seuls les moments qui franchissent déjà _SEUIL_MOMENT_CLE (ou un mat)
    sont candidats aux deux labels : "plus_grave" n'est jamais un accroc
    mineur resté sous le seuil.

    Pour chaque moment retenu, les deux derniers coups d'Alain qui le
    précèdent (celui qui l'a permis, et celui d'avant) — jamais le coup du
    moment lui-même, qui est nécessairement celui de l'adversaire (une perte
    de matériel pour Alain ou un mat contre lui ne peut être infligé que par
    un coup adverse). Le moment le plus grave est toujours listé en premier
    (pour que l'appelant le vérifie en priorité si son budget de temps est
    dépassé avant la fin, cf. app.py _stockfish_check_key_moment) ; les
    positions déjà couvertes par le moment le plus grave ne sont jamais
    répétées pour le premier moment significatif.

    Retourne une liste d'au plus 4 éléments (2 par moment, avant
    déduplication) : {"fen_avant": str, "san": str, "numero": str,
    "coup_plein": int, "camp": "blancs"/"noirs", "moment":
    "plus_grave"/"premier_significatif", "uci_reponse_suivante": str | None}
    — fen_avant est la position AVANT ce coup d'Alain, à transmettre telle
    quelle à Stockfish par l'appelant (app.py, qui détient engine_manager).
    uci_reponse_suivante (issue #66, point 1) est le coup réellement joué
    ensuite dans la partie (nécessairement celui de l'adversaire, puisque
    ce coup-ci est celui d'Alain), en UCI, ou None si ce coup est le
    dernier de la partie — permet à l'appelant de décrire mécaniquement
    cette réponse réelle sans avoir à rejouer tout le PGN une seconde fois.

    Repli silencieux ([]) si le PGN est illisible, camp_alain n'est pas
    connu, ou aucun moment de cette gravité n'est trouvé dans la partie."""
    pgn_text = (pgn_text or "").strip()
    if not pgn_text or camp_alain not in ("blancs", "noirs"):
        return []

    try:
        game = chess.pgn.read_game(io.StringIO(pgn_text))
        if game is None:
            return []
        board = game.board()
    except Exception as e:
        logger.warning(f"[GAME_FACTS] find_stockfish_check_targets : PGN illisible : {e}")
        return []

    est_blanc_alain = camp_alain == "blancs"
    historique = []
    w_avant, b_avant = _materiel(board)
    premier_index = None
    plus_grave_index = None
    plus_grave_perte = None

    try:
        for i, move in enumerate(game.mainline_moves()):
            est_blanc = board.turn == chess.WHITE
            numero = _numero_coup(board, est_blanc)
            coup_plein = board.fullmove_number
            fen_avant = board.fen()
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
            historique.append({
                "numero": numero, "san": san, "est_blanc": est_blanc, "fen_avant": fen_avant,
                "coup_plein": coup_plein, "idx": i, "uci": move.uci(),
            })
            w_apres, b_apres = _materiel(board)

            if est_blanc != est_blanc_alain:
                # Le coup qui inflige la perte/le mat est nécessairement
                # celui de l'adversaire (est_blanc != est_blanc_alain) : un
                # coup d'Alain lui-même ne peut pas le faire perdre du
                # matériel net ni le mater à son propre trait.
                perte = None
                if board.is_checkmate():
                    perte = float("inf")
                elif piece_capturee is not None:
                    variation = abs(_variation_materielle(w_avant, b_avant, w_apres, b_apres))
                    solde_net = _solde_net_apres_capture(board, case_arrivee, variation)
                    perte = -solde_net if solde_net is not None else variation
                if perte is not None and perte >= _SEUIL_MOMENT_CLE:
                    if premier_index is None:
                        premier_index = i
                    if plus_grave_perte is None or perte > plus_grave_perte:
                        plus_grave_perte = perte
                        plus_grave_index = i

            w_avant, b_avant = w_apres, b_apres
    except Exception as e:
        logger.warning(f"[GAME_FACTS] find_stockfish_check_targets : rejeu interrompu : {e}")
        return []

    if plus_grave_index is None:
        return []

    def _cibles_pour(moment_index: int, label: str) -> list:
        coups_alain = [h for h in historique[:moment_index + 1] if h["est_blanc"] == est_blanc_alain]
        resultats = []
        for c in coups_alain[-2:]:
            suivant = historique[c["idx"] + 1] if c["idx"] + 1 < len(historique) else None
            resultats.append({
                "fen_avant": c["fen_avant"], "san": c["san"], "numero": c["numero"],
                "coup_plein": c["coup_plein"], "camp": camp_alain, "moment": label,
                "uci_reponse_suivante": suivant["uci"] if suivant else None,
            })
        return resultats

    resultats = _cibles_pour(plus_grave_index, "plus_grave")
    if premier_index is not None and premier_index != plus_grave_index:
        deja_vues = {c["fen_avant"] for c in resultats}
        for c in _cibles_pour(premier_index, "premier_significatif"):
            if c["fen_avant"] not in deja_vues:
                resultats.append(c)
                deja_vues.add(c["fen_avant"])

    return resultats


def build_game_facts_text(pgn_text: str, camp_alain: str, flagged_moves: list | None = None,
                           stockfish_check: list | None = None) -> str:
    """Construit le bloc de faits calculés (issue #55) :
      1. coups numérotés, camp explicite de chacun, bilan matériel après
         chaque coup (point de vue d'Alain, points classiques) ;
      2. moments clés (variation matérielle d'au moins 2 points, qui capture
         quoi, reprise possible et solde net après reprise le cas échéant,
         issue #57) et, en dernier, la fin de partie (mat/pat/nulle par la
         règle/abandon) si la partie est terminée — ajoutée même sans aucune
         variation matérielle (issue #56 point 4) ;
      2bis. pions perdus sans reprise (variation d'exactement 1 point, sous
         le seuil des moments clés), les 3 plus récents de la partie (issue
         #66, point 4) ;
      3. position actuelle : pièces par camp avec cases exactes, FEN,
         matériel restant, mention explicite si un camp n'a plus de dame ;
      4. si fourni, les coups flagués par une analyse mécanique Stockfish
         déjà effectuée cette session (bouton "Analyser cette partie") ;
      5. si fourni (issue #57/#62), la vérification Stockfish ciblée sur les
         deux coups d'Alain qui précèdent chacun des deux moments (le plus
         grave, et le premier significatif s'il est différent) désignés par
         find_stockfish_check_targets — calculée par l'appelant (app.py),
         jamais par ce module. Chaque coup cité (coup joué, meilleur coup,
         réponse réellement jouée ensuite, premier pli après le meilleur
         coup si la ligne principale en compte plus d'un) est décrit
         mécaniquement (describe_move_mechanically/describe_pv_mechanically,
         issue #66 point 1), et la position juste avant le coup joué est
         listée pièce par pièce (issue #66 point 2).

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
    pions_perdus_sans_reprise = []
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

            variation = _variation_materielle(w_avant, b_avant, w_apres, b_apres)
            if abs(variation) >= _SEUIL_MOMENT_CLE:
                moments_cles.append(_decrit_moment_cle(
                    numero, san, est_blanc, camp_alain, piece_capturee, case_arrivee,
                    board, abs(variation),
                ))
            elif (piece_capturee is not None and piece_capturee.piece_type == chess.PAWN
                    and abs(variation) == 1
                    and _solde_net_apres_capture(board, case_arrivee, abs(variation)) is None):
                # Pion perdu sans reprise (issue #66, point 4) : reste sous
                # le seuil des "moments clés" (2 points) mais mérite d'être
                # signalé séparément — sans quoi 6.Nxe5 (pion e5 laissé sans
                # défense par 5...Nb6, cf. partie de test) reste invisible au
                # coach. Ne garde que les _MAX_PIONS_PERDUS_SANS_REPRISE plus
                # récents ci-dessous, pas la liste entière de la partie.
                pions_perdus_sans_reprise.append(_decrit_moment_cle(
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

    if pions_perdus_sans_reprise:
        parties.append(
            "Pions perdus sans reprise (variation d'exactement 1 point, distincts des "
            f"moments clés ci-dessus qui restent sous leur seuil de {_SEUIL_MOMENT_CLE} "
            f"points ; {_MAX_PIONS_PERDUS_SANS_REPRISE} plus récents de la partie au plus) "
            ":\n" + "\n".join(pions_perdus_sans_reprise[-_MAX_PIONS_PERDUS_SANS_REPRISE:])
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

    if stockfish_check:
        par_moment = {"plus_grave": [], "premier_significatif": []}
        for c in stockfish_check:
            if not isinstance(c, dict):
                continue
            numero    = c.get("numero")
            san       = (c.get("san") or "").strip()
            camp      = (c.get("camp") or "").strip()
            moment    = (c.get("moment") or "").strip()
            fen_avant = (c.get("fen_avant") or "").strip()
            if not san or numero is None or moment not in par_moment:
                continue
            camp_txt = camp_label(camp == "blancs", camp_alain) if camp in ("blancs", "noirs") else ""

            # Position juste avant ce coup, pièce par pièce (issue #66,
            # point 2) — même présentation que la position actuelle, pour
            # que le coach n'ait pas à deviner où se trouvent les pièces à
            # ce moment de la partie.
            lignes_cible = [f"Coup {numero} {san}{(' (' + camp_txt + ')') if camp_txt else ''} :"]
            if fen_avant:
                try:
                    board_position_avant = chess.Board(fen_avant)
                    lignes_cible.append(
                        "  Position juste avant ce coup — "
                        f"{camp_label(True, camp_alain)} : {_liste_pieces(board_position_avant, True)} ; "
                        f"{camp_label(False, camp_alain)} : {_liste_pieces(board_position_avant, False)}"
                    )
                except Exception:
                    pass

            # Description mécanique de chaque coup cité (issue #66, point 1)
            # — jamais laissée à la charge du modèle, qui reconstituait de
            # tête quelle pièce joue et se trompait (cavalier b6 au lieu de
            # f6, fou capturant un cavalier au lieu d'un pion...).
            desc_joue = describe_move_mechanically(fen_avant, san, camp_alain)
            lignes_cible.append(
                f"  Coup joué {san} : {desc_joue}" if desc_joue else f"  coup joué {san}"
            )

            meilleur_coup = (c.get("meilleur_coup") or "").strip()
            if meilleur_coup:
                desc_meilleur = describe_move_mechanically(fen_avant, meilleur_coup, camp_alain)
                lignes_cible.append(
                    f"  Meilleur coup selon Stockfish {meilleur_coup} : {desc_meilleur}"
                    if desc_meilleur else f"  meilleur coup selon Stockfish {meilleur_coup}"
                )

            perte_cp = c.get("perte_cp")
            if isinstance(perte_cp, (int, float)):
                lignes_cible.append(f"  Perte estimée {perte_cp} centipawns")

            ligne_principale = (c.get("ligne_principale") or "").strip()
            if ligne_principale:
                lignes_cible.append(f"  Ligne principale {ligne_principale}")
                # Premiers coups de la ligne principale (issue #66, point 1)
                # : le premier pli est déjà décrit ci-dessus (meilleur_coup
                # en est le premier coup) — on décrit ici en plus la réponse
                # anticipée par cette ligne (2e pli), s'il y en a une.
                suite_pv = describe_pv_mechanically(fen_avant, ligne_principale, camp_alain, max_plies=2)
                tokens_pv = ligne_principale.split()
                if len(suite_pv) >= 2 and len(tokens_pv) >= 2:
                    lignes_cible.append(
                        f"  Réponse anticipée par la ligne principale {tokens_pv[1]} : {suite_pv[1]}"
                    )

            # Réponse réellement jouée ensuite dans la partie (issue #66,
            # point 1) — coup suivant réel du PGN, PAS une hypothèse.
            uci_reponse_suivante = (c.get("uci_reponse_suivante") or "").strip()
            if uci_reponse_suivante and fen_avant:
                try:
                    board_reponse = chess.Board(fen_avant)
                    board_reponse.push(board_reponse.parse_san(san))
                    move_reponse = chess.Move.from_uci(uci_reponse_suivante)
                    san_reponse = board_reponse.san(move_reponse)
                    desc_reponse = describe_move_mechanically(
                        board_reponse.fen(), move_reponse, camp_alain,
                    )
                    if desc_reponse:
                        lignes_cible.append(
                            f"  Réponse jouée ensuite dans la partie {san_reponse} : {desc_reponse}"
                        )
                except Exception as e:
                    logger.warning(f"[GAME_FACTS] Description de la réponse suivante échouée : {e}")

            par_moment[moment].append("\n".join(lignes_cible))

        blocs = []
        if par_moment["plus_grave"]:
            blocs.append(
                "Moment le plus grave (perte nette la plus importante subie par Alain, ou mat "
                "subi, dans toute cette partie — LE tournant si Alain demande lequel) :\n"
                + "\n\n".join(par_moment["plus_grave"])
            )
        if par_moment["premier_significatif"]:
            blocs.append(
                "Premier moment significatif (le premier de la partie où Alain a perdu au "
                f"moins {_SEUIL_MOMENT_CLE} points nets ou s'est fait mater — distinct du "
                "moment le plus grave ci-dessus, pas un second tournant) :\n"
                + "\n\n".join(par_moment["premier_significatif"])
            )
        if blocs:
            parties.append(
                "Vérification Stockfish ciblée (issue #62), calcul court et borné, sur les "
                "deux derniers coups d'Alain qui précèdent chacun des moments ci-dessous — "
                "absente si Stockfish était indisponible ou trop lent au moment du calcul, "
                "sans que cela soit une erreur. Chaque coup cité (coup joué, meilleur coup, "
                "réponse jouée ensuite, réponse anticipée par la ligne principale) est suivi "
                "d'une description mécanique calculée (issue #66) : ne complète ni ne "
                "corrige jamais cette description, elle est déjà exacte :\n\n" + "\n\n".join(blocs)
            )

    return "\n\n".join(parties)
