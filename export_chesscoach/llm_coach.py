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
    "durée. Réponds en français."
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
    lines = []
    if fen:
        lines.append(f"Position actuelle (FEN) : {fen}")
    if move:
        lines.append(f"Coup actuel : {move}")
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
        "max_tokens": 300,
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
