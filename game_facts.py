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

Ajouté par l'issue #80, constat en usage réel sur le mode "Exercice" (coup
h4, position avec un pion h3 attaqué par un pion g4 et par la dame adverse) :
le coach avait présenté un coup purement défensif comme une "expansion
offensive", puis — relancé sur la menace réelle — avait affirmé qu'un pion
protégeait à tort une case qu'il n'attaque pas, recopié le FEN de mémoire
avec une erreur de transcription, et fini par déclarer ce FEN invalide :
  - describe_pieces_lists : liste des pièces de chaque camp par case pour une
    position FEN isolée (même présentation que _liste_pieces/
    build_game_facts_text), réutilisable par le mode "Exercice" qui ne rejoue
    aucun PGN ;
  - _decrit_coup_mecanique enrichie (_attaques_defenses_arrivee/
    _resultat_echange_case/_pieces_amies_changement_attaque) : attaques et
    défenses de la case d'arrivée d'un coup, résultat de l'échange si la
    pièce qui vient de jouer est attaquée, et pièces amies qui gagnent ou
    perdent l'attaque adverse ailleurs sur l'échiquier — propagée
    automatiquement à describe_move_mechanically/describe_pv_mechanically/
    describe_pv_with_balance, donc à tout coup cité (proposé, réel, meilleur,
    PV) ;
  - describe_menace_adverse : formate en texte de contexte le résultat de
    EngineManager.get_threats (menace adverse via coup nul, calculée côté
    app.py) — menace(s) décrite(s) mécaniquement, évaluation résultante et
    perte d'avantage par rapport au meilleur coup, avec un seuil de gravité
    réglable (SEUIL_MENACE_SIGNIFICATIVE_CP) ;
  - build_idees_coup/format_idees_coup : idées détectées pour un coup cité,
    combinant les variations de la décomposition classique de l'évaluation
    Stockfish (EngineManager.get_eval_breakdown, calculée côté app.py) au-delà
    de SEUIL_IDEE_PION, traduites en français, et des idées mécaniques
    (parade d'une menace, échec/mat, développement/centralisation) — liste
    courte (3 au plus), triée par importance, jamais de valeur chiffrée.

Ajouté par l'issue #87, constat sur un exercice réel (mode "Exercice", coup
Re3 dans une position Q7/ppkq3p/2p3n1/2Pp1p2/1P6/2b5/P5PP/4R2K w - - 9 35) :
les données transmises étaient exactes (listes de pièces, description
mécanique des coups), mais le coach a quand même parlé d'un "échange tour
contre tour" (un seul camp avait une tour) et affirmé qu'un fou en e5
attaquait une tour en e3 (géométriquement faux) — les données ne CONTREDISAIENT
pas ces inventions, elles se contentaient de ne pas les couvrir :
  - describe_material_summary : résumé du matériel de chaque camp par type de
    pièce, avec les absences dites explicitement ("aucune tour") plutôt que
    silencieuses, le total en points et l'équilibre matériel — généralise les
    deux lignes "n'a plus de dame" déjà présentes dans build_game_facts_text ;
  - _statut_attaque_case, utilisée par describe_pv_with_balance pour le
    second demi-coup de toute ligne (la réponse adverse immédiate au coup
    proposé ou au meilleur coup) : dit TOUJOURS explicitement si la pièce qui
    vient de jouer au premier demi-coup est désormais attaquée ou non, là où
    les descriptions mécaniques existantes ne mentionnaient une pièce que
    lorsqu'elle était attaquée (silence total sinon, jamais une négation
    explicite).
"""

import io
import logging
import re

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

# Seuil de magnitude (centipawns) au-delà duquel une évaluation ou une perte
# Stockfish n'est plus un nombre de pions interprétable (issue #75, point 1)
# — même valeur que SEUIL_DEJA_DECISIF dans build_patterns_erreurs.py et
# SEUIL_DECIDE dans engine_stockfish.py. Constat réel (audit de 18 appels du
# mode exercice) : des valeurs de gain forcé (19974, 3456 centipawns, soit
# "+199,74"/"+34,56" pions) citées telles quelles par le coach, alors que
# Stockfish peut reporter plusieurs milliers de centipawns dans une position
# de gain forcé pas encore détectée comme un mat (score NNUE non borné, à la
# différence d'un nombre de pions réel). describe_eval_alain_cp_clause /
# describe_perte_cp_clause reformulent systématiquement ces valeurs en mots
# au-delà de ce seuil, jamais en nombre.
SEUIL_GRANDE_VALEUR_CP = 1000

# Seuil de perte d'avantage (centipawns), au-delà duquel une menace adverse
# calculée par EngineManager.get_threats (issue #80, point 1) est jugée
# "significative" — réglable en ce seul endroit, réutilisé à la fois pour la
# présentation (describe_menace_adverse ci-dessous) et pour la règle de
# prompt qui impose d'expliquer la menace avant le reste (llm_coach.py,
# _EXERCISE_SYSTEM_ADDENDUM). Valeur choisie dans l'ordre de grandeur demandé
# par l'issue ("perte d'avantage supérieure à environ 100 centipions").
SEUIL_MENACE_SIGNIFICATIVE_CP = 100

# Seuil de variation (en pions) d'un terme de la décomposition classique de
# l'évaluation Stockfish ("Contributing terms for the classical eval", issue
# #80, point 5) au-delà duquel cette variation est retenue comme une "idée"
# du coup — réglable en ce seul endroit (cf. diff_idees_evaluation).
SEUIL_IDEE_PION = 0.3

# Seuil (en points classiques) en deçà duquel le solde net d'une suite de
# capture/reprise immédiate (_resultat_echange_case) est qualifié
# "équilibré" plutôt que "gain net"/"perte nette" explicite — réglable en ce
# seul endroit (issue #94, point 1). Constat ayant motivé cette issue : le
# coach a qualifié "échange équilibré" un cas où les Noirs perdaient leur
# dame contre un pion (solde net de 8 points), parce que la description
# mécanique transmise disait elle-même "échange favorable ou équilibré" —
# une étiquette trop floue pour empêcher le coach de retenir la lecture la
# plus optimiste. Les valeurs de pièces (_VALEURS ci-dessus) étant toutes
# entières, un solde "proche de zéro" ne peut en pratique être qu'exactement
# nul pour une reprise immédiate unique — ce seuil reste à 0 par défaut.
SEUIL_ECHANGE_EQUILIBRE_PTS = 0

# Nombre maximal de coups distincts traités quand Alain en interroge un ou
# plusieurs précisément dans sa question (ex. "et Bxh7+ ?", issue #96,
# cf. detect_moves_in_text/build_coups_interroges_texte) — réglable en ce
# seul endroit, avec MAX_CARACTERES_COUP_QUESTION ci-dessous pour la
# longueur du texte produit par coup.
MAX_COUPS_QUESTION = 3

# Longueur maximale (en caractères) du texte produit pour UN coup interrogé
# (issue #96) — au-delà, le texte est tronqué ("…") plutôt que de gonfler
# indéfiniment le contexte envoyé au coach (ex. un coup légal sur de
# nombreuses positions testées).
MAX_CARACTERES_COUP_QUESTION = 700


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


def _resultat_echange_case(board_apres: "chess.Board", case: int, camp_alain: str = "") -> str:
    """Si la pièce qui vient d'arriver en `case` (sur board_apres) est
    attaquée par l'adversaire, décrit le résultat si cet adversaire la
    capture (attaquant le moins cher d'abord — hypothèse d'échange standard
    —, puis reprise mécanique éventuelle comme _solde_net_apres_capture) —
    issue #80, point 2. Chaîne vide si la pièce n'est pas attaquée, ou si la
    capture géométriquement possible s'avère en fait illégale (clouage...).

    Réécrit par l'issue #94, point 1 : l'ancienne étiquette unique "échange
    favorable ou équilibré pour <camp>" couvrait aussi bien un vrai
    équilibre matériel qu'une dame gagnée contre un pion — trop floue pour
    empêcher le coach de retenir "équilibré" dans ce dernier cas (constat
    réel, cas h4). Le résultat est désormais toujours chiffré : "échange
    équilibré" seulement si le solde net est dans SEUIL_ECHANGE_EQUILIBRE_PTS
    de zéro, sinon "gain net"/"perte nette" de ce solde pour le camp qui
    possédait la pièce initialement attaquée (camp_piece), accompagné d'une
    phrase courte disant ce qui est pris et donné."""
    piece = board_apres.piece_at(case)
    if piece is None:
        return ""
    attaquants = sorted(
        board_apres.attackers(not piece.color, case),
        key=lambda sq: _VALEURS.get(board_apres.piece_at(sq).piece_type, 0),
    )
    if not attaquants:
        return ""
    coup_capture = chess.Move(attaquants[0], case)
    if coup_capture not in board_apres.legal_moves:
        return ""
    piece_attaquante = board_apres.piece_at(attaquants[0])
    nom_piece_attaquante = _nom_piece_capturee(piece_attaquante.piece_type)
    board_echange = board_apres.copy()
    try:
        san_capture = board_echange.san(coup_capture)
    except Exception:
        san_capture = coup_capture.uci()
    board_echange.push(coup_capture)
    variation = _VALEURS.get(piece.piece_type, 0)
    solde_net = _solde_net_apres_capture(board_echange, case, variation)
    recapture_move = _premier_coup_vers(board_echange, case)
    nom_piece_perdue = _nom_piece_capturee(piece.piece_type)
    camp_piece = camp_label(piece.color, camp_alain)
    if recapture_move is None or solde_net is None:
        return (
            f" : {san_capture} perdrait {nom_piece_perdue} ({variation} point(s)), "
            f"aucune reprise possible : perte nette de {variation} point(s) pour {camp_piece}"
        )
    try:
        san_recapture = board_echange.san(recapture_move)
    except Exception:
        san_recapture = recapture_move.uci()
    if solde_net > SEUIL_ECHANGE_EQUILIBRE_PTS:
        bilan = (
            f"{camp_label(not piece.color, camp_alain)} prennent {nom_piece_perdue} puis perdent "
            f"{nom_piece_attaquante} en reprise : gain net de {solde_net} point(s) pour {camp_piece}"
        )
    elif solde_net < -SEUIL_ECHANGE_EQUILIBRE_PTS:
        bilan = (
            f"{camp_piece} perdent {nom_piece_perdue} contre {nom_piece_attaquante} : "
            f"perte nette de {-solde_net} point(s) pour {camp_piece}"
        )
    else:
        bilan = "échange équilibré"
    return f" : {san_capture} {san_recapture}, {bilan}"


def _statut_attaque_case(board_apres: "chess.Board", case: int, camp_piece,
                          camp_alain: str = "") -> str:
    """Statut explicite (attaqué ou PAS attaqué) d'une pièce amie restée sur
    `case` après la réponse adverse immédiate d'une ligne principale (issue
    #87, point 2) — comble un angle mort réel : une description mécanique ne
    mentionne une pièce QUE quand elle est attaquée (_pieces_attaquees_apres
    ci-dessus), jamais quand elle ne l'est PAS. Un coach a déjà affirmé
    qu'une tour restée immobile était "désormais attaquée" par un fou qui
    venait de jouer sur une case ne l'attaquant géométriquement pas — les
    données transmises ne mentionnaient simplement pas cette tour (silence,
    pas une négation explicite), ce qui n'empêchait pas l'invention. Cette
    fonction dit toujours explicitement l'un ou l'autre.

    `camp_piece` : couleur (chess.WHITE/chess.BLACK) de la pièce dont on
    vérifie le statut sur `case` — si elle n'y est plus (capturée, ou a
    bougé depuis, déjà décrit ailleurs) ou si camp_piece est None, retourne
    une chaîne vide plutôt qu'une supposition."""
    if camp_piece is None:
        return ""
    piece = board_apres.piece_at(case)
    if piece is None or piece.color != camp_piece:
        return ""
    nom = f"{_NOM_PIECE_MAJ[piece.piece_type]} {_couleur_accordee(piece.piece_type, piece.color)} en {chess.square_name(case)}"
    attaquants = sorted(board_apres.attackers(not piece.color, case))
    if not attaquants:
        return f"{nom} n'est PAS attaqué(e) par ce coup"
    noms_attaquants = ", ".join(
        f"{_NOM_PIECE_MAJ[board_apres.piece_at(sq).piece_type]} {chess.square_name(sq)}"
        for sq in attaquants
    )
    echange = _resultat_echange_case(board_apres, case, camp_alain)
    return f"{nom} est désormais attaqué(e) par {noms_attaquants}{echange}"


def _attaques_defenses_arrivee(board: "chess.Board", board_apres: "chess.Board",
                                move: "chess.Move", camp_alain: str = "") -> str:
    """Décrit, pour la pièce qui vient de jouer, les attaques/défenses de sa
    case d'arrivée et les anciens attaquants de sa case de DÉPART qui ne
    l'atteignent plus depuis qu'elle a bougé (issue #80, point 2 — exemple
    attendu : "le pion blanc de h3... passe en h4 ; en h4, il n'est plus
    attaqué par le pion g4 ; la dame h5 l'attaque encore mais il est défendu
    par le pion g3"). Chaîne vide si rien à signaler."""
    piece = board_apres.piece_at(move.to_square)
    if piece is None:
        return ""
    segs = []
    attaquants_apres = set(board_apres.attackers(not piece.color, move.to_square))
    if attaquants_apres:
        noms_attaquants = ", ".join(
            f"{_NOM_PIECE_MAJ[board_apres.piece_at(sq).piece_type]} {chess.square_name(sq)}"
            for sq in sorted(attaquants_apres)
        )
        defenseurs = sorted(board_apres.attackers(piece.color, move.to_square))
        if defenseurs:
            noms_defenseurs = ", ".join(
                f"{_NOM_PIECE_MAJ[board_apres.piece_at(sq).piece_type]} {chess.square_name(sq)}"
                for sq in defenseurs
            )
            echange = _resultat_echange_case(board_apres, move.to_square, camp_alain)
            segs.append(
                f"en {chess.square_name(move.to_square)}, attaqué(e) par {noms_attaquants}, "
                f"défendu(e) par {noms_defenseurs}{echange}"
            )
        else:
            segs.append(
                f"en {chess.square_name(move.to_square)}, attaqué(e) par {noms_attaquants}, SANS défense"
            )
    attaquants_avant = set(board.attackers(not piece.color, move.from_square))
    disparus = sorted(
        sq for sq in attaquants_avant
        if sq not in attaquants_apres and board_apres.piece_at(sq) is not None
    )
    if disparus:
        noms_disparus = ", ".join(
            f"{_NOM_PIECE_MAJ[board_apres.piece_at(sq).piece_type]} {chess.square_name(sq)}"
            for sq in disparus
        )
        segs.append(f"n'est plus attaqué(e) par {noms_disparus}")
    return " ; ".join(segs)


def _pieces_amies_changement_attaque(board: "chess.Board", board_apres: "chess.Board",
                                      move: "chess.Move", max_items: int = 3) -> str:
    """Pièces amies (même camp que la pièce qui vient de jouer), hors sa
    case de départ/arrivée (déjà couvertes par _attaques_defenses_arrivee),
    dont le statut d'attaque par l'adversaire change entre AVANT et APRÈS ce
    coup — attaque découverte ou pièce mise à l'abri (issue #80, point 2).
    Limité à `max_items` par liste pour ne pas gonfler le contexte."""
    piece = board.piece_at(move.from_square)
    if piece is None:
        return ""
    exclues = {move.from_square, move.to_square}
    plus_protegees, plus_attaquees = [], []
    for sq in chess.SQUARES:
        if sq in exclues:
            continue
        p_avant = board.piece_at(sq)
        if p_avant is None or p_avant.color != piece.color:
            continue
        p_apres = board_apres.piece_at(sq)
        if p_apres is None or p_apres.piece_type != p_avant.piece_type or p_apres.color != p_avant.color:
            continue
        etait = board.is_attacked_by(not piece.color, sq)
        est = board_apres.is_attacked_by(not piece.color, sq)
        nom = f"{_NOM_PIECE_MAJ[p_avant.piece_type]} {chess.square_name(sq)}"
        if etait and not est:
            plus_protegees.append(nom)
        elif not etait and est:
            plus_attaquees.append(nom)
    segs = []
    if plus_protegees:
        segs.append(f"n'est/ne sont plus attaqué(e)(s) : {', '.join(plus_protegees[:max_items])}")
    if plus_attaquees:
        segs.append(f"désormais attaqué(e)(s) (découvert) : {', '.join(plus_attaquees[:max_items])}")
    return " ; ".join(segs)


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

    # Attaques/défenses de la case d'arrivée et pièces amies dont le statut
    # d'attaque change ailleurs (issue #80, point 2) — omis sur un mat (plus
    # aucun coup adverse possible ensuite, l'échange hypothétique n'a plus de
    # sens) pour ne pas gonfler inutilement une description déjà conclusive.
    if not board_apres.is_checkmate():
        arrivee_txt = _attaques_defenses_arrivee(board, board_apres, move, camp_alain)
        if arrivee_txt:
            segs.append(arrivee_txt)
        amies_txt = _pieces_amies_changement_attaque(board, board_apres, move)
        if amies_txt:
            segs.append(amies_txt)

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


# --- Coup précis interrogé par Alain dans sa question (issue #96) --------
#
# Cas réel ayant motivé cette section (signalement d'Alain, 2 octobre 2026,
# mode Exercice) : FEN r2q1rk1/pppbbppp/2n2n2/3p2N1/3P4/3BB3/PPP1QPPP/
# RN2K2R b KQ - 11 9, question "et Bxh7+ ?" — le coach, sans AUCUNE donnée
# sur ce coup, a répondu qu'il ne voyait pas cette idée et a laissé Alain
# sans explication, alors que Bxh7+ existe pour les Blancs dans la position
# de départ (mauvais : Nxh7 Nxh7 Kxh7, environ -3,6) mais devient impossible
# après g6 ou Ne4 (diagonale d3-h7 bloquée) et reste légal mais sans effet
# après Nb4. Les fonctions ci-dessous détectent un coup mentionné dans le
# texte d'Alain (SAN ou case à case), testent sa légalité position par
# position — y compris quand c'est le trait de l'AUTRE camp dans cette
# position précise (ex. Bxh7+ est un coup blanc posé alors que les Noirs
# ont le trait dans la position de départ de l'exercice) — et produisent,
# pour chaque position, soit une description mécanique + l'évaluation
# Stockfish (si légal), soit une phrase mécanique expliquant pourquoi il ne
# l'est pas (ligne bloquée, pièce absente ou déplacée, case occupée...).
# Jamais un appel Stockfish ici (cf. en-tête de module) : `evaluateur`,
# injecté par l'appelant (app.py, seul détenteur de EngineManager), est un
# callback optionnel (fen, chess.Move) -> dict compatible avec
# app.py._evaluate_move_for_coach.

_PIECE_LETTRE = {"K": chess.KING, "Q": chess.QUEEN, "R": chess.ROOK, "B": chess.BISHOP, "N": chess.KNIGHT}

# Reconnaît soit une notation case à case explicite ("d3 vers h7",
# "d3 -> h7" — groupe "case_depart"/"case_arrivee", convertie en UCI par
# detect_moves_in_text), soit une notation SAN standard (castling, coup de
# pièce avec capture/désambiguïsation/promotion/échec facultatifs, coup de
# pion poussée ou prise) — groupe "san". L'alternative "case à case" est
# listée en premier : sur "d3 -> h7", elle consomme tout le token et empêche
# la branche SAN de ne matcher que "d3" puis "h7" séparément comme deux
# coups de pion sans rapport (vérifié par les tests de non-régression).
# Un simple tiret nu ("d3-h7") est volontairement EXCLU de cette liste de
# séparateurs (issue #96, correctif après revue) : une phrase descriptive
# française légitime emploie couramment cette même forme sans viser un coup
# du tout (ex. "la diagonale d3-h7", "la chaîne de pions d4-d5") — seuls des
# mots/symboles explicitement directionnels ("vers", "->", "à") sont
# retenus comme notation case à case, par prudence. Même prudence pour
# l'alternative "coup de pion poussée" (dernière du groupe "san") : EXCLUE
# spécifiquement si adjacente à un tiret ("(?<!-)"/"(?!-)", issue #96,
# correctif après revue) — sinon un simple tiret nu dans une phrase
# descriptive ("la diagonale d3-h7", "la chaîne d4-d5") produirait deux
# fausses détections séparées ("d3"+"h7"/"d4"+"d5") plutôt qu'aucune.
_COUP_TOKEN_RE = re.compile(
    r'(?<![A-Za-z0-9])(?:'
    r'(?P<case_depart>[a-h][1-8])\s*(?:->|vers|à)\s*(?P<case_arrivee>[a-h][1-8])'
    r'|(?P<san>O-O-O|O-O'
    r'|[KQRBN][a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?'
    r'|[a-h]x[a-h][1-8](?:=[QRBN])?[+#]?'
    r'|(?<!-)[a-h][1-8](?:=[QRBN])?[+#]?(?!-)'
    r')'
    r')(?![A-Za-z0-9])'
)

_SAN_LOOSE_RE = re.compile(
    r'^(?P<piece>[KQRBN])?(?P<disamb_file>[a-h])?(?P<disamb_rank>[1-8])?'
    r'(?P<capture>x)?(?P<dest>[a-h][1-8])(?:=(?P<promo>[QRBN]))?[+#]?$'
)

_UCI_LOOSE_RE = re.compile(r'^([a-h][1-8])([a-h][1-8])(?:=?[QRBN])?$')


def detect_moves_in_text(text: str, max_coups: int = MAX_COUPS_QUESTION) -> list[str]:
    """Détecte dans `text` un ou plusieurs coups en notation algébrique (SAN,
    par exemple "Bxh7+", "Nf3", "O-O", "e4") ou décrits par case de départ et
    d'arrivée (par exemple "d3 vers h7", "d3 -> h7" — PAS un simple tiret
    nu, trop ambigu avec une mention descriptive comme "la diagonale
    d3-h7", cf. _COUP_TOKEN_RE) — issue #96, étape 1. Volontairement
    permissif sur la FORME (une notation syntaxiquement valide est détectée
    même hors contexte, par exemple la simple mention d'une case comme "e4")
    mais jamais sur le FOND : la légalité réelle n'est tranchée qu'ensuite,
    position par position (resolve_coup_sur_position ci-dessous), qui répond
    explicitement "notation ambiguë" plutôt que de deviner. Dédoublonné dans
    l'ordre d'apparition, limité à `max_coups`. Retourne une liste vide si
    `text` est vide ou si aucun token ne correspond — y compris une phrase
    sans coup identifiable (prudence demandée par l'issue #96)."""
    if not text:
        return []
    vus: list[str] = []
    for m in _COUP_TOKEN_RE.finditer(text):
        if m.group("case_depart") and m.group("case_arrivee"):
            coup = m.group("case_depart") + m.group("case_arrivee")
        else:
            coup = m.group("san")
        if not coup or coup in vus:
            continue
        vus.append(coup)
        if len(vus) >= max_coups:
            break
    return vus


def _trajectoire_bloquee(board: "chess.Board", origine: int, arrivee: int) -> list:
    """Cases occupées entre `origine` et `arrivee`, alignées en colonne,
    ligne ou diagonale (vide si non alignées ou adjacentes, cf.
    chess.between) — sert à nommer la pièce qui bloque le trajet d'un coup
    de pièce à trajectoire rectiligne (issue #96, cas Bxh7+ bloqué en g6)."""
    return [sq for sq in chess.SquareSet(chess.between(origine, arrivee)) if board.piece_at(sq) is not None]


def _raison_malgre_portee(board: "chess.Board", couleur, dest: int, dest_nom: str,
                           coup_str: str, origine_nom: str) -> str:
    """Pour une case d'arrivée géométriquement atteignable (blocages déjà
    écartés par l'appelant) où `coup_str` reste pourtant illégal : seules
    DEUX raisons chiragrammaticales restent possibles en échecs — la case
    est occupée par une pièce du même camp (capture de sa propre pièce,
    impossible), ou ce coup laisserait son propre roi en échec (clouage ou
    échec déjà en cours) — jamais une supposition (issue #96, correctif
    après revue : la version initiale disait "probablement un roi laissé
    en échec" même quand une pièce amie occupait la case, une raison
    pourtant certaine et différente)."""
    cible = board.piece_at(dest)
    if cible is not None and cible.color == couleur:
        return (
            f"{coup_str} reste illégal depuis {origine_nom} : {dest_nom} est occupée par une "
            f"pièce du même camp"
        )
    return f"{coup_str} reste illégal depuis {origine_nom} : ce coup laisserait son roi en échec"


def _explique_trajectoire(board: "chess.Board", piece_type: int, couleur, origine: int, dest: int,
                           dest_nom: str, coup_str: str) -> str | None:
    """Pour UNE case d'origine candidate (déjà filtrée par type de pièce,
    couleur et désambiguïsation éventuelle), explique pourquoi `coup_str` ne
    peut pas en partir — ligne/colonne/diagonale bloquée par une pièce
    nommée, case d'arrivée occupée par une pièce amie, pion sans cible à
    prendre, ou roi laissé en échec (cf. _raison_malgre_portee). Retourne
    None si cette case d'origine n'est de toute façon pas candidate
    géométriquement (hors de portée du tout, ignorant les autres pièces) —
    l'appelant essaie alors la case candidate suivante."""
    est_blanc = couleur == chess.WHITE
    origine_nom = chess.square_name(origine)
    if piece_type == chess.PAWN:
        direction = 8 if est_blanc else -8
        rang_depart = 1 if est_blanc else 6
        diff_fichier = chess.square_file(dest) - chess.square_file(origine)
        if diff_fichier != 0:
            board_vide = chess.Board(None)
            board_vide.set_piece_at(origine, chess.Piece(chess.PAWN, couleur))
            if dest not in board_vide.attacks(origine):
                return None
            if board.piece_at(dest) is None and not board.is_en_passant(chess.Move(origine, dest)):
                return f"aucune pièce adverse à prendre en {dest_nom} depuis {origine_nom}"
            return _raison_malgre_portee(board, couleur, dest, dest_nom, coup_str, origine_nom)
        if origine + direction == dest:
            if board.piece_at(dest) is not None:
                return f"le pion de {origine_nom} est bloqué : {dest_nom} est occupée"
            return _raison_malgre_portee(board, couleur, dest, dest_nom, coup_str, origine_nom)
        if origine + 2 * direction == dest and chess.square_rank(origine) == rang_depart:
            inter = origine + direction
            occupees = [s for s in (inter, dest) if board.piece_at(s) is not None]
            if occupees:
                piece_bloc = board.piece_at(occupees[0])
                nom_bloc = (
                    f"{_NOM_PIECE_MAJ[piece_bloc.piece_type]} "
                    f"{_couleur_accordee(piece_bloc.piece_type, piece_bloc.color)}"
                )
                return (
                    f"le pion de {origine_nom} est bloqué en route vers "
                    f"{dest_nom} par {nom_bloc} en {chess.square_name(occupees[0])}"
                )
            return _raison_malgre_portee(board, couleur, dest, dest_nom, coup_str, origine_nom)
        return None

    board_vide = chess.Board(None)
    board_vide.set_piece_at(origine, chess.Piece(piece_type, couleur))
    if dest not in board_vide.attacks(origine):
        return None
    if dest in board.attacks(origine):
        return _raison_malgre_portee(board, couleur, dest, dest_nom, coup_str, origine_nom)
    bloc = _trajectoire_bloquee(board, origine, dest)
    if bloc:
        piece_bloc = board.piece_at(bloc[0])
        nom_bloc = (
            f"{_NOM_PIECE_MAJ[piece_bloc.piece_type]} "
            f"{_couleur_accordee(piece_bloc.piece_type, piece_bloc.color)}"
        )
        return (
            f"la trajectoire {chess.square_name(origine)}-{dest_nom} est bloquée par "
            f"{nom_bloc} en {chess.square_name(bloc[0])}"
        )
    return None


def _explique_coup_impossible(board: "chess.Board", coup_str: str, couleur) -> str:
    """Explique en UNE phrase mécanique pourquoi `coup_str` (SAN ou case à
    case "d3h7") n'est pas jouable sur `board` pour `couleur` — issue #96,
    étape 2 : ligne bloquée, pièce absente ou ayant changé de case, case
    occupée par une pièce amie, ou coup laissant le roi en échec. Chaque
    clause provient d'un calcul géométrique explicite (chess.between,
    pièces réellement présentes sur `board`) — jamais une supposition :
    repli générique si la raison précise n'a pas pu être établie."""
    coup_str = (coup_str or "").strip()
    est_blanc = couleur == chess.WHITE

    if coup_str in ("O-O", "O-O-O"):
        # La notation SAN du roque n'indique pas le camp : on explique pour
        # `couleur` (le trait réel ou forcé déjà essayé par
        # resolve_coup_sur_position) ET pour l'autre camp si besoin, et on
        # retient la première explication où le DROIT de roque existe
        # encore — sinon la réponse pourrait, à tort, expliquer l'absence
        # de droit d'un camp qui n'a jamais eu l'intention de roquer alors
        # que l'autre a bien ce droit mais un trajet bloqué (cas réel :
        # cavalier en b1 bloquant O-O-O pour les Blancs, alors que les
        # Noirs n'ont simplement plus aucun droit de roque).
        for c in (couleur, not couleur):
            droit = (
                board.has_kingside_castling_rights(c) if coup_str == "O-O"
                else board.has_queenside_castling_rights(c)
            )
            if not droit:
                continue
            roi = board.king(c)
            if roi is None:
                continue
            rang = chess.square_rank(roi)
            fichiers_traverses = (5, 6) if coup_str == "O-O" else (1, 2, 3)
            occupees = [
                chess.square(f, rang) for f in fichiers_traverses
                if board.piece_at(chess.square(f, rang)) is not None
            ]
            if occupees:
                piece_bloc = board.piece_at(occupees[0])
                nom_bloc = (
                    f"{_NOM_PIECE_MAJ[piece_bloc.piece_type]} "
                    f"{_couleur_accordee(piece_bloc.piece_type, piece_bloc.color)}"
                )
                return f"le roque {coup_str} est bloqué par {nom_bloc} en {chess.square_name(occupees[0])}"
            return (
                f"le roque {coup_str} n'est pas jouable dans cette position (case "
                f"traversée attaquée, ou roi actuellement en échec)"
            )
        return f"le roque {coup_str} n'est plus possible : le droit de roque a été perdu"

    m_uci = _UCI_LOOSE_RE.match(coup_str)
    if m_uci:
        origine = chess.parse_square(m_uci.group(1))
        dest = chess.parse_square(m_uci.group(2))
        piece = board.piece_at(origine)
        if piece is None:
            return (
                f"aucune pièce en {m_uci.group(1)} sur cette position : elle a été capturée "
                f"ou a changé de case"
            )
        if piece.color != couleur:
            return f"la pièce en {m_uci.group(1)} appartient à l'autre camp sur cette position"
        raison = _explique_trajectoire(board, piece.piece_type, couleur, origine, dest, m_uci.group(2), coup_str)
        return raison or (
            f"{coup_str} reste illégal sur cette position (roi probablement laissé en échec)"
        )

    m = _SAN_LOOSE_RE.match(coup_str)
    if not m:
        return "notation non reconnue sur cette position"

    piece_type = _PIECE_LETTRE.get(m.group("piece"), chess.PAWN)
    dest = chess.parse_square(m.group("dest"))
    dest_nom = m.group("dest")
    disamb_file = m.group("disamb_file")
    disamb_rank = m.group("disamb_rank")
    nom_piece = _NOM_PIECE_MAJ.get(piece_type, "pièce")
    couleur_txt = _couleur_accordee(piece_type, est_blanc)

    candidats = [
        sq for sq in board.pieces(piece_type, couleur)
        if (not disamb_file or chess.square_name(sq)[0] == disamb_file)
        and (not disamb_rank or chess.square_name(sq)[1] == disamb_rank)
    ]
    if not candidats:
        return (
            f"aucun(e) {nom_piece} {couleur_txt} ne peut rejoindre {dest_nom} : cette pièce "
            f"n'est plus sur l'échiquier ou a changé de case"
        )
    for origine in candidats:
        raison = _explique_trajectoire(board, piece_type, couleur, origine, dest, dest_nom, coup_str)
        if raison:
            return raison
    return f"aucun(e) {nom_piece} {couleur_txt} ne peut atteindre {dest_nom} depuis la position actuelle"


def resolve_coup_sur_position(board: "chess.Board", coup_str: str) -> dict:
    """Résout `coup_str` (SAN ou case à case "d3h7") sur `board`, en testant
    le trait réel ET le trait inverse (issue #96) — une question porte
    souvent sur un coup de l'AUTRE camp que celui qui a la main dans cette
    position précise (cas réel : "et Bxh7+ ?" posée alors que les Noirs ont
    le trait dans la position de départ de l'exercice — Bxh7+ est un coup
    blanc). Retourne {"legal": bool, "move": chess.Move|None, "couleur":
    chess.WHITE|chess.BLACK, "ambigu": bool, "raison_illegal": str} —
    "couleur" est le camp qui joue réellement ce coup (nécessaire pour
    décrire le coup mécaniquement avec le bon trait, cf. appelant), PEUT
    différer de board.turn quand le trait a dû être forcé pour trouver une
    interprétation légale. "ambigu"=True (par prudence, ni légal ni
    illégal) signale une notation SAN réellement ambiguë sur cette position
    précise (deux pièces candidates sans désambiguïsation) pour TOUTES les
    couleurs testées : une ambiguïté pour une seule des deux couleurs ne
    suffit pas à conclure "ambigu" si l'AUTRE couleur donne une
    interprétation légale et non ambiguë (celle-ci est alors retenue —
    corrigé après revue : la version initiale s'arrêtait à la première
    AmbiguousMoveError rencontrée, y compris quand board.turn n'était pas
    la couleur réellement visée par la question, perdant alors une
    interprétation pourtant claire de l'autre côté)."""
    ambigu_rencontre = False
    for couleur in (board.turn, not board.turn):
        b = board.copy()
        b.turn = couleur
        try:
            move = b.parse_san(coup_str)
            return {"legal": True, "move": move, "couleur": couleur, "ambigu": False, "raison_illegal": ""}
        except chess.AmbiguousMoveError:
            ambigu_rencontre = True
            continue
        except ValueError:
            continue
    if ambigu_rencontre:
        return {"legal": False, "move": None, "couleur": board.turn, "ambigu": True, "raison_illegal": ""}
    return {
        "legal": False, "move": None, "couleur": board.turn, "ambigu": False,
        "raison_illegal": _explique_coup_impossible(board, coup_str, board.turn),
    }


def _texte_evaluation_coup_interroge(evaluation: dict) -> str:
    """Formate en une courte clause l'évaluation Stockfish d'un coup
    interrogé (issue #96, étape 2) — qualité/perte par rapport au meilleur
    coup et courte ligne principale, dans le même format que les autres
    coups déjà commentés par le coach (describe_perte_cp_clause). Chaîne
    vide si `evaluation` est vide ou si l'analyse a échoué (jamais un verdict
    inventé — cf. `analyse_indisponible`)."""
    if not evaluation or evaluation.get("analyse_indisponible"):
        return ""
    segs = []
    qualite = evaluation.get("verdict_qualite")
    if qualite:
        delta_cp = evaluation.get("verdict_delta_cp")
        segs.append(f"évaluation Stockfish : {qualite}{describe_perte_cp_clause(delta_cp)}")
    pv = (evaluation.get("pv_coup_propose") or "").strip()
    if pv:
        segs.append("ligne calculée : " + " ".join(pv.split()[:4]))
    if not segs:
        return ""
    return " — " + " ; ".join(segs)


def build_coup_interroge_bloc(coup_str: str, positions: list, camp_alain: str = "",
                               evaluateur=None,
                               max_caracteres: int = MAX_CARACTERES_COUP_QUESTION) -> str:
    """Construit le texte complet pour UN coup interrogé par Alain (issue
    #96, étape 2) : pour chaque position pertinente de `positions` (liste de
    tuples (label, fen), déjà dédoublonnée par l'appelant), teste la
    légalité (resolve_coup_sur_position) et, si légal, décrit le coup
    mécaniquement (_decrit_coup_mecanique, même fonction que pour coup_
    propose/coup_reel/meilleur_coup) complété par l'évaluation Stockfish
    (`evaluateur`, callback optionnel) ; si illégal, la raison mécanique en
    une phrase. Les positions consécutives au même résultat sont regroupées
    pour rester concis. Retourne une chaîne vide si `coup_str` s'avère
    ambigu sur TOUTES les positions testées (prudence : aucune conclusion),
    ou si aucune position n'a pu être lue."""
    groupes: list[tuple[list[str], str]] = []
    une_conclusion = False
    for label, fen in positions:
        try:
            board = chess.Board(fen)
        except Exception:
            continue
        resultat = resolve_coup_sur_position(board, coup_str)
        if resultat["ambigu"]:
            continue
        une_conclusion = True
        if resultat["legal"]:
            # board_coup : trait forcé sur le camp qui joue RÉELLEMENT ce
            # coup (resultat["couleur"], cf. resolve_coup_sur_position) —
            # peut différer de board.turn quand la question porte sur un
            # coup de l'autre camp dans cette position précise (cas Bxh7+,
            # un coup blanc posé alors que les Noirs ont le trait) ; sans ce
            # trait forcé, _decrit_coup_mecanique lirait le camp joueur sur
            # board.turn et attribuerait le coup au mauvais camp.
            board_coup = board.copy()
            board_coup.turn = resultat["couleur"]
            texte = _decrit_coup_mecanique(board_coup, resultat["move"], camp_alain)
            if evaluateur:
                try:
                    # fen du trait forcé (board_coup), PAS `fen` tel que
                    # transmis par l'appelant : Stockfish doit recevoir une
                    # position où le trait correspond réellement au camp qui
                    # joue ce coup, sinon l'appel moteur porte sur une
                    # position incohérente (même raison que ci-dessus).
                    evaluation = evaluateur(board_coup.fen(), resultat["move"])
                except Exception as e:
                    logger.warning(f"[GAME_FACTS] Évaluation du coup interrogé échouée : {e}")
                    evaluation = None
                texte += _texte_evaluation_coup_interroge(evaluation or {})
        else:
            texte = resultat["raison_illegal"] or "illégal sur cette position"
        if groupes and groupes[-1][1] == texte:
            groupes[-1][0].append(label)
        else:
            groupes.append(([label], texte))
    if not une_conclusion or not groupes:
        return ""
    parts = [f"{' et '.join(labels)} : {texte}" for labels, texte in groupes]
    corps = " ; ".join(parts)
    if len(corps) > max_caracteres:
        corps = corps[:max_caracteres].rstrip() + "…"
    return f"{coup_str} — {corps}"


def build_coups_interroges_texte(message_text: str, positions: list, camp_alain: str = "",
                                   evaluateur=None,
                                   max_coups: int = MAX_COUPS_QUESTION,
                                   max_caracteres: int = MAX_CARACTERES_COUP_QUESTION) -> str:
    """API publique (issue #96) : détecte dans `message_text` (la question
    actuelle d'Alain) un ou plusieurs coups précis, et retourne le texte
    complet à ajouter au contexte du coach (une ligne par coup détecté,
    vide si aucun coup n'a été identifié ou si `positions` est vide). Chaque
    coup est traité indépendamment par build_coup_interroge_bloc ci-dessus ;
    `evaluateur`, si fourni, y est transmis tel quel. Best-effort : une
    erreur sur un coup n'empêche jamais de traiter les autres."""
    coups = detect_moves_in_text(message_text, max_coups=max_coups)
    if not coups or not positions:
        return ""
    blocs = []
    for coup in coups:
        try:
            bloc = build_coup_interroge_bloc(coup, positions, camp_alain, evaluateur, max_caracteres)
        except Exception as e:
            logger.warning(f"[GAME_FACTS] Traitement du coup interrogé '{coup}' échoué : {e}")
            bloc = ""
        if bloc:
            blocs.append(bloc)
    return "\n".join(blocs)


def _materiel_alain(board: "chess.Board", camp_alain: str) -> int | None:
    """Solde matériel (points classiques, pion=1...dame=9) du point de vue
    d'Alain — positif = avantage pour Alain, négatif = avantage pour
    l'adversaire. None si camp_alain n'est ni "blancs" ni "noirs" (solde
    Blancs-Noirs non convertible sans ambiguïté, même garde-fou que
    app._vers_point_de_vue_alain pour une évaluation Stockfish, issue #73)."""
    if camp_alain not in ("blancs", "noirs"):
        return None
    blancs, noirs = _materiel(board)
    solde_blancs = blancs - noirs
    return solde_blancs if camp_alain == "blancs" else -solde_blancs


def describe_pv_with_balance(fen_avant: str, pv_text: str, camp_alain: str = "",
                              max_plies: int = 4) -> list[dict]:
    """API publique (issue #75, point 3) : comme describe_pv_mechanically,
    mais ajoute à chaque demi-coup décrit le solde matériel CUMULÉ après ce
    coup, du point de vue d'Alain (_materiel_alain) — sans ce solde, le coach
    devait reconstituer de tête le bilan d'une ligne principale et s'est déjà
    trompé sur un simple échange (ex. "tu as gagné la dame contre rien" sur
    Qh8+ Ke7 Qxd8+ Kxd8, qui échange les deux dames, solde net 0 ; "tu
    échanges ta tour contre le fou" sur Rxd5, qui gagne simplement le fou
    sans rien céder en retour).

    Retourne une liste de dicts {"san": str, "description": str,
    "solde_alain": int | None} (un par demi-coup décrit, dans l'ordre de la
    ligne) — liste tronquée au premier coup illégal rencontré, vide si
    fen_avant/pv_text sont vides ou illisibles, comme describe_pv_mechanically."""
    fen_avant = (fen_avant or "").strip()
    pv_text = (pv_text or "").strip()
    if not fen_avant or not pv_text:
        return []
    try:
        board = chess.Board(fen_avant)
        resultat = []
        case_premier_coup = None
        camp_premier_coup = None
        for i, san in enumerate(pv_text.split()[:max_plies]):
            move = _parse_coup(board, san)
            if move is None:
                break
            piece_qui_joue = board.piece_at(move.from_square)
            description = _decrit_coup_mecanique(board, move, camp_alain)
            board.push(move)
            if i == 0:
                # Case/camp du premier demi-coup de la ligne (le coup proposé
                # ou le meilleur coup lui-même) — sert à vérifier son statut
                # une fois la réponse adverse immédiate jouée, ci-dessous.
                case_premier_coup = move.to_square
                camp_premier_coup = piece_qui_joue.color if piece_qui_joue else None
            elif i == 1 and case_premier_coup is not None:
                # Première réponse adverse (issue #87, point 2) : dit
                # explicitement si la pièce qui vient de jouer au demi-coup
                # précédent est désormais attaquée ou non — jamais un simple
                # silence qui laisserait deviner.
                statut = _statut_attaque_case(board, case_premier_coup, camp_premier_coup, camp_alain)
                if statut:
                    description = f"{description} ; {statut}"
            resultat.append({
                "san": san,
                "description": description,
                "solde_alain": _materiel_alain(board, camp_alain),
            })
        return resultat
    except Exception as e:
        logger.warning(f"[GAME_FACTS] describe_pv_with_balance a échoué : {e}")
        return []


def format_pv_with_balance(label: str, pv_descriptions: list[dict]) -> str:
    """Formate le résultat de describe_pv_with_balance en texte prêt à
    injecter dans le contexte du coach (issue #75, point 3) : une ligne par
    demi-coup, avec sa description mécanique et le solde matériel cumulé
    pour Alain après ce coup précis — jamais après la ligne entière
    seulement, pour que le coach puisse situer exactement À QUEL COUP un
    échange se solde. Chaîne vide si pv_descriptions est vide."""
    if not pv_descriptions:
        return ""
    lignes = [f"{label} :"]
    for d in pv_descriptions:
        solde = d.get("solde_alain")
        solde_txt = (
            f"solde matériel cumulé pour Alain après ce coup : {solde:+d}"
            if solde is not None
            else "solde matériel cumulé pour Alain après ce coup : indéterminé (camp d'Alain inconnu)"
        )
        lignes.append(f"  {d['san']} : {d['description']} ({solde_txt})")
    return "\n".join(lignes)


def describe_eval_alain_cp_clause(eval_alain_cp) -> str:
    """Phrase complète décrivant l'évaluation Stockfish réelle d'une position,
    du point de vue d'Alain (issue #75, point 1) — en mots dès que la
    magnitude dépasse SEUIL_GRANDE_VALEUR_CP, jamais le chiffre brut dans ce
    cas (voir le commentaire de SEUIL_GRANDE_VALEUR_CP ci-dessus). Chaîne
    vide si eval_alain_cp n'est pas un nombre."""
    if not isinstance(eval_alain_cp, (int, float)):
        return ""
    if abs(eval_alain_cp) > SEUIL_GRANDE_VALEUR_CP:
        gagnant = "Alain" if eval_alain_cp > 0 else "l'adversaire"
        return (
            "Évaluation Stockfish réelle de la position résultant du coup "
            f"proposé : position gagnée de façon forcée pour {gagnant} (valeur "
            "extrême, à ne JAMAIS exprimer en centipawns ni en nombre de pions)."
        )
    return (
        "Évaluation Stockfish réelle de la position résultant du coup proposé, "
        "du point de vue d'Alain (positif = avantage pour Alain, négatif = "
        f"avantage pour l'adversaire) : {eval_alain_cp:+d} centipawns."
    )


def describe_perte_cp_clause(delta_cp) -> str:
    """Clause ', perte ... par rapport au meilleur coup' prête à l'emploi
    dans le texte de contexte transmis au coach (issue #75, point 1) — en
    mots dès que la magnitude dépasse SEUIL_GRANDE_VALEUR_CP, jamais le
    chiffre brut dans ce cas. Chaîne vide si delta_cp n'est pas un nombre."""
    if not isinstance(delta_cp, (int, float)):
        return ""
    if abs(delta_cp) > SEUIL_GRANDE_VALEUR_CP:
        return (
            ", perte d'une ampleur extrême par rapport au meilleur coup "
            "(bien au-delà d'une perte de matériel ordinaire — ne JAMAIS "
            "exprimer cette perte en centipawns ni en nombre de pions)"
        )
    return f", perte de {delta_cp:g} centipawns par rapport au meilleur coup"


def describe_menace_adverse(menace_data: dict, fen_avant: str, camp_alain: str = "") -> str:
    """API publique (issue #80, point 1) : formate en texte de contexte le
    résultat de EngineManager.get_threats — jusqu'à deux menaces adverses
    (coup nul), chacune décrite mécaniquement (describe_move_mechanically,
    réutilisé tel quel) avec son évaluation résultante et sa perte
    d'avantage par rapport à l'évaluation de la position (baseline, déjà
    calculée en supposant le meilleur coup du camp au trait).

    menace_data : dict retourné par EngineManager.get_threats(board).
    fen_avant : position AVANT tout coup (celle transmise à get_threats).

    Retourne toujours une phrase explicite, même quand aucune menace n'a pu
    être calculée (position en échec, Stockfish indisponible) — pour que le
    contexte le dise clairement plutôt que de laisser le coach deviner
    pourquoi ce bloc est absent (cf. tâche 1 : "Ne rien calculer... et le
    dire dans le contexte")."""
    if not menace_data or not menace_data.get("disponible"):
        raison = (menace_data or {}).get("raison")
        if raison == "en_echec":
            return (
                "Menace adverse (issue #80) : non calculée, le camp au trait est "
                "en échec dans cette position (un coup nul n'est pas possible "
                "pour détecter une menace adverse ici)."
            )
        return (
            "Menace adverse (issue #80) : non calculée, Stockfish indisponible "
            "pour ce calcul."
        )

    menaces = menace_data.get("menaces") or []
    if not menaces:
        return "Menace adverse (issue #80) : aucune menace calculable trouvée pour l'adversaire."

    try:
        board_nul = chess.Board(fen_avant)
        board_nul.push(chess.Move.null())
        fen_nul = board_nul.fen()
    except Exception as e:
        logger.warning(f"[GAME_FACTS] describe_menace_adverse a échoué : {e}")
        return ""

    lignes = [
        "Menace(s) de l'adversaire si Alain passait son tour (coup nul, "
        "calculé uniquement pour détecter la menace réelle — PAS un coup "
        "qu'Alain va réellement jouer), chiffres INTERNES (jamais à citer "
        "tels quels à Alain) :"
    ]
    for i, m in enumerate(menaces, start=1):
        desc = describe_move_mechanically(fen_nul, m["move"], camp_alain) or (
            f"{m['move']} (description indisponible)"
        )
        perte = m.get("perte_cp")
        if m.get("mate") is not None:
            eval_txt = f"mat en {abs(m['mate'])} coup(s) contre Alain"
        elif m.get("cp") is not None:
            eval_txt = f"{m['cp']:+d} centipawns pour Alain"
        else:
            eval_txt = "indéterminée"
        if perte is None:
            gravite = "gravité indéterminée"
        elif perte > SEUIL_MENACE_SIGNIFICATIVE_CP:
            gravite = f"perte de {perte} centipawns par rapport au meilleur coup d'Alain — menace SIGNIFICATIVE"
        else:
            gravite = f"perte de {perte} centipawns par rapport au meilleur coup d'Alain — menace mineure"
        lignes.append(f"  Menace n°{i} : {desc} ; évaluation résultante : {eval_txt} ({gravite}).")
    return "\n".join(lignes)


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


def _pieces_clouees_camp(board: "chess.Board", est_blanc: bool) -> list[str]:
    couleur = chess.WHITE if est_blanc else chess.BLACK
    clouees = []
    for square, piece in sorted(board.piece_map().items()):
        if (
            piece.color == couleur
            and piece.piece_type != chess.KING
            and board.is_pinned(couleur, square)
        ):
            clouees.append(f"{_NOM_PIECE_MAJ[piece.piece_type]} {chess.square_name(square)}")
    return clouees


def describe_pieces_clouees(fen: str, camp_alain: str = "") -> str:
    """API publique (issue #92, tâche 2) : liste, pour chaque camp, les
    pièces clouées dans la position `fen` (case et pièce), ou "aucune pièce
    clouée" — calcul déterministe avec python-chess (Board.is_pinned), jamais
    une estimation ou une lecture géométrique du coach. Constat ayant motivé
    cet ajout (cas réel, journal du coach du 2026-10-02, cf.
    coach_reliability.py) : le coach a affirmé qu'une dame restait "clouée
    face à la dame adverse" alors qu'aucune pièce blanche n'était clouée dans
    cette position.

    Un roi n'est jamais listé comme "cloué" (il ne peut pas l'être au sens
    des échecs : c'est lui qui impose le clouage aux autres pièces).

    Retourne "Pièces clouées dans cette position : Blancs (...) : ...\\nNoirs
    (...) : ..." (même présentation que describe_pieces_lists), ou "" si fen
    est vide ou illisible."""
    fen = (fen or "").strip()
    if not fen:
        return ""
    try:
        board = chess.Board(fen)
    except Exception as e:
        logger.warning(f"[GAME_FACTS] describe_pieces_clouees a échoué : {e}")
        return ""
    label_blancs = camp_label(True, camp_alain)
    label_noirs = camp_label(False, camp_alain)
    clouees_blancs = _pieces_clouees_camp(board, True)
    clouees_noirs = _pieces_clouees_camp(board, False)
    texte_blancs = ", ".join(clouees_blancs) if clouees_blancs else "aucune pièce clouée"
    texte_noirs = ", ".join(clouees_noirs) if clouees_noirs else "aucune pièce clouée"
    return (
        "Pièces clouées dans cette position (issue #92, calcul déterministe "
        "python-chess) :\n"
        f"  {label_blancs} : {texte_blancs}\n"
        f"  {label_noirs} : {texte_noirs}"
    )


def describe_pieces_lists(fen: str, camp_alain: str = "") -> str:
    """API publique (issue #80, point 3) : liste des pièces de chaque camp
    par case, pour une position FEN isolée — même présentation que le bloc
    de faits des modes de partie (_liste_pieces/build_game_facts_text), mais
    réutilisable pour le mode "Exercice" qui ne rejoue pas de PGN. Jointe au
    contexte pour la position de DÉPART et la position ACTUELLE de
    l'exercice, afin que le coach n'ait plus jamais à lire les pièces depuis
    un FEN recopié de mémoire (cause du bug source : un FEN mal recopié,
    "p1" devenu "g1", avait fait disparaître un pion du contexte).

    Retourne "Blancs (...) : ...\\nNoirs (...) : ..." (camp_label applique
    déjà "(Alain)"/"(adversaire)" si camp_alain est connu), ou "" si fen est
    vide ou illisible."""
    fen = (fen or "").strip()
    if not fen:
        return ""
    try:
        board = chess.Board(fen)
    except Exception as e:
        logger.warning(f"[GAME_FACTS] describe_pieces_lists a échoué : {e}")
        return ""
    label_blancs = camp_label(True, camp_alain)
    label_noirs = camp_label(False, camp_alain)
    return (
        f"{label_blancs} : {_liste_pieces(board, True)}\n"
        f"{label_noirs} : {_liste_pieces(board, False)}"
    )


# Types de pièces résumés par describe_material_summary, dans l'ordre
# d'affichage demandé (issue #87) — dame d'abord (la plus forte), roi exclu
# (toujours présent des deux côtés, sans valeur de points).
_TYPES_RESUME_MATERIEL = (chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT, chess.PAWN)

_NOM_PIECE_SINGULIER = {
    chess.QUEEN: "dame", chess.ROOK: "tour", chess.BISHOP: "fou",
    chess.KNIGHT: "cavalier", chess.PAWN: "pion",
}

_NOM_PIECE_PLURIEL = {
    chess.QUEEN: "dames", chess.ROOK: "tours", chess.BISHOP: "fous",
    chess.KNIGHT: "cavaliers", chess.PAWN: "pions",
}


def _aucun_texte(piece_type: int) -> str:
    """"aucune tour"/"aucune dame" (féminin) ou "aucun fou"/"aucun cavalier"/
    "aucun pion" (masculin) — absence explicite d'un type de pièce (issue
    #87, point 1), condition centrale du bug source : le coach avait parlé
    d'un "échange tour contre tour" dans une position où un seul camp avait
    une tour."""
    article = "aucune" if piece_type in _FEMININ else "aucun"
    return f"{article} {_NOM_PIECE_SINGULIER[piece_type]}"


def _resume_materiel_camp(board: "chess.Board", est_blanc: bool) -> tuple[list[str], int]:
    segs = []
    total = 0
    for pt in _TYPES_RESUME_MATERIEL:
        n = len(board.pieces(pt, est_blanc))
        total += n * _VALEURS[pt]
        if n == 0:
            segs.append(_aucun_texte(pt))
        elif n == 1:
            segs.append(f"1 {_NOM_PIECE_SINGULIER[pt]}")
        else:
            segs.append(f"{n} {_NOM_PIECE_PLURIEL[pt]}")
    return segs, total


def describe_material_summary(fen: str, camp_alain: str = "") -> str:
    """API publique (issue #87, point 1) : résumé du matériel de chaque camp,
    PAR TYPE de pièce, avec les absences dites explicitement ("aucune tour"),
    le total en points classiques et l'équilibre matériel — en complément de
    describe_pieces_lists (qui donne les pièces case par case, mais ne dit
    jamais explicitement qu'un type de pièce est totalement absent d'un
    camp). Sans cette absence explicite, le coach a déjà parlé d'un "échange
    tour contre tour" dans une position où les Noirs n'avaient plus aucune
    tour — les données fournies (liste des pièces) étaient exactes, mais
    n'empêchaient pas cette invention faute de le dire en toutes lettres.

    Retourne "" si fen est vide ou illisible."""
    fen = (fen or "").strip()
    if not fen:
        return ""
    try:
        board = chess.Board(fen)
    except Exception as e:
        logger.warning(f"[GAME_FACTS] describe_material_summary a échoué : {e}")
        return ""
    label_blancs = camp_label(True, camp_alain)
    label_noirs = camp_label(False, camp_alain)
    segs_blancs, total_blancs = _resume_materiel_camp(board, True)
    segs_noirs, total_noirs = _resume_materiel_camp(board, False)
    diff = total_blancs - total_noirs
    if diff == 0:
        equilibre = "matériel égal"
    else:
        camp_en_plus = label_blancs if diff > 0 else label_noirs
        equilibre = f"{camp_en_plus} ont {abs(diff)} point(s) de plus"
    return (
        "Résumé du matériel par type de pièce (points classiques : pion=1, "
        "cavalier=fou=3, tour=5, dame=9 ; roi non compté) — ne parle JAMAIS "
        "d'échange, de prise ou de perte d'un type de pièce marqué "
        "\"aucun(e)\" ci-dessous pour le camp concerné :\n"
        f"  {label_blancs} : {', '.join(segs_blancs)} (total {total_blancs} points)\n"
        f"  {label_noirs} : {', '.join(segs_noirs)} (total {total_noirs} points)\n"
        f"  Équilibre matériel : {equilibre}."
    )


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

    # Résumé du matériel par type de pièce de la position actuelle (issue
    # #87, point 1) — généralise les deux lignes "n'a plus de dame" ci-dessus
    # à tous les types de pièces, avec le total en points et l'équilibre.
    materiel_resume = describe_material_summary(board.fen(), camp_alain)
    if materiel_resume:
        parties.append(materiel_resume)

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
                if abs(perte_cp) > SEUIL_GRANDE_VALEUR_CP:
                    lignes_cible.append(
                        "  Perte estimée : ampleur extrême, bien au-delà "
                        "d'une perte de matériel ordinaire (issue #75 — ne "
                        "JAMAIS exprimer cette perte en centipawns ni en "
                        "nombre de pions)"
                    )
                else:
                    lignes_cible.append(f"  Perte estimée {perte_cp:g} centipawns")

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


# ── Idées du coup (issue #80, point 5) ──────────────────────────────────────
# Traduction en français des termes de la décomposition classique de
# l'évaluation Stockfish (EngineManager.get_eval_breakdown) en "idées"
# compréhensibles par le coach — seuls les termes explicitement demandés par
# l'issue sont mappés ; "Queens" et "Winnable" restent volontairement hors de
# cette table (aucune traduction demandée), leur variation éventuelle n'est
# donc jamais retenue comme idée. "Material"/"Imbalance" partagent le même
# libellé ("matériel") : leurs variations sont sommées plutôt que remontées
# comme deux idées distinctes sur un même coup.
_IDEE_LIBELLES = {
    "King safety": "sécurité du roi",
    "Threats": "menaces sur les pièces adverses",
    "Mobility": "activité des pièces",
    "Passed": "pion passé",
    "Space": "espace",
    "Pawns": "structure de pions",
    "Knights": "meilleur placement du cavalier",
    "Bishops": "meilleur placement du fou",
    "Rooks": "meilleur placement de la tour",
    "Material": "matériel",
    "Imbalance": "matériel",
}

# Cases de départ standard des cavaliers/fous (issue #80, point 5, idée
# mécanique "pièce développée") — ne sert qu'à l'heuristique d'ouverture,
# aucune prétention à détecter un développement plus tardif ou atypique.
_CASES_DEPART_DEVELOPPEMENT = {
    (chess.KNIGHT, True): {chess.B1, chess.G1},
    (chess.KNIGHT, False): {chess.B8, chess.G8},
    (chess.BISHOP, True): {chess.C1, chess.F1},
    (chess.BISHOP, False): {chess.C8, chess.F8},
}

# Cases centrales (issue #80, point 5, idée mécanique "pièce centralisée") —
# le carré central au sens strict, pas l'étendue plus large parfois utilisée
# en théorie des ouvertures (c3-f6), pour rester une heuristique simple et
# non ambiguë.
_CASES_CENTRALES = {chess.D4, chess.D5, chess.E4, chess.E5}


def _phase_mg_ou_eg(board: "chess.Board") -> str:
    """"mg"/"eg" selon le matériel restant sur l'échiquier (issue #80, point
    5) — même heuristique que la phase "finale" déjà utilisée ailleurs
    (app.py _analyse_full_game : 12 pièces ou moins sur l'échiquier)."""
    return "eg" if chess.popcount(board.occupied) <= 12 else "mg"


def _diff_termes_evaluation(breakdown_avant: dict | None, breakdown_apres: dict | None,
                             phase: str, camp_alain: str) -> list[dict]:
    """Variation de chaque terme de la décomposition classique de
    l'évaluation Stockfish entre AVANT et APRÈS un coup, du point de vue
    d'Alain, pour les termes au-delà de SEUIL_IDEE_PION (issue #80, point 5).
    "Material"/"Imbalance" sont fusionnés sous le même libellé ("matériel").

    Retourne une liste de {"libelle": str, "poids": float} (poids = delta en
    pions, signé, du point de vue d'Alain) — [] si l'une des deux
    décompositions est absente (commande "eval" indisponible/échouée) ou si
    camp_alain n'est ni "blancs" ni "noirs"."""
    if not breakdown_avant or not breakdown_apres or camp_alain not in ("blancs", "noirs"):
        return []
    signe = 1 if camp_alain == "blancs" else -1
    par_libelle: dict[str, float] = {}
    for terme, libelle in _IDEE_LIBELLES.items():
        avant = (breakdown_avant.get(terme) or {}).get(phase)
        apres = (breakdown_apres.get(terme) or {}).get(phase)
        if avant is None or apres is None:
            continue
        par_libelle[libelle] = par_libelle.get(libelle, 0.0) + signe * (apres - avant)
    return [
        {"libelle": libelle, "poids": poids}
        for libelle, poids in par_libelle.items()
        if abs(poids) >= SEUIL_IDEE_PION
    ]


def _idee_parade_menace(board_avant: "chess.Board", move: "chess.Move",
                         menace_data: dict | None) -> dict | None:
    """Idée mécanique "pare une menace adverse" (issue #80, points 1 et 5) :
    si la menace la plus sévère calculée par EngineManager.get_threats sur
    `board_avant` n'est plus légale sur la position résultant de `move`,
    c'est que ce coup la pare — jamais déduit autrement qu'en rejouant
    mécaniquement la menace sur la position réelle. None si aucune menace
    significative n'a été calculée, ou si la menace reste jouable après ce
    coup (ce coup ne la pare pas)."""
    if not menace_data or not menace_data.get("disponible"):
        return None
    menaces = menace_data.get("menaces") or []
    if not menaces:
        return None
    principale = menaces[0]
    perte_cp = principale.get("perte_cp")
    if not perte_cp or perte_cp <= SEUIL_MENACE_SIGNIFICATIVE_CP:
        return None
    try:
        menace_move = chess.Move.from_uci(principale["move"])
        board_apres = board_avant.copy()
        board_apres.push(move)
        if menace_move in board_apres.legal_moves:
            return None
        case = chess.square_name(menace_move.to_square)
        origine = chess.square_name(menace_move.from_square)
    except Exception:
        return None
    return {
        "libelle": "pare une menace adverse",
        "poids": perte_cp / 100,
        "detail": f"empêche {origine}-{case}",
    }


def _idee_developpement_centralisation(board_avant: "chess.Board", move: "chess.Move") -> dict | None:
    """Idée mécanique "pièce développée"/"pièce centralisée" (issue #80,
    point 5) — heuristiques simples sur la case de départ (case initiale du
    cavalier/fou) et la case d'arrivée (carré central), jamais combinées
    pour un même coup (la centralisation prime si les deux s'appliquent, un
    développement qui centralise directement étant plus parlant qu'un
    développement seul)."""
    piece = board_avant.piece_at(move.from_square)
    if piece is None:
        return None
    if move.to_square in _CASES_CENTRALES and piece.piece_type in (
        chess.KNIGHT, chess.BISHOP, chess.QUEEN, chess.PAWN,
    ):
        return {
            "libelle": "centralise une pièce",
            "poids": 0.4,
            "detail": f"{_NOM_PIECE[piece.piece_type]} en {chess.square_name(move.to_square)}",
        }
    if move.from_square in _CASES_DEPART_DEVELOPPEMENT.get((piece.piece_type, piece.color), set()):
        return {
            "libelle": "développe une pièce",
            "poids": 0.5,
            "detail": f"{_NOM_PIECE[piece.piece_type]} vers {chess.square_name(move.to_square)}",
        }
    return None


def build_idees_coup(fen_avant: str, coup, camp_alain: str,
                      breakdown_avant: dict | None, breakdown_apres: dict | None,
                      menace_data: dict | None = None, max_idees: int = 3) -> list[dict]:
    """API publique (issue #80, point 5) : idées détectées pour UN coup cité
    (coup proposé, coup réellement joué, meilleur coup), combinant :
      - les variations de la décomposition classique de l'évaluation
        Stockfish au-delà de SEUIL_IDEE_PION (_diff_termes_evaluation),
        traduites en français (_IDEE_LIBELLES) ;
      - les idées mécaniques calculées avec python-chess : parade d'une
        menace adverse de la tâche 1 (_idee_parade_menace), échec/mat
        (board.is_checkmate/is_check), pièce développée ou centralisée
        (_idee_developpement_centralisation).
    Triées par importance (valeur absolue du poids — pions pour les idées
    moteur, échelle comparable pour les idées mécaniques) et limitées à
    `max_idees` (3 par défaut, demandé par l'issue) : sans plafond, un coup
    qui change beaucoup de termes gonflerait le contexte envoyé au coach,
    contrairement à la liste courte demandée.

    Retourne une liste de {"libelle": str, "detail": str} (SANS aucune
    valeur chiffrée — jamais transmise au coach, cf. llm_coach.py) : []
    si fen_avant/coup sont illisibles/illégaux, ou si rien ne dépasse les
    seuils (ne pas inventer une idée en l'absence de signal réel)."""
    fen_avant = (fen_avant or "").strip()
    if not fen_avant or not coup:
        return []
    try:
        board_avant = chess.Board(fen_avant)
        move = _parse_coup(board_avant, coup)
        if move is None:
            return []
        board_apres = board_avant.copy()
        board_apres.push(move)
    except Exception as e:
        logger.warning(f"[GAME_FACTS] build_idees_coup a échoué : {e}")
        return []

    # Trois paliers d'importance (issue #80, point 5) avant le tri par
    # magnitude à l'intérieur de chacun : un mat ou un échec prime toujours
    # sur tout le reste (palier 0) ; les idées tirées de la décomposition de
    # l'évaluation Stockfish — l'objet principal de cette tâche, qui mesure
    # l'effet réel du coup sur la position — passent avant les idées
    # mécaniques complémentaires de la tâche 2/1 comme la parade d'une
    # menace ou le développement (palier 2), qui restent des COMPLÉMENTS
    # explicatifs, pas le signal principal, même quand leur magnitude brute
    # (ex. perte évitée en centipawns/100) dépasserait numériquement celle
    # d'un terme d'évaluation (constat sur l'exemple de l'issue : h4 doit
    # présenter "sécurité du roi" en tête, la parade de gxh3+ ensuite).
    idees = []

    if board_apres.is_checkmate():
        idees.append({"libelle": "échec et mat", "poids": 1000.0, "detail": "", "palier": 0})
    elif board_apres.is_check():
        idees.append({"libelle": "échec", "poids": 1.5, "detail": "", "palier": 0})

    phase = _phase_mg_ou_eg(board_apres)
    for idee_eval in _diff_termes_evaluation(breakdown_avant, breakdown_apres, phase, camp_alain):
        idees.append({**idee_eval, "detail": "", "palier": 1})

    parade = _idee_parade_menace(board_avant, move, menace_data)
    if parade:
        idees.append({**parade, "palier": 2})

    developpement = _idee_developpement_centralisation(board_avant, move)
    if developpement:
        idees.append({**developpement, "palier": 2})

    idees.sort(key=lambda d: (d["palier"], -abs(d["poids"])))
    return [{"libelle": d["libelle"], "detail": d["detail"]} for d in idees[:max_idees]]


def format_idees_coup(label: str, idees: list[dict]) -> str:
    """Formate le résultat de build_idees_coup en texte de contexte (issue
    #80, point 5) — une ligne par idée, numérotée dans l'ordre d'importance
    déjà trié, avec la ou les pièces/cases concernées quand il y en a.
    Chaîne vide si idees est vide (rien à transmettre, cf. tâche 5 : "ne
    rien transmettre" si la décomposition est indisponible ou vide)."""
    if not idees:
        return ""
    lignes = [f"Idées détectées pour {label} (indication du moteur, dans l'ordre d'importance) :"]
    for i, idee in enumerate(idees, start=1):
        detail = f" ({idee['detail']})" if idee.get("detail") else ""
        lignes.append(f"  {i}. {idee['libelle']}{detail}")
    return "\n".join(lignes)


# ── Réponse adverse forcée (issue #91, tâche 1) ────────────────────────────
# Constat réel ayant motivé cette extension (même cas que l'en-tête du
# module) : les données envoyées au coach décrivaient la ligne principale
# (Re8 Qxe8 Qxe8) mais pas le sort des AUTRES réponses adverses possibles —
# le coach ne pouvait donc pas savoir que Qxe8 était forcé (toute autre
# réponse perd par mat en 1, menace principale Qb8 mat) et a inventé une
# fausse raison ("la dame perd la tour gratuitement").
#
# Seuil réglable en CE SEUL endroit (issue #91) : perte d'avantage
# (centipawns, même barème mat/cp unique que evaluate_move/get_threats)
# au-delà de laquelle une réponse adverse alternative est jugée perdante —
# en plus d'un mat détecté directement (toujours perdant, quel que soit ce
# seuil).
SEUIL_REPONSE_FORCEE_CP = 300


def _decrire_menace_evitee(board_apres_coup: "chess.Board", alternative: dict) -> str:
    """Décrit mécaniquement (issue #91, point 1) la menace que la MOINS
    mauvaise réponse perdante éviterait d'affronter — rejoue la ligne (pv)
    réellement calculée par le moteur pour CETTE alternative précise, coup
    par coup, en SAN, jusqu'au premier mat rencontré (le cas qui motive
    l'issue) ou jusqu'à épuisement de la ligne. Sur un mat, ajoute qui
    défend la pièce qui mate (ex. "dame protégée par la tour e8 et la dame
    a8") — l'information manquante dans le cas réel ayant motivé l'issue.
    Chaîne vide si la ligne est vide ou illisible dès le premier coup."""
    pv = alternative.get("pv") or []
    if not pv:
        return ""
    b = board_apres_coup.copy()
    sans = []
    mat_trouve = False
    defenseurs_txt = ""
    for uci in pv:
        try:
            move = chess.Move.from_uci(uci)
        except Exception:
            break
        if move not in b.legal_moves:
            break
        piece = b.piece_at(move.from_square)
        try:
            san = b.san(move)
        except Exception:
            san = uci
        b.push(move)
        sans.append(san)
        if b.is_checkmate():
            mat_trouve = True
            if piece is not None:
                defenseurs = sorted(b.attackers(piece.color, move.to_square))
                if defenseurs:
                    noms = ", ".join(
                        f"{_NOM_PIECE_MAJ[b.piece_at(sq).piece_type]} {chess.square_name(sq)}"
                        for sq in defenseurs
                    )
                    defenseurs_txt = f", {_NOM_PIECE[piece.piece_type]} protégé(e) par {noms}"
            break
    if mat_trouve:
        return f"mat en {len(sans)} demi-coup(s) ({' '.join(sans)}){defenseurs_txt}"
    if sans:
        return f"notamment {' '.join(sans)}, perte nette de matériel selon Stockfish"
    return ""


def build_reponse_adverse_obligee_texte(label: str, fen_apres_coup: str, reponses_data: dict,
                                         camp_alain: str = "") -> str:
    """API publique (issue #91, point 1) : formate en texte de contexte le
    résultat de EngineManager.get_reponses_adverses (calculée côté app.py)
    pour `label` ("le coup proposé" / "le meilleur coup") — dit explicitement
    si la réponse adverse de la ligne principale est la SEULE qui évite une
    perte nette ou un mat (SEUIL_REPONSE_FORCEE_CP, réglable en un seul
    endroit ci-dessus), avec la menace évitée décrite mécaniquement
    (_decrire_menace_evitee), ou si plusieurs réponses se valent — jamais
    laissé au silence, qui a déjà produit une fausse raison inventée (cf.
    en-tête du module).

    Retourne toujours une phrase explicite, même quand le calcul est
    indisponible (position terminale ou Stockfish indisponible) — même
    philosophie que describe_menace_adverse."""
    if not reponses_data or not reponses_data.get("disponible"):
        raison = (reponses_data or {}).get("raison")
        if raison == "position_terminale":
            return (
                f"Réponse(s) adverse(s) après {label} (issue #91) : non calculée(s), "
                "position déjà terminale (mat ou pat), aucun coup adverse possible."
            )
        return (
            f"Réponse(s) adverse(s) après {label} (issue #91) : non calculée(s), "
            "Stockfish indisponible pour ce calcul."
        )

    reponses = reponses_data.get("reponses") or []
    if not reponses:
        return (
            f"Réponse(s) adverse(s) après {label} (issue #91) : aucune réponse légale "
            "trouvée (position terminale)."
        )

    try:
        board = chess.Board(fen_apres_coup)
    except Exception as e:
        logger.warning(f"[GAME_FACTS] build_reponse_adverse_obligee_texte a échoué : {e}")
        return ""

    meilleure = reponses[0]
    try:
        san_meilleure = board.san(chess.Move.from_uci(meilleure["move"]))
    except Exception:
        san_meilleure = meilleure["move"]

    alternatives = reponses[1:]
    if not alternatives:
        return (
            f"Réponse adverse après {label} (issue #91) : {san_meilleure} est le SEUL "
            "coup légal dans cette position, aucune alternative à comparer."
        )

    def _perd(r: dict) -> bool:
        if r.get("mate") is not None and r["mate"] < 0:
            return True
        return (r.get("perte_cp") or 0) >= SEUIL_REPONSE_FORCEE_CP

    if not all(_perd(r) for r in alternatives):
        return (
            f"Réponse(s) adverse(s) après {label} (issue #91) : plusieurs réponses se "
            f"valent (aucune n'est une réponse UNIQUE qui évite une perte nette ou un "
            f"mat) — la meilleure selon Stockfish est {san_meilleure}."
        )

    menace_texte = _decrire_menace_evitee(board, alternatives[0])
    detail = f" ({menace_texte})" if menace_texte else ""
    return (
        f"Réponse adverse après {label} (issue #91) : {san_meilleure} est la SEULE "
        f"réponse qui évite une perte nette ou un mat — toute autre réponse perd"
        f"{detail}. N'invente AUCUNE autre raison : c'est la vraie raison pour "
        "laquelle cette réponse est forcée."
    )
