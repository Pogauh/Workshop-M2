# Préparation du PC Hôte (Windows)

## Prérequis
- **Docker Desktop** (backend WSL2 recommandé), avec au moins 10 Go de RAM alloués — voir
  `.wslconfig.example` si Docker Desktop tourne sur WSL2.
- **Ansible** : le plus simple est de l'exécuter depuis WSL2 (`sudo apt install ansible`) plutôt que
  nativement sous Windows.
- **Python 3.11+** si vous lancez les tests ou scripts Python directement sur l'hôte (sinon, tout
  tourne dans les conteneurs).

## Démarrage
```
scripts\windows\gen_secrets.ps1
docker compose up -d --build
```
Puis, si vous utilisez l'assistant IA local : `docker compose --profile ai up -d` et
`./scripts/setup_assistant.sh` (depuis WSL2) ou l'équivalent manuel (`ollama pull`, puis
`docker compose exec assistant python -m app.ingest`).

## Pare-feu, pendant la démonstration
Le PC Hôte doit être joignable depuis le PC Attaquant sur le port `8080` uniquement (voir
`scripts/windows/firewall.ps1`, à exécuter en Administrateur) :
```
scripts\windows\firewall.ps1 -Subnet 192.168.137.0/24
```

## Adresse IP du PC Hôte sur le hotspot
```
ipconfig                      # repérez l'adresse du point d'accès RESILIENCE-G<n>, ex. 10.136.206.89
```
Utilisée par `attacker/flood.py --target http://<cette-adresse>:8080` et dans les commandes de ce
dépôt qui mentionnent `10.136.206.89`.

## Problèmes fréquents
- **Docker Desktop lent / mémoire saturée** : réduisez le nombre de services démarrés (évitez le
  profil `ai` si l'assistant n'est pas nécessaire à la démonstration en cours) ou ajustez
  `.wslconfig`.
- **Port 8080 déjà utilisé** : un autre service Windows l'occupe ; libérez-le ou changez le mappage de
  port du service `waf` dans `docker-compose.yml` (et adaptez les scripts en conséquence).
