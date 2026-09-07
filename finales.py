"""
finales.py — ChessCoach (issue #10, mode "travail de finales")

Bibliothèque curatée de positions-types de finales. Contrairement au mode
"travail d'ouverture" (issue #9), aucune génération dynamique par Claude :
dans une finale technique (roi + pion par exemple), une seule case de
décalage change complètement la nature de la position (qui a l'opposition,
quelle case est clé...). Chaque entrée ci-dessous a donc été vérifiée légale
via python-chess (Board.is_valid()) avant d'être ajoutée.

Format pensé pour ajouter facilement d'autres positions plus tard sans
changement de code côté app.py/finales.js (pas dans le périmètre de cette
issue d'en ajouter davantage) : il suffit d'ajouter une entrée à FINALES.

Chaque entrée :
  id          : identifiant stable, utilisé côté client pour la sélection
  nom         : nom affiché dans le panneau "Travail de finales"
  fen         : position de départ (FEN) ; le camp au trait dans la FEN est
                celui qui joue en premier une fois la position chargée, pas
                nécessairement camp_alain (l'adversaire peut ouvrir, voir
                app.py on_finale_start)
  camp_alain  : "blancs" ou "noirs" — camp qu'Alain doit jouer, fixé par la
                position-type elle-même (pas un choix libre comme dans les
                modes pédagogique/ouverture)
  description : objectif/technique travaillée, injecté dans le contexte du
                coach (get_coach_response, clé "theme_finale") pour que son
                commentaire puisse s'y référer
"""

import logging

import chess

logger = logging.getLogger("chesscoach.finales")

FINALES = [
    {
        "id": "roi_pion_colonne_e",
        "nom": "Roi et pion contre roi (colonne e) — opposition et case clé",
        # Position de référence classique de la théorie des finales roi et
        # pion contre roi (voir par ex. Fine, "Basic Chess Endings", ou
        # Silman, "Complete Endgame Course") : Roi blanc e5, pion blanc e4,
        # Roi noir e7, trait aux Noirs. Les rois sont en opposition directe
        # (un rang d'écart, e6 vide entre eux) ; comme c'est aux Noirs de
        # jouer, ce sont eux qui doivent céder du terrain et laisser le Roi
        # blanc s'infiltrer sur une case clé (d6, e6 ou f6 pour un pion en
        # e4/e5) — une fois une case clé atteinte, le pion promeut sans
        # encombre quelle que soit la défense noire.
        "fen": "8/4k3/8/4K3/4P3/8/8/8 b - - 0 1",
        "camp_alain": "blancs",
        "description": (
            "Finale roi et pion contre roi, pion en e4, trait aux Noirs. "
            "Position de référence classique : les Blancs (Alain) ont "
            "l'opposition et doivent en profiter pour conquérir une case clé "
            "(d6, e6 ou f6) en manœuvrant leur roi plutôt qu'en poussant le "
            "pion trop tôt — une fois une case clé atteinte, le pion promeut "
            "sans encombre quelle que soit la défense noire."
        ),
    },
]


def _valid_entry(entry: dict) -> bool:
    """Vérifie qu'une entrée a une FEN légale et un camp_alain reconnu."""
    if entry.get("camp_alain") not in ("blancs", "noirs"):
        return False
    try:
        board = chess.Board(entry.get("fen", ""))
    except Exception:
        return False
    return board.is_valid()


def get_finales() -> list[dict]:
    """Retourne la bibliothèque de finales, en écartant silencieusement toute
    entrée mal formée (FEN illégale ou camp_alain invalide) plutôt que de
    planter le mode entier pour une seule entrée fautive."""
    valid = [e for e in FINALES if _valid_entry(e)]
    if len(valid) != len(FINALES):
        logger.warning("Certaines entrées de FINALES ont été écartées (FEN invalide).")
    return valid


def get_finale_by_id(finale_id: str) -> dict | None:
    """Retourne l'entrée correspondant à l'id donné, ou None si absente/invalide."""
    for entry in get_finales():
        if entry["id"] == finale_id:
            return entry
    return None
