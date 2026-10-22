"""
fact_checker.py — ChessCoach (issue #117)

Vérificateur déterministe (aucun appel à un modèle, uniquement python-chess
et le contexte déjà calculé) des affirmations factuelles des avis du coach
en mode exercices, pour les deux agents (Claude et Mistral).

Ce module implémente une version initiale volontairement étroite et prudente
qui vérifie :
  (a) les affirmations « pièce en case » (« ta dame en b5 », « le cavalier en e5 »)
  (b) les affirmations d'attaque par un pion (« le pion X attaque/menace/prend/chasse
      la pièce Y »)
  (c) la cohérence verdict/texte
  (d) le sens de « qui est mieux » (« pour toi », « tu restes mieux », « en ta
      faveur », « pour les Blancs/Noirs ») contre le signe réel de
      l'évaluation et le camp d'Alain, et la formule « pour toi » accolée à
      un chiffre signé (issue #134, suite #128)
  (e) le mot de qualité de la première phrase de l'avis, qui doit reprendre le
      verdict officiel sans l'atténuer (issue #134, suite #128)

Règle de prudence essentielle : le texte peut parler de la position de départ,
de la position après le coup proposé, ou d'une position à n'importe quel moment
de la ligne calculée. Une affirmation n'est signalée comme fausse que si elle
est fausse dans TOUTES les positions candidates. Dans le doute, ne rien signaler.

Les affirmations que le vérificateur ne sait pas interpréter sont ignorées
sans bruit.
"""

import re
import chess
from typing import List, Dict, Tuple, Optional, Set

import avis_format


# Motifs regex pour détecter les affirmations à vérifier
# (a) Pièce en case : "ta dame en b5", "le cavalier en e5", "une tour sur d1", etc.
# Exclure "ce" et "cet" pour éviter de capturer des références à des positions passées
# Utiliser une assertion négative pour exclure "ce " ou "cet " avant la pièce
_PIECE_EN_CASE_PATTERN = re.compile(
    r'(?<!\bce\s)(?<!\bcet\s)'
    r'(?:(?:ta|ton|tes|ma|mon|mes|sa|son|ses|le|la|les|un|une|des)\s+)?'
    r'(dame|roi|tour|fou|cavalier|pion)\s+'
    r'(?:en|sur|à|au|aux)\s+'
    r'([a-h][1-8])',
    re.IGNORECASE
)

# (a) Variante : "dame b5", "cavalier e5" (sans préposition)
# Exclure les cas où la case est suivie de mots comme "sur", "dans", "vers", etc.
# ou de caractères comme "/" pour éviter de capturer des expressions comme "peser sur le pion d4/la colonne"
_PIECE_CASE_SANS_PREPOSITION_PATTERN = re.compile(
    r'(?:(?:ta|ton|tes|ma|mon|mes|sa|son|ses|le|la|les|un|une|des)\s+)?'
    r'(dame|roi|tour|fou|cavalier|pion)\s+'
    r'([a-h][1-8])'
    r'(?!\s+(?:sur|dans|vers|à|au|aux|par|pour|avec)|/|,|;)',
    re.IGNORECASE
)

# (b) Attaque par un pion avec case et pièce explicitement mentionnées
# Pattern: "pion [couleur] en [case] attaque/menace/prend [pièce]"
_PION_ATTAQUE_AVEC_PIECE_PATTERN = re.compile(
    r'pion\s+(?:(blanc|noir|blancs|noirs)\s+)?'
    r'(?:en|sur|à|au|aux)?\s*'
    r'([a-h][1-8])\s+'
    r'(attaqu|menac|prend|chass|captur|frappe|contrôl)\w*\s+'
    r'(?:la|le|les|une|un|ta|ton|tes|ma|mon|mes|sa|son|ses)?\s*'
    r'(dame|roi|tour|fou|cavalier|pion)',
    re.IGNORECASE
)

# (b) Attaque par un pion avec case mentionnée mais pièce implicite
# Pattern: "pion [couleur] en [case] attaque/menace/prend"
_PION_ATTAQUE_CASE_SEULE_PATTERN = re.compile(
    r'pion\s+(?:(blanc|noir|blancs|noirs)\s+)?'
    r'(?:en|sur|à|au|aux)?\s*'
    r'([a-h][1-8])\s+'
    r'(attaqu|menac|prend|chass|captur|frappe|contrôl)\w*',
    re.IGNORECASE
)

# (b) Pattern pour détecter "[case] pour menacer [pièce] en [case]"
# Exemple: "c6 pour menacer ton fou en b7"
_CASE_POUR_MENACER_PIECE_PATTERN = re.compile(
    r'([a-h][1-8])\s+'
    r'pour\s+'
    r'(attaqu|menac|prend|chass|captur|frappe|contrôl)\w*\s+'
    r'(?:la|le|les|une|un|ta|ton|tes|ma|mon|mes|sa|son|ses)?\s*'
    r'(dame|roi|tour|fou|cavalier|pion)\s+'
    r'(?:en|sur|à|au|aux)?\s*'
    r'([a-h][1-8])',
    re.IGNORECASE
)

# (b) Pattern pour détecter "ce pion [couleur] attaque [pièce] et [pièce]"
# Exemple: "ce pion noir attaque ta dame et ton cavalier"
_CE_PION_ATTAQUE_PIECES_PATTERN = re.compile(
    r'ce\s+pion\s+(?:(blanc|noir|blancs|noirs)\s+)?'
    r'(attaqu|menac|prend|chass|captur|frappe|contrôl)\w*\s+'
    r'(?:la|le|les|une|un|ta|ton|tes|ma|mon|mes|sa|son|ses)?\s*'
    r'(dame|roi|tour|fou|cavalier|pion)\s+'
    r'et\s+'
    r'(?:la|le|les|une|un|ta|ton|tes|ma|mon|mes|sa|son|ses)?\s*'
    r'(dame|roi|tour|fou|cavalier|pion)',
    re.IGNORECASE
)

# (b) Pattern pour détecter "[pièce] en [case] est attaquée par le pion [couleur] [case]"
# Exemple: "Ta tour en g8 est immédiatement attaquée par le pion blanc c4"
_PIECE_ATTAQUEE_PAR_PION_PATTERN = re.compile(
    r'(?:la|le|les|une|un|ta|ton|tes|ma|mon|mes|sa|son|ses)?\s*'
    r'(dame|roi|tour|fou|cavalier|pion)\s+'
    r'(?:en|sur|à|au|aux)?\s+'
    r'([a-h][1-8])\s+'
    r'est\s+(?:immédiatement\s+)?attaquée\s+par\s+le\s+pion\s+'
    r'(?:(blanc|noir|blancs|noirs)\s+)?'
    r'(?:en|sur|à|au|aux)?\s*'
    r'([a-h][1-8])',
    re.IGNORECASE
)

# (c) Cohérence verdict/texte : expressions indiquant une incohérence
_INCONSISTENCIES = [
    # "moins précis que le meilleur coup" alors que c'est le meilleur coup
    (r'moins\s+précis\s+(?:que|que le)\s+meilleur\s+coup', re.IGNORECASE),
    (r'moins\s+bon\s+(?:que|que le)\s+meilleur\s+coup', re.IGNORECASE),
    (r'pas\s+aussi\s+bon\s+(?:que|que le)\s+meilleur\s+coup', re.IGNORECASE),
    (r'inférieur\s+au\s+meilleur\s+coup', re.IGNORECASE),
    # "erreur" ou "gaffe" pour un coup de verdict "bon"
    # Utiliser \b pour éviter de matcher des mots comme "erreur" dans "erreur_stratégique"
    # Mais on veut matcher "erreur" comme mot complet
    (r'\b(?:erreur|gaffe|faute)\b', re.IGNORECASE),
]

# Verbes d'attaque pour la vérification des pions
_ATTAQUE_VERBS = {
    'attaqu', 'menac', 'prend', 'chass', 'captur', 'frappe', 'contrôl'
}

# (d) Sens de "qui est mieux" (issue #134, suite #128) : le camp d'Alain
# désigné par une formule en "toi" (pas de chiffre signé sans bornage,
# cf. Convention de signe) et le camp désigné explicitement par couleur.
_SEUIL_EGALITE_CP = 30

_QUI_EST_MIEUX_TOI_PATTERN = re.compile(
    r'pour\s+toi\b|en\s+ta\s+faveur\b|'
    r'tu\s+(?:restes?|es|demeures?)\s+'
    r'(?:largement\s+|légèrement\s+|nettement\s+|toujours\s+|encore\s+)*mieux\b',
    re.IGNORECASE
)

_QUI_EST_MIEUX_CAMP_PATTERN = re.compile(
    r'(?:pour\s+les|en\s+faveur\s+des)\s+(blancs|noirs)\b',
    re.IGNORECASE
)

_POUR_TOI_PATTERN = re.compile(r'pour\s+toi\b', re.IGNORECASE)

_CHIFFRE_SIGNE_PATTERN = re.compile(r'[+\-−–]\s?\d+(?:[.,]\d+)?')

_NEGATION_AVANT_PATTERN = re.compile(r'\b(?:pas|plus|jamais)\b', re.IGNORECASE)

# (e) Mots de qualité connus, par verdict officiel (issue #134, suite #128) :
# "bon coup" doit compter comme "bon", "imprécision"/"imprécis" comme
# "imprecision" (le champ context ne porte pas l'accent).
_VERDICT_MOTS = {
    'bon': {'bon', 'bonne', 'correct', 'correcte', 'juste', 'précis', 'précise',
            'excellent', 'excellente', 'parfait', 'parfaite', 'solide'},
    'imprecision': {'imprécision', 'imprécisions', 'imprécis', 'imprécise'},
    'erreur': {'erreur', 'erreurs'},
    'gaffe': {'gaffe', 'gaffes', 'blunder'},
}
_VERDICT_GRAVITE = {'bon': 0, 'imprecision': 1, 'erreur': 2, 'gaffe': 3}

# Mapping des noms de pièces français vers les lettres python-chess
_PIECE_TYPE_MAP = {
    'dame': chess.QUEEN,
    'roi': chess.KING,
    'tour': chess.ROOK,
    'fou': chess.BISHOP,
    'cavalier': chess.KNIGHT,
    'pion': chess.PAWN,
}

# Couleurs
_COLOR_MAP = {
    'blanc': chess.WHITE,
    'blancs': chess.WHITE,
    'noir': chess.BLACK,
    'noirs': chess.BLACK,
}


def _get_piece_type_french(piece: chess.Piece) -> str:
    """Retourne le nom français d'une pièce python-chess."""
    piece_type = piece.piece_type
    for french, pt in _PIECE_TYPE_MAP.items():
        if pt == piece_type:
            return french
    return "inconnu"


def _get_couleur_from_possessif(possessif: str) -> Optional[int]:
    """Déduit la couleur à partir d'un possessif (ta, ton, tes, ma, mon, mes, etc.)."""
    possessifs_blancs = {'ta', 'ton', 'tes', 'ma', 'mon', 'mes'}
    possessifs_noirs = {'sa', 'son', 'ses'}
    
    possessif_lower = possessif.lower() if possessif else ""
    
    if possessif_lower in possessifs_blancs:
        return chess.WHITE
    elif possessif_lower in possessifs_noirs:
        return chess.BLACK
    
    return None


def _get_couleur_from_article(article: str) -> Optional[int]:
    """Déduit la couleur à partir d'un article + nom de pièce (le cavalier blanc, etc.)."""
    if not article:
        return None
    
    article_lower = article.lower()
    for couleur_fr, couleur in _COLOR_MAP.items():
        if couleur_fr in article_lower:
            return couleur
    
    return None


def _get_all_positions_candidates(context: Dict) -> List[str]:
    """Retourne toutes les positions candidates à vérifier.
    
    Cela inclut :
    - position de départ (fen_depart_exercice ou fen)
    - position après le coup proposé (si disponible)
    - chaque position de la ligne calculée (pv_coup_propose)
    - chaque position de la ligne du meilleur coup (pv_meilleur_coup)
    """
    positions = []
    
    # Position de départ
    fen_depart = context.get('fen_depart_exercice') or context.get('fen')
    if fen_depart and isinstance(fen_depart, str):
        positions.append(fen_depart)
    
    # Position après le coup proposé (si on peut la calculer)
    coup_propose = context.get('coup_propose')
    if coup_propose and isinstance(coup_propose, str) and fen_depart and isinstance(fen_depart, str):
        try:
            board = chess.Board(fen_depart)
            move = board.parse_san(coup_propose) if board.parse_san(coup_propose) else board.parse_uci(coup_propose)
            board.push(move)
            positions.append(board.fen())
        except:
            pass
    
    # Ligne calculée pour le coup proposé
    pv_coup_propose = context.get('pv_coup_propose', '')
    if pv_coup_propose and isinstance(pv_coup_propose, str) and fen_depart and isinstance(fen_depart, str):
        try:
            board = chess.Board(fen_depart)
            moves = pv_coup_propose.split()
            for move_san in moves:
                try:
                    move = board.parse_san(move_san)
                    board.push(move)
                    positions.append(board.fen())
                except:
                    try:
                        move = board.parse_uci(move_san)
                        board.push(move)
                        positions.append(board.fen())
                    except:
                        break
        except:
            pass
    
    # Ligne du meilleur coup
    pv_meilleur_coup = context.get('pv_meilleur_coup', '')
    if pv_meilleur_coup and isinstance(pv_meilleur_coup, str) and fen_depart and isinstance(fen_depart, str):
        try:
            board = chess.Board(fen_depart)
            moves = pv_meilleur_coup.split()
            for move_san in moves:
                try:
                    move = board.parse_san(move_san)
                    board.push(move)
                    positions.append(board.fen())
                except:
                    try:
                        move = board.parse_uci(move_san)
                        board.push(move)
                        positions.append(board.fen())
                    except:
                        break
        except:
            pass
    
    # Supprimer les doublons
    return list(set(positions))


def _verifier_piece_en_case(
    texte: str,
    positions_candidates: List[str],
    camp_alain: Optional[str] = None
) -> List[Dict]:
    """Vérifie les affirmations "pièce en case" dans le texte.
    
    Retourne une liste d'alertes pour les affirmations fausses.
    Une affirmation est fausse si la pièce mentionnée n'est PAS sur la case
    mentionnée dans TOUTES les positions candidates.
    """
    alertes = []
    
    # Trouver toutes les mentions de pièce en case
    matches = _PIECE_EN_CASE_PATTERN.finditer(texte)
    
    for match in matches:
        piece_nom = match.group(1).lower()
        case = match.group(2).lower()
        
        # Déterminer la couleur si possible
        # Chercher dans le texte avant le nom de la pièce (pas avant le match complet)
        # Le match est de la forme "[possessif] pièce préposition case"
        # On veut chercher le possessif dans les 15 caractères avant le nom de la pièce
        
        # Trouver la position du nom de la pièce dans le match
        # Le groupe 1 est le nom de la pièce
        piece_start_in_match = match.start(1)
        texte_avant_piece = texte[max(0, match.start() + piece_start_in_match - 15):match.start() + piece_start_in_match]
        
        # Chercher un possessif ou un article de couleur
        couleur = None
        
        # Chercher un possessif immédiatement avant le nom de la pièce
        possessif_match = re.search(
            r'\b(ta|ton|tes|ma|mon|mes|sa|son|ses)\s+$',
            texte_avant_piece,
            re.IGNORECASE
        )
        if possessif_match:
            couleur = _get_couleur_from_possessif(possessif_match.group(1))
        
        # Chercher un article de couleur dans les 15 caractères avant le nom de la pièce
        if couleur is None:
            couleur_match = re.search(
                r'\b(blanc|blancs|noir|noirs)\s+$',
                texte_avant_piece,
                re.IGNORECASE
            )
            if couleur_match:
                couleur = _COLOR_MAP.get(couleur_match.group(1).lower())
        
        # Vérifier dans toutes les positions candidates
        piece_trouvee_dans_une_position = False
        
        for fen in positions_candidates:
            try:
                board = chess.Board(fen)
                piece = board.piece_at(chess.parse_square(case))
                
                if piece is not None:
                    piece_type = piece.piece_type
                    piece_color = piece.color
                    
                    # Vérifier le type de pièce
                    expected_type = _PIECE_TYPE_MAP.get(piece_nom)
                    if expected_type is None:
                        continue
                    
                    # Si la couleur est spécifiée, vérifier aussi la couleur
                    if couleur is not None:
                        if piece_type == expected_type and piece_color == couleur:
                            piece_trouvee_dans_une_position = True
                            break
                    else:
                        # Sans couleur spécifiée, on vérifie juste le type
                        if piece_type == expected_type:
                            piece_trouvee_dans_une_position = True
                            break
            except:
                continue
        
        # Si la pièce n'a pas été trouvée dans AUCUNE position candidate,
        # c'est une alerte
        if not piece_trouvee_dans_une_position:
            alerte = {
                'type': 'piece_en_case',
                'affirmation': f"{match.group(0)}",
                'piece': piece_nom,
                'case': case,
                'couleur': 'blancs' if couleur == chess.WHITE else 'noirs' if couleur == chess.BLACK else None,
                'details': f"Aucune {piece_nom} {'blanche' if couleur == chess.WHITE else 'noire' if couleur == chess.BLACK else ''} en {case} dans les positions candidates"
            }
            alertes.append(alerte)
    
    return alertes


def _verifier_piece_case_sans_preposition(
    texte: str,
    positions_candidates: List[str],
    camp_alain: Optional[str] = None
) -> List[Dict]:
    """Vérifie les affirmations "pièce case" sans préposition (ex: "dame b5").
    
    Retourne une liste d'alertes pour les affirmations fausses.
    """
    alertes = []
    
    # Trouver toutes les mentions de pièce + case sans préposition
    matches = _PIECE_CASE_SANS_PREPOSITION_PATTERN.finditer(texte)
    
    for match in matches:
        piece_nom = match.group(1).lower()
        case = match.group(2).lower()
        
        # Déterminer la couleur si possible
        # Chercher dans le texte avant le nom de la pièce
        piece_start_in_match = match.start(1)
        texte_avant_piece = texte[max(0, match.start() + piece_start_in_match - 15):match.start() + piece_start_in_match]
        
        couleur = None
        
        possessif_match = re.search(
            r'\b(ta|ton|tes|ma|mon|mes|sa|son|ses)\s+$',
            texte_avant_piece,
            re.IGNORECASE
        )
        if possessif_match:
            couleur = _get_couleur_from_possessif(possessif_match.group(1))
        
        couleur_match = re.search(
            r'\b(blanc|blancs|noir|noirs)\s+$',
            texte_avant_piece,
            re.IGNORECASE
        )
        if couleur_match:
            couleur = _COLOR_MAP.get(couleur_match.group(1).lower())
        
        # Vérifier dans toutes les positions candidates
        piece_trouvee_dans_une_position = False
        
        for fen in positions_candidates:
            try:
                board = chess.Board(fen)
                piece = board.piece_at(chess.parse_square(case))
                
                if piece is not None:
                    piece_type = piece.piece_type
                    piece_color = piece.color
                    
                    expected_type = _PIECE_TYPE_MAP.get(piece_nom)
                    if expected_type is None:
                        continue
                    
                    if couleur is not None:
                        if piece_type == expected_type and piece_color == couleur:
                            piece_trouvee_dans_une_position = True
                            break
                    else:
                        if piece_type == expected_type:
                            piece_trouvee_dans_une_position = True
                            break
            except:
                continue
        
        if not piece_trouvee_dans_une_position:
            alerte = {
                'type': 'piece_case_sans_preposition',
                'affirmation': f"{match.group(0)}",
                'piece': piece_nom,
                'case': case,
                'couleur': 'blancs' if couleur == chess.WHITE else 'noirs' if couleur == chess.BLACK else None,
                'details': f"Aucune {piece_nom} {'blanche' if couleur == chess.WHITE else 'noire' if couleur == chess.BLACK else ''} en {case} dans les positions candidates"
            }
            alertes.append(alerte)
    
    return alertes


def _verifier_pion_attaque_avec_piece(
    texte: str,
    positions_candidates: List[str]
) -> List[Dict]:
    """Vérifie les affirmations d'attaque par un pion avec pièce explicitement mentionnée.
    
    Pattern: "pion [couleur] en [case] attaque/menace/prend [pièce]"
    """
    alertes = []
    
    matches = _PION_ATTAQUE_AVEC_PIECE_PATTERN.finditer(texte)
    
    for match in matches:
        pion_couleur_str = match.group(1)
        pion_case = match.group(2).lower()
        verbe = match.group(3).lower()
        piece_attaquee = match.group(4).lower()
        
        # Déterminer la couleur du pion
        if pion_couleur_str:
            couleur = _COLOR_MAP.get(pion_couleur_str.lower())
        else:
            couleur = None
        
        if couleur is None:
            continue
        
        # Vérifier la géométrie d'attaque du pion
        # Un pion attaque diagonalement en avant d'une case
        try:
            pion_square = chess.parse_square(pion_case)
        except:
            continue
        
        if couleur == chess.WHITE:
            # Pion blanc : attaque une case en diagonale devant (rang + 1)
            attaques_possibles = [pion_square + 7, pion_square + 9]
        else:
            # Pion noir : attaque une case en diagonale devant (rang - 1)
            attaques_possibles = [pion_square - 7, pion_square - 9]
        
        # Filtrer les cases valides (0-63)
        attaques_possibles = [sq for sq in attaques_possibles if 0 <= sq < 64]
        
        # Vérifier dans toutes les positions candidates
        attaque_valide_dans_une_position = False
        
        for fen in positions_candidates:
            try:
                board = chess.Board(fen)
                piece = board.piece_at(pion_square)
                
                # Vérifier que c'est bien un pion de la bonne couleur
                if piece and piece.piece_type == chess.PAWN and piece.color == couleur:
                    # Vérifier que le pion attaque bien une pièce de type piece_attaquee
                    expected_type = _PIECE_TYPE_MAP.get(piece_attaquee)
                    if expected_type is None:
                        continue
                    
                    # Vérifier si une pièce de ce type est sur une case attaquée par le pion
                    for attaque_sq in attaques_possibles:
                        piece_cible = board.piece_at(attaque_sq)
                        if piece_cible and piece_cible.piece_type == expected_type:
                            attaque_valide_dans_une_position = True
                            break
                    
                    if attaque_valide_dans_une_position:
                        break
            except:
                continue
        
        if not attaque_valide_dans_une_position:
            alerte = {
                'type': 'pion_attaque_avec_piece',
                'affirmation': f"pion {'blanc' if couleur == chess.WHITE else 'noir'} en {pion_case} {verbe} {piece_attaquee}",
                'pion_case': pion_case,
                'pion_couleur': 'blancs' if couleur == chess.WHITE else 'noirs',
                'piece_attaquee': piece_attaquee,
                'details': f"Un pion {'blanc' if couleur == chess.WHITE else 'noir'} en {pion_case} n'attaque pas de {piece_attaquee} dans les positions candidates"
            }
            alertes.append(alerte)
    
    return alertes


def _verifier_pion_attaque_case_seule(
    texte: str,
    positions_candidates: List[str]
) -> List[Dict]:
    """Vérifie les affirmations d'attaque par un pion avec case mentionnée mais pièce non mentionnée.
    
    Pattern: "pion [couleur] en [case] attaque/menace/prend"
    
    Pour ces cas, on vérifie que le pion existe bien et qu'il attaque au moins une pièce.
    """
    alertes = []
    
    matches = _PION_ATTAQUE_CASE_SEULE_PATTERN.finditer(texte)
    
    for match in matches:
        pion_couleur_str = match.group(1)
        pion_case = match.group(2).lower()
        verbe = match.group(3).lower()
        
        # Déterminer la couleur du pion
        if pion_couleur_str:
            couleur = _COLOR_MAP.get(pion_couleur_str.lower())
        else:
            couleur = None
        
        if couleur is None:
            continue
        
        # Vérifier que le pion existe et attaque bien quelque chose
        try:
            pion_square = chess.parse_square(pion_case)
        except:
            continue
        
        # Vérifier dans toutes les positions candidates
        pion_existe_et_attaque = False
        
        for fen in positions_candidates:
            try:
                board = chess.Board(fen)
                piece = board.piece_at(pion_square)
                
                # Vérifier que c'est bien un pion de la bonne couleur
                if piece and piece.piece_type == chess.PAWN and piece.color == couleur:
                    # Calculer les cases attaquées par ce pion
                    if couleur == chess.WHITE:
                        attaques_possibles = [pion_square + 7, pion_square + 9]
                    else:
                        attaques_possibles = [pion_square - 7, pion_square - 9]
                    
                    attaques_possibles = [sq for sq in attaques_possibles if 0 <= sq < 64]
                    
                    # Vérifier si au moins une pièce est sur une case attaquée
                    for attaque_sq in attaques_possibles:
                        if board.piece_at(attaque_sq) is not None:
                            pion_existe_et_attaque = True
                            break
                    
                    if pion_existe_et_attaque:
                        break
            except:
                continue
        
        # Si le pion n'existe pas OU n'attaque rien dans AUCUNE position candidate
        if not pion_existe_et_attaque:
            alerte = {
                'type': 'pion_attaque_case_seule',
                'affirmation': f"pion {'blanc' if couleur == chess.WHITE else 'noir'} en {pion_case} {verbe}",
                'pion_case': pion_case,
                'pion_couleur': 'blancs' if couleur == chess.WHITE else 'noirs',
                'details': f"Le pion {'blanc' if couleur == chess.WHITE else 'noir'} en {pion_case} n'existe pas ou n'attaque rien dans les positions candidates"
            }
            alertes.append(alerte)
    
    return alertes


def _verifier_case_pour_menacer_piece(
    texte: str,
    positions_candidates: List[str]
) -> List[Dict]:
    """Vérifie les affirmations du type "[case] pour menacer [pièce] en [case]".
    
    Exemple: "c6 pour menacer ton fou en b7"
    
    Cela signifie qu'un pion (ou une pièce) en [case1] menace [pièce] en [case2].
    Pour un pion, on vérifie la géométrie d'attaque.
    """
    alertes = []
    
    matches = _CASE_POUR_MENACER_PIECE_PATTERN.finditer(texte)
    
    for match in matches:
        case_attaquante = match.group(1).lower()
        verbe = match.group(2).lower()
        piece_attaquee = match.group(3).lower()
        case_attaquee = match.group(4).lower()
        
        # Vérifier la géométrie d'attaque
        try:
            attaquant_square = chess.parse_square(case_attaquante)
            attaquee_square = chess.parse_square(case_attaquee)
        except:
            continue
        
        # Vérifier dans toutes les positions candidates
        attaque_valide_dans_une_position = False
        
        for fen in positions_candidates:
            try:
                board = chess.Board(fen)
                piece_attaquante = board.piece_at(attaquant_square)
                
                if piece_attaquante is not None:
                    piece_attaquee_obj = board.piece_at(attaquee_square)
                    
                    # Si c'est un pion, vérifier la géométrie spécifique
                    if piece_attaquante.piece_type == chess.PAWN:
                        couleur = piece_attaquante.color
                        
                        # Calculer les cases qu'un pion de cette couleur attaquerait
                        if couleur == chess.WHITE:
                            attaques_possibles = [attaquant_square + 7, attaquant_square + 9]
                        else:
                            attaques_possibles = [attaquant_square - 7, attaquant_square - 9]
                        
                        attaques_possibles = [sq for sq in attaques_possibles if 0 <= sq < 64]
                        
                        # Vérifier si la case attaquée est dans les attaques possibles
                        if attaquee_square in attaques_possibles:
                            # Vérifier que la pièce attaquée existe et correspond au type
                            expected_type = _PIECE_TYPE_MAP.get(piece_attaquee)
                            if piece_attaquee_obj and piece_attaquee_obj.piece_type == expected_type:
                                attaque_valide_dans_une_position = True
                                break
                    else:
                        # Pour les autres pièces, vérifier si elles attaquent la case
                        if board.is_attacked_by(piece_attaquante.color, attaquee_square):
                            # Vérifier que la pièce attaquée existe et correspond au type
                            expected_type = _PIECE_TYPE_MAP.get(piece_attaquee)
                            if piece_attaquee_obj and piece_attaquee_obj.piece_type == expected_type:
                                attaque_valide_dans_une_position = True
                                break
            except:
                continue
        
        if not attaque_valide_dans_une_position:
            alerte = {
                'type': 'case_pour_menacer_piece',
                'affirmation': f"{case_attaquante} pour {verbe} {piece_attaquee} en {case_attaquee}",
                'case_attaquante': case_attaquante,
                'piece_attaquee': piece_attaquee,
                'case_attaquee': case_attaquee,
                'details': f"La case {case_attaquante} ne menace pas {piece_attaquee} en {case_attaquee} dans les positions candidates"
            }
            alertes.append(alerte)
    
    return alertes


def _verifier_ce_pion_attaque_pieces(
    texte: str,
    positions_candidates: List[str]
) -> List[Dict]:
    """Vérifie les affirmations du type "ce pion [couleur] attaque [pièce] et [pièce]".
    
    Exemple: "ce pion noir attaque ta dame et ton cavalier"
    ou "les Noirs répondent d4 : ce pion noir attaque ta dame et ton cavalier"
    
    On vérifie que le pion attaque bien les deux pièces mentionnées.
    """
    alertes = []
    
    matches = _CE_PION_ATTAQUE_PIECES_PATTERN.finditer(texte)
    
    for match in matches:
        pion_couleur_str = match.group(1)
        verbe = match.group(2).lower()
        piece1 = match.group(3).lower()
        piece2 = match.group(4).lower()
        
        # Déterminer la couleur du pion
        if pion_couleur_str:
            couleur = _COLOR_MAP.get(pion_couleur_str.lower())
        else:
            couleur = None
        
        if couleur is None:
            continue
        
        # Trouver la case du pion dans le texte
        # Chercher dans les 50 caractères avant "ce pion"
        match_start = match.start()
        texte_avant = texte[max(0, match_start - 50):match_start]
        
        # Chercher une case mentionnée avant, avec des patterns comme "d4", "en d4", "sur d4", "répondent d4"
        # Mais ignorer les cases qui font partie d'un coup (ex: Bh3, cxd5)
        # On cherche une case qui n'est PAS précédée d'une lettre de pièce (D, T, C, F, R, P)
        case_match = re.search(
            r'(?:répondent|jouent|poussent|avancent|placent)?\s*'
            r'(?:en|sur|à|au|aux|:)?\s*'
            r'(?<![A-Za-z])([a-h][1-8])',
            texte_avant,
            re.IGNORECASE
        )
        
        if not case_match:
            # Chercher après "ce pion" et avant le verbe
            texte_apres_pion = texte[match_start:match.start(2)]
            case_match = re.search(r'([a-h][1-8])', texte_apres_pion, re.IGNORECASE)
        
        if not case_match:
            continue
        
        pion_case = case_match.group(1).lower()
        
        # Vérifier la géométrie d'attaque du pion
        try:
            pion_square = chess.parse_square(pion_case)
        except:
            continue
        
        if couleur == chess.WHITE:
            attaques_possibles = [pion_square + 7, pion_square + 9]
        else:
            attaques_possibles = [pion_square - 7, pion_square - 9]
        
        attaques_possibles = [sq for sq in attaques_possibles if 0 <= sq < 64]
        
        # Vérifier dans toutes les positions candidates
        attaque_valide_dans_une_position = False
        
        for fen in positions_candidates:
            try:
                board = chess.Board(fen)
                piece = board.piece_at(pion_square)
                
                # Vérifier que c'est bien un pion de la bonne couleur
                if piece and piece.piece_type == chess.PAWN and piece.color == couleur:
                    # Vérifier que le pion attaque bien les deux pièces mentionnées
                    expected_type1 = _PIECE_TYPE_MAP.get(piece1)
                    expected_type2 = _PIECE_TYPE_MAP.get(piece2)
                    
                    if expected_type1 is None or expected_type2 is None:
                        continue
                    
                    # Vérifier si les deux types de pièces sont sur des cases attaquées par le pion
                    pieces_trouvees = []
                    for attaque_sq in attaques_possibles:
                        piece_cible = board.piece_at(attaque_sq)
                        if piece_cible:
                            pieces_trouvees.append(piece_cible.piece_type)
                    
                    # Vérifier si les deux types sont présents
                    if expected_type1 in pieces_trouvees and expected_type2 in pieces_trouvees:
                        attaque_valide_dans_une_position = True
                        break
            except:
                continue
        
        if not attaque_valide_dans_une_position:
            alerte = {
                'type': 'ce_pion_attaque_pieces',
                'affirmation': f"ce pion {'noir' if couleur == chess.BLACK else 'blanc'} en {pion_case} attaque {piece1} et {piece2}",
                'pion_case': pion_case,
                'pion_couleur': 'noirs' if couleur == chess.BLACK else 'blancs',
                'piece1': piece1,
                'piece2': piece2,
                'details': f"Un pion {'noir' if couleur == chess.BLACK else 'blanc'} en {pion_case} n'attaque pas à la fois {piece1} et {piece2} dans les positions candidates"
            }
            alertes.append(alerte)
    
    return alertes


def _verifier_piece_attaquee_par_pion(
    texte: str,
    positions_candidates: List[str]
) -> List[Dict]:
    """Vérifie les affirmations du type "[pièce] en [case] est attaquée par le pion [couleur] [case]".
    
    Exemple: "Ta tour en g8 est immédiatement attaquée par le pion blanc c4"
    """
    alertes = []
    
    matches = _PIECE_ATTAQUEE_PAR_PION_PATTERN.finditer(texte)
    
    for match in matches:
        piece_nom = match.group(1).lower()
        piece_case = match.group(2).lower()
        pion_couleur_str = match.group(3)
        pion_case = match.group(4).lower()
        
        # Déterminer la couleur du pion
        if pion_couleur_str:
            couleur = _COLOR_MAP.get(pion_couleur_str.lower())
        else:
            couleur = None
        
        if couleur is None:
            continue
        
        # Vérifier la géométrie d'attaque
        try:
            pion_square = chess.parse_square(pion_case)
            piece_square = chess.parse_square(piece_case)
        except:
            continue
        
        # Calculer les cases qu'un pion de cette couleur attaquerait
        if couleur == chess.WHITE:
            attaques_possibles = [pion_square + 7, pion_square + 9]
        else:
            attaques_possibles = [pion_square - 7, pion_square - 9]
        
        attaques_possibles = [sq for sq in attaques_possibles if 0 <= sq < 64]
        
        # Vérifier dans toutes les positions candidates
        attaque_valide_dans_une_position = False
        
        for fen in positions_candidates:
            try:
                board = chess.Board(fen)
                
                # Vérifier que le pion existe
                pion = board.piece_at(pion_square)
                if not (pion and pion.piece_type == chess.PAWN and pion.color == couleur):
                    continue
                
                # Vérifier que la pièce existe
                piece = board.piece_at(piece_square)
                if not piece:
                    continue
                
                # Vérifier le type de pièce
                expected_type = _PIECE_TYPE_MAP.get(piece_nom)
                if expected_type is None:
                    continue
                
                if piece.piece_type != expected_type:
                    continue
                
                # Vérifier que le pion attaque bien la case de la pièce
                if piece_square in attaques_possibles:
                    attaque_valide_dans_une_position = True
                    break
            except:
                continue
        
        if not attaque_valide_dans_une_position:
            alerte = {
                'type': 'piece_attaquee_par_pion',
                'affirmation': f"{piece_nom} en {piece_case} est attaquée par le pion {'blanc' if couleur == chess.WHITE else 'noir'} en {pion_case}",
                'piece': piece_nom,
                'piece_case': piece_case,
                'pion_case': pion_case,
                'pion_couleur': 'blancs' if couleur == chess.WHITE else 'noirs',
                'details': f"Le pion {'blanc' if couleur == chess.WHITE else 'noir'} en {pion_case} n'attaque pas {piece_nom} en {piece_case} dans les positions candidates"
            }
            alertes.append(alerte)
    
    return alertes


def _verifier_coherence_verdict(
    texte: str,
    verdict: Optional[str],
    meilleur_coup: Optional[str],
    coup_propose: Optional[str]
) -> List[Dict]:
    """Vérifie la cohérence entre le verdict et le texte de l'avis.
    
    Retourne une liste d'alertes pour les incohérences détectées.
    """
    alertes = []
    
    if not verdict:
        return alertes
    
    texte_lower = texte.lower()
    
    # (c) Vérifier "moins précis que le meilleur coup" alors que c'est le meilleur coup
    if coup_propose and meilleur_coup and coup_propose == meilleur_coup:
        for pattern, _ in _INCONSISTENCIES[:4]:  # Les 4 premiers patterns
            if re.search(pattern, texte_lower):
                alerte = {
                    'type': 'coherence_verdict',
                    'affirmation': f"Le coup proposé est le meilleur coup, mais l'avis dit qu'il est moins précis",
                    'verdict': verdict,
                    'coup_propose': coup_propose,
                    'meilleur_coup': meilleur_coup,
                    'details': f"Contradiction : le coup proposé ({coup_propose}) est le meilleur coup, mais l'avis affirme qu'il est moins précis"
                }
                alertes.append(alerte)
                break
    
    # (c) Vérifier "erreur" ou "gaffe" pour un coup de verdict "bon"
    # On vérifie que le mot "erreur", "gaffe" ou "faute" apparaît comme mot complet
    # et pas comme partie d'un autre mot
    if verdict.lower() in ['bon', 'excellent', 'parfait']:
        for pattern, _ in _INCONSISTENCIES[4:]:  # Les patterns d'erreur/gaffe
            if re.search(pattern, texte_lower):
                # Vérifier que ce n'est pas dans un contexte où on parle d'une erreur passée
                # ou d'une erreur de l'adversaire
                # On va être plus prudent : vérifier que le mot n'est pas précédé de "ton", "ta", "tes", etc.
                # qui indiquerait qu'on parle de l'erreur d'Alain
                
                # Chercher toutes les occurrences du pattern
                matches = re.finditer(pattern, texte_lower)
                for match in matches:
                    # Vérifier le contexte autour du match
                    start = max(0, match.start() - 20)
                    end = min(len(texte_lower), match.end() + 20)
                    contexte = texte_lower[start:end]
                    
                    # Si on trouve des possessifs d'Alain (ta, ton, tes, ma, mon, mes) avant le mot,
                    # c'est probablement une erreur d'Alain, donc incohérent avec verdict "bon"
                    # Sinon, on ignore pour éviter les fausses alertes
                    possessifs_alain = ['ta ', 'ton ', 'tes ', 'ma ', 'mon ', 'mes ']
                    if any(poss in contexte[:match.start() - start + 3] for poss in possessifs_alain):
                        alerte = {
                            'type': 'coherence_verdict',
                            'affirmation': f"L'avis qualifie le coup d'erreur/gaffe alors que le verdict est '{verdict}'",
                            'verdict': verdict,
                            'details': f"Incohérence : verdict '{verdict}' mais l'avis utilise des termes comme 'erreur' ou 'gaffe' pour le coup d'Alain"
                        }
                        alertes.append(alerte)
                        break
                    elif match.start() < 50:
                        # Si le mot apparaît dans les 50 premiers caractères, c'est probablement
                        # une qualification du coup d'Alain
                        alerte = {
                            'type': 'coherence_verdict',
                            'affirmation': f"L'avis qualifie le coup d'erreur/gaffe alors que le verdict est '{verdict}'",
                            'verdict': verdict,
                            'details': f"Incohérence : verdict '{verdict}' mais l'avis utilise des termes comme 'erreur' ou 'gaffe' pour le coup d'Alain"
                        }
                        alertes.append(alerte)
                        break
                
                if alertes:
                    break
    
    return alertes


def _camp_mieux_reel(context: Dict) -> Optional[str]:
    """Détermine, à partir du signe de l'évaluation du contexte (avant et/ou
    après le coup — peu importe laquelle est citée dans le texte, issue
    #134), quel camp est réellement mieux. Retourne 'blancs', 'noirs', ou
    None si aucune évaluation n'est disponible, si elle est trop proche de
    l'égalité (< _SEUIL_EGALITE_CP), ou si avant/après se contredisent (le
    camp mieux placé a changé entre les deux) — dans le doute, ne rien
    signaler, comme le reste de ce module."""
    camps = []
    for champ in ("eval_before_cp", "eval_after_cp"):
        valeur = context.get(champ)
        if isinstance(valeur, (int, float)) and abs(valeur) >= _SEUIL_EGALITE_CP:
            camps.append("blancs" if valeur > 0 else "noirs")
    if not camps or len(set(camps)) > 1:
        return None
    return camps[0]


def _verifier_sens_qui_est_mieux(
    texte: str,
    context: Dict,
    camp_alain: Optional[str] = None
) -> List[Dict]:
    """Vérifie que les phrases désignant qui est mieux ("pour toi", "tu
    restes mieux", "en ta faveur", "pour les Blancs/Noirs", "en faveur des
    Blancs/Noirs") ne contredisent pas le signe réel de l'évaluation du
    contexte, une fois ramené au camp d'Alain (issue #134, suite #128).

    Prudence : sans évaluation exploitable (cf. _camp_mieux_reel) ou sans
    camp_alain connu pour une formule en "toi", rien n'est signalé.
    """
    alertes = []

    camp_mieux = _camp_mieux_reel(context)
    if camp_mieux is None:
        return alertes

    camp_alain_norm = (camp_alain or "").strip().lower()
    if camp_alain_norm not in ("blancs", "noirs"):
        camp_alain_norm = None

    phrases = re.split(r'(?<=[.!?\n])\s+', texte)

    for phrase in phrases:
        camp_implique = None

        m_toi = _QUI_EST_MIEUX_TOI_PATTERN.search(phrase)
        if m_toi and camp_alain_norm:
            avant = phrase[max(0, m_toi.start() - 15):m_toi.start()]
            if not _NEGATION_AVANT_PATTERN.search(avant):
                camp_implique = camp_alain_norm

        if camp_implique is None:
            m_camp = _QUI_EST_MIEUX_CAMP_PATTERN.search(phrase)
            if m_camp:
                avant = phrase[max(0, m_camp.start() - 15):m_camp.start()]
                if not _NEGATION_AVANT_PATTERN.search(avant):
                    camp_implique = m_camp.group(1).lower()

        if camp_implique and camp_implique != camp_mieux:
            alertes.append({
                'type': 'sens_qui_est_mieux_inverse',
                'affirmation': phrase.strip(),
                'camp_implique': camp_implique,
                'camp_reel_mieux': camp_mieux,
                'details': (
                    f"La phrase désigne {camp_implique} comme mieux placé, mais "
                    f"le signe de l'évaluation du contexte indique que ce sont "
                    f"les {camp_mieux} qui sont mieux placés."
                )
            })

    return alertes


def _verifier_pour_toi_chiffre_colle(texte: str) -> List[Dict]:
    """Vérifie qu'aucune formule "pour toi" n'est accolée à un chiffre signé
    (issue #134, suite #128) — interdit par la convention de signe de
    l'issue #128 quel que soit le signe réel du chiffre : "pour toi" doit
    toujours être dans une phrase sans aucun chiffre.

    La fenêtre de proximité (45 caractères) est cherchée DANS LA MÊME
    PHRASE que "pour toi" (jamais au-delà d'un '.'/'!'/'?'/saut de ligne),
    pour ne pas rattacher à tort un chiffre d'une phrase précédente ou
    suivante sans rapport (prudence)."""
    alertes = []

    phrases = re.split(r'(?<=[.!?\n])\s+', texte)
    for phrase in phrases:
        for match in _POUR_TOI_PATTERN.finditer(phrase):
            fenetre = phrase[max(0, match.start() - 45):min(len(phrase), match.end() + 45)]
            if _CHIFFRE_SIGNE_PATTERN.search(fenetre):
                alertes.append({
                    'type': 'pour_toi_colle_chiffre',
                    'affirmation': fenetre.strip(),
                    'details': (
                        "La formule \"pour toi\" est accolée à un chiffre signé "
                        "(interdit par la convention de signe de l'issue #128, "
                        "même si le chiffre lui-même est correct)."
                    )
                })

    return alertes


def _premiere_phrase(texte: str) -> str:
    """Retourne la première phrase du texte (jusqu'au premier '.', '!', '?'
    ou saut de ligne), ou le texte entier si aucun de ces séparateurs n'y
    figure."""
    match = re.search(r'^(.*?[.!?\n])', texte.strip(), re.DOTALL)
    return match.group(1) if match else texte.strip()


def _mot_verdict_dans_phrase(phrase: str) -> Optional[str]:
    """Retourne le verdict ('bon'/'imprecision'/'erreur'/'gaffe') correspondant
    au premier mot de qualité connu trouvé dans la phrase, ou None si aucun
    de ces mots n'y figure."""
    phrase_lower = phrase.lower()
    candidats = []
    for verdict, mots in _VERDICT_MOTS.items():
        for mot in mots:
            for m in re.finditer(r'\b' + re.escape(mot) + r'\b', phrase_lower):
                candidats.append((m.start(), verdict))
    if not candidats:
        return None
    candidats.sort()
    return candidats[0][1]


def _texte_evaluation_rapide_ou_premiere_phrase(texte: str) -> str:
    """Texte à inspecter pour le mot de qualité du verdict (issue #135,
    suite #134/#128) : depuis le format à titres fixes imposé par le
    prompt système (cf. avis_format.py), ce n'est plus la première phrase
    de la réponse ENTIÈRE (qui serait désormais le titre "## Coup joué",
    sans aucun mot de verdict) mais le contenu de la rubrique "Évaluation
    rapide" sous "Coup joué" — seule rubrique censée l'énoncer.

    Repli sur l'ancien comportement (première phrase du texte brut) quand
    le format n'est pas respecté (titre manquant ou désordonné) : app.py
    affiche alors le texte brut tel quel, ce contrôle doit continuer à
    s'appliquer dessus plutôt que de se taire silencieusement."""
    avis = avis_format.parser_avis(texte)
    if avis["conforme"]:
        return _premiere_phrase(avis["sections"]["coup_joue_evaluation_rapide"])
    return _premiere_phrase(texte)


def _verifier_mot_verdict_premiere_phrase(
    texte: str,
    verdict_officiel: Optional[str]
) -> List[Dict]:
    """Vérifie que le mot de qualité de la rubrique "Évaluation rapide" (ou,
    à défaut de format conforme, de la première phrase du texte brut) reprend
    le verdict officiel fourni, sans l'atténuer (issue #134, suite #128 ;
    adapté au format à titres fixes par l'issue #135, suite #125) — par
    exemple ouvrir sur "imprécision" alors que le verdict officiel est
    "erreur" ou "gaffe"."""
    alertes = []

    if not verdict_officiel:
        return alertes
    verdict_officiel_norm = verdict_officiel.strip().lower()
    if verdict_officiel_norm not in _VERDICT_GRAVITE:
        return alertes

    premiere = _texte_evaluation_rapide_ou_premiere_phrase(texte)
    mot_detecte = _mot_verdict_dans_phrase(premiere)

    if mot_detecte is None or mot_detecte == verdict_officiel_norm:
        return alertes

    alertes.append({
        'type': 'mot_verdict_premiere_phrase',
        'affirmation': premiere.strip(),
        'verdict_officiel': verdict_officiel_norm,
        'verdict_detecte': mot_detecte,
        'details': (
            f"La première phrase utilise le mot de qualité \"{mot_detecte}\" "
            f"alors que le verdict officiel est \"{verdict_officiel_norm}\"."
        )
    })

    return alertes


def verifier_affirmations(
    texte: str,
    context: Dict,
    agent: str = "inconnu",
    camp_alain: Optional[str] = None
) -> Dict:
    """Fonction principale : vérifie toutes les affirmations factuelles dans le texte.
    
    Paramètres :
      texte : le texte de l'avis du coach à vérifier
      context : le contexte envoyé au coach (contient FEN, coups, verdict, etc.)
      agent : l'agent qui a produit l'avis (Claude ou Mistral)
      camp_alain : le camp d'Alain ("blancs" ou "noirs")
    
    Retourne :
      {
        'alertes': [liste des alertes détectées],
        'affirmations_verifiees': nombre d'affirmations vérifiées,
        'affirmations_ignorees': nombre d'affirmations ignorées
      }
    """
    positions_candidates = _get_all_positions_candidates(context)

    alertes = []
    affirmations_verifiees = 0
    affirmations_ignorees = 0

    if positions_candidates:
        # (a) Vérifier les affirmations "pièce en case"
        piece_en_case_alertes = _verifier_piece_en_case(texte, positions_candidates, camp_alain)
        alertes.extend(piece_en_case_alertes)
        affirmations_verifiees += len(piece_en_case_alertes)

        # (a) Vérifier les affirmations "pièce case" sans préposition
        piece_case_sans_prep_alertes = _verifier_piece_case_sans_preposition(texte, positions_candidates, camp_alain)
        alertes.extend(piece_case_sans_prep_alertes)
        affirmations_verifiees += len(piece_case_sans_prep_alertes)

        # (b) Vérifier les affirmations d'attaque par un pion avec pièce explicitement mentionnée
        pion_attaque_avec_piece_alertes = _verifier_pion_attaque_avec_piece(texte, positions_candidates)
        alertes.extend(pion_attaque_avec_piece_alertes)
        affirmations_verifiees += len(pion_attaque_avec_piece_alertes)

        # (b) Vérifier les affirmations d'attaque par un pion avec case seule
        pion_attaque_case_seule_alertes = _verifier_pion_attaque_case_seule(texte, positions_candidates)
        alertes.extend(pion_attaque_case_seule_alertes)
        affirmations_verifiees += len(pion_attaque_case_seule_alertes)

        # (b) Vérifier les affirmations "[case] pour menacer [pièce] en [case]"
        case_pour_menacer_alertes = _verifier_case_pour_menacer_piece(texte, positions_candidates)
        alertes.extend(case_pour_menacer_alertes)
        affirmations_verifiees += len(case_pour_menacer_alertes)

        # (b) Vérifier les affirmations "ce pion [couleur] attaque [pièce] et [pièce]"
        ce_pion_attaque_alertes = _verifier_ce_pion_attaque_pieces(texte, positions_candidates)
        alertes.extend(ce_pion_attaque_alertes)
        affirmations_verifiees += len(ce_pion_attaque_alertes)

        # (b) Vérifier les affirmations "[pièce] en [case] est attaquée par le pion [couleur] [case]"
        piece_attaquee_par_pion_alertes = _verifier_piece_attaquee_par_pion(texte, positions_candidates)
        alertes.extend(piece_attaquee_par_pion_alertes)
        affirmations_verifiees += len(piece_attaquee_par_pion_alertes)

    # (c) Vérifier la cohérence verdict/texte
    # Issue #125 : utiliser le verdict officiel Lichess pour la vérification
    verdict = context.get('verdict_qualite_officiel') if isinstance(context.get('verdict_qualite_officiel'), str) else context.get('verdict_qualite') if isinstance(context.get('verdict_qualite'), str) else None
    meilleur_coup = context.get('meilleur_coup') if isinstance(context.get('meilleur_coup'), str) else None
    coup_propose = context.get('coup_propose') if isinstance(context.get('coup_propose'), str) else None
    
    coherence_alertes = _verifier_coherence_verdict(texte, verdict, meilleur_coup, coup_propose)
    alertes.extend(coherence_alertes)
    affirmations_verifiees += len(coherence_alertes)

    # (d) Vérifier le sens de "qui est mieux" contre le signe réel de
    # l'évaluation et le camp d'Alain, et la formule "pour toi" accolée à
    # un chiffre signé (issue #134, suite #128)
    sens_qui_est_mieux_alertes = _verifier_sens_qui_est_mieux(texte, context, camp_alain)
    alertes.extend(sens_qui_est_mieux_alertes)
    affirmations_verifiees += len(sens_qui_est_mieux_alertes)

    pour_toi_colle_alertes = _verifier_pour_toi_chiffre_colle(texte)
    alertes.extend(pour_toi_colle_alertes)
    affirmations_verifiees += len(pour_toi_colle_alertes)

    # (e) Vérifier que le mot de qualité de la première phrase reprend le
    # verdict officiel sans l'atténuer (issue #134, suite #128)
    mot_verdict_alertes = _verifier_mot_verdict_premiere_phrase(texte, verdict)
    alertes.extend(mot_verdict_alertes)
    affirmations_verifiees += len(mot_verdict_alertes)

    # Ajouter l'agent à chaque alerte
    for alerte in alertes:
        alerte['agent'] = agent
    
    return {
        'alertes': alertes,
        'affirmations_verifiees': affirmations_verifiees,
        'affirmations_ignorees': affirmations_ignorees
    }


def formater_alertes(alertes: List[Dict]) -> List[str]:
    """Formate les alertes pour affichage.
    
    Retourne une liste de chaînes formatées pour affichage sous l'avis.
    """
    messages = []
    
    for alerte in alertes:
        agent = alerte.get('agent', 'inconnu')
        type_alerte = alerte.get('type', 'inconnu')
        affirmation = alerte.get('affirmation', '')
        
        messages.append(f"à vérifier ({agent}) : {affirmation}")
    
    return messages
