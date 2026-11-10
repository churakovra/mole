from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/mole'))
from molekit.errors import MoleError
from molekit.snapshots import save, restore
from molekit.workspace import atomic_json, read_json


class SnapshotTests(unittest.TestCase):
    def test_large_state_is_sharded_and_round_trips_without_aliasing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            value = {'items': [{'id': str(i), 'text': 'x' * 2000} for i in range(10000)]}
            save(root / 'state.json', value, root, atomic_json)
            self.assertLess((root / 'state.json').stat().st_size, 1024 * 1024)
            self.assertGreater(len(list((root / '.objects').glob('*.json'))), 1)
            result = restore(read_json(root / 'state.json'), root)
            self.assertEqual(result, value)
            result['items'][0]['text'] = 'changed'
            self.assertEqual(result['items'][1]['text'], 'x' * 2000)

    def test_object_corruption_or_pointer_failure_preserves_prior_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            value = {'items': list(range(1000))}
            save(root / 'state.json', value, root, atomic_json)
            before = (root / 'state.json').read_bytes()
            def interrupted(path, data):
                if path.name == 'state.json':
                    raise OSError('interrupted pointer')
                atomic_json(path, data)
            with self.assertRaises(OSError):
                save(root / 'state.json', {'items': list(range(2000))}, root, interrupted)
            self.assertEqual((root / 'state.json').read_bytes(), before)
            header = read_json(root / 'state.json')
            key = header['state']['v'][0][1]['v'][0]['v']
            blob = root / '.objects' / (key + '.json')
            blob.write_text('{}')
            with self.assertRaises(MoleError):
                restore(read_json(root / 'state.json'), root)

    def test_legacy_workspace_migrates_and_unknown_version_is_rejected(self):
        from molekit.pipeline import start
        from molekit.workspace import load, save_state
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, workspace = root / 'repo', root / 'workspace'
            repo.mkdir()
            start(repo, workspace, 'standard', 'repository')
            state = load(workspace)
            atomic_json(workspace / 'state.json', state)
            self.assertEqual(load(workspace), state)
            save_state(workspace, state)
            self.assertEqual(read_json(workspace / 'state.json')['schemaVersion'], 2)
            self.assertEqual(load(workspace), state)
            atomic_json(workspace / 'state.json', {'schemaVersion': 99})
            with self.assertRaises(MoleError) as caught:
                load(workspace)
            self.assertEqual(caught.exception.code, 'SCHEMA_MISMATCH')
