import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/mole'))
from molekit.pipeline import start, operate
from molekit.workspace import load
from molekit.quality import assess


class QualityGateTests(unittest.TestCase):
    def test_unknown_claim_is_partial_not_semantic_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'
            repo.mkdir()
            (repo / 'app.py').write_text('def f(): return 1\n')
            workspace = Path(tmp) / 'workspace'
            start(repo, workspace, 'standard', 'repository')
            task = operate('next', workspace)['task']
            path = Path(tmp) / 'patch.json'
            path.write_text(json.dumps({'protocolVersion': '1.0', 'taskId': task['id'], 'baseRevision': task['baseRevision'],
                'claims': [{'id': 'c-unknown', 'statement': 'Purpose is unknown', 'status': 'unknown',
                            'evidenceIds': [], 'limitations': ['No business policy']}]}))
            operate('submit', workspace, input=path)
            report = assess(load(workspace))
            self.assertEqual(report['technicalAnalysis'], 'PASS')
            self.assertEqual(report['semanticCoverage'], 'PARTIAL')
            self.assertGreater(report['criticalUnknownCount'], 0)

    def test_material_claim_requires_review_and_can_be_contradicted(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'
            repo.mkdir()
            (repo / 'app.py').write_text('def f(): return 1\n')
            workspace = Path(tmp) / 'workspace'
            start(repo, workspace, 'standard', 'repository')
            task = operate('next', workspace)['task']
            path = Path(tmp) / 'patch.json'
            path.write_text(json.dumps({'protocolVersion': '1.0', 'taskId': task['id'], 'baseRevision': task['baseRevision'],
                'claims': [{'id': 'c-guarantee', 'statement': 'Exactly once delivery is guaranteed', 'status': 'source_observed',
                            'evidenceIds': task['evidenceIds'], 'limitations': []}]}))
            result = operate('submit', workspace, input=path)
            self.assertEqual(result['status'], 'NEEDS_ANALYSIS')
            review_task = operate('next', workspace)['task']
            self.assertEqual(review_task['kind'], 'claim_review')
            path.write_text(json.dumps({'protocolVersion': '1.0', 'taskId': review_task['id'], 'baseRevision': review_task['baseRevision'],
                'claims': [], 'review': {'claimIds': ['c-guarantee'], 'verdict': 'contradicted',
                                       'evidenceIds': review_task['evidenceIds'], 'rationale': 'The function only returns a constant; it contains no delivery behavior'}}))
            operate('submit', workspace, input=path)
            state = load(workspace)
            self.assertEqual(state['scan']['model']['claims'][0]['status'], 'contradicted')
            self.assertEqual(assess(state)['semanticCoverage'], 'PARTIAL')

    def test_every_operation_can_be_retrieved_after_preview_truncation(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'
            repo.mkdir()
            (repo / 'app.py').write_text(''.join('def f' + str(i) + '(): return ' + str(i) + '\n' for i in range(60)))
            workspace = Path(tmp) / 'workspace'
            start(repo, workspace, 'standard', 'repository')
            task = operate('next', workspace)['task']
            full = load(workspace)['tasks'][0]
            cursor, collected = 'ops:0', set()
            for _ in range(200):
                page = operate('inspect', workspace, task=task['id'], budget_chars=3000, cursor=cursor)
                self.assertLessEqual(len(json.dumps(page)), 3000)
                collected.update(op['id'] for op in page['operations'])
                cursor = page['nextCursor']
                if cursor is None:
                    break
            self.assertIsNone(cursor)
            self.assertEqual(collected, set(full['operationIds']))

    def test_explicit_bounded_workflow_can_complete_without_unknown_claims(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, workspace = Path(tmp) / 'repo', Path(tmp) / 'workspace'
            repo.mkdir()
            (repo / 'app.py').write_text('def check(value):\n    if value:\n        return True\n    return False\n')
            start(repo, workspace, 'standard', 'repository')
            task = operate('next', workspace)['task']
            operation = task['operationIds'][0]
            path = Path(tmp) / 'patch.json'
            path.write_text(json.dumps({'protocolVersion': '1.0', 'taskId': task['id'], 'baseRevision': task['baseRevision'],
                'claims': [{'id': 'c-check', 'statement': 'The callable returns a boolean based on the supplied value.',
                            'status': 'source_observed', 'evidenceIds': task['evidenceIds'], 'limitations': []}],
                'scenarios': [{'id': 'semantic-check', 'title': 'Boolean check', 'trigger': 'Caller invokes check',
                    'actors': ['Callable caller'], 'preconditions': ['Value is supplied'], 'operationIds': task['operationIds'],
                    'claimIds': ['c-check'], 'steps': [{'operationId': operation, 'description': 'Evaluate value', 'condition': '', 'claimIds': ['c-check']}],
                    'failurePaths': [{'condition': 'Value is false', 'operationIds': [operation], 'outcome': 'Return False', 'claimIds': ['c-check']}],
                    'outcomes': ['Return True or False'], 'unknowns': []}]}))
            operate('submit', workspace, input=path)
            result = operate('finish', workspace, output=Path(tmp) / 'output')
            self.assertEqual(result['status'], 'COMPLETED')
            self.assertEqual(assess(load(workspace))['semanticCoverage'], 'PASS')

    def test_one_authored_scope_does_not_cover_other_completed_tasks(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, workspace = Path(tmp) / 'repo', Path(tmp) / 'workspace'
            repo.mkdir()
            for name in ('a', 'b'):
                (repo / (name + '.py')).write_text('def check(): return True\n')
            start(repo, workspace, 'standard', 'repository')
            index = 0
            while (task := operate('next', workspace)['task']):
                claim = 'c-' + str(index)
                patch_value = {'protocolVersion': '1.0', 'taskId': task['id'], 'baseRevision': task['baseRevision'],
                    'claims': [{'id': claim, 'statement': 'Callable returns True.', 'status': 'source_observed',
                                'evidenceIds': task['evidenceIds'], 'limitations': []}]}
                if index == 0:
                    op = task['operationIds'][0]
                    patch_value['scenarios'] = [{'id': 'semantic-first', 'title': 'First check', 'trigger': 'Call',
                        'actors': ['Caller'], 'preconditions': ['Invoked'], 'operationIds': task['operationIds'], 'claimIds': [claim],
                        'steps': [{'operationId': op, 'description': 'Check', 'condition': '', 'claimIds': [claim]}],
                        'failurePaths': [{'condition': 'No explicit error handler', 'operationIds': [op], 'outcome': 'No handled failure is observed', 'claimIds': [claim]}],
                        'outcomes': ['True'], 'unknowns': []}]
                path = Path(tmp) / 'patch.json'
                path.write_text(json.dumps(patch_value))
                operate('submit', workspace, input=path)
                index += 1
            self.assertEqual(index, 2)
            report = assess(load(workspace))
            self.assertEqual(report['semanticCoverage'], 'PARTIAL')
            self.assertIn('Scopes without authored interpretation: 1', report['reasons'])
