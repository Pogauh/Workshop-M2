# PC Attaquant — a lancer DEPUIS la machine attaquante, jamais depuis le PC Hote
Cible: http://10.136.206.89:8080 (adapter l'IP si besoin). Aucun outil defensif sur ce poste.
Nécessite seulement Python 3 + `pip install -r requirements.txt` (httpx) sur le PC Attaquant, pas de build Docker.

## Scénarios

1. **Déni de service applicatif** (`flood.py`) : charge soutenue sur `/api/payments` avec le compte `attacker`.
   ```
   python flood.py --target http://10.136.206.89:8080 --password "$(sed -n 's/^ATTACKER_PASSWORD=//p' .env)"
   ```
2. **Injection** (`sqli_probe.py`, bonus) : doit être bloquée par le WAF (403), jamais par l'API.
3. **Brute-force sur la connexion** (`bruteforce.py`) : le compte `carol` utilise volontairement `WEAK_PASSWORD`
   (voir `.env`). Côté défense : verrouillage avant bcrypt, règles SIEM R2/R3, confinement de compromission
   (voir `docs/ebios-rm.md`). Inclus dans le dépôt (aucun outil externe requis) :
   ```
   python bruteforce.py --target http://10.136.206.89:8080 --threads 8 --seconds 60
   ```
   Pour déclencher EN PLUS la compromission probable (R3 : échecs en rafale puis succès -> confinement, sessions
   révoquées, mot de passe à réinitialiser), donnez le vrai mot de passe et le rang de l'essai gagnant :
   ```
   python bruteforce.py --target http://10.136.206.89:8080 --real-password "$(sed -n 's/^WEAK_PASSWORD=//p' .env)" --succeed-after 40 --seconds 60
   ```
   Alternative avec un outil standard (ex. Hydra) pointé sur `POST /auth/login`, body JSON
   `{"username":"carol","password":"<essai>"}` — utile si vous voulez rejouer l'entraînement avec un outil externe :
   ```
   hydra -l carol -P wordlist.txt -s 8080 10.136.206.89 http-post-form \
     "/auth/login:{\"username\":\"^USER^\",\"password\":\"^PASS^\"}:F=bad credentials:H=Content-Type: application/json"
   ```
   Les deux approches déclenchent la même chaîne de défense : verrouillage du compte, puis, si une connexion finit
   par réussir après la série d'échecs, confinement de la compromission.

Conteneurisé (profil `lab`, réseau interne — à utiliser pour reproduire une attaque dans le laboratoire Docker plutôt
que depuis un second poste, ou pour regénérer les données d'entraînement : voir `scripts/bootstrap_model.sh`) :
```
docker compose --profile lab run --rm attacker python flood.py --password "$(sed -n 's/^ATTACKER_PASSWORD=//p' .env)" --target http://waf:8080
docker compose --profile lab run --rm attacker python bruteforce.py --target http://waf:8080 --seconds 60
```
