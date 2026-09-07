"""
build_repertoire_ouvertures.py — ChessCoach (issue Bridge_Agent #2)

Parcourt toutes les parties importées dans la bibliothèque PGN
(data/pgn_library/, via library_manager.py) et remplit
repertoire_ouvertures.blancs / .noirs dans coach_memory.json avec les
ouvertures effectivement jouées par Alain (pseudo athanatos123 sur Lichess
et Chess.com), distinguées selon la couleur jouée.

Identification de l'ouverture, par ordre de préférence :
  1. Tag PGN ECOUrl (chess.com) : nom de famille dérivé du slug de l'URL
     (ex. "French-Defense-Advance-Steinitz-Variation" -> "French Defense").
  2. Tag PGN ECO seul (sans ECOUrl) : fallback "ECO <code>".
  3. Ni ECO ni ECOUrl (cas de tous les imports Lichess de ce jeu de
     données) : détection simple sur les 4 premiers coups (pas de
     Stockfish, pas d'analyse de qualité — seulement l'identification de
     la famille d'ouverture).

Usage : python build_repertoire_ouvertures.py
Sauvegarde coach_memory.json via save_coach_memory (llm_coach.py). Les
autres sections du fichier (profil, patterns_erreurs, historique_sessions,
objectifs_courants) sont préservées telles quelles.
"""

import io
from collections import Counter

import chess.pgn

import library_manager
from config import COACH_MEMORY_PATH
from llm_coach import load_coach_memory, save_coach_memory

ALAIN_PSEUDO = "athanatos123"

# Mots-clés marquant la fin du nom de famille dans un slug ECOUrl chess.com,
# ex. "Queens-Pawn-Opening-Chigorin-Irish-Gambit" -> famille "Queens Pawn Opening".
_FAMILY_KEYWORDS = {"Defense", "Defence", "Attack", "Opening", "Gambit", "Game", "System"}


def _family_from_eco_url(eco_url: str) -> str:
    slug = eco_url.rstrip("/").split("/")[-1]
    if slug == "Undefined":
        return "Ouverture non identifiee"
    # La notation de coups (ex. "3...dxc4-4.e3") suit le nom de la famille
    # sans séparateur "-" fiable avant les points de suspension : on tronque
    # avant, pour ne garder que la partie nom d'ouverture du slug.
    slug = slug.split("...", 1)[0]
    words = [w for w in slug.split("-") if w]
    for i, word in enumerate(words):
        if word in _FAMILY_KEYWORDS:
            return " ".join(words[: i + 1])
    return " ".join(words[:2]) if words else "Ouverture non identifiee"


def _classify_by_moves(sans: list) -> str:
    """Détection simple de la famille d'ouverture sur les premiers coups
    (SAN), pour les parties sans tag ECO/ECOUrl."""
    m = sans
    if len(m) >= 1 and m[0] == "e4":
        if len(m) < 2:
            return "Kings Pawn Opening"
        if m[1] == "e5":
            return "Kings Pawn Opening"
        if m[1] == "c5":
            return "Sicilian Defense"
        if m[1] == "e6":
            return "French Defense"
        if m[1] == "c6":
            return "Caro Kann Defense"
        if m[1] == "d5":
            return "Scandinavian Defense"
        if m[1] == "d6":
            return "Pirc Defense"
        if m[1] == "g6":
            return "Modern Defense"
        if m[1] == "Nf6":
            return "Alekhine Defense"
        return "Kings Pawn Opening"
    if len(m) >= 1 and m[0] == "d4":
        if len(m) < 2:
            return "Queens Pawn Opening"
        if m[1] == "d5":
            if len(m) >= 4 and m[2] == "c4":
                return "Slav Defense" if m[3] == "c6" else "Queens Gambit"
            return "Queens Pawn Opening"
        if m[1] == "Nf6":
            if len(m) >= 3 and m[2] == "c4":
                return "Indian Game"
            return "Queens Pawn Opening"
        if m[1] == "f5":
            return "Dutch Defense"
        return "Queens Pawn Opening"
    if len(m) >= 1 and m[0] == "c4":
        return "English Opening"
    if len(m) >= 1 and m[0] == "Nf3":
        return "Reti Opening"
    if len(m) >= 1 and m[0] == "g3":
        return "Kings Fianchetto Opening"
    if len(m) >= 1 and m[0] == "b3":
        return "Nimzowitsch Larsen Attack"
    if len(m) >= 1 and m[0] == "f4":
        return "Birds Opening"
    return "Ouverture non identifiee"


def _identify_opening(game: chess.pgn.Game) -> tuple:
    """Retourne (nom_ouverture, methode) avec methode = 'tag_pgn' ou 'detection_coups'."""
    headers = game.headers
    eco_url = headers.get("ECOUrl", "")
    if eco_url:
        return _family_from_eco_url(eco_url), "tag_pgn"
    eco = headers.get("ECO", "")
    if eco:
        return f"ECO {eco}", "tag_pgn"

    board = game.board()
    sans = []
    for move in game.mainline_moves():
        if len(sans) >= 4:
            break
        sans.append(board.san(move))
        board.push(move)
    return _classify_by_moves(sans), "detection_coups"


def _build_repertoire(counter: Counter, total_games: int) -> list:
    entries = []
    for nom, parties in counter.most_common():
        entries.append({
            "nom": nom,
            "parties_jouees": parties,
            "frequence_pct": round(100 * parties / total_games, 1) if total_games else 0.0,
        })
    return entries


def main():
    counts = {"blancs": Counter(), "noirs": Counter()}
    methodes_utilisees = set()
    parties_traitees = 0
    parties_ignorees = 0

    for collection in library_manager.list_collections():
        collection_id = collection["id"]
        for game_entry in library_manager.list_games(collection_id):
            pgn_text = library_manager.load_game(collection_id, game_entry["index"])
            game = chess.pgn.read_game(io.StringIO(pgn_text))
            if game is None:
                parties_ignorees += 1
                continue

            headers = game.headers
            white = headers.get("White", "")
            black = headers.get("Black", "")
            if white.lower() == ALAIN_PSEUDO:
                couleur = "blancs"
            elif black.lower() == ALAIN_PSEUDO:
                couleur = "noirs"
            else:
                parties_ignorees += 1
                continue

            nom_ouverture, methode = _identify_opening(game)
            counts[couleur][nom_ouverture] += 1
            methodes_utilisees.add(methode)
            parties_traitees += 1

    memory = load_coach_memory(COACH_MEMORY_PATH)
    memory.setdefault("repertoire_ouvertures", {})
    memory["repertoire_ouvertures"]["blancs"] = _build_repertoire(counts["blancs"], sum(counts["blancs"].values()))
    memory["repertoire_ouvertures"]["noirs"] = _build_repertoire(counts["noirs"], sum(counts["noirs"].values()))

    save_coach_memory(COACH_MEMORY_PATH, memory)

    print(f"Parties traitees : {parties_traitees} (ignorees : {parties_ignorees})")
    print(f"Ouvertures distinctes - blancs : {len(counts['blancs'])}, noirs : {len(counts['noirs'])}")
    print(f"Methodes utilisees : {', '.join(sorted(methodes_utilisees))}")


if __name__ == "__main__":
    main()
