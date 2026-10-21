"""avis_format.py — ChessCoach (issue #135, suite #125)

Format structuré imposé aux avis du coach en mode "Exercice", IDENTIQUE pour
Claude et Mistral (cf. llm_coach._REPONSE_STRUCTUREE_ADDENDUM, qui impose ces
titres exacts dans le prompt système) : titres fixes à deux niveaux ("## "
pour une section, "### " pour une sous-rubrique), dans un ordre imposé.

Avant cette issue, Claude et Mistral répondaient en prose libre (4
paragraphes sans titre, issue #91) : certains avis mélangeaient, dans le
MÊME paragraphe, le meilleur coup et le coup réellement joué à l'époque
("le meilleur coup était... à l'époque, tu avais joué..."), rendant la
lecture confuse — trois coups différents (coup proposé, meilleur coup
Stockfish, coup de l'époque) doivent toujours être clairement séparés.

Ce module est partagé par :
  - llm_coach.py (journalisation des sections lues + indicateur de
    conformité + version du format, cf. _log_coach_call) ;
  - app.py (transmission des sections au client pour l'affichage séparé,
    cf. on_exercise_answer/_on_exercise_answer_lichess) ;
  - fact_checker.py (lecture ciblée de la rubrique "Évaluation rapide"
    plutôt que de la première phrase du texte brut, pour le contrôle du mot
    de verdict).

Aucune dépendance à python-chess ni à aucun autre module de ce dépôt :
une simple fonction de découpage par expressions régulières, déterministe,
jamais d'appel réseau."""

import re

# Version du format de prompt (issue #135, tâche 5) : incrémenter à chaque
# changement de la structure imposée (titres ajoutés/retirés/réordonnés) —
# sert à regrouper les avis du journal par version de format dans un rapport
# ultérieur. 1 = ancien format en 4 paragraphes sans titre (issue #91),
# jamais écrit par ce module (il n'existait pas encore) ; 2 = ce format à
# titres fixes.
FORMAT_AVIS_VERSION = 2

TITRE_COUP_JOUE = "Coup joué"
TITRE_EVALUATION_RAPIDE = "Évaluation rapide"
TITRE_POINTS_NEGATIFS = "Points négatifs"
TITRE_POINTS_POSITIFS = "Points positifs"
TITRE_MEILLEUR_COUP = "Meilleur coup"
TITRE_EXPLICATION = "Explication"
TITRE_COUP_EPOQUE = "Coup de l'époque"
TITRE_CONCLUSION = "Conclusion"

# Deux ordres valides pour les titres de premier niveau : avec ou sans
# "Coup de l'époque" (omis quand le coup de la partie d'origine est
# identique au coup proposé, ou qu'il n'existe aucune partie d'origine —
# cf. _EXERCISE_LICHESS_ADDENDUM/_REPONSE_STRUCTUREE_ADDENDUM, llm_coach.py).
_ORDRE_AVEC_EPOQUE = [TITRE_COUP_JOUE, TITRE_MEILLEUR_COUP, TITRE_COUP_EPOQUE, TITRE_CONCLUSION]
_ORDRE_SANS_EPOQUE = [TITRE_COUP_JOUE, TITRE_MEILLEUR_COUP, TITRE_CONCLUSION]

_RE_TITRE_N1 = re.compile(r'^##[ \t]+(.+?)[ \t]*$', re.MULTILINE)
_RE_TITRE_N2 = re.compile(r'^###[ \t]+(.+?)[ \t]*$', re.MULTILINE)


def _sous_sections(bloc: str) -> list:
    """Liste des sous-titres ("### ...") d'un bloc, avec leur contenu
    (texte entre ce sous-titre et le suivant, ou la fin du bloc) —
    [(titre, contenu), ...] dans l'ordre d'apparition."""
    matches = list(_RE_TITRE_N2.finditer(bloc))
    resultat = []
    for i, m in enumerate(matches):
        debut = m.end()
        fin = matches[i + 1].start() if i + 1 < len(matches) else len(bloc)
        resultat.append((m.group(1).strip(), bloc[debut:fin].strip()))
    return resultat


def parser_avis(texte: str) -> dict:
    """Découpe la réponse brute du coach selon le format à titres fixes
    imposé par le prompt système (issue #135).

    Retourne toujours {"conforme": bool, "sections": dict} :
      - "conforme" est False si un titre de premier niveau obligatoire est
        absent, dans le désordre, ou si une sous-rubrique obligatoire
        manque sous "Coup joué"/"Meilleur coup" — dans ce cas "sections"
        est un dict vide : l'appelant doit alors traiter `texte` comme du
        texte brut non structuré (rien n'est perdu, cf. app.py), jamais
        tenter de recomposer un affichage partiel.
      - sinon, "sections" contient :
          "coup_joue_evaluation_rapide", "coup_joue_points_negatifs",
          "coup_joue_points_positifs", "meilleur_coup_explication",
          "coup_epoque" (chaîne vide si la rubrique est absente — coup
          identique ou partie d'origine inexistante), "conclusion".
    """
    texte = texte or ""
    titres_n1 = [m.group(1).strip() for m in _RE_TITRE_N1.finditer(texte)]

    if titres_n1 == _ORDRE_AVEC_EPOQUE:
        a_coup_epoque = True
    elif titres_n1 == _ORDRE_SANS_EPOQUE:
        a_coup_epoque = False
    else:
        return {"conforme": False, "sections": {}}

    matches_n1 = list(_RE_TITRE_N1.finditer(texte))
    blocs = {}
    for i, m in enumerate(matches_n1):
        debut = m.end()
        fin = matches_n1[i + 1].start() if i + 1 < len(matches_n1) else len(texte)
        blocs[titres_n1[i]] = texte[debut:fin].strip()

    sous_coup_joue = dict(_sous_sections(blocs.get(TITRE_COUP_JOUE, "")))
    eval_rapide = sous_coup_joue.get(TITRE_EVALUATION_RAPIDE)
    points_negatifs = sous_coup_joue.get(TITRE_POINTS_NEGATIFS)
    points_positifs = sous_coup_joue.get(TITRE_POINTS_POSITIFS)

    sous_meilleur_coup = dict(_sous_sections(blocs.get(TITRE_MEILLEUR_COUP, "")))
    explication = sous_meilleur_coup.get(TITRE_EXPLICATION)

    if eval_rapide is None or points_negatifs is None or points_positifs is None or explication is None:
        return {"conforme": False, "sections": {}}

    return {
        "conforme": True,
        "sections": {
            "coup_joue_evaluation_rapide": eval_rapide,
            "coup_joue_points_negatifs": points_negatifs,
            "coup_joue_points_positifs": points_positifs,
            "meilleur_coup_explication": explication,
            "coup_epoque": blocs.get(TITRE_COUP_EPOQUE, "") if a_coup_epoque else "",
            "conclusion": blocs.get(TITRE_CONCLUSION, ""),
        },
    }
