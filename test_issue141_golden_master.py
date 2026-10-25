"""
test_issue141_golden_master.py — ChessCoach (issue #141, suite #140)

Golden master : capture le contexte exact transmis à chaque IA (Claude et
Mistral) et les événements émis vers le navigateur, pour un ensemble de cas
couvrant les deux sources (« mes erreurs »/« Position précise » et
« Problèmes Lichess »), les deux camps, un coup « bon », une gaffe, un coup
qui est le meilleur coup, une position avec mat, et le mode série activé et
désactivé — exécuté via le VRAI gestionnaire (app.on_exercise_answer /
app._on_exercise_answer_lichess), le client de test Flask-SocketIO et
l'infrastructure d'isolation de test_issue128.py (chemins de données
redirigés vers un dossier temporaire, aucun fichier personnel d'Alain lu ni
écrit). API Claude/Mistral simulées au niveau le plus bas possible
(llm_coach._call_claude/_call_mistral, comme test_issue140_mode_serie_ia_
arriere_plan.py) : get_coach_response/get_mistral_response s'exécutent
réellement de bout en bout (vérificateur de fiabilité, vérificateur
d'affirmations factuelles, écriture au journal), pour que le golden master
couvre aussi ces calculs en aval du contexte — jamais d'appel réseau réel.

Référence committée : golden_master_issue141.json — écrite/régénérée par
generer_golden_master_issue141.py (hors suite de tests, exécuté à la main
pour établir ou mettre à jour la référence — jamais par ce fichier de test
lui-même).

Positions : des finales éparses (peu de pièces) choisies pour que Stockfish
y réponde vite à DEPTH_EXERCICE_TEMPS_REEL (18) tout en produisant des
verdicts déterministes — une position de départ avec de nombreuses pièces
(ouverture standard) multiplie le nombre de coups légaux examinés par
l'évaluation "always_return_best" et ralentit chaque cas de façon non
négligeable (constaté en explorant les positions candidates pour cette
issue).

Issue #141, vérification (d) : aucun test de ce fichier n'est ignoré,
désactivé ou conditionné par une variable d'environnement — Stockfish
absent de la machine fait ÉCHOUER setUpClass (RuntimeError), il n'est
jamais sauté.

Ce fichier importe app.py comme test_issue128.py/test_issue134.py/
test_issue135.py/test_issue137_signe_eval_lichess.py/
test_issue139_mode_serie.py/test_issue140_mode_serie_ia_arriere_plan.py :
ne JAMAIS l'exécuter dans le même process que l'un de ces fichiers (même
contrainte, voir leurs en-têtes) — invoquer séparément :
    python3 -m unittest test_issue141_golden_master
"""

import importlib
import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from engine_stockfish import find_stockfish
from test_issue128 import _patch_config_paths_vers_tmp, _restaure_config_paths


# =============================================================================
# Positions et coups déterministes (finales éparses, recherche rapide).
# =============================================================================

FEN_GAFFE_BLANCS = "4k3/8/2n5/8/3Q4/8/8/4K3 w - - 0 1"
UCI_GAFFE_BLANCS = "e1d1"        # Roi e1-d1 : ignore la Dame en prise (gaffe).
UCI_MEILLEUR_BLANCS = "d4e4"     # Qe4+ : sauve la Dame en donnant échec (meilleur coup).
UCI_BON_BLANCS = "d4g7"          # Qg7 : un des coups également "bon" (delta 0).

FEN_GAFFE_NOIRS = "4k3/8/8/3q4/8/2N5/8/4K3 b - - 0 1"
UCI_GAFFE_NOIRS = "e8d8"         # Roi e8-d8 : ignore la Dame en prise (gaffe).
UCI_BON_NOIRS = "d5d6"           # Qd6 : coup "bon" qui sauve la Dame.

FEN_MAT_BLANCS = "6k1/5ppp/8/8/8/8/8/R6K w - - 0 1"
UCI_MAT_BLANCS = "a1a8"          # Ra8# : mat sur la 8e rangée (pions noirs bloquent la fuite).

FEN_MAT_NOIRS = "r6k/8/8/8/8/8/5PPP/6K1 b - - 0 1"
UCI_MAT_NOIRS = "a8a1"           # Ra1# : mat sur la 1re rangée (pions blancs bloquent la fuite).


def _exercice_mes_erreurs(fen_avant, camp_alain, coup_joue_uci="", meilleur_coup_uci=""):
    return {
        "source": "mes_erreurs", "fen_avant": fen_avant, "camp_alain": camp_alain,
        "coup_joue_san": "", "coup_joue_uci": coup_joue_uci,
        "meilleur_coup_san": "", "meilleur_coup_uci": meilleur_coup_uci,
    }


def _exercice_position_precise(fen_avant, camp_alain):
    return {
        "source": "position_precise", "fen_avant": fen_avant, "camp_alain": camp_alain,
        "phase": "toutes", "sous_type": None,
    }


def _exercice_lichess(fen_avant, camp_alain, solution_uci, categorie="mat_en_1", cle="lichess:golden"):
    return {
        "source": "lichess", "fen_avant": fen_avant, "camp_alain": camp_alain,
        "solution": [solution_uci], "categorie_tirage": categorie,
        "cle_historique": cle, "niveau_tirage": 1000, "rating": 1000, "themes": ["mateIn1"],
    }


# 14 cas : couvre les deux sources, les deux camps, bon/gaffe/meilleur coup/
# mat, et le mode série activé/désactivé (issue #141, tâche 1).
CASES = [
    {"label": "me_blancs_bon", "exercice": _exercice_mes_erreurs(
        FEN_GAFFE_BLANCS, "blancs", meilleur_coup_uci=UCI_MEILLEUR_BLANCS),
        "uci": UCI_BON_BLANCS, "mode_serie": False},
    {"label": "me_noirs_bon", "exercice": _exercice_mes_erreurs(FEN_GAFFE_NOIRS, "noirs"),
        "uci": UCI_BON_NOIRS, "mode_serie": False},
    {"label": "me_blancs_gaffe", "exercice": _exercice_mes_erreurs(FEN_GAFFE_BLANCS, "blancs"),
        "uci": UCI_GAFFE_BLANCS, "mode_serie": False},
    {"label": "me_noirs_gaffe", "exercice": _exercice_mes_erreurs(FEN_GAFFE_NOIRS, "noirs"),
        "uci": UCI_GAFFE_NOIRS, "mode_serie": False},
    {"label": "me_blancs_meilleur_coup", "exercice": _exercice_mes_erreurs(FEN_GAFFE_BLANCS, "blancs"),
        "uci": UCI_MEILLEUR_BLANCS, "mode_serie": False},
    {"label": "me_blancs_mat", "exercice": _exercice_mes_erreurs(FEN_MAT_BLANCS, "blancs"),
        "uci": UCI_MAT_BLANCS, "mode_serie": False},
    {"label": "me_noirs_mat", "exercice": _exercice_mes_erreurs(FEN_MAT_NOIRS, "noirs"),
        "uci": UCI_MAT_NOIRS, "mode_serie": False},
    {"label": "position_precise_blancs_bon", "exercice": _exercice_position_precise(FEN_GAFFE_BLANCS, "blancs"),
        "uci": UCI_BON_BLANCS, "mode_serie": False},
    {"label": "me_blancs_gaffe_mode_serie", "exercice": _exercice_mes_erreurs(FEN_GAFFE_BLANCS, "blancs"),
        "uci": UCI_GAFFE_BLANCS, "mode_serie": True},
    {"label": "me_noirs_bon_mode_serie", "exercice": _exercice_mes_erreurs(FEN_GAFFE_NOIRS, "noirs"),
        "uci": UCI_BON_NOIRS, "mode_serie": True},
    {"label": "lichess_blancs_bon", "exercice": _exercice_lichess(FEN_GAFFE_BLANCS, "blancs", UCI_MEILLEUR_BLANCS),
        "uci": UCI_MEILLEUR_BLANCS, "mode_serie": False},
    {"label": "lichess_noirs_bon", "exercice": _exercice_lichess(FEN_GAFFE_NOIRS, "noirs", UCI_BON_NOIRS),
        "uci": UCI_BON_NOIRS, "mode_serie": False},
    {"label": "lichess_blancs_gaffe", "exercice": _exercice_lichess(FEN_GAFFE_BLANCS, "blancs", UCI_MEILLEUR_BLANCS),
        "uci": UCI_GAFFE_BLANCS, "mode_serie": False},
    {"label": "lichess_blancs_mat", "exercice": _exercice_lichess(FEN_MAT_BLANCS, "blancs", UCI_MAT_BLANCS),
        "uci": UCI_MAT_BLANCS, "mode_serie": False},
    {"label": "lichess_blancs_gaffe_mode_serie", "exercice": _exercice_lichess(
        FEN_GAFFE_BLANCS, "blancs", UCI_MEILLEUR_BLANCS), "uci": UCI_GAFFE_BLANCS, "mode_serie": True},
]


# =============================================================================
# Simulations des IA (jamais d'appel réseau réel) et nettoyage des champs
# volatils (identifiants, horodatages, informations de version git) avant
# comparaison.
# =============================================================================

def _fausse_reponse_claude(prompt_sys, messages, api_key, model, usage_path=None,
                            timeout_s=90, temperature=None):
    return "Réponse simulée du coach (Claude) pour le golden master issue #141."


def _fausse_reponse_mistral(prompt_sys, messages, api_key, model, usage_path=None,
                             timeout_s=90, temperature=None):
    return "Réponse simulée du coach (Mistral) pour le golden master issue #141.", None


# Champs volatils (changent à chaque exécution, ou dépendent de l'état git
# courant) : exclus de la comparaison (issue #141, tâche 1). date_debut/
# dernier_appel (évènement usage_data) : horodatages de compteur global,
# jamais identiques entre deux exécutions — vérifié déterministe par
# ailleurs (tous les autres champs de cet évènement, à zéro puisque les IA
# simulées ne rapportent aucun usage, sont identiques d'une exécution à
# l'autre).
_CLES_VOLATILES = {"log_id", "id", "horodatage", "version_info", "date_debut", "dernier_appel"}


def _nettoyer(obj):
    if isinstance(obj, dict):
        return {k: _nettoyer(v) for k, v in obj.items() if k not in _CLES_VOLATILES}
    if isinstance(obj, list):
        return [_nettoyer(v) for v in obj]
    return obj


def _cle_triable(valeur) -> str:
    return json.dumps(valeur, ensure_ascii=False, sort_keys=True)


def _canoniser_listes_racees(resultat_cas: dict) -> dict:
    """Tolérance EXPLICITE (issue #141, tâche 1) : "appels_ia", "evenements"
    et "journal" proviennent de deux threads indépendants quand Mistral est
    actif (l'appel Claude synchrone et l'appel Mistral en arrière-plan,
    issue #113 ; ou les deux en arrière-plan en mode série, issue #140) —
    leur ORDRE D'ARRIVÉE n'est pas déterministe. Vérifié en capturant deux
    fois le code D'ORIGINE (avant toute modification) : les deux captures
    ne diffèrent JAMAIS par le contenu, seulement par cet ordre. Trier ces
    trois listes dans un ordre canonique (sérialisation JSON triée) avant
    comparaison neutralise cette course sans masquer un vrai changement de
    contenu."""
    resultat = dict(resultat_cas)
    for cle in ("appels_ia", "evenements", "journal"):
        resultat[cle] = sorted(resultat[cle], key=_cle_triable)
    return resultat


class _CaptureGoldenMaster:
    """Pilote le VRAI gestionnaire pour chaque cas de CASES, capture le
    contexte transmis à chaque IA et les évènements émis — utilisé à la fois
    par generer_golden_master_issue141.py (écriture de la référence) et par
    TestGoldenMasterIssue141 (comparaison à la référence committée)."""

    def __init__(self, app_module, client):
        self.app_module = app_module
        self.client = client
        self._verrou = threading.Lock()

    def _patch_ia_reseau(self):
        p1 = patch.object(self.app_module.llm_coach, "_call_claude", side_effect=_fausse_reponse_claude)
        p2 = patch.object(self.app_module.llm_coach, "_call_mistral", side_effect=_fausse_reponse_mistral)
        p1.start()
        p2.start()
        return [p1, p2]

    def _instrumenter_appels_ia(self):
        """Capture (messages, context) de chaque appel à get_coach_response/
        get_mistral_response SANS remplacer leur exécution réelle (spy qui
        appelle la fonction d'origine) : le vérificateur de fiabilité, le
        vérificateur d'affirmations factuelles et l'écriture au journal
        continuent de s'exécuter normalement."""
        appels = []
        original_coach = self.app_module.llm_coach.get_coach_response
        original_mistral = self.app_module.llm_coach.get_mistral_response

        def spy_coach(messages, context, coach_memory, cfg):
            resultat = original_coach(messages, context, coach_memory, cfg)
            with self._verrou:
                appels.append({"agent": "claude", "messages": messages, "context": context})
            return resultat

        def spy_mistral(messages, context, cfg):
            resultat = original_mistral(messages, context, cfg)
            with self._verrou:
                appels.append({"agent": "mistral", "messages": messages, "context": context})
            return resultat

        p1 = patch.object(self.app_module.llm_coach, "get_coach_response", side_effect=spy_coach)
        p2 = patch.object(self.app_module.llm_coach, "get_mistral_response", side_effect=spy_mistral)
        p1.start()
        p2.start()
        return appels, [p1, p2]

    def _attendre_compteur_serie_zero(self, timeout: float = 20.0) -> None:
        deadline = time.monotonic() + timeout
        n = None
        while time.monotonic() < deadline:
            with self.app_module._mode_serie_lock:
                n = self.app_module._mode_serie_avis_en_cours
            if n == 0:
                return
            time.sleep(0.02)
        raise AssertionError(f"compteur 'avis en cours' du mode série non revenu à 0 sous {timeout}s (reste {n})")

    def _lire_journal(self) -> list:
        chemin = self.app_module.llm_coach._coach_log_fichier_actif(
            self.app_module.config.COACH_CALLS_LOG_PATH
        )
        if not chemin.exists():
            return []
        return [
            json.loads(ligne) for ligne in chemin.read_text(encoding="utf-8").splitlines()
            if ligne.strip()
        ]

    def capturer_un_cas(self, cas: dict) -> dict:
        self.client.get_received()
        self.app_module._current_exercise = dict(cas["exercice"])

        appels, patchers_spy = self._instrumenter_appels_ia()
        avant_journal = len(self._lire_journal())
        try:
            self.client.emit("exercise_answer", {
                "uci": cas["uci"], "exercise_id": f"golden-{cas['label']}",
                "mode_serie": cas["mode_serie"],
            })
            recus = self.client.get_received()
            if cas["mode_serie"]:
                self._attendre_compteur_serie_zero()
                recus += self.client.get_received()
            else:
                # Mistral (source "mes_erreurs"/"position_precise" avec
                # MISTRAL_API_KEY actif, issue #113) part dans un thread
                # séparé du mode normal — attendre son évènement avec une
                # limite de temps explicite plutôt qu'un sleep fixe fragile.
                attendu = 2 if cas["exercice"].get("source") != "lichess" else 1
                deadline = time.monotonic() + 15.0
                while len(appels) < attendu and time.monotonic() < deadline:
                    time.sleep(0.02)
                recus += self.client.get_received()
        finally:
            for p in patchers_spy:
                p.stop()
        nouvelles_entrees_journal = self._lire_journal()[avant_journal:]

        return _canoniser_listes_racees(_nettoyer({
            "label": cas["label"],
            "appels_ia": appels,
            "evenements": [{"name": e["name"], "args": e["args"]} for e in recus],
            "journal": nouvelles_entrees_journal,
        }))


def capturer_golden_master(app_module, client) -> list:
    """Active Mistral (issue #140 : jamais appelé pour la source "lichess",
    configuration inchangée — l'activer globalement ici ne change donc rien
    pour ces cas-là) et exécute tous les CASES dans l'ordre."""
    ancienne_mistral = app_module.config.MISTRAL_API_KEY
    app_module.config.MISTRAL_API_KEY = "fake-golden-master-key-issue141"
    cg = _CaptureGoldenMaster(app_module, client)
    patchers_reseau = cg._patch_ia_reseau()
    try:
        return [cg.capturer_un_cas(cas) for cas in CASES]
    finally:
        for p in patchers_reseau:
            p.stop()
        app_module.config.MISTRAL_API_KEY = ancienne_mistral


REFERENCE_PATH = Path(__file__).parent / "golden_master_issue141.json"


class TestGoldenMasterIssue141(unittest.TestCase):
    """Compare une capture fraîche (VRAI gestionnaire) à la référence
    committée golden_master_issue141.json — zéro différence attendue après
    la refactorisation de l'issue #141 (extraction de la construction du
    contexte coach), hors champs volatils déjà exclus par _nettoyer."""

    @classmethod
    def setUpClass(cls):
        # Issue #141, vérification (d) : une dépendance manquante (ici
        # Stockfish) fait ÉCHOUER ce test, jamais le sauter.
        if not find_stockfish():
            raise RuntimeError(
                "Stockfish introuvable sur cette machine : ce test doit "
                "échouer plutôt que d'être sauté (issue #141, vérification d)."
            )

        cls._tmp = tempfile.TemporaryDirectory()
        tmp_dir = Path(cls._tmp.name)

        import config as config_module
        cls._config_module = config_module
        cls._anciens_config = _patch_config_paths_vers_tmp(config_module, tmp_dir)

        if "app" in sys.modules:
            raise RuntimeError(
                "app.py était déjà importé avant ce test : l'isolation des "
                "chemins de données ne peut plus être garantie (même "
                "contrainte que test_issue128.py — ne jamais exécuter ces "
                "fichiers dans le même process)."
            )
        cls.app_module = importlib.import_module("app")
        cls.client = cls.app_module.socketio.test_client(cls.app_module.app)

    @classmethod
    def tearDownClass(cls):
        _restaure_config_paths(cls._config_module, cls._anciens_config)
        cls._tmp.cleanup()

    def test_contexte_et_evenements_identiques_au_golden_master(self):
        if not REFERENCE_PATH.exists():
            self.fail(
                f"Référence absente : {REFERENCE_PATH} — générer avec "
                "generer_golden_master_issue141.py avant d'exécuter ce test."
            )
        reference = json.loads(REFERENCE_PATH.read_text(encoding="utf-8"))
        resultats = capturer_golden_master(self.app_module, self.client)

        self.assertEqual(
            [c["label"] for c in resultats], [c["label"] for c in reference],
            "liste de cas différente de la référence",
        )
        for actuel, attendu in zip(resultats, reference):
            self.assertEqual(
                actuel, attendu,
                f"différence détectée pour le cas « {actuel['label']} » par rapport au golden master",
            )


if __name__ == "__main__":
    unittest.main()
