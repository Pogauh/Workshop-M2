# PROJECT RESILIENCE-ALPHA — système immunitaire numérique

PayAlpha, une plateforme de paiement fictive, qui se défend et se répare **seule** : détection par
apprentissage automatique et règles SIEM, décision, action, vérification par une vraie transaction —
sans intervention humaine sur le chemin nominal. Voir `docs/architecture.md` pour le détail.

## Prérequis (PC Hôte)
Windows 10/11, Docker Desktop (backend WSL2 recommandé), 16 Go RAM minimum (10 Go alloués à WSL2, voir
`.wslconfig.example`), 50 Go libres. Rien d'autre à installer pour les secrets : un `.env` local
généré par script (voir `docs/secrets.md`). Hotspot Windows nommé `RESILIENCE-G<n>`, IP du PC Hôte
`192.168.137.1`. Détail pas à pas : `docs/windows-setup.md`.

## Démarrage
```bash
./scripts/gen_secrets.sh                  # Linux/macOS/WSL — ou scripts\windows\gen_secrets.ps1
docker compose up -d --build              # démarre la plateforme (.env chargé nativement par Compose)
```
Vérifier : `curl http://localhost:8080/api/health` → `{"status":"ok"}`.

- **Interface de paiement (PayAlpha)** : `http://localhost:8080`
- **Console de supervision** (jury) : `http://localhost:3000`
- **Grafana** (métriques et journaux détaillés) : `http://localhost:3001`

Ou via Ansible : `ansible-playbook -i ansible/inventory.ini ansible/deploy.yml` (vérifie les secrets,
construit, démarre, attend que l'API réponde).

## Comptes de démonstration
| Compte | Rôle | Mot de passe |
|---|---|---|
| `alice`, `bob`, `merchant` | Clients normaux | `DEMO_PASSWORD` |
| `carol` | Mot de passe volontairement faible (scénario brute-force) | `WEAK_PASSWORD` |
| `attacker` | Compte client valide utilisé pour le scénario de surcharge | `ATTACKER_PASSWORD` |
| `probe` | Sonde de santé interne (jamais suspendu ni banni) | `PROBE_PASSWORD` |

`sed -n 's/^<NOM_DE_VARIABLE>=//p' .env` affiche une valeur précise (ex. pour le PC Attaquant).
Soldes de départ : 100 000 chacun, invariant total **600 000** vérifié par `/api/health/deep`.

## Entraîner le détecteur ML
```bash
./scripts/bootstrap_model.sh              # trafic normal + flood + brute-force, entraîne et évalue (~20 min)
./scripts/export_model.sh                 # embarque le modèle dans detector/model/ pour le livrable
```
Le rapport (`detector/model/report.json`) donne le taux de faux positifs et le rappel par type
d'attaque — à joindre au Dossier.pdf (section IA/Data, voir `docs/dossier-outline.md`).

## Les trois scénarios d'attaque
1. **Surcharge applicative** (`attacker/flood.py`) — compte `attacker`, charge soutenue sur les
   paiements.
2. **Brute-force sur la connexion** — essais répétés sur le compte `carol` (mot de passe faible),
   avec un outil que vous choisissez (voir `attacker/README.md`) ; déclenche verrouillage, puis
   confinement de compromission si une connexion finit par réussir.
3. **Injection** (`attacker/sqli_probe.py`, bonus) — doit être bloquée par le WAF, jamais par l'API.

Répéter rapidement un scénario pour la vidéo chronométrée : `./scripts/repeat_demo.sh dos` (ou
`brute`). Réinitialiser entre deux essais : `./scripts/reset.sh`.

## Panne franche (sans attaque)
```bash
ansible-playbook ansible/chaos.yml                       # tue un service au hasard
ansible-playbook ansible/chaos.yml -e chaos_service=db    # service choisi
```
Vérifie que le chien de garde du moteur de remédiation redémarre seul le service.

## Limite connue : IP source sous Docker Desktop
L'adresse source vue par le WAF peut être celle du NAT interne de Docker Desktop, pas celle du PC
Attaquant. **Vérifiez-le avant la démonstration** (regardez `ip`/`remote_addr` dans les journaux du
WAF pendant un essai). Si l'IP n'est pas fiable, laissez `TRUST_SOURCE_IP=false` (valeur par défaut) :
le bannissement par IP est alors désactivé et le système s'appuie sur la suspension de compte, le
verrouillage et la limitation de débit par jeton, qui restent efficaces et fiables sous NAT.

## Secrets
Voir `docs/secrets.md`. En résumé : un `.env` local généré par `scripts/gen_secrets.sh`, en clair,
jamais commité. Avant toute livraison : `./scripts/check_secrets.sh`.

## Organisation du dépôt
```
web/              -> développement (interface de paiement PayAlpha, React/Tailwind)
api/ auth/        -> développement (microservices métier)
waf/              -> cybersécurité (première ligne de défense)
detector/         -> IA/Data (détection ML + règles SIEM)
remediator/       -> développement + cybersécurité (décision, échelles d'actions, vérification)
actuator/         -> cybersécurité (seul composant avec le socket Docker, actions en liste blanche)
dashboard/        -> développement (supervision « signes vitaux » pour le jury)
monitoring/       -> infrastructure (Prometheus/Grafana/Loki)
attacker/ traffic/ -> cybersécurité / IA-Data (scénarios et données d'entraînement)
ansible/          -> infrastructure (déploiement, durcissement, sauvegarde, chaos engineering)
assistant/        -> transformation / IA (assistant local en lecture seule)
docs/             -> transformation (architecture, EBIOS RM, PCA/PRA, NIS2/DORA, protocole de mesure)
tests/            -> tous domaines (vérifications structurelles + tests de bout en bout)
```

## Assistant IA local (Ollama + LangChain + RAG)
Aide les opérateurs à comprendre un incident. **Lecture seule** : isolé sur son propre réseau Docker
`assist`, sans aucun accès à l'`actuator`, à la base ou aux secrets. Il ne lit que `GET /state` du
moteur de remédiation (en direct) et un corpus documentaire versionné (`assistant/corpus/` + `docs/`).
```bash
docker compose --profile ai up -d
./scripts/setup_assistant.sh          # télécharge les modèles + construit l'index RAG (une fois)
```
Interface : `http://localhost:3002`. Après avoir modifié un document du corpus :
`docker compose exec assistant python -m app.ingest` (ou `POST /reindex`). Voir
`assistant/corpus/runbooks/perimetre.md` pour le détail des garanties d'isolation, et `memoire.md`
pour l'absence volontaire de réentraînement automatique.

Si le PC Hôte est sous forte charge mémoire, déportez `ollama` sur le PC de délestage IA optionnel :
changez `OLLAMA_URL` vers l'IP de ce poste et lancez-y uniquement le conteneur `ollama`.

## Vérifications avant livraison
```bash
python3 tests/smoke.py                 # plateforme démarrée : chemin nominal
python3 tests/e2e_demo.py --attacker-password "$(sed -n 's/^ATTACKER_PASSWORD=//p' .env)"
./scripts/check_secrets.sh
./scripts/package.sh G<n>              # construit Workshop2026-M2-G<n>-Code.zip sans secrets
```
Protocole complet de mesure (RTO, taux de détection, répétabilité) : `docs/tests-chaos.md`.
Préparation du clip chronométré : `docs/clip-chrono.md`. Plan du dossier : `docs/dossier-outline.md`.
Questions probables du jury : `docs/qa-jury.md`.

## Ce qu'il reste à faire par l'équipe avant la remise
- [ ] Vérifier `TRUST_SOURCE_IP` sur le PC Hôte réel (voir section ci-dessus).
- [ ] Faire tourner `scripts/bootstrap_model.sh` sur le vrai PC Hôte et reporter les chiffres réels
      dans le Dossier.pdf (ce dépôt ne contient que la méthode, pas des résultats inventés).
- [ ] Répéter chaque scénario au moins 10 fois pour fiabiliser le Clip Chrono (≤ 60 s, sans coupure).
- [ ] `docker compose config` et un démarrage complet avant le gel du code (jeudi 17h).
