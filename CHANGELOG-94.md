# Changelog — Issue #94

## Coach : fiabilité 5 — échanges par gain net exact, contrôle des parenthèses, coup isolé, journal de la relance, non-régression plus tolérant

Premier test de non-régression avec de vrais appels API (3 essais, modèle
Sonnet) : Re3 et c4 réussissent 3/3, h4 échoue 3/3. Analyse avec Stockfish
16 réel et python-chess : le coach a qualifié « échange équilibré » une
suite où les Noirs perdent leur dame contre un pion (8 points), parce que
les descriptions mécaniques elles-mêmes employaient l'étiquette floue
« échange favorable ou équilibré » — et parce que le contrôle des échanges
mal qualifiés ignorait les suites citées entre parenthèses. Un coup isolé
légal (« gxh4 » cité sans écrire le « Qxh4 » qui le précède) a aussi
déclenché une relance automatique inutile, dont la première réponse
n'était pas journalisée.

### 1. Étiquettes d'échange précises (`game_facts.py`)

- `SEUIL_ECHANGE_EQUILIBRE_PTS` (0 par défaut, réglable en un seul endroit)
  — solde net d'une capture/reprise immédiate en deçà duquel l'échange
  reste qualifié « équilibré ».
- `_resultat_echange_case` (seule fonction produisant cette étiquette —
  réutilisée par `describe_move_mechanically`/`_attaques_defenses_arrivee`
  pour les captures et le coup proposé/meilleur coup, et par
  `describe_pv_with_balance`/`_statut_attaque_case` pour les lignes
  principales) réécrite : ne dit plus jamais « échange favorable ou
  équilibré », mais « échange équilibré » (solde nul), ou « gain net »/
  « perte nette » de N points pour le camp qui possédait la pièce
  initialement attaquée, précédé d'une courte phrase disant ce qui est pris
  et donné.
- Vérifié avec Stockfish réel et python-chess :
  - Cas h4 (`1r1r2k1/4Qpbp/2Bp1n2/3Pp2q/2P1P1p1/2N3PP/PP3PK1/R1B2R2 w - -
    0 23`, coup h4) : « Qxh4 gxh4, Noirs (adversaire) prennent un pion puis
    perdent la dame en reprise : gain net de 8 point(s) pour Blancs
    (Alain) » — plus jamais « équilibré ».
  - Cas Re8 (`Q7/ppkq3p/2p3n1/2Pp1p2/1P6/2b5/P5PP/4R2K w - - 9 35`, meilleur
    coup Re8) : « Qxe8 Qxe8, Noirs (adversaire) prennent la tour puis
    perdent la dame en reprise : gain net de 4 point(s) pour Blancs
    (Alain) ».
  - Cas sans reprise (variation seule) : désormais chiffré aussi
    (« perte nette de N point(s) pour <camp> »), plus seulement « perdrait
    la dame » sans magnitude.

### 2. Prompt (`llm_coach.py`, `_MATERIEL_ADDENDUM`)

- Nouvelle consigne courte : reprendre le gain net/la perte nette/
  l'équilibre déjà chiffrés par les données plutôt que de les requalifier
  soi-même en « favorable »/« équilibré »/« défavorable ».

### 3. Contrôle des parenthèses (`coach_reliability.detecter_echanges_mal_qualifies`)

- Ne skip plus les suites citées ENTRE PARENTHÈSES (seul
  `si_hypothetique` reste ignoré — même traitement que
  `detecter_echange_type_incoherent` depuis l'issue #92) : une suite de
  concision du type « (Qxh4 gxh4) : échange équilibré » est désormais
  analysée comme une suite normale.
- Vérifié : « si la dame prend en h4, gxh4 reprend (Qxh4 gxh4) : un
  échange équilibré » → alerte **rouge**, écart de 8 points, détectée ;
  « (Qxh4 gxh4) : tu gagnes la dame pour un pion » → aucune alerte (pas de
  qualificatif contredit) ; échange réellement équilibré entre
  parenthèses → aucune alerte ; hypothèse « si Dxd5... » → toujours
  ignorée ; cas c4 (« Bxc6+ bxc6, un échange équilibré », sans
  parenthèses) → toujours aucune alerte (régression vérifiée).

### 4. Coup isolé : demi-coup caché (`coach_reliability.detecter_suites_illegales`)

- Nouvelle fonction `_legal_apres_demi_coup_cache` : pour une suite d'UN
  SEUL coup cité, illégale sur toutes les positions candidates, essaie
  aussi de la jouer après chacun des coups légaux (un seul, caché,
  n'importe lequel) de chaque position candidate. Devient légale → aucune
  alerte (coup plausible, prudence conforme à l'issue #90).
- Vérifié : « si la dame prend en h4, gxh4 reprend » sur le cas h4 →
  aucune alerte (le demi-coup caché « Qxh4 » rend « gxh4 » légal) ; coups
  réellement illégaux cités isolément (« Rxh5 », « Qxa1 » — pièce absente
  de la case, aucune prise possible même avec un demi-coup caché) →
  toujours signalés en rouge.
- Limite assumée (conforme à la philosophie « mieux vaut un faux négatif
  qu'une fausse alerte » déjà documentée dans ce module) : quelques coups
  isolés cités à tort peuvent désormais échapper au contrôle s'ils
  deviennent accidentellement légaux via un demi-coup caché sans rapport
  avec l'intention du coach (observé sur deux coups de test artificiels
  pendant la vérification) — un vrai coup absurde (pièce totalement
  étrangère à la position) reste détecté.

### 5. Journal de la relance (`llm_coach.py`, `lire_journal_coach.py`)

- `_log_coach_call` accepte un nouveau paramètre `premiere_reponse`
  (dict `{"texte": str, "alertes": list}` ou `None`), écrit comme nouveau
  champ `"premiere_reponse"` de l'entrée JSON — ne modifie aucune clé
  existante (aucun impact sur `lire_journal_coach.py` ni sur la fonction
  `coachlog` d'Alain, non lue — hors périmètre strict de ce worktree —
  mais protégée par construction : un lecteur qui ne connaît pas cette
  clé l'ignore simplement).
- `get_coach_response` capture `response`/`fiabilite["alertes"]` dans
  `premiere_reponse` AVANT la relance automatique, qu'elle réussisse ou
  non — jusqu'ici, une relance réussie écrasait silencieusement la
  première réponse, la rendant irrécupérable pour juger un faux positif
  après coup.
- `lire_journal_coach.py` affiche désormais cette première réponse (et
  les alertes qui l'ont déclenchée) quand elle est présente, avant la
  réponse finale.
- Vérifié par un appel simulé (`_call_claude` mocké, pas d'appel API
  réel) reproduisant exactement le cas h4 fautif suivi d'une correction :
  l'entrée du journal contient bien `premiere_reponse.texte` (la réponse
  fautive) et `premiere_reponse.alertes` (l'alerte « échange_mal_qualifie »
  qui a déclenché la relance), en plus de `reponse` (la réponse finale
  corrigée) — `lire_journal_coach.py` affiche les deux.

### 6. Script de non-régression (`non_regression_coach.py`, `tests/cas_coach/`)

- `motifs_interdits`/`motifs_attendus` acceptent désormais des
  alternatives séparées par `|` (présent si au moins une correspond) et un
  préfixe `regex:` (expression régulière Python complète, recherchée sur
  le texte brut).
- `motifs_interdits` (motifs ordinaires, pas `regex:`) tolère une négation
  proche (« pas », « jamais », « aucun(e) », « ni », « non » — fenêtre de
  20 caractères) : une occurrence précédée d'une négation ne compte plus
  comme une présence du motif interdit.
- Échec de pastille (`pastille_attendue`) : affiche désormais la couleur
  réellement obtenue, la raison (`fiabilite["raison"]`) et les types de
  contrôles déclenchés, à la fois dans le tableau récapitulatif et dans le
  détail par tentative.
- Cas `h4_menace_gxh3_defensif` mis à jour : `motifs_attendus` avec
  alternatives (`défensif|pare la menace|sécurité du roi`, le coach ne dit
  pas toujours « défensif » littéralement) ; nouveau `motifs_interdits`
  `regex:` limité au voisinage de « Qxh4 gxh4 » pour l'étiquette
  « équilibré » (sans toucher le cas c4, dont l'« échange équilibré » porte
  sur des coups différents) ; nouveau `faits_attendus` vérifiant la
  présence du texte exact « gain net de 8 point(s) pour Blancs (Alain) »
  dans le contexte réellement envoyé au coach (vérifié avec Stockfish
  réel : la vraie meilleure ligne après h4 est en fait `h4 Qg6 Re1 h6 Kg1
  Nh7`, mais l'étiquette hypothétique de la prise en h4 reste bien décrite
  avec l'exacte magnitude).
- `tests/cas_coach/README.md` mis à jour : syntaxe des alternatives/regex,
  tolérance à la négation, affichage enrichi d'un échec de pastille.
- Vérifié : relance des trois cas (`re3_dame_contre_tour`,
  `c4_bxc6_bxc6_reste_verte`, `h4_menace_gxh3_defensif`) sans `--api` —
  faits exacts avec Stockfish réel, trois cas OK ; test ciblé avec
  `appeler_coach` simulé (sans appel API réel) sur trois réponses
  (correcte avec négation+alternative, fautive avec regex+pastille,
  motif attendu absent) — les trois comportements attendus confirmés.

### Limites

- Appel API réel non effectué dans cette tâche (pas de budget/accord
  explicite donné pour relancer `--api` avec de vrais tokens) : toutes les
  vérifications de contrôle (parenthèses, coup isolé, motifs, pastille,
  journal) ont été faites avec des réponses **simulées** reproduisant
  fidèlement les cas réels décrits dans l'issue, jamais avec un vrai appel
  Claude. Les faits (données Stockfish/python-chess réelles) ont, eux,
  été entièrement vérifiés avec un vrai Stockfish 16.
- `coachlog` (fonction bash d'Alain, `~/.bashrc`) n'a pas été lue ni
  modifiée : hors du périmètre strict de ce worktree. Le nouveau champ
  `premiere_reponse` est additif (aucune clé existante modifiée), donc
  sans impact attendu sur son affichage — à confirmer par Alain.
- Le demi-coup caché du contrôle des coups isolés (point 4) accepte par
  construction quelques faux négatifs supplémentaires (cf. limite déjà
  documentée dans ce module) en échange de la suppression du faux positif
  réel ayant motivé cette issue.
