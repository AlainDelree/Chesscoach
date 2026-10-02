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
    sur le fond sans déclencher la moindre alerte ;
  - le contrôle "échanges mal qualifiés" (issue #91, point 3 — cf.
    detecter_echanges_mal_qualifies) rejoue une suite d'AU MOINS DEUX
    captures citées (même extraction que le contrôle "suites illégales"
    ci-dessus, jamais dupliquée ni contredite) et compare son résultat
    matériel réel au qualificatif employé à proximité ("équilibré(e)",
    "favorable"/"défavorable" — ce dernier couple seulement si un camp est
    explicitement mentionné à proximité). Les verbes "gagne"/"perd", cités en
    exemple par l'issue, ne sont volontairement PAS vérifiés : trop généraux
    en français pour être associés avec confiance à la suite citée, mieux
    vaut ne rien signaler qu'un faux positif. Une incohérence détectée ici
    porte une gravité ("orange"/"rouge" selon l'écart matériel réel,
    SEUIL_ECHANGE_GRAVE_PTS) — c'est la seule famille d'alerte qui n'entraîne
    pas systématiquement une pastille rouge ;
  - trois contrôles supplémentaires (issue #92, tâche 3, même cas réel
    corrigé une première fois par l'issue #91 mais toujours en défaut sur
    trois formulations précises) : detecter_clouage_errone (une pièce dite
    "clouée" alors que python-chess ne la trouve clouée dans aucune position
    connue), detecter_echange_type_incoherent ("échange de dames"/"de
    tours"/"de fous"/"de cavaliers" accolé à une suite citée qui ne retire
    PAS une pièce de ce type à chacun des deux camps) et
    detecter_bilan_materiel_annonce ("équilibre matériel"/"matériel égal"/
    "égalité matérielle" à propos du résultat d'une suite citée, contredit
    par le bilan matériel réel après cette suite). Les deux derniers
    réutilisent la même extraction de suites et le même rejeu que
    detecter_echanges_mal_qualifies (jamais dupliqués), mais tolèrent une
    suite citée ENTRE PARENTHÈSES par simple concision (suite["entre_
    parentheses"]) — seule une suite introduite par "si" (suite["si_
    hypothetique"]) reste exclue, cf. _extraire_suites : le cas réel motivant
    ces deux contrôles citait justement sa suite entre parenthèses
    ("un échange de dames (Qxe8 Qxe8)"), ce que l'ancien filtre "douteuse"
    (issue #90) aurait exclu à tort ;
  - trois correctifs supplémentaires (issue #97, cas réel : "les Noirs
    peuvent jouer Bh6 pour échanger les fous (Bxh6 Qxh6), un échange
    équilibré" signalé à tort comme un gain net de 3 points pour les Noirs) :
    (1) un coup cité avec un "x" doit désormais être une VRAIE prise (y
    compris en passant, cf. Board.is_capture) sur la position essayée, sinon
    il est rejeté pour cette lecture — python-chess accepte sinon "Bxh6"
    même sur une case vide, en ignorant simplement le "x" (_tenter_suite) ;
    (2) l'extraction des suites (_extraire_suites) inclut désormais, pour
    une suite entre parenthèses, le dernier coup cité juste avant la
    parenthèse dans la même proposition ("Bh6" dans l'exemple ci-dessus)
    comme lecture candidate SUPPLÉMENTAIRE (coup_precedent, en plus de la
    lecture isolée, jamais à la place) ; (3) les trois contrôles de
    qualificatif ci-dessus (échanges mal qualifiés, échange de type,
    bilan matériel annoncé) rassemblent maintenant TOUTES les lectures
    valides d'une suite (positions candidates x avec/sans coup précédent
    cité x avec/sans demi-coup caché, cf. _rassembler_lectures) et ne
    signalent une incohérence que si TOUTES ces lectures contredisent le
    texte — une seule lecture cohérente suffit à ne rien signaler. Ce
    dernier changement élargit volontairement la tolérance (encore un faux
    négatif préféré à un faux positif), au prix, documenté, d'un risque
    accru qu'une lecture "chanceuse" découverte via un demi-coup caché
    masque une vraie erreur sur une suite par ailleurs correctement
    identifiée ; les alertes qui survivent journalisent désormais le nombre
    de lectures valides retenues et leur résultat (ex. "3 lecture(s) valide
    (s) : 0, -3, 3"), pour juger après coup un éventuel faux positif.
  - un quatrième contrôle (issue #98, cas réel : une réponse pourtant déjà
    corrigée par la relance automatique affirmait encore "après Be5, ton
    fou adverse attaque la tour", alors que le fou noir en e5 n'attaque pas
    la tour blanche en e3, cf. detecter_attaque_defense_incoherente) vérifie
    une phrase simple affirmant qu'une pièce attaque ou défend une autre,
    contredite par TOUTES les lectures valides de la position concernée
    (python-chess, Board.attacks) — les deux pièces doivent être
    identifiables sans ambiguïté (case citée, mot de couleur "adverse"/
    "noir"/"blanc"/"ton"/"ta"/"tes", ou pièce UNIQUE de ce type sur la
    position essayée), sinon la phrase n'est jamais contrôlée (même
    prudence que le reste du module). Gravité "orange" par défaut, "rouge"
    seulement si un connecteur de justification de verdict suit à proximité
    ou si la même affirmation se répète dans le texte — heuristique
    volontairement approximative, documentée en détail au-dessus de
    detecter_attaque_defense_incoherente.
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
# Volontairement strict en tête (\b) pour limiter les faux positifs sur un
# mot qui ressemblerait par hasard à un coup. Frontière de FIN en négatif
# `(?!\w)` plutôt que `\b` (issue #90) : un `\b` final échouerait sur un
# coup se terminant par "+"/"#" suivi d'un espace — "+"/"#" et l'espace sont
# tous deux des caractères NON-mot, donc `\b` n'y voit aucune frontière et
# tronquait silencieusement "a8=Q+" en "a8=Q" (ensuite rejeté par
# python-chess, qui exige la notation d'échec exacte) ; `(?!\w)` accepte
# correctement tout caractère suivant non alphanumérique, y compris rien du
# tout en fin de texte.
_SAN_RE = re.compile(
    r"\b(O-O-O|O-O|[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?)(?!\w)"
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

# Fenêtre de recherche du "coup précédent cité" devant une parenthèse (issue
# #97, point 2) — bornée par la première fin de phrase rencontrée en
# remontant, pour ne jamais aller chercher un coup d'une proposition sans
# rapport.
_FENETRE_COUP_PRECEDENT = 80


def _coup_precedent_cite(texte: str, position_parenthese: int) -> str:
    """Cherche, juste avant la parenthèse ouvrante à `position_parenthese`
    (position ABSOLUE dans `texte`), le DERNIER coup cité en notation SAN
    dans la même proposition (issue #97, point 2) — ex. "les Noirs peuvent
    jouer Bh6 pour échanger les fous (Bxh6 Qxh6)" retrouve "Bh6" comme coup
    précédent de la suite entre parenthèses "Bxh6 Qxh6". Borné par la
    première fin de phrase rencontrée en remontant (jamais au-delà) et par
    _FENETRE_COUP_PRECEDENT caractères. Retourne "" si aucun coup cité n'est
    trouvé dans cette fenêtre."""
    debut = max(0, position_parenthese - _FENETRE_COUP_PRECEDENT)
    morceau = texte[debut:position_parenthese]
    derniere_frontiere = None
    for mm in re.finditer(r"[.\n!?]", morceau):
        derniere_frontiere = mm.end()
    if derniere_frontiere is not None:
        morceau = morceau[derniere_frontiere:]
    candidats = [
        m.group(1) for m in _SAN_RE.finditer(morceau)
        if not _CASE_SEULE_RE.match(m.group(1))
    ]
    return candidats[-1] if candidats else ""


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
    bool, "raison_doute": str|None, "coup_precedent": str} — "douteuse"
    signale un coup cité entre parenthèses ou introduit par "si" (hypothèse,
    point 2) : une telle suite n'est jamais vérifiée, ni comme légale ni
    comme illégale. "coup_precedent" (issue #97, point 2) : pour une suite
    entre parenthèses seulement, le dernier coup cité juste avant la
    parenthèse ouvrante dans la même proposition (cf. _coup_precedent_cite),
    "" si aucun — sert de lecture candidate SUPPLÉMENTAIRE (coup_precedent +
    coups de la suite) aux contrôles ci-dessous, en plus de la lecture
    isolée de la parenthèse elle-même, jamais à la place."""
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
        entre_parentheses, si_hypothetique = False, False
        coup_precedent = ""
        if "(" in avant and avant.rfind("(") > avant.rfind(")") and ")" in apres:
            douteuse, raison = True, "coup cité entre parenthèses (remarque hypothétique)"
            entre_parentheses = True
            position_parenthese = max(0, s["debut"] - 20) + avant.rfind("(")
            coup_precedent = _coup_precedent_cite(texte, position_parenthese)
        elif _SI_HYPOTHETIQUE_RE.search(avant):
            douteuse, raison = True, "coup introduit par \"si\" (hypothèse non confirmée)"
            si_hypothetique = True
        resultat.append({
            "coups": s["coups"],
            "texte": texte[s["debut"]:s["fin"]],
            "debut": s["debut"],
            "fin": s["fin"],
            "douteuse": douteuse,
            "raison_doute": raison,
            # Distinction fine (issue #92, tâches 3a/3c) : une suite citée
            # ENTRE PARENTHÈSES par simple concision ("il force un échange de
            # dames (Qxe8 Qxe8)", cas réel ayant motivé l'issue) n'est pas une
            # hypothèse non confirmée comme "si Dxd5..." — detecter_suites_
            # illegales et detecter_echanges_mal_qualifies continuent de
            # l'ignorer comme avant (champ "douteuse" inchangé, aucune
            # régression), mais les contrôles ajoutés par l'issue #92
            # (detecter_echange_type_incoherent, detecter_bilan_materiel_
            # annonce) s'appuient sur ce champ plus fin pour rester tolérants
            # au style "entre parenthèses" tout en continuant à ignorer une
            # vraie hypothèse "si...".
            "entre_parentheses": entre_parentheses,
            "si_hypothetique": si_hypothetique,
            "coup_precedent": coup_precedent,
        })
    return resultat


def _variantes_coups(suite: dict) -> list:
    """Les lectures (listes de coups) candidates pour `suite` (issue #97,
    point 2 et 3) : la suite telle que citée, et, si un coup précédent a été
    trouvé juste avant la parenthèse (suite["coup_precedent"]), la même
    suite PRÉCÉDÉE de ce coup — jamais à la place de la lecture isolée,
    toujours en plus."""
    variantes = [suite["coups"]]
    if suite.get("coup_precedent"):
        variantes.append([suite["coup_precedent"]] + suite["coups"])
    return variantes


def _tenter_suite(coups: list, board: "chess.Board") -> str:
    """Essaie de jouer `coups` (notation SAN, dans l'ordre) depuis une COPIE
    de `board` — jamais `board` lui-même. Retourne "ok" si toute la suite
    est jouable jusqu'au bout, "ambigu"/"invalide" si un coup n'a pas pu
    être résolu avec certitude (issue #90, point 2 : chess.AmbiguousMoveError/
    chess.InvalidMoveError — jamais traité comme une preuve d'illégalité),
    "illegal" sinon (coup syntaxiquement valide mais impossible depuis cette
    position, pièce citée inexistante, ou coup noté avec un "x" qui n'est
    PAS réellement une prise sur cette position précise, issue #97, point 1).

    Constat ayant motivé ce dernier cas (cas réel, exercice h4) : python-chess
    accepte la notation "Bxh6" même quand la case d'arrivée est vide (il
    ignore simplement le "x"), ce qui a fait rejouer un coup qui N'EST PAS
    une prise comme s'il en était une, produisant un bilan matériel inventé.
    `Board.is_capture` reconnaît aussi la prise en passant — un coup noté
    avec "x" qui capture en passant reste donc accepté normalement."""
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
        if "x" in coup and not b.is_capture(move):
            return "illegal"
        b.push(move)
    return "ok"


def _jouer_suite(coups: list, board: "chess.Board"):
    """Comme `_tenter_suite`, mais retourne directement la position
    d'arrivée (COPIE de `board`, jamais modifiée) si `coups` est
    intégralement jouable, None sinon — évite de dupliquer le rejeu dans
    chaque appelant (issue #97)."""
    if _tenter_suite(coups, board) != "ok":
        return None
    b = board.copy()
    for coup in coups:
        b.push(b.parse_san(coup))
    return b


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


def _legal_apres_demi_coup_cache(coup: str, board: "chess.Board") -> bool:
    """Essaie `coup` (un seul coup SAN) depuis `board`, après chacun des
    demi-coups légaux de `board`, un seul à la fois (issue #94, point 4) —
    jamais `board` lui-même modifié. Sert de filet de sécurité pour un coup
    cité ISOLÉMENT (sans suite rattachée) qui décrit en réalité une reprise :
    constat réel ayant motivé cet ajout, "si la dame prend en h4, gxh4
    reprend" cite "gxh4" seul, sans jamais écrire "Qxh4" — ce coup n'est
    légal sur aucune position candidate SANS la prise de dame intermédiaire,
    mais le devient dès qu'on y insère N'IMPORTE QUEL demi-coup caché (ici,
    la prise de dame réelle fait partie des coups légaux essayés). Retourne
    False dès que `board` n'a aucun coup légal (position terminale)."""
    for coup_cache in board.legal_moves:
        board_intermediaire = board.copy()
        board_intermediaire.push(coup_cache)
        if _tenter_suite([coup], board_intermediaire) == "ok":
            return True
    return False


def _lectures_demi_coup_cache(coups: list, board: "chess.Board") -> list:
    """Variante de `_legal_apres_demi_coup_cache` qui accepte une suite
    entière (pas seulement un coup isolé) et retourne TOUTES les positions
    d'arrivée obtenues en insérant, un seul à la fois, chacun des demi-coups
    légaux de `board` avant d'essayer `coups` (issue #97, point 3) — au lieu
    d'un simple booléen, nécessaire ici pour calculer le bilan matériel de
    chaque lecture ainsi découverte. Retourne une liste de tuples
    (board_avant: chess.Board, board_apres: chess.Board)."""
    resultats = []
    for coup_cache in board.legal_moves:
        board_intermediaire = board.copy()
        board_intermediaire.push(coup_cache)
        board_apres = _jouer_suite(coups, board_intermediaire)
        if board_apres is not None:
            resultats.append((board_intermediaire, board_apres))
    return resultats


def _rassembler_lectures(suite: dict, candidats: list) -> list:
    """Rassemble TOUTES les lectures valides d'une suite citée (issue #97,
    point 3) : combine chaque position candidate (`candidats`), chaque
    lecture des coups (_variantes_coups — avec ou sans le coup précédent
    cité, point 2) et, quand la lecture directe échoue, chaque demi-coup
    intermédiaire caché possible (_lectures_demi_coup_cache, même principe
    que _legal_apres_demi_coup_cache mais généralisé à une suite entière).
    Une lecture qui mène à la MÊME position d'arrivée qu'une lecture déjà
    retenue (même FEN) n'est comptée qu'une seule fois — atteinte par deux
    chemins différents, ce n'est pas une lecture supplémentaire.

    Retourne une liste de tuples (board_avant: chess.Board, board_apres:
    chess.Board), une entrée par lecture DISTINCTE — [] si la suite ne se
    joue d'aucune façon connue (aucune lecture, cf. appelants : dans ce cas,
    le contrôle appelant ne signale rien, comme avant cette issue)."""
    lectures = []
    vues = set()
    for _label, board in candidats:
        for coups in _variantes_coups(suite):
            board_apres = _jouer_suite(coups, board)
            if board_apres is not None:
                cle = board_apres.fen()
                if cle not in vues:
                    vues.add(cle)
                    lectures.append((board, board_apres))
                continue
            for board_avant_c, board_apres_c in _lectures_demi_coup_cache(coups, board):
                cle = board_apres_c.fen()
                if cle not in vues:
                    vues.add(cle)
                    lectures.append((board_avant_c, board_apres_c))
    return lectures


def _resume_valeurs(valeurs: list) -> str:
    """Résumé, pour le journal (issue #97, point 4), des résultats
    numériques de TOUTES les lectures valides d'une suite — DÉDUPLIQUÉS,
    plusieurs lectures distinctes (positions candidates, coup précédent cité
    ou non, demi-coup caché différent) donnant très souvent le même résultat
    matériel (cf. _rassembler_lectures, qui déduplique seulement par
    position d'arrivée, plus fine que ce résumé). Ex. "3 lecture(s)
    distincte(s) : 0, -3, 3"."""
    distinctes = sorted(set(valeurs))
    return f"{len(distinctes)} lecture(s) distincte(s) : {', '.join(str(v) for v in distinctes)}"


def _delta_materiel(board_avant: "chess.Board", board_apres: "chess.Board") -> int:
    return (
        (_materiel_camp(board_apres, chess.WHITE) - _materiel_camp(board_apres, chess.BLACK))
        - (_materiel_camp(board_avant, chess.WHITE) - _materiel_camp(board_avant, chess.BLACK))
    )


def detecter_suites_illegales(texte: str, candidats: list) -> list:
    """Détecte une suite de coups cités à la suite les uns des autres
    (issue #90, point 1) qu'AUCUNE des positions candidates ne permet de
    jouer jusqu'au bout, même en autorisant pour un coup ISOLÉ (une seule
    suite d'un seul coup) un demi-coup intermédiaire caché quelconque avant
    de l'essayer (issue #94, point 4 — cf. _legal_apres_demi_coup_cache).
    Tolérant par construction : une suite jouable depuis au moins une
    position candidate n'est jamais signalée — une ligne hypothétique citée
    en prose peut tout à fait partir d'un point de départ différent de ceux
    fournis (cf. limites en en-tête de module). Prudent (point 2) : une
    suite dont l'échec ne s'explique, sur CHAQUE position candidate essayée,
    que par une ambiguïté ou une notation invalide n'est jamais signalée non
    plus, de même qu'une suite citée entre parenthèses ou introduite par
    "si" (jamais vérifiée du tout) — mieux vaut un faux négatif qu'une
    pastille rouge et une relance pour rien.

    Constat ayant motivé le demi-coup caché (issue #94) : "si la dame prend
    en h4, gxh4 reprend" cite "gxh4" seul, en décrivant par des mots la prise
    précédente plutôt que de l'écrire ("Qxh4") — ce coup est pourtant bel et
    bien légal, une fois cette prise jouée. Sans ce filet, un coup isolé mais
    plausible (rattaché par le texte à un coup non cité) déclenchait à tort
    une alerte rouge et une relance automatique inutile. Un coup réellement
    illégal (pièce absente, prise géométriquement impossible...) continue
    d'être signalé : aucun demi-coup cache ne le rend légal nulle part.

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
        if not reussie and not doute and len(suite["coups"]) == 1:
            reussie = any(
                _legal_apres_demi_coup_cache(suite["coups"][0], board)
                for _label, board in candidats
            )
        if reussie or doute:
            continue
        labels_essayes = [label for label, _ in candidats]
        if len(suite["coups"]) == 1:
            detail = (
                f"coup cité \"{suite['coups'][0]}\" illégal sur toutes les "
                f"positions essayées ({len(labels_essayes)}), trait inversé "
                "et un demi-coup intermédiaire caché compris"
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


# ── Vérification des échanges cités (issue #91, tâche 3) ───────────────────
# Constat ayant motivé cet ajout (même cas que l'en-tête du module) : le coach
# a écrit "après Rxe5 Nxe5, l'échange reste équilibré" alors que cette suite,
# rejouée sur l'échiquier, perd une tour (5 points) contre un fou (3 points) —
# un gain net de 2 points pour les Noirs, pas un échange équilibré. Les
# contrôles existants (pièces inexistantes, coups illégaux) ne détectent
# aucune erreur de ce genre : ceux-ci ne portent jamais sur la JUSTESSE
# stratégique, seulement sur des faits bruts.
#
# Portée volontairement limitée (prudence, cf. docstring de module) :
#   - seules les suites d'AU MOINS DEUX coups cités à la suite (une suite
#     d'un seul coup n'est pas un "échange" à vérifier de cette façon) sont
#     concernées ;
#   - le qualificatif "équilibré"/"équilibrée" ne nécessite aucun camp
#     explicite (c'est une affirmation symétrique : delta matériel nul) ;
#   - les qualificatifs "favorable"/"défavorable" ne sont vérifiés QUE s'un
#     camp (Blancs/Noirs) est explicitement mentionné à proximité immédiate
#     (_FENETRE_CAMP_PROXIMITE_ECHANGE) — sans cette mention, le camp visé
#     est trop incertain pour être deviné, le qualificatif n'est alors
#     jamais vérifié (faux négatif assumé) ;
#   - les verbes "gagne"/"perd" cités par l'issue comme exemples ne sont
#     DÉLIBÉRÉMENT PAS vérifiés : ce sont des verbes à usage bien trop
#     général en français ("gagner la partie", "perdre du temps"...) pour
#     être associés avec confiance à la suite de coups cités juste avant,
#     même avec un camp explicite à proximité — le risque de faux positif
#     (relancer le coach sur une phrase qui n'a rien à voir avec l'échange
#     cité) est jugé trop élevé face au bénéfice. Mieux vaut ne rien
#     signaler qu'un faux positif, cf. consigne explicite de l'issue #91.
_VALEURS_MATERIELLES = {
    chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9,
}

# Seuil (en points classiques) au-delà duquel une incohérence d'échange est
# jugée assez grave pour une pastille ROUGE plutôt qu'ORANGE — réglable en ce
# seul endroit (issue #91, tâche 1 et 3 : "seuils réglables en un seul
# endroit").
SEUIL_ECHANGE_GRAVE_PTS = 3

_QUALIF_EQUILIBRE_RE = re.compile(r"\béquilibr\w*\b", re.IGNORECASE)
_QUALIF_FAVORABLE_RE = re.compile(r"\bfavorables?\b", re.IGNORECASE)
_QUALIF_DEFAVORABLE_RE = re.compile(r"\bd[ée]favorables?\b", re.IGNORECASE)
_CAMP_MOT_RE = re.compile(r"\b(blancs?|blanches?|noirs?|noires?)\b", re.IGNORECASE)

# Fenêtre de recherche d'un qualificatif autour d'une suite citée : un peu
# avant (un qualificatif peut précéder, ex. "échange favorable Rxe5 Nxe5"),
# surtout après (cas réel : "Rxe5 Nxe5... l'échange reste équilibré"),
# coupée à la première fin de phrase rencontrée pour ne jamais associer un
# qualificatif d'une phrase sans rapport.
_FENETRE_AVANT_ECHANGE = 40
_FENETRE_APRES_ECHANGE = 150
# Distance maximale (caractères) entre "favorable"/"défavorable" et le mot de
# camp qui lui donne un sens univoque — au-delà, le camp visé est trop
# incertain (cf. portée ci-dessus).
_FENETRE_CAMP_PROXIMITE_ECHANGE = 30


def _materiel_camp(board: "chess.Board", couleur) -> int:
    return sum(
        _VALEURS_MATERIELLES[pt] * len(board.pieces(pt, couleur))
        for pt in _VALEURS_MATERIELLES
    )


# Négation juste avant le qualificatif (issue #91, prudence) : "ce n'est PAS
# un échange équilibré" affirme en fait l'inverse du qualificatif qu'elle
# contient — une détection naïve par simple mot-clé le signalerait à tort. Ne
# pas essayer d'inverser le sens (trop incertain avec une simple regex, cf.
# double négation, "pas vraiment", portée des négations imbriquées) : une
# négation détectée à proximité immédiate suffit à abstenir ce qualificatif
# plutôt que de risquer un faux positif.
_NEGATION_RE = re.compile(r"\b(pas|jamais|aucunement|nullement)\b", re.IGNORECASE)
_FENETRE_NEGATION_ECHANGE = 20


def _qualificatif_nie(fenetre: str, position: int) -> bool:
    return bool(_NEGATION_RE.search(fenetre[max(0, position - _FENETRE_NEGATION_ECHANGE):position]))


def _fenetre_qualificatif_echange(texte: str, suite: dict) -> str:
    debut = max(0, suite["debut"] - _FENETRE_AVANT_ECHANGE)
    fin = min(len(texte), suite["fin"] + _FENETRE_APRES_ECHANGE)
    morceau_apres = texte[suite["fin"]:fin]
    m_fin_phrase = re.search(r"[.\n]", morceau_apres)
    if m_fin_phrase:
        fin = suite["fin"] + m_fin_phrase.start()
    return texte[debut:fin]


def detecter_echanges_mal_qualifies(texte: str, candidats: list) -> list:
    """Détecte une suite de captures citées (issue #91, tâche 3, AU MOINS
    deux coups — cf. portée ci-dessus) qualifiée dans le texte
    ("équilibré"/"favorable"/"défavorable", ce dernier couple seulement avec
    un camp explicite à proximité) d'une façon CONTREDITE par le résultat
    matériel réel de cette suite, rejouée sur l'échiquier depuis l'une des
    positions candidates (même construction que detecter_suites_illegales —
    cette fonction ne duplique ni ne recalcule la légalité : une suite
    illégale partout ou ambiguë est simplement ignorée ici, c'est le rôle de
    detecter_suites_illegales de la signaler). Un qualificatif précédé d'une
    négation à proximité immédiate (\"pas\", \"jamais\"...) n'est jamais
    signalé non plus (prudence : \"ce n'est PAS un échange équilibré\"
    affirme l'inverse, une simple inversion de sens par regex serait trop
    incertaine, cf. _qualificatif_nie).

    Différence volontaire sur le filtre \"douteuse\" (issue #94, point 3,
    même raisonnement que detecter_echange_type_incoherent ci-dessous) : une
    suite citée ENTRE PARENTHÈSES par simple concision (style courant du
    coach, ex. \"(Qxh4 gxh4) : échange équilibré\") n'est PAS ignorée ici —
    seule suite[\"si_hypothetique\"] l'est (cf. _extraire_suites). Constat
    ayant motivé ce changement : la version originale de ce contrôle
    ignorait TOUTE suite entre parenthèses (champ \"douteuse\"), ce qui a
    laissé passer sans alerte \"si la dame prend en h4, gxh3 reprend (Qxh4
    gxh4) : un échange équilibré\" sur une suite qui perd en réalité une
    dame contre un pion (8 points). Un filet de sécurité reste la tentative
    de rejeu elle-même (board_avant reste None, donc ignoré, si la suite ne
    se joue depuis aucune position candidate).

    Chaque alerte porte un champ \"gravite\" (\"orange\"/\"rouge\", selon que
    l'écart matériel réel dépasse SEUIL_ECHANGE_GRAVE_PTS) — cf.
    evaluer_fiabilite, qui l'utilise pour choisir la couleur de la pastille
    sans jamais la dégrader en rouge pour une incohérence mineure.

    Lectures multiples (issue #97, point 3 — cas réel ayant motivé le
    changement : \"les Noirs peuvent jouer Bh6 pour échanger les fous (Bxh6
    Qxh6), un échange équilibré\" signalé à tort, alors que c'est exact une
    fois Bh6 pris en compte). `_rassembler_lectures` combine chaque position
    candidate, chaque lecture des coups (avec ou sans le coup précédent cité
    juste avant la parenthèse, point 2) et, si besoin, un demi-coup
    intermédiaire caché (point 3) : CHAQUE lecture valide ainsi obtenue est
    comparée au qualificatif, et une incohérence n'est signalée QUE SI
    TOUTES les lectures valides la contredisent — une seule lecture
    cohérente avec le texte suffit à ne rien signaler. Si la suite ne se
    joue d'aucune façon connue, rien n'est signalé non plus (comme avant
    cette issue, prudence inchangée).

    Retourne une liste de dicts {"type": "echange_mal_qualifie", "gravite":
    str, "detail": str}."""
    if not candidats:
        return []
    alertes = []
    for suite in _extraire_suites(texte):
        if suite["si_hypothetique"] or len(suite["coups"]) < 2:
            continue
        fenetre = _fenetre_qualificatif_echange(texte, suite)

        lectures = _rassembler_lectures(suite, candidats)
        if not lectures:
            continue
        deltas = [_delta_materiel(av, ap) for av, ap in lectures]
        delta_pire = max(deltas, key=abs)
        gravite = "rouge" if abs(delta_pire) >= SEUIL_ECHANGE_GRAVE_PTS else "orange"
        resume_lectures = _resume_valeurs(deltas)

        for m in _QUALIF_EQUILIBRE_RE.finditer(fenetre):
            if _qualificatif_nie(fenetre, m.start()):
                continue
            if any(d == 0 for d in deltas):
                continue
            camp_gagnant = "les Blancs" if delta_pire > 0 else "les Noirs"
            alertes.append({
                "type": "echange_mal_qualifie",
                "gravite": gravite,
                "detail": (
                    f"\"{m.group(0)}\" accolé à la suite citée \"{suite['texte']}\" "
                    "prétend un échange équilibré, alors qu'AUCUNE lecture valide de "
                    f"cette suite, rejouée sur l'échiquier ({resume_lectures}), ne "
                    f"donne un bilan nul — au pire, un gain net de {abs(delta_pire)} "
                    f"point(s) pour {camp_gagnant}"
                ),
            })

        for regex, attendu_positif in (
            (_QUALIF_FAVORABLE_RE, True), (_QUALIF_DEFAVORABLE_RE, False),
        ):
            for m in regex.finditer(fenetre):
                if _qualificatif_nie(fenetre, m.start()):
                    continue
                camp_m, meilleure_distance = None, None
                for cm in _CAMP_MOT_RE.finditer(fenetre):
                    distance = abs(cm.start() - m.start())
                    if distance <= _FENETRE_CAMP_PROXIMITE_ECHANGE and (
                        meilleure_distance is None or distance < meilleure_distance
                    ):
                        camp_m, meilleure_distance = cm, distance
                if camp_m is None:
                    continue
                couleur = _couleur_depuis_mot(camp_m.group(1))
                if couleur is None:
                    continue
                deltas_pour_camp = [d if couleur == chess.WHITE else -d for d in deltas]
                coherent_quelque_part = any(
                    (dc > 0) if attendu_positif else (dc < 0) for dc in deltas_pour_camp
                )
                if coherent_quelque_part:
                    continue
                camp_txt = "Blancs" if couleur == chess.WHITE else "Noirs"
                resultats_txt = ", ".join(
                    "équilibré" if d == 0 else
                    f"favorable aux {'Blancs' if d > 0 else 'Noirs'} ({abs(d)} point(s) net)"
                    for d in sorted(set(deltas))
                )
                alertes.append({
                    "type": "echange_mal_qualifie",
                    "gravite": gravite,
                    "detail": (
                        f"\"{m.group(0)}\" (associé aux {camp_txt}) accolé à la suite "
                        f"citée \"{suite['texte']}\" ne correspond à AUCUNE lecture "
                        f"valide de cette suite, rejouée sur l'échiquier ({resume_lectures} "
                        f"— détail : {resultats_txt})"
                    ),
                })
    return alertes


# ── Pièces clouées, « échange de X » et bilan matériel annoncé (issue #92,
# tâche 3) ───────────────────────────────────────────────────────────────
# Constats ayant motivé ces trois ajouts (même cas réel que l'en-tête de
# module, suite au correctif de l'issue #91) : une réponse courte et au
# verdict juste a quand même affirmé "Re8 : il force un échange de dames
# (Qxe8 Qxe8)" alors que cette suite perd une TOUR contre une DAME (pas un
# échange de dames : un seul camp y perd sa dame), "ta dame en a8 reste
# clouée face à la dame adverse en d7" alors qu'aucune pièce blanche n'est
# clouée dans cette position (vérifié avec python-chess), et "après
# l'échange, tu récupères l'équilibre matériel" alors que les Blancs
# terminent en avance de 2 points (14 contre 12) après la suite citée.
# Aucun des contrôles existants (pièces inexistantes, coups illégaux,
# qualificatif d'échange précis "équilibré"/"favorable"/"défavorable" collé
# à une suite) ne couvre ces trois formulations.

_CLOUAGE_RE = re.compile(r"\bclou\w*\b", re.IGNORECASE)
# Fenêtres volontairement asymétriques et bornées par la phrase en cours
# (avant ET après, contrairement à _fenetre_qualificatif_echange qui ne
# coupe qu'après) : un mot de clouage peut précéder ("la dame clouée en a8",
# non capté par _CASE_PIECE_RE lui-même, cf. limite ci-dessous) ou suivre
# ("ta dame en a8 reste clouée...", cas réel) la citation pièce+case.
_FENETRE_CLOUAGE_AVANT = 60
_FENETRE_CLOUAGE_APRES = 100


def _fenetre_clouage(texte: str, debut: int, fin: int) -> tuple:
    """Même esprit que _fenetre_qualificatif_echange, mais bornée des DEUX
    côtés par la première fin de phrase rencontrée (jamais au-delà), pour
    éviter d'associer un mot de clouage à une phrase sans rapport. Retourne
    (fenetre, offset_debut) — offset_debut sert à retrouver la position
    ABSOLUE d'un match trouvé dans la fenêtre (utile pour _qualificatif_nie,
    qui attend une position dans le texte complet)."""
    avant_debut = max(0, debut - _FENETRE_CLOUAGE_AVANT)
    morceau_avant = texte[avant_debut:debut]
    derniere_frontiere = None
    for mm in re.finditer(r"[.\n]", morceau_avant):
        derniere_frontiere = mm.end()
    if derniere_frontiere is not None:
        avant_debut += derniere_frontiere
    apres_fin = min(len(texte), fin + _FENETRE_CLOUAGE_APRES)
    morceau_apres = texte[fin:apres_fin]
    m_fin_phrase = re.search(r"[.\n]", morceau_apres)
    if m_fin_phrase:
        apres_fin = fin + m_fin_phrase.start()
    return texte[avant_debut:apres_fin], avant_debut


def detecter_clouage_errone(texte: str, boards_reference: list, candidats: list) -> list:
    """Détecte une pièce citée \"<type> [<couleur>] en/sur <case>\" (issue
    #92, tâche 3b) dite CLOUÉE dans le texte (mot de la famille \"clou...\"
    dans la même phrase, avant ou après) alors qu'elle n'est clouée dans
    AUCUNE des positions disponibles (position de départ, position actuelle,
    ni aucune étape des lignes/suites citées déjà construites pour les
    contrôles ci-dessus — même tolérance que detecter_case_piece_incoherente
    : clouée dans AU MOINS UNE position connue n'est jamais signalée).

    Identification volontairement prudente (\"signaler seulement si la
    pièce est identifiable sans ambiguïté\", issue #92) : la couleur n'a PAS
    besoin d'être explicite dans le texte (\"ta dame en a8\", cas réel) — la
    case suffit à identifier sans ambiguïté la pièce réellement présente
    dans `boards_reference` (position de départ/actuelle) ; si aucune des
    positions de référence n'a une pièce du type cité sur cette case (ou si
    une couleur explicite contredit la pièce réellement présente), la
    mention n'est tout simplement pas contrôlée (faux négatif assumé,
    c'est le rôle de detecter_case_piece_incoherente de signaler une case
    fausse, jamais celui de ce contrôle-ci). Un roi n'est jamais contrôlé
    (il ne peut pas être \"cloué\" au sens des échecs). Une mention niée
    (\"pas clouée\") ou hypothétique (\"si... était clouée\") n'est jamais
    signalée non plus (même prudence que les contrôles d'échange ci-dessus).

    Limite assumée : une tournure où le mot de clouage ne figure pas dans la
    même phrase que la citation pièce+case (au-delà de
    _FENETRE_CLOUAGE_AVANT/_APRES, ou séparée par une fin de phrase) échappe
    à ce contrôle, comme pour tout contrôle fondé sur une fenêtre de
    proximité dans ce module.

    Retourne une liste de dicts {"type": "clouage_errone", "detail": str}
    (pas de champ "gravite" — fait géométrique vérifié avec certitude par
    python-chess, traité comme les autres contrôles déjà existants qui n'en
    portent pas, cf. evaluer_fiabilite : gravité "rouge" par défaut)."""
    if not boards_reference:
        return []
    alertes = []
    tous_boards = list(boards_reference) + [b for _, b in candidats]
    for m in _CASE_PIECE_RE.finditer(texte):
        piece_type = _NOM_PIECE_TYPE[m.group(1).lower()]
        if piece_type == chess.KING:
            continue
        case = chess.parse_square(m.group(3).lower())
        couleur_citee = _couleur_depuis_mot(m.group(2)) if m.group(2) else None

        fenetre, offset = _fenetre_clouage(texte, m.start(), m.end())
        clouage_m = _CLOUAGE_RE.search(fenetre)
        if not clouage_m:
            continue
        position_absolue = offset + clouage_m.start()
        if _qualificatif_nie(texte, position_absolue):
            continue
        if _SI_HYPOTHETIQUE_RE.search(texte[max(0, m.start() - 30):m.start()]):
            continue

        couleur_resolue = None
        for b in boards_reference:
            p = b.piece_at(case)
            if p is not None and p.piece_type == piece_type and (
                couleur_citee is None or p.color == couleur_citee
            ):
                couleur_resolue = p.color
                break
        if couleur_resolue is None:
            continue

        clouee_quelque_part = any(
            (p := b.piece_at(case)) is not None and p.piece_type == piece_type
            and p.color == couleur_resolue and b.is_pinned(couleur_resolue, case)
            for b in tous_boards
        )
        if clouee_quelque_part:
            continue
        camp_txt = "blanc" if couleur_resolue == chess.WHITE else "noir"
        nom = _NOM_PIECE_AFFICHAGE[piece_type]
        alertes.append({
            "type": "clouage_errone",
            "detail": (
                f"\"{nom} {camp_txt} en {m.group(3)}\" dite clouée, alors que "
                "cette pièce n'est clouée dans aucune des positions "
                "disponibles (position de départ, position actuelle, lignes "
                "citées) d'après python-chess"
            ),
        })
    return alertes


_ECHANGE_DE_TYPE_RE = re.compile(
    r"\b[ée]chang\w*\s+(?:de|des)\s+(dames?|tours?|fous?|cavaliers?)\b",
    re.IGNORECASE,
)


def detecter_echange_type_incoherent(texte: str, candidats: list) -> list:
    """Détecte \"échange de dames\"/\"de tours\"/\"de fous\"/\"de cavaliers\"
    (issue #92, tâche 3a) accolé à une suite d'au moins deux coups cités,
    quand cette suite, rejouée sur l'échiquier, ne retire PAS une pièce de
    ce type précis à CHACUN des deux camps — cas réel ayant motivé cette
    tâche : \"il force un échange de dames (Qxe8 Qxe8)\" sur une suite qui
    prend une tour aux Blancs et une dame aux Noirs (un seul camp perd sa
    dame, ce n'est pas un \"échange de dames\").

    Même construction que detecter_echanges_mal_qualifies (fenêtre de
    proximité autour de la suite via _fenetre_qualificatif_echange, suite
    rejouée via _rassembler_lectures) — ne duplique ni ne recalcule la
    légalité. Différence volontaire sur le filtre \"douteuse\" : une suite
    citée ENTRE PARENTHÈSES par simple concision (cas réel ci-dessus) n'est
    PAS ignorée ici (seul suite[\"si_hypothetique\"] l'est, cf.
    _extraire_suites) — un filet de sécurité reste la tentative de rejeu
    elle-même ([] lectures, donc ignoré, si la suite ne se joue d'aucune
    façon connue).

    Lectures multiples (issue #97, point 3, même principe que
    detecter_echanges_mal_qualifies) : une incohérence n'est signalée que si
    TOUTES les lectures valides de la suite (cf. _rassembler_lectures —
    positions candidates, avec ou sans le coup précédent cité, avec ou sans
    demi-coup caché) montrent qu'au moins un camp ne perd aucune pièce de ce
    type ; une seule lecture où CHAQUE camp perd bien une pièce de ce type
    suffit à ne rien signaler.

    Retourne une liste de dicts {"type": "echange_type_incoherent",
    "gravite": "orange"/"rouge" (même seuil SEUIL_ECHANGE_GRAVE_PTS que
    detecter_echanges_mal_qualifies), "detail": str}."""
    if not candidats:
        return []
    alertes = []
    for suite in _extraire_suites(texte):
        if suite["si_hypothetique"] or len(suite["coups"]) < 2:
            continue
        fenetre = _fenetre_qualificatif_echange(texte, suite)
        matches = list(_ECHANGE_DE_TYPE_RE.finditer(fenetre))
        if not matches:
            continue

        lectures = _rassembler_lectures(suite, candidats)
        if not lectures:
            continue
        deltas = [_delta_materiel(av, ap) for av, ap in lectures]
        delta_pire = max(deltas, key=abs)
        gravite = "rouge" if abs(delta_pire) >= SEUIL_ECHANGE_GRAVE_PTS else "orange"
        resume_lectures = _resume_valeurs(deltas)

        for m in matches:
            if _qualificatif_nie(fenetre, m.start()):
                continue
            piece_type = _NOM_PIECE_TYPE[m.group(1).lower()]
            pertes_par_lecture = []
            for board_avant, board_apres in lectures:
                perte_blancs = (
                    len(board_avant.pieces(piece_type, chess.WHITE))
                    - len(board_apres.pieces(piece_type, chess.WHITE))
                )
                perte_noirs = (
                    len(board_avant.pieces(piece_type, chess.BLACK))
                    - len(board_apres.pieces(piece_type, chess.BLACK))
                )
                pertes_par_lecture.append((perte_blancs, perte_noirs))
            if any(pb >= 1 and pn >= 1 for pb, pn in pertes_par_lecture):
                continue
            nom = _NOM_PIECE_AFFICHAGE[piece_type]
            perte_blancs, perte_noirs = pertes_par_lecture[0]
            camps_sans_perte = []
            if perte_blancs < 1:
                camps_sans_perte.append("les Blancs")
            if perte_noirs < 1:
                camps_sans_perte.append("les Noirs")
            alertes.append({
                "type": "echange_type_incoherent",
                "gravite": gravite,
                "detail": (
                    f"\"{m.group(0)}\" accolé à la suite citée \"{suite['texte']}\" "
                    f"prétend que chaque camp perd un(e) {nom}, alors que, dans "
                    f"TOUTES les lectures valides de cette suite ({resume_lectures}), "
                    f"{' et '.join(camps_sans_perte)} n'en perd(ent) aucun(e)"
                ),
            })
    return alertes


_BILAN_MATERIEL_RE = re.compile(
    r"\b([ée]quilibre\s+mat[ée]riel|mat[ée]riel\s+(?:reste\s+|redevient\s+)?[ée]gal|"
    r"[ée]galit[ée]\s+mat[ée]rielle)\b",
    re.IGNORECASE,
)

# Seuils (en points classiques) du contrôle "bilan matériel annoncé" (issue
# #92, tâche 3c), réglables en CE SEUL endroit — même esprit que
# SEUIL_ECHANGE_GRAVE_PTS ci-dessus, mais une échelle distincte : ce contrôle
# porte sur le bilan ABSOLU après la suite (pas sur le delta qu'elle
# provoque), une notion différente de detecter_echanges_mal_qualifies.
SEUIL_BILAN_MATERIEL_PTS = 2
SEUIL_BILAN_MATERIEL_GRAVE_PTS = 4

# Fenêtre volontairement plus large que _FENETRE_APRES_ECHANGE (une annonce
# de bilan matériel suit souvent la suite citée dans une phrase SÉPARÉE, cas
# réel : "...perd une tour. Mais après l'échange, tu récupères l'équilibre
# matériel.") — coupée au prochain saut de paragraphe plutôt qu'à la
# première fin de phrase, pour couvrir cette deuxième phrase.
_FENETRE_APRES_BILAN = 250


def _fenetre_bilan_materiel(texte: str, suite: dict) -> str:
    debut = max(0, suite["debut"] - _FENETRE_AVANT_ECHANGE)
    fin = min(len(texte), suite["fin"] + _FENETRE_APRES_BILAN)
    morceau_apres = texte[suite["fin"]:fin]
    m_paragraphe = re.search(r"\n\s*\n", morceau_apres)
    if m_paragraphe:
        fin = suite["fin"] + m_paragraphe.start()
    return texte[debut:fin]


def detecter_bilan_materiel_annonce(texte: str, candidats: list) -> list:
    """Détecte \"équilibre matériel\"/\"matériel égal\"/\"égalité "
    matérielle\" (issue #92, tâche 3c) à propos du résultat d'une suite
    d'au moins deux coups cités, quand le bilan matériel RÉEL après cette
    suite (pas le delta qu'elle provoque, le total absolu de chaque camp)
    s'écarte de SEUIL_BILAN_MATERIEL_PTS ou plus — cas réel ayant motivé
    cette tâche : \"après l'échange, tu récupères l'équilibre matériel\"
    alors que la position après la suite citée donne 14 points aux Blancs
    contre 12 aux Noirs (écart de 2).

    Même construction et même tolérance \"entre parenthèses\" que
    detecter_echange_type_incoherent ci-dessus (seul suite[\"si_hypothetique\"]
    exclut une suite, jamais suite[\"entre_parentheses\"]) — ne duplique ni
    ne recalcule la légalité des coups.

    Lectures multiples (issue #97, point 3, même principe que
    detecter_echanges_mal_qualifies) : ce contrôle porte sur le bilan
    ABSOLU de la position d'arrivée, pas sur un delta — une incohérence
    n'est signalée que si TOUTES les lectures valides de la suite (cf.
    _rassembler_lectures) donnent un écart d'au moins SEUIL_BILAN_MATERIEL_PTS ;
    une seule lecture quasi équilibrée suffit à ne rien signaler.

    Retourne une liste de dicts {"type": "bilan_materiel_incoherent",
    "gravite": "orange"/"rouge" (gravité plus forte au-delà de
    SEUIL_BILAN_MATERIEL_GRAVE_PTS), "detail": str}."""
    if not candidats:
        return []
    alertes = []
    for suite in _extraire_suites(texte):
        if suite["si_hypothetique"] or len(suite["coups"]) < 2:
            continue
        fenetre = _fenetre_bilan_materiel(texte, suite)
        matches = list(_BILAN_MATERIEL_RE.finditer(fenetre))
        if not matches:
            continue

        lectures = _rassembler_lectures(suite, candidats)
        if not lectures:
            continue
        ecarts = [
            _materiel_camp(ap, chess.WHITE) - _materiel_camp(ap, chess.BLACK)
            for _av, ap in lectures
        ]
        if any(abs(e) < SEUIL_BILAN_MATERIEL_PTS for e in ecarts):
            continue
        ecart_pire = max(ecarts, key=abs)
        camp_en_avance = "les Blancs" if ecart_pire > 0 else "les Noirs"
        gravite = "rouge" if abs(ecart_pire) >= SEUIL_BILAN_MATERIEL_GRAVE_PTS else "orange"
        resume_lectures = _resume_valeurs(ecarts)
        for m in matches:
            if _qualificatif_nie(fenetre, m.start()):
                continue
            alertes.append({
                "type": "bilan_materiel_incoherent",
                "gravite": gravite,
                "detail": (
                    f"\"{m.group(0)}\" accolé à la suite citée \"{suite['texte']}\" "
                    "annonce un bilan matériel équilibré, alors que TOUTES les "
                    f"lectures valides de cette suite, rejouée sur l'échiquier "
                    f"({resume_lectures}), donnent un écart d'au moins "
                    f"{SEUIL_BILAN_MATERIEL_PTS} point(s) — au pire, en faveur de "
                    f"{camp_en_avance} ({abs(ecart_pire)} point(s))"
                ),
            })
    return alertes


# ── Phrases d'attaque/de défense entre deux pièces (issue #98) ─────────────
# Constat ayant motivé cet ajout (cas réel, re3, essai 5 — même position que
# les contrôles d'échange ci-dessus) : la réponse corrigée par la relance
# automatique affirmait quand même "après Be5, ton fou adverse attaque la
# tour", alors que le fou noir en e5 n'attaque géométriquement PAS la tour
# blanche en e3 (il attaque a1, b2, c3, c7, d4, d6, f4, f6, g3, g7, h2, h8,
# vérifié avec python-chess) — aucun contrôle existant ne vérifie une
# affirmation d'attaque ou de défense entre deux pièces nommées.
#
# Portée volontairement limitée à une forme de phrase SIMPLE, active
# ("<pièce1> attaque/défend <pièce2>") ou passive ("<pièce2> est
# attaqué(e)/défendu(e) par <pièce1>"), reconnue par _ATTAQUE_DEFENSE_ACTIF_RE/
# _ATTAQUE_DEFENSE_PASSIF_RE — une tournure plus élaborée (relative,
# énumération de plusieurs pièces...) échappe à ce contrôle (faux négatif
# assumé, même philosophie que le reste du module).
#
# Identification des deux pièces (type + couleur + case si possible) :
#   - le type est l'un des 6 noms de pièce français (dame/tour/fou/cavalier/
#     pion/roi, singulier ou pluriel) ;
#   - la couleur n'est reconnue que via les mots explicitement cités par
#     l'issue : "adverse" (camp opposé au camp d'Alain, cf. camp_alain),
#     "noir(e)(s)"/"blanc(he)(s)" (couleur absolue), "ton"/"ta"/"tes" (camp
#     d'Alain lui-même) — "adverse" l'emporte sur "ton"/"ta" si les deux sont
#     accolés à la même pièce ("ton fou adverse", cas réel ci-dessus : la
#     couleur retenue est l'adversaire d'Alain, pas Alain) ;
#   - la case, si citée directement après la pièce (avec ou sans "en"/"sur"
#     entre les deux, ex. "le pion h2" ou "le pion en h2") sert à vérifier/
#     compléter la couleur plutôt qu'à la deviner (cf. _resoudre_piece_
#     attaque_defense) ;
#   - si ni couleur ni case ne permettent de trancher, la pièce n'est
#     identifiée sans ambiguïté QUE s'il n'existe qu'UNE SEULE pièce de ce
#     type, toutes couleurs confondues, sur la position essayée (résolution
#     par défaut) — sinon (plusieurs pièces de ce type possibles), la pièce
#     n'est pas identifiable : la phrase entière n'est jamais signalée
#     (prudence explicitement demandée par l'issue).
#
# Position(s) essayée(s) (même ordre de priorité que demandé par l'issue) :
#   - si la phrase est précédée, dans la même proposition (bornée par la
#     première fin de phrase rencontrée en remontant, cf. _fenetre_clouage),
#     d'une citation "après <coup(s)>" (ex. "après Be5,"), SEULES les
#     positions obtenues en jouant ce(s) coup(s) depuis chacune des positions
#     de `candidats` sont essayées (lecture scopée explicitement par le
#     texte) — si aucune ne permet de jouer ce(s) coup(s), rien n'est
#     signalé (la citation elle-même est hors de portée, cf. detecter_suites_
#     illegales qui a ce rôle) ;
#   - sinon, toutes les positions de `candidats` (position de départ,
#     position actuelle, après coup proposé/réel/meilleur, lignes PV...) sont
#     essayées, comme pour les autres contrôles de ce module.
# Une incohérence n'est signalée que si TOUTES les lectures valides
# (positions où les deux pièces sont identifiables sans ambiguïté)
# contredisent l'affirmation — une seule lecture cohérente suffit à ne rien
# signaler, et l'absence de toute lecture valide n'est jamais signalée non
# plus (même tolérance que le reste du module).
#
# Négation ("le fou n'attaque pas la tour") : la négation française place
# "ne"/"n'" directement avant le verbe, ce qui empêche structurellement
# _ATTAQUE_DEFENSE_ACTIF_RE/_PASSIF_RE de reconnaître la forme verbale
# attendue (adjacence stricte pièce+espace+verbe) — aucune règle de négation
# dédiée n'est donc nécessaire pour cette forme. Reste explicitement exclue
# une hypothèse introduite par "si" juste avant la pièce sujet (même
# _SI_HYPOTHETIQUE_RE que le reste du module) : "si le fou attaque la tour"
# emploie bien la forme verbale reconnue (présent de l'indicatif), sans
# qu'aucune négation ne la bloque.
#
# Gravité ("orange" par défaut, "rouge" si l'affirmation est centrale — un
# connecteur de justification de verdict comme "donc"/"c'est pourquoi" suit
# la phrase à proximité — ou répétée au moins deux fois dans le même texte
# avec la même paire pièce+couleur+relation) : heuristique volontairement
# approximative (contrairement aux seuils numériques des contrôles
# d'échange ci-dessus), documentée comme telle — une phrase centrale sans
# connecteur explicite peut donc rester "orange" à tort (faux négatif de
# gravité, jamais de faux positif de détection).
_PIECE_MOD_RE = r"adverse\w*|blancs?|blanches?|noirs?|noires?"
_PIECE_CASE_RE = r"(?:\s+(?:(?:en|sur)\s+)?([a-h][1-8])\b)?"

_ATTAQUE_DEFENSE_ACTIF_RE = re.compile(
    r"\b(?:(?P<p1_ton>ton|ta|tes)\s+)?"
    r"(?P<p1_type>dames?|tours?|fous?|cavaliers?|pions?|rois?)"
    rf"(?:\s+(?P<p1_mod>{_PIECE_MOD_RE}))?"
    rf"(?:\s+(?:(?:en|sur)\s+)?(?P<p1_case>[a-h][1-8])\b)?"
    r"\s+(?P<verbe>attaques?|attaquent|d[ée]fends?|d[ée]fendent)\s+"
    r"(?:(?:le|la|les)\s+)?(?:(?P<p2_ton>ton|ta|tes)\s+)?"
    r"(?P<p2_type>dames?|tours?|fous?|cavaliers?|pions?|rois?)"
    rf"(?:\s+(?P<p2_mod>{_PIECE_MOD_RE}))?"
    rf"(?:\s+(?:(?:en|sur)\s+)?(?P<p2_case>[a-h][1-8])\b)?",
    re.IGNORECASE,
)
_ATTAQUE_DEFENSE_PASSIF_RE = re.compile(
    r"\b(?:(?:le|la|les)\s+)?(?:(?P<p2_ton>ton|ta|tes)\s+)?"
    r"(?P<p2_type>dames?|tours?|fous?|cavaliers?|pions?|rois?)"
    rf"(?:\s+(?P<p2_mod>{_PIECE_MOD_RE}))?"
    rf"(?:\s+(?:(?:en|sur)\s+)?(?P<p2_case>[a-h][1-8])\b)?"
    r"\s+(?:est|sont)\s+(?P<verbe>attaqu[ée]e?s?|d[ée]fendue?s?)\s+par\s+"
    r"(?:(?:le|la|les)\s+)?(?:(?P<p1_ton>ton|ta|tes)\s+)?"
    r"(?P<p1_type>dames?|tours?|fous?|cavaliers?|pions?|rois?)"
    rf"(?:\s+(?P<p1_mod>{_PIECE_MOD_RE}))?"
    rf"(?:\s+(?:(?:en|sur)\s+)?(?P<p1_case>[a-h][1-8])\b)?",
    re.IGNORECASE,
)

_APRES_CITATION_RE = re.compile(r"\bapr[eè]s\s+", re.IGNORECASE)
_FENETRE_APRES_CITATION = 80

_CONNECTEUR_VERDICT_RE = re.compile(
    r"\b(donc|c'est pourquoi|ce qui (?:explique|justifie)|voil[àa] pourquoi|"
    r"d'o[uù]|par cons[ée]quent)\b",
    re.IGNORECASE,
)
_FENETRE_CONNECTEUR_VERDICT = 100


def _camp_alain_chess(camp_alain: str):
    if camp_alain == "blancs":
        return chess.WHITE
    if camp_alain == "noirs":
        return chess.BLACK
    return None


def _resoudre_couleur_attaque_defense(mod: str, ton: str, camp_alain_couleur) -> object:
    """Résout la couleur d'une pièce mentionnée dans une phrase d'attaque/
    défense depuis les seuls indices TEXTUELS (jamais depuis la position —
    cf. _resoudre_piece_attaque_defense pour le repli sur la position) :
    "adverse" (camp opposé à camp_alain_couleur) l'emporte sur "ton"/"ta"/
    "tes" (camp_alain_couleur lui-même) si les deux sont présents ; "noir(e)
    (s)"/"blanc(he)(s)" donnent directement une couleur absolue. Retourne
    None si aucun indice n'est présent, ou si "adverse"/"ton" est présent
    mais camp_alain_couleur est inconnu (impossible de résoudre sans le camp
    d'Alain)."""
    if mod:
        m = mod.lower()
        if m.startswith("adverse"):
            return None if camp_alain_couleur is None else not camp_alain_couleur
        if m.startswith("blanc"):
            return chess.WHITE
        if m.startswith("noir"):
            return chess.BLACK
    if ton:
        return None if camp_alain_couleur is None else camp_alain_couleur
    return None


def _resoudre_piece_attaque_defense(piece_type: int, couleur_texte, case_citee, board: "chess.Board"):
    """Résout la case ET la couleur d'une pièce (type `piece_type`) citée
    dans une phrase d'attaque/défense, sur `board` (issue #98) :
      - case_citee connue : la pièce RÉELLEMENT présente sur cette case doit
        être du type attendu (et de la couleur attendue si `couleur_texte`
        est connu) — la case est alors AUTORITAIRE, elle peut donner la
        couleur même si le texte n'en citait aucune ;
      - sinon, couleur_texte connue : la pièce doit être la SEULE de ce type
        ET cette couleur sur `board` ;
      - sinon (ni case ni couleur) : la pièce doit être la SEULE de ce type,
        TOUTES COULEURS confondues, sur `board` — résolution par défaut
        tant qu'elle reste sans ambiguïté (cf. cas réel "la tour", issue
        #98 : une seule tour sur l'échiquier après Re3 Be5, donc résolue
        sans qu'aucun mot de couleur ne soit cité).
    Retourne (case: int, couleur: bool) si résolu sans ambiguïté, None
    sinon (cette position ne fournit simplement pas de lecture pour cette
    pièce — pas une preuve de contradiction, cf. appelant)."""
    if case_citee is not None:
        p = board.piece_at(case_citee)
        if p is None or p.piece_type != piece_type:
            return None
        if couleur_texte is not None and p.color != couleur_texte:
            return None
        return (case_citee, p.color)
    if couleur_texte is not None:
        cases = board.pieces(piece_type, couleur_texte)
        if len(cases) == 1:
            return (next(iter(cases)), couleur_texte)
        return None
    cases_blanches = board.pieces(piece_type, chess.WHITE)
    cases_noires = board.pieces(piece_type, chess.BLACK)
    if len(cases_blanches) + len(cases_noires) == 1:
        if cases_blanches:
            return (next(iter(cases_blanches)), chess.WHITE)
        return (next(iter(cases_noires)), chess.BLACK)
    return None


def _coups_apres_citation_proche(texte: str, position: int) -> list:
    """Cherche, dans les _FENETRE_APRES_CITATION caractères qui précèdent
    `position` (bornés par la première fin de phrase rencontrée en
    remontant, même principe que _coup_precedent_cite), la DERNIÈRE citation
    "après <coup(s)>" (ex. "après Be5,") — retourne la liste de coups SAN
    cités juste après ce mot (même regroupement que _extraire_suites), []
    si aucune trouvée dans cette fenêtre."""
    debut = max(0, position - _FENETRE_APRES_CITATION)
    morceau = texte[debut:position]
    derniere_frontiere = None
    for mm in re.finditer(r"[.\n!?]", morceau):
        derniere_frontiere = mm.end()
    if derniere_frontiere is not None:
        morceau = morceau[derniere_frontiere:]
    occurrences = list(_APRES_CITATION_RE.finditer(morceau))
    if not occurrences:
        return []
    reste = morceau[occurrences[-1].end():]
    candidats_coups = [
        mm for mm in _SAN_RE.finditer(reste)
        if not _CASE_SEULE_RE.match(mm.group(1))
    ]
    coups = []
    fin_courante = 0
    for mm in candidats_coups:
        if coups and not _SEPARATEUR_SUITE_RE.match(reste[fin_courante:mm.start()]):
            break
        coups.append(mm.group(1))
        fin_courante = mm.end()
    return coups


def _candidats_apres_citation(coups: list, candidats: list) -> list:
    resultats = []
    for label, board in candidats:
        board_apres = _jouer_suite(coups, board)
        if board_apres is not None:
            resultats.append((f"après {' '.join(coups)} depuis {label}", board_apres))
    return resultats


_PIECES_FEMININES = {chess.QUEEN, chess.ROOK}


def _decrire_piece_genre(piece_type: int, couleur: bool) -> str:
    """"le fou noir"/"la tour blanche" — accord de genre pour le journal
    (issue #98, purement cosmétique, aucun impact sur la détection)."""
    nom = _NOM_PIECE_AFFICHAGE[piece_type]
    feminin = piece_type in _PIECES_FEMININES
    article = "la" if feminin else "le"
    adjectif = ("blanche" if feminin else "blanc") if couleur == chess.WHITE else "noire" if feminin else "noir"
    return f"{article} {nom} {adjectif}"


def detecter_attaque_defense_incoherente(texte: str, candidats: list, camp_alain: str = "") -> list:
    """Détecte une phrase simple, active ("<pièce1> attaque/défend <pièce2>")
    ou passive ("<pièce2> est attaqué(e)/défendu(e) par <pièce1>"), issue
    #98, dont TOUTES les lectures valides (positions où les deux pièces sont
    identifiables sans ambiguïté, cf. _resoudre_piece_attaque_defense)
    contredisent la relation géométrique réelle (python-chess, Board.attacks)
    — une "défense" exige en outre que les deux pièces soient du MÊME camp
    (sinon ce n'est pas une défense, quelle que soit la géométrie). Cas de
    référence ayant motivé ce contrôle : "après Be5, ton fou adverse attaque
    la tour" est faux (le fou noir en e5 n'attaque pas la tour blanche en
    e3) — cf. commentaire ci-dessus pour la portée complète (identification
    des pièces, positions essayées, négation/hypothèse, gravité).

    `camp_alain` : "blancs"/"noirs" (même convention que le reste du projet),
    "" si inconnu — sert uniquement à résoudre "adverse"/"ton"/"ta"/"tes"
    (cf. _resoudre_couleur_attaque_defense) ; sans lui, ces mots ne résolvent
    aucune couleur (ni preuve ni contradiction, la pièce reste simplement
    inidentifiable par ce biais).

    Retourne une liste de dicts {"type": "attaque_defense_incoherente",
    "gravite": "orange"/"rouge", "detail": str}."""
    if not candidats:
        return []
    camp_alain_couleur = _camp_alain_chess(camp_alain)
    alertes = []
    compte_repetition: dict = {}

    for regex in (_ATTAQUE_DEFENSE_ACTIF_RE, _ATTAQUE_DEFENSE_PASSIF_RE):
        for m in regex.finditer(texte):
            p1_type = _NOM_PIECE_TYPE.get(m.group("p1_type").lower())
            p2_type = _NOM_PIECE_TYPE.get(m.group("p2_type").lower())
            if p1_type is None or p2_type is None:
                continue

            avant = texte[max(0, m.start() - 40):m.start()]
            if _SI_HYPOTHETIQUE_RE.search(avant):
                continue

            verbe = m.group("verbe").lower()
            relation = "attaque" if verbe.startswith("attaqu") else "defend"
            couleur1 = _resoudre_couleur_attaque_defense(m.group("p1_mod"), m.group("p1_ton"), camp_alain_couleur)
            couleur2 = _resoudre_couleur_attaque_defense(m.group("p2_mod"), m.group("p2_ton"), camp_alain_couleur)
            case1 = chess.parse_square(m.group("p1_case").lower()) if m.group("p1_case") else None
            case2 = chess.parse_square(m.group("p2_case").lower()) if m.group("p2_case") else None

            coups_apres = _coups_apres_citation_proche(texte, m.start())
            if coups_apres:
                candidats_phrase = _candidats_apres_citation(coups_apres, candidats)
                if not candidats_phrase:
                    continue
            else:
                candidats_phrase = candidats

            lectures = []
            for _label, board in candidats_phrase:
                r1 = _resoudre_piece_attaque_defense(p1_type, couleur1, case1, board)
                r2 = _resoudre_piece_attaque_defense(p2_type, couleur2, case2, board)
                if r1 is None or r2 is None:
                    continue
                sq1, col1 = r1
                sq2, col2 = r2
                if relation == "attaque":
                    vrai = sq2 in board.attacks(sq1)
                else:
                    vrai = col1 == col2 and sq2 in board.attacks(sq1)
                lectures.append((sq1, col1, sq2, col2, vrai))

            if not lectures or any(l[4] for l in lectures):
                continue

            sq1_0, col1_0, sq2_0, col2_0, _ = lectures[0]
            desc1 = _decrire_piece_genre(p1_type, col1_0)
            desc2 = _decrire_piece_genre(p2_type, col2_0)
            verbe_txt = "attaque" if relation == "attaque" else "défend"
            detail = (
                f"\"{m.group(0).strip()}\" affirme que {desc1} "
                f"({chess.square_name(sq1_0)}) {verbe_txt} {desc2} "
                f"({chess.square_name(sq2_0)}), contredit par les "
                f"{len(lectures)} lecture(s) valide(s) disponible(s) (aucune "
                f"ne confirme cette {'attaque' if relation == 'attaque' else 'défense'})"
            )
            fenetre_connecteur = texte[m.end():m.end() + _FENETRE_CONNECTEUR_VERDICT]
            central = bool(_CONNECTEUR_VERDICT_RE.search(fenetre_connecteur))
            cle_repetition = (p1_type, col1_0, p2_type, col2_0, relation)
            compte_repetition[cle_repetition] = compte_repetition.get(cle_repetition, 0) + 1
            alertes.append({
                "type": "attaque_defense_incoherente",
                "detail": detail,
                "_central": central,
                "_cle_repetition": cle_repetition,
            })

    for a in alertes:
        repetee = compte_repetition[a["_cle_repetition"]] >= 2
        a["gravite"] = "rouge" if (a.pop("_central") or repetee) else "orange"
        a.pop("_cle_repetition")
    return alertes


def evaluer_fiabilite(texte: str, fen_reference: str = "", fen_reference2: str = "",
                       analyse_indisponible: bool = False, verdict_partiel: bool = False,
                       coup_propose: str = "", coup_reel: str = "", meilleur_coup: str = "",
                       pv_coup_propose: str = "", pv_meilleur_coup: str = "",
                       camp_alain: str = "") -> dict:
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
    camp_alain (issue #98) : "blancs"/"noirs" (même convention que le reste
    du projet), "" si inconnu — sert uniquement à detecter_attaque_defense_
    incoherente, pour résoudre "adverse"/"ton"/"ta"/"tes" dans une phrase
    d'attaque/défense ; sans lui, ce contrôle reste actif mais ces mots ne
    résolvent simplement aucune couleur.

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
        "cohérence matérielle des échanges cités (issue #91, étendu par "
        "l'issue #97) : une suite d'au moins deux captures citées, "
        "qualifiée \"équilibré(e)\" ou \"favorable\"/\"défavorable\" (ce "
        "dernier couple seulement si un camp Blancs/Noirs est explicitement "
        "mentionné à proximité), est rejouée sur l'échiquier — un coup noté "
        "avec un \"x\" doit être une vraie prise (en passant comprise), "
        "sinon il est rejeté pour cette lecture (issue #97, point 1) — et "
        "TOUTES les lectures valides de la suite (positions candidates, "
        "avec ou sans le coup cité juste avant une parenthèse, avec ou sans "
        "demi-coup caché, issue #97, points 2 et 3) sont comparées au "
        "qualificatif employé : une incohérence n'est signalée que si "
        "AUCUNE lecture valide n'est cohérente avec le texte (limite : les "
        "verbes \"gagne\"/\"perd\", trop généraux en français pour être "
        "associés avec confiance à la suite citée, ne sont volontairement "
        "PAS vérifiés — ni un qualificatif sans camp explicite pour "
        "\"favorable\"/\"défavorable\" — faux négatifs assumés, cf. "
        "coach_reliability.py)",
        "clouage annoncé (issue #92) : une pièce citée \"<type> [<couleur>] "
        "en/sur <case>\" dite clouée (mot de la famille \"clou...\" dans la "
        "même phrase) est comparée à python-chess (Board.is_pinned) sur la "
        "position de départ, la position actuelle et chaque étape des "
        "lignes/suites citées — signalée seulement si elle n'est clouée "
        "nulle part (limite : la couleur n'a pas besoin d'être explicite, "
        "la case suffit à l'identifier sans ambiguïté via les positions de "
        "référence ; une pièce non identifiable ainsi, ou un mot de clouage "
        "hors de la même phrase, n'est jamais contrôlée)",
        "« échange de X » cité (issue #92) : une suite d'au moins deux "
        "coups cités qualifiée \"échange de dames\"/\"de tours\"/\"de "
        "fous\"/\"de cavaliers\" est rejouée sur l'échiquier et comparée au "
        "nombre de pièces de ce type précis réellement perdues par CHAQUE "
        "camp (limite : ne couvre que la forme \"échange de <type>\", pas "
        "une tournure équivalente comme \"ils échangent leurs dames\")",
        "bilan matériel annoncé (issue #92) : \"équilibre matériel\"/"
        "\"matériel égal\"/\"égalité matérielle\" à propos du résultat "
        "d'une suite citée est comparé au bilan matériel RÉEL (total "
        "absolu de chaque camp, pas le delta provoqué) après cette suite, "
        "rejouée sur l'échiquier — signalé si l'écart atteint "
        "SEUIL_BILAN_MATERIEL_PTS (2 points), gravité plus forte au-delà "
        "de SEUIL_BILAN_MATERIEL_GRAVE_PTS (4 points), réglables en ce "
        "seul endroit (limite : seules ces trois formulations précises "
        "sont reconnues)",
        "attaque/défense entre deux pièces citées (issue #98) : une phrase "
        "simple, active (\"<pièce1> attaque/défend <pièce2>\") ou passive "
        "(\"<pièce2> est attaqué(e)/défendu(e) par <pièce1>\"), est comparée "
        "à la géométrie réelle (python-chess, Board.attacks) sur la "
        "position qui suit une citation \"après <coup(s)>\" juste avant la "
        "phrase si elle existe, sinon sur toutes les positions candidates "
        "habituelles — signalée seulement si AUCUNE lecture valide ne "
        "confirme l'affirmation (limite : les deux pièces doivent être "
        "identifiables sans ambiguïté — par une case citée, par un mot de "
        "couleur \"adverse\"/\"noir\"/\"blanc\"/\"ton\"/\"ta\"/\"tes\", ou, à "
        "défaut, en étant la SEULE pièce de ce type sur la position essayée "
        "— une tournure plus élaborée que la forme simple reconnue, ou une "
        "pièce non identifiable ainsi, n'est jamais contrôlée ; gravité "
        "\"rouge\" seulement si un connecteur de justification de verdict "
        "suit à proximité ou si la même affirmation se répète, sinon "
        "\"orange\" — heuristique approximative, cf. coach_reliability.py)",
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
    alertes += detecter_echanges_mal_qualifies(texte, candidats_suites)
    alertes += detecter_clouage_errone(texte, boards_reference, candidats_suites)
    alertes += detecter_echange_type_incoherent(texte, candidats_suites)
    alertes += detecter_bilan_materiel_annonce(texte, candidats_suites)
    alertes += detecter_attaque_defense_incoherente(texte, candidats_suites, camp_alain)

    if alertes:
        premiere = alertes[0]["detail"]
        # Gravité par alerte (issue #91) : seules les alertes "echange_mal_
        # qualifie" portent un champ "gravite" explicite (cf. ci-dessus) —
        # toute alerte SANS ce champ (types déjà présents avant l'issue #91)
        # reste traitée comme avant, implicitement grave (couleur rouge),
        # pour ne jamais adoucir leur traitement existant. La couleur ne
        # descend à orange que si TOUTES les alertes de ce texte sont
        # explicitement de gravité "orange".
        couleur = "orange" if alertes and all(a.get("gravite") == "orange" for a in alertes) else "rouge"
        return {
            "couleur": couleur,
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
