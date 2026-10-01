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
from datetime import datetime
from pathlib import Path

import game_facts

logger = logging.getLogger("chesscoach.llm_coach")


class CreditInsuffisantError(Exception):
    """Levée quand l'API Claude répond que le crédit est épuisé (issue #54,
    détection tolérante depuis l'issue #60 : error.type == "billing_error"
    quel que soit le code HTTP, ou HTTP 402, ou HTTP 400
    "invalid_request_error" dont le message évoque le solde/les crédits) —
    distinguée des autres erreurs HTTP pour que l'appelant puisse afficher un
    message clair dans le chat plutôt qu'une erreur technique générique."""
    pass


class ModeleIndisponibleError(Exception):
    """Levée quand l'API Claude refuse l'identifiant de modèle demandé (issue
    #61, erreur HTTP 404 de type "not_found_error" — modèle inconnu, retiré
    ou momentanément indisponible côté Anthropic) — distinguée des autres
    erreurs HTTP pour que l'appelant revienne au choix précédent et affiche
    un message clair dans le chat plutôt qu'une erreur technique générique."""
    pass

_SYSTEM_PROMPT = (
    "Tu es un coach d'échecs personnel. Tu aides un joueur à analyser une "
    "partie qu'il vient de jouer, en te basant sur la position, le coup "
    "courant et le PGN fournis en contexte, ainsi que sur son historique de "
    "progression si disponible. Sois direct et factuel, sans flatterie, "
    "sans émoji. Appuie-toi sur les erreurs récurrentes déjà identifiées "
    "dans son historique pour rendre tes remarques plus utiles dans la "
    "durée. Quand une évaluation Stockfish réelle de la position (score ou "
    "mat forcé annoncé) est fournie en contexte, base ton jugement du coup "
    "d'abord sur cette évaluation réelle, pas seulement sur la comparaison "
    "au meilleur coup : un coup qui mène à un mat forcé contre le joueur "
    "n'est jamais un bon coup, même s'il semble raisonnable à première vue. "
    "Si un programme d'entraînement en cours (objectifs_courants) figure "
    "dans sa mémoire de progression, garde ces priorités à l'esprit et "
    "relie tes réponses à ces objectifs quand c'est pertinent. "
    "Réponds en français."
    "\n\n"
    "Isolation stricte d'une partie à l'autre (issue #64) : l'historique de "
    "conversation qui t'est transmis peut, à l'écran d'Alain, afficher aussi "
    "des échanges sur une partie ou un exercice précédent, séparés par un "
    "trait \"Nouvelle partie\"/\"Nouvel exercice\" — mais seuls les messages "
    "envoyés dans CET appel portent sur la partie actuellement identifiée "
    "ci-dessous. Ne reprends jamais un coup, un numéro de coup ou une "
    "situation qui ne figurent pas explicitement dans le PGN ou le bloc de "
    "faits fournis pour CETTE partie, même s'ils ont été mentionnés dans un "
    "message antérieur de la conversation. Si la question d'Alain évoque un "
    "coup, un événement ou un numéro de coup absent de cette partie-ci, "
    "dis-le clairement plutôt que d'improviser une réponse construite sur "
    "une autre partie."
)

# Complément de system prompt partagé (issue #26), ajouté dès qu'un verdict
# Stockfish et/ou une PV (ligne calculée) figurent dans le contexte — plus
# seulement en mode "exercice" (cf. get_coach_response) : les mêmes classes
# de bugs (verdicts improvisés/contradictoires, inventions tactiques) valent
# pour tout mode qui transmet ces champs au coach (pédagogique/ouverture
# hors-livre/finales), pas seulement l'exercice qui les a fait apparaître en
# premier (issue #17/#20/#25). Texte volontairement neutre sur le vocabulaire
# ("le coup" / "la position en cours", jamais "cette tentative d'exercice")
# pour rester valable quel que soit le mode appelant.
_ANTI_INVENTION_ADDENDUM = (
    "Vérification des affirmations tactiques (issue #20) : quand le "
    "contexte fournit une suite réellement calculée par Stockfish (\"Suite "
    "réellement calculée par Stockfish...\"), c'est ta SEULE base pour "
    "expliquer une menace, une combinaison ou un mat — construis ton "
    "commentaire sur cette ligne précise, pas sur une justification "
    "positionnelle générique improvisée. Si Alain affirme lui-même une "
    "menace, une combinaison ou un mat (annoncé ou évité) sur le coup ou la "
    "position en cours, ne confirme JAMAIS cette affirmation par simple "
    "plausibilité : vérifie-la contre la ou les lignes calculées fournies "
    "dans le contexte. Si elle y est explicitement présente, confirme-la en "
    "t'appuyant sur cette ligne précise. Si elle n'y apparaît pas, ou si "
    "aucune ligne calculée n'a été fournie pour ce coup, dis-le clairement "
    "(par exemple \"je ne suis pas sûr, je ne vois pas cette suite dans mon "
    "analyse\") plutôt que d'acquiescer sans base réelle — une réponse "
    "honnête et prudente est toujours préférable à une confirmation non "
    "fondée, même si l'affirmation d'Alain paraît plausible."
    "\n\n"
    "Interdiction d'inventer une pièce, une case ou une menace (issue #25) : "
    "une ligne calculée par Stockfish (\"Suite réellement calculée...\") ne "
    "te donne QUE la séquence de coups en notation SAN — elle ne te dit PAS "
    "explicitement quelle pièce occupe une case donnée avant qu'un coup ne "
    "l'atteigne ou ne la capture. Un coup comme \"Nxg6\" te dit qu'un "
    "cavalier capture sur g6, mais ne te dit RIEN sur la nature de la pièce "
    "capturée : ne la nomme jamais (\"le cavalier en g6\", \"le fou en g6\"...) "
    "sauf si cette pièce t'a été explicitement donnée par ailleurs dans le "
    "contexte (FEN, ou champs pièce/capture fournis pour coup_propose/"
    "coup_reel/meilleur_coup). En cas de doute réel sur l'identité d'une "
    "pièce, décris uniquement la séquence de coups elle-même (\"la dame va "
    "en h4, puis après Qf3 Nd7, le cavalier prend sur g6\") sans qualifier "
    "la pièce prise. De même, ne fais jamais remonter une menace ou une "
    "capture à un coup plus tôt qu'elle n'apparaît réellement dans la ligne "
    "donnée : si la capture n'a lieu qu'au 3e coup de la suite, ne dis pas "
    "que le 1er coup \"menace\" ou \"crée une attaque directe\" sur la case "
    "en question — décris le plan tel qu'il s'enchaîne réellement, coup "
    "après coup, sans raccourci qui déforme le moment où la menace se "
    "concrétise."
    "\n\n"
    "Vérification des cases mentionnées (issue #44) : avant de nommer "
    "explicitement la case précise où se trouve une pièce (par exemple "
    "\"ta dame est en b5\"), vérifie cette affirmation contre le FEN fourni "
    "dans le contexte, case par case si nécessaire — ne la déduis JAMAIS de "
    "mémoire, par association avec un message précédent de la même "
    "conversation, ou par supposition sur l'endroit où une pièce \"devrait\" "
    "se trouver après tel ou tel coup. Un message que tu as toi-même écrit "
    "plus tôt dans la conversation n'est pas une source fiable pour "
    "localiser une pièce maintenant : la position a pu changer depuis, ou "
    "ce message précédent contenir lui-même une erreur. En cas de doute "
    "réel sur la case exacte d'une pièce, décris la situation sans donner "
    "de case précise plutôt que d'en affirmer une qui n'est pas vérifiée "
    "contre le FEN."
)

# Complément de system prompt pour une position issue d'une démonstration
# Stockfish-contre-Stockfish (issue #29, mode "Travail de finales" — voir
# app.py on_finale_demo_start/on_finale_demo_next) : sans ce garde-fou, un
# chat libre sollicité pendant/après une démonstration (aucun coup joué par
# Alain) a déjà inventé un récit accusant Alain d'avoir mal joué la finale,
# en confondant la position affichée avec une partie qu'il aurait lui-même
# jouée. Ajouté dès que context["mode_demonstration"] est vrai (cf.
# _build_context_text), indépendamment des autres compléments ci-dessous.
_DEMONSTRATION_ADDENDUM = (
    "Mode \"démonstration\" en cours (voir le champ mode_demonstration du "
    "contexte) : la position affichée résulte d'une séquence où Stockfish "
    "joue seul les deux camps, coup après coup, sans aucune intervention "
    "d'Alain. Tu peux expliquer la position elle-même, la technique de mat "
    "ou de finale qu'elle illustre, ou pourquoi tel camp joue tel coup — "
    "mais tu ne dois JAMAIS attribuer une erreur, une faute ou un mauvais "
    "coup à Alain sur cette séquence, ni raconter qu'il aurait \"mal joué\" "
    "ou \"laissé échapper\" quoi que ce soit : il n'a joué aucun des coups "
    "affichés. Tu peux mentionner ses erreurs passées sur ce thème comme "
    "contexte général si sa mémoire de progression en fournit, mais jamais "
    "comme si elles venaient de se reproduire dans cette démonstration."
)

# Complément de system prompt pour une analyse Stockfish indisponible (issue
# #79) : ajouté dès que context["analyse_indisponible"] est vrai (cf.
# _build_context_text, qui écrit alors explicitement dans le contexte
# qu'aucun verdict/évaluation/meilleur coup n'est disponible), indépendamment
# des autres compléments — y compris en mode exercice, où get_coach_response
# refuse normalement l'appel API avant d'en arriver là (cf. plus bas) : ce
# complément reste donc surtout utile aux AUTRES modes (pédagogique,
# ouverture hors-livre, finales, "Demander l'avis du coach"), qui n'ont pas
# ce garde-fou serveur strict et peuvent légitimement continuer la
# conversation sans verdict Stockfish. Constat réel ayant motivé ce
# correctif (cf. rapport de clôture) : contexte sans aucun verdict ni
# évaluation (exercice), le coach a quand même affirmé disposer d'un
# "verdict final", inventé un coup de capture inexistant et contredit la
# réalité (le moteur classait en fait le coup proposé meilleur coup).
_ANALYSE_INDISPONIBLE_ADDENDUM = (
    "Analyse Stockfish indisponible (issue #79) : le contexte indique "
    "explicitement qu'aucun verdict, aucune évaluation et aucun meilleur "
    "coup n'ont pu être calculés pour ce coup ou cette position — panne ou "
    "délai dépassé du moteur, jamais un choix délibéré. N'invente JAMAIS un "
    "verdict (\"bon\", \"gaffe\", \"imprécision\"...), un chiffre "
    "d'évaluation, un meilleur coup ou une ligne de coups pour combler ce "
    "vide, même si Alain insiste, reformule sa question ou affirme "
    "lui-même qu'un coup est bon ou mauvais : dis-lui explicitement que tu "
    "n'as pas le résultat du moteur pour ce coup ou cette position "
    "actuellement, propose de réessayer plus tard, et limite-toi à décrire "
    "ce qui est factuellement donné (listes de pièces, description "
    "mécanique d'un coup, FEN) sans te prononcer sur la qualité d'un coup."
)

# Complément de system prompt spécifique au mode "Exercice" (issue #17),
# ajouté à _SYSTEM_PROMPT quand context["mode_exercice"] est vrai — que ce
# soit pour le commentaire du coup proposé (exercise_answer) ou pour une
# question de suivi posée dans le chat libre pendant l'exercice. Les LLM
# (tous modèles confondus) se sont révélés peu fiables pour juger eux-mêmes
# la qualité d'un coup à partir du seul nom des coups (ex. verdicts
# contradictoires sur un même roque selon le tour de conversation) : ce
# complément leur retire ce rôle de jugement dès qu'un verdict Stockfish est
# fourni dans le contexte (cf. _build_context_text), tout en gardant un ton
# chaleureux et pédagogique — l'ancrage sur Stockfish doit rendre le coach
# plus fiable, pas plus froid. Le garde-fou anti-invention (issue #25/#26)
# lui-même est mutualisé avec les autres modes via _ANTI_INVENTION_ADDENDUM.
_GAME_FACTS_ADDENDUM = (
    "Faits calculés sur cette partie (issue #55) : le contexte contient un "
    "bloc \"Faits calculés mécaniquement\" — coups numérotés avec le camp "
    "exact de chacun (Alain / adversaire), bilan matériel après chaque coup, "
    "moments clés (chaque variation matérielle d'au moins 2 points, avec qui "
    "capture quoi et si une reprise était possible, et la fin de partie — "
    "mat/pat/nulle/abandon — si la partie est terminée) et la position "
    "actuelle pièce par pièce avec les cases exactes. Ce bloc est déjà calculé "
    "mécaniquement (pas par toi) : c'est ta base factuelle sur le "
    "déroulement de cette partie, à utiliser en complément du PGN fourni — "
    "ne reconstitue jamais la partie de mémoire à partir du seul texte du "
    "PGN. N'attribue JAMAIS un coup, une capture ou une pièce au mauvais "
    "camp, et ne cite JAMAIS un coup, une capture, une reprise ou une pièce "
    "qui n'apparaît pas explicitement dans ce bloc ou dans le PGN. En cas de "
    "doute réel, dis que tu n'es pas sûr plutôt que d'improviser. Si Alain "
    "demande ce qui s'est passé dans la partie (\"que s'est-il passé ?\" ou "
    "équivalent), commence ta réponse par les moments clés listés dans ce "
    "bloc."
    "\n\n"
    "Solde net après reprise (issue #57) : pour un moment clé qui indique à "
    "la fois une \"variation matérielle brute\" et un \"solde net\" après une "
    "reprise possible, le solde net EST le résultat réel de l'échange — "
    "n'annonce JAMAIS la variation brute comme perte ou gain final (par "
    "exemple ne dis jamais \"la dame est perdue sans compensation, 9 points "
    "envolés\" si le bloc précise qu'une reprise ramène le solde net à 4 "
    "points) : cite le solde net, en mentionnant si tu veux la variation "
    "brute comme étape intermédiaire de l'échange. Quand le bloc indique au "
    "contraire qu'aucune reprise n'est possible, la variation brute est bien "
    "le résultat final. N'annonce jamais toi-même un chiffre de variation "
    "matérielle (brute ou nette) différent de celui écrit dans ce bloc, "
    "même par arrondi ou approximation."
    "\n\n"
    "Vérification Stockfish ciblée (issue #57, étendue par l'issue #62) : si "
    "le bloc contient une section \"Vérification Stockfish ciblée\", c'est ta "
    "SEULE source pour le meilleur coup Stockfish et la ligne principale sur "
    "les positions concernées — ne propose et ne nomme JAMAIS un \"meilleur "
    "coup\" ou une variante alternative sur une position de la partie si "
    "elle n'apparaît pas explicitement dans cette section (ou ailleurs dans "
    "le bloc/PGN) ; si cette section est absente, ou ne couvre pas le coup "
    "dont Alain te parle (Stockfish indisponible ou trop lent au moment du "
    "calcul), dis clairement que tu ne sais pas ce qui aurait été mieux "
    "plutôt que d'improviser une suite. Ne cite jamais le chiffre brut de "
    "centipawns de \"perte estimée\" (même logique que le mode \"exercice\") : "
    "reformule toujours cette perte en langage naturel (\"cela coûte "
    "beaucoup de matériel\", \"c'est une petite imprécision\"...). Cette "
    "section peut contenir jusqu'à deux sous-parties, chacune explicitement "
    "étiquetée : \"Moment le plus grave\" (la perte nette la plus importante "
    "subie par Alain dans toute la partie, ou un mat — si Alain demande "
    "quel a été LE tournant ou le moment décisif de la partie, désigne "
    "toujours celui-ci, jamais un autre) et \"Premier moment significatif\" "
    "(le premier moment de la partie où il a déjà perdu du terrain, "
    "présenté comme une cause plus précoce mais PAS comme un second "
    "tournant — ne le qualifie jamais de \"vrai tournant\" s'il est distinct "
    "du moment le plus grave ci-dessus, dont la perte est plus importante)."
    "\n\n"
    "Description mécanique de chaque coup cité, et pions perdus sans "
    "reprise (issue #66) : dans la section \"Vérification Stockfish ciblée\", "
    "chaque coup cité (\"Coup joué\", \"Meilleur coup selon Stockfish\", "
    "\"Réponse jouée ensuite dans la partie\", \"Réponse anticipée par la "
    "ligne principale\") est suivi d'une ligne calculée mécaniquement qui "
    "précise déjà quelle pièce joue (type et case de départ), la case "
    "d'arrivée, la pièce capturée le cas échéant (avec sa case, si elle "
    "était défendue et par quoi, et le solde net réel après reprise), "
    "l'échec/mat, et les pièces adverses désormais attaquées — RÈGLE "
    "ABSOLUE : pour toute pièce ou case en lien avec UN de ces coups, ne "
    "reprends QUE ce que cette ligne calculée (ou le reste du bloc, ou le "
    "PGN) dit explicitement. Ne dis JAMAIS toi-même quelle pièce joue un "
    "coup, où se trouve une pièce à ce moment de la partie, ni ce qu'un "
    "coup attaque ou menace, si cette information n'apparaît pas "
    "explicitement dans le bloc — même par déduction ou par ce qui te "
    "semblerait logique. Une capture jamais qualifiée de \"gratuite\" ou "
    "\"sans contrepartie\" si la ligne calculée indique qu'elle était "
    "défendue et reprise (le solde net après reprise est alors le seul "
    "résultat réel, cf. paragraphe \"Solde net après reprise\" ci-dessus). "
    "Si un coup t'intéresse mais que la ligne calculée correspondante est "
    "absente, cite ce coup uniquement en notation abrégée standard (par "
    "exemple \"8...Bxe5\"), sans AUCUN commentaire sur la pièce qui joue, sa "
    "case de départ, ce qu'elle capture ou ce qu'elle attaque. Le bloc "
    "contient aussi, si la partie en a, une section \"Pions perdus sans "
    "reprise\" (jusqu'à 3, les plus récents) : des pertes d'un seul pion, "
    "sans reprise possible, trop mineures pour être des \"moments clés\" "
    "mais réelles — signale-les si Alain demande un bilan complet de la "
    "partie, sans jamais les présenter comme LE tournant."
)

# Complément de system prompt pour l'explication à la demande d'un coup
# flagué du rapport mécanique (issue #56, on_analyse_expliquer_coup/
# get_coach_response, mode_origine == "analyse_partie") — même famille de bug
# que le "chat coach : bloc de faits calculés" (issue #55) et que le module
# d'explications narratives en lot (issue #42, _MOVE_SELECTION_SYSTEM_PROMPT
# ci-dessous) : un coup unique explicité hors de tout bloc de faits calculés
# (pas de PGN complet transmis ici, seulement le FEN avant le coup et son
# camp_alain) reste exposé au même risque d'attribuer un coup adverse à
# Alain ou d'inventer un nom d'ouverture — constat en usage réel sur "10.
# (Noirs) Bf8" présenté comme joué par Alain, et sur une ouverture nommée
# "Française" alors qu'aucun nom d'ouverture n'était fourni en contexte.
_ANALYSE_PARTIE_ADDENDUM = (
    "Explication d'un coup flagué de l'analyse post-partie (issue #56) : le "
    "champ camp_alain du contexte (ou son absence explicite ci-dessus) est "
    "la SEULE source fiable pour savoir quel camp est celui d'Alain — "
    "déduis le camp qui a joué le coup depuis le FEN fourni (trait avant le "
    "coup) et ne l'attribue à Alain que si ce camp correspond exactement à "
    "camp_alain. Si le contexte indique que le camp d'Alain est "
    "indéterminable, ne dis JAMAIS que ce coup est \"le sien\" ou celui de "
    "\"l'adversaire\" : décris-le uniquement par son camp (Blancs/Noirs). Si "
    "le coup est celui de l'adversaire, explique ce qu'il offre ou permet à "
    "Alain plutôt que de le commenter comme si Alain l'avait joué. Ne nomme "
    "une ouverture (par exemple \"Française\", \"Sicilienne\"...) que si son "
    "nom t'est explicitement fourni dans le contexte ; sinon décris la "
    "structure ou l'idée des coups joués sans lui donner de nom inventé."
    "\n\n"
    "Réfutation calculée du coup (issue #62) : quand le contexte fournit une "
    "\"Réfutation calculée mécaniquement de ce coup\" (la réponse réellement "
    "jouée ensuite dans la partie et sa conséquence matérielle), c'est la "
    "VRAIE raison pour laquelle ce coup est flagué — explique-la en premier, "
    "avant toute autre remarque. Ne propose JAMAIS une raison stratégique "
    "différente ou concurrente de cette réfutation calculée (par exemple ne "
    "dis pas \"le roque était préférable pour la sécurité du roi\" comme "
    "raison principale si la réfutation indique qu'une pièce est capturée "
    "sans reprise possible) : tu peux ajouter une remarque stratégique "
    "complémentaire, mais seulement en plus de cette réfutation, jamais à sa "
    "place. Si ce champ est absent, décris l'impact du coup à partir des "
    "autres données fournies (verdict, meilleur coup), sans inventer de "
    "capture ou de menace qui n'y figure pas."
    "\n\n"
    "Ce contexte ne porte que sur UN coup isolé, sans visibilité sur le "
    "reste de la partie : ne le qualifie donc JAMAIS de \"vrai tournant de "
    "la partie\", \"le moment décisif\" ou équivalent — tu ne peux pas savoir "
    "d'ici s'il existe ailleurs dans la partie une perte plus importante "
    "pour Alain. Décris uniquement l'impact de ce coup précis."
    "\n\n"
    "Description mécanique du coup et du meilleur coup (issue #66) : quand "
    "le contexte fournit une \"Description mécanique calculée\" pour ce coup "
    "ou pour le meilleur coup, c'est ta SEULE source pour dire quelle pièce "
    "joue, sa case de départ, la pièce capturée (et si elle était défendue, "
    "avec le solde net réel après reprise), et ce que ce coup attaque "
    "désormais. Ne dis JAMAIS toi-même quelle pièce joue un coup, où se "
    "trouve une pièce, ni ce qu'un coup attaque ou menace si cette "
    "description mécanique est absente ou ne le précise pas — cite alors le "
    "coup uniquement en notation abrégée (par exemple \"8...Bxe5\"), sans "
    "aucun commentaire sur la pièce ou la case. Ne qualifie jamais une "
    "capture de \"gratuite\" si la description indique qu'elle était "
    "défendue et reprise : c'est le solde net après reprise qui est le "
    "résultat réel de l'échange, pas la valeur brute de la pièce prise en "
    "premier."
)

_EXERCISE_SYSTEM_ADDENDUM = (
    "Mode \"exercice\" en cours : Alain s'entraîne sur une position tirée "
    "d'une de ses erreurs passées. Quand un verdict Stockfish est fourni "
    "dans le contexte pour un coup qu'il a proposé, ce verdict FAIT FOI et "
    "est déjà tranché — ton rôle est d'expliquer POURQUOI il est justifié "
    "(menaces, pièces en jeu, plans), jamais de rejuger toi-même la qualité "
    "du coup à partir du seul nom des coups, et jamais de le contredire ou "
    "de le relativiser (\"pas si mauvais\", \"solide quand même\"...) dans un "
    "message ultérieur de la même conversation, même si Alain reste mieux "
    "dans l'absolu après ce coup (issue #73 : un coup peut être une gaffe "
    "qui laisse filer l'essentiel d'un avantage tout en restant, dans "
    "l'absolu, encore légèrement favorable à Alain — dans ce cas dis-le "
    "explicitement, par exemple \"tu restes mieux, mais tu laisses filer "
    "l'essentiel de ton avantage\", sans jamais présenter le coup lui-même "
    "comme bon ou solide). Commence ta réponse en énonçant clairement ce "
    "verdict reformulé (par exemple \"c'est une gaffe\", \"c'est imprécis\"), "
    "avant d'en expliquer les raisons. Ne cite jamais de chiffre brut de "
    "centipawns ni d'étiquette technique (\"delta\", \"blunder\"...) à Alain, "
    "sauf s'il le demande explicitement : reformule toujours ce verdict en "
    "langage naturel, chaleureux et pédagogique. Si Alain pose une question "
    "de suivi sur cet exercice dans le chat libre, réponds directement à "
    "partir du contexte fourni (position de départ, position actuelle, coup "
    "proposé, verdict) sans lui redemander des informations déjà données. "
    "Quand tu cites une ligne de coups (une suite d'au moins deux coups), "
    "écris-la toujours en notation d'échecs standard, coups séparés par des "
    "espaces (exemple : \"Kc3 Ke1 Kd3 Kd1 Ke3 Kc2\") — Alain peut alors la "
    "rejouer automatiquement sur l'échiquier."
    "\n\n"
    "Position de départ vs position actuelle (issue #73) : le contexte "
    "distingue toujours la position de DÉPART de cet exercice (avant tout "
    "coup) de la position ACTUELLEMENT affichée sur l'échiquier, qui peut "
    "déjà refléter le coup proposé ou une exploration libre ultérieure — "
    "ces deux FEN peuvent différer. Pour toute pièce ou case en lien avec un "
    "coup cité (coup proposé, coup réellement joué à l'époque, meilleur "
    "coup), ne reprends QUE ce que sa description mécanique fournie dans le "
    "contexte dit explicitement, calculée sur la position de DÉPART. Ne "
    "conclus JAMAIS qu'une pièce \"n'existe pas\", \"n'est pas là\" ou \"n'est "
    "pas ce que tu crois\" en te basant sur la seule position ACTUELLE : "
    "compare toujours à la position de départ avant d'affirmer qu'une pièce "
    "est absente d'une case."
    "\n\n"
    "Grandes valeurs (issue #75, point 1) : certaines évaluations ou pertes "
    "du contexte (verdict Stockfish, évaluation de la position résultant du "
    "coup proposé) sont volontairement formulées en mots (\"position gagnée "
    "de façon forcée\", \"perte d'une ampleur extrême\"...) plutôt qu'en "
    "centipawns, car leur magnitude dépasse ce qu'un nombre de pions peut "
    "représenter. Quand c'est le cas, n'invente JAMAIS toi-même un chiffre "
    "de centipawns ou un nombre de pions pour la remplacer (pas de \"+199\", "
    "pas d'\"environ 30 pions\"...) : reprends uniquement la formulation en "
    "mots fournie, même si Alain demande explicitement un chiffre précis — "
    "dis-lui alors que l'avantage est trop massif pour être compté en pions, "
    "pas une valeur approximative."
    "\n\n"
    "Bilan matériel d'une ligne principale (issue #75, point 3) : quand le "
    "contexte fournit le détail coup par coup d'une ligne (\"Suite "
    "réellement calculée par Stockfish...\" suivie d'un bloc détaillé avec "
    "un \"solde matériel cumulé pour Alain\" après chaque demi-coup), ce "
    "solde EST le résultat réel de la ligne à ce stade précis — n'annonce "
    "JAMAIS toi-même qu'un camp \"gagne\" ou \"perd\" une pièce sur cette "
    "ligne si le solde cumulé fourni après ce coup ne le confirme pas (par "
    "exemple ne dis jamais \"tu gagnes la dame\" sur un coup suivi d'une "
    "reprise immédiate qui ramène le solde cumulé à 0 : c'est un échange, "
    "pas un gain). Si ce détail coup par coup est absent pour une ligne "
    "citée, décris-la uniquement en notation SAN, sans aucune affirmation "
    "sur le matériel gagné ou perdu."
    "\n\n"
    + _ANTI_INVENTION_ADDENDUM
    + "\n\n"
    + (
        "Listes de pièces et interdiction de citer un FEN (issue #80, point "
        "3) : le contexte ci-dessous donne, pour la position de DÉPART et "
        "pour la position ACTUELLE de cet exercice, la liste des pièces de "
        "chaque camp case par case (\"Liste des pièces...\") — c'est ta "
        "SEULE source, en plus des descriptions mécaniques des coups cités, "
        "pour savoir où se trouve une pièce. Ne recopie et ne cite JAMAIS un "
        "FEN dans ta réponse, même partiellement, même pour l'expliquer à "
        "Alain : un FEN recopié de mémoire a déjà produit une erreur de "
        "transcription qui a fait disparaître un pion du contexte. Ne "
        "déclare JAMAIS qu'un FEN fourni est invalide, mal formé ou contient "
        "un caractère incorrect : si une information te semble incohérente, "
        "dis que tu n'es pas sûr plutôt que de mettre en cause le FEN "
        "lui-même. N'affirme JAMAIS qu'une pièce en protège, défend ou "
        "soutient une autre si ce n'est pas écrit explicitement dans une "
        "description mécanique ou un bloc de menace fourni ci-dessous — ne "
        "déduis jamais toi-même une défense à partir du seul type de pièce "
        "ou de sa case (constat réel : un pion blanc dit à tort \"protégé\" "
        "par un pion qui ne le défendait pas)."
        "\n\n"
        "Menace adverse (issue #80, points 1 et 4) : quand le contexte "
        "fournit un bloc \"Menace(s) de l'adversaire...\" où au moins une "
        "menace est marquée \"SIGNIFICATIVE\", OU quand la description "
        "mécanique d'un coup cité indique qu'une pièce amie \"n'est plus "
        "attaqué(e)\" par rapport à avant ce coup : commence ton explication "
        "par cette menace (ce que l'adversaire aurait joué, et ce que cela "
        "aurait provoqué), puis explique pourquoi le coup la pare, et "
        "seulement ensuite les points secondaires. Ne présente JAMAIS un "
        "coup qui pare une telle menace comme un plan offensif ou une "
        "expansion volontaire (constat réel : h4, qui pare uniquement "
        "...gxh3+ et ...Qxh3+, présenté à tort comme préparant \"une "
        "expansion à l'aile roi\") — un coup défensif ou préventif reste "
        "défensif, même s'il a aussi des mérites secondaires. S'il n'y a "
        "aucune menace marquée \"SIGNIFICATIVE\" et qu'aucune pièce ne perd "
        "son attaque, n'invente AUCUNE menace."
        "\n\n"
        "Idées détectées pour ce coup (issue #80, points 5 et 6) : quand le "
        "contexte fournit un bloc \"Idées détectées pour...\" à la suite "
        "d'un coup cité, commence par énoncer ces idées dans l'ordre fourni "
        "(c'est déjà l'ordre d'importance), puis précise pour chacune "
        "comment elle se réalise concrètement (quelles pièces, quelles "
        "cases, quelles menaces) à partir des descriptions mécaniques et "
        "des listes de pièces fournies ailleurs dans ce contexte. N'ajoute "
        "JAMAIS une idée absente de cette liste, et ne cite JAMAIS de valeur "
        "chiffrée pour les justifier (ces idées sont de simples indications "
        "tirées d'une décomposition interne de l'évaluation du moteur, pas "
        "des vérités absolues — présente-les comme telles, par exemple \"le "
        "moteur indique que...\", jamais comme un fait établi). Si ce bloc "
        "est absent pour un coup cité (décomposition indisponible pour "
        "cette version de Stockfish, ou aucune idée détectée), ne l'invente "
        "jamais : dis que ce coup se justifie surtout par la ligne calculée "
        "ou par la tactique. Quand le coup proposé diffère du meilleur coup "
        "et que les deux ont leurs propres idées détectées, compare-les "
        "explicitement."
    )
)

# Complément au-dessus, spécifique à la source « Problèmes Lichess » du mode
# "exercice" (issue #78, en complément de _EXERCISE_SYSTEM_ADDENDUM, pas un
# remplacement) : contrairement à la source "mes erreurs", il n'y a aucune
# partie d'origine ni coup réellement joué à mentionner, et la réponse doit
# rester courte — un problème Lichess n'appelle pas la même profondeur
# d'explication qu'une erreur personnelle.
_EXERCISE_LICHESS_ADDENDUM = (
    "Cette tentative porte sur un problème tiré de la base ouverte de "
    "problèmes Lichess (licence CC0), pas sur une erreur passée d'Alain : il "
    "n'existe donc AUCUN \"coup réellement joué à l'époque\" ni partie "
    "d'origine à mentionner ou à supposer. Réponds de façon COURTE (2 à 4 "
    "phrases) : dis d'abord si le coup proposé est juste, puis explique "
    "l'idée de la solution en t'appuyant uniquement sur la ligne de "
    "solution et les descriptions mécaniques fournies dans le contexte — "
    "n'invente aucun motif tactique, thème ou menace qui n'en ferait pas "
    "partie."
)

# Complément de system prompt pour les modes de partie avec un historique réel
# (libre, pédagogique, ouverture, finales) et la revue de bibliothèque (issue
# #68) — chat coach en dehors du mode "exercice" (qui garde son propre
# complément ci-dessus, une position isolée sans historique). Ajouté à toute
# réponse hors exercice (get_coach_response), pas seulement quand un verdict
# Stockfish est transmis : contrairement à l'exercice, une ligne alternative
# citée ici peut partir d'une position déjà jouée PLUS TÔT dans la partie
# (ex. "qu'aurais-je dû jouer au coup 8 ?"), pas seulement de la position
# actuelle — Alain ne peut la rejouer sur l'échiquier (issue #68,
# static/game_coach_lines.js) que si le coach introduit ce départ par une
# mention au format fixe ci-dessous, que l'extraction côté client sait
# reconnaître sans avoir à deviner quoi que ce soit.
_GAME_LINES_ADDENDUM = (
    "Quand tu cites une ligne de coups (une suite d'au moins deux coups), "
    "écris-la toujours en notation d'échecs standard, coups séparés par des "
    "espaces (exemple : \"Nxg4 exd6 Qxd6\") — Alain peut alors la rejouer "
    "automatiquement sur l'échiquier. Si cette ligne part de la position "
    "ACTUELLEMENT affichée sur l'échiquier, cite-la telle quelle, sans rien "
    "ajouter avant. Si elle part au contraire d'une position DÉJÀ JOUÉE PLUS "
    "TÔT dans cette partie (par exemple pour répondre à \"qu'aurais-je dû "
    "jouer au coup 8 ?\"), introduis-la TOUJOURS, immédiatement avant les "
    "coups, par une mention au format fixe suivant : \"depuis le coup N... "
    "(Noirs)\" si c'est un coup des Noirs, ou \"depuis le coup N (Blancs)\" "
    "si c'est un coup des Blancs — N étant le numéro de coup PGN standard de "
    "cette partie (exemple complet : \"Ligne depuis le coup 8... (Noirs) : "
    "Nxg4 exd6 Qxd6\"). N'utilise cette mention QUE si le numéro de coup et "
    "le camp sont déjà connus avec certitude d'après la partie transmise "
    "dans ce contexte — ne l'invente jamais, et ne devine jamais un autre "
    "format : c'est cette mention exacte, et elle seule, qui permet à Alain "
    "de retrouver la bonne position de départ."
)

# Appel dédié, distinct du chat coach (issue #14, "Établir mon programme
# d'entraînement") : comme get_opening_moves, une réponse structurée en JSON
# plutôt que de la prose libre, pour pouvoir stocker le résultat de façon
# fiable dans objectifs_courants (coach_memory.json).
_TRAINING_PROGRAM_SYSTEM_PROMPT = (
    "Tu es un coach d'échecs personnel. On te fournit les patterns "
    "d'erreurs récurrentes du joueur (par phase de partie) et son "
    "répertoire d'ouvertures (Blancs et Noirs), au format JSON. À partir de "
    "ces données, établis un programme de travail concret : 2 à 3 "
    "priorités d'entraînement, chacune en une phrase courte et actionnable "
    "(pas de prose ni de longue justification), ciblant les points les "
    "plus impactants pour progresser. Réponds UNIQUEMENT avec un objet "
    "JSON, sans aucun texte ni balise autour, au format exact "
    "{\"objectifs\": [\"...\", \"...\"]} où \"objectifs\" contient 2 à 3 "
    "chaînes de caractères, en français."
)

# Appel dédié, distinct du chat coach (issue #9, mode "travail d'ouverture") :
# un livre Polyglot ne connaît que des positions/coups, pas de noms
# d'ouverture. On demande donc à Claude, une seule fois au démarrage du mode,
# les quelques coups caractéristiques permettant d'atteindre la position de
# départ réelle de l'entraînement, à partir de sa connaissance générale des
# ouvertures standard — ensuite, c'est le livre Polyglot qui prend le relais.
_OPENING_SYSTEM_PROMPT = (
    "Tu es un expert en théorie des ouvertures d'échecs. On te donne le nom "
    "d'une ouverture, éventuellement en français, en anglais, ou avec de "
    "petites fautes de frappe. Réponds UNIQUEMENT avec un objet JSON, sans "
    "aucun texte ni balise autour, au format exact "
    "{\"moves\": [\"e4\", \"e5\", \"Nf3\", ...]} où \"moves\" est la liste "
    "ordonnée des 2 à 6 premiers coups caractéristiques de cette ouverture, "
    "en notation SAN standard, dans l'ordre où ils sont joués (en alternant "
    "Blancs puis Noirs). Si le nom donné ne correspond à aucune ouverture "
    "d'échecs reconnaissable, réponds UNIQUEMENT avec "
    "{\"error\": \"ouverture_non_reconnue\"}."
)


# Appel dédié, distinct du chat coach (issue #42, module d'analyse post-
# partie) : comme get_opening_moves/get_training_program, une réponse
# structurée en JSON plutôt que de la prose libre. Contrairement à un simple
# classement mécanique par delta_cp (issue #41), c'est le coach qui choisit
# lui-même les coups les plus instructifs parmi ceux flagués, avec pour
# consigne explicite de rester ancré sur les données réelles transmises
# (jamais un coup hors de la liste fournie) — même logique de garde-fou
# anti-invention qu'ailleurs (issue #17/#22/#25), adaptée ici à un appel en
# lot plutôt qu'à un coup unique avec PV.
_MOVE_SELECTION_SYSTEM_PROMPT = (
    "Tu es un coach d'échecs personnel. On te fournit un objet JSON décrivant "
    "les coups flagués (imprécision, erreur ou gaffe) d'une partie qu'Alain "
    "vient de jouer, avec deux champs de haut niveau : \"camp_alain\" "
    "(\"blancs\"/\"noirs\", ou null si le camp d'Alain n'a pas pu être "
    "déterminé pour cette partie) et \"coups\" (la liste des coups flagués). "
    "Chaque élément de \"coups\" a : id (identifiant numérique unique de ce "
    "coup dans la liste — à recopier tel quel dans ta réponse, il ne te "
    "renseigne sur rien d'autre), camp (\"blancs\"/\"noirs\"), \"auteur\" "
    "(déjà calculé mécaniquement à partir de camp et camp_alain — vaut par "
    "exemple \"Blancs (Alain)\" ou \"Noirs (adversaire)\" si camp_alain est "
    "connu, ou simplement \"Blancs\"/\"Noirs\" si camp_alain vaut null : "
    "RECOPIE cette information telle quelle, ne déduis ni ne recalcule "
    "JAMAIS toi-même qui a joué un coup à partir du seul champ camp), "
    "coup_plein (numéro du coup plein), san et uci (le coup réellement joué "
    "— ATTENTION, un même uci/san peut réapparaître plusieurs fois dans la "
    "liste, par exemple lors d'échecs répétés par va-et-vient d'une tour : "
    "c'est bien \"id\" qui identifie CE coup précis, jamais uci ni san), "
    "meilleur_coup (le coup recommandé par Stockfish à cette position, ou "
    "null si non disponible), qualite (\"imprecision\"/\"erreur\"/"
    "\"blunder\"), delta_cp (perte en centipawns par rapport au meilleur "
    "coup), phase (\"ouverture\"/\"milieu_de_partie\"/\"finale\") et "
    "reponse_suivante (issue #62, calculée mécaniquement : la réponse "
    "réellement jouée ensuite dans la partie et sa conséquence matérielle "
    "immédiate — capture, perte nette, reprise possible ou non — ou null si "
    "ce coup est le dernier de la partie ou si la réponse suivante n'est pas "
    "une capture), description_mecanique et meilleur_coup_description (issue "
    "#66, calculées mécaniquement : quelle pièce joue ce coup ou le "
    "meilleur coup, sa case de départ, la pièce capturée éventuelle — "
    "défendue ou non, avec le solde net réel après reprise — et ce qui est "
    "désormais attaqué ; null si non calculable). "
    "\n\n"
    "RÈGLE ABSOLUE sur la pièce qui joue et les cases (issue #66) : pour "
    "toute pièce ou case en lien avec un coup, ne reprends QUE ce que "
    "description_mecanique ou meilleur_coup_description dit explicitement "
    "pour ce coup précis. Ne dis JAMAIS toi-même quelle pièce joue un coup, "
    "où se trouve une pièce, ni ce qu'un coup attaque, si le champ "
    "correspondant est null — cite alors ce coup uniquement en notation "
    "abrégée (san), sans aucun commentaire de position. Ne qualifie jamais "
    "une capture de \"gratuite\" si sa description indique qu'elle était "
    "défendue et reprise : le solde net après reprise (donné dans cette "
    "description) est le seul résultat réel de l'échange."
    "\n\n"
    "RÈGLE ABSOLUE sur l'auteur d'un coup (issue #56) : un coup dont "
    "l'auteur ne contient pas \"Alain\" n'est JAMAIS un coup d'Alain — ne "
    "dis jamais \"tu as joué\", \"ton coup\" ou équivalent pour un coup de "
    "l'adversaire. Pour un tel coup, explique plutôt ce que cette erreur ou "
    "ce choix de l'adversaire offre ou permet à Alain (une case, une pièce, "
    "un plan), jamais comme si Alain l'avait joué lui-même. Si camp_alain "
    "vaut null (indéterminable), ne prête AUCUN coup à Alain ni à "
    "\"l'adversaire\" : décris chaque coup uniquement par son camp "
    "(Blancs/Noirs). Ne nomme JAMAIS une ouverture précise (par exemple "
    "\"Française\", \"Sicilienne\"...) à partir des seuls coups fournis : "
    "cette information n'est jamais incluse dans les données ci-dessus, et "
    "une ouverture devinée depuis les premiers coups a déjà été confondue "
    "avec une autre ouverture réelle. Si un coup se situe en phase "
    "\"ouverture\" et que tu veux le resituer, décris la structure ou "
    "l'idée du coup sans lui donner de nom d'ouverture inventé."
    "\n\n"
    "Choisis, PARMI CETTE LISTE UNIQUEMENT, jusqu'à 5 coups que tu juges "
    "réellement décisifs pour l'issue ou l'apprentissage de la partie — pas "
    "nécessairement ceux à la plus grosse perte en centipawns : un coup "
    "moins spectaculaire en chiffre peut être plus instructif (par exemple "
    "un coup passif qui ne participe pas à une attaque en cours, ou un "
    "échange favorable manqué). Pour chaque coup choisi, rédige une "
    "explication courte et concrète en langage naturel, comme un coach "
    "donnerait à l'oral (par exemple \"tu as raté l'occasion d'un échange "
    "favorable\" ou \"ce coup est passif, il ne participe pas à l'assaut du "
    "roque adverse\"), fondée UNIQUEMENT sur les données fournies pour ce "
    "coup précis (auteur, coup joué, meilleur coup, phase, qualité, perte "
    "en centipawns) — n'invente jamais de pièce, case, menace ou "
    "combinaison qui n'en serait pas déductible. Ne cite jamais le chiffre "
    "brut de centipawns ni l'étiquette technique (\"delta\", \"blunder\"...) "
    "dans l'explication : reformule toujours en langage naturel."
    "\n\n"
    "Réfutation calculée (issue #62) : quand reponse_suivante n'est pas null "
    "pour un coup choisi, explique CETTE conséquence calculée EN PREMIER "
    "dans ton explication (c'est la vraie raison, pas une supposition) — ne "
    "propose JAMAIS une raison stratégique différente ou concurrente de "
    "cette réfutation (par exemple ne dis pas \"le roque était préférable "
    "pour la sécurité du roi\" comme raison principale si reponse_suivante "
    "indique qu'une pièce est capturée sans reprise possible) : tu peux "
    "ajouter une remarque stratégique complémentaire, mais seulement en plus "
    "de cette réfutation, jamais à sa place."
    "\n\n"
    "Le \"vrai tournant\" de la partie (issue #62) : n'utilise l'expression "
    "\"le vrai tournant de la partie\", \"le moment décisif\" ou équivalent "
    "que pour le coup de CETTE liste dont la perte (delta_cp, ou la perte "
    "nette indiquée par reponse_suivante si elle est plus parlante) est la "
    "plus importante de tous les coups fournis ci-dessus — jamais pour un "
    "autre coup, même si sa qualite vaut \"blunder\" : pour tout coup dont la "
    "perte est nettement inférieure à celle du pire coup de la liste, décris "
    "son impact sans cette formulation. Réponds "
    "UNIQUEMENT avec un objet JSON, sans aucun texte ni balise autour, au "
    "format exact {\"choix\": [{\"id\": 0, \"explication\": \"...\"}, ...]} "
    "où chaque \"id\" correspond EXACTEMENT à l'un des coups de la liste "
    "fournie (aucun id inventé, aucun autre coup ne doit apparaître), en "
    "français."
)


def get_move_explanations(flagged_moves, camp_alain, config):
    """Sélectionne jusqu'à 5 coups décisifs parmi les coups flagués d'une
    partie et fournit une explication en langage naturel pour chacun (issue
    #42, module d'explications narratives du rapport d'analyse post-partie
    de l'issue #41) — un appel dédié, indépendant du chat coach multi-tours,
    même pattern que get_opening_moves/get_training_program (réponse JSON
    structurée, pas du chat libre).

    Paramètres :
      flagged_moves : liste de dicts, un par coup flagué de la partie
                      ({"id", "uci", "san", "camp", "coup_plein", "delta_cp",
                      "qualite", "phase", "meilleur_coup",
                      "reponse_suivante"}) — construite par l'appelant
                      (app.py) à partir du rapport mécanique de l'issue #41.
                      "id" doit être unique par coup : un même uci/san peut
                      réapparaître plusieurs fois dans une partie (ex. échecs
                      répétés par va-et-vient d'une tour, constaté en
                      vérification réelle), donc l'uci seul ne suffit pas à
                      réassocier sans ambiguïté le choix du coach à son coup
                      d'origine. "reponse_suivante" (issue #62, calculée
                      mécaniquement par game_facts.describe_reponse_suivante)
                      : la réponse réellement jouée ensuite dans la partie et
                      sa conséquence matérielle, ou None. "description_mecanique"/
                      "meilleur_coup_description" (issue #66, calculées par
                      game_facts.describe_move_mechanically) : quelle pièce
                      joue ce coup/le meilleur coup, sa case de départ, la
                      pièce capturée (défendue ou non, solde net après
                      reprise) et ce qui est désormais attaqué, ou None.
      camp_alain    : "blancs"/"noirs", ou "" si indéterminable pour cette
                      partie (issue #56 — ex. mode "partie libre" où les deux
                      camps peuvent être joués par Alain, ou partie importée
                      dont aucun en-tête White/Black ne correspond à Alain).
                      Utilisé ici pour calculer un champ "auteur" par coup
                      (via game_facts.camp_label, réutilisé tel quel plutôt
                      que redupliqué) : sans cette information explicite, le
                      coach n'a aucun moyen de savoir qui est Alain parmi
                      "blancs"/"noirs" et peut attribuer à tort un coup de
                      l'adversaire à Alain (constaté en usage réel, "10.
                      (Noirs) Bf8" présenté comme joué par Alain).
      config        : dict avec au moins "llm_api_key" et, optionnellement,
                      "llm_model" (même convention que get_opening_moves)

    Retourne (liste de {"id", "explication"}, erreur) — un seul des deux
    est non vide/None. La liste retournée est filtrée pour ne contenir QUE
    des id présents dans flagged_moves (garde-fou appliqué ici, pas
    seulement dans le system prompt : jamais d'invention au-delà des coups
    listés, même si le modèle en proposait un autre). Erreurs possibles :
    "no_api_key", "aucun_coup_flague", "reponse_invalide", ou le message de
    l'exception réseau.
    """
    api_key = (config or {}).get("llm_api_key", "")
    if not api_key:
        return None, "no_api_key"

    if not flagged_moves:
        return None, "aucun_coup_flague"

    camp_alain = (camp_alain or "").strip()
    if camp_alain not in ("blancs", "noirs"):
        camp_alain = ""

    model = (config or {}).get("llm_model", "")
    coups_avec_auteur = []
    for m in flagged_moves:
        camp = (m.get("camp") or "").strip()
        auteur = game_facts.camp_label(camp == "blancs", camp_alain) if camp in ("blancs", "noirs") else ""
        coups_avec_auteur.append({**m, "auteur": auteur})
    data_obj = {"camp_alain": camp_alain or None, "coups": coups_avec_auteur}
    data_text = json.dumps(data_obj, ensure_ascii=False, indent=2)
    prompt_user = f"Coups flagués de la partie (JSON) :\n{data_text}"

    usage_path = (config or {}).get("usage_path")
    try:
        raw = _call_claude(_MOVE_SELECTION_SYSTEM_PROMPT, prompt_user, api_key, model, usage_path)
    except CreditInsuffisantError as e:
        logger.warning(f"[LLM_COACH] Appel Claude (sélection de coups décisifs) : crédit épuisé : {e}")
        return None, "credit_insuffisant"
    except ModeleIndisponibleError as e:
        logger.warning(f"[LLM_COACH] Appel Claude (sélection de coups décisifs) : modèle indisponible : {e}")
        return None, "modele_indisponible"
    except (urllib.error.URLError, urllib.error.HTTPError, KeyError, ValueError, TimeoutError) as e:
        logger.warning(f"[LLM_COACH] Appel Claude (sélection de coups décisifs) échoué : {e}")
        return None, str(e)

    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()

    try:
        parsed = json.loads(text)
    except (ValueError, TypeError):
        logger.warning(f"[LLM_COACH] Réponse sélection de coups décisifs non-JSON : {raw!r}")
        return None, "reponse_invalide"

    if not isinstance(parsed, dict):
        return None, "reponse_invalide"

    choix = parsed.get("choix")
    if not isinstance(choix, list):
        return None, "reponse_invalide"

    ids_valides = {m.get("id") for m in flagged_moves if m.get("id") is not None}
    resultat = []
    for c in choix:
        if not isinstance(c, dict):
            continue
        id_ = c.get("id")
        explication = (c.get("explication") or "").strip()
        if id_ in ids_valides and explication:
            resultat.append({"id": id_, "explication": explication})

    if not resultat:
        return None, "reponse_invalide"

    return resultat[:5], None


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


# ── Compteur cumulé de tokens (issue #54) ───────────────────────────────────
# Fichier de données local (usage_tokens.json, sous DATA_DIR — non suivi par
# git comme coach_memory.json et le reste de data/) qui cumule les tokens
# d'entrée/sortie/cache consommés par l'API Claude, par modèle utilisé,
# depuis une date de départ. Volontairement sans aucune notion de prix ni de
# table de coût par modèle (décision explicite d'Alain) : seul le compte de
# tokens bruts est cumulé, à charge pour lui de le rapprocher du solde de la
# Console pour évaluer le coût réel d'une intervention.

_USAGE_CHAMPS = (
    "input_tokens",
    "output_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
)


def _usage_vide() -> dict:
    return {"date_debut": datetime.now().isoformat(), "dernier_appel": None, "par_modele": {}}


def load_usage(path) -> dict:
    """Charge le fichier de compteur de tokens. Retourne une structure vide
    (avec une date de départ fraîche) si le fichier est absent ou illisible —
    même tolérance que load_coach_memory."""
    path = Path(path)
    if not path.exists():
        return _usage_vide()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or "par_modele" not in data:
            return _usage_vide()
        return data
    except Exception as e:
        logger.warning(f"[LLM_COACH] Compteur de tokens illisible ({path}) : {e}")
        return _usage_vide()


def _save_usage(path, usage: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(usage, f, ensure_ascii=False, indent=2)
    tmp_path.replace(path)


def _record_usage(usage_path, model: str, usage_appel: dict) -> None:
    """Cumule les tokens d'un appel réussi dans le fichier de compteur
    (issue #54). Best-effort : une erreur d'écriture ne doit jamais faire
    échouer la réponse du coach, même logique que _log_coach_call."""
    if not usage_path:
        return
    try:
        data = load_usage(usage_path)
        modele = model or "inconnu"
        compteur = data["par_modele"].setdefault(
            modele, {champ: 0 for champ in _USAGE_CHAMPS} | {"appels": 0}
        )
        for champ in _USAGE_CHAMPS:
            compteur[champ] = compteur.get(champ, 0) + int(usage_appel.get(champ) or 0)
        compteur["appels"] = compteur.get("appels", 0) + 1
        data["dernier_appel"] = {
            "model": modele,
            "horodatage": datetime.now().isoformat(),
            **{champ: int(usage_appel.get(champ) or 0) for champ in _USAGE_CHAMPS},
        }
        _save_usage(usage_path, data)
    except Exception as e:
        logger.warning(f"[LLM_COACH] Écriture du compteur de tokens échouée : {e}")


def get_usage_summary(usage_path) -> dict:
    """Retourne la structure affichable côté client : date de départ, dernier
    appel, détail par modèle et totaux tous modèles confondus (calculés à la
    volée, jamais stockés séparément pour éviter toute désynchronisation)."""
    data = load_usage(usage_path)
    totaux = {champ: 0 for champ in _USAGE_CHAMPS}
    for compteur in data.get("par_modele", {}).values():
        for champ in _USAGE_CHAMPS:
            totaux[champ] += compteur.get(champ, 0)
    return {
        "date_debut": data.get("date_debut"),
        "dernier_appel": data.get("dernier_appel"),
        "par_modele": data.get("par_modele", {}),
        "total": totaux,
    }


def reset_usage(usage_path) -> dict:
    """Remet à zéro le compteur de tokens, y compris la date de départ
    (issue #54, bouton de remise à zéro de l'en-tête)."""
    data = _usage_vide()
    _save_usage(usage_path, data)
    return get_usage_summary(usage_path)


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
    # Camp joué par Alain dans cette partie/position (issue #12 point 1) :
    # sans cette information, le coach ne peut que deviner le camp d'après le
    # trait de la FEN, ce qui l'a déjà induit en erreur (ex. exercice où
    # Alain a les Noirs, commentaire parlant à tort de "votre roi blanc").
    camp_alain = (context.get("camp_alain") or "").strip()
    # Camp d'Alain explicitement indéterminable (issue #56) : distinct de
    # l'absence simple de camp_alain (modes qui ne transmettent pas ce champ
    # du tout, ex. exercice sur position isolée) — ici la déduction a été
    # tentée (en-têtes PGN White/Black) et a échoué, ce qui doit être dit
    # explicitement au coach plutôt que de le laisser deviner un camp d'après
    # le seul FEN (cause du bug source : coup adverse attribué à Alain).
    camp_alain_inconnu = bool(context.get("camp_alain_inconnu"))
    # Position de DÉPART de l'exercice en cours (issue #73), distincte de
    # `fen` ci-dessus qui reste la position ACTUELLEMENT affichée (déjà après
    # le coup proposé, ou déplacée par une exploration libre) : sans ce champ
    # séparé et explicitement étiqueté, une question de suivi transmettait
    # SEULEMENT la position actuelle comme si elle était la position de
    # départ, et le coach a déjà nié la présence d'une pièce (un fou) pourtant
    # bien présente avant le coup, faute de pouvoir comparer les deux.
    fen_depart_exercice = (context.get("fen_depart_exercice") or "").strip()
    # Listes des pièces de chaque camp, case par case, pour la position de
    # DÉPART et la position ACTUELLE de l'exercice (issue #80, point 3,
    # calculées par game_facts.describe_pieces_lists) — même présentation
    # que le bloc de faits des modes de partie (build_game_facts_text), pour
    # que le coach n'ait plus jamais à relire un FEN de mémoire : un FEN
    # recopié à la main a déjà produit une erreur de transcription qui a
    # fait disparaître un pion du contexte (cf. _EXERCISE_PIECES_ET_MENACE_
    # ADDENDUM pour l'interdiction de citer un FEN qui accompagne ces listes).
    pieces_depart_texte = (context.get("pieces_depart_texte") or "").strip()
    pieces_actuelles_texte = (context.get("pieces_actuelles_texte") or "").strip()
    # Menace adverse (issue #80, point 1), déjà calculée et décrite
    # mécaniquement par app.py/game_facts (EngineManager.get_threats +
    # describe_menace_adverse) : si Alain passait son tour, les meilleurs
    # coups de l'adversaire, leur évaluation et la perte d'avantage qu'ils
    # provoqueraient — pour que le coach explique un coup défensif comme tel
    # (voir _EXERCISE_PIECES_ET_MENACE_ADDENDUM), au lieu de l'inventer comme
    # un plan offensif (constat réel : h4, qui pare ...gxh3+/...Qxh3+,
    # présenté à tort comme "une expansion à l'aile roi").
    menace_adverse_texte = (context.get("menace_adverse_texte") or "").strip()
    # Idées détectées pour chaque coup cité (issue #80, points 5 et 6),
    # déjà traduites en français et limitées à 3 par coup (game_facts.
    # build_idees_coup/format_idees_coup) — jamais de valeur chiffrée dans
    # ce texte (voir _EXERCISE_PIECES_ET_MENACE_ADDENDUM).
    idees_coup_propose_texte = (context.get("idees_coup_propose_texte") or "").strip()
    idees_coup_reel_texte = (context.get("idees_coup_reel_texte") or "").strip()
    idees_meilleur_coup_texte = (context.get("idees_meilleur_coup_texte") or "").strip()
    # Mode "Exercice" (issue #7) : comparaison coup proposé / coup réellement
    # joué / meilleur coup Stockfish, plutôt qu'un chat libre sur une partie.
    coup_propose  = (context.get("coup_propose") or "").strip()
    coup_reel     = (context.get("coup_reel") or "").strip()
    meilleur_coup = (context.get("meilleur_coup") or "").strip()
    # Description mécanique de chacun de ces trois coups (issue #73, en
    # remplacement des champs piece/capture de l'issue #18) : quelle pièce
    # joue, sa case de départ, la pièce capturée (avec sa case, si elle était
    # défendue et par quoi, et le solde net réel après reprise), l'échec/mat
    # et les pièces désormais attaquées — calculée mécaniquement (game_facts.
    # describe_move_mechanically côté app.py, DEPUIS la position de départ de
    # l'exercice), comme pour le mode "analyse_partie" (issue #66). L'ancienne
    # version (_move_details_fr côté app.py) ne donnait que le type de pièce
    # jouée/capturée, sans défenseur ni solde net — insuffisant pour justifier
    # qu'une capture jugée "blunder" perd réellement du matériel.
    coup_propose_description_mecanique = (
        context.get("coup_propose_description_mecanique") or ""
    ).strip()
    coup_reel_description_mecanique = (
        context.get("coup_reel_description_mecanique") or ""
    ).strip()
    meilleur_coup_description_mecanique = (
        context.get("meilleur_coup_description_mecanique") or ""
    ).strip()
    # Verdict Stockfish chiffré du coup exact proposé (issue #17), calculé via
    # EngineManager.evaluate_move (mêmes seuils que classifier_coup) : donné
    # en contexte pour que le coach explique un jugement déjà tranché plutôt
    # que de rejuger lui-même la qualité du coup à partir des seuls noms de
    # coups — ce chiffre ne doit jamais être répété tel quel à Alain (cf.
    # _EXERCISE_SYSTEM_ADDENDUM).
    verdict_qualite  = (context.get("verdict_qualite") or "").strip()
    verdict_delta_cp = context.get("verdict_delta_cp")
    # Analyse Stockfish indisponible (issue #79) : panne moteur malgré la
    # reprise automatique de EngineManager (ou quota de relances épuisé),
    # distincte d'un contexte qui ne demande simplement aucune évaluation
    # (chat libre général). Transmis explicitement par app.py dès qu'un
    # appel moteur a été tenté et a échoué (cf. _evaluate_move_for_coach/
    # on_coach_comment_on_demand) — jamais déduit ici de la seule absence
    # des champs verdict/eval/meilleur_coup, qui serait aussi le cas normal
    # d'un message sans rapport avec un coup précis.
    analyse_indisponible = bool(context.get("analyse_indisponible")) and not verdict_qualite
    # Réfutation réelle d'un coup flagué (issue #62) : la réponse réellement
    # jouée ensuite dans la partie et sa conséquence matérielle immédiate,
    # calculée mécaniquement par app.py (game_facts.describe_reponse_suivante)
    # — sans ce champ, l'explication d'un coup comme 8.Qf4?? (perd la dame
    # sans reprise) ne mentionnait que des raisons stratégiques génériques
    # ("le roque était préférable"), jamais la vraie raison (8...Nxf4 capture
    # la dame) : le modèle devait la deviner au lieu de la recevoir.
    reponse_suivante = (context.get("reponse_suivante") or "").strip()
    # Description mécanique du coup flagué expliqué (mode "analyse_partie",
    # issue #66) : quelle pièce joue, sa case de départ, la pièce capturée
    # éventuelle (défendue ou non, solde net après reprise) et ce qui est
    # désormais attaqué — calculé mécaniquement (game_facts.
    # describe_move_mechanically côté app.py), même risque et même correctif
    # que le bloc de faits du chat coach (voir _GAME_FACTS_ADDENDUM) pour un
    # coup unique expliqué hors de ce bloc. meilleur_coup_description_mecanique
    # est déclaré plus haut, partagé avec le mode "exercice" (issue #73).
    coup_description_mecanique = (context.get("coup_description_mecanique") or "").strip()
    # Ligne (PV) réellement calculée par Stockfish pour le coup proposé et
    # pour le meilleur coup (issue #20), en SAN, depuis la même analyse à
    # depth=18 que verdict_qualite/meilleur_coup ci-dessus (cf. app.py,
    # on_exercise_answer) : le seul ancrage disponible au coach pour
    # justifier une continuation tactique réellement calculée, ou pour juger
    # si une affirmation de menace/mat d'Alain est cohérente avec ce que
    # Stockfish a effectivement vu — jamais une preuve de mat forcé au-delà
    # de ce qu'elle montre explicitement.
    pv_coup_propose  = (context.get("pv_coup_propose") or "").strip()
    pv_meilleur_coup = (context.get("pv_meilleur_coup") or "").strip()
    # Détail mécanique coup par coup de ces deux lignes, avec le solde
    # matériel CUMULÉ pour Alain après chaque demi-coup (issue #75, point 3,
    # cf. app.py/game_facts.describe_pv_with_balance+format_pv_with_balance)
    # — déjà formaté en texte prêt à l'emploi. Sans ce détail, le coach
    # racontait le bilan matériel d'une ligne de mémoire et s'est déjà trompé
    # sur un simple échange (ex. "tu as gagné la dame contre rien" sur
    # Qh8+ Ke7 Qxd8+ Kxd8, qui échange les deux dames, solde net 0).
    pv_coup_propose_detail  = (context.get("pv_coup_propose_detail") or "").strip()
    pv_meilleur_coup_detail = (context.get("pv_meilleur_coup_detail") or "").strip()
    # Vrai juste après un "Reprendre mon coup" tant qu'Alain n'a pas encore
    # reproposé de coup (issue #17) : évite qu'un verdict/coup discuté plus
    # tôt dans la même conversation du chat libre soit pris pour l'état réel
    # de la tentative en cours, désormais annulée.
    reprise_recente = bool(context.get("reprise_recente"))
    # Évaluation Stockfish réelle de la position résultant du coup proposé
    # (issue #12 point 3), en complément de la seule comparaison à
    # meilleur_coup. Transmise du point de vue d'Alain (issue #73, positif =
    # avantage pour Alain, négatif = avantage pour l'adversaire), déjà
    # convertie côté app.py depuis le point de vue des Blancs en fonction de
    # camp_alain : un signe "point de vue des Blancs" transmis tel quel s'est
    # déjà révélé ambigu en usage réel (un -131 lu comme "en faveur des "
    # "Blancs" alors que camp_alain="noirs" signifiait +131, donc un avantage
    # pour Alain). Plus aucun nombre dont le signe dépend de la couleur n'est
    # transmis ici.
    eval_alain_cp  = context.get("eval_alain_cp")
    eval_alain_mat = context.get("eval_alain_mat")
    # Mode "Travail d'ouverture" (issue #9) : statut par rapport au livre
    # Polyglot de référence (gm2001.bin), en complément de meilleur_coup.
    dans_le_livre          = context.get("dans_le_livre")
    coup_livre_recommande  = (context.get("coup_livre_recommande") or "").strip()
    popularite_pct         = context.get("popularite_pct")
    # Mode "Travail de finales" (issue #10) : thème/technique de la
    # position-type sélectionnée (finales.py), pour que le commentaire
    # puisse s'y référer explicitement (ex. mentionner l'opposition).
    theme_finale = (context.get("theme_finale") or "").strip()
    # Démonstration Stockfish-contre-Stockfish en cours (issue #29, mode
    # "Travail de finales") : la position affichée ne résulte d'aucun coup
    # d'Alain, contrairement au jeu normal — sans ce champ explicite, le
    # coach n'a aucun moyen de distinguer une démonstration d'une partie
    # réellement jouée par Alain (voir _DEMONSTRATION_ADDENDUM).
    mode_demonstration = bool(context.get("mode_demonstration"))
    demo_coups_joues = context.get("demo_coups_joues")
    # Partie terminée par abandon (issue #52) : sans ce champ explicite, le
    # chat libre sollicité juste après un clic sur "Abandonner" ne recevait
    # que le PGN/FEN de la partie, sans savoir qu'elle est terminée ni
    # pourquoi — le coach répondait alors comme si la partie continuait,
    # voire niait qu'un coup ait été joué (plateau remis à zéro côté client
    # avant ce correctif).
    partie_terminee = bool(context.get("partie_terminee"))
    resultat_partie = (context.get("resultat_partie") or "").strip()
    # Bloc de faits calculés mécaniquement côté serveur avec python-chess
    # (issue #55, cf. game_facts.py/app.py _enrich_context_with_game_facts) :
    # coups numérotés/camp explicite/bilan matériel, moments clés, position
    # actuelle pièce par pièce — pour ne plus faire relire le PGN en texte
    # au modèle, source directe de coups attribués au mauvais camp ou
    # d'échanges inventés (voir _GAME_FACTS_ADDENDUM plus haut).
    faits_calcules = (context.get("faits_calcules") or "").strip()
    # Identification de la partie/l'exercice actuellement discuté(e) (issue
    # #64 point 3) : mode, nombre de coups déjà joués et heure de début du
    # segment de conversation courant (cf. board.js coachNewSegment) —
    # complète l'isolation de l'historique déjà faite côté client
    # (coachSend() ne renvoie que les messages depuis le dernier début de
    # partie/exercice) par un signal explicite dans le contexte lui-même,
    # pour que le modèle distingue sans ambiguïté cette partie-ci d'une autre
    # qu'un message affiché plus haut à l'écran pourrait encore évoquer.
    mode_origine_ctx = (context.get("mode_origine") or "").strip()
    nb_coups = context.get("nb_coups")
    debut_partie = (context.get("debut_partie") or "").strip()
    # Source « Problèmes Lichess » du mode exercice (issue #78) : thèmes
    # Lichess du problème, sa note (difficulté Glicko-2) et le niveau
    # courant d'Alain dans la catégorie ayant servi au tirage — en
    # complément du contexte déjà commun avec la source "mes erreurs"
    # (position, coups, verdict...) ci-dessus/ci-dessous.
    themes_lichess = (context.get("themes_lichess") or "").strip()
    rating_probleme = context.get("rating_probleme")
    niveau_categorie = context.get("niveau_categorie")
    categorie_libelle = (context.get("categorie_libelle") or "").strip()
    lines = []
    identification = []
    if mode_origine_ctx:
        identification.append(f"mode {mode_origine_ctx}")
    if isinstance(nb_coups, int):
        identification.append(f"{nb_coups} coup(s) déjà joué(s)")
    if debut_partie:
        identification.append(f"partie/exercice commencé(e) à {debut_partie}")
    if identification:
        lines.append(
            "Identification de la partie/l'exercice actuellement discuté(e) : "
            + ", ".join(identification) + ". Si un message affiché plus haut "
            "dans cette conversation évoque une partie différente (mode, "
            "camp, nombre de coups ou heure de début différents de ceux "
            "ci-dessus), ignore-le complètement : base-toi uniquement sur les "
            "données ci-dessous pour cette partie-ci."
        )
    if camp_alain in ("blancs", "noirs"):
        camp_txt = "Blancs" if camp_alain == "blancs" else "Noirs"
        lines.append(f"Alain (le joueur que tu coaches) joue les {camp_txt} dans cette partie.")
    elif camp_alain_inconnu:
        lines.append(
            "Camp joué par Alain dans cette partie : indéterminable à partir "
            "des données disponibles (en-têtes PGN ne correspondant ni au "
            "pseudo d'Alain ni au nom \"Alain\"). N'attribue donc AUCUN coup "
            "à Alain ni à \"l'adversaire\" : décris chaque coup uniquement "
            "par son camp (Blancs/Noirs)."
        )
    if fen_depart_exercice:
        lines.append(
            f"Position de DÉPART de cet exercice (FEN), avant tout coup : "
            f"{fen_depart_exercice}"
        )
    if fen:
        lines.append(f"Position ACTUELLEMENT affichée sur l'échiquier (FEN) : {fen}")
    if fen_depart_exercice and fen and fen_depart_exercice != fen:
        lines.append(
            "La position de départ et la position actuelle ci-dessus sont "
            "DIFFÉRENTES (le coup proposé a déjà été joué sur l'échiquier, ou "
            "Alain explore librement la suite) : pour toute pièce ou case en "
            "lien avec un coup cité ci-dessous, fie-toi uniquement à sa "
            "description mécanique (calculée sur la position de départ), "
            "jamais à ce que tu observes sur la position actuelle — ne "
            "conclus jamais qu'une pièce \"n'existe pas\" ou \"n'est pas là\" "
            "sans comparer explicitement les deux positions."
        )
    if pieces_depart_texte:
        lines.append(
            "Liste des pièces de la position de DÉPART de cet exercice, case "
            f"par case (issue #80) :\n{pieces_depart_texte}"
        )
    if pieces_actuelles_texte:
        lines.append(
            "Liste des pièces de la position ACTUELLE, case par case (issue "
            f"#80) :\n{pieces_actuelles_texte}"
        )
    if menace_adverse_texte:
        lines.append(menace_adverse_texte)
    if move:
        lines.append(f"Coup actuel : {move}")
    if coup_propose:
        # Étiquette explicite "MAINTENANT" / coup_reel étiqueté "À L'ÉPOQUE"
        # ci-dessous (issue #18 point 3) : évite que le coach présente le
        # coup réellement joué dans la partie d'origine comme si Alain
        # venait de le proposer dans la tentative en cours.
        lines.append(
            "Coup que le joueur vient de proposer MAINTENANT, dans cette "
            f"tentative d'exercice : {coup_propose}"
        )
        if coup_propose_description_mecanique:
            lines.append(
                f"Description mécanique calculée de ce coup (depuis la "
                f"position de départ) : {coup_propose_description_mecanique}"
            )
        if pv_coup_propose:
            lines.append(
                "Suite réellement calculée par Stockfish après ce coup proposé "
                f"(à utiliser comme seule base pour expliquer les menaces ou la "
                f"suite tactique, pas une généralité inventée) : {pv_coup_propose}"
            )
        if pv_coup_propose_detail:
            lines.append(pv_coup_propose_detail)
        if idees_coup_propose_texte:
            lines.append(idees_coup_propose_texte)
    if coup_reel:
        lines.append(
            "Coup que le joueur avait réellement joué À L'ÉPOQUE, dans la "
            "partie d'origine dont cet exercice est tiré — PAS le coup qu'il "
            f"vient de proposer ci-dessus : {coup_reel}"
        )
        if coup_reel_description_mecanique:
            lines.append(
                f"Description mécanique calculée de ce coup (depuis la "
                f"position de départ) : {coup_reel_description_mecanique}"
            )
        if idees_coup_reel_texte:
            lines.append(idees_coup_reel_texte)
    if meilleur_coup:
        detail = f"Meilleur coup selon Stockfish : {meilleur_coup}."
        lines.append(detail)
        if meilleur_coup_description_mecanique:
            lines.append(
                f"Description mécanique calculée de ce coup (depuis la "
                f"position de départ) : {meilleur_coup_description_mecanique}"
            )
        if pv_meilleur_coup:
            lines.append(
                "Suite réellement calculée par Stockfish pour ce meilleur coup "
                f"(à utiliser comme seule base pour expliquer les menaces ou le "
                f"plan qu'il prépare, pas une généralité inventée) : {pv_meilleur_coup}"
            )
        if pv_meilleur_coup_detail:
            lines.append(pv_meilleur_coup_detail)
        if idees_meilleur_coup_texte:
            lines.append(idees_meilleur_coup_texte)
    if rating_probleme is not None:
        lines.append(
            f"Ce problème est tiré de la base ouverte de problèmes Lichess "
            f"(pas une erreur passée d'Alain) : thème principal \"{categorie_libelle}\""
            f"{f', thèmes Lichess : {themes_lichess}' if themes_lichess else ''}, "
            f"note de difficulté {rating_probleme} (plus c'est élevé, plus "
            f"c'est difficile). Niveau actuel d'Alain dans cette catégorie "
            f"(\"{categorie_libelle}\") : {niveau_categorie}."
        )
    if analyse_indisponible:
        # Issue #79, point 4c (deuxième ligne de défense) : même en mode
        # exercice (où get_coach_response refuse normalement déjà l'appel
        # API avant d'arriver ici, cf. point 4b), ce message explicite
        # protège aussi les AUTRES modes (pédagogique, ouverture hors-livre,
        # finales, "Demander l'avis du coach") qui n'ont pas ce garde-fou
        # serveur strict. Constat réel ayant motivé ce correctif (cf.
        # rapport de clôture) : sans cette ligne, le coach a affirmé
        # disposer d'un "verdict final" alors qu'aucun verdict ni évaluation
        # n'avait pu être calculé, et a contredit la réalité (inventé une
        # capture inexistante, qualifié de gaffe un coup que Stockfish
        # classait en fait meilleur coup).
        sujet = "cet exercice" if context.get("mode_exercice") else "cette position"
        lines.append(
            f"Analyse Stockfish indisponible pour {sujet} : aucun verdict, "
            "aucune évaluation, aucun meilleur coup (panne ou délai dépassé "
            "du moteur — voir _ANALYSE_INDISPONIBLE_ADDENDUM pour la règle "
            "complète à appliquer ici)."
        )
    elif verdict_qualite:
        # describe_perte_cp_clause (issue #75, point 1) : en mots dès que la
        # magnitude dépasse SEUIL_GRANDE_VALEUR_CP (ex. le delta sentinelle
        # DELTA_CP_MAT_CONTRE d'un coup qui permet un mat forcé contre
        # Alain, engine_stockfish.py) — jamais le chiffre brut dans ce cas.
        detail_cp = game_facts.describe_perte_cp_clause(verdict_delta_cp)
        lines.append(
            "Verdict Stockfish déjà calculé pour ce coup exact (INTERNE — ne "
            f"jamais citer ce chiffre ni cette étiquette brute à Alain) : classé "
            f"\"{verdict_qualite}\"{detail_cp}. Ce verdict est définitif : "
            "explique pourquoi il est justifié, ne le confirme ni ne le "
            "contredis par ton propre jugement."
        )
        # Données partielles (issue #79, point 5) : le verdict a été rendu,
        # mais un champ auxiliaire attendu peut manquer (panne ponctuelle
        # d'un appel moteur distinct, cf. app.py _eval_blancs_apres/
        # _evaluate_move_for_coach) — l'indiquer explicitement champ par
        # champ plutôt que de laisser le prompt en inventer une valeur
        # plausible à partir du seul verdict.
        if eval_alain_cp is None and eval_alain_mat is None:
            lines.append(
                "Évaluation de la position résultant de ce coup proposé : "
                "indisponible. N'invente AUCUN chiffre ni mot d'ampleur "
                "(\"léger avantage\", \"position gagnée\"...) pour la "
                "remplacer — dis simplement que tu n'as pas cette évaluation "
                "si Alain la demande."
            )
        if not meilleur_coup:
            lines.append(
                "Coup de référence (meilleur coup selon Stockfish) : "
                "indisponible pour cette position. N'en invente AUCUN à la "
                "place."
            )
        if coup_propose and not pv_coup_propose:
            lines.append(
                "Ligne principale (suite calculée) du coup proposé : "
                "indisponible. Décris ce coup sans supposer de suite "
                "tactique calculée."
            )
        if meilleur_coup and not pv_meilleur_coup:
            lines.append(
                "Ligne principale (suite calculée) du meilleur coup : "
                "indisponible. Décris ce coup sans supposer de suite "
                "tactique calculée."
            )
    if reponse_suivante:
        lines.append(
            f"Réfutation calculée mécaniquement de ce coup (issue #62), à "
            f"expliquer EN PREMIER, avant toute autre remarque stratégique : "
            f"{reponse_suivante}"
        )
    if coup_description_mecanique:
        lines.append(
            f"Description mécanique calculée de ce coup (issue #66), seule "
            f"source fiable pour la pièce qui joue, sa case de départ et ce "
            f"qu'elle capture ou attaque : {coup_description_mecanique}"
        )
    # meilleur_coup_description_mecanique est déjà émis ci-dessus, dans le
    # bloc "if meilleur_coup:" (partagé entre le mode "exercice" et le mode
    # "analyse_partie", tous deux transmettent "meilleur_coup").
    if reprise_recente:
        lines.append(
            "Alain vient d'annuler sa dernière tentative sur cet exercice avec "
            "\"Reprendre mon coup\" et n'a pas encore reproposé de coup : la "
            "position ci-dessus est donc à nouveau la position de départ, "
            "inchangée. Le coup et le verdict éventuellement discutés plus tôt "
            "dans cette conversation ne s'appliquent plus à l'état actuel."
        )
    if eval_alain_mat is not None:
        cible = "Alain" if eval_alain_mat > 0 else "l'adversaire"
        lines.append(
            f"Évaluation Stockfish réelle de la position résultant du coup proposé : "
            f"mat forcé en {abs(eval_alain_mat)} coup(s) en faveur de {cible}."
        )
    elif eval_alain_cp is not None:
        # describe_eval_alain_cp_clause (issue #75, point 1) : en mots dès
        # que la magnitude dépasse SEUIL_GRANDE_VALEUR_CP — jamais le chiffre
        # brut dans ce cas (constat réel : "+199,74"/"+34,56" pions cités
        # tels quels à Alain, pour des évaluations de 19974/3456 centipawns
        # dans des positions de gain forcé).
        lines.append(game_facts.describe_eval_alain_cp_clause(eval_alain_cp))
    if dans_le_livre is not None:
        statut = "dans le livre d'ouvertures" if dans_le_livre else "hors du livre d'ouvertures"
        lines.append(f"Statut par rapport au livre de référence : {statut}")
    if popularite_pct is not None:
        lines.append(f"Popularité de ce coup dans le livre : {popularite_pct}% des parties de référence")
    if coup_livre_recommande:
        lines.append(f"Coup le plus joué dans le livre pour cette position : {coup_livre_recommande}")
    if theme_finale:
        lines.append(f"Thème technique de cette finale : {theme_finale}")
    if mode_demonstration:
        detail_coups = (
            f" ({demo_coups_joues} demi-coup(s) joué(s), tous par Stockfish, 0 par Alain)"
            if isinstance(demo_coups_joues, int) else ""
        )
        lines.append(
            "Mode démonstration : Stockfish joue seul les deux camps sur "
            f"cette position, Alain n'a joué AUCUN coup{detail_coups}."
        )
    if partie_terminee:
        detail = f" ({resultat_partie})" if resultat_partie else ""
        lines.append(
            "Cette partie est terminée{detail} — Alain ne jouera plus aucun "
            "coup dans cette partie précise. S'il pose une question sur ce "
            "qui vient de se passer, réponds à partir du PGN complet "
            "ci-dessous, ne dis jamais qu'aucun coup n'a été joué.".format(detail=detail)
        )
    if faits_calcules:
        lines.append(faits_calcules)
    if pgn:
        lines.append(f"PGN de la partie :\n{pgn}")
    return "\n".join(lines)


def _log_coach_call(log_path, system_prompt: str, context: dict, messages, mode_origine: str,
                     model: str = None, reponse: str = None, erreur: str = None, usage: dict = None) -> None:
    """Journalise un appel complet au coach (issue #18, étendu à tous les
    modes par l'issue #26 — plus seulement le mode "Exercice") : horodatage,
    mode d'origine, system prompt complet, contexte construit (tous les
    champs, y compris coup_propose/coup_reel/meilleur_coup/verdict_qualite/
    verdict_delta_cp/pv_coup_propose/pv_meilleur_coup) et messages envoyés,
    en JSON Lines dans log_path — pour diagnostiquer une erreur factuelle du
    coach à partir de ce qui a été réellement transmis à Haiku, pas d'une
    supposition, quel que soit le mode. Best-effort : une erreur d'écriture
    ne doit jamais faire échouer la réponse au coach.

    Étendu par l'issue #44 : le log n'enregistrait jusque-là que la requête
    envoyée à Claude, jamais sa réponse réelle — un diagnostic sur une
    affirmation erronée du coach (ex. case mentionnée incorrecte) dépendait
    donc d'un copier-coller manuel d'Alain. `reponse`/`erreur` sont les
    champs `text`/erreur retournés par `_call_claude` (un seul des deux non
    None), écrits dans la même entrée que la requête plutôt que dans une
    entrée séparée, pour garder la corrélation requête/réponse triviale à
    relire.

    Étendu par l'issue #54 : `usage` (tokens input/output/cache de cet appel
    précis, ou None si indisponible — ex. `credit_insuffisant`, aucun appel
    API n'a abouti) vient compléter le diagnostic ligne à ligne, en plus du
    compteur cumulé (usage_tokens.json).

    Étendu par l'issue #61 : `model` (le paramètre "llm_model" transmis à cet
    appel, alias éventuel compris) est désormais inscrit explicitement dans
    chaque entrée, y compris en cas d'erreur où `usage.model` (résolu par
    l'API) est absent — un changement de modèle en cours de session reste
    ainsi traçable ligne à ligne, même sur un appel qui a échoué avant toute
    réponse (ex. modele_indisponible).
    """
    if not log_path:
        return
    try:
        log_path = Path(log_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "horodatage": datetime.now().isoformat(),
            "mode_origine": mode_origine,
            "model": model,
            "system_prompt": system_prompt,
            "context": context or {},
            "messages": messages,
            "reponse": reponse,
            "erreur": erreur,
            "usage": usage,
        }
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.warning(f"[LLM_COACH] Écriture du log coach_calls échouée : {e}")


def _call_claude(prompt_sys: str, messages, api_key: str, model: str, usage_path=None) -> str:
    """messages : liste de {"role": "user"|"assistant", "content": str}, ou une
    simple chaîne (raccourci équivalent à [{"role": "user", "content": messages}]).

    Retourne le texte de la réponse (comme avant l'issue #54). Lève
    CreditInsuffisantError si l'API répond que le crédit est épuisé (détection
    tolérante, issue #60 : voir CreditInsuffisantError ci-dessus), pour que
    l'appelant affiche un message clair au lieu de la ValueError générique.
    Relève aussi les tokens
    consommés (usage.input_tokens/output_tokens/cache_*) depuis la réponse et
    les cumule dans usage_path si fourni — aucun appel API supplémentaire,
    ces informations sont déjà présentes dans la réponse normale (issue #54)."""
    if isinstance(messages, str):
        messages = [{"role": "user", "content": messages}]
    body = json.dumps({
        "model": model or "claude-haiku-4-5",
        # 300 tokens coupait certaines réponses en plein mot dès que le coach
        # développait un conseil détaillé plutôt qu'un commentaire de coup
        # isolé (issue #12 point 2). 1024 s'est révélé encore insuffisant à
        # l'usage (stop_reason "max_tokens" constaté sur une question
        # détaillée type "explique-moi la stratégie de la Défense française") :
        # 2048 laisse la marge nécessaire pour ce genre de conseil structuré,
        # tout en restant loin de dériver vers des réponses interminables.
        # Porté à 4096 (issue #47) : au-delà de la marge pour le texte de
        # réponse, ce budget doit aussi couvrir un éventuel raisonnement
        # adaptatif sur claude-sonnet-5 (voir "thinking" ci-dessous) — 2048
        # pouvait être entièrement consommé par la réflexion, laissant 0
        # token pour la réponse elle-même.
        "max_tokens": 4096,
        # claude-sonnet-5 exécute un raisonnement adaptatif par défaut dès que
        # ce paramètre est omis (contrairement à Haiku, qui ne pense jamais).
        # Ce raisonnement consomme une partie de max_tokens avant même de
        # commencer à écrire la réponse ; sur une question simple, il pouvait
        # occuper tout le budget et laisser une réponse entièrement vide —
        # un seul bloc "thinking" sans aucun bloc "text" (issue #47). Un
        # commentaire de coach aux échecs n'a pas besoin d'exposer un
        # raisonnement séparé de la réponse elle-même (Haiku, utilisé
        # jusqu'à l'issue #44, ne raisonnait jamais et convenait déjà à cet
        # usage) : on désactive donc explicitement la réflexion plutôt que de
        # simplement lui laisser plus de place, ce qui élimine la classe de
        # problème à la racine.
        "thinking": {"type": "disabled"},
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
    # 15s suffisait pour un contexte léger, mais devenait insuffisant dès que
    # le PGN complet d'une partie longue et la mémoire de progression complète
    # sont transmis (Bibliothèque/Revue), surtout depuis le passage à
    # claude-sonnet-5 (latence un peu supérieure à Haiku) — timeout "the read
    # operation timed out" observé même sur une question triviale (issue #45).
    # 90s laisse une marge large sans bloquer indéfiniment l'interface en cas
    # de vrai problème réseau.
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        # Solde de crédit épuisé (issue #54, détection élargie issue #60) :
        # distinct de "permission_error" (403, clé sans les droits
        # nécessaires) et d'un 400 "invalid_request_error" ordinaire (requête
        # mal formée, sans rapport avec le crédit). Le corps de la réponse
        # doit être lu ici : une fois l'exception propagée, e.read() ne
        # serait plus disponible.
        corps = e.read().decode("utf-8", errors="replace")
        try:
            err_data = json.loads(corps)
        except (ValueError, TypeError):
            err_data = {}
        err_info = err_data.get("error") or {}
        err_type = err_info.get("type", "")
        err_msg = err_info.get("message", "")
        # Détection tolérante (issue #60) : la forme "403 billing_error"
        # observée initialement (issue #54) n'est pas garantie stable dans le
        # temps — des retours d'utilisateurs de l'API (2024-2025, non
        # revérifiables sans épuiser réellement un crédit) rapportent aussi un
        # statut 402, ou un 400 "invalid_request_error" dont le message
        # évoque le solde/les crédits (ex. "Your credit balance is too low...
        # Plans & Billing..."). On reconnaît donc les trois formes, sans se
        # fier à un unique couple (code, type) — tout en gardant les vraies
        # erreurs de permission (403 permission_error) et les vraies requêtes
        # invalides (400 sans mention de crédit) hors de ce cas.
        msg_lower = err_msg.lower()
        mots_credit = ("credit balance", "insufficient credit", "plans & billing", "plans and billing")
        est_credit_epuise = (
            err_type == "billing_error"
            or e.code == 402
            or (e.code == 400 and err_type == "invalid_request_error"
                and any(mot in msg_lower for mot in mots_credit))
        )
        if est_credit_epuise:
            raise CreditInsuffisantError(err_msg or "Crédit épuisé") from e
        # Modèle refusé par l'API (issue #61) : identifiant inconnu, retiré ou
        # momentanément indisponible côté Anthropic — distingué des autres
        # erreurs HTTP pour que l'appelant revienne au choix précédent plutôt
        # que d'afficher une erreur technique brute.
        if e.code == 404 and err_type == "not_found_error":
            raise ModeleIndisponibleError(
                (err_data.get("error") or {}).get("message", f"Modèle indisponible : {model}")
            ) from e
        raise
    # Tokens consommés par cet appel (issue #54) — déjà présents dans la
    # réponse normale de l'API, pas d'appel supplémentaire nécessaire. Le
    # modèle réellement utilisé (data["model"]) est repris plutôt que le
    # paramètre "model" d'entrée : celui-ci peut être vide (défaut appliqué
    # côté API) ou un alias, alors que la réponse renvoie l'ID résolu.
    usage_brut = data.get("usage") or {}
    modele_reel = data.get("model") or model or "claude-haiku-4-5"
    usage_appel = {
        "input_tokens": usage_brut.get("input_tokens") or 0,
        "output_tokens": usage_brut.get("output_tokens") or 0,
        "cache_creation_input_tokens": usage_brut.get("cache_creation_input_tokens") or 0,
        "cache_read_input_tokens": usage_brut.get("cache_read_input_tokens") or 0,
    }
    _record_usage(usage_path, modele_reel, usage_appel)
    # La liste "content" peut en théorie contenir un bloc "thinking" avant le
    # bloc "text", même si "thinking" est désormais explicitement désactivé
    # ci-dessus (issue #47) — cette recherche reste une défense en profondeur
    # plutôt qu'une hypothèse sur la position du bloc texte. Supposer que
    # content[0] est le texte provoquait un KeyError('text') (issue #46) : on
    # cherche donc le premier bloc de type "text", quelle que soit sa position.
    for bloc in data["content"]:
        if bloc.get("type") == "text":
            return bloc["text"]
    raise ValueError(f"Aucun bloc de type 'text' dans la réponse Claude : {data.get('content')!r}")


def get_opening_moves(opening_name: str, config):
    """Identifie les 2 à 6 premiers coups caractéristiques d'une ouverture
    nommée par Alain (issue #9), via un appel dédié à Claude — indépendant du
    chat coach multi-tours, pas de mémoire ni de contexte de partie injectés.

    Paramètres :
      opening_name : nom de l'ouverture, tel que saisi par Alain
      config       : dict avec au moins "llm_api_key" et, optionnellement,
                     "llm_model" (même convention que get_coach_response)

    Retourne (liste de coups SAN, erreur) — un seul des deux est non vide/None.
    Erreurs possibles : "nom_vide", "no_api_key", "ouverture_non_reconnue",
    "reponse_invalide", ou le message de l'exception réseau.
    """
    opening_name = (opening_name or "").strip()
    if not opening_name:
        return None, "nom_vide"

    api_key = (config or {}).get("llm_api_key", "")
    if not api_key:
        return None, "no_api_key"

    model = (config or {}).get("llm_model", "")
    usage_path = (config or {}).get("usage_path")

    try:
        raw = _call_claude(_OPENING_SYSTEM_PROMPT, opening_name, api_key, model, usage_path)
    except CreditInsuffisantError as e:
        logger.warning(f"[LLM_COACH] Appel Claude (ouverture) : crédit épuisé : {e}")
        return None, "credit_insuffisant"
    except ModeleIndisponibleError as e:
        logger.warning(f"[LLM_COACH] Appel Claude (ouverture) : modèle indisponible : {e}")
        return None, "modele_indisponible"
    except (urllib.error.URLError, urllib.error.HTTPError, KeyError, ValueError, TimeoutError) as e:
        logger.warning(f"[LLM_COACH] Appel Claude (ouverture) échoué : {e}")
        return None, str(e)

    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()

    try:
        parsed = json.loads(text)
    except (ValueError, TypeError):
        logger.warning(f"[LLM_COACH] Réponse ouverture non-JSON : {raw!r}")
        return None, "reponse_invalide"

    if not isinstance(parsed, dict):
        return None, "reponse_invalide"
    if parsed.get("error"):
        return None, "ouverture_non_reconnue"

    moves = parsed.get("moves")
    if not isinstance(moves, list) or not moves or not all(isinstance(m, str) and m.strip() for m in moves):
        return None, "reponse_invalide"

    return [m.strip() for m in moves[:6]], None


def get_training_program(patterns_erreurs, repertoire_ouvertures, config):
    """Établit un programme d'entraînement de 2 à 3 priorités concrètes
    (issue #14, bouton "Établir mon programme d'entraînement"), via un appel
    dédié à Claude — indépendant du chat coach multi-tours, à partir des
    patterns_erreurs et repertoire_ouvertures de coach_memory.json.

    Paramètres :
      patterns_erreurs      : dict (clé coach_memory.json) — peut être {}
      repertoire_ouvertures : dict (clé coach_memory.json) — peut être {}
      config                : dict avec au moins "llm_api_key" et,
                               optionnellement, "llm_model"

    Retourne (liste de 2 à 3 priorités textuelles, erreur) — un seul des
    deux est non vide/None. Erreurs possibles : "no_api_key",
    "donnees_insuffisantes", "reponse_invalide", ou le message de
    l'exception réseau.
    """
    api_key = (config or {}).get("llm_api_key", "")
    if not api_key:
        return None, "no_api_key"

    if not patterns_erreurs and not repertoire_ouvertures:
        return None, "donnees_insuffisantes"

    model = (config or {}).get("llm_model", "")
    data_text = json.dumps({
        "patterns_erreurs": patterns_erreurs or {},
        "repertoire_ouvertures": repertoire_ouvertures or {},
    }, ensure_ascii=False, indent=2)
    prompt_user = f"Données du joueur (JSON) :\n{data_text}"
    usage_path = (config or {}).get("usage_path")

    try:
        raw = _call_claude(_TRAINING_PROGRAM_SYSTEM_PROMPT, prompt_user, api_key, model, usage_path)
    except CreditInsuffisantError as e:
        logger.warning(f"[LLM_COACH] Appel Claude (programme d'entraînement) : crédit épuisé : {e}")
        return None, "credit_insuffisant"
    except ModeleIndisponibleError as e:
        logger.warning(f"[LLM_COACH] Appel Claude (programme d'entraînement) : modèle indisponible : {e}")
        return None, "modele_indisponible"
    except (urllib.error.URLError, urllib.error.HTTPError, KeyError, ValueError, TimeoutError) as e:
        logger.warning(f"[LLM_COACH] Appel Claude (programme d'entraînement) échoué : {e}")
        return None, str(e)

    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()

    try:
        parsed = json.loads(text)
    except (ValueError, TypeError):
        logger.warning(f"[LLM_COACH] Réponse programme d'entraînement non-JSON : {raw!r}")
        return None, "reponse_invalide"

    if not isinstance(parsed, dict):
        return None, "reponse_invalide"

    objectifs = parsed.get("objectifs")
    if not isinstance(objectifs, list) or not objectifs or not all(
        isinstance(o, str) and o.strip() for o in objectifs
    ):
        return None, "reponse_invalide"

    return [o.strip() for o in objectifs[:3]], None


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

    # Issue #79, point 4b : refuse l'appel au modèle quand le contexte d'un
    # exercice ne contient aucun verdict Stockfish — AVANT tout appel API,
    # pour qu'aucun chemin (rechargement de page, reconnexion, événement
    # tardif) ne puisse contourner le blocage côté interface (cf.
    # exercise.js/#4a) : même un rechargement qui rejouerait un vieux
    # payload sans verdict se heurte à ce garde-fou serveur. Couvre
    # uniformément exercise_answer, la source « Problèmes Lichess » et toute
    # question de suivi posée pendant l'exercice (coach_ask/
    # coach_comment_on_demand, qui transmettent tous mode_exercice=True —
    # cf. app.py exerciseChatContextExtra). Message fixe, sans journaliser
    # ni appeler l'API : un exercice sans verdict n'a rien à journaliser
    # côté appel LLM, la panne moteur elle-même est déjà tracée dans
    # MOTEUR_ERREURS_LOG_PATH (cf. engine_stockfish.py).
    if (context or {}).get("mode_exercice") and not (context or {}).get("verdict_qualite"):
        return None, "pas_de_verdict_exercice"

    model = (config or {}).get("llm_model", "")
    prompt_sys = _SYSTEM_PROMPT
    if (context or {}).get("mode_exercice"):
        prompt_sys = f"{prompt_sys}\n\n{_EXERCISE_SYSTEM_ADDENDUM}"
        if (context or {}).get("source_lichess"):
            # Source « Problèmes Lichess » (issue #78) : réponse courte, pas
            # de "coup réel à l'époque" — complément du garde-fou générique
            # de l'exercice ci-dessus, pas un remplacement.
            prompt_sys = f"{prompt_sys}\n\n{_EXERCISE_LICHESS_ADDENDUM}"
    else:
        # Issue #68 : format de départ des lignes alternatives pour tous les
        # modes hors exercice (partie avec historique réel, ou revue) — pas
        # conditionné à la présence d'un verdict/d'une PV Stockfish,
        # contrairement au garde-fou ci-dessous qui reste indépendant.
        prompt_sys = f"{prompt_sys}\n\n{_GAME_LINES_ADDENDUM}"
        if (context or {}).get("verdict_qualite") or (context or {}).get("pv_coup_propose") or (context or {}).get("pv_meilleur_coup"):
            # Mêmes garde-fous qu'en mode "exercice" (issue #26) dès qu'un
            # verdict et/ou une PV Stockfish sont transmis par un autre mode
            # (pédagogique, ouverture hors-livre, finales) — pas de flag
            # mode_exercice requis.
            prompt_sys = f"{prompt_sys}\n\n{_ANTI_INVENTION_ADDENDUM}"
    if (context or {}).get("mode_demonstration"):
        # Indépendant des branches ci-dessus (issue #29) : une démonstration
        # ne transmet ni mode_exercice ni verdict Stockfish, ce garde-fou doit
        # donc pouvoir s'ajouter seul.
        prompt_sys = f"{prompt_sys}\n\n{_DEMONSTRATION_ADDENDUM}"
    if (context or {}).get("mode_origine") == "analyse_partie":
        # Indépendant des branches ci-dessus (issue #56) : l'explication à la
        # demande d'un coup flagué (on_analyse_expliquer_coup) transmet aussi
        # mode_exercice=True (réutilisation du garde-fou verdict Stockfish
        # existant, issue #17/#26) — ce complément s'ajoute donc en plus,
        # jamais à la place.
        prompt_sys = f"{prompt_sys}\n\n{_ANALYSE_PARTIE_ADDENDUM}"
    if (context or {}).get("faits_calcules"):
        # Indépendant des branches ci-dessus (issue #55) : le bloc de faits
        # calculés peut coexister avec n'importe lequel des autres modes
        # (ex. pédagogique avec verdict Stockfish sur le coup courant, ET
        # faits calculés sur la partie en cours).
        prompt_sys = f"{prompt_sys}\n\n{_GAME_FACTS_ADDENDUM}"
    if (context or {}).get("analyse_indisponible") and not (context or {}).get("verdict_qualite"):
        # Indépendant des branches ci-dessus (issue #79) : s'ajoute dès que
        # le contexte signale une analyse Stockfish indisponible SANS
        # verdict déjà obtenu par ailleurs (cf. _build_context_text, même
        # condition) — en mode exercice ce cas ne devrait jamais atteindre
        # l'appel API (garde-fou ci-dessus), ce complément reste donc
        # surtout utile aux autres modes.
        prompt_sys = f"{prompt_sys}\n\n{_ANALYSE_INDISPONIBLE_ADDENDUM}"

    memory_text = _build_memory_text(coach_memory)
    if memory_text:
        prompt_sys = f"{prompt_sys}\n\n{memory_text}"

    context_text = _build_context_text(context)
    if context_text:
        prompt_sys = f"{prompt_sys}\n\nContexte de la position en cours :\n{context_text}"

    # Logging étendu à tous les modes (issue #26) — plus seulement l'exercice
    # (issue #18) : mode_origine explicite si fourni par l'appelant, sinon
    # déduit de mode_exercice, sinon "chat_libre" (conversation hors mode
    # d'entraînement actif, ex. revue d'une partie importée).
    mode_origine = (context or {}).get("mode_origine") or (
        "exercice" if (context or {}).get("mode_exercice") else "chat_libre"
    )
    log_path = (config or {}).get("coach_log_path")
    usage_path = (config or {}).get("usage_path")

    # Appel loggé une seule fois, après coup (issue #44) : plus tôt, seule la
    # requête était journalisée (avant même l'appel API) — la réponse réelle
    # du coach n'apparaissait donc jamais dans coach_calls.log, obligeant à
    # se fier à un copier-coller manuel d'Alain pour diagnostiquer une
    # affirmation erronée.
    try:
        response = _call_claude(prompt_sys, clean_messages, api_key, model, usage_path)
    except CreditInsuffisantError as e:
        logger.warning(f"[LLM_COACH] Appel Claude : crédit épuisé : {e}")
        _log_coach_call(log_path, prompt_sys, context, clean_messages, mode_origine, model=model, erreur="credit_insuffisant")
        return None, "credit_insuffisant"
    except ModeleIndisponibleError as e:
        logger.warning(f"[LLM_COACH] Appel Claude : modèle indisponible : {e}")
        _log_coach_call(log_path, prompt_sys, context, clean_messages, mode_origine, model=model, erreur="modele_indisponible")
        return None, "modele_indisponible"
    except (urllib.error.URLError, urllib.error.HTTPError, KeyError, ValueError, TimeoutError) as e:
        logger.warning(f"[LLM_COACH] Appel Claude échoué : {e}")
        _log_coach_call(log_path, prompt_sys, context, clean_messages, mode_origine, model=model, erreur=str(e))
        return None, str(e)

    response = (response or "").strip()
    # dernier_appel vient d'être écrit par _call_claude (via _record_usage)
    # pour ce même appel : le relire ici évite de faire remonter le tuple
    # d'usage à travers toute la chaîne de retour juste pour le logging
    # (issue #54, champ d'usage ajouté à coach_calls.log).
    usage_appel = (get_usage_summary(usage_path) or {}).get("dernier_appel") if usage_path else None
    _log_coach_call(log_path, prompt_sys, context, clean_messages, mode_origine, model=model, reponse=response, usage=usage_appel)
    return response, None
