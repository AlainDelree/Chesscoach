# Enregistrement des jetons Mistral et estimation du coût (issue #119)

Depuis l'issue #119, les appels à l'API Mistral enregistrent aussi leur
consommation de jetons (jetons d'entrée et de sortie, et jetons en cache si
l'API les indique) dans le champ `usage` de chaque entrée du journal
`coach_calls*.log`, avec la même structure que celle utilisée pour Claude.
La consommation est extraite directement de la réponse de l'API Mistral
(champ `usage` avec `prompt_tokens` et `completion_tokens`), sans appel
supplémentaire. Une réponse sans information de consommation ne casse rien
: le champ `usage` vaut alors `null` dans le journal.

Le compteur de jetons affiché dans l'en-tête de l'appli reste celui de
Claude uniquement (via `usage_tokens.json`) — les jetons de Mistral sont
comptés à part et ne sont pas ajoutés au compteur existant, conformément à
la demande d'Alain.

Un fichier de données modifiable à la main, `data/token_prices.json`, contient
le tableau de prix par modèle : prix par million de jetons en entrée et en
sortie, devise, date de dernière vérification, indication « vérifié »
(vrai/faux) et note sur la source. Ce fichier est pré-rempli avec les valeurs
connues (Claude Sonnet 5, Claude Haiku 4.5, Mistral Large latest/2512/4/4-0),
toutes marquées « à vérifier » initialement. Un modèle absent du tableau n'a
jamais de prix inventé : le script affiche « prix inconnu », jamais 0.

Le script `scripts/estimer_cout_api.py` lit tous les fichiers `coach_calls*.log`
et affiche, pour un jour donné (aujourd'hui par défaut, avec options `--date`,
`--debut`, `--fin`) : par agent (Claude/Mistral) et par modèle, le nombre
d'appels, les jetons d'entrée et de sortie, et le coût estimé dans la devise
du modèle, puis les totaux par devise. Les appels sans consommation enregistrée
(par exemple les appels de Mistral d'avant l'issue #119) sont comptés à part
comme « consommation inconnue », avec leur nombre, sans estimation inventée.
Le script affiche un avertissement tant que des prix utilisés sont marqués
« à vérifier », et rappelle qu'il s'agit d'une estimation et non de la
facturation officielle (les remises, le cache et les arrondis peuvent différer).
