"""
generer_golden_master_issue141.py — ChessCoach (issue #141, suite #140)

Génère ou régénère golden_master_issue141.json, la référence committée
comparée par test_issue141_golden_master.py. Jamais exécuté par la suite de
tests elle-même — seulement à la main, pour établir la référence AVANT une
refactorisation (code d'origine) ou pour la revalider APRÈS (code
refactorisé, en vérifiant qu'elle reste strictement identique).

Usage :
    python3 generer_golden_master_issue141.py
"""

import importlib
import json
import sys
import tempfile
from pathlib import Path

from engine_stockfish import find_stockfish
from test_issue128 import _patch_config_paths_vers_tmp, _restaure_config_paths
from test_issue141_golden_master import REFERENCE_PATH, capturer_golden_master


def main() -> None:
    if not find_stockfish():
        raise RuntimeError("Stockfish introuvable sur cette machine.")

    tmp = tempfile.TemporaryDirectory()
    tmp_dir = Path(tmp.name)

    import config as config_module
    anciens = _patch_config_paths_vers_tmp(config_module, tmp_dir)

    if "app" in sys.modules:
        raise RuntimeError(
            "app.py était déjà importé : l'isolation des chemins de "
            "données ne peut plus être garantie."
        )
    app_module = importlib.import_module("app")
    client = app_module.socketio.test_client(app_module.app)

    resultats = capturer_golden_master(app_module, client)

    REFERENCE_PATH.write_text(
        json.dumps(resultats, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    _restaure_config_paths(config_module, anciens)
    tmp.cleanup()
    print(f"Golden master écrit : {REFERENCE_PATH} ({len(resultats)} cas)")


if __name__ == "__main__":
    main()
