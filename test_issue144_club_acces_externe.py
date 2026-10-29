"""
test_issue144_club_acces_externe.py — ChessCoach (issue #144)

Tests de l'entrée club dédiée (app_club.py) : jeton obligatoire (absent/
faux/valide), 404 « par construction » sur toute route hors club (y
compris quand un jeton valide est fourni), refus de construire
l'application si CLUB_JETON ou CLUB_ANTHROPIC_API_KEY est absente, clé
Anthropic dédiée jamais remplacée par la clé principale, mode debug
désactivé.

Utilise app_club.creer_app_club(...).test_client() (comme
test_issue142_page_club.py utilise app.app.test_client()) — aucun
processus serveur réel n'est lancé par ces tests (ni app_club.run, ni
tailscale funnel), donc rien à arrêter après coup.

Ce fichier importe app.py (via app_club.py) comme test_issue128.py/
test_issue134.py/test_issue135.py/test_issue137_signe_eval_lichess.py/
test_issue139_mode_serie.py/test_issue140_mode_serie_ia_arriere_plan.py/
test_issue141_golden_master.py/test_issue142_page_club.py : ne JAMAIS
l'exécuter dans le même process que l'un de ces fichiers — invoquer
séparément :
    python3 -m unittest test_issue144_club_acces_externe
"""

import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

from engine_stockfish import find_stockfish
from test_issue128 import _patch_config_paths_vers_tmp, _restaure_config_paths


class TestAccesExterneClub(unittest.TestCase):
    """Fait tourner le VRAI code de app_club.py (filtre de jeton, routes
    déléguées à app.py, clé API dédiée) via le client de test Flask."""

    JETON = "jeton-de-test-issue144"
    CLE_CLUB = "fake-club-anthropic-key-issue144"

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
        cls.app_principale = cls.app_club_module.app_principale
        cls.club = cls.app_club_module.creer_app_club(
            club_jeton=cls.JETON, club_api_key=cls.CLE_CLUB,
        )
        cls.client = cls.club.test_client()

    @classmethod
    def tearDownClass(cls):
        # Arrête explicitement les instances Stockfish AVANT la fin du
        # process (issue #144, point 7 : « pas de processus laissé en
        # suspens ») — s'appuyer uniquement sur atexit.register(...) dans
        # app.py ne suffit PAS : à la fermeture de l'interpréteur, Python
        # attend la fin des threads non-démons des moteurs AVANT d'exécuter
        # les callbacks atexit, ce qui bloque indéfiniment tant que
        # engine_manager.quit() n'a pas déjà été appelé explicitement (bug
        # préexistant, reproductible aussi avec test_issue142_page_club.py,
        # hors périmètre de cette issue — seul ce fichier de test l'évite
        # ici en appelant quit() explicitement avant la fin du process).
        if cls.app_principale.engine_manager:
            cls.app_principale.engine_manager.quit()
        _restaure_config_paths(cls._config_module, cls._anciens_config)
        cls._tmp.cleanup()

    def setUp(self):
        try:
            self.app_principale.config.CLUB_AVIS_COMPTEUR_PATH.unlink()
        except FileNotFoundError:
            pass
        with self.app_principale._club_appels_lock:
            self.app_principale._club_appels_en_cours = 0

    # -- Jeton : absent / faux / valide --------------------------------------

    def test_jeton_absent_recoit_404(self):
        reponse = self.client.get("/club")
        self.assertEqual(reponse.status_code, 404)

    def test_jeton_faux_recoit_404(self):
        reponse = self.client.get("/club?t=mauvais-jeton")
        self.assertEqual(reponse.status_code, 404)

    def test_jeton_valide_sert_la_page(self):
        reponse = self.client.get(f"/club?t={self.JETON}")
        self.assertEqual(reponse.status_code, 200)
        self.assertIn(b"club", reponse.data.lower())

    def test_jeton_valide_via_entete_pour_api_eval(self):
        fen = "4k3/8/8/8/3Q4/8/8/4K3 w - - 0 1"
        reponse = self.client.post(
            "/api/club/eval", json={"fen": fen},
            headers={"X-Club-Jeton": self.JETON},
        )
        self.assertEqual(reponse.status_code, 200, reponse.get_json())

    def test_jeton_absent_sur_api_recoit_404_pas_400(self):
        # Même un corps JSON par ailleurs valide ne doit jamais passer le
        # filtre de jeton : refusé avant la validation de la requête.
        reponse = self.client.post("/api/club/eval", json={"fen": "x"})
        self.assertEqual(reponse.status_code, 404)

    def test_404_identique_a_une_route_inexistante(self):
        # Même contenu que la 404 "route inexistante" (issue #144, point 2 :
        # « aucune indication sur la raison » du refus).
        reponse_jeton_invalide = self.client.get("/club?t=faux")
        reponse_route_inexistante = self.client.get(
            f"/une/route/qui/n/existe/pas?t={self.JETON}"
        )
        self.assertEqual(reponse_jeton_invalide.status_code, 404)
        self.assertEqual(reponse_route_inexistante.status_code, 404)
        self.assertEqual(reponse_jeton_invalide.data, reponse_route_inexistante.data)

    # -- 404 « par construction » sur toute route hors club ------------------

    def test_route_hors_club_404_meme_avec_jeton_valide(self):
        for route in ("/", "/club.html", "/api/exercise", "/static/club.html"):
            with self.subTest(route=route):
                reponse = self.client.get(f"{route}?t={self.JETON}")
                self.assertEqual(reponse.status_code, 404)

    # -- Refus de construire sans les deux variables --------------------------

    def test_refuse_de_construire_sans_jeton(self):
        with self.assertRaises(RuntimeError):
            self.app_club_module.creer_app_club(club_jeton="", club_api_key=self.CLE_CLUB)

    def test_refuse_de_construire_sans_cle_api_dediee(self):
        with self.assertRaises(RuntimeError):
            self.app_club_module.creer_app_club(club_jeton=self.JETON, club_api_key="")

    def test_jeton_vide_jamais_un_acces_ouvert_par_defaut(self):
        # Garde-fou direct : un jeton vide (donc aucun jeton fourni non
        # plus, "" == "") ne doit JAMAIS laisser passer une requête — ce
        # qui est garanti ici par le refus de construction lui-même.
        with self.assertRaises(RuntimeError):
            self.app_club_module.creer_app_club(club_jeton="", club_api_key=self.CLE_CLUB)

    def test_variables_environnement_absentes_refusent(self):
        anciennes = {}
        for nom in ("CLUB_JETON", "CLUB_ANTHROPIC_API_KEY"):
            anciennes[nom] = os.environ.pop(nom, None)
        try:
            with self.assertRaises(RuntimeError):
                self.app_club_module.creer_app_club()
        finally:
            for nom, valeur in anciennes.items():
                if valeur is not None:
                    os.environ[nom] = valeur

    # -- Clé API dédiée, jamais la clé principale -----------------------------

    def test_cle_api_dediee_jamais_la_cle_principale(self):
        ancienne_cle_principale = self.app_principale.config.LLM_API_KEY
        self.app_principale.config.LLM_API_KEY = "cle-principale-ne-doit-jamais-servir"
        self.addCleanup(
            setattr, self.app_principale.config, "LLM_API_KEY", ancienne_cle_principale
        )
        self.assertEqual(self.app_principale._club_get_llm_api_key(), self.CLE_CLUB)

    def test_port_5000_sans_override_utilise_toujours_la_cle_principale(self):
        # Simule le port 5000 lancé seul (jamais app_club.py importé) :
        # _club_llm_api_key reste à None => repli sur config.LLM_API_KEY,
        # exactement le comportement d'avant l'issue #144.
        ancien_override = self.app_principale._club_llm_api_key
        ancienne_cle_principale = self.app_principale.config.LLM_API_KEY
        self.app_principale._club_llm_api_key = None
        self.app_principale.config.LLM_API_KEY = "cle-principale-du-port-5000"

        def _restaurer():
            self.app_principale._club_llm_api_key = ancien_override
            self.app_principale.config.LLM_API_KEY = ancienne_cle_principale
        self.addCleanup(_restaurer)

        self.assertEqual(
            self.app_principale._club_get_llm_api_key(), "cle-principale-du-port-5000"
        )

    # -- Mode debug désactivé --------------------------------------------------

    def test_mode_debug_desactive(self):
        self.assertFalse(self.club.debug)
        self.assertFalse(self.club.config["DEBUG"])
        self.assertFalse(self.club.config["TESTING"])


if __name__ == "__main__":
    unittest.main()
