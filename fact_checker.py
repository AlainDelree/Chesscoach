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


# Motifs regex pour détecter les affirmations à vérifier
# (a) Pièce en case : "ta dame en b5", "le cavalier en e5", "une tour sur d1", etc.
_PIECE_EN_CASE_PATTERN = re.compile(
    r'(?:(?:ta|ton|tes|ma|mon|mes|sa|son|ses|le|la|les|un|une|des)\s+)?'
    r'(dame|roi|tour|fou|cavalier|pion)\s+'
    r'(?:en|sur|à|au|aux)\s+'
    r'([a-h][1-8])',
    re.IGNORECASE
)

# (a) Variante : "dame b5", "cavalier e5" (sans préposition)
_PIECE_CASE_SANS_PREPOSITION_PATTERN = re.compile(
    r'(?:(?:ta|ton|tes|ma|mon|mes|sa|son|ses|le|la|les|un|une|des)\s+)?'
    r'(dame|roi|tour|fou|cavalier|pion)\s+'
    r'([a-h][1-8])',
    re.IGNORECASE
)

# (b) Attaque par un pion : "le pion X attaque/menace/prend/chasse la pièce Y"
# On cherche des patterns comme "pion [case] attaque/menace/prend/chasse"
_PION_ATTAQUE_PATTERN = re.compile(
    r'pion\s+(?:blanc|noir|blancs|noirs)?\s*'
    r'(?:en|sur|à|au|aux)?\s*'
    r'([a-h][1-8])\s+'
    r'(attaqu|menac|prend|chass|captur)',
    re.IGNORECASE
)

# (b) Variante : "pion [case] [verbe] [pièce]"
_PION_ATTAQUE_PIECE_PATTERN = re.compile(
    r'pion\s+(?:blanc|noir|blancs|noirs)?\s*'
    r'(?:en|sur|à|au|aux)?\s*'
    r'([a-h][1-8])\s+'
    r'(attaqu|menac|prend|chass|captur)\s+'
    r'(?:la|le|les|une|un|ta|ton|tes|ma|mon|mes|sa|son|ses)?\s*'
    r'(dame|roi|tour|fou|cavalier|pion)',
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
    (r'(?:erreur|gaffe|faute)\s+(?:grossièr|stratégiqu|tactiqu|graves?)?', re.IGNORECASE),
]

# Verbes d'attaque pour la vérification des pions
_ATTAQUE_VERBS = {
    'attaqu', 'menac', 'prend', 'chass', 'captur', 'frappe', 'contrôl'
}

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
    if fen_depart:
        positions.append(fen_depart)
    
    # Position après le coup proposé (si on peut la calculer)
    coup_propose = context.get('coup_propose')
    if coup_propose and fen_depart:
        try:
            board = chess.Board(fen_depart)
            move = board.parse_san(coup_propose) if board.parse_san(coup_propose) else board.parse_uci(coup_propose)
            board.push(move)
            positions.append(board.fen())
        except:
            pass
    
    # Ligne calculée pour le coup proposé
    pv_coup_propose = context.get('pv_coup_propose', '')
    if pv_coup_propose and fen_depart:
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
    if pv_meilleur_coup and fen_depart:
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
        # Chercher dans le texte avant le match
        texte_avant = texte[:match.start()]
        
        # Chercher un possessif ou un article de couleur
        couleur = None
        
        # Chercher un possessif dans les 20 caractères avant
        possessif_match = re.search(
            r'\b(ta|ton|tes|ma|mon|mes|sa|son|ses)\b',
            texte_avant[-50:],
            re.IGNORECASE
        )
        if possessif_match:
            couleur = _get_couleur_from_possessif(possessif_match.group(0))
        
        # Chercher un article de couleur dans les 30 caractères avant
        if couleur is None:
            couleur_match = re.search(
                r'\b(blanc|blancs|noir|noirs)\b',
                texte_avant[-50:],
                re.IGNORECASE
            )
            if couleur_match:
                couleur = _COLOR_MAP.get(couleur_match.group(0).lower())
        
        # Si camp_alain est fourni et qu'on a un possessif "ta/ton/tes", 
        # on peut déduire que c'est la couleur d'Alain
        if couleur is None and camp_alain:
            possessif_match = re.search(
                r'\b(ta|ton|tes)\b',
                texte_avant[-50:],
                re.IGNORECASE
            )
            if possessif_match:
                couleur = chess.WHITE if camp_alain == "blancs" else chess.BLACK
        
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
        texte_avant = texte[:match.start()]
        couleur = None
        
        possessif_match = re.search(
            r'\b(ta|ton|tes|ma|mon|mes|sa|son|ses)\b',
            texte_avant[-50:],
            re.IGNORECASE
        )
        if possessif_match:
            couleur = _get_couleur_from_possessif(possessif_match.group(0))
        
        couleur_match = re.search(
            r'\b(blanc|blancs|noir|noirs)\b',
            texte_avant[-50:],
            re.IGNORECASE
        )
        if couleur_match:
            couleur = _COLOR_MAP.get(couleur_match.group(0).lower())
        
        if couleur is None and camp_alain:
            possessif_match = re.search(
                r'\b(ta|ton|tes)\b',
                texte_avant[-50:],
                re.IGNORECASE
            )
            if possessif_match:
                couleur = chess.WHITE if camp_alain == "blancs" else chess.BLACK
        
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


def _verifier_pion_attaque(
    texte: str,
    positions_candidates: List[str]
) -> List[Dict]:
    """Vérifie les affirmations d'attaque par un pion.
    
    Un pion attaque diagonalement en avant. Pour les blancs : a2->b3, a2->a3 (non, c'est devant)
    Un pion en c2 (blanc) attaque b3 et d3.
    Un pion en c7 (noir) attaque b6 et d6.
    
    Retourne une liste d'alertes pour les affirmations fausses.
    """
    alertes = []
    
    # Trouver toutes les mentions de pion qui attaque
    matches = _PION_ATTAQUE_PATTERN.finditer(texte)
    
    for match in matches:
        pion_case = match.group(1).lower()
        verbe = match.group(2).lower()
        
        # Déterminer la couleur du pion
        couleur = None
        texte_match = match.group(0)
        
        if 'blanc' in texte_match.lower():
            couleur = chess.WHITE
        elif 'noir' in texte_match.lower():
            couleur = chess.BLACK
        
        # Si la couleur n'est pas spécifiée, on essaie de la déduire du contexte
        # Mais pour les pions, sans couleur explicite, on ne peut pas vérifier
        if couleur is None:
            continue
        
        # Trouver la pièce attaquée si mentionnée
        piece_attaquee = None
        piece_attaquee_case = None
        
        # Chercher après le verbe
        reste_texte = texte[match.end():]
        piece_match = re.search(
            r'(?:la|le|les|une|un|ta|ton|tes|ma|mon|mes|sa|son|ses)?\s*'
            r'(dame|roi|tour|fou|cavalier|pion)\s+'
            r'(?:en|sur|à|au|aux)?\s*'
            r'([a-h][1-8])',
            reste_texte[:100],
            re.IGNORECASE
        )
        
        if piece_match:
            piece_attaquee = piece_match.group(1).lower()
            piece_attaquee_case = piece_match.group(2).lower()
        
        # Vérifier la géométrie d'attaque du pion
        # Un pion attaque diagonalement en avant d'une case
        pion_square = chess.parse_square(pion_case)
        
        if couleur == chess.WHITE:
            # Pion blanc : attaque une case en diagonale devant (rang + 1)
            attaques_possibles = [
                pion_square + 7,  # b3 depuis a2 (file +1, rang +1)
                pion_square + 9,  # d3 depuis a2 (file -1, rang +1)
            ]
        else:
            # Pion noir : attaque une case en diagonale devant (rang - 1)
            attaques_possibles = [
                pion_square - 7,  # b6 depuis c7 (file +1, rang -1)
                pion_square - 9,  # d6 depuis c7 (file -1, rang -1)
            ]
        
        # Filtrer les cases valides (0-63)
        attaques_possibles = [sq for sq in attaques_possibles if 0 <= sq < 64]
        
        # Si une pièce attaquée est mentionnée avec sa case
        if piece_attaquee and piece_attaquee_case:
            piece_attaquee_square = chess.parse_square(piece_attaquee_case)
            
            # Vérifier si cette case est dans les attaques possibles
            if piece_attaquee_square not in attaques_possibles:
                # Vérifier dans toutes les positions candidates
                attaque_valide_dans_une_position = False
                
                for fen in positions_candidates:
                    try:
                        board = chess.Board(fen)
                        piece = board.piece_at(pion_square)
                        
                        # Vérifier que c'est bien un pion de la bonne couleur
                        if piece and piece.piece_type == chess.PAWN and piece.color == couleur:
                            # Vérifier que le pion attaque bien la case mentionnée
                            if board.is_attacked_by(couleur, piece_attaquee_square):
                                # Vérifier que c'est bien le pion qui attaque
                                # (pas une autre pièce)
                                if board.is_attacked_by(couleur, piece_attaquee_square):
                                    # On vérifie si le pion est bien celui qui attaque
                                    # en vérifiant que la pièce sur la case attaquée est bien attaquée par ce pion
                                    # Pour être précis, on vérifie que le pion attaque cette case
                                    if chess.square_distance(pion_square, piece_attaquee_square) == 2 and \
                                       abs(chess.square_file(pion_square) - chess.square_file(piece_attaquee_square)) == 1:
                                        # C'est une attaque diagonale valide
                                        if (couleur == chess.WHITE and 
                                            chess.square_rank(pion_square) + 1 == chess.square_rank(piece_attaquee_square)) or \
                                           (couleur == chess.BLACK and 
                                            chess.square_rank(pion_square) - 1 == chess.square_rank(piece_attaquee_square)):
                                            attaque_valide_dans_une_position = True
                                            break
                    except:
                        continue
                
                if not attaque_valide_dans_une_position:
                    alerte = {
                        'type': 'pion_attaque',
                        'affirmation': f"pion {'blanc' if couleur == chess.WHITE else 'noir'} en {pion_case} {verbe} {piece_attaquee} en {piece_attaquee_case}",
                        'pion_case': pion_case,
                        'pion_couleur': 'blancs' if couleur == chess.WHITE else 'noirs',
                        'piece_attaquee': piece_attaquee,
                        'piece_attaquee_case': piece_attaquee_case,
                        'details': f"Un pion {'blanc' if couleur == chess.WHITE else 'noir'} en {pion_case} n'attaque pas {piece_attaquee} en {piece_attaquee_case} (géométrie invalide)"
                    }
                    alertes.append(alerte)
        else:
            # Pas de pièce attaquée mentionnée, on vérifie juste la géométrie
            # On ne peut pas vérifier sans savoir quelle pièce est attaquée
            pass
    
    return alertes


def _verifier_pion_attaque_piece(
    texte: str,
    positions_candidates: List[str]
) -> List[Dict]:
    """Vérifie les affirmations d'attaque par un pion avec pièce mentionnée."""
    alertes = []
    
    matches = _PION_ATTAQUE_PIECE_PATTERN.finditer(texte)
    
    for match in matches:
        pion_case = match.group(1).lower()
        verbe = match.group(2).lower()
        piece_attaquee = match.group(3).lower()
        
        # Déterminer la couleur du pion
        couleur = None
        texte_match = match.group(0)
        
        if 'blanc' in texte_match.lower():
            couleur = chess.WHITE
        elif 'noir' in texte_match.lower():
            couleur = chess.BLACK
        
        if couleur is None:
            continue
        
        # Trouver la case de la pièce attaquée
        piece_attaquee_case = None
        reste_texte = texte[match.end():]
        case_match = re.search(r'(?:en|sur|à|au|aux)\s+([a-h][1-8])', reste_texte[:50], re.IGNORECASE)
        
        if case_match:
            piece_attaquee_case = case_match.group(1).lower()
        
        if not piece_attaquee_case:
            continue
        
        # Vérifier la géométrie
        pion_square = chess.parse_square(pion_case)
        piece_attaquee_square = chess.parse_square(piece_attaquee_case)
        
        if couleur == chess.WHITE:
            attaques_possibles = [pion_square + 7, pion_square + 9]
        else:
            attaques_possibles = [pion_square - 7, pion_square - 9]
        
        attaques_possibles = [sq for sq in attaques_possibles if 0 <= sq < 64]
        
        if piece_attaquee_square not in attaques_possibles:
            # Vérifier dans toutes les positions candidates
            attaque_valide_dans_une_position = False
            
            for fen in positions_candidates:
                try:
                    board = chess.Board(fen)
                    piece = board.piece_at(pion_square)
                    
                    if piece and piece.piece_type == chess.PAWN and piece.color == couleur:
                        if (couleur == chess.WHITE and 
                            chess.square_rank(pion_square) + 1 == chess.square_rank(piece_attaquee_square) and
                            abs(chess.square_file(pion_square) - chess.square_file(piece_attaquee_square)) == 1) or \
                           (couleur == chess.BLACK and 
                            chess.square_rank(pion_square) - 1 == chess.square_rank(piece_attaquee_square) and
                            abs(chess.square_file(pion_square) - chess.square_file(piece_attaquee_square)) == 1):
                            attaque_valide_dans_une_position = True
                            break
                except:
                    continue
            
            if not attaque_valide_dans_une_position:
                alerte = {
                    'type': 'pion_attaque_piece',
                    'affirmation': f"pion {'blanc' if couleur == chess.WHITE else 'noir'} en {pion_case} {verbe} {piece_attaquee} en {piece_attaquee_case}",
                    'pion_case': pion_case,
                    'pion_couleur': 'blancs' if couleur == chess.WHITE else 'noirs',
                    'piece_attaquee': piece_attaquee,
                    'piece_attaquee_case': piece_attaquee_case,
                    'details': f"Un pion {'blanc' if couleur == chess.WHITE else 'noir'} en {pion_case} n'attaque pas {piece_attaquee} en {piece_attaquee_case}"
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
    if verdict.lower() in ['bon', 'excellent', 'parfait']:
        for pattern, _ in _INCONSISTENCIES[4:]:  # Les patterns d'erreur/gaffe
            if re.search(pattern, texte_lower):
                alerte = {
                    'type': 'coherence_verdict',
                    'affirmation': f"L'avis qualifie le coup d'erreur/gaffe alors que le verdict est '{verdict}'",
                    'verdict': verdict,
                    'details': f"Incohérence : verdict '{verdict}' mais l'avis utilise des termes comme 'erreur' ou 'gaffe'"
                }
                alertes.append(alerte)
                break
    
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
    
    if not positions_candidates:
        # Sans positions candidates, on ne peut rien vérifier
        return {
            'alertes': [],
            'affirmations_verifiees': 0,
            'affirmations_ignorees': 0
        }
    
    alertes = []
    affirmations_verifiees = 0
    affirmations_ignorees = 0
    
    # (a) Vérifier les affirmations "pièce en case"
    piece_en_case_alertes = _verifier_piece_en_case(texte, positions_candidates, camp_alain)
    alertes.extend(piece_en_case_alertes)
    affirmations_verifiees += len(piece_en_case_alertes)
    
    # (a) Vérifier les affirmations "pièce case" sans préposition
    piece_case_sans_prep_alertes = _verifier_piece_case_sans_preposition(texte, positions_candidates, camp_alain)
    alertes.extend(piece_case_sans_prep_alertes)
    affirmations_verifiees += len(piece_case_sans_prep_alertes)
    
    # (b) Vérifier les affirmations d'attaque par un pion
    pion_attaque_alertes = _verifier_pion_attaque(texte, positions_candidates)
    alertes.extend(pion_attaque_alertes)
    affirmations_verifiees += len(pion_attaque_alertes)
    
    # (b) Vérifier les affirmations d'attaque par un pion avec pièce mentionnée
    pion_attaque_piece_alertes = _verifier_pion_attaque_piece(texte, positions_candidates)
    alertes.extend(pion_attaque_piece_alertes)
    affirmations_verifiees += len(pion_attaque_piece_alertes)
    
    # (c) Vérifier la cohérence verdict/texte
    verdict = context.get('verdict_qualite')
    meilleur_coup = context.get('meilleur_coup')
    coup_propose = context.get('coup_propose')
    
    coherence_alertes = _verifier_coherence_verdict(texte, verdict, meilleur_coup, coup_propose)
    alertes.extend(coherence_alertes)
    affirmations_verifiees += len(coherence_alertes)
    
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
