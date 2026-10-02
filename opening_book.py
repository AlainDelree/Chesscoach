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


# Familles d'ouvertures reconnaissables au tout premier coup (issue #27,
# suggestions rapides du panneau "Travail d'ouverture") — uniquement les
# quatre citées par Alain, qui correspondent à des familles bien identifiées
# sans ambiguïté. Au-delà d'un coup, aucun nom n'est déterminable de façon
# fiable à partir des seules statistiques pondérées du livre (voir docstring
# du module) : get_starting_suggestions se limite alors au coup lui-même.
FIRST_MOVE_OPENING_NAMES = {
    "e4":  "Ouverture du Roi (1.e4)",
    "d4":  "Ouverture de la Dame (1.d4)",
    "c4":  "Ouverture anglaise (1.c4)",
    "Nf3": "Ouverture Réti (1.Nf3)",
}


def get_starting_suggestions(book_path, limit: int = 8) -> list[dict]:
    """Retourne les coups les plus pondérés du livre à la position de départ
    (issue #27) : [{"san": str, "nom": str|None, "pct": float|None}, ...],
    triés par poids décroissant. "nom" n'est renseigné que pour les quatre
    familles standards de FIRST_MOVE_OPENING_NAMES — les autres coups ne
    renvoient que leur SAN, sans nom d'ouverture inventé.
    """
    entries = get_book_entries(book_path, chess.Board())
    total_weight = sum(e["weight"] for e in entries)
    return [
        {
            "san": e["san"],
            "nom": FIRST_MOVE_OPENING_NAMES.get(e["san"]),
            "pct": round(e["weight"] / total_weight * 100, 1) if total_weight else None,
        }
        for e in entries[:limit]
    ]


# Liste des ouvertures connues (issue #95, point 4) : remplace la saisie
# libre du nom d'ouverture par une liste déroulante (même principe que le
# sélecteur de finales, finales.py get_finales()) — contrairement aux
# finales, cette liste n'est pas persistée dans un fichier JSON extensible
# (aucun mécanisme "enregistrer cette ouverture" n'a été demandé) : c'est une
# liste statique d'ouvertures classiques largement reconnues, à étendre
# directement ici si besoin. Le nom choisi est transmis tel quel à
# llm_coach.get_opening_moves (inchangé) — Claude reste seul responsable de
# retrouver la séquence de coups caractéristique, cette liste ne fait que
# fiabiliser la saisie du nom lui-même (plus de faute de frappe/ambiguïté).
KNOWN_OPENINGS = sorted([
    "Attaque Trompowsky",
    "Défense alekhine",
    "Défense Benoni",
    "Défense Benoni moderne",
    "Défense Caro-Kann",
    "Défense est-indienne",
    "Défense française",
    "Défense Grünfeld",
    "Défense hollandaise",
    "Défense Nimzo-indienne",
    "Défense nord-indienne",
    "Défense ouest-indienne",
    "Défense Philidor",
    "Défense Pirc",
    "Défense scandinave",
    "Défense sicilienne",
    "Défense sicilienne, variante Najdorf",
    "Défense sicilienne, variante dragon",
    "Défense slave",
    "Gambit Benko",
    "Gambit dame accepté",
    "Gambit dame refusé",
    "Gambit évans",
    "Gambit letton",
    "Gambit Ménage (Blackmar-Diemer)",
    "Gambit roi",
    "Ouverture anglaise",
    "Ouverture Bird",
    "Ouverture du Roi (1.e4)",
    "Ouverture de la Dame (1.d4)",
    "Ouverture Réti",
    "Partie Alapine",
    "Partie autrichienne",
    "Partie Bogo-indienne",
    "Partie catalane",
    "Partie des quatre cavaliers",
    "Partie écossaise",
    "Partie espagnole (Ruy Lopez)",
    "Partie italienne",
    "Partie Petroff",
    "Partie Ponziani",
    "Partie russe",
    "Partie Vienne",
    "Système Colle",
    "Système Londres",
])


def get_known_openings() -> list[str]:
    """Retourne la liste des ouvertures connues du programme (issue #95,
    point 4), pour peupler le menu déroulant du panneau "Travail d'ouverture"
    — voir KNOWN_OPENINGS ci-dessus pour les limites de cette liste statique."""
    return list(KNOWN_OPENINGS)


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
