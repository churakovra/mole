"""AST facts with lexical ownership, bindings and conditional source regions."""

import ast


def name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = name(node.value)
        return (parent + "." if parent else "") + node.attr
    if isinstance(node, ast.Call):
        return name(node.func) + "()"
    if isinstance(node, ast.Subscript):
        return name(node.value)
    return "<dynamic>"


class Extractor(ast.NodeVisitor):
    def __init__(self, sanitize=lambda value: value):
        self.sanitize = sanitize
        self.owner = []
        self.context = []
        self.region_counts = {}
        self.node_refs = {}
        self.symbols, self.calls, self.branches, self.imports, self.bindings = [], [], [], [], []

    def visit_Import(self, node):
        for alias in node.names:
            self.imports.append({"module": alias.name if alias.asname else alias.name.split(".")[0],
                                 "alias": alias.asname or alias.name.split(".")[0],
                                 "level": 0, "owner": ".".join(self.owner), "line": node.lineno})

    def visit_ImportFrom(self, node):
        for alias in node.names:
            self.imports.append({"module": (node.module + "." if node.module else "") + alias.name,
                                 "alias": alias.asname or alias.name, "level": node.level,
                                 "owner": ".".join(self.owner), "line": node.lineno})

    def bind(self, target, value, node):
        self.bindings.append({"owner": ".".join(self.owner), "name": target, "type": value,
                              "line": node.lineno})

    def symbol(self, node, kind):
        decorators = [name(d.func if isinstance(d, ast.Call) else d) for d in node.decorator_list]
        # Decorators/default expressions execute in the enclosing declaration
        # context, not inside each invocation of the decorated callable.
        self.owner.append(node.name)
        local = ".".join(self.owner)
        self.symbols.append({"name": local, "kind": kind, "line": node.lineno,
                             "end": node.end_lineno, "decorators": decorators,
                             "decoratorLine": min([node.lineno, *[d.lineno for d in node.decorator_list]]),
                             "bases": [name(base) for base in getattr(node, "bases", [])]})
        if hasattr(node, "args"):
            args = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
            for argument in args:
                self.bind(argument.arg, name(argument.annotation) if argument.annotation else "<dynamic>", node)
        context, self.context = self.context, []
        for statement in node.body:
            self.visit(statement)
        self.context = context
        self.owner.pop()

    def visit_FunctionDef(self, node):
        self.symbol(node, "function")

    def visit_AsyncFunctionDef(self, node):
        self.symbol(node, "async_function")

    def visit_ClassDef(self, node):
        self.symbol(node, "class")

    def visit_Assign(self, node):
        value = node.value.value if isinstance(node.value, ast.Await) else node.value
        for target in node.targets:
            self.bind(name(target), name(value.func) if isinstance(value, ast.Call) else name(value), node)
        self.generic_visit(node)

    def visit_AnnAssign(self, node):
        self.bind(name(node.target), name(node.annotation), node)
        self.generic_visit(node)

    def visit_With(self, node):
        for item in node.items:
            if item.optional_vars and isinstance(item.context_expr, ast.Call):
                self.bind(name(item.optional_vars), name(item.context_expr.func), node)
        self.generic_visit(node)

    visit_AsyncWith = visit_With

    def visit_Call(self, node):
        target = name(node.func)
        tail = target.split(".")[-1]
        channels = {}
        # Persist only protocol/configuration literals, never arbitrary call
        # arguments. Full source remains behind bounded/redacted inspection.
        if tail in {"declare_queue", "subscribe", "send", "send_and_wait", "AIOKafkaConsumer"}:
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                channels["channel"] = self.sanitize(node.args[0].value[:200])
        for keyword in node.keywords:
            if keyword.arg in {"routing_key", "topic", "queue"} and isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
                channels["channel"] = self.sanitize(keyword.value.value[:200])
        self.node_refs[id(node)] = "call:" + str(len(self.calls))
        self.calls.append({"owner": ".".join(self.owner) if self.owner else "<module>", "target": target,
                           "line": node.lineno, "end": node.end_lineno, "column": node.col_offset,
                           "arguments": [name(arg.func) if isinstance(arg, ast.Call) else name(arg) for arg in node.args],
                           "channels": channels, "context": list(self.context)})
        self.generic_visit(node)

    def region(self, node, label, statements):
        self.context.append(self.sanitize(label))
        for statement in statements:
            self.visit(statement)
        self.context.pop()

    def boundary(self, node, kind, condition=""):
        condition = self.sanitize(condition)
        key = (".".join(self.owner), kind)
        ordinal = self.region_counts.get(key, 0)
        self.region_counts[key] = ordinal + 1
        region_id = kind + ":" + str(ordinal)
        self.node_refs[id(node)] = "branch:" + str(len(self.branches))
        self.branches.append({"regionId": region_id, "owner": ".".join(self.owner), "kind": kind, "line": node.lineno,
                              "end": node.end_lineno, "condition": condition, "context": list(self.context)})
        return region_id

    def visit_If(self, node):
        condition = self.sanitize(ast.unparse(node.test)[:300])
        region_id = self.boundary(node, "If", condition)
        self.visit(node.test)
        self.region(node, region_id + " true: " + condition, node.body)
        self.region(node, region_id + " false: " + condition, node.orelse)

    def visit_Try(self, node):
        region_id = self.boundary(node, "Try")
        self.region(node, region_id + " try", node.body)
        for handler in node.handlers:
            self.region(node, region_id + " except " + (name(handler.type) if handler.type else "BaseException"), handler.body)
        self.region(node, region_id + " else", node.orelse)
        self.region(node, region_id + " finally", node.finalbody)

    visit_TryStar = visit_Try

    def visit_For(self, node):
        self.bind(name(node.target), (name(node.iter.func) if isinstance(node.iter, ast.Call) else name(node.iter)) + ".item", node)
        self.boundary(node, "Loop", ast.unparse(node.iter)[:300])
        self.visit(node.iter)
        self.region(node, "loop [iteration]", node.body)
        self.region(node, "loop [else]", node.orelse)

    visit_AsyncFor = visit_For

    def visit_While(self, node):
        self.boundary(node, "Loop", ast.unparse(node.test)[:300])
        self.visit(node.test)
        self.region(node, "loop [iteration]", node.body)
        self.region(node, "loop [else]", node.orelse)

    def generic_visit(self, node):
        if self.owner and isinstance(node, (ast.Raise, ast.Return, ast.Await, ast.Break, ast.Continue)):
            condition = name(node.exc) if isinstance(node, ast.Raise) and node.exc else ""
            self.boundary(node, type(node).__name__, condition)
        super().generic_visit(node)
