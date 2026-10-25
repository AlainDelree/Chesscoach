"""
test_issue143_selection_club.py — ChessCoach (issue #143, suite #142)

Tests pour scripts/selection_club.py (sélection des exercices de la future
page « club » selon l'écart entre les meilleurs coups de Stockfish). AUCUN
fichier personnel d'Alain n'est lu ni écrit : le jeu de données est fabriqué
ici même (positions construites et validées par python-chess), jamais lu
depuis data/erreurs_detectees.json réel.

Issue #143, vérification (c) : aucun test de ce fichier n'est ignoré,
désactivé ou conditionné par une variable d'environnement — Stockfish
absent de la machine fait ÉCHOUER setUpClass (RuntimeError), il n'est
jamais sauté (même convention que test_issue142_page_club.py).

Indépendant de app.py (jamais importé) : scripts/selection_club.py est un
script autonome, sans route Flask ni appel IA.

Exécution isolée, comme les autres fichiers test_issue*.py de ce dépôt :
    python3 -m unittest test_issue143_selection_club
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import chess

from engine_stockfish import find_stockfish
from scripts import selection_club as sc


def _fixture_erreurs() -> list:
    """Jeu de données fabriqué (même format que data/erreurs_detectees.json),
    couvrant tous les cas demandés par l'issue #143 : une position évidente
    par camp, une discutable par camp (+ un doublon de partie), une position
    décidée mais à écart faible (ne doit PAS être « discutable »), un mat
    forcé en 1 coup (exclu des deux catégories), une position invalide et un
    doublon exact de position."""
    b_apres_e4 = chess.Board()
    b_apres_e4.push_san("e4")
    b_meme_partie_que_colC = chess.Board()
    b_meme_partie_que_colC.push_san("d4")

    return [
        {  # 1. évidente, Blancs : Nxd5 gagne une dame pendante
            "collection_id": "colA", "game_index": 1, "white": "Alain", "black": "X",
            "date": "2026-01-01", "camp_alain": "blancs", "coup_plein": 10,
            "phase": "milieu_de_partie", "sous_type": "materiel", "qualite": "blunder",
            "delta_cp": 700,
            "fen_avant": "r1bk3r/ppp2ppp/2n5/3q4/8/2N2N2/PPPP1PPP/R1B1KB1R w KQ - 0 1",
            "coup_joue_san": "d4", "coup_joue_uci": "d2d4",
            "meilleur_coup_uci": "c3d5", "meilleur_coup_san": "Nxd5",
        },
        {  # 2. évidente, Noirs : miroir exact du cas 1
            "collection_id": "colB", "game_index": 1, "white": "Y", "black": "Alain",
            "date": "2026-01-02", "camp_alain": "noirs", "coup_plein": 12,
            "phase": "milieu_de_partie", "sous_type": "materiel", "qualite": "blunder",
            "delta_cp": 700,
            "fen_avant": "r1b1kb1r/pppp1ppp/2n2n2/8/3Q4/2N5/PPP2PPP/R1BK3R b kq - 0 1",
            "coup_joue_san": "d5", "coup_joue_uci": "d7d5",
            "meilleur_coup_uci": "c6d4", "meilleur_coup_san": "Nxd4",
        },
        {  # 3. discutable, Blancs : position de départ (coups quasi équivalents)
            "collection_id": "colC", "game_index": 1, "white": "Alain", "black": "Z",
            "date": "2026-01-03", "camp_alain": "blancs", "coup_plein": 1,
            "phase": "ouverture", "sous_type": "positionnel", "qualite": "imprecision",
            "delta_cp": 5,
            "fen_avant": chess.STARTING_FEN,
            "coup_joue_san": "a3", "coup_joue_uci": "a2a3",
            "meilleur_coup_uci": "e2e4", "meilleur_coup_san": "e4",
        },
        {  # 3b. même partie que #3 (colC:1) : doit être écartée par « au plus une position par partie »
            "collection_id": "colC", "game_index": 1, "white": "Alain", "black": "Z",
            "date": "2026-01-03", "camp_alain": "noirs", "coup_plein": 2,
            "phase": "ouverture", "sous_type": "positionnel", "qualite": "imprecision",
            "delta_cp": 5,
            "fen_avant": b_meme_partie_que_colC.fen(),
            "coup_joue_san": "a6", "coup_joue_uci": "a7a6",
            "meilleur_coup_uci": "g8f6", "meilleur_coup_san": "Nf6",
        },
        {  # 4. discutable, Noirs : après 1.e4
            "collection_id": "colD", "game_index": 1, "white": "W", "black": "Alain",
            "date": "2026-01-04", "camp_alain": "noirs", "coup_plein": 1,
            "phase": "ouverture", "sous_type": "positionnel", "qualite": "imprecision",
            "delta_cp": 5,
            "fen_avant": b_apres_e4.fen(),
            "coup_joue_san": "a6", "coup_joue_uci": "a7a6",
            "meilleur_coup_uci": "e7e5", "meilleur_coup_san": "e5",
        },
        {  # 5. décidée (|éval| ~850) mais écart faible entre les 3 premiers coups : NE DOIT PAS être « discutable »
            "collection_id": "colE", "game_index": 1, "white": "Alain", "black": "W2",
            "date": "2026-01-05", "camp_alain": "noirs", "coup_plein": 40,
            "phase": "finale", "sous_type": "positionnel", "qualite": "erreur",
            "delta_cp": 50,
            "fen_avant": "8/8/8/8/5k2/8/5P2/4K2R b K - 0 1",
            "coup_joue_san": "Ke5", "coup_joue_uci": "f4e5",
            "meilleur_coup_uci": "f4e4", "meilleur_coup_san": "Ke4",
        },
        {  # 6. mat forcé en 1 coup annoncé : DOIT être exclue des deux catégories
            "collection_id": "colF", "game_index": 1, "white": "Alain", "black": "W3",
            "date": "2026-01-06", "camp_alain": "blancs", "coup_plein": 30,
            "phase": "finale", "sous_type": "positionnel", "qualite": "blunder",
            "delta_cp": 900,
            "fen_avant": "6k1/5ppp/8/8/8/8/5PPP/R5K1 w - - 0 1",
            "coup_joue_san": "g4", "coup_joue_uci": "g2g4",
            "meilleur_coup_uci": "a1a8", "meilleur_coup_san": "Ra8#",
        },
        {  # 7. position invalide (FEN illisible)
            "collection_id": "colG", "game_index": 1, "white": "Alain", "black": "W4",
            "date": "2026-01-07", "camp_alain": "blancs", "coup_plein": 5,
            "phase": "ouverture", "sous_type": "positionnel", "qualite": "erreur",
            "delta_cp": 150,
            "fen_avant": "ceci n'est pas un FEN valide",
            "coup_joue_san": "??", "coup_joue_uci": "e2e4",
            "meilleur_coup_uci": "d2d4", "meilleur_coup_san": "d4",
        },
        {  # 8. doublon exact de la position évidente Blancs (#1), autre partie
            "collection_id": "colH", "game_index": 7, "white": "Alain", "black": "W5",
            "date": "2026-01-08", "camp_alain": "blancs", "coup_plein": 10,
            "phase": "milieu_de_partie", "sous_type": "materiel", "qualite": "blunder",
            "delta_cp": 700,
            "fen_avant": "r1bk3r/ppp2ppp/2n5/3q4/8/2N2N2/PPPP1PPP/R1B1KB1R w KQ - 0 1",
            "coup_joue_san": "d4", "coup_joue_uci": "d2d4",
            "meilleur_coup_uci": "c3d5", "meilleur_coup_san": "Nxd5",
        },
    ]


class TestSelectionClub(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not find_stockfish():
            raise RuntimeError(
                "Stockfish introuvable sur cette machine : ce test doit "
                "échouer plutôt que d'être sauté (issue #143, vérification c)."
            )

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.erreurs_path = Path(self._tmpdir.name) / "erreurs_test.json"
        with open(self.erreurs_path, "w", encoding="utf-8") as f:
            json.dump(_fixture_erreurs(), f, ensure_ascii=False)

    def _run(self, output_name="sortie.json", extra_argv=None):
        output_path = Path(self._tmpdir.name) / output_name
        argv = ["--erreurs-path", str(self.erreurs_path), "--output", str(output_path)]
        argv += extra_argv or []
        code = sc.main(argv)
        self.assertEqual(code, 0)
        with open(output_path, "r", encoding="utf-8") as f:
            return json.load(f)

    # -- Classification -------------------------------------------------

    def test_position_evidente_piece_pendante(self):
        sortie = self._run(extra_argv=["--n-evidents", "2", "--n-discutables", "0"])
        fens = {e["fen"] for e in sortie["evidents"]}
        self.assertIn("r1bk3r/ppp2ppp/2n5/3q4/8/2N2N2/PPPP1PPP/R1B1KB1R w KQ - 0 1", fens)
        evident_blancs = next(e for e in sortie["evidents"] if e["camp"] == "blancs")
        self.assertGreaterEqual(evident_blancs["ecart_1er_2e_cp"], sc.SEUIL_EVIDENT_CP)
        self.assertEqual(evident_blancs["coups"][0]["coup"], "Nxd5")

    def test_positions_discutables_coups_equivalents(self):
        sortie = self._run(extra_argv=["--n-evidents", "0", "--n-discutables", "9"])
        self.assertGreaterEqual(len(sortie["discutables"]), 1)
        for d in sortie["discutables"]:
            self.assertLessEqual(d["ecart_1er_2e_cp"], sc.SEUIL_DISCUTABLE_CP)

    def test_position_decidee_pas_classee_discutable(self):
        sortie = self._run(extra_argv=["--n-evidents", "0", "--n-discutables", "9"])
        fens = {d["fen"] for d in sortie["discutables"]} | {e["fen"] for e in sortie["evidents"]}
        self.assertNotIn("8/8/8/8/5k2/8/5P2/4K2R b K - 0 1", fens)

    def test_mat_force_exclu_des_deux_categories(self):
        sortie = self._run(extra_argv=["--n-evidents", "9", "--n-discutables", "9"])
        fens = {e["fen"] for e in sortie["evidents"]} | {d["fen"] for d in sortie["discutables"]}
        self.assertNotIn("6k1/5ppp/8/8/8/8/5PPP/R5K1 w - - 0 1", fens)
        self.assertEqual(sortie["resume"]["mats_forces_exclus"], 1)

    def test_position_invalide_comptee_et_ignoree(self):
        sortie = self._run()
        self.assertEqual(sortie["resume"]["positions_invalides_ignorees"], 1)

    def test_doublon_de_position_ignore(self):
        sortie = self._run()
        self.assertEqual(sortie["resume"]["doublons_fen_ignores"], 1)
        fens_evidents = [e["fen"] for e in sortie["evidents"]]
        # Un seul exemplaire malgré les deux entrées (colA et colH) partageant la même FEN
        self.assertEqual(
            fens_evidents.count("r1bk3r/ppp2ppp/2n5/3q4/8/2N2N2/PPPP1PPP/R1B1KB1R w KQ - 0 1"),
            1,
        )

    def test_seuils_modifiables_en_ligne_de_commande(self):
        # Avec un seuil "évident" porté à 1000, les deux pièces pendantes
        # (écart ~780-810) ne doivent plus être classées "évidentes".
        sortie = self._run(extra_argv=["--seuil-evident", "1000", "--n-evidents", "9", "--n-discutables", "0"])
        self.assertEqual(len(sortie["evidents"]), 0)

    # -- Quotas, équilibre des camps, pénurie ----------------------------

    def test_equilibre_blancs_noirs_evidents(self):
        sortie = self._run(extra_argv=["--n-evidents", "2", "--n-discutables", "0"])
        camps = sorted(e["camp"] for e in sortie["evidents"])
        self.assertEqual(camps, ["blancs", "noirs"])

    def test_au_plus_une_position_par_partie(self):
        sortie = self._run(extra_argv=["--n-evidents", "0", "--n-discutables", "9"])
        parties = [d["partie_id"] for d in sortie["discutables"] if d["partie_id"]]
        self.assertEqual(len(parties), len(set(parties)))

    def test_penurie_signalee_sans_completer_hors_critere(self):
        sortie = self._run(extra_argv=["--n-evidents", "3", "--n-discutables", "9"])
        self.assertLess(sortie["resume"]["evidents"]["trouve"], sortie["resume"]["evidents"]["demande"])
        self.assertLess(sortie["resume"]["discutables"]["trouve"], sortie["resume"]["discutables"]["demande"])
        # Seulement 2 positions "évidentes" existent réellement dans le jeu de test
        self.assertEqual(len(sortie["evidents"]), 2)

    # -- Déterminisme et moteur -------------------------------------------

    def test_stabilite_entre_deux_executions(self):
        sortie1 = self._run(output_name="sortie1.json", extra_argv=["--n-evidents", "2", "--n-discutables", "2"])
        sortie2 = self._run(output_name="sortie2.json", extra_argv=["--n-evidents", "2", "--n-discutables", "2"])
        self.assertEqual(sortie1, sortie2)

    def test_moteur_ferme_meme_apres_une_erreur_pendant_lanalyse(self):
        """Un seul processus Stockfish pour toute l'exécution, fermé
        proprement même si l'analyse plante en cours de route (issue #143,
        point 6)."""
        real_engine = sc.find_stockfish()
        self.assertIsNotNone(real_engine)

        import chess.engine as chess_engine_module

        vrai_popen_uci = chess_engine_module.SimpleEngine.popen_uci

        class _MoteurQuiPlanteApresUnAppel:
            def __init__(self, moteur_reel):
                self._reel = moteur_reel
                self._appels = 0
                self.quit_appele = False

            def analyse(self, *args, **kwargs):
                self._appels += 1
                if self._appels > 1:
                    raise RuntimeError("panne Stockfish simulée")
                return self._reel.analyse(*args, **kwargs)

            def quit(self):
                self.quit_appele = True
                self._reel.quit()

        moteurs_crees = []

        def _fabrique_moteur_qui_plante(*args, **kwargs):
            reel = vrai_popen_uci(*args, **kwargs)
            faux = _MoteurQuiPlanteApresUnAppel(reel)
            moteurs_crees.append(faux)
            return faux

        with patch.object(chess_engine_module.SimpleEngine, "popen_uci", staticmethod(_fabrique_moteur_qui_plante)):
            sortie = self._run(extra_argv=["--n-evidents", "2", "--n-discutables", "2"])

        self.assertEqual(len(moteurs_crees), 1)  # un seul processus pour toute l'exécution
        self.assertTrue(moteurs_crees[0].quit_appele)
        # L'erreur en cours d'analyse est signalée, pas silencieuse
        self.assertEqual(sortie["resume"]["candidats_bruts"], 9)


if __name__ == "__main__":
    unittest.main()
