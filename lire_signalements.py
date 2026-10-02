#!/usr/bin/env python3
"""
lire_signalements.py — ChessCoach (issue #89)

Signalements d'une réponse du coach (bouton "Signaler" sous chaque réponse,
tous modes) : data/logs/signalements.log (JSON Lines, hors git, écrit par
app.py on_signalement_envoyer). Jusqu'ici, retrouver puis retransmettre une
réponse signalée à Claude Chat pour vérification Stockfish obligeait à
composer des commandes Python ad hoc sur coach_calls.log — ce script affiche
directement les signalements, et --dernier produit un texte complet prêt à
coller dans un chat : commentaire d'Alain, mode, FEN, coup, réponse du
coach, contexte envoyé au coach (allégé des champs volumineux, même filtre
que lire_journal_coach.py) et la ligne principale de Stockfish, recalculée
en direct sur la position signalée (pas relue d'une éventuelle valeur déjà
présente dans le journal, qui peut être absente selon le mode — ex. chat
libre, qui n'en calcule aucune).

Usage (une seule ligne) :
    python3 lire_signalements.py [--n 10] [--dernier] [--traiter ID]

Exemples :
    python3 lire_signalements.py
    python3 lire_signalements.py --n 5
    python3 lire_signalements.py --dernier
    python3 lire_signalements.py --traiter 3f9a2b1c7e4d
"""

import argparse
import json
import sys
from pathlib import Path

import chess

import config
import lire_journal_coach


def _charger(path: Path) -> list:
    if not path.exists():
        return []
    entrees = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for ligne in f:
                ligne = ligne.strip()
                if not ligne:
                    continue
                try:
                    entrees.append(json.loads(ligne))
                except (ValueError, TypeError):
                    continue
    except OSError as e:
        print(f"(illisible : {path} — {e})", file=sys.stderr)
    return entrees


def _sauvegarder(path: Path, entrees: list) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        for entree in entrees:
            f.write(json.dumps(entree, ensure_ascii=False) + "\n")
    tmp_path.replace(path)


def _tronquer(texte: str, n: int = 160) -> str:
    texte = texte or ""
    return texte if len(texte) <= n else texte[:n] + "..."


def _afficher_resume(entree: dict, index_journal: dict | None = None) -> None:
    traite = " [traité]" if entree.get("traite") else ""
    print("=" * 78)
    print(f"id={entree.get('id', '?')}  {entree.get('horodatage', '?')}  mode={entree.get('mode_origine') or '?'}{traite}")
    if entree.get("fen"):
        print(f"Position (FEN) : {entree['fen']}")
    if entree.get("move"):
        print(f"Coup : {entree['move']}")
    if entree.get("commentaire"):
        print(f"Commentaire d'Alain : {entree['commentaire']}")
    print(f"Réponse signalée : {_tronquer(entree.get('reponse'))}")
    journal = _trouver_entree_journal(entree.get("log_id"), index_journal)
    for ligne in _lignes_pastille(journal):
        print(ligne)


def _charger_index_journal() -> dict:
    """Index {id: entrée} de tout coach_calls.log (toutes archives
    comprises) — construit une seule fois par exécution du script (issue
    #90, point 4) plutôt que rescanné à chaque signalement affiché, qui
    peuvent être plusieurs sous --n."""
    log_path = Path(config.COACH_CALLS_LOG_PATH)
    log_dir = log_path.parent
    if not log_dir.exists():
        return {}
    fichiers = lire_journal_coach._fichiers_journal(log_dir, log_path.name)
    return {
        entree["id"]: entree
        for entree in lire_journal_coach._charger_entrees(fichiers)
        if entree.get("id")
    }


def _trouver_entree_journal(log_id, index_journal: dict | None = None) -> dict | None:
    """Retrouve l'entrée de coach_calls.log correspondant à log_id (cf.
    llm_coach._log_coach_call) — None si log_id est absent (signalement
    d'une réponse jamais journalisée) ou introuvable (archive déjà purgée,
    cf. llm_coach._purge_vieux_logs_coach). `index_journal` : index déjà
    chargé par _charger_index_journal, pour éviter de rescanner le disque à
    chaque appel (repli sur un chargement à la volée si omis)."""
    if not log_id:
        return None
    if index_journal is None:
        index_journal = _charger_index_journal()
    return index_journal.get(log_id)


def _lignes_pastille(journal: dict | None) -> list:
    """Lignes d'affichage de la pastille de fiabilité (couleur, raison,
    avertissement) et des contrôles déclenchés, relus dans l'entrée du
    journal du coach reliée par l'identifiant (issue #90, point 4) — une
    seule ligne si cette entrée est introuvable, plutôt qu'un bloc vide ou
    une exception."""
    if journal is None:
        return [
            "Pastille de fiabilité : entrée du journal introuvable "
            "(log_id absent du signalement, ou archive déjà purgée)."
        ]
    fiabilite = journal.get("fiabilite") or {}
    lignes = [
        f"Pastille de fiabilité : {fiabilite.get('couleur') or '?'} — "
        f"{fiabilite.get('raison') or '(aucune raison enregistrée)'}"
    ]
    avertissement = journal.get("avertissement")
    if avertissement:
        lignes.append(f"Avertissement (avant relance éventuelle) : {avertissement}")
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


def _ligne_stockfish(fen: str) -> str | None:
    """Ligne principale de Stockfish sur `fen`, recalculée en direct (pas de
    dépendance à une éventuelle PV déjà présente dans le journal, absente
    selon le mode — ex. chat libre). None si Stockfish est indisponible sur
    ce système ou si fen est vide/invalide."""
    if not fen:
        return None
    try:
        from engine_stockfish import EngineManager, find_stockfish
        stockfish_path = find_stockfish()
        if not stockfish_path:
            return None
        board = chess.Board(fen)
    except Exception as e:
        print(f"(FEN invalide, ligne Stockfish ignorée : {e})", file=sys.stderr)
        return None
    manager = None
    try:
        manager = EngineManager(stockfish_path)
        resultat = manager.evaluate(board, depth=16)
    except Exception as e:
        print(f"(ligne Stockfish indisponible : {e})", file=sys.stderr)
        return None
    finally:
        if manager:
            manager.quit()
    if resultat.get("indisponible"):
        return None
    cp, mate = resultat.get("cp"), resultat.get("mate")
    score = f"mat en {mate}" if mate is not None else (f"{cp:+d}cp" if cp is not None else "?")
    pv = resultat.get("pv") or []
    sans = []
    b = board.copy()
    for coup in pv[:10]:
        sans.append(b.san(coup))
        b.push(coup)
    return f"{score} — {' '.join(sans)}" if sans else score


def _texte_pret_a_coller(entree: dict) -> str:
    lignes = [
        "=== Signalement d'une réponse du coach (ChessCoach) ===",
        f"Commentaire d'Alain : {entree.get('commentaire') or '(aucun)'}",
        f"Mode : {entree.get('mode_origine') or '(inconnu)'}",
        f"FEN : {entree.get('fen') or '(inconnue)'}",
        f"Coup concerné : {entree.get('move') or '(aucun)'}",
        f"Réponse du coach : {entree.get('reponse') or ''}",
    ]
    journal = _trouver_entree_journal(entree.get("log_id"))
    lignes += _lignes_pastille(journal)
    if journal:
        contexte = lire_journal_coach._contexte_allege(journal.get("context") or {})
        lignes.append(f"Contexte envoyé au coach : {json.dumps(contexte, ensure_ascii=False)}")
    else:
        lignes.append("Contexte envoyé au coach : (entrée du journal introuvable — réponse non journalisée, ou archive déjà purgée)")
    ligne_sf = _ligne_stockfish(entree.get("fen") or "")
    lignes.append(f"Ligne principale de Stockfish : {ligne_sf or '(indisponible)'}")
    return "\n".join(lignes)


def main():
    parser = argparse.ArgumentParser(
        description='Affiche les signalements du coach (bouton "Signaler", issue #89).'
    )
    parser.add_argument("--n", type=int, default=10, help="Nombre de signalements à afficher (les plus récents), défaut 10.")
    parser.add_argument("--dernier", action="store_true", help="Affiche le dernier signalement sous forme de texte complet prêt à coller dans un chat.")
    parser.add_argument("--traiter", default=None, metavar="ID", help="Marque le signalement ID comme traité.")
    args = parser.parse_args()

    path = Path(config.SIGNALEMENTS_LOG_PATH)
    entrees = _charger(path)

    if args.traiter:
        trouve = False
        for entree in entrees:
            if entree.get("id") == args.traiter:
                entree["traite"] = True
                trouve = True
        if not trouve:
            print(f"Signalement introuvable : {args.traiter}")
            return 1
        _sauvegarder(path, entrees)
        print(f"Signalement {args.traiter} marqué comme traité.")
        return 0

    if not entrees:
        print("Aucun signalement.")
        return 0

    if args.dernier:
        print(_texte_pret_a_coller(entrees[-1]))
        return 0

    a_afficher = entrees[-args.n:] if args.n > 0 else entrees
    index_journal = _charger_index_journal()
    for entree in a_afficher:
        _afficher_resume(entree, index_journal)
    print("=" * 78)
    print(f"{len(entrees)} signalement(s) au total, {len(a_afficher)} affiché(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
