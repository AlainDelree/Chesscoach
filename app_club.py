"""
app_club.py — ChessCoach, entrée dédiée à la page « club » (issue #144)

Second point d'entrée HTTP, sur un port séparé (5001 par défaut), qui ne
sert QUE /club et ses 3 points d'accès (/api/club/avis, /api/club/eval,
/api/club/jugement) — réutilise les fonctions de route de app.py SANS
duplication, mais sur sa PROPRE instance Flask, qui ne connaît aucune
autre route : toute autre URL y reçoit un 404 PAR CONSTRUCTION, jamais par
détection de l'origine de la requête. app.py / le port 5000 restent
strictement inchangés (alias `coach` d'Alain : toujours `python3 app.py`).

Conçu pour être exposé publiquement via Tailscale Funnel (lien ouvert par
un membre du club, sans application à installer), derrière un jeton
secret obligatoire — y compris pour /club elle-même. Deux variables sont
lues dans .env (jamais affichées ni journalisées ici) :

  - CLUB_JETON             : jeton partagé dans le lien. Absente ou vide
    => cette entrée refuse de démarrer (jamais d'accès ouvert par défaut).
    Comparée en temps constant (hmac.compare_digest) à chaque requête ; un
    jeton absent ou faux reçoit exactement le même 404 que n'importe quelle
    route inexistante (abort(404) standard Flask, pas de réponse fabriquée
    à la main qui pourrait différer).
  - CLUB_ANTHROPIC_API_KEY : clé Anthropic DÉDIÉE aux avis du coach depuis
    cette entrée (jamais celle d'app.py/config.LLM_API_KEY). Absente ou
    vide => cette entrée refuse de démarrer, jamais de repli sur la clé
    principale.

Le jeton se transmet dans le lien partagé (`https://.../club?t=<jeton>`,
seul moyen pour un lien cliqué d'atteindre le serveur) et doit ensuite être
repris par la page pour ses appels aux 3 points d'accès SANS que le
visiteur ait à le ressaisir (static/club.html le relit depuis l'URL et le
renvoie dans l'en-tête X-Club-Jeton de chaque appel — jamais à nouveau dans
une URL, pour ne laisser aucune trace de sa valeur dans un journal d'accès
HTTP). Le journal d'accès de Werkzeug (qui journalise la ligne de requête
complète, donc le `?t=...` de la requête initiale) est désactivé plus bas
pour cette seule raison : ne jamais écrire le jeton dans un journal.

Lancement (jamais par CCL) :
    CLUB_JETON=... CLUB_ANTHROPIC_API_KEY=... python3 app_club.py
(ou valeurs exportées depuis .env par le shell, comme pour app.py). Port
modifiable via CLUB_PORT. Ensuite, côté Tailscale (commande lancée par
Alain, jamais par CCL) :
    tailscale funnel 5001
"""

import hmac
import logging
import os
import threading

from flask import Flask, abort, request

import app as app_principale

logger = logging.getLogger("chesscoach.app_club")

# Journal minimal des accès refusés (issue #144, point 5) — un simple
# compteur en mémoire, jamais le jeton fourni ni l'adresse de l'appelant :
# juste de quoi voir, dans les journaux, qu'un lien club a été sondé.
_club_refus_lock = threading.Lock()
_club_refus_compteur = 0


def _compter_et_journaliser_refus() -> None:
    global _club_refus_compteur
    with _club_refus_lock:
        _club_refus_compteur += 1
        total = _club_refus_compteur
    logger.warning(
        "Entrée club : accès refusé (jeton absent ou invalide) — "
        f"{total} refus cumulés depuis le démarrage de ce processus."
    )


def _jeton_fourni() -> str:
    """En-tête X-Club-Jeton (appels /api/club/*, jamais dans une URL donc
    jamais dans un journal d'accès) ou paramètre `t` de l'URL (seul moyen
    pour un lien cliqué d'atteindre /club)."""
    return request.headers.get("X-Club-Jeton", "") or request.args.get("t", "")


def creer_app_club(club_jeton: str | None = None, club_api_key: str | None = None) -> Flask:
    """Construit l'application Flask dédiée au club (issue #144). Lève
    RuntimeError SANS rien construire ni démarrer si CLUB_JETON ou
    CLUB_ANTHROPIC_API_KEY est absente ou vide — jamais d'accès ouvert par
    défaut, jamais de repli sur la clé Anthropic principale.

    `club_jeton`/`club_api_key` permettent aux tests d'injecter des valeurs
    sans dépendre de vraies variables d'environnement ; en production
    (bloc `__main__` ci-dessous), les deux sont lues depuis l'environnement
    (CLUB_JETON/CLUB_ANTHROPIC_API_KEY, exportées depuis .env)."""
    jeton = club_jeton if club_jeton is not None else os.environ.get("CLUB_JETON", "")
    cle_api = club_api_key if club_api_key is not None else os.environ.get("CLUB_ANTHROPIC_API_KEY", "")

    if not jeton:
        raise RuntimeError(
            "CLUB_JETON absente ou vide : l'entrée club refuse de démarrer "
            "(jamais d'accès ouvert par défaut)."
        )
    if not cle_api:
        raise RuntimeError(
            "CLUB_ANTHROPIC_API_KEY absente ou vide : l'entrée club refuse "
            "de démarrer (jamais de repli sur la clé Anthropic principale)."
        )

    # Réassigné sur le module app.py (issue #144) : api_club_avis() le relit
    # à chaque appel via _club_get_llm_api_key() — le port 5000 (app.py lancé
    # seul, _club_llm_api_key resté à None) n'est jamais affecté.
    app_principale._club_llm_api_key = cle_api

    # static_folder=None (issue #144, point 1) : Flask enregistre sinon
    # automatiquement une route "/static/<path:filename>" — strictement par
    # construction, cette application ne doit connaître QUE les quatre
    # routes ajoutées ci-dessous, aucune autre, même une route statique
    # implicite qui pointerait (par coïncidence de chemins) vers le même
    # dossier static/ que app.py.
    club = Flask(__name__, static_folder=None)
    # Explicite plutôt qu'implicite (issue #144, point 4) : pas de
    # rechargeur automatique ni de page d'erreur détaillée visible de
    # l'extérieur, quelle que soit une variable d'environnement ambiante
    # (CHESSCOACH_DEBUG_DEV ne concerne que app.py/le port 5000, jamais lue
    # ici).
    club.config.update(DEBUG=False, TESTING=False)

    # Par construction : AUCUNE autre route que ces quatre n'existe sur
    # cette application — toute autre URL reçoit le 404 standard de Flask
    # (aucune détection de l'origine de la requête nécessaire).
    club.add_url_rule("/club", view_func=app_principale.club_page)
    club.add_url_rule("/api/club/avis", view_func=app_principale.api_club_avis, methods=["POST"])
    club.add_url_rule("/api/club/eval", view_func=app_principale.api_club_eval, methods=["POST"])
    club.add_url_rule("/api/club/jugement", view_func=app_principale.api_club_jugement, methods=["POST"])

    @club.before_request
    def _verifier_jeton():
        if not hmac.compare_digest(_jeton_fourni(), jeton):
            _compter_et_journaliser_refus()
            # abort(404) standard Flask : réponse à l'octet près identique
            # à celle d'une route inexistante — aucune indication que la
            # route existe mais que le jeton est refusé.
            abort(404)

    return club


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Jamais le jeton dans un journal (issue #144, point 2) : le journal
    # d'accès de Werkzeug écrirait la ligne de requête complète (donc le
    # `?t=...` de la requête initiale vers /club) à chaque appel.
    logging.getLogger("werkzeug").setLevel(logging.ERROR)

    try:
        app_club = creer_app_club()
    except RuntimeError as erreur:
        logger.error(str(erreur))
        raise SystemExit(1)

    port = int(os.environ.get("CLUB_PORT", "5001"))
    # host="0.0.0.0" (comme app.py, issue #49) : joignable depuis le réseau
    # Tailscale d'Alain et, via `tailscale funnel`, depuis le lien public
    # partagé au club — le jeton ci-dessus est ici la vraie barrière, cette
    # entrée ne servant par construction que /club et ses 3 points d'accès.
    app_club.run(host="0.0.0.0", port=port, debug=False)
