# Protocole de mesure — résilience et chaos engineering

Ce document est un **protocole à exécuter avec la plateforme réellement démarrée** (impossible depuis
un environnement sans Docker) : il donne la méthode et les tableaux à remplir avec les chiffres
observés, pour le Dossier.pdf (section mesures) et pour `docs/pca-pra.md` (RTO/RPO).

## Préparation
```
./scripts/gen_secrets.sh && docker compose up -d --build
./scripts/bootstrap_model.sh           # entraîne le modèle ML sur du trafic réel (~20 min)
```

## 1. Surcharge applicative (DoS)
```
./scripts/repeat_demo.sh dos
```
Répéter 5 fois (`./scripts/reset.sh` entre chaque essai). Relever, pour chaque essai, depuis le
dashboard ou `GET /state` :

| Essai | Détecté après (s) | Actions appliquées | Rétabli après (s, MTTR) | Escalade ? |
|---|---|---|---|---|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |
| 4 | | | | |
| 5 | | | | |

## 2. Brute-force sur la connexion
```
python attacker/bruteforce.py --target http://10.136.206.89:8080 --threads 8 --seconds 60
```
(ou tout autre outil, voir `attacker/README.md` pour un exemple Hydra). Répéter 5 fois pendant que la
plateforme tourne. Même tableau que ci-dessus, en notant en plus si le compte a été verrouillé avant ou
après une connexion réussie (confinement de compromission, voir `echelle-actions.md` — pour forcer ce
cas en répétable : `--real-password "$WEAK_PASSWORD" --succeed-after 40`).

## 3. Injection (bonus)
```
python attacker/sqli_probe.py --target http://10.136.206.89:8080
```
Vérifier que les 4 charges utiles reçoivent un `403` (bloquées par le WAF, jamais par l'API).

## 4. Panne franche (chien de garde, sans attaque)
```
ansible-playbook ansible/chaos.yml                       # service au hasard
ansible-playbook ansible/chaos.yml -e chaos_service=db    # service choisi
```
Répéter pour `api`, `auth`, `db`. Relever le temps de détection et de redémarrage pour chacun.

| Service tué | Détecté après (s) | Redémarré après (s) | Rétabli et vérifié après (s) |
|---|---|---|---|
| api | | | |
| auth | | | |
| db | | | |

## 5. Non-régression automatisée
```
python3 tests/smoke.py --target http://localhost:8080
python3 tests/e2e_demo.py --attacker-password "$(sed -n 's/^ATTACKER_PASSWORD=//p' .env)"   # flood
python3 tests/e2e_bruteforce.py                                                              # brute-force
```
Les deux `e2e_*` échouent (code non nul) si le système n'atteint pas `RESTORED` sans intervention
humaine dans le délai imparti — ce sont les tests qui protègent l'axe « remédiation autonome » de la
grille du jury, un par type d'attaque.

## Synthèse à reporter dans le Dossier.pdf
- RTO observé = moyenne des MTTR mesurés ci-dessus, par scénario.
- Taux de faux positifs et de détection par type d'attaque : `detector/model/report.json`, produit par
  `scripts/bootstrap_model.sh` / `scripts/export_model.sh`.
- Nombre d'essais nécessaires avant d'obtenir une reprise fiable sans `ESCALATION` (répétabilité).
