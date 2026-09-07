"""
opening_book.py — ChessCoach (issue #9, mode "travail d'ouverture")

Fine couche autour de chess.polyglot (déjà fourni par la dépendance
python-chess existante, pas de nouvelle dépendance) pour lire le livre
d'ouvertures réel data/books/gm2001.bin (config.BOOK_PATH) : lister les
coups de référence d'une position avec leur poids, ou en tirer un au sort
pondéré pour le jeu automatique de l'adversaire.

Un livre Polyglot ne connaît que des positions et des coups statistiquement
fondés — pas de noms d'ouverture. La reconnaissance du nom d'ouverture donné
par Alain (pour atteindre la position de départ de l'entraînement) est faite
par ailleurs via un appel dédié à Claude (voir llm_coach.get_opening_moves).
"""

import logging
from pathlib import Path

import chess
import chess.polyglot

logger = logging.getLogger("chesscoach.opening_book")


def book_available(book_path) -> bool:
    """Retourne True si le fichier de livre Polyglot est présent sur disque."""
    return Path(book_path).exists()


def get_book_entries(book_path, board: chess.Board) -> list[dict]:
    """Retourne les entrées du livre pour la position donnée, triées par
    poids décroissant : [{"uci": str, "san": str, "weight": int}, ...].

    Liste vide si le livre est absent ou si la position n'y figure pas (fin
    de la couverture théorique pour cette ligne).
    """
    book_path = Path(book_path)
    if not book_path.exists():
        return []
    try:
        with chess.polyglot.open_reader(str(book_path)) as reader:
            entries = sorted(reader.find_all(board), key=lambda e: e.weight, reverse=True)
            return [
                {"uci": e.move.uci(), "san": board.san(e.move), "weight": e.weight}
                for e in entries
            ]
    except Exception as e:
        logger.warning(f"Lecture du livre Polyglot échouée ({book_path}) : {e}")
        return []


def choose_weighted_move(book_path, board: chess.Board) -> chess.Move | None:
    """Tire un coup pondéré aléatoirement parmi les entrées du livre pour
    cette position (chess.polyglot.MemoryMappedReader.weighted_choice) —
    variété réaliste dans le jeu de l'adversaire automatique plutôt que de
    toujours rejouer le coup le plus populaire.

    Retourne None si le livre est absent ou si la position n'y figure pas.
    """
    book_path = Path(book_path)
    if not book_path.exists():
        return None
    try:
        with chess.polyglot.open_reader(str(book_path)) as reader:
            return reader.weighted_choice(board).move
    except IndexError:
        return None
    except Exception as e:
        logger.warning(f"Tirage pondéré du livre Polyglot échoué ({book_path}) : {e}")
        return None
