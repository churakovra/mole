"""Regressions for the 2026-11-10 combined release audit."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/mole'))
from molekit.scanner import scan
from molekit.adapters import enrich
from molekit.agent import create_tasks
from molekit.quality import assess


class ReleaseAuditTests(unittest.TestCase):
    def analyze(self, source):
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as workspace:
            Path(repo, 'app.py').write_text(source)
            return enrich(scan(repo, workspace))

    def edges(self, result, kind=None):
        ops = {op['id']: op for op in result['model']['operations']}
        return [(ops[e['source']]['title'], ops[e['target']]['title'], e['kind'])
                for e in result['model']['relationships'] if kind is None or e['kind'] == kind]

    def test_method_bare_name_skips_class_but_self_preserves_member(self):
        result = self.analyze('def helper(): return 1\nclass C:\n    def helper(self): return 2\n    def run(self): return helper() + self.helper()\n')
        calls = self.edges(result, 'calls')
        self.assertIn(('app.helper', 'app.helper', 'calls'), calls)
        self.assertIn(('app.C.helper', 'app.C.helper', 'calls'), calls)

    def test_method_nested_function_keeps_enclosing_function_scope(self):
        result = self.analyze('def factory():\n    def helper(): return 1\n    class C:\n        def helper(self): return 2\n        def run(self):\n            def nested(): return helper()\n            return nested()\n    return C\n')
        self.assertTrue(any(target == 'app.factory.helper' for _, target, _ in self.edges(result, 'calls')))

    def test_nested_calls_follow_argument_evaluation(self):
        result = self.analyze('def inner(): return 1\ndef outer(x): return x\ndef main(): return outer(inner())\n')
        edges = self.edges(result)
        self.assertIn(('app.inner', 'app.outer', 'lexical_next_candidate'), edges)
        self.assertNotIn(('app.outer', 'app.inner', 'lexical_next_candidate'), edges)

    def test_branch_joins_before_following_statement(self):
        result = self.analyze('def a(): pass\ndef b(): pass\ndef main(flag):\n    if flag:\n        a()\n    b()\n')
        self.assertTrue(any(a == 'app.a' and b == 'app.b' for a, b, _ in self.edges(result)))

    def test_break_and_continue_stop_unreachable_tail(self):
        for exit_statement in ('break', 'continue'):
            with self.subTest(exit_statement=exit_statement):
                result = self.analyze('def a(): pass\ndef b(): pass\ndef main(items):\n    for item in items:\n        a()\n        ' + exit_statement + '\n        b()\n')
                ops = {op['id']: op for op in result['model']['operations']}
                calls = {call['operationId'] for call in result['callSites'] if call['owner'] == 'main' and call['target'] == 'b'}
                self.assertFalse(any(e['target'] in calls for e in result['model']['relationships']))
                self.assertTrue(any(op['kind'] == 'control_' + exit_statement for op in ops.values()))

    def test_loop_break_bypasses_else_and_connects_following_statement(self):
        result = self.analyze('def a(): pass\ndef b(): pass\ndef main(items):\n    for item in items:\n        break\n    else:\n        a()\n    b()\n')
        edges = self.edges(result)
        self.assertTrue(any(a == 'Break' and b == 'app.b' for a, b, _ in edges))
        self.assertFalse(any(a == 'Break' and b == 'app.a' for a, b, _ in edges))

    def test_workflow_budget_is_reported_to_quality_and_task(self):
        result = self.analyze('from fastapi import FastAPI\napp=FastAPI()\n@app.get("/")\ndef main():\n' + '    print(1)\n' * 450)
        tasks = create_tasks(result, 'standard')
        self.assertIn('workflow_node_budget', [item['reason'] for item in result['limitations']])
        self.assertIn('workflow_node_budget', tasks[0]['limitations'])
        self.assertTrue(tasks[0]['deferredOperationIds'])
        report = assess({'scan': result, 'tasks': tasks})
        self.assertEqual(report['technicalAnalysis'], 'PARTIAL')

    def test_early_return_does_not_join_normal_successor(self):
        result = self.analyze('def a(): pass\ndef b(): pass\ndef main(flag):\n    if flag:\n        return a()\n    b()\n')
        self.assertFalse(any(a == 'Return' and b == 'app.b' for a, b, _ in self.edges(result)))

    def test_while_back_edge_reevaluates_condition(self):
        result = self.analyze('def check(): return True\ndef act(): pass\ndef main():\n    while check():\n        act()\n        continue\n')
        self.assertIn(('Continue', 'app.check', 'loop_back_candidate'), self.edges(result))

    def test_nested_loop_break_exits_only_inner_loop(self):
        result = self.analyze('def act(): pass\ndef done(): pass\ndef main(items):\n    for x in items:\n        for y in items:\n            break\n        act()\n    done()\n')
        edges = self.edges(result)
        self.assertTrue(any(a == 'Break' and b == 'app.act' for a, b, _ in edges))
        self.assertFalse(any(a == 'Break' and b == 'app.done' for a, b, _ in edges))

    def test_try_finally_on_return_never_reaches_following_call(self):
        result = self.analyze('def cleanup(): pass\ndef tail(): pass\ndef main():\n    try:\n        return 1\n    finally:\n        cleanup()\n    tail()\n')
        calls = {call['operationId'] for call in result['callSites'] if call['target'] == 'tail'}
        self.assertFalse(any(edge['target'] in calls for edge in result['model']['relationships']))
        self.assertIn(('Return', 'app.cleanup', 'finally_candidate'), self.edges(result))
        self.assertIn('control_flow_finally_pending_completion', [item['reason'] for item in result['limitations']])

    def test_finally_break_does_not_bypass_cleanup(self):
        result = self.analyze('def cleanup(): pass\ndef tail(): pass\ndef main(items):\n    for item in items:\n        try:\n            break\n        finally:\n            cleanup()\n    tail()\n')
        edges = self.edges(result)
        self.assertIn(('Break', 'app.cleanup', 'finally_candidate'), edges)
        self.assertFalse(any(a == 'Break' and b == 'app.tail' for a, b, _ in edges))
        self.assertTrue(any(a == 'app.cleanup' and b == 'app.tail' for a, b, _ in edges))

    def test_dictionary_evaluates_each_key_before_its_value(self):
        result = self.analyze('def k1(): pass\ndef k2(): pass\ndef v1(): pass\ndef v2(): pass\ndef main(): return {k1(): v1(), k2(): v2()}\n')
        edges = self.edges(result)
        for a, b in [('app.k1', 'app.v1'), ('app.v1', 'app.k2'), ('app.k2', 'app.v2')]:
            self.assertIn((a, b, 'lexical_next_candidate'), edges)

    def test_conditional_expression_does_not_sequence_alternatives(self):
        result = self.analyze('def yes(): pass\ndef no(): pass\ndef main(flag): return yes() if flag else no()\n')
        self.assertFalse(any(a == 'app.yes' and b == 'app.no' for a, b, _ in self.edges(result)))

    def test_deferred_metadata_pages_without_exceeding_reply_budget(self):
        from molekit.agent import inspect
        result = self.analyze('def main(): return 1\n')
        tasks = create_tasks(result, 'standard')
        task = tasks[0]
        task['deferredOperationIds'] = ['op-' + str(i) for i in range(500)]
        state = {'scan': result, 'revision': result['model']['revision']}
        cursor, collected = 'deferred:0', []
        while cursor:
            page = inspect(state, task, 1500, cursor)
            collected.extend(page['deferredOperationIds'])
            cursor = page['nextCursor']
        self.assertEqual(collected, task['deferredOperationIds'])


    def test_inner_loop_else_break_reaches_outer_successor(self):
        result = self.analyze('def tail(): pass\ndef main(xs, ys):\n    for x in xs:\n        for y in ys:\n            pass\n        else:\n            break\n    tail()\n')
        self.assertTrue(any(a == 'Break' and b == 'app.tail' for a, b, _ in self.edges(result)))

    def test_inner_loop_else_continue_reaches_outer_loop(self):
        result = self.analyze('def main(xs, ys):\n    for x in xs:\n        for y in ys:\n            pass\n        else:\n            continue\n')
        self.assertTrue(any(a == 'Continue' and b.startswith('Loop: xs') and kind == 'loop_back_candidate'
                            for a, b, kind in self.edges(result)))
