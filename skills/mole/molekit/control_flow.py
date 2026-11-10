"""Bounded, source-only control flow. Edges are candidates, never runtime traces."""
import ast
from collections import defaultdict


class ControlFlow:
    def __init__(self, extractor):
        self.extractor = extractor
        self.edges = []
        self.limitations = set()
        self.owner = ''

    def link(self, incoming, target):
        for source, kind, condition in dict.fromkeys(incoming):
            if len(self.edges) >= 20000:
                self.limitations.add("control_flow_edge_budget")
                break
            self.edges.append({'owner': self.owner, 'source': source, 'target': target,
                               'kind': kind, 'condition': condition})
        return [(target, 'lexical_next_candidate', 'Static evaluation order; runtime reachability unverified')]

    def ref(self, node):
        return self.extractor.node_refs.get(id(node))

    def tagged(self, incoming, kind, condition):
        return [(source, kind, condition) for source, _, _ in incoming]

    def expression(self, node, incoming):
        if node is None:
            return incoming
        if isinstance(node, (ast.Lambda, ast.GeneratorExp)):
            # Lazy bodies are not executed when the expression is created.
            self.limitations.add('control_flow_lazy_expression')
            return incoming
        if isinstance(node, ast.BoolOp):
            exits = []
            for value in node.values:
                incoming = self.expression(value, incoming)
                exits.extend(incoming)
                incoming = self.tagged(incoming, 'short_circuit_candidate', 'Only if another operand must be evaluated')
            return exits
        if isinstance(node, ast.IfExp):
            decision = self.expression(node.test, incoming)
            return (self.expression(node.body, self.tagged(decision, 'branch_true_candidate', 'Conditional expression true')) +
                    self.expression(node.orelse, self.tagged(decision, 'branch_false_candidate', 'Conditional expression false')))
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp)):
            self.limitations.add('control_flow_comprehension')
            # Do not flatten conditional/repeated evaluation into a sequence.
            return incoming
        if isinstance(node, ast.Call):
            incoming = self.expression(node.func, incoming)
            # Positional/starred arguments precede keyword/** argument evaluation.
            for value in [*node.args, *[kw.value for kw in node.keywords]]:
                incoming = self.expression(value, incoming)
            return self.link(incoming, self.ref(node)) if self.ref(node) else incoming
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                incoming = self.expression(key, incoming)
                incoming = self.expression(value, incoming)
            return incoming
        if isinstance(node, ast.Compare) and len(node.comparators) > 1:
            self.limitations.add('control_flow_chained_comparison')
            # Later operands are conditional; expose alternatives instead of a
            # strict all-operands sequence.
            incoming = self.expression(node.left, incoming)
            exits = []
            for value in node.comparators:
                incoming = self.expression(value, incoming)
                exits.extend(incoming)
                incoming = self.tagged(incoming, 'short_circuit_candidate', 'Only if preceding comparisons succeed')
            return exits
        for child in ast.iter_child_nodes(node):
            incoming = self.expression(child, incoming)
        return incoming

    def block(self, statements, incoming):
        abrupt = defaultdict(list)
        for statement in statements:
            if not incoming:
                break
            incoming, exits = self.statement(statement, list(dict.fromkeys(incoming)))
            for kind, values in exits.items():
                abrupt[kind].extend(values)
        return incoming, abrupt

    def statement(self, node, incoming):
        abrupt = defaultdict(list)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return incoming, abrupt
        if isinstance(node, ast.If):
            decision = self.link(self.expression(node.test, incoming), self.ref(node))
            yes, yes_exits = self.block(node.body, self.tagged(decision, 'branch_true_candidate', 'Condition true'))
            no, no_exits = self.block(node.orelse, self.tagged(decision, 'branch_false_candidate', 'Condition false'))
            for kind in set(yes_exits) | set(no_exits):
                abrupt[kind] = yes_exits[kind] + no_exits[kind]
            return yes + no, abrupt
        if isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
            expression = node.test if isinstance(node, ast.While) else node.iter
            edge_start = len(self.edges)
            evaluated = self.expression(expression, incoming)
            root = self.ref(node)
            decision = self.link(evaluated, root)
            body, exits = self.block(node.body, self.tagged(decision, 'loop_iteration_candidate', 'Loop iteration'))
            # While conditions may call functions and must be re-evaluated.
            test_entry = self.edges[edge_start]['target'] if len(self.edges) > edge_start else root
            back = test_entry if isinstance(node, ast.While) else root
            self.link(self.tagged(body + exits['continue'], 'loop_back_candidate', 'Next iteration'), back)
            otherwise, else_exits = self.block(node.orelse, self.tagged(decision, 'loop_exit_candidate', 'Loop exhausted / condition false; no break'))
            for kind in ('return', 'raise'):
                abrupt[kind] = exits[kind] + else_exits[kind]
            for kind in ('break', 'continue'):
                abrupt[kind] = else_exits[kind]
            return otherwise + self.tagged(exits['break'], 'loop_break_candidate', 'Break skips loop else'), abrupt
        if isinstance(node, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
            if isinstance(node, ast.Return):
                incoming = self.expression(node.value, incoming)
            elif isinstance(node, ast.Raise):
                incoming = self.expression(node.exc, incoming)
                incoming = self.expression(node.cause, incoming)
            end = self.link(incoming, self.ref(node))
            abrupt[type(node).__name__.lower()] = end
            return [], abrupt
        if isinstance(node, (ast.Try, getattr(ast, 'TryStar', ast.Try))):
            decision = self.link(incoming, self.ref(node))
            start = len(self.edges)
            normal, exits = self.block(node.body, decision)
            body_refs = {edge['target'] for edge in self.edges[start:]}
            normal, else_exits = self.block(node.orelse, normal)
            for kind, values in else_exits.items():
                abrupt[kind].extend(values)
            for kind in ('return', 'break', 'continue'):
                abrupt[kind].extend(exits[kind])
            # Exceptions may escape even when a handler exists. Handler edges
            # explicitly say matching/raising are not established.
            abrupt['raise'].extend(exits['raise'])
            for handler in node.handlers:
                handler_entry = self.tagged(decision + [(ref, '', '') for ref in sorted(body_refs)],
                    'exception_path_candidate', 'Possible matching exception; raised type/dispatch unverified')
                handled, handler_exits = self.block(handler.body, handler_entry)
                normal += handled
                for kind, values in handler_exits.items():
                    abrupt[kind].extend(values)
            if node.finalbody:
                # A shared finally body cannot encode pending completion state.
                # Keep normal and abrupt execution distinct through guarded
                # outgoing edges and expose that abstraction as a limitation.
                pending = [value for values in abrupt.values() for value in values]
                final, final_exits = self.block(node.finalbody, self.tagged(normal + pending, 'finally_candidate', 'Finally executes before normal or pending abrupt completion'))
                if pending:
                    self.limitations.add('control_flow_finally_pending_completion')
                for kind in list(abrupt):
                    abrupt[kind] = self.tagged(final, 'finally_pending_' + kind + '_candidate', 'Resume pending ' + kind + ' only') if abrupt[kind] else []
                for kind, values in final_exits.items():
                    abrupt[kind].extend(values)
                normal = self.tagged(final, 'finally_normal_completion_candidate', 'Only after normal completion; pending return/raise/break/continue resumes otherwise') if normal else []
            return normal, abrupt
        if isinstance(node, (ast.With, ast.AsyncWith)):
            self.limitations.add('control_flow_context_manager_exit')
            for item in node.items:
                incoming = self.expression(item.context_expr, incoming)
            return self.block(node.body, incoming)
        if isinstance(node, ast.Match):
            self.limitations.add('control_flow_match')
            decision = self.expression(node.subject, incoming)
            exits = list(decision)  # No case may match.
            for case in node.cases:
                branch = self.expression(case.guard, self.tagged(decision, 'branch_candidate', 'Pattern/guard may match'))
                normal, pending = self.block(case.body, branch)
                exits.extend(normal)
                for kind, values in pending.items():
                    abrupt[kind].extend(values)
            return exits, abrupt
        if isinstance(node, ast.Assert):
            self.limitations.add('control_flow_assert')
            return self.expression(node.test, incoming), abrupt
        # Ordinary statements evaluate their expression children. Assignment
        # RHS precedes subscript/attribute target evaluation.
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            if isinstance(node, ast.AugAssign):
                self.limitations.add('control_flow_augmented_assignment')
            incoming = self.expression(node.value, incoming)
            for target in getattr(node, 'targets', [getattr(node, 'target', None)]):
                incoming = self.expression(target, incoming)
            return incoming, abrupt
        return self.expression(node, incoming), abrupt

    def build(self, tree):
        def declarations(node, owner=''):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    qualified = (owner + '.' if owner else '') + child.name
                    self.owner = qualified
                    self.block(child.body, [('entry:' + qualified, 'contains', 'Callable source entry; invocation unverified')])
                    declarations(child, qualified)
                else:
                    declarations(child, owner)
        declarations(tree)
        return self.edges, sorted(self.limitations)
