from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from generate_example import generate
from molekit.errors import MoleError


class ExampleGeneratorTests(unittest.TestCase):
    def test_symlinked_sample_directory_never_writes_outside_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve()
            output,external=root/'example',root/'external'
            output.mkdir();external.mkdir()
            (output/'processes').symlink_to(external,target_is_directory=True)
            with self.assertRaises(ValueError):
                generate(output)
            self.assertEqual(list(external.iterdir()),[])

    def test_generated_edits_conflict_and_markdown_mermaid_notes_survive(self):
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp).resolve()/'example'
            generate(output)
            for relative,start in [('README.md','<!-- mole:manual:start -->'),('workflows.mmd','%% mole:manual:start')]:
                path=output/relative
                path.write_text(path.read_text().replace(start,start+'\nOwner note'))
            generate(output)
            self.assertIn('Owner note',(output/'README.md').read_text())
            self.assertIn('Owner note',(output/'workflows.mmd').read_text())
            readme=output/'README.md'
            readme.write_text(readme.read_text().replace('# System workflows','# Authored correction'))
            before=readme.read_bytes()
            with self.assertRaises(MoleError) as caught:
                generate(output)
            self.assertEqual(caught.exception.code,'OUTPUT_CONFLICT')
            self.assertEqual(readme.read_bytes(),before)

    def test_retired_page_authored_prefix_cannot_be_deleted(self):
        import json
        from molekit.markdown import plan_writes,atomic_text
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp).resolve()/'example'
            generate(output)
            writes,bases=plan_writes(output,{'processes/retired.md':'# Previous trace\n'},{})
            for path,body in writes.items(): atomic_text(path,body)
            baseline=output/'.sample-bases.json'
            baseline.write_text(json.dumps({**json.loads(baseline.read_text()),**bases}))
            page=output/'processes/retired.md'
            page.write_text('# Authored historical context\n'+page.read_text())
            before=page.read_bytes()
            with self.assertRaises(ValueError): generate(output)
            self.assertEqual(page.read_bytes(),before)
