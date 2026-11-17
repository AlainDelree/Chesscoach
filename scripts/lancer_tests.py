"""
scripts/lancer_tests.py — ChessCoach (issue #153)

Lance toute la suite de tests (test_*.py à la racine) en une seule
commande qui se termine toute seule. Chaque fichier tourne dans son
propre process (les fichiers ne peuvent pas partager un process : certains
font importlib.reload(app), ce qui casserait les autres si lancés dans le
même interpréteur). Pas de pytest : chaque fichier est lancé soit via
« python3 -m unittest <module> » (fichiers avec une classe
unittest.TestCase), soit directement « python3 <fichier>.py » (anciens
fichiers de tests sans classe, qui s'exécutent via leur propre main()).

Un délai maximal (--timeout, 300s par défaut) s'applique à chaque fichier.
En cas de dépassement, tout le groupe de process du fichier (l'interpréteur
Python ET le processus Stockfish qu'il a pu lancer) est arrêté — jamais de
processus laissé derrière, même après expiration.

Tests lents (vrai Stockfish, ex. test_issue143_selection_club.py) : sautés
en mode --rapide via la variable d'environnement CHESSCOACH_SKIP_SLOW_TESTS
(cf. docs/contexte/tests.md).

Usage :
    python3 scripts/lancer_tests.py              # suite complète
    python3 scripts/lancer_tests.py --rapide     # sans les tests lents
    python3 scripts/lancer_tests.py --timeout 600
"""

import argparse
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
TIMEOUT_DEFAUT_S = 300

_RE_UNITTEST = re.compile(r"class\s+\w+\([^)]*unittest\.TestCase[^)]*\)\s*:")


def _mode_unittest(chemin: Path) -> bool:
    return bool(_RE_UNITTEST.search(chemin.read_text(encoding="utf-8")))


def _commande(chemin: Path) -> list:
    if _mode_unittest(chemin):
        return [sys.executable, "-m", "unittest", "-q", chemin.stem]
    return [sys.executable, chemin.name]


def _tuer_groupe(proc: subprocess.Popen) -> None:
    """Arrête tout le groupe de process (Python + Stockfish éventuel)."""
    try:
        pgid = os.getpgid(proc.pid)
    except ProcessLookupError:
        return
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(pgid, sig)
        except ProcessLookupError:
            return
        for _ in range(20):
            if proc.poll() is not None:
                return
            time.sleep(0.25)


def _lancer_fichier(chemin: Path, timeout_s: int, env: dict) -> dict:
    cmd = _commande(chemin)
    debut = time.monotonic()
    proc = subprocess.Popen(
        cmd, cwd=RACINE, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, start_new_session=True,
    )
    try:
        try:
            sortie, _ = proc.communicate(timeout=timeout_s)
            statut = "OK" if proc.returncode == 0 else "ECHEC"
        except subprocess.TimeoutExpired:
            _tuer_groupe(proc)
            try:
                sortie, _ = proc.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                sortie = ""
            statut = "EXPIRE"
    finally:
        # Garde-fou : ce fichier ne doit jamais laisser de process vivant,
        # même si communicate() a levé une exception inattendue ci-dessus.
        if proc.poll() is None:
            _tuer_groupe(proc)
    duree = time.monotonic() - debut
    return {
        "fichier": chemin.name, "statut": statut, "duree": duree,
        "sortie": sortie, "code": proc.returncode,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--rapide", action="store_true",
                    help="saute les tests lents (CHESSCOACH_SKIP_SLOW_TESTS=1)")
    p.add_argument("--timeout", type=int, default=TIMEOUT_DEFAUT_S,
                    help=f"délai maximal par fichier, en secondes (défaut {TIMEOUT_DEFAUT_S})")
    args = p.parse_args(argv)

    env = dict(os.environ)
    if args.rapide:
        env["CHESSCOACH_SKIP_SLOW_TESTS"] = "1"
    else:
        env.pop("CHESSCOACH_SKIP_SLOW_TESTS", None)

    fichiers = sorted(RACINE.glob("test_*.py"))
    if not fichiers:
        print("Aucun fichier test_*.py trouvé à la racine.")
        return 1

    resultats = []
    debut_total = time.monotonic()
    for chemin in fichiers:
        print(f"-> {chemin.name} ...", flush=True)
        r = _lancer_fichier(chemin, args.timeout, env)
        resultats.append(r)
        print(f"   {r['statut']} en {r['duree']:.1f}s")
        if r["statut"] != "OK":
            print(r["sortie"][-4000:])
    duree_total = time.monotonic() - debut_total

    reussis = [r for r in resultats if r["statut"] == "OK"]
    echoues = [r for r in resultats if r["statut"] == "ECHEC"]
    expires = [r for r in resultats if r["statut"] == "EXPIRE"]

    print("\n" + "=" * 70)
    print(
        f"Résumé : {len(reussis)} réussi(s), {len(echoues)} échoué(s), "
        f"{len(expires)} expiré(s) sur {len(resultats)} fichiers — "
        f"{duree_total:.1f}s au total"
    )
    if echoues:
        print("Échoués : " + ", ".join(r["fichier"] for r in echoues))
    if expires:
        print("Expirés : " + ", ".join(r["fichier"] for r in expires))
    print("=" * 70)

    return 0 if not echoues and not expires else 1


if __name__ == "__main__":
    sys.exit(main())
