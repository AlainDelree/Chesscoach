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

Pour chaque entrée affichée : horodatage, mode d'origine et modèle, position
(FEN), coup (notation + numéro de coup si disponible), contexte restant
(sans les champs très volumineux "pgn"/"faits_calcules" — liste complète des
coups de la partie / bloc de faits calculés), dernière question posée (le
dernier message "user" envoyé), la PREMIÈRE réponse du coach et les alertes
qui ont déclenché une relance automatique le cas échéant (issue #94, point
5 — absent si aucune relance n'a eu lieu pour cette entrée), et réponse
finale (ou erreur) du coach.

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
    contexte = entree.get("context") or {}
    print("=" * 78)
    print(f"{entree.get('horodatage', '?')}  mode={entree.get('mode_origine', '?')}  modele={entree.get('model', '?')}")
    position = _position(contexte)
    if position:
        print(f"Position (FEN) : {position}")
    coup = _coup(contexte)
    numero = contexte.get("coup_plein")
    if coup:
        suffixe = f" (coup {numero})" if numero is not None else ""
        print(f"Coup : {coup}{suffixe}")
    contexte_allege = _contexte_allege(contexte)
    if contexte_allege:
        print(f"Contexte : {json.dumps(contexte_allege, ensure_ascii=False)}")
    question = _derniere_question(entree.get("messages"))
    if question:
        print(f"Dernière question : {question}")
    premiere_reponse = entree.get("premiere_reponse") or {}
    if premiere_reponse.get("texte") is not None:
        alertes = premiere_reponse.get("alertes") or []
        details = "; ".join(a.get("detail", "?") for a in alertes) or "?"
        print(f"Première réponse (avant relance automatique, alerte(s) : {details}) :")
        print(f"  {premiere_reponse['texte']}")
    if entree.get("erreur"):
        print(f"Erreur : {entree['erreur']}")
    elif entree.get("reponse") is not None:
        print(f"Réponse : {entree['reponse']}")


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
