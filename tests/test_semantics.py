import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/mole"))
from molekit.errors import MoleError
from molekit.pipeline import start, operate
from molekit.workspace import load


class SemanticAuthoringTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        (self.repo / "app.py").write_text("def approve(): return True\n")
        self.workspace = Path(self.temp.name) / "workspace"
        self.output = Path(self.temp.name) / "output"
        start(self.repo, self.workspace, "standard", "repository")
        self.task = operate("next", self.workspace)["task"]
        page = operate("inspect", self.workspace, task=self.task["id"], budget_chars=12000)
        self.op = page["operations"][0]["id"]

    def patch(self):
        return {"protocolVersion": "1.0", "taskId": self.task["id"], "baseRevision": self.task["baseRevision"],
            "claims": [{"id": "claim-purpose", "statement": "Approval intent is inferred from naming.",
                        "status": "inferred", "evidenceIds": self.task["evidenceIds"], "limitations": ["No business policy supplied"]}],
            "scenarios": [{"id": "semantic-approval", "title": "Approval review", "trigger": "Caller requests approval",
                           "operationIds": [self.op], "claimIds": ["claim-purpose"], "outcomes": [], "unknowns": ["Actual business policy unknown"]}],
            "businessSteps": [{"id": "semantic-approve-step", "what": "Review approval", "why": "Intent inferred from callable name",
                               "operationIds": [self.op], "claimIds": ["claim-purpose"]}],
            "glossary": [{"id": "semantic-term-approval", "term": "Approval", "definition": "An inferred review decision; policy is unknown.",
                          "claimIds": ["claim-purpose"]}]}

    def submit(self, value):
        path = Path(self.temp.name) / "patch.json"
        path.write_text(json.dumps(value))
        return operate("submit", self.workspace, input=path)

    def test_named_scenario_business_mapping_glossary_and_regeneration(self):
        self.submit(self.patch())
        operate("finish", self.workspace, output=self.output)
        self.assertIn("Approval", (self.output / "glossary.md").read_text())
        process = self.output / "processes/semantic-approval.md"
        self.assertIn("Business mapping", process.read_text())
        self.assertIn("inferred", process.read_text())
        self.assertIn("Approval review", (self.output / "explorer.html").read_text())
        operate("finish", self.workspace, output=self.output)
        self.assertEqual(len(load(self.workspace)["scan"]["semantic"]["scenarios"]), 1)

    def test_authored_knowledge_reused_then_invalidated_with_its_evidence(self):
        self.submit(self.patch())
        (self.repo / "other.py").write_text("def other(): return 1\n")
        operate("update", self.workspace)
        self.assertEqual(len(load(self.workspace)["scan"]["semantic"]["scenarios"]), 1)
        (self.repo / "app.py").write_text("def approve(): return False\n")
        report = operate("update", self.workspace)["changes"]
        self.assertIn("semantic-approval", report["invalidatedSemanticIds"])
        self.assertEqual(load(self.workspace)["scan"]["semantic"]["glossary"], [])

    def test_authored_meaning_cannot_reference_unrelated_operations_or_claims(self):
        cases = [("scenarios", "operationIds", ["missing"], "INSUFFICIENT_EVIDENCE"),
                 ("glossary", "claimIds", [], "INSUFFICIENT_EVIDENCE"),
                 ("scenarios", "operationIds", [self.op, self.op], "INVALID_ID")]
        for group, field, invalid, code in cases:
            with self.subTest(group=group, field=field):
                value = self.patch()
                value[group][0][field] = invalid
                with self.assertRaises(MoleError) as caught:
                    self.submit(value)
                self.assertEqual(caught.exception.code, code)

    def test_unknown_business_step_without_scenario_remains_in_markdown(self):
        value = self.patch()
        value["claims"][0].update(status="unknown", evidenceIds=[])
        value["scenarios"] = []
        value["glossary"] = []
        value["businessSteps"][0]["what"] = "Unique authored review step"
        self.submit(value)
        operate("finish", self.workspace, output=self.output)
        self.assertIn("Unique authored review step", (self.output / "quality-report.md").read_text())
