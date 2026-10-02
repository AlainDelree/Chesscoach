"""
coach_reliability.py — ChessCoach (issue #87)

Contrôles déterministes, avec python-chess (aucun appel au LLM, aucun appel
Stockfish), exécutés APRÈS la réponse du coach pour repérer des incohérences
factuelles évidentes dans son texte — en complément des garde-fous de prompt
(llm_coach.py), jamais à leur place. Constat ayant motivé ce module (cas réel,
journal du coach du 2026-10-02) : les données transmises au coach étaient
exactes (listes de pièces, descriptions mécaniques des coups), mais sa
réponse a quand même parlé d'un "échange tour contre tour" dans une position
où un seul camp avait une tour, et affirmé qu'une tour était attaquée par un
fou qui ne l'attaquait géométriquement pas. Un garde-fou de prompt ne peut
pas, à lui seul, garantir qu'un LLM ne répète jamais ce genre d'invention :
ce module ajoute donc une vérification déterministe, APRÈS COUP, sur le texte
réellement produit.

Limites assumées (volontairement documentées, cf. evaluer_fiabilite) :
  - la détection de mentions de pièces repose sur des expressions régulières
    sur le texte en français, pas sur une compréhension du langage — une
    tournure inhabituelle peut échapper à la détection (faux négatif), ou une
    couleur mentionnée par hasard à proximité d'un type de pièce sans lien
    réel peut déclencher une fausse alerte (faux positif) ;
  - le contrôle "case/pièce" et le contrôle "coup cité" ne connaissent que
    la position de départ et la position actuelle transmises par l'appelant
    (pas chaque position intermédiaire d'une ligne hypothétique citée en
    prose) : un coup ou une case cités dans une ligne hypothétique profonde
    peuvent donc être signalés à tort (faux positif), ou une vraie erreur sur
    une position intermédiaire peut ne pas être détectée (faux négatif) ;
  - ces contrôles ne vérifient JAMAIS la justesse stratégique ou tactique de
    l'explication, seulement des faits bruts (existence d'un type de pièce,
    contenu d'une case, légalité d'un coup) : une réponse peut rester fausse
    sur le fond sans déclencher la moindre alerte.
"""

import logging
import re

import chess

logger = logging.getLogger("chesscoach.coach_reliability")

_NOM_PIECE_TYPE = {
    "dame": chess.QUEEN, "dames": chess.QUEEN,
    "tour": chess.ROOK, "tours": chess.ROOK,
    "fou": chess.BISHOP, "fous": chess.BISHOP,
    "cavalier": chess.KNIGHT, "cavaliers": chess.KNIGHT,
    "pion": chess.PAWN, "pions": chess.PAWN,
    "roi": chess.KING, "rois": chess.KING,
}

_NOM_PIECE_AFFICHAGE = {
    chess.QUEEN: "dame", chess.ROOK: "tour", chess.BISHOP: "fou",
    chess.KNIGHT: "cavalier", chess.PAWN: "pion", chess.KING: "roi",
}

# Les 5 types de pièces pouvant être totalement absents d'un camp (le roi est
# toujours présent des deux côtés dans une position légale — jamais à
# signaler comme "absent").
_TYPES_SURVEILLES = (chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT, chess.PAWN)

_NOMBRES_FR = {
    "un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4,
    "cinq": 5, "six": 6, "sept": 7, "huit": 8,
}

# Coup en notation SAN standard (issue #87, point 5 — "coup cité illégal") :
# roque, ou [pièce]?[case départ partielle]?x?case arrivée[=promotion]?[+#]?.
# Volontairement strict (ancré \b des deux côtés) pour limiter les faux
# positifs sur un mot qui ressemblerait par hasard à un coup.
_SAN_RE = re.compile(
    r"\b(O-O-O|O-O|[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?)\b"
)
# Case seule (ex. "e5"), pas un coup — exclue des candidats "coup cité" pour
# ne pas confondre une simple mention de case avec un coup joué.
_CASE_SEULE_RE = re.compile(r"^[a-h][1-8]$")


def _couleur_depuis_mot(mot: str):
    m = mot.lower()
    if m.startswith("blanc"):
        return chess.WHITE
    if m.startswith("noir"):
        return chess.BLACK
    return None


# Association piece+couleur STRICTEMENT ADJACENTE (issue #87, correctif après
# test réel) : une première version associait la couleur la plus proche dans
# toute la même clause, ce qui a produit un faux positif concret — "le fou
# s'echappe et la tour blanche n'est pas attaquee" associait à tort "blanche"
# (qui qualifie "tour", 5 mots plus loin) à "fou", qui n'a pourtant aucune
# couleur dans cette clause. Seule une couleur directement accolée au nom de
# la pièce (adjectif juste après, ou "des Blancs"/"des Noirs" juste après) est
# retenue — au prix de quelques faux négatifs (couleur exprimée plus loin
# dans la phrase), largement préférable à un faux positif.
_PIECE_COULEUR_ADJ_RE = re.compile(
    r"\b(dames?|tours?|fous?|cavaliers?|pions?)\s+(blancs?|blanches?|noirs?|noires?)\b",
    re.IGNORECASE,
)
_PIECE_CAMP_ADJ_RE = re.compile(
    r"\b(dames?|tours?|fous?|cavaliers?|pions?)\s+(?:des|du)\s+(blancs?|noirs?)\b",
    re.IGNORECASE,
)


def detecter_types_pieces_absents(texte: str, board: "chess.Board") -> list:
    """Détecte une mention d'un type de pièce DIRECTEMENT accolée à une
    couleur ("tour blanche", "fou des Noirs"...) pour un camp qui n'en a
    AUCUNE dans `board` (issue #87, point 4, exemple de l'issue : "tour"
    pour un camp qui n'en a plus). Retourne une liste de dicts
    {"type": "piece_absente", "detail": str}."""
    alertes = []
    for regex in (_PIECE_COULEUR_ADJ_RE, _PIECE_CAMP_ADJ_RE):
        for m in regex.finditer(texte):
            piece_type = _NOM_PIECE_TYPE[m.group(1).lower()]
            if piece_type not in _TYPES_SURVEILLES:
                continue
            couleur = _couleur_depuis_mot(m.group(2))
            if couleur is None:
                continue
            if len(board.pieces(piece_type, couleur)) == 0:
                camp_txt = "Blancs" if couleur == chess.WHITE else "Noirs"
                nom = _NOM_PIECE_AFFICHAGE[piece_type]
                alertes.append({
                    "type": "piece_absente",
                    "detail": (
                        f"mention de \"{m.group(0).strip()}\" ({camp_txt}), alors "
                        f"que ce camp n'a aucun(e) {nom} dans la position"
                    ),
                })
    return alertes


_NOMBRE_PIECE_COULEUR_RE = re.compile(
    r"\b(un|une|deux|trois|quatre|cinq|six|sept|huit)\s+"
    r"(dames?|tours?|fous?|cavaliers?|pions?)\s+"
    r"(blancs?|blanches?|noirs?|noires?)\b",
    re.IGNORECASE,
)


def detecter_nombre_pieces_excessif(texte: str, board: "chess.Board") -> list:
    """Détecte une mention \"deux tours blanches\"/\"trois pions noirs\"...
    dont le nombre réel de pièces de ce type, pour ce camp, est STRICTEMENT
    inférieur au nombre cité (issue #87, point 4 — "plus de pièces citées "
    "qu'il n'y en a"). Même exigence d'adjacence stricte que
    detecter_types_pieces_absents (cf. ci-dessus)."""
    alertes = []
    for m in _NOMBRE_PIECE_COULEUR_RE.finditer(texte):
        nombre = _NOMBRES_FR[m.group(1).lower()]
        piece_type = _NOM_PIECE_TYPE[m.group(2).lower()]
        if piece_type not in _TYPES_SURVEILLES:
            continue
        couleur = _couleur_depuis_mot(m.group(3))
        if couleur is None:
            continue
        reel = len(board.pieces(piece_type, couleur))
        if nombre > reel:
            camp_txt = "Blancs" if couleur == chess.WHITE else "Noirs"
            nom = _NOM_PIECE_AFFICHAGE[piece_type]
            alertes.append({
                "type": "nombre_excessif",
                "detail": (
                    f"mention de \"{m.group(0).strip()}\" ({camp_txt}), alors "
                    f"que ce camp n'a que {reel} {nom}(s) dans la position"
                ),
            })
    return alertes


_ECHANGE_RE = re.compile(
    r"\b(dames?|tours?|fous?|cavaliers?|pions?)\s+contre\s+"
    r"(?:un\s+|une\s+)?(dames?|tours?|fous?|cavaliers?|pions?)\b",
    re.IGNORECASE,
)


def _echange_possible(type1: int, type2: int, board: "chess.Board") -> bool:
    w1, n1 = len(board.pieces(type1, chess.WHITE)) > 0, len(board.pieces(type1, chess.BLACK)) > 0
    w2, n2 = len(board.pieces(type2, chess.WHITE)) > 0, len(board.pieces(type2, chess.BLACK)) > 0
    return (w1 and n2) or (n1 and w2)


def detecter_echange_impossible(texte: str, board: "chess.Board") -> list:
    """Détecte une mention \"<type> contre <type>\" (issue #87, exemple réel :
    "échange tour contre tour", "échange tour contre cavalier") matériellement
    IMPOSSIBLE dans `board` — un échange entre les deux camps suppose qu'un
    camp a le premier type et l'autre le second (dans un sens ou dans
    l'autre) ; sans couleur à vérifier (contrairement à
    detecter_types_pieces_absents), ce contrôle couvre justement le cas réel
    qui a motivé l'issue #87 : un texte qui ne mentionne jamais explicitement
    quel camp a quelle pièce (\"simple échange tour contre tour\"), alors
    qu'un seul camp avait une tour."""
    alertes = []
    for m in _ECHANGE_RE.finditer(texte):
        t1 = _NOM_PIECE_TYPE[m.group(1).lower()]
        t2 = _NOM_PIECE_TYPE[m.group(2).lower()]
        if t1 not in _TYPES_SURVEILLES or t2 not in _TYPES_SURVEILLES:
            continue
        if not _echange_possible(t1, t2, board):
            alertes.append({
                "type": "echange_impossible",
                "detail": (
                    f"\"{m.group(0).strip()}\" matériellement impossible : au moins "
                    "un des deux camps n'a aucune pièce du type nécessaire pour "
                    "cet échange dans la position"
                ),
            })
    return alertes


_CASE_PIECE_RE = re.compile(
    r"\b(dames?|tours?|fous?|cavaliers?|pions?|rois?)\b"
    r"(?:\s+(blanche?s?|noire?s?))?"
    r"\s*(?:en|sur)\s+([a-h][1-8])\b",
    re.IGNORECASE,
)


def detecter_case_piece_incoherente(texte: str, boards_reference: list) -> list:
    """Détecte une citation \"<pièce> [<couleur>] en/sur <case>\" (issue #87,
    point 5 — "case citée qui ne contient pas la pièce annoncée") contredite
    par TOUTES les positions de référence disponibles — même tolérance que
    detecter_coups_illegaux : une citation cohérente avec AU MOINS UNE des
    positions de référence n'est jamais signalée, pour limiter les faux
    positifs sur une ligne hypothétique qui ne part d'aucune des deux
    positions connues (cf. limites en en-tête de module). Couleur exigée
    DIRECTEMENT accolée au nom de la pièce dans la citation elle-même
    (jamais devinée ailleurs dans la phrase, cf. detecter_types_pieces_absents
    pour la raison de cette exigence) — une citation sans couleur explicite
    n'est tout simplement pas contrôlée (faux négatif assumé)."""
    if not boards_reference:
        return []
    alertes = []
    for m in _CASE_PIECE_RE.finditer(texte):
        piece_type = _NOM_PIECE_TYPE[m.group(1).lower()]
        couleur = _couleur_depuis_mot(m.group(2)) if m.group(2) else None
        if couleur is None:
            continue
        case = chess.parse_square(m.group(3).lower())
        coherente_quelque_part = any(
            (b.piece_at(case) is not None
             and b.piece_at(case).piece_type == piece_type
             and b.piece_at(case).color == couleur)
            for b in boards_reference
        )
        if not coherente_quelque_part:
            camp_txt = "blanc" if couleur == chess.WHITE else "noir"
            nom = _NOM_PIECE_AFFICHAGE[piece_type]
            alertes.append({
                "type": "case_incoherente",
                "detail": (
                    f"\"{nom} {camp_txt} en {m.group(3)}\" ne correspond à la "
                    "pièce présente sur cette case ni dans la position de "
                    "départ ni dans la position actuelle"
                ),
            })
    return alertes


def _variante_trait_inverse(board: "chess.Board"):
    """Copie de `board` avec le trait inversé (et la case en passant
    effacée, qui n'a plus de sens avec ce trait) — une ligne de coups citée
    en prose alterne forcément les deux camps, alors qu'une position de
    référence isolée n'a qu'un seul trait : sans cette variante, le coup de
    l'ADVERSAIRE qui répond au premier coup de la ligne serait signalé à
    tort comme illégal (aucun coup de ce camp n'est légal tant que c'est
    encore l'autre camp qui a le trait sur `board`). Retourne None si la
    position obtenue est invalide (cas limite)."""
    parts = board.fen().split(" ")
    parts[1] = "b" if parts[1] == "w" else "w"
    parts[3] = "-"
    try:
        return chess.Board(" ".join(parts))
    except Exception:
        return None


def detecter_coups_illegaux(texte: str, boards_reference: list) -> list:
    """Détecte un coup cité (notation SAN) illégal sur TOUTES les positions
    de référence fournies, trait inversé compris (issue #87, point 5) —
    typiquement la position de départ et la position actuelle de l'exercice.
    Volontairement tolérant : un coup légal sur AU MOINS UNE des positions
    de référence (dans un camp comme dans l'autre) n'est jamais signalé
    (une ligne hypothétique citée en prose peut tout à fait partir d'une
    position différente de ces deux-là, cf. limites en en-tête de module).
    Retourne une liste de dicts {"type": "coup_illegal", "detail": str}."""
    if not boards_reference:
        return []
    boards_essai = list(boards_reference)
    for b in boards_reference:
        variante = _variante_trait_inverse(b)
        if variante is not None:
            boards_essai.append(variante)
    alertes = []
    deja_vus = set()
    for m in _SAN_RE.finditer(texte):
        candidat = m.group(1)
        if candidat in deja_vus or _CASE_SEULE_RE.match(candidat):
            continue
        deja_vus.add(candidat)
        legal_quelque_part = False
        for board in boards_essai:
            try:
                board.parse_san(candidat)
                legal_quelque_part = True
                break
            except Exception:
                continue
        if not legal_quelque_part:
            alertes.append({
                "type": "coup_illegal",
                "detail": (
                    f"coup cité \"{candidat}\" illégal sur la position de "
                    "départ comme sur la position actuelle de l'exercice, "
                    "trait inversé compris"
                ),
            })
    return alertes


def evaluer_fiabilite(texte: str, fen_reference: str = "", fen_reference2: str = "",
                       analyse_indisponible: bool = False, verdict_partiel: bool = False) -> dict:
    """Fonction principale (issue #87, point 5) : exécute les contrôles
    déterministes disponibles sur `texte` et retourne un verdict de fiabilité
    prêt à afficher ("couleur" vert/orange/rouge) et à journaliser. Ne sait
    rien d'une éventuelle relance automatique (point 4) : c'est à l'appelant
    (llm_coach.get_coach_response, qui orchestre la relance) d'ajuster
    couleur/raison après coup selon qu'elle a eu lieu et a corrigé ou non —
    cette fonction se contente d'évaluer LE TEXTE qu'on lui donne.

    fen_reference / fen_reference2 : position(s) connues pour cette réponse
    (typiquement position de départ et position actuelle de l'exercice, ou
    simplement l'une des deux hors exercice) — "" si non disponible(s) :
    les contrôles qui en dépendent sont alors simplement absents du rapport,
    jamais remplacés par une supposition.
    analyse_indisponible / verdict_partiel : contexte transmis par
    l'appelant — motifs "orange" indépendants du texte lui-même (analyse
    moteur partielle ou indisponible).

    Retourne {"couleur": "vert"|"orange"|"rouge", "raison": str (une seule
    phrase, affichable à Alain), "controles": [liste des contrôles exécutés
    avec leurs limites, pour le rapport], "alertes": [liste des alertes
    détectées par les contrôles déterministes sur CE texte]}."""
    controles = [
        "existence du type de pièce cité pour le camp associé (regex "
        "français + python-chess ; limite : seule une couleur DIRECTEMENT "
        "accolée au nom de la pièce est prise en compte, ex. \"tour "
        "blanche\" ou \"fou des Noirs\" — une couleur exprimée plus loin "
        "dans la phrase n'est jamais associée à tort, mais une telle "
        "mention peut donc passer inaperçue, cf. coach_reliability.py)",
        "nombre de pièces d'un type cité pour un camp (même limite)",
        "possibilité matérielle d'un échange \"type contre type\" cité (ex. "
        "\"tour contre tour\") — détecte le cas sans même associer de couleur "
        "(limite : ne couvre que la forme \"X contre Y\", pas toute tournure "
        "équivalente)",
        "présence de la pièce annoncée sur la case citée (\"en\"/\"sur\" telle "
        "case), comparée à la position de départ et à la position actuelle "
        "(limite : une case d'une ligne hypothétique peut être signalée à "
        "tort, ou une vraie erreur sur une position intermédiaire peut "
        "passer inaperçue)",
        "légalité des coups cités en notation SAN sur la position de départ "
        "et la position actuelle (limite : un coup d'une ligne hypothétique "
        "profonde peut être signalé à tort, ou passer inaperçu)",
    ]

    boards_reference = []
    board_pieces = None
    for fen in (fen_reference, fen_reference2):
        fen = (fen or "").strip()
        if not fen:
            continue
        try:
            b = chess.Board(fen)
            boards_reference.append(b)
            if board_pieces is None:
                board_pieces = b
        except Exception as e:
            logger.warning(f"[COACH_RELIABILITY] FEN de référence illisible : {e}")

    alertes = []
    texte = texte or ""
    if board_pieces is not None:
        alertes += detecter_types_pieces_absents(texte, board_pieces)
        alertes += detecter_nombre_pieces_excessif(texte, board_pieces)
        alertes += detecter_echange_impossible(texte, board_pieces)
    if boards_reference:
        alertes += detecter_case_piece_incoherente(texte, boards_reference)
        alertes += detecter_coups_illegaux(texte, boards_reference)

    if alertes:
        premiere = alertes[0]["detail"]
        return {
            "couleur": "rouge",
            "raison": f"incohérence détectée par les contrôles automatiques : {premiere}",
            "controles": controles, "alertes": alertes,
        }

    if analyse_indisponible:
        return {
            "couleur": "orange",
            "raison": "analyse Stockfish partielle ou indisponible pour cette réponse",
            "controles": controles, "alertes": [],
        }
    if verdict_partiel:
        return {
            "couleur": "orange",
            "raison": "verdict Stockfish partiel pour cette réponse",
            "controles": controles, "alertes": [],
        }
    return {
        "couleur": "vert",
        "raison": (
            "aucune incohérence détectée par les contrôles automatiques — "
            "cela ne garantit pas que l'explication est juste"
        ),
        "controles": controles, "alertes": [],
    }
