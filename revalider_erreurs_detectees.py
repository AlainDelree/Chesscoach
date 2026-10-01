"""
revalider_erreurs_detectees.py — ChessCoach (issue #75, point 4b)

Revalide un fichier erreurs_detectees.json DÉJÀ existant (produit par une
exécution antérieure de build_patterns_erreurs.py, avant son propre correctif
de revalidation à la volée — issue #75, point 4a) : relit chaque entrée,
rejoue sa position avec Stockfish à une profondeur supérieure
(DEPTH_ANALYSE_PARTIE, même profondeur que le bouton "Analyser cette
partie"), et n'en conserve que celles qui restent de vraies "erreur"/
"blunder" (cf. build_patterns_erreurs._revalider_erreur pour le détail des
deux critères d'écart : perte réelle inférieure à ~100 centipawns par rapport
au meilleur coup à cette profondeur, ou position déjà décidée dans le même
sens avant et après le coup).

Sauvegarde automatique de l'ancien fichier avant toute écriture (horodatée,
jamais écrasée d'une exécution à l'autre) — écriture finale atomique (fichier
temporaire puis remplacement), comme build_patterns_erreurs.py.

Usage (chemin par défaut : config.ERREURS_DETECTEES_PATH) :
    python3 revalider_erreurs_detectees.py
Ou sur un fichier explicite (ex. pour un essai sur des données de test) :
    python3 revalider_erreurs_detectees.py chemin/vers/fichier.json

Volontairement livré SANS être exécuté sur les données réelles d'Alain dans
le cadre de cette issue (consigne explicite) — à lancer par Alain lui-même
quand il le souhaite, une fois la commande ci-dessus vérifiée sur un petit
fichier d'essai.
"""

import json
import shutil
import sys
import time
from pathlib import Path

import chess.engine

from build_patterns_erreurs import _revalider_erreur
from config import ERREURS_DETECTEES_PATH
from engine_stockfish import DEPTH_ANALYSE_PARTIE, find_stockfish


def _sauvegarder(path: Path) -> Path:
    """Copie `path` vers un fichier horodaté (jamais écrasé d'une exécution à
    l'autre) avant toute modification. Retourne le chemin de la sauvegarde."""
    horodatage = time.strftime("%Y%m%d-%H%M%S")
    backup_path = path.with_name(f"{path.stem}.avant-revalidation-{horodatage}{path.suffix}")
    shutil.copy2(path, backup_path)
    return backup_path


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(ERREURS_DETECTEES_PATH)
    if not path.exists():
        print(f"Fichier introuvable : {path}")
        return

    with open(path, "r", encoding="utf-8") as f:
        erreurs = json.load(f)
    if not isinstance(erreurs, list):
        print(f"Format inattendu dans {path} (liste JSON attendue), abandon.")
        return

    backup_path = _sauvegarder(path)
    print(f"Sauvegarde de l'ancien fichier : {backup_path}")

    stockfish_path = find_stockfish()
    if not stockfish_path:
        print("Stockfish introuvable, abandon (aucune modification écrite).")
        return

    t0 = time.time()
    nb_avant = len(erreurs)
    print(f"Revalidation de {nb_avant} position(s) à la profondeur {DEPTH_ANALYSE_PARTIE}...")

    engine = chess.engine.SimpleEngine.popen_uci(stockfish_path)
    try:
        erreurs_revalidees = [
            e for e in (_revalider_erreur(engine, e) for e in erreurs) if e is not None
        ]
    finally:
        engine.quit()

    nb_apres = len(erreurs_revalidees)
    duree = time.time() - t0

    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(erreurs_revalidees, f, ensure_ascii=False, indent=2)
    tmp_path.replace(path)

    print("=== Rapport de revalidation ===")
    print(f"Positions conservées : {nb_apres}")
    print(f"Positions écartées   : {nb_avant - nb_apres}")
    print(f"Durée totale : {duree:.1f}s")
    print(f"Fichier mis à jour : {path}")
    print(f"Ancien fichier sauvegardé dans : {backup_path}")


if __name__ == "__main__":
    main()
