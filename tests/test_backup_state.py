import os
import pathlib
import subprocess
import tempfile
import unittest

BIN = pathlib.Path(__file__).resolve().parents[1] / "imageroot" / "bin"


class BackupStateScriptsTest(unittest.TestCase):
    """module-dump-state and module-cleanup-state must use the same directory."""

    def run_script(self, name, cwd):
        return subprocess.run(
            ["bash", str(BIN / name)],
            cwd=cwd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def test_cleanup_removes_what_dump_creates(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = pathlib.Path(tmp)
            (home / "traefik.yaml").write_text("entryPoints: {}\n")
            for directory in ("configs", "manual_flags", "custom_certificates", "acme"):
                (home / directory).mkdir()
            (home / "acme" / "acme.json").write_text("{}\n")
            os.chmod(home / "acme" / "acme.json", 0o600)

            self.run_script("module-dump-state", home)
            dump = home / "state-backup"
            self.assertTrue((dump / "traefik.yaml").is_file())
            self.assertTrue((dump / "acme" / "acme.json").is_file())

            self.run_script("module-cleanup-state", home)
            self.assertFalse(dump.exists(), "cleanup left the dump with keys behind")

    def test_include_file_lists_the_dump_directory(self):
        include = (BIN.parent / "etc" / "state-include.conf").read_text()
        self.assertIn("state/state-backup", include.split())


if __name__ == "__main__":
    unittest.main()
