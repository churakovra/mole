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
from molekit.workspace import load, atomic_json


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        (self.repo / "a.py").write_text("def a(): return 1\n")
        (self.repo / "b.py").write_text("def b(): return 2\n")
        self.workspace = Path(self.temp.name) / "workspace"
        self.output = self.repo / "docs/workflows"
        start(self.repo, self.workspace, "standard", "repository")
        while True:
            result = operate("next", self.workspace)
            if result["task"] is None:
                break
            task = result["task"]
            path = Path(self.temp.name) / "patch.json"
            path.write_text(json.dumps({"protocolVersion": "1.0", "taskId": task["id"],
                "baseRevision": task["baseRevision"], "claims": [{"id": "claim-" + task["id"],
                "statement": "A callable is declared", "status": "source_observed",
                "evidenceIds": task["evidenceIds"], "limitations": []}]}))
            operate("submit", self.workspace, input=path)
        operate("finish", self.workspace, output=self.output, allow_partial=True)

    def test_changed_file_invalidates_only_affected_claims(self):
        path = resolve_output(self.output) / "README.md"
        path.write_text(path.read_text().replace("<!-- mole:manual:start -->", "<!-- mole:manual:start -->\nKeep this note"))
        old_revision = load(self.workspace)["revision"]
        (self.repo / "a.py").write_text("def a(): return 3\n")
        self.assertEqual(operate("diff", self.workspace)["changes"]["changed"], ["a.py"])
        result = operate("update", self.workspace)
        self.assertEqual(result["changes"]["reusedClaims"], 1)
        self.assertEqual(len(result["changes"]["invalidatedClaims"]), 1)
        self.assertEqual(result["summary"]["pendingTasks"], 1)
        self.assertTrue((self.workspace / "history" / (old_revision + ".json")).exists())
        operate("finish", self.workspace, output=self.output, allow_partial=True)
        self.assertIn("Keep this note", (resolve_output(self.output) / "README.md").read_text())
        self.assertIn("a.py", (resolve_output(self.output) / "change-report.md").read_text())

    def test_unchanged_update_preserves_tasks_and_cache(self):
        before = load(self.workspace)
        result = operate("update", self.workspace)
        self.assertEqual(result["changes"]["changed"], [])
        self.assertEqual(load(self.workspace), before)

    def test_parser_version_change_reopens_semantic_review(self):
        state = load(self.workspace)
        state["scan"]["parserVersion"] = "previous-parser"
        atomic_json(self.workspace / "state.json", state)
        with self.assertRaises(MoleError) as caught:
            operate("next", self.workspace)
        self.assertEqual(caught.exception.code, "TASK_STALE")
        result = operate("update", self.workspace)
        self.assertTrue(result["changes"]["parserChanged"])
        self.assertEqual(result["changes"]["reusedClaims"], 0)
        self.assertEqual(result["summary"]["pendingTasks"], 2)

    def test_exact_rename_retains_symbol_and_process_ids(self):
        before = load(self.workspace)
        ids = {s["id"] for s in before["scan"]["model"]["symbols"]}
        (self.repo / "a.py").rename(self.repo / "renamed.py")
        result = operate("update", self.workspace)
        self.assertEqual(result["changes"]["renames"], {"a.py": "renamed.py"})
        after = load(self.workspace)
        self.assertEqual(ids, {s["id"] for s in after["scan"]["model"]["symbols"]})
        operate("finish", self.workspace, output=self.output, allow_partial=True)
        self.assertEqual({s["id"] for s in before["scan"]["model"]["scenarios"]},
                         {s["id"] for s in load(self.workspace)["scan"]["model"]["scenarios"]})
        first = load(self.workspace)
        (self.repo / "b.py").write_text("def b(): return 9\n")
        operate("update", self.workspace)
        second = load(self.workspace)
        self.assertEqual({s["id"] for s in first["scan"]["model"]["symbols"]},
                         {s["id"] for s in second["scan"]["model"]["symbols"]})
        self.assertEqual({o["id"] for o in first["scan"]["model"]["operations"] if o["kind"] not in {"scenario_summary", "component_summary"}},
                         {o["id"] for o in second["scan"]["model"]["operations"] if o["kind"] not in {"scenario_summary", "component_summary"}})
        renamed = self.repo / "renamed.py"
        renamed.write_text("\n" + renamed.read_text())
        operate("update", self.workspace)
        self.assertEqual({o["id"] for o in second["scan"]["model"]["operations"] if o["kind"] not in {"scenario_summary", "component_summary"}},
                         {o["id"] for o in load(self.workspace)["scan"]["model"]["operations"] if o["kind"] not in {"scenario_summary", "component_summary"}})

    def test_removed_process_keeps_manual_notes_and_is_retired(self):
        process = next(path for path in (resolve_output(self.output) / "processes").glob("*.md") if "a.a" in path.read_text())
        process.write_text(process.read_text().replace("<!-- mole:manual:start -->", "<!-- mole:manual:start -->\nOld owner notes"))
        (self.repo / "a.py").unlink()
        operate("update", self.workspace)
        operate("finish", self.workspace, output=self.output, allow_partial=True)
        process = resolve_output(self.output) / "processes" / process.name
        self.assertIn("Retired process", process.read_text())
        self.assertIn("Old owner notes", process.read_text())

    def test_old_patch_rejected_after_update(self):
        state = load(self.workspace)
        old_task = state["tasks"][0]
        (self.repo / "new.py").write_text("def new(): return 4\n")
        operate("update", self.workspace)
        patch = Path(self.temp.name) / "stale.json"
        patch.write_text(json.dumps({"taskId": old_task["id"], "baseRevision": state["revision"]}))
        with self.assertRaises(MoleError) as caught:
            operate("submit", self.workspace, input=patch)
        self.assertEqual(caught.exception.code, "TASK_STALE")

    def test_recreated_vacated_name_gets_distinct_identity(self):
        (self.repo / "a.py").rename(self.repo / "moved.py")
        operate("update", self.workspace)
        moved = next(s["id"] for s in load(self.workspace)["scan"]["model"]["symbols"] if s["qualifiedName"] == "moved.a")
        (self.repo / "a.py").write_text("def a(): return 999\n")
        operate("update", self.workspace)
        symbols = {s["qualifiedName"]: s["id"] for s in load(self.workspace)["scan"]["model"]["symbols"]}
        self.assertEqual(symbols["moved.a"], moved)
        self.assertNotEqual(symbols["moved.a"], symbols["a.a"])
        (self.repo / "b.py").write_text("def b(): return 88\n")
        operate("update", self.workspace)
        self.assertEqual(symbols, {s["qualifiedName"]: s["id"] for s in load(self.workspace)["scan"]["model"]["symbols"]})

    def test_failed_update_preserves_authoritative_checkpoint(self):
        before = (self.workspace / "state.json").read_bytes()
        (self.repo / "a.py").write_text("def a(): return 7\n")
        from molekit.workspace import atomic_json
        def interrupted(path, value):
            if path.name == "state.json":
                raise OSError("interrupted commit")
            atomic_json(path, value)
        with patch("molekit.update.atomic_json", side_effect=interrupted):
            with self.assertRaises(OSError):
                operate("update", self.workspace)
        self.assertEqual((self.workspace / "state.json").read_bytes(), before)
        self.assertEqual(operate("update", self.workspace)["changes"]["changed"], ["a.py"])

    def test_incomplete_inventory_is_unknown_not_removal(self):
        before = (self.workspace / 'state.json').read_bytes()
        with patch('molekit.update.inventory', return_value=([], [{'path': '.', 'reason': 'inventory_budget_exceeded'}])):
            report = operate('diff', self.workspace)
            self.assertEqual(report['status'], 'PARTIAL')
            self.assertEqual(report['changes']['removed'], [])
            self.assertEqual(report['changes']['inventory']['unknownPaths'], ['a.py', 'b.py'])
            with self.assertRaises(MoleError) as caught:
                operate('update', self.workspace)
            self.assertEqual(caught.exception.code, 'INCOMPLETE_INVENTORY')
        self.assertEqual((self.workspace / 'state.json').read_bytes(), before)

    def test_source_update_can_resume_after_interrupted_export(self):
        (self.repo / 'a.py').write_text('def a(): return 3\n')
        operate('update', self.workspace)
        with patch('molekit.markdown.atomic_text', side_effect=OSError('interrupt')):
            with self.assertRaises(OSError):
                operate('finish', self.workspace, output=self.output, allow_partial=True)
        self.assertEqual(load(self.workspace)['status'], 'EXPORTING')
        (self.repo / 'a.py').write_text('def a(): return 4\n')
        result = operate('update', self.workspace)
        self.assertEqual(result['changes']['changed'], ['a.py'])
        self.assertNotIn('pendingExport', load(self.workspace))
        operate('finish', self.workspace, output=self.output, allow_partial=True)

    def test_unrelated_edit_in_same_file_keeps_unchanged_span_claim(self):
        from molekit.workspace import save_state
        (self.repo / 'a.py').write_text('def a(): return 1\n\ndef untouched(): return 5\n')
        operate('update', self.workspace)
        state = load(self.workspace)
        operation = next(op for op in state['scan']['model']['operations'] if op['title'] == 'a.untouched' and op['kind'] == 'function')
        state['scan']['model']['claims'].append({'id': 'claim-untouched', 'statement': 'untouched returns five',
            'status': 'source_observed', 'evidenceIds': operation['evidenceIds'], 'limitations': []})
        save_state(self.workspace, state)
        (self.repo / 'a.py').write_text('# Unrelated new comment\ndef a(): return 99\n\ndef untouched(): return 5\n')
        result = operate('update', self.workspace)
        self.assertNotIn('claim-untouched', result['changes']['invalidatedClaims'])
        claim = next(c for c in load(self.workspace)['scan']['model']['claims'] if c['id'] == 'claim-untouched')
        self.assertEqual(claim['evidenceIds'], operation['evidenceIds'])
