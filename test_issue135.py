"""
test_issue135.py — ChessCoach (issue #135, suite #125)

Tests pour le format standard des avis du coach (sections fixes à titres
imposés, identiques pour Claude et Mistral — cf. llm_coach.
_REPONSE_STRUCTUREE_ADDENDUM) : découpage côté serveur (avis_format.py),
journalisation section par section, adaptation du vérificateur
d'affirmations (fact_checker.py), et comportement du VRAI gestionnaire de
réponse d'exercice (app.on_exercise_answer/_on_exercise_answer_lichess) sur
les cas conforme / non conforme / vide / erreur, pour les sources « Mes
erreurs » et « Problèmes Lichess ».

Partie 1 : avis_format.py — découpage déterministe, aucun appel réseau.
Partie 2 : présence du format imposé dans le prompt système, aucun appel
           réseau.
Partie 3 : fact_checker.py — le contrôle du mot de verdict lit la rubrique
           "Évaluation rapide" plutôt que la première phrase du texte brut.
Partie 4 : llm_coach.get_coach_response (la vraie fonction) — journal
           (sections lues, indicateur de conformité, version du format).
Partie 5 : exécution du VRAI gestionnaire de réponse d'exercice via le
           client de test Flask-SocketIO (comme test_issue128.py/
           test_issue134.py) — API Claude simulée, isolation complète des
           fichiers personnels d'Alain via des chemins temporaires. Ce
           fichier importe app.py : ne JAMAIS l'exécuter dans le même
           process que test_issue128/test_issue134 (même contrainte, voir
           leurs en-têtes) — invoquer séparément :
    python3 -m unittest test_issue135
"""

import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import avis_format
import fact_checker
from engine_stockfish import find_stockfish
from test_issue128 import _patch_config_paths_vers_tmp, _restaure_config_paths


# =============================================================================
# Partie 1 : avis_format.py — découpage déterministe (aucun appel réseau)
# =============================================================================

AVIS_CONFORME_AVEC_EPOQUE = """## Coup joué
### Évaluation rapide
C'est une erreur qui laisse échapper l'essentiel de l'avantage.
### Points négatifs
- 31.Re7 abandonne le contrôle de la colonne e après 31...Txe7
- La tour recule sans but précis
### Points positifs
- Aucun.

## Meilleur coup
### Explication
31.Qb3 attaque directement b7 et force une défense passive.

## Coup de l'époque
30...e4 ferme le centre, non évalué.

## Conclusion
Avant de reculer une pièce, vérifie si elle a une case active disponible.
"""

AVIS_CONFORME_SANS_EPOQUE = """## Coup joué
### Évaluation rapide
Bon coup.
### Points négatifs
- Aucun.
### Points positifs
- Développe la pièce vers le centre.

## Meilleur coup
### Explication
C'est justement le coup que tu as joué.

## Conclusion
Continue à développer tes pièces avant d'attaquer.
"""


class TestAvisFormatParser(unittest.TestCase):
    def test_conforme_avec_coup_epoque(self):
        r = avis_format.parser_avis(AVIS_CONFORME_AVEC_EPOQUE)
        self.assertTrue(r["conforme"])
        self.assertTrue(r["sections"]["coup_epoque"].startswith("30...e4"))
        self.assertIn("31.Re7", r["sections"]["coup_joue_points_negatifs"])
        self.assertIn("31.Qb3", r["sections"]["meilleur_coup_explication"])
        self.assertTrue(r["sections"]["conclusion"].startswith("Avant de reculer"))

    def test_conforme_sans_coup_epoque(self):
        r = avis_format.parser_avis(AVIS_CONFORME_SANS_EPOQUE)
        self.assertTrue(r["conforme"])
        self.assertEqual(r["sections"]["coup_epoque"], "")

    def test_prose_libre_non_conforme(self):
        r = avis_format.parser_avis(
            "C'est une erreur. Le meilleur coup était Qb3. À l'époque, tu avais joué e4."
        )
        self.assertFalse(r["conforme"])
        self.assertEqual(r["sections"], {})

    def test_ordre_des_titres_incorrect_non_conforme(self):
        texte = AVIS_CONFORME_SANS_EPOQUE.replace(
            "## Coup joué", "## TEMP_COUP_JOUE"
        ).replace("## Meilleur coup", "## Coup joué").replace(
            "## TEMP_COUP_JOUE", "## Meilleur coup"
        )
        r = avis_format.parser_avis(texte)
        self.assertFalse(r["conforme"])

    def test_sous_rubrique_manquante_non_conforme(self):
        texte = AVIS_CONFORME_SANS_EPOQUE.replace(
            "### Points positifs\n- Développe la pièce vers le centre.\n\n", ""
        )
        r = avis_format.parser_avis(texte)
        self.assertFalse(r["conforme"])

    def test_texte_vide_non_conforme_sans_lever_d_exception(self):
        r = avis_format.parser_avis("")
        self.assertFalse(r["conforme"])
        self.assertEqual(r["sections"], {})

    def test_version_format_est_un_entier(self):
        self.assertIsInstance(avis_format.FORMAT_AVIS_VERSION, int)


# =============================================================================
# Partie 2 : présence du format imposé dans le prompt système (aucun appel
# réseau)
# =============================================================================

class TestPromptFormatImpose(unittest.TestCase):
    def setUp(self):
        import llm_coach
        self.llm_coach = llm_coach

    def test_titres_fixes_presents_et_identiques_pour_les_deux_ia(self):
        # _REPONSE_STRUCTUREE_ADDENDUM est injecté tel quel pour Claude
        # (get_coach_response) ET pour Mistral (get_mistral_response) —
        # vérifié une seule fois ici, pas besoin de dupliquer le test.
        addendum = self.llm_coach._REPONSE_STRUCTUREE_ADDENDUM
        for titre in (
            "## Coup joué", "### Évaluation rapide", "### Points négatifs",
            "### Points positifs", "## Meilleur coup", "### Explication",
            "## Coup de l'époque", "## Conclusion",
        ):
            self.assertIn(titre, addendum)

    def test_regle_numerotation_des_coups(self):
        addendum = self.llm_coach._REPONSE_STRUCTUREE_ADDENDUM
        self.assertIn("31.Re7", addendum)
        self.assertIn("30...Rxb6", addendum)

    def test_regle_non_vérifié_pour_fait_absent(self):
        self.assertIn("non vérifié", self.llm_coach._REPONSE_STRUCTUREE_ADDENDUM)

    def test_lichess_addendum_ne_contredit_plus_le_format_titre(self):
        # Avant l'issue #135, ce complément imposait une réponse "courte, 2
        # à 4 phrases, sans titre" — contradiction directe avec le format à
        # titres fixes. Vérifie que cette contradiction a disparu.
        self.assertNotIn("2 à 4", self.llm_coach._EXERCISE_LICHESS_ADDENDUM)
        self.assertIn("Coup de l'époque", self.llm_coach._EXERCISE_LICHESS_ADDENDUM)

    def test_build_context_text_numerote_les_coups_cites(self):
        contexte = {
            "fen_depart_exercice": "8/8/8/8/8/8/8/4k2K b - - 0 1",
            "fen": "8/8/8/8/8/8/8/4k2K b - - 0 1",
            "coup_propose": "Kd2",
            "coup_reel": "Ke2",
            "meilleur_coup": "Kf2",
            "mode_exercice": True,
        }
        texte = self.llm_coach._build_context_text(contexte)
        self.assertIn("1...Kd2", texte)
        self.assertIn("1...Ke2", texte)
        self.assertIn("1...Kf2", texte)


# =============================================================================
# Partie 3 : fact_checker.py — lecture ciblée de la rubrique "Évaluation
# rapide" (issue #135, suite #134/#128)
# =============================================================================

class TestFactCheckerFormatStructure(unittest.TestCase):
    FEN = "8/8/8/8/8/8/8/4k2K b - - 0 1"

    def test_mot_verdict_detecte_dans_evaluation_rapide_conforme(self):
        texte = AVIS_CONFORME_SANS_EPOQUE  # ouvre sur "Bon coup."
        ctx = {"fen": self.FEN, "verdict_qualite_officiel": "gaffe"}
        r = fact_checker.verifier_affirmations(texte, ctx, agent="claude", camp_alain="noirs")
        types = [a["type"] for a in r["alertes"]]
        self.assertIn("mot_verdict_premiere_phrase", types)

    def test_pas_de_fausse_alerte_quand_verdict_coherent_format_structure(self):
        texte = AVIS_CONFORME_SANS_EPOQUE  # "Bon coup."
        ctx = {"fen": self.FEN, "verdict_qualite_officiel": "bon"}
        r = fact_checker.verifier_affirmations(texte, ctx, agent="claude", camp_alain="noirs")
        types = [a["type"] for a in r["alertes"]]
        self.assertNotIn("mot_verdict_premiere_phrase", types)

    def test_titre_de_section_sans_mot_de_verdict_pas_de_crash(self):
        # Le titre "## Coup joué" (désormais la toute première ligne d'une
        # réponse conforme) ne contient aucun mot de qualité — s'assurer
        # que ça ne lève jamais d'alerte spuriely ni d'exception.
        texte = "## Coup joué\n### Évaluation rapide\nBon coup.\n"
        ctx = {"fen": self.FEN, "verdict_qualite_officiel": "bon"}
        r = fact_checker.verifier_affirmations(texte, ctx, agent="claude", camp_alain="noirs")
        self.assertIsInstance(r["alertes"], list)

    def test_repli_sur_premiere_phrase_si_format_non_conforme(self):
        # Texte non structuré : le contrôle doit continuer à s'appliquer
        # (repli sur l'ancien comportement), pas se taire silencieusement.
        texte = "C'est une imprécision qui laisse filer l'essentiel de l'avantage."
        ctx = {"fen": self.FEN, "verdict_qualite_officiel": "gaffe"}
        r = fact_checker.verifier_affirmations(texte, ctx, agent="claude", camp_alain="noirs")
        types = [a["type"] for a in r["alertes"]]
        self.assertIn("mot_verdict_premiere_phrase", types)


# =============================================================================
# Partie 4 : llm_coach.get_coach_response — journal (sections, conformité,
# version du format)
# =============================================================================

class TestJournalSectionsEtVersion(unittest.TestCase):
    def _contexte_exercice(self, **kwargs):
        ctx = {
            "mode_exercice": True,
            "fen": "8/8/8/8/8/8/8/4k2K b - - 0 1",
            "fen_depart_exercice": "8/8/8/8/8/8/8/4k2K b - - 0 1",
            "verdict_qualite": "bon",
        }
        ctx.update(kwargs)
        return ctx

    def _appeler(self, texte_reponse, log_path):
        import llm_coach
        with patch.object(llm_coach, "_call_claude", return_value=texte_reponse):
            return llm_coach.get_coach_response(
                messages=[{"role": "user", "content": "Avis ?"}],
                context=self._contexte_exercice(),
                coach_memory={},
                cfg={"llm_api_key": "fake-test-key-issue135", "llm_model": "claude-sonnet-5",
                     "coach_log_path": log_path, "usage_path": None, "coach_timeout_s": 5},
            )

    def _derniere_entree_journal(self, log_path):
        import json
        fichiers = sorted(log_path.parent.glob(f"{log_path.stem}*{log_path.suffix}"))
        self.assertTrue(fichiers, "aucun fichier de journal écrit")
        lignes = fichiers[-1].read_text(encoding="utf-8").strip().splitlines()
        return json.loads(lignes[-1])

    def test_journal_conforme(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "coach_calls_test135.log"
            self._appeler(AVIS_CONFORME_SANS_EPOQUE, log_path)
            entree = self._derniere_entree_journal(log_path)
            self.assertTrue(entree["avis_format_conforme"])
            self.assertEqual(entree["avis_format_version"], avis_format.FORMAT_AVIS_VERSION)
            self.assertIn("coup_joue_evaluation_rapide", entree["avis_sections"])

    def test_journal_non_conforme_rien_perdu(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "coach_calls_test135b.log"
            texte_libre = "Un avis en prose libre, sans aucun titre structuré."
            self._appeler(texte_libre, log_path)
            entree = self._derniere_entree_journal(log_path)
            self.assertFalse(entree["avis_format_conforme"])
            self.assertNotIn("avis_sections", entree)
            # Le texte brut reste toujours journalisé intégralement.
            self.assertEqual(entree["reponse"], texte_libre)


# =============================================================================
# Partie 5 : exécution du VRAI gestionnaire de réponse d'exercice (issue
# #135, tâche 7b) — client de test Flask-SocketIO, API Claude simulée,
# sources « Mes erreurs » et « Problèmes Lichess », cas conforme / non
# conforme / vide / erreur.
# =============================================================================

@unittest.skipUnless(find_stockfish(), "Stockfish introuvable sur cette machine")
class TestExerciseAnswerSocketIOFormat135(unittest.TestCase):

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
                "contrainte que test_issue128.py/test_issue134.py — ne "
                "jamais exécuter ces fichiers dans le même process)."
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

    FEN_NOIRS_AU_TRAIT = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNB1KBNR b KQkq - 0 1"
    UCI_NOIRS = "g8h6"

    def _poser_exercice(self, source: str):
        self.app_module._current_exercise = {
            "source": source,
            "fen_avant": self.FEN_NOIRS_AU_TRAIT,
            "camp_alain": "noirs",
            "coup_joue_san": "", "coup_joue_uci": "",
            "meilleur_coup_san": "", "meilleur_coup_uci": "",
            # Lichess : solution = le coup proposé lui-même, pour garantir
            # un verdict "bon" déterministe (coup_reussi) plutôt que de
            # dépendre d'un seuil d'équivalence Stockfish variable.
            "solution": [self.UCI_NOIRS], "categorie_tirage": "mat_en_1" if source == "lichess" else None,
            "cle_historique": "lichess:test135" if source == "lichess" else None,
            "niveau_tirage": 1000, "rating": 1000, "themes": [],
        }

    def _emettre_avec_reponse_simulee(self, source: str, texte_reponse=None, exception=None):
        self._poser_exercice(source)

        def _faux_call_claude(prompt_sys, messages, api_key, model, usage_path=None,
                               timeout_s=90, temperature=None):
            if exception is not None:
                raise exception
            return texte_reponse

        patcher = patch.object(self.app_module.llm_coach, "_call_claude", side_effect=_faux_call_claude)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.client.emit("exercise_answer", {"uci": self.UCI_NOIRS, "exercise_id": f"test135-{source}"})
        return self.client.get_received()

    def _comment(self, recus):
        return next((e for e in recus if e["name"] == "exercise_comment"), None)

    def _error(self, recus):
        return next((e for e in recus if e["name"] == "exercise_error"), None)

    # -- cas "réponse conforme" -------------------------------------------

    def test_mes_erreurs_reponse_conforme(self):
        recus = self._emettre_avec_reponse_simulee("mes_erreurs", texte_reponse=AVIS_CONFORME_SANS_EPOQUE)
        comment = self._comment(recus)
        self.assertIsNotNone(comment, "aucun exercise_comment reçu")
        payload = comment["args"][0]
        self.assertTrue(payload["avis_format_conforme"])
        self.assertEqual(payload["avis_format_version"], avis_format.FORMAT_AVIS_VERSION)
        self.assertIn("coup_joue_evaluation_rapide", payload["avis_sections"])
        self.assertIsNone(self._error(recus))

    def test_problemes_lichess_reponse_conforme(self):
        recus = self._emettre_avec_reponse_simulee("lichess", texte_reponse=AVIS_CONFORME_SANS_EPOQUE)
        comment = self._comment(recus)
        self.assertIsNotNone(comment, "aucun exercise_comment reçu")
        payload = comment["args"][0]
        self.assertTrue(payload["avis_format_conforme"])
        self.assertIn("coup_joue_evaluation_rapide", payload["avis_sections"])

    # -- cas "réponse non conforme" (texte brut à afficher tel quel) -----

    def test_mes_erreurs_reponse_non_conforme_rien_perdu(self):
        texte_libre = "C'est une erreur. Le meilleur coup était Qb3. À l'époque, tu avais joué e4."
        recus = self._emettre_avec_reponse_simulee("mes_erreurs", texte_reponse=texte_libre)
        comment = self._comment(recus)
        self.assertIsNotNone(comment)
        payload = comment["args"][0]
        self.assertFalse(payload["avis_format_conforme"])
        self.assertEqual(payload["avis_sections"], {})
        # Rien n'est perdu : le texte brut complet est toujours transmis.
        self.assertEqual(payload["text"], texte_libre)

    def test_problemes_lichess_reponse_non_conforme_rien_perdu(self):
        texte_libre = "Coup juste, bravo."
        recus = self._emettre_avec_reponse_simulee("lichess", texte_reponse=texte_libre)
        comment = self._comment(recus)
        self.assertIsNotNone(comment)
        payload = comment["args"][0]
        self.assertFalse(payload["avis_format_conforme"])
        self.assertEqual(payload["text"], texte_libre)

    # -- cas "réponse vide" ------------------------------------------------

    def test_mes_erreurs_reponse_vide(self):
        recus = self._emettre_avec_reponse_simulee("mes_erreurs", texte_reponse="")
        comment = self._comment(recus)
        self.assertIsNotNone(comment)
        payload = comment["args"][0]
        self.assertEqual(payload["text"], "")
        self.assertFalse(payload["avis_format_conforme"])
        self.assertIsNone(self._error(recus))

    def test_problemes_lichess_reponse_vide(self):
        recus = self._emettre_avec_reponse_simulee("lichess", texte_reponse="")
        comment = self._comment(recus)
        self.assertIsNotNone(comment)
        self.assertEqual(comment["args"][0]["text"], "")

    # -- cas "réponse d'erreur" (panne API) --------------------------------

    def test_mes_erreurs_reponse_erreur_api(self):
        recus = self._emettre_avec_reponse_simulee("mes_erreurs", exception=TimeoutError("test issue135"))
        self.assertIsNone(self._comment(recus), "aucun exercise_comment attendu en cas d'erreur API")
        erreur = self._error(recus)
        self.assertIsNotNone(erreur, "exercise_error attendu en cas d'erreur API")

    def test_problemes_lichess_reponse_erreur_api(self):
        recus = self._emettre_avec_reponse_simulee("lichess", exception=TimeoutError("test issue135"))
        self.assertIsNone(self._comment(recus))
        self.assertIsNotNone(self._error(recus))


if __name__ == "__main__":
    unittest.main()
