"""Billet d'authentification faciale (HMAC signé). Pur : aucun réseau, aucune image.
Lancer : cd face && FACE_TICKET_KEY=test python3 -I -m unittest discover -s tests -t . -v"""
import os
os.environ.setdefault("FACE_TICKET_KEY", "test-key-not-a-real-secret")
os.environ.setdefault("JWT_SECRET", "test-key-not-a-real-secret")

import unittest

from app import ticket


class Ticket(unittest.TestCase):
    def test_round_trip(self):
        t = ticket.issue("alice", now=1000)
        self.assertTrue(ticket.verify(t, "alice", now=1010))

    def test_expired_after_ttl(self):
        t = ticket.issue("alice", ttl_s=120, now=1000)
        self.assertTrue(ticket.verify(t, "alice", now=1000 + 120))
        self.assertFalse(ticket.verify(t, "alice", now=1000 + 121))

    def test_rejected_for_a_different_username(self):
        t = ticket.issue("alice", now=1000)
        self.assertFalse(ticket.verify(t, "bob", now=1001))

    def test_tampered_signature_rejected(self):
        t = ticket.issue("alice", now=1000)
        head, _, _sig = t.rpartition(":")
        self.assertFalse(ticket.verify(head + ":0" * 64, "alice", now=1001))

    def test_tampered_expiry_rejected(self):
        """Changer l'horodatage sans recalculer la signature doit échouer (pas de falsification possible)."""
        t = ticket.issue("alice", ttl_s=1, now=1000)   # expire presque immédiatement
        user, _exp, sig = t.split(":")
        forged = f"{user}:9999999999:{sig}"
        self.assertFalse(ticket.verify(forged, "alice", now=2000))

    def test_malformed_tickets_rejected(self):
        for bad in (None, "", "not-a-ticket", "a:b", "a:b:c:d"):
            self.assertFalse(ticket.verify(bad, "alice"))


if __name__ == "__main__":
    unittest.main()
