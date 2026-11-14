"""Versioned request admission and isolated investigation persistence."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/mole'))
from molekit.errors import MoleError
from molekit.requests import validate_request
from molekit.investigations import begin, operate
from molekit.workspace import read_json


def request(request_id='req-one', question='Where is verify_jwt?'):
    return {'requestVersion': '2.0', 'requestId': request_id, 'question': question,
            'intent': ['locate'], 'audience': 'developer', 'focus': ['verify_jwt'],
            'indexScope': 'repository', 'answerScope': 'repository', 'userOutputPreference': 'auto',
            'deliverable': {'contractVersion': '1.0', 'deliverableType': 'chat_answer',
                            'requirements': [{'id': 'answer', 'kind': 'question_answered', 'required': True}],
                            'formats': []}, 'limits': {'maxProbeRounds': 12, 'maxEvidenceChars': 160000}}


class RequestTests(unittest.TestCase):
    def test_rooted_scope_is_rejected_even_with_windows_path_semantics(self):
        from pathlib import PureWindowsPath
        from molekit.requests import safe_scope
        with patch('molekit.requests.Path', PureWindowsPath):
            for scope in ('/root','//server/share','C:/root','C:root','\\root','../escape','bad\x00path'):
                with self.subTest(scope=scope), self.assertRaises(MoleError):
                    safe_scope(scope)

    def test_request_and_deliverable_are_both_required(self):
        value = request()
        self.assertEqual(validate_request(value)['question'], value['question'])
        for key in ('question', 'intent', 'deliverable'):
            bad = copy.deepcopy(value)
            del bad[key]
            with self.subTest(key=key), self.assertRaises(MoleError):
                validate_request(bad)

    def test_unknown_fields_types_enums_limits_and_traversal_rejected(self):
        for key, value in [('requestVersion', '9'), ('intent', ['magic']), ('intent', []),
                           ('question', ''), ('question', 'x'*9000), ('requestId', '../other'),
                           ('requestId', 'a/b'), ('answerScope', '../escape'), ('indexScope', '/root'),
                           ('focus', 'verify_jwt'), ('unexpected', 'secret-value'),
                           ('limits', {'maxProbeRounds': True}), ('limits', {'maxEvidenceChars': 0})]:
            bad = request()
            bad[key] = value
            with self.subTest(key=key, value=str(value)[:40]), self.assertRaises(MoleError):
                validate_request(bad)

    def test_text_only_cannot_be_overridden_by_map_contract(self):
        value = request()
        value['userOutputPreference'] = 'text_only'
        value['deliverable']['deliverableType'] = 'interactive_process_map'
        value['deliverable']['formats'] = ['html', 'markdown']
        with self.assertRaises(MoleError):
            validate_request(value)

    def test_duplicate_requirement_ids_and_empty_map_formats_rejected(self):
        value = request()
        value['deliverable']['requirements'] *= 2
        with self.assertRaises(MoleError):
            validate_request(value)
        value = request()
        value['deliverable']['deliverableType'] = 'interactive_process_map'
        with self.assertRaises(MoleError):
            validate_request(value)

    def test_sensitive_question_is_redacted_before_persistence(self):
        value = request(question='Find password="super-secret-987" usage')
        self.assertNotIn('super-secret-987', json.dumps(validate_request(value)))


class InvestigationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root/'repo'
        self.repo.mkdir()
        (self.repo/'app.py').write_text('def verify_jwt(token):\n    return bool(token)\n')
        self.workspace = self.root/'workspace'
        self.input = self.root/'request.json'

    def begin(self, value=None):
        self.input.write_text(json.dumps(value or request()))
        return begin(self.repo, self.workspace, self.input)

    def test_begin_status_resume_and_two_questions_share_source_snapshot(self):
        first = self.begin()
        self.assertEqual(first['protocolVersion'], '2.0')
        self.assertEqual(first['requestId'], 'req-one')
        self.assertEqual(first['investigationState'], 'PLANNING')
        self.assertEqual(operate('status', self.workspace)['currentGoal'], request()['question'])
        objects = {p.name for p in (self.workspace/'repository/.objects').glob('*')}
        self.assertTrue(self.begin()['resumed'])
        second = self.begin(request('req-two', 'Explain verify_jwt'))
        self.assertEqual(first['repositorySnapshotRef'], second['repositorySnapshotRef'])
        self.assertEqual(objects, {p.name for p in (self.workspace/'repository/.objects').glob('*')})
        self.assertEqual(operate('status', self.workspace, request_id='req-one')['currentGoal'], request()['question'])
        for state in (self.workspace/'investigations').glob('*/state.json'):
            self.assertLess(state.stat().st_size, 20000)
            self.assertNotIn('scan', read_json(state))

    def test_conflicting_request_does_not_replace_prior_question(self):
        self.begin()
        before = (self.workspace/'investigations/req-one/state.json').read_bytes()
        with self.assertRaises(MoleError) as caught:
            self.begin(request(question='Different question'))
        self.assertEqual(caught.exception.code, 'REQUEST_CONFLICT')
        self.assertEqual(before, (self.workspace/'investigations/req-one/state.json').read_bytes())

    def test_status_is_read_only_and_source_changes_are_stale(self):
        self.begin()
        before = (self.workspace/'investigations/req-one/state.json').read_bytes()
        operate('status', self.workspace)
        self.assertEqual(before, (self.workspace/'investigations/req-one/state.json').read_bytes())
        (self.repo/'app.py').write_text('def verify_jwt(token): return False\n')
        self.assertEqual(operate('status', self.workspace)['engineState'], 'STALE')
        with self.assertRaises(MoleError) as caught:
            operate('next', self.workspace)
        self.assertEqual(caught.exception.code, 'TASK_STALE')
        self.assertEqual(operate('update', self.workspace)['engineState'], 'READY')

    def test_existing_v1_and_target_inside_workspace_are_not_modified(self):
        from molekit.pipeline import start
        start(self.repo, self.workspace, 'standard', 'repository')
        before = (self.workspace/'state.json').read_bytes()
        with self.assertRaises(MoleError):
            self.begin()
        self.assertEqual(before, (self.workspace/'state.json').read_bytes())
        self.input.write_text(json.dumps(request()))
        with self.assertRaises(MoleError):
            begin(self.repo, self.repo/'unsafe', self.input)
        self.assertFalse((self.repo/'unsafe').exists())

    def test_symlink_request_directory_cannot_escape_workspace(self):
        self.begin()
        outside = self.root/'outside'
        outside.mkdir()
        (self.workspace/'investigations/req-two').symlink_to(outside, target_is_directory=True)
        with self.assertRaises(MoleError):
            self.begin(request('req-two'))
        self.assertEqual(list(outside.iterdir()), [])

    def test_interrupted_session_write_can_retry_without_losing_existing_session(self):
        self.begin()
        from molekit.workspace import atomic_json
        def fail_session(path, value):
            if Path(path).name == 'state.json' and Path(path).parent.name == 'req-two':
                raise OSError('injected disk failure')
            return atomic_json(path, value)
        with patch('molekit.investigations.atomic_json', side_effect=fail_session):
            with self.assertRaises(OSError):
                self.begin(request('req-two'))
        self.assertEqual(operate('status', self.workspace)['requestId'], 'req-one')
        self.assertEqual(self.begin(request('req-two'))['requestId'], 'req-two')

    def test_revision_bound_submit_and_duplicate_work_across_restart(self):
        self.begin()
        task = operate('next', self.workspace)['task']
        page = operate('inspect', self.workspace, task=task['id'], budget_chars=12000)
        self.assertTrue(page['context'])
        response = self.root/'patch.json'
        response.write_text(json.dumps({'protocolVersion':'1.0','taskId':task['id'],
            'baseRevision':task['baseRevision'],'claims':[{'id':'claim-jwt','statement':'verify_jwt is declared.',
            'status':'source_observed','evidenceIds':task['evidenceIds'],'limitations':[]}]}))
        result = operate('submit', self.workspace, input=response)
        self.assertNotEqual(result['investigationState'], 'READY_TO_PRESENT')
        self.assertTrue(operate('submit', self.workspace, input=response)['duplicate'])
        self.assertIsNone(operate('next', self.workspace)['task'])

    def test_bounded_json_rejects_duplicate_keys_truncation_and_oversize(self):
        for content in ('{"requestVersion":"2.0",', '{"question":"x","question":"y"}', ' '*300000):
            self.input.write_text(content)
            with self.subTest(content=content[:20]), self.assertRaises(MoleError):
                begin(self.repo, self.workspace, self.input)
            self.assertFalse(self.workspace.exists())

    def test_other_request_task_is_not_authorized(self):
        self.begin()
        first = operate('next', self.workspace)['task']
        self.begin(request('req-two'))
        with self.assertRaises(MoleError) as caught:
            operate('inspect', self.workspace, task=first['id'], budget_chars=12000)
        self.assertEqual(caught.exception.code, 'TASK_UNKNOWN')

    def test_legacy_start_cannot_shadow_an_existing_v2_workspace(self):
        from molekit.pipeline import start
        self.begin()
        pointer = (self.workspace/'.mole-v2.json').read_bytes()
        session = (self.workspace/'investigations/req-one/state.json').read_bytes()
        with self.assertRaises(MoleError) as caught:
            start(self.repo, self.workspace, 'standard', 'repository')
        self.assertEqual(caught.exception.code, 'WORKSPACE_CONFLICT')
        self.assertFalse((self.workspace/'state.json').exists())
        self.assertEqual(pointer, (self.workspace/'.mole-v2.json').read_bytes())
        self.assertEqual(session, (self.workspace/'investigations/req-one/state.json').read_bytes())
        self.assertTrue(self.begin()['resumed'])

    def test_cli_begin_status_and_new_protocol_are_isolated(self):
        import subprocess
        self.input.write_text(json.dumps(request()))
        entry = Path(__file__).resolve().parents[1]/'skills/mole/scripts/mole.py'
        first = subprocess.run([sys.executable,'-I','-S','-B',str(entry),'begin','--repo',str(self.repo),
            '--workspace',str(self.workspace),'--request',str(self.input),'--json'],capture_output=True,text=True)
        self.assertEqual(first.returncode,0,first.stdout+first.stderr)
        self.assertEqual(json.loads(first.stdout)['protocolVersion'],'2.0')
        from molekit.model import validate_schema
        schemas = Path(__file__).resolve().parents[1]/'skills/mole/schemas'
        validate_schema(json.loads(first.stdout), json.loads((schemas/'cli-envelope.v2.schema.json').read_text()))
        second = subprocess.run([sys.executable,'-I','-S','-B',str(entry),'status','--workspace',str(self.workspace),
            '--request-id','req-one','--json'],capture_output=True,text=True)
        self.assertEqual(second.returncode,0,second.stdout+second.stderr)
        self.assertEqual(json.loads(second.stdout)['currentGoal'],request()['question'])
        self.assertEqual(sorted(path.name for path in self.repo.iterdir()),['app.py'])

    def test_large_question_and_source_remain_pageable_within_total_reply_budget(self):
        (self.repo/'app.py').write_text('def verify_jwt(token):\n'+'    value = bool(token)\n'*1000+'    return value\n')
        self.begin(request(question='Explain verify_jwt. '+'context '*900))
        task = operate('next', self.workspace)['task']
        cursor, pages, lines = '0:0', 0, 0
        while cursor:
            page = operate('inspect', self.workspace, task=task['id'], budget_chars=16000, cursor=cursor)
            self.assertLessEqual(len(json.dumps(page,ensure_ascii=True))+16,16000)
            cursor = page['nextCursor']
            pages += 1
            lines += len(page['context'])
            self.assertLess(pages,100)
        self.assertGreater(pages,1)
        self.assertGreaterEqual(lines,1002)

    def test_unicode_goal_preview_cannot_make_inspection_impossible(self):
        value = request(question='Explain verify_jwt '+ '\U0001f4a1'*7000)
        self.begin(value)
        task = operate('next', self.workspace)['task']
        page = operate('inspect', self.workspace, task=task['id'], budget_chars=32000)
        self.assertTrue(page['goalTruncated'])
        self.assertTrue(page['context'])
        self.assertLessEqual(len(json.dumps(page,ensure_ascii=True))+16,32000)
        stored = read_json(self.workspace/'investigations/req-one/state.json')
        self.assertEqual(stored['request']['question'],value['question'])

    def test_next_query_adds_a_bound_probe_without_changing_original_goal(self):
        (self.repo/'app.py').write_text('def verify_jwt(token): return bool(token)\ndef rollback(): return None\n')
        self.begin()
        first=operate('next',self.workspace)['task']
        query=self.root/'query.json'
        query.write_text(json.dumps({'focusSymbols':['rollback'],'text':'rollback','direction':'none'}))
        second=operate('next',self.workspace,query=query)
        self.assertNotEqual(first['id'],second['task']['id'])
        self.assertEqual(second['currentGoal'],request()['question'])
        self.assertTrue(any('rollback' in reason for item in second['search']['matchReasons'] for reason in item['reasons']))
        before=read_json(self.workspace/'investigations/req-one/state.json')
        operate('next',self.workspace,query=query)
        after=read_json(self.workspace/'investigations/req-one/state.json')
        self.assertEqual(len(before['tasks']),len(after['tasks']))
        self.assertEqual(before['requestHash'],after['requestHash'])

    def test_new_probes_cannot_extend_admitted_round_limit(self):
        value=request()
        value['limits']['maxProbeRounds']=1
        self.begin(value)
        query=self.root/'query.json'
        query.write_text(json.dumps({'text':'another query','focusSymbols':[]}))
        with self.assertRaises(MoleError) as caught:
            operate('next',self.workspace,query=query)
        self.assertEqual(caught.exception.code,'PROBE_LIMIT')


if __name__ == '__main__':
    unittest.main()
