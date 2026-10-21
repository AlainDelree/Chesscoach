"""
test_issue134.py — ChessCoach (issue #134, suite #128)

Tests pour les trois défauts constatés sur les avis en version #128
(mesure du 21/10/2026, cf. rapport de l'issue #134) :
  1. « pour toi » accolé à un chiffre signé (avis 0fbb605945ae, 5d7671f3f1f5)
  2. sens inversé de « qui est mieux » malgré des chiffres corrects
     (avis 8047ab634b9c)
  3. verdict sous-évalué en première phrase (5d7671f3f1f5, 8047ab634b9c,
     8d3de2625b90, 0b44c9273753, 081ebb115499)

et pour les deux nouveaux contrôles déterministes ajoutés à fact_checker.py
pour les détecter.

Partie 1 : tests unitaires de fact_checker.py (aucun appel réseau, aucune
donnée personnelle), avec les valeurs réelles citées par l'issue #134 pour
reconstituer les défauts, et les cas corrects qui ne doivent PAS alerter
(faux positifs déjà repérés par l'issue : « bon coup » ~ « bon »,
« effondrement en faveur des Noirs », « de +278 à +498 en faveur des
Blancs »).

Partie 2 : présence des nouvelles consignes dans le prompt système
(llm_coach._SYSTEM_PROMPT / _EXERCISE_SYSTEM_ADDENDUM), sans appel réseau.

Partie 3 : exécution du VRAI gestionnaire de réponse d'exercice
(llm_coach.get_coach_response, et pour deux cas via le client de test
Flask-SocketIO comme test_issue128.py, tâche 5c) avec une API Claude
simulée — mêmes précautions d'isolation que test_issue128.py (chemins de
données redirigés vers un dossier temporaire, AUCUNE donnée personnelle
touchée). Ce fichier importe app.py comme test_issue128.py : les deux ne
doivent jamais être exécutés dans le même process (même contrainte que
test_issue128.py, voir son en-tête) — invoquer séparément :
    python3 -m unittest test_issue134
"""

import importlib
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import chess

import fact_checker
from engine_stockfish import find_stockfish
from test_issue128 import _patch_config_paths_vers_tmp, _restaure_config_paths


# =============================================================================
# Partie 1 : fact_checker.py — contrôles déterministes (d) et (e)
# =============================================================================

class TestFactCheckerPourToiColleChiffre(unittest.TestCase):
    """Défaut 1 : « pour toi » accolé à un chiffre signé, interdit par la
    convention de signe de l'issue #128 quel que soit le signe réel du
    chiffre."""

    FEN = "8/8/8/8/8/8/8/4k2K b - - 0 1"

    def test_defaut_0fbb605945ae_largement_gagnante_pour_toi(self):
        texte = "Position largement gagnante pour toi (-311)."
        ctx = {"fen": self.FEN, "eval_before_cp": -311, "eval_after_cp": -311}
        r = fact_checker.verifier_affirmations(texte, ctx, agent="claude", camp_alain="noirs")
        types = [a["type"] for a in r["alertes"]]
        self.assertIn("pour_toi_colle_chiffre", types)

    def test_defaut_5d7671f3f1f5_leger_avantage_pour_toi(self):
        texte = "Ton avantage reste réel (-90, soit toujours un léger avantage pour toi)."
        ctx = {"fen": self.FEN, "eval_before_cp": -90, "eval_after_cp": -90}
        r = fact_checker.verifier_affirmations(texte, ctx, agent="claude", camp_alain="noirs")
        types = [a["type"] for a in r["alertes"]]
        self.assertIn("pour_toi_colle_chiffre", types)

    def test_pas_de_fausse_alerte_pour_toi_sans_chiffre_a_proximite(self):
        # "pour toi" dans une phrase sans aucun chiffre signé à proximité :
        # formulation correcte selon la consigne #134, aucune alerte.
        texte = (
            "Les Blancs sont mieux après ce coup (+297). "
            "C'est un peu délicat pour toi dans la suite, mais rien n'est perdu."
        )
        ctx = {"fen": self.FEN, "eval_before_cp": 148, "eval_after_cp": 297}
        r = fact_checker.verifier_affirmations(texte, ctx, agent="claude", camp_alain="noirs")
        types = [a["type"] for a in r["alertes"]]
        self.assertNotIn("pour_toi_colle_chiffre", types)


class TestFactCheckerSensQuiEstMieuxInverse(unittest.TestCase):
    """Défaut 2 : sens inversé de « qui est mieux » malgré des chiffres
    corrects (avis 8047ab634b9c : Alain joue les Noirs, évaluation +148 puis
    +297 en faveur des Blancs, mais l'avis dit « tu restes légèrement
    mieux »)."""

    FEN = "8/8/8/8/8/8/8/4k2K b - - 0 1"

    def test_defaut_8047ab634b9c_tu_restes_mieux_alors_que_blancs_favorises(self):
        texte = "Ce coup est raisonnable, tu restes légèrement mieux."
        ctx = {"fen": self.FEN, "eval_before_cp": 148, "eval_after_cp": 297}
        r = fact_checker.verifier_affirmations(texte, ctx, agent="claude", camp_alain="noirs")
        types = [a["type"] for a in r["alertes"]]
        self.assertIn("sens_qui_est_mieux_inverse", types)

    def test_meme_defaut_cote_blancs(self):
        # Même défaut reconstitué côté Blancs (issue #134, "cas des deux
        # camps") : Alain joue les Blancs, évaluation négative (Noirs
        # favorisés), mais l'avis dit "tu restes mieux".
        texte = "Ce coup est raisonnable, tu restes mieux dans l'ensemble."
        ctx = {"fen": self.FEN, "eval_before_cp": -148, "eval_after_cp": -297}
        r = fact_checker.verifier_affirmations(texte, ctx, agent="claude", camp_alain="blancs")
        types = [a["type"] for a in r["alertes"]]
        self.assertIn("sens_qui_est_mieux_inverse", types)

    def test_formule_en_faveur_des_blancs_contredite(self):
        texte = "Ce coup est bon pour les Blancs."
        ctx = {"fen": self.FEN, "eval_before_cp": -300, "eval_after_cp": -350}
        r = fact_checker.verifier_affirmations(texte, ctx, agent="claude", camp_alain="noirs")
        types = [a["type"] for a in r["alertes"]]
        self.assertIn("sens_qui_est_mieux_inverse", types)

    def test_pas_de_fausse_alerte_sens_correct_cote_noirs(self):
        texte = "Les Noirs sont mieux après ce coup. Tu conserves ton avantage."
        ctx = {"fen": self.FEN, "eval_before_cp": -148, "eval_after_cp": -297}
        r = fact_checker.verifier_affirmations(texte, ctx, agent="claude", camp_alain="noirs")
        types = [a["type"] for a in r["alertes"]]
        self.assertNotIn("sens_qui_est_mieux_inverse", types)

    def test_pas_de_fausse_alerte_effondrement_en_faveur_des_noirs(self):
        # Faux positif déjà repéré par l'issue #134 : "effondrement en
        # faveur des Noirs" est une formulation correcte.
        texte = "Analyse : effondrement en faveur des Noirs après ce coup."
        ctx = {"fen": self.FEN, "eval_before_cp": -50, "eval_after_cp": -400}
        r = fact_checker.verifier_affirmations(texte, ctx, agent="claude", camp_alain="noirs")
        types = [a["type"] for a in r["alertes"]]
        self.assertNotIn("sens_qui_est_mieux_inverse", types)

    def test_pas_de_fausse_alerte_278_a_498_en_faveur_des_blancs(self):
        # Faux positif déjà repéré par l'issue #134.
        texte = "La position passe de +278 à +498 en faveur des Blancs."
        ctx = {"fen": self.FEN, "eval_before_cp": 278, "eval_after_cp": 498}
        r = fact_checker.verifier_affirmations(texte, ctx, agent="claude", camp_alain="noirs")
        types = [a["type"] for a in r["alertes"]]
        self.assertNotIn("sens_qui_est_mieux_inverse", types)

    def test_pas_de_fausse_alerte_chiffre_avant_ou_apres_le_coup(self):
        # Le chiffre cité peut être celui d'avant OU d'après le coup — seul
        # le sens "qui est mieux" compte (issue #134).
        texte = "Tu restes mieux (évaluation avant le coup : +148)."
        ctx = {"fen": self.FEN, "eval_before_cp": 148, "eval_after_cp": 297}
        r = fact_checker.verifier_affirmations(texte, ctx, agent="claude", camp_alain="blancs")
        types = [a["type"] for a in r["alertes"]]
        self.assertNotIn("sens_qui_est_mieux_inverse", types)

    def test_prudence_evaluations_avant_apres_contradictoires(self):
        # Avant/après ne sont pas du même signe (le camp mieux placé a
        # changé) : dans le doute, ne rien signaler (même philosophie que le
        # reste du module).
        texte = "Tu restes mieux."
        ctx = {"fen": self.FEN, "eval_before_cp": 50, "eval_after_cp": -400}
        r = fact_checker.verifier_affirmations(texte, ctx, agent="claude", camp_alain="blancs")
        types = [a["type"] for a in r["alertes"]]
        self.assertNotIn("sens_qui_est_mieux_inverse", types)

    def test_prudence_sans_camp_alain_connu(self):
        texte = "Tu restes mieux."
        ctx = {"fen": self.FEN, "eval_before_cp": 148, "eval_after_cp": 297}
        r = fact_checker.verifier_affirmations(texte, ctx, agent="claude", camp_alain="")
        types = [a["type"] for a in r["alertes"]]
        self.assertNotIn("sens_qui_est_mieux_inverse", types)


class TestFactCheckerMotVerdictPremierePhrase(unittest.TestCase):
    """Défaut 3 : verdict sous-évalué en première phrase (5 avis sur 26
    ouvrent sur "imprécision" alors que le verdict officiel est "erreur" ou
    "gaffe")."""

    FEN = "8/8/8/8/8/8/8/4k2K b - - 0 1"

    def test_imprecision_alors_que_verdict_officiel_gaffe(self):
        texte = "C'est une imprécision qui laisse filer l'essentiel de l'avantage."
        ctx = {"fen": self.FEN, "verdict_qualite_officiel": "gaffe"}
        r = fact_checker.verifier_affirmations(texte, ctx, agent="claude", camp_alain="noirs")
        types = [a["type"] for a in r["alertes"]]
        self.assertIn("mot_verdict_premiere_phrase", types)

    def test_imprecision_alors_que_verdict_officiel_erreur(self):
        texte = "C'est une petite imprécision, rien de grave."
        ctx = {"fen": self.FEN, "verdict_qualite_officiel": "erreur"}
        r = fact_checker.verifier_affirmations(texte, ctx, agent="claude", camp_alain="blancs")
        types = [a["type"] for a in r["alertes"]]
        self.assertIn("mot_verdict_premiere_phrase", types)

    def test_bon_coup_equivalent_a_bon_pas_de_fausse_alerte(self):
        # Faux positif déjà repéré par l'issue #134 : "bon coup" doit être
        # reconnu comme équivalent à "bon".
        texte = "Bon coup : tu consolides ta position sans rien céder."
        ctx = {"fen": self.FEN, "verdict_qualite_officiel": "bon"}
        r = fact_checker.verifier_affirmations(texte, ctx, agent="claude", camp_alain="blancs")
        types = [a["type"] for a in r["alertes"]]
        self.assertNotIn("mot_verdict_premiere_phrase", types)

    def test_gaffe_reprise_correctement_pas_de_fausse_alerte(self):
        texte = "C'est une gaffe qui change complètement l'évaluation."
        ctx = {"fen": self.FEN, "verdict_qualite_officiel": "gaffe"}
        r = fact_checker.verifier_affirmations(texte, ctx, agent="claude", camp_alain="noirs")
        types = [a["type"] for a in r["alertes"]]
        self.assertNotIn("mot_verdict_premiere_phrase", types)

    def test_sans_verdict_officiel_aucune_alerte(self):
        texte = "C'est une imprécision mineure."
        ctx = {"fen": self.FEN}
        r = fact_checker.verifier_affirmations(texte, ctx, agent="claude", camp_alain="noirs")
        types = [a["type"] for a in r["alertes"]]
        self.assertNotIn("mot_verdict_premiere_phrase", types)


# =============================================================================
# Partie 2 : présence des nouvelles consignes dans le prompt système
# (aucun appel réseau)
# =============================================================================

class TestConsignesPromptPourToiEtVerdict(unittest.TestCase):
    """Vérifie que le prompt système interdit explicitement « pour toi »/
    « en ta faveur »/« tu restes mieux » accolé à un chiffre, exige de nommer
    le camp par sa couleur, fournit un mini-exemple par camp, et exige que le
    premier mot de qualité reprenne le verdict officiel sans l'atténuer."""

    def setUp(self):
        import llm_coach
        self.llm_coach = llm_coach
        self.texte_complet = llm_coach._SYSTEM_PROMPT + "\n\n" + llm_coach._EXERCISE_SYSTEM_ADDENDUM

    def test_interdiction_formules_accolees_a_un_chiffre(self):
        for formule in ("pour toi", "en ta faveur", "tu restes mieux"):
            self.assertIn(formule, self.texte_complet)

    def test_exige_nommer_le_camp_par_couleur(self):
        self.assertIn("Blancs", self.texte_complet)
        self.assertIn("Noirs", self.texte_complet)

    def test_deux_mini_exemples_un_par_camp(self):
        # Un exemple côté Blancs et un exemple côté Noirs, chacun avec un
        # chiffre signé réaliste (issue #134, tâche 1).
        self.assertIn("Alain joue les Blancs", self.texte_complet)
        self.assertIn("Alain joue les Noirs", self.texte_complet)

    def test_consigne_mot_verdict_premiere_phrase(self):
        self.assertIn("verdict officiel", self.llm_coach._EXERCISE_SYSTEM_ADDENDUM)
        self.assertIn("atténuer", self.llm_coach._EXERCISE_SYSTEM_ADDENDUM)


# =============================================================================
# Partie 3 : exécution du VRAI gestionnaire de réponse (issue #134, tâche 4)
# =============================================================================

class TestGetCoachResponseReelAvecDefauts(unittest.TestCase):
    """Appelle directement llm_coach.get_coach_response (la vraie fonction de
    production, pas une réimplémentation) avec une API Claude simulée, pour
    vérifier que fact_checker_alertes/fiabilite réagissent bien aux trois
    défauts. N'importe PAS app.py (pas besoin de Stockfish ici) — tâche 4,
    volet qui ne nécessite pas un verdict "gaffe"/"erreur" réellement calculé
    par Stockfish (limitation documentée dans le rapport de clôture)."""

    def _contexte_exercice(self, **kwargs):
        ctx = {
            "mode_exercice": True,
            "fen": "8/8/8/8/8/8/8/4k2K b - - 0 1",
            "fen_depart_exercice": "8/8/8/8/8/8/8/4k2K b - - 0 1",
            # Garde-fou issue #79 point 4b (llm_coach.get_coach_response) :
            # un exercice sans verdict_qualite refuse l'appel API avant
            # même d'arriver au fact_checker — en fournir un par défaut,
            # les tests qui veulent un verdict_qualite_officiel précis le
            # passent explicitement en kwarg.
            "verdict_qualite": "bon",
        }
        ctx.update(kwargs)
        return ctx

    def _appeler_avec_reponse_simulee(self, texte_reponse, context):
        import llm_coach
        with patch.object(llm_coach, "_call_claude", return_value=texte_reponse):
            response, error, fiabilite, log_id = llm_coach.get_coach_response(
                messages=[{"role": "user", "content": "Avis ?"}],
                context=context,
                coach_memory={},
                cfg={"llm_api_key": "fake-test-key-issue134", "llm_model": "claude-sonnet-5",
                     "coach_log_path": None, "usage_path": None, "coach_timeout_s": 5},
            )
        self.assertIsNone(error)
        return response, fiabilite

    def test_defaut1_pour_toi_colle_chiffre_detecte(self):
        texte = "Position largement gagnante pour toi (-311)."
        ctx = self._contexte_exercice(camp_alain="noirs", eval_before_cp=-311, eval_after_cp=-311,
                                       win_prob_drop=0.05)
        _, fiabilite = self._appeler_avec_reponse_simulee(texte, ctx)
        types = [a.get("fact_checker_type") for a in fiabilite.get("alertes", [])]
        self.assertIn("pour_toi_colle_chiffre", types)
        self.assertEqual(fiabilite["couleur"], "orange")

    def test_defaut2_sens_inverse_detecte(self):
        texte = "Ce coup est raisonnable, tu restes légèrement mieux."
        ctx = self._contexte_exercice(camp_alain="noirs", eval_before_cp=148, eval_after_cp=297,
                                       win_prob_drop=0.05)
        _, fiabilite = self._appeler_avec_reponse_simulee(texte, ctx)
        types = [a.get("fact_checker_type") for a in fiabilite.get("alertes", [])]
        self.assertIn("sens_qui_est_mieux_inverse", types)
        self.assertEqual(fiabilite["couleur"], "orange")

    def test_defaut3_verdict_sous_evalue_detecte(self):
        texte = "C'est une imprécision qui laisse filer l'essentiel de l'avantage."
        ctx = self._contexte_exercice(camp_alain="noirs", verdict_qualite_officiel="gaffe")
        _, fiabilite = self._appeler_avec_reponse_simulee(texte, ctx)
        types = [a.get("fact_checker_type") for a in fiabilite.get("alertes", [])]
        self.assertIn("mot_verdict_premiere_phrase", types)
        self.assertEqual(fiabilite["couleur"], "orange")

    def test_cas_correct_ne_declenche_aucune_alerte_fact_checker(self):
        texte = "Les Noirs sont mieux après ce coup. Tu conserves ton avantage, c'est une gaffe de l'adversaire."
        ctx = self._contexte_exercice(camp_alain="noirs", eval_before_cp=-148, eval_after_cp=-297,
                                       win_prob_drop=0.05, verdict_qualite_officiel="bon")
        _, fiabilite = self._appeler_avec_reponse_simulee(texte, ctx)
        types = [a.get("fact_checker_type") for a in fiabilite.get("alertes", [])]
        self.assertNotIn("pour_toi_colle_chiffre", types)
        self.assertNotIn("sens_qui_est_mieux_inverse", types)
        self.assertNotIn("mot_verdict_premiere_phrase", types)


@unittest.skipUnless(find_stockfish(), "Stockfish introuvable sur cette machine")
class TestExerciseAnswerSocketIODefauts134(unittest.TestCase):
    """Reconstitue les défauts 1 et 2 via le VRAI gestionnaire SocketIO
    d'exercice (même infrastructure que test_issue128.py,
    TestExerciseAnswerSocketIO : client de test Flask-SocketIO, chemins de
    données temporaires, API Claude simulée), pour les deux camps."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        tmp_dir = Path(cls._tmp.name)

        import config as config_module
        cls._config_module = config_module
        cls._anciens_config = _patch_config_paths_vers_tmp(config_module, tmp_dir)

        if "app" in sys.modules:
            raise RuntimeError(
                "app.py était déjà importé avant ce test : l'isolation des "
                "chemins de données ne peut plus être garantie (même "
                "contrainte que test_issue128.py — ne jamais exécuter "
                "test_issue128 et test_issue134 dans le même process)."
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

    def _capturer_appel_claude(self, texte_reponse):
        def _faux_call_claude(prompt_sys, messages, api_key, model, usage_path=None,
                               timeout_s=90, temperature=None):
            return texte_reponse

        patcher = patch.object(
            self.app_module.llm_coach, "_call_claude", side_effect=_faux_call_claude,
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _emettre_exercise_answer(self, fen_avant, camp_alain, uci, texte_reponse):
        self.app_module._current_exercise = {
            "source": "mes_erreurs",
            "fen_avant": fen_avant,
            "camp_alain": camp_alain,
            "coup_joue_san": "", "coup_joue_uci": "",
            "meilleur_coup_san": "", "meilleur_coup_uci": "",
            "solution": [], "categorie_tirage": None, "cle_historique": None,
            "niveau_tirage": None, "rating": None, "themes": [],
        }
        self._capturer_appel_claude(texte_reponse)
        self.client.emit("exercise_answer", {"uci": uci, "exercise_id": f"test-issue134-{camp_alain}"})
        recus = self.client.get_received()
        comment = next(e for e in recus if e["name"] == "exercise_comment")
        return comment["args"][0]

    def test_defaut1_pour_toi_colle_chiffre_cote_noirs(self):
        fen = "rnb1kbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR b KQkq - 0 1"  # dame noire manquante : Blancs favorisés
        payload = self._emettre_exercise_answer(
            fen, "noirs", "g8h6",
            "Position largement gagnante pour toi (-900)."
        )
        fact_checker_types = [
            a.get("fact_checker_type") for a in payload["fiabilite"].get("alertes", [])
            if a.get("type") == "fact_checker"
        ]
        self.assertIn("pour_toi_colle_chiffre", fact_checker_types)

    def test_defaut2_sens_inverse_cote_blancs(self):
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNB1KBNR w KQkq - 0 1"  # dame blanche manquante : Noirs favorisés
        payload = self._emettre_exercise_answer(
            fen, "blancs", "g1h3",
            "Ce coup est raisonnable, tu restes largement mieux."
        )
        fact_checker_types = [
            a.get("fact_checker_type") for a in payload["fiabilite"].get("alertes", [])
            if a.get("type") == "fact_checker"
        ]
        self.assertIn("sens_qui_est_mieux_inverse", fact_checker_types)

    def test_cas_correct_cote_noirs_aucune_alerte_fact_checker(self):
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNB1KBNR b KQkq - 0 1"  # dame blanche manquante : Noirs favorisés
        payload = self._emettre_exercise_answer(
            fen, "noirs", "g8h6",
            "Les Noirs sont mieux après ce coup. Tu conserves ton avantage."
        )
        fact_checker_types = [
            a.get("fact_checker_type") for a in payload["fiabilite"].get("alertes", [])
            if a.get("type") == "fact_checker"
        ]
        self.assertNotIn("pour_toi_colle_chiffre", fact_checker_types)
        self.assertNotIn("sens_qui_est_mieux_inverse", fact_checker_types)


if __name__ == "__main__":
    unittest.main()
