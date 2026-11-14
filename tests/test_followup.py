"""Follow-ups share fresh knowledge without inheriting completion or changing goals."""
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/mole'))
from molekit.investigations import begin,operate
from molekit.errors import MoleError

class FollowupTests(unittest.TestCase):
    def map_fixture(self):
        from molekit.investigations import operate
        from test_process_graph import GraphSubmissionTests
        fixture=GraphSubmissionTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        fixture.submit(fixture.patch)
        answer={'answerVersion':'1.0','requestId':'process-map','baseRevision':fixture.task['baseRevision'],
            'responseMarkdown':'Completion can credit a wallet. Purchase is independently callable.',
            'assertions':[{'text':fixture.claim['statement'],'claimIds':[fixture.claim['id']],
                'evidenceIds':fixture.claim['evidenceIds'],'category':'observation'}],
            'limitations':['Static source only.'],'selfReview':{'goalMatched':True,'readabilityChecked':True,'knownGaps':[]},'outcome':'ANSWERED'}
        path=fixture.root/'answer.json';path.write_text(json.dumps(answer))
        operate('complete',fixture.workspace,answer=path,output=fixture.root/'output')
        return fixture

    def fixture(self,parent_options=None):
        from test_delivery_contract import DeliveryTests
        fixture=DeliveryTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        fixture.value.update(parent_options or {})
        fixture.start();fixture.complete();return fixture

    def test_followup_reclassifies_goal_and_drops_parent_search_and_output(self):
        fixture=self.fixture({'search':{'paths':['app.py']},
            'userOutputPreference':'artifacts'})
        before=operate('status',fixture.workspace)
        path=fixture.root/'followup.json'
        path.write_text(json.dumps({'requestVersion':'2.0','requestId':'req-two','action':'followUp',
            'parentRequestId':'req-one','turnId':'turn-two','question':'What about invalid tokens?',
            'intent':['explain'],'deliverable':{'contractVersion':'1.0','deliverableType':'chat_answer',
                'requirements':[{'id':'answer','kind':'question_answered','required':True}],'formats':[]}}))
        result=begin(fixture.repo,fixture.workspace,path)
        self.assertEqual(result['requestId'],'req-two')
        self.assertNotEqual(result['investigationState'],'READY_TO_PRESENT')
        old=json.loads((fixture.workspace/'investigations/req-one/state.json').read_text())
        new=json.loads((fixture.workspace/'investigations/req-two/state.json').read_text())
        self.assertEqual(new['semanticRef'],old['semanticRef'])
        self.assertEqual(new['request']['focus'],old['request']['focus'])
        self.assertEqual(new['request']['intent'],['explain'])
        self.assertEqual(new['request']['deliverable']['deliverableType'],'chat_answer')
        self.assertNotIn('search',new['request'])
        self.assertEqual(new['request']['userOutputPreference'],'auto')
        self.assertEqual(new['request']['indexScope'],old['request']['indexScope'])
        self.assertNotIn('answerRef',new)
        self.assertEqual(operate('status',fixture.workspace,request_id='req-one')['investigationState'],before['investigationState'])

    def test_followup_requires_new_intent_and_deliverable(self):
        fixture=self.fixture()
        path=fixture.root/'followup.json';path.write_text(json.dumps({'requestVersion':'2.0','action':'followUp',
            'parentRequestId':'req-one','turnId':'next','question':'What about rollback?'}))
        with self.assertRaises(MoleError) as caught:begin(fixture.repo,fixture.workspace,path)
        self.assertEqual(caught.exception.code,'INVALID_REQUEST')
        self.assertIn('reclassify',str(caught.exception).lower())

    def test_map_followup_can_be_a_chat_answer(self):
        fixture=self.map_fixture()
        path=fixture.root/'followup.json';path.write_text(json.dumps({'requestVersion':'2.0','requestId':'rollback-answer',
            'action':'followUp','parentRequestId':'process-map','turnId':'rollback','question':'What if rollback happens?',
            'intent':['explain'],'deliverable':{'contractVersion':'1.0','deliverableType':'chat_answer',
                'requirements':[{'id':'answer','kind':'question_answered','required':True}],'formats':[]}}))
        result=begin(fixture.repo,fixture.workspace,path)
        state=json.loads((fixture.workspace/'investigations/rollback-answer/state.json').read_text())
        self.assertEqual(state['semanticRef'],json.loads((fixture.workspace/'investigations/process-map/state.json').read_text())['semanticRef'])
        self.assertEqual(state['request']['deliverable']['deliverableType'],'chat_answer')
        self.assertEqual(state['request']['deliverable']['formats'],[])
        self.assertNotIn('answerRef',state)
        self.assertNotEqual(result['investigationState'],'READY_TO_PRESENT')

    def test_map_followup_can_explicitly_request_another_map(self):
        fixture=self.map_fixture()
        path=fixture.root/'followup.json';path.write_text(json.dumps({'requestVersion':'2.0','requestId':'error-map',
            'action':'followUp','parentRequestId':'process-map','turnId':'error','question':'Add the error handling branch.',
            'intent':['system_orientation'],'deliverable':{'contractVersion':'1.0','deliverableType':'interactive_process_map',
                'requirements':[{'id':'overview','kind':'business_overview','required':True}],'formats':['html','markdown']}}))
        result=begin(fixture.repo,fixture.workspace,path)
        state=json.loads((fixture.workspace/'investigations/error-map/state.json').read_text())
        self.assertEqual(state['request']['deliverable']['deliverableType'],'interactive_process_map')
        self.assertEqual(result['processGraph']['processesCount'],3)
        self.assertNotIn('answerRef',state)
        self.assertNotEqual(result['investigationState'],'READY_TO_PRESENT')

    def test_followup_rejects_stale_parent(self):
        fixture=self.fixture();(fixture.repo/'app.py').write_text('def changed(): pass\n')
        path=fixture.root/'followup.json';path.write_text(json.dumps({'requestVersion':'2.0','action':'followUp',
            'parentRequestId':'req-one','turnId':'next','question':'What about rollback?',
            'intent':['investigate'],'deliverable':{'contractVersion':'1.0','deliverableType':'chat_answer',
                'requirements':[{'id':'answer','kind':'question_answered','required':True}],'formats':[]}}))
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
