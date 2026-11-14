"""Business maps must show evidenced handoffs and actual alternative paths."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/mole'))
from molekit.errors import MoleError
from molekit.html import render
from molekit.knowledge import compose
from molekit.pipeline import start, operate
from molekit.workspace import load
from test_html import BROWSER, browser_test


class ProcessLinkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        (self.repo / 'README.md').write_text('# Orders\nCheck requests. Accept valid requests for fulfillment; reject invalid requests.\n')
        (self.repo / 'ARCHITECTURE.md').write_text('# Fulfillment\nFulfill accepted orders.\n')
        (self.repo / 'app.py').write_text('def check(): return True\n')
        self.workspace = self.root / 'workspace'
        start(self.repo, self.workspace, 'standard', 'repository')
        task = operate('next', self.workspace)['task']
        page = operate('inspect', self.workspace, task=task['id'], budget_chars=12000)
        ops = {op['title']: op['id'] for op in page['operations']}
        evs = {item['path']: item['evidenceId'] for item in page['context']}
        self.patch = {'protocolVersion': '1.0', 'taskId': task['id'], 'baseRevision': task['baseRevision'],
            'claims': [{'id': key, 'statement': statement, 'status': 'documented_intent',
                        'evidenceIds': [evs[path]], 'limitations': ['Documentation only']} for key, statement, path in
                       [('c-check', 'Delivery to fulfillment follows acceptance; invalid requests are rejected.', 'README.md'),
                        ('c-fulfill', 'Accepted orders enter fulfillment.', 'ARCHITECTURE.md')]],
            'scenarios': [
                {'id': 'semantic-check', 'title': 'Check requests', 'trigger': 'Request arrives',
                 'operationIds': [ops['README.md']], 'claimIds': ['c-check'], 'outcomes': ['Accepted or rejected'], 'unknowns': [],
                 'steps': [{'operationId': ops['README.md'], 'description': label, 'condition': condition, 'claimIds': ['c-check']}
                           for label, condition in [('Check request', 'Request available'), ('Accept request', 'Valid'), ('Reject request', 'Invalid')]],
                 'stepTransitions': [{'fromStep': 0, 'toStep': target, 'label': label, 'condition': condition, 'claimIds': ['c-check']}
                                     for target, label, condition in [(1, 'Accept', 'Valid'), (2, 'Reject', 'Invalid')]],
                 'links': [{'targetScenarioId': 'semantic-fulfill', 'label': 'Accepted request', 'condition': 'Valid requests only', 'claimIds': ['c-check']}]},
                {'id': 'semantic-fulfill', 'title': 'Fulfill orders', 'trigger': 'Accepted request',
                 'operationIds': [ops['ARCHITECTURE.md']], 'claimIds': ['c-fulfill'], 'outcomes': ['Fulfilled'], 'unknowns': []}]}

    def submit(self, value):
        path = self.root / 'patch.json'
        path.write_text(json.dumps(value))
        return operate('submit', self.workspace, input=path)

    def test_explicit_handoffs_and_branching_survive_export_and_browser_navigation(self):
        self.submit(self.patch)
        result = operate('finish', self.workspace, output=self.root / 'output', allow_partial=True)
        model = load(self.workspace)['scan']['model']
        overview = model['diagramViews'][0]
        self.assertEqual(len(overview['edgeIds']), 1)
        relationships = {edge['id']: edge for edge in model['relationships']}
        edge = relationships[overview['edgeIds'][0]]
        self.assertEqual(edge['claimIds'], ['c-check'])
        process = overview['nodes'][0]
        business = next(view for view in model['diagramViews'] if view['id'] == process['childViewId'])
        nodes = business['nodes']
        pairs = {(relationships[eid]['source'], relationships[eid]['target']) for eid in business['edgeIds']}
        self.assertEqual(pairs, {(nodes[0]['id'], nodes[1]['id']), (nodes[0]['id'], nodes[2]['id'])})
        self.assertTrue((Path(result['output']) / 'explorer.html').is_file())
        if Path(BROWSER).is_file():
            check = browser_test(render(model), '''
check(document.querySelectorAll('.edge').length===1,'no top-level handoff');
document.querySelector('.edge').dispatchEvent(new MouseEvent('click',{bubbles:true}));
check(document.querySelector('#details').textContent.includes('c-check')===false,'raw claim ID substituted for explanation');
check(document.querySelector('#details').textContent.includes('documented_intent: Delivery'),'handoff evidence missing');
check(!document.querySelector('#details').textContent.includes('Accepted orders enter fulfillment'),'unrelated claim leaked into handoff proof');
document.querySelector('.node').dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true}));
check(document.querySelectorAll('.edge').length===2,'branch links missing');
check(document.querySelector('#diagram').textContent.includes('Valid'),'branch condition missing');
document.querySelector('#back').click();
check(document.querySelectorAll('.edge').length===1,'return lost handoff');
''', self.root)
            self.assertTrue(check['ok'], check)

    def test_bad_transition_targets_and_unsupported_claims_are_rejected_without_mutation(self):
        before = (self.workspace / 'state.json').read_bytes()
        for case in ('step', 'scenario', 'unknown', 'scope'):
            patch = copy.deepcopy(self.patch)
            if case == 'step': patch['scenarios'][0]['stepTransitions'][0]['toStep'] = 7
            if case == 'scenario': patch['scenarios'][0]['links'][0]['targetScenarioId'] = 'semantic-missing'
            if case == 'unknown': patch['claims'][0]['status'] = 'unknown'
            if case == 'scope': patch['scenarios'][0]['links'][0]['claimIds'] = ['c-fulfill']
            with self.subTest(case=case), self.assertRaises(MoleError): self.submit(patch)
            self.assertEqual((self.workspace / 'state.json').read_bytes(), before)

    def test_review_downgrade_withdraws_edges_and_preserves_unknown_interpretation(self):
        self.submit(self.patch)
        state = load(self.workspace)
        review = next(task for task in state['tasks'] if task['kind'] == 'claim_review')
        self.submit({'protocolVersion': '1.0', 'taskId': review['id'], 'baseRevision': state['revision'], 'claims': [],
                     'review': {'claimIds': review['reviewClaimIds'], 'evidenceIds': review['evidenceIds'],
                                'rationale': 'The described handoff is not established by the supplied source.', 'verdict': 'unknown'}})
        state = load(self.workspace)
        model = compose(state['scan'])
        self.assertEqual(model['diagramViews'][0]['edgeIds'], [])
        self.assertTrue(state['scan']['semantic']['scenarios'][0]['links'])
        self.assertEqual(next(c for c in model['claims'] if c['id'] == 'c-check')['status'], 'unknown')

    def test_withdrawn_target_invalidates_dependent_scenario_links(self):
        self.submit(self.patch)
        (self.repo / 'ARCHITECTURE.md').write_text('# Fulfillment\nProcess canceled orders instead.\n')
        result = operate('update', self.workspace)
        self.assertTrue({'semantic-check', 'semantic-fulfill'} <= set(result['changes']['invalidatedSemanticIds']))
        self.assertEqual(load(self.workspace)['scan']['semantic']['scenarios'], [])

    def test_resuming_after_export_cannot_link_to_generated_candidates_and_corrupt_state(self):
        self.submit(self.patch)
        operate('finish', self.workspace, output=self.root / 'output', allow_partial=True)
        state = load(self.workspace)
        candidate = next(scene for scene in state['scan']['model']['scenarios'] if not scene['id'].startswith('semantic-'))
        task = next(task for task in state['tasks'] if task['kind'] == 'component_review')
        patch = {'protocolVersion': '1.0', 'taskId': task['id'], 'baseRevision': state['revision'],
                 'claims': [{'id': 'c-new', 'statement': 'Static check supports request checking.', 'status': 'inferred',
                             'evidenceIds': task['evidenceIds'], 'limitations': ['Purpose is inferred']}],
                 'scenarios': [{'id': 'semantic-new', 'title': 'Check value', 'trigger': 'Call',
                                'operationIds': task['operationIds'], 'claimIds': ['c-new'], 'outcomes': ['True'], 'unknowns': [],
                                'links': [{'targetScenarioId': candidate['id'], 'label': 'Check result', 'condition': '', 'claimIds': ['c-new']}]}]}
        before = (self.workspace / 'state.json').read_bytes()
        with self.assertRaises(MoleError) as caught:
            self.submit(patch)
        self.assertEqual(caught.exception.code, 'DANGLING_REFERENCE')
        self.assertEqual((self.workspace / 'state.json').read_bytes(), before)
        self.assertEqual(load(self.workspace)['status'], 'PARTIAL')
        patch['scenarios'][0]['links'][0]['targetScenarioId'] = 'semantic-check'
        self.submit(patch)
        self.assertTrue(any(scene['id'] == 'semantic-new' for scene in load(self.workspace)['scan']['semantic']['scenarios']))
