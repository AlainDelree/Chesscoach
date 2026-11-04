"""
test_issue146_club_securite_reseau.py — ChessCoach (issue #146)

Tests pour :
1. La liaison réseau par défaut de l'entrée club (`app_club._club_host_par_defaut`)
   — SANS lancer de vrai serveur (la fonction est testée directement).
2. Le refus explicite (415/400) des requêtes non JSON, vides ou illisibles
   sur les 3 routes POST du club (`/api/club/avis`, `/api/club/eval`,
   `/api/club/jugement`), sur les DEUX entrées (`app.py`/port 5000 ET
   `app_club.py`/port 5001) — sans modification d'état (compteur
   quotidien, journal des jugements) ni appel IA/Stockfish.
3. La non-régression des requêtes valides sur ces mêmes routes.

Utilise app.app.test_client() et app_club.creer_app_club(...).test_client()
(comme test_issue142_page_club.py et test_issue144_club_acces_externe.py) :
aucun processus serveur réel n'est lancé par ce fichier. Une seule classe
de test, avec un seul import de app_club (donc de app.py) dans
setUpClass, APRÈS le patch des chemins de configuration vers un dossier
temporaire — importer app_club une deuxième fois ailleurs (ex. dans une
classe séparée exécutée avant) importerait app.py avec ses VRAIS chemins
de données, cf. la garde dans setUpClass.

Ce fichier importe app.py (via app_club.py) comme test_issue128.py/
test_issue142_page_club.py/test_issue144_club_acces_externe.py : ne JAMAIS
l'exécuter dans le même process que l'un de ces fichiers — invoquer
séparément :
    python3 -m unittest test_issue146_club_securite_reseau
"""

import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from engine_stockfish import find_stockfish
from test_issue128 import _patch_config_paths_vers_tmp, _restaure_config_paths


class TestRefusRequetesNonJson(unittest.TestCase):
    """Fait tourner le VRAI code des 3 routes POST du club, sur les deux
    entrées (`app.py` et `app_club.py`), avec des corps non JSON, vides ou
    illisibles — vérifie le refus explicite, l'absence d'appel IA/Stockfish
    et l'absence de modification d'état, puis la non-régression d'une
    requête valide."""

    JETON = "jeton-de-test-issue146"
    CLE_CLUB = "fake-club-anthropic-key-issue146"

    FEN_GAFFE_BLANCS = "4k3/8/2n5/8/3Q4/8/8/4K3 w - - 0 1"
    UCI_GAFFE_BLANCS = "e1d1"  # Roi e1-d1 : ignore la Dame en prise.

    @classmethod
    def setUpClass(cls):
        stockfish_path = find_stockfish()
        if not stockfish_path:
            raise RuntimeError(
                "Stockfish introuvable sur cette machine : ce test doit "
                "échouer plutôt que d'être sauté (même convention que "
                "test_issue142_page_club.py)."
            )

        cls._tmp = tempfile.TemporaryDirectory()
        tmp_dir = Path(cls._tmp.name)

        import config as config_module
        cls._config_module = config_module
        cls._anciens_config = _patch_config_paths_vers_tmp(config_module, tmp_dir)
        cls._anciens_config["CLUB_AVIS_COMPTEUR_PATH"] = config_module.CLUB_AVIS_COMPTEUR_PATH
        cls._anciens_config["CLUB_JUGEMENTS_LOG_PATH"] = config_module.CLUB_JUGEMENTS_LOG_PATH
        config_module.CLUB_AVIS_COMPTEUR_PATH = tmp_dir / "club_avis_compteur.tmp.json"
        config_module.CLUB_JUGEMENTS_LOG_PATH = tmp_dir / "logs" / "club_jugements.tmp.log"

        if "app" in sys.modules or "app_club" in sys.modules:
            raise RuntimeError(
                "app.py ou app_club.py était déjà importé avant ce test : "
                "l'isolation des chemins de données ne peut plus être "
                "garantie (voir l'en-tête de test_issue142_page_club.py)."
            )
        cls.app_club_module = importlib.import_module("app_club")
        cls.app_module = cls.app_club_module.app_principale
        cls.club = cls.app_club_module.creer_app_club(
            club_jeton=cls.JETON, club_api_key=cls.CLE_CLUB,
        )
        cls.port_5000 = cls.app_module.app.test_client()
        cls.port_5001 = cls.club.test_client()

    @classmethod
    def tearDownClass(cls):
        # Arrêt explicite des moteurs Stockfish AVANT la fin du process
        # (issue #146, même précaution que test_issue144_club_acces_externe.py).
        if cls.app_module.engine_manager:
            cls.app_module.engine_manager.quit()
        _restaure_config_paths(cls._config_module, cls._anciens_config)
        cls._tmp.cleanup()

    def setUp(self):
        self._reset_etat_avis()
        self._ancienne_valeur_ouvrir_reseau = os.environ.pop("CLUB_OUVRIR_RESEAU", None)

    def tearDown(self):
        if self._ancienne_valeur_ouvrir_reseau is None:
            os.environ.pop("CLUB_OUVRIR_RESEAU", None)
        else:
            os.environ["CLUB_OUVRIR_RESEAU"] = self._ancienne_valeur_ouvrir_reseau

    # -- Liaison réseau par défaut de l'entrée club (sans vrai serveur) -----

    def test_host_local_par_defaut_sans_variable(self):
        self.assertEqual(self.app_club_module._club_host_par_defaut(), "127.0.0.1")

    def test_host_reste_local_pour_toute_autre_valeur(self):
        for valeur in ("0", "", "oui", "true", "2"):
            os.environ["CLUB_OUVRIR_RESEAU"] = valeur
            with self.subTest(valeur=valeur):
                self.assertEqual(self.app_club_module._club_host_par_defaut(), "127.0.0.1")

    def test_host_ouvre_sur_toutes_interfaces_si_variable_vaut_1(self):
        os.environ["CLUB_OUVRIR_RESEAU"] = "1"
        self.assertEqual(self.app_club_module._club_host_par_defaut(), "0.0.0.0")

    def _reset_etat_avis(self) -> None:
        try:
            self.app_module.config.CLUB_AVIS_COMPTEUR_PATH.unlink()
        except FileNotFoundError:
            pass
        with self.app_module._club_appels_lock:
            self.app_module._club_appels_en_cours = 0

    def _patch_claude_rapide(self, texte: str = "Réponse simulée du coach (issue #146)."):
        captures = []

        def _faux_call_claude(prompt_sys, messages, api_key, model, usage_path=None,
                               timeout_s=90, temperature=None):
            captures.append(prompt_sys)
            return texte

        patcher = patch.object(self.app_module.llm_coach, "_call_claude", side_effect=_faux_call_claude)
        patcher.start()
        self.addCleanup(patcher.stop)
        return captures

    def _entrees(self):
        """Les deux entrées équivalentes pour une route club : (nom, client,
        en-têtes additionnels requis par cette entrée)."""
        return [
            ("port_5000", self.port_5000, {}),
            ("port_5001", self.port_5001, {"X-Club-Jeton": self.JETON}),
        ]

    # -- Content-Type non JSON (415) sur les 3 routes, sur les 2 entrées ----

    def test_content_type_non_json_refuse_415(self):
        for route in ("/api/club/avis", "/api/club/eval", "/api/club/jugement"):
            for nom, client, entetes in self._entrees():
                with self.subTest(route=route, entree=nom):
                    captures = self._patch_claude_rapide()
                    reponse = client.post(
                        route, data="fen=abc", content_type="application/x-www-form-urlencoded",
                        headers=entetes,
                    )
                    self.assertEqual(reponse.status_code, 415)
                    self.assertEqual(reponse.get_json()["erreur"], "content_type_invalide")
                    self.assertEqual(len(captures), 0, "aucun appel IA pour un Content-Type non JSON")
                    self._verifier_aucune_mutation_etat()

    # -- Corps vide ou illisible (400) sur les 3 routes, sur les 2 entrées --

    def test_corps_vide_refuse_400(self):
        for route in ("/api/club/avis", "/api/club/eval", "/api/club/jugement"):
            for nom, client, entetes in self._entrees():
                with self.subTest(route=route, entree=nom):
                    captures = self._patch_claude_rapide()
                    reponse = client.post(
                        route, data="", content_type="application/json", headers=entetes,
                    )
                    self.assertEqual(reponse.status_code, 400)
                    self.assertEqual(reponse.get_json()["erreur"], "corps_json_invalide")
                    self.assertEqual(len(captures), 0)
                    self._verifier_aucune_mutation_etat()

    def test_corps_illisible_refuse_400(self):
        for route in ("/api/club/avis", "/api/club/eval", "/api/club/jugement"):
            for nom, client, entetes in self._entrees():
                with self.subTest(route=route, entree=nom):
                    captures = self._patch_claude_rapide()
                    reponse = client.post(
                        route, data="{ceci n'est pas du json", content_type="application/json",
                        headers=entetes,
                    )
                    self.assertEqual(reponse.status_code, 400)
                    self.assertEqual(reponse.get_json()["erreur"], "corps_json_invalide")
                    self.assertEqual(len(captures), 0)
                    self._verifier_aucune_mutation_etat()

    def test_json_non_objet_refuse_400(self):
        # Un JSON syntaxiquement valide mais qui n'est pas un objet (ex. une
        # liste) ne doit jamais atteindre `data.get(...)`.
        for route in ("/api/club/avis", "/api/club/eval", "/api/club/jugement"):
            for nom, client, entetes in self._entrees():
                with self.subTest(route=route, entree=nom):
                    reponse = client.post(route, json=[1, 2, 3], headers=entetes)
                    self.assertEqual(reponse.status_code, 400)
                    self.assertEqual(reponse.get_json()["erreur"], "corps_json_invalide")

    def _verifier_aucune_mutation_etat(self) -> None:
        self.assertEqual(
            self.app_module._club_charger_compteur().get("count", 0), 0,
            "une requête refusée ne doit jamais consommer la limite quotidienne",
        )
        self.assertFalse(
            self.app_module.config.CLUB_JUGEMENTS_LOG_PATH.exists(),
            "une requête refusée ne doit jamais écrire dans le journal des jugements",
        )

    # -- Le filtre de jeton de app_club.py reste prioritaire -----------------

    def test_jeton_invalide_prioritaire_sur_le_refus_json(self):
        # Sur le port 5001, un jeton absent/faux doit recevoir le 404 « par
        # construction » AVANT même que le corps de la requête soit examiné
        # — jamais un 415/400 qui révélerait l'existence de la route.
        reponse = self.port_5001.post(
            "/api/club/eval", data="pas du json", content_type="text/plain",
        )
        self.assertEqual(reponse.status_code, 404)

    # -- Non-régression : requêtes valides inchangées ------------------------

    def test_avis_valide_inchange_sur_les_deux_entrees(self):
        for nom, client, entetes in self._entrees():
            with self.subTest(entree=nom):
                self._reset_etat_avis()  # repartir d'un compteur à zéro entre les deux entrées
                self._patch_claude_rapide()
                reponse = client.post(
                    "/api/club/avis",
                    json={"fen": self.FEN_GAFFE_BLANCS, "coup": self.UCI_GAFFE_BLANCS},
                    headers=entetes,
                )
                self.assertEqual(reponse.status_code, 200, reponse.get_json())
                corps = reponse.get_json()
                self.assertIn("text", corps)
                self.assertEqual(corps["verdict_qualite_officiel"], "gaffe")

    def test_eval_valide_inchange_sur_les_deux_entrees(self):
        fen = "4k3/8/8/8/3Q4/8/8/4K3 w - - 0 1"
        for nom, client, entetes in self._entrees():
            with self.subTest(entree=nom):
                reponse = client.post("/api/club/eval", json={"fen": fen}, headers=entetes)
                self.assertEqual(reponse.status_code, 200, reponse.get_json())
                self.assertTrue(reponse.get_json()["meilleurs_coups"])

    def test_jugement_valide_inchange_sur_les_deux_entrees(self):
        for nom, client, entetes in self._entrees():
            with self.subTest(entree=nom):
                try:
                    self.app_module.config.CLUB_JUGEMENTS_LOG_PATH.unlink()
                except FileNotFoundError:
                    pass
                reponse = client.post(
                    "/api/club/jugement",
                    json={"log_id": "abc123", "jugement": "accord"},
                    headers=entetes,
                )
                self.assertEqual(reponse.status_code, 200, reponse.get_json())
                self.assertIn("id", reponse.get_json())
                self.assertTrue(self.app_module.config.CLUB_JUGEMENTS_LOG_PATH.exists())


if __name__ == "__main__":
    unittest.main()
