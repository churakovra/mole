"""Static operation graph and bounded, entrypoint-centred workflow candidates."""

from collections import defaultdict, deque
from pathlib import PurePosixPath

from molekit.scanner import identity, redact


def module_name(path):
    parts = list(PurePosixPath(path).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


class Resolver:
    def __init__(self, facts, symbols, operations):
        self.facts = facts
        self.modules = defaultdict(list)
        self.defined = {}
        self.local = {}
        self.aliases = defaultdict(dict)
        self.alias_lines = defaultdict(dict)
        self.symbol_lines = {}
        self.bindings = defaultdict(lambda: defaultdict(set))
        self.classes = defaultdict(set)
        for path, entry in facts.items():
            module = module_name(path)
            self.modules[module].append(path)
            package = module if path.endswith("/__init__.py") else module.rpartition(".")[0]
            for imported in entry["facts"]["imports"]:
                target = imported["module"]
                level = imported.get("level", 0)
                if level:
                    pieces = package.split(".") if package else []
                    prefix = ".".join(pieces[:len(pieces) - level + 1])
                    target = prefix + ("." if prefix else "") + target
                self.aliases[(path, imported.get("owner", ""))][imported["alias"]] = target
                self.alias_lines[(path, imported.get("owner", ""))][imported["alias"]] = imported["line"]
            for binding in entry["facts"].get("bindings", []):
                self.bindings[(path, binding["owner"])][binding["name"]].add(binding["type"])
            for symbol in entry["facts"]["symbols"]:
                sid = symbols[(path, symbol["name"])]
                op = operations[sid]
                self.local[(path, symbol["name"])] = op
                self.symbol_lines[(path, symbol["name"])] = symbol["line"]
                self.defined[module + ("." if module else "") + symbol["name"]] = op
                if symbol["kind"] == "class":
                    self.classes[path].add(symbol["name"])

    def scopes(self, owner):
        parts = owner.split(".") if owner and owner != "<module>" else []
        return [".".join(parts[:index]) for index in range(len(parts), -1, -1)]

    def canonical(self, target, path, owner, depth=0):
        if depth > 8:
            return "<dynamic>"
        target = target.replace("()", "")
        pieces = target.split(".")
        scopes = self.scopes(owner)
        for cls in self.classes[path]:
            if owner.startswith(cls + "."):
                scopes.append(cls + ".__init__")
        for scope in scopes:
            for length in range(len(pieces), 0, -1):
                receiver = ".".join(pieces[:length])
                if receiver in {"self", "cls"}:
                    continue
                values = self.bindings[(path, scope)].get(receiver, set())
                if len(values) > 1:
                    return "<dynamic>"
                if values:
                    value = next(iter(values))
                    if value == receiver:
                        continue
                    resolved = self.canonical(value, path, scope, depth + 1)
                    if (path, value) in self.local:
                        resolved = module_name(path) + "." + value
                    return resolved + ("." + ".".join(pieces[length:]) if length < len(pieces) else "")
            local_name = (scope + "." if scope else "") + pieces[0]
            if ((path, local_name) in self.local and self.symbol_lines[(path, local_name)] >=
                    self.alias_lines[(path, scope)].get(pieces[0], -1)):
                return module_name(path) + "." + local_name + ("." + ".".join(pieces[1:]) if len(pieces) > 1 else "")
            alias = self.aliases[(path, scope)].get(pieces[0])
            if alias:
                return alias + ("." + ".".join(pieces[1:]) if len(pieces) > 1 else "")
        if pieces[0] in {"self", "cls"}:
            candidates = [name for name in self.classes[path] if owner.startswith(name + ".")]
            if candidates:
                owner_class = max(candidates, key=len)
                return module_name(path) + "." + owner_class + ("." + ".".join(pieces[1:]) if len(pieces) > 1 else "")
        return target

    def find(self, target, path, owner, visited=None):
        visited = set() if visited is None else visited
        key = (path, owner, target)
        if key in visited or len(visited) > 20:
            return None
        visited.add(key)
        canonical = self.canonical(target, path, owner)
        if canonical == "<dynamic>" or canonical.startswith("<dynamic>."):
            return None
        if canonical in self.defined:
            return self.defined[canonical]
        for scope in self.scopes(owner):
            local = scope + "." + target if scope else target
            if (path, local) in self.local:
                return self.local[(path, local)]
        for module, paths in self.modules.items():
            if len(paths) != 1 or not canonical.startswith(module + "."):
                continue
            exported = canonical[len(module) + 1:]
            alias = self.aliases[(paths[0], "")].get(exported.split(".")[0])
            if alias:
                suffix = exported.partition(".")[2]
                return self.find(alias + ("." + suffix if suffix else ""), paths[0], "", visited)
        return None


def connect(model, facts, symbols, records, evidence):
    by_name = {op["title"]: op["id"] for op in model["operations"]}
    symbol_ops = {symbol["id"]: by_name[symbol["qualifiedName"]] for symbol in model["symbols"]}
    resolver = Resolver(facts, symbols, symbol_ops)
    record_map = {record["path"]: record for record in records}
    call_sites, boundaries, unresolved = [], [], []
    occurrences = defaultdict(int)
    owner_items = defaultdict(list)
    control_roots = {}
    builtins = {"str", "int", "float", "bool", "dict", "set", "list", "tuple", "len", "range", "print", "isinstance", "super", "Exception", "ValueError", "RuntimeError"}

    def relation(source, target, kind, evs, condition):
        model["relationships"].append({"id": identity("edge", source + ":" + target + ":" + kind),
            "source": source, "target": target, "kind": kind, "resolution": "possible",
            "evidenceIds": list(dict.fromkeys(evs)), "condition": condition})

    for path, entry in facts.items():
        for call in entry["facts"]["calls"]:
            owner = resolver.local.get((path, call["owner"]))
            canonical = resolver.canonical(call["target"], path, call["owner"])
            context = [redact(value) for value in call.get("context", [])]
            occurrence_key = (path, call["owner"], call["target"], tuple(context))
            ordinal = occurrences[occurrence_key]
            occurrences[occurrence_key] += 1
            token = (owner or path) + ":" + call["target"] + ":" + str(context) + ":" + str(ordinal)
            op_id = identity("call", token)
            _, ev = evidence(record_map[path], call["line"], call["end"], "Call candidate " + call["owner"] + ": " + call["target"] + " #" + str(ordinal))
            operation = {"id": op_id, "kind": "call_candidate", "title": canonical,
                         "evidenceIds": [ev], "sourceOrder": call["line"] * 4096 + call["column"],
                         "control": context, "sourcePattern": "AST call site"}
            if owner:
                operation["ownerId"] = owner
                owner_items[owner].append(operation)
            model["operations"].append(operation)
            target = resolver.find(call["target"], path, call["owner"])
            if target:
                relation(op_id, target, "calls", [ev], "Statically resolved name; invocation and dispatch unverified")
            elif owner and call["target"].split(".")[0] not in builtins:
                kind = "external_dependency" if canonical.split(".")[0] in {"sqlalchemy", "django", "fastapi", "asyncio", "aio_pika", "aiokafka"} else "unresolved_dispatch"
                unresolved.append({"evidenceId": ev, "target": canonical, "owner": owner,
                                   "operationId": op_id, "kind": kind})
            call_sites.append({**call, "path": path, "operationId": op_id, "ownerOperationId": owner,
                               "canonicalTarget": canonical, "evidenceId": ev, "resolvedTarget": target})
        for branch in entry["facts"]["branches"]:
            owner = resolver.local.get((path, branch["owner"]))
            if not owner or branch["kind"] == "Await":
                continue
            context = [redact(value) for value in branch.get("context", [])]
            label = redact(branch.get("condition", ""))
            key = (owner, branch["kind"], label, tuple(context))
            ordinal = occurrences[key]
            occurrences[key] += 1
            op_id = identity("control", str(key) + str(ordinal))
            _, ev = evidence(record_map[path], branch["line"], branch["end"], branch["owner"] + ": " + branch["kind"] + " " + label + " #" + str(ordinal))
            op = {"id": op_id, "kind": "control_" + branch["kind"].lower(), "title": branch["kind"] + (": " + label if label else ""),
                  "evidenceIds": [ev], "sourceOrder": branch["line"] * 4096 + (4095 if branch["kind"] in {"Return", "Raise"} else -1),
                  "control": context, "ownerId": owner, "sourcePattern": "AST control region"}
            model["operations"].append(op)
            owner_items[owner].append(op)
            control_roots[(owner, branch.get("regionId", ""))] = op_id
            boundaries.append({**branch, "operationId": op_id, "ownerOperationId": owner, "evidenceId": ev, "path": path})
    # Lexical control regions distinguish alternatives: no unconditional
    # happy-path edge is invented from try's final statement to its handler.
    for owner, operations in owner_items.items():
        regions = defaultdict(list)
        for op in sorted(operations, key=lambda op: (op["sourceOrder"], op["id"])):
            regions[tuple(op["control"])].append(op)
        for context, sequence in regions.items():
            previous = control_roots.get((owner, context[-1].split(" ", 1)[0]), owner) if context else owner
            for index, op in enumerate(sequence):
                kind = "lexical_next_candidate" if index else "branch_candidate" if context else "contains"
                if context and any(" except " in value for value in context):
                    kind = "exception_path_candidate" if index == 0 else kind
                if context and " true:" in context[-1] and index == 0:
                    kind = "branch_true_candidate"
                if context and " false:" in context[-1] and index == 0:
                    kind = "branch_false_candidate"
                if context and " finally" in context[-1] and index == 0:
                    kind = "finally_candidate"
                relation(previous, op["id"], kind, op["evidenceIds"], "; ".join(context) or "Source order only; runtime reachability unverified")
                previous = op["id"]
                if op["kind"] in {"control_return", "control_raise"}:
                    break
    return {"symbolOperations": symbol_ops, "callSites": call_sites, "controlBoundaries": boundaries, "unresolved": unresolved}


def adjacency(model):
    result = defaultdict(list)
    for edge in model["relationships"]:
        result[edge["source"]].append(edge)
    return result


def workflows(scan, max_nodes=400):
    model = scan["model"]
    operations = {op["id"]: op for op in model["operations"]}
    graph = adjacency(model)
    declaration_ids = {scan["symbolOperations"][symbol["id"]] for symbol in model["symbols"] if symbol["kind"] != "class"}
    incoming = {edge["target"] for edge in model["relationships"] if edge["kind"] in {"calls", "dispatch_candidate", "invokes_handler_candidate", "schedules_candidate"}}
    entries = sorted(scan.get("entryPoints", []), key=lambda entry: (entry["kind"] != "http", entry["id"]))
    roots = [(entry["id"], "workflow", entry["kind"]) for entry in entries]
    # Disconnected utilities are reviewed as a module/component, not asserted
    # to be independent business workflows just because they are functions.
    grouped = defaultdict(list)
    for oid in declaration_ids:
        if oid not in incoming:
            grouped[operations[oid]["title"].rpartition(".")[0]].append(oid)
    covered, candidates = set(), []
    for origin, kind, trigger in roots + [(sorted(ids)[0], "component", module) for module, ids in sorted(grouped.items()) if ids]:
        if origin in covered:
            continue
        seeds = [origin] if kind == "workflow" else sorted(grouped[trigger])
        queue = deque(seeds)
        seen, edge_ids, limits = set(), set(), []
        while queue:
            node = queue.popleft()
            if node in seen:
                continue
            if len(seen) >= max_nodes:
                limits.append("workflow_node_budget")
                break
            seen.add(node)
            for edge in graph.get(node, []):
                edge_ids.add(edge["id"])
                queue.append(edge["target"])
        covered.update(seen)
        if not seen:
            continue
        evs = sorted({ev for oid in seen for ev in operations[oid]["evidenceIds"]})
        unresolved = [item for item in scan["unresolved"] if item.get("operationId") in seen]
        candidates.append({"id": identity("workflow", origin if kind == "workflow" else "component:" + trigger),
            "kind": kind, "entryOperationId": origin, "title": operations[origin]["title"] if kind == "workflow" else trigger,
            "trigger": trigger, "operationIds": sorted(seen), "evidenceIds": evs,
            "edgeIds": sorted(edge_ids), "boundaries": unresolved,
            "limitations": sorted(set(limits)), "critical": kind == "workflow" or any(
                operations[oid]["kind"] in {"db_write", "publish", "consume", "transaction_boundary"} for oid in seen)})
    remaining = declaration_ids - covered
    if remaining:
        scan.setdefault("limitations", []).append({"path": ".", "reason": "uncovered_declaration_components:" + str(len(remaining))})
    scan["workflows"] = candidates
    return candidates
