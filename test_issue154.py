"""
test_issue154.py — ChessCoach (issue #154)

Tests courts pour la robustesse des captures d'erreur (issue #154) :
1. config.set_llm_model : échec d'écriture simulé -> la fonction renvoie un
   échec (False) et une trace de niveau avertissement est émise, sans
   changer le format du fichier ni la liste des modèles.
2. scripts/fiche_dernier_exercice._ecrire_atomique : si l'écriture échoue
   (ici : l'étape finale de remplacement), le fichier d'état existant
   n'est jamais tronqué — son ancien contenu reste intact — et le fichier
   temporaire est nettoyé.
3. Un site représentatif par catégorie de correctif choisie pour les
   captures silencieuses (S110/S112/E722) :
   - contextlib.suppress avec exception précise déjà en place :
     config._charger_choix_modele_llm (fichier de choix corrompu).
   - exception restreinte (narrowed depuis un bare `except:`) :
     scripts.fiche_dernier_exercice.lire_jsonl (ligne JSON invalide).
   - trace de niveau debug (repli inchangé) :
     coach_ratings.get_all_ratings (fichier de notes corrompu).

Aucun de ces tests n'importe app.py ni ne crée de moteur Stockfish —
pas d'arrêt de moteur requis (cf. docs/contexte/tests.md).
"""

import json
import logging
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))

import config
import coach_ratings
from scripts import fiche_dernier_exercice


class TestSetLlmModelEchecEcriture(unittest.TestCase):
    """Issue #154, point 3 : échec d'écriture du choix de modèle."""

    def setUp(self):
        self._ancien_chemin = config.LLM_MODEL_CHOICE_PATH
        self._ancien_modele = config.LLM_MODEL

    def tearDown(self):
        config.LLM_MODEL_CHOICE_PATH = self._ancien_chemin
        config.LLM_MODEL = self._ancien_modele

    def test_echec_ecriture_renvoie_echec_et_trace_avertissement(self):
        with tempfile.TemporaryDirectory() as d:
            # Un dossier à la place du fichier attendu : write_text() y
            # échoue avec IsADirectoryError (sous-classe d'OSError), sans
            # avoir besoin de mocker quoi que ce soit de plus bas niveau.
            config.LLM_MODEL_CHOICE_PATH = Path(d)
            autre_modele = (
                config.LLM_MODEL_HAIKU if self._ancien_modele != config.LLM_MODEL_HAIKU
                else config.LLM_MODEL_SONNET
            )
            with self.assertLogs("config", level="WARNING") as cm:
                resultat = config.set_llm_model(autre_modele)

        self.assertFalse(resultat)
        self.assertTrue(any("échec d'écriture" in message for message in cm.output))
        # Format du fichier et liste des modèles inchangés par ce correctif.
        self.assertIn(config.LLM_MODEL_HAIKU, config.LLM_MODEL_CHOICES)
        self.assertIn(config.LLM_MODEL_SONNET, config.LLM_MODEL_CHOICES)

    def test_model_id_invalide_renvoie_toujours_echec_sans_trace(self):
        # Comportement préexistant, non modifié par cette issue : aucune
        # trace à ce niveau, juste un refus (cas distinct de l'échec
        # d'écriture ci-dessus).
        resultat = config.set_llm_model("modele-qui-n-existe-pas")
        self.assertFalse(resultat)


class TestEcritureAtomiqueFicheDernierExercice(unittest.TestCase):
    """Issue #154, point 4 : écriture atomique (fichier temporaire + remplacement)."""

    def test_echec_au_remplacement_laisse_l_ancien_contenu_intact(self):
        with tempfile.TemporaryDirectory() as d:
            chemin = Path(d) / "fiches_dernier_exercice.md"
            chemin.write_text("ancien contenu", encoding="utf-8")

            with patch.object(
                fiche_dernier_exercice.os, "replace",
                side_effect=OSError("échec simulé du remplacement"),
            ):
                with self.assertRaises(OSError):
                    fiche_dernier_exercice._ecrire_atomique(str(chemin), "contenu tronque si pas atomique")

            # L'ancien contenu n'a jamais été touché : pas de troncature.
            self.assertEqual(chemin.read_text(encoding="utf-8"), "ancien contenu")
            # Le fichier temporaire ne doit pas traîner derrière.
            self.assertEqual(list(Path(d).glob(".tmp_*")), [])

    def test_ecriture_normale_remplace_bien_le_contenu(self):
        with tempfile.TemporaryDirectory() as d:
            chemin = Path(d) / "fiches_dernier_exercice.md"
            chemin.write_text("ancien contenu", encoding="utf-8")

            fiche_dernier_exercice._ecrire_atomique(str(chemin), "nouveau contenu")

            self.assertEqual(chemin.read_text(encoding="utf-8"), "nouveau contenu")
            self.assertEqual(list(Path(d).glob(".tmp_*")), [])


class TestSitesRepresentatifsParCategorie(unittest.TestCase):
    """Issue #154, point 6 : un site par catégorie de correctif."""

    def test_suppress_fichier_choix_modele_corrompu(self):
        """contextlib.suppress avec exception précise (config._charger_choix_modele_llm)."""
        ancien_chemin = config.LLM_MODEL_CHOICE_PATH
        ancien_env = os.environ.pop("CHESSCOACH_LLM_MODEL", None)
        try:
            with tempfile.TemporaryDirectory() as d:
                chemin = Path(d) / "choix.json"
                chemin.write_text("{ceci n'est pas du json valide", encoding="utf-8")
                config.LLM_MODEL_CHOICE_PATH = chemin
                resultat = config._charger_choix_modele_llm()
        finally:
            config.LLM_MODEL_CHOICE_PATH = ancien_chemin
            if ancien_env is not None:
                os.environ["CHESSCOACH_LLM_MODEL"] = ancien_env

        # Repli silencieux attendu : Sonnet par défaut, aucune exception levée.
        self.assertEqual(resultat, config.LLM_MODEL_SONNET)

    def test_exception_restreinte_ligne_jsonl_invalide(self):
        """Exception restreinte (json.JSONDecodeError) : fiche_dernier_exercice.lire_jsonl."""
        ancien_data = fiche_dernier_exercice.DATA
        try:
            with tempfile.TemporaryDirectory() as d:
                fiche_dernier_exercice.DATA = d
                chemin = Path(d) / "exemple.jsonl"
                chemin.write_text(
                    '{"valide": 1}\nceci n\'est pas une ligne JSON\n{"valide": 2}\n',
                    encoding="utf-8",
                )
                resultat = fiche_dernier_exercice.lire_jsonl("exemple.jsonl")
        finally:
            fiche_dernier_exercice.DATA = ancien_data

        self.assertEqual(resultat, [{"valide": 1}, {"valide": 2}])

    def test_trace_debug_fichier_notes_corrompu(self):
        """Trace de niveau debug, repli inchangé : coach_ratings.get_all_ratings."""
        ancien_path = coach_ratings.RATINGS_PATH
        try:
            with tempfile.TemporaryDirectory() as d:
                chemin = Path(d) / "coach_ratings.jsonl"
                # Ligne syntaxiquement valide en UTF-8 mais pas en JSON une
                # fois ouverte en lecture texte standard : simuler une
                # erreur de lecture à l'aide d'un chemin qui n'est pas un
                # fichier régulier (répertoire) force une OSError à
                # l'ouverture, capturée par le même except Exception.
                coach_ratings.RATINGS_PATH = str(chemin)
                chemin.mkdir()
                with self.assertLogs("chesscoach.coach_ratings", level="DEBUG") as cm:
                    resultat = coach_ratings.get_all_ratings()
        finally:
            coach_ratings.RATINGS_PATH = ancien_path

        self.assertEqual(resultat, [])
        self.assertTrue(any("get_all_ratings" in message for message in cm.output))


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
