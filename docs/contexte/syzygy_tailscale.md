# Tables de finales Syzygy — détail (issue #32)

Chemin exact : `~/ChessCoach/engines/syzygy/` (`SYZYGY_PATH` dans config.py,
créé automatiquement s'il n'existe pas, gitignoré). Alain y dépose
manuellement les fichiers Syzygy 3-4-5 pièces (depuis
https://tablebase.lichess.ovh/tables/standard/, ~1 Go) — pas de
téléchargement automatisé par CCL. engine_stockfish.py détecte leur présence
au démarrage de chaque instance moteur et configure l'option UCI SyzygyPath
en conséquence ; dossier vide ou absent → dégradation gracieuse (log
informatif, pas d'erreur), même pattern que le livre Polyglot (issue #9).

L'historique du correctif qui a mené le moteur du mode "travail de finales"
à tourner en pleine force (avant l'issue #32, il réutilisait par erreur le
moteur Elo limité du mode partie libre) est dans le changelog de l'issue #32
— uniquement l'état actuel (moteur dédié, pleine force) est un invariant
vivant, documenté dans le noyau CONTEXTE.md.

# Accès distant via Tailscale (issue #49)

L'appli écoute sur toutes les interfaces (`0.0.0.0:5000`) mais un middleware
WSGI (`_FiltreAccesDistant` dans app.py) n'accepte que la boucle locale
(127.0.0.1/::1) et le réseau Tailscale (100.64.0.0/10) ; toute autre origine
(LAN, wifi public) reçoit un 403 explicite. Le port 5000 et le mécanisme de
filtrage sont inchangés côté ThinkPad : l'alias `coach` continue d'ouvrir le
navigateur en local comme avant.

Pour ouvrir l'appli depuis le GSM (Tailscale actif des deux côtés) :
`http://100.92.48.81:5000` (adresse Tailscale du ThinkPad thinkpadcarbon7).
Le chat temps réel (Socket.IO) fonctionne aussi par cette adresse : la
vérification d'origine intégrée à Socket.IO compare l'Origin du navigateur
au Host de la requête, donc elle s'aligne automatiquement sur l'adresse
utilisée (locale ou Tailscale) sans configuration supplémentaire.

Mode debug Flask/Werkzeug désactivé par défaut (issue #51) : le débogueur
interactif expose une console web (protégée par un simple code PIN) qui
pourrait être servie avant `_FiltreAccesDistant` et donc potentiellement
joignable depuis le réseau local ou un wifi public. Conséquence pratique :
**après une modification du code, il faut relancer le coach à la main**
(plus de rechargement automatique). Réactivation volontaire pour le
développement local via `CHESSCOACH_DEBUG_DEV=1` — dans ce cas l'appli
n'écoute plus que sur `127.0.0.1` (jamais combiné avec l'écoute
`0.0.0.0`/Tailscale).
