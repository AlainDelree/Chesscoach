# Changelog — Issue #85

## Journal du coach : couverture de tous les points d'appel, rotation/limite de taille, script de lecture

`llm_coach.py`, `app.py`, `lire_journal_coach.py` (nouveau, racine du dépôt).

### Couverture (part. 1)

Recensement de tous les points d'appel à l'API du coach (9 appels à
`get_coach_response`, plus `get_move_explanations`, `get_opening_moves`,
`get_training_program`) :

- Déjà journalisés avant cette issue : les 9 appels à `get_coach_response`
  (exercice, exercice Lichess, pédagogique, ouverture, finales, chat libre,
  "Demander l'avis du coach", "Expliquer ce coup" en analyse de partie,
  question de suivi `coach_ask`).
- **Non journalisés avant cette issue** (cause du commentaire introuvable
  signalé par Alain) :
  - `get_move_explanations` (étape 1 du module d'explications narratives de
    l'analyse de partie, `on_analyse_choisir_coups_decisifs` — le
    commentaire "coup 6...Nf6, Erreur -117cp, Bb4" vient de ce chemin) ;
  - `get_opening_moves` (identification des coups caractéristiques d'une
    ouverture, `on_opening_start`) ;
  - `get_training_program` (bouton "Établir mon programme d'entraînement",
    `on_training_program_build`).
  Dans les trois cas, `coach_log_path` était déjà transmis dans `llm_config`
  côté `app.py` mais ignoré côté `llm_coach.py` — correction uniquement
  côté `llm_coach.py`.
- `get_move_explanations` journalise désormais **une entrée par coup
  réellement expliqué** (pas une entrée unique pour tout l'appel groupé) :
  `context` porte `fen`/`move`/`coup_plein`/`camp`/`verdict_qualite`/
  `verdict_delta_cp`/`meilleur_coup`, cohérent avec les entrées "fen"/"move"
  déjà utilisées par `on_analyse_expliquer_coup` (analyse de partie à la
  demande) et par l'exercice. Le FEN ("fen_avant") est ajouté par
  `app.py::_prepare_flagged_moves_for_coach` uniquement pour ce logging —
  retiré par `get_move_explanations` avant tout envoi à l'API (jamais
  transmis au coach, coût de tokens inchangé).
- `get_opening_moves`/`get_training_program` journalisent une entrée par
  appel, `mode_origine` dédié (`ouverture_coups` / `programme_entrainement`)
  distinct des `mode_origine` déjà utilisés par le chat coach.
- Format des entrées existantes inchangé (mêmes clés : horodatage,
  mode_origine, model, system_prompt, context, messages, reponse, erreur,
  usage).

### Taille maîtrisée (part. 2)

- Rotation mensuelle dans `_log_coach_call` (`llm_coach.py`) :
  `coach_calls.log` → `coach_calls-AAAA-MM.log`, un fichier par mois. Le
  fichier d'origine (sans suffixe, 184 entrées/4 Mo accumulées depuis
  septembre) n'est plus jamais réécrit — il reste tel quel, comme l'archive
  la plus ancienne, et demeure lisible par le script de lecture.
- Limite de taille totale réglable en un seul endroit :
  `llm_coach._COACH_LOG_MAX_TOTAL_MB` (20 Mo par défaut). Après chaque
  écriture, `_purge_vieux_logs_coach` supprime les archives mensuelles les
  plus anciennes tant que la taille totale (actif + archives) dépasse cette
  limite — jamais le fichier du mois en cours, même s'il la dépasse seul.
- Panne d'écriture (dossier non accessible, disque plein...) : déjà
  entourée d'un `try/except Exception` best-effort avant cette issue (juste
  un `logger.warning` interne) ; la rotation/purge est ajoutée À
  L'INTÉRIEUR de ce même bloc, donc couverte par la même garantie — testé
  avec un dossier en lecture seule (voir Tests).
- Dédoublonnage du system prompt par empreinte (évalué, PAS implémenté) :
  voir section "Limites" ci-dessous.

### Script de lecture (part. 3)

`lire_journal_coach.py` (nouveau, racine du dépôt) : lecture JSON Lines du
fichier actif et de toutes les archives mensuelles, filtres `--mode`
(mode_origine exact), `--mot` (recherche insensible à la casse dans toute
l'entrée), `--date` (préfixe de l'horodatage ISO), `--coup` (numéro de
coup, `context.coup_plein`), `--n` (nombre d'entrées, défaut 10),
`--log-dir` (dossier de test, sinon celui de `config.COACH_CALLS_LOG_PATH`).
Pour chaque entrée : horodatage/mode/modèle, position (FEN), coup (+
numéro), contexte allégé (tous les champs sauf `pgn`/`faits_calcules`,
volumineux et peu utiles à une relecture rapide), dernière question
("user" le plus récent dans `messages`) et réponse/erreur.

Commande (une ligne) :
```
python3 lire_journal_coach.py --n 10 --mode analyse_partie --mot "Bb4" --date 2026-10-02 --coup 6
```
(chaque filtre est optionnel et indépendant ; sans aucun filtre, affiche
les 10 dernières entrées toutes origines confondues).

### Confidentialité (part. 4)

- `data/` est déjà exclu par `.gitignore` (ligne existante, vérifiée — rien
  à modifier) ; `*.log` est également exclu en plus, par précaution
  générale. Le journal (sous `DATA_DIR/logs/`) reste donc hors git.
- Aucune entrée ne contient la clé API : `_call_claude`/`_log_coach_call` ne
  reçoivent et n'écrivent jamais `api_key` — vérifié par test (voir
  ci-dessous).

### Tests

Aucun appel réseau réel (en-tête de l'issue : RESEAU=non) — `llm_coach.
_call_claude` a été remplacé par une fonction factice (monkeypatch) dans un
harnais de test isolé, sous `.test_tmp/` (jamais committé, supprimé après
exécution), avec un `log_path`/`log_dir` pointant dans ce même dossier
temporaire du worktree — jamais vers `~/ChessCoach/data` (hors périmètre de
ce worktree, non touché). `parties_test_coach.pgn`, mentionné par l'issue,
existe sur la machine mais hors du périmètre strict de ce worktree
(`~/Téléchargements/...`) : non utilisé, remplacé par un coup flagué
synthétique représentatif (6...Nf6, -117cp, meilleur coup Bb4 — le cas
exact signalé par Alain).

Scénarios validés :

1. **Analyse de partie** (`get_move_explanations`) : 1 coup flagué simulé →
   1 entrée journalisée, `context.fen`/`move`/`coup_plein`/`camp`/
   `verdict_delta_cp`/`meilleur_coup` corrects, réponse = l'explication
   reçue, `fen_avant` absent du payload réellement envoyé à l'API (vérifié
   sur les arguments reçus par la fonction factice).
2. **Exercice** (`get_coach_response`, mode_origine=exercice) : entrée
   journalisée (comportement déjà correct avant cette issue, non régressé).
3. **Partie libre / question de suivi** (`get_coach_response`,
   mode_origine déduit `chat_libre`) : entrée journalisée.
4. **Partie pédagogique** (`get_coach_response`, mode_origine=pedagogique) :
   entrée journalisée.
5. **`get_opening_moves`** et **`get_training_program`** (nouvellement
   journalisés) : une entrée chacun, mode_origine `ouverture_coups` /
   `programme_entrainement`.
6. Script `lire_journal_coach.py --log-dir .test_tmp/logs` : retrouve
   l'entrée "coup 6...Nf6" par `--mot Bb4`, par `--coup 6`, par `--mode
   analyse_partie`, par `--date` (jour du test) ; `--mode foo_bar`
   (inexistant) affiche "Aucune entrée ne correspond." sans erreur ;
   `--log-dir` inexistant affiche un message clair (code de sortie 1, pas
   de trace Python).
7. **Rotation + limite de taille basse** : `_COACH_LOG_MAX_TOTAL_MB` abaissé
   à 1 Mo en mémoire, 3 fausses archives mensuelles de 512 Ko ajoutées +
   fichier actif → après écriture, les archives les plus anciennes sont
   supprimées, le fichier actif est conservé, taille totale repassée sous
   la limite (543 Ko constatés sur 1024 Ko). Les archives restantes, avec
   du contenu non-JSON (simulation), ne font pas planter la lecture
   (lignes invalides ignorées silencieusement, par le code de lecture déjà
   existant ET par `lire_journal_coach.py`).
8. **Dossier de logs non inscriptible** (`chmod 0500`) : la réponse du coach
   est quand même retournée sans erreur visible pour l'appelant (seul un
   `logger.warning` interne, déjà le comportement avant cette issue).
9. **Clé API absente** : recherche de la clé factice utilisée dans le test
   sur le contenu brut de tous les fichiers de journal écrits — absente.
10. Anciennes entrées lisibles par le script : confirmé (le fichier
    d'origine, jamais réécrit après la rotation, reste inclus dans le motif
    de recherche `coach_calls*.log`).

`py_compile` sur `app.py`, `llm_coach.py`, `lire_journal_coach.py` : OK.

### Limites

- **Dédoublonnage du system prompt par empreinte** (demandé par l'issue
  comme piste à évaluer, pas à implémenter par défaut) : jugé **pas assez
  simple/sans risque** pour l'implémenter dans cette issue. Le system
  prompt varie presque à chaque appel (mémoire du coach + contexte de
  position concaténés dedans), donc peu d'entrées partageraient
  réellement la même empreinte ; implémenter un stockage par référence
  obligerait à maintenir un fichier d'index séparé, à le synchroniser avec
  la rotation/purge (ne jamais supprimer une empreinte encore référencée
  par une entrée vivante), et à adapter le script de lecture — complexité
  et risque (empreinte orpheline après une purge mal synchronisée)
  disproportionnés par rapport au gain, déjà couvert par la rotation
  mensuelle + la limite de taille totale. Non implémenté.
- Test de bout en bout (vrai appel API Claude, vraie partie importée) non
  effectué : RESEAU=non dans l'en-tête de l'issue, et la donnée réelle
  (`~/ChessCoach/data/logs/coach_calls.log`, `parties_test_coach.pgn`) est
  hors du périmètre strict de ce worktree. Les 10 scénarios ci-dessus
  couvrent la logique unitairement (mock de `_call_claude`) mais pas le
  trajet complet SocketIO → navigateur.
- La purge par taille totale compare au nom de fichier (tri chronologique
  par préfixe `AAAA-MM`), pas à la date de dernière modification : fiable
  tant que l'horloge système n'est pas modifiée manuellement entre deux
  mois.
