"""Follow-ups share fresh knowledge without inheriting completion or changing goals."""
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/mole'))
from molekit.investigations import begin,operate
from molekit.errors import MoleError

class FollowupTests(unittest.TestCase):
    def fixture(self):
        from test_delivery_contract import DeliveryTests
        fixture=DeliveryTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        fixture.start();fixture.complete();return fixture

    def test_followup_inherits_focus_and_semantics_but_not_answer(self):
        fixture=self.fixture();before=operate('status',fixture.workspace)
        path=fixture.root/'followup.json'
        path.write_text(json.dumps({'requestVersion':'2.0','requestId':'req-two','action':'followUp',
            'parentRequestId':'req-one','turnId':'turn-two','question':'What about invalid tokens?'}))
        result=begin(fixture.repo,fixture.workspace,path)
        self.assertEqual(result['requestId'],'req-two')
        self.assertNotEqual(result['investigationState'],'READY_TO_PRESENT')
        old=json.loads((fixture.workspace/'investigations/req-one/state.json').read_text())
        new=json.loads((fixture.workspace/'investigations/req-two/state.json').read_text())
        self.assertEqual(new['semanticRef'],old['semanticRef'])
        self.assertEqual(new['request']['focus'],old['request']['focus'])
        self.assertNotIn('answerRef',new)
        self.assertEqual(operate('status',fixture.workspace,request_id='req-one')['investigationState'],before['investigationState'])

    def test_followup_rejects_stale_parent(self):
        fixture=self.fixture();(fixture.repo/'app.py').write_text('def changed(): pass\n')
        path=fixture.root/'followup.json';path.write_text(json.dumps({'requestVersion':'2.0','action':'followUp',
            'parentRequestId':'req-one','turnId':'next','question':'What about rollback?'}))
        with self.assertRaises(MoleError) as caught:begin(fixture.repo,fixture.workspace,path)
        self.assertEqual(caught.exception.code,'TASK_STALE')

class ReuseTests(unittest.TestCase):
    def test_unrelated_file_change_preserves_claim_but_own_source_change_invalidates(self):
        from test_delivery_contract import DeliveryTests
        fixture=DeliveryTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        (fixture.repo/'other.py').write_text('def unrelated(): return 1\n')
        fixture.start()
        (fixture.repo/'other.py').write_text('def unrelated(): return 2\n')
        report=operate('update',fixture.workspace)['changes']
        self.assertEqual(report['reusedClaims'],1)
        self.assertEqual(report['invalidatedClaims'],[])
        (fixture.repo/'other.py').write_text('def unrelated(): return 3\n')
        self.assertEqual(operate('update',fixture.workspace)['changes']['reusedClaims'],1)
        (fixture.repo/'app.py').write_text('def verify_jwt(token): return False\n')
        report=operate('update',fixture.workspace)['changes']
        self.assertEqual(report['reusedClaims'],0)
        self.assertIn('claim-observed',report['invalidatedClaims'])

    def test_glossary_survives_unrelated_update_and_restart(self):
        from test_delivery_contract import DeliveryTests
        fixture=DeliveryTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        (fixture.repo/'other.py').write_text('def unrelated(): return 1\n')
        fixture.start(claim=False)
        patch=fixture.root/'semantic.json';patch.write_text(json.dumps({'protocolVersion':'1.0','taskId':fixture.task['id'],
            'baseRevision':fixture.task['baseRevision'],'claims':[{'id':'claim-token','statement':'JWT verification is declared.',
            'status':'source_observed','evidenceIds':fixture.task['evidenceIds'],'limitations':[]}],
            'glossary':[{'id':'semantic-token','term':'JWT','definition':'Token checked by verify_jwt.','claimIds':['claim-token']}]}))
        operate('submit',fixture.workspace,input=patch)
        (fixture.repo/'other.py').write_text('def unrelated(): return 2\n')
        self.assertEqual(operate('update',fixture.workspace)['changes']['reusedClaims'],1)
        from molekit.investigations import _knowledge,_manifest,_session
        manifest=_manifest(fixture.workspace);session=_session(fixture.workspace,manifest)
        self.assertEqual(_knowledge(fixture.workspace,session)['semantic']['glossary'][0]['id'],'semantic-token')

    def test_withdrawn_handoff_reopens_review_without_corrupting_processes(self):
        from test_delivery_contract import DeliveryTests
        from test_process_graph import ProcessGraphTests,SOURCE
        fixture=DeliveryTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        (fixture.repo/'app.py').write_text(SOURCE)
        (fixture.repo/'other.py').write_text('def unrelated(): return 1\n')
        fixture.value['intent']=['system_orientation'];fixture.value['focus']=[]
        fixture.value['search']={'paths':['app.py']}
        fixture.start(claim=False)
        graph_fixture=ProcessGraphTests();graph_fixture.setUp();graph=graph_fixture.graph
        graph['baseRevision']=fixture.task['baseRevision'];handoff=graph['processHandoffs'].pop()
        patch=fixture.root/'process.json'
        patch.write_text(json.dumps({'protocolVersion':'2.0','requestId':'req-one','taskId':fixture.task['id'],
            'baseRevision':fixture.task['baseRevision'],'claims':[graph_fixture.claim],'processGraph':graph}))
        operate('submit',fixture.workspace,input=patch)
        query=fixture.root/'query.json';query.write_text(json.dumps({'paths':['app.py','other.py']}))
        broad=operate('next',fixture.workspace,query=query)['task']
        handoff['claimIds']=['claim-handoff']
        basis=operate('status',fixture.workspace)['processGraph']['hash']
        patch.write_text(json.dumps({'protocolVersion':'2.0','requestId':'req-one','taskId':broad['id'],
            'baseRevision':broad['baseRevision'],'claims':[{'id':'claim-handoff','statement':'Completion invokes wallet credit.',
            'status':'source_observed','evidenceIds':graph_fixture.claim['evidenceIds'],'limitations':[]}],
            'processGraph':{'processGraphVersion':'1.0','baseRevision':broad['baseRevision'],'baseGraphHash':basis,'processHandoffs':[handoff]}}))
        operate('submit',fixture.workspace,input=patch)
        (fixture.repo/'other.py').write_text('def unrelated(): return 2\n')
        report=operate('update',fixture.workspace)['changes']
        self.assertIn('claim-handoff',report['invalidatedClaims'])
        self.assertNotIn('claim-flow',report['invalidatedClaims'])
        self.assertEqual(operate('status',fixture.workspace)['processGraph']['processesCount'],3)
        from molekit.investigations import _knowledge,_manifest,_session
        manifest=_manifest(fixture.workspace);session=_session(fixture.workspace,manifest)
        retained=_knowledge(fixture.workspace,session)['processGraph']
        self.assertEqual(retained['processHandoffs'],[])
        self.assertNotIn('handoffReview',retained['processes'][0])
