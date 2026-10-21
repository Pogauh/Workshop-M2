"""Verrouillage de la phase de reconnaissance faciale (1 essai puis blocage 5 min). Pur, en mémoire.
Lancer : cd face && python3 -I -m unittest discover -s tests -t . -v"""
import importlib
import unittest


class Lockout(unittest.TestCase):
    def setUp(self):
        # état en mémoire : module rechargé à chaque test pour repartir propre, sans dépendre de l'ordre
        from app import lockout
        importlib.reload(lockout)
        self.lockout = lockout

    def test_first_failure_does_not_lock(self):
        self.assertIsNone(self.lockout.record_failure("carol", now=0))
        self.assertIsNone(self.lockout.is_locked("carol", now=1))

    def test_second_consecutive_failure_locks_5_minutes(self):
        self.lockout.record_failure("carol", now=0)
        until = self.lockout.record_failure("carol", now=5)
        self.assertEqual(until, 5 + 300)
        self.assertEqual(self.lockout.is_locked("carol", now=10), until)

    def test_lock_expires_after_300s(self):
        self.lockout.record_failure("carol", now=0)
        self.lockout.record_failure("carol", now=5)
        self.assertIsNone(self.lockout.is_locked("carol", now=5 + 300 + 1))

    def test_success_resets_the_failure_counter(self):
        self.lockout.record_failure("carol", now=0)
        self.lockout.record_success("carol")
        # repart de zéro : il faut de nouveau 2 échecs, pas 1, pour verrouiller
        self.assertIsNone(self.lockout.record_failure("carol", now=10))

    def test_cycle_repeats_after_a_lock_expires(self):
        """« bloqué 5 minutes, etc. » : le cycle (1 essai -> verrou) se répète après expiration."""
        self.lockout.record_failure("carol", now=0)
        until1 = self.lockout.record_failure("carol", now=5)
        self.assertIsNotNone(until1)
        self.assertIsNone(self.lockout.record_failure("carol", now=until1 + 1))          # 1er échec du nouveau cycle
        until2 = self.lockout.record_failure("carol", now=until1 + 5)                     # 2e -> reverrouille
        self.assertIsNotNone(until2)

    def test_accounts_are_independent(self):
        self.lockout.record_failure("carol", now=0)
        self.lockout.record_failure("carol", now=1)
        self.assertIsNone(self.lockout.is_locked("alice", now=2))

    def test_reset_clears_both_counters_and_lock(self):
        self.lockout.record_failure("carol", now=0)
        self.lockout.record_failure("carol", now=1)
        self.lockout.reset("carol")
        self.assertIsNone(self.lockout.is_locked("carol", now=1))
        self.assertIsNone(self.lockout.record_failure("carol", now=2))   # repart bien de zéro, pas déjà "1 échec"


if __name__ == "__main__":
    unittest.main()
