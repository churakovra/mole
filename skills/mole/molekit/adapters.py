"""Detected-framework candidates, never inferred delivery guarantees."""

from collections import deque

from molekit.model import validate_model
from molekit.scanner import identity


def enrich(result):
    model = result["model"]
    sources = {s["id"]: s for s in model["sources"]}
    source_evidence = {}
    for ev in model["evidence"]:
        span = sources[ev["sourceId"]]
        source_evidence.setdefault((span["path"], span["lineStart"]), []).append(ev["id"])
    symbol_map = {s["qualifiedName"]: s for s in model["symbols"]}
    detected = set()
    events = []
    for path, entry in result["facts"].items():
        facts = entry["facts"]
        modules = {i["module"].split(".")[0] for i in facts["imports"]}
        active = modules & {"fastapi", "starlette", "django", "sqlalchemy", "asyncio", "aio_pika", "aiokafka"}
        detected.update(active)
        prefix = path.removesuffix(".py").replace("/", ".") + "."

        def event(kind, title, owner, line, suffix):
            evidence = source_evidence.get((path, line), [])
            symbol = symbol_map.get(prefix + owner)
            if not evidence and symbol:
                evidence = [ev["id"] for ev in model["evidence"] if ev["sourceId"] in symbol["sourceRefs"]]
            if not evidence:
                return
            oid = identity("event", path + ":" + str(line) + ":" + suffix)
            if any(op["id"] == oid for op in model["operations"]):
                return
            model["operations"].append({"id": oid, "kind": kind, "title": title, "evidenceIds": evidence})
            if symbol:
                model["relationships"].append({"id": identity("edge", symbol["id"] + oid),
                    "source": symbol["id"], "target": oid, "kind": kind, "resolution": "possible",
                    "evidenceIds": evidence, "condition": "Detected pattern; execution and ordering unproven"})
            events.append({"operationId": oid, "ownerId": symbol["id"] if symbol else None,
                           "kind": kind, "path": path, "line": line})

        for symbol in facts["symbols"]:
            for decorator in symbol["decorators"]:
                tail = decorator.split(".")[-1]
                if active & {"fastapi", "starlette"} and tail in {"get", "post", "put", "delete", "patch", "websocket", "route", "middleware", "on_event"}:
                    event("http_entry", decorator + " decorator on " + symbol["name"], symbol["name"], symbol["line"], decorator)
            if symbol["kind"] == "async_function":
                event("async_function", "Async declaration " + symbol["name"], symbol["name"], symbol["line"], "async")
        for call in facts["calls"]:
            target = call["target"]
            tail = target.split(".")[-1]
            kind = None
            if active & {"sqlalchemy", "django"}:
                if tail in {"commit", "rollback", "begin", "atomic", "begin_nested"}:
                    kind = "transaction_boundary"
                elif tail in {"add", "add_all", "save", "create", "update", "delete", "bulk_create"}:
                    kind = "db_write"
                elif tail in {"query", "select", "execute", "filter", "all", "get", "first"}:
                    kind = "db_read"
            if active & {"aio_pika", "aiokafka"}:
                if tail in {"publish", "send", "send_and_wait"}:
                    kind = "publish"
                elif tail in {"consume", "iterator", "getone", "getmany"}:
                    kind = "consume"
                elif tail in {"ack", "nack", "reject"}:
                    kind = "acknowledgement"
            if "asyncio" in active and tail in {"create_task", "gather", "wait_for", "timeout", "cancel", "sleep"}:
                kind = "async_boundary"
            if "fastapi" in active and tail in {"Depends", "add_task"}:
                kind = "dependency" if tail == "Depends" else "background_task"
            if "django" in active and tail in {"path", "re_path"}:
                kind = "http_route_candidate"
            if kind:
                event(kind, target + " candidate", call["owner"], call["line"], target + str(call["column"]))
        # Branches retained by the scanner locate failure/recovery boundaries.
        for branch in facts["branches"]:
            if branch["kind"] in {"Try", "Raise", "Await", "If", "AsyncWith"}:
                event("control_" + branch["kind"].lower(), branch["kind"] + " boundary",
                      branch["owner"], branch["line"], branch["kind"])
    result["adapters"] = sorted(detected)
    result["events"] = events
    validate_model(model)
    return result


def trace(model, origin, direction="forward", max_depth=8, max_nodes=200):
    """Bounded graph traversal reports boundaries rather than claiming full paths."""
    seen, edges, boundaries = set(), set(), []
    queue = deque([(origin, 0)])
    while queue:
        node, depth = queue.popleft()
        if node in seen:
            continue
        if len(seen) >= max_nodes or depth >= max_depth:
            boundaries.append({"nodeId": node, "reason": "trace_budget"})
            continue
        seen.add(node)
        adjacent = [e for e in model["relationships"]
                    if e["source" if direction == "forward" else "target"] == node]
        if not adjacent:
            boundaries.append({"nodeId": node, "reason": "static_evidence_boundary"})
        for edge in adjacent:
            edges.add(edge["id"])
            queue.append((edge["target" if direction == "forward" else "source"], depth + 1))
    return {"nodeIds": sorted(seen), "edgeIds": sorted(edges), "boundaries": boundaries,
            "limitations": ["Static candidates only; runtime ordering and delivery guarantees are unproven."]}
