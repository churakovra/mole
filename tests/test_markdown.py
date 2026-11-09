import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/mole"))
from molekit.errors import MoleError
from molekit.pipeline import start, operate
from molekit.output import resolve_output
from molekit.workspace import load


class MarkdownTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        (self.repo / "app.py").write_text("def f(): return 1\n")
        self.workspace = Path(self.temp.name) / "workspace"
        self.output = self.repo / "docs/workflows"
        start(self.repo, self.workspace, "standard", "repository")
        task = operate("next", self.workspace)["task"]
        response = Path(self.temp.name) / "patch.json"
        response.write_text(json.dumps({"protocolVersion": "1.0", "taskId": task["id"],
            "baseRevision": task["baseRevision"], "claims": [{"id": "claim-f", "statement": "f is declared",
            "status": "source_observed", "evidenceIds": task["evidenceIds"], "limitations": []}]}))
        operate("submit", self.workspace, input=response)

    def finish(self):
        return operate("finish", self.workspace, output=self.output, allow_partial=True)

    def test_documentation_and_manual_sections_survive_regeneration(self):
        result = self.finish()
        self.assertEqual(result["status"], "PARTIAL")
        process = next((resolve_output(self.output) / "processes").glob("*.md"))
        self.assertIn("source_observed", process.read_text())
        self.assertIn("app.py", process.read_text())
        path = resolve_output(self.output) / "README.md"
        path.write_text(path.read_text().replace("<!-- mole:manual:start -->", "<!-- mole:manual:start -->\nMy notes"))
        self.finish()
        self.assertIn("My notes", (resolve_output(self.output) / "README.md").read_text())
        self.assertEqual(operate("next", self.workspace)["status"], "PARTIAL")

    def test_generated_edit_conflict_is_preserved(self):
        self.finish()
        path = resolve_output(self.output) / "README.md"
        path.write_text(path.read_text().replace("# System workflows", "# My authored version"))
        before = path.read_bytes()
        with self.assertRaises(MoleError) as caught:
            self.finish()
        self.assertEqual(caught.exception.code, "OUTPUT_CONFLICT")
        self.assertEqual(path.read_bytes(), before)

    def test_interrupted_export_recovers(self):
        from molekit.markdown import atomic_text
        calls = []
        def interrupted(path, content):
            calls.append(path)
            if len(calls) == 2:
                raise OSError("disk interrupted")
            atomic_text(path, content)
        with patch("molekit.markdown.atomic_text", side_effect=interrupted):
            with self.assertRaises(OSError):
                self.finish()
        self.assertEqual(load(self.workspace)["status"], "EXPORTING")
        self.assertEqual(self.finish()["status"], "PARTIAL")

    def test_partial_export_requires_explicit_flag(self):
        (self.repo / "legacy.py").write_text("print 'old'\n")
        other = Path(self.temp.name) / "other"
        start(self.repo, other, "quick", "repository")
        operate("next", other)
        with self.assertRaises(MoleError):
            operate("finish", other, output=self.output)
        output = Path(self.temp.name) / "partial"
        result = operate("finish", other, output=output, allow_partial=True)
        self.assertEqual(result["status"], "PARTIAL")
        self.assertIn("PARTIAL", (resolve_output(output) / "README.md").read_text())

    def test_output_cannot_hide_indexed_source_changes(self):
        with self.assertRaises(MoleError) as caught:
            operate("finish", self.workspace, output=self.repo, allow_partial=True)
        self.assertEqual(caught.exception.code, "UNSAFE_PATH")
        source_dir = self.repo / "source-docs"
        source_dir.mkdir()
        (source_dir / "input.py").write_text("def g(): return 2\n")
        workspace = Path(self.temp.name) / "new-session"
        start(self.repo, workspace, "standard", "repository")
        operate("next", workspace)
        with self.assertRaises(MoleError) as caught:
            operate("finish", workspace, output=source_dir, allow_partial=True)
        self.assertEqual(caught.exception.code, "UNSAFE_PATH")

    def test_partial_tasks_can_resume_and_unknown_claim_is_rendered(self):
        workspace = Path(self.temp.name) / "partial-session"
        start(self.repo, workspace, "standard", "repository")
        task = operate("next", workspace)["task"]
        output = Path(self.temp.name) / "partial-output"
        operate("finish", workspace, output=output, allow_partial=True)
        self.assertEqual(operate("next", workspace)["status"], "NEEDS_ANALYSIS")
        response = Path(self.temp.name) / "unknown.json"
        response.write_text(json.dumps({"protocolVersion": "1.0", "taskId": task["id"],
            "baseRevision": task["baseRevision"], "claims": [{"id": "claim-unknown",
            "statement": "Owner must confirm retention obligations", "status": "unknown",
            "evidenceIds": [], "limitations": ["No business policy supplied"]}]}))
        operate("submit", workspace, input=response)
        operate("finish", workspace, output=output, allow_partial=True)
        self.assertIn("Owner must confirm", (resolve_output(output) / "quality-report.md").read_text())
