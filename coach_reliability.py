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
  - le contrôle "case/pièce" ne connaît que la position de départ et la
    position actuelle transmises par l'appelant (pas chaque position
    intermédiaire d'une ligne hypothétique citée en prose) : une case citée
    dans une ligne hypothétique profonde peut donc être signalée à tort
    (faux positif), ou une vraie erreur sur une position intermédiaire peut
    ne pas être détectée (faux négatif) ;
  - le contrôle "suite de coups cités" (issue #90) rejoue les coups cités
    À LA SUITE les uns des autres (même phrase/proposition) depuis la
    position de départ, la position actuelle, après le coup proposé/réel/
    meilleur, et chaque position intermédiaire des lignes (PV) fournies au
    coach pour le coup proposé et le meilleur coup — une suite jouable
    depuis AU MOINS UN de ces points de départ n'est jamais signalée. Une
    ligne hypothétique qui ne part d'AUCUN de ces points reste cependant
    hors de portée (faux négatif assumé), et une suite dont l'échec ne
    s'explique que par une notation ambiguë, invalide, entre parenthèses ou
    introduite par "si" n'est jamais signalée non plus (prudence délibérée,
    cf. detecter_suites_illegales — un faux négatif occasionnel est
    préférable à un faux positif, qui déclenche une relance inutile) ;
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


# Séparateur ADMIS entre deux coups cités consécutifs d'une même suite
# (issue #90, point 1) : espace(s)/virgule(s), numéro de coup ("12." /
# "12..." / "6...") et annotations (!, ?, !?, ?!) — n'importe quel autre
# texte entre deux coups (un mot de prose, "...") met fin à la suite en
# cours, qui en démarre une nouvelle à partir du coup suivant.
_SEPARATEUR_SUITE_RE = re.compile(r"^(?:[\s,]|\d+\.{1,3}|[!?])*$")

# Un "si" isolé juste avant un coup cité signale une hypothèse non confirmée
# ("si Dxd5, les Blancs gagnent...") — jamais vérifiée (point 2, prudence).
_SI_HYPOTHETIQUE_RE = re.compile(r"\bsi\b\s*$", re.IGNORECASE)


def _extraire_suites(texte: str) -> list:
    """Regroupe les coups cités en notation SAN en suites (issue #90, point
    1) : des coups consécutifs dans le texte, séparés uniquement par un
    espace, une virgule, un numéro de coup ou une annotation, sont destinés
    à être joués DANS L'ORDRE sur le plateau, plutôt que vérifiés isolément
    chacun sur son propre coup — ce qui produisait le faux positif réel
    ayant motivé cette issue ("bxc6" dans "Bxc6+ bxc6" n'est illégal
    qu'isolé, pas joué à la suite de "Bxc6+").

    Retourne une liste de dicts {"coups": [str, ...] (notation SAN inchangée,
    casse jamais modifiée), "texte": str (sous-chaîne d'origine), "douteuse":
    bool, "raison_doute": str|None} — "douteuse" signale un coup cité entre
    parenthèses ou introduit par "si" (hypothèse, point 2) : une telle suite
    n'est jamais vérifiée, ni comme légale ni comme illégale."""
    candidats = [
        m for m in _SAN_RE.finditer(texte)
        if not _CASE_SEULE_RE.match(m.group(1))
    ]
    suites_brutes = []
    courante = None
    for m in candidats:
        if courante is not None:
            gap = texte[courante["fin"]:m.start()]
            if _SEPARATEUR_SUITE_RE.match(gap):
                courante["coups"].append(m.group(1))
                courante["fin"] = m.end()
                continue
            suites_brutes.append(courante)
        courante = {"debut": m.start(), "fin": m.end(), "coups": [m.group(1)]}
    if courante is not None:
        suites_brutes.append(courante)

    resultat = []
    for s in suites_brutes:
        avant = texte[max(0, s["debut"] - 20):s["debut"]]
        apres = texte[s["fin"]:s["fin"] + 20]
        douteuse, raison = False, None
        if "(" in avant and avant.rfind("(") > avant.rfind(")") and ")" in apres:
            douteuse, raison = True, "coup cité entre parenthèses (remarque hypothétique)"
        elif _SI_HYPOTHETIQUE_RE.search(avant):
            douteuse, raison = True, "coup introduit par \"si\" (hypothèse non confirmée)"
        resultat.append({
            "coups": s["coups"],
            "texte": texte[s["debut"]:s["fin"]],
            "douteuse": douteuse,
            "raison_doute": raison,
        })
    return resultat


def _tenter_suite(coups: list, board: "chess.Board") -> str:
    """Essaie de jouer `coups` (notation SAN, dans l'ordre) depuis une COPIE
    de `board` — jamais `board` lui-même. Retourne "ok" si toute la suite
    est jouable jusqu'au bout, "ambigu"/"invalide" si un coup n'a pas pu
    être résolu avec certitude (issue #90, point 2 : chess.AmbiguousMoveError/
    chess.InvalidMoveError — jamais traité comme une preuve d'illégalité),
    "illegal" sinon (coup syntaxiquement valide mais impossible depuis cette
    position, ou pièce citée inexistante)."""
    b = board.copy()
    for coup in coups:
        try:
            move = b.parse_san(coup)
        except chess.AmbiguousMoveError:
            return "ambigu"
        except chess.InvalidMoveError:
            return "invalide"
        except Exception:
            return "illegal"
        b.push(move)
    return "ok"


def _construire_candidats(fen_reference: str, fen_reference2: str = "",
                           coup_propose: str = "", coup_reel: str = "",
                           meilleur_coup: str = "", pv_coup_propose: str = "",
                           pv_meilleur_coup: str = "") -> list:
    """Construit les positions depuis lesquelles essayer de jouer une suite
    de coups citée, dans l'ordre de priorité demandé (issue #90, point 1) :
    position de départ, position actuelle, après le coup proposé, après le
    coup réellement joué, après le meilleur coup, puis chaque position
    intermédiaire des lignes (PV) calculées par le moteur pour le coup
    proposé et pour le meilleur coup (en reprenant la suite à chacune de
    leurs étapes) — et enfin, en dernier recours, le trait inversé de la
    position de départ et de la position actuelle (une ligne citée en prose
    alterne forcément les deux camps, cf. _variante_trait_inverse ;
    conservé de l'issue #87 pour ne pas régresser sur un coup isolé cité du
    point de vue de l'adversaire). Un coup ou une PV illisible/absent est
    simplement ignoré (pas d'exception remontée à l'appelant).

    Retourne une liste de tuples (label: str, board: chess.Board)."""
    candidats = []
    refs = []
    for fen in (fen_reference, fen_reference2):
        fen = (fen or "").strip()
        if not fen:
            continue
        try:
            refs.append(chess.Board(fen))
        except Exception as e:
            logger.warning(f"[COACH_RELIABILITY] FEN de référence illisible : {e}")

    board_depart = refs[0] if refs else None
    if board_depart is not None:
        candidats.append(("position de départ", board_depart))
    for b in refs[1:]:
        if b.fen() != board_depart.fen():
            candidats.append(("position actuelle", b))

    if board_depart is not None:
        for label, coup in (
            ("après le coup proposé", coup_propose),
            ("après le coup réellement joué", coup_reel),
            ("après le meilleur coup", meilleur_coup),
        ):
            coup = (coup or "").strip()
            if not coup:
                continue
            b = board_depart.copy()
            try:
                b.push_san(coup)
            except Exception:
                continue
            candidats.append((label, b))

        for label_ligne, pv in (
            ("ligne du coup proposé", pv_coup_propose),
            ("ligne du meilleur coup", pv_meilleur_coup),
        ):
            pv = (pv or "").strip()
            if not pv:
                continue
            b = board_depart.copy()
            for n, coup in enumerate(pv.split(), start=1):
                try:
                    b.push_san(coup)
                except Exception:
                    break
                candidats.append((f"{label_ligne}, après {n} coup(s)", b.copy()))

    for label, b in list(candidats):
        if label in ("position de départ", "position actuelle"):
            variante = _variante_trait_inverse(b)
            if variante is not None:
                candidats.append((f"{label} (trait inversé)", variante))

    return candidats


def detecter_suites_illegales(texte: str, candidats: list) -> list:
    """Détecte une suite de coups cités à la suite les uns des autres
    (issue #90, point 1) qu'AUCUNE des positions candidates ne permet de
    jouer jusqu'au bout. Tolérant par construction : une suite jouable
    depuis au moins une position candidate n'est jamais signalée — une ligne
    hypothétique citée en prose peut tout à fait partir d'un point de départ
    différent de ceux fournis (cf. limites en en-tête de module). Prudent
    (point 2) : une suite dont l'échec ne s'explique, sur CHAQUE position
    candidate essayée, que par une ambiguïté ou une notation invalide n'est
    jamais signalée non plus, de même qu'une suite citée entre parenthèses
    ou introduite par "si" (jamais vérifiée du tout) — mieux vaut un faux
    négatif qu'une pastille rouge et une relance pour rien.

    Retourne une liste de dicts {"type": "coup_illegal", "detail": str,
    "coups_cites": list, "positions_essayees": list} — "positions_essayees"
    (les libellés des candidats, dans l'ordre essayé) sert au journal
    (issue #90, point 3) à juger ensuite un faux positif."""
    if not candidats:
        return []
    alertes = []
    deja_vues = set()
    for suite in _extraire_suites(texte):
        cle = tuple(suite["coups"])
        if cle in deja_vues:
            continue
        deja_vues.add(cle)
        if suite["douteuse"]:
            continue
        reussie = False
        doute = False
        for _label, board in candidats:
            statut = _tenter_suite(suite["coups"], board)
            if statut == "ok":
                reussie = True
                break
            if statut in ("ambigu", "invalide"):
                doute = True
        if reussie or doute:
            continue
        labels_essayes = [label for label, _ in candidats]
        if len(suite["coups"]) == 1:
            detail = (
                f"coup cité \"{suite['coups'][0]}\" illégal sur toutes les "
                f"positions essayées ({len(labels_essayes)}), trait inversé "
                "compris"
            )
        else:
            detail = (
                f"suite de coups citée \"{suite['texte']}\" injouable depuis "
                f"toutes les positions essayées ({len(labels_essayes)})"
            )
        alertes.append({
            "type": "coup_illegal",
            "detail": detail,
            "coups_cites": suite["coups"],
            "positions_essayees": labels_essayes,
        })
    return alertes


def evaluer_fiabilite(texte: str, fen_reference: str = "", fen_reference2: str = "",
                       analyse_indisponible: bool = False, verdict_partiel: bool = False,
                       coup_propose: str = "", coup_reel: str = "", meilleur_coup: str = "",
                       pv_coup_propose: str = "", pv_meilleur_coup: str = "") -> dict:
    """Fonction principale (issue #87, point 5 ; étendue par l'issue #90,
    point 1) : exécute les contrôles déterministes disponibles sur `texte`
    et retourne un verdict de fiabilité prêt à afficher ("couleur"
    vert/orange/rouge) et à journaliser. Ne sait rien d'une éventuelle
    relance automatique (point 4) : c'est à l'appelant
    (llm_coach.get_coach_response, qui orchestre la relance) d'ajuster
    couleur/raison après coup selon qu'elle a eu lieu et a corrigé ou non —
    cette fonction se contente d'évaluer LE TEXTE qu'on lui donne.

    fen_reference / fen_reference2 : position(s) connues pour cette réponse
    (typiquement position de départ et position actuelle de l'exercice, ou
    simplement l'une des deux hors exercice) — "" si non disponible(s) :
    les contrôles qui en dépendent sont alors simplement absents du rapport,
    jamais remplacés par une supposition.
    coup_propose / coup_reel / meilleur_coup (notation SAN, depuis
    fen_reference) et pv_coup_propose / pv_meilleur_coup (lignes SAN
    calculées par le moteur depuis fen_reference, issue #90) : points de
    départ supplémentaires pour le contrôle des SUITES de coups cités (cf.
    _construire_candidats/detecter_suites_illegales) — "" si non
    disponible(s), le contrôle se contente alors des positions de référence
    seules, comme avant l'issue #90.
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
        "légalité des SUITES de coups cités à la suite les uns des autres "
        "(issue #90) : rejouées dans l'ordre depuis la position de départ, "
        "la position actuelle, après le coup proposé/réel/meilleur, et "
        "chaque étape des lignes (PV) calculées par le moteur pour le coup "
        "proposé et le meilleur coup — jamais signalée si jouable depuis AU "
        "MOINS UN de ces points de départ, ni si l'échec ne s'explique que "
        "par une notation ambiguë/invalide/entre parenthèses/hypothétique "
        "(\"si...\") (limite : une ligne qui ne part d'aucun de ces points "
        "reste hors de portée, faux négatif assumé)",
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
    candidats_suites = _construire_candidats(
        fen_reference, fen_reference2, coup_propose, coup_reel, meilleur_coup,
        pv_coup_propose, pv_meilleur_coup,
    )
    alertes += detecter_suites_illegales(texte, candidats_suites)

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
