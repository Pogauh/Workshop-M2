#!/usr/bin/env python3
"""Test de bout en bout du cycle immunitaire : provoque une surcharge (DoS applicatif) et vérifie que le système se
rétablit SEUL (ND 0/5 sur l'axe 1 si une intervention humaine est nécessaire). Nécessite la plateforme ET le profil
« lab » démarrés, et le mot de passe du compte attacker.
  python3 tests/e2e_demo.py --attacker-password "$(sed -n 's/^ATTACKER_PASSWORD=//p' .env)"
Durée : jusqu'à ~3 minutes (attaque 30 s + fenêtre de vérification)."""
import argparse, subprocess, sys, time
import httpx

ap = argparse.ArgumentParser()
ap.add_argument("--target", default="http://localhost:8080")
ap.add_argument("--state-url", default="http://localhost:9000/state", help="port du moteur publié localement pour ce test")
ap.add_argument("--attacker-password", required=True)
ap.add_argument("--attack-seconds", type=int, default=30)
ap.add_argument("--timeout", type=int, default=150)
a = ap.parse_args()


def state():
    return httpx.get(a.state_url, timeout=5).json()


def main():
    print("État initial :", state()["state"])
    print(f"Lancement de l'attaque ({a.attack_seconds} s)...")
    proc = subprocess.Popen(["python3", "attacker/flood.py", "--target", a.target, "--password", a.attacker_password,
                             "--seconds", str(a.attack_seconds), "--threads", "40"])

    deadline = time.time() + a.timeout
    seen_defense = False
    while time.time() < deadline:
        s = state()
        if s["state"] in ("IMMUNITY", "REGENERATION", "RESTORED"):
            seen_defense = True
        if s["state"] == "RESTORED" and not s.get("busy"):
            proc.wait(timeout=5)
            mttr = s.get("last_mttr")
            print(f"RÉTABLI sans intervention humaine. MTTR mesuré : {mttr} s")
            sys.exit(0)
        if s["state"] == "ESCALATION":
            print("ESCALADE : la reprise n'a pas pu être vérifiée automatiquement (vérifier le détecteur/modèle)."); sys.exit(1)
        time.sleep(2)
    proc.terminate()
    print("ÉCHEC : pas de rétablissement vérifié dans le délai imparti.", "(une défense a été observée)" if seen_defense else "(aucune défense observée : le modèle est-il chargé ?)")
    sys.exit(1)


if __name__ == "__main__":
    main()
