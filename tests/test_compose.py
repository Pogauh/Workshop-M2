"""Contrôles structurels de docker-compose.yml sans Docker (PyYAML) : réseaux, volumes, dépendances, surface exposée,
variables d'environnement documentées, chemins montés/construits présents dans le dépôt."""
import re, unittest
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent
C = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
S = C["services"]
ENV_NAMES = set(re.findall(r"^([A-Z][A-Z0-9_]+)=", (ROOT / ".env.example").read_text(), re.M))


def nets(svc):
    n = S[svc].get("networks", [])
    return set(n if isinstance(n, list) else n.keys())


class Compose(unittest.TestCase):
    def test_references_resolve(self):
        for name, s in S.items():
            self.assertTrue(nets(name) <= set(C["networks"]), name)
            deps = s.get("depends_on", [])
            for d in (deps if isinstance(deps, list) else deps.keys()):
                self.assertIn(d, S, f"{name} dépend de {d}")
            for v in s.get("volumes", []):
                src = v.split(":")[0]
                if not src.startswith(("/", ".")):
                    self.assertIn(src, C["volumes"], f"{name}: volume {src}")

    def test_env_vars_are_documented(self):
        used = set(re.findall(r"\$\{([A-Z][A-Z0-9_]+)", (ROOT / "docker-compose.yml").read_text()))
        self.assertTrue(used <= ENV_NAMES, used - ENV_NAMES)

    def test_every_secret_is_required(self):
        txt = (ROOT / "docker-compose.yml").read_text()
        for v in ("POSTGRES_PASSWORD", "API_DB_PASSWORD", "AUTH_DB_PASSWORD", "JWT_SECRET", "INTERNAL_TOKEN", "ACTUATOR_TOKEN",
                  "EVENT_HMAC_KEY", "GRAFANA_PASSWORD", "DEMO_PASSWORD", "WEAK_PASSWORD", "ATTACKER_PASSWORD", "PROBE_PASSWORD"):
            self.assertRegex(txt, r"\$\{%s:\?" % v)
        self.assertNotRegex(txt, r"(PASSWORD|SECRET|TOKEN|KEY): +[A-Za-z0-9]{12,}\s*$")

    def test_only_the_waf_is_public(self):
        for name, s in S.items():
            for p in s.get("ports", []):
                host = str(p).split(":")[0]
                if name == "waf":
                    self.assertEqual(str(p), "8080:8080")
                else:
                    self.assertEqual(host, "127.0.0.1", f"{name} publie {p} hors localhost")

    def test_docker_socket_access(self):
        holders = {n for n, s in S.items() if any("docker.sock" in v for v in s.get("volumes", []))}
        self.assertEqual(holders, {"actuator", "docker-ro"})
        self.assertTrue(any(v.endswith(":ro") for v in S["docker-ro"]["volumes"]))
        self.assertEqual(nets("docker-ro"), {"logs"}); self.assertEqual(nets("actuator"), {"control"})

    def test_assistant_isolated(self):
        self.assertEqual(nets("assistant"), {"assist"}); self.assertEqual(nets("ollama"), {"assist"})
        self.assertTrue(C["networks"]["assist"]["internal"])
        for n in ("db", "api", "auth", "actuator"):
            self.assertNotIn("assist", nets(n))

    def test_database_not_reachable_from_outside_internal(self):
        self.assertEqual(nets("db"), {"internal"})
        self.assertNotIn("ports", S["db"])

    def test_no_privileged_or_host_network(self):
        for n, s in S.items():
            self.assertNotIn("privileged", s, n); self.assertNotEqual(s.get("network_mode"), "host", n)
            self.assertNotIn("cap_add", s, n)

    def test_hardening_on_application_services(self):
        for n in ("waf", "web", "api", "auth", "remediator", "actuator", "detector", "dashboard", "assistant"):
            s = S[n]
            self.assertTrue(s.get("read_only"), n); self.assertEqual(s.get("cap_drop"), ["ALL"], n)
            self.assertIn("no-new-privileges:true", s.get("security_opt", []), n)
            self.assertIn("mem_limit", s, n)

    def test_paths_exist(self):
        missing = []
        for n, s in S.items():
            b = s.get("build")
            if b:
                ctx = b if isinstance(b, str) else b["context"]
                if not (ROOT / ctx).is_dir():
                    missing.append(f"{n}: build {ctx}")
                elif isinstance(b, dict) and not (ROOT / ctx / b.get("dockerfile", "Dockerfile")).is_file():
                    missing.append(f"{n}: dockerfile")
                elif isinstance(b, str) and not (ROOT / ctx / "Dockerfile").is_file():
                    missing.append(f"{n}: {ctx}/Dockerfile")
            for v in s.get("volumes", []):
                src = v.split(":")[0]
                if src.startswith("./") and not (ROOT / src).exists():
                    missing.append(f"{n}: {src}")
        self.assertEqual(missing, [])

    def test_profiles(self):
        self.assertEqual({n for n, s in S.items() if "lab" in s.get("profiles", [])}, {"traffic", "attacker"})
        self.assertEqual({n for n, s in S.items() if "ai" in s.get("profiles", [])}, {"ollama", "assistant", "assistant-ui"})


if __name__ == "__main__":
    unittest.main()
