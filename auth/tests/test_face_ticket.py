"""Vérification (côté auth) du billet de reconnaissance faciale émis par `face`. Pur, sans base ni réseau.
Lancer : cd auth && FACE_TICKET_KEY=test python3 -I -m unittest discover -s tests -t . -v
(Doit rester identique à face/tests/test_ticket.py : même secret, même format, deux services indépendants.)"""
import os
os.environ.setdefault("FACE_TICKET_KEY", "test-key-not-a-real-secret")

import hashlib, hmac, time, unittest

from app import face_ticket


def _issue(username, ttl_s=120, now=None):
    """Émetteur minimal pour le test (le vrai émetteur vit dans face/app/ticket.py)."""
    exp = int((now if now is not None else time.time())) + ttl_s
    payload = f"{username}:{exp}"
    sig = hmac.new(os.environ["FACE_TICKET_KEY"].encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"


class FaceTicket(unittest.TestCase):
    def test_accepts_a_ticket_issued_with_the_same_key(self):
        t = _issue("manager", now=1000)
        self.assertTrue(face_ticket.verify(t, "manager", now=1010))

    def test_rejects_after_expiry(self):
        t = _issue("manager", ttl_s=120, now=1000)
        self.assertFalse(face_ticket.verify(t, "manager", now=1121))

    def test_rejects_for_another_username(self):
        t = _issue("manager", now=1000)
        self.assertFalse(face_ticket.verify(t, "attacker", now=1001))

    def test_rejects_tampered_signature(self):
        t = _issue("manager", now=1000)
        head, _, _sig = t.rpartition(":")
        self.assertFalse(face_ticket.verify(head + ":0" * 64, "manager", now=1001))

    def test_rejects_missing_or_malformed(self):
        for bad in (None, "", "x", "a:b", "a:b:c:d"):
            self.assertFalse(face_ticket.verify(bad, "manager"))


if __name__ == "__main__":
    unittest.main()
