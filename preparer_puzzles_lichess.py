#!/usr/bin/env python3
"""
preparer_puzzles_lichess.py — ChessCoach (issue #78)

Script de préparation HORS-LIGNE, sans aucun accès réseau, pour la source
d'exercices « Problèmes Lichess ». Lit le CSV de la base ouverte de
problèmes Lichess (licence CC0, colonnes PuzzleId, FEN, Moves, Rating,
RatingDeviation, Popularity, NbPlays, Themes, GameUrl, OpeningTags, et
éventuellement DailyDate — Alain la télécharge lui-même, CCL n'y touche
jamais), filtre les problèmes fiables et exploitables, les classe par
catégorie de thème (lichess_puzzles.CATEGORIES) et par phase (opening/
middlegame/endgame), échantillonne un nombre raisonnable par catégorie et
par tranche de note, et écrit le résultat dans data/puzzles_lichess.json
(donnée personnelle, gitignorée comme le reste de data/, hors du dépôt).

Usage :
    python3 preparer_puzzles_lichess.py <chemin_vers_le_csv> [--sortie FICHIER]
    python3 preparer_puzzles_lichess.py data/lichess_db_puzzle.csv

Formats acceptés pour l'entrée : CSV brut (.csv), gzip (.csv.gz — module
`gzip` de la bibliothèque standard, toujours disponible), zstandard
(.csv.zst — nécessite le module tiers `zstandard` ; s'il est absent, le
script l'indique clairement et s'arrête : décompresser le fichier à la main
au préalable, par exemple `zstd -d lichess_db_puzzle.csv.zst`).

N'écrit QUE data/puzzles_lichess.json (ou --sortie) — ne touche à aucune
autre donnée (pas de coach_memory.json, pas d'exercice_historique.json).
"""

import argparse
import csv
import gzip
import json
import random
import sys
from pathlib import Path

import chess

import config
import lichess_puzzles

# ── Filtres de fiabilité/exploitabilité (issue #78, énoncé) ─────────────────
# Réglables ici uniquement.
RATING_MIN = 800
RATING_MAX = 2200
RATING_DEVIATION_MAX = 100
NB_PLAYS_MIN = 500
POPULARITY_MIN = 80

# ── Échantillonnage par catégorie et par tranche de note ────────────────────
# "quelques milliers à quelques dizaines de milliers répartis par catégorie
# et par tranches de note" (issue #78, énoncé) : une tranche = 100 points de
# note (14 tranches entre 800 et 2200), un maximum de problèmes conservés par
# (catégorie, tranche) — 16 catégories x 14 tranches x 200 = 44800 au
# maximum, en pratique nettement moins (un problème est rarement seul dans sa
# catégorie, et les notes extrêmes sont plus rares). Réglable ici uniquement.
TAILLE_TRANCHE = 100
MAX_PAR_CATEGORIE_ET_TRANCHE = 200

# Tirage déterministe (issue #78) : même CSV en entrée -> même fichier en
# sortie d'un lancement à l'autre, plus simple à vérifier/comparer. Purement
# un choix de confort, aucune signification cryptographique.
GRAINE_ECHANTILLONNAGE = 20260131


def _ouvrir_csv(chemin: Path):
    """Ouvre le CSV, décompressé à la volée pour .gz (stdlib) ou .zst (module
    tiers `zstandard`, optionnel) — jamais de téléchargement, jamais d'accès
    réseau. Lève SystemExit avec un message clair si le format ne peut pas
    être lu avec ce qui est disponible sur la machine."""
    suffixes = chemin.suffixes
    if chemin.suffix == ".gz":
        return gzip.open(chemin, mode="rt", encoding="utf-8", newline="")
    if chemin.suffix == ".zst":
        try:
            import zstandard
        except ImportError:
            sys.exit(
                f"Le fichier '{chemin}' est compressé en zstandard (.zst), mais le "
                "module Python 'zstandard' n'est pas installé sur cette machine "
                "(pip install zstandard). Sans lui, décompressez le fichier à la "
                "main avant de relancer ce script, par exemple :\n"
                f"    zstd -d {chemin}\n"
                "ou avec un outil d'archive graphique, puis relancez ce script sur "
                "le fichier .csv obtenu."
            )
        dctx = zstandard.ZstdDecompressor()
        fh = open(chemin, "rb")
        reader = dctx.stream_reader(fh)
        import io
        return io.TextIOWrapper(reader, encoding="utf-8", newline="")
    return open(chemin, "r", encoding="utf-8", newline="")


def _classer_phases(themes: list) -> list:
    return [t for t in ("opening", "middlegame", "endgame") if t in themes]


def _classer_categories(themes: list) -> list:
    return [c for c in lichess_puzzles.CATEGORIES if lichess_puzzles.categorie_correspond(themes, c)]


def _preparer_entree(row: dict, rating: int, rating_deviation: int, popularity: int,
                      nb_plays: int) -> dict | None:
    """Valide et normalise une ligne du CSV déjà passée par le filtre de
    fiabilité (cf. preparer()) en une entrée du pool, ou None si elle doit
    être écartée (aucune catégorie connue, FEN/Moves invalides)."""
    themes = (row.get("Themes") or "").split()
    categories = _classer_categories(themes)
    if not categories:
        # Aucune des 16 catégories de niveau : inutilisable par le tirage
        # (lichess_puzzles.tirer_probleme exige toujours une catégorie), pas
        # la peine de le conserver.
        return None
    phases = _classer_phases(themes)

    moves = (row.get("Moves") or "").split()
    if len(moves) < 2:
        # Il faut au moins le coup adverse initial + un coup du joueur.
        return None

    try:
        board = chess.Board(row["FEN"])
        premier_coup = chess.Move.from_uci(moves[0])
        if premier_coup not in board.legal_moves:
            return None
        board.push(premier_coup)
    except (ValueError, KeyError):
        return None

    camp_alain = "blancs" if board.turn == chess.WHITE else "noirs"
    fen_position = board.fen()

    # Validité de toute la suite (solution) depuis fen_position, pour ne
    # jamais transmettre à l'appli une ligne illégale.
    solution = moves[1:]
    board_verif = board.copy()
    for uci in solution:
        try:
            coup = chess.Move.from_uci(uci)
        except ValueError:
            return None
        if coup not in board_verif.legal_moves:
            return None
        board_verif.push(coup)

    return {
        "fen_avant": f"lichess:{row['PuzzleId']}",  # clé d'historique (issue #78), PAS une FEN
        "puzzle_id": row["PuzzleId"],
        "rating": rating,
        "rating_deviation": rating_deviation,
        "popularity": popularity,
        "nb_plays": nb_plays,
        "themes": themes,
        "categories": categories,
        "phases": phases,
        "camp_alain": camp_alain,
        "fen_position": fen_position,
        "premier_coup_adverse": moves[0],
        "solution": solution,
        "game_url": row.get("GameUrl", ""),
        "opening_tags": row.get("OpeningTags", ""),
    }


def _tranche(rating: int) -> int:
    tranche = (rating // TAILLE_TRANCHE) * TAILLE_TRANCHE
    return min(tranche, RATING_MAX - TAILLE_TRANCHE)


def preparer(chemin_csv: Path) -> tuple[list, dict]:
    """Lit et classe tout le CSV, puis échantillonne. Retourne (pool_final,
    stats) — stats est un résumé imprimable, pas écrit sur le disque."""
    total_lignes = 0
    rejets_filtre = 0
    rejets_categorie = 0
    rejets_invalides = 0
    candidats = []

    with _ouvrir_csv(chemin_csv) as f:
        reader = csv.DictReader(f)
        for row in reader:
            total_lignes += 1
            try:
                rating = int(row["Rating"])
                rating_deviation = int(row["RatingDeviation"])
                popularity = int(row["Popularity"])
                nb_plays = int(row["NbPlays"])
                filtre_ok = (
                    RATING_MIN <= rating <= RATING_MAX
                    and rating_deviation <= RATING_DEVIATION_MAX
                    and nb_plays >= NB_PLAYS_MIN
                    and popularity >= POPULARITY_MIN
                )
            except (KeyError, ValueError):
                filtre_ok = False
            if not filtre_ok:
                rejets_filtre += 1
                continue

            entree = _preparer_entree(row, rating, rating_deviation, popularity, nb_plays)
            if entree is None:
                themes = (row.get("Themes") or "").split()
                if not _classer_categories(themes):
                    rejets_categorie += 1
                else:
                    rejets_invalides += 1
                continue
            candidats.append(entree)

    # Échantillonnage par (catégorie, tranche de note) — un problème peut
    # être retenu via plusieurs catégories différentes, il n'est stocké
    # qu'une seule fois dans le pool final (ensemble d'index retenus).
    rng = random.Random(GRAINE_ECHANTILLONNAGE)
    par_case = {}  # (categorie, tranche) -> [index]
    for idx, entree in enumerate(candidats):
        tranche = _tranche(entree["rating"])
        for categorie in entree["categories"]:
            par_case.setdefault((categorie, tranche), []).append(idx)

    retenus = set()
    comptes_avant = {}
    comptes_apres = {}
    for (categorie, tranche), indices in par_case.items():
        comptes_avant[(categorie, tranche)] = len(indices)
        rng.shuffle(indices)
        gardes = indices[:MAX_PAR_CATEGORIE_ET_TRANCHE]
        comptes_apres[(categorie, tranche)] = len(gardes)
        retenus.update(gardes)

    pool_final = [candidats[i] for i in sorted(retenus)]

    stats = {
        "total_lignes_csv": total_lignes,
        "rejets_filtre_fiabilite": rejets_filtre,
        "rejets_sans_categorie": rejets_categorie,
        "rejets_fen_ou_coups_invalides": rejets_invalides,
        "candidats_apres_filtre_et_classement": len(candidats),
        "pool_final": len(pool_final),
        "comptes_avant": comptes_avant,
        "comptes_apres": comptes_apres,
    }
    return pool_final, stats


def _afficher_resume(stats: dict) -> None:
    print("── Résumé preparer_puzzles_lichess.py ──────────────────────────")
    print(f"Lignes lues dans le CSV           : {stats['total_lignes_csv']}")
    print(f"Écartées (note/fiabilité hors filtre) : {stats['rejets_filtre_fiabilite']}")
    print(f"Écartées (aucune catégorie connue) : {stats['rejets_sans_categorie']}")
    print(f"Écartées (FEN/coups invalides)    : {stats['rejets_fen_ou_coups_invalides']}")
    print(f"Candidats classés avant échantillonnage : {stats['candidats_apres_filtre_et_classement']}")
    print(f"Problèmes conservés dans le pool final   : {stats['pool_final']}")
    print()
    print("Par catégorie et par tranche de note (gardés / trouvés) :")
    categories_vues = sorted({c for (c, _t) in stats["comptes_avant"]})
    for categorie in categories_vues:
        libelle = lichess_puzzles.CATEGORIES.get(categorie, categorie)
        total_cat_avant = sum(v for (c, _t), v in stats["comptes_avant"].items() if c == categorie)
        total_cat_apres = sum(v for (c, _t), v in stats["comptes_apres"].items() if c == categorie)
        print(f"  {categorie} ({libelle}) : {total_cat_apres} / {total_cat_avant}")
        tranches = sorted(t for (c, t) in stats["comptes_avant"] if c == categorie)
        for tranche in tranches:
            avant = stats["comptes_avant"][(categorie, tranche)]
            apres = stats["comptes_apres"][(categorie, tranche)]
            print(f"      [{tranche}-{tranche + TAILLE_TRANCHE}) : {apres} / {avant}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("csv", type=Path, help="Chemin vers le CSV (ou .csv.gz/.csv.zst) de la base Lichess")
    parser.add_argument(
        "--sortie", type=Path, default=config.LICHESS_PUZZLES_PATH,
        help=f"Fichier JSON de sortie (défaut : {config.LICHESS_PUZZLES_PATH})",
    )
    args = parser.parse_args()

    if not args.csv.exists():
        sys.exit(f"Fichier introuvable : {args.csv}")

    pool_final, stats = preparer(args.csv)
    if not pool_final:
        sys.exit("Aucun problème retenu — vérifier le CSV et les filtres de fiabilité en tête de script.")

    args.sortie.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.sortie.with_suffix(args.sortie.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(pool_final, f, ensure_ascii=False, indent=2)
    tmp.replace(args.sortie)

    _afficher_resume(stats)
    print()
    print(f"Écrit : {args.sortie}")


if __name__ == "__main__":
    main()
