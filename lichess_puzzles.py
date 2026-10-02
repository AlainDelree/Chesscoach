"""
lichess_puzzles.py — ChessCoach (issue #78)

Source d'exercices « Problèmes Lichess » : sélection d'un problème dans le
pool préparé hors-ligne par preparer_puzzles_lichess.py (data/puzzles_lichess.json,
donnée personnelle hors git) et niveau adaptatif par catégorie de thème,
indépendant du niveau utilisé par la source « Mes erreurs ».

Le tirage réutilise exercise_history.choisir_exercice (déjà générique :
indexé par une simple clé opaque, pas forcément une FEN) pour la variété et
l'indicateur « déjà fait » — ici la clé est "lichess:<PuzzleId>", pas une
FEN, puisque deux problèmes Lichess différents peuvent en théorie partager
la même position.
"""

import json
import logging
import random
from pathlib import Path

logger = logging.getLogger("chesscoach.lichess_puzzles")

# ── Catégories de niveau (issue #78) ────────────────────────────────────────
# Les 16 thèmes Lichess retenus comme catégories de niveau adaptatif, avec
# leur libellé français. "mate" couvre aussi mateIn1/mateIn2/... (cf.
# _THEMES_PAR_CATEGORIE ci-dessous) — un seul niveau pour tous les mats, pas
# un niveau par longueur de mat.
CATEGORIES = {
    "pin":              "clouage",
    "discoveredAttack": "attaque à la découverte",
    "defensiveMove":    "coup défensif",
    "quietMove":        "coup silencieux",
    "zugzwang":         "zugzwang",
    "rookEndgame":      "finale de tours",
    "endgame":          "finale",
    "pawnEndgame":      "finale de pions",
    "exposedKing":      "roi exposé",
    "attraction":       "attraction",
    "kingsideAttack":   "attaque sur l'aile roi",
    "advancedPawn":     "pion avancé",
    "sacrifice":        "sacrifice",
    "mate":             "mat",
    "fork":             "fourchette",
    "middlegame":       "milieu de jeu",
}

# Thèmes de phase Lichess (distincts des catégories ci-dessus, bien que
# "endgame"/"middlegame" soient utilisés à la fois comme catégorie ET comme
# thème de phase — cf. CONTEXTE.md) — correspondance avec les valeurs du
# sélecteur de phase déjà utilisé par le mode Exercice ("mes erreurs").
PHASES_LICHESS = {"ouverture": "opening", "milieu_de_partie": "middlegame", "finale": "endgame"}


def categorie_correspond(themes: list, categorie: str) -> bool:
    """Un problème porte-t-il le thème de cette catégorie ? "mate" couvre
    aussi les variantes mateIn1/mateIn2/... (issue #78, énoncé)."""
    if categorie == "mate":
        return any(t == "mate" or t.startswith("mateIn") for t in themes)
    return categorie in themes


# ── Niveau de départ par catégorie (issue #78) ──────────────────────────────
# Performances relevées sur les pages Lichess "Tableau de bord"/"Points
# forts"/"Aspects à améliorer" d'Alain (30 jours, 115 problèmes, 56%
# résolus, ~1471 de performance globale) — valeurs de départ APPROXIMATIVES
# et modifiables, chacune (nb_problemes_faits, performance_relevee).
# Catégorie absente de ce dict, ou avec nb_problemes_faits=0 : repli complet
# sur NIVEAU_DEPART_DEFAUT (cf. valeur_depart_categorie ci-dessous) — c'est
# aussi ce repli qui sert de valeur de référence pour la phase "ouverture"
# (aucune des 16 catégories ne représente l'ouverture en tant que telle).
PERFORMANCES_INITIALES = {
    "pin":              (4,  1673),
    "discoveredAttack": (6,  1672),
    "defensiveMove":    (10, 1629),
    "quietMove":        (14, 1600),
    "zugzwang":         (54, 1522),
    "rookEndgame":      (10, 1513),
    "endgame":          (67, 1508),
    "pawnEndgame":      (42, 1493),
    "exposedKing":      (6,  962),
    "attraction":       (4,  1025),
    "kingsideAttack":   (7,  1087),
    "advancedPawn":     (5,  1155),
    "sacrifice":        (6,  1309),
    "mate":             (20, 1357),
    "fork":             (7,  1363),
    "middlegame":       (48, 1422),
}

# Valeur de repli globale (performance Lichess tous thèmes confondus sur 30
# jours) — réglable ici uniquement.
NIVEAU_DEPART_DEFAUT = 1471

# Poids du repli vers NIVEAU_DEPART_DEFAUT pour les catégories peu pratiquées
# (issue #78, énoncé) : valeur_depart = (n*perf + POIDS_LISSAGE*1471) /
# (n+POIDS_LISSAGE) — plus POIDS_LISSAGE est grand, plus il faut de problèmes
# faits pour que la performance relevée l'emporte sur le repli. Réglable ici
# uniquement.
POIDS_LISSAGE = 5

# Fenêtre de note autour du niveau de la catégorie pour le tirage d'un
# problème (issue #78, énoncé : "±100"), élargie progressivement si aucun
# problème ne s'y trouve plutôt que d'échouer le tirage. Réglables ici
# uniquement.
FENETRE_NOTE = 100
FENETRE_NOTE_PAS_ELARGISSEMENT = 100
FENETRE_NOTE_MAX = 700

# Pas de mise à jour du classement Elo de la catégorie après un résultat
# (issue #78, énoncé : "environ 24 à 32 points") — réglable ici uniquement.
PAS_ELO = 28

# Bornes de sécurité du niveau d'une catégorie après mise à jour Elo (issue
# #78 : "jamais hors limites raisonnables") — très larges, servent seulement
# de garde-fou contre une dérive après une très longue série de réussites ou
# d'échecs, pas des bornes de jeu normales.
NIVEAU_MIN = 400
NIVEAU_MAX = 3000


def valeur_depart_categorie(categorie: str) -> float:
    """Valeur de départ du niveau d'une catégorie (issue #78), pondérée vers
    NIVEAU_DEPART_DEFAUT quand peu de problèmes ont été faits dans cette
    catégorie — cf. POIDS_LISSAGE ci-dessus. Catégorie absente de
    PERFORMANCES_INITIALES (future catégorie, erreur de frappe...) : repli
    direct sur NIVEAU_DEPART_DEFAUT (équivaut à n=0)."""
    n, perf = PERFORMANCES_INITIALES.get(categorie, (0, NIVEAU_DEPART_DEFAUT))
    return (n * perf + POIDS_LISSAGE * NIVEAU_DEPART_DEFAUT) / (n + POIDS_LISSAGE)


def charger_puzzles(path) -> list:
    """Charge le pool de problèmes préparé par preparer_puzzles_lichess.py.
    Retourne [] si le fichier est absent ou illisible (script pas encore
    lancé) — la source "Problèmes Lichess" se désactive alors proprement
    côté app.py, même tolérance que _load_erreurs_detectees."""
    path = Path(path)
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception as e:
        logger.warning(f"Pool de problèmes Lichess illisible ({path}) : {e}")
        return []


def charger_niveaux(path) -> dict:
    """Charge les niveaux courants par catégorie (donnée personnelle, un seul
    niveau Elo-like par catégorie). Retourne {} si absent/illisible — chaque
    catégorie non encore présente est alors initialisée à la demande par
    niveau_categorie() ci-dessous, à partir de valeur_depart_categorie()."""
    path = Path(path)
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.warning(f"Niveaux de problèmes Lichess illisibles ({path}) : {e}")
        return {}


def _sauvegarder_niveaux(path, niveaux: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(niveaux, f, ensure_ascii=False, indent=2)
    tmp_path.replace(path)


def niveau_categorie(niveaux: dict, categorie: str) -> float:
    """Niveau courant d'une catégorie : valeur mémorisée si déjà présente
    dans `niveaux` (donnée personnelle), sinon calculée à la volée depuis
    valeur_depart_categorie() SANS écrire sur le disque (seule une mise à
    jour réelle après résultat, cf. mettre_a_jour_niveau, doit persister un
    fichier)."""
    if categorie in niveaux:
        return niveaux[categorie]
    return valeur_depart_categorie(categorie)


def mettre_a_jour_niveau(niveaux: dict, path, categorie: str, note_probleme: float,
                          reussite: bool) -> float:
    """Met à jour le niveau d'une catégorie après un résultat (issue #78),
    formule du classement Elo : résultat attendu = 1 / (1 + 10^((note du
    problème - niveau) / 400)), nouveau niveau = niveau + PAS_ELO *
    (résultat réel - résultat attendu), résultat réel = 1 si réussite, 0
    sinon. Un échec fait donc baisser le niveau (résultat attendu > 0 non
    atteint), une réussite le fait monter — jamais hors de [NIVEAU_MIN,
    NIVEAU_MAX]. Persiste immédiatement (comme exercise_history) et retourne
    le nouveau niveau pour affichage éventuel côté appelant."""
    niveau_avant = niveau_categorie(niveaux, categorie)
    resultat_attendu = 1.0 / (1.0 + 10 ** ((note_probleme - niveau_avant) / 400.0))
    resultat_reel = 1.0 if reussite else 0.0
    nouveau = niveau_avant + PAS_ELO * (resultat_reel - resultat_attendu)
    nouveau = max(NIVEAU_MIN, min(NIVEAU_MAX, nouveau))
    niveaux[categorie] = nouveau
    _sauvegarder_niveaux(path, niveaux)
    return nouveau


def _poids_categorie(niveau: float) -> float:
    """Poids de tirage d'une catégorie (issue #78 : "une probabilité qui
    décroît avec le niveau, pour que les thèmes faibles reviennent plus
    souvent sans exclure les autres") — décroissant et toujours strictement
    positif (jamais 0, donc jamais une catégorie totalement exclue), simple
    inverse du niveau : une catégorie à 900 a près du double du poids d'une
    catégorie à 1800."""
    return 1.0 / max(1.0, niveau)


def categories_compatibles(pool: list, phase_theme: str | None) -> dict:
    """Catégories pour lesquelles au moins un problème du pool porte à la
    fois le thème de la catégorie et, si phase_theme est fourni, le thème de
    phase demandé (issue #78, énoncé) — {categorie: [problèmes]}."""
    resultat = {}
    for categorie in CATEGORIES:
        candidats = [
            p for p in pool
            if categorie_correspond(p.get("themes", []), categorie)
            and (phase_theme is None or phase_theme in p.get("phases", []))
        ]
        if candidats:
            resultat[categorie] = candidats
    return resultat


def _filtrer_fenetre(candidats: list, niveau: float, fenetre: float) -> list:
    return [p for p in candidats if abs(p.get("rating", niveau) - niveau) <= fenetre]


def tirer_probleme(pool: list, phase_theme: str | None, niveaux: dict, historique: dict,
                    categorie_forcee: str | None = None):
    """Tire un problème Lichess (issue #78, choix explicite de catégorie
    ajouté par l'issue #83), par ordre :

    1. Catégorie :
       - Automatique (categorie_forcee=None, comportement d'origine) :
         catégories compatibles avec la phase demandée (thème de catégorie +
         thème de phase tous deux présents sur le problème, cf.
         categories_compatibles), puis tirage pondéré d'UNE catégorie parmi
         elles, favorisant les niveaux les plus bas (cf. _poids_categorie).
       - Choisie (categorie_forcee = une clé de CATEGORIES, issue #83) :
         cette catégorie est imposée. Si elle n'a aucun problème pour la
         phase demandée, la phase est IGNORÉE pour ce tirage plutôt que
         d'échouer — avertissement (une phrase) retourné pour affichage
         plutôt qu'un tirage silencieusement différent de ce qui a été
         demandé.
    2. Dans cette catégorie, fenêtre de note [niveau-FENETRE_NOTE,
       niveau+FENETRE_NOTE], élargie progressivement si vide.
    3. Dans cette fenêtre, exercise_history.choisir_exercice (réutilisé tel
       quel : jamais proposé > dû pour révision > plus ancien de la
       catégorie épuisée) — la "FEN" qu'il utilise comme clé d'historique
       est ici l'identifiant "lichess:<PuzzleId>" (cf. entrée "fen_avant" du
       pool, posée par preparer_puzzles_lichess.py), pas une position.

    Retourne (entree, categorie, avertissement) ou (None, None, None) si
    aucun problème n'est disponible pour la catégorie/phase demandée (pool
    vide, phase non couverte en automatique, ou catégorie forcée totalement
    absente du pool)."""
    import exercise_history  # import tardif : évite un cycle avec app.py au chargement

    avertissement = None

    if categorie_forcee:
        candidats_categorie = [
            p for p in pool if categorie_correspond(p.get("themes", []), categorie_forcee)
        ]
        if not candidats_categorie:
            return None, None, None
        categorie = categorie_forcee
        if phase_theme is not None:
            candidats_phase = [p for p in candidats_categorie if phase_theme in p.get("phases", [])]
            if candidats_phase:
                candidats_categorie = candidats_phase
            else:
                avertissement = (
                    f"Aucun problème de catégorie « {CATEGORIES.get(categorie, categorie)} » "
                    "pour cette phase de partie : la phase a été ignorée pour ce tirage."
                )
    else:
        compatibles = categories_compatibles(pool, phase_theme)
        if not compatibles:
            return None, None, None
        categories_ok = list(compatibles.keys())
        poids = [_poids_categorie(niveau_categorie(niveaux, c)) for c in categories_ok]
        categorie = random.choices(categories_ok, weights=poids, k=1)[0]
        candidats_categorie = compatibles[categorie]

    niveau = niveau_categorie(niveaux, categorie)
    fenetre = FENETRE_NOTE
    fenetres_candidats = _filtrer_fenetre(candidats_categorie, niveau, fenetre)
    while not fenetres_candidats and fenetre < FENETRE_NOTE_MAX:
        fenetre += FENETRE_NOTE_PAS_ELARGISSEMENT
        fenetres_candidats = _filtrer_fenetre(candidats_categorie, niveau, fenetre)
    if not fenetres_candidats:
        # Fenêtre maximale toujours vide (catégorie compatible avec la phase
        # mais notes trop éloignées du niveau courant) : repli sur tous les
        # candidats de la catégorie plutôt qu'échouer le tirage.
        fenetres_candidats = candidats_categorie

    entree = exercise_history.choisir_exercice(fenetres_candidats, historique)
    return entree, categorie, avertissement
