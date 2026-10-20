# API — référence rapide

Toutes les routes passent par le WAF (`http://10.136.206.89:8080` en démonstration,
`http://localhost:8080` en local). Les routes `/internal/*` (authentification) et `/api/health/deep`
(API) ne sont jamais routées par le WAF : elles ne sont joignables que depuis le réseau interne, par
le moteur de remédiation.

## Authentification — `auth` (préfixe `/auth`)
| Méthode | Route | Description |
|---|---|---|
| POST | `/auth/login` | `{username, password}` → `{token, expires_in}` (JWT, 15 min). 401 si invalide, 423 si verrouillé, 403 si suspendu ou réinitialisation requise. |

## Paiements — `api` (préfixe `/api`, jeton `Authorization: Bearer <token>` requis sauf `/api/health`)
| Méthode | Route | Description |
|---|---|---|
| POST | `/api/payments` | `{to, amount, label?}` + en-tête `Idempotency-Key` (8–64 caractères). 201 à la création, 200 si la clé a déjà été traitée (aucun double débit), 402 si solde insuffisant. |
| GET | `/api/payments?limit=20` | Historique de l'utilisateur connecté (20 par défaut, 50 max). |
| GET | `/api/payments/{id}` | Détail d'un paiement dont l'utilisateur est l'émetteur ou le bénéficiaire. |
| GET | `/api/accounts/me` | Solde et nom affiché du compte connecté. |
| GET | `/api/beneficiaries` | Liste des bénéficiaires possibles (hors soi-même, `probe`, `attacker`). |
| GET | `/api/health` | Vivacité simple (sans authentification). |

## Validation des entrées (schéma `PaymentIn`)
- `to` : `^[a-z0-9_]+$`, 1 à 32 caractères.
- `amount` : décimal strictement positif, 2 décimales maximum, 10 000 au plus.
- `label` : `^[\w .,'()\-]*$`, 64 caractères au plus, facultatif.

## Supervision (lecture seule, non authentifiée sur `localhost`)
| Méthode | Route | Service | Description |
|---|---|---|---|
| GET | `/state` | `remediator:9000` | État complet du moteur (consommé par le dashboard et l'assistant). |
| GET | `/incidents?n=50` | `remediator:9000` | Derniers incidents journalisés. |
| GET | `/metrics` | `api`, `auth`, `remediator`, `detector:9100` | Métriques Prometheus. |
| POST | `/ask` | `assistant:8500` | `{question}` → réponse du RAG local (lecture seule, aucune action). |

## Événements du détecteur vers le moteur de remédiation
`POST /event` (interne, signé HMAC-SHA256 avec `EVENT_HMAC_KEY`, en-tête `X-Signature`) : le détecteur
y envoie un évènement toutes les ~5 secondes (`kind`, `score`, `features`, `suspects`, `alerts`). Un
évènement non signé, signé avec une mauvaise clé, ou daté de plus de 30 secondes est rejeté (401).
