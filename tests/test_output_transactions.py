import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/mole'))
from molekit import output, markdown
from molekit.errors import MoleError
from molekit.workspace import locked


class OutputTransactionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'output'
        self.state = {'manifest': {'repo': self.temp.name, 'scope': 'repository'}, 'runId': 'first',
                      'revision': 'r1', 'scan': {'model': {'revision': 'r1'}}}
        self.saved = []

    def publish(self, state=None, formats=None, **options):
        state = state or self.state
        formats = formats or ['markdown', 'html']
        def build(physical, previous):
            files = {'README.md': '# Revision ' + state['revision'] + '\n'}
            if 'html' in formats:
                files['explorer.html'] = '<p>' + state['revision'] + '</p>'
            return files
        return output.publish(state, Path(self.temp.name), self.root, formats, {}, build,
                              lambda: self.saved.append(copy.deepcopy(state)), **options)

    def checkpoint(self, result):
        self.state.update(output=str(self.root), outputGeneration=result['generation'], exportBases=result['manifest']['bases'])
        self.state.pop('pendingExport', None)

    def advance(self):
        self.state['revision'] = 'r2'
        self.state['scan']['model']['revision'] = 'r2'

    def test_stage_failure_keeps_whole_previous_generation_and_retry_preserves_notes(self):
        first = self.publish()
        self.checkpoint(first)
        old = Path(first['output'])
        page = old / 'README.md'
        page.write_text(page.read_text().replace('<!-- mole:manual:start -->', '<!-- mole:manual:start -->\nOwner note'))
        before = page.read_bytes()
        pointer = (self.root / 'current.json').read_bytes()
        self.advance()
        with patch('molekit.markdown.atomic_text', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                self.publish()
        self.assertEqual((self.root / 'current.json').read_bytes(), pointer)
        self.assertEqual(page.read_bytes(), before)
        second = self.publish()
        self.assertNotEqual(first['generation'], second['generation'])
        self.assertIn('Owner note', (Path(second['output']) / 'README.md').read_text())
        self.assertEqual(page.read_bytes(), before)

    def test_pointer_commit_recovers_even_if_gateway_or_workspace_write_failed(self):
        with patch('molekit.output.write_gateway', side_effect=OSError('interrupted')):
            with self.assertRaises(OSError):
                self.publish()
        active = output.resolve_output(self.root)
        pointer = (self.root / 'current.json').read_bytes()
        result = self.publish()
        self.assertEqual(Path(result['output']), active)
        self.assertEqual((self.root / 'current.json').read_bytes(), pointer)
        self.assertTrue((self.root / 'MOLE-OPEN.html').is_file())

    def test_other_workspace_must_explicitly_adopt_and_output_lock_serializes(self):
        first = self.publish()
        other = copy.deepcopy(self.state)
        other.pop('pendingExport')
        other['runId'] = 'second'
        with self.assertRaises(MoleError) as caught:
            self.publish(state=other)
        self.assertEqual(caught.exception.code, 'OUTPUT_CONFLICT')
        self.assertEqual(self.publish(state=other, adopt=True)['generation'], first['generation'])
        with locked(self.root):
            with self.assertRaises(MoleError) as caught:
                self.publish()
        self.assertEqual(caught.exception.code, 'WORKSPACE_BUSY')

    def test_withdrawn_format_is_only_in_retained_previous_generation(self):
        first = self.publish()
        self.checkpoint(first)
        result = self.publish(formats=['markdown'])
        self.assertFalse((Path(result['output']) / 'explorer.html').exists())
        self.assertTrue((Path(first['output']) / 'explorer.html').exists())
        self.assertEqual(result['manifest']['retired'], ['explorer.html'])

    def test_concurrent_manual_edit_aborts_before_pointer_publication(self):
        first = self.publish()
        self.checkpoint(first)
        self.advance()
        old = Path(first['output']) / 'README.md'
        atomic = markdown.atomic_text
        def concurrent(path, text):
            atomic(path, text)
            old.write_text(old.read_text().replace('<!-- mole:manual:start -->', '<!-- mole:manual:start -->\nConcurrent note'))
        with patch('molekit.markdown.atomic_text', side_effect=concurrent):
            with self.assertRaises(MoleError) as caught:
                self.publish()
        self.assertEqual(caught.exception.code, 'OUTPUT_CONFLICT')
        self.assertEqual(output.resolve_output(self.root), Path(first['output']))
        with self.assertRaises(MoleError):
            self.publish()
        second = self.publish(restart=True)
        self.assertIn('Concurrent note', (Path(second['output']) / 'README.md').read_text())

    def test_changed_intent_requires_restart_and_symlink_is_rejected(self):
        with patch('molekit.markdown.atomic_text', side_effect=OSError('interrupt')):
            with self.assertRaises(OSError):
                self.publish()
        with self.assertRaises(MoleError):
            self.publish(formats=['markdown'])
        result = self.publish(formats=['markdown'], restart=True)
        self.checkpoint(result)
        page = Path(result['output']) / 'README.md'
        page.unlink()
        page.symlink_to(Path(self.temp.name) / 'private')
        with self.assertRaises(MoleError) as caught:
            self.publish()
        self.assertEqual(caught.exception.code, 'UNSAFE_PATH')

    def test_untracked_authored_asset_cannot_be_silently_stranded(self):
        first = self.publish()
        self.checkpoint(first)
        active = Path(first['output'])
        (active / 'notes.md').write_text('Owner notes')
        readme = active / 'README.md'
        readme.write_text(readme.read_text().replace('<!-- mole:manual:start -->', '<!-- mole:manual:start -->\n[notes](notes.md)'))
        self.advance()
        with self.assertRaises(MoleError) as caught:
            self.publish()
        self.assertEqual(caught.exception.code, 'OUTPUT_CONFLICT')
        self.assertEqual(output.resolve_output(self.root), active)
        self.assertEqual((active / 'notes.md').read_text(), 'Owner notes')

    def test_unreadable_untracked_directory_preserves_pointer(self):
        first = self.publish()
        self.checkpoint(first)
        private = Path(first['output']) / 'private'
        private.mkdir()
        (private / 'notes.md').write_text('Owner notes')
        private.chmod(0)
        try:
            self.advance()
            with self.assertRaises(MoleError) as caught:
                self.publish()
            self.assertEqual(caught.exception.code, 'OUTPUT_CONFLICT')
            self.assertEqual(output.resolve_output(self.root), Path(first['output']))
        finally:
            private.chmod(0o700)
