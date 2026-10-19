#!/usr/bin/env python3
"""Test de fumée : la plateforme tourne (docker compose up -d) et répond correctement sur le chemin nominal.
  python3 tests/smoke.py [--target http://localhost:8080]
Ne nécessite que httpx (installé dans le conteneur detector ou remediator : docker compose exec detector python -m tests.smoke,
depuis la racine montée, ou en local avec `pip install httpx`)."""
import argparse, sys, time, uuid
import httpx

ap = argparse.ArgumentParser()
ap.add_argument("--target", default="http://localhost:8080")
ap.add_argument("--password", default=None, help="DEMO_PASSWORD (sinon : lu depuis .env à la racine du dépôt)")
a = ap.parse_args()

checks = []


def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(("OK  " if ok else "ÉCHEC"), name, (f"({detail})" if detail and not ok else ""))


def main():
    pwd = a.password
    if not pwd:
        try:
            with open(".env") as f:
                for line in f:
                    if line.startswith("DEMO_PASSWORD="):
                        pwd = line.strip().split("=", 1)[1]
                        break
        except FileNotFoundError:
            pass
    if not pwd:
        print("mot de passe introuvable : passez --password ou lancez depuis la racine du dépôt (fichier .env)"); sys.exit(2)

    with httpx.Client(base_url=a.target, timeout=10) as c:
        r = c.get("/api/health"); check("API saine", r.status_code == 200, str(r.status_code))
        r = c.get("/"); check("Interface de paiement servie", r.status_code == 200, str(r.status_code))

        r = c.post("/auth/login", json={"username": "alice", "password": "mauvais-mot-de-passe"})
        check("Identifiants invalides rejetés (401)", r.status_code == 401, str(r.status_code))

        r = c.post("/auth/login", json={"username": "alice", "password": pwd})
        check("Connexion légitime acceptée", r.status_code == 200, str(r.status_code))
        token = r.json().get("token") if r.status_code == 200 else None
        if not token:
            print("arrêt : pas de jeton, les contrôles suivants sont ignorés"); _finish(); return
        h = {"Authorization": "Bearer " + token}

        r = c.get("/api/accounts/me", headers=h); check("Solde accessible", r.status_code == 200, str(r.status_code))
        r = c.get("/api/beneficiaries", headers=h); check("Bénéficiaires accessibles", r.status_code == 200, str(r.status_code))

        key = uuid.uuid4().hex
        r1 = c.post("/api/payments", json={"to": "merchant", "amount": "0.01", "label": "smoke"}, headers={**h, "Idempotency-Key": key})
        check("Paiement créé (201)", r1.status_code == 201, str(r1.status_code))
        r2 = c.post("/api/payments", json={"to": "merchant", "amount": "0.01", "label": "smoke"}, headers={**h, "Idempotency-Key": key})
        check("Rejeu idempotent sans double débit (200, même id)", r2.status_code == 200 and r1.json().get("id") == r2.json().get("id"),
              f"{r2.status_code}, id={r2.json().get('id')}")

        r = c.get("/api/payments/" + "' OR 1=1 --")
        check("Injection bloquée par le WAF (403)", r.status_code == 403, str(r.status_code))
        r = c.get("/auth/login")
        check("Chemin interne non routé (health/deep)", c.get("/api/health/deep").status_code == 404)

    _finish()


def _finish():
    failed = [n for n, ok, _ in checks if not ok]
    print(f"\n{len(checks) - len(failed)}/{len(checks)} contrôles réussis")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
