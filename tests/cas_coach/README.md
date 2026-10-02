# Cas de non-régression du coach (issue #93)

Ce dossier contient des positions où le coach s'est trompé par le passé
(tour inexistante citée, coup qualifié « illégal » à tort, « échange de
dames » pour une dame prise contre une tour, « dame clouée » alors qu'elle
ne l'est pas, « équilibre matériel » annoncé alors qu'un camp est en
avance...). Le script `non_regression_coach.py`, à la racine du projet, les
rejoue pour vérifier qu'une modification du prompt ou des données
n'aggrave pas un cas déjà corrigé.

## Lancer les cas

Depuis la racine du projet :

```bash
# Vérifie seulement les FAITS envoyés au coach (vrai Stockfish, pas d'appel
# API, ne dépense rien) — c'est la commande à lancer systématiquement.
python3 non_regression_coach.py

# Un ou plusieurs cas précis.
python3 non_regression_coach.py --cas re3_dame_contre_tour

# Appelle réellement le coach (Claude) et vérifie aussi sa réponse —
# dépense des tokens. 3 répétitions par cas par défaut (la réponse d'un
# modèle de langage varie d'un appel à l'autre).
python3 non_regression_coach.py --api

# Avec un modèle précis (sinon : le modèle actif de l'application) et plus
# de répétitions.
python3 non_regression_coach.py --api --modele haiku --repetitions 5

# Affiche le détail des réponses fautives.
python3 non_regression_coach.py --api --verbose
```

Le script affiche, avant tout appel API, une estimation du nombre d'appels
(`nombre de cas x --repetitions`). Code de sortie non nul si un fait attendu
est absent, ou si au moins une tentative d'appel API a échoué.

Ce script ne modifie jamais l'historique des erreurs d'Alain, son niveau
adaptatif, ses statistiques, son journal habituel (`coach_calls.log`) ni ses
signalements — il journalise ses propres appels dans un fichier distinct
(`data/logs/non_regression_coach_calls.log`) et ne se connecte jamais à une
instance de l'application en cours d'exécution (il lance sa propre instance
de Stockfish).

## Format d'un fichier de cas (`*.case`)

Un fichier texte par cas, dans ce dossier, avec des lignes `clé: valeur`
pour les champs simples et des blocs `clé:` suivis de lignes indentées pour
les listes. Les lignes commençant par `#` sont des commentaires (ignorées).

```
id: identifiant_court_et_stable
description: une phrase expliquant ce qui a été corrigé
source: mes_erreurs — ou "problème Lichess", ou référence précise
fen: FEN de départ
camp_alain: blancs ou noirs
coup_propose: le coup à tester (SAN, ex. Re3)
meilleur_coup: le meilleur coup attendu (SAN, ex. Re8)

question: question de suivi simulée (issue #96, optionnel) — ex. "et Bxh7+
  ?". Remplace le message initial habituel ("Commente le coup que je
  propose...") par cette question, et enrichit le contexte avec
  "coup_interroge_texte" (légalité/évaluation Stockfish du ou des coups
  détectés dans cette question, sur chaque position pertinente de
  l'exercice — même calcul que app.py on_coach_ask/
  _enrich_context_with_coup_interroge). Sans ce champ, le cas simule le
  message initial comme avant (comportement inchangé).

faits_attendus:
  une ligne par fait — par défaut une sous-chaîne cherchée (insensible à
  la casse et aux accents) dans le texte de contexte RÉELLEMENT envoyé au
  coach (même texte que celui injecté dans son system prompt)

motifs_interdits:
  une ligne par phrase/mot interdit dans la réponse FINALE du coach (--api)
  — après une éventuelle relance automatique de fiabilité, cf. ci-dessous

motifs_interdits_stricts:
  comme motifs_interdits, mais vérifié EN PLUS sur la toute PREMIÈRE réponse
  du coach si une relance automatique a eu lieu (issue #98) — pour les
  motifs jugés trop graves pour tolérer qu'ils aient seulement été corrigés
  après coup (voir « Relance automatique de fiabilité » ci-dessous)

motifs_attendus:
  une ligne par phrase/mot attendu dans la réponse du coach (--api)

pastille_attendue: vert, orange ou rouge
```

### Syntaxe d'une ligne de `motifs_interdits`/`motifs_attendus` (issue #94)

Par défaut, une ligne est une simple sous-chaîne cherchée dans la réponse du
coach (insensible à la casse et aux accents, comme `faits_attendus`). Deux
variantes supplémentaires, dans les deux blocs :

- **Alternatives** : plusieurs formulations séparées par `|`, présent si
  AU MOINS UNE correspond — utile quand le coach paraphrase sans jamais
  employer un mot précis (ex. `défensif|pare la menace|sécurité du roi`
  dans `h4_menace_gxh3_defensif`, le coach explique parfois la défense sans
  jamais écrire « défensif »).
- **Expression régulière** : préfixe `regex: <motif>` — recherché tel quel
  (`re.search`, `re.IGNORECASE`) sur la réponse BRUTE, pas normalisée ;
  l'auteur du motif gère lui-même casse/accents/négation via la syntaxe
  regex. Utile quand la seule proximité textuelle ne suffit pas, ex.
  limiter un motif interdit au voisinage immédiat d'une suite de coups
  précise (voir `regex: qxh4[\s,]*gxh4...équilibr` dans
  `h4_menace_gxh3_defensif`, qui ne doit JAMAIS se déclencher sur le cas
  `c4_bxc6_bxc6_reste_verte`, dont l'« échange équilibré » porte sur
  « Bxc6+ bxc6 », des coups différents).

**Négation proche tolérée pour un motif interdit non-regex** : si le motif
(ou une de ses alternatives) apparaît précédé, à moins de 20 caractères,
d'un mot de négation (« pas », « jamais », « aucun »/« aucune », « ni »,
« non »), cette occurrence n'est PAS comptée comme une présence du motif
interdit — constat ayant motivé cet ajout : la réponse correcte du coach
sur le cas h4 (« un coup défensif, pas une expansion offensive ») contenait
littéralement « expansion », provoquant un échec à tort du motif interdit
`expansion` malgré la négation explicite juste avant. Un motif `regex:...`
garde l'entière responsabilité de la négation (via `(?<!pas )` ou
équivalent) : cette tolérance automatique ne s'applique qu'aux motifs
ordinaires.

**Pastille non conforme** : depuis l'issue #94, l'échec affiche désormais
la couleur réellement obtenue, la raison donnée par
`coach_reliability.evaluer_fiabilite` et les types de contrôles qui ont
déclenché une alerte — à la fois dans le tableau récapitulatif et dans le
détail par tentative, plus besoin de relire l'extrait de réponse pour
comprendre pourquoi la pastille diffère de `pastille_attendue`.

**Relance automatique de fiabilité (issue #98)** : quand la première
réponse du coach a déclenché une alerte de fiabilité et que la relance
automatique (`llm_coach.get_coach_response`) l'a corrigée, la pastille
finale est « orange » (« à prendre avec prudence »), pas « vert » — compter
cela comme un échec de `pastille_attendue: vert` serait trompeur, le
mécanisme a justement fonctionné comme prévu. Un essai dans ce cas est donc
compté comme **réussi**, et affiché à part dans la colonne « Relances » du
tableau récapitulatif (ex. `1/5 relance(s) corrigée(s)`), jamais comme un
échec de pastille. Reste un échec, inchangé : une pastille rouge, ou une
pastille orange SANS relance justifiée (ex. analyse Stockfish
indisponible). Pour exiger qu'un motif particulièrement grave soit absent
même de la toute première réponse (avant correction), utiliser
`motifs_interdits_stricts` plutôt que `motifs_interdits`.

Champs obligatoires : `id`, `fen`, `coup_propose`, `camp_alain`,
`meilleur_coup`. Les autres (`description`, `source`, `faits_attendus`,
`motifs_interdits`, `motifs_interdits_stricts`, `motifs_attendus`,
`pastille_attendue`) sont optionnels mais vivement recommandés — sans eux,
le cas ne vérifie plus grand-chose.

Deux vérifications sont **toujours** faites, même sans `faits_attendus` :
le coup proposé doit être légal sur `fen`, et le meilleur coup recalculé
par le vrai Stockfish doit correspondre à `meilleur_coup` (utile pour
détecter un changement de comportement du moteur installé, pas seulement
une régression du coach).

### Directives reconnues dans `faits_attendus`

Une ligne qui ne commence par aucun des mots-clés ci-dessous est traitée
comme `texte_contient` (toute la ligne est la sous-chaîne cherchée) — c'est
le cas le plus simple, suffisant pour la plupart des cas. Pour un fait
indépendant du libellé exact employé par le code (donc plus robuste aux
reformulations futures), utiliser une directive :

- `texte_contient: <texte>` — sous-chaîne cherchée dans le texte de contexte.
- `camp_sans_tour: blancs|noirs` — ce camp n'a aucune tour sur `fen`.
- `camp_a_une_tour: blancs|noirs` — ce camp a exactement une tour sur `fen`.
- `aucune_piece_clouee: blancs|noirs` — aucune pièce de ce camp n'est
  clouée sur `fen` (calculé avec python-chess, `Board.is_pinned`).
- `menace_significative_contient: <texte>` — le bloc de menace adverse
  mentionne ce texte et contient au moins une menace marquée SIGNIFICATIVE.
- `reponse_simulee_verte: <texte>` — en simulant ce texte comme réponse du
  coach (sans appel API), `coach_reliability.evaluer_fiabilite` ne doit
  déclencher aucune alerte sur CE cas (utile pour les régressions de
  détection, ex. une suite de coups auparavant signalée « illégale » à
  tort, ou un échange mal qualifié).
- `reponse_simulee_signalee: <texte>` — symétrique (issue #97) : en
  simulant ce texte, `coach_reliability.evaluer_fiabilite` DOIT déclencher
  au moins une alerte — sert à vérifier qu'un assouplissement d'un contrôle
  (ex. la tolérance des lectures multiples ajoutée par l'issue #97) n'a
  pas, par la même occasion, affaibli sa capacité à détecter une vraie
  incohérence déjà couverte.

### Comment un fait est vérifié

`non_regression_coach.py` reconstruit, avec les mêmes fonctions que
l'application (`game_facts.py`, `coach_reliability.py`,
`engine_stockfish.py`) et un vrai Stockfish, exactement le contexte que le
mode « Exercice » envoie au coach pour `fen`/`coup_propose`/`camp_alain`
(comme une « Position précise », sans comparaison à un coup réellement
joué). `faits_attendus` est vérifié sur ce contexte ; `motifs_interdits`/
`motifs_attendus`/`pastille_attendue` sont vérifiés sur la réponse réelle du
coach, uniquement avec `--api`.

## Ajouter un cas

### À la main

Dupliquer un fichier `.case` existant, changer `id` (doit être unique dans
ce dossier) et les autres champs, puis lancer `python3
non_regression_coach.py --cas <nouvel_id> --verbose` pour vérifier que le
fichier est bien formé et que les faits attendus sont corrects.

### Depuis un signalement existant

Si le coup, le FEN et la réponse fautive sont déjà enregistrés dans un
signalement (bouton « Signaler » de l'application, voir
`lire_signalements.py`) :

```bash
python3 non_regression_coach.py --depuis-signalement <id_signalement> --nouvel-id <nouvel_id>
```

Crée un squelette (`<nouvel_id>.case`) avec le FEN, le coup et le camp
déjà remplis, et la réponse fautive citée en commentaire au-dessus — il
reste à compléter `description`, `meilleur_coup`, `faits_attendus`,
`motifs_interdits`/`motifs_attendus` (en choisissant les mots fautifs dans
le commentaire) et `pastille_attendue`, puis à supprimer le commentaire.

## Cas fournis au départ

- `re3_dame_contre_tour` — gain de dame contre une tour mal qualifié
  d'« échange », dame non clouée dite « clouée », matériel dit
  « équilibré » alors que les Blancs sont en avance (issue #91).
- `c4_bxc6_bxc6_reste_verte` — non-régression de l'issue #90 : la suite
  « Bxc6+ bxc6 » ne doit plus être signalée comme une suite de coups
  illégale. Étendu par l'issue #99 : « Bxc6+ Qxc6, un échange de cavalier
  contre fou » (le cavalier noir échangé contre le fou blanc, deux types
  différents) ne doit plus être signalé à tort par l'ancienne règle
  symétrique — et les variantes fausses « cavalier contre cavalier »/« fou
  contre fou » (qui prétendent que les DEUX camps perdent le même type)
  doivent rester signalées.
- `h4_menace_gxh3_defensif` — h4 pare une menace réelle sur h3 et ne doit
  pas être présenté comme un plan offensif (issue #80). Étendu par l'issue
  #94 : motif attendu avec alternatives (`défensif|pare la menace|sécurité
  du roi`, le coach ne dit pas toujours « défensif » littéralement) et
  motif interdit par expression régulière limité au voisinage de « Qxh4
  gxh4 » pour l'étiquette « équilibré » (la dame noire perdue contre un
  pion, 8 points, qualifiée à tort d'« échange équilibré » — voir
  `game_facts._resultat_echange_case`). Étendu par l'issue #97 : quatre
  `reponse_simulee_verte`/`reponse_simulee_signalee` qui couvrent « Bxh6
  Qxh6 » (fou contre fou, bilan nul) — équilibré avec « Bh6 » cité juste
  avant la parenthèse (vert), sans « Bh6 » cité du tout (lecture ambiguë,
  toujours vert), qualifié à tort de « favorable aux Blancs » (signalé) et
  non-régression de « Qxh4 gxh4 » qualifié d'« équilibré » (toujours
  signalé).
- `bxh7_coup_interroge` — coup interrogé par Alain dans le chat libre
  pendant un exercice (« et Bxh7+ ? »), jamais proposé par lui-même : le
  coach n'avait aucune donnée sur ce coup et répondait qu'il ne voyait pas
  cette idée, alors que Bxh7+ existe et est mauvais dans la position de
  départ mais devient impossible après le coup proposé g6 (diagonale
  d3-h7 bloquée par le pion, issue #96). Premier cas à utiliser le champ
  `question` ci-dessus. Étendu par l'issue #99 : une réponse citant "Bxh7+"
  dans une phrase, puis la suite "Nxh7 Nxh7 Kxh7" (injouable seule) plus
  loin dans le texte sans parenthèses, ne doit déclencher aucune alerte —
  le coup précédent cité ("Bxh7+") doit être retrouvé et inséré devant la
  suite, même hors parenthèses.

Deux cas supplémentaires, tirés de `parties_test_coach.pgn` (parties sans
erreur connue, pour avoir aussi des cas de référence « tout va bien »),
étaient prévus par l'issue #93 mais n'ont pas pu être créés : ce fichier
n'est pas présent dans ce dépôt (périmètre strict du projet).
