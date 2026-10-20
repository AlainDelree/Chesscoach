"""
test_issue128.py — ChessCoach (issue #128, suite #126)

Tests pour la convention de signe de Lichess (+ = avantage Blancs,
− = avantage Noirs) appliquée à toutes les évaluations et soldes matériel
transmis aux IA, et pour les correctifs manuels du 20 octobre 2026
(échange réel pour « en prise », numérotation, roques, prolongation des
lignes).

Isolation (même précaution que non_regression_coach.py, tâche 3 de l'issue
#93) : la partie de ce fichier qui importe app.py et pilote ses VRAIS
handlers SocketIO (TestExerciseAnswerSocketIO ci-dessous, issue #128 tâche
5c) redirige IMPÉRATIVEMENT tous les chemins de data/ de config.py vers un
dossier temporaire AVANT cet import — app.py lit/écrit plusieurs fichiers
personnels d'Alain dès l'import (coach_memory.json, niveau_exercices_
lichess.json) ou à l'usage (coach_calls.log, usage_tokens.json,
exercice_historique.json) : aucun de ces fichiers réels ne doit être
touché par ce test. Les appels aux API Claude/Mistral sont remplacés par
des simulations (jamais d'appel réseau réel).
"""

import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import chess

import game_facts
from engine_stockfish import EngineManager, find_stockfish, _couper_pv


# =============================================================================
# Partie 1 : calcul « en prise » par échange (défense par pion, défenseur
# cloué), numérotation, noms de roque, prolongation de ligne — unitaires,
# sans Stockfish ni app.py.
# =============================================================================

class TestEnPriseParEchange(unittest.TestCase):
    """_get_insufficiently_defended (donc le « en prise » du bloc de faits
    PV, issue #126 corrigée le 20 octobre 2026) doit être un vrai calcul
    d'échange — pas une comparaison de valeurs brutes."""

    def test_piece_attaquee_par_tour_mais_defendue_par_pion_pas_en_prise(self):
        # Tour noire en d8 attaque le cavalier blanc en d4, mais un pion
        # blanc en e3 défend la case d4 (reprise ePx d4 possible) : le
        # cavalier n'est PAS "en prise" malgré l'attaque d'une pièce plus
        # chère.
        fen = "3r1k2/8/8/8/3N4/4P3/8/4K3 w - - 0 1"
        board = chess.Board(fen)
        self.assertEqual(board.piece_at(chess.D4).piece_type, chess.KNIGHT)
        en_prise_blancs = game_facts._get_insufficiently_defended(board, chess.WHITE)
        self.assertNotIn("Cavalier d4", en_prise_blancs)

    def test_piece_attaquee_et_vraiment_sans_defense_en_prise(self):
        # Même tour en d8, mais plus aucun défenseur blanc de d4 : le
        # cavalier est bien "en prise" cette fois.
        fen = "3r1k2/8/8/8/3N4/8/8/4K3 w - - 0 1"
        board = chess.Board(fen)
        en_prise_blancs = game_facts._get_insufficiently_defended(board, chess.WHITE)
        self.assertIn("Cavalier d4", en_prise_blancs)

    def test_defenseur_cloue_ne_protege_pas(self):
        # Cavalier noir en c3, seul défenseur géométrique blanc : le pion
        # b2 (bxc3). Mais ce pion est cloué sur la diagonale a3-c1 par le
        # fou noir en a3 contre le roi blanc en c1 : bxc3 l'éloignerait de
        # cette diagonale et exposerait le roi — coup illégal, donc le
        # cavalier noir n'est PAS repris malgré la présence apparente d'un
        # défenseur.
        fen = "4k3/8/8/8/8/b1n5/1P6/2K5 w - - 0 1"
        board = chess.Board(fen)
        self.assertTrue(board.is_pinned(chess.WHITE, chess.B2))
        gain = game_facts._gain_capture(board, chess.C3, chess.WHITE)
        self.assertEqual(gain, 0, "le pion cloué en b2 ne doit pas pouvoir reprendre en c3")


class TestNumerotationEtRoques(unittest.TestCase):
    """Numérotation « 31.R5xe4 »/« 30...Rxb6 » et noms de roque (petit/
    grand), issue #126 corrigée le 20 octobre 2026."""

    def test_numerotation_coup_blanc_avec_desambiguation(self):
        # Deux tours blanches (e5 et e2) pouvant toutes deux capturer en e4 ;
        # seul le numéro de rang désambiguïse (même colonne e) — la ligne
        # doit porter le numéro de coup ET cette désambiguïsation SAN
        # (R5xe4, déjà résolue par python-chess).
        fen = "k7/8/8/4R3/4n3/8/4R3/K7 w - - 0 31"
        board = chess.Board(fen)
        san = board.san(board.parse_san("R5xe4"))
        self.assertEqual(san, "R5xe4")
        facts = game_facts.describe_pv_facts(fen, san, "blancs", max_plies=1)
        self.assertEqual(facts[0]["san"], "31.R5xe4")

    def test_numerotation_coup_noir_avec_desambiguation(self):
        fen = "k7/8/8/4r3/4N3/8/4r3/K7 b - - 0 30"
        board = chess.Board(fen)
        san = board.san(board.parse_san("R5xe4"))
        self.assertEqual(san, "R5xe4")
        facts = game_facts.describe_pv_facts(fen, san, "noirs", max_plies=1)
        self.assertEqual(facts[0]["san"], "30...R5xe4")

    def test_petit_roque(self):
        fen = "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1"
        facts = game_facts.describe_pv_facts(fen, "O-O", "blancs", max_plies=1)
        formatted = game_facts.format_pv_facts("Test", facts, "blancs")
        self.assertIn("petit roque", formatted)
        self.assertNotIn("grand roque", formatted)

    def test_grand_roque(self):
        fen = "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1"
        facts = game_facts.describe_pv_facts(fen, "O-O-O", "blancs", max_plies=1)
        formatted = game_facts.format_pv_facts("Test", facts, "blancs")
        self.assertIn("grand roque", formatted)
        self.assertNotIn("petit roque", formatted)


class TestProlongationLigne(unittest.TestCase):
    """Les lignes ne sont jamais coupées en plein échange (au plus 2 coups
    de plus tant que le dernier coup retenu est une capture) — même règle
    pour engine_stockfish._couper_pv, game_facts.describe_pv_with_balance
    et game_facts.describe_pv_facts (issue #126 corrigée le 20 octobre
    2026 ; issue #128 tâche 5 : même règle pour le détail coup par coup)."""

    # Exemple réel cité par l'issue #128 : une ligne "Bd6 O-O O-O exd5" doit
    # être prolongée par "cxd5" (le pion qui vient de prendre en d5 est
    # lui-même repris) plutôt que de s'arrêter au milieu de l'échange.
    FEN_DEPART = "r1bqkb1r/p2n1ppp/1pp1pn2/3p4/2PPP3/2N2N2/PPQ1BPPP/R1B1K2R b KQkq - 1 7"
    PV = "Bd6 O-O O-O exd5 cxd5"

    @classmethod
    def _coups_pv(cls):
        """Reconstruit la liste de chess.Move de self.PV, rejouée coup par
        coup depuis self.FEN_DEPART (nécessaire pour _couper_pv, qui attend
        des coups réellement légaux EN SÉQUENCE depuis le plateau donné)."""
        b = chess.Board(cls.FEN_DEPART)
        coups = []
        for s in cls.PV.split():
            m = b.parse_san(s)
            coups.append(m)
            b.push(m)
        return coups

    def test_couper_pv_engine_stockfish_prolonge_sur_capture(self):
        board = chess.Board(self.FEN_DEPART)
        coups = self._coups_pv()
        # n=4 : sans prolongation, on s'arrêterait après "Bd6 O-O O-O exd5"
        # (4e coup = capture) — la règle doit ajouter "cxd5" (5e coup).
        gardes = _couper_pv(board, coups, n=4, extra=2)
        self.assertEqual(len(gardes), 5)

    def test_describe_pv_with_balance_prolonge_sur_capture(self):
        resultat = game_facts.describe_pv_with_balance(
            self.FEN_DEPART, self.PV, "noirs", max_plies=4
        )
        sans = [d["san"] for d in resultat]
        self.assertEqual(sans, ["Bd6", "O-O", "O-O", "exd5", "cxd5"])

    def test_describe_pv_facts_prolonge_sur_capture(self):
        resultat = game_facts.describe_pv_facts(
            self.FEN_DEPART, self.PV, "noirs", max_plies=4
        )
        self.assertEqual(len(resultat), 5)
        self.assertIn("cxd5", resultat[-1]["san"])

    def test_ne_prolonge_pas_quand_dernier_coup_retenu_n_est_pas_une_capture(self):
        # Garde-fou symétrique : si le DERNIER coup des n premiers n'est pas
        # une capture (ici "O-O", 2e coup de la ligne), aucune prolongation
        # n'a lieu — même si un coup ultérieur de la ligne EST une capture.
        board = chess.Board(self.FEN_DEPART)
        coups = self._coups_pv()
        gardes = _couper_pv(board, coups, n=2, extra=2)
        self.assertEqual(len(gardes), 2)


# =============================================================================
# Partie 2 : conversion de signe — évaluations et solde matériel en
# convention Lichess, pour un exercice joué avec les Noirs ET avec les
# Blancs (issue #128, tâches 1 à 3).
# =============================================================================

class TestConventionSigneEvaluation(unittest.TestCase):
    """engine_stockfish.EngineManager.evaluate_move doit rendre eval_before_cp/
    eval_after_cp en convention Lichess (+ = avantage Blancs), quel que soit
    le camp qui vient de jouer — jamais "point de vue du joueur"."""

    @classmethod
    def setUpClass(cls):
        path = find_stockfish()
        if not path:
            raise unittest.SkipTest("Stockfish introuvable sur cette machine")
        cls.engine_manager = EngineManager(path)

    @classmethod
    def tearDownClass(cls):
        cls.engine_manager.quit()

    def test_noirs_en_avance_eval_negative(self):
        # Dame blanche manquante : les Noirs sont massivement en avance,
        # et ce sont eux qui viennent de jouer (trait aux Noirs sur
        # fen_avant). Avant l'issue #128, ce cas produisait un chiffre
        # POSITIF ("point de vue du joueur" = Alain = Noirs) alors que
        # Lichess afficherait un chiffre négatif pour cette même position.
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNB1KBNR b KQkq - 0 1"
        board = chess.Board(fen)
        move = next(iter(board.legal_moves))
        res = self.engine_manager.evaluate_move(
            board, move, depth=10, always_return_best=True, return_pv=True
        )
        self.assertIsNotNone(res["eval_before_cp"])
        self.assertLess(res["eval_before_cp"], 0, "les Noirs sont en avance : attendu négatif (convention Lichess)")

    def test_blancs_en_avance_eval_positive(self):
        fen = "rnb1kbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        board = chess.Board(fen)
        move = next(iter(board.legal_moves))
        res = self.engine_manager.evaluate_move(
            board, move, depth=10, always_return_best=True, return_pv=True
        )
        self.assertIsNotNone(res["eval_before_cp"])
        self.assertGreater(res["eval_before_cp"], 0, "les Blancs sont en avance : attendu positif (convention Lichess)")


class TestConventionSigneSoldeMateriel(unittest.TestCase):
    """game_facts._solde_blancs / describe_pv_facts / describe_pv_with_balance
    doivent rendre un solde matériel en convention Lichess, indépendant de
    camp_alain (issue #128, tâche 2)."""

    def test_solde_blancs_valeur_attendue(self):
        # Position simple : une tour blanche, une tour noire, un cavalier
        # noir de plus -> solde = 5 - 5 - 3 = -3 (avantage Noirs).
        fen = "4k3/8/8/8/8/5n2/8/R3K2r w - - 0 1"
        board = chess.Board(fen)
        self.assertEqual(game_facts._solde_blancs(board), -3)

    def test_format_pv_facts_pas_de_pour_toi_ni_pour_alain(self):
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNB1KBNR b KQkq - 0 1"
        facts = game_facts.describe_pv_facts(fen, "Nc6", "noirs", max_plies=1)
        formatted = game_facts.format_pv_facts("Test", facts, "noirs")
        self.assertNotIn("pour toi", formatted)
        self.assertNotIn("pour Alain", formatted)
        self.assertIn("convention de Lichess", formatted)
        # Les Noirs sont en avance (dame blanche manquante) : solde négatif.
        self.assertIn("solde matériel : -", formatted)

    def test_describe_pv_with_balance_solde_blancs_pov(self):
        fen = "rnb1kbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        resultat = game_facts.describe_pv_with_balance(fen, "Nc3", "blancs", max_plies=1)
        self.assertEqual(len(resultat), 1)
        # Les Blancs sont en avance (dame noire manquante) : solde positif.
        self.assertGreater(resultat[0]["solde_blancs"], 0)

    def test_describe_eval_blancs_cp_clause_jamais_pour_alain(self):
        texte = game_facts.describe_eval_blancs_cp_clause(-250)
        self.assertNotIn("pour Alain", texte)
        self.assertNotIn("pour toi", texte)
        self.assertIn("avantage Noirs", texte)
        self.assertIn("-250", texte)


# =============================================================================
# Partie 3 : exécution du VRAI gestionnaire de réponse d'exercice avec le
# client de test Flask-SocketIO (issue #128, tâche 5c) — « Mes erreurs » et
# « Problèmes Lichess », appels aux API des IA simulés, isolation complète
# des fichiers personnels d'Alain via des chemins temporaires.
# =============================================================================

def _patch_config_paths_vers_tmp(config_module, tmp_dir: Path) -> dict:
    """Redirige tous les chemins de données de config.py vers `tmp_dir`,
    retourne les anciennes valeurs pour restauration (voir tearDownClass)."""
    noms = [
        "DATA_DIR", "COACH_MEMORY_PATH", "ERREURS_DETECTEES_PATH",
        "EXERCICE_HISTORIQUE_PATH", "LICHESS_PUZZLES_PATH", "LICHESS_NIVEAUX_PATH",
        "COACH_CALLS_LOG_PATH", "ANALYSE_ERREURS_LOG_PATH", "SIGNALEMENTS_LOG_PATH",
        "MOTEUR_ERREURS_LOG_PATH", "EVAL_BREAKDOWN_STATE_PATH", "USAGE_TOKENS_PATH",
        "FINALES_PATH", "LLM_MODEL_CHOICE_PATH",
    ]
    anciens = {nom: getattr(config_module, nom) for nom in noms}
    for nom in noms:
        setattr(config_module, nom, tmp_dir / f"{nom.lower()}.tmp")
    anciens["LLM_API_KEY"] = config_module.LLM_API_KEY
    anciens["MISTRAL_API_KEY"] = config_module.MISTRAL_API_KEY
    config_module.LLM_API_KEY = "fake-test-key-issue128"
    config_module.MISTRAL_API_KEY = ""
    return anciens


def _restaure_config_paths(config_module, anciens: dict) -> None:
    for nom, valeur in anciens.items():
        setattr(config_module, nom, valeur)


@unittest.skipUnless(find_stockfish(), "Stockfish introuvable sur cette machine")
class TestExerciseAnswerSocketIO(unittest.TestCase):
    """Fait tourner app.on_exercise_answer / app._on_exercise_answer_lichess
    via un VRAI client de test Flask-SocketIO (issue #128, tâche 5c), API
    Claude simulée — vérifie le signe des évaluations du contexte envoyé à
    l'IA pour un exercice noir et un exercice blanc, pour les deux sources
    « Mes erreurs » et « Problèmes Lichess »."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        tmp_dir = Path(cls._tmp.name)

        import config as config_module
        cls._config_module = config_module
        cls._anciens_config = _patch_config_paths_vers_tmp(config_module, tmp_dir)

        # (Ré)importer les modules qui lisent des chemins config.* dès leur
        # import, APRÈS le patch ci-dessus, pour qu'ils utilisent bien les
        # chemins temporaires (jamais les fichiers personnels réels
        # d'Alain) — app.py n'avait encore jamais été importé par aucun
        # test de ce dépôt (vérifié avant d'écrire ce test).
        if "app" in sys.modules:
            raise RuntimeError(
                "app.py était déjà importé avant ce test : l'isolation des "
                "chemins de données ne peut plus être garantie (voir "
                "l'en-tête de ce fichier)."
            )
        cls.app_module = importlib.import_module("app")
        cls.client = cls.app_module.socketio.test_client(cls.app_module.app)

    @classmethod
    def tearDownClass(cls):
        _restaure_config_paths(cls._config_module, cls._anciens_config)
        cls._tmp.cleanup()

    def setUp(self):
        # Vider les éventuels événements résiduels d'un test précédent.
        self.client.get_received()
        self.app_module._current_exercise = None

    def _capturer_appel_claude(self):
        """Remplace llm_coach._call_claude par une simulation qui capture
        le system prompt complet (contexte envoyé à l'IA inclus) et ne fait
        JAMAIS d'appel réseau réel — retourne (patcher, liste_captures)."""
        captures = []

        def _faux_call_claude(prompt_sys, messages, api_key, model, usage_path=None,
                               timeout_s=90, temperature=None):
            captures.append(prompt_sys)
            return "Réponse simulée du coach pour le test issue #128."

        patcher = patch.object(
            self.app_module.llm_coach, "_call_claude", side_effect=_faux_call_claude,
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        return captures

    def _emettre_exercise_answer(self, fen_avant: str, camp_alain: str, uci: str,
                                   source: str = "mes_erreurs") -> list:
        self.app_module._current_exercise = {
            "source": source,
            "fen_avant": fen_avant,
            "camp_alain": camp_alain,
            "coup_joue_san": "", "coup_joue_uci": "",
            "meilleur_coup_san": "", "meilleur_coup_uci": "",
            # Champs additionnels attendus par la source "lichess" :
            "solution": [], "categorie_tirage": None, "cle_historique": None,
            "niveau_tirage": None, "rating": None, "themes": [],
        }
        captures = self._capturer_appel_claude()
        self.client.emit("exercise_answer", {"uci": uci, "exercise_id": f"test-{source}-{camp_alain}"})
        recus = self.client.get_received()
        self.assertTrue(captures, "l'API du coach (simulée) n'a jamais été appelée")
        return captures, recus

    @staticmethod
    def _contexte_dynamique(prompt_sys: str) -> str:
        """Partie du system prompt réellement spécifique à cette position
        (après le marqueur "Contexte de la position en cours :"), SANS les
        consignes statiques de llm_coach.py qui, elles, doivent légitimement
        citer "pour toi"/"pour Alain" entre guillemets pour dire à l'IA de
        ne JAMAIS les employer (cf. _SYSTEM_PROMPT/_EXERCISE_SYSTEM_ADDENDUM) —
        chercher ces phrases dans le prompt système complet serait donc
        toujours positif, indépendamment de tout bug réel."""
        marqueur = "Contexte de la position en cours :"
        idx = prompt_sys.find(marqueur)
        return prompt_sys[idx:] if idx != -1 else prompt_sys

    def test_mes_erreurs_exercice_noir_eval_negative_et_pas_pour_qui(self):
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNB1KBNR b KQkq - 0 1"  # dame blanche manquante : Noirs en avance
        captures, recus = self._emettre_exercise_answer(fen, "noirs", "g8h6", source="mes_erreurs")
        prompt_sys = captures[0]
        self.assertIn("Évaluation avant le coup", prompt_sys)
        contexte = self._contexte_dynamique(prompt_sys)
        self.assertNotIn("pour toi", contexte)
        self.assertNotIn("pour Alain", contexte)
        # Extrait le nombre juste après "... avantage Noirs) : " — ".*?" (et
        # non "[^:]*") car le texte contient un premier ":" à l'intérieur de
        # "(convention Lichess : ...)" avant le vrai séparateur numérique.
        import re
        m = re.search(r"Évaluation avant le coup.*?:\s*([+-]\d+(?:\.\d+)?)cp", prompt_sys)
        self.assertIsNotNone(m, "évaluation avant le coup introuvable dans le prompt système")
        self.assertLess(float(m.group(1)), 0, "les Noirs sont en avance : attendu négatif")
        self.assertTrue(any(e["name"] == "exercise_comment" for e in recus))

    def test_mes_erreurs_exercice_blanc_eval_positive(self):
        fen = "rnb1kbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"  # dame noire manquante : Blancs en avance
        captures, recus = self._emettre_exercise_answer(fen, "blancs", "g1h3", source="mes_erreurs")
        prompt_sys = captures[0]
        import re
        m = re.search(r"Évaluation avant le coup.*?:\s*([+-]\d+(?:\.\d+)?)cp", prompt_sys)
        self.assertIsNotNone(m)
        self.assertGreater(float(m.group(1)), 0, "les Blancs sont en avance : attendu positif")
        self.assertTrue(any(e["name"] == "exercise_comment" for e in recus))

    def test_problemes_lichess_exercice_noir_eval_negative(self):
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNB1KBNR b KQkq - 0 1"
        captures, recus = self._emettre_exercise_answer(fen, "noirs", "g8h6", source="lichess")
        prompt_sys = captures[0]
        contexte = self._contexte_dynamique(prompt_sys)
        self.assertNotIn("pour toi", contexte)
        self.assertNotIn("pour Alain", contexte)
        self.assertTrue(any(e["name"] == "exercise_comment" for e in recus))

    def test_problemes_lichess_exercice_blanc_eval_positive(self):
        fen = "rnb1kbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        captures, recus = self._emettre_exercise_answer(fen, "blancs", "g1h3", source="lichess")
        prompt_sys = captures[0]
        contexte = self._contexte_dynamique(prompt_sys)
        self.assertNotIn("pour toi", contexte)
        self.assertNotIn("pour Alain", contexte)
        self.assertTrue(any(e["name"] == "exercise_comment" for e in recus))


if __name__ == "__main__":
    unittest.main()
