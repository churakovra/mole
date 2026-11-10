import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/mole"))
from molekit.errors import MoleError
from molekit.model import empty_model, validate_model


def golden_model():
    model = empty_model("rev-1")
    model["sources"] = [{"id": "src-1", "path": "app.py", "revision": "rev-1",
                         "lineStart": 1, "lineEnd": 2, "kind": "source_code"}]
    model["evidence"] = [{"id": "ev-1", "sourceId": "src-1", "observation": "Function exists",
                          "extractor": "python-ast-v1", "excerptHash": "abc",
                          "classification": "source_code"}]
    model["claims"] = [{"id": "claim-1", "statement": "Function declared",
                        "status": "source_observed", "evidenceIds": ["ev-1"], "limitations": []}]
    model["symbols"] = [{"id": "symbol-1", "kind": "function", "qualifiedName": "app.f",
                         "sourceRefs": ["src-1"]}]
    return model


class ModelTests(unittest.TestCase):
    def test_golden_round_trip(self):
        model = golden_model()
        self.assertEqual(validate_model(json.loads(json.dumps(model))), model)

    def test_invalid_models(self):
        mutations = [lambda m: m["claims"][0].update(status="proven"),
                     lambda m: m["claims"][0].update(status="runtime_verified"),
                     lambda m: m["claims"][0].update(evidenceIds=[]),
                     lambda m: m["evidence"][0].update(sourceId="missing"),
                     lambda m: m["sources"][0].update(path="../secret"),
                     lambda m: m["sources"][0].update(revision="stale"),
                     lambda m: m["sources"][0].update(lineStart=True),
                     lambda m: m["sources"].append(copy.deepcopy(m["sources"][0])),
                     lambda m: m.update(schemaVersion=2)]
        for mutation in mutations:
            model = golden_model()
            mutation(model)
            with self.subTest(model=model):
                with self.assertRaises(MoleError):
                    validate_model(model)

    def test_inferred_requires_limitations(self):
        model = golden_model()
        model["claims"][0].update(status="inferred", evidenceIds=[])
        with self.assertRaises(MoleError):
            validate_model(model)
        model["claims"][0]["limitations"] = ["Source not available"]
        validate_model(model)

    def test_static_edge_cannot_be_runtime_observation(self):
        model = golden_model()
        model["relationships"] = [{"id": "edge-1", "source": "symbol-1", "target": "symbol-1",
                                   "kind": "calls", "resolution": "observed_runtime",
                                   "evidenceIds": ["ev-1"], "condition": ""}]
        with self.assertRaises(MoleError):
            validate_model(model)
        model["relationships"][0]["resolution"] = "possible"
        validate_model(model)

    def test_missing_fact_provenance_rejected(self):
        for collection, item in [
            ("symbols", {"id": "s2", "kind": "function", "qualifiedName": "f", "sourceRefs": []}),
            ("operations", {"id": "o1", "kind": "db_write", "title": "Deletes data", "evidenceIds": []}),
            ("businessSteps", {"id": "b1", "what": "Deletes data", "why": "policy", "operationIds": [], "claimIds": []}),
        ]:
            model = golden_model()
            model[collection].append(item)
            with self.subTest(collection=collection):
                with self.assertRaises(MoleError):
                    validate_model(model)

    def test_view_requires_edge_endpoints(self):
        model = golden_model()
        model["relationships"] = [{"id": "r1", "source": "symbol-1", "target": "symbol-1",
                                   "kind": "calls", "resolution": "possible",
                                   "evidenceIds": ["ev-1"], "condition": ""}]
        model["diagramViews"] = [{"id": "v1", "title": "view", "scenarioIds": [],
                                  "nodes": [], "edgeIds": ["r1"], "childRefs": []}]
        with self.assertRaises(MoleError):
            validate_model(model)
        model["diagramViews"][0]["nodes"] = [{"id": "symbol-1", "label": "f"}]
        validate_model(model)
