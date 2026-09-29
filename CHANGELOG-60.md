# Changelog — Issue #60

## Détection tolérante de l'erreur « crédit épuisé » de l'API (suite de l'issue #54)

- Contexte : la détection introduite à l'issue #54 ne reconnaissait qu'une
  seule forme exacte (HTTP 403, `error.type == "billing_error"`). Des
  retours d'utilisateurs de l'API (2024-2025, non revérifiables sans
  épuiser réellement un crédit) indiquent qu'un solde insuffisant peut
  aussi se manifester en HTTP 400 `invalid_request_error` avec un message
  du type « Your credit balance is too low to access the Anthropic API.
  Please go to Plans & Billing to upgrade or purchase credits. » — un cas
  qui tombait auparavant dans l'erreur générique, sans le message clair ni
  le lien vers la Console.
- `llm_coach.py` (`_call_claude`, gestion de `urllib.error.HTTPError`) :
  la détection reconnaît désormais trois formes, sans se fier à un unique
  couple (code, type) :
  - `error.type == "billing_error"`, quel que soit le code HTTP ;
  - code HTTP 402, quel que soit `error.type` ;
  - code HTTP 400 avec `error.type == "invalid_request_error"` dont le
    message contient (insensible à la casse) « credit balance »,
    « insufficient credit » ou « plans & billing »/« plans and billing ».
  - Une vraie erreur de permission (403 `permission_error`) et une vraie
    requête invalide (400 sans mention de crédit) continuent de propager
    l'erreur HTTP normale (pas de `CreditInsuffisantError`).
  - Le message affiché à l'utilisateur (bulle dédiée + lien Console) est
    inchangé : tous les appelants attrapent `CreditInsuffisantError` de la
    même façon qu'avant.
- Docstrings de `CreditInsuffisantError` et `_call_claude`, et `CONTEXTE.md`,
  mis à jour pour refléter la détection élargie.
- Vérification par simulation locale (`urllib.request.urlopen` mocké, aucun
  appel réseau réel — voir la section « Limite » ci-dessous) : les 5 cas
  suivants ont été rejoués et donnent le résultat attendu :
  1. HTTP 403 `billing_error` (forme historique) → `CreditInsuffisantError`.
  2. HTTP 402 `invalid_request_error` → `CreditInsuffisantError`.
  3. HTTP 400 `invalid_request_error`, message « Your credit balance is too
     low ... Plans & Billing ... » → `CreditInsuffisantError`.
  4. HTTP 403 `permission_error` (vraie erreur de permission) →
     `HTTPError` propagée normalement, PAS de `CreditInsuffisantError`.
  5. HTTP 400 `invalid_request_error` sans mention de crédit (« messages:
     at least one message is required ») → `HTTPError` propagée
     normalement, PAS de `CreditInsuffisantError`.
- Limite assumée : cette vérification simule le corps de réponse HTTP tel
  que rapporté par des utilisateurs de l'API ; elle ne constitue pas un
  test sur une vraie réponse de crédit épuisé (impossible à provoquer sans
  épuiser réellement le crédit de la clé API). Si la forme réelle
  divergeait encore de ces trois hypothèses, un nouvel ajustement resterait
  possible.
