#!/usr/bin/env python3
"""Trafic normal et DOUX de la plateforme PayAlpha : fait vivre la démo et sert de référence à l'entraînement du détecteur
(scripts/bootstrap_model.sh --label normal). Variance volontaire des connexions (carol se reconnecte, de rares échecs de
frappe) : un détecteur entraîné sur un trafic trop constant confondrait la moindre variation avec une anomalie.

Variables d'environnement (service « traffic », profil lab) avec équivalents en option de ligne de commande :
  TARGET (--target)  DEMO_PASSWORD (--demo-password)  WEAK_PASSWORD (--weak-password)  RPS (--rps)  DURATION_S (--seconds, 0=infini)
"""
import argparse, os, random, threading, time
import httpx

ap = argparse.ArgumentParser()
ap.add_argument("--target", default=os.getenv("TARGET", "http://localhost:8080"))
ap.add_argument("--demo-password", default=os.getenv("DEMO_PASSWORD"))
ap.add_argument("--weak-password", default=os.getenv("WEAK_PASSWORD"))
ap.add_argument("--rps", type=float, default=float(os.getenv("RPS", "4")))
ap.add_argument("--seconds", type=int, default=int(os.getenv("DURATION_S", "0")))   # 0 = infini
a = ap.parse_args()
if not a.demo_password:
    raise SystemExit("mot de passe manquant : --demo-password ou $DEMO_PASSWORD")

USERS = {"alice": a.demo_password, "bob": a.demo_password, "carol": a.weak_password or a.demo_password}
LABELS = ["", "", "Courses", "Loyer", "Café", "Remboursement", "Cadeau", "Abonnement", "Covoiturage"]
tokens, lock = {}, threading.Lock()


def login(c, user):
    pwd = USERS[user]
    if random.random() < 0.015:                               # bruit réaliste : rare faute de frappe, PAS une attaque
        pwd = pwd[:-1] + ("x" if pwd[-1:] != "x" else "y")
    r = c.post(a.target + "/auth/login", json={"username": user, "password": pwd}, timeout=5)
    if r.status_code == 200:
        with lock:
            tokens[user] = r.json()["token"]


def renew_loop(stop_at):
    """Chaque utilisateur se reconnecte de temps en temps : fait varier login_rps / login_fail_rate (traits du détecteur)."""
    with httpx.Client() as c:
        for u in USERS:
            login(c, u)
        while stop_at is None or time.time() < stop_at:
            time.sleep(random.uniform(20, 60))
            login(c, random.choice(list(USERS)))


def pay_loop(stop_at):
    with httpx.Client(timeout=5) as c:
        while stop_at is None or time.time() < stop_at:
            u = random.choice(["alice", "bob", "carol"])
            with lock:
                tok = tokens.get(u)
            if tok:
                to = "merchant" if random.random() < 0.75 else random.choice([x for x in ("alice", "bob", "carol") if x != u])
                try:
                    c.post(a.target + "/api/payments", json={"to": to, "amount": round(random.uniform(1, 60), 2),
                           "label": random.choice(LABELS)}, headers={"Authorization": "Bearer " + tok})
                except Exception:
                    pass
            time.sleep(max(0.05, random.expovariate(a.rps)))


if __name__ == "__main__":
    end = time.time() + a.seconds if a.seconds else None
    print(f"trafic normal -> {a.target} (~{a.rps} req/s, {'infini' if not a.seconds else f'{a.seconds}s'})", flush=True)
    threading.Thread(target=renew_loop, args=(end,), daemon=True).start()
    pay_loop(end)
