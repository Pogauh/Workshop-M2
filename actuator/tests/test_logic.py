"""Tests de la liste blanche de l'actionneur avec un faux client Docker.
Lancer :  cd actuator && python3 -I -m unittest discover -s tests -t . -v"""
import unittest
from app.logic import Actuator, Denied, RESTART_ALLOW


class FakeC:
    def __init__(self, name, status="running", health="healthy"):
        self.name, self.status, self.attrs, self.calls = name, status, {"State": {"Health": {"Status": health}}}, []
    def restart(self, timeout=10): self.calls.append(("restart", timeout))
    def kill(self, signal): self.calls.append(("kill", signal))


class FakeCli:
    def __init__(self, names):
        self.cs = {n: FakeC(n) for n in names}
        self.containers = self
    def get(self, name):
        if name not in self.cs: raise KeyError(name)
        return self.cs[name]


class T(unittest.TestCase):
    def setUp(self):
        self.t = [1000.0]
        self.cli = FakeCli(["immune-waf", "immune-api", "immune-auth", "immune-db", "immune-web"])
        self.a = Actuator(self.cli, "secret", clock=lambda: self.t[0])

    def code(self, fn, *args):
        with self.assertRaises(Denied) as cm: fn(*args)
        return cm.exception.code

    def test_token_required(self):
        self.assertEqual(self.code(self.a.restart, None, "api"), 401)
        self.assertEqual(self.code(self.a.restart, "wrong", "api"), 401)
        self.assertEqual(self.code(self.a.status, "", ), 401)
        self.assertEqual(self.code(self.a.reload_waf, "x"), 401)
        self.assertEqual(self.cli.cs["immune-api"].calls, [])

    def test_empty_configured_token_never_matches(self):
        self.assertEqual(self.code(Actuator(self.cli, "").restart, "", "api"), 401)

    def test_whitelist_only(self):
        for svc in ("web", "waf", "assistant", "ollama", "../etc", "api;rm"):
            self.assertEqual(self.code(self.a.restart, "secret", svc), 403, svc)
        self.assertEqual(set(RESTART_ALLOW), {"api", "auth", "db"})

    def test_restart_and_rate_limit(self):
        self.assertEqual(self.a.restart("secret", "api"), {"ok": True, "restarted": "api"})
        self.assertEqual(self.cli.cs["immune-api"].calls, [("restart", 10)])
        self.assertEqual(self.code(self.a.restart, "secret", "api"), 429)
        self.a.restart("secret", "auth")                       # autre service : autorisé
        self.t[0] += 21
        self.a.restart("secret", "api")
        self.assertEqual(len(self.cli.cs["immune-api"].calls), 2)

    def test_waf_reload_sends_hup_only(self):
        self.a.reload_waf("secret")
        self.assertEqual(self.cli.cs["immune-waf"].calls, [("kill", "HUP")])

    def test_status_reports_missing_containers(self):
        del self.cli.cs["immune-db"]
        self.cli.cs["immune-api"].attrs["State"]["Health"]["Status"] = "unhealthy"
        st = self.a.status("secret")
        self.assertEqual(st["db"], {"state": "missing", "health": "n/a"})
        self.assertEqual(st["api"], {"state": "running", "health": "unhealthy"})
        self.assertEqual(set(st), {"waf", "api", "auth", "db"})


if __name__ == "__main__":
    unittest.main()
