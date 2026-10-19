"""
version_info.py — ChessCoach, détection de version du code et étiquette de série

Module pour détecter et mémoriser la version du code source au démarrage de
l'application, ainsi que l'étiquette de série optionnelle. Ces informations
sont ensuite utilisées pour enrichir les logs des appels au coach et les notes.

Issue #124 : Suite #120 — enregistrer la version du code (automatique) et une
étiquette de série (optionnelle) avec chaque avis et chaque note.

Ce module est conçu pour être importé une seule fois au démarrage de l'appli
(par app.py) et expose :
  - get_version_info() : retourne le dict complet de version
  - VERSION_INFO : variable globale contenant ce dict (calculé une fois)

Le dict de version contient :
  - commit_hash : identifiant court du commit HEAD (ex: "a1b2c3d") ou "inconnue"
  - commit_message : première ligne du message de commit ou "inconnue"
  - modified : bool, True si des fichiers suivis ont des changements non commités
  - last_issue : numéro de la dernière issue citée dans l'historique récent, ou None
  - serie : étiquette de série depuis CHESSCOACH_SERIE (tronquée à 50 chars) ou ""
"""

import os
import re
import subprocess
from pathlib import Path

# Variable globale pour mémoriser la version (calculée une fois au démarrage)
VERSION_INFO: dict | None = None

# Longueur maximale pour l'étiquette de série
MAX_SERIE_LENGTH = 50

# Nombre de commits à examiner pour trouver une issue
NUM_COMMITS_TO_CHECK = 30


def _get_git_commit_hash(repo_path: Path) -> str:
    """Récupère l'identifiant court du commit HEAD.
    
    Args:
        repo_path: chemin vers le répertoire racine du dépôt git
        
    Returns:
        Identifiant court (7 caractères) ou "inconnue" en cas d'erreur.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short=7", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "inconnue"


def _get_git_commit_message(repo_path: Path) -> str:
    """Récupère la première ligne du message du commit HEAD.
    
    Args:
        repo_path: chemin vers le répertoire racine du dépôt git
        
    Returns:
        Première ligne du message ou "inconnue" en cas d'erreur.
    """
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--pretty=format:%s"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "inconnue"


def _is_git_repo_modified(repo_path: Path) -> bool:
    """Vérifie si des fichiers suivis par git ont des changements non commités.
    
    Args:
        repo_path: chemin vers le répertoire racine du dépôt git
        
    Returns:
        True si des modifications non commitées existent, False sinon.
    """
    try:
        # Vérifier les modifications (fichiers modifiés ou supprimés)
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            # Si la sortie n'est pas vide, il y a des modifications
            return len(result.stdout.strip()) > 0
    except Exception:
        pass
    return False


def _find_last_issue_in_commits(repo_path: Path, num_commits: int = NUM_COMMITS_TO_CHECK) -> str | None:
    """Cherche le numéro de la dernière issue citée dans l'historique récent.
    
    Cherche parmi les derniers commits des mentions de type :
      - "issue-N" (ex: "issue-124")
      - "issue N" (ex: "issue 124")
      - "#N" (ex: "#124")
      - "worktree-issue-N" (ex: "worktree-issue-124")
    
    Args:
        repo_path: chemin vers le répertoire racine du dépôt git
        num_commits: nombre de commits à examiner
        
    Returns:
        Numéro de l'issue la plus récente trouvée, ou None si aucune.
    """
    try:
        # Récupérer les messages des derniers commits
        result = subprocess.run(
            ["git", "log", f"-n{num_commits}", "--pretty=format:%s"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            messages = result.stdout.strip().split('\n')
            
            # Patterns à rechercher (par ordre de priorité)
            # On cherche des numéros d'issue valides (entiers positifs)
            patterns = [
                r'worktree-issue-(\d+)',  # worktree-issue-124
                r'issue-(\d+)',           # issue-124
                r'#(\d+)',                # #124
                r'issue\s+(\d+)',        # issue 124
            ]
            
            last_issue = None
            for message in messages:
                for pattern in patterns:
                    matches = re.findall(pattern, message)
                    for match in matches:
                        issue_num = match
                        # Vérifier que c'est un numéro valide
                        if issue_num.isdigit():
                            current_issue = int(issue_num)
                            if last_issue is None or current_issue > last_issue:
                                last_issue = current_issue
            
            return str(last_issue) if last_issue is not None else None
    except Exception:
        pass
    return None


def _get_serie_label() -> str:
    """Récupère l'étiquette de série depuis la variable d'environnement.
    
    Lit CHESSCOACH_SERIE et la tronque à MAX_SERIE_LENGTH caractères.
    
    Returns:
        L'étiquette de série (éventuellement vide) ou "" si non définie.
    """
    serie = os.environ.get("CHESSCOACH_SERIE", "")
    if not isinstance(serie, str):
        return ""
    # Tronquer à la longueur maximale
    return serie[:MAX_SERIE_LENGTH]


def _detect_version_info(repo_path: Path | None = None) -> dict:
    """Détecte toutes les informations de version.
    
    Args:
        repo_path: chemin vers le répertoire racine du dépôt git.
                   Si None, essaie de trouver le dépôt parent du fichier courant.
    
    Returns:
        Dict contenant :
          - commit_hash: str
          - commit_message: str
          - modified: bool
          - last_issue: str | None
          - serie: str
    """
    global VERSION_INFO
    
    # Si déjà calculé, retourner la valeur mémorisée
    if VERSION_INFO is not None:
        return VERSION_INFO
    
    # Déterminer le chemin du dépôt
    if repo_path is None:
        # Essayer de trouver le dépôt parent du fichier courant
        current_file = Path(__file__).resolve()
        repo_path = current_file.parent
        # Remonter jusqu'à trouver un .git
        for _ in range(10):  # Limite de sécurité
            if (repo_path / ".git").exists():
                break
            repo_path = repo_path.parent
        else:
            repo_path = None
    
    # Si pas de dépôt git trouvé, tout vaut "inconnue"
    if repo_path is None or not (repo_path / ".git").exists():
        VERSION_INFO = {
            "commit_hash": "inconnue",
            "commit_message": "inconnue",
            "modified": False,
            "last_issue": None,
            "serie": _get_serie_label(),
        }
        return VERSION_INFO
    
    # Détecter les informations git
    commit_hash = _get_git_commit_hash(repo_path)
    commit_message = _get_git_commit_message(repo_path)
    modified = _is_git_repo_modified(repo_path)
    last_issue = _find_last_issue_in_commits(repo_path)
    serie = _get_serie_label()
    
    # Si git a échoué (commit_hash est "inconnue"), tout vaut "inconnue"
    if commit_hash == "inconnue":
        VERSION_INFO = {
            "commit_hash": "inconnue",
            "commit_message": "inconnue",
            "modified": False,
            "last_issue": None,
            "serie": serie,
        }
    else:
        VERSION_INFO = {
            "commit_hash": commit_hash,
            "commit_message": commit_message,
            "modified": modified,
            "last_issue": last_issue,
            "serie": serie,
        }
    
    return VERSION_INFO


def get_version_info() -> dict:
    """Retourne les informations de version du code.
    
    Cette fonction doit être appelée une fois au démarrage de l'application.
    Les informations sont calculées une seule fois et mémorisées.
    
    Returns:
        Dict contenant :
          - commit_hash: str (identifiant court du commit HEAD)
          - commit_message: str (première ligne du message)
          - modified: bool (True si des fichiers suivis ont des changements non commités)
          - last_issue: str | None (numéro de la dernière issue citée)
          - serie: str (étiquette de série depuis CHESSCOACH_SERIE)
    """
    return _detect_version_info()


def get_version_string() -> str:
    """Retourne une chaîne formatée représentant la version.
    
    Format : "commit_hash (commit_message) [last_issue] [modified?] [serie]"
    
    Returns:
        Chaîne formatée ou "inconnue" si git est absent.
    """
    info = get_version_info()
    
    if info["commit_hash"] == "inconnue":
        return "inconnue"
    
    parts = [info["commit_hash"]]
    if info["commit_message"] != "inconnue":
        parts.append(f"({info['commit_message'][:50]})")
    if info["last_issue"]:
        parts.append(f"issue-{info['last_issue']}")
    if info["modified"]:
        parts.append("modifié")
    if info["serie"]:
        parts.append(f"série:{info['serie']}")
    
    return " ".join(parts)


# Initialisation automatique au premier import
# (mais seulement si ce module est importé directement, pas via un import dans un test)
if __name__ != "__main__":
    # Ne pas calculer automatiquement à l'import
    # L'appelant doit appeler explicitement get_version_info()
    pass
