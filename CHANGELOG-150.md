# Changelog — Issue #150

## Issue #150 — Sécurité : marquer en ligne, avec une raison, les faux positifs déjà jugés (urlopen, subprocess, aléa de jeu)

But : l'outil d'audit sait désormais afficher les suppressions de constats
de sécurité comme « justifiées en ligne » plutôt que de les cacher, à
condition qu'un commentaire en clair explique la raison juste au-dessus de
la ligne, et que la ligne elle-même porte le code de règle exact (`# noqa:
Sxxx  # nosec Bxxx`). Les quatre familles de faux positifs déjà relus
(ouverture d'URL, lancement de processus, aléa de jeu) sont donc marquées
en ligne, sans changement de comportement.

Chaque site a été relu individuellement et confirmé contre le jugement
attendu avant modification (adresse littérale en https, jamais dérivée ;
arguments fixes sans shell ; aléa de jeu seulement, jamais fabrication d'un
secret). Les codes de règle exacts à poser par ligne ont été vérifiés avec
`ruff check --select S310,S311,S603,S607` sur chaque fichier avant
modification, pour éviter de deviner.

**`llm_coach.py`** (4 sites, lignes 2434, 2477, 2598, 2632 après ajout du
commentaire — `urlopen` dans `_call_claude`/`_call_mistral` et leurs
réessais sans température) : commentaire « URL constante en https, jamais
saisie par l'utilisateur » + `# noqa: S310  # nosec B310`. Les quatre
adresses (`https://api.anthropic.com/v1/messages`,
`https://api.mistral.ai/v1/chat/completions`) sont des littéraux en dur
dans le même bloc `urllib.request.Request(...)`, jamais issues d'une
variable de configuration ni d'une entrée utilisateur.

**`engine_stockfish.py`** (ligne 1029, `get_eval_breakdown`) :
`subprocess.run([self._engine_path], ...)` — commentaire « Binaire et
arguments fixes, sans shell, aucune entrée utilisateur » + `# noqa: S603
# nosec B603` (`self._engine_path` vient du constructeur de
`EngineManager`, donc de la configuration applicative, pas d'une requête ;
S607 ne s'applique pas ici car l'argument n'est pas un littéral de chemin
partiel). `ruff --select S603,S607` confirme que seul S603 est signalé sur
cette ligne.

**`version_info.py`** (5 sites, lignes décalées de +1/+2 après ajout des
commentaires — `_get_git_commit_hash`, `_get_git_commit_message`,
`_is_git_repo_modified`, `_find_last_issue_in_commits`) : git lancé via le
PATH avec une liste d'arguments littéraux, sans shell. Trois sites (listes
entièrement littérales) ne portent que `# noqa: S607  # nosec B607`
(« Git lancé via le PATH, arguments fixes, sans shell ») ; le quatrième
(`["git", "log", f"-n{num_commits}", ...]`, argument construit par
f-string à partir du paramètre interne `num_commits`, jamais une entrée
utilisateur) porte en plus `# noqa: S603  # nosec B603` sur la ligne
`subprocess.run(`, avec un second commentaire dédié. Répartition des codes
confirmée par `ruff --select S603,S607` : S607 seul sur les 3 premiers
sites, S603 + S607 sur le quatrième.

**`exercise_history.py`** (ligne 179, `choisir_exercice`),
**`lichess_puzzles.py`** (ligne 291, `tirer_probleme`),
**`preparer_puzzles_lichess.py`** (ligne 216, `preparer`),
**`scripts/fiche_dernier_exercice.py`** (ligne 111, `fabriquer`) : tirage
ou mélange de jeu (choix d'un exercice, pondération de catégorie,
échantillonnage du pool de puzzles, ordre de relecture) — jamais
fabrication d'un secret ou d'un jeton. Commentaire dédié à chaque site +
`# noqa: S311  # nosec B311`.

Aucun site ne s'est révélé non conforme au jugement attendu : les quatre
adresses sont bien des littéraux, tous les arguments de processus sont
fixes et sans shell, tous les usages d'aléa sont du tirage de jeu. Aucune
correction (type vérification `https://` avant ouverture) n'a été
nécessaire : les quatre URLs d'`llm_coach.py` sont déjà des littéraux en
dur, pas des valeurs construites à vérifier.

Aucune autre ligne touchée (notamment aucune suppression RUF100
existante). `ruff check --select S310,S311,S603,S607,RUF100` passe sans
erreur sur les 7 fichiers modifiés une fois les commentaires et codes en
place — confirmant que les codes posés correspondent exactement aux
règles réellement signalées, sans RUF100 résiduel. `python3 -m py_compile`
passe sur les 7 fichiers.

Hors périmètre, non traité ici (conforme à l'issue) : captures d'erreur
silencieuses (`try/except/pass`), toute modification de comportement, de
prompt, de format d'avis ou du vérificateur, `configs/*.conf`, `.env`,
lancement de Stockfish ou de la suite de tests.
