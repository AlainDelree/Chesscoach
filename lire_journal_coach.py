#!/usr/bin/env python3
"""
lire_journal_coach.py — ChessCoach (issue #85, part. 3)

Script de lecture du journal des appels au coach (coach_calls.log et ses
archives mensuelles coach_calls-AAAA-MM.log créées par la rotation, cf.
llm_coach._log_coach_call/_coach_log_fichier_actif) : jusqu'ici, relire une
entrée obligeait à composer à chaque fois une commande Python ad hoc.
Lecture JSON Lines brute, sans dépendre de llm_coach.py.

Usage (chemin par défaut : config.COACH_CALLS_LOG_PATH, son dossier parent
pour les archives) — une seule ligne :
    python3 lire_journal_coach.py [--n 10] [--mode MODE_ORIGINE] [--mot MOT] [--date AAAA-MM-JJ] [--coup N] [--log-dir DOSSIER]

Exemples :
    python3 lire_journal_coach.py
    python3 lire_journal_coach.py --n 5 --mode analyse_partie
    python3 lire_journal_coach.py --mot "Bb4"
    python3 lire_journal_coach.py --date 2026-10-02
    python3 lire_journal_coach.py --coup 6

Pour chaque entrée affichée, mêmes titres de section que lire_signalements.py
(issue #109) : « Ce que tu as noté » (dernière question posée, le dernier
message "user" envoyé), « Réponse du coach » (la PREMIÈRE réponse et les
alertes qui ont déclenché une relance automatique le cas échéant — issue
#94, point 5, absent si aucune relance n'a eu lieu — puis la réponse finale
ou l'erreur), « Fiabilité » (couleur/raison/contrôles déclenchés) et
« Position » (FEN, coup avec numéro si disponible, contexte restant
reformaté lisiblement, une clé par ligne, sans les champs très volumineux
"pgn"/"faits_calcules" — liste complète des coups de la partie / bloc de
faits calculés).

--log-dir permet de pointer vers un dossier de test au lieu du journal réel
(utilisé par les tests de cette issue — jamais nécessaire en usage normal).
"""

import argparse
import json
import sys
from pathlib import Path

import config

# Champs de "context" volontairement omis de l'affichage (issue #85, part.
# 3) : volumineux et peu utiles à une relecture rapide — le PGN complet de
# la partie, et le bloc de faits calculés (idées détectées, listes de
# pièces...) déjà résumés par "coup"/verdict affichés séparément ci-dessous.
_CHAMPS_CONTEXTE_VOLUMINEUX = ("pgn", "faits_calcules")


def _fichiers_journal(log_dir: Path, nom_fichier_base: str) -> list:
    """Fichier d'origine + archives mensuelles dans log_dir, triés du plus
    ancien au plus récent (tri par nom : le fichier d'origine, sans suffixe
    de date, trie avant toute archive "-AAAA-MM", elles-mêmes triées par
    année-mois croissant)."""
    base = Path(nom_fichier_base)
    return sorted(log_dir.glob(f"{base.stem}*{base.suffix}"), key=lambda p: p.name)


def _charger_entrees(fichiers: list) -> list:
    entrees = []
    for fichier in fichiers:
        try:
            with open(fichier, "r", encoding="utf-8") as f:
                for ligne in f:
                    ligne = ligne.strip()
                    if not ligne:
                        continue
                    try:
                        entrees.append(json.loads(ligne))
                    except (ValueError, TypeError):
                        continue
        except OSError as e:
            print(f"(ignoré, illisible : {fichier} — {e})", file=sys.stderr)
    return entrees


def _derniere_question(messages) -> str:
    for m in reversed(messages or []):
        if isinstance(m, dict) and m.get("role") == "user":
            return (m.get("content") or "").strip()
    return ""


def _contexte_allege(context: dict) -> dict:
    return {k: v for k, v in (context or {}).items() if k not in _CHAMPS_CONTEXTE_VOLUMINEUX}


def _lignes_cle_valeur(cle: str, valeur, indent: str = "") -> list:
    """Une entrée clé/valeur sur une ou plusieurs lignes, indentée (issue
    #109) : les valeurs scalaires courtes restent sur la ligne de la clé,
    les valeurs multi-lignes (ex. pieces_depart_texte) ou les dict/list
    passent à la ligne, indentées d'un niveau — pour un contexte lisible à
    l'œil plutôt que la ligne JSON brute d'avant cette issue."""
    prefixe = f"{indent}{cle} :"
    if isinstance(valeur, dict):
        if not valeur:
            return [f"{prefixe} (vide)"]
        lignes = [prefixe]
        for sous_cle, sous_valeur in valeur.items():
            lignes.extend(_lignes_cle_valeur(sous_cle, sous_valeur, indent + "  "))
        return lignes
    if isinstance(valeur, list):
        if not valeur:
            return [f"{prefixe} (vide)"]
        lignes = [prefixe]
        for item in valeur:
            if isinstance(item, (dict, list)):
                lignes.extend(_lignes_cle_valeur("-", item, indent + "  "))
            else:
                lignes.append(f"{indent}  - {item}")
        return lignes
    texte = "" if valeur is None else str(valeur)
    if "\n" in texte:
        lignes = [prefixe]
        for sous_ligne in texte.split("\n"):
            lignes.append(f"{indent}  {sous_ligne}")
        return lignes
    return [f"{prefixe} {texte}"]


def _lignes_contexte(contexte: dict) -> list:
    """Contexte reformaté lisiblement, une clé par ligne (issue #109, point
    2) — à appliquer à un contexte déjà allégé (_contexte_allege), jamais au
    contexte brut (pgn/faits_calcules restent exclus)."""
    lignes = []
    for cle, valeur in (contexte or {}).items():
        lignes.extend(_lignes_cle_valeur(cle, valeur))
    return lignes


def _lignes_fiabilite(entree: dict | None) -> list:
    """Lignes d'affichage de la fiabilité d'une entrée du journal du coach
    (couleur, raison, avertissement d'une première réponse corrigée par
    relance si elle existe, contrôles déclenchés) — réutilisée par ce
    script et par lire_signalements.py (section "Fiabilité", issue #109,
    point 1c) pour éviter deux implémentations divergentes. Une seule ligne
    si l'entrée est introuvable, plutôt qu'un bloc vide ou une exception."""
    if entree is None:
        return ["(entrée du journal introuvable : log_id absent, ou archive déjà purgée)"]
    fiabilite = entree.get("fiabilite") or {}
    lignes = [
        f"Couleur : {fiabilite.get('couleur') or '?'}",
        f"Raison : {fiabilite.get('raison') or '(aucune raison enregistrée)'}",
    ]
    avertissement = entree.get("avertissement")
    if avertissement:
        lignes.append(f"Avertissement (première réponse corrigée par relance) : {avertissement}")
    alertes = fiabilite.get("alertes") or []
    if alertes:
        lignes.append(f"Contrôles déclenchés ({len(alertes)}) :")
        for a in alertes:
            lignes.append(f"  - [{a.get('type', '?')}] {a.get('detail', '?')}")
            positions = a.get("positions_essayees")
            if positions:
                lignes.append(f"    positions essayées : {', '.join(positions)}")
    else:
        lignes.append("Contrôles déclenchés : aucun.")
    return lignes


def _position(context: dict) -> str:
    context = context or {}
    return context.get("fen") or context.get("fen_avant") or context.get("fen_depart_exercice") or ""


def _coup(context: dict) -> str:
    context = context or {}
    for champ in ("move", "coup_propose", "coup_reel"):
        if context.get(champ):
            return context[champ]
    return ""


def _correspond_filtres(entree: dict, args) -> bool:
    if args.mode and (entree.get("mode_origine") or "") != args.mode:
        return False
    if args.mot and args.mot.lower() not in json.dumps(entree, ensure_ascii=False).lower():
        return False
    if args.date and not (entree.get("horodatage") or "").startswith(args.date):
        return False
    if args.coup is not None and (entree.get("context") or {}).get("coup_plein") != args.coup:
        return False
    return True


def _afficher(entree: dict) -> None:
    """Affiche une entrée du journal avec les mêmes titres de section que
    lire_signalements.py (issue #109, point 4) : "Ce que tu as noté"
    (dernière question d'Alain), "Réponse du coach" (réponse finale ou
    erreur, et la première réponse avant relance le cas échéant),
    "Fiabilité" (couleur/raison/contrôles, via _lignes_fiabilite partagée
    avec lire_signalements.py) et "Position" (FEN, coup, contexte restant
    reformaté lisiblement par _lignes_contexte). Les options de ce script
    (--n/--mode/--mot/--date/--coup/--log-dir) sont inchangées."""
    contexte = entree.get("context") or {}
    print("=" * 78)
    print(f"{entree.get('horodatage', '?')}  mode={entree.get('mode_origine', '?')}  modele={entree.get('model', '?')}")

    print()
    print("Ce que tu as noté")
    print("-" * len("Ce que tu as noté"))
    question = _derniere_question(entree.get("messages"))
    print(f"Dernière question : {question or '(aucune question)'}")

    print()
    print("Réponse du coach")
    print("-" * len("Réponse du coach"))
    premiere_reponse = entree.get("premiere_reponse") or {}
    if premiere_reponse.get("texte") is not None:
        alertes = premiere_reponse.get("alertes") or []
        details = "; ".join(a.get("detail", "?") for a in alertes) or "?"
        print(f"Première réponse (avant relance automatique, alerte(s) : {details}) :")
        print(f"  {premiere_reponse['texte']}")
    if entree.get("erreur"):
        print(f"Erreur : {entree['erreur']}")
    elif entree.get("reponse") is not None:
        print(entree["reponse"])
    else:
        print("(aucune réponse enregistrée)")

    print()
    print("Fiabilité")
    print("-" * len("Fiabilité"))
    for ligne in _lignes_fiabilite(entree):
        print(ligne)

    print()
    print("Position")
    print("-" * len("Position"))
    position = _position(contexte)
    print(f"FEN : {position or '(inconnue)'}")
    coup = _coup(contexte)
    numero = contexte.get("coup_plein")
    if coup:
        suffixe = f" (coup {numero})" if numero is not None else ""
        print(f"Coup : {coup}{suffixe}")
    contexte_allege = _contexte_allege(contexte)
    if contexte_allege:
        print("Contexte :")
        for ligne in _lignes_contexte(contexte_allege):
            print(f"  {ligne}")


def main():
    parser = argparse.ArgumentParser(
        description="Relit le journal des appels au coach (coach_calls.log + archives mensuelles)."
    )
    parser.add_argument("--n", type=int, default=10, help="Nombre d'entrées à afficher (les plus récentes), défaut 10.")
    parser.add_argument("--mode", default=None, help="Filtre par mode_origine exact (ex. analyse_partie, exercice, pedagogique).")
    parser.add_argument("--mot", default=None, help="Filtre : mot présent dans l'entrée (insensible à la casse).")
    parser.add_argument("--date", default=None, help="Filtre par date, préfixe de l'horodatage ISO (ex. 2026-10-02).")
    parser.add_argument("--coup", type=int, default=None, help="Filtre par numéro de coup (context.coup_plein).")
    parser.add_argument("--log-dir", default=None, help="Dossier du journal (défaut : dossier de config.COACH_CALLS_LOG_PATH).")
    args = parser.parse_args()

    log_path = Path(config.COACH_CALLS_LOG_PATH)
    log_dir = Path(args.log_dir) if args.log_dir else log_path.parent
    if not log_dir.exists():
        print(f"Dossier introuvable : {log_dir}")
        return 1

    fichiers = _fichiers_journal(log_dir, log_path.name)
    if not fichiers:
        print(f"Aucun fichier de journal dans {log_dir}")
        return 0

    entrees = [e for e in _charger_entrees(fichiers) if _correspond_filtres(e, args)]
    if not entrees:
        print("Aucune entrée ne correspond.")
        return 0

    a_afficher = entrees[-args.n:] if args.n > 0 else entrees
    for entree in a_afficher:
        _afficher(entree)
    print("=" * 78)
    print(f"{len(entrees)} entrée(s) correspondante(s) (sur {len(fichiers)} fichier(s) lus), {len(a_afficher)} affichée(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
