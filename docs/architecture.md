# Architecture — PROJECT RESILIENCE-ALPHA

## Correspondance biologie → technique

| Mécanisme biologique | Composant | Rôle |
|---|---|---|
| Peau | `waf` (nginx) + `web` (interface PayAlpha) | Seul point exposé (hotspot), limite le débit, bloque les signatures connues |
| Globules blancs | `detector` | IsolationForest sur métriques/journaux + règles SIEM → score d'anomalie et alertes |
| Anticorps | Signatures WAF + règles SIEM (R1–R5) | Association menace → réponse qualifiée |
| Cerveau / système nerveux | `remediator` | Machine à états, choisit l'échelle d'actions et vérifie la reprise |
| Muscle | `actuator` | Seul détenteur du socket Docker, 3 actions en liste blanche |
| Cicatrisation | Échelles graduées (voir `echelle-actions.md`) | Réparation graduée, la moins invasive d'abord |
| Mémoire immunitaire | `remdata/incidents.jsonl` + historique dans `/state` | Journal d'incidents ; ne réentraîne jamais automatiquement le modèle |
| Système nerveux conscient | `assistant` (RAG, Ollama local) | Aide à la compréhension, lecture seule, isolé du reste |

## Réseaux Docker (isolation = système lymphatique)

| Réseau | Membres | Sortie internet |
|---|---|---|
| `edge` | waf, grafana, dashboard, assistant-ui | Oui (seul réseau non `internal`) |
| `internal` | waf, web, api, auth, db, remediator | Non |
| `obs` | api, auth, remediator, detector, prometheus, loki, promtail, grafana | Non |
| `control` | remediator, actuator, detector, dashboard | Non — **l'actuator n'est joignable que depuis ce réseau** |
| `assist` | remediator (lecture de `/state` uniquement), ollama, assistant, assistant-ui | Non |
| `logs` | promtail, docker-ro | Non — lecture seule du socket Docker, séparée du reste |

Seul le WAF publie un port sur le réseau du hotspot (`8080`) ; Grafana, le dashboard et l'assistant ne
sont publiés que sur `127.0.0.1` (accès depuis le PC Hôte uniquement, pour le jury).

## Pourquoi le moteur de remédiation n'a pas le socket Docker

Donner au composant de décision un accès direct à l'infrastructure (socket Docker) reviendrait à
construire, par facilité, une interface d'administration accessible depuis le composant le plus
exposé à une logique d'attaquant (celui qui décide en réaction à un trafic hostile). Le `remediator`
appelle donc un `actuator` dédié, authentifié par jeton, qui n'expose que : redémarrer `api`, `auth`
ou `db`, recharger le WAF, lire le statut des services. Aucune création de conteneur, aucun `exec`,
aucun montage arbitraire — la surface est testée (`actuator/tests/test_logic.py`).

## Boucle immunitaire (états)

`HOMEOSTASIS` → `SURVEILLANCE` (une fenêtre suspecte) → `IMMUNITY` (3 fenêtres anormales consécutives
ou règle SIEM déclenchée : incident qualifié) → `REGENERATION` (action appliquée + vérification par
sonde) → `RESTORED` (3 sondes de transaction réussies d'affilée) → `HOMEOSTASIS` (après un palier de
stabilisation), ou `CONTAINED` si la source de l'incident persiste sans plus affecter le service. Si
la vérification échoue à chaque étage de l'échelle → `ESCALATION` (seul état où une intervention
humaine est attendue — voir `assistant/corpus/runbooks/que-faire-si-escalation.md`).

## Trois scénarios d'attaque, trois échelles de réponse

1. **Surcharge d'un compte** (déni de service applicatif) : limitation de débit → suspension du
   compte → bannissement IP (si fiable) → redémarrage.
2. **Brute-force sur la connexion** : confinement d'une compromission probable → verrouillage du
   compte ciblé → limitation du débit de connexion (si fiable) → redémarrage de l'authentification.
3. **Panne de service** (chien de garde, indépendant du détecteur ML) : redémarrage direct du service
   en défaut, détecté par l'échec répété de la sonde de transaction.

Détail des trois échelles : `assistant/corpus/runbooks/echelle-actions.md`.

## Pourquoi la limitation de débit est indexée sur le jeton, pas sur l'IP

Sous Docker Desktop, le trafic venant du PC Attaquant traverse une traduction d'adresse (NAT) avant
d'atteindre le conteneur WAF : l'adresse IP source vue par nginx n'est donc pas toujours celle du
poste attaquant. La zone de débit `pay` est indexée sur `$rl_key` (le jeton d'autorisation s'il est
présent, l'adresse sinon — voir `waf/nginx.conf`), et les actions par IP (`ban_ip`, `throttle_login`)
restent désactivées par défaut (`TRUST_SOURCE_IP=false`) tant qu'une vérification manuelle des
journaux du WAF n'a pas confirmé la fiabilité de l'adresse source dans l'environnement de démo.

## Régulation (anti-emballement)

- Anti-boucle : 2 redémarrages par service max / 10 min, 6 actions max / 10 min au total.
- Palier de stabilisation (`hold = 30 s`) avant de redescendre en `HOMEOSTASIS`.
- Relâchement automatique du débit et des bannissements après 2 minutes de calme confirmé.
- Comptes protégés jamais suspendus ni bannis (`probe`, `merchant`).

## Secrets

Tous les secrets (mots de passe DB, `JWT_SECRET`, jetons internes, clé HMAC des événements) vivent
dans un `.env` local généré par `scripts/gen_secrets.sh` (ou son équivalent PowerShell), jamais
commité (voir `docs/secrets.md`). Docker Compose le charge nativement ; aucun wrapper n'est
nécessaire pour démarrer la plateforme.
