# Température configurable pour les appels LLM (issue #116)

Pour permettre une comparaison honnête entre Claude et Mistral sur les
exercices, les deux IA doivent tourner dans des conditions connues et, si
possible, identiques. Deux variables d'environnement permettent désormais de
configurer la température pour chaque fournisseur :

- `CHESSCOACH_CLAUDE_TEMPERATURE` : température pour les appels à Claude en
  mode exercice. Si absente ou vide, aucun paramètre n'est envoyé (l'API
  utilise sa valeur par défaut). Si l'API refuse le paramètre pour le modèle
  utilisé, l'appel est réessayé sans le paramètre et un avertissement est
  consigné dans le journal. **Note (issue #118) :** le modèle `claude-sonnet-5`
  n'accepte pas de température personnalisée (paramètre déprécié pour ce
  modèle) — avec ce modèle, la variable `CHESSCOACH_CLAUDE_TEMPERATURE` n'a
  donc aucun effet, et la comparaison Claude/Mistral ne peut pas être faite à
  température identique tant que ce modèle est utilisé.
- `CHESSCOACH_MISTRAL_TEMPERATURE` : température pour les appels à Mistral.
  Valeur par défaut : 0.0 (comportement initial). Une valeur invalide (non
  numérique, hors plage acceptée) est ignorée avec un avertissement dans les
  logs, et la valeur par défaut s'applique. Si l'API Mistral refuse le
  paramètre pour le modèle utilisé, l'appel est réessayé sans le paramètre et
  un avertissement est consigné dans le journal.

La température réellement envoyée (ou "defaut API" quand rien n'est envoyé) est
consignée dans chaque entrée des journaux `coach_calls*.log` pour les deux
agents, sous le champ `temperature`. Le script `scripts/coach_ratings_report.py`
affiche désormais la température à côté du modèle pour chaque avis, permettant
de tracer précisément les conditions de chaque appel.
