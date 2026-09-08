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
from pathlib import Path

logger = logging.getLogger("chesscoach.llm_coach")

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
    "Réponds en français."
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
    lines = []
    if camp_alain in ("blancs", "noirs"):
        camp_txt = "Blancs" if camp_alain == "blancs" else "Noirs"
        lines.append(f"Alain (le joueur que tu coaches) joue les {camp_txt} dans cette partie.")
    if fen:
        lines.append(f"Position actuelle (FEN) : {fen}")
    if move:
        lines.append(f"Coup actuel : {move}")
    if coup_propose:
        lines.append(f"Coup proposé par le joueur pour cet exercice : {coup_propose}")
    if coup_reel:
        lines.append(f"Coup réellement joué par le joueur dans la partie d'origine : {coup_reel}")
    if meilleur_coup:
        lines.append(f"Meilleur coup selon Stockfish : {meilleur_coup}")
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
    if pgn:
        lines.append(f"PGN de la partie :\n{pgn}")
    return "\n".join(lines)


def _call_claude(prompt_sys: str, messages, api_key: str, model: str) -> str:
    """messages : liste de {"role": "user"|"assistant", "content": str}, ou une
    simple chaîne (raccourci équivalent à [{"role": "user", "content": messages}])."""
    if isinstance(messages, str):
        messages = [{"role": "user", "content": messages}]
    body = json.dumps({
        "model": model or "claude-haiku-4-5",
        # 300 tokens coupait certaines réponses en plein mot dès que le coach
        # développait un conseil détaillé plutôt qu'un commentaire de coup
        # isolé (issue #12 point 2) — 1024 laisse la marge nécessaire tout en
        # restant loin de dériver vers des réponses interminables.
        "max_tokens": 1024,
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
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["content"][0]["text"]


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

    try:
        raw = _call_claude(_OPENING_SYSTEM_PROMPT, opening_name, api_key, model)
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

    memory_text = _build_memory_text(coach_memory)
    if memory_text:
        prompt_sys = f"{prompt_sys}\n\n{memory_text}"

    context_text = _build_context_text(context)
    if context_text:
        prompt_sys = f"{prompt_sys}\n\nContexte de la position en cours :\n{context_text}"

    try:
        response = _call_claude(prompt_sys, clean_messages, api_key, model)
    except (urllib.error.URLError, urllib.error.HTTPError, KeyError, ValueError, TimeoutError) as e:
        logger.warning(f"[LLM_COACH] Appel Claude échoué : {e}")
        return None, str(e)

    return (response or "").strip(), None
