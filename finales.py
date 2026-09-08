"""
finales.py — ChessCoach (issue #10, mode "travail de finales")

Bibliothèque de positions-types de finales, persistée dans data/finales.json
(issue #13) plutôt que codée en dur : le bouton "Enregistrer comme finale"
du mode "Partie libre" peut ainsi y ajouter de nouvelles entrées sans
modification de code. Au premier démarrage (fichier absent), le JSON est
amorcé avec la position de référence ci-dessous (_SEED_FINALES).

Contrairement au mode "travail d'ouverture" (issue #9), aucune génération
dynamique par Claude : dans une finale technique (roi + pion par exemple),
une seule case de décalage change complètement la nature de la position
(qui a l'opposition, quelle case est clé...). Chaque entrée est vérifiée
légale via python-chess (Board.is_valid()) avant d'être retenue.

Chaque entrée :
  id          : identifiant stable, utilisé côté client pour la sélection
                (dérivé du nom lors de l'ajout, cf. _slugify)
  nom         : nom affiché dans le panneau "Travail de finales"
  fen         : position de départ (FEN) ; le camp au trait dans la FEN est
                celui qui joue en premier une fois la position chargée, pas
                nécessairement camp_alain (l'adversaire peut ouvrir, voir
                app.py on_finale_start)
  camp_alain  : "blancs" ou "noirs" — camp qu'Alain doit jouer
  description : objectif/technique travaillée, injecté dans le contexte du
                coach (get_coach_response, clé "theme_finale") pour que son
                commentaire puisse s'y référer
"""

import json
import logging
import re
import unicodedata
from pathlib import Path

import chess

import config

logger = logging.getLogger("chesscoach.finales")

# Amorce de data/finales.json à la première exécution uniquement — au-delà,
# toute modification passe par ce fichier (ajouts via add_finale), pas par
# ce module.
_SEED_FINALES = [
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


def _load() -> list[dict]:
    """Charge data/finales.json, l'amorce avec _SEED_FINALES s'il est
    absent (première exécution)."""
    path = Path(config.FINALES_PATH)
    if not path.exists():
        _save(_SEED_FINALES)
        return list(_SEED_FINALES)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Bibliothèque de finales illisible ({path}) : {e}")
        return []


def _save(entries: list[dict]) -> None:
    path = Path(config.FINALES_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)


def _valid_entry(entry: dict) -> bool:
    """Vérifie qu'une entrée a une FEN légale et un camp_alain reconnu."""
    if entry.get("camp_alain") not in ("blancs", "noirs"):
        return False
    try:
        board = chess.Board(entry.get("fen", ""))
    except Exception:
        return False
    return board.is_valid()


def _slugify(nom: str) -> str:
    normalized = unicodedata.normalize("NFKD", nom).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "_", normalized.lower()).strip("_")
    return slug or "finale"


def get_finales() -> list[dict]:
    """Retourne la bibliothèque de finales, en écartant silencieusement toute
    entrée mal formée (FEN illégale ou camp_alain invalide) plutôt que de
    planter le mode entier pour une seule entrée fautive."""
    entries = _load()
    valid = [e for e in entries if _valid_entry(e)]
    if len(valid) != len(entries):
        logger.warning("Certaines entrées de data/finales.json ont été écartées (FEN invalide).")
    return valid


def get_finale_by_id(finale_id: str) -> dict | None:
    """Retourne l'entrée correspondant à l'id donné, ou None si absente/invalide."""
    for entry in get_finales():
        if entry["id"] == finale_id:
            return entry
    return None


def add_finale(fen: str, camp_alain: str, nom: str, description: str) -> dict | None:
    """Ajoute une nouvelle finale à data/finales.json (issue #13, bouton
    "Enregistrer comme finale" du mode "Partie libre") et la persiste tout de
    suite. Retourne l'entrée ajoutée, ou None si la FEN/le camp/le nom saisi
    sont invalides — le nom sert de base à l'id (slug), avec un suffixe
    numérique en cas de collision plutôt que d'écraser une entrée existante."""
    nom = (nom or "").strip()
    if not nom:
        return None
    entry = {
        "id": _slugify(nom),
        "nom": nom,
        "fen": fen,
        "camp_alain": camp_alain,
        "description": (description or "").strip(),
    }
    if not _valid_entry(entry):
        return None

    entries = _load()
    existing_ids = {e.get("id") for e in entries}
    base_id = entry["id"]
    n = 2
    while entry["id"] in existing_ids:
        entry["id"] = f"{base_id}_{n}"
        n += 1

    entries.append(entry)
    _save(entries)
    return entry
