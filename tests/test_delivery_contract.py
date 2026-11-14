"""Objective completion: no forced chat artifacts or premature map readiness."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/mole'))
from molekit.errors import MoleError
from molekit.investigations import begin,operate
from test_requests import request


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.repo=self.root/'repo';self.repo.mkdir()
        (self.repo/'app.py').write_text('def verify_jwt(token): return bool(token)\n')
        self.workspace=self.root/'workspace'
        self.value=request();self.input=self.root/'request.json'

    def start(self,claim=True):
        self.input.write_text(json.dumps(self.value));begin(self.repo,self.workspace,self.input)
        self.task=operate('next',self.workspace)['task']
        if claim:
            patch=self.root/'patch.json';patch.write_text(json.dumps({'protocolVersion':'1.0','taskId':self.task['id'],
                'baseRevision':self.task['baseRevision'],'claims':[{'id':'claim-observed','statement':'verify_jwt is declared.',
                'status':'source_observed','evidenceIds':self.task['evidenceIds'],'limitations':[]}]}))
            operate('submit',self.workspace,input=patch)
        self.answer={'answerVersion':'1.0','requestId':'req-one','baseRevision':self.task['baseRevision'],
            'responseMarkdown':'verify_jwt is declared in app.py.','assertions':[{'text':'verify_jwt is declared.',
            'claimIds':['claim-observed'],'evidenceIds':self.task['evidenceIds'],'category':'observation'}],
            'limitations':['Static source only.'],'selfReview':{'goalMatched':True,'readabilityChecked':True,'knownGaps':[]},'outcome':'ANSWERED'}
        self.path=self.root/'answer.json'

    def complete(self,**options):
        self.path.write_text(json.dumps(self.answer))
        return operate('complete',self.workspace,answer=self.path,**options)

    def test_chat_ready_without_output_directory_and_check_is_read_only(self):
        self.start()
        result=self.complete(output=self.root/'unwanted')
        self.assertEqual(result['investigationState'],'READY_TO_PRESENT')
        self.assertFalse((self.root/'unwanted').exists())
        self.assertFalse((self.workspace/'outputs').exists())
        state=self.workspace/'investigations/req-one/state.json';before=state.read_bytes()
        self.assertEqual(operate('check',self.workspace)['goalStatus'],'READY_TO_PRESENT')
        self.assertEqual(before,state.read_bytes())

    def test_map_cannot_complete_after_inspect_or_prose_alone(self):
        self.value['intent']=['system_orientation'];self.value['focus']=[]
        self.value['deliverable'].update(deliverableType='interactive_process_map',formats=['html','markdown'])
        self.start()
        operate('inspect',self.workspace,task=self.task['id'],budget_chars=12000)
        with self.assertRaises(MoleError) as caught:self.complete(output=self.root/'output')
        self.assertEqual(caught.exception.code,'DELIVERABLE_INCOMPLETE')
        self.assertFalse((self.root/'output').exists())
        self.assertTrue(operate('check',self.workspace)['missing'])

    def test_unknown_assertion_refs_or_static_runtime_guarantees_are_rejected(self):
        self.start()
        self.answer['assertions'][0]['claimIds']=['invented']
        with self.assertRaises(MoleError):self.complete()
        self.answer['assertions'][0].update(claimIds=['claim-observed'],category='runtime_guarantee',guaranteeKind='security')
        with self.assertRaises(MoleError):self.complete()

    def test_broken_source_locator_is_rejected(self):
        self.start();self.answer['responseMarkdown']='[Source](does-not-exist.py#L999)'
        with self.assertRaises(MoleError):self.complete()

    def test_cited_material_claim_requires_review(self):
        self.start(claim=False)
        patch=self.root/'material.json';patch.write_text(json.dumps({'protocolVersion':'1.0','taskId':self.task['id'],
            'baseRevision':self.task['baseRevision'],'claims':[{'id':'claim-observed','statement':'The transaction commits after validation.',
            'status':'source_observed','evidenceIds':self.task['evidenceIds'],'limitations':[]}]}))
        operate('submit',self.workspace,input=patch)
        with self.assertRaises(MoleError) as caught:self.complete()
        self.assertEqual(caught.exception.code,'DELIVERABLE_INCOMPLETE')

    def test_stale_source_cannot_reuse_a_ready_answer(self):
        self.start();self.complete()
        (self.repo/'app.py').write_text('def verify_jwt(token): return False\n')
        self.assertEqual(operate('check',self.workspace)['goalStatus'],'BLOCKED')
        self.assertEqual(operate('status',self.workspace)['investigationState'],'BLOCKED')
        with self.assertRaises(MoleError):self.complete()
        operate('update',self.workspace)
        self.assertNotEqual(operate('check',self.workspace)['goalStatus'],'READY_TO_PRESENT')

    def test_explicit_partial_never_becomes_ready(self):
        self.start();self.answer['outcome']='PARTIAL';self.answer['selfReview']['knownGaps']=['Runtime verification unavailable.']
        with self.assertRaises(MoleError):self.complete()
        result=self.complete(allow_partial=True)
        self.assertEqual(result['investigationState'],'PARTIAL_READY')

class MapDeliveryTests(unittest.TestCase):
    def test_generated_map_is_checked_and_tampering_revokes_ready(self):
        from test_process_graph import GraphSubmissionTests
        fixture=GraphSubmissionTests();fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.submit(fixture.patch)
        answer={'answerVersion':'1.0','requestId':'process-map','baseRevision':fixture.task['baseRevision'],
            'responseMarkdown':'Completion can credit a wallet. Purchase is independently callable.',
            'assertions':[{'text':fixture.claim['statement'],'claimIds':[fixture.claim['id']],
                'evidenceIds':fixture.claim['evidenceIds'],'category':'observation'}],
            'limitations':['Static source only.'],'selfReview':{'goalMatched':True,'readabilityChecked':True,'knownGaps':[]},'outcome':'ANSWERED'}
        path=fixture.root/'answer.json';path.write_text(json.dumps(answer))
        result=operate('complete',fixture.workspace,answer=path,output=fixture.root/'output')
        self.assertEqual(result['goalStatus'],'READY_TO_PRESENT')
        delivery=result['delivery']
        html=Path(delivery['output'])/'explorer.html'
        self.assertTrue(html.is_file())
        # Rewording the answer must publish a new answer-bound generation.
        answer['responseMarkdown']+=' Runtime guarantees remain unchecked.'
        path.write_text(json.dumps(answer))
        revised=operate('complete',fixture.workspace,answer=path,output=fixture.root/'output')
        self.assertNotEqual(result['delivery']['generation'],revised['delivery']['generation'])
        self.assertIn('Runtime guarantees', (Path(revised['delivery']['output'])/'answer.md').read_text())
        html=Path(revised['delivery']['output'])/'explorer.html'
        linked=next((Path(revised['delivery']['output'])/'processes').glob('*.md'))
        original=linked.read_bytes();linked.unlink()
        self.assertNotEqual(operate('check',fixture.workspace)['goalStatus'],'READY_TO_PRESENT')
        linked.write_bytes(original)
        html.write_text('broken')
        self.assertNotEqual(operate('check',fixture.workspace)['goalStatus'],'READY_TO_PRESENT')

    def test_partial_map_stays_partial_on_repeated_read_only_check(self):
        from test_process_graph import GraphSubmissionTests
        fixture=GraphSubmissionTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        fixture.submit(fixture.patch)
        answer={'answerVersion':'1.0','requestId':'process-map','baseRevision':fixture.task['baseRevision'],
            'responseMarkdown':'Completion has a statically observed wallet path; runtime guarantees remain unknown.',
            'assertions':[{'text':fixture.claim['statement'],'claimIds':[fixture.claim['id']],
                'evidenceIds':fixture.claim['evidenceIds'],'category':'observation'}],
            'limitations':['Runtime behavior is unverified.'],'selfReview':{'goalMatched':True,'readabilityChecked':True,'knownGaps':['Runtime behavior.']},'outcome':'PARTIAL'}
        path=fixture.root/'answer.json';path.write_text(json.dumps(answer))
        result=operate('complete',fixture.workspace,answer=path,output=fixture.root/'output',allow_partial=True)
        self.assertEqual(result['goalStatus'],'PARTIAL_READY')
        for _ in range(2):
            checked=operate('check',fixture.workspace)
            self.assertEqual(checked['goalStatus'],'PARTIAL_READY')
            self.assertEqual(checked['investigationState'],'PARTIAL_READY')
