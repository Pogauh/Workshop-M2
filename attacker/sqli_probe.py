#!/usr/bin/env python3
"""Attaque secondaire (bonus): tentative d'injection, doit etre bloquee par le WAF (403), pas par l'API."""
import argparse, httpx
ap = argparse.ArgumentParser(); ap.add_argument("--target", default="http://192.168.137.1:8080")
a = ap.parse_args()
payloads = ["' OR 1=1 --", "' UNION SELECT NULL--", "<script>alert(1)</script>", "../../etc/passwd"]
for p in payloads:
    r = httpx.get(a.target + "/api/payments/" + p, timeout=5)
    print(p, "->", r.status_code, "(403 attendu = bloque par le WAF)")
