import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/mole"))
from molekit.adapters import enrich
from molekit.drawio import render, validate
from molekit.errors import MoleError
from molekit.knowledge import compose
from molekit.mermaid import render as mermaid
from molekit.scanner import scan
from molekit.markdown import plan_writes


class ExportTests(unittest.TestCase):
    def model(self):
        with tempfile.TemporaryDirectory() as tmp:
            return compose(enrich(scan(Path(__file__).parent / "fixtures/fastapi-db-events", tmp)))

    def test_multipage_links_ids_and_xml_round_trip(self):
        model = self.model()
        model["diagramViews"][0]["nodes"][0]["label"] = '<script>&"label"'
        xml = render(model)
        self.assertNotIn("<script>", xml)
        parsed = validate(xml)
        self.assertEqual(len(parsed.findall("diagram")), len(model["diagramViews"]))
        self.assertTrue(parsed.findall(".//UserObject[@link]"))
        again = validate(ET.tostring(parsed, encoding="unicode"))
        self.assertEqual([p.get("id") for p in parsed], [p.get("id") for p in again])
        self.assertEqual(render(model), xml)

    def test_unsafe_xml_and_dangling_links_rejected(self):
        with self.assertRaises(MoleError):
            validate('<!DOCTYPE mxfile><mxfile/>')
        xml = render(self.model()).replace("data:page/id,", "javascript:")
        with self.assertRaises(MoleError):
            validate(xml)

    def test_mermaid_declares_losses_and_escapes_syntax(self):
        model = self.model()
        model["diagramViews"][0]["nodes"][0]["label"] = '"] --> bad["x'
        output = mermaid(model, True)
        self.assertIn("%% Losses:", output)
        self.assertIn("%% PARTIAL", output)
        self.assertNotIn('"] --> bad', output)
        self.assertNotIn("click ", output)
        with tempfile.TemporaryDirectory() as tmp:
            writes, _ = plan_writes(tmp, {"workflows.mmd": output}, {})
            self.assertTrue(next(iter(writes.values())).startswith("%%"))

    @unittest.skipUnless(os.environ.get("MOLE_DRAWIO_XSD") and shutil.which("xmllint"), "Official XSD/xmllint not configured")
    def test_official_xsd(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "workflows.drawio"
            path.write_text(render(self.model()))
            result = subprocess.run(["xmllint", "--nonet", "--noout", "--schema", os.environ["MOLE_DRAWIO_XSD"], str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
