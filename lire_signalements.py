#!/usr/bin/env python3
"""
lire_signalements.py — ChessCoach (issue #89, affichage revu par l'issue #109)

Signalements d'une réponse du coach (bouton "Signaler" sous chaque réponse,
tous modes) : data/logs/signalements.log (JSON Lines, hors git, écrit par
app.py on_signalement_envoyer).

Trois commandes (issue #109, la sortie complète d'origine mélangeait les
notes d'Alain — commentaire, question — avec une ligne JSON de contexte de
plusieurs milliers de caractères, ce qui les faisait défiler hors de
l'écran) :

    python3 lire_signalements.py                  # résumé lisible du dernier signalement (1 écran)
    python3 lire_signalements.py --complet         # texte complet prêt à coller dans un chat (contexte inclus)
    python3 lire_signalements.py --id ID [--complet]   # un signalement précis (identifiant affiché par --n)

Sans --id, c'est toujours le dernier signalement qui est affiché. Le résumé
tient sur un écran de terminal (~40 lignes) : ce qu'Alain a noté
(commentaire + question) en tête, la réponse du coach, la fiabilité, la
position et les lignes Stockfish — jamais la ligne JSON brute de contexte.
--complet reprend les mêmes titres puis ajoute le contexte complet envoyé
au coach (une clé par ligne, allégé des champs volumineux, même filtre que
lire_journal_coach.py) et la ligne principale de Stockfish recalculée en
direct sur la position signalée (pas relue d'une éventuelle valeur déjà
présente dans le journal, qui peut être absente selon le mode — ex. chat
libre, qui n'en calcule aucune).

--n conserve l'affichage liste existant (résumés tronqués), avec un rappel
de la commande pour voir un signalement en entier. --dernier (issue #89) et
--traiter sont inchangés.

Usage (une seule ligne) :
    python3 lire_signalements.py [--n 10] [--dernier] [--complet] [--id ID] [--traiter ID]

Exemples :
    python3 lire_signalements.py
    python3 lire_signalements.py --complet
    python3 lire_signalements.py --id 3f9a2b1c7e4d
    python3 lire_signalements.py --id 3f9a2b1c7e4d --complet
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
    agent = entree.get("agent") or ""
    model = entree.get("model") or ""
    agent_info = f"  agent={agent}" if agent else ""
    model_info = f"  model={model}" if model else ""
    print("=" * 78)
    print(f"id={entree.get('id', '?')}  {entree.get('horodatage', '?')}  mode={entree.get('mode_origine') or '?'}{traite}")
    if agent_info or model_info:
        print(f"{agent_info}{model_info}")
    if entree.get("fen"):
        print(f"Position (FEN) : {entree['fen']}")
    journal = _trouver_entree_journal(entree.get("log_id"), index_journal)
    print(_ligne_coup_ou_question(entree, journal))
    if entree.get("commentaire"):
        print(f"Commentaire d'Alain : {entree['commentaire']}")
    print(f"Réponse signalée : {_tronquer(entree.get('reponse'))}")
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


def _ligne_coup_ou_question(entree: dict, journal: dict | None) -> str:
    """Ligne "Coup concerné"/"Question posée" (issue #95, point 8) : une
    réponse du coach répond soit à un coup joué (mode partie/exercice...),
    soit à une question libre d'Alain (chat) — jamais les deux à la fois.
    Pour un coup, ligne inchangée ("Coup concerné : ..."). Pour une question
    (entree["move"] vide), affiche la dernière question d'Alain retrouvée
    dans l'entrée du journal reliée par log_id (lire_journal_coach.
    _derniere_question, déjà utilisée par lire_journal_coach.py) plutôt que
    l'ancien "Coup concerné : (aucun)", qui ne disait rien d'utile sur ce qui
    avait motivé la réponse signalée ; "(aucune question)" si même la
    question est introuvable (réponse non journalisée, archive déjà purgée,
    ou réponse qui ne suit réellement aucune question)."""
    if entree.get("move"):
        return f"Coup concerné : {entree['move']}"
    question = lire_journal_coach._derniere_question(journal.get("messages")) if journal else ""
    return f"Question posée par Alain : {question}" if question else "Question posée par Alain : (aucune question)"


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


def _formater_pv(board: "chess.Board", pv: list) -> str:
    """Suite de coups `pv` formatée en notation standard (numéro de coup et
    points de suspension si la suite commence au trait des Noirs), issue
    #109 point 1d — l'ancien format concatenait les SAN sans numéro ni
    camp, peu lisible sans rejouer la position de tête."""
    morceaux = []
    b = board.copy()
    for i, coup in enumerate(pv):
        if b.turn == chess.WHITE:
            morceaux.append(f"{b.fullmove_number}.")
        elif i == 0:
            morceaux.append(f"{b.fullmove_number}...")
        morceaux.append(b.san(coup))
        b.push(coup)
    return " ".join(morceaux)


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
    trait = "Blancs" if board.turn == chess.WHITE else "Noirs"
    pv_texte = _formater_pv(board, (resultat.get("pv") or [])[:10])
    entete = f"{score} (trait aux {trait})"
    return f"{entete} — {pv_texte}" if pv_texte else entete


def _lignes_position(entree: dict, journal: dict | None, ligne_sf: str | None) -> list:
    """Section "Position" du résumé/texte complet (issue #109, point 1d) :
    mode, FEN affichée, FEN de départ de l'exercice si elle diffère, camp
    d'Alain, coup proposé/réel/meilleur coup, verdict et ligne Stockfish —
    tous relus dans le contexte de l'entrée du journal reliée par log_id
    (absents si cette entrée est introuvable, ou si le mode ne les
    transmet pas, ex. chat libre)."""
    contexte = (journal or {}).get("context") or {}
    fen = entree.get("fen") or ""
    lignes = [
        f"Mode : {entree.get('mode_origine') or '(inconnu)'}",
        f"FEN affichée : {fen or '(inconnue)'}",
    ]
    fen_depart = (contexte.get("fen_depart_exercice") or "").strip()
    if fen_depart and fen_depart != fen:
        lignes.append(f"FEN de départ de l'exercice : {fen_depart}")
    if contexte.get("camp_alain_inconnu"):
        lignes.append("Camp d'Alain : indéterminé")
    else:
        camp_alain = (contexte.get("camp_alain") or "").strip()
        if camp_alain:
            lignes.append(f"Camp d'Alain : {camp_alain}")
    for champ, libelle in (
        ("coup_propose", "Coup proposé"),
        ("coup_reel", "Coup réel"),
        ("meilleur_coup", "Meilleur coup"),
    ):
        valeur = (contexte.get(champ) or "").strip()
        if valeur:
            lignes.append(f"{libelle} : {valeur}")
    verdict_qualite = (contexte.get("verdict_qualite") or "").strip()
    verdict_delta = contexte.get("verdict_delta_cp")
    if verdict_qualite or verdict_delta is not None:
        detail = verdict_qualite or "?"
        if isinstance(verdict_delta, (int, float)):
            detail += f" ({verdict_delta:+.0f}cp)"
        lignes.append(f"Verdict : {detail}")
    lignes.append(f"Stockfish : {ligne_sf or '(indisponible)'}")
    return lignes


def _construire_resume(entree: dict, journal: dict | None, ligne_sf: str | None) -> str:
    """Résumé lisible tenant sur un écran de terminal (issue #109, point 1) :
    "Ce que tu as noté" (commentaire d'Alain + question/coup, en tête et
    bien visibles), "Réponse du coach" (texte complet), "Fiabilité"
    (couleur/raison/contrôles/avertissement de relance) et "Position"
    (mode/FEN/coups/verdict/Stockfish) — jamais la ligne JSON brute de
    contexte, suivi d'un rappel de la commande pour le texte complet."""
    traite = " [traité]" if entree.get("traite") else ""
    agent = entree.get("agent") or ""
    model = entree.get("model") or ""
    agent_model = f" — Agent: {agent}" if agent else ""
    if model:
        agent_model += f" (modèle: {model})"
    lignes = [f"=== Signalement {entree.get('id', '?')} — {entree.get('horodatage', '?')}{traite}{agent_model} ==="]

    lignes.append("")
    lignes.append("Ce que tu as noté")
    lignes.append("-" * len("Ce que tu as noté"))
    lignes.append(f"Commentaire : {entree.get('commentaire') or '(aucun)'}")
    lignes.append(_ligne_coup_ou_question(entree, journal))

    lignes.append("")
    lignes.append("Réponse du coach")
    lignes.append("-" * len("Réponse du coach"))
    lignes.append(entree.get("reponse") or "(réponse vide)")

    lignes.append("")
    lignes.append("Fiabilité")
    lignes.append("-" * len("Fiabilité"))
    lignes.extend(lire_journal_coach._lignes_fiabilite(journal))

    lignes.append("")
    lignes.append("Position")
    lignes.append("-" * len("Position"))
    lignes.extend(_lignes_position(entree, journal, ligne_sf))

    lignes.append("")
    lignes.append(f"Texte complet à coller dans un chat : python3 lire_signalements.py --complet --id {entree.get('id', '?')}")
    return "\n".join(lignes)


def _texte_complet(entree: dict, journal: dict | None, ligne_sf: str | None) -> str:
    """Texte complet prêt à coller dans un chat (issue #109, point 2) :
    mêmes titres que le résumé (_construire_resume), suivis du contexte
    complet envoyé au coach reformaté lisiblement — une clé par ligne, les
    champs volumineux déjà exclus aujourd'hui (pgn/faits_calcules) restant
    exclus — puis la ligne principale de Stockfish recalculée."""
    lignes = _construire_resume(entree, journal, ligne_sf).split("\n")
    # Retire le rappel de commande du résumé (propre au résumé, pas au texte
    # complet) et la ligne vide qui le précède.
    del lignes[-2:]

    lignes.append("")
    lignes.append("Contexte envoyé au coach")
    lignes.append("-" * len("Contexte envoyé au coach"))
    if journal:
        contexte = lire_journal_coach._contexte_allege(journal.get("context") or {})
        if contexte:
            lignes.extend(lire_journal_coach._lignes_contexte(contexte))
        else:
            lignes.append("(contexte vide)")
    else:
        lignes.append("(entrée du journal introuvable — réponse non journalisée, ou archive déjà purgée)")

    lignes.append("")
    lignes.append(f"Ligne principale de Stockfish (recalculée) : {ligne_sf or '(indisponible)'}")
    return "\n".join(lignes)


def main():
    parser = argparse.ArgumentParser(
        description='Affiche les signalements du coach (bouton "Signaler", issue #89).'
    )
    parser.add_argument("--n", type=int, default=None, metavar="N", help="Affiche la liste des N signalements les plus récents (résumés tronqués), au lieu du résumé d'un seul signalement.")
    parser.add_argument("--complet", action="store_true", help="Texte complet prêt à coller dans un chat (contexte envoyé au coach inclus), au lieu du résumé.")
    parser.add_argument("--id", default=None, metavar="ID", help="Signalement précis à afficher (identifiant affiché par --n). Sans --id, c'est le dernier.")
    parser.add_argument("--dernier", action="store_true", help="Alias de --complet sur le dernier signalement (compatibilité).")
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
        args.complet = True  # alias rétro-compatible (issue #89, --dernier affichait déjà le texte complet du dernier signalement)

    if args.id:
        cible = next((e for e in entrees if e.get("id") == args.id), None)
        if cible is None:
            print(f"Signalement introuvable : {args.id}")
            return 1
    elif args.n is not None:
        a_afficher = entrees[-args.n:] if args.n > 0 else entrees
        index_journal = _charger_index_journal()
        for entree in a_afficher:
            _afficher_resume(entree, index_journal)
        print("=" * 78)
        print(f"{len(entrees)} signalement(s) au total, {len(a_afficher)} affiché(s).")
        print("Pour voir un signalement en entier : python3 lire_signalements.py --id ID [--complet]")
        return 0
    else:
        cible = entrees[-1]

    journal = _trouver_entree_journal(cible.get("log_id"))
    ligne_sf = _ligne_stockfish(cible.get("fen") or "")
    if args.complet:
        print(_texte_complet(cible, journal, ligne_sf))
    else:
        print(_construire_resume(cible, journal, ligne_sf))
    return 0


if __name__ == "__main__":
    sys.exit(main())
