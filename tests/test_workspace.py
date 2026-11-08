import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "mole"))
from molekit.errors import MoleError
from molekit.pipeline import start, operate, transition
from molekit.workspace import atomic_json, load, locked


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        self.workspace = Path(self.temp.name) / "workspace"

    def start(self):
        return start(self.repo, self.workspace, "standard", "repository")

    def test_start_resume_and_conflict(self):
        initial = self.start()
        self.assertEqual(self.start(), initial)
        self.assertEqual(operate("status", self.workspace)["runId"], initial["runId"])
        with self.assertRaisesRegex(MoleError, "different request"):
            start(self.repo, self.workspace, "deep", "repository")

    def test_lock_is_exclusive_and_released_on_error(self):
        self.start()
        with locked(self.workspace):
            with self.assertRaisesRegex(MoleError, "locked"):
                with locked(self.workspace):
                    self.fail("second lock acquired")
        with locked(self.workspace):
            self.assertEqual(load(self.workspace)["status"], "NEW")

    def test_corrupt_state_not_overwritten(self):
        self.start()
        path = self.workspace / "state.json"
        path.write_text("{invalid", encoding="utf-8")
        with self.assertRaises(MoleError):
            self.start()
        self.assertEqual(path.read_text(), "{invalid")

    def test_invalid_transition_and_unvalidated_finish(self):
        self.start()
        state = load(self.workspace)
        with self.assertRaisesRegex(MoleError, "Invalid transition"):
            transition(state, "COMPLETED")
        with self.assertRaises(MoleError) as caught:
            operate("finish", self.workspace, output=str(self.repo / "docs"))
        self.assertEqual(caught.exception.exit_code, 6)

    def test_malformed_state_fields_return_structured_error(self):
        self.start()
        baseline = load(self.workspace)
        for field, value in [("status", []), ("runId", None), ("tasks", [0]),
                             ("manifest", {}), ("submissions", {"a": 1}),
                             ("tasks", [{"id": "bad", "status": "pending"}])]:
            with self.subTest(field=field):
                state = {**baseline, field: value}
                atomic_json(self.workspace / "state.json", state)
                with self.assertRaises(MoleError) as caught:
                    operate("status", self.workspace)
                self.assertEqual(caught.exception.code, "STATE_CORRUPT")

    def test_cli_corruption_preserves_json_contract(self):
        self.start()
        state = load(self.workspace)
        state.pop("runId")
        atomic_json(self.workspace / "state.json", state)
        entry = Path(__file__).resolve().parents[1] / "skills/mole/scripts/mole.py"
        result = subprocess.run([sys.executable, str(entry), "status", "--workspace",
                                 str(self.workspace), "--json"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 5, result.stderr)
        self.assertEqual(json.loads(result.stdout)["error"]["code"], "STATE_CORRUPT")

    def test_failed_atomic_replace_preserves_checkpoint(self):
        self.start()
        before = (self.workspace / "state.json").read_bytes()
        with patch("molekit.workspace.os.replace", side_effect=OSError("interrupted")):
            with self.assertRaises(OSError):
                atomic_json(self.workspace / "state.json", {"invalid": True})
        self.assertEqual((self.workspace / "state.json").read_bytes(), before)
        self.assertEqual(list(self.workspace.glob(".mole-*")), [])

    def test_generated_checkpoint_cannot_exceed_reader_complexity(self):
        self.start()
        before = (self.workspace / "state.json").read_bytes()
        nested = []
        for _ in range(65):
            nested = [nested]
        with self.assertRaises(MoleError):
            atomic_json(self.workspace / "state.json", nested)
        self.assertEqual((self.workspace / "state.json").read_bytes(), before)

    def test_lock_released_after_process_termination(self):
        self.start()
        payload = Path(__file__).resolve().parents[1] / "skills/mole"
        script = ("import sys,time; sys.path.insert(0,sys.argv[1]); "
                  "from molekit.workspace import locked; "
                  "lock=locked(sys.argv[2]); lock.__enter__(); "
                  "print('locked',flush=True); time.sleep(30)")
        child = subprocess.Popen([sys.executable, "-c", script, str(payload),
                                  str(self.workspace)], stdout=subprocess.PIPE, text=True)
        try:
            self.assertEqual(child.stdout.readline().strip(), "locked")
            with self.assertRaises(MoleError):
                operate("status", self.workspace)
        finally:
            child.kill()
            child.wait(timeout=5)
            child.stdout.close()
        self.assertEqual(operate("status", self.workspace)["status"], "NEW")

    def test_duplicate_and_stale_submission(self):
        (self.repo / "app.py").write_text("def f(): return 1\n")
        self.start()
        task = operate("next", self.workspace)["task"]
        path = Path(self.temp.name) / "patch.json"
        path.write_text(json.dumps({"taskId": task["id"], "baseRevision": "b"}))
        with self.assertRaises(MoleError) as caught:
            operate("submit", self.workspace, input=path)
        self.assertEqual(caught.exception.code, "TASK_STALE")

    def test_symlink_state_rejected(self):
        self.start()
        path = self.workspace / "state.json"
        other = self.repo / "state.json"
        path.rename(other)
        try:
            path.symlink_to(other)
        except OSError:
            self.skipTest("symlink permission unavailable")
        with self.assertRaises(MoleError):
            operate("status", self.workspace)
