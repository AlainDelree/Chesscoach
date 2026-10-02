# Changelog — Issue #91

## Coach : fiabilité 2 — réponse adverse forcée, réponses plus courtes et structurées, vérification des échanges cités

Cas réel ayant motivé cette issue (journal du coach, 2 octobre 2026 15:19,
modèle Sonnet) : exercice FEN `Q7/ppkq3p/2p3n1/2Pp1p2/1P6/2b5/P5PP/4R2K w -
- 9 35`, coup proposé Re3 (gaffe), meilleur coup Re8. Le verdict était juste
et la pastille verte, mais l'explication contenait plusieurs erreurs :
« Re8 force un échange de dames » (faux : gain net de dame contre une
tour), « sans Qxe8 la dame perd la tour gratuitement » (faux : toute autre
réponse perd par mat en 1, menace Qb8 mat — jamais dite au coach), « après
Rxe5 Nxe5 l'échange reste équilibré » (faux : tour contre fou), et une
reprise de phrase au milieu de la réponse (« ton fou... pardon, le fou
adverse » — les Blancs n'ont pourtant aucun fou).

### 1. Réponses adverses alternatives (`engine_stockfish.py`, `game_facts.py`, `app.py`)

- `EngineManager.get_multipv` : nouveau paramètre optionnel `with_pv`
  (+ `pv_max_plies`) — ajoute, par candidat, la ligne complète (`pv`, UCI)
  calculée par le moteur pour CE coup précis, pas seulement son premier
  demi-coup. Désactivé par défaut (`with_pv=False`), aucun changement pour
  les appelants existants (`get_threats`).
- `EngineManager.get_reponses_adverses(board, depth, n, pv_max_plies)`
  (nouveau) : les `n` meilleures réponses du camp au trait sur `board`
  (typiquement la position APRÈS le coup proposé ou le meilleur coup), avec
  la perte d'avantage de chacune par rapport à la meilleure (`perte_cp`,
  même barème mat/cp que `evaluate_move`). Ne décide rien elle-même (faits
  bruts seulement, même séparation que `get_threats`/
  `describe_menace_adverse`).
- `game_facts.SEUIL_REPONSE_FORCEE_CP = 300` (nouveau, réglable en CE SEUL
  endroit) : perte au-delà de laquelle une réponse alternative est jugée
  perdante (en plus d'un mat détecté directement, toujours perdant quel que
  soit ce seuil).
- `game_facts._decrire_menace_evitee` (nouveau) : rejoue la ligne calculée
  pour la MOINS mauvaise réponse perdante, coup par coup, jusqu'au premier
  mat rencontré — décrit alors mécaniquement qui défend la pièce qui mate
  (ex. « dame protégée par la tour e8 »), l'information manquante dans le
  cas réel.
- `game_facts.build_reponse_adverse_obligee_texte(label, fen_apres_coup,
  reponses_data, camp_alain)` (nouveau, API publique) : formate le tout en
  texte de contexte — dit explicitement si la réponse de la ligne
  principale est la SEULE qui évite une perte nette ou un mat (avec la
  menace évitée), ou si plusieurs réponses se valent, ou si le calcul est
  indisponible (position terminale / Stockfish indisponible) — jamais un
  silence.
- `app.py` : `N_REPONSES_ADVERSES = 4` (réglable), `_calculer_reponses_
  adverses(fen_apres_coup)` (mode-agnostique, même pattern que
  `_calculer_menace_adverse`/`_calculer_idees_coup`), câblé dans
  `on_exercise_answer` (source « mes erreurs »/« position précise ») pour
  le coup proposé ET pour le meilleur coup — deux nouveaux champs de
  contexte `reponse_adverse_coup_propose_texte`/
  `reponse_adverse_meilleur_coup_texte`, transmis au coach ET renvoyés au
  client (`exercise_comment`) pour une question de suivi dans le chat
  libre (`static/exercise.js`, `exerciseChatContextExtra`).

**Extrait réel obtenu avec Stockfish 16 sur le cas Re8** (profondeur 18,
4 réponses comparées) :

```
Qxe8 -497  (meilleure)
Bxb4  mat en -1 (pour les Noirs), perte 99502
f4    mat en -1, perte 99502
h6    mat en -1, perte 99502
```

Texte produit : « Réponse adverse après le coup Re8 (issue #91) : Qxe8 est
la SEULE réponse qui évite une perte nette ou un mat — toute autre réponse
perd (mat en 2 demi-coup(s) (Bxb4 Qb8#), la dame protégé(e) par Tour e8).
N'invente AUCUNE autre raison : c'est la vraie raison pour laquelle cette
réponse est forcée. » — correspond exactement à la menace réelle (Qb8 mat,
dame protégée par la tour e8 et la dame a8) citée par l'issue.

Sur Re3 (coup proposé, gaffe) : 4 réponses noires comparables (Be5 369,
Bf6 278/perte 91, Bxb4 195/perte 174, Ne7 88/perte 281) → aucune n'est
« forcée » au sens du seuil, texte : « plusieurs réponses se valent ... la
meilleure selon Stockfish est Be5 » — confirmé sans incohérence avec le
test demandé (Be5 est la meilleure réponse, ET elle n'attaque pas la tour
en e3, vérifié séparément via `game_facts._statut_attaque_case`, mécanisme
déjà existant de l'issue #87 : « Tour blanche en e3 n'est PAS attaqué(e)
par ce coup »).

### 2. Prompt : réponse plus courte, structurée, sans reprise (`llm_coach.py`)

- `_LONGUEUR_MAX_MOTS_REPONSE_EXERCICE = 120` (nouveau, réglable en CE SEUL
  endroit, indicatif — jamais vérifié mécaniquement après coup).
- `_REPONSE_STRUCTUREE_ADDENDUM` (nouveau complément de system prompt,
  ajouté en mode "exercice" juste après `_EXERCISE_SYSTEM_ADDENDUM`) :
  - structure imposée en 4 parties (verdict ; pourquoi, en s'appuyant sur
    la réponse adverse réelle de la ligne principale ; idée du meilleur
    coup en 1-2 phrases, y compris le caractère FORCÉ de la réponse
    adverse quand le bloc "Réponse adverse après..." le précise
    explicitement ; une phrase de conseil) ;
  - interdiction de se reprendre en cours de réponse (« pardon », « en fait
    non », « je me corrige »...) ;
  - interdiction de qualifier un échange (« équilibré », « favorable »,
    « défavorable ») hors des données fournies, et d'appeler « échange »
    une capture qui gagne du matériel net d'après ces mêmes données ;
  - objectifs personnels d'Alain cités au plus une fois.
- `_build_context_text` : lit et injecte les deux nouveaux champs
  `reponse_adverse_coup_propose_texte`/`reponse_adverse_meilleur_coup_texte`
  juste après les blocs `pv_coup_propose`/`pv_meilleur_coup` existants.
- Message de relance automatique (`get_coach_response`) étendu pour
  mentionner aussi l'incohérence d'échange mal qualifié (issue #91) parmi
  les points que la relance doit corriger.

### 3. Vérification des échanges cités (`coach_reliability.py`)

Construite SUR la logique de suites déjà présente (issue #90,
`_extraire_suites`/`_tenter_suite`/`_construire_candidats`), jamais
dupliquée ni contredite — `_extraire_suites` gagne juste deux champs
(`debut`/`fin`, offsets dans le texte) pour localiser le voisinage d'un
qualificatif.

- `coach_reliability.SEUIL_ECHANGE_GRAVE_PTS = 3` (nouveau, réglable en CE
  SEUL endroit) : écart matériel au-delà duquel l'incohérence est jugée
  grave (pastille rouge) plutôt que mineure (orange) — **c'est la première
  famille d'alerte qui n'entraîne pas automatiquement une pastille
  rouge** ; `evaluer_fiabilite` choisit désormais la couleur en fonction du
  champ `gravite` de chaque alerte (absent = rouge, comportement d'avant
  l'issue #91 inchangé pour tous les contrôles existants).
- `detecter_echanges_mal_qualifies(texte, candidats)` (nouveau) : pour
  chaque suite d'AU MOINS DEUX captures citées (suite d'un seul coup non
  concernée), rejoue la suite depuis l'une des positions candidates
  (mêmes candidats que `detecter_suites_illegales`, une suite illégale
  partout/ambiguë/douteuse est simplement ignorée ici — c'est l'autre
  contrôle qui la signale), calcule le résultat matériel réel (différence
  Blancs−Noirs avant/après, barème pion=1/cavalier=3/fou=3/tour=5/dame=9) et
  le compare au qualificatif trouvé à proximité dans le texte :
  - `"équilibré(e)"` : incohérent si le delta réel n'est pas nul ;
  - `"favorable"`/`"défavorable"` : vérifié SEULEMENT si un camp
    (Blancs/Noirs) est explicitement mentionné à moins de 30 caractères du
    qualificatif — sinon trop incertain, rien n'est signalé ;
  - une négation à moins de 20 caractères avant le qualificatif (« pas »,
    « jamais »...) désactive la vérification de cette occurrence (prudence :
    « ce n'est PAS un échange équilibré » affirme l'inverse, une inversion
    de sens par regex serait trop incertaine).
  - **Délibérément PAS vérifié** (prudence explicite, documenté dans le
    docstring du module et ci-dessous) : les verbes "gagne"/"perd" cités en
    exemple par l'issue — trop généraux en français (« gagner la partie »,
    « perdre du temps »...) pour être associés avec confiance à la suite
    citée juste avant, même avec un camp explicite à proximité. Mieux vaut
    ne rien signaler qu'un faux positif.
- `evaluer_fiabilite` appelle ce nouveau contrôle en plus des précédents et
  l'ajoute à la liste `controles` (documentation des limites, pour le
  rapport et pour `lire_signalements.py`).

### Tests effectués

- **Reproduction exacte du cas réel** (FEN de l'issue, vrai Stockfish 16,
  `depth=18`) : confirmé ci-dessus — Qxe8 seul coup qui évite le mat après
  Re8 (menace Qb8 mat décrite avec défenseurs), Be5 meilleure réponse après
  Re3 sans attaquer la tour en e3.
- **Vérification des échanges, textes simulés** (position FEN
  `4k3/8/6n1/4b3/8/4R3/8/4K3 w - - 0 1`, tour e3 / fou e5 défendu par
  cavalier g6) :
  - qualificatif FAUX (« Rxe5 Nxe5, l'échange reste équilibré ») → détecté,
    orange (écart 2 points, sous SEUIL_ECHANGE_GRAVE_PTS) ;
  - qualificatif FAUX avec camp explicite (« échange favorable pour les
    Blancs ») → détecté ;
  - qualificatif CORRECT (« favorable pour les Noirs ») → non détecté,
    vert ;
  - qualificatif AMBIGU (pas de mot-clé de camp, ou qualificatif absent) →
    non détecté, vert ;
  - qualificatif NIÉ (« ce n'est PAS un échange équilibré ») → non détecté
    (prudence sur la négation) ;
  - sur le cas réel Re8/Qxe8 (gain net de 5 points) avec qualificatif
    « équilibré » → détecté, **rouge** (écart ≥ SEUIL_ECHANGE_GRAVE_PTS).
- **Non-régression issue #90** (FEN `r1b1kbnr/pp3ppp/1qn1p3/1Bpp4/3PP3/
  2PQ1P2/PP4PP/RNB1K1NR b KQkq - 4 6`, textes exacts du changelog #90
  dont « Bxc6+ bxc6, un échange équilibré » — bishop contre cavalier,
  réellement équilibré) → toujours vert, aucune fausse alerte introduite
  par le nouveau contrôle.
- **Non-régression exercice h4** (FEN `1r1r2k1/4Qpbp/2Bp1n2/3Pp2q/2P1P1p1/
  2N3PP/PP3PK1/R1B2R2 w - - 0 23`) : `evaluer_fiabilite` sur un texte neutre
  → vert ; `get_reponses_adverses`/`build_reponse_adverse_obligee_texte`
  sur ce FEN (coup h4, vrai Stockfish) → aucune exception, texte cohérent
  (« plusieurs réponses se valent ... la meilleure selon Stockfish est
  Qg6 »).
- **`_build_context_text`** : contexte simulé complet (Re3/Re8, verdict
  blunder, les deux nouveaux champs `reponse_adverse_*`) → texte de
  contexte généré sans erreur, blocs insérés au bon endroit (juste après
  les lignes PV de chaque coup).
- **`app.py` s'importe et démarre le moteur sans erreur** (Stockfish 16
  détecté, Elo limité, WDL, Syzygy, eval breakdown — logs normaux).
- **py_compile** sur les 5 fichiers modifiés (`coach_reliability.py`,
  `engine_stockfish.py`, `game_facts.py`, `app.py`, `llm_coach.py`) et
  `node --check` sur `static/exercise.js` : OK.

### Limites (à documenter dans le rapport de clôture)

- Les réponses adverses alternatives ne sont câblées QUE dans le chemin
  principal du mode "Exercice" (`on_exercise_answer`, sources « mes
  erreurs » et « position précise » — pas la source « Problèmes Lichess »,
  qui n'a qu'un coup de solution unique et pas de comparaison coup
  proposé/meilleur coup de la même façon, ni les autres modes
  pédagogique/ouverture/finales) — portée volontairement limitée au
  périmètre exact du cas réel et du plan de test de l'issue.
- Aucun appel API Claude réel n'a pu être effectué (`ANTHROPIC_API_KEY`
  absente de l'environnement de cette session, pas de fichier `.env` dans
  ce worktree, non modifié conformément à la consigne) : la demande "poser
  la question sous Sonnet et sous Haiku" n'a pas pu être exécutée — vérifié
  à la place le contenu exact des données transmises (ci-dessus) et la
  construction du prompt système, comme demandé en repli par l'issue.
- Vérification des échanges : ne couvre que les suites d'AU MOINS DEUX
  captures et les qualificatifs "équilibré"/"favorable"/"défavorable" (ce
  dernier couple seulement avec camp explicite à proximité) — "gagne"/
  "perd" délibérément exclus (trop ambigus), une suite à un seul coup
  n'est jamais concernée par ce contrôle précis (mais reste couverte par
  les règles de prompt de la tâche 2 et par `detecter_suites_illegales`
  pour sa légalité).
