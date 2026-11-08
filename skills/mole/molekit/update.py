"""Changed-source invalidation and conservative semantic reuse."""

import copy
from pathlib import Path

from molekit.adapters import enrich
from molekit.agent import create_tasks
from molekit.errors import MoleError
from molekit.model import validate_model
from molekit.scanner import identity, inventory, scan
from molekit.workspace import atomic_json


def changes(state, directory):
    if "scan" not in state:
        raise MoleError("INVALID_STATE", "Scan before requesting a diff/update.", 5)
    records, _ = inventory(state["manifest"]["repo"], directory, state["manifest"].get("outputs", []))
    before = {item["path"]: item["hash"] for item in state["scan"]["index"]}
    after = {item["path"]: item["hash"] for item in records}
    added, removed = sorted(after.keys() - before.keys()), sorted(before.keys() - after.keys())
    changed = sorted(path for path in before.keys() & after.keys() if before[path] != after[path])
    renames = {}
    ambiguous = []
    for old in removed:
        candidates = [new for new in added if after[new] == before[old]]
        old_matches = [path for path in removed if before[path] == before[old]]
        if len(candidates) == len(old_matches) == 1:
            renames[old] = candidates[0]
        elif candidates:
            ambiguous.append(old)
    return {"added": added, "removed": removed, "changed": changed,
            "renames": renames, "ambiguousRenames": ambiguous}


def retain_renamed_ids(old_scan, new_scan, renames):
    """Only exact, unique file-content matches retain semantic identities."""
    old_model, model = old_scan["model"], new_scan["model"]
    old_sources = {s["id"]: s for s in old_model["sources"]}
    new_sources = {s["id"]: s for s in model["sources"]}
    old_evidence = {e["id"]: e for e in old_model["evidence"]}
    new_evidence = {e["id"]: e for e in model["evidence"]}
    mapping = {}
    # A prior relocation is now the established identity at its current path.
    # Preserve it on every refresh, not only the update that detects the rename.
    old_symbols = {(s["qualifiedName"], s["kind"]): s for s in old_model["symbols"]}
    for symbol in model["symbols"]:
        prior = old_symbols.get((symbol["qualifiedName"], symbol["kind"]))
        if prior:
            mapping[symbol["id"]] = prior["id"]
    for operation in model["operations"]:
        matches = [op for op in old_model["operations"]
                   if op["kind"] == operation["kind"] and op["title"] == operation["title"]
                   and (operation["kind"] in {"function", "async_function", "class"} or
                       [(old_sources[old_evidence[e]["sourceId"]]["path"], old_sources[old_evidence[e]["sourceId"]]["lineStart"])
                        for e in op["evidenceIds"]] ==
                       [(new_sources[new_evidence[e]["sourceId"]]["path"], new_sources[new_evidence[e]["sourceId"]]["lineStart"])
                        for e in operation["evidenceIds"]])]
        if len(matches) == 1:
            mapping[operation["id"]] = matches[0]["id"]
    for old_path, new_path in renames.items():
        old_prefix = old_path.removesuffix(".py").replace("/", ".") + "."
        new_prefix = new_path.removesuffix(".py").replace("/", ".") + "."
        for symbol in model["symbols"]:
            if symbol["qualifiedName"].startswith(new_prefix):
                old_name = old_prefix + symbol["qualifiedName"][len(new_prefix):]
                previous = next((s for s in old_model["symbols"] if s["qualifiedName"] == old_name), None)
                if previous:
                    mapping[symbol["id"]] = previous["id"]

        def signature(operation, evidence, sources, path, prefix):
            spans = [sources[evidence[e]["sourceId"]] for e in operation["evidenceIds"]]
            if not spans or any(source["path"] != path for source in spans):
                return None
            title = operation["title"]
            if title.startswith(prefix):
                title = "<module>." + title[len(prefix):]
            return operation["kind"], title, tuple(sorted((s["lineStart"], s["lineEnd"]) for s in spans))
        for operation in model["operations"]:
            sig = signature(operation, new_evidence, new_sources, new_path, new_prefix)
            if sig:
                matches = [op for op in old_model["operations"] if signature(op, old_evidence, old_sources, old_path, old_prefix) == sig]
                if len(matches) == 1:
                    mapping[operation["id"]] = matches[0]["id"]
    def allocate(items, preferred):
        """Reserve established IDs before allocating IDs for new declarations.

        Natural name hashes are only initial candidates: a vacated name may
        have been retained by a relocated entity and cannot be assigned twice.
        """
        assigned = set(preferred.values())
        resolved = dict(preferred)
        for item in items:
            original = item["id"]
            if original in resolved:
                continue
            candidate = original
            counter = 0
            while candidate in assigned:
                counter += 1
                candidate = identity(original.split("-", 1)[0], original + model["revision"] + str(counter))
            assigned.add(candidate)
            resolved[original] = candidate
        for item in items:
            item["id"] = resolved[item["id"]]
        return resolved
    mapping = allocate(model["symbols"] + model["operations"], mapping)
    for edge in model["relationships"]:
        edge["source"] = mapping.get(edge["source"], edge["source"])
        edge["target"] = mapping.get(edge["target"], edge["target"])
    inverse = {new: old for old, new in renames.items()}
    def edge_key(edge, evidence, sources, remap):
        spans = [sources[evidence[e]["sourceId"]] for e in edge["evidenceIds"]]
        return (edge["source"], edge["target"], edge["kind"],
                tuple((remap.get(s["path"], s["path"]), s["lineStart"], s["lineEnd"]) for s in spans))
    previous_edges = {}
    for edge in old_model["relationships"]:
        previous_edges.setdefault(edge_key(edge, old_evidence, old_sources, {}), []).append(edge["id"])
    preferred_edges = {}
    for edge in model["relationships"]:
        candidates = previous_edges.get(edge_key(edge, new_evidence, new_sources, inverse), [])
        if candidates:
            preferred_edges[edge["id"]] = candidates.pop(0)
    allocate(model["relationships"], preferred_edges)
    for event in new_scan["events"]:
        event["operationId"] = mapping.get(event["operationId"], event["operationId"])
        event["ownerId"] = mapping.get(event["ownerId"], event["ownerId"])
    # Renamed code is re-reviewed: IDs are retained, claims are not silently
    # rewritten to pretend statements naming the old module remain current.
    validate_model(model)


def refresh(state, directory):
    if state["status"] == "EXPORTING":
        raise MoleError("WORKSPACE_CONFLICT", "Resume the interrupted export before updating.", 5)
    report = changes(state, directory)
    if not any(report[key] for key in ("added", "removed", "changed")):
        return state, {**report, "reusedClaims": len(state["scan"]["model"]["claims"]), "invalidatedClaims": []}
    result = enrich(scan(state["manifest"]["repo"], directory, state["manifest"].get("outputs", [])))
    retain_renamed_ids(state["scan"], result, report["renames"])
    if report["ambiguousRenames"]:
        result["limitations"].append({"path": ".", "reason": "ambiguous_rename_requires_review"})
    tasks = create_tasks(result, state["manifest"]["mode"])
    old_tasks = {task["id"]: task for task in state["tasks"]}
    available = {ev["id"] for ev in result["model"]["evidence"]}
    reused_claims = []
    invalidated = []
    for claim in state["scan"]["model"]["claims"]:
        linked = [task for task, ids in state.get("taskClaims", {}).items() if claim["id"] in ids]
        fresh = set(claim["evidenceIds"]) <= available
        if not claim["evidenceIds"]:
            fresh = bool(linked) and all(any(t["id"] == tid and set(t["evidenceIds"]) == set(old_tasks[tid]["evidenceIds"])
                                             for t in tasks) for tid in linked)
        if fresh:
            reused_claims.append(claim)
        else:
            invalidated.append(claim["id"])
    result["model"]["claims"] = reused_claims
    kept = {c["id"] for c in reused_claims}
    for task in tasks:
        old = old_tasks.get(task["id"])
        claims = state.get("taskClaims", {}).get(task["id"], [])
        if (old and old["status"] == "completed" and claims and set(claims) <= kept
                and set(old["evidenceIds"]) == set(task["evidenceIds"])):
            task["status"] = "completed"
    validate_model(result["model"])
    history = directory / "history"
    if history.is_symlink():
        raise MoleError("UNSAFE_PATH", "History must not be a symlink.")
    history.mkdir(exist_ok=True)
    atomic_json(history / (state["revision"] + ".json"), state["scan"]["model"])
    updated = copy.deepcopy(state)
    updated.update(scan=result, revision=result["model"]["revision"], tasks=tasks, submissions={},
                   taskClaims={tid: [cid for cid in ids if cid in kept] for tid, ids in state.get("taskClaims", {}).items()},
                   status="NEEDS_ANALYSIS" if any(t["status"] == "pending" for t in tasks) else "VALIDATING")
    report.update(reusedClaims=len(reused_claims), invalidatedClaims=invalidated)
    updated["changeReport"] = report
    atomic_json(directory / "state.json", updated)
    return updated, report
