"""Tests de validation d'entrée de l'API.  Lancer : cd api && python -m unittest discover -s tests -v"""
import os, sys, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from pydantic import ValidationError           # noqa: E402
from app.schemas import PaymentIn              # noqa: E402


class PaymentInTests(unittest.TestCase):
    def test_valid(self):
        p = PaymentIn(to="merchant", amount="12.50", label="Café (équipe)")
        self.assertEqual(str(p.amount), "12.50")

    def test_rejects_injection_in_recipient(self):
        for bad in ["alice' OR 1=1 --", "a;DROP TABLE accounts", "<script>", "Alice", "x" * 40, ""]:
            with self.assertRaises(ValidationError, msg=bad):
                PaymentIn(to=bad, amount="1.00")

    def test_rejects_bad_amounts(self):
        for bad in ["0", "-1", "10000.01", "1.234", "abc", "1e9"]:
            with self.assertRaises(ValidationError, msg=bad):
                PaymentIn(to="bob", amount=bad)

    def test_rejects_unsafe_label(self):
        for bad in ["<img src=x onerror=alert(1)>", "'; DROP TABLE payments;--", "a" * 65]:
            with self.assertRaises(ValidationError, msg=bad):
                PaymentIn(to="bob", amount="1.00", label=bad)


if __name__ == "__main__":
    unittest.main()
