# Compteur de tokens consommés (usage_tokens.json, dans DATA_DIR — issue #54)

Le solde restant de la clé API n'est pas lisible par programme (il n'existe
que sur la Console platform.claude.com) et Alain préfère ne pas maintenir de
table de prix par modèle côté ChessCoach : le compteur affiche donc
uniquement des tokens bruts, sans aucun prix ni équivalent en argent — à
charge pour lui de rapprocher ce compte du solde réel affiché sur la
Console.

À chaque appel réussi à l'API Claude (tous les chemins : chat du coach,
explications de coups, programme d'entraînement, commentaires des modes
ouverture/finales/pédagogique/exercice), `_call_claude` (llm_coach.py) relève
les tokens d'entrée/de sortie/de cache (création et lecture) déjà présents
dans la réponse de l'API (`usage`, aucun appel supplémentaire) et les cumule
dans `data/usage_tokens.json` via `_record_usage`/`_save_usage`, par modèle
réellement utilisé (`data["model"]` de la réponse, pas le paramètre d'entrée
qui peut être un alias ou vide). Le fichier garde aussi une date de départ du
cumul et le détail du dernier appel ; il survit donc à un redémarrage de
l'appli (comme coach_memory.json), et reste hors du dépôt (sous DATA_DIR,
gitignoré).

Côté interface, l'en-tête affiche un texte discret à côté du lien
« Coût API » (`#usage-tokens-widget` dans templates/index.html, logique dans
static/usage_tokens.js) : tokens du dernier appel et total cumulé depuis la
date de départ, entrée/sortie séparées. Le détail par modèle apparaît au
survol (desktop) ou au tap (mobile, via une bascule de classe CSS) — un token
n'a pas le même « coût » selon le modèle utilisé, ce détail doit donc rester
consultable même si le résumé affiché est compact. Sur écran étroit (media
query `max-width: 900px`), le texte bascule vers une forme courte
(`Σ … in / … out`) pour ne pas déborder de l'en-tête. Un bouton « Remettre le
compteur à zéro » (dans le détail, avec confirmation `confirm()` légère)
réinitialise le fichier entier, y compris la date de départ.

Quand l'API répond que le crédit est épuisé, `_call_claude` lève
`CreditInsuffisantError` plutôt que la `ValueError` générique ; tous les
gestionnaires SocketIO renvoient alors `error: "credit_insuffisant"` et le
client affiche un message clair (bulle dédiée dans le chat coach, ou message
inline selon le mode) avec un lien vers la Console pour recharger, au lieu
d'une erreur technique. Détection tolérante (issue #60) plutôt que basée sur
un unique couple (code HTTP, type) : `error.type == "billing_error"` quel que
soit le code HTTP, ou HTTP 402, ou HTTP 400 `invalid_request_error` dont le
message mentionne le solde/les crédits (ex. « credit balance », « Plans &
Billing »), insensible à la casse — la forme exacte renvoyée par l'API pour
ce cas n'est pas garantie stable dans le temps et ne peut pas être vérifiée
sans épuiser réellement un crédit. Les vraies erreurs de permission (403
`permission_error`) et les vraies requêtes invalides (400 sans mention de
crédit) restent distinguées et ne déclenchent pas ce message.

Chaque appel loggé dans `data/logs/coach_calls.log` porte désormais aussi son
propre champ `usage` (tokens de cet appel précis, ou `null` si l'appel n'a
pas abouti), en complément du compteur cumulé, pour le diagnostic. Depuis
l'issue #61, chaque entrée porte aussi un champ `model` explicite (le
paramètre transmis à cet appel précis), y compris sur les entrées d'erreur où
`usage` est absent — ce qui garde traçable, ligne à ligne, quel modèle a
réellement servi même après un changement de modèle en cours de session.
