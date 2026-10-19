"""Tests du moteur de remédiation (sans réseau, sans Docker, horloge simulée).
Lancer :  cd remediator && python -m unittest discover -s tests -v
Ils documentent le comportement attendu de l'échelle d'actions, de l'anti-boucle et de la vérification."""
import os, sys, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.engine import Config, Engine, render_waf_rules     # noqa: E402


class FakeClock:
    def __init__(self): self.t = 1_000_000.0
    def now(self): return self.t
    def sleep(self, s): self.t += s


class FakeIO:
    def __init__(self, clock):
        self.clock, self.calls, self.journaled = clock, [], []
        self.probe_ok, self.defense = True, True
        self.services = {s: {"state": "running", "health": "healthy"} for s in ("waf", "api", "auth", "db")}
        self.heal_on_restart = True

    def emit(self, e): pass
    def journal(self, inc): self.journaled.append(inc)
    def load_journal(self, n): return []
    def write_rules(self, rules): self.calls.append(("rules", rules["pay_rate"], rules["login_rate"]))
    def reload_waf(self): self.calls.append(("reload",))
    def auth(self, action, payload): self.calls.append(("auth", action, payload["username"]))
    def services_status(self): return self.services

    def restart(self, svc):
        self.calls.append(("restart", svc))
        if self.heal_on_restart:
            self.probe_ok = True
            self.services[svc] = {"state": "running", "health": "healthy"}

    def probe(self):
        return {"ok": self.probe_ok, "ms": 40 if self.probe_ok else 3000, "detail": "", "ts": self.clock.now(),
                "tx": {"id": "tx-1", "amount": "0.01", "to": "merchant", "created": 201, "reread": 200, "consistent": True}}

    def login_defense_ok(self): return self.defense, "test"

    def names(self, kind): return [c for c in self.calls if c[0] == kind]


def dos_event(users=("attacker",), **kw):
    return {"ts": 0, "kind": "anomaly", "score": -0.2, "features": {"rps": 300, "login_fail_rate": 0},
            "suspects": {"users": list(users), "ips": ["172.18.0.1"], "targets": [], "compromised": []}, **kw}


def brute_event(targets=("alice",), compromised=()):
    return {"ts": 0, "kind": "anomaly", "score": -0.3, "features": {"rps": 80, "login_fail_rate": 25.0},
            "suspects": {"users": [], "ips": [], "targets": list(targets), "compromised": list(compromised)}}


class EngineBase(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock(); self.io = FakeIO(self.clock)
        self.e = Engine(self.io, Config(), clock=self.clock.now, sleep=self.clock.sleep)

    def actions(self): return [a["name"] for a in self.e.S["incident"]["actions"]]


class DosTests(EngineBase):
    def test_throttle_then_suspend_no_restart_when_service_recovers(self):
        self.e.run_incident(dos_event(), "dos")
        self.assertEqual(self.actions(), ["throttle", "suspend_user"])
        self.assertEqual(self.e.S["state"], "RESTORED")
        self.assertEqual(self.io.names("restart"), [])
        self.assertIn(("auth", "suspend", "attacker"), self.io.calls)
        self.assertIsNotNone(self.e.S["incident"]["mttr_s"])
        self.assertEqual(len(self.io.journaled), 1)

    def test_persisting_attack_never_restarts_a_healthy_api(self):
        """Régression : un second incident sur une menace déjà contenue ne doit PAS redémarrer l'API."""
        self.e.run_incident(dos_event(), "dos")
        self.clock.sleep(self.e.cfg.hold + 1)
        self.e.S["busy"] = False
        self.e.run_incident(dos_event(), "dos")
        self.assertEqual(self.io.names("restart"), [])
        self.assertEqual(self.e.S["state"], "HOMEOSTASIS")          # rien de nouveau, rien de récent
        self.assertEqual(self.e.S["incident"]["attack"], "dos")      # le dernier incident réel reste affiché

    def test_contained_state_ignores_persisting_anomaly_but_reacts_to_new_threat(self):
        self.e.run_incident(dos_event(), "dos")
        self.clock.sleep(self.e.cfg.hold + 1)
        self.e.handle_event(dos_event())                             # l'anomalie persiste (429 loggués par le WAF)
        self.e.monitor_tick()
        self.assertEqual(self.e.S["state"], "CONTAINED")
        self.assertIsNone(self.e.handle_event(dos_event()))          # même menace : pas de nouvel incident
        self.assertEqual(self.e.handle_event(dos_event(users=("mallory",))), "dos")   # nouvel acteur : oui

    def test_contained_returns_to_homeostasis_after_quiet(self):
        self.e.run_incident(dos_event(), "dos")
        self.clock.sleep(self.e.cfg.hold + 1); self.e.handle_event(dos_event()); self.e.monitor_tick()
        self.assertEqual(self.e.S["state"], "CONTAINED")
        self.clock.sleep(self.e.cfg.quiet + 1); self.e.monitor_tick()
        self.assertEqual(self.e.S["state"], "HOMEOSTASIS")

    def test_escalation_when_service_never_recovers(self):
        self.io.probe_ok = False; self.io.heal_on_restart = False
        self.e.run_incident(dos_event(), "dos")
        self.assertEqual(self.actions(), ["throttle", "suspend_user", "restart_api"])
        self.assertEqual(self.e.S["state"], "ESCALATION")

    def test_restart_anti_loop_two_per_window(self):
        self.io.probe_ok = False; self.io.heal_on_restart = False
        for _ in range(4):
            self.e.run_incident(dos_event(), "dos"); self.clock.sleep(5)
        self.assertEqual(len(self.io.names("restart")), 2)

    def test_protected_and_invalid_users_are_never_suspended(self):
        self.assertIsNone(self.e.a_suspend(dos_event(users=("probe", "merchant", "x';drop table users;--"))))
        self.assertEqual(self.io.names("auth"), [])

    def test_ip_actions_disabled_without_trusted_source_ip(self):
        self.assertIsNone(self.e.a_ban(dos_event()))
        self.e.cfg.trust_ip = True
        self.assertIn("172.18.0.1", self.e.a_ban(dos_event()))
        self.assertIsNone(self.e.a_ban(dos_event()))                 # idempotent


class BruteForceTests(EngineBase):
    def test_classification(self):
        self.assertEqual(self.e.classify(brute_event()), "bruteforce")
        self.assertEqual(self.e.classify(dos_event()), "dos")

    def test_lock_targeted_account_and_verify_defense(self):
        self.e.run_incident(brute_event(), "bruteforce")
        self.assertEqual(self.actions(), ["lock_account"])
        self.assertIn(("auth", "lock", "alice"), self.io.calls)
        self.assertEqual(self.e.S["state"], "RESTORED")

    def test_compromise_is_contained_not_just_availability_restored(self):
        self.e.run_incident(brute_event(targets=("alice", "carol"), compromised=("carol",)), "bruteforce")
        self.assertEqual(self.actions(), ["contain_compromise", "lock_account"])
        for step in ("revoke", "force_reset", "lock"):
            self.assertIn(("auth", step, "carol"), self.io.calls)
        self.assertEqual(sum(1 for c in self.io.calls if c[:2] == ("auth", "lock") and c[2] == "carol"), 1)
        self.assertEqual(self.e.S["rules"]["compromised_users"], ["carol"])

    def test_escalation_if_attack_still_generates_failures(self):
        self.io.defense = False
        self.e.run_incident(brute_event(), "bruteforce")
        self.assertEqual(self.e.S["state"], "ESCALATION")

    def test_probe_account_is_never_locked(self):
        self.assertIsNone(self.e.a_lock_targets(brute_event(targets=("probe",))))

    def test_already_locked_target_is_not_a_new_threat(self):
        self.e.run_incident(brute_event(), "bruteforce")
        self.clock.sleep(self.e.cfg.hold + 1); self.e.S["last_anomaly"] = self.clock.now()
        self.e.monitor_tick()
        self.assertIsNone(self.e.handle_event(brute_event()))
        self.clock.sleep(self.e.cfg.lock_seconds + 1)                # le verrou a expiré : l'attaque reprend
        self.assertEqual(self.e.handle_event(brute_event()), "bruteforce")


class OutageTests(EngineBase):
    def test_watchdog_restarts_the_crashed_service_and_verifies(self):
        self.io.probe_ok = False; self.io.services["api"] = {"state": "exited", "health": "n/a"}
        out = None
        for _ in range(3):
            out = self.e.monitor_tick()
        self.assertIsNotNone(out)
        ev, attack = out
        self.assertEqual((attack, ev["suspects"]["services"]), ("outage", ["api"]))
        self.e.guarded(ev, attack)
        self.assertEqual(self.io.names("restart"), [("restart", "api")])
        self.assertEqual(self.e.S["state"], "RESTORED")
        self.assertFalse(self.e.S["busy"])

    def test_no_watchdog_action_when_containers_are_healthy_and_failures_are_few(self):
        self.io.probe_ok = False
        for _ in range(5):
            self.assertIsNone(self.e.monitor_tick())

    def test_hung_service_with_healthy_containers_is_eventually_restarted(self):
        self.io.probe_ok = False
        outs = [self.e.monitor_tick() for _ in range(9)]
        self.assertIsNotNone(outs[-1])
        self.assertEqual(outs[-1][0]["suspects"]["services"], ["api"])


class EventAndRegulationTests(EngineBase):
    def test_state_transitions_on_events(self):
        self.e.handle_event({"kind": "suspect", "score": -0.05, "features": {}})
        self.assertEqual(self.e.S["state"], "SURVEILLANCE")
        self.e.handle_event({"kind": "normal", "score": 0.1, "features": {}})
        self.assertEqual(self.e.S["state"], "HOMEOSTASIS")

    def test_single_incident_at_a_time(self):
        self.assertEqual(self.e.handle_event(dos_event()), "dos")
        self.assertIsNone(self.e.handle_event(dos_event()))          # busy

    def test_detector_error_never_opens_an_incident(self):
        self.assertIsNone(self.e.handle_event({"kind": "detector_error", "error": "loki down"}))
        self.assertEqual(self.e.S["detector"]["error"], "loki down")

    def test_defenses_relax_after_calm(self):
        self.e.run_incident(dos_event(), "dos")
        self.assertEqual(self.e.S["rules"]["pay_rate"], 10)
        self.clock.sleep(self.e.cfg.hold + 1); self.e.monitor_tick()            # -> HOMEOSTASIS
        self.clock.sleep(self.e.cfg.relax_after + 1); self.e.monitor_tick()
        self.assertEqual(self.e.S["rules"]["pay_rate"], self.e.cfg.pay_default)

    def test_reset_clears_everything(self):
        self.e.run_incident(dos_event(), "dos")
        self.e.reset()
        self.assertIn(("auth", "clear", "attacker"), self.io.calls)
        self.assertEqual((self.e.S["state"], self.e.S["rules"]["suspended_users"]), ("HOMEOSTASIS", []))

    def test_metrics_text(self):
        t = self.e.metrics_text()
        self.assertIn('remediator_state{state="HOMEOSTASIS"} 1', t)
        self.assertIn("remediator_probe_ok", t)

    def test_waf_rules_rendering_is_safe(self):
        txt = render_waf_rules({"pay_rate": 10, "login_rate": 100, "banned_ips": ["10.0.0.9"]})
        self.assertIn("limit_req_zone $rl_key zone=pay:10m rate=10r/s;", txt)
        self.assertIn("    10.0.0.9 1;", txt)
        with self.assertRaises(ValueError):
            render_waf_rules({"pay_rate": 10, "login_rate": 100, "banned_ips": ["1.1.1.1 1; } server { listen 80"]})


if __name__ == "__main__":
    unittest.main()
