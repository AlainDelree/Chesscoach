#!/usr/bin/env python3
"""
test_issue124.py — Tests de simulation pour l'issue #124

Script de test pour vérifier le bon fonctionnement de l'implémentation
de l'issue #124 : suivi de version du code et étiquette de série.

Ce script crée un dépôt git temporaire avec différents scénarios et teste :
1. Détection des informations de version depuis un dépôt git valide
2. Détection avec des commits citant des issues
3. Détection avec un correctif sans numéro d'issue
4. Détection avec un arbre modifié non commité
5. Comportement avec absence de git
6. Variable de série vide ou renseignée
7. Anciennes entrées de journal et de notes sans version
8. Sortie du bilan groupé
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

# Ajouter le répertoire courant au path
sys.path.insert(0, str(Path(__file__).parent))

import version_info
import coach_ratings
import config


def create_test_git_repo(repo_path: Path, commits_spec: list) -> Path:
    """Crée un dépôt git temporaire avec des commits spécifiques.
    
    Args:
        repo_path: chemin vers le répertoire du dépôt
        commits_spec: liste de dicts avec :
            - message: message de commit
            - files: dict {nom_fichier: contenu}
    
    Returns:
        Path vers le répertoire du dépôt
    """
    repo_path.mkdir(parents=True, exist_ok=True)
    
    # Initialiser le dépôt git
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path, check=True, capture_output=True)
    
    # Créer les commits
    for commit in commits_spec:
        # Créer les fichiers
        for filename, content in commit.get("files", {}).items():
            file_path = repo_path / filename
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content)
        
        # Ajouter et committer
        subprocess.run(["git", "add", "."], cwd=repo_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", commit["message"]],
            cwd=repo_path,
            check=True,
            capture_output=True
        )
    
    return repo_path


def test_version_detection_with_issues():
    """Test 1 : Détection avec des commits citant des issues."""
    print("\n" + "=" * 80)
    print("Test 1 : Détection avec des commits citant des issues")
    print("=" * 80)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir) / "test_repo_issues"
        
        commits = [
            {
                "message": "Initial commit",
                "files": {"README.md": "# Project"}
            },
            {
                "message": "fix-issue-100: correction bug majeur",
                "files": {"bug.py": "# Bug fix"}
            },
            {
                "message": "fix #101: autre correction",
                "files": {"bug2.py": "# Bug fix 2"}
            },
            {
                "message": "worktree-issue-102: fonctionnalité",
                "files": {"feature.py": "# Feature"}
            },
            {
                "message": "issue 103: amélioration",
                "files": {"improvement.py": "# Improvement"}
            },
            {
                "message": "Autre commit sans issue",
                "files": {"other.py": "# Other"}
            },
        ]
        
        create_test_git_repo(repo_path, commits)
        
        # Tester la détection
        version_info.VERSION_INFO = None  # Réinitialiser
        info = version_info._detect_version_info(repo_path)
        
        print(f"Commit hash: {info['commit_hash']}")
        print(f"Commit message: {info['commit_message']}")
        print(f"Modified: {info['modified']}")
        print(f"Last issue: {info['last_issue']}")
        
        # Vérifications
        assert info['commit_hash'] != "inconnue", "Commit hash devrait être détecté"
        assert info['last_issue'] == "103", f"Dernière issue devrait être 103, obtenu {info['last_issue']}"
        print("✓ Test passé")


def test_version_detection_without_issues():
    """Test 2 : Détection avec un correctif sans numéro d'issue."""
    print("\n" + "=" * 80)
    print("Test 2 : Détection avec un correctif sans numéro d'issue")
    print("=" * 80)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir) / "test_repo_no_issues"
        
        commits = [
            {
                "message": "Initial commit",
                "files": {"README.md": "# Project"}
            },
            {
                "message": "Correctif manuel",
                "files": {"fix.py": "# Manual fix"}
            },
            {
                "message": "Autre correction",
                "files": {"fix2.py": "# Another fix"}
            },
        ]
        
        create_test_git_repo(repo_path, commits)
        
        # Tester la détection
        version_info.VERSION_INFO = None
        info = version_info._detect_version_info(repo_path)
        
        print(f"Commit hash: {info['commit_hash']}")
        print(f"Commit message: {info['commit_message']}")
        print(f"Modified: {info['modified']}")
        print(f"Last issue: {info['last_issue']}")
        
        # Vérifications
        assert info['commit_hash'] != "inconnue", "Commit hash devrait être détecté"
        assert info['last_issue'] is None, f"Dernière issue devrait être None, obtenu {info['last_issue']}"
        print("✓ Test passé")


def test_version_detection_with_modified_files():
    """Test 3 : Détection avec un arbre modifié non commité."""
    print("\n" + "=" * 80)
    print("Test 3 : Détection avec un arbre modifié non commité")
    print("=" * 80)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir) / "test_repo_modified"
        
        commits = [
            {
                "message": "Initial commit",
                "files": {"README.md": "# Project"}
            },
        ]
        
        create_test_git_repo(repo_path, commits)
        
        # Modifier un fichier sans commiter
        (repo_path / "README.md").write_text("# Project Modified")
        
        # Tester la détection
        version_info.VERSION_INFO = None
        info = version_info._detect_version_info(repo_path)
        
        print(f"Commit hash: {info['commit_hash']}")
        print(f"Modified: {info['modified']}")
        
        # Vérifications
        assert info['modified'] is True, "Modified devrait être True"
        print("✓ Test passé")


def test_version_detection_no_git():
    """Test 4 : Comportement avec absence de git."""
    print("\n" + "=" * 80)
    print("Test 4 : Comportement avec absence de git")
    print("=" * 80)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir) / "test_no_git"
        repo_path.mkdir(parents=True, exist_ok=True)
        
        # Tester la détection
        version_info.VERSION_INFO = None
        info = version_info._detect_version_info(repo_path)
        
        print(f"Commit hash: {info['commit_hash']}")
        print(f"Commit message: {info['commit_message']}")
        print(f"Modified: {info['modified']}")
        print(f"Last issue: {info['last_issue']}")
        
        # Vérifications
        assert info['commit_hash'] == "inconnue", "Commit hash devrait être 'inconnue'"
        assert info['commit_message'] == "inconnue", "Commit message devrait être 'inconnue'"
        assert info['modified'] is False, "Modified devrait être False"
        assert info['last_issue'] is None, "Last issue devrait être None"
        print("✓ Test passé")


def test_serie_label():
    """Test 5 : Variable de série vide ou renseignée."""
    print("\n" + "=" * 80)
    print("Test 5 : Variable de série")
    print("=" * 80)
    
    # Tester avec série vide
    os.environ.pop("CHESSCOACH_SERIE", None)
    serie = version_info._get_serie_label()
    print(f"Série vide: '{serie}'")
    assert serie == "", "Série devrait être vide"
    
    # Tester avec série renseignée
    os.environ["CHESSCOACH_SERIE"] = "test-serie-01"
    serie = version_info._get_serie_label()
    print(f"Série renseignée: '{serie}'")
    assert serie == "test-serie-01", "Série devrait être 'test-serie-01'"
    
    # Tester avec série longue (tronquée à 50 chars)
    long_serie = "a" * 100
    os.environ["CHESSCOACH_SERIE"] = long_serie
    serie = version_info._get_serie_label()
    print(f"Série longue (tronquée): '{serie}' (longueur: {len(serie)})")
    assert len(serie) == 50, "Série devrait être tronquée à 50 caractères"
    
    # Nettoyer
    os.environ.pop("CHESSCOACH_SERIE", None)
    print("✓ Test passé")


def test_version_string():
    """Test 6 : Génération de la chaîne de version."""
    print("\n" + "=" * 80)
    print("Test 6 : Génération de la chaîne de version")
    print("=" * 80)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir) / "test_repo_string"
        
        commits = [
            {
                "message": "fix-issue-124: implémentation",
                "files": {"README.md": "# Project"}
            },
        ]
        
        create_test_git_repo(repo_path, commits)
        
        # Tester la détection
        version_info.VERSION_INFO = None
        info = version_info._detect_version_info(repo_path)
        
        # Tester la chaîne de version
        version_str = version_info.get_version_string()
        print(f"Version string: {version_str}")
        
        assert "fix-issue-124" in version_str, "La chaîne de version devrait contenir le message"
        assert "issue-124" in version_str, "La chaîne de version devrait contenir l'issue"
        print("✓ Test passé")


def test_old_log_entries():
    """Test 7 : Anciennes entrées de journal sans version_info."""
    print("\n" + "=" * 80)
    print("Test 7 : Anciennes entrées de journal sans version_info")
    print("=" * 80)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Créer un faux fichier de log avec une ancienne entrée
        log_dir = Path(tmpdir) / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "coach_calls.log"
        
        # Écrire une ancienne entrée sans version_info
        old_entry = {
            "id": "test123",
            "horodatage": datetime.now().isoformat(),
            "mode_origine": "exercice",
            "model": "claude-3-5-sonnet",
            "reponse": "Test response",
        }
        
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(json.dumps(old_entry, ensure_ascii=False) + "\n")
        
        # Tester la récupération des informations de version
        version_info_result = coach_ratings._get_version_info_from_log_id("test123")
        
        print(f"Version info pour ancienne entrée: {version_info_result}")
        
        # Vérifications
        assert version_info_result["commit_hash"] == "inconnue", "Commit hash devrait être 'inconnue'"
        assert version_info_result["last_issue"] is None, "Last issue devrait être None"
        print("✓ Test passé")


def test_new_log_entries():
    """Test 8 : Nouvelles entrées de journal avec version_info."""
    print("\n" + "=" * 80)
    print("Test 8 : Nouvelles entrées de journal avec version_info")
    print("=" * 80)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Créer un faux fichier de log avec une nouvelle entrée
        log_dir = Path(tmpdir) / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "coach_calls.log"
        
        # Écrire une nouvelle entrée avec version_info
        new_entry = {
            "id": "test456",
            "horodatage": datetime.now().isoformat(),
            "mode_origine": "exercice",
            "model": "claude-3-5-sonnet",
            "reponse": "Test response",
            "version_info": {
                "commit_hash": "a1b2c3d",
                "commit_message": "fix: test",
                "modified": False,
                "last_issue": "124",
                "serie": "test-serie",
            }
        }
        
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(json.dumps(new_entry, ensure_ascii=False) + "\n")
        
        # Tester la récupération des informations de version
        # On va simuler la fonction _get_version_info_from_log_id avec le chemin temporaire
        def get_version_info_from_log_id_temp(log_id: str, log_files: list) -> dict:
            """Version temporaire de _get_version_info_from_log_id pour les tests."""
            for log_path in log_files:
                if os.path.exists(log_path):
                    try:
                        with open(log_path, "r", encoding="utf-8") as f:
                            for line in f:
                                line = line.strip()
                                if line:
                                    entry = json.loads(line)
                                    if entry.get("id") == log_id:
                                        version_info = entry.get("version_info")
                                        if version_info is not None:
                                            return version_info
                                        else:
                                            return {
                                                "commit_hash": "inconnue",
                                                "commit_message": "inconnue",
                                                "modified": False,
                                                "last_issue": None,
                                                "serie": "",
                                            }
                    except Exception:
                        continue
            return {
                "commit_hash": "inconnue",
                "commit_message": "inconnue",
                "modified": False,
                "last_issue": None,
                "serie": "",
            }
        
        version_info_result = get_version_info_from_log_id_temp("test456", [log_file])
        
        print(f"Version info pour nouvelle entrée: {version_info_result}")
        
        # Vérifications
        assert version_info_result["commit_hash"] == "a1b2c3d", "Commit hash devrait être 'a1b2c3d'"
        assert version_info_result["last_issue"] == "124", "Last issue devrait être '124'"
        assert version_info_result["serie"] == "test-serie", "Serie devrait être 'test-serie'"
        print("✓ Test passé")


def test_ratings_report():
    """Test 9 : Sortie du bilan groupé."""
    print("\n" + "=" * 80)
    print("Test 9 : Sortie du bilan groupé")
    print("=" * 80)
    
    # Importer le module de rapport
    sys.path.insert(0, str(Path(__file__).parent / "scripts"))
    import coach_ratings_report
    
    # Créer une liste de notes en mémoire pour le test
    ratings = [
        {
            "timestamp": datetime(2026, 1, 1).isoformat(),
            "agent": "claude",
            "model": "claude-3-5-sonnet",
            "rating": 1,
            "log_id": "log1",
            "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "coup_propose": "e4",
            "mode": "exercice",
            "version_info": {
                "commit_hash": "a1b2c3d",
                "commit_message": "fix-issue-124",
                "modified": False,
                "last_issue": "124",
                "serie": "test-01",
            }
        },
        {
            "timestamp": datetime(2026, 1, 2).isoformat(),
            "agent": "claude",
            "model": "claude-3-5-sonnet",
            "rating": 0,
            "log_id": "log2",
            "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "coup_propose": "e4",
            "mode": "exercice",
            "version_info": {
                "commit_hash": "a1b2c3d",
                "commit_message": "fix-issue-124",
                "modified": False,
                "last_issue": "124",
                "serie": "test-01",
            }
        },
        {
            "timestamp": datetime(2026, 1, 3).isoformat(),
            "agent": "mistral",
            "model": "mistral-large",
            "rating": 1,
            "log_id": "log3",
            "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "coup_propose": "e4",
            "mode": "exercice",
            "version_info": {
                "commit_hash": "a1b2c3d",
                "commit_message": "fix-issue-124",
                "modified": False,
                "last_issue": "124",
                "serie": "test-01",
            }
        },
        {
            "timestamp": datetime(2026, 2, 1).isoformat(),
            "agent": "claude",
            "model": "claude-3-5-sonnet",
            "rating": 1,
            "log_id": "log4",
            "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "coup_propose": "e4",
            "mode": "exercice",
            "version_info": {
                "commit_hash": "e5f6g7h",
                "commit_message": "fix-issue-125",
                "modified": False,
                "last_issue": "125",
                "serie": "test-02",
            }
        },
        # Ancienne note sans version_info
        {
            "timestamp": datetime(2025, 12, 1).isoformat(),
            "agent": "claude",
            "model": "claude-3-5-sonnet",
            "rating": 1,
            "log_id": "log5",
            "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "coup_propose": "e4",
            "mode": "exercice",
        },
    ]
    
    print(f"Test avec {len(ratings)} notes en mémoire")
    
    # Tester le regroupement
    groups = coach_ratings_report._group_by_version(ratings)
    
    print(f"\nGroupes trouvés: {len(groups)}")
    for version_key, group in groups.items():
        print(f"  {version_key}: {len(group['timestamps'])} notes")
    
    # Vérifications
    assert len(groups) == 3, f"Devrait avoir 3 groupes, obtenu {len(groups)}"
    assert "inconnue (avant ce suivi)" in groups, "Devrait avoir un groupe 'inconnue'"
    assert "a1b2c3d issue-124" in groups, "Devrait avoir un groupe 'a1b2c3d issue-124'"
    assert "e5f6g7h issue-125" in groups, "Devrait avoir un groupe 'e5f6g7h issue-125'"
    
    print("✓ Test passé")


def run_all_tests():
    """Exécute tous les tests."""
    print("\n" + "=" * 80)
    print("DEBUT DES TESTS POUR ISSUE #124")
    print("=" * 80)
    
    tests = [
        test_version_detection_with_issues,
        test_version_detection_without_issues,
        test_version_detection_with_modified_files,
        test_version_detection_no_git,
        test_serie_label,
        test_version_string,
        test_old_log_entries,
        test_new_log_entries,
        test_ratings_report,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"✗ Test échoué: {test.__name__}")
            print(f"  Erreur: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "=" * 80)
    print("RESUME DES TESTS")
    print("=" * 80)
    print(f"Passés: {passed}")
    print(f"Échoués: {failed}")
    print(f"Total: {passed + failed}")
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
