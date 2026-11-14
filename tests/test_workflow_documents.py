import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/mole'))
from molekit.pipeline import start, operate
from molekit.output import resolve_output
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
            self.assertIn('Retention policy needs owner confirmation', (resolve_output(output) / ('processes/' + before + '.md')).read_text())
    def test_one_document_explains_connected_order_workflow_and_failure_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(__file__).parent / 'fixtures/cross-file-workflow'
            workspace, output = Path(tmp) / 'workspace', Path(tmp) / 'output'
            start(repo, workspace, 'standard', 'repository')
            task = operate('next', workspace)['task']
            self.assertEqual(task['kind'], 'workflow_review')
            state = load(workspace)
            task = next(item for item in state['tasks'] if item['id'] == task['id'])
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
            labels = ['Accept order', 'Process order', 'Save order', 'Record order',
                      'Commit order', 'Prepare notification', 'Publish notification', 'Handle notification']
            for step, label in zip(patch['scenarios'][0]['steps'], labels):
                step['description'] = label
            patch['scenarios'][0]['stepTransitions'] = [
                {'fromStep': i, 'toStep': i + 1, 'label': 'Continue order processing', 'condition': '', 'claimIds': ['claim-order']}
                for i in range(len(labels) - 1)]
            path = Path(tmp) / 'patch.json'
            path.write_text(json.dumps(patch))
            operate('submit', workspace, input=path)
            operate('finish', workspace, output=output, allow_partial=True)
            document = (resolve_output(output) / 'processes/semantic-order.md').read_text()
            for filename in ('api.py', 'service.py', 'repository.py', 'publisher.py', 'worker.py'):
                self.assertIn(filename, document)
            self.assertIn('1. Accept order', document)
            self.assertIn('Actors', document)
            self.assertIn('ValueError', document)
            self.assertIn('rollback', document)
            self.assertIn('unverified', document)
            state = load(workspace)
            model = state['scan']['model']
            root = model['diagramViews'][0]
            self.assertNotIn('Static trace:', json.dumps(root))
            self.assertTrue(any(node['label'] == 'Order processing' for node in root['nodes']))
            self.assertFalse(any(node['label'].startswith(('Workflow candidate:', 'Component review:')) for node in root['nodes']))
            views = {view['id']: view for view in model['diagramViews']}
            business = views[next(node['childViewId'] for node in root['nodes'] if node['label'] == 'Order processing')]
            self.assertEqual([node['label'] for node in business['nodes']][:len(labels)], labels)
            self.assertGreaterEqual(len(business['edgeIds']), 3)
            self.assertTrue(all(node.get('childViewId') in views for node in business['nodes']))
            self.assertTrue(any('rollback' in node['label'].lower() for node in business['nodes']))
            # Regeneration must not accumulate generated business nodes or edges.
            first_model = json.dumps(model, sort_keys=True)
            compose(state['scan'])
            self.assertEqual(first_model, json.dumps(state['scan']['model'], sort_keys=True))
            conditional_state = load(workspace)
            conditional_scene = conditional_state['scan']['semantic']['scenarios'][0]
            conditional_scene.pop('stepTransitions')
            conditional_scene['steps'][1]['condition'] = 'If approved'
            conditional_scene['steps'][2]['condition'] = 'If rejected'
            conditional_model = compose(conditional_state['scan'])
            conditional_view = next(view for view in conditional_model['diagramViews'] if view['id'] == business['id'])
            conditional_nodes = {node['id'] for node in conditional_view['nodes']
                                 if 'If approved' in node['label'] or 'If rejected' in node['label']}
            self.assertFalse(any(edge['source'] in conditional_nodes or edge['target'] in conditional_nodes
                                 for edge in conditional_model['relationships'] if edge['id'] in conditional_view['edgeIds']))
            from unittest.mock import patch as mock_patch
            with mock_patch('molekit.knowledge.MAX_VIEWS', 4):
                bounded = compose(load(workspace)['scan'])
            bounded_views = {view['id']: view for view in bounded['diagramViews']}
            process_node = next(node for node in bounded['diagramViews'][0]['nodes'] if node['label'] == 'Order processing')
            self.assertIn(process_node['childViewId'], bounded_views)
            self.assertEqual(bounded_views[process_node['childViewId']]['nodes'][0]['label'], 'Accept order')
            from test_html import BROWSER, browser_test
            from molekit.html import render
            if Path(BROWSER).is_file():
                result = browser_test(render(model, partial=True), '''
const rootTitle=document.querySelector('#title').textContent;
const process=[...document.querySelectorAll('.node')].find(n=>n.textContent.includes('Order processing'));
process.dispatchEvent(new MouseEvent('click',{bubbles:true}));
check(document.querySelector('#details').textContent.includes('HTTP order request'),'process explanation missing');
process.dispatchEvent(new MouseEvent('dblclick',{bubbles:true}));
check(document.querySelector('#diagram').textContent.includes('Accept order'),'business steps missing');
const step=[...document.querySelectorAll('.node')].find(n=>n.textContent.includes('Accept order'));
step.dispatchEvent(new MouseEvent('click',{bubbles:true}));
check(document.querySelector('#open-details'),'no subprocess control');
document.querySelector('#open-details').click();
check(document.querySelector('#title').textContent!=='Order processing','subprocess did not open');
document.querySelector('#back').click();
check(document.querySelector('#title').textContent==='Order processing','back lost business process');
document.querySelector('#back').click();
check(document.querySelector('#title').textContent===rootTitle,'back lost overview');
''', tmp)
                self.assertTrue(result['ok'], result)
            self.assertIn('publisher.py', (resolve_output(output) / 'architecture.md').read_text())
