"""PR-00 regressions: route identity, declaration evidence and portable exports."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/mole'))
from molekit.adapters import enrich
from molekit.errors import MoleError
from molekit.markdown import atomic_text, plan_writes
from molekit.output import resolve_output
from molekit.pipeline import operate, start
from molekit.scanner import scan


class BlueprintBaselineTests(unittest.TestCase):
    def analyze(self, source):
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as workspace:
            Path(repo, 'app.py').write_text(source, encoding='utf-8')
            return enrich(scan(repo, workspace))

    def test_stacked_routes_have_distinct_stable_method_path_identity(self):
        source = '''from fastapi import APIRouter
router = APIRouter(prefix="/api")
@router.get("/a")
@router.get("/b")
@router.post("/a")
@router.api_route("/multi", methods=["GET", "POST"])
async def handler(): return 1
'''
        first = self.analyze(source)
        routes = [op for op in first['model']['operations'] if op['kind'] == 'http_entry']
        self.assertEqual(len(routes), 5)
        self.assertEqual(len({op['id'] for op in routes}), 5)
        self.assertEqual({op['routeMethod'] + ' ' + op['routePath'] for op in routes},
                         {'GET /api/a', 'GET /api/b', 'POST /api/a', 'GET /api/multi', 'POST /api/multi'})
        second = self.analyze('\n# harmless comment\n' + source)
        self.assertEqual({op['id'] for op in routes},
                         {op['id'] for op in second['model']['operations'] if op['kind'] == 'http_entry'})

    def test_depends_defaults_are_declaration_evidence_without_runtime_edges(self):
        result = self.analyze('''from fastapi import FastAPI, Depends
app = FastAPI()
def cleanup(): pass
def get_session():
    try:
        yield 1
    finally:
        cleanup()
@app.get("/", dependencies=[Depends(get_session)])
async def handler(session=Depends(get_session), *, other=Depends(get_session)):
    return session
''')
        dependencies = [op for op in result['model']['operations'] if op['kind'] == 'dependency']
        self.assertEqual(len(dependencies), 3)
        self.assertTrue(all(op.get('uncertainty') for op in dependencies))
        calls = {call['operationId']: call for call in result['callSites']}
        self.assertTrue(all(calls[op['id']]['owner'] == '<module>' for op in dependencies))
        ids = {op['id'] for op in dependencies}
        self.assertFalse(any(edge['target'] in ids and edge['kind'] == 'contains'
                             for edge in result['model']['relationships']))
        self.assertTrue(any(call['target'] == 'cleanup' and call['owner'] == 'get_session'
                            for call in result['callSites']))
        from molekit.agent import create_tasks
        tasks = create_tasks(result, 'standard')
        self.assertTrue(ids <= set().union(*(set(task['operationIds']) for task in tasks)))

    def test_dynamic_methods_are_unknown_and_annotated_prefix_is_retained(self):
        result = self.analyze('''from fastapi import APIRouter
router: APIRouter = APIRouter(prefix="/api")
@router.api_route("/x", methods=METHODS)
async def handler(): pass
''')
        routes = [op for op in result['model']['operations'] if op['kind'] == 'http_entry']
        self.assertEqual([(op['routeMethod'], op['routePath']) for op in routes], [('<DYNAMIC>', '/api/x')])

    def test_declaration_side_effects_are_not_handler_execution(self):
        result = self.analyze('''def effect(): return 1
def decorator(value): return lambda f: f
@decorator(effect())
async def handler(value=effect()): return value
''')
        effects = [call for call in result['callSites'] if call['target'] == 'effect']
        self.assertEqual(len(effects), 2)
        self.assertTrue(all(call['owner'] == '<module>' for call in effects))
        self.assertTrue(all(edge['resolution'] == 'possible' for edge in result['model']['relationships']))

    def test_cross_volume_export_keeps_visible_source_locators(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, workspace, output = root / 'repo', root / 'workspace', root / 'output'
            repo.mkdir()
            (repo / 'app.py').write_text('def handler(): return 1\n')
            start(repo, workspace, 'standard', 'repository')
            operate('next', workspace)
            with patch('os.path.relpath', side_effect=ValueError('path is on mount D:')):
                result = operate('finish', workspace, output=output, allow_partial=True)
            bundle = resolve_output(output)
            document = next((bundle / 'processes').glob('*.md')).read_text()
            self.assertIn('app.py', document)
            self.assertIn('lines 1', document)
            self.assertNotIn('file://', document)
            self.assertNotIn(str(repo), document)
            html = (bundle / 'explorer.html').read_text()
            self.assertIn('"sourcePrefix": null', html)
            self.assertEqual(result['status'], 'PARTIAL')

    def test_crlf_roundtrip_preserves_manual_bytes_and_detects_generated_edit(self):
        for suffix in ('.md', '.mmd', '.html'):
            with self.subTest(suffix=suffix), tempfile.TemporaryDirectory() as tmp:
                relative = 'document' + suffix
                writes, bases = plan_writes(tmp, {relative: 'Generated\nbody\n'}, {})
                path, original = next(iter(writes.items()))
                manual = '\r\nAuthor note: café\r\n  preserve spacing  \r\n'
                path.write_bytes(original.replace('\n', '\r\n').encode() + manual.encode())
                writes, bases = plan_writes(tmp, {relative: 'Updated\nbody\n'}, bases)
                for target, content in writes.items():
                    atomic_text(target, content)
                self.assertTrue(path.read_bytes().endswith(manual.encode()))
                path.write_bytes(path.read_bytes().replace(b'Updated', b'Authored'))
                before = path.read_bytes()
                with self.assertRaises(MoleError) as caught:
                    plan_writes(tmp, {relative: 'Another\n'}, bases)
                self.assertEqual(caught.exception.code, 'OUTPUT_CONFLICT')
                self.assertEqual(before, path.read_bytes())

    def test_successful_tool_calls_do_not_replace_required_artifact(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
        from evaluate import delivery_receipt_outcome
        receipt = json.loads((Path(__file__).parent / 'fixtures/acceptance/premature-exit.json').read_text())
        self.assertEqual(delivery_receipt_outcome(receipt)['outcome'], 'user_goal_not_met')
        receipt['observedCommands'].extend(['finish', 'status'])
        self.assertEqual(delivery_receipt_outcome(receipt)['outcome'], 'user_goal_not_met')
        receipt['deliveredFormats'] = ['html']
        self.assertEqual(delivery_receipt_outcome(receipt)['outcome'], 'requires_semantic_review')


if __name__ == '__main__':
    unittest.main()
