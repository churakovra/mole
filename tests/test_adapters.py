from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/mole"))
from molekit.adapters import enrich, trace
from molekit.scanner import scan


class AdapterTests(unittest.TestCase):
    def test_representative_framework_fixtures(self):
        expectations = {
            "fastapi-db-events": {"http_entry", "transaction_boundary", "db_write", "background_task", "publish", "async_boundary"},
            "django-transactions": {"transaction_boundary", "db_write", "http_route_candidate"},
            "consumer-retry-idempotency": {"consume", "acknowledgement", "async_boundary"},
        }
        for fixture, expected in expectations.items():
            with self.subTest(fixture=fixture), tempfile.TemporaryDirectory() as tmp:
                repo = Path(__file__).parent / "fixtures" / fixture
                result = enrich(scan(repo, tmp))
                self.assertTrue(expected <= {op["kind"] for op in result["model"]["operations"]})
                self.assertTrue(all(e["resolution"] == "possible" for e in result["model"]["relationships"]))
                origin = result["model"]["symbols"][0]["id"]
                forward = trace(result["model"], origin)
                self.assertIn(origin, forward["nodeIds"])
                self.assertTrue(forward["limitations"])
                backward = trace(result["model"], origin, "backward")
                self.assertIn(origin, backward["nodeIds"])

    def test_adapter_not_enabled_by_method_name_alone(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as repo:
            Path(repo, "app.py").write_text("def f(x):\n    return x.commit()\n")
            result = enrich(scan(repo, tmp))
            self.assertNotIn("transaction_boundary", {o["kind"] for o in result["model"]["operations"]})

    def test_trace_budget_terminates_cycles(self):
        model = {"relationships": [{"id": "e", "source": "s", "target": "s"}]}
        self.assertEqual(trace(model, "s")["nodeIds"], ["s"])
        self.assertEqual(trace(model, "s", max_depth=0)["boundaries"][0]["reason"], "trace_budget")
