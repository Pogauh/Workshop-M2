# PC Attaquant — a lancer DEPUIS la machine attaquante, jamais depuis le PC Hote
Cible: http://192.168.137.1:8080 (adapter l'IP si besoin). Aucun outil defensif sur ce poste.

## Scénarios

1. **Déni de service applicatif** (`flood.py`) : charge soutenue sur `/api/payments` avec le compte `attacker`.
   `python flood.py --password "$(sed -n 's/^ATTACKER_PASSWORD=//p' .env)"`
2. **Injection** (`sqli_probe.py`, bonus) : doit être bloquée par le WAF (403), jamais par l'API.
3. **Brute-force sur la connexion** : le compte `carol` utilise volontairement `WEAK_PASSWORD` (voir `.env`).
   Côté défense : verrouillage avant bcrypt, règles SIEM R2/R3, confinement de compromission (voir `docs/ebios-rm.md`).
   Pour la démonstration en direct, un outil de brute-force standard (par ex. Hydra, installé sur le PC Attaquant,
   hors de ce dépôt) pointé sur `POST /auth/login` avec `{"username":"carol","password":"<essai>"}` suffit à
   déclencher la chaîne complète : verrouillage du compte, puis, si une connexion finit par réussir après la
   série d'échecs, confinement de la compromission (révocation des sessions, mot de passe à réinitialiser).

Conteneurisé (profil `lab`, réseau interne — à utiliser pour reproduire une attaque dans le laboratoire Docker plutôt
que depuis un second poste) :
```
docker compose --profile lab run --rm attacker python flood.py --password "$(sed -n 's/^ATTACKER_PASSWORD=//p' .env)" --target http://waf:8080
```
