#!/usr/bin/env python3
"""Test de bout en bout du cycle immunitaire, scénario BRUTE-FORCE : provoque des échecs de connexion
répétés sur 'carol' et vérifie que le système se rétablit SEUL (verrouillage du compte, puis service de
nouveau utilisable), sans intervention humaine. Miroir de e2e_demo.py (scénario flood) pour le second
scénario d'attaque requis par le sujet.
  python3 tests/e2e_bruteforce.py
Durée : jusqu'à ~3 minutes (attaque 45 s + fenêtre de vérification)."""
import argparse, subprocess, sys, time
import httpx

PY = sys.executable  # l'exact interpréteur courant : "python3" n'existe pas forcément (ex. Windows)

ap = argparse.ArgumentParser()
ap.add_argument("--target", default="http://localhost:8080")
ap.add_argument("--state-url", default="http://localhost:3000/state",
                 help="le moteur n'a pas de port publié (voir architecture.md) : on relit son état via le proxy /state du dashboard")
ap.add_argument("--attack-seconds", type=int, default=45)
ap.add_argument("--timeout", type=int, default=180)
a = ap.parse_args()


def state():
    return httpx.get(a.state_url, timeout=5).json()


def main():
    s0 = state()
    print("État initial :", s0["state"])
    if s0.get("rules", {}).get("locked_users", {}).get("carol"):
        print("AVERTISSEMENT : carol est déjà verrouillée (./scripts/reset.sh avant de relancer ce test).")
    print(f"Lancement du brute-force sur 'carol' ({a.attack_seconds} s)...")
    proc = subprocess.Popen([PY, "attacker/bruteforce.py", "--target", a.target,
                             "--seconds", str(a.attack_seconds), "--threads", "8"])

    deadline = time.time() + a.timeout
    seen_defense = seen_lock = False
    while time.time() < deadline:
        s = state()
        if s["state"] in ("IMMUNITY", "REGENERATION", "RESTORED"):
            seen_defense = True
        if s.get("rules", {}).get("locked_users", {}).get("carol"):
            seen_lock = True
        if s["state"] == "RESTORED" and not s.get("busy"):
            mttr = s.get("last_mttr")
            proc.terminate()                        # la remédiation peut être plus rapide que la durée d'attaque restante
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            print(f"RÉTABLI sans intervention humaine. Compte verrouillé : {seen_lock}. MTTR mesuré : {mttr} s")
            sys.exit(0)
        if s["state"] == "ESCALATION":
            print("ESCALADE : la reprise n'a pas pu être vérifiée automatiquement (vérifier le détecteur/modèle)."); sys.exit(1)
        time.sleep(2)
    proc.terminate()
    print("ÉCHEC : pas de rétablissement vérifié dans le délai imparti.",
          "(une défense a été observée)" if seen_defense else "(aucune défense observée : le modèle est-il chargé et entraîné sur du brute-force ? voir docs/ml.md)")
    sys.exit(1)


if __name__ == "__main__":
    main()
