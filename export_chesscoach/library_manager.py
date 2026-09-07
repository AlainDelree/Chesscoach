"""
library_manager.py — ChessCoach (extrait/adapté d'AlChess)
Bibliothèque PGN personnelle : collections de parties PGN externes
(ex. "Carlsen", "Parties pro", "Mes parties lichess"), importées depuis
lichess/chess.com (fichier multi-parties ou partie unique).

Modèle de données sous DATA_DIR/pgn_library/ :
    manifest.json          — liste des collections (id UUID, name, created)
    <id>/games.pgn          — parties de la collection, en append
    <id>/meta.json          — index des parties (headers + offset dans games.pgn)

Le dossier DATA_DIR/pgn_library/ est créé automatiquement à la première
utilisation. Aucun changement fonctionnel par rapport à la version AlChess :
ce module était déjà mono-utilisateur et sans dépendance pédagogique.
"""

import datetime
import io
import json
import shutil
import sys
import uuid

import chess.pgn

# ── À câbler côté ChessCoach ─────────────────────────────────────────────────
# Remplacer cet import par le point d'entrée de config du nouveau projet.
# Valeur attendue : un pathlib.Path pointant vers le dossier de données de
# l'application (ex. Path.home() / "ChessCoach" / "data").
from config import DATA_DIR

LIBRARY_DIR   = DATA_DIR / "pgn_library"
MANIFEST_PATH = LIBRARY_DIR / "manifest.json"


def _ensure_library_dir():
    LIBRARY_DIR.mkdir(parents=True, exist_ok=True)


def _load_manifest() -> dict:
    _ensure_library_dir()
    if not MANIFEST_PATH.exists():
        return {"collections": []}
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_manifest(manifest: dict):
    _ensure_library_dir()
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)


def _collection_dir(collection_id: str):
    return LIBRARY_DIR / collection_id


def _games_pgn_path(collection_id: str):
    return _collection_dir(collection_id) / "games.pgn"


def _meta_path(collection_id: str):
    return _collection_dir(collection_id) / "meta.json"


def _load_meta(collection_id: str) -> dict:
    meta_path = _meta_path(collection_id)
    if not meta_path.exists():
        return {"games": []}
    with open(meta_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_meta(collection_id: str, meta: dict):
    with open(_meta_path(collection_id), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def _find_collection(manifest: dict, collection_id: str):
    return next((c for c in manifest["collections"] if c["id"] == collection_id), None)


def _require_collection(collection_id: str):
    manifest = _load_manifest()
    entry = _find_collection(manifest, collection_id)
    if entry is None:
        raise ValueError(f"Collection introuvable : {collection_id}")
    return manifest, entry


# ──────────────────────────────────────────────
# Collections
# ──────────────────────────────────────────────

def list_collections() -> list:
    """Retourne la liste des collections, avec leur nombre de parties."""
    manifest = _load_manifest()
    result = []
    for c in manifest["collections"]:
        meta = _load_meta(c["id"])
        result.append({
            "id":         c["id"],
            "name":       c["name"],
            "created":    c["created"],
            "game_count": len(meta["games"]),
        })
    return result


def create_collection(name: str) -> dict:
    """Crée une nouvelle collection (dossier + fichiers vides), l'ajoute au manifest."""
    name = (name or "").strip()
    if not name:
        raise ValueError("Le nom de la collection ne peut pas être vide.")

    manifest = _load_manifest()
    collection_id = str(uuid.uuid4())
    created = datetime.datetime.now().isoformat(timespec="seconds")

    collection_dir = _collection_dir(collection_id)
    collection_dir.mkdir(parents=True, exist_ok=True)
    _games_pgn_path(collection_id).touch()
    _save_meta(collection_id, {"games": []})

    manifest["collections"].append({"id": collection_id, "name": name, "created": created})
    _save_manifest(manifest)

    return {"id": collection_id, "name": name, "created": created, "game_count": 0}


def delete_collection(collection_id: str):
    """Supprime une collection (dossier + entrée manifest)."""
    manifest, _entry = _require_collection(collection_id)

    manifest["collections"] = [c for c in manifest["collections"] if c["id"] != collection_id]
    _save_manifest(manifest)

    collection_dir = _collection_dir(collection_id)
    if collection_dir.exists():
        shutil.rmtree(collection_dir)


# ──────────────────────────────────────────────
# Import PGN (lichess/chess.com, mono ou multi-parties)
# ──────────────────────────────────────────────

def import_pgn(collection_id: str, content: str) -> dict:
    """
    Parse un PGN (une ou plusieurs parties, export lichess/chess.com typique)
    avec python-chess, append les parties au games.pgn de la collection et
    met à jour l'index meta.json.

    Retourne {"ok": bool, "imported": int, "errors": [str, ...]}.
    """
    _require_collection(collection_id)

    meta = _load_meta(collection_id)
    games_path = _games_pgn_path(collection_id)

    errors = []
    imported = 0
    next_index = len(meta["games"])
    stream = io.StringIO(content)

    # newline="" : pas de traduction \n -> \r\n, pour que les offsets écrits
    # dans meta.json correspondent exactement aux octets sur disque.
    with open(games_path, "a", encoding="utf-8", newline="") as out:
        offset = games_path.stat().st_size
        while True:
            # python-chess écrit ses avertissements PGN malformé sur stderr.
            _stderr_cap = io.StringIO()
            _old_stderr = sys.stderr
            sys.stderr = _stderr_cap
            try:
                game = chess.pgn.read_game(stream)
            finally:
                sys.stderr = _old_stderr

            if game is None:
                break

            headers = game.headers
            if not headers.get("White") and not headers.get("Black") and not list(game.mainline_moves()):
                errors.append("Partie ignorée (en-têtes et coups vides)")
                continue

            text = str(game) + "\n\n"
            out.write(text)

            meta["games"].append({
                "index":  next_index,
                "white":  headers.get("White", "?"),
                "black":  headers.get("Black", "?"),
                "date":   headers.get("Date", "????.??.??"),
                "result": headers.get("Result", "*"),
                "event":  headers.get("Event", ""),
                "offset": offset,
            })

            offset += len(text.encode("utf-8"))
            next_index += 1
            imported += 1

    _save_meta(collection_id, meta)

    if imported == 0 and not errors:
        errors.append("Aucune partie valide trouvée dans le PGN fourni.")

    return {"ok": imported > 0, "imported": imported, "errors": errors}


# ──────────────────────────────────────────────
# Consultation
# ──────────────────────────────────────────────

def list_games(collection_id: str) -> list:
    """Retourne l'index des parties d'une collection (sans lire games.pgn)."""
    _require_collection(collection_id)
    return _load_meta(collection_id)["games"]


def load_game(collection_id: str, index: int) -> str:
    """
    Charge le PGN d'une seule partie via son offset dans games.pgn,
    sans relire tout le fichier.
    """
    _require_collection(collection_id)

    games = _load_meta(collection_id)["games"]
    entry = next((g for g in games if g["index"] == index), None)
    if entry is None:
        raise ValueError(f"Partie introuvable (index {index}) dans la collection {collection_id}")

    games_path = _games_pgn_path(collection_id)
    start = entry["offset"]
    later_offsets = [g["offset"] for g in games if g["offset"] > start]
    end = min(later_offsets) if later_offsets else games_path.stat().st_size

    with open(games_path, "rb") as f:
        f.seek(start)
        raw = f.read(end - start)

    return raw.decode("utf-8").strip() + "\n"
