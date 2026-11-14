import os
import pathlib
import subprocess
import sys
import tempfile
import textwrap
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
HOOK = ROOT / "imageroot" / "update-module.d" / "15upgrade_v3"
RESTART = ROOT / "imageroot" / "update-module.d" / "20restart"

# Minimal stand-ins for the NS8 agent and the certificate helper: the
# migration code itself is the real hook.
FAKES = {
    "agent.py": """
import subprocess
def run_helper(*args, **kw):
    if args[0] == "podman":
        return
    return subprocess.run(args, check=True)
""",
    "cert_helpers.py": """
names = []
def has_acmejson_name(name):
    return True
def add_default_certificate_name(main, sans=()):
    names.append((main, list(sans)))
""",
}

V2_STATIC = "entryPoints:\n  http:\n    address: ':80'\n"
GOOD_CERT = ("http:\n  routers:\n    certificate-a:\n      rule: Host(`a.example.org`)\n"
             "      tls:\n        domains:\n          - main: a.example.org\n")
GOOD_ROUTE = ("http:\n  routers:\n    app-https:\n      entryPoints: https\n      rule: Host(`a.example.org`)\n"
              "      tls: {}\n")


class UpgradeV3(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = pathlib.Path(self.tmp.name)
        fake = self.home.parent / (self.home.name + "-fakes")
        fake.mkdir()
        for name, body in FAKES.items():
            (fake / name).write_text(body)
        self.fake = fake
        (self.home / "traefik.yaml").write_text(V2_STATIC)
        (self.home / "configs").mkdir()
        (self.home / "custom_certificates").mkdir()
        (self.home / "custom_certificates" / "x.crt").write_text("CERT")

    def tearDown(self):
        self.tmp.cleanup()
        for p in self.fake.iterdir():
            p.unlink()
        self.fake.rmdir()

    def run_hook(self):
        env = dict(os.environ, PYTHONPATH=f"{self.fake}", PYTHONDONTWRITEBYTECODE="1")
        return subprocess.run([sys.executable, "-B", str(HOOK)], cwd=self.home, env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def static(self):
        return (self.home / "traefik.yaml").read_text()

    def test_successful_migration_marks_v3_and_keeps_the_original(self):
        (self.home / "configs" / "certificate-a.yml").write_text(GOOD_CERT)
        (self.home / "configs" / "app.yml").write_text(GOOD_ROUTE)
        result = self.run_hook()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("defaultRuleSyntax: v3", self.static())
        self.assertEqual((self.home / "traefik.yaml.v2").read_text(), V2_STATIC)
        self.assertTrue((self.home / "configs.v2" / "certificate-a.yml").exists())
        self.assertFalse((self.home / "configs" / "certificate-a.yml").exists())
        self.assertIn("- https", (self.home / "configs" / "app.yml").read_text())

    def test_unreadable_file_fails_without_marking_and_keeps_the_file(self):
        (self.home / "configs" / "certificate-a.yml").write_text("http: [unclosed\n")
        result = self.run_hook()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertNotIn("defaultRuleSyntax", self.static())
        self.assertTrue((self.home / "configs" / "certificate-a.yml").exists())

    def test_failed_route_conversion_is_not_marked_done(self):
        (self.home / "configs" / "app.yml").write_text("http: {routers: [not-a-map]}\n")
        result = self.run_hook()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertNotIn("defaultRuleSyntax", self.static())

    def test_retry_does_not_overwrite_the_original_backup(self):
        (self.home / "configs" / "app.yml").write_text("http: {routers: [not-a-map]}\n")
        self.assertEqual(self.run_hook().returncode, 1)
        # A partly converted state must not replace the first backup
        (self.home / "traefik.yaml").write_text(V2_STATIC + "changed: by-first-run\n")
        (self.home / "configs" / "app.yml").write_text(GOOD_ROUTE)
        self.assertEqual(self.run_hook().returncode, 0)
        self.assertEqual((self.home / "traefik.yaml.v2").read_text(), V2_STATIC)

    def test_already_migrated_is_a_noop(self):
        (self.home / "traefik.yaml").write_text("core:\n  defaultRuleSyntax: v3\nentryPoints:\n  metrics:\n    address: ':8082'\n")
        before = self.static()
        self.assertEqual(self.run_hook().returncode, 0)
        self.assertEqual(self.static(), before)
        self.assertFalse((self.home / "traefik.yaml.v2").exists())


class RestartGuard(unittest.TestCase):
    def run_restart(self, static):
        with tempfile.TemporaryDirectory() as tmp:
            home = pathlib.Path(tmp)
            bindir = home / "bin"
            bindir.mkdir()
            ctl = bindir / "systemctl"
            ctl.write_text('#!/bin/bash\necho "$@" >> "$HOME_LOG"\n')
            ctl.chmod(0o755)
            log = home / "log"
            if static is not None:
                (home / "traefik.yaml").write_text(static)
            env = dict(os.environ, PATH=f"{bindir}:{os.environ['PATH']}", HOME_LOG=str(log))
            r = subprocess.run(["bash", str(RESTART)], cwd=home, env=env,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            return r, (log.read_text() if log.exists() else "")

    def test_restarts_when_migrated(self):
        r, log = self.run_restart("core:\n  defaultRuleSyntax: v3\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(log.strip(), "--user restart traefik.service")

    def test_does_not_restart_without_v3_marker(self):
        r, log = self.run_restart(V2_STATIC)
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(log, "")

    def test_does_not_restart_without_config(self):
        r, log = self.run_restart(None)
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(log, "")


if __name__ == "__main__":
    unittest.main()
