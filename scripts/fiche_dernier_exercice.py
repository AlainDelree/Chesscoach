#!/usr/bin/env python3
"""Fabrique des fiches de relecture à partir du journal du coach (hors interface).

Usage (depuis ~/ChessCoach, avec le python de l'environnement virtuel) :
    venv/bin/python scripts/fiche_dernier_exercice.py            # dernier exercice
    venv/bin/python scripts/fiche_dernier_exercice.py --n 5      # les 5 derniers
    venv/bin/python scripts/fiche_dernier_exercice.py --serie verdict-officiel --n 10

Sortie : data/fiches_dernier_exercice.md (les avis A et B dans un ordre aléatoire)
et data/fiches_dernier_exercice_cle.json (qui est A, qui est B : ne pas l'ouvrir).
Ne modifie ni l'appli ni les journaux.
"""
import argparse
import glob
import json
import os
import random

import chess

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(RACINE, "data")


def lire_jsonl(motif):
    lignes = []
    for f in sorted(glob.glob(os.path.join(DATA, motif))):
        for ligne in open(f, encoding="utf-8"):
            try:
                lignes.append(json.loads(ligne))
            except Exception:
                continue
    return lignes


def ligne_numerotee(fen, coups_san, longue=False):
    """'Qxf4 Bxf4 f6' -> '15...Qxf4 16.Bxf4 f6' (ou notation longue : Qf5xf4)."""
    try:
        b = chess.Board(fen)
        sortie, premier = [], True
        for san in (coups_san or "").split():
            m = b.parse_san(san)
            if longue:
                p = b.piece_at(m.from_square)
                lettre = "" if p.piece_type == chess.PAWN else p.symbol().upper()
                if b.is_castling(m):
                    txt = san
                else:
                    txt = "%s%s%s%s" % (lettre, chess.square_name(m.from_square),
                                         "x" if b.is_capture(m) else "-", chess.square_name(m.to_square))
                    if m.promotion:
                        txt += "=" + chess.piece_symbol(m.promotion).upper()
            else:
                txt = san
            if b.turn == chess.WHITE:
                sortie.append("%d.%s" % (b.fullmove_number, txt))
            elif premier:
                sortie.append("%d...%s" % (b.fullmove_number, txt))
            else:
                sortie.append(txt)
            premier = False
            b.push(m)
        return " ".join(sortie)
    except Exception:
        return coups_san or "(indisponible)"


def nombre(v, defaut="?"):
    return defaut if v is None else str(v)


def chute_lisible(v):
    """Chute de chances de gain : arrondie, et dite 'gain' quand le coup améliore."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return "?"
    return "gain de %.2f" % (-v) if v < 0 else "chute de %.2f" % v


def fabriquer(args):
    journal = [e for e in lire_jsonl("logs/coach_calls*.log")
               if e.get("model") and e.get("reponse") and e.get("mode_origine") == "exercice"
               and isinstance(e.get("context"), dict) and e["context"].get("fen_depart_exercice")]
    if args.serie:
        journal = [e for e in journal if (e.get("version_info") or {}).get("serie") == args.serie]
    journal.sort(key=lambda e: e["horodatage"])
    # regrouper par (position, coup) : un exercice = un avis de chaque agent
    groupes, ordre = {}, []
    for e in journal:
        cle = (e["context"]["fen_depart_exercice"], e["context"].get("coup_propose"))
        if cle not in groupes:
            groupes[cle] = {}
            ordre.append(cle)
        agent = "claude" if str(e["model"]).startswith("claude") else "mistral"
        groupes[cle][agent] = e
    cles = [c for c in ordre if len(groupes[c]) >= 1][-args.n:]
    if not cles:
        raise SystemExit("Aucun exercice trouvé dans le journal.")

    try:
        phases = {x["fen_avant"]: x["phase"] for x in json.load(open(os.path.join(DATA, "erreurs_detectees.json"), encoding="utf-8"))}
    except Exception:
        phases = {}
    signalements = {}
    for s in lire_jsonl("logs/signalements.log"):
        if s.get("log_id") and (s.get("commentaire") or "").strip():
            signalements.setdefault(s["log_id"], []).append(s["commentaire"].strip())

    rnd = random.Random()
    md, cle_ab = ["# Fiches de relecture : 1 = juste, 0 = au moins une erreur sur la position, la suite des coups, ou autre", "",
                  "Règle de notation : une seule ligne « Note: » par avis, avec 0 ou 1 (0,5 toléré). Le reste va dans « Commentaires: ».", ""], {}
    for k, (fen, coup) in enumerate(cles, 1):
        avis = groupes[(fen, coup)]
        c = next(iter(avis.values()))["context"]
        camp = "blancs" if fen.split()[1] == "w" else "noirs"
        meilleur = c.get("meilleur_coup")
        identique = (coup == meilleur)
        md += ["++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++", "",
               "## Fiche %d" % k, "", "### Métadonnées (remplies automatiquement)",
               "https://lichess.org/analysis/" + fen.replace(" ", "_"),
               "Camp d'Alain : %s | Phase : %s" % (camp, phases.get(fen, "?")),
               "Coup joué : %s | Meilleur coup (Stockfish) : %s%s | Coup de l'époque : %s" % (
                   coup, meilleur, " (identique)" if identique else "", c.get("coup_reel"))]
        avant, apres = c.get("eval_before_cp"), c.get("eval_after_cp")
        md += ["Évaluation avant le coup : %s cp | après le coup joué : %s cp | après le meilleur coup : %s" % (
            nombre(avant), nombre(apres), "identique" if identique else "(pas encore disponible)"),
               "Verdict officiel (Lichess) : %s | ancien verdict : %s | perte : %s cp | %s" % (
                   c.get("verdict_qualite_officiel"), c.get("verdict_qualite_ancien"), nombre(c.get("verdict_delta_cp")),
                   chute_lisible(c.get("win_prob_drop")))]
        if identique:
            md += ["Ligne calculée (coup joué = meilleur coup) : " + ligne_numerotee(fen, c.get("pv_coup_propose")),
                   "   notation longue : " + ligne_numerotee(fen, c.get("pv_coup_propose"), longue=True)]
        else:
            md += ["Ligne calculée après le coup joué : " + ligne_numerotee(fen, c.get("pv_coup_propose")),
                   "   notation longue : " + ligne_numerotee(fen, c.get("pv_coup_propose"), longue=True),
                   "Ligne calculée après le meilleur coup : " + ligne_numerotee(fen, c.get("pv_meilleur_coup")),
                   "   notation longue : " + ligne_numerotee(fen, c.get("pv_meilleur_coup"), longue=True)]
        cles_faits = ("pv_coup_propose_faits",) if identique else ("pv_coup_propose_faits", "pv_meilleur_coup_faits")
        faits = [str(c[k]) for k in cles_faits if c.get(k)]
        md += (["Données python-chess par coup :"] + faits + [""]) if faits else ["Données python-chess par coup : (non disponibles pour cet exercice)", ""]
        agents = list(avis)
        rnd.shuffle(agents)
        cle_ab[str(k)] = {}
        for lettre, ag in zip("AB", agents):
            e = avis[ag]
            cle_ab[str(k)][lettre] = ag
            prerempli = " | ".join(signalements.get(e.get("id"), []))
            md += ["### Avis " + lettre, "#### Texte de l'avis (format actuel, pas encore structuré)", e["reponse"], "",
                   "#### À remplir (Alain)", "Note:", "Utile pour mon niveau (1/0):",
                   "Phrases fautives (recopie-les telles quelles, je classerai les types d'erreurs après):",
                   "Commentaires: " + (("[signalement] " + prerempli) if prerempli else ""), "",
                   "------------------------------------------------------------", ""]
        md += ["### Préférence sur cette fiche", "Meilleur avis (A / B / égal):", "Pourquoi (facultatif):", ""]
    chemin = os.path.join(DATA, "fiches_dernier_exercice.md")
    open(chemin, "w", encoding="utf-8").write("\n".join(md))
    json.dump(cle_ab, open(os.path.join(DATA, "fiches_dernier_exercice_cle.json"), "w", encoding="utf-8"), indent=1)
    print("%d fiche(s) écrite(s) : %s" % (len(cles), chemin))
    print("(clé A/B : data/fiches_dernier_exercice_cle.json, ne pas l'ouvrir avant d'avoir noté)")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--n", type=int, default=1, help="nombre d'exercices (les plus récents)")
    p.add_argument("--serie", default="", help="ne garder que les avis de cette série (CHESSCOACH_SERIE)")
    fabriquer(p.parse_args())
