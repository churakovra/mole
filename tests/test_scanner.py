from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/mole"))
from molekit.scanner import scan, PARSER_VERSION
from molekit.workspace import read_json, atomic_json
from molekit.pipeline import start, operate


class ScannerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        self.workspace = Path(self.temp.name) / "workspace"
        self.workspace.mkdir()

    def test_static_calls_and_cache_invalidation(self):
        path = self.repo / "app.py"
        path.write_text("def child():\n    return 1\ndef parent():\n    return child() + child()\n")
        first = scan(self.repo, self.workspace)
        self.assertEqual(len(first["model"]["relationships"]), 2)
        self.assertTrue(all(e["resolution"] == "possible" for e in first["model"]["relationships"]))
        second = scan(self.repo, self.workspace)
        self.assertEqual(second["stats"]["reused"], 1)
        self.assertEqual(first["model"], second["model"])
        path.write_text("def child():\n    return 2\n")
        third = scan(self.repo, self.workspace)
        self.assertNotEqual(first["model"]["revision"], third["model"]["revision"])
        self.assertEqual(third["stats"]["parsed"], 1)

    def test_no_execution_secrets_symlink_and_ignore(self):
        sentinel = Path(self.temp.name) / "executed"
        (self.repo / "app.py").write_text(
            "from pathlib import Path\nPath(" + repr(str(sentinel)) + ").touch()\ndef safe():\n    return 1\n")
        (self.repo / ".env").write_text("TOKEN=private")
        (self.repo / ".gitignore").write_text("ignored/\n*.tmp\n!keep.tmp\n")
        (self.repo / "ignored").mkdir()
        (self.repo / "ignored" / "bad.py").write_text("def bad(): pass")
        (self.repo / "omit.tmp").write_text("omitted")
        (self.repo / "keep.tmp").write_text("kept")
        try:
            (self.repo / "escaped.py").symlink_to(sentinel)
        except OSError:
            pass
        result = scan(self.repo, self.workspace)
        paths = {r["path"] for r in result["index"]}
        self.assertIn("keep.tmp", paths)
        self.assertNotIn("omit.tmp", paths)
        self.assertNotIn(".env", paths)
        self.assertNotIn("ignored/bad.py", paths)
        self.assertNotIn("escaped.py", paths)
        self.assertFalse(sentinel.exists())

    def test_unsupported_syntax_reported(self):
        (self.repo / "legacy.py").write_text("print 'python2'\n")
        result = scan(self.repo, self.workspace)
        self.assertEqual(result["limitations"][0]["reason"], "PARSER_UNSUPPORTED_SYNTAX")

    def test_overload_declarations_and_invalid_cache(self):
        (self.repo / "app.py").write_text(
            "from typing import overload\n@overload\ndef f(x: int): ...\n"
            "@overload\ndef f(x: str): ...\ndef f(x): return x\n")
        first = scan(self.repo, self.workspace)
        self.assertEqual(len(first["model"]["symbols"]), 1)
        self.assertEqual(len(first["model"]["symbols"][0]["sourceRefs"]), 3)
        cache = read_json(self.workspace / "scan-cache.json")
        cache["app.py"].pop("facts")
        atomic_json(self.workspace / "scan-cache.json", cache)
        second = scan(self.repo, self.workspace)
        self.assertEqual(second["stats"]["parsed"], 1)
        self.assertEqual(first["model"], second["model"])
        cache = read_json(self.workspace / "scan-cache.json")
        cache["app.py"]["parser"] = PARSER_VERSION + "-different-host"
        atomic_json(self.workspace / "scan-cache.json", cache)
        self.assertEqual(scan(self.repo, self.workspace)["stats"]["parsed"], 1)

    def test_cli_pipeline_records_real_scan(self):
        (self.repo / "app.py").write_text("def f(): return 1\n")
        start(self.repo, self.workspace, "standard", "repository")
        result = operate("next", self.workspace)
        self.assertEqual(result["status"], "NEEDS_ANALYSIS")
        self.assertIsNotNone(result["revision"])
