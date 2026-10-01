"""
build_patterns_erreurs.py — ChessCoach (issue Bridge_Agent #3, étendu issue #7)

Analyse Stockfish (profondeur réduite) sur les N parties les plus récentes
d'Alain (pseudo athanatos123, tri par date PGN décroissante, tous types de
parties confondus) pour repérer les coups en erreur significative, les
regrouper par phase de jeu (ouverture / milieu de partie / finale) et
produire des patterns récurrents en langage naturel dans
patterns_erreurs.{ouverture,milieu_de_partie,finale} de coach_memory.json.

Ce premier lot (200-300 parties) sert d'amorçage : traiter l'historique
complet (3532 parties) prendrait trop longtemps en une seule passe — voir
le rapport affiché en fin d'exécution pour calibrer la taille d'un futur lot.

Issue #7 : sauvegarde en plus, dans data/erreurs_detectees.json, le détail
individuel de chaque erreur détectée (FEN avant coup, coup joué, meilleur
coup Stockfish...) — nécessaire pour le mode "Exercice", qui a besoin de
positions réelles précises plutôt que des statistiques agrégées.

Détection, volontairement simple (pas d'appel LLM — RESEAU=non sur cette
issue) :
  - Passe unique par partie : chaque position du plan principal est évaluée
    une seule fois par Stockfish (profondeur réduite), au lieu de deux
    évaluations par coup d'Alain comme le ferait EngineManager.evaluate_move.
  - Coup en erreur significative : classifier_coup(delta_cp) renvoie
    "erreur" (100-300cp) ou "blunder" (>=300cp), voir engine_stockfish.py.
    Les positions déjà décisives (|éval| >= 1000cp avant le coup) sont
    ignorées : la perte de précision n'y est pas un signal utile.
  - Phase de jeu : heuristique sur le numéro de coup plein (<=10 -> ouverture)
    et le nombre de pièces restantes sur l'échiquier (<=12 -> finale),
    sinon milieu de partie.
  - Sous-type de pattern : "matériel" si le coup suivant réellement joué par
    l'adversaire (pas une ligne d'engine) capture une pièce mineure ou
    majeure d'Alain juste après l'erreur ; "positionnel" sinon.

Usage : python build_patterns_erreurs.py
Sauvegarde coach_memory.json via save_coach_memory. Les autres sections
(profil, repertoire_ouvertures, historique_sessions, objectifs_courants)
sont préservées telles quelles.
"""

import io
import json
import statistics
import time
from collections import defaultdict

import chess
import chess.engine
import chess.pgn

import library_manager
from config import COACH_MEMORY_PATH, ERREURS_DETECTEES_PATH
from engine_stockfish import DEPTH_ANALYSE_PARTIE, SEUIL_DECIDE, classifier_coup, find_stockfish
from llm_coach import load_coach_memory, save_coach_memory

ALAIN_PSEUDO = "athanatos123"
NB_PARTIES = 280
PROFONDEUR = 10
SEUIL_DEJA_DECISIF = 1000  # |cp| avant le coup : position déjà gagnée/perdue, on ignore
DELTA_CP_PLAFOND = 1000  # plafond de delta_cp reporté (mate_score peut sinon fausser les moyennes)
PIECE_VALUES = {chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}

PHRASES_MATERIEL = {
    "ouverture": "souvent après une sortie de pièce précipitée, sans vérifier les prises possibles",
    "milieu_de_partie": "généralement lors d'un échange mal calculé ou d'une pièce oubliée en prise",
    "finale": "souvent un pion ou une pièce isolée laissé sans protection en fin de partie",
}
PHRASES_POSITIONNEL = {
    "ouverture": "souvent un développement qui néglige le centre ou la sécurité du roi",
    "milieu_de_partie": "souvent une combinaison manquée ou un coup qui laisse l'adversaire améliorer l'activité de ses pièces",
    "finale": "souvent une manoeuvre de roi ou de pions imprécise qui laisse échapper le gain ou la nulle",
}
NOMS_PHASE = {
    "ouverture": "en ouverture",
    "milieu_de_partie": "au milieu de partie",
    "finale": "en finale",
}


def _select_recent_games(collection_id: str, n: int) -> list:
    games = library_manager.list_games(collection_id)
    games_sorted = sorted(games, key=lambda g: g["date"], reverse=True)
    return games_sorted[:n]


def board_avant_move_san(fen: str, move_uci: str) -> str | None:
    """SAN d'un coup UCI joué depuis une position FEN donnée, sans muter
    l'appelant (utilisé pour convertir le meilleur coup Stockfish en SAN
    lisible dans erreurs_detectees.json)."""
    board = chess.Board(fen)
    move = chess.Move.from_uci(move_uci)
    if move not in board.legal_moves:
        return None
    return board.san(move)


def _phase(board: chess.Board) -> str:
    if board.fullmove_number <= 10:
        return "ouverture"
    if chess.popcount(board.occupied) <= 12:
        return "finale"
    return "milieu_de_partie"


def _analyse_game(engine: chess.engine.SimpleEngine, game: chess.pgn.Game,
                   alain_color: chess.Color, erreurs: list, game_ref: dict) -> int:
    """Évalue chaque position du plan principal une seule fois et détecte les
    coups d'Alain en erreur significative. Retourne le nombre de coups d'Alain
    examinés.

    game_ref (référence de la partie, pour erreurs_detectees.json) est
    fusionné tel quel dans chaque erreur enregistrée."""
    board = chess.Board()
    moves = list(game.mainline_moves())

    cp_blanc = [None] * (len(moves) + 1)
    pv_uci = [None] * (len(moves) + 1)  # meilleur coup UCI suggéré à chaque position
    info = engine.analyse(board, chess.engine.Limit(depth=PROFONDEUR))
    cp_blanc[0] = info["score"].white().score(mate_score=100000)
    pv0 = info.get("pv")
    pv_uci[0] = pv0[0].uci() if pv0 else None

    nb_coups_alain = 0

    for idx, move in enumerate(moves):
        ply = idx + 1  # 1-indexé : impair = Blancs, pair = Noirs
        mover = chess.WHITE if ply % 2 == 1 else chess.BLACK

        board_avant_fullmove = board.fullmove_number
        board_avant_pieces = chess.popcount(board.occupied)
        fen_avant = board.fen()
        san_joue = board.san(move)

        board.push(move)
        info = engine.analyse(board, chess.engine.Limit(depth=PROFONDEUR))
        cp_blanc[ply] = info["score"].white().score(mate_score=100000)
        pv = info.get("pv")
        pv_uci[ply] = pv[0].uci() if pv else None

        if mover != alain_color:
            continue
        nb_coups_alain += 1

        cp_avant_blanc = cp_blanc[ply - 1]
        cp_apres_blanc = cp_blanc[ply]
        if mover == chess.WHITE:
            avant_mover = cp_avant_blanc
            apres_mover = cp_apres_blanc
        else:
            avant_mover = -cp_avant_blanc
            apres_mover = -cp_apres_blanc

        if abs(avant_mover) >= SEUIL_DEJA_DECISIF:
            continue  # position déjà décisive, signal peu utile

        delta_brut = max(0, avant_mover - apres_mover)
        qualite = classifier_coup(delta_brut)
        # Plafond pour le reporting : au-delà, la magnitude exacte (parfois
        # démesurée à cause du mapping mat->cp) n'apporte plus d'info utile,
        # la classification qualite (déjà "blunder") suffit.
        delta = min(delta_brut, DELTA_CP_PLAFOND)
        if qualite not in ("erreur", "blunder"):
            continue

        # Phase évaluée sur la position AVANT le coup d'Alain
        phase = "ouverture" if board_avant_fullmove <= 10 else (
            "finale" if board_avant_pieces <= 12 else "milieu_de_partie"
        )

        # Sous-type : le coup suivant réellement joué par l'adversaire
        # capture-t-il une pièce mineure/majeure d'Alain ?
        materiel = False
        if idx + 1 < len(moves):
            coup_adverse = moves[idx + 1]
            if board.is_capture(coup_adverse):
                piece = board.piece_at(coup_adverse.to_square)
                if piece and piece.piece_type in PIECE_VALUES:
                    materiel = True

        meilleur_coup_uci = pv_uci[ply - 1]
        meilleur_coup_san = None
        if meilleur_coup_uci:
            try:
                meilleur_coup_san = board_avant_move_san(fen_avant, meilleur_coup_uci)
            except Exception:
                meilleur_coup_san = None

        erreurs.append({
            **game_ref,
            "phase": phase,
            "qualite": qualite,
            "delta_cp": delta,
            "materiel": materiel,
            "coup_plein": board_avant_fullmove,
            "fen_avant": fen_avant,
            "coup_joue_san": san_joue,
            "coup_joue_uci": move.uci(),
            "meilleur_coup_uci": meilleur_coup_uci,
            "meilleur_coup_san": meilleur_coup_san,
        })

    return nb_coups_alain


def _revalider_erreur(engine: chess.engine.SimpleEngine, erreur: dict) -> dict | None:
    """Revalide un candidat "erreur"/"blunder" détecté par _analyse_game (à
    PROFONDEUR, un choix de vitesse pour traiter NB_PARTIES parties d'un
    coup) à une profondeur supérieure (DEPTH_ANALYSE_PARTIE — celle déjà
    utilisée par le bouton "Analyser cette partie", issue #75 point 4a) avant
    de le retenir pour erreurs_detectees.json.

    Constat réel (audit de 18 appels du mode "Exercice", 15 exercices) :
    environ un tiers des exercices proposés n'étaient pas de vraies erreurs
    (le coup réel valait le meilleur coup) — ex. Qh4 classé "erreur" à
    profondeur 10 (écart de 148 centipawns) mais seulement 18-40 centipawns à
    profondeur 16 ou plus. Deux critères d'écart, réévalués ici avec le même
    barème mat/cp que _analyse_game (mate_score=100000, valeurs du point de
    vue des Blancs converties vers le joueur qui a joué le coup) :
      - le coup réel perd moins d'environ 100 centipawns par rapport au
        meilleur coup à cette profondeur supérieure (qualite retombe à "bon"
        ou "imprecision" — SEUIL_IMPRECISION/SEUIL_ERREUR dans
        engine_stockfish.py, pas de second seuil redondant ici) ;
      - la position reste décidée dans le MÊME sens avant et après le coup,
        au-delà de SEUIL_DECIDE (qu'Alain y soit gagnant ou perdant) : le
        résultat ne dépendait alors pas de ce choix précis, aucune valeur
        pédagogique comme "erreur à corriger" (même principe que le
        garde-fou "position déjà décidée" de EngineManager.evaluate_move,
        mais appliqué ici symétriquement aux deux sens, pas seulement à
        l'avantage d'Alain : une position déjà perdue par force des deux
        côtés n'offre pas davantage d'alternative réaliste).

    Retourne l'erreur mise à jour (delta_cp/qualite/meilleur_coup_uci/
    meilleur_coup_san recalculés à DEPTH_ANALYSE_PARTIE) si elle reste une
    "erreur"/"blunder" réelle, sinon None (candidat écarté). Best-effort :
    écarte aussi la position si la réévaluation échoue (FEN/coup illisible,
    erreur moteur), plutôt que de la laisser passer invérifiée."""
    try:
        board = chess.Board(erreur["fen_avant"])
        move = chess.Move.from_uci(erreur["coup_joue_uci"])
        if move not in board.legal_moves:
            return None
        mover_blanc = board.turn == chess.WHITE

        info_avant = engine.analyse(board, chess.engine.Limit(depth=DEPTH_ANALYSE_PARTIE))
        cp_avant_blanc = info_avant["score"].white().score(mate_score=100000)
        pv_avant = info_avant.get("pv") or []
        meilleur_coup_uci = pv_avant[0].uci() if pv_avant else None

        board.push(move)
        info_apres = engine.analyse(board, chess.engine.Limit(depth=DEPTH_ANALYSE_PARTIE))
        cp_apres_blanc = info_apres["score"].white().score(mate_score=100000)

        avant_mover = cp_avant_blanc if mover_blanc else -cp_avant_blanc
        apres_mover = cp_apres_blanc if mover_blanc else -cp_apres_blanc

        deja_decide_meme_sens = (
            abs(avant_mover) >= SEUIL_DECIDE and abs(apres_mover) >= SEUIL_DECIDE
            and (avant_mover > 0) == (apres_mover > 0)
        )
        if deja_decide_meme_sens:
            return None

        delta_brut = max(0, avant_mover - apres_mover)
        delta = min(delta_brut, DELTA_CP_PLAFOND)
        qualite = classifier_coup(delta)
        if qualite not in ("erreur", "blunder"):
            return None

        erreur = dict(erreur)
        erreur["qualite"] = qualite
        erreur["delta_cp"] = delta
        if meilleur_coup_uci:
            erreur["meilleur_coup_uci"] = meilleur_coup_uci
            try:
                erreur["meilleur_coup_san"] = board_avant_move_san(erreur["fen_avant"], meilleur_coup_uci)
            except Exception:
                erreur["meilleur_coup_san"] = None
        return erreur
    except Exception as e:
        print(f"Revalidation écartée (erreur sur {erreur.get('fen_avant')}) : {e}")
        return None


def _build_patterns(erreurs: list) -> dict:
    par_phase = defaultdict(list)
    for e in erreurs:
        par_phase[e["phase"]].append(e)

    resultat = {"ouverture": [], "milieu_de_partie": [], "finale": []}
    for phase, liste in par_phase.items():
        materiels = [e for e in liste if e["materiel"]]
        positionnels = [e for e in liste if not e["materiel"]]

        if materiels:
            avg = round(statistics.mean(e["delta_cp"] for e in materiels))
            resultat[phase].append({
                "pattern": (
                    f"Pertes de matériel non compensées {NOMS_PHASE[phase]} "
                    f"({len(materiels)} occurrences sur ce lot, perte moyenne "
                    f"de {avg}cp) : {PHRASES_MATERIEL[phase]}."
                ),
                "occurrences": len(materiels),
                "delta_cp_moyen": avg,
            })

        if positionnels:
            avg = round(statistics.mean(e["delta_cp"] for e in positionnels))
            resultat[phase].append({
                "pattern": (
                    f"Dégradations d'évaluation sans perte de matériel immédiate "
                    f"{NOMS_PHASE[phase]} ({len(positionnels)} occurrences sur ce "
                    f"lot, perte moyenne de {avg}cp) : {PHRASES_POSITIONNEL[phase]}."
                ),
                "occurrences": len(positionnels),
                "delta_cp_moyen": avg,
            })

    return resultat


def main():
    t0 = time.time()

    collections = library_manager.list_collections()
    if not collections:
        print("Aucune collection dans la bibliothèque PGN.")
        return
    collection_id = collections[0]["id"]

    stockfish_path = find_stockfish()
    if not stockfish_path:
        print("Stockfish introuvable, abandon.")
        return

    selection = _select_recent_games(collection_id, NB_PARTIES)

    engine = chess.engine.SimpleEngine.popen_uci(stockfish_path)
    erreurs = []
    parties_analysees = 0
    parties_ignorees = 0
    total_coups_alain = 0

    try:
        for game_entry in selection:
            pgn_text = library_manager.load_game(collection_id, game_entry["index"])
            game = chess.pgn.read_game(io.StringIO(pgn_text))
            if game is None:
                parties_ignorees += 1
                continue

            white = game.headers.get("White", "")
            black = game.headers.get("Black", "")
            if white.lower() == ALAIN_PSEUDO:
                alain_color = chess.WHITE
            elif black.lower() == ALAIN_PSEUDO:
                alain_color = chess.BLACK
            else:
                parties_ignorees += 1
                continue

            game_ref = {
                "collection_id": collection_id,
                "game_index": game_entry["index"],
                "white": white,
                "black": black,
                "date": game.headers.get("Date", "????.??.??"),
                "camp_alain": "blancs" if alain_color == chess.WHITE else "noirs",
            }

            try:
                total_coups_alain += _analyse_game(engine, game, alain_color, erreurs, game_ref)
                parties_analysees += 1
            except Exception as e:
                print(f"Partie {game_entry['index']} ignorée (erreur d'analyse) : {e}")
                parties_ignorees += 1

        # Revalidation à profondeur supérieure (issue #75, point 4a) — avant
        # de fermer le moteur, voir _revalider_erreur pour le détail des deux
        # critères d'écart.
        nb_candidats = len(erreurs)
        print(f"Revalidation de {nb_candidats} candidat(s) à la profondeur {DEPTH_ANALYSE_PARTIE}...")
        erreurs = [e for e in (_revalider_erreur(engine, e) for e in erreurs) if e is not None]
        print(f"Revalidation terminée : {len(erreurs)} conservée(s), {nb_candidats - len(erreurs)} écartée(s)")
    finally:
        engine.quit()

    duree = time.time() - t0

    patterns = _build_patterns(erreurs)

    memory = load_coach_memory(COACH_MEMORY_PATH)
    memory.setdefault("patterns_erreurs", {})
    memory["patterns_erreurs"]["ouverture"] = patterns["ouverture"]
    memory["patterns_erreurs"]["milieu_de_partie"] = patterns["milieu_de_partie"]
    memory["patterns_erreurs"]["finale"] = patterns["finale"]
    save_coach_memory(COACH_MEMORY_PATH, memory)

    erreurs_detectees = [
        {
            "collection_id": e["collection_id"],
            "game_index": e["game_index"],
            "white": e["white"],
            "black": e["black"],
            "date": e["date"],
            "camp_alain": e["camp_alain"],
            "coup_plein": e["coup_plein"],
            "phase": e["phase"],
            "sous_type": "materiel" if e["materiel"] else "positionnel",
            "qualite": e["qualite"],
            "delta_cp": e["delta_cp"],
            "fen_avant": e["fen_avant"],
            "coup_joue_san": e["coup_joue_san"],
            "coup_joue_uci": e["coup_joue_uci"],
            "meilleur_coup_uci": e["meilleur_coup_uci"],
            "meilleur_coup_san": e["meilleur_coup_san"],
        }
        for e in erreurs
    ]
    ERREURS_DETECTEES_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = ERREURS_DETECTEES_PATH.with_suffix(ERREURS_DETECTEES_PATH.suffix + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(erreurs_detectees, f, ensure_ascii=False, indent=2)
    tmp_path.replace(ERREURS_DETECTEES_PATH)

    par_phase_count = defaultdict(int)
    for e in erreurs:
        par_phase_count[e["phase"]] += 1

    print("=== Rapport build_patterns_erreurs ===")
    print(f"Parties sélectionnées : {len(selection)} (analysées : {parties_analysees}, ignorées : {parties_ignorees})")
    print(f"Profondeur Stockfish : {PROFONDEUR}")
    print(f"Coups d'Alain examinés : {total_coups_alain}")
    print(f"Erreurs significatives détectées : {len(erreurs)}")
    print(f"  dont ouverture : {par_phase_count['ouverture']}")
    print(f"  dont milieu_de_partie : {par_phase_count['milieu_de_partie']}")
    print(f"  dont finale : {par_phase_count['finale']}")
    print(f"Durée totale : {duree:.1f}s ({duree/max(1,parties_analysees):.2f}s/partie)")
    print(f"Détail individuel sauvegardé : {ERREURS_DETECTEES_PATH} ({len(erreurs_detectees)} erreurs)")


if __name__ == "__main__":
    main()
