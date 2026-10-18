#!/usr/bin/env python3
"""
Script d'estimation du coût API par jour pour ChessCoach (issue #119).

Lit tous les fichiers coach_calls*.log et affiche, pour un jour donné
(aujourd'hui par défaut, avec une option pour une date précise ou une période) :
- par agent et par modèle : nombre d'appels, jetons d'entrée/sortie, coût estimé
- les totaux par devise
- les appels sans consommation enregistrée (comptés à part)

Affiche un avertissement si des prix utilisés sont marqués "à vérifier".
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

# Chemin vers le fichier de prix (relatif au script ou chemin absolu)
DEFAULT_PRICES_PATH = Path(__file__).parent.parent / "data" / "token_prices.json"


def charger_prix(chemin: Path | str | None = None) -> dict:
    """Charge le fichier de prix des tokens.
    
    Args:
        chemin : chemin vers le fichier JSON de prix (défaut : data/token_prices.json)
        
    Returns:
        Dictionnaire des prix par modèle, ou dict vide si erreur.
    """
    if chemin is None:
        chemin = DEFAULT_PRICES_PATH
    else:
        chemin = Path(chemin)
    
    if not chemin.exists():
        print(f"Avertissement : fichier de prix introuvable : {chemin}", file=sys.stderr)
        return {}
    
    try:
        with open(chemin, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("modeles", {})
    except (json.JSONDecodeError, OSError) as e:
        print(f"Erreur de lecture du fichier de prix {chemin} : {e}", file=sys.stderr)
        return {}


def obtenir_prix_modele(modele: str, prix: dict) -> tuple[float | None, float | None, str | None]:
    """Obtient le prix pour un modèle donné.
    
    Args:
        modele : identifiant du modèle
        prix : dictionnaire des prix chargé par charger_prix()
        
    Returns:
        Tuple (prix_entree, prix_sortie, devise) ou (None, None, None) si modèle inconnu.
    """
    # Normaliser le nom du modèle (supprimer préfixes comme "mistral:" ou "claude:")
    modele_net = modele
    if ":" in modele:
        modele_net = modele.split(":", 1)[1]
    
    info = prix.get(modele_net)
    if not info:
        return None, None, None
    
    return (
        info.get("prix_entree"),
        info.get("prix_sortie"),
        info.get("devise"),
    )


def est_verifie(modele: str, prix: dict) -> bool:
    """Vérifie si un modèle a un prix vérifié.
    
    Args:
        modele : identifiant du modèle
        prix : dictionnaire des prix
        
    Returns:
        True si le modèle est marqué comme vérifié, False sinon.
    """
    modele_net = modele.split(":", 1)[1] if ":" in modele else modele
    info = prix.get(modele_net)
    if not info:
        return False
    return info.get("verifie", False)


def parser_date(date_str: str) -> datetime | None:
    """Parse une date au format AAAA-MM-JJ ou AAAA-MM-JJ.
    
    Args:
        date_str : chaîne de date
        
    Returns:
        Objet datetime ou None si invalide.
    """
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        pass
    return None


def extraire_date_de_fichier(fichier: Path) -> datetime | None:
    """Extrait la date du nom de fichier coach_calls-YYYY-MM.log.
    
    Args:
        fichier : chemin du fichier
        
    Returns:
        Date extraite ou None.
    """
    # Pattern : coach_calls-YYYY-MM.log
    match = re.search(r'coach_calls-(\d{4}-\d{2})\.log', fichier.name)
    if match:
        date_str = match.group(1)
        try:
            return datetime.strptime(date_str, "%Y-%m")
        except ValueError:
            pass
    return None


def lire_entrees_journal(fichier: Path) -> list[dict]:
    """Lit toutes les entrées d'un fichier journal coach_calls.
    
    Args:
        fichier : chemin du fichier journal
        
    Returns:
        Liste de dictionnaires (une entrée par ligne JSON).
    """
    if not fichier.exists():
        return []
    
    entrees = []
    try:
        with open(fichier, "r", encoding="utf-8") as f:
            for ligne in f:
                ligne = ligne.strip()
                if ligne:
                    try:
                        entrees.append(json.loads(ligne))
                    except json.JSONDecodeError:
                        # Ignorer les lignes invalides
                        continue
    except OSError as e:
        print(f"Erreur de lecture de {fichier} : {e}", file=sys.stderr)
    
    return entrees


def filtrer_entrees_par_date(entrees: list[dict], date_debut: datetime | None = None, 
                           date_fin: datetime | None = None) -> list[dict]:
    """Filtre les entrées par date d'horodatage.
    
    Args:
        entrees : liste d'entrées du journal
        date_debut : date de début (inclusive)
        date_fin : date de fin (inclusive)
        
    Returns:
        Liste filtrée.
    """
    result = []
    for entree in entrees:
        horodatage_str = entree.get("horodatage")
        if not horodatage_str:
            continue
        
        try:
            # Parser l'horodatage ISO (ex: 2026-10-18T14:30:00.123456)
            date_entree = datetime.fromisoformat(horodatage_str.replace("Z", "+00:00"))
            
            # Si date_debut est fourni, vérifier que l'entrée est >= date_debut
            if date_debut and date_entree < date_debut:
                continue
            
            # Si date_fin est fourni, vérifier que l'entrée est <= date_fin
            if date_fin and date_entree > date_fin:
                continue
            
            result.append(entree)
        except (ValueError, TypeError):
            continue
    
    return result


def calculer_cout(jetons_entree: int, jetons_sortie: int, prix_entree: float, 
                 prix_sortie: float) -> float:
    """Calcule le coût estimé en fonction des jetons et des prix.
    
    Args:
        jetons_entree : nombre de jetons d'entrée
        jetons_sortie : nombre de jetons de sortie
        prix_entree : prix par million de jetons d'entrée
        prix_sortie : prix par million de jetons de sortie
        
    Returns:
        Coût estimé.
    """
    cout_entree = (jetons_entree / 1_000_000) * prix_entree
    cout_sortie = (jetons_sortie / 1_000_000) * prix_sortie
    return cout_entree + cout_sortie


def analyser_entrees(entrees: list[dict], prix: dict) -> tuple[dict, dict, int]:
    """Analyse les entrées et calcule les statistiques.
    
    Args:
        entrees : liste d'entrées du journal
        prix : dictionnaire des prix
        
    Returns:
        Tuple (stats_par_modele, stats_par_devise, nombre_consommation_inconnue)
        où :
        - stats_par_modele : dict {modele: {agent, appels, jetons_entree, jetons_sortie, cout, devise}}
        - stats_par_devise : dict {devise: {appels, jetons_entree, jetons_sortie, cout}}
        - nombre_consommation_inconnue : nombre d'appels sans consommation enregistrée
    """
    stats_par_modele = defaultdict(lambda: {
        "agent": "",
        "appels": 0,
        "jetons_entree": 0,
        "jetons_sortie": 0,
        "cout": 0.0,
        "devise": "inconnu"
    })
    stats_par_devise = defaultdict(lambda: {
        "appels": 0,
        "jetons_entree": 0,
        "jetons_sortie": 0,
        "cout": 0.0
    })
    nombre_consommation_inconnue = 0
    
    for entree in entrees:
        modele = entree.get("model", "inconnu")
        usage = entree.get("usage")
        
        # Déterminer l'agent (Claude ou Mistral)
        agent = "Claude"
        if modele.startswith("mistral:"):
            agent = "Mistral"
        elif modele.startswith("claude:"):
            agent = "Claude"
        elif "mistral" in modele.lower():
            agent = "Mistral"
        elif "claude" in modele.lower():
            agent = "Claude"
        
        # Vérifier si la consommation est enregistrée
        if usage is None:
            nombre_consommation_inconnue += 1
            continue
        
        # Extraire les jetons
        jetons_entree = usage.get("input_tokens", 0) or 0
        jetons_sortie = usage.get("output_tokens", 0) or 0
        
        # Si les jetons sont à 0 et qu'il n'y a pas d'autres champs, considérer comme consommation inconnue
        if jetons_entree == 0 and jetons_sortie == 0 and not any(
            usage.get(champ, 0) for champ in ["cache_creation_input_tokens", "cache_read_input_tokens"]
        ):
            # Vérifier si c'est une entrée Mistral sans usage (avant l'issue #119)
            if agent == "Mistral" and usage == None:
                nombre_consommation_inconnue += 1
                continue
        
        # Obtenir le prix pour ce modèle
        prix_entree, prix_sortie, devise = obtenir_prix_modele(modele, prix)
        
        # Calculer le coût
        if prix_entree is not None and prix_sortie is not None and devise is not None:
            cout = calculer_cout(jetons_entree, jetons_sortie, prix_entree, prix_sortie)
        else:
            # Modèle inconnu : prix inconnu
            cout = None
            devise = "prix inconnu"
        
        # Mettre à jour les stats par modèle
        key_modele = f"{agent}:{modele}" if ":" not in modele else modele
        stats_par_modele[key_modele]["agent"] = agent
        stats_par_modele[key_modele]["appels"] += 1
        stats_par_modele[key_modele]["jetons_entree"] += jetons_entree
        stats_par_modele[key_modele]["jetons_sortie"] += jetons_sortie
        # Si cout est None (prix inconnu), ne pas ajouter au total
        if cout is not None:
            stats_par_modele[key_modele]["cout"] += cout
        stats_par_modele[key_modele]["devise"] = devise if devise and devise != "prix inconnu" else "prix inconnu"
        
        # Mettre à jour les stats par devise (si devise connue)
        if devise and devise != "prix inconnu" and cout is not None:
            stats_par_devise[devise]["appels"] += 1
            stats_par_devise[devise]["jetons_entree"] += jetons_entree
            stats_par_devise[devise]["jetons_sortie"] += jetons_sortie
            stats_par_devise[devise]["cout"] += cout
    
    return dict(stats_par_modele), dict(stats_par_devise), nombre_consommation_inconnue


def trouver_fichiers_journal(dossier: Path | str | None = None) -> list[Path]:
    """Trouve tous les fichiers coach_calls*.log et test_coach_calls*.log.
    
    Args:
        dossier : dossier où chercher (défaut : dossier courant)
        
    Returns:
        Liste de chemins de fichiers.
    """
    if dossier is None:
        dossier = Path.cwd()
    else:
        dossier = Path(dossier)
    
    # Chercher dans le dossier courant et ses sous-dossiers
    fichiers = []
    
    # D'abord chercher dans data/logs/ (emplacement standard)
    logs_dir = dossier / "data" / "logs"
    if logs_dir.exists():
        fichiers.extend(logs_dir.glob("coach_calls*.log"))
        fichiers.extend(logs_dir.glob("test_coach_calls*.log"))
    
    # Chercher aussi dans le dossier courant
    fichiers.extend(dossier.glob("coach_calls*.log"))
    fichiers.extend(dossier.glob("test_coach_calls*.log"))
    
    # Chercher dans data/ directement
    data_dir = dossier / "data"
    if data_dir.exists():
        fichiers.extend(data_dir.glob("coach_calls*.log"))
        fichiers.extend(data_dir.glob("test_coach_calls*.log"))
    
    return sorted(set(fichiers))


def formater_cout(cout: float | None) -> str:
    """Formate un coût pour l'affichage.
    
    Args:
        cout : coût à formater
        
    Returns:
        Chaîne formatée.
    """
    if cout is None:
        return "prix inconnu"
    return f"{cout:.4f}"


def afficher_statistiques(stats_par_modele: dict, stats_par_devise: dict, 
                         nombre_consommation_inconnue: int, prix: dict, 
                         date_debut: datetime | None = None, date_fin: datetime | None = None) -> None:
    """Affiche les statistiques calculées.
    
    Args:
        stats_par_modele : statistiques par modèle
        stats_par_devise : statistiques par devise
        nombre_consommation_inconnue : nombre d'appels sans consommation
        prix : dictionnaire des prix
        date_debut : date de début de la période
        date_fin : date de fin de la période
    """
    # Vérifier si des prix non vérifiés sont utilisés
    prix_non_verifies = []
    for modele, info in prix.items():
        if not info.get("verifie", False):
            # Vérifier si ce modèle apparaît dans les stats
            for key_modele in stats_par_modele:
                modele_net = key_modele.split(":", 1)[-1] if ":" in key_modele else key_modele
                if modele_net == modele:
                    prix_non_verifies.append(modele)
                    break
    
    # Afficher l'avertissement si nécessaire
    if prix_non_verifies:
        print("\n⚠️  AVERTISSEMENT : Les prix pour les modèles suivants ne sont pas vérifiés :")
        for modele in sorted(prix_non_verifies):
            print(f"  - {modele}")
        print("   Il s'agit d'une ESTIMATION, pas de la facturation officielle.")
        print("   Les remises, le cache et les arrondis peuvent différer.\n")
    
    # Afficher la période
    if date_debut and date_fin:
        periode = f"du {date_debut.strftime('%Y-%m-%d')} au {date_fin.strftime('%Y-%m-%d')}"
    elif date_debut:
        periode = f"à partir du {date_debut.strftime('%Y-%m-%d')}"
    elif date_fin:
        periode = f"jusqu'au {date_fin.strftime('%Y-%m-%d')}"
    else:
        periode = "aujourd'hui"
    
    print(f"=== Statistiques de consommation API {periode} ===\n")
    
    # Afficher par agent et par modèle
    print("Par agent et par modèle :")
    print("-" * 100)
    print(f"{'Agent':<10} {'Modèle':<30} {'Appels':>8} {'Entrée':>12} {'Sortie':>12} {'Coût':>15} {'Devise':>10}")
    print("-" * 100)
    
    for key_modele, stats in sorted(stats_par_modele.items(), key=lambda x: x[0]):
        agent = stats["agent"]
        modele = key_modele
        appels = stats["appels"]
        jetons_entree = stats["jetons_entree"]
        jetons_sortie = stats["jetons_sortie"]
        cout = stats["cout"]
        devise = stats["devise"]
        
        # Formater les nombres
        if devise == "prix inconnu":
            cout_str = "prix inconnu"
        else:
            cout_str = formater_cout(cout)
        
        print(f"{agent:<10} {modele:<30} {appels:>8} {jetons_entree:>12,} {jetons_sortie:>12,} {cout_str:>15} {devise:>10}")
    
    print("-" * 100)
    
    # Afficher les totaux par devise
    print("\nTotaux par devise :")
    print("-" * 60)
    print(f"{'Devise':<10} {'Appels':>8} {'Entrée':>12} {'Sortie':>12} {'Coût':>15}")
    print("-" * 60)
    
    for devise, stats in sorted(stats_par_devise.items()):
        appels = stats["appels"]
        jetons_entree = stats["jetons_entree"]
        jetons_sortie = stats["jetons_sortie"]
        cout = stats["cout"]
        
        print(f"{devise:<10} {appels:>8} {jetons_entree:>12,} {jetons_sortie:>12,} {cout:>15.4f}")
    
    print("-" * 60)
    
    # Afficher les appels sans consommation enregistrée
    if nombre_consommation_inconnue > 0:
        print(f"\n⚠️  Appels sans consommation enregistrée : {nombre_consommation_inconnue}")
        print("   (Ces appels ne sont pas inclus dans les totaux ci-dessus)")
    
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Estimer le coût API par jour à partir des journaux coach_calls",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples :
  python estimer_cout_api.py                          # Aujourd'hui
  python estimer_cout_api.py --date 2026-10-18        # Date spécifique
  python estimer_cout_api.py --debut 2026-10-01 --fin 2026-10-31  # Période
  python estimer_cout_api.py --prix /chemin/vers/prix.json  # Fichier de prix personnalisé
        """
    )
    parser.add_argument(
        "--date", "-d",
        type=str,
        help="Date spécifique au format AAAA-MM-JJ"
    )
    parser.add_argument(
        "--debut", "-s",
        type=str,
        help="Date de début au format AAAA-MM-JJ"
    )
    parser.add_argument(
        "--fin", "-e",
        type=str,
        help="Date de fin au format AAAA-MM-JJ"
    )
    parser.add_argument(
        "--prix", "-p",
        type=str,
        default=None,
        help="Chemin vers le fichier de prix JSON (défaut : data/token_prices.json)"
    )
    parser.add_argument(
        "--dossier", "-D",
        type=str,
        default=None,
        help="Dossier où chercher les fichiers coach_calls*.log (défaut : dossier courant)"
    )
    
    args = parser.parse_args()
    
    # Déterminer la période
    aujourdhui = datetime.now().date()
    
    if args.date:
        date_centrale = parser_date(args.date)
        if not date_centrale:
            print(f"Date invalide : {args.date}", file=sys.stderr)
            sys.exit(1)
        date_debut = datetime.combine(date_centrale, datetime.min.time())
        date_fin = datetime.combine(date_centrale, datetime.max.time())
    elif args.debut and args.fin:
        date_debut = parser_date(args.debut)
        date_fin = parser_date(args.fin)
        if not date_debut or not date_fin:
            print("Dates invalides", file=sys.stderr)
            sys.exit(1)
        date_debut = datetime.combine(date_debut.date(), datetime.min.time())
        date_fin = datetime.combine(date_fin.date(), datetime.max.time())
    elif args.debut:
        date_debut = parser_date(args.debut)
        if not date_debut:
            print(f"Date de début invalide : {args.debut}", file=sys.stderr)
            sys.exit(1)
        date_debut = datetime.combine(date_debut.date(), datetime.min.time())
        date_fin = None
    elif args.fin:
        date_fin = parser_date(args.fin)
        if not date_fin:
            print(f"Date de fin invalide : {args.fin}", file=sys.stderr)
            sys.exit(1)
        date_fin = datetime.combine(date_fin.date(), datetime.max.time())
        date_debut = None
    else:
        # Aujourd'hui
        date_debut = datetime.combine(aujourdhui, datetime.min.time())
        date_fin = datetime.combine(aujourdhui, datetime.max.time())
    
    # Charger les prix
    prix = charger_prix(args.prix)
    if not prix:
        print("Aucun fichier de prix disponible. Utilisation des prix par défaut.", file=sys.stderr)
    
    # Trouver les fichiers journal
    dossier = Path(args.dossier) if args.dossier else None
    fichiers_journal = trouver_fichiers_journal(dossier)
    
    if not fichiers_journal:
        print(f"Aucun fichier coach_calls*.log trouvé dans {dossier or 'le dossier courant'}", file=sys.stderr)
        sys.exit(1)
    
    # Lire toutes les entrées
    toutes_entrees = []
    for fichier in fichiers_journal:
        entrees = lire_entrees_journal(fichier)
        toutes_entrees.extend(entrees)
    
    if not toutes_entrees:
        print("Aucune entrée trouvée dans les fichiers journal.", file=sys.stderr)
        sys.exit(0)
    
    # Filtrer par date
    entrees_filtrees = filtrer_entrees_par_date(toutes_entrees, date_debut, date_fin)
    
    if not entrees_filtrees:
        print(f"Aucune entrée trouvée pour la période {date_debut.date() if date_debut else 'début'} à {date_fin.date() if date_fin else 'fin'}", file=sys.stderr)
        sys.exit(0)
    
    # Analyser les entrées
    stats_par_modele, stats_par_devise, nombre_consommation_inconnue = analyser_entrees(
        entrees_filtrees, prix
    )
    
    # Afficher les statistiques
    afficher_statistiques(
        stats_par_modele, stats_par_devise, nombre_consommation_inconnue,
        prix, date_debut, date_fin
    )


if __name__ == "__main__":
    main()
