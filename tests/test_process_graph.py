"""Canonical v2 business graph, provenance and deterministic projections."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/mole'))
from molekit.adapters import enrich
from molekit.errors import MoleError
from molekit.knowledge import compose
from molekit.process_graph import empty_graph,merge_graph,validate_process_graph
from molekit.scanner import scan

SOURCE='def complete(score):\n    if score >= 10:\n        return credit(score)\n    return "ineligible"\ndef credit(score): return score\ndef purchase(balance,cost): return balance-cost\n'

class ProcessGraphTests(unittest.TestCase):
    def setUp(self):
        with tempfile.TemporaryDirectory() as repo,tempfile.TemporaryDirectory() as workspace:
            Path(repo,'app.py').write_text(SOURCE)
            self.scan=enrich(scan(repo,workspace))
        self.model=self.scan['model']
        ops={op['title'].split('.')[-1]:op for op in self.model['operations'] if op['kind']=='function'}
        self.claim={'id':'claim-flow','statement':'The source contains completion, wallet credit and independently callable purchase.',
            'status':'source_observed','evidenceIds':[ev['id'] for ev in self.model['evidence']],'limitations':[]}
        self.model['claims']=[self.claim]
        graph=empty_graph(self.model['revision'])
        for key,title in [('complete','Complete game'),('credit','Credit wallet'),('purchase','Purchase cosmetics')]:
            op=ops[key]
            step_ids=['step-'+key] if key!='complete' else ['step-check','step-approved','step-rejected']
            graph['processes'].append({'id':'process-'+key,'title':title,'purpose':title+' using source-backed steps.',
                'trigger':'A caller invokes '+key,'actors':['Caller'],'preconditions':['Inputs supplied'],
                'stepIds':step_ids,'operationIds':[op['id']],'claimIds':['claim-flow'],
                'outcomes':['Source outcome'],'unknowns':[],
                'handoffReview':{'status':'supported' if key=='complete' else 'independent' if key=='purchase' else 'terminal','claimIds':['claim-flow'],'limitations':[]}})
            for step_id in step_ids:
                graph['steps'].append({'id':step_id,'processId':'process-'+key,'title':step_id.removeprefix('step-').capitalize(),
                    'description':'Source-backed '+step_id,'kind':'failure' if step_id=='step-rejected' else 'action',
                    'operationIds':[op['id']],'claimIds':['claim-flow'],'evidenceIds':op['evidenceIds']})
        basis={'label':'Approved','condition':'score >= 10','kind':'branch','resolution':'observed_static',
            'claimIds':['claim-flow'],'evidenceIds':ops['complete']['evidenceIds'],'limitations':[]}
        graph['stepTransitions']=[{**basis,'id':'transition-yes','fromStepId':'step-check','toStepId':'step-approved'},
            {**basis,'id':'transition-no','label':'Ineligible','condition':'score < 10','fromStepId':'step-check','toStepId':'step-rejected'}]
        graph['processHandoffs']=[{**basis,'id':'handoff-credit','label':'Credit eligible reward','kind':'call',
            'fromProcessId':'process-complete','toProcessId':'process-credit'}]
        self.graph=graph

    def test_branching_and_handoffs_survive_projection_without_fake_purchase_order(self):
        validate_process_graph(self.graph,self.model)
        self.scan['processGraph']=self.graph
        model=compose(self.scan)
        views={view['id']:view for view in model['diagramViews']}
        root=model['diagramViews'][0]
        self.assertEqual({node['id'] for node in root['nodes']},{p['id'] for p in self.graph['processes']})
        self.assertEqual(len(root['edgeIds']),1)
        edges={edge['id']:edge for edge in model['relationships']}
        self.assertEqual([(edges[e]['source'],edges[e]['target']) for e in root['edgeIds']], [('process-complete','process-credit')])
        process=views[next(node['childViewId'] for node in root['nodes'] if node['id']=='process-complete')]
        self.assertEqual({node['id'] for node in process['nodes']},{'step-check','step-approved','step-rejected'})
        self.assertEqual(len(process['edgeIds']),2)
        self.assertTrue(all(node.get('childViewId') in views for node in process['nodes']))
        first=copy.deepcopy(model)
        self.assertEqual(first,compose(self.scan))
        self.assertEqual(self.graph,self.scan['processGraph'])

    def test_missing_or_out_of_scope_evidence_rejected(self):
        for field in ('claimIds','evidenceIds'):
            graph=copy.deepcopy(self.graph)
            graph['processHandoffs'][0][field]=[]
            with self.subTest(field=field),self.assertRaises(MoleError):
                validate_process_graph(graph,self.model)
        with self.assertRaises(MoleError):
            validate_process_graph(self.graph,self.model,allowed_operations=set())

    def test_cross_process_step_transition_and_stale_revision_rejected(self):
        graph=copy.deepcopy(self.graph)
        graph['stepTransitions'][0]['toStepId']='step-credit'
        with self.assertRaises(MoleError): validate_process_graph(graph,self.model)
        graph=copy.deepcopy(self.graph)
        graph['baseRevision']='stale'
        with self.assertRaises(MoleError): validate_process_graph(graph,self.model)

    def test_runtime_or_inferred_edges_require_their_actual_basis(self):
        for resolution in ('observed_runtime','inferred'):
            graph=copy.deepcopy(self.graph)
            graph['processHandoffs'][0]['resolution']=resolution
            with self.subTest(resolution=resolution),self.assertRaises(MoleError):
                validate_process_graph(graph,self.model)

    def test_hierarchy_cycles_rejected_and_child_refs_are_valid(self):
        relation={'id':'hierarchy-one','parentProcessId':'process-complete','childProcessId':'process-credit',
            'entryStepId':'step-credit','claimIds':['claim-flow'],'evidenceIds':self.graph['steps'][0]['evidenceIds']}
        self.graph['hierarchy']=[relation,{**relation,'id':'hierarchy-two','parentProcessId':'process-credit','childProcessId':'process-complete','entryStepId':'step-check'}]
        with self.assertRaises(MoleError): validate_process_graph(self.graph,self.model)

    def test_duplicate_hierarchy_pair_is_rejected_before_projection(self):
        relation={'id':'hierarchy-one','parentProcessId':'process-complete','childProcessId':'process-credit',
            'claimIds':['claim-flow'],'evidenceIds':self.graph['steps'][0]['evidenceIds']}
        self.graph['hierarchy']=[relation,{**relation,'id':'hierarchy-two'}]
        with self.assertRaises(MoleError) as caught:
            validate_process_graph(self.graph,self.model)
        self.assertEqual(caught.exception.code,'INVALID_PROCESS_GRAPH')

    def test_glossary_and_business_mappings_survive_canonical_projection(self):
        mapping={'id':'semantic-wallet-step','what':'Credit','why':'Record reward','operationIds':self.graph['processes'][1]['operationIds'],'claimIds':['claim-flow']}
        term={'id':'semantic-wallet','term':'Wallet','definition':'A balance','claimIds':['claim-flow']}
        self.scan['semantic']={'scenarios':[],'businessSteps':[mapping],'glossary':[term]}
        self.scan['processGraph']=self.graph
        projected=compose(self.scan)
        self.assertEqual(projected['glossary'],[term])
        self.assertEqual(projected['businessSteps'],[mapping])

    def test_mixed_legacy_scenarios_are_rejected_instead_of_suppressed(self):
        scene={'id':'semantic-legacy','title':'Legacy flow','trigger':'Caller',
            'operationIds':self.graph['processes'][0]['operationIds'],'claimIds':['claim-flow'],
            'outcomes':['Source outcome'],'unknowns':[]}
        self.scan['semantic']={'scenarios':[scene],'businessSteps':[],'glossary':[]}
        before=copy.deepcopy(self.scan['semantic'])
        self.scan['processGraph']=self.graph
        with self.assertRaises(MoleError) as caught: compose(self.scan)
        self.assertEqual(caught.exception.code,'SEMANTIC_MIGRATION_REQUIRED')
        self.assertEqual(self.scan['semantic'],before)

    def test_changed_graph_entities_require_current_semantic_hash(self):
        changed=copy.deepcopy(self.graph)
        changed['processes'][0]['purpose']='Updated purpose'
        with self.assertRaises(MoleError) as caught:
            merge_graph(self.graph,changed,self.model)
        self.assertEqual(caught.exception.code,'TASK_CONFLICT')
        from molekit.investigations import digest
        changed['baseGraphHash']=digest(self.graph)
        self.assertEqual(merge_graph(self.graph,changed,self.model)['processes'][0]['purpose'],'Updated purpose')

    def test_downgraded_claim_withdraws_connectors_without_erasing_canonical_knowledge(self):
        self.model['claims'][0].update(status='unknown',limitations=['Needs review'])
        self.scan['processGraph']=self.graph
        projected=compose(self.scan)
        self.assertEqual(projected['diagramViews'][0]['edgeIds'],[])
        self.assertEqual(len(self.scan['processGraph']['processHandoffs']),1)
        self.assertTrue(any('Not established:' in value for scene in projected['scenarios'] for value in scene['unknowns']))

    def test_removal_is_explicit_hash_bound_and_cannot_leave_dangling_steps(self):
        from molekit.investigations import digest
        delta={'processGraphVersion':'1.0','baseRevision':self.model['revision'],
            'baseGraphHash':digest(self.graph),'removeIds':['step-rejected']}
        with self.assertRaises(MoleError): merge_graph(self.graph,delta,self.model)
        delta['removeIds'].append('transition-no')
        process=copy.deepcopy(self.graph['processes'][0])
        process['stepIds'].remove('step-rejected')
        delta['processes']=[process]
        updated=merge_graph(self.graph,delta,self.model)
        self.assertEqual(len(updated['steps']),len(self.graph['steps'])-1)
        self.assertIn('step-rejected',[step['id'] for step in self.graph['steps']])

    def test_business_views_survive_a_tight_technical_view_budget(self):
        from unittest.mock import patch
        self.scan['processGraph']=self.graph
        with patch('molekit.knowledge.MAX_VIEWS',4):
            model=compose(self.scan)
        self.assertEqual(len(model['diagramViews']),4)
        self.assertEqual({node['id'] for node in model['diagramViews'][0]['nodes']},{process['id'] for process in self.graph['processes']})
        self.assertTrue(any(item['reason']=='process_technical_drilldown_budget' for item in self.scan['limitations']))


class GraphSubmissionTests(unittest.TestCase):
    def setUp(self):
        import json
        from molekit.investigations import begin,operate
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.repo=self.root/'repo'; self.repo.mkdir()
        (self.repo/'app.py').write_text(SOURCE)
        self.workspace=self.root/'workspace'
        request=self.root/'request.json'
        request.write_text(json.dumps({'requestVersion':'2.0','requestId':'process-map','question':'Explain this service',
            'intent':['system_orientation'],'deliverable':{'contractVersion':'1.0','deliverableType':'interactive_process_map',
            'formats':['html','markdown'],'requirements':[{'id':'overview','kind':'business_overview','required':True}]}}))
        begin(self.repo,self.workspace,request)
        self.task=operate('next',self.workspace)['task']
        fixture=ProcessGraphTests(); fixture.setUp()
        self.graph=fixture.graph; self.claim=fixture.claim
        self.patch={'protocolVersion':'2.0','requestId':'process-map','taskId':self.task['id'],
            'baseRevision':self.task['baseRevision'],'claims':[self.claim],'processGraph':self.graph}
        self.file=self.root/'patch.json'

    def submit(self,value):
        import json
        from molekit.investigations import operate
        self.file.write_text(json.dumps(value))
        return operate('submit',self.workspace,input=self.file)

    def test_canonical_graph_persists_and_pages_across_restart(self):
        import json
        from molekit.investigations import operate
        result=self.submit(self.patch)
        self.assertEqual(result['processGraph']['processesCount'],3)
        self.assertNotEqual(result['investigationState'],'READY_TO_PRESENT')
        self.assertEqual(operate('status',self.workspace)['processGraph'],result['processGraph'])
        self.assertTrue(self.submit(self.patch)['duplicate'])
        cursor,chunks='graph:0',[]
        while cursor:
            page=operate('inspect',self.workspace,task=self.task['id'],cursor=cursor,budget_chars=6000)
            self.assertLessEqual(len(json.dumps(page,ensure_ascii=True))+16,6000)
            chunks.append(page['graphChunk']); cursor=page['nextCursor']
            self.assertLess(len(chunks),100)
        self.assertEqual(json.loads(''.join(chunks)),self.graph)

    def test_invalid_process_patch_is_atomic_and_request_bound(self):
        path=self.workspace/'investigations/process-map/state.json'
        before=path.read_bytes()
        value=copy.deepcopy(self.patch)
        value['processGraph']['processHandoffs'][0]['evidenceIds']=[]
        with self.assertRaises(MoleError): self.submit(value)
        self.assertEqual(before,path.read_bytes())
        value=copy.deepcopy(self.patch); value['requestId']='other-request'
        with self.assertRaises(MoleError): self.submit(value)
        self.assertEqual(before,path.read_bytes())

    def test_semantic_update_keeps_prior_snapshot_and_invalidates_old_graph_cursor(self):
        import json
        from molekit.investigations import operate
        from molekit.workspace import read_json
        first=self.submit(self.patch)
        query=self.root/'query.json'; query.write_text(json.dumps({'focusSymbols':['complete']}))
        task=operate('next',self.workspace,query=query)['task']
        changed=copy.deepcopy(self.graph['processes'][0]); changed['purpose']='Corrected source-backed purpose'
        self.submit({'protocolVersion':'2.0','requestId':'process-map','taskId':task['id'],'baseRevision':task['baseRevision'],
            'claims':[],'processGraph':{'processGraphVersion':'1.0','baseRevision':task['baseRevision'],
            'baseGraphHash':first['processGraph']['hash'],'processes':[changed]}})
        state=read_json(self.workspace/'investigations/process-map/state.json')
        self.assertTrue(state['history'])
        self.assertTrue((self.workspace/'repository/semantic'/(state['history'][-1]['semanticRef']+'.json')).is_file())
        with self.assertRaises(MoleError) as caught:
            operate('inspect',self.workspace,task=task['id'],cursor='graph:'+first['processGraph']['hash']+':1',budget_chars=8000)
        self.assertEqual(caught.exception.code,'TASK_CONFLICT')

    def test_graph_activation_cannot_silently_replace_legacy_scenarios(self):
        import json
        from molekit.investigations import operate
        self.submit({'protocolVersion':'1.0','taskId':self.task['id'],'baseRevision':self.task['baseRevision'],
            'claims':[self.claim],'scenarios':[{'id':'semantic-legacy','title':'Legacy workflow','trigger':'Caller',
            'operationIds':self.graph['processes'][0]['operationIds'],'claimIds':['claim-flow'],
            'outcomes':['Source outcome'],'unknowns':[]}]})
        query=self.root/'query.json'; query.write_text(json.dumps({'focusSymbols':['complete']}))
        task=operate('next',self.workspace,query=query)['task']
        path=self.workspace/'investigations/process-map/state.json'; before=path.read_bytes()
        value={**self.patch,'taskId':task['id'],'claims':[]}
        with self.assertRaises(MoleError) as caught: self.submit(value)
        self.assertEqual(caught.exception.code,'SEMANTIC_MIGRATION_REQUIRED')
        self.assertEqual(path.read_bytes(),before)
        self.assertIsNone(operate('status',self.workspace)['processGraph'])


if __name__=='__main__': unittest.main()
