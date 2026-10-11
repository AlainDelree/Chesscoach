# Issue #109 — Signalements : affichage lisible par défaut, texte complet à coller dans un chat sur option

## Problème

`sigcoach` (lire_signalements.py) n'offrait que deux affichages : une liste
tronquée à ~200 caractères (--n, par défaut) et le texte complet prêt à
coller dans un chat (--dernier), qui mélangeait en une seule sortie dense le
commentaire d'Alain, sa question, la réponse du coach, la pastille de
fiabilité, puis une ligne JSON brute de contexte de plusieurs milliers de
caractères, puis la ligne Stockfish. Ses propres notes (ce qu'il voulait
relire en premier) défilaient hors de l'écran, noyées dans le reste.

## Mise en page du résumé (nouvelle commande par défaut)

`python3 lire_signalements.py` (sans option) affiche désormais, pour le
DERNIER signalement, un résumé qui tient sur un écran (~25-30 lignes dans
tous les cas testés, jamais plus de 45 même avec un contexte volumineux),
avec des titres courts séparés par des lignes vides, dans cet ordre :

1. **Ce que tu as noté** — le commentaire libre d'Alain, puis soit "Coup
   concerné" (modes partie/exercice) soit "Question posée par Alain"
   (chat libre, relue dans l'entrée du journal liée par `log_id`) — en
   tête, bien visible.
2. **Réponse du coach** — le texte complet, jamais tronqué.
3. **Fiabilité** — couleur, raison, avertissement d'une première réponse
   corrigée par relance automatique le cas échéant, et liste des contrôles
   déclenchés.
4. **Position** — mode, FEN affichée, FEN de départ de l'exercice si elle
   diffère, camp d'Alain, coup proposé/réel/meilleur coup, verdict
   (qualité + delta en centipawns), et la ligne Stockfish recalculée en
   direct — reformatée en notation standard numérotée (ex. `3... Nf6 4.
   Nc3 Bb4`) avec la mention du camp au trait, au lieu de l'ancienne
   concaténation de SAN sans numéro.
5. Une dernière ligne : la commande exacte pour obtenir le texte complet
   de CE signalement précis.

Aucune ligne JSON brute dans ce résumé.

## Les trois commandes

```
python3 lire_signalements.py                        # résumé du dernier signalement
python3 lire_signalements.py --complet               # texte complet (contexte inclus) du dernier signalement
python3 lire_signalements.py --id ID [--complet]     # un signalement précis (résumé ou texte complet)
```

`--complet` reprend exactement les mêmes titres que le résumé, puis ajoute
deux blocs : **Contexte envoyé au coach** (le contexte allégé des champs
volumineux déjà exclus aujourd'hui — `pgn`/`faits_calcules` — reformaté une
clé par ligne, les valeurs multi-lignes ou volumineuses — listes de pièces,
détails coup par coup — indentées sur les lignes suivantes plutôt
qu'aplaties en JSON), puis **Ligne principale de Stockfish (recalculée)**,
la ligne faisant autorité pour Claude Chat.

`--id ID` fonctionne avec le résumé ou avec `--complet` ; sans `--id`,
c'est toujours le dernier signalement.

`--n` (liste) : affichage par entrée inchangé (identifiants déjà affichés
auparavant via `id=...`, conservés), avec une ligne de rappel ajoutée après
le décompte : `Pour voir un signalement en entier : python3
lire_signalements.py --id ID [--complet]`.

`--dernier` (issue #89) devient un alias rétro-compatible de `--complet`
sur le dernier signalement — même comportement qu'avant cette issue.
`--traiter` est inchangé.

## lire_journal_coach.py (point 4, réutilisation)

Les helpers de mise en forme (`_lignes_cle_valeur`/`_lignes_contexte` pour
le contexte lisible, `_lignes_fiabilite` pour la pastille) ont été écrits
dans lire_journal_coach.py plutôt que dans lire_signalements.py, pour être
réellement partagés (lire_signalements.py importe déjà ce module) — c'est
cette fonction `_lignes_fiabilite` et ces deux helpers de contexte qui sont
réutilisés par lire_signalements.py pour les sections Fiabilité/Contexte.

`_afficher()` (une entrée du journal, utilisée par `--n`/`--mode`/`--mot`/
`--date`/`--coup`/`--log-dir`, toutes options inchangées) a été restructurée
avec les mêmes titres : **Ce que tu as noté** (dernière question), **Réponse
du coach** (première réponse + alertes avant relance le cas échéant, puis
réponse finale ou erreur), **Fiabilité** (nouveau dans cet affichage —
couleur/raison/contrôles, déjà présents dans l'entrée mais jamais montrés
avant cette issue), **Position** (FEN, coup, contexte restant désormais
reformaté une clé par ligne au lieu de la ligne JSON brute).

## Non-régression volontaire : `_lignes_pastille`/`_afficher_resume` (liste --n)

La fonction `_lignes_pastille` de lire_signalements.py (utilisée par
`_afficher_resume`, l'affichage par entrée de la liste `--n`) n'a PAS été
touchée — même texte "Pastille de fiabilité : couleur — raison" qu'avant
cette issue — pour garantir que "conserver l'affichage actuel" (demandé
explicitement par la tâche pour `--n`) soit vérifié à la lettre. La section
Fiabilité du résumé/texte complet utilise une fonction distincte et
nouvelle, `lire_journal_coach._lignes_fiabilite` (wording légèrement
différent : "Couleur :"/"Raison :" sur deux lignes, et l'avertissement
reformulé "première réponse corrigée par relance" au lieu de "avant
relance éventuelle", pour correspondre au vocabulaire demandé par la
tâche).

## Tests effectués

Signalements factices écrits dans un répertoire temporaire (jamais les
fichiers réels d'Alain), `config.SIGNALEMENTS_LOG_PATH`/
`config.COACH_CALLS_LOG_PATH` redirigés par monkeypatch vers ce répertoire
pour la durée des tests, supprimé ensuite :

- Résumé avec question (chat libre) ET résumé avec coup concerné (mode
  exercice/pédagogique) : les deux formats de la ligne "Ce que tu as noté"
  vérifiés.
- Réponse du coach longue (texte répété ~900 caractères) : affichée en
  entier, non tronquée.
- Signalement avec première réponse corrigée par relance (premiere_reponse
  + avertissement) : la ligne "Avertissement (première réponse corrigée
  par relance) : ..." s'affiche bien dans la section Fiabilité.
- Signalement dont l'entrée du journal est introuvable (log_id absent ou
  inconnu) : une seule ligne dans Fiabilité et dans le bloc Contexte de
  `--complet`, pas d'exception.
- `--complet` : contexte affiché une clé par ligne, valeurs multi-lignes
  (listes de pièces, résumé matériel) indentées, `pgn`/`faits_calcules`
  toujours exclus — vérifié visuellement sur signalement factice ET sur un
  vrai signalement de l'environnement (champs réels : pv_coup_propose_detail,
  pieces_clouees_texte, menace_adverse_texte, etc., tous bien formatés).
- `--id` : signalement précis retrouvé (résumé et `--complet`) ; identifiant
  inexistant → message d'erreur + code de sortie 1.
- `--n` : affichage par entrée inchangé, ligne de rappel ajoutée en fin de
  liste.
- Longueur du résumé avec un contexte volumineux (listes de pièces sur 24
  lignes + résumé matériel sur 14 lignes dans le contexte, soit non affiché
  dans le résumé) : 30 lignes au total, bien sous la limite de 45.
- Non-régression `--traiter` (marque bien `traite: true`, persiste sur
  disque, message d'erreur + code 1 si identifiant inconnu) et `--dernier`
  (toujours le texte complet du dernier signalement, comportement
  identique à avant cette issue).
- lire_journal_coach.py : `--log-dir` sur le même répertoire de test,
  nouveaux titres vérifiés visuellement (dernière question, première
  réponse + alertes, fiabilité, contexte reformaté) ; non-régression de
  `--mode`/`--mot`/`--date` (filtres toujours fonctionnels).
- Vrai signalement disponible dans l'environnement
  (~/ChessCoach/data/logs/signalements.log, 9 entrées) : résumé par défaut
  et `--complet --id <id réel>` exécutés en lecture seule (jamais
  `--traiter` contre ce fichier) — fichier vérifié inchangé après coup
  (même nombre de lignes, même empreinte MD5). Stockfish est disponible
  dans cet environnement : la ligne recalculée (numérotée, avec camp au
  trait) a pu être vérifiée sur une position réelle, pas seulement
  simulée.

`python3 -m py_compile lire_signalements.py lire_journal_coach.py` : OK.

## Limites

- La section Position du résumé/texte complet ne montre QUE les champs de
  contexte relus dans l'entrée du journal reliée par `log_id` (coup
  proposé/réel/meilleur coup, verdict, camp, FEN de départ) : si cette
  entrée est introuvable (réponse non journalisée, ou archive déjà
  purgée), ces champs sont simplement absents — seules Mode/FEN
  affichée/Stockfish restent disponibles (déjà le cas avant cette issue
  pour la ligne "Coup concerné"/"Question posée").
- `--complet` calcule la ligne Stockfish une seule fois et la réutilise à
  la fois dans la section Position et dans le bloc final "Ligne principale
  de Stockfish (recalculée)" — intentionnel (un seul lancement du moteur,
  pas de double calcul), mais la ligne apparaît donc deux fois dans la
  sortie, une fois dans le résumé abrégé en tête, une fois explicitement
  en fin de texte prêt à coller.
- Le champ `--n` n'accepte toujours qu'un affichage de LISTE (résumés
  tronqués par entrée) : il ne peut pas être combiné avec `--id` ou
  `--complet` (ignoré si `--id` est fourni, car `--id` prend le dessus).
- La commande `sigcoach` de ~/.bashrc n'a pas été lue ni modifiée (hors
  périmètre du worktree) : elle transmet déjà tous les arguments au script
  (`python3 .../lire_signalements.py "$@"` ou équivalent), donc les
  nouvelles options `--complet`/`--id` lui sont accessibles sans aucun
  changement de sa part — à vérifier par Alain lui-même après revue.
- `.env` non touché. Aucun `git push`.
