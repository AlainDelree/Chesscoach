# Changelog — Issue #151

## Issue #151 — Restructurer tout le contexte du projet : CONTEXTE.md sous 4000 caractères et détail sous docs/contexte/

Inventaire préalable (détail complet dans le rapport de clôture) : `CONTEXTE.md`
(12841 caractères, largement au-dessus des 4000 injectés par le watcher),
12 fiches déjà sous `docs/contexte/` (toutes déjà référencées par
l'index de `CONTEXTE.md`, aucune dépendance code sur leur chemin —
seulement des commentaires `cf. docs/contexte/...`), `NOTES_EXPORT.md`
(note de migration AlChess, historique et obsolète, référencée par deux
commentaires dans `engine_stockfish.py`/`llm_coach.py`), deux `README.md`
de sous-dossier (`design/partie_mobile/`, `tests/cas_coach/`, hors
périmètre de cette issue), `.audit.json` (données d'audit sécurité, pas
un fichier de contexte au sens de cette issue). Aucun `CHANGELOG-NNN.md`
présent dans ce worktree (fusionnés et supprimés automatiquement par le
script de fusion externe au dépôt).

**`CONTEXTE.md` réécrit** (3996 caractères, mesurés en caractères) dans
l'ordre imposé : règles de travail (master propre avant fusion,
vérification Stockfish/python-chess avant d'affirmer quoi que ce soit sur
une position, suppressions de sécurité uniquement sur faux positif déjà
jugé avec raison + code précis dans `.audit.json`, absence de suite de
tests unique — chaque `test_*.py` séparément via `python3 -m unittest`),
architecture (objectif, deux entrées Flask `app.py`/`app_club.py`, carte
des fichiers, mémoire du coach, données personnelles), conventions
(rédaction du fichier, convention de signe), puis index des 13 fiches de
`docs/contexte/` avec « quand la lire » pour chacune. Les longs
paragraphes « Invariants et pièges » (convention de signe, classification
des coups, modèle LLM, température, accès distant/Syzygy, mode série,
contexte coach Exercice, page club) sont retirés du noyau : leur contenu
était déjà dupliqué, en plus complet, dans la fiche correspondante.

**Nouvelle fiche `docs/contexte/lignes_calculees.md`** : seul invariant du
noyau qui n'avait encore aucune fiche (limite de 4 coups + prolongation de
2 coups tant que capture pour une ligne calculée — `_couper_pv`,
`engine_stockfish.py` ; calcul réel d'échange avec clouages pour « en
prise » — `game_facts._gain_capture`).

**Correctif sécurité connexe (dépôt public)** : `docs/contexte/syzygy_tailscale.md`
contenait une adresse Tailscale privée en dur (IP + nom de machine du
ThinkPad d'Alain) — remplacée par un renvoi générique à l'admin Tailscale,
sans changement de comportement. La même adresse existe aussi dans le
changelog historique de l'issue #49 (`CHANGELOG.md`) : laissée inchangée,
hors périmètre de cette issue (récit déjà clos, pas un fichier de
contexte vivant) — signalée dans le rapport de clôture pour qu'Alain
décide s'il souhaite la purger de l'historique.

**Vérifications de fraîcheur demandées par l'issue** : aucune trace de
« comparatif »/« tagcomp » trouvée nulle part dans le dépôt (rien à
corriger) ; les routes club (`/club`, `/api/club/avis|eval|jugement`)
n'existent bien que sur `app_club.py`/port 5001 depuis l'issue #149,
confirmé contre `app.py`/`app_club.py` ; `api_club_avis` n'appelle bien
jamais Mistral, confirmé contre `app.py`. Aucune de ces trois informations
n'était fausse dans l'ancien `CONTEXTE.md` — aucune correction de fond
nécessaire au-delà de la restructuration.

**Non déplacé** : `NOTES_EXPORT.md` reste à la racine, listé dans le
rapport pour décision d'Alain (contenu historique/obsolète mais référencé
par deux commentaires de code ; ni déplacé ni supprimé par cette issue,
par prudence face à un fichier ambigu). `.audit.json` et les deux
`README.md` de sous-dossier ne sont pas des fichiers de contexte au sens
de cette issue et n'ont pas été touchés.

Aucun fichier `configs/*.conf` modifié. Aucune valeur sensible ajoutée
(l'unique correction a retiré une adresse privée, pas introduit de
nouvelle).

### Fichiers modifiés
- `CONTEXTE.md` : réécriture complète (12841 → 3996 caractères).
- `docs/contexte/syzygy_tailscale.md` : redaction de l'adresse Tailscale
  privée en dur.
- `docs/contexte/lignes_calculees.md` : nouvelle fiche.

### Tests
Aucun fichier Python modifié — uniquement de la documentation. Pas de
suite de tests concernée.
