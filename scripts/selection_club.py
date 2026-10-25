"""
scripts/selection_club.py — ChessCoach (issue #143, suite #142)

Sélectionne, parmi les erreurs déjà détectées par build_patterns_erreurs.py
(data/erreurs_detectees.json), des positions pour la future page « club »
(étape 4, hors périmètre ici) : un mélange de positions ÉVIDENTES (un seul
bon coup nettement meilleur que les autres) et DISCUTABLES (plusieurs coups
presque équivalents), avec autant de Blancs que de Noirs que possible.

Ne fait QUE la sélection — aucune page, aucun appel à une IA, aucun réseau.

Critère : pour chaque position, les trois meilleurs coups de Stockfish
(multi-lignes, même profondeur que le mode Exercice — DEPTH_EXERCICE_TEMPS_
REEL, cf. app.api_club_eval) sont comparés du point de vue du camp qui joue
(celui qui a le trait dans la position de départ). Les scores de mat sont
ramenés, comme la classification officielle Lichess (issue #125,
engine_stockfish.cp_to_win_probability), à l'échelle plafonnée à ±PLAFOND_CP
— un mat vaut toujours ±PLAFOND_CP, quel que soit le nombre de coups.

Catégories (constantes modifiables en ligne de commande, cf. --help) :
  - « évident » si l'écart entre le 1er et le 2e coup est >= SEUIL_EVIDENT_CP.
  - « discutable » si cet écart est <= SEUIL_DISCUTABLE_CP ET que l'évaluation
    de la position (convention de Lichess) reste dans
    [-BORNE_POSITION_INDECISE_CP, +BORNE_POSITION_INDECISE_CP].
  - exclues des deux : position avec un mat forcé en <= MAT_MAX_COUPS_EXCLUS
    coups, position invalide (FEN illisible ou partie déjà terminée),
    doublon de position (même FEN déjà vue) ou position avec moins de deux
    coups légaux (rien à comparer).

Un seul processus Stockfish est ouvert pour toute l'exécution (jamais un
par position), fermé dans un bloc finally (erreur ou interruption comprise),
avec une limite de temps globale configurable (--timeout-global).

Usage (depuis ~/ChessCoach, sur les vraies données) :
    python3 scripts/selection_club.py
Sur un fichier de test explicite :
    python3 scripts/selection_club.py --erreurs-path chemin/vers/test.json \
        --output /tmp/essai_club_selection.json
"""

import argparse
import json
import sys
import time
from pathlib import Path

import chess
import chess.engine

from config import DATA_DIR, ERREURS_DETECTEES_PATH
from engine_stockfish import DEPTH_EXERCICE_TEMPS_REEL, find_stockfish

# ── Constantes (issue #143) — toutes modifiables par option de ligne de commande ──

SEUIL_EVIDENT_CP = 200
# Écart minimal (en centipions, point de vue du camp qui joue) entre le 1er
# et le 2e coup pour classer une position « évidente ».

SEUIL_DISCUTABLE_CP = 40
# Écart maximal entre le 1er et le 2e coup pour classer une position
# « discutable ».

BORNE_POSITION_INDECISE_CP = 300
# Une position « discutable » doit en plus avoir une évaluation (convention
# de Lichess, point de vue des Blancs) comprise dans [-BORNE, +BORNE] —
# sinon la position est déjà décidée, l'écart faible entre les coups ne
# traduit alors aucune nuance intéressante pour le jugement.

MAT_MAX_COUPS_EXCLUS = 3
# Un mat forcé annoncé en ce nombre de coups ou moins exclut la position
# des deux catégories (ni « évidente » ni « discutable »).

N_EVIDENTS_DEFAUT = 3
N_DISCUTABLES_DEFAUT = 9

MULTIPV_N = 3  # "les trois meilleurs coups de Stockfish" (énoncé de l'issue)

PLAFOND_CP = 1000
# Même plafond que engine_stockfish.cp_to_win_probability (classification
# officielle Lichess, issue #125) : tout score, mat ou centipions bruts, est
# ramené à cette échelle avant de calculer un écart — un mat vaut toujours
# ±PLAFOND_CP, quel que soit le nombre de coups.

TIMEOUT_GLOBAL_S_DEFAUT = 1800  # 30 minutes

_PHASES_ORDRE = ["ouverture", "milieu_de_partie", "finale", None]


def _charger_erreurs_detectees(path: Path) -> list:
    """Charge data/erreurs_detectees.json — même format et même tolérance
    que app._load_erreurs_detectees (liste vide si absent ou illisible).

    Reproduit ici plutôt qu'importé : importer app.py exécute, dès le
    chargement du module, la lecture de PLUSIEURS fichiers personnels
    réels (coach_memory.json, puzzles_lichess.json, niveau_exercices_
    lichess.json, erreurs_detectees.json) et l'initialisation de Flask/
    SocketIO/EngineManager — hors périmètre de ce script autonome et
    contraire à la consigne « aucune lecture de data/ réel » pour cette
    issue. La logique de lecture elle-même (3 lignes) est strictement
    identique à app._load_erreurs_detectees."""
    path = Path(path)
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Erreurs détectées illisibles ({path}) : {e}")
        return []


def _dedupe_par_fen(erreurs: list) -> tuple:
    """Conserve la première occurrence de chaque fen_avant (ordre du
    fichier, donc déterministe). Retourne (liste_dédupliquée, nb_doublons)."""
    vues = set()
    resultat = []
    doublons = 0
    for e in erreurs:
        fen = e.get("fen_avant")
        if fen in vues:
            doublons += 1
            continue
        vues.add(fen)
        resultat.append(e)
    return resultat, doublons


def _plafonner(cp, mate) -> int:
    """Valeur unique (mat ou centipions) plafonnée à ±PLAFOND_CP, du point
    de vue du joueur au trait — même plafond que la classification
    officielle Lichess (issue #125)."""
    if mate is not None:
        valeur = PLAFOND_CP if mate > 0 else -PLAFOND_CP
    else:
        valeur = cp
    return max(-PLAFOND_CP, min(PLAFOND_CP, valeur))


def _analyser_position(engine: chess.engine.SimpleEngine, board: chess.Board,
                        depth: int) -> list:
    """Les MULTIPV_N meilleurs coups, du point de vue du joueur au trait.
    Retourne une liste de dict {"uci", "san", "cp", "mate"} (cp/mate déjà du
    point de vue du joueur au trait, comme EngineManager.get_multipv)."""
    infos = engine.analyse(board, chess.engine.Limit(depth=depth),
                            multipv=MULTIPV_N, info=chess.engine.INFO_ALL)
    resultat = []
    for info in infos:
        pv = info.get("pv")
        score = info.get("score")
        if not pv or not score:
            continue
        pov = score.pov(board.turn)
        cp = None
        mate = None
        if pov.is_mate():
            mate = pov.mate()
        else:
            cp = pov.score()
        move = pv[0]
        resultat.append({
            "uci": move.uci(),
            "san": board.san(move),
            "cp": cp,
            "mate": mate,
        })
    return resultat


def _position_valide(fen: str) -> chess.Board | None:
    """FEN syntaxiquement et sémantiquement valide, partie pas déjà
    terminée (sinon rien à juger) — None si invalide."""
    try:
        board = chess.Board(fen)
    except Exception:
        return None
    if not board.is_valid() or board.is_game_over():
        return None
    return board


def _classer_candidats(engine: chess.engine.SimpleEngine, erreurs: list,
                        depth: int, timeout_global_s: float) -> tuple:
    """Analyse chaque candidat (un seul processus Stockfish, déjà ouvert) et
    renvoie (evidents, discutables, stats) où stats compte les exclusions."""
    t0 = time.monotonic()
    stats = {
        "candidats_bruts": len(erreurs),
        "positions_invalides": 0,
        "mats_forces_exclus": 0,
        "moins_de_deux_coups_legaux": 0,
        "non_analysees_timeout": 0,
    }
    evidents = []
    discutables = []

    for e in erreurs:
        if time.monotonic() - t0 >= timeout_global_s:
            stats["non_analysees_timeout"] += 1
            continue

        board = _position_valide(e.get("fen_avant", ""))
        if board is None:
            stats["positions_invalides"] += 1
            continue

        coups = _analyser_position(engine, board, depth)
        if len(coups) < 2:
            stats["moins_de_deux_coups_legaux"] += 1
            continue

        mate1 = coups[0]["mate"]
        if mate1 is not None and abs(mate1) <= MAT_MAX_COUPS_EXCLUS:
            stats["mats_forces_exclus"] += 1
            continue

        valeur1 = _plafonner(coups[0]["cp"], coups[0]["mate"])
        valeur2 = _plafonner(coups[1]["cp"], coups[1]["mate"])
        ecart_12 = valeur1 - valeur2
        ecart_13 = None
        if len(coups) >= 3:
            valeur3 = _plafonner(coups[2]["cp"], coups[2]["mate"])
            ecart_13 = valeur1 - valeur3

        signe = 1 if board.turn == chess.WHITE else -1
        eval_blancs_position = signe * valeur1

        if ecart_12 >= SEUIL_EVIDENT_CP:
            categorie = "evident"
        elif ecart_12 <= SEUIL_DISCUTABLE_CP and abs(eval_blancs_position) <= BORNE_POSITION_INDECISE_CP:
            categorie = "discutable"
        else:
            continue

        camp = "blancs" if board.turn == chess.WHITE else "noirs"
        collection_id = e.get("collection_id")
        game_index = e.get("game_index")
        partie_id = f"{collection_id}:{game_index}" if collection_id is not None and game_index is not None else None

        record = {
            "fen": e.get("fen_avant"),
            "camp": camp,
            "categorie": categorie,
            "ecart_1er_2e_cp": ecart_12,
            "ecart_1er_3e_cp": ecart_13,
            "coups": [
                {
                    "coup": c["san"],
                    "eval_blancs_cp": signe * c["cp"] if c["cp"] is not None else None,
                    "eval_blancs_mat": signe * c["mate"] if c["mate"] is not None else None,
                }
                for c in coups
            ],
            "phase": e.get("phase"),
            "partie_id": partie_id,
        }
        (evidents if categorie == "evident" else discutables).append(record)

    return evidents, discutables, stats


def _cle_tri(categorie: str):
    """Tri stable et déterministe, départage explicite par fen en dernier
    recours (stabilité entre deux exécutions même si l'écart donné par le
    moteur varie légèrement, cf. rapport)."""
    if categorie == "evident":
        return lambda r: (-r["ecart_1er_2e_cp"], r["fen"])
    return lambda r: (r["ecart_1er_2e_cp"], abs(r["coups"][0]["eval_blancs_cp"] or 0), r["fen"])


def _selectionner(candidats: list, n_demande: int, categorie: str,
                   parties_deja_utilisees: set) -> tuple:
    """Sélectionne n_demande candidats déjà classés dans `categorie`, en
    excluant les parties déjà utilisées par une autre catégorie (au plus une
    position par partie, tout catégories confondues), avec équilibre
    Blancs/Noirs et mélange des phases en best-effort — jamais de complément
    par des positions hors critère (shortfall signalé dans le rapport).

    Retourne (selection, rapport, parties_utilisees_ici)."""
    candidats = sorted(candidats, key=_cle_tri(categorie))

    pool = []
    parties_vues = set()
    for c in candidats:
        pid = c["partie_id"]
        if pid is not None and (pid in parties_deja_utilisees or pid in parties_vues):
            continue
        if pid is not None:
            parties_vues.add(pid)
        pool.append(c)

    par_camp = {"blancs": [c for c in pool if c["camp"] == "blancs"],
                "noirs": [c for c in pool if c["camp"] == "noirs"]}

    moitie = n_demande // 2
    reste = n_demande - 2 * moitie
    quotas = {"blancs": moitie + reste, "noirs": moitie}  # le reste va aux Blancs, choix déterministe

    def _prendre(camp_liste: list, quota: int) -> list:
        """Mélange des phases par roue libre (round-robin), dans l'ordre
        fixe _PHASES_ORDRE, en respectant l'ordre de tri à l'intérieur de
        chaque phase."""
        par_phase = {p: [c for c in camp_liste if c.get("phase") == p] for p in _PHASES_ORDRE}
        choisis = []
        progresse = True
        while len(choisis) < quota and progresse:
            progresse = False
            for p in _PHASES_ORDRE:
                if len(choisis) >= quota:
                    break
                bucket = par_phase[p]
                if bucket:
                    choisis.append(bucket.pop(0))
                    progresse = True
        return choisis

    choisis_blancs = _prendre(list(par_camp["blancs"]), quotas["blancs"])
    choisis_noirs = _prendre(list(par_camp["noirs"]), quotas["noirs"])

    # Report best-effort : si un camp n'a pas assez de candidats, l'autre
    # camp peut compléter JUSQU'À n_demande (toujours des candidats
    # conformes à la catégorie, seul l'équilibre des camps en pâtit).
    deficit = (quotas["blancs"] - len(choisis_blancs)) + (quotas["noirs"] - len(choisis_noirs))
    if deficit > 0:
        fens_blancs = {c["fen"] for c in choisis_blancs}
        fens_noirs = {c["fen"] for c in choisis_noirs}
        restants_blancs = [c for c in par_camp["blancs"] if c["fen"] not in fens_blancs]
        restants_noirs = [c for c in par_camp["noirs"] if c["fen"] not in fens_noirs]
        for pool_restant, choisis in ((restants_blancs, choisis_blancs), (restants_noirs, choisis_noirs)):
            while deficit > 0 and pool_restant:
                choisis.append(pool_restant.pop(0))
                deficit -= 1

    selection = choisis_blancs + choisis_noirs
    parties_utilisees_ici = {c["partie_id"] for c in selection if c["partie_id"] is not None}

    rapport = {
        "demande": n_demande,
        "trouve": len(selection),
        "blancs": {"demande": quotas["blancs"], "trouve": len(choisis_blancs)},
        "noirs": {"demande": quotas["noirs"], "trouve": len(choisis_noirs)},
    }
    return selection, rapport, parties_utilisees_ici


def _afficher_resume(rapport_evidents: dict, rapport_discutables: dict, stats: dict) -> None:
    print()
    print("=== Sélection club (issue #143) ===")
    print(f"Candidats bruts lus           : {stats['candidats_bruts']}")
    print(f"Doublons de position ignorés  : {stats['doublons_fen']}")
    print(f"Positions invalides ignorées  : {stats['positions_invalides']}")
    print(f"Mats forcés exclus (<= {MAT_MAX_COUPS_EXCLUS} coups) : {stats['mats_forces_exclus']}")
    print(f"Moins de 2 coups légaux       : {stats['moins_de_deux_coups_legaux']}")
    print(f"Non analysées (timeout global): {stats['non_analysees_timeout']}")
    print()
    print(f"{'Catégorie':<12} {'Demandé':>8} {'Trouvé':>8} {'Blancs (d/t)':>14} {'Noirs (d/t)':>14}")
    for nom, rap in (("évident", rapport_evidents), ("discutable", rapport_discutables)):
        print(f"{nom:<12} {rap['demande']:>8} {rap['trouve']:>8} "
              f"{rap['blancs']['demande']:>6}/{rap['blancs']['trouve']:<6} "
              f"{rap['noirs']['demande']:>6}/{rap['noirs']['trouve']:<6}")
    for nom, rap in (("évident", rapport_evidents), ("discutable", rapport_discutables)):
        if rap["trouve"] < rap["demande"]:
            print(f"ATTENTION : seulement {rap['trouve']}/{rap['demande']} position(s) « {nom} » "
                  "trouvée(s) respectant les critères — AUCUN complément hors critère.")
    print()


def _parser_arguments(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--erreurs-path", type=Path, default=ERREURS_DETECTEES_PATH,
                    help=f"Fichier erreurs_detectees.json à lire (défaut : {ERREURS_DETECTEES_PATH})")
    p.add_argument("--output", type=Path, default=DATA_DIR / "club_selection.json",
                    help="Fichier JSON de sortie (défaut : data/club_selection.json)")
    p.add_argument("--seuil-evident", type=int, default=SEUIL_EVIDENT_CP,
                    help=f"Écart mini 1er/2e coup pour « évident » (défaut : {SEUIL_EVIDENT_CP})")
    p.add_argument("--seuil-discutable", type=int, default=SEUIL_DISCUTABLE_CP,
                    help=f"Écart maxi 1er/2e coup pour « discutable » (défaut : {SEUIL_DISCUTABLE_CP})")
    p.add_argument("--borne-indecise", type=int, default=BORNE_POSITION_INDECISE_CP,
                    help=f"|évaluation| maxi pour qu'une position soit « non décidée » (défaut : {BORNE_POSITION_INDECISE_CP})")
    p.add_argument("--mat-max", type=int, default=MAT_MAX_COUPS_EXCLUS,
                    help=f"Mat forcé en ce nombre de coups ou moins -> position exclue (défaut : {MAT_MAX_COUPS_EXCLUS})")
    p.add_argument("--n-evidents", type=int, default=N_EVIDENTS_DEFAUT,
                    help=f"Nombre de positions évidentes à sélectionner (défaut : {N_EVIDENTS_DEFAUT})")
    p.add_argument("--n-discutables", type=int, default=N_DISCUTABLES_DEFAUT,
                    help=f"Nombre de positions discutables à sélectionner (défaut : {N_DISCUTABLES_DEFAUT})")
    p.add_argument("--depth", type=int, default=DEPTH_EXERCICE_TEMPS_REEL,
                    help=f"Profondeur Stockfish (défaut : {DEPTH_EXERCICE_TEMPS_REEL}, même que le mode Exercice)")
    p.add_argument("--timeout-global", type=float, default=TIMEOUT_GLOBAL_S_DEFAUT,
                    help=f"Limite de temps globale en secondes (défaut : {TIMEOUT_GLOBAL_S_DEFAUT})")
    return p.parse_args(argv)


def main(argv=None) -> int:
    global SEUIL_EVIDENT_CP, SEUIL_DISCUTABLE_CP, BORNE_POSITION_INDECISE_CP, MAT_MAX_COUPS_EXCLUS
    args = _parser_arguments(argv)
    SEUIL_EVIDENT_CP = args.seuil_evident
    SEUIL_DISCUTABLE_CP = args.seuil_discutable
    BORNE_POSITION_INDECISE_CP = args.borne_indecise
    MAT_MAX_COUPS_EXCLUS = args.mat_max

    erreurs = _charger_erreurs_detectees(args.erreurs_path)
    erreurs, n_doublons = _dedupe_par_fen(erreurs)
    if not erreurs:
        print(f"Aucune erreur détectée dans {args.erreurs_path} — rien à sélectionner.")

    stockfish_path = find_stockfish()
    if not stockfish_path:
        print("Stockfish introuvable, abandon (aucun fichier écrit).")
        return 1

    evidents, discutables, stats = [], [], {
        "candidats_bruts": len(erreurs) + n_doublons, "doublons_fen": n_doublons,
        "positions_invalides": 0, "mats_forces_exclus": 0,
        "moins_de_deux_coups_legaux": 0, "non_analysees_timeout": 0,
    }

    if erreurs:
        engine = chess.engine.SimpleEngine.popen_uci(stockfish_path)
        try:
            evidents, discutables, stats_analyse = _classer_candidats(
                engine, erreurs, args.depth, args.timeout_global
            )
            stats.update({k: v for k, v in stats_analyse.items() if k != "candidats_bruts"})
        except Exception as e:
            print(f"ERREUR Stockfish pendant l'analyse : {e}")
        finally:
            engine.quit()

    sel_evidents, rapport_evidents, parties_evidents = _selectionner(
        evidents, args.n_evidents, "evident", set()
    )
    sel_discutables, rapport_discutables, _ = _selectionner(
        discutables, args.n_discutables, "discutable", parties_evidents
    )

    _afficher_resume(rapport_evidents, rapport_discutables, stats)

    sortie = {
        "parametres": {
            "depth": args.depth,
            "multipv": MULTIPV_N,
            "seuil_evident_cp": SEUIL_EVIDENT_CP,
            "seuil_discutable_cp": SEUIL_DISCUTABLE_CP,
            "borne_position_indecise_cp": BORNE_POSITION_INDECISE_CP,
            "mat_max_coups_exclus": MAT_MAX_COUPS_EXCLUS,
            "n_evidents_demande": args.n_evidents,
            "n_discutables_demande": args.n_discutables,
        },
        "evidents": sel_evidents,
        "discutables": sel_discutables,
        "resume": {
            "evidents": rapport_evidents,
            "discutables": rapport_discutables,
            "candidats_bruts": stats["candidats_bruts"],
            "doublons_fen_ignores": stats["doublons_fen"],
            "positions_invalides_ignorees": stats["positions_invalides"],
            "mats_forces_exclus": stats["mats_forces_exclus"],
            "positions_sans_assez_de_coups_legaux": stats["moins_de_deux_coups_legaux"],
            "non_analysees_timeout": stats["non_analysees_timeout"],
        },
        "avertissements": [
            "Stockfish peut donner de légères variations d'une exécution à "
            "l'autre à profondeur fixe ; la sélection reste stable tant "
            "qu'une variation ne fait pas franchir un seuil de catégorie "
            "(départage explicite par FEN en cas d'égalité, cf. _cle_tri)."
        ],
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(sortie, f, ensure_ascii=False, indent=2)
    print(f"Écrit : {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
