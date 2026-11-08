"""Exercise the installed payload rather than importing from the checkout."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SKILL = Path(__file__).resolve().parents[1] / "skills" / "mole"

# Installed only in the subprocess. Deny network and child processes, and ensure
# the actual engine import resolves inside the copied payload.
RUNNER = r'''
import pathlib, runpy, sys
entrypoint = pathlib.Path(sys.argv[1])
expected = entrypoint.parent.parent.resolve()
def audit(event, args):
    if event.startswith("socket.") or event in (
        "subprocess.Popen", "os.system", "os.posix_spawn", "os.exec", "os.fork"
    ):
        raise RuntimeError("Forbidden side effect: " + event)
sys.addaudithook(audit)
sys.argv = sys.argv[1:]
try:
    runpy.run_path(str(entrypoint), run_name="__main__")
finally:
    import molekit
    assert pathlib.Path(molekit.__file__).resolve().parent == expected / "molekit"
'''


class InstalledSkillTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.installed = self.root / "installed skill with spaces"
        shutil.copytree(SKILL, self.installed,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        self.cwd = self.root / "unrelated project"
        self.cwd.mkdir()
        # A target module must never be imported during diagnostics.
        (self.cwd / "molekit.py").write_text(
            "raise RuntimeError('target code executed')\n", encoding="utf-8")

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "-I", "-S", "-B", "-c", RUNNER,
             str(self.installed / "scripts" / "mole.py"), *args],
            cwd=self.cwd, env={**os.environ, "PYTHONPATH": str(SKILL)},
            capture_output=True, text=True, timeout=15,
        )

    def test_doctor_offline_isolated_payload(self):
        result = self.run_cli("doctor", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["checks"]["pythonSupported"])
        self.assertTrue(payload["checks"]["bundledEngine"])
        self.assertIn("doctor", payload["capabilities"])
        self.assertIn("update", payload["capabilities"])
        self.assertEqual(result.stderr, "")
        self.assertFalse((self.cwd / ".mole").exists())

    def test_help_and_version(self):
        for args in [("--help",), ("doctor", "--help"), ("--version",)]:
            with self.subTest(args=args):
                result = self.run_cli(*args)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(result.stdout.strip())
                self.assertEqual(result.stderr, "")

    def test_human_doctor(self):
        result = self.run_cli("doctor")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Static analysis", result.stdout)

    def test_incomplete_payload_returns_structured_error(self):
        (self.installed / "molekit/errors.py").unlink()
        result = self.run_cli("doctor", "--json")
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertEqual(json.loads(result.stdout)["error"]["code"], "PAYLOAD_INCOMPLETE")

    def test_installed_scan_offline_without_target_execution(self):
        (self.cwd / "app.py").write_text("raise RuntimeError('target code executed')\ndef f(): return 1\n")
        workspace = self.root / "workspace"
        result = self.run_cli("start", "--repo", str(self.cwd), "--workspace", str(workspace), "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.run_cli("next", "--workspace", str(workspace), "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIsNotNone(json.loads(result.stdout)["revision"])
        task = json.loads(result.stdout)["task"]
        result = self.run_cli("inspect", "--workspace", str(workspace), "--task", task["id"], "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        response = self.root / "patch.json"
        response.write_text(json.dumps({"protocolVersion": "1.0", "taskId": task["id"],
            "baseRevision": task["baseRevision"], "claims": [{"id": "claim-f",
            "statement": "A function is declared", "status": "source_observed",
            "evidenceIds": task["evidenceIds"], "limitations": []}]}))
        result = self.run_cli("submit", "--workspace", str(workspace), "--input", str(response), "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        output = self.root / "output"
        result = self.run_cli("finish", "--workspace", str(workspace), "--output", str(output), "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((output / "README.md").is_file())
        self.assertTrue((output / "explorer.html").is_file())
        self.assertTrue((output / "confluence/workflows.drawio").is_file())

    def test_invalid_requests(self):
        for args in [(), ("start",), ("doctor", "--repo", "."),
                     ("doctor", "--unknown")]:
            with self.subTest(args=args):
                result = self.run_cli(*args)
                self.assertEqual(result.returncode, 2, result.stderr)
                payload = json.loads(result.stdout)
                self.assertFalse(payload["ok"])
                self.assertEqual(payload["error"]["code"], "INVALID_REQUEST")

    def test_unsupported_python(self):
        # Run the real entrypoint with an older version reported by the runtime.
        runner = "import sys; sys.version_info = (3, 10, 0);\n" + RUNNER
        result = subprocess.run(
            [sys.executable, "-I", "-S", "-B", "-c", runner,
             str(self.installed / "scripts" / "mole.py"), "doctor", "--json"],
            cwd=self.cwd, capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertEqual(json.loads(result.stdout)["error"]["code"],
                         "PYTHON_UNSUPPORTED")


if __name__ == "__main__":
    unittest.main()
