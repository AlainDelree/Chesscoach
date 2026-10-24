"""
test_issue140_mode_serie_ia_arriere_plan.py — ChessCoach (issue #140, suite #139,
étape 2)

Tests pour le mode série, étape 2 : appel des deux IA en arrière-plan avec
le contexte complet du mode normal, file d'attente bornée
(MODE_SERIE_MAX_APPELS_SIMULTANES), compteur "avis en cours" et écriture au
journal (coach_calls.log) avec l'indicateur mode_serie, y compris en cas
d'échec d'une IA simulée.

Exécute le VRAI gestionnaire de réponse d'exercice (app.on_exercise_answer /
app._on_exercise_answer_lichess) via le client de test Flask-SocketIO, en
réutilisant l'infrastructure d'isolation de test_issue128.py (chemins de
données redirigés vers un dossier temporaire — AUCUN fichier personnel
d'Alain n'est lu ni écrit par ce test), exactement comme
test_issue139_mode_serie.py. Contrairement à test_issue139_mode_serie.py
(qui patche get_mistral_response en entier), les IA sont simulées ici au
niveau le plus bas possible (llm_coach._call_claude / llm_coach._call_mistral)
pour que get_coach_response/get_mistral_response s'exécutent réellement de
bout en bout (vérificateur de fiabilité, vérificateur d'affirmations
factuelles, écriture au journal via _log_coach_call) — cf. issue #140,
point 2 : "aucune copie de la logique d'appel ni du vérificateur". Un délai
simulé (time.sleep) permet d'observer le nombre d'appels réellement
simultanés et de vérifier qu'il ne dépasse jamais
MODE_SERIE_MAX_APPELS_SIMULTANES.

Issue #139/#140, vérification (d) : aucun test de ce fichier n'est ignoré,
désactivé ou conditionné par une variable d'environnement — Stockfish
absent de la machine fait ÉCHOUER setUpClass (RuntimeError), il n'est
jamais sauté.

Ce fichier importe app.py comme test_issue128.py/test_issue134.py/
test_issue135.py/test_issue137_signe_eval_lichess.py/
test_issue139_mode_serie.py : ne JAMAIS l'exécuter dans le même process que
l'un de ces fichiers (même contrainte, voir leurs en-têtes) — invoquer
séparément :
    python3 -m unittest test_issue140_mode_serie_ia_arriere_plan
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


class TestModeSerieAvisArrierePlan(unittest.TestCase):
    """Fait tourner app.on_exercise_answer / app._on_exercise_answer_lichess
    via un VRAI client de test Flask-SocketIO, API Claude/Mistral simulées
    AU NIVEAU RÉSEAU (_call_claude/_call_mistral), jamais d'appel réel."""

    @classmethod
    def setUpClass(cls):
        # Issue #139/#140, vérification (d) : une dépendance manquante (ici
        # Stockfish) fait ÉCHOUER ce test, jamais le sauter.
        stockfish_path = find_stockfish()
        if not stockfish_path:
            raise RuntimeError(
                "Stockfish introuvable sur cette machine : ce test doit "
                "échouer plutôt que d'être sauté (issue #140, vérification d)."
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
        # Repartir d'un compteur à zéro entre deux tests (indépendance) —
        # avec une limite de temps explicite, jamais un sleep fixe.
        self._attendre_compteur_serie_zero()

    # Même position que test_issue139_mode_serie.py (gaffe déterministe,
    # vérifiée au préalable avec Stockfish).
    FEN_GAFFE = "4k3/8/2n5/8/3Q4/8/8/4K3 w - - 0 1"
    UCI_GAFFE = "e1d1"          # Roi e1-d1 : ignore la Dame en prise.
    UCI_MEILLEUR_COUP = "d4e4"  # Qe4+ : sauve la Dame en donnant échec.

    def _poser_exercice(self, source: str, cle_historique: str = "lichess:test140") -> None:
        self.app_module._current_exercise = {
            "source": source,
            "fen_avant": self.FEN_GAFFE,
            "camp_alain": "blancs",
            "coup_joue_san": "Kd1", "coup_joue_uci": "e1d1",
            "meilleur_coup_san": "", "meilleur_coup_uci": "",
            "solution": [self.UCI_MEILLEUR_COUP],
            "categorie_tirage": "mat_en_1" if source == "lichess" else None,
            "cle_historique": cle_historique if source == "lichess" else None,
            "niveau_tirage": 1000, "rating": 1000, "themes": [],
        }

    def _activer_mistral(self) -> None:
        ancienne = self.app_module.config.MISTRAL_API_KEY
        self.app_module.config.MISTRAL_API_KEY = "fake-mistral-key-issue140"
        self.addCleanup(setattr, self.app_module.config, "MISTRAL_API_KEY", ancienne)

    def _emettre(self, uci: str, exercise_id: str, mode_serie: bool = True) -> list:
        self.client.emit("exercise_answer", {
            "uci": uci, "exercise_id": exercise_id, "mode_serie": mode_serie,
        })
        return self.client.get_received()

    @staticmethod
    def _evt(recus, nom):
        return next((e for e in recus if e["name"] == nom), None)

    def _attendre_compteur_serie_zero(self, timeout: float = 15.0) -> None:
        """Attend la fin de TOUS les appels IA déjà soumis à
        _mode_serie_executor (compteur "avis en cours" revenu à 0), avec une
        limite de temps EXPLICITE plutôt qu'un sleep fixe fragile — échoue
        au lieu de rester bloqué indéfiniment si le compteur ne retombe
        jamais à 0 (issue #140, vérification 8d)."""
        deadline = time.monotonic() + timeout
        n = None
        while time.monotonic() < deadline:
            with self.app_module._mode_serie_lock:
                n = self.app_module._mode_serie_avis_en_cours
            if n == 0:
                return
            time.sleep(0.02)
        self.fail(f"compteur 'avis en cours' du mode série non revenu à 0 sous {timeout}s (reste {n})")

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

    def _patch_ia_lentes(self, delai_s: float = 0.15, echec_au_n_ieme_appel: int = None) -> dict:
        """Remplace llm_coach._call_claude/_call_mistral (niveau le plus bas
        possible, cf. en-tête de ce fichier) par des simulations LENTES
        (time.sleep) qui comptent le nombre d'appels simultanés réellement
        en cours — jamais d'appel réseau réel. Si echec_au_n_ieme_appel est
        fourni, le N-ième appel (toutes IA confondues, dans l'ordre
        d'arrivée) lève une TimeoutError simulée, exactement comme un vrai
        dépassement de délai — get_coach_response/get_mistral_response
        catchent déjà ce cas elles-mêmes (jamais dupliqué ici) et journalisent
        une entrée d'erreur. Retourne un dict d'état partagé {"appels": int,
        "max_simultanes": int}."""
        etat = {"appels": 0, "concurrents": 0, "max_simultanes": 0}
        verrou = threading.Lock()

        def _entree() -> bool:
            with verrou:
                etat["appels"] += 1
                etat["concurrents"] += 1
                etat["max_simultanes"] = max(etat["max_simultanes"], etat["concurrents"])
                return echec_au_n_ieme_appel is not None and etat["appels"] == echec_au_n_ieme_appel

        def _sortie() -> None:
            with verrou:
                etat["concurrents"] -= 1

        def _faux_call_claude(prompt_sys, messages, api_key, model, usage_path=None,
                               timeout_s=90, temperature=None):
            doit_echouer = _entree()
            try:
                time.sleep(delai_s)
                if doit_echouer:
                    raise TimeoutError("échec simulé issue #140 (Claude)")
                return "Réponse simulée du coach (Claude) pour le test issue #140, étape 2."
            finally:
                _sortie()

        def _faux_call_mistral(prompt_sys, messages, api_key, model, usage_path=None,
                                timeout_s=90, temperature=None):
            doit_echouer = _entree()
            try:
                time.sleep(delai_s)
                if doit_echouer:
                    raise TimeoutError("échec simulé issue #140 (Mistral)")
                return "Réponse simulée du coach (Mistral) pour le test issue #140, étape 2.", None
            finally:
                _sortie()

        p1 = patch.object(self.app_module.llm_coach, "_call_claude", side_effect=_faux_call_claude)
        p1.start()
        self.addCleanup(p1.stop)
        p2 = patch.object(self.app_module.llm_coach, "_call_mistral", side_effect=_faux_call_mistral)
        p2.start()
        self.addCleanup(p2.stop)
        return etat

    # -- File d'attente bornée, compteur, dix avis au journal ------------

    def test_mes_erreurs_cinq_reponses_rapides_dix_avis_au_journal(self):
        self._activer_mistral()
        etat = self._patch_ia_lentes(delai_s=0.15)
        avant = len(self._lire_journal())

        verdicts = []
        for i in range(5):
            self._poser_exercice("mes_erreurs")
            recus = self._emettre(self.UCI_GAFFE, f"test140-me-{i}")
            verdicts.append(self._evt(recus, "exercise_serie_verdict"))
            self.assertIsNone(self._evt(recus, "exercise_comment"))
            self.assertIsNone(self._evt(recus, "exercise_mistral_comment"))

        # Le verdict en une ligne apparaît à CHAQUE exercice, immédiatement
        # (avant même la fin des appels IA en arrière-plan).
        self.assertEqual(len(verdicts), 5)
        self.assertTrue(all(v is not None for v in verdicts),
                         "un verdict en une ligne est attendu à chaque exercice")

        # Le compteur doit revenir à 0 une fois tous les avis enregistrés.
        self._attendre_compteur_serie_zero()

        # Dix appels au total (cinq exercices x deux IA) ; jamais plus de
        # MODE_SERIE_MAX_APPELS_SIMULTANES exécutés en même temps.
        self.assertEqual(etat["appels"], 10, "cinq exercices x deux IA (Claude+Mistral) = dix appels")
        self.assertLessEqual(
            etat["max_simultanes"], self.app_module.MODE_SERIE_MAX_APPELS_SIMULTANES,
            "le nombre d'appels IA simultanés observés ne doit jamais dépasser la limite fixée",
        )

        journal = self._lire_journal()
        nouvelles = journal[avant:]
        self.assertEqual(len(nouvelles), 10, "dix avis attendus au journal (cinq par IA)")
        for entree in nouvelles:
            # Champs habituels, exactement comme hors mode série, plus
            # l'indicateur mode_serie (issue #140, point 2).
            self.assertIs(entree["context"].get("mode_serie"), True)
            self.assertEqual(entree["mode_origine"], "exercice")
            self.assertIsNone(entree.get("erreur"))
            self.assertIsNotNone(entree.get("reponse"))
            self.assertIn("fiabilite", entree)
            self.assertIn("fact_checker_alertes", entree)
        claude_entries = [e for e in nouvelles if not str(e.get("model") or "").startswith("mistral:")]
        mistral_entries = [e for e in nouvelles if str(e.get("model") or "").startswith("mistral:")]
        self.assertEqual(len(claude_entries), 5)
        self.assertEqual(len(mistral_entries), 5)

    def test_lichess_cinq_reponses_rapides_cinq_avis_claude_seul(self):
        # La source "lichess" n'appelle jamais Mistral, mode série ou pas
        # (configuration existante, inchangée par cette issue) — même en
        # activant Mistral globalement ici, seul Claude doit être sollicité.
        self._activer_mistral()
        etat = self._patch_ia_lentes(delai_s=0.1)
        avant = len(self._lire_journal())

        verdicts = []
        for i in range(5):
            self._poser_exercice("lichess", cle_historique=f"lichess:test140-{i}")
            recus = self._emettre(self.UCI_GAFFE, f"test140-lichess-{i}")
            verdicts.append(self._evt(recus, "exercise_serie_verdict"))
            self.assertIsNone(self._evt(recus, "exercise_comment"))

        self.assertTrue(all(v is not None for v in verdicts))
        self._attendre_compteur_serie_zero()

        self.assertEqual(etat["appels"], 5, "cinq exercices x une seule IA (Claude) = cinq appels")
        self.assertLessEqual(etat["max_simultanes"], self.app_module.MODE_SERIE_MAX_APPELS_SIMULTANES)

        journal = self._lire_journal()
        nouvelles = journal[avant:]
        self.assertEqual(len(nouvelles), 5)
        for entree in nouvelles:
            self.assertIs(entree["context"].get("mode_serie"), True)
            self.assertEqual(entree["mode_origine"], "exercice_lichess")
            self.assertIsNone(entree.get("erreur"))

    # -- Échec d'une IA simulée : compteur jamais bloqué, erreur journalisée

    def test_echec_ia_simulee_ne_bloque_pas_le_compteur_et_journalise_erreur(self):
        self._poser_exercice("mes_erreurs")
        # Mistral désactivé par défaut (_patch_config_paths_vers_tmp) : un
        # seul appel (Claude) aura lieu pour cet exercice, et c'est celui-là
        # qui doit échouer.
        etat = self._patch_ia_lentes(delai_s=0.05, echec_au_n_ieme_appel=1)
        avant = len(self._lire_journal())

        recus = self._emettre(self.UCI_GAFFE, "test140-echec")
        self.assertIsNotNone(self._evt(recus, "exercise_serie_verdict"))

        # Le compteur doit redescendre à 0 même après un échec simulé —
        # jamais bloqué à une valeur positive.
        self._attendre_compteur_serie_zero()

        self.assertEqual(etat["appels"], 1)
        journal = self._lire_journal()
        nouvelles = journal[avant:]
        self.assertEqual(len(nouvelles), 1, "une seule IA active dans ce test (Mistral désactivé)")
        entree = nouvelles[0]
        self.assertIsNotNone(entree.get("erreur"), "une entrée d'erreur est attendue au journal")
        self.assertIs(entree["context"].get("mode_serie"), True)
        self.assertEqual(entree["mode_origine"], "exercice")

    # -- Mode normal : comportement inchangé (issue #140, vérification 8b) -

    def test_mode_normal_inchange_un_appel_par_ia_avis_affiche(self):
        self._poser_exercice("mes_erreurs")
        self._activer_mistral()
        etat = self._patch_ia_lentes(delai_s=0.05)
        avant = len(self._lire_journal())

        recus = self._emettre(self.UCI_GAFFE, "test140-normal", mode_serie=False)

        # Hors mode série : Claude est appelé de façon synchrone (son avis
        # est donc déjà reçu ici), Mistral part dans le thread d'arrière-plan
        # EXISTANT du mode normal (issue #113, pas _mode_serie_executor).
        self.assertIsNone(self._evt(recus, "exercise_serie_verdict"))
        self.assertIsNotNone(self._evt(recus, "exercise_comment"))

        # Attendre que les DEUX entrées (Claude + Mistral) soient réellement
        # écrites au journal — pas seulement que les deux appels aient
        # démarré (etat["appels"] ne compte que l'entrée dans la fonction
        # simulée, pas la fin du traitement : fact-checker, écriture au
        # journal, émission socket pour Mistral) : un simple sondage sur
        # etat["appels"] laisserait l'écriture du thread Mistral encore en
        # cours au moment où ce test (et tearDownClass juste après, pour la
        # dernière méthode de la classe) nettoie son dossier temporaire.
        deadline = time.monotonic() + 10.0
        nouvelles = []
        while time.monotonic() < deadline:
            nouvelles = self._lire_journal()[avant:]
            if len(nouvelles) >= 2:
                break
            time.sleep(0.02)
        self.assertEqual(len(nouvelles), 2, "un appel Claude + un appel Mistral attendus hors mode série")
        self.assertEqual(etat["appels"], 2)

        # Le mode normal ne doit jamais toucher au compteur du mode série.
        with self.app_module._mode_serie_lock:
            self.assertEqual(
                self.app_module._mode_serie_avis_en_cours, 0,
                "le mode normal ne doit jamais incrémenter le compteur du mode série",
            )


if __name__ == "__main__":
    unittest.main()
