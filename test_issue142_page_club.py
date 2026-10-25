"""
test_issue142_page_club.py — ChessCoach (issue #142, suite #141, étape 2/4)

Tests pour la page « club » servie par ChessCoach et les points d'accès HTTP
qui jugent un coup quelconque (avis du coach, évaluation Stockfish seule,
jugement sur un avis, limite d'appels quotidienne et concurrence).

Exécute le VRAI code (routes Flask /club, /api/club/avis, /api/club/eval,
/api/club/jugement) via le client de test Flask (app.test_client()), en
réutilisant l'infrastructure d'isolation de test_issue128.py (chemins de
données redirigés vers un dossier temporaire — AUCUN fichier personnel
d'Alain n'est lu ni écrit par ce test). Les appels à l'API Claude sont
simulés au niveau le plus bas possible (llm_coach._call_claude), comme
test_issue140_mode_serie_ia_arriere_plan.py, pour que get_coach_response
s'exécute réellement de bout en bout (vérificateur de fiabilité,
vérificateur d'affirmations factuelles, écriture au journal).

Issue #142, vérification (d) : aucun test de ce fichier n'est ignoré,
désactivé ou conditionné par une variable d'environnement — Stockfish
absent de la machine fait ÉCHOUER setUpClass (RuntimeError), il n'est
jamais sauté.

Ce fichier importe app.py comme test_issue128.py/test_issue134.py/
test_issue135.py/test_issue137_signe_eval_lichess.py/
test_issue139_mode_serie.py/test_issue140_mode_serie_ia_arriere_plan.py/
test_issue141_golden_master.py : ne JAMAIS l'exécuter dans le même process
que l'un de ces fichiers (même contrainte, voir leurs en-têtes) — invoquer
séparément :
    python3 -m unittest test_issue142_page_club
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

import chess

from engine_stockfish import find_stockfish
from test_issue128 import _patch_config_paths_vers_tmp, _restaure_config_paths


class TestPageClub(unittest.TestCase):
    """Fait tourner les routes /club, /api/club/avis, /api/club/eval,
    /api/club/jugement via un VRAI client de test Flask, API Claude simulée
    AU NIVEAU RÉSEAU (llm_coach._call_claude), jamais d'appel réel."""

    @classmethod
    def setUpClass(cls):
        stockfish_path = find_stockfish()
        if not stockfish_path:
            raise RuntimeError(
                "Stockfish introuvable sur cette machine : ce test doit "
                "échouer plutôt que d'être sauté (issue #142, vérification d)."
            )

        cls._tmp = tempfile.TemporaryDirectory()
        tmp_dir = Path(cls._tmp.name)

        import config as config_module
        cls._config_module = config_module
        cls._anciens_config = _patch_config_paths_vers_tmp(config_module, tmp_dir)
        # Chemins propres à l'issue #142, absents de la liste partagée de
        # test_issue128.py (qui ne connaît pas encore ces noms) : patchés
        # séparément ici, jamais en modifiant ce fichier partagé.
        cls._anciens_config["CLUB_AVIS_COMPTEUR_PATH"] = config_module.CLUB_AVIS_COMPTEUR_PATH
        cls._anciens_config["CLUB_JUGEMENTS_LOG_PATH"] = config_module.CLUB_JUGEMENTS_LOG_PATH
        config_module.CLUB_AVIS_COMPTEUR_PATH = tmp_dir / "club_avis_compteur.tmp.json"
        config_module.CLUB_JUGEMENTS_LOG_PATH = tmp_dir / "logs" / "club_jugements.tmp.log"

        if "app" in sys.modules:
            raise RuntimeError(
                "app.py était déjà importé avant ce test : l'isolation des "
                "chemins de données ne peut plus être garantie (même "
                "contrainte que test_issue128.py — ne jamais exécuter ces "
                "fichiers dans le même process)."
            )
        cls.app_module = importlib.import_module("app")
        cls.client = cls.app_module.app.test_client()
        cls.socketio_client = cls.app_module.socketio.test_client(cls.app_module.app)

    @classmethod
    def tearDownClass(cls):
        _restaure_config_paths(cls._config_module, cls._anciens_config)
        cls._tmp.cleanup()

    def setUp(self):
        self.app_module._current_exercise = None
        self.socketio_client.get_received()
        # Indépendance entre tests : repartir d'un compteur/d'une file
        # d'appels à zéro (jamais un fichier/compteur hérité d'un test
        # précédent).
        try:
            self.app_module.config.CLUB_AVIS_COMPTEUR_PATH.unlink()
        except FileNotFoundError:
            pass
        with self.app_module._club_appels_lock:
            self.app_module._club_appels_en_cours = 0

    # -- Positions de test ------------------------------------------------

    FEN_GAFFE_BLANCS = "4k3/8/2n5/8/3Q4/8/8/4K3 w - - 0 1"
    UCI_GAFFE_BLANCS = "e1d1"          # Roi e1-d1 : ignore la Dame en prise.

    FEN_GAFFE_NOIRS = "4k3/8/8/3q4/8/2N5/8/4K3 b - - 0 1"
    UCI_GAFFE_NOIRS = "e8d8"           # Roi e8-d8 : ignore la Dame en prise.

    def _patch_claude_rapide(self, texte: str = "Réponse simulée du coach (issue #142).",
                              delai_s: float = 0.0):
        """Remplace llm_coach._call_claude (niveau le plus bas) par une
        simulation qui capture chaque system prompt complet reçu (contexte
        inclus) — jamais d'appel réseau réel. Retourne la liste des
        captures."""
        captures = []

        def _faux_call_claude(prompt_sys, messages, api_key, model, usage_path=None,
                               timeout_s=90, temperature=None):
            captures.append(prompt_sys)
            if delai_s:
                time.sleep(delai_s)
            return texte

        patcher = patch.object(self.app_module.llm_coach, "_call_claude", side_effect=_faux_call_claude)
        patcher.start()
        self.addCleanup(patcher.stop)
        return captures

    def _figer_moteur_pour_determinisme(self) -> None:
        """Mémorise chaque méthode d'analyse de engine_manager (issue #142) :
        un appel avec les MÊMES arguments (FEN/coup/profondeur) renvoie
        TOUJOURS le résultat de son PREMIER calcul réel — jamais une
        exception, jamais un résultat inventé. Nécessaire pour comparer deux
        exécutions complètes du même code sur la même position (exercice
        « Position précise » puis /api/club/avis) : constaté en préparant ce
        test, Stockfish (pourtant configuré à Threads=1) ne garantit PAS la
        même ligne "meilleure" d'un appel à l'autre pour une position où
        plusieurs coups mènent à un mat forcé équivalent (table de
        hachage partagée, polluée par les nombreux appels intermédiaires
        d'un exercice complet — menace adverse, idées, réponses adverses —
        avant que le second appel ne revienne sur la même position de
        départ) : un détail de reproductibilité de Stockfish, PAS un défaut
        du code de cette issue, cf. rapport de clôture. Mémoriser (plutôt
        que simuler) garde un calcul Stockfish RÉEL pour chaque argument
        inédit."""
        engine_manager = self.app_module.engine_manager
        noms = [
            "evaluate", "evaluate_move", "get_multipv", "get_reponses_adverses",
            "get_eval_breakdown", "get_threats",
        ]
        cache = {}
        originaux = {nom: getattr(engine_manager, nom) for nom in noms}

        def _rep(valeur):
            if isinstance(valeur, chess.Board):
                return valeur.fen()
            if isinstance(valeur, chess.Move):
                return valeur.uci()
            return valeur

        def _cle(nom, args, kwargs):
            return (
                nom, tuple(_rep(a) for a in args),
                tuple(sorted((k, _rep(v)) for k, v in kwargs.items())),
            )

        def _fabrique(nom):
            original = originaux[nom]

            def _wrapped(*args, **kwargs):
                cle = _cle(nom, args, kwargs)
                if cle not in cache:
                    cache[cle] = original(*args, **kwargs)
                return cache[cle]
            return _wrapped

        for nom in noms:
            patcher = patch.object(engine_manager, nom, side_effect=_fabrique(nom))
            patcher.start()
            self.addCleanup(patcher.stop)

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

    # -- Route de page ------------------------------------------------------

    def test_route_club_sert_le_fichier_statique(self):
        reponse = self.client.get("/club")
        self.assertEqual(reponse.status_code, 200)
        self.assertIn(b"club", reponse.data.lower())

    # -- Avis : coup valide, les deux camps, contexte identique au ----------
    # -- gestionnaire « Position précise » -----------------------------------

    def _emettre_position_precise(self, fen: str, camp_alain: str, uci: str) -> list:
        self.app_module._current_exercise = {
            "source": "position_precise", "fen_avant": fen, "camp_alain": camp_alain,
            "phase": "toutes", "sous_type": None,
        }
        self.socketio_client.emit("exercise_answer", {"uci": uci, "exercise_id": "test142-exo"})
        return self.socketio_client.get_received()

    def test_avis_blancs_contexte_identique_a_position_precise(self):
        self._verifier_contexte_identique(self.FEN_GAFFE_BLANCS, "blancs", self.UCI_GAFFE_BLANCS)

    def test_avis_noirs_contexte_identique_a_position_precise(self):
        self._verifier_contexte_identique(self.FEN_GAFFE_NOIRS, "noirs", self.UCI_GAFFE_NOIRS)

    def _verifier_contexte_identique(self, fen: str, camp_alain: str, uci: str) -> None:
        self._figer_moteur_pour_determinisme()

        # Chemin existant : exercice « Position précise ».
        captures_exo = self._patch_claude_rapide()
        recus = self._emettre_position_precise(fen, camp_alain, uci)
        evt = next((e for e in recus if e["name"] == "exercise_comment"), None)
        self.assertIsNotNone(evt, "exercise_comment attendu pour l'exercice « Position précise »")
        self.assertEqual(len(captures_exo), 1)
        prompt_exo = captures_exo[0]

        # Chemin nouveau : /api/club/avis sur la MÊME position/coup.
        captures_club = self._patch_claude_rapide()
        reponse = self.client.post("/api/club/avis", json={"fen": fen, "coup": uci})
        self.assertEqual(reponse.status_code, 200, reponse.get_json())
        self.assertEqual(len(captures_club), 1)
        prompt_club = captures_club[0]

        # Même system prompt COMPLET (addenda + contexte construit) transmis
        # à l'IA pour la même position et le même coup (issue #142, point
        # 2) — à l'EXCEPTION, attendue et volontaire, de la ligne
        # d'identification qui cite littéralement mode_origine ("mode
        # exercice" vs "mode club", cf. llm_coach._build_context_text) :
        # mode_origine DOIT différer entre les deux chemins (issue #142,
        # point 6, pour que scripts/controle_avis.py les distingue), donc
        # cette seule ligne diffère par construction. Tout le reste du
        # contexte (menace adverse, pièces, idées, lignes, faits, réponses
        # adverses...) doit être STRICTEMENT identique.
        self.assertEqual(prompt_exo, prompt_club.replace("mode club", "mode exercice", 1))

        corps = reponse.get_json()
        self.assertIn("text", corps)
        self.assertIn("avis_sections", corps)
        self.assertIn("avis_format_conforme", corps)
        self.assertEqual(corps["verdict_qualite_officiel"], "gaffe")
        self.assertIsInstance(corps["verdict_delta_cp"], int)
        self.assertTrue(corps["meilleur_coup"])
        self.assertIn("eval_before_cp", corps)
        self.assertIn("eval_after_cp", corps)
        self.assertIn("fiabilite", corps)
        self.assertIn("alertes", corps["fiabilite"])
        self.assertIsNotNone(corps["log_id"])

        # Journalisé avec mode_origine="club" (issue #142, point 6), jamais
        # retenu par le filtre de scripts/controle_avis.py (qui ne garde que
        # mode_origine=="exercice", cf. son code :
        # `d.get('mode_origine')=='exercice'`).
        journal = self._lire_journal()
        entree = next((e for e in journal if e.get("id") == corps["log_id"]), None)
        self.assertIsNotNone(entree)
        self.assertEqual(entree["mode_origine"], "club")
        self.assertIs(entree["context"].get("via_club"), True)
        self.assertNotEqual(entree["mode_origine"], "exercice")

    # -- Coup illégal ---------------------------------------------------------

    def test_coup_illegal_refuse_sans_appel_ia_ni_stockfish_gaspille(self):
        captures = self._patch_claude_rapide()
        reponse = self.client.post("/api/club/avis", json={
            "fen": self.FEN_GAFFE_BLANCS, "coup": "e1e8",  # roi ne peut pas aller si loin
        })
        self.assertEqual(reponse.status_code, 400)
        corps = reponse.get_json()
        self.assertEqual(corps["erreur"], "coup_invalide")
        self.assertTrue(corps["message"])
        self.assertEqual(len(captures), 0, "aucun appel IA pour un coup illégal")
        self.assertEqual(
            self.app_module._club_charger_compteur().get("count", 0), 0,
            "une requête invalide ne doit jamais consommer la limite quotidienne",
        )

    # -- FEN invalide -----------------------------------------------------

    def test_fen_invalide_refusee_sans_appel_ia(self):
        captures = self._patch_claude_rapide()
        reponse = self.client.post("/api/club/avis", json={
            "fen": "ceci n'est pas un FEN", "coup": "e2e4",
        })
        self.assertEqual(reponse.status_code, 400)
        corps = reponse.get_json()
        self.assertEqual(corps["erreur"], "fen_invalide")
        self.assertEqual(len(captures), 0)
        self.assertEqual(self.app_module._club_charger_compteur().get("count", 0), 0)

    def test_coup_ambigu_refuse(self):
        # Deux cavaliers blancs peuvent tous les deux rejoindre e4 : "Ne4"
        # est ambigu sans préciser la case de départ.
        fen = "4k3/8/8/8/8/1N6/8/1N2K3 w - - 0 1"
        captures = self._patch_claude_rapide()
        reponse = self.client.post("/api/club/avis", json={"fen": fen, "coup": "Ne4"})
        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(reponse.get_json()["erreur"], "coup_invalide")
        self.assertEqual(len(captures), 0)

    # -- Limite quotidienne -------------------------------------------------

    def test_limite_quotidienne_troisieme_requete_refusee_sans_appel(self):
        self.app_module.CLUB_MAX_AVIS_PAR_JOUR, ancien = 2, self.app_module.CLUB_MAX_AVIS_PAR_JOUR
        self.addCleanup(setattr, self.app_module, "CLUB_MAX_AVIS_PAR_JOUR", ancien)

        captures = self._patch_claude_rapide()
        for i in range(2):
            reponse = self.client.post("/api/club/avis", json={
                "fen": self.FEN_GAFFE_BLANCS, "coup": self.UCI_GAFFE_BLANCS,
            })
            self.assertEqual(reponse.status_code, 200, reponse.get_json())
        self.assertEqual(len(captures), 2)

        # Troisième requête : refusée SANS appel IA simulé supplémentaire.
        reponse = self.client.post("/api/club/avis", json={
            "fen": self.FEN_GAFFE_BLANCS, "coup": self.UCI_GAFFE_BLANCS,
        })
        self.assertEqual(reponse.status_code, 429)
        corps = reponse.get_json()
        self.assertEqual(corps["erreur"], "limite_quotidienne_atteinte")
        self.assertIn("minuit", corps["message"].lower())
        self.assertIn("2", corps["message"])
        self.assertEqual(len(captures), 2, "aucun appel IA supplémentaire une fois la limite atteinte")

    def test_z_compteur_persiste_apres_rechargement_du_module(self):
        # Nommé "test_z_..." pour s'exécuter EN DERNIER dans cette classe
        # (ordre alphabétique par défaut d'unittest) : importlib.reload(app)
        # réinitialise engine_manager/coach_memory/etc., ce qui ne doit
        # jamais affecter les tests précédents (self.client/self.socketio_client,
        # créés avant ce test, restent valides pour EUX, mais autant éviter
        # tout effet de bord sur un test qui s'exécuterait après).
        #
        # Fait deux incréments directs (sans passer par l'IA, pour un test
        # rapide et indépendant de toute simulation) puis recharge le module
        # app.py : le compteur doit être relu depuis le disque, pas depuis
        # un état en mémoire qui serait réinitialisé par le rechargement
        # (issue #142, point 7 : "il survit à un redémarrage").
        self.assertTrue(self.app_module._club_verifier_et_incrementer_compteur())
        self.assertTrue(self.app_module._club_verifier_et_incrementer_compteur())
        avant = self.app_module._club_charger_compteur()
        self.assertEqual(avant["count"], 2)

        importlib.reload(self.app_module)

        apres = self.app_module._club_charger_compteur()
        self.assertEqual(apres["count"], 2, "le compteur doit survivre à un rechargement du module")
        self.assertEqual(apres["date"], avant["date"])

    # -- Concurrence : au plus 2 appels simultanés ---------------------------

    def test_troisieme_appel_simultane_refuse_occupe(self):
        delai_s = 0.6
        verrou = threading.Lock()
        etat = {"concurrents": 0, "max_simultanes": 0}

        def _faux_call_claude(prompt_sys, messages, api_key, model, usage_path=None,
                               timeout_s=90, temperature=None):
            with verrou:
                etat["concurrents"] += 1
                etat["max_simultanes"] = max(etat["max_simultanes"], etat["concurrents"])
            try:
                time.sleep(delai_s)
                return "Réponse simulée lente (issue #142, test de concurrence)."
            finally:
                with verrou:
                    etat["concurrents"] -= 1

        patcher = patch.object(self.app_module.llm_coach, "_call_claude", side_effect=_faux_call_claude)
        patcher.start()
        self.addCleanup(patcher.stop)

        resultats = {}

        def _requete(nom: str) -> None:
            client_thread = self.app_module.app.test_client()
            reponse = client_thread.post("/api/club/avis", json={
                "fen": self.FEN_GAFFE_BLANCS, "coup": self.UCI_GAFFE_BLANCS,
            })
            resultats[nom] = reponse

        t1 = threading.Thread(target=_requete, args=("t1",))
        t2 = threading.Thread(target=_requete, args=("t2",))
        t1.start()
        t2.start()
        # Laisser les deux premières requêtes occuper leurs deux
        # emplacements avant de tenter la troisième.
        time.sleep(0.2)

        reponse3 = self.client.post("/api/club/avis", json={
            "fen": self.FEN_GAFFE_BLANCS, "coup": self.UCI_GAFFE_BLANCS,
        })
        self.assertEqual(reponse3.status_code, 503)
        self.assertEqual(reponse3.get_json()["erreur"], "occupe")

        t1.join(timeout=10)
        t2.join(timeout=10)
        self.assertFalse(t1.is_alive())
        self.assertFalse(t2.is_alive())
        self.assertEqual(resultats["t1"].status_code, 200)
        self.assertEqual(resultats["t2"].status_code, 200)
        self.assertLessEqual(etat["max_simultanes"], self.app_module.CLUB_MAX_APPELS_SIMULTANES)

        # La requête refusée "occupé" ne doit pas avoir consommé la limite
        # quotidienne (seules les deux requêtes acceptées l'ont fait).
        self.assertEqual(self.app_module._club_charger_compteur().get("count", 0), 2)

    # -- Mistral jamais appelé ------------------------------------------------

    def test_mistral_jamais_appele_meme_avec_cle_configuree(self):
        ancienne = self.app_module.config.MISTRAL_API_KEY
        self.app_module.config.MISTRAL_API_KEY = "fake-mistral-key-issue142"
        self.addCleanup(setattr, self.app_module.config, "MISTRAL_API_KEY", ancienne)

        self._patch_claude_rapide()
        mistral_patcher = patch.object(self.app_module.llm_coach, "get_mistral_response")
        mock_mistral = mistral_patcher.start()
        self.addCleanup(mistral_patcher.stop)

        reponse = self.client.post("/api/club/avis", json={
            "fen": self.FEN_GAFFE_BLANCS, "coup": self.UCI_GAFFE_BLANCS,
        })
        self.assertEqual(reponse.status_code, 200, reponse.get_json())
        mock_mistral.assert_not_called()

    # -- Évaluation seule (sans appel IA) -------------------------------------

    @staticmethod
    def _avantage_blancs_signe(corps: dict):
        """cp si disponible (position pas encore forcément décidée par mat),
        sinon le signe du mat (issue #142 : K+D contre K seul, utilisé
        ci-dessous, est un mat forcé trouvé par Stockfish dès cette
        profondeur — eval_blancs_cp reste alors None par construction,
        cf. engine_stockfish.evaluate_move/evaluate, jamais un défaut de
        cette issue)."""
        if corps["eval_blancs_cp"] is not None:
            return corps["eval_blancs_cp"]
        return corps["eval_blancs_mat"]

    def test_eval_position_blancs_mieux(self):
        captures = self._patch_claude_rapide()
        fen = "4k3/8/8/8/3Q4/8/8/4K3 w - - 0 1"  # Blancs : Dame de plus (mat forcé).
        reponse = self.client.post("/api/club/eval", json={"fen": fen})
        self.assertEqual(reponse.status_code, 200, reponse.get_json())
        corps = reponse.get_json()
        avantage = self._avantage_blancs_signe(corps)
        self.assertIsNotNone(avantage)
        self.assertGreater(avantage, 0, "les Blancs doivent être évalués comme mieux (convention Lichess)")
        self.assertTrue(corps["meilleurs_coups"])
        self.assertLessEqual(len(corps["meilleurs_coups"]), 3)
        for coup in corps["meilleurs_coups"]:
            avantage_coup = coup["eval_blancs_cp"] if coup["eval_blancs_cp"] is not None else coup["eval_blancs_mat"]
            self.assertIsNotNone(avantage_coup)
            self.assertGreaterEqual(avantage_coup, 0)
        self.assertEqual(len(captures), 0, "aucun appel IA pour /api/club/eval")

    def test_eval_position_noirs_mieux(self):
        fen = "4k3/8/8/3q4/8/8/8/4K3 w - - 0 1"  # Noirs : Dame de plus (mat forcé).
        reponse = self.client.post("/api/club/eval", json={"fen": fen})
        self.assertEqual(reponse.status_code, 200, reponse.get_json())
        corps = reponse.get_json()
        avantage = self._avantage_blancs_signe(corps)
        self.assertIsNotNone(avantage)
        self.assertLess(avantage, 0, "les Noirs doivent être évalués comme mieux (convention Lichess)")

    def test_eval_fen_invalide(self):
        reponse = self.client.post("/api/club/eval", json={"fen": "pas un fen"})
        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(reponse.get_json()["erreur"], "fen_invalide")

    # -- Jugement -------------------------------------------------------------

    def test_jugement_enregistre_dans_le_bon_fichier(self):
        reponse = self.client.post("/api/club/jugement", json={
            "log_id": "abc123", "jugement": "accord", "etiquettes": ["tactique"],
            "remarque": "Avis clair.",
        })
        self.assertEqual(reponse.status_code, 200, reponse.get_json())
        self.assertIn("id", reponse.get_json())

        chemin = self.app_module.config.CLUB_JUGEMENTS_LOG_PATH
        self.assertTrue(chemin.exists())
        lignes = [json.loads(l) for l in chemin.read_text(encoding="utf-8").splitlines() if l.strip()]
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0]["log_id"], "abc123")
        self.assertEqual(lignes[0]["jugement"], "accord")
        self.assertEqual(lignes[0]["etiquettes"], ["tactique"])

        # Jamais dans coach_ratings.jsonl (issue #142, point 5).
        import coach_ratings
        self.assertFalse(
            Path(coach_ratings.RATINGS_PATH).exists(),
            "un jugement club ne doit jamais être écrit dans coach_ratings.jsonl",
        )

    def test_jugement_invalide_refuse(self):
        reponse = self.client.post("/api/club/jugement", json={
            "log_id": "abc123", "jugement": "pas_une_valeur_valide",
        })
        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(reponse.get_json()["erreur"], "jugement_invalide")


if __name__ == "__main__":
    unittest.main()
