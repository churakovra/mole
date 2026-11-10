import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/mole"))
from molekit.errors import MoleError
from molekit.pipeline import start, operate
from molekit.workspace import load, atomic_json


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        self.source = self.repo / "app.py"
        self.source.write_text("def f():\n" + "    value = 1\n" * 100 + "    return value\n")
        self.workspace = Path(self.temp.name) / "workspace"
        start(self.repo, self.workspace, "standard", "repository")
        self.active = operate("next", self.workspace)
        self.task = self.active["task"]

    def patch(self, **changes):
        patch = {"protocolVersion": "1.0", "taskId": self.task["id"],
                 "baseRevision": self.active["revision"], "claims": [{
                     "id": "claim-purpose", "statement": "Purpose is unknown from local code alone.",
                     "status": "unknown", "evidenceIds": self.task["evidenceIds"],
                     "limitations": ["Business context absent"]}]}
        patch.update(changes)
        path = Path(self.temp.name) / "patch.json"
        path.write_text(json.dumps(patch))
        return path

    def test_real_submission_and_idempotent_duplicate(self):
        path = self.patch()
        result = operate("submit", self.workspace, input=path)
        self.assertEqual(result["status"], "VALIDATING")
        self.assertTrue(operate("submit", self.workspace, input=path)["duplicate"])
        path = self.patch(claims=[])
        with self.assertRaises(MoleError) as caught:
            operate("submit", self.workspace, input=path)
        self.assertEqual(caught.exception.code, "TASK_CONFLICT")

    def test_bounded_paginated_inspection(self):
        cursor = "0:0"
        lines = []
        for _ in range(100):
            page = operate("inspect", self.workspace, task=self.task["id"], budget_chars=2200, cursor=cursor)
            self.assertLessEqual(len(json.dumps(page)), 2200)
            lines.extend(item["line"] for item in page["context"])
            cursor = page["nextCursor"]
            if cursor is None:
                break
        self.assertIsNone(cursor)
        self.assertIn(1, lines)
        self.assertIn(102, lines)

    def test_stale_source_and_wrong_evidence_rejected(self):
        path = self.patch(claims=[{"id": "bad", "statement": "fabricated", "status": "source_observed",
                                  "evidenceIds": ["missing"], "limitations": []}])
        with self.assertRaises(MoleError) as caught:
            operate("submit", self.workspace, input=path)
        self.assertEqual(caught.exception.code, "INSUFFICIENT_EVIDENCE")
        path = self.patch()
        self.source.write_text("def f(): return 2\n")
        with self.assertRaises(MoleError) as caught:
            operate("submit", self.workspace, input=path)
        self.assertEqual(caught.exception.code, "TASK_STALE")

    def test_bad_budget_cursor_and_patch_types(self):
        for budget, cursor in [(10, "0:0"), (2000, "-1:0"), (2000, "garbage")]:
            with self.assertRaises(MoleError):
                operate("inspect", self.workspace, task=self.task["id"], budget_chars=budget, cursor=cursor)
        with self.assertRaises(MoleError):
            operate("submit", self.workspace, input=self.patch(claims="bad"))

    def test_malformed_task_evidence_is_rejected_on_load(self):
        state = load(self.workspace)
        state["tasks"][0]["evidenceIds"] = ["missing"]
        atomic_json(self.workspace / "state.json", state)
        with self.assertRaises(MoleError) as caught:
            operate("inspect", self.workspace, task=self.task["id"], budget_chars=2000)
        self.assertEqual(caught.exception.code, "STATE_CORRUPT")

    def test_long_metadata_never_exceeds_minimum_budget(self):
        directory = self.repo
        for _ in range(5):
            directory = directory / ("x" * 150)
            directory.mkdir()
        self.source.rename(directory / "app.py")
        other = Path(self.temp.name) / "workspace2"
        start(self.repo, other, "standard", "repository")
        task = operate("next", other)["task"]
        with self.assertRaises(MoleError) as caught:
            operate("inspect", other, task=task["id"], budget_chars=1024)
        self.assertEqual(caught.exception.code, "INVALID_BUDGET")
