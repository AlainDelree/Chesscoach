"""
test_issue139_mode_serie.py — ChessCoach (issue #139, suite #125)

Tests pour le mode série, étape 1 (interrupteur mémorisé côté navigateur,
verdict Stockfish affiché en une ligne) : AUCUN appel aux IA (ni Claude ni
Mistral) quand mode_serie est transmis par le client avec "exercise_answer",
pour les deux sources « Mes erreurs » et « Problèmes Lichess » ; comportement
strictement inchangé (appel aux IA, exercise_comment classique) quand
mode_serie est absent ou faux.

Exécute le VRAI gestionnaire de réponse d'exercice (app.on_exercise_answer /
app._on_exercise_answer_lichess) via le client de test Flask-SocketIO, en
réutilisant l'infrastructure d'isolation de test_issue128.py (chemins de
données redirigés vers un dossier temporaire — AUCUN fichier personnel
d'Alain n'est lu ni écrit par ce test). Les appels aux API Claude/Mistral
sont remplacés par des simulations (jamais d'appel réseau réel).

Issue #139, vérification (d) : aucun test de ce fichier n'est ignoré,
désactivé ou conditionné par une variable d'environnement — Stockfish
absent de la machine fait ÉCHOUER setUpClass (RuntimeError), il n'est
jamais sauté (contrairement à @unittest.skipUnless, utilisé par les issues
précédentes mais volontairement PAS repris ici).

Ce fichier importe app.py comme test_issue128.py/test_issue134.py/
test_issue135.py/test_issue137_signe_eval_lichess.py : ne JAMAIS l'exécuter
dans le même process que l'un de ces fichiers (même contrainte, voir leurs
en-têtes) — invoquer séparément :
    python3 -m unittest test_issue139_mode_serie
"""

import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from engine_stockfish import find_stockfish
from test_issue128 import _patch_config_paths_vers_tmp, _restaure_config_paths


class TestExerciseAnswerSocketIOModeSerie(unittest.TestCase):
    """Fait tourner app.on_exercise_answer / app._on_exercise_answer_lichess
    via un VRAI client de test Flask-SocketIO (même technique que
    test_issue128.py tâche 5c), API Claude/Mistral simulées."""

    @classmethod
    def setUpClass(cls):
        # Issue #139, vérification (d) : une dépendance manquante (ici
        # Stockfish) fait ÉCHOUER ce test, jamais le sauter.
        stockfish_path = find_stockfish()
        if not stockfish_path:
            raise RuntimeError(
                "Stockfish introuvable sur cette machine : ce test doit "
                "échouer plutôt que d'être sauté (issue #139, vérification d)."
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

    def setUp(self):
        self.client.get_received()
        self.app_module._current_exercise = None

    # Dame blanche en d4 attaquée par le Cavalier noir en c6 : jouer un
    # coup de Roi qui l'ignore est une gaffe nette et déterministe (vérifié
    # au préalable avec Stockfish : qualite_officielle="gaffe", delta_cp
    # plafonné à 1000, meilleur_coup="d4e4"/Qe4+) — bien plus fiable qu'un
    # coup "probablement pas optimal" dans une position déjà écrasante, où
    # Stockfish peut classer plusieurs coups comme équivalents au meilleur.
    FEN_GAFFE = "4k3/8/2n5/8/3Q4/8/8/4K3 w - - 0 1"
    UCI_GAFFE = "e1d1"       # Roi e1-d1 : ignore la Dame en prise.
    UCI_MEILLEUR_COUP = "d4e4"  # Qe4+ : sauve la Dame en donnant échec.

    def _poser_exercice(self, source: str, uci_solution: str = None):
        self.app_module._current_exercise = {
            "source": source,
            "fen_avant": self.FEN_GAFFE,
            "camp_alain": "blancs",
            "coup_joue_san": "Kd1", "coup_joue_uci": "e1d1",
            "meilleur_coup_san": "", "meilleur_coup_uci": "",
            # Lichess : solution indépendante du coup proposé pour ces
            # tests (seule la ligne de verdict série est vérifiée, jamais
            # coup_reussi/l'historique).
            "solution": [uci_solution or self.UCI_MEILLEUR_COUP],
            "categorie_tirage": "mat_en_1" if source == "lichess" else None,
            "cle_historique": "lichess:test139" if source == "lichess" else None,
            "niveau_tirage": 1000, "rating": 1000, "themes": [],
        }

    def _patch_ia(self):
        """Remplace les appels Claude/Mistral par des simulations qui
        comptent leurs appels — jamais d'appel réseau réel. Retourne un
        dict {"claude": int, "mistral": int} mis à jour en direct."""
        compteurs = {"claude": 0, "mistral": 0}

        def _faux_call_claude(prompt_sys, messages, api_key, model, usage_path=None,
                               timeout_s=90, temperature=None):
            compteurs["claude"] += 1
            return "Réponse simulée du coach pour le test issue #139."

        def _faux_get_mistral_response(messages, context, cfg):
            compteurs["mistral"] += 1
            return "Réponse Mistral simulée pour le test issue #139.", None, "fake-log-id", []

        p1 = patch.object(self.app_module.llm_coach, "_call_claude", side_effect=_faux_call_claude)
        p1.start()
        self.addCleanup(p1.stop)
        p2 = patch.object(self.app_module.llm_coach, "get_mistral_response", side_effect=_faux_get_mistral_response)
        p2.start()
        self.addCleanup(p2.stop)
        return compteurs

    def _activer_mistral_pour_ce_test(self):
        """Mistral est désactivé par défaut par _patch_config_paths_vers_tmp
        (MISTRAL_API_KEY = "") — l'activer ici (clé factice) pour vérifier
        que le mode série bloque bien aussi cet appel, pas seulement Claude,
        même quand Mistral serait normalement sollicité (issue #113)."""
        ancienne = self.app_module.config.MISTRAL_API_KEY
        self.app_module.config.MISTRAL_API_KEY = "fake-mistral-key-issue139"
        self.addCleanup(setattr, self.app_module.config, "MISTRAL_API_KEY", ancienne)

    def _emettre(self, uci: str, exercise_id: str, mode_serie=None):
        payload = {"uci": uci, "exercise_id": exercise_id}
        if mode_serie is not None:
            payload["mode_serie"] = mode_serie
        self.client.emit("exercise_answer", payload)
        return self.client.get_received()

    @staticmethod
    def _evt(recus, nom):
        return next((e for e in recus if e["name"] == nom), None)

    # -- Mode série : zéro appel aux IA, un événement de verdict ----------

    def test_mes_erreurs_mode_serie_zero_appel_ia(self):
        self._poser_exercice("mes_erreurs")
        self._activer_mistral_pour_ce_test()
        compteurs = self._patch_ia()
        recus = self._emettre(self.UCI_GAFFE, "test139-me", mode_serie=True)

        self.assertEqual(compteurs["claude"], 0, "aucun appel Claude attendu en mode série")
        self.assertEqual(compteurs["mistral"], 0, "aucun appel Mistral attendu en mode série")
        self.assertIsNone(self._evt(recus, "exercise_comment"))
        self.assertIsNone(self._evt(recus, "exercise_mistral_comment"))
        self.assertIsNone(self._evt(recus, "exercise_error"))
        verdict = self._evt(recus, "exercise_serie_verdict")
        self.assertIsNotNone(verdict, "un événement exercise_serie_verdict est attendu")
        payload = verdict["args"][0]
        self.assertEqual(payload["exercise_id"], "test139-me")
        # Classification/perte capée (issue #125) : stables quelle que soit
        # la profondeur de recherche installée — une Dame laissée en prise
        # face à un Cavalier reste une "gaffe" avec une perte plafonnée à
        # 1000cp (cf. docs/contexte/classification_coups.md), peu importe
        # la version exacte de Stockfish sur la machine.
        self.assertEqual(payload["verdict_qualite_officiel"], "gaffe")
        self.assertEqual(payload["verdict_delta_cp"], 1000)
        # Le texte doit correspondre exactement à ce que produit la
        # fonction pure à partir de ces mêmes données (meilleur_coup peut
        # varier selon la profondeur réelle de recherche — non hardcodé ici).
        texte_attendu = self.app_module._construire_ligne_verdict_serie(
            payload["verdict_qualite_officiel"], payload["verdict_delta_cp"], payload["meilleur_coup"],
        )
        self.assertEqual(payload["text"], texte_attendu)
        self.assertTrue(payload["text"].startswith("Verdict : gaffe (perte de 1000 cp) — meilleur coup : "))
        # La perte est un nombre positif : jamais de signe +/- devant.
        self.assertNotIn("+-", payload["text"])
        self.assertNotRegex(payload["text"], r"perte de -\d")

    def test_problemes_lichess_mode_serie_zero_appel_ia(self):
        self._poser_exercice("lichess")
        self._activer_mistral_pour_ce_test()
        compteurs = self._patch_ia()
        recus = self._emettre(self.UCI_GAFFE, "test139-lichess", mode_serie=True)

        self.assertEqual(compteurs["claude"], 0)
        self.assertEqual(compteurs["mistral"], 0)
        self.assertIsNone(self._evt(recus, "exercise_comment"))
        self.assertIsNone(self._evt(recus, "exercise_error"))
        verdict = self._evt(recus, "exercise_serie_verdict")
        self.assertIsNotNone(verdict)
        payload = verdict["args"][0]
        self.assertEqual(payload["source"], "lichess")
        self.assertEqual(payload["verdict_qualite_officiel"], "gaffe")
        self.assertTrue(payload["text"].startswith("Verdict : gaffe (perte de 1000 cp)"))

    def test_mode_serie_coup_joue_est_le_meilleur_coup_pas_de_perte_zero(self):
        # Coup joué EST le meilleur coup Stockfish depuis cette position
        # (Qe4+ sauve la Dame en échec, vérifié au préalable : delta_cp=0,
        # qualite_officielle="bon") : la ligne ne doit jamais afficher
        # "(perte de 0 cp)".
        self._poser_exercice("mes_erreurs")
        self._patch_ia()
        recus = self._emettre(self.UCI_MEILLEUR_COUP, "test139-meilleur", mode_serie=True)
        verdict = self._evt(recus, "exercise_serie_verdict")
        self.assertIsNotNone(verdict)
        payload = verdict["args"][0]
        self.assertEqual(payload["verdict_delta_cp"], 0)
        self.assertEqual(payload["text"], "Verdict : bon coup — c'est le meilleur coup.")
        self.assertNotIn("perte de 0", payload["text"])

    # -- Hors mode série : comportement strictement inchangé -------------

    def test_mes_erreurs_hors_mode_serie_appelle_claude(self):
        self._poser_exercice("mes_erreurs")
        compteurs = self._patch_ia()
        recus = self._emettre(self.UCI_GAFFE, "test139-me-off", mode_serie=False)

        self.assertEqual(compteurs["claude"], 1, "exactement un appel Claude attendu hors mode série")
        self.assertIsNone(self._evt(recus, "exercise_serie_verdict"))
        self.assertIsNotNone(self._evt(recus, "exercise_comment"))

    def test_problemes_lichess_hors_mode_serie_appelle_claude(self):
        self._poser_exercice("lichess", uci_solution="g1f3")
        compteurs = self._patch_ia()
        recus = self._emettre(self.UCI_GAFFE, "test139-lichess-off", mode_serie=False)

        self.assertEqual(compteurs["claude"], 1)
        self.assertIsNone(self._evt(recus, "exercise_serie_verdict"))
        self.assertIsNotNone(self._evt(recus, "exercise_comment"))

    def test_absence_du_champ_mode_serie_equivaut_a_desactive(self):
        # Compatibilité : un client qui ne transmet pas mode_serie du tout
        # (ancien comportement) doit se comporter exactement comme
        # mode_serie=False, jamais planter.
        self._poser_exercice("mes_erreurs")
        compteurs = self._patch_ia()
        recus = self._emettre(self.UCI_GAFFE, "test139-me-absent", mode_serie=None)

        self.assertEqual(compteurs["claude"], 1)
        self.assertIsNone(self._evt(recus, "exercise_serie_verdict"))
        self.assertIsNotNone(self._evt(recus, "exercise_comment"))

    # -- Construction de la ligne de verdict (fonction pure) --------------

    def test_construire_ligne_verdict_serie_analyse_indisponible(self):
        ligne = self.app_module._construire_ligne_verdict_serie(None, None, None)
        self.assertEqual(ligne, "Verdict indisponible (analyse Stockfish indisponible).")

    def test_construire_ligne_verdict_serie_perte_positive(self):
        ligne = self.app_module._construire_ligne_verdict_serie("erreur", 150, "Qd4")
        self.assertEqual(ligne, "Verdict : erreur (perte de 150 cp) — meilleur coup : Qd4.")
        self.assertNotIn("+", ligne)
        self.assertNotIn("-150", ligne)

    def test_construire_ligne_verdict_serie_meilleur_coup(self):
        ligne = self.app_module._construire_ligne_verdict_serie("bon", 0, "Nf3")
        self.assertEqual(ligne, "Verdict : bon coup — c'est le meilleur coup.")
        self.assertNotIn("perte de 0", ligne)


if __name__ == "__main__":
    unittest.main()
