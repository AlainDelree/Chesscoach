"""
test_issue149_club_routes_app_principale.py — ChessCoach (issue #149)

Une revue d'authentification en lecture seule a montré que les 4 routes
club (`/club`, `/api/club/avis`, `/api/club/eval`, `/api/club/jugement`)
restaient enregistrées sur l'application principale (`app.py`/port 5000,
via les décorateurs `@app.route`), en plus de l'entrée club dédiée
(`app_club.py`) qui les sert derrière un jeton obligatoire — si bien que
ces quatre adresses répondaient SANS jeton sur le port 5000, contrairement
à l'invariant documenté (« le club n'est accessible qu'avec le jeton »).

Issue #149 : les décorateurs `@app.route` de ces quatre fonctions ont été
retirés de `app.py` — elles restent des fonctions ordinaires, réutilisées
SANS modification par `app_club.creer_app_club` (`add_url_rule`). Ce
fichier vérifie :

1. Les 4 adresses répondent désormais le 404 standard de Flask sur
   l'application principale (`app.app.test_client()`), sans jeton ni
   aucun autre mécanisme de détection.
2. L'entrée club (`app_club.creer_app_club(...)`) les sert toujours
   normalement, avec un jeton de test — comportement inchangé par cette
   issue.
3. Aucune régression sur le reste de l'application principale : une autre
   route HTTP (`/`) et un événement Socket.IO existant (`usage_get`)
   continuent de répondre normalement.

Utilise app_club.creer_app_club(...).test_client() et
app_club.app_principale.app.test_client() (comme
test_issue144_club_acces_externe.py/test_issue146_club_securite_reseau.py) :
aucun processus serveur réel n'est lancé par ce fichier.

Ce fichier importe app.py (via app_club.py) comme test_issue128.py/
test_issue142_page_club.py/test_issue144_club_acces_externe.py/
test_issue146_club_securite_reseau.py : ne JAMAIS l'exécuter dans le même
process que l'un de ces fichiers — invoquer séparément :
    python3 -m unittest test_issue149_club_routes_app_principale
"""

import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from engine_stockfish import find_stockfish
from test_issue128 import _patch_config_paths_vers_tmp, _restaure_config_paths


class TestRoutesClubAppPrincipale(unittest.TestCase):
    """Vérifie que les 4 routes club n'existent plus que sur l'entrée club,
    et que le reste de l'application principale (autres routes HTTP,
    événements Socket.IO) n'est pas affecté par leur retrait."""

    JETON = "jeton-de-test-issue149"
    CLE_CLUB = "fake-club-anthropic-key-issue149"

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
        cls.port_club = cls.club.test_client()
        cls.socketio_client = cls.app_module.socketio.test_client(cls.app_module.app)

    @classmethod
    def tearDownClass(cls):
        # Arrêt explicite du moteur Stockfish AVANT la fin du process (même
        # précaution que test_issue144_club_acces_externe.py/
        # test_issue146_club_securite_reseau.py) : sans cet appel, Python
        # attend indéfiniment la fin des threads non-démons du moteur avant
        # d'exécuter les callbacks atexit de app.py.
        if cls.app_module.engine_manager:
            cls.app_module.engine_manager.quit()
        _restaure_config_paths(cls._config_module, cls._anciens_config)
        cls._tmp.cleanup()

    def setUp(self):
        try:
            self.app_module.config.CLUB_AVIS_COMPTEUR_PATH.unlink()
        except FileNotFoundError:
            pass
        with self.app_module._club_appels_lock:
            self.app_module._club_appels_en_cours = 0

    def _patch_claude_rapide(self, texte: str = "Réponse simulée du coach (issue #149)."):
        captures = []

        def _faux_call_claude(prompt_sys, messages, api_key, model, usage_path=None,
                               timeout_s=90, temperature=None):
            captures.append(prompt_sys)
            return texte

        patcher = patch.object(self.app_module.llm_coach, "_call_claude", side_effect=_faux_call_claude)
        patcher.start()
        self.addCleanup(patcher.stop)
        return captures

    # -- 1. 404 standard sur les 4 adresses, côté application principale ----

    def test_page_club_404_sur_application_principale(self):
        reponse = self.port_5000.get("/club")
        self.assertEqual(reponse.status_code, 404)

    def test_api_club_avis_404_sur_application_principale(self):
        reponse = self.port_5000.post(
            "/api/club/avis",
            json={"fen": self.FEN_GAFFE_BLANCS, "coup": self.UCI_GAFFE_BLANCS},
        )
        self.assertEqual(reponse.status_code, 404)

    def test_api_club_eval_404_sur_application_principale(self):
        reponse = self.port_5000.post("/api/club/eval", json={"fen": self.FEN_GAFFE_BLANCS})
        self.assertEqual(reponse.status_code, 404)

    def test_api_club_jugement_404_sur_application_principale(self):
        reponse = self.port_5000.post(
            "/api/club/jugement", json={"log_id": "abc123", "jugement": "accord"},
        )
        self.assertEqual(reponse.status_code, 404)

    def test_404_identique_a_une_route_vraiment_inexistante(self):
        # Même contenu que n'importe quelle URL inexistante — aucune
        # indication que ces quatre adresses aient jamais existé sur
        # l'application principale.
        reponse_club = self.port_5000.get("/club")
        reponse_inexistante = self.port_5000.get("/une/route/qui/n/existe/pas")
        self.assertEqual(reponse_club.status_code, 404)
        self.assertEqual(reponse_inexistante.status_code, 404)
        self.assertEqual(reponse_club.data, reponse_inexistante.data)

    # -- 2. Accès normal, inchangé, côté entrée club -------------------------

    def test_page_club_servie_normalement_par_lentree_club(self):
        reponse = self.port_club.get(f"/club?t={self.JETON}")
        self.assertEqual(reponse.status_code, 200)
        self.assertIn(b"club", reponse.data.lower())

    def test_api_club_avis_fonctionne_sur_lentree_club(self):
        self._patch_claude_rapide()
        reponse = self.port_club.post(
            "/api/club/avis",
            json={"fen": self.FEN_GAFFE_BLANCS, "coup": self.UCI_GAFFE_BLANCS},
            headers={"X-Club-Jeton": self.JETON},
        )
        self.assertEqual(reponse.status_code, 200, reponse.get_json())
        self.assertEqual(reponse.get_json()["verdict_qualite_officiel"], "gaffe")

    def test_api_club_eval_fonctionne_sur_lentree_club(self):
        reponse = self.port_club.post(
            "/api/club/eval", json={"fen": self.FEN_GAFFE_BLANCS},
            headers={"X-Club-Jeton": self.JETON},
        )
        self.assertEqual(reponse.status_code, 200, reponse.get_json())
        self.assertTrue(reponse.get_json()["meilleurs_coups"])

    def test_api_club_jugement_fonctionne_sur_lentree_club(self):
        reponse = self.port_club.post(
            "/api/club/jugement", json={"log_id": "abc123", "jugement": "accord"},
            headers={"X-Club-Jeton": self.JETON},
        )
        self.assertEqual(reponse.status_code, 200, reponse.get_json())
        self.assertIn("id", reponse.get_json())

    def test_entree_club_refuse_toujours_sans_jeton(self):
        # Le retrait des routes de l'application principale ne touche en
        # rien le filtre de jeton de l'entrée club elle-même.
        reponse = self.port_club.get("/club")
        self.assertEqual(reponse.status_code, 404)

    # -- 3. Non-régression : reste de l'application principale --------------

    def test_route_racine_toujours_servie_par_application_principale(self):
        reponse = self.port_5000.get("/")
        self.assertEqual(reponse.status_code, 200)

    def test_evenement_usage_get_toujours_fonctionnel(self):
        self.socketio_client.get_received()
        self.socketio_client.emit("usage_get")
        recus = self.socketio_client.get_received()
        evt = next((e for e in recus if e["name"] == "usage_data"), None)
        self.assertIsNotNone(evt, "usage_data attendu en réponse à usage_get")


if __name__ == "__main__":
    unittest.main()
