"""Bounded v2 progress, restart and structural repair behavior."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/mole'))
from molekit.errors import MoleError
from molekit.investigations import begin,operate
from molekit.workspace import read_json
from test_requests import request


class AgentLoopTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.repo=self.root/'repo';self.repo.mkdir()
        (self.repo/'app.py').write_text('def verify_jwt(token):\n    return bool(token)\n')
        self.workspace=self.root/'workspace'

    def start(self,value=None):
        path=self.root/'request.json';path.write_text(json.dumps(value or request()))
        begin(self.repo,self.workspace,path)
        return operate('next',self.workspace)['task']

    def test_repeated_next_is_idempotent_and_does_not_block(self):
        task=self.start()
        results=[operate('next',self.workspace) for _ in range(5)]
        self.assertTrue(all(result['task']==task for result in results))
        self.assertTrue(all(result['investigationState']=='INVESTIGATING' for result in results))
        self.assertTrue(all(result['progress']['noProgressRounds']==0 for result in results))

    def test_repeated_page_read_is_idempotent_and_unique_page_is_charged_once(self):
        task=self.start()
        page=operate('inspect',self.workspace,task=task['id'],budget_chars=12000)
        self.assertEqual(page['investigationState'],'INVESTIGATING')
        charged=page['progress']['evidenceChars']
        repeated=[operate('inspect',self.workspace,task=task['id'],budget_chars=12000) for _ in range(5)]
        self.assertTrue(all(result['progress']['evidenceChars']==charged for result in repeated))
        self.assertTrue(all(result['progress']['probeRounds']==1 for result in repeated))
        self.assertTrue(all(result['investigationState']=='INVESTIGATING' for result in repeated))
        self.assertTrue(all(result['progress']['noProgressRounds']==0 for result in repeated))

    def test_next_after_restart_keeps_pending_task(self):
        task=self.start()
        # Each operate call reloads the persisted session from the workspace.
        for _ in range(5):
            result=operate('next',self.workspace)
            self.assertEqual(result['task'],task)
        self.assertEqual(result['investigationState'],'INVESTIGATING')

    def test_evidence_budget_blocks_before_overrun_and_persists_on_restart(self):
        (self.repo/'app.py').write_text('def verify_jwt(token):\n'+'    value = bool(token)\n'*100+'    return value\n')
        value=request();value['limits']['maxEvidenceChars']=1024
        task=self.start(value)
        with self.assertRaises(MoleError) as caught:
            operate('inspect',self.workspace,task=task['id'],budget_chars=12000)
        self.assertEqual(caught.exception.code,'BUDGET_EXHAUSTED')
        result=operate('status',self.workspace)
        self.assertEqual(result['investigationState'],'BLOCKED')
        self.assertLessEqual(result['progress']['evidenceChars'],1024)

    def test_round_budget_counts_tasks_not_source_pages(self):
        (self.repo/'app.py').write_text('def verify_jwt(token):\n'+'    value = bool(token)\n'*100+'    return value\n')
        value=request();value['limits']['maxProbeRounds']=1
        task=self.start(value)
        cursor='0:0';pages=0
        while cursor:
            page=operate('inspect',self.workspace,task=task['id'],budget_chars=6000,cursor=cursor)
            cursor=page['nextCursor'];pages+=1
        self.assertGreater(pages,1)
        self.assertEqual(page['progress']['probeRounds'],1)

    def test_unfulfilled_map_gets_goal_repair_task_after_claim_submission(self):
        value=request();value['intent']=['system_orientation'];value['focus']=[]
        value['deliverable'].update(deliverableType='interactive_process_map',formats=['html','markdown'])
        task=self.start(value)
        path=self.root/'patch.json';path.write_text(json.dumps({'protocolVersion':'1.0','taskId':task['id'],
            'baseRevision':task['baseRevision'],'claims':[{'id':'claim-source','statement':'A function is declared.',
            'status':'source_observed','evidenceIds':task['evidenceIds'],'limitations':[]}]}))
        operate('submit',self.workspace,input=path)
        result=operate('next',self.workspace)
        self.assertEqual(result['task']['kind'],'review_process')
        self.assertIn('business_overview',result['task']['limitations'][0])
        self.assertNotEqual(result['investigationState'],'READY_TO_PRESENT')
