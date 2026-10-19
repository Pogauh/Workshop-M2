"""Tests du détecteur : règles SIEM (pures) et modèle ML (données synthétiques, sans Loki ni Docker).
Lancer :  cd detector && python3 -I -m unittest discover -s tests -t . -v"""
import unittest
import numpy as np

from app import siem
from app.model import FEATURES, flags, score_one
from app.train import train, runs_of, first_detection_s


def synth_normal(n, rng):
    """Trafic normal : quelques req/s, latence stable, des échecs de connexion occasionnels (variance indispensable)."""
    rps = rng.gamma(4, 0.8, n)
    return np.column_stack([rps, rps * rng.uniform(0.2, 0.5, n), rng.normal(60, 12, n).clip(10),
                            rng.beta(1, 80, n), rng.beta(1, 60, n), rng.poisson(1.5, n),
                            rng.gamma(2, 0.15, n), rng.gamma(1, 0.05, n)])


def synth_flood(n, rng):
    rps = rng.normal(180, 30, n).clip(60)
    return np.column_stack([rps, rps * 0.95, rng.normal(900, 200, n).clip(100), rng.beta(2, 20, n), rng.beta(5, 6, n),
                            rng.poisson(40, n), rng.gamma(2, 0.15, n), rng.gamma(1, 0.05, n)])


def synth_brute(n, rng):
    base = synth_normal(n, rng)
    base[:, 6] = rng.normal(12, 2, n).clip(5)           # login_rps
    base[:, 7] = base[:, 6] * 0.97                      # presque tous échoués
    base[:, 2] = rng.normal(250, 50, n)                 # bcrypt sature le CPU
    return base


class SiemRules(unittest.TestCase):
    def test_dominant_user_flagged_not_probe(self):
        a, s = siem.evaluate({"user_rate": {"attacker": 80.0, "alice": 1.0, "probe": 0.5}})
        self.assertEqual(s["users"], ["attacker"]); self.assertEqual([x["rule"] for x in a], ["R4"])

    def test_shared_load_is_not_a_single_culprit(self):
        _, s = siem.evaluate({"user_rate": {"alice": 8.0, "bob": 8.0, "carol": 8.0, "merchant": 8.0}})
        self.assertEqual(s["users"], [])

    def test_bruteforce_targets_the_account(self):
        a, s = siem.evaluate({"login_fail_15": {"carol": 40.0, "alice": 1.0}})
        self.assertEqual(s["targets"], ["carol"]); self.assertEqual(a[0]["rule"], "R2")

    def test_fail_then_success_is_critical_compromise(self):
        a, s = siem.evaluate({"login_fail_60": {"carol": 30.0}, "login_ok_60": {"carol": 1.0}})
        self.assertEqual(s["compromised"], ["carol"])
        self.assertEqual([x["severity"] for x in a], ["critical"])

    def test_failures_without_success_are_not_compromise(self):
        _, s = siem.evaluate({"login_fail_60": {"carol": 30.0}})
        self.assertEqual(s["compromised"], [])

    def test_hostile_usernames_are_ignored(self):
        _, s = siem.evaluate({"login_fail_15": {"'; drop table users;--": 99.0}, "user_rate": {"A B": 500.0}})
        self.assertEqual((s["targets"], s["users"]), ([], []))

    def test_waf_rule_alert_and_suspended_info(self):
        a, s = siem.evaluate({"waf_rules": {"sqli": 12.0}, "suspended_hits": {"attacker": 5.0}})
        self.assertEqual(sorted(x["rule"] for x in a), ["R1", "R5"]); self.assertEqual(s["waf_rules"], ["sqli"])

    def test_alertbook_dedup_count_and_expiry(self):
        book = siem.AlertBook(ttl=60)
        al = [{"rule": "R2", "severity": "high", "subject": "carol", "title": "t", "detail": "d", "ts": 100.0}]
        book.update(al, now=100.0)
        out = book.update([{**al[0], "ts": 110.0}], now=110.0)
        self.assertEqual((len(out), out[0]["count"], out[0]["first_ts"]), (1, 2, 100.0))
        self.assertEqual(book.update([], now=300.0), [])


class Model(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rng = np.random.default_rng(7)
        cls.normal = synth_normal(400, rng)
        cls.flood, cls.brute = synth_flood(60, rng), synth_brute(60, rng)
        cls.bundle, cls.report = train(cls.normal, {"flood": cls.flood, "brute": cls.brute})

    def test_features_contract(self):
        self.assertEqual(len(FEATURES), self.normal.shape[1]); self.assertEqual(self.bundle["features"], FEATURES)

    def test_low_false_positive_rate_on_held_out_normal(self):
        self.assertLessEqual(self.report["false_positive_rate"], 0.06)
        self.assertEqual(self.report["false_alerts_after_debounce_k3"], 0)

    def test_attacks_detected(self):
        for name in ("flood", "brute"):
            self.assertGreaterEqual(self.report["attacks"][name]["recall"], 0.9, name)
            self.assertIsNotNone(self.report["attacks"][name]["detected_after_s"], name)

    def test_idle_system_is_not_an_attack(self):
        idle = np.zeros((20, len(FEATURES)))
        _, a = flags(self.bundle, idle)
        self.assertFalse(a.any())

    def test_score_one_shape(self):
        s, a = score_one(self.bundle, dict(zip(FEATURES, self.flood[0])))
        self.assertTrue(a); self.assertIsInstance(s, float)

    def test_debounce_helpers(self):
        self.assertEqual(runs_of([1, 1, 0, 1, 1, 1, 1], 3), 2)
        self.assertEqual(first_detection_s([0, 1, 1, 1], 3), 20); self.assertIsNone(first_detection_s([1, 0, 1], 3))


if __name__ == "__main__":
    unittest.main()
