#!/usr/bin/env python3
"""
non_regression_coach.py — ChessCoach (issue #93)

Rejoue une liste de positions où le coach s'est trompé par le passé (tour
inexistante citée, coup qualifié "illégal" à tort, "échange de dames" pour
une dame prise contre une tour, "dame clouée" alors qu'elle ne l'est pas,
"équilibre matériel" annoncé alors qu'un camp est en avance...) et vérifie,
pour chacune :
  1. les FAITS que le contexte réellement envoyé au coach doit contenir —
     construit avec les mêmes fonctions que l'application (game_facts.py,
     coach_reliability.py, engine_stockfish.py) et un vrai Stockfish, sans
     jamais passer par app.py/Flask/SocketIO ni par une instance en cours
     d'exécution ;
  2. si --api est donné, la réponse réellement envoyée par le coach (Claude) :
     aucun motif interdit, les motifs attendus présents, et la pastille de
     fiabilité conforme (coach_reliability.evaluer_fiabilite, via
     llm_coach.get_coach_response — strictement le même chemin que
     l'application).

Isolation (issue #93, tâche 3) : ce script ne lit ni ne modifie jamais
coach_memory.json, erreurs_detectees.json, exercice_historique.json,
coach_calls.log ni signalements.log d'Alain. Il journalise ses propres
appels dans un fichier DISTINCT, NON_REGRESSION_LOG_PATH ci-dessous (sous
data/logs, comme les autres journaux du projet, mais sous un nom différent)
et passe toujours coach_memory={} à get_coach_response (mémoire de
progression neutre, jamais relue depuis le disque). Le seul fichier
personnel jamais lu est, à la demande explicite d'Alain (--depuis-signalement),
SIGNALEMENTS_LOG_PATH — en lecture seule, pour créer un squelette de cas.

Usage (une seule commande) :
    python3 non_regression_coach.py [--cas ID [ID ...]] [--repetitions N]
                                     [--api] [--modele {sonnet,haiku}]
                                     [--verbose]
    python3 non_regression_coach.py --depuis-signalement ID --nouvel-id ID

Voir tests/cas_coach/README.md pour le format des fichiers de cas et pour
ajouter un nouveau cas.
"""

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

import chess

import coach_reliability
import config
import game_facts
import llm_coach
from engine_stockfish import DEPTH_EXERCICE_TEMPS_REEL, EngineManager, find_stockfish

RACINE = Path(__file__).resolve().parent
CAS_DIR = RACINE / "tests" / "cas_coach"

# Journal DISTINCT de coach_calls.log (issue #93, tâche 3 — isolation) : un
# chemin relatif au script lui-même, jamais config.DATA_DIR/config.
# COACH_CALLS_LOG_PATH. En usage réel (script exécuté depuis la racine du
# projet ~/ChessCoach), RACINE == Path.home()/"ChessCoach" et ce chemin
# tombe donc naturellement dans data/logs/, comme les autres journaux —
# sans jamais dépendre de config.DATA_DIR, qui reste fixé sur ~/ChessCoach
# quel que soit le répertoire de travail courant (utile notamment quand ce
# script est testé depuis un autre clone/worktree du dépôt).
NON_REGRESSION_LOG_PATH = RACINE / "data" / "logs" / "non_regression_coach_calls.log"

_SCALAR_FIELDS = (
    "id", "description", "source", "fen", "coup_propose", "camp_alain",
    "meilleur_coup", "pastille_attendue",
    # question (issue #96, optionnel) : simule une question de suivi du chat
    # libre pendant l'exercice portant sur un coup précis (ex. "et Bxh7+ ?"),
    # au lieu du message initial "Commente le coup que je propose..." —
    # cf. construire_contexte ci-dessous.
    "question",
)
_BLOCK_FIELDS = (
    "faits_attendus", "motifs_interdits", "motifs_attendus",
    # motifs_interdits_stricts (issue #98, point 2c) : comme motifs_interdits,
    # mais vérifié en plus sur la PREMIÈRE réponse du coach (avant une
    # éventuelle relance automatique de fiabilité, cf. verifier_reponse) —
    # pour les motifs jugés assez graves pour ne JAMAIS tolérer qu'ils aient
    # seulement été corrigés après coup.
    "motifs_interdits_stricts",
)


class CasInvalideError(Exception):
    pass


# ── Chargement des fichiers de cas ──────────────────────────────────────────

def parser_cas(path: Path) -> dict:
    """Parse un fichier .case (format documenté dans tests/cas_coach/README.md) :
    lignes "clé: valeur" pour les champs scalaires, "clé:" suivie de lignes
    indentées pour les champs listes (faits_attendus/motifs_interdits/
    motifs_attendus), lignes "#..." ignorées (commentaires)."""
    cas = {champ: [] for champ in _BLOCK_FIELDS}
    bloc_courant = None
    for ligne_brute in path.read_text(encoding="utf-8").splitlines():
        ligne = ligne_brute.rstrip()
        if not ligne.strip() or ligne.lstrip().startswith("#"):
            continue
        if not ligne[:1].isspace():
            if ":" not in ligne:
                continue
            cle, _, valeur = ligne.partition(":")
            cle, valeur = cle.strip(), valeur.strip()
            if cle in _BLOCK_FIELDS:
                bloc_courant = cle
                if valeur:
                    cas[cle].append(valeur)
            else:
                bloc_courant = None
                cas[cle] = valeur
        elif bloc_courant:
            item = ligne.strip()
            if item.startswith("- "):
                item = item[2:].strip()
            if item:
                cas[bloc_courant].append(item)
    cas["_fichier"] = str(path)
    manquants = [c for c in ("id", "fen", "coup_propose", "camp_alain", "meilleur_coup") if not cas.get(c)]
    if manquants:
        raise CasInvalideError(f"{path.name} : champ(s) obligatoire(s) manquant(s) : {', '.join(manquants)}")
    if cas["camp_alain"] not in ("blancs", "noirs"):
        raise CasInvalideError(f"{path.name} : camp_alain doit être \"blancs\" ou \"noirs\" (valeur : {cas['camp_alain']!r})")
    return cas


def charger_cas(identifiants: list[str] | None = None) -> list[dict]:
    if not CAS_DIR.is_dir():
        raise CasInvalideError(f"Dossier de cas introuvable : {CAS_DIR}")
    fichiers = sorted(CAS_DIR.glob("*.case"))
    tous = [parser_cas(f) for f in fichiers]
    if not identifiants:
        return tous
    par_id = {c["id"]: c for c in tous}
    inconnus = [i for i in identifiants if i not in par_id]
    if inconnus:
        disponibles = ", ".join(sorted(par_id)) or "(aucun)"
        raise CasInvalideError(f"Cas inconnu(s) : {', '.join(inconnus)}. Disponibles : {disponibles}")
    return [par_id[i] for i in identifiants]


# ── Reconstruction du contexte envoyé au coach (mêmes fonctions que app.py) ─
# Les quatre fonctions suivantes reprennent délibérément le même enchaînement
# d'appels EngineManager/game_facts que app.py (_evaluate_move_for_coach/
# _calculer_menace_adverse/_calculer_idees_coup/_calculer_reponses_adverses),
# sur une instance LOCALE d'EngineManager — jamais sur app.engine_manager ni
# sur une instance de l'application en cours d'exécution (issue #93, tâche 3).

def _evaluer_coup_pour_coach(engine_manager, fen_avant: str, move: "chess.Move") -> dict:
    result = {
        "meilleur_coup": "", "verdict_qualite": None, "verdict_delta_cp": None,
        "pv_coup_propose": "", "pv_meilleur_coup": "", "analyse_indisponible": True,
    }
    board = chess.Board(fen_avant)
    verdict_qualite, verdict_delta_cp, meilleur_coup_uci, pv_info = engine_manager.evaluate_move(
        board, move, depth=DEPTH_EXERCICE_TEMPS_REEL, always_return_best=True, return_pv=True
    )
    result["verdict_qualite"] = verdict_qualite
    result["verdict_delta_cp"] = verdict_delta_cp
    result["pv_coup_propose"] = pv_info.get("pv_coup_propose", "")
    result["pv_meilleur_coup"] = pv_info.get("pv_meilleur_coup", "")
    result["analyse_indisponible"] = verdict_qualite is None
    if meilleur_coup_uci:
        try:
            result["meilleur_coup"] = board.san(chess.Move.from_uci(meilleur_coup_uci))
        except Exception:
            result["meilleur_coup"] = meilleur_coup_uci
    return result


def _calculer_menace_adverse(engine_manager, fen_avant: str, depth: int = DEPTH_EXERCICE_TEMPS_REEL) -> dict:
    board = chess.Board(fen_avant)
    return engine_manager.get_threats(board, depth=depth, n=2)


def _calculer_idees_coup(engine_manager, fen_avant: str, coup, camp_alain: str, menace_data: dict | None) -> list:
    if not coup:
        return []
    try:
        board = chess.Board(fen_avant)
        try:
            move = board.parse_san(coup) if isinstance(coup, str) else coup
        except ValueError:
            move = chess.Move.from_uci(coup)
        if move not in board.legal_moves:
            return []
        board_apres = board.copy()
        board_apres.push(move)
    except Exception:
        return []
    breakdown_avant = engine_manager.get_eval_breakdown(fen_avant)
    breakdown_apres = engine_manager.get_eval_breakdown(board_apres.fen())
    if not breakdown_avant or not breakdown_apres:
        return []
    return game_facts.build_idees_coup(fen_avant, coup, camp_alain, breakdown_avant, breakdown_apres, menace_data)


def _calculer_reponses_adverses(engine_manager, fen_apres_coup: str) -> dict:
    if not fen_apres_coup:
        return {"disponible": False, "raison": "position_illisible"}
    board = chess.Board(fen_apres_coup)
    return engine_manager.get_reponses_adverses(board, depth=DEPTH_EXERCICE_TEMPS_REEL, n=4)


def _eval_blancs_apres(engine_manager, board: "chess.Board", depth: int = 8) -> tuple:
    eval_info = engine_manager.evaluate(board, depth=depth)
    sign = 1 if board.turn == chess.WHITE else -1
    if eval_info["mate"] is not None:
        return None, sign * eval_info["mate"]
    if eval_info["cp"] is not None:
        return sign * eval_info["cp"], None
    return None, None


def _vers_point_de_vue_alain(valeur, camp_alain: str):
    if valeur is None:
        return None
    return -valeur if camp_alain == "noirs" else valeur


def _positions_pour_coup_interroge(context: dict) -> list:
    """Duplique délibérément app.py._positions_pour_coup_interroge (issue
    #96, même raison que les autres fonctions de cette section : jamais sur
    une instance de l'application en cours d'exécution) — construit la
    liste (label, fen) des positions pertinentes de l'exercice simulé par
    `context` (position de départ, après coup proposé/réel/meilleur, après
    les lignes déjà calculées), pour tester un coup qu'une `question`
    simulée interroge précisément (cf. construire_contexte)."""
    fen_depart = (context.get("fen_depart_exercice") or "").strip()
    if not fen_depart:
        return []
    positions = [("la position de départ de l'exercice", fen_depart)]
    vues = {fen_depart}

    def _ajoute(label: str, coup_san) -> None:
        coup_san = (coup_san or "").strip()
        if not coup_san:
            return
        try:
            board = chess.Board(fen_depart)
            board.push_san(coup_san)
        except Exception:
            return
        fen = board.fen()
        if fen in vues:
            return
        vues.add(fen)
        positions.append((label, fen))

    _ajoute("après le coup proposé par Alain", context.get("coup_propose"))
    _ajoute("après le coup réellement joué dans la partie d'origine", context.get("coup_reel"))
    _ajoute("après le meilleur coup", context.get("meilleur_coup"))

    def _ajoute_ligne(label: str, pv_text) -> None:
        pv_text = (pv_text or "").strip()
        if not pv_text:
            return
        try:
            board = chess.Board(fen_depart)
            for san in pv_text.split():
                board.push_san(san)
        except Exception:
            return
        fen = board.fen()
        if fen in vues:
            return
        vues.add(fen)
        positions.append((label, fen))

    _ajoute_ligne("après la ligne déjà calculée par Stockfish sur le coup proposé", context.get("pv_coup_propose"))
    _ajoute_ligne("après la ligne déjà calculée par Stockfish sur le meilleur coup", context.get("pv_meilleur_coup"))

    return positions


def construire_contexte(engine_manager, cas: dict) -> tuple:
    """Reconstruit EXACTEMENT le contexte envoyé au coach par app.py
    on_exercise_answer pour une « Position précise » (pas de "coup réellement
    joué à l'époque" ni d'historique d'exercice modifié, cf. isolation ci-
    dessus) — même enchaînement d'appels, même vrai Stockfish, pour le cas
    `cas` (fen/coup_propose/camp_alain).

    Retourne (messages, context, extras) — extras contient les objets
    intermédiaires nécessaires aux vérifications de faits (board_avant,
    fen_avant, fen_apres, menace_adverse_data, candidats_suites, meilleur_coup
    recalculé, texte_contexte_complet tel qu'injecté dans le system prompt).

    Si `cas["question"]` est renseignée (issue #96, optionnel) : `messages`
    devient cette question (au lieu du message initial "Commente le coup que
    je propose..."), et `context` est enrichi par "coup_interroge_texte" —
    même calcul que app.py on_coach_ask/_enrich_context_with_coup_interroge,
    pour simuler une question de suivi du chat libre portant sur un coup
    précis (ex. "et Bxh7+ ?") pendant cet exercice."""
    fen_avant = cas["fen"]
    camp_alain = cas["camp_alain"]
    board_avant = chess.Board(fen_avant)
    try:
        move = board_avant.parse_san(cas["coup_propose"])
    except ValueError as e:
        raise CasInvalideError(f"{cas['id']} : coup_propose {cas['coup_propose']!r} illégal sur fen ({e})")
    coup_propose_san = board_avant.san(move)

    eval_result = _evaluer_coup_pour_coach(engine_manager, fen_avant, move)
    board_apres = board_avant.copy()
    board_apres.push(move)
    fen_apres = board_apres.fen()
    eval_blancs_cp, eval_mat = _eval_blancs_apres(engine_manager, board_apres)
    eval_alain_cp = _vers_point_de_vue_alain(eval_blancs_cp, camp_alain)
    eval_alain_mat = _vers_point_de_vue_alain(eval_mat, camp_alain)

    meilleur_coup = eval_result["meilleur_coup"] or cas["meilleur_coup"]

    menace_adverse_data = _calculer_menace_adverse(engine_manager, fen_avant)
    menace_adverse_texte = game_facts.describe_menace_adverse(menace_adverse_data, fen_avant, camp_alain)
    pieces_depart_texte = game_facts.describe_pieces_lists(fen_avant, camp_alain)
    pieces_actuelles_texte = game_facts.describe_pieces_lists(fen_apres, camp_alain)
    materiel_resume_texte = game_facts.describe_material_summary(fen_avant, camp_alain)

    idees_coup_propose_texte = game_facts.format_idees_coup(
        "le coup proposé", _calculer_idees_coup(engine_manager, fen_avant, coup_propose_san, camp_alain, menace_adverse_data)
    )
    idees_meilleur_coup_texte = game_facts.format_idees_coup(
        "le meilleur coup selon Stockfish", _calculer_idees_coup(engine_manager, fen_avant, meilleur_coup, camp_alain, menace_adverse_data)
    )
    coup_propose_description_mecanique = game_facts.describe_move_mechanically(fen_avant, coup_propose_san, camp_alain)
    meilleur_coup_description_mecanique = (
        game_facts.describe_move_mechanically(fen_avant, meilleur_coup, camp_alain) if meilleur_coup else None
    )
    pv_coup_propose_detail = game_facts.format_pv_with_balance(
        "Détail coup par coup de la suite réellement calculée après le coup proposé",
        game_facts.describe_pv_with_balance(fen_avant, eval_result["pv_coup_propose"], camp_alain, max_plies=4),
    )
    pv_meilleur_coup_detail = game_facts.format_pv_with_balance(
        "Détail coup par coup de la suite réellement calculée pour le meilleur coup",
        game_facts.describe_pv_with_balance(fen_avant, eval_result["pv_meilleur_coup"], camp_alain, max_plies=4),
    )

    fen_apres_meilleur_coup = ""
    if meilleur_coup:
        try:
            board_meilleur = chess.Board(fen_avant)
            board_meilleur.push_san(meilleur_coup)
            fen_apres_meilleur_coup = board_meilleur.fen()
        except Exception:
            pass
    reponse_adverse_coup_propose_texte = (
        game_facts.build_reponse_adverse_obligee_texte(
            "le coup proposé", fen_apres, _calculer_reponses_adverses(engine_manager, fen_apres), camp_alain,
        ) if coup_propose_san and fen_apres != fen_avant else ""
    )
    reponse_adverse_meilleur_coup_texte = (
        game_facts.build_reponse_adverse_obligee_texte(
            "le meilleur coup", fen_apres_meilleur_coup,
            _calculer_reponses_adverses(engine_manager, fen_apres_meilleur_coup), camp_alain,
        ) if fen_apres_meilleur_coup else ""
    )

    messages = [{
        "role": "user",
        "content": (
            "Je m'entraîne sur une position précise que j'ai choisie "
            "moi-même (pas une erreur de ma part, pas un problème "
            "Lichess). Commente le coup que je propose pour cette "
            "position : est-il bon ou mauvais, et pourquoi ? Si le "
            "meilleur coup est différent, explique-le aussi. Sois "
            "concis."
        ),
    }]
    context = {
        "fen_depart_exercice": fen_avant,
        "fen": fen_apres,
        "camp_alain": camp_alain,
        "pieces_depart_texte": pieces_depart_texte,
        "pieces_actuelles_texte": pieces_actuelles_texte,
        "materiel_resume_texte": materiel_resume_texte,
        "menace_adverse_texte": menace_adverse_texte,
        "coup_propose": coup_propose_san,
        "coup_propose_description_mecanique": coup_propose_description_mecanique,
        "idees_coup_propose_texte": idees_coup_propose_texte,
        "coup_reel": "",
        "coup_reel_description_mecanique": None,
        "idees_coup_reel_texte": "",
        "meilleur_coup": meilleur_coup,
        "meilleur_coup_description_mecanique": meilleur_coup_description_mecanique,
        "idees_meilleur_coup_texte": idees_meilleur_coup_texte,
        "pv_coup_propose": eval_result["pv_coup_propose"],
        "pv_meilleur_coup": eval_result["pv_meilleur_coup"],
        "pv_coup_propose_detail": pv_coup_propose_detail,
        "pv_meilleur_coup_detail": pv_meilleur_coup_detail,
        "reponse_adverse_coup_propose_texte": reponse_adverse_coup_propose_texte,
        "reponse_adverse_meilleur_coup_texte": reponse_adverse_meilleur_coup_texte,
        "eval_alain_cp": eval_alain_cp,
        "eval_alain_mat": eval_alain_mat,
        "verdict_qualite": eval_result["verdict_qualite"],
        "verdict_delta_cp": eval_result["verdict_delta_cp"],
        "mode_exercice": True,
        "mode_origine": "exercice",
        "analyse_indisponible": eval_result["analyse_indisponible"],
    }

    # Question de suivi simulée sur un coup précis (issue #96, optionnelle) :
    # remplace le message initial "Commente le coup que je propose..." par
    # `question` elle-même (ex. "et Bxh7+ ?"), et enrichit le contexte avec
    # le même calcul que app.py on_coach_ask/_enrich_context_with_coup_
    # interroge — légalité et évaluation Stockfish du coup interrogé sur
    # chaque position pertinente de cet exercice.
    question = (cas.get("question") or "").strip()
    if question:
        positions = _positions_pour_coup_interroge(context)
        coup_interroge_texte = game_facts.build_coups_interroges_texte(
            question, positions, camp_alain,
            evaluateur=lambda fen, move: _evaluer_coup_pour_coach(engine_manager, fen, move),
        )
        if coup_interroge_texte:
            context["coup_interroge_texte"] = coup_interroge_texte
        messages = [{"role": "user", "content": question}]

    texte_contexte_complet = llm_coach._build_context_text(context)
    extras = {
        "fen_avant": fen_avant,
        "fen_apres": fen_apres,
        "board_avant": board_avant,
        "meilleur_coup_calcule": meilleur_coup,
        "menace_adverse_data": menace_adverse_data,
        "menace_adverse_texte": menace_adverse_texte,
        "texte_contexte_complet": texte_contexte_complet,
        "candidats_suites": coach_reliability._construire_candidats(
            fen_avant, fen_apres, coup_propose_san, "", meilleur_coup,
            eval_result["pv_coup_propose"], eval_result["pv_meilleur_coup"],
        ),
    }
    return messages, context, extras


# ── Vérification des faits (sans appel API) ─────────────────────────────────

def _normaliser(texte: str) -> str:
    texte = unicodedata.normalize("NFKD", texte or "")
    texte = "".join(c for c in texte if not unicodedata.combining(c))
    return texte.lower()


def _texte_contient(sous_chaine: str, texte: str) -> bool:
    return _normaliser(sous_chaine) in _normaliser(texte)


# ── Motifs attendus/interdits : alternatives, regex, négation (issue #94,
# point 6a/6b) ───────────────────────────────────────────────────────────
# Un motif de motifs_attendus/motifs_interdits (fichier .case) peut désormais
# être :
#   - une simple sous-chaîne (comportement historique, insensible à la casse
#     et aux accents, cf. _texte_contient) ;
#   - plusieurs alternatives séparées par "|" (ex. "défensif|pare la
#     menace|sécurité du roi") : présent si AU MOINS UNE des alternatives
#     est trouvée — motivé par le cas h4, où deux essais sur trois du coach
#     paraphrasent "défensif" sans jamais écrire ce mot ;
#   - un motif préfixé par "regex:" : expression régulière Python complète,
#     recherchée sur le texte BRUT (pas normalisé — l'auteur du motif gère
#     lui-même casse/accents/négation via la syntaxe regex), pour les cas où
#     la seule proximité textuelle ne suffit pas (ex. "équilibré" accolé à
#     une suite de coups précise, issue #94, point 6d).
_PREFIXE_REGEX = "regex:"


def _motif_regex(motif: str):
    """Compile `motif` en expression régulière s'il commence par "regex:",
    None sinon (motif ordinaire, cf. _motif_present ci-dessous)."""
    if motif.startswith(_PREFIXE_REGEX):
        return re.compile(motif[len(_PREFIXE_REGEX):].strip(), re.IGNORECASE | re.DOTALL)
    return None


def _motif_present(motif: str, texte: str) -> bool:
    """Présence de `motif` dans `texte` (issue #94, point 6a) — un motif
    "regex:..." est recherché tel quel sur le texte brut ; sinon, chaque
    alternative séparée par "|" est comparée en sous-chaîne (_texte_contient),
    présent si au moins une correspond."""
    pattern = _motif_regex(motif)
    if pattern is not None:
        return bool(pattern.search(texte))
    return any(_texte_contient(alt.strip(), texte) for alt in motif.split("|") if alt.strip())


# Négations reconnues à proximité immédiate d'un motif INTERDIT (issue #94,
# point 6b) — même famille de mots que coach_reliability._NEGATION_RE,
# dupliquée ici plutôt qu'importée : ce script vérifie la réponse du COACH
# dans son ensemble, pas une suite de coups précise, portée volontairement
# différente (une simple fenêtre de caractères, pas de limite à la phrase).
_NEGATION_MOTIF_RE = re.compile(r"\b(pas|jamais|aucun\w*|ni|non)\b", re.IGNORECASE)
_FENETRE_NEGATION_MOTIF = 20


def _motif_interdit_present(motif: str, texte: str) -> bool:
    """Comme _motif_present, mais tolérant à une négation proche pour un
    motif ORDINAIRE (pas "regex:", dont l'auteur garde l'entière
    responsabilité de la négation via la syntaxe regex elle-même) — issue
    #94, point 6b. Constat ayant motivé cet ajout : une réponse correcte du
    coach sur le cas h4 ("un coup défensif, pas une expansion offensive")
    contient littéralement "expansion", provoquant un échec à tort du motif
    interdit malgré la négation explicite juste avant. Chaque occurrence
    d'une alternative est ignorée si une négation apparaît dans les
    _FENETRE_NEGATION_MOTIF caractères qui la précèdent ; motif présent dès
    qu'UNE occurrence échappe à cette tolérance."""
    pattern = _motif_regex(motif)
    if pattern is not None:
        return bool(pattern.search(texte))
    texte_norm = _normaliser(texte)
    for alt in motif.split("|"):
        alt_norm = _normaliser(alt.strip())
        if not alt_norm:
            continue
        debut = 0
        while True:
            pos = texte_norm.find(alt_norm, debut)
            if pos == -1:
                break
            fenetre = texte_norm[max(0, pos - _FENETRE_NEGATION_MOTIF):pos]
            if not _NEGATION_MOTIF_RE.search(fenetre):
                return True
            debut = pos + 1
    return False


def _camp_chess(camp: str):
    return chess.WHITE if camp == "blancs" else chess.BLACK


_DIRECTIVES_CONNUES = (
    "texte_contient", "camp_sans_tour", "camp_a_une_tour",
    "aucune_piece_clouee", "menace_significative_contient", "reponse_simulee_verte",
    "reponse_simulee_signalee",
)


def _verifier_fait(directive: str, cas: dict, extras: dict) -> tuple:
    """Vérifie une ligne de `faits_attendus`. Retourne (ok: bool, libelle: str).
    Si `directive` commence par un mot-clé reconnu (_DIRECTIVES_CONNUES)
    suivi de ":", applique le contrôle correspondant ; sinon, la ligne
    entière (même si elle contient elle-même un ":") est traitée comme
    `texte_contient` — une phrase française libre peut légitimement
    contenir un ":" sans être une directive, ex. "Qxe8 : seul coup qui
    évite le mat"."""
    cle, arg = "", directive
    if ":" in directive:
        cle_candidate, _, arg_candidate = directive.partition(":")
        if cle_candidate.strip() in _DIRECTIVES_CONNUES:
            cle, arg = cle_candidate.strip(), arg_candidate.strip()

    board = extras["board_avant"]
    libelle = f"{cle or 'texte_contient'}: {arg}"

    if cle == "camp_sans_tour":
        n = len(board.pieces(chess.ROOK, _camp_chess(arg)))
        return n == 0, f"{libelle} (réel : {n} tour(s))"
    if cle == "camp_a_une_tour":
        n = len(board.pieces(chess.ROOK, _camp_chess(arg)))
        return n == 1, f"{libelle} (réel : {n} tour(s))"
    if cle == "aucune_piece_clouee":
        couleur = _camp_chess(arg)
        clouees = [
            chess.square_name(sq) for sq in chess.SQUARES
            if board.piece_at(sq) is not None
            and board.piece_at(sq).color == couleur
            and board.piece_at(sq).piece_type != chess.KING
            and board.is_pinned(couleur, sq)
        ]
        return not clouees, f"{libelle} (clouée(s) trouvée(s) : {', '.join(clouees) or 'aucune'})"
    if cle == "menace_significative_contient":
        texte = extras["menace_adverse_texte"]
        ok = _texte_contient(arg, texte) and "SIGNIFICATIVE" in texte
        return ok, f"{libelle} (menace_adverse_texte : {texte[:200]!r}...)"
    if cle == "reponse_simulee_verte":
        fiabilite = coach_reliability.evaluer_fiabilite(
            arg, extras["fen_avant"], extras["fen_apres"],
            coup_propose=cas["coup_propose"], meilleur_coup=extras["meilleur_coup_calcule"],
            camp_alain=cas["camp_alain"],
        )
        ok = fiabilite["couleur"] == "vert"
        return ok, f"{libelle} (pastille obtenue : {fiabilite['couleur']} — {fiabilite['raison']})"
    if cle == "reponse_simulee_signalee":
        # Symétrique de reponse_simulee_verte (issue #97, point 4) : vérifie
        # qu'un texte simulé DÉCLENCHE bien au moins une alerte — sert à
        # s'assurer que la tolérance des lectures multiples (coach_
        # reliability._rassembler_lectures) n'a pas affaibli un contrôle au
        # point de manquer une vraie incohérence déjà couverte.
        fiabilite = coach_reliability.evaluer_fiabilite(
            arg, extras["fen_avant"], extras["fen_apres"],
            coup_propose=cas["coup_propose"], meilleur_coup=extras["meilleur_coup_calcule"],
            camp_alain=cas["camp_alain"],
        )
        ok = bool(fiabilite["alertes"])
        return ok, f"{libelle} (pastille obtenue : {fiabilite['couleur']} — {fiabilite['raison']})"
    # Défaut : texte_contient (mot-clé explicite, ou simple ligne libre non
    # préfixée par un mot-clé connu — cf. docstring ci-dessus) : `arg` est
    # alors déjà la ligne complète.
    texte = extras["texte_contexte_complet"]
    ok = _texte_contient(arg, texte)
    return ok, f"texte_contient: {arg!r}" + ("" if ok else " (absent du contexte envoyé au coach)")


def verifier_faits(cas: dict, extras: dict) -> list:
    """Vérifie tous les faits attendus pour `cas`, plus deux contrôles
    systématiques (toujours exécutés, indépendamment de faits_attendus) :
    le coup proposé est légal (déjà garanti par construire_contexte, qui
    aurait levé CasInvalideError sinon) et le meilleur coup recalculé par le
    vrai Stockfish correspond bien au meilleur_coup attendu dans le cas —
    un désaccord ici signale soit un cas mal renseigné, soit (plus
    intéressant) un changement de comportement du moteur installé."""
    resultats = []
    meilleur_reel = extras["meilleur_coup_calcule"]
    meilleur_attendu = cas["meilleur_coup"]
    ok_meilleur = _normaliser(meilleur_reel).rstrip("+#") == _normaliser(meilleur_attendu).rstrip("+#")
    resultats.append((
        ok_meilleur,
        f"meilleur_coup_stockfish: attendu {meilleur_attendu!r}, calculé {meilleur_reel!r}",
    ))
    for directive in cas["faits_attendus"]:
        resultats.append(_verifier_fait(directive, cas, extras))
    return resultats


# ── Appel du coach et vérification de sa réponse (--api) ───────────────────

def appeler_coach(messages: list, context: dict, modele: str) -> tuple:
    """Appelle le coach EXACTEMENT comme app.py (llm_coach.get_coach_response),
    avec une mémoire de progression neutre (coach_memory={}, jamais relue
    depuis coach_memory.json) et un journal ISOLÉ (NON_REGRESSION_LOG_PATH,
    jamais coach_calls.log) — cf. isolation en en-tête de module. usage_path
    omis volontairement : ce script ne doit pas gonfler le compteur de
    tokens personnel d'Alain (usage_tokens.json)."""
    llm_config = {
        "llm_api_key": config.LLM_API_KEY,
        "llm_model": modele,
        "coach_log_path": NON_REGRESSION_LOG_PATH,
    }
    return llm_coach.get_coach_response(messages, context, {}, llm_config)


def verifier_reponse(cas: dict, response: str, fiabilite: dict) -> list:
    resultats = []
    fiabilite = fiabilite or {}
    for motif in cas["motifs_interdits"]:
        present = _motif_interdit_present(motif, response)
        resultats.append((not present, f"motif_interdit absent: {motif!r}" + ("" if not present else " — PRÉSENT")))
    # motifs_interdits_stricts (issue #98, point 2c) : vérifiés en plus sur
    # la PREMIÈRE réponse du coach si une relance automatique a eu lieu
    # (fiabilite["premiere_reponse_texte"], cf. llm_coach.get_coach_response)
    # — absent si aucune relance (pas de première réponse distincte à
    # vérifier), le motif n'est alors contrôlé que sur `response`, comme
    # motifs_interdits ci-dessus.
    premiere_texte = fiabilite.get("premiere_reponse_texte")
    textes_strict = [response] + ([premiere_texte] if premiere_texte else [])
    for motif in cas.get("motifs_interdits_stricts", []):
        present = any(_motif_interdit_present(motif, t) for t in textes_strict)
        resultats.append((not present, (
            f"motif_interdit_strict absent (y compris avant une relance éventuelle): "
            f"{motif!r}" + ("" if not present else " — PRÉSENT")
        )))
    for motif in cas["motifs_attendus"]:
        present = _motif_present(motif, response)
        resultats.append((present, f"motif_attendu présent: {motif!r}" + ("" if present else " — ABSENT")))
    attendue = cas.get("pastille_attendue", "").strip()
    if attendue:
        obtenue = fiabilite.get("couleur", "?")
        # Relance automatique JUSTIFIÉE (issue #98, point 2a) : une première
        # réponse fautive, corrigée par la relance (fiabilite["relance_
        # corrigee"] — cf. llm_coach.get_coach_response), produit une
        # pastille "orange" ("à prendre avec prudence") plutôt que "vert" —
        # compter cela comme un échec de pastille serait trompeur, le
        # mécanisme de relance a justement fonctionné comme prévu. Affiché à
        # part dans la colonne "Relances" du résumé (cf. executer_cas/main),
        # jamais comme un échec ici. Une pastille rouge, ou orange SANS
        # relance justifiée (ex. analyse indisponible), reste un échec
        # inchangé (issue #98, point 2b).
        if obtenue == attendue:
            resultats.append((True, f"pastille: {obtenue!r} (conforme)"))
        elif attendue == "vert" and obtenue == "orange" and fiabilite.get("relance_corrigee"):
            resultats.append((True, (
                f"pastille: {obtenue!r} — relance automatique corrigée "
                "(conforme, à prendre avec prudence)"
            )))
        else:
            # Couleur obtenue, sa raison et les contrôles déclenchés affichés
            # explicitement (issue #94, point 6c) — avant cet ajout, seule la
            # couleur apparaissait, obligeant à relire extrait/réponse pour
            # comprendre pourquoi la pastille différait de l'attendu.
            raison = fiabilite.get("raison", "?")
            controles = ", ".join(sorted({
                a.get("type", "?") for a in (fiabilite.get("alertes") or [])
            })) or "(aucun)"
            resultats.append((False, (
                f"pastille: attendue {attendue!r}, obtenue {obtenue!r} — "
                f"raison : {raison} — contrôles déclenchés : {controles}"
            )))
    return resultats


# ── Exécution d'un cas et agrégation ────────────────────────────────────────

def executer_cas(engine_manager, cas: dict, repetitions: int, api_active: bool, modele: str, verbose: bool) -> dict:
    resultat = {"id": cas["id"], "echecs_faits": [], "tentatives": [], "erreur": None}
    try:
        messages, context, extras = construire_contexte(engine_manager, cas)
    except CasInvalideError as e:
        resultat["erreur"] = str(e)
        return resultat

    faits = verifier_faits(cas, extras)
    resultat["echecs_faits"] = [libelle for ok, libelle in faits if not ok]

    if not api_active or resultat["echecs_faits"]:
        return resultat

    for i in range(repetitions):
        response, error, fiabilite, _log_id = appeler_coach(messages, context, modele)
        if error:
            resultat["tentatives"].append({"ok": False, "motifs": [f"erreur_api: {error}"], "extrait": ""})
            continue
        controles = verifier_reponse(cas, response, fiabilite)
        echecs = [libelle for ok, libelle in controles if not ok]
        resultat["tentatives"].append({
            "ok": not echecs,
            "motifs": echecs,
            "extrait": response[:300],
            # relance_corrigee (issue #98, point 2a) : une première réponse
            # fautive corrigée par la relance automatique de fiabilité (cf.
            # llm_coach.get_coach_response) — affiché à part dans la colonne
            # "Relances" du résumé (cf. main), jamais confondu avec un échec.
            "relance_corrigee": bool((fiabilite or {}).get("relance_corrigee")),
        })
        if verbose and echecs:
            print(f"  [essai {i + 1}/{repetitions}] échec(s) : {', '.join(echecs)}")
            print(f"    réponse complète : {response}")
    return resultat


# ── Création d'un squelette de cas depuis un signalement ───────────────────

def creer_cas_depuis_signalement(id_signalement: str, nouvel_id: str, signalements_path: Path) -> Path:
    if not signalements_path.exists():
        raise CasInvalideError(f"Fichier de signalements introuvable : {signalements_path}")
    entree = None
    with open(signalements_path, "r", encoding="utf-8") as f:
        for ligne in f:
            ligne = ligne.strip()
            if not ligne:
                continue
            try:
                e = json.loads(ligne)
            except (ValueError, TypeError):
                continue
            if e.get("id") == id_signalement:
                entree = e
                break
    if entree is None:
        raise CasInvalideError(f"Signalement introuvable : {id_signalement} (dans {signalements_path})")

    cible = CAS_DIR / f"{nouvel_id}.case"
    if cible.exists():
        raise CasInvalideError(f"Le fichier {cible} existe déjà — choisissez un autre --nouvel-id.")

    fen = (entree.get("fen") or "").strip()
    camp_alain = ""
    try:
        camp_alain = "blancs" if chess.Board(fen).turn == chess.WHITE else "noirs"
    except Exception:
        pass

    # Attention (issue #93) : le parseur de cas (parser_cas) ne reconnaît que
    # des lignes de COMMENTAIRE ENTIÈRES ("#..." en début de ligne) — jamais
    # un commentaire en fin de ligne après une valeur, qui serait sinon
    # inclus tel quel dans la valeur (et un "#" en fin de ligne serait de
    # toute façon ambigu avec la notation d'échec et mat, ex. "Qxe8#"). Ce
    # squelette ne place donc JAMAIS de commentaire sur la même ligne qu'une
    # valeur : chaque remarque est une ligne "#" séparée, au-dessus.
    reponse_fautive = (entree.get("reponse") or "").replace("\n", "\n#   ")
    contenu = f"""# Squelette généré automatiquement depuis le signalement {id_signalement}
# ({entree.get('horodatage', '?')}, mode {entree.get('mode_origine', '?')}).
#
# Réponse fautive du coach, pour choisir les motifs_interdits/motifs_attendus
# ci-dessous (reproduite ici en commentaire, à relire puis à supprimer une
# fois le cas complété) :
#   {reponse_fautive}
#
# Commentaire d'Alain au moment du signalement : {entree.get('commentaire') or '(aucun)'}
id: {nouvel_id}
# À COMPLÉTER — en une phrase, ce que le coach a dit de faux
description: (à compléter)
source: signalement {id_signalement} du {entree.get('horodatage', '?')}
fen: {fen}
# camp_alain deviné depuis le trait du FEN — à vérifier avant de lancer le cas
camp_alain: {camp_alain}
# coup_propose à compléter ci-dessous si le signalement ne l'avait pas transmis
coup_propose: {entree.get('move') or '(à compléter)'}
# meilleur_coup : à compléter avec le vrai meilleur coup Stockfish attendu
meilleur_coup: (à compléter)

faits_attendus:
  # texte_contient: ...   (sous-chaîne attendue dans le contexte envoyé au coach)

motifs_interdits:
  # ...   (un des mots/phrases fautifs de la réponse ci-dessus en commentaire)

motifs_attendus:
  # ...

pastille_attendue: vert
"""
    cible.write_text(contenu, encoding="utf-8")
    return cible


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Non-régression du coach ChessCoach (issue #93) : rejoue des positions où le coach s'est trompé."
    )
    parser.add_argument("--cas", nargs="+", metavar="ID", help="Identifiant(s) de cas à rejouer (défaut : tous).")
    parser.add_argument("--repetitions", type=int, default=3, help="Nombre d'appels API par cas (défaut 3).")
    parser.add_argument("--api", action="store_true", help="Appelle réellement le coach (Claude) — désactivé par défaut.")
    parser.add_argument("--modele", choices=("sonnet", "haiku"), default=None,
                         help="Modèle Claude à utiliser avec --api (défaut : modèle actif de l'application, config.LLM_MODEL).")
    parser.add_argument("--verbose", action="store_true", help="Affiche le détail des réponses fautives.")
    parser.add_argument("--depuis-signalement", metavar="ID", help="Crée un squelette de cas depuis ce signalement (lecture seule).")
    parser.add_argument("--nouvel-id", metavar="ID", help="Identifiant du nouveau cas (avec --depuis-signalement).")
    parser.add_argument("--signalements-path", metavar="PATH", default=None,
                         help="Fichier de signalements à utiliser (défaut : config.SIGNALEMENTS_LOG_PATH).")
    args = parser.parse_args()

    if args.depuis_signalement:
        if not args.nouvel_id:
            parser.error("--depuis-signalement nécessite --nouvel-id")
        chemin_signalements = Path(args.signalements_path) if args.signalements_path else Path(config.SIGNALEMENTS_LOG_PATH)
        try:
            cible = creer_cas_depuis_signalement(args.depuis_signalement, args.nouvel_id, chemin_signalements)
        except CasInvalideError as e:
            print(f"Erreur : {e}", file=sys.stderr)
            return 1
        print(f"Squelette créé : {cible}")
        print("Complétez les champs marqués « À COMPLÉTER », choisissez les motifs à partir "
              "de la réponse fautive citée en commentaire, puis supprimez ce commentaire.")
        return 0

    try:
        cas_liste = charger_cas(args.cas)
    except CasInvalideError as e:
        print(f"Erreur : {e}", file=sys.stderr)
        return 1

    if not cas_liste:
        print("Aucun cas à exécuter.", file=sys.stderr)
        return 1

    modele = None
    if args.api:
        modele = {"sonnet": config.LLM_MODEL_SONNET, "haiku": config.LLM_MODEL_HAIKU}.get(args.modele, config.LLM_MODEL)
        if not config.LLM_API_KEY:
            print("Erreur : --api demandé mais ANTHROPIC_API_KEY est absent de l'environnement.", file=sys.stderr)
            return 1
        print(f"Estimation : {len(cas_liste)} cas x {args.repetitions} répétition(s) = "
              f"{len(cas_liste) * args.repetitions} appel(s) API (modèle {modele}).")

    stockfish_path = find_stockfish()
    if not stockfish_path:
        print("Erreur : Stockfish introuvable sur ce système.", file=sys.stderr)
        return 1
    engine_manager = EngineManager(stockfish_path)

    try:
        resultats = []
        for cas in cas_liste:
            print(f"Cas {cas['id']}...")
            resultats.append(executer_cas(engine_manager, cas, args.repetitions, args.api, modele, args.verbose))
    finally:
        engine_manager.quit()

    # ── Résumé ───────────────────────────────────────────────────────────
    # Colonne "Relances" (issue #98, point 2a) : nombre d'essais réussis
    # GRÂCE à une relance automatique de fiabilité justifiée (première
    # réponse fautive, corrigée — cf. verifier_reponse/executer_cas),
    # affiché séparément de "API réussites" plutôt que noyé dans ce taux —
    # un essai "1/5 relance(s) corrigée(s)" reste un essai RÉUSSI (compté
    # dans n_ok ci-dessous), pas un échec de pastille.
    echec_global = False
    print("\n" + "=" * 94)
    print(f"{'Cas':<28} {'Faits':<8} {'API réussites':<16} {'Relances':<22} Détail")
    print("=" * 94)
    for r in resultats:
        if r["erreur"]:
            echec_global = True
            print(f"{r['id']:<28} {'ERREUR':<8} {'':<16} {'':<22} {r['erreur']}")
            continue
        faits_ok = not r["echecs_faits"]
        if not faits_ok:
            echec_global = True
        detail_parts = list(r["echecs_faits"])
        relances_txt = ""
        if args.api and faits_ok:
            n_ok = sum(1 for t in r["tentatives"] if t["ok"])
            n_total = len(r["tentatives"])
            n_relances = sum(1 for t in r["tentatives"] if t.get("relance_corrigee"))
            if n_relances:
                relances_txt = f"{n_relances}/{n_total} relance(s) corrigée(s)"
            if n_ok < n_total:
                echec_global = True
                # Motifs d'échec API distincts affichés directement dans le
                # tableau récapitulatif (issue #94, point 6c), pas seulement
                # dans le détail par tentative imprimé après le tableau —
                # couleur obtenue, raison et contrôles déclenchés compris
                # pour un échec de pastille (cf. verifier_reponse).
                motifs_api = sorted({
                    motif for t in r["tentatives"] if not t["ok"] for motif in t["motifs"]
                })
                detail_parts.extend(motifs_api)
            api_txt = f"{n_ok}/{n_total}"
        else:
            api_txt = "(non testé)" if not args.api else "—"
        detail = "; ".join(detail_parts)
        print(f"{r['id']:<28} {'OK' if faits_ok else 'KO':<8} {api_txt:<16} {relances_txt:<22} {detail}")
    print("=" * 94)

    if args.api:
        for r in resultats:
            for i, t in enumerate(r.get("tentatives", []), start=1):
                if not t["ok"]:
                    print(f"\nÉCHEC {r['id']} (essai {i}) : {', '.join(t['motifs'])}")
                    print(f"  Extrait de la réponse : {t['extrait']!r}")

    return 1 if echec_global else 0


if __name__ == "__main__":
    sys.exit(main())
