"""
llm_coach.py — ChessCoach (extrait/adapté de nicsoft/modes/opening_explorer/llm_explainer.py, AlChess)

Garde de l'original :
  - le pattern « construction du system prompt + prompt utilisateur +
    appel API + conversation multi-tours » (fonction `get_analyse_response`
    d'AlChess, issue #196) ;
  - l'appel HTTP brut à l'API Claude (`urllib`, pas de SDK requis).

Retiré par rapport à l'original :
  - le support trilingue FR/EN/DE (un seul prompt système, en français) ;
  - le provider OpenAI (ChessCoach n'utilise que l'API Claude) ;
  - tout ce qui concernait le mode pédagogique débutant (explications de
    coups d'ouverture avec flèches SVG, cache disque par ligne/coup) —
    hors sujet pour un coach d'analyse post-partie.

Ajouté pour ChessCoach :
  - `load_coach_memory` / `_build_memory_text` : un fichier de contexte JSON
    externe (mémoire du coach) est chargé et injecté dans le system prompt,
    en plus du PGN/FEN de la partie du jour. Le schéma de ce fichier est
    laissé libre côté ChessCoach (voir NOTES_EXPORT.md) — ce module se
    contente de le sérialiser tel quel dans le prompt.
"""

import json
import logging
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("chesscoach.llm_coach")


class CreditInsuffisantError(Exception):
    """Levée quand l'API Claude répond que le crédit est épuisé (issue #54,
    erreur HTTP 403 de type "billing_error") — distinguée des autres erreurs
    HTTP pour que l'appelant puisse afficher un message clair dans le chat
    plutôt qu'une erreur technique générique."""
    pass

_SYSTEM_PROMPT = (
    "Tu es un coach d'échecs personnel. Tu aides un joueur à analyser une "
    "partie qu'il vient de jouer, en te basant sur la position, le coup "
    "courant et le PGN fournis en contexte, ainsi que sur son historique de "
    "progression si disponible. Sois direct et factuel, sans flatterie, "
    "sans émoji. Appuie-toi sur les erreurs récurrentes déjà identifiées "
    "dans son historique pour rendre tes remarques plus utiles dans la "
    "durée. Quand une évaluation Stockfish réelle de la position (score ou "
    "mat forcé annoncé) est fournie en contexte, base ton jugement du coup "
    "d'abord sur cette évaluation réelle, pas seulement sur la comparaison "
    "au meilleur coup : un coup qui mène à un mat forcé contre le joueur "
    "n'est jamais un bon coup, même s'il semble raisonnable à première vue. "
    "Si un programme d'entraînement en cours (objectifs_courants) figure "
    "dans sa mémoire de progression, garde ces priorités à l'esprit et "
    "relie tes réponses à ces objectifs quand c'est pertinent. "
    "Réponds en français."
)

# Complément de system prompt partagé (issue #26), ajouté dès qu'un verdict
# Stockfish et/ou une PV (ligne calculée) figurent dans le contexte — plus
# seulement en mode "exercice" (cf. get_coach_response) : les mêmes classes
# de bugs (verdicts improvisés/contradictoires, inventions tactiques) valent
# pour tout mode qui transmet ces champs au coach (pédagogique/ouverture
# hors-livre/finales), pas seulement l'exercice qui les a fait apparaître en
# premier (issue #17/#20/#25). Texte volontairement neutre sur le vocabulaire
# ("le coup" / "la position en cours", jamais "cette tentative d'exercice")
# pour rester valable quel que soit le mode appelant.
_ANTI_INVENTION_ADDENDUM = (
    "Vérification des affirmations tactiques (issue #20) : quand le "
    "contexte fournit une suite réellement calculée par Stockfish (\"Suite "
    "réellement calculée par Stockfish...\"), c'est ta SEULE base pour "
    "expliquer une menace, une combinaison ou un mat — construis ton "
    "commentaire sur cette ligne précise, pas sur une justification "
    "positionnelle générique improvisée. Si Alain affirme lui-même une "
    "menace, une combinaison ou un mat (annoncé ou évité) sur le coup ou la "
    "position en cours, ne confirme JAMAIS cette affirmation par simple "
    "plausibilité : vérifie-la contre la ou les lignes calculées fournies "
    "dans le contexte. Si elle y est explicitement présente, confirme-la en "
    "t'appuyant sur cette ligne précise. Si elle n'y apparaît pas, ou si "
    "aucune ligne calculée n'a été fournie pour ce coup, dis-le clairement "
    "(par exemple \"je ne suis pas sûr, je ne vois pas cette suite dans mon "
    "analyse\") plutôt que d'acquiescer sans base réelle — une réponse "
    "honnête et prudente est toujours préférable à une confirmation non "
    "fondée, même si l'affirmation d'Alain paraît plausible."
    "\n\n"
    "Interdiction d'inventer une pièce, une case ou une menace (issue #25) : "
    "une ligne calculée par Stockfish (\"Suite réellement calculée...\") ne "
    "te donne QUE la séquence de coups en notation SAN — elle ne te dit PAS "
    "explicitement quelle pièce occupe une case donnée avant qu'un coup ne "
    "l'atteigne ou ne la capture. Un coup comme \"Nxg6\" te dit qu'un "
    "cavalier capture sur g6, mais ne te dit RIEN sur la nature de la pièce "
    "capturée : ne la nomme jamais (\"le cavalier en g6\", \"le fou en g6\"...) "
    "sauf si cette pièce t'a été explicitement donnée par ailleurs dans le "
    "contexte (FEN, ou champs pièce/capture fournis pour coup_propose/"
    "coup_reel/meilleur_coup). En cas de doute réel sur l'identité d'une "
    "pièce, décris uniquement la séquence de coups elle-même (\"la dame va "
    "en h4, puis après Qf3 Nd7, le cavalier prend sur g6\") sans qualifier "
    "la pièce prise. De même, ne fais jamais remonter une menace ou une "
    "capture à un coup plus tôt qu'elle n'apparaît réellement dans la ligne "
    "donnée : si la capture n'a lieu qu'au 3e coup de la suite, ne dis pas "
    "que le 1er coup \"menace\" ou \"crée une attaque directe\" sur la case "
    "en question — décris le plan tel qu'il s'enchaîne réellement, coup "
    "après coup, sans raccourci qui déforme le moment où la menace se "
    "concrétise."
    "\n\n"
    "Vérification des cases mentionnées (issue #44) : avant de nommer "
    "explicitement la case précise où se trouve une pièce (par exemple "
    "\"ta dame est en b5\"), vérifie cette affirmation contre le FEN fourni "
    "dans le contexte, case par case si nécessaire — ne la déduis JAMAIS de "
    "mémoire, par association avec un message précédent de la même "
    "conversation, ou par supposition sur l'endroit où une pièce \"devrait\" "
    "se trouver après tel ou tel coup. Un message que tu as toi-même écrit "
    "plus tôt dans la conversation n'est pas une source fiable pour "
    "localiser une pièce maintenant : la position a pu changer depuis, ou "
    "ce message précédent contenir lui-même une erreur. En cas de doute "
    "réel sur la case exacte d'une pièce, décris la situation sans donner "
    "de case précise plutôt que d'en affirmer une qui n'est pas vérifiée "
    "contre le FEN."
)

# Complément de system prompt pour une position issue d'une démonstration
# Stockfish-contre-Stockfish (issue #29, mode "Travail de finales" — voir
# app.py on_finale_demo_start/on_finale_demo_next) : sans ce garde-fou, un
# chat libre sollicité pendant/après une démonstration (aucun coup joué par
# Alain) a déjà inventé un récit accusant Alain d'avoir mal joué la finale,
# en confondant la position affichée avec une partie qu'il aurait lui-même
# jouée. Ajouté dès que context["mode_demonstration"] est vrai (cf.
# _build_context_text), indépendamment des autres compléments ci-dessous.
_DEMONSTRATION_ADDENDUM = (
    "Mode \"démonstration\" en cours (voir le champ mode_demonstration du "
    "contexte) : la position affichée résulte d'une séquence où Stockfish "
    "joue seul les deux camps, coup après coup, sans aucune intervention "
    "d'Alain. Tu peux expliquer la position elle-même, la technique de mat "
    "ou de finale qu'elle illustre, ou pourquoi tel camp joue tel coup — "
    "mais tu ne dois JAMAIS attribuer une erreur, une faute ou un mauvais "
    "coup à Alain sur cette séquence, ni raconter qu'il aurait \"mal joué\" "
    "ou \"laissé échapper\" quoi que ce soit : il n'a joué aucun des coups "
    "affichés. Tu peux mentionner ses erreurs passées sur ce thème comme "
    "contexte général si sa mémoire de progression en fournit, mais jamais "
    "comme si elles venaient de se reproduire dans cette démonstration."
)

# Complément de system prompt spécifique au mode "Exercice" (issue #17),
# ajouté à _SYSTEM_PROMPT quand context["mode_exercice"] est vrai — que ce
# soit pour le commentaire du coup proposé (exercise_answer) ou pour une
# question de suivi posée dans le chat libre pendant l'exercice. Les LLM
# (tous modèles confondus) se sont révélés peu fiables pour juger eux-mêmes
# la qualité d'un coup à partir du seul nom des coups (ex. verdicts
# contradictoires sur un même roque selon le tour de conversation) : ce
# complément leur retire ce rôle de jugement dès qu'un verdict Stockfish est
# fourni dans le contexte (cf. _build_context_text), tout en gardant un ton
# chaleureux et pédagogique — l'ancrage sur Stockfish doit rendre le coach
# plus fiable, pas plus froid. Le garde-fou anti-invention (issue #25/#26)
# lui-même est mutualisé avec les autres modes via _ANTI_INVENTION_ADDENDUM.
_EXERCISE_SYSTEM_ADDENDUM = (
    "Mode \"exercice\" en cours : Alain s'entraîne sur une position tirée "
    "d'une de ses erreurs passées. Quand un verdict Stockfish est fourni "
    "dans le contexte pour un coup qu'il a proposé, ce verdict est déjà "
    "tranché — ton rôle est d'expliquer POURQUOI il est justifié (menaces, "
    "pièces en jeu, plans), jamais de rejuger toi-même la qualité du coup à "
    "partir du seul nom des coups, et jamais de le contredire dans un "
    "message ultérieur de la même conversation. Ne cite jamais de chiffre "
    "brut de centipawns ni d'étiquette technique (\"delta\", \"blunder\"...) "
    "à Alain, sauf s'il le demande explicitement : reformule toujours ce "
    "verdict en langage naturel, chaleureux et pédagogique. Si Alain pose "
    "une question de suivi sur cet exercice dans le chat libre, réponds "
    "directement à partir du contexte fourni (position, coup proposé, "
    "verdict) sans lui redemander des informations déjà données. "
    "\n\n"
    + _ANTI_INVENTION_ADDENDUM
)

# Appel dédié, distinct du chat coach (issue #14, "Établir mon programme
# d'entraînement") : comme get_opening_moves, une réponse structurée en JSON
# plutôt que de la prose libre, pour pouvoir stocker le résultat de façon
# fiable dans objectifs_courants (coach_memory.json).
_TRAINING_PROGRAM_SYSTEM_PROMPT = (
    "Tu es un coach d'échecs personnel. On te fournit les patterns "
    "d'erreurs récurrentes du joueur (par phase de partie) et son "
    "répertoire d'ouvertures (Blancs et Noirs), au format JSON. À partir de "
    "ces données, établis un programme de travail concret : 2 à 3 "
    "priorités d'entraînement, chacune en une phrase courte et actionnable "
    "(pas de prose ni de longue justification), ciblant les points les "
    "plus impactants pour progresser. Réponds UNIQUEMENT avec un objet "
    "JSON, sans aucun texte ni balise autour, au format exact "
    "{\"objectifs\": [\"...\", \"...\"]} où \"objectifs\" contient 2 à 3 "
    "chaînes de caractères, en français."
)

# Appel dédié, distinct du chat coach (issue #9, mode "travail d'ouverture") :
# un livre Polyglot ne connaît que des positions/coups, pas de noms
# d'ouverture. On demande donc à Claude, une seule fois au démarrage du mode,
# les quelques coups caractéristiques permettant d'atteindre la position de
# départ réelle de l'entraînement, à partir de sa connaissance générale des
# ouvertures standard — ensuite, c'est le livre Polyglot qui prend le relais.
_OPENING_SYSTEM_PROMPT = (
    "Tu es un expert en théorie des ouvertures d'échecs. On te donne le nom "
    "d'une ouverture, éventuellement en français, en anglais, ou avec de "
    "petites fautes de frappe. Réponds UNIQUEMENT avec un objet JSON, sans "
    "aucun texte ni balise autour, au format exact "
    "{\"moves\": [\"e4\", \"e5\", \"Nf3\", ...]} où \"moves\" est la liste "
    "ordonnée des 2 à 6 premiers coups caractéristiques de cette ouverture, "
    "en notation SAN standard, dans l'ordre où ils sont joués (en alternant "
    "Blancs puis Noirs). Si le nom donné ne correspond à aucune ouverture "
    "d'échecs reconnaissable, réponds UNIQUEMENT avec "
    "{\"error\": \"ouverture_non_reconnue\"}."
)


# Appel dédié, distinct du chat coach (issue #42, module d'analyse post-
# partie) : comme get_opening_moves/get_training_program, une réponse
# structurée en JSON plutôt que de la prose libre. Contrairement à un simple
# classement mécanique par delta_cp (issue #41), c'est le coach qui choisit
# lui-même les coups les plus instructifs parmi ceux flagués, avec pour
# consigne explicite de rester ancré sur les données réelles transmises
# (jamais un coup hors de la liste fournie) — même logique de garde-fou
# anti-invention qu'ailleurs (issue #17/#22/#25), adaptée ici à un appel en
# lot plutôt qu'à un coup unique avec PV.
_MOVE_SELECTION_SYSTEM_PROMPT = (
    "Tu es un coach d'échecs personnel. On te fournit la liste complète des "
    "coups flagués (imprécision, erreur ou gaffe) d'une partie qu'Alain "
    "vient de jouer, au format JSON — un objet par coup, avec : id (identifiant "
    "numérique unique de ce coup dans la liste — à recopier tel quel dans ta "
    "réponse, il ne te renseigne sur rien d'autre), camp (\"blancs\"/"
    "\"noirs\"), coup_plein (numéro du coup plein), san et uci (le coup "
    "réellement joué — ATTENTION, un même uci/san peut réapparaître "
    "plusieurs fois dans la liste, par exemple lors d'échecs répétés par "
    "va-et-vient d'une tour : c'est bien \"id\" qui identifie CE coup précis, "
    "jamais uci ni san), meilleur_coup (le coup recommandé par Stockfish à "
    "cette position, ou null si non disponible), qualite "
    "(\"imprecision\"/\"erreur\"/\"blunder\"), delta_cp (perte en "
    "centipawns par rapport au meilleur coup) et phase "
    "(\"ouverture\"/\"milieu_de_partie\"/\"finale\"). Choisis, PARMI CETTE "
    "LISTE UNIQUEMENT, jusqu'à 5 coups que tu juges réellement décisifs pour "
    "l'issue ou l'apprentissage de la partie — pas nécessairement ceux à la "
    "plus grosse perte en centipawns : un coup moins spectaculaire en "
    "chiffre peut être plus instructif (par exemple un coup passif qui ne "
    "participe pas à une attaque en cours, ou un échange favorable manqué). "
    "Pour chaque coup choisi, rédige une explication courte et concrète en "
    "langage naturel, comme un coach donnerait à l'oral (par exemple \"tu "
    "as raté l'occasion d'un échange favorable\" ou \"ce coup est passif, "
    "il ne participe pas à l'assaut du roque adverse\"), fondée UNIQUEMENT "
    "sur les données fournies pour ce coup précis (camp, coup joué, "
    "meilleur coup, phase, qualité, perte en centipawns) — n'invente jamais "
    "de pièce, case, menace ou combinaison qui n'en serait pas déductible. "
    "Ne cite jamais le chiffre brut de centipawns ni l'étiquette technique "
    "(\"delta\", \"blunder\"...) dans l'explication : reformule toujours en "
    "langage naturel. Réponds UNIQUEMENT avec un objet JSON, sans aucun "
    "texte ni balise autour, au format exact {\"choix\": [{\"id\": 0, "
    "\"explication\": \"...\"}, ...]} où chaque \"id\" correspond EXACTEMENT "
    "à l'un des coups de la liste fournie (aucun id inventé, aucun autre "
    "coup ne doit apparaître), en français."
)


def get_move_explanations(flagged_moves, config):
    """Sélectionne jusqu'à 5 coups décisifs parmi les coups flagués d'une
    partie et fournit une explication en langage naturel pour chacun (issue
    #42, module d'explications narratives du rapport d'analyse post-partie
    de l'issue #41) — un appel dédié, indépendant du chat coach multi-tours,
    même pattern que get_opening_moves/get_training_program (réponse JSON
    structurée, pas du chat libre).

    Paramètres :
      flagged_moves : liste de dicts, un par coup flagué de la partie
                      ({"id", "uci", "san", "camp", "coup_plein", "delta_cp",
                      "qualite", "phase", "meilleur_coup"}) — construite par
                      l'appelant (app.py) à partir du rapport mécanique de
                      l'issue #41. "id" doit être unique par coup : un même
                      uci/san peut réapparaître plusieurs fois dans une
                      partie (ex. échecs répétés par va-et-vient d'une tour,
                      constaté en vérification réelle), donc l'uci seul ne
                      suffit pas à réassocier sans ambiguïté le choix du
                      coach à son coup d'origine.
      config        : dict avec au moins "llm_api_key" et, optionnellement,
                      "llm_model" (même convention que get_opening_moves)

    Retourne (liste de {"id", "explication"}, erreur) — un seul des deux
    est non vide/None. La liste retournée est filtrée pour ne contenir QUE
    des id présents dans flagged_moves (garde-fou appliqué ici, pas
    seulement dans le system prompt : jamais d'invention au-delà des coups
    listés, même si le modèle en proposait un autre). Erreurs possibles :
    "no_api_key", "aucun_coup_flague", "reponse_invalide", ou le message de
    l'exception réseau.
    """
    api_key = (config or {}).get("llm_api_key", "")
    if not api_key:
        return None, "no_api_key"

    if not flagged_moves:
        return None, "aucun_coup_flague"

    model = (config or {}).get("llm_model", "")
    data_text = json.dumps(flagged_moves, ensure_ascii=False, indent=2)
    prompt_user = f"Coups flagués de la partie (JSON) :\n{data_text}"

    usage_path = (config or {}).get("usage_path")
    try:
        raw = _call_claude(_MOVE_SELECTION_SYSTEM_PROMPT, prompt_user, api_key, model, usage_path)
    except CreditInsuffisantError as e:
        logger.warning(f"[LLM_COACH] Appel Claude (sélection de coups décisifs) : crédit épuisé : {e}")
        return None, "credit_insuffisant"
    except (urllib.error.URLError, urllib.error.HTTPError, KeyError, ValueError, TimeoutError) as e:
        logger.warning(f"[LLM_COACH] Appel Claude (sélection de coups décisifs) échoué : {e}")
        return None, str(e)

    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()

    try:
        parsed = json.loads(text)
    except (ValueError, TypeError):
        logger.warning(f"[LLM_COACH] Réponse sélection de coups décisifs non-JSON : {raw!r}")
        return None, "reponse_invalide"

    if not isinstance(parsed, dict):
        return None, "reponse_invalide"

    choix = parsed.get("choix")
    if not isinstance(choix, list):
        return None, "reponse_invalide"

    ids_valides = {m.get("id") for m in flagged_moves if m.get("id") is not None}
    resultat = []
    for c in choix:
        if not isinstance(c, dict):
            continue
        id_ = c.get("id")
        explication = (c.get("explication") or "").strip()
        if id_ in ids_valides and explication:
            resultat.append({"id": id_, "explication": explication})

    if not resultat:
        return None, "reponse_invalide"

    return resultat[:5], None


def load_coach_memory(path) -> dict:
    """Charge le fichier de contexte JSON externe (mémoire du coach).

    Retourne {} si le fichier est absent ou illisible : la conversation
    peut toujours avoir lieu sans mémoire, juste sans continuité.
    """
    path = Path(path)
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"[LLM_COACH] Mémoire illisible ({path}) : {e}")
        return {}


def save_coach_memory(path, memory: dict) -> None:
    """Sauvegarde le fichier de contexte JSON externe (mémoire du coach)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)
    tmp_path.replace(path)


# ── Compteur cumulé de tokens (issue #54) ───────────────────────────────────
# Fichier de données local (usage_tokens.json, sous DATA_DIR — non suivi par
# git comme coach_memory.json et le reste de data/) qui cumule les tokens
# d'entrée/sortie/cache consommés par l'API Claude, par modèle utilisé,
# depuis une date de départ. Volontairement sans aucune notion de prix ni de
# table de coût par modèle (décision explicite d'Alain) : seul le compte de
# tokens bruts est cumulé, à charge pour lui de le rapprocher du solde de la
# Console pour évaluer le coût réel d'une intervention.

_USAGE_CHAMPS = (
    "input_tokens",
    "output_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
)


def _usage_vide() -> dict:
    return {"date_debut": datetime.now().isoformat(), "dernier_appel": None, "par_modele": {}}


def load_usage(path) -> dict:
    """Charge le fichier de compteur de tokens. Retourne une structure vide
    (avec une date de départ fraîche) si le fichier est absent ou illisible —
    même tolérance que load_coach_memory."""
    path = Path(path)
    if not path.exists():
        return _usage_vide()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or "par_modele" not in data:
            return _usage_vide()
        return data
    except Exception as e:
        logger.warning(f"[LLM_COACH] Compteur de tokens illisible ({path}) : {e}")
        return _usage_vide()


def _save_usage(path, usage: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(usage, f, ensure_ascii=False, indent=2)
    tmp_path.replace(path)


def _record_usage(usage_path, model: str, usage_appel: dict) -> None:
    """Cumule les tokens d'un appel réussi dans le fichier de compteur
    (issue #54). Best-effort : une erreur d'écriture ne doit jamais faire
    échouer la réponse du coach, même logique que _log_coach_call."""
    if not usage_path:
        return
    try:
        data = load_usage(usage_path)
        modele = model or "inconnu"
        compteur = data["par_modele"].setdefault(
            modele, {champ: 0 for champ in _USAGE_CHAMPS} | {"appels": 0}
        )
        for champ in _USAGE_CHAMPS:
            compteur[champ] = compteur.get(champ, 0) + int(usage_appel.get(champ) or 0)
        compteur["appels"] = compteur.get("appels", 0) + 1
        data["dernier_appel"] = {
            "model": modele,
            "horodatage": datetime.now().isoformat(),
            **{champ: int(usage_appel.get(champ) or 0) for champ in _USAGE_CHAMPS},
        }
        _save_usage(usage_path, data)
    except Exception as e:
        logger.warning(f"[LLM_COACH] Écriture du compteur de tokens échouée : {e}")


def get_usage_summary(usage_path) -> dict:
    """Retourne la structure affichable côté client : date de départ, dernier
    appel, détail par modèle et totaux tous modèles confondus (calculés à la
    volée, jamais stockés séparément pour éviter toute désynchronisation)."""
    data = load_usage(usage_path)
    totaux = {champ: 0 for champ in _USAGE_CHAMPS}
    for compteur in data.get("par_modele", {}).values():
        for champ in _USAGE_CHAMPS:
            totaux[champ] += compteur.get(champ, 0)
    return {
        "date_debut": data.get("date_debut"),
        "dernier_appel": data.get("dernier_appel"),
        "par_modele": data.get("par_modele", {}),
        "total": totaux,
    }


def reset_usage(usage_path) -> dict:
    """Remet à zéro le compteur de tokens, y compris la date de départ
    (issue #54, bouton de remise à zéro de l'en-tête)."""
    data = _usage_vide()
    _save_usage(usage_path, data)
    return get_usage_summary(usage_path)


def _build_memory_text(memory: dict) -> str:
    """Sérialise la mémoire du coach en texte injectable dans le system prompt.

    Le schéma exact (progression, erreurs récurrentes, objectifs...) est
    défini côté ChessCoach ; ce module reste agnostique et sérialise tel
    quel en JSON lisible.
    """
    if not memory:
        return ""
    return (
        "Mémoire de progression du joueur (sessions précédentes, au format "
        "JSON) :\n" + json.dumps(memory, ensure_ascii=False, indent=2)
    )


def _build_context_text(context) -> str:
    context = context or {}
    fen  = (context.get("fen") or "").strip()
    move = (context.get("move") or "").strip()
    pgn  = (context.get("pgn") or "").strip()
    # Camp joué par Alain dans cette partie/position (issue #12 point 1) :
    # sans cette information, le coach ne peut que deviner le camp d'après le
    # trait de la FEN, ce qui l'a déjà induit en erreur (ex. exercice où
    # Alain a les Noirs, commentaire parlant à tort de "votre roi blanc").
    camp_alain = (context.get("camp_alain") or "").strip()
    # Mode "Exercice" (issue #7) : comparaison coup proposé / coup réellement
    # joué / meilleur coup Stockfish, plutôt qu'un chat libre sur une partie.
    coup_propose  = (context.get("coup_propose") or "").strip()
    coup_reel     = (context.get("coup_reel") or "").strip()
    meilleur_coup = (context.get("meilleur_coup") or "").strip()
    # Pièce jouée / pièce capturée par chacun de ces trois coups (issue #18) :
    # calculées côté app.py depuis la position réelle (python-chess), pas
    # laissées à la charge du modèle qui a pu confondre le type de pièce
    # capturée (ex. "tu prends le cavalier" pour la prise d'un pion) en ne
    # se fiant qu'au nom SAN/UCI du coup, qui ne le précise pas lui-même.
    coup_propose_piece    = (context.get("coup_propose_piece") or "").strip()
    coup_propose_capture  = (context.get("coup_propose_capture") or "").strip()
    coup_reel_piece       = (context.get("coup_reel_piece") or "").strip()
    coup_reel_capture     = (context.get("coup_reel_capture") or "").strip()
    meilleur_coup_piece   = (context.get("meilleur_coup_piece") or "").strip()
    meilleur_coup_capture = (context.get("meilleur_coup_capture") or "").strip()
    # Verdict Stockfish chiffré du coup exact proposé (issue #17), calculé via
    # EngineManager.evaluate_move (mêmes seuils que classifier_coup) : donné
    # en contexte pour que le coach explique un jugement déjà tranché plutôt
    # que de rejuger lui-même la qualité du coup à partir des seuls noms de
    # coups — ce chiffre ne doit jamais être répété tel quel à Alain (cf.
    # _EXERCISE_SYSTEM_ADDENDUM).
    verdict_qualite  = (context.get("verdict_qualite") or "").strip()
    verdict_delta_cp = context.get("verdict_delta_cp")
    # Ligne (PV) réellement calculée par Stockfish pour le coup proposé et
    # pour le meilleur coup (issue #20), en SAN, depuis la même analyse à
    # depth=18 que verdict_qualite/meilleur_coup ci-dessus (cf. app.py,
    # on_exercise_answer) : le seul ancrage disponible au coach pour
    # justifier une continuation tactique réellement calculée, ou pour juger
    # si une affirmation de menace/mat d'Alain est cohérente avec ce que
    # Stockfish a effectivement vu — jamais une preuve de mat forcé au-delà
    # de ce qu'elle montre explicitement.
    pv_coup_propose  = (context.get("pv_coup_propose") or "").strip()
    pv_meilleur_coup = (context.get("pv_meilleur_coup") or "").strip()
    # Vrai juste après un "Reprendre mon coup" tant qu'Alain n'a pas encore
    # reproposé de coup (issue #17) : évite qu'un verdict/coup discuté plus
    # tôt dans la même conversation du chat libre soit pris pour l'état réel
    # de la tentative en cours, désormais annulée.
    reprise_recente = bool(context.get("reprise_recente"))
    # Évaluation Stockfish réelle de la position résultant du coup proposé
    # (issue #12 point 3), en complément de la seule comparaison à
    # meilleur_coup : toujours du point de vue des Blancs, pour rester non
    # ambigu quel que soit le camp d'Alain ou le mode d'entraînement.
    eval_blancs_cp = context.get("eval_blancs_cp")
    eval_mat       = context.get("eval_mat")
    # Mode "Travail d'ouverture" (issue #9) : statut par rapport au livre
    # Polyglot de référence (gm2001.bin), en complément de meilleur_coup.
    dans_le_livre          = context.get("dans_le_livre")
    coup_livre_recommande  = (context.get("coup_livre_recommande") or "").strip()
    popularite_pct         = context.get("popularite_pct")
    # Mode "Travail de finales" (issue #10) : thème/technique de la
    # position-type sélectionnée (finales.py), pour que le commentaire
    # puisse s'y référer explicitement (ex. mentionner l'opposition).
    theme_finale = (context.get("theme_finale") or "").strip()
    # Démonstration Stockfish-contre-Stockfish en cours (issue #29, mode
    # "Travail de finales") : la position affichée ne résulte d'aucun coup
    # d'Alain, contrairement au jeu normal — sans ce champ explicite, le
    # coach n'a aucun moyen de distinguer une démonstration d'une partie
    # réellement jouée par Alain (voir _DEMONSTRATION_ADDENDUM).
    mode_demonstration = bool(context.get("mode_demonstration"))
    demo_coups_joues = context.get("demo_coups_joues")
    # Partie terminée par abandon (issue #52) : sans ce champ explicite, le
    # chat libre sollicité juste après un clic sur "Abandonner" ne recevait
    # que le PGN/FEN de la partie, sans savoir qu'elle est terminée ni
    # pourquoi — le coach répondait alors comme si la partie continuait,
    # voire niait qu'un coup ait été joué (plateau remis à zéro côté client
    # avant ce correctif).
    partie_terminee = bool(context.get("partie_terminee"))
    resultat_partie = (context.get("resultat_partie") or "").strip()
    lines = []
    if camp_alain in ("blancs", "noirs"):
        camp_txt = "Blancs" if camp_alain == "blancs" else "Noirs"
        lines.append(f"Alain (le joueur que tu coaches) joue les {camp_txt} dans cette partie.")
    if fen:
        lines.append(f"Position actuelle (FEN) : {fen}")
    if move:
        lines.append(f"Coup actuel : {move}")
    if coup_propose:
        # Étiquette explicite "MAINTENANT" / coup_reel étiqueté "À L'ÉPOQUE"
        # ci-dessous (issue #18 point 3) : évite que le coach présente le
        # coup réellement joué dans la partie d'origine comme si Alain
        # venait de le proposer dans la tentative en cours.
        lines.append(
            "Coup que le joueur vient de proposer MAINTENANT, dans cette "
            f"tentative d'exercice : {coup_propose}"
        )
        if coup_propose_piece:
            detail = f"Pièce jouée par ce coup : {coup_propose_piece}."
            if coup_propose_capture:
                detail += (
                    f" Pièce capturée sur la case d'arrivée : {coup_propose_capture} "
                    "(c'est cette pièce, et aucune autre, qui se trouvait sur cette case)."
                )
            lines.append(detail)
        if pv_coup_propose:
            lines.append(
                "Suite réellement calculée par Stockfish après ce coup proposé "
                f"(à utiliser comme seule base pour expliquer les menaces ou la "
                f"suite tactique, pas une généralité inventée) : {pv_coup_propose}"
            )
    if coup_reel:
        lines.append(
            "Coup que le joueur avait réellement joué À L'ÉPOQUE, dans la "
            "partie d'origine dont cet exercice est tiré — PAS le coup qu'il "
            f"vient de proposer ci-dessus : {coup_reel}"
        )
        if coup_reel_piece:
            detail = f"Pièce jouée par ce coup-là : {coup_reel_piece}."
            if coup_reel_capture:
                detail += (
                    f" Pièce capturée sur la case d'arrivée : {coup_reel_capture} "
                    "(c'est cette pièce, et aucune autre, qui se trouvait sur cette case)."
                )
            lines.append(detail)
    if meilleur_coup:
        detail = f"Meilleur coup selon Stockfish : {meilleur_coup}."
        if meilleur_coup_piece:
            detail += f" Pièce jouée par ce coup : {meilleur_coup_piece}."
            if meilleur_coup_capture:
                detail += (
                    f" Pièce capturée sur la case d'arrivée : {meilleur_coup_capture} "
                    "(c'est cette pièce, et aucune autre, qui se trouvait sur cette case)."
                )
        lines.append(detail)
        if pv_meilleur_coup:
            lines.append(
                "Suite réellement calculée par Stockfish pour ce meilleur coup "
                f"(à utiliser comme seule base pour expliquer les menaces ou le "
                f"plan qu'il prépare, pas une généralité inventée) : {pv_meilleur_coup}"
            )
    if verdict_qualite:
        detail_cp = (
            f", perte de {verdict_delta_cp} centipawns par rapport au meilleur coup"
            if isinstance(verdict_delta_cp, (int, float)) else ""
        )
        lines.append(
            "Verdict Stockfish déjà calculé pour ce coup exact (INTERNE — ne "
            f"jamais citer ce chiffre ni cette étiquette brute à Alain) : classé "
            f"\"{verdict_qualite}\"{detail_cp}. Ce verdict est définitif : "
            "explique pourquoi il est justifié, ne le confirme ni ne le "
            "contredis par ton propre jugement."
        )
    if reprise_recente:
        lines.append(
            "Alain vient d'annuler sa dernière tentative sur cet exercice avec "
            "\"Reprendre mon coup\" et n'a pas encore reproposé de coup : la "
            "position ci-dessus est donc à nouveau la position de départ, "
            "inchangée. Le coup et le verdict éventuellement discutés plus tôt "
            "dans cette conversation ne s'appliquent plus à l'état actuel."
        )
    if eval_mat is not None:
        side = "Blancs" if eval_mat > 0 else "Noirs"
        lines.append(
            f"Évaluation Stockfish réelle de la position résultant du coup proposé : "
            f"mat forcé en {abs(eval_mat)} coup(s) en faveur des {side}."
        )
    elif eval_blancs_cp is not None:
        lines.append(
            "Évaluation Stockfish réelle de la position résultant du coup proposé "
            f"(point de vue des Blancs, positif = avantage Blancs) : {eval_blancs_cp:+d} centipawns."
        )
    if dans_le_livre is not None:
        statut = "dans le livre d'ouvertures" if dans_le_livre else "hors du livre d'ouvertures"
        lines.append(f"Statut par rapport au livre de référence : {statut}")
    if popularite_pct is not None:
        lines.append(f"Popularité de ce coup dans le livre : {popularite_pct}% des parties de référence")
    if coup_livre_recommande:
        lines.append(f"Coup le plus joué dans le livre pour cette position : {coup_livre_recommande}")
    if theme_finale:
        lines.append(f"Thème technique de cette finale : {theme_finale}")
    if mode_demonstration:
        detail_coups = (
            f" ({demo_coups_joues} demi-coup(s) joué(s), tous par Stockfish, 0 par Alain)"
            if isinstance(demo_coups_joues, int) else ""
        )
        lines.append(
            "Mode démonstration : Stockfish joue seul les deux camps sur "
            f"cette position, Alain n'a joué AUCUN coup{detail_coups}."
        )
    if partie_terminee:
        detail = f" ({resultat_partie})" if resultat_partie else ""
        lines.append(
            "Cette partie est terminée{detail} — Alain ne jouera plus aucun "
            "coup dans cette partie précise. S'il pose une question sur ce "
            "qui vient de se passer, réponds à partir du PGN complet "
            "ci-dessous, ne dis jamais qu'aucun coup n'a été joué.".format(detail=detail)
        )
    if pgn:
        lines.append(f"PGN de la partie :\n{pgn}")
    return "\n".join(lines)


def _log_coach_call(log_path, system_prompt: str, context: dict, messages, mode_origine: str,
                     reponse: str = None, erreur: str = None, usage: dict = None) -> None:
    """Journalise un appel complet au coach (issue #18, étendu à tous les
    modes par l'issue #26 — plus seulement le mode "Exercice") : horodatage,
    mode d'origine, system prompt complet, contexte construit (tous les
    champs, y compris coup_propose/coup_reel/meilleur_coup/verdict_qualite/
    verdict_delta_cp/pv_coup_propose/pv_meilleur_coup) et messages envoyés,
    en JSON Lines dans log_path — pour diagnostiquer une erreur factuelle du
    coach à partir de ce qui a été réellement transmis à Haiku, pas d'une
    supposition, quel que soit le mode. Best-effort : une erreur d'écriture
    ne doit jamais faire échouer la réponse au coach.

    Étendu par l'issue #44 : le log n'enregistrait jusque-là que la requête
    envoyée à Claude, jamais sa réponse réelle — un diagnostic sur une
    affirmation erronée du coach (ex. case mentionnée incorrecte) dépendait
    donc d'un copier-coller manuel d'Alain. `reponse`/`erreur` sont les
    champs `text`/erreur retournés par `_call_claude` (un seul des deux non
    None), écrits dans la même entrée que la requête plutôt que dans une
    entrée séparée, pour garder la corrélation requête/réponse triviale à
    relire.

    Étendu par l'issue #54 : `usage` (tokens input/output/cache de cet appel
    précis, ou None si indisponible — ex. `credit_insuffisant`, aucun appel
    API n'a abouti) vient compléter le diagnostic ligne à ligne, en plus du
    compteur cumulé (usage_tokens.json).
    """
    if not log_path:
        return
    try:
        log_path = Path(log_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "horodatage": datetime.now().isoformat(),
            "mode_origine": mode_origine,
            "system_prompt": system_prompt,
            "context": context or {},
            "messages": messages,
            "reponse": reponse,
            "erreur": erreur,
            "usage": usage,
        }
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.warning(f"[LLM_COACH] Écriture du log coach_calls échouée : {e}")


def _call_claude(prompt_sys: str, messages, api_key: str, model: str, usage_path=None) -> str:
    """messages : liste de {"role": "user"|"assistant", "content": str}, ou une
    simple chaîne (raccourci équivalent à [{"role": "user", "content": messages}]).

    Retourne le texte de la réponse (comme avant l'issue #54). Lève
    CreditInsuffisantError si l'API répond que le crédit est épuisé (HTTP 403,
    error.type == "billing_error"), pour que l'appelant affiche un message
    clair au lieu de la ValueError générique. Relève aussi les tokens
    consommés (usage.input_tokens/output_tokens/cache_*) depuis la réponse et
    les cumule dans usage_path si fourni — aucun appel API supplémentaire,
    ces informations sont déjà présentes dans la réponse normale (issue #54)."""
    if isinstance(messages, str):
        messages = [{"role": "user", "content": messages}]
    body = json.dumps({
        "model": model or "claude-haiku-4-5",
        # 300 tokens coupait certaines réponses en plein mot dès que le coach
        # développait un conseil détaillé plutôt qu'un commentaire de coup
        # isolé (issue #12 point 2). 1024 s'est révélé encore insuffisant à
        # l'usage (stop_reason "max_tokens" constaté sur une question
        # détaillée type "explique-moi la stratégie de la Défense française") :
        # 2048 laisse la marge nécessaire pour ce genre de conseil structuré,
        # tout en restant loin de dériver vers des réponses interminables.
        # Porté à 4096 (issue #47) : au-delà de la marge pour le texte de
        # réponse, ce budget doit aussi couvrir un éventuel raisonnement
        # adaptatif sur claude-sonnet-5 (voir "thinking" ci-dessous) — 2048
        # pouvait être entièrement consommé par la réflexion, laissant 0
        # token pour la réponse elle-même.
        "max_tokens": 4096,
        # claude-sonnet-5 exécute un raisonnement adaptatif par défaut dès que
        # ce paramètre est omis (contrairement à Haiku, qui ne pense jamais).
        # Ce raisonnement consomme une partie de max_tokens avant même de
        # commencer à écrire la réponse ; sur une question simple, il pouvait
        # occuper tout le budget et laisser une réponse entièrement vide —
        # un seul bloc "thinking" sans aucun bloc "text" (issue #47). Un
        # commentaire de coach aux échecs n'a pas besoin d'exposer un
        # raisonnement séparé de la réponse elle-même (Haiku, utilisé
        # jusqu'à l'issue #44, ne raisonnait jamais et convenait déjà à cet
        # usage) : on désactive donc explicitement la réflexion plutôt que de
        # simplement lui laisser plus de place, ce qui élimine la classe de
        # problème à la racine.
        "thinking": {"type": "disabled"},
        "system": prompt_sys,
        "messages": messages,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST",
    )
    # 15s suffisait pour un contexte léger, mais devenait insuffisant dès que
    # le PGN complet d'une partie longue et la mémoire de progression complète
    # sont transmis (Bibliothèque/Revue), surtout depuis le passage à
    # claude-sonnet-5 (latence un peu supérieure à Haiku) — timeout "the read
    # operation timed out" observé même sur une question triviale (issue #45).
    # 90s laisse une marge large sans bloquer indéfiniment l'interface en cas
    # de vrai problème réseau.
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        # Solde de crédit épuisé (issue #54) : l'API répond alors en HTTP 403
        # avec error.type == "billing_error" (distinct de "permission_error",
        # qui partage le même code HTTP mais désigne une clé sans les droits
        # nécessaires). Le corps de la réponse doit être lu ici : une fois
        # l'exception propagée, e.read() ne serait plus disponible.
        corps = e.read().decode("utf-8", errors="replace")
        try:
            err_data = json.loads(corps)
        except (ValueError, TypeError):
            err_data = {}
        err_type = (err_data.get("error") or {}).get("type", "")
        if e.code == 403 and err_type == "billing_error":
            raise CreditInsuffisantError(
                (err_data.get("error") or {}).get("message", "Crédit épuisé")
            ) from e
        raise
    # Tokens consommés par cet appel (issue #54) — déjà présents dans la
    # réponse normale de l'API, pas d'appel supplémentaire nécessaire. Le
    # modèle réellement utilisé (data["model"]) est repris plutôt que le
    # paramètre "model" d'entrée : celui-ci peut être vide (défaut appliqué
    # côté API) ou un alias, alors que la réponse renvoie l'ID résolu.
    usage_brut = data.get("usage") or {}
    modele_reel = data.get("model") or model or "claude-haiku-4-5"
    usage_appel = {
        "input_tokens": usage_brut.get("input_tokens") or 0,
        "output_tokens": usage_brut.get("output_tokens") or 0,
        "cache_creation_input_tokens": usage_brut.get("cache_creation_input_tokens") or 0,
        "cache_read_input_tokens": usage_brut.get("cache_read_input_tokens") or 0,
    }
    _record_usage(usage_path, modele_reel, usage_appel)
    # La liste "content" peut en théorie contenir un bloc "thinking" avant le
    # bloc "text", même si "thinking" est désormais explicitement désactivé
    # ci-dessus (issue #47) — cette recherche reste une défense en profondeur
    # plutôt qu'une hypothèse sur la position du bloc texte. Supposer que
    # content[0] est le texte provoquait un KeyError('text') (issue #46) : on
    # cherche donc le premier bloc de type "text", quelle que soit sa position.
    for bloc in data["content"]:
        if bloc.get("type") == "text":
            return bloc["text"]
    raise ValueError(f"Aucun bloc de type 'text' dans la réponse Claude : {data.get('content')!r}")


def get_opening_moves(opening_name: str, config):
    """Identifie les 2 à 6 premiers coups caractéristiques d'une ouverture
    nommée par Alain (issue #9), via un appel dédié à Claude — indépendant du
    chat coach multi-tours, pas de mémoire ni de contexte de partie injectés.

    Paramètres :
      opening_name : nom de l'ouverture, tel que saisi par Alain
      config       : dict avec au moins "llm_api_key" et, optionnellement,
                     "llm_model" (même convention que get_coach_response)

    Retourne (liste de coups SAN, erreur) — un seul des deux est non vide/None.
    Erreurs possibles : "nom_vide", "no_api_key", "ouverture_non_reconnue",
    "reponse_invalide", ou le message de l'exception réseau.
    """
    opening_name = (opening_name or "").strip()
    if not opening_name:
        return None, "nom_vide"

    api_key = (config or {}).get("llm_api_key", "")
    if not api_key:
        return None, "no_api_key"

    model = (config or {}).get("llm_model", "")
    usage_path = (config or {}).get("usage_path")

    try:
        raw = _call_claude(_OPENING_SYSTEM_PROMPT, opening_name, api_key, model, usage_path)
    except CreditInsuffisantError as e:
        logger.warning(f"[LLM_COACH] Appel Claude (ouverture) : crédit épuisé : {e}")
        return None, "credit_insuffisant"
    except (urllib.error.URLError, urllib.error.HTTPError, KeyError, ValueError, TimeoutError) as e:
        logger.warning(f"[LLM_COACH] Appel Claude (ouverture) échoué : {e}")
        return None, str(e)

    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()

    try:
        parsed = json.loads(text)
    except (ValueError, TypeError):
        logger.warning(f"[LLM_COACH] Réponse ouverture non-JSON : {raw!r}")
        return None, "reponse_invalide"

    if not isinstance(parsed, dict):
        return None, "reponse_invalide"
    if parsed.get("error"):
        return None, "ouverture_non_reconnue"

    moves = parsed.get("moves")
    if not isinstance(moves, list) or not moves or not all(isinstance(m, str) and m.strip() for m in moves):
        return None, "reponse_invalide"

    return [m.strip() for m in moves[:6]], None


def get_training_program(patterns_erreurs, repertoire_ouvertures, config):
    """Établit un programme d'entraînement de 2 à 3 priorités concrètes
    (issue #14, bouton "Établir mon programme d'entraînement"), via un appel
    dédié à Claude — indépendant du chat coach multi-tours, à partir des
    patterns_erreurs et repertoire_ouvertures de coach_memory.json.

    Paramètres :
      patterns_erreurs      : dict (clé coach_memory.json) — peut être {}
      repertoire_ouvertures : dict (clé coach_memory.json) — peut être {}
      config                : dict avec au moins "llm_api_key" et,
                               optionnellement, "llm_model"

    Retourne (liste de 2 à 3 priorités textuelles, erreur) — un seul des
    deux est non vide/None. Erreurs possibles : "no_api_key",
    "donnees_insuffisantes", "reponse_invalide", ou le message de
    l'exception réseau.
    """
    api_key = (config or {}).get("llm_api_key", "")
    if not api_key:
        return None, "no_api_key"

    if not patterns_erreurs and not repertoire_ouvertures:
        return None, "donnees_insuffisantes"

    model = (config or {}).get("llm_model", "")
    data_text = json.dumps({
        "patterns_erreurs": patterns_erreurs or {},
        "repertoire_ouvertures": repertoire_ouvertures or {},
    }, ensure_ascii=False, indent=2)
    prompt_user = f"Données du joueur (JSON) :\n{data_text}"
    usage_path = (config or {}).get("usage_path")

    try:
        raw = _call_claude(_TRAINING_PROGRAM_SYSTEM_PROMPT, prompt_user, api_key, model, usage_path)
    except CreditInsuffisantError as e:
        logger.warning(f"[LLM_COACH] Appel Claude (programme d'entraînement) : crédit épuisé : {e}")
        return None, "credit_insuffisant"
    except (urllib.error.URLError, urllib.error.HTTPError, KeyError, ValueError, TimeoutError) as e:
        logger.warning(f"[LLM_COACH] Appel Claude (programme d'entraînement) échoué : {e}")
        return None, str(e)

    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()

    try:
        parsed = json.loads(text)
    except (ValueError, TypeError):
        logger.warning(f"[LLM_COACH] Réponse programme d'entraînement non-JSON : {raw!r}")
        return None, "reponse_invalide"

    if not isinstance(parsed, dict):
        return None, "reponse_invalide"

    objectifs = parsed.get("objectifs")
    if not isinstance(objectifs, list) or not objectifs or not all(
        isinstance(o, str) and o.strip() for o in objectifs
    ):
        return None, "reponse_invalide"

    return [o.strip() for o in objectifs[:3]], None


def get_coach_response(messages, context, coach_memory, config):
    """Répond à un tour de conversation multi-tours avec le coach.

    Paramètres :
      messages     : historique complet de la conversation
                     ([{"role": "user"|"assistant", "content": str}, ...])
      context      : dict fen/move/pgn de la position courante, injecté à
                     chaque appel (voir _build_context_text)
      coach_memory : dict chargé via `load_coach_memory` — mémoire de
                     progression du joueur, injectée dans le system prompt
      config       : dict avec au moins "llm_api_key" (clé API Claude) et,
                     optionnellement, "llm_model"

    Retourne (réponse, erreur) — un seul des deux est non vide/non None.
    Pas de cache : conversation libre, contexte changeant à chaque tour.
    """
    api_key = (config or {}).get("llm_api_key", "")
    if not api_key:
        return None, "no_api_key"

    clean_messages = [
        {"role": m.get("role"), "content": (m.get("content") or "").strip()}
        for m in (messages or [])
        if m.get("role") in ("user", "assistant") and (m.get("content") or "").strip()
    ]
    if not clean_messages:
        return None, "empty"

    model = (config or {}).get("llm_model", "")
    prompt_sys = _SYSTEM_PROMPT
    if (context or {}).get("mode_exercice"):
        prompt_sys = f"{prompt_sys}\n\n{_EXERCISE_SYSTEM_ADDENDUM}"
    elif (context or {}).get("verdict_qualite") or (context or {}).get("pv_coup_propose") or (context or {}).get("pv_meilleur_coup"):
        # Mêmes garde-fous qu'en mode "exercice" (issue #26) dès qu'un verdict
        # et/ou une PV Stockfish sont transmis par un autre mode (pédagogique,
        # ouverture hors-livre, finales) — pas de flag mode_exercice requis.
        prompt_sys = f"{prompt_sys}\n\n{_ANTI_INVENTION_ADDENDUM}"
    if (context or {}).get("mode_demonstration"):
        # Indépendant des branches ci-dessus (issue #29) : une démonstration
        # ne transmet ni mode_exercice ni verdict Stockfish, ce garde-fou doit
        # donc pouvoir s'ajouter seul.
        prompt_sys = f"{prompt_sys}\n\n{_DEMONSTRATION_ADDENDUM}"

    memory_text = _build_memory_text(coach_memory)
    if memory_text:
        prompt_sys = f"{prompt_sys}\n\n{memory_text}"

    context_text = _build_context_text(context)
    if context_text:
        prompt_sys = f"{prompt_sys}\n\nContexte de la position en cours :\n{context_text}"

    # Logging étendu à tous les modes (issue #26) — plus seulement l'exercice
    # (issue #18) : mode_origine explicite si fourni par l'appelant, sinon
    # déduit de mode_exercice, sinon "chat_libre" (conversation hors mode
    # d'entraînement actif, ex. revue d'une partie importée).
    mode_origine = (context or {}).get("mode_origine") or (
        "exercice" if (context or {}).get("mode_exercice") else "chat_libre"
    )
    log_path = (config or {}).get("coach_log_path")
    usage_path = (config or {}).get("usage_path")

    # Appel loggé une seule fois, après coup (issue #44) : plus tôt, seule la
    # requête était journalisée (avant même l'appel API) — la réponse réelle
    # du coach n'apparaissait donc jamais dans coach_calls.log, obligeant à
    # se fier à un copier-coller manuel d'Alain pour diagnostiquer une
    # affirmation erronée.
    try:
        response = _call_claude(prompt_sys, clean_messages, api_key, model, usage_path)
    except CreditInsuffisantError as e:
        logger.warning(f"[LLM_COACH] Appel Claude : crédit épuisé : {e}")
        _log_coach_call(log_path, prompt_sys, context, clean_messages, mode_origine, erreur="credit_insuffisant")
        return None, "credit_insuffisant"
    except (urllib.error.URLError, urllib.error.HTTPError, KeyError, ValueError, TimeoutError) as e:
        logger.warning(f"[LLM_COACH] Appel Claude échoué : {e}")
        _log_coach_call(log_path, prompt_sys, context, clean_messages, mode_origine, erreur=str(e))
        return None, str(e)

    response = (response or "").strip()
    # dernier_appel vient d'être écrit par _call_claude (via _record_usage)
    # pour ce même appel : le relire ici évite de faire remonter le tuple
    # d'usage à travers toute la chaîne de retour juste pour le logging
    # (issue #54, champ d'usage ajouté à coach_calls.log).
    usage_appel = (get_usage_summary(usage_path) or {}).get("dernier_appel") if usage_path else None
    _log_coach_call(log_path, prompt_sys, context, clean_messages, mode_origine, reponse=response, usage=usage_appel)
    return response, None
