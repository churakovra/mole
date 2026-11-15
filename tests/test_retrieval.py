"""Goal-aware retrieval: actual cross-module paths, ambiguity and honest bounds."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/mole'))
from molekit.adapters import enrich
from molekit.retrieval import SearchQuery, search
from molekit.scanner import scan


class RetrievalTests(unittest.TestCase):
    def analyze(self, fixture):
        with tempfile.TemporaryDirectory() as tmp:
            return enrich(scan(Path(__file__).parent/'fixtures'/fixture,tmp))

    def paths(self, result, found):
        model=result['model']
        sources={source['id']:source['path'] for source in model['sources']}
        return {sources[evidence['sourceId']] for evidence in model['evidence'] if evidence['id'] in found['evidenceIds']}

    def test_route_trace_crosses_answer_directory_without_cutting_index(self):
        result=self.analyze('cross-file-workflow')
        found=search(result,SearchQuery(text='POST /orders',direction='forward'),answer_scope='api.py')
        self.assertTrue({'api.py','service.py','repository.py','publisher.py','worker.py'}<=self.paths(result,found))
        self.assertTrue(found['matchReasons'])
        self.assertTrue(all(edge['resolution']!='observed_runtime' for edge in found['relationships']))

    def test_focused_game_trace_does_not_invent_purchase_ordering(self):
        result=self.analyze('game-settlement')
        found=search(result,SearchQuery(text='POST /games/complete',direction='forward'),answer_scope='completion.py')
        self.assertTrue({'completion.py','settlement.py','wallet.py'}<=self.paths(result,found))
        ops={op['id']:op for op in result['model']['operations']}
        self.assertFalse(any(ops[oid]['title']=='wallet.purchase' for oid in found['operationIds']))

    def test_missing_route_never_falls_back_to_an_arbitrary_post_handler(self):
        found=search(self.analyze('cross-file-workflow'),SearchQuery(text='POST /unknown'))
        self.assertEqual(found['operationIds'],[])
        self.assertTrue(found['negativeSearch'])
        self.assertIn('indexed',found['negativeSearch']['scope'])

    def test_ambiguous_basename_retains_both_declarations(self):
        result=self.analyze('ambiguous-symbols')
        found=search(result,SearchQuery(focus_symbols=('process_order',),direction='none'))
        self.assertEqual(len(found['ambiguities']),1)
        self.assertEqual(len(found['ambiguities'][0]['operationIds']),2)
        limited=search(result,SearchQuery(focus_symbols=('process_order',),direction='none',limit=1))
        self.assertEqual(limited['ambiguities'][0]['matchCount'],2)
        self.assertEqual(len(limited['operationIds']),1)

    def test_root_route_is_exact_and_does_not_select_other_get_routes(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as repo:
            Path(repo,'app.py').write_text('from fastapi import FastAPI\napp=FastAPI()\n@app.get("/")\ndef root(): return 1\n@app.get("/other")\ndef other(): return 2\n')
            result=enrich(scan(repo,tmp))
        found=search(result,SearchQuery(text='GET /',direction='none'))
        ops={op['id']:op for op in result['model']['operations']}
        self.assertEqual([ops[oid]['routePath'] for oid in found['operationIds']],['/'])

    def test_missing_literal_route_with_dynamic_registration_stays_partial(self):
        with tempfile.TemporaryDirectory() as tmp,tempfile.TemporaryDirectory() as repo:
            Path(repo,'app.py').write_text('from fastapi import FastAPI\napp=FastAPI()\n@app.post(route_path)\ndef handler(): return 1\n')
            result=enrich(scan(repo,tmp))
        found=search(result,SearchQuery(text='POST /orders'))
        self.assertEqual(found['operationIds'],[])
        self.assertEqual(found['coverage'],'PARTIAL')
        self.assertTrue(any(item['reason']=='dynamic_route_registration_unresolved' for item in found['coverageLimitations']))

    def test_reverse_traversal_finds_callers(self):
        result=self.analyze('cross-file-workflow')
        found=search(result,SearchQuery(focus_symbols=('repository.Store.save',),direction='reverse'))
        self.assertTrue({'api.py','service.py','repository.py'}<=self.paths(result,found))

    def test_budget_frontier_has_no_dangling_returned_edges(self):
        result=self.analyze('cross-file-workflow')
        found=search(result,SearchQuery(text='POST /orders',direction='forward',max_nodes=3,max_depth=1))
        self.assertLessEqual(len(found['operationIds']),3)
        self.assertTrue(found['frontier'])
        ids=set(found['operationIds'])
        self.assertTrue(all(edge['source'] in ids and edge['target'] in ids for edge in found['relationships']))
        self.assertTrue(found['truncation'])

    def test_unsupported_language_is_not_ast_runtime_evidence(self):
        result=self.analyze('game-settlement')
        found=search(result,SearchQuery(text='verifier',direction='none'))
        self.assertIn('verifier.ts',self.paths(result,found))
        self.assertTrue(found['coverageLimitations'])
        self.assertNotEqual(found['coverage'],'PASS')

    def test_duplicate_question_expands_to_ack_retry_candidates_with_reasons(self):
        result=self.analyze('consumer-retry-idempotency')
        found=search(result,SearchQuery(text='duplicate notifications',direction='both'))
        ops={op['id']:op for op in result['model']['operations']}
        self.assertTrue(any(ops[oid]['kind']=='acknowledgement' for oid in found['operationIds']))
        self.assertTrue(any('candidate expansion' in reason for item in found['matchReasons'] for reason in item['reasons']))

    def test_cycle_is_bounded_and_deterministic(self):
        result=self.analyze('cross-file-workflow')
        query=SearchQuery(text='POST /orders',direction='both',max_nodes=15)
        self.assertEqual(search(result,query),search(result,query))
        self.assertLessEqual(len(search(result,query)['operationIds']),15)

    def test_high_fanout_queue_and_frontier_preview_are_bounded(self):
        operations=[{'id':'op-'+str(i),'kind':'function','title':'main' if i==0 else 'f'+str(i),'evidenceIds':['ev']} for i in range(10000)]
        model={'operations':operations,'sources':[{'id':'src','path':'app.py'}],
               'evidence':[{'id':'ev','sourceId':'src'}],
               'relationships':[{'id':'edge-'+str(i),'source':'op-0','target':'op-'+str(i),'kind':'calls','resolution':'possible','evidenceIds':['ev']} for i in range(1,10000)]}
        found=search({'model':model},SearchQuery(focus_symbols=('main',),max_nodes=3))
        self.assertEqual(len(found['operationIds']),3)
        self.assertLessEqual(len(found['frontier']),100)
        self.assertGreater(found['frontierCount'],1000)
        self.assertIn('frontier_preview_limit',found['truncation'])

    def test_limited_index_does_not_claim_repository_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            result=enrich(scan(Path(__file__).parent/'fixtures/cross-file-workflow',tmp,scope='api.py'))
        found=search(result,SearchQuery(text='POST /orders'),answer_scope='repository')
        self.assertEqual(found['coverage'],'PARTIAL')
        self.assertTrue(any(item['reason']=='index_scope_boundary' for item in found['coverageLimitations']))

    def test_document_headings_are_searchable_metadata_only(self):
        result=self.analyze('game-settlement')
        found=search(result,SearchQuery(text='game completion rewards',direction='none'))
        self.assertIn('README.md',self.paths(result,found))
        self.assertTrue(all(claim['status']!='runtime_verified' for claim in result['model']['claims']))

    def test_thousand_way_ambiguity_keeps_request_metadata_pageable(self):
        import json
        from molekit.investigations import _initial_tasks,summary
        from molekit.requests import validate_request
        operations=[{'id':'op-'+str(i).zfill(30),'kind':'function','title':'app'+str(i)+'.main','evidenceIds':['ev']} for i in range(1000)]
        scan={'model':{'revision':'a'*64,'operations':operations,'relationships':[],
            'sources':[{'id':'src','path':'app.py'}],'evidence':[{'id':'ev','sourceId':'src'}]}}
        request=validate_request({'requestVersion':'2.0','requestId':'ambiguous','question':'Which main?',
            'intent':['locate'],'focus':['main'],'limits':{'maxNodes':1000},
            'search':{'limit':1000,'maxNodes':1000,'direction':'none'},
            'deliverable':{'contractVersion':'1.0','deliverableType':'chat_answer','formats':[],
            'requirements':[{'id':'answer','kind':'question_answered','required':True}]}})
        tasks,limitations,retrieval=_initial_tasks(request,scan)
        session={'tasks':tasks,'request':request,'retrieval':retrieval,'requestId':'ambiguous',
            'counters':{'probeRounds':0,'evidenceChars':0,'noProgressRounds':0},
            'repositorySnapshotRef':'a'*64,'investigationState':'PLANNING','phase':'PLAN','limitations':limitations}
        result=summary({'indexScope':'repository'},session,scan)
        self.assertLessEqual(len(json.dumps(result['search'])),4000)
        self.assertEqual(result['search']['ambiguityCount'],1)
        ambiguity=result['search']['ambiguities'][0]
        self.assertEqual(ambiguity['matchCount'],1000)
        self.assertTrue(ambiguity['previewTruncated'])
        self.assertEqual(len(ambiguity['operationIds']),20)

    def test_dense_graph_edge_output_is_explicitly_bounded(self):
        operations=[{'id':'op-'+str(i),'kind':'function','title':'f'+str(i),'evidenceIds':['ev']} for i in range(5)]
        model={'operations':operations,'sources':[{'id':'src','path':'app.py'}],'evidence':[{'id':'ev','sourceId':'src'}],
            'relationships':[{'id':str(i)+'-'+str(j),'source':'op-'+str(i),'target':'op-'+str(j),'kind':'calls','resolution':'possible','evidenceIds':['ev']} for i in range(5) for j in range(5) if i!=j]}
        result=search({'model':model},SearchQuery(direction='none',max_edges=2))
        self.assertEqual(len(result['relationships']),2)
        self.assertIn('edge_budget',result['truncation'])

    def test_new_symbol_probe_does_not_keep_the_original_exact_route(self):
        from molekit.retrieval import query_for_request
        from molekit.requests import validate_request
        request=validate_request({'requestVersion':'2.0','question':'Trace POST /orders',
            'intent':['trace'],'focus':['api.create_order'],
            'deliverable':{'contractVersion':'1.0','deliverableType':'chat_answer','formats':[],
                'requirements':[{'id':'answer','kind':'trace_path','required':True}]}})
        query,_=query_for_request(request,{'focusSymbols':['publisher.publish_order']})
        self.assertEqual(query.text,'')
        found=search(self.analyze('cross-file-workflow'),query)
        self.assertTrue(any('exact symbol candidate: publisher.publish_order' in item['reasons'] for item in found['matchReasons']))
        self.assertFalse(any('exact route' in reason for item in found['matchReasons'] for reason in item['reasons']))
        topic,_=query_for_request(request,{'topics':['rollback']})
        self.assertEqual(topic.focus_symbols,())
        self.assertEqual(request['question'],'Trace POST /orders')
        request['search']={'focusSymbols':['publisher.publish_order'],'direction':'forward'}
        reverse,_=query_for_request(request,{'direction':'reverse'})
        self.assertEqual(reverse.focus_symbols,('publisher.publish_order',))
        self.assertEqual(reverse.text,'')
        self.assertEqual(reverse.direction,'reverse')


if __name__=='__main__': unittest.main()
