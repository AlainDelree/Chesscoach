"""
test_issue137_signe_eval_lichess.py — ChessCoach (issue #137, suite #128)

Depuis l'issue #128 (précisée par #134), toutes les évaluations transmises
aux IA et au journal suivent la convention de Lichess (+ = avantage Blancs,
− = avantage Noirs), SANS conversion vers le camp d'Alain. Les tests
existants pour le chemin « Problèmes Lichess » (test_issue128.py) portent des
noms du type « eval_negative »/« eval_positive » mais ne vérifient JAMAIS
réellement le signe d'une évaluation chiffrée — une inversion de signe
passerait inaperçue :

  - test_problemes_lichess_exercice_noir_eval_negative (test_issue128.py) :
    vérifie seulement l'absence de « pour toi »/« pour Alain » dans le
    contexte dynamique du prompt et la réception d'un exercise_comment —
    AUCUNE extraction ni comparaison de signe numérique.
  - test_problemes_lichess_exercice_blanc_eval_positive (test_issue128.py) :
    même chose, toujours aucune vérification de signe malgré le nom.

(Par contraste, les tests équivalents côté « Mes erreurs » dans le même
fichier — test_mes_erreurs_exercice_noir_eval_negative_et_pas_pour_qui/
test_mes_erreurs_exercice_blanc_eval_positive — extraient bien le chiffre par
regex et vérifient son signe : eux ne sont pas trompeurs.)

Ce fichier ajoute des cas qui ÉCHOUENT si le signe de eval_blancs_cp/
eval_blancs_mat est inversé, pour le VRAI gestionnaire de réponse de
« Problèmes Lichess » (app._on_exercise_answer_lichess), via le client de
test Flask-SocketIO et l'infrastructure de test_issue128.py (chemins de
données temporaires, API Claude simulée). Aucune donnée réelle de data/
n'est lue ni modifiée. Aucun test n'est ignoré/sauté : si Stockfish ou
app.engine_manager est indisponible, setUpClass lève une erreur réelle
(jamais unittest.SkipTest).

Précision technique (le libellé "la conversion se fait une seule fois à la
source engine_stockfish.evaluate_move" de l'en-tête d'issue #137 décrit le
chemin « Mes erreurs », pas « Problèmes Lichess ») : pour LE CHEMIN
« Problèmes Lichess » spécifiquement, eval_blancs_cp/eval_blancs_mat du
contexte proviennent de app._eval_blancs_apres (appelée sur le plateau
APRÈS le coup d'Alain), qui calcule elle-même son propre signe (sign = 1 si
Blancs au trait sinon -1) via un appel direct à EngineManager.evaluate —
PAS via EngineManager.evaluate_move. C'est bien ce que documente déjà
docs/contexte/convention_signe.md (deux mécanismes distincts : evaluate_move
pour eval_before_cp/eval_after_cp côté « Mes erreurs », _eval_blancs_apres
pour eval_blancs_cp/eval_blancs_mat), donc aucune incohérence de doc — mais
cela veut dire que le contrôle par inversion (tâche 6 de l'issue #137),
pour couvrir réellement ce que ces tests exercent, doit inverser le signe
dans app._eval_blancs_apres et non dans evaluate_move (voir rapport de
clôture). Les champs eval_before_cp/eval_after_cp ne sont même pas inclus
dans le contexte envoyé pour « Problèmes Lichess » (seulement pour « Mes
erreurs »).
"""

import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import chess

from engine_stockfish import find_stockfish
from test_issue128 import _patch_config_paths_vers_tmp, _restaure_config_paths


# FEN/coup génériques (position de départ, un seul coup simple) pour les cas
# à valeur fixe simulée (eval_blancs_cp/eval_blancs_mat n'est pas recalculé
# normalement par le vrai moteur dans ces cas : seul l'appel EngineManager.
# evaluate(depth=8) utilisé par app._eval_blancs_apres est intercepté — le
# verdict/la PV restent calculés par le VRAI Stockfish via evaluate_move,
# profondeur DEPTH_EXERCICE_TEMPS_REEL, jamais simulés).
FEN_NOIR_GENERIQUE = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
UCI_NOIR_GENERIQUE = "e7e5"
FEN_BLANC_GENERIQUE = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
UCI_BLANC_GENERIQUE = "e2e4"

# FEN de bascule (signes opposés avant/après) : Alain blundere une dame en
# prise — avant le coup, le camp d'Alain est massivement en avance (dame
# contre tour/rien) ; après son coup, la dame est prenable gratuitement et le
# camp adverse devient massivement en avance. Positions fixes et volontai-
# rement simples (peu de pièces) pour que le VRAI moteur (profondeur 8 au
# minimum) voie la capture immédiatement, sans aléa de recherche.
FEN_NOIR_BASCULE = "4k3/8/8/8/3q4/8/8/R3K3 b - - 0 1"
UCI_NOIR_BASCULE = "d4d1"  # Dxd1+?? — la tour a1 reprend la dame (Rxd1).
FEN_BLANC_BASCULE = "r3k3/8/8/8/8/8/8/3QK3 w - - 0 1"
UCI_BLANC_BASCULE = "d1a1"  # Qa1?? — la tour a8 reprend la dame (Rxa1).

# FEN à grand avantage matériel évident (dame manquante d'un côté), pour le
# VRAI moteur sans aucune simulation — tâche 2 de l'issue #137 : "pour le
# vrai moteur des positions où le camp gagnant est évident".
FEN_NOIR_AVANTAGE_EVIDENT = "rnb1kbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR b - - 0 1"
FEN_BLANC_AVANTAGE_EVIDENT = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNB1KBNR w - - 0 1"


class TestSigneEvalProblemesLichess(unittest.TestCase):
    """Fait tourner le VRAI app._on_exercise_answer_lichess via le client de
    test Flask-SocketIO (même infrastructure que test_issue128.py,
    TestExerciseAnswerSocketIO) et vérifie le SIGNE réel de eval_blancs_cp/
    eval_blancs_mat transmis au contexte de l'IA (simulée) et enregistré tel
    quel dans coach_calls.log — jamais seulement l'absence de "pour toi"/
    "pour Alain" comme le font (à tort, malgré leur nom) les tests existants
    cités dans le docstring du module."""

    @classmethod
    def setUpClass(cls):
        chemin_stockfish = find_stockfish()
        if not chemin_stockfish:
            # JAMAIS unittest.SkipTest ici (issue #137, tâche 5) : sans
            # Stockfish, le signe des évaluations ne peut pas être vérifié
            # en conditions réelles — le test doit échouer bruyamment.
            raise RuntimeError(
                "Stockfish introuvable sur cette machine : ce test DOIT "
                "échouer (jamais être sauté, issue #137) tant que le signe "
                "des évaluations transmises au coach n'a pas pu être "
                "vérifié avec un vrai moteur."
            )

        cls._tmp = tempfile.TemporaryDirectory()
        cls._tmp_dir = Path(cls._tmp.name)

        import config as config_module
        cls._config_module = config_module
        cls._anciens_config = _patch_config_paths_vers_tmp(config_module, cls._tmp_dir)

        # Contrairement au garde-fou de test_issue128.py (qui refuse un
        # second import d'app.py dans le même processus), ce fichier doit
        # pouvoir cohabiter avec test_issue128.py s'ils tournent dans le
        # même processus de test : on réutilise le module déjà importé s'il
        # existe. Le repatch des chemins config.* ci-dessus reste suffisant
        # pour l'isolation, puisqu'app.py relit ces attributs à chaque appel
        # (jamais figés à l'import).
        if "app" in sys.modules:
            cls.app_module = sys.modules["app"]
        else:
            cls.app_module = importlib.import_module("app")

        if cls.app_module.engine_manager is None:
            raise RuntimeError(
                "app.engine_manager est None malgré un Stockfish détecté : "
                "ce test DOIT échouer, pas être sauté (issue #137)."
            )

        cls.client = cls.app_module.socketio.test_client(cls.app_module.app)

    @classmethod
    def tearDownClass(cls):
        _restaure_config_paths(cls._config_module, cls._anciens_config)
        cls._tmp.cleanup()

    def setUp(self):
        self.client.get_received()
        self.app_module._current_exercise = None

    # -- Simulations (IA uniquement) et captures ----------------------------

    def _capturer_appel_claude(self):
        """Remplace llm_coach._call_claude par une simulation (aucun appel
        réseau réel) — même mécanisme que test_issue128.py."""
        captures = []

        def _faux_call_claude(prompt_sys, messages, api_key, model, usage_path=None,
                               timeout_s=90, temperature=None):
            captures.append(prompt_sys)
            return "Réponse simulée du coach pour le test issue #137."

        patcher = patch.object(
            self.app_module.llm_coach, "_call_claude", side_effect=_faux_call_claude,
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        return captures

    def _capturer_contexte_coach(self):
        """Intercepte llm_coach.get_coach_response SANS remplacer son
        exécution réelle (side_effect qui rappelle l'original) : capture le
        dict `context` réellement transmis — c'est ce dict qui porte
        eval_blancs_cp/eval_blancs_mat et qui finit, inchangé, dans
        coach_calls.log (cf. llm_coach._log_coach_call)."""
        captures = []
        original = self.app_module.llm_coach.get_coach_response

        def _espion(messages, context, coach_memory, cfg):
            captures.append(context)
            return original(messages, context, coach_memory, cfg)

        patcher = patch.object(
            self.app_module.llm_coach, "get_coach_response", side_effect=_espion,
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        return captures

    def _patch_eval_apres(self, cp=None, mate=None):
        """Intercepte UNIQUEMENT l'appel EngineManager.evaluate(depth=8) —
        la signature exacte utilisée par app._eval_blancs_apres (seule
        fonction de ce chemin appelée avec cette profondeur par défaut ;
        evaluate_move et get_threats utilisent systématiquement
        DEPTH_EXERCICE_TEMPS_REEL=18, cf. engine_stockfish.py/app.py) — pour
        lui faire rendre une valeur cp/mat FIXE et contrôlée, inspirée des
        journaux réels. Tout autre appel (profondeur différente) retombe
        sur le VRAI moteur : le verdict, la PV, la menace adverse restent
        une analyse Stockfish réelle, jamais simulée."""
        engine_manager = self.app_module.engine_manager
        original_evaluate = engine_manager.evaluate

        def _evaluate_simule(board, depth=8, time_limit=None):
            if depth == 8 and time_limit is None:
                return {
                    "cp": cp, "mate": mate, "wdl": None,
                    "best_move": None, "pv": [], "indisponible": False,
                }
            return original_evaluate(board, depth=depth, time_limit=time_limit)

        patcher = patch.object(engine_manager, "evaluate", side_effect=_evaluate_simule)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _lire_entree_log(self, log_id):
        candidats = list(self._tmp_dir.glob("coach_calls_log_path*.tmp"))
        self.assertTrue(candidats, "aucun fichier coach_calls.log (temporaire) n'a été créé")
        for chemin in candidats:
            for ligne in chemin.read_text(encoding="utf-8").splitlines():
                if not ligne.strip():
                    continue
                entree = json.loads(ligne)
                if entree.get("id") == log_id:
                    return entree
        self.fail(f"aucune entrée de coach_calls.log ne porte l'id {log_id!r}")

    def _emettre_lichess(self, fen_avant: str, camp_alain: str, uci: str, exercise_id: str):
        self.app_module._current_exercise = {
            "source": "lichess",
            "fen_avant": fen_avant,
            "camp_alain": camp_alain,
            "coup_joue_san": "", "coup_joue_uci": "",
            "meilleur_coup_san": "", "meilleur_coup_uci": "",
            "solution": [], "categorie_tirage": None, "cle_historique": None,
            "niveau_tirage": None, "rating": None, "themes": [],
        }
        captures_claude = self._capturer_appel_claude()
        captures_contexte = self._capturer_contexte_coach()
        self.client.emit("exercise_answer", {"uci": uci, "exercise_id": exercise_id})
        recus = self.client.get_received()
        self.assertTrue(captures_claude, "l'API du coach (simulée) n'a jamais été appelée")
        self.assertTrue(captures_contexte, "get_coach_response n'a jamais été appelé")
        commentaires = [e for e in recus if e["name"] == "exercise_comment"]
        self.assertTrue(commentaires, "aucun événement exercise_comment reçu (verdict indisponible ?)")
        return captures_contexte[0], commentaires[0]["args"][0]

    def _verifier_contexte_et_log(self, contexte: dict, evenement: dict,
                                    attendu_cp=None, attendu_mat=None):
        """Vérifie (a) que le contexte transmis à l'IA porte exactement la
        valeur attendue en convention Lichess, et (b) que coach_calls.log
        enregistre la MÊME valeur, sans aucune conversion (issue #137,
        tâche 3)."""
        if attendu_mat is not None:
            self.assertEqual(contexte.get("eval_blancs_mat"), attendu_mat)
        else:
            self.assertEqual(contexte.get("eval_blancs_cp"), attendu_cp)
        log_id = evenement.get("log_id")
        self.assertTrue(log_id, "log_id absent de l'événement exercise_comment")
        entree_log = self._lire_entree_log(log_id)
        self.assertEqual(
            entree_log["context"].get("eval_blancs_cp"), contexte.get("eval_blancs_cp"),
            "coach_calls.log n'enregistre pas la même valeur eval_blancs_cp que le contexte transmis à l'IA",
        )
        self.assertEqual(
            entree_log["context"].get("eval_blancs_mat"), contexte.get("eval_blancs_mat"),
            "coach_calls.log n'enregistre pas la même valeur eval_blancs_mat que le contexte transmis à l'IA",
        )

    # == Alain Noir (sign Lichess = +1 après son coup : Blancs au trait) ====

    def test_alain_noir_avantage_blancs_354cp(self):
        # Inspiré du journal réel (+297 puis +354, Alain Noir).
        self._patch_eval_apres(cp=354)
        contexte, evenement = self._emettre_lichess(
            FEN_NOIR_GENERIQUE, "noirs", UCI_NOIR_GENERIQUE, "test137-noir-avantage-blancs")
        self._verifier_contexte_et_log(contexte, evenement, attendu_cp=354)
        self.assertGreater(contexte["eval_blancs_cp"], 0)

    def test_alain_noir_avantage_noirs_163cp(self):
        # Inspiré du journal réel (-90 puis -163, Alain Noir).
        self._patch_eval_apres(cp=-163)
        contexte, evenement = self._emettre_lichess(
            FEN_NOIR_GENERIQUE, "noirs", UCI_NOIR_GENERIQUE, "test137-noir-avantage-noirs")
        self._verifier_contexte_et_log(contexte, evenement, attendu_cp=-163)
        self.assertLess(contexte["eval_blancs_cp"], 0)

    def test_alain_noir_quasi_egalite_12cp(self):
        self._patch_eval_apres(cp=12)
        contexte, evenement = self._emettre_lichess(
            FEN_NOIR_GENERIQUE, "noirs", UCI_NOIR_GENERIQUE, "test137-noir-egalite")
        self._verifier_contexte_et_log(contexte, evenement, attendu_cp=12)
        self.assertLess(abs(contexte["eval_blancs_cp"]), 30)

    def test_alain_noir_mat_blancs(self):
        self._patch_eval_apres(mate=3)
        contexte, evenement = self._emettre_lichess(
            FEN_NOIR_GENERIQUE, "noirs", UCI_NOIR_GENERIQUE, "test137-noir-mat-blancs")
        self._verifier_contexte_et_log(contexte, evenement, attendu_mat=3)
        self.assertGreater(contexte["eval_blancs_mat"], 0)

    def test_alain_noir_mat_noirs(self):
        self._patch_eval_apres(mate=-4)
        contexte, evenement = self._emettre_lichess(
            FEN_NOIR_GENERIQUE, "noirs", UCI_NOIR_GENERIQUE, "test137-noir-mat-noirs")
        self._verifier_contexte_et_log(contexte, evenement, attendu_mat=-4)
        self.assertLess(contexte["eval_blancs_mat"], 0)

    def test_alain_noir_signes_opposes_avant_apres_vrai_moteur(self):
        # Avant le coup (Alain Noir massivement en avance, dame contre
        # tour) : signe attendu négatif. Après le blunder Dxd1+?? (la tour
        # blanche reprend la dame) : signe attendu positif. VRAI moteur,
        # aucune simulation.
        board_avant = chess.Board(FEN_NOIR_BASCULE)
        eval_avant_brut = self.app_module.engine_manager.evaluate(board_avant, depth=8)
        sign_avant = 1 if board_avant.turn == chess.WHITE else -1
        eval_avant_blancs = sign_avant * eval_avant_brut["cp"]
        self.assertLess(eval_avant_blancs, -50, "position de départ censée être massivement en faveur des Noirs")

        contexte, evenement = self._emettre_lichess(
            FEN_NOIR_BASCULE, "noirs", UCI_NOIR_BASCULE, "test137-noir-bascule")
        self.assertIsNotNone(contexte.get("eval_blancs_cp"))
        self.assertGreater(contexte["eval_blancs_cp"], 50, "après le blunder, les Blancs doivent être massivement en avance")
        log_id = evenement.get("log_id")
        entree_log = self._lire_entree_log(log_id)
        self.assertEqual(entree_log["context"].get("eval_blancs_cp"), contexte.get("eval_blancs_cp"))

    def test_alain_noir_avantage_blancs_evident_vrai_moteur(self):
        # Dame noire manquante dès le départ : avantage Blancs évident,
        # VRAI moteur, aucune simulation (issue #137, tâche 2 : "pour le
        # vrai moteur des positions où le camp gagnant est évident").
        contexte, evenement = self._emettre_lichess(
            FEN_NOIR_AVANTAGE_EVIDENT, "noirs", "e7e5", "test137-noir-evident")
        self.assertIsNotNone(contexte.get("eval_blancs_cp"))
        self.assertGreater(contexte["eval_blancs_cp"], 300)
        log_id = evenement.get("log_id")
        entree_log = self._lire_entree_log(log_id)
        self.assertEqual(entree_log["context"].get("eval_blancs_cp"), contexte.get("eval_blancs_cp"))

    # == Alain Blancs (sign Lichess = -1 après son coup : Noirs au trait) ===

    def test_alain_blancs_avantage_blancs_125cp(self):
        # Inspiré du journal réel (+125, Alain Blancs) : mock_cp = -125 car
        # le signe de app._eval_blancs_apres est -1 après un coup Blanc
        # (Noirs au trait) — ce test échoue si cette inversion n'a pas lieu.
        self._patch_eval_apres(cp=-125)
        contexte, evenement = self._emettre_lichess(
            FEN_BLANC_GENERIQUE, "blancs", UCI_BLANC_GENERIQUE, "test137-blancs-avantage-blancs")
        self._verifier_contexte_et_log(contexte, evenement, attendu_cp=125)
        self.assertGreater(contexte["eval_blancs_cp"], 0)

    def test_alain_blancs_avantage_noirs_626cp(self):
        # Inspiré du journal réel (-430 puis -626, Alain Blancs).
        self._patch_eval_apres(cp=626)
        contexte, evenement = self._emettre_lichess(
            FEN_BLANC_GENERIQUE, "blancs", UCI_BLANC_GENERIQUE, "test137-blancs-avantage-noirs")
        self._verifier_contexte_et_log(contexte, evenement, attendu_cp=-626)
        self.assertLess(contexte["eval_blancs_cp"], 0)

    def test_alain_blancs_quasi_egalite_9cp(self):
        self._patch_eval_apres(cp=-9)
        contexte, evenement = self._emettre_lichess(
            FEN_BLANC_GENERIQUE, "blancs", UCI_BLANC_GENERIQUE, "test137-blancs-egalite")
        self._verifier_contexte_et_log(contexte, evenement, attendu_cp=9)
        self.assertLess(abs(contexte["eval_blancs_cp"]), 30)

    def test_alain_blancs_mat_blancs(self):
        self._patch_eval_apres(mate=-5)
        contexte, evenement = self._emettre_lichess(
            FEN_BLANC_GENERIQUE, "blancs", UCI_BLANC_GENERIQUE, "test137-blancs-mat-blancs")
        self._verifier_contexte_et_log(contexte, evenement, attendu_mat=5)
        self.assertGreater(contexte["eval_blancs_mat"], 0)

    def test_alain_blancs_mat_noirs(self):
        self._patch_eval_apres(mate=6)
        contexte, evenement = self._emettre_lichess(
            FEN_BLANC_GENERIQUE, "blancs", UCI_BLANC_GENERIQUE, "test137-blancs-mat-noirs")
        self._verifier_contexte_et_log(contexte, evenement, attendu_mat=-6)
        self.assertLess(contexte["eval_blancs_mat"], 0)

    def test_alain_blancs_signes_opposes_avant_apres_vrai_moteur(self):
        # Avant le coup (Alain Blancs massivement en avance, dame contre
        # tour) : signe attendu positif. Après le blunder Qa1?? (la tour
        # noire reprend la dame) : signe attendu négatif. VRAI moteur,
        # aucune simulation.
        board_avant = chess.Board(FEN_BLANC_BASCULE)
        eval_avant_brut = self.app_module.engine_manager.evaluate(board_avant, depth=8)
        sign_avant = 1 if board_avant.turn == chess.WHITE else -1
        eval_avant_blancs = sign_avant * eval_avant_brut["cp"]
        self.assertGreater(eval_avant_blancs, 50, "position de départ censée être massivement en faveur des Blancs")

        contexte, evenement = self._emettre_lichess(
            FEN_BLANC_BASCULE, "blancs", UCI_BLANC_BASCULE, "test137-blancs-bascule")
        self.assertIsNotNone(contexte.get("eval_blancs_cp"))
        self.assertLess(contexte["eval_blancs_cp"], -50, "après le blunder, les Noirs doivent être massivement en avance")
        log_id = evenement.get("log_id")
        entree_log = self._lire_entree_log(log_id)
        self.assertEqual(entree_log["context"].get("eval_blancs_cp"), contexte.get("eval_blancs_cp"))

    def test_alain_blancs_avantage_noirs_evident_vrai_moteur(self):
        # Dame blanche manquante dès le départ : avantage Noirs évident,
        # VRAI moteur, aucune simulation.
        contexte, evenement = self._emettre_lichess(
            FEN_BLANC_AVANTAGE_EVIDENT, "blancs", "e2e4", "test137-blancs-evident")
        self.assertIsNotNone(contexte.get("eval_blancs_cp"))
        self.assertLess(contexte["eval_blancs_cp"], -300)
        log_id = evenement.get("log_id")
        entree_log = self._lire_entree_log(log_id)
        self.assertEqual(entree_log["context"].get("eval_blancs_cp"), contexte.get("eval_blancs_cp"))


if __name__ == "__main__":
    unittest.main()
