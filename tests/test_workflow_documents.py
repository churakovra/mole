import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/mole'))
from molekit.pipeline import start, operate
from molekit.workspace import load
from molekit.knowledge import compose


class WorkflowDocumentTests(unittest.TestCase):
    def test_unrelated_update_retains_evidence_empty_claim_process_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, workspace, output = Path(tmp) / 'repo', Path(tmp) / 'workspace', Path(tmp) / 'output'
            repo.mkdir()
            (repo / 'app.py').write_text('def f(): return 1\n')
            start(repo, workspace, 'standard', 'repository')
            task = operate('next', workspace)['task']
            path = Path(tmp) / 'patch.json'
            path.write_text(json.dumps({'protocolVersion': '1.0', 'taskId': task['id'], 'baseRevision': task['baseRevision'],
                'claims': [{'id': 'claim-unknown-policy', 'statement': 'Retention policy needs owner confirmation', 'status': 'unknown',
                            'evidenceIds': [], 'limitations': ['Policy absent']}]}))
            operate('submit', workspace, input=path)
            operate('finish', workspace, output=output, allow_partial=True)
            before = next(scene['id'] for scene in load(workspace)['scan']['model']['scenarios'] if 'claim-unknown-policy' in scene['claimIds'])
            (repo / 'other.py').write_text('def g(): return 2\n')
            operate('update', workspace)
            operate('finish', workspace, output=output, allow_partial=True)
            self.assertIn('Retention policy needs owner confirmation', (output / ('processes/' + before + '.md')).read_text())
    def test_one_document_explains_connected_order_workflow_and_failure_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(__file__).parent / 'fixtures/cross-file-workflow'
            workspace, output = Path(tmp) / 'workspace', Path(tmp) / 'output'
            start(repo, workspace, 'standard', 'repository')
            task = operate('next', workspace)['task']
            self.assertEqual(task['kind'], 'workflow_review')
            state = load(workspace)
            by_title = {op['title']: op['id'] for op in state['scan']['model']['operations']}
            titles = ['api.create_order', 'service.execute', 'repository.Store.save',
                      'sqlalchemy.orm.Session.add', 'sqlalchemy.orm.Session.commit',
                      'publisher.publish_order', 'aio_pika.Exchange.publish', 'worker.handle_order']
            patch = {'protocolVersion': '1.0', 'taskId': task['id'], 'baseRevision': task['baseRevision'],
                'claims': [{'id': 'claim-order', 'statement': 'Static order processing candidates cross HTTP, persistence, messaging and a registered consumer.',
                            'status': 'inferred', 'evidenceIds': task['evidenceIds'], 'limitations': ['No runtime execution or broker guarantee was verified']}],
                'scenarios': [{'id': 'semantic-order', 'title': 'Order processing', 'trigger': 'HTTP order request',
                    'actors': ['Requesting client (inferred)'], 'preconditions': ['Configured session and broker are assumptions'],
                    'operationIds': task['operationIds'], 'claimIds': ['claim-order'],
                    'steps': [{'operationId': by_title[title], 'description': title, 'condition': '', 'claimIds': ['claim-order']} for title in titles],
                    'failurePaths': [{'condition': 'ValueError in Store.save', 'operationIds': [by_title['sqlalchemy.orm.Session.rollback']],
                                      'outcome': 'Rollback is attempted by the matching handler; other exception behavior is unknown', 'claimIds': ['claim-order']}],
                    'outcomes': ['Source contains storage and publication/consumer candidates'],
                    'unknowns': ['Runtime routing, delivery and registration startup remain unverified']} ]}
            path = Path(tmp) / 'patch.json'
            path.write_text(json.dumps(patch))
            operate('submit', workspace, input=path)
            operate('finish', workspace, output=output, allow_partial=True)
            document = (output / 'processes/semantic-order.md').read_text()
            for filename in ('api.py', 'service.py', 'repository.py', 'publisher.py', 'worker.py'):
                self.assertIn(filename, document)
            self.assertIn('1. api.create', document)
            self.assertIn('Actors', document)
            self.assertIn('ValueError', document)
            self.assertIn('rollback', document)
            self.assertIn('unverified', document)
            model = load(workspace)['scan']['model']
            root = model['diagramViews'][0]
            self.assertNotIn('Static trace:', json.dumps(root))
            self.assertTrue(any(node['label'] == 'Order processing' for node in root['nodes']))
            views = {view['id']: view for view in model['diagramViews']}
            business = views[next(node['childViewId'] for node in root['nodes'] if node['label'] == 'Order processing')]
            self.assertGreaterEqual(len(business['edgeIds']), 3)
            module = views[business['childRefs'][0]]
            self.assertTrue(module['childRefs'])
            self.assertIn('publisher.py', (output / 'architecture.md').read_text())
