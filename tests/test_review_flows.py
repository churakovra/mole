import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/mole"))
from molekit.adapters import enrich
from molekit.agent import create_tasks
from molekit.scanner import scan
from molekit.agent import accept_patch


class ReviewFlowTests(unittest.TestCase):
    def test_later_external_import_does_not_resolve_to_shadowed_local_and_reexports_cite_bindings(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as repo:
            root = Path(repo)
            (root / 'api.py').write_text('def run(): return 1\nfrom unknown_library import run\ndef main(): return run()\n')
            result = enrich(scan(root, tmp))
            self.assertFalse(any(edge['kind'] == 'calls' for edge in result['model']['relationships']))
            (root / 'api.py').write_text('from exports import helper as go\ndef main(): return go()\n')
            (root / 'exports.py').write_text('from service import helper\n')
            (root / 'service.py').write_text('def helper(): return 1\n')
            result = enrich(scan(root, tmp))
            evidence = {ev['id']:ev for ev in result['model']['evidence']}
            sources = {source['id']:source for source in result['model']['sources']}
            edge = next(edge for edge in result['model']['relationships'] if edge['kind']=='calls')
            self.assertEqual({sources[evidence[eid]['sourceId']]['path'] for eid in edge['evidenceIds']}, {'api.py','exports.py'})

    def test_local_declaration_shadows_earlier_import(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as repo:
            Path(repo, "external.py").write_text("def run(): return 10\n")
            Path(repo, "api.py").write_text("from external import run\ndef run(): return 20\ndef main(): return run()\n")
            result = enrich(scan(repo, tmp))
            operations = {op["id"]: op for op in result["model"]["operations"]}
            calls = [edge for edge in result["model"]["relationships"] if edge["kind"] == "calls"]
            self.assertEqual([operations[edge["target"]]["title"] for edge in calls], ["api.run"])

    def test_custom_objects_collection_is_not_a_django_model(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as repo:
            Path(repo, "app.py").write_text("class Cache:\n    objects = set()\ndef f(): Cache.objects.add(1)\n")
            result = enrich(scan(repo, tmp))
            self.assertNotIn("db_write", {op["kind"] for op in result["model"]["operations"]})
    def test_control_metadata_never_persists_sensitive_loop_literals(self):
        for statement in ("for item in {'api_key':'abcdef123456SECRET'}:", "while {'api_key':'abcdef123456SECRET'}:"):
            with self.subTest(statement=statement), tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as repo:
                Path(repo, "app.py").write_text("def f():\n    " + statement + "\n        break\n")
                result = enrich(scan(repo, tmp))
                self.assertNotIn("abcdef123456SECRET", json.dumps(result))
                self.assertNotIn("abcdef123456SECRET", Path(tmp, "scan-cache.json").read_text())
                self.assertFalse(any('abcdef123456SECRET' in path.read_text() for path in Path(tmp,'.objects').glob('*.json')))
    def test_cross_file_http_db_publish_consumer_share_one_review_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = enrich(scan(Path(__file__).parent / "fixtures/cross-file-workflow", tmp))
            tasks = create_tasks(result, "standard")
            workflow = next(task for task in tasks if task["kind"] == "workflow_review")
            evidence = {ev["id"]: ev for ev in result["model"]["evidence"]}
            sources = {src["id"]: src for src in result["model"]["sources"]}
            paths = {sources[evidence[e]["sourceId"]]["path"] for e in workflow["evidenceIds"]}
            self.assertEqual(paths, {"api.py", "service.py", "repository.py", "publisher.py", "worker.py"})
            operations = {op["id"]: op for op in result["model"]["operations"]}
            titles = {operations[op]["title"] for op in workflow["operationIds"]}
            self.assertTrue({"service.execute", "repository.Store.save", "repository.Store.validate", "worker.handle_order"} <= titles)
            self.assertTrue(all(edge["resolution"] != "observed_runtime" for edge in result["model"]["relationships"]))
            self.assertTrue(any(edge["kind"] == "message_channel_candidate" for edge in result["model"]["relationships"]))
            state = {"scan": result, "revision": result["model"]["revision"]}
            patch = {"protocolVersion": "1.0", "taskId": workflow["id"], "baseRevision": state["revision"],
                "claims": [{"id": "claim-candidate-workflow", "statement": "Static references connect the order entry to storage and messaging candidates.",
                            "status": "inferred", "evidenceIds": workflow["evidenceIds"], "limitations": ["Runtime dispatch and delivery are unproven"]}],
                "scenarios": [{"id": "semantic-order", "title": "Order processing", "trigger": "HTTP order request",
                    "operationIds": workflow["operationIds"], "claimIds": ["claim-candidate-workflow"],
                    "outcomes": [], "unknowns": ["Broker/runtime behavior unverified"]}]}
            accept_patch(state, workflow, patch)
            self.assertEqual(result["semantic"]["scenarios"][0]["operationIds"], workflow["operationIds"])

    def test_aliases_reexports_self_and_class_receivers(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as repo:
            root = Path(repo)
            (root / "pkg").mkdir()
            (root / "pkg/__init__.py").write_text("from .service import helper\n")
            (root / "pkg/service.py").write_text("def helper(): return 1\n")
            (root / "models.py").write_text("class Worker:\n    def run(self): return self.check()\n    def check(self): return 2\n")
            (root / "api.py").write_text("from pkg import helper as go\nfrom models import Worker\ndef main():\n    worker = Worker()\n    return worker.run() + go()\n")
            result = enrich(scan(root, tmp))
            operations = {op["id"]: op for op in result["model"]["operations"]}
            targets = {operations[edge["target"]]["title"] for edge in result["model"]["relationships"] if edge["kind"] == "calls"}
            self.assertTrue({"pkg.service.helper", "models.Worker.run", "models.Worker.check"} <= targets)

    def test_except_and_rollback_are_not_an_unconditional_happy_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = enrich(scan(Path(__file__).parent / "fixtures/cross-file-workflow", tmp))
            model = result["model"]
            operations = {op["id"]: op for op in model["operations"]}
            rollback = next(op for op in model["operations"] if op["title"].endswith("Session.rollback"))
            self.assertTrue(any("except ValueError" in context for context in rollback["control"]))
            incoming = [edge for edge in model["relationships"] if edge["target"] == rollback["id"]]
            self.assertTrue(incoming)
            self.assertFalse(any(operations[edge["source"]]["title"].endswith("Session.commit")
                                 and edge["kind"] != "exception_path_candidate" for edge in incoming))
            self.assertTrue(all("unverified" in edge["condition"] for edge in incoming
                                if operations[edge["source"]]["title"].endswith("Session.commit")))

    def test_imported_library_does_not_turn_set_add_into_db_write(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as repo:
            Path(repo, "app.py").write_text("import sqlalchemy\ndef f():\n    seen = set()\n    seen.add(1)\n")
            result = enrich(scan(repo, tmp))
            self.assertNotIn("db_write", {op["kind"] for op in result["model"]["operations"]})
