import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/mole"))
from molekit.agent import inspect
from molekit.errors import MoleError
from molekit.pipeline import start, operate
from molekit.safety import read_source, confined_output
from molekit.scanner import redact, redacted_lines, scan
from molekit.workspace import read_json, load


class SecurityTests(unittest.TestCase):
    def test_secret_formats_suppressed(self):
        for line in ['TOKEN=abcdef123456', '"api_key": "abcdef123456"',
                     "password = 'abcdef123456'", 'Bearer abcdefghijklmnop',
                     'postgres://user:private@db/name', '-----BEGIN PRIVATE KEY-----',
                     'ghp_' + 'A' * 30, 'AKIA' + 'A' * 16]:
            with self.subTest(line=line):
                self.assertEqual(redact(line), "[sensitive source line suppressed]")

    def test_multiline_secret_blocks_suppressed_before_pagination(self):
        for filename, content in [
            ("settings.json", '{"api_key":\n "abcdef123456SECRET"}\n'),
            ("settings.yaml", 'secret: |\n  abcdef123456SECRET\n  otherprivatevalue\nordinary: public\n'),
            ("notes.md", '-----BEGIN PRIVATE KEY-----\nabcdef123456SECRET\n-----END PRIVATE KEY-----\n'),
        ]:
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as tmp:
                repo = Path(tmp) / "repo"
                repo.mkdir()
                (repo / filename).write_text(content)
                workspace = Path(tmp) / "workspace"
                start(repo, workspace, "standard", "repository")
                task = operate("next", workspace)["task"]
                response = operate("inspect", workspace, task=task["id"], budget_chars=12000)
                self.assertNotIn("abcdef123456SECRET", json.dumps(response))
                self.assertNotIn("otherprivatevalue", json.dumps(response))
                self.assertEqual(len(redacted_lines(content)), len(content.splitlines()))

    def test_duplicate_nonfinite_and_deep_json_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "input.json"
            for data in ['{"x":1,"x":2}', '{"x":NaN}', '[' * 1100 + '0' + ']' * 1100]:
                path.write_text(data)
                with self.assertRaises(MoleError):
                    read_json(path)

    def test_secret_blocks_with_cr_and_mixed_line_endings(self):
        for separator in ("\r", "\r\n", "\u2028"):
            for content in ['{"api_key":\n "abcdef123456SECRET"}\n',
                            '-----BEGIN PRIVATE KEY-----\nabcdef123456SECRET\n-----END PRIVATE KEY-----\n']:
                with self.subTest(separator=repr(separator)):
                    content = content.replace("\n", separator)
                    self.assertNotIn("abcdef123456SECRET", "\n".join(redacted_lines(content)))
        mixed = 'secret: |\r\n  abcdef123456SECRET\r  otherprivatevalue\npublic: yes\n'
        self.assertNotIn("abcdef123456SECRET", "\n".join(redacted_lines(mixed)))
        self.assertNotIn("otherprivatevalue", "\n".join(redacted_lines(mixed)))

    def test_source_and_output_symlink_escape_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            outside = Path(tmp) / "outside"
            outside.mkdir()
            (outside / "secret.py").write_text("private = 'sensitive'\n")
            try:
                (root / "escape").symlink_to(outside, target_is_directory=True)
            except OSError:
                self.skipTest("Symlink permission unavailable")
            with self.assertRaises(MoleError):
                read_source(root, root / "escape/secret.py")
            with self.assertRaises(MoleError):
                confined_output(root, root / "escape/docs")
            with self.assertRaises(MoleError):
                start(root, root / "escape/workspace", "standard", "repository")

    def test_inspect_redacts_and_checks_post_freshness_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            source = repo / "app.py"
            source.write_text('def f():\n    token = "abcdef123456"\n    return token\n')
            workspace = Path(tmp) / "workspace"
            start(repo, workspace, "standard", "repository")
            task = operate("next", workspace)["task"]
            result = operate("inspect", workspace, task=task["id"], budget_chars=12000)
            self.assertNotIn("abcdef123456", json.dumps(result))
            state = load(workspace)
            source.write_text("def f(): return 2\n")
            with self.assertRaises(MoleError) as caught:
                inspect(state, task, 12000, "0:0")
            self.assertEqual(caught.exception.code, "TASK_STALE")

    def test_document_and_unsupported_language_coverage_are_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            (repo / "process.md").write_text("A reviewer approves an order before dispatch.\n")
            (repo / "app.js").write_text("function dispatch() {}\n")
            workspace = Path(tmp) / "workspace"
            start(repo, workspace, "standard", "repository")
            result = operate("next", workspace)
            self.assertEqual(result["task"]["kind"], "document_review")
            state = load(workspace)
            self.assertEqual(state["scan"]["model"]["symbols"], [])
            self.assertIn("reduced_coverage_no_ast_adapter", [x["reason"] for x in state["scan"]["limitations"]])

    @unittest.skipUnless(os.name == "posix" and os.geteuid() != 0, "Requires non-root POSIX permissions")
    def test_real_permission_denial_does_not_change_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            workspace = Path(tmp) / "workspace"
            start(repo, workspace, "standard", "repository")
            state_path = workspace / "state.json"
            before = state_path.read_bytes()
            try:
                state_path.chmod(0)
                with self.assertRaises(PermissionError):
                    operate("status", workspace)
            finally:
                state_path.chmod(0o600)
            self.assertEqual(state_path.read_bytes(), before)
