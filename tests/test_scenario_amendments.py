import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/mole'))
from molekit.errors import MoleError
from molekit.pipeline import start, operate
from molekit.workspace import load


class ScenarioAmendmentTests(unittest.TestCase):
    def test_later_related_task_extends_one_scenario_and_stale_or_unrelated_patch_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, workspace = Path(tmp) / 'repo', Path(tmp) / 'workspace'
            repo.mkdir()
            (repo / 'api.py').write_text('from fastapi import FastAPI\napp=FastAPI()\ndef shared(): return True\n@app.get("/a")\ndef first(): return shared()\n@app.post("/b")\ndef second(): return shared()\n')
            (repo / 'unrelated.py').write_text('def unrelated(): return 7\n')
            start(repo, workspace, 'standard', 'repository')
            path = Path(tmp) / 'patch.json'
            def submit(task, claim, **extra):
                value = {'protocolVersion':'1.0','taskId':task['id'],'baseRevision':task['baseRevision'],
                    'claims':[{'id':claim,'statement':'Static callable behavior is source bounded.', 'status':'inferred',
                               'evidenceIds':task['evidenceIds'],'limitations':['Runtime behavior not tested']}], **extra}
                path.write_text(json.dumps(value))
                return operate('submit',workspace,input=path)
            first = operate('next',workspace)['task']
            self.assertEqual(first['kind'],'workflow_review')
            scene = {'id':'semantic-combined','title':'Shared boolean check','trigger':'HTTP call',
                     'operationIds':first['operationIds'],'claimIds':['c-first'],'outcomes':['Boolean candidate'], 'unknowns':['Runtime startup untested']}
            submit(first,'c-first',scenarios=[scene])
            second = operate('next',workspace)['task']
            self.assertEqual(second['kind'],'workflow_review')
            page = operate('inspect',workspace,task=second['id'],budget_chars=3000,cursor='scenes:0')
            self.assertEqual(page['scenarios'][0]['id'],scene['id'])
            amendment = {'scenarioId':scene['id'],'expectedHash':'stale','addOperationIds':second['operationIds'],
                         'addClaimIds':['c-second'],'addOutcomes':['Second HTTP entry also reaches the helper']}
            before = (workspace / 'state.json').read_bytes()
            with self.assertRaises(MoleError) as caught:
                submit(second,'c-second',scenarioAmendments=[amendment])
            self.assertEqual(caught.exception.code,'TASK_CONFLICT')
            self.assertEqual((workspace / 'state.json').read_bytes(),before)
            amendment['expectedHash'] = page['scenarios'][0]['expectedHash']
            submit(second,'c-second',scenarioAmendments=[amendment])
            authored = load(workspace)['scan']['semantic']['scenarios']
            self.assertEqual(len(authored),1)
            self.assertEqual(set(authored[0]['operationIds']),set(first['operationIds'])|set(second['operationIds']))
            self.assertEqual(authored[0]['claimIds'],['c-first','c-second'])
            other = operate('next',workspace)['task']
            page = operate('inspect',workspace,task=other['id'],budget_chars=3000,cursor='scenes:0')
            self.assertEqual(page['scenarios'],[])
            amendment.update(addOperationIds=other['operationIds'],addClaimIds=['c-unrelated'])
            with self.assertRaises(MoleError) as caught:
                submit(other,'c-unrelated',scenarioAmendments=[amendment])
            self.assertEqual(caught.exception.code,'INSUFFICIENT_EVIDENCE')

            # Invalidating one contributor reopens all surviving authoring scopes.
            source = repo / 'api.py'
            source.write_text(source.read_text().replace('def second(): return shared()', 'def second():\n    result = shared()\n    return result'))
            result = operate('update', workspace)
            self.assertIn('semantic-combined', result['changes']['invalidatedSemanticIds'])
            state = load(workspace)
            self.assertEqual(state['scan']['semantic']['scenarios'], [])
            contributing = {first['scopeId'], second['scopeId']}
            self.assertTrue(contributing <= set(result['changes']['reopenedSemanticScopes']))
            self.assertTrue(all(task['status'] == 'pending' for task in state['tasks'] if task.get('scopeId') in contributing))
