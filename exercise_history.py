"""
exercise_history.py — ChessCoach (issue #76)

Historique local des exercices proposés (mode "Exercice", donnée
personnelle hors git, cf. config.EXERCICE_HISTORIQUE_PATH) et règles de
tirage favorisant la variété, en remplacement du tirage uniforme avec
remise d'origine (issue #7) qui pouvait reproposer plusieurs fois la même
position dans une même journée.

Indexé par FEN de départ de l'exercice (erreurs_detectees.json) plutôt que
par un identifiant arbitraire : deux entrées qui partagent exactement la
même position de départ partagent la même mémoire de révision, ce qui est
le comportement voulu (même position à l'écran, même historique pour
Alain).

Format du fichier (un objet par FEN) :
    {"<fen_avant>": {"nb_fois": 2, "derniere_date": "2026-09-20T14:32:00",
                      "dernier_resultat": "reussi" | "rate" | None}, ...}
"""

import json
import logging
import random
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("chesscoach.exercise_history")

# ── Délais de révision espacée — réglables ici UNIQUEMENT (issue #76) ──────
# Une position RÉUSSIE n'est pas reproposée avant ce délai écoulé depuis sa
# dernière proposition, sauf si la catégorie (phase) est épuisée (cf.
# choisir_exercice ci-dessous).
DELAI_REVISION_REUSSI_JOURS = 14
# Une position RATÉE est reproposée volontiers (révision espacée) dès ce
# délai, plus court, écoulé.
DELAI_REVISION_RATE_JOURS = 3


def charger_historique(path) -> dict:
    """Charge l'historique des exercices proposés. Retourne {} si le fichier
    est absent ou illisible (même tolérance que llm_coach.load_coach_memory)
    — le tirage se comporte alors comme si aucune position n'avait jamais
    été proposée."""
    path = Path(path)
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.warning(f"Historique d'exercices illisible ({path}) : {e}")
        return {}


def _sauvegarder_historique(path, historique: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(historique, f, ensure_ascii=False, indent=2)
    tmp_path.replace(path)


def enregistrer_proposition(path, fen: str, maintenant: datetime | None = None) -> None:
    """Enregistre qu'une position vient d'être tirée : incrémente le nombre
    de fois proposé et met à jour la date de dernière proposition, SANS
    toucher au résultat de la dernière tentative — une position proposée
    puis jamais répondue (abandon, "Exercice suivant" immédiat) garde le
    résultat de sa tentative précédente, s'il y en a une."""
    maintenant = maintenant or datetime.now()
    historique = charger_historique(path)
    entree = historique.setdefault(
        fen, {"nb_fois": 0, "derniere_date": None, "dernier_resultat": None}
    )
    entree["nb_fois"] = entree.get("nb_fois", 0) + 1
    entree["derniere_date"] = maintenant.isoformat()
    historique[fen] = entree
    _sauvegarder_historique(path, historique)


def enregistrer_resultat(path, fen: str, reussi: bool) -> None:
    """Enregistre le résultat de la dernière tentative sur une position déjà
    proposée (issue #76) : réussi si le premier coup proposé reçoit le
    verdict Stockfish "bon" — ce qui couvre aussi "le meilleur coup", un coup
    identique au meilleur coup de la position ayant toujours un delta_cp de 0
    et donc une qualité "bon" (cf. engine_stockfish.classifier_coup, seuil
    SEUIL_BON) — raté sinon (imprécision/erreur/blunder).

    N'incrémente pas nb_fois et ne touche pas derniere_date : c'est déjà le
    rôle d'enregistrer_proposition au moment du tirage. Une reprise
    ("Reprendre mon coup") qui aboutit à un nouveau verdict réécrit
    simplement le résultat le plus récent."""
    historique = charger_historique(path)
    entree = historique.setdefault(
        fen, {"nb_fois": 1, "derniere_date": datetime.now().isoformat(), "dernier_resultat": None}
    )
    entree["dernier_resultat"] = "reussi" if reussi else "rate"
    historique[fen] = entree
    _sauvegarder_historique(path, historique)


def _jours_ecoules(derniere_date_iso, maintenant: datetime) -> float | None:
    if not derniere_date_iso:
        return None
    try:
        derniere = datetime.fromisoformat(derniere_date_iso)
    except (TypeError, ValueError):
        return None
    return (maintenant - derniere).total_seconds() / 86400.0


def choisir_exercice(pool: list, historique: dict, dernier_sous_type: str | None = None,
                      maintenant: datetime | None = None) -> dict | None:
    """Tire une entrée du pool (déjà filtré par phase par l'appelant, cf.
    app.py on_exercise_new) selon les règles de variété de l'issue #76,
    par ordre de priorité :

    1. Positions jamais proposées (absentes de l'historique).
    2. À défaut, positions "dues" pour révision : ratées depuis au moins
       DELAI_REVISION_RATE_JOURS, ou réussies depuis au moins
       DELAI_REVISION_REUSSI_JOURS.
    3. Catégorie épuisée (ni 1 ni 2) : reprise des positions les plus
       anciennes de la phase (le quart le plus ancien, pour garder un peu de
       variété plutôt que de retomber toujours sur la même), en ignorant
       leur délai de révision.

    Dans le niveau retenu, tirage UNIFORME (comme le tirage d'origine, pas
    de pondération) en évitant si possible de reproposer la même "nature"
    (sous_type : matériel/positionnel) que le tirage précédent — ignoré si
    ça viderait les candidats restants.

    Retourne None si pool est vide."""
    if not pool:
        return None
    maintenant = maintenant or datetime.now()

    jamais_vues = []
    dues = []
    toutes_avec_date = []

    for entree in pool:
        info = historique.get(entree["fen_avant"])
        if info is None:
            jamais_vues.append(entree)
            continue
        jours = _jours_ecoules(info.get("derniere_date"), maintenant)
        # Issue #79, point 6 : seul un résultat "reussi" explicite donne le
        # délai long — un résultat "rate" ET l'absence de résultat
        # (dernier_resultat=None, verdict jamais calculé ou exercice proposé
        # puis jamais répondu/abandonné) reçoivent tous deux le délai court,
        # pour être reproposés plus tôt plutôt que d'être traités comme
        # "maîtrisés" par erreur (avant ce correctif, None tombait dans le
        # même cas que "reussi" via le simple "else" ci-dessous).
        delai = (
            DELAI_REVISION_REUSSI_JOURS if info.get("dernier_resultat") == "reussi"
            else DELAI_REVISION_RATE_JOURS
        )
        if jours is None or jours >= delai:
            dues.append(entree)
        toutes_avec_date.append((entree, info.get("derniere_date") or ""))

    if jamais_vues:
        candidats = jamais_vues
    elif dues:
        candidats = dues
    else:
        # Catégorie épuisée : reprise des plus anciennes, délais ignorés.
        toutes_avec_date.sort(key=lambda t: t[1])
        n = max(1, len(toutes_avec_date) // 4)
        candidats = [e for e, _ in toutes_avec_date[:n]]

    if dernier_sous_type and len(candidats) > 1:
        sans_repetition = [e for e in candidats if e.get("sous_type") != dernier_sous_type]
        if sans_repetition:
            candidats = sans_repetition

    return random.choice(candidats)
