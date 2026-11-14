"""Changed-source invalidation and conservative semantic reuse."""

import copy
from pathlib import Path

from molekit.adapters import enrich
from molekit.agent import create_tasks
from molekit.errors import MoleError
from molekit.model import validate_model
from molekit.scanner import identity, inventory, inventory_status, scan, PARSER_VERSION
from molekit.workspace import atomic_json, save_state


def changes(state, directory):
    if "scan" not in state:
        raise MoleError("INVALID_STATE", "Scan before requesting a diff/update.", 5)
    records, limitations = inventory(state["manifest"]["repo"], directory, state["manifest"].get("outputs", []), state["manifest"]["scope"])
    completeness = inventory_status(records, limitations, state['scan']['index'])
    before = {item["path"]: item["hash"] for item in state["scan"]["index"]}
    after = {item["path"]: item["hash"] for item in records}
    added = sorted(after.keys() - before.keys())
    removed = sorted(before.keys() - after.keys()) if completeness['complete'] else []
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
            "renames": renames, "ambiguousRenames": ambiguous,
            'inventory': completeness,
            "parserChanged": state["scan"].get("parserVersion") != PARSER_VERSION}


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
    def operation_key(operation, evidence, sources):
        declaration = operation['kind'] in {'function', 'async_function', 'class'}
        spans = () if declaration else tuple((sources[evidence[e]['sourceId']]['path'], evidence[e]['excerptHash'])
                                             for e in operation['evidenceIds'])
        return operation['kind'], operation['title'], spans
    old_operations = {}
    for operation in old_model['operations']:
        old_operations.setdefault(operation_key(operation, old_evidence, old_sources), []).append(operation['id'])
    for operation in model['operations']:
        matches = old_operations.get(operation_key(operation, new_evidence, new_sources), [])
        if len(matches) == 1:
            mapping[operation['id']] = matches[0]
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
        old_signatures = {}
        for operation in old_model['operations']:
            sig = signature(operation, old_evidence, old_sources, old_path, old_prefix)
            if sig:
                old_signatures.setdefault(sig, []).append(operation['id'])
        for operation in model['operations']:
            sig = signature(operation, new_evidence, new_sources, new_path, new_prefix)
            matches = old_signatures.get(sig, [])
            if sig and len(matches) == 1:
                mapping[operation['id']] = matches[0]
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
    for operation in model["operations"]:
        if "ownerId" in operation:
            operation["ownerId"] = mapping.get(operation["ownerId"], operation["ownerId"])
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
        if "ownerOperationId" in event:
            event["ownerOperationId"] = mapping.get(event["ownerOperationId"], event["ownerOperationId"])
    new_scan["symbolOperations"] = {mapping.get(symbol, symbol): mapping.get(operation, operation)
                                    for symbol, operation in new_scan.get("symbolOperations", {}).items()}
    for collection in ("callSites", "controlBoundaries", "unresolved"):
        for item in new_scan.get(collection, []):
            for field in ("operationId", "ownerOperationId", "resolvedTarget", "owner"):
                if field in item:
                    item[field] = mapping.get(item[field], item[field])
    for entry in new_scan.get("entryPoints", []):
        entry["id"] = mapping.get(entry["id"], entry["id"])
    # Renamed code is re-reviewed: IDs are retained, claims are not silently
    # rewritten to pretend statements naming the old module remain current.
    validate_model(model)


def refresh(state, directory):
    if state["status"] == "EXPORTING":
        # An explicit update abandons unpublished staging, or acknowledges an
        # already committed pointer. Immutable generations need no rollback.
        from molekit.output import current
        from molekit.workspace import locked
        pending = state.get('pendingExport', {})
        if pending.get('version') != 2:
            raise MoleError('WORKSPACE_CONFLICT', 'Resume the previous-engine export before updating.', 5)
        state = copy.deepcopy(state)
        with locked(pending['output']):
            pointer, manifest, active = current(pending['output'])
            if pointer and pointer.get('token') == pending['token']:
                state.update(output=pending['output'], outputGeneration=pointer['generation'], exportBases=manifest['bases'])
            elif pointer and pointer['generation'] != state.get('outputGeneration'):
                raise MoleError('OUTPUT_CONFLICT', 'Another workspace changed the output during interrupted export.', 5)
            state.pop('pendingExport', None)
            state['status'] = 'VALIDATING'
        # Persist reconciliation even when no source changed.
        save_state(directory, state, writer=atomic_json)
    report = changes(state, directory)
    if not report['inventory']['complete']:
        raise MoleError('INCOMPLETE_INVENTORY', 'Cannot update knowledge from an incomplete source inventory.', 6,
                        'Restore source access or narrow/adjust explicit ignore scope, then retry; prior knowledge is unchanged.')
    if not report["parserChanged"] and not any(report[key] for key in ("added", "removed", "changed")):
        return state, {**report, "reusedClaims": len(state["scan"]["model"]["claims"]), "invalidatedClaims": []}
    result = enrich(scan(state["manifest"]["repo"], directory, state["manifest"].get("outputs", []), state["manifest"]["scope"]))
    completeness = inventory_status(result['index'], result['limitations'], state['scan']['index'])
    if not completeness['complete']:
        raise MoleError('INCOMPLETE_INVENTORY', 'Analysis inventory became incomplete; prior knowledge is unchanged.', 6)
    retain_renamed_ids(state["scan"], result, report["renames"])
    if report["ambiguousRenames"]:
        result["limitations"].append({"path": ".", "reason": "ambiguous_rename_requires_review"})
    tasks = create_tasks(result, state["manifest"]["mode"])
    old_tasks = {task["id"]: task for task in state["tasks"]}
    available = {ev["id"] for ev in result["model"]["evidence"]}
    reused_claims = []
    invalidated = []
    claim_tasks = {}
    new_tasks = {task['id']: task for task in tasks}
    for tid, ids in state.get('taskClaims', {}).items():
        for cid in ids:
            claim_tasks.setdefault(cid, []).append(tid)
    for claim in state["scan"]["model"]["claims"]:
        linked = claim_tasks.get(claim['id'], [])
        fresh = not report["parserChanged"] and set(claim["evidenceIds"]) <= available
        if not claim["evidenceIds"]:
            fresh = not report["parserChanged"] and bool(linked) and all(tid in new_tasks and tid in old_tasks and set(new_tasks[tid]['evidenceIds']) == set(old_tasks[tid]['evidenceIds']) for tid in linked)
        if fresh:
            reused_claims.append(claim)
        else:
            invalidated.append(claim["id"])
    result["model"]["claims"] = reused_claims
    kept = {c["id"] for c in reused_claims}
    result["claimScopes"] = {cid: scope for cid, scope in state["scan"].get("claimScopes", {}).items() if cid in kept}
    available_operations = {op["id"] for op in result["model"]["operations"]}
    result["semantic"] = {}
    invalidated_semantic = []
    reconstruction_scopes = set()
    for group in ("scenarios", "businessSteps", "glossary"):
        result["semantic"][group] = []
        for entity in state["scan"].get("semantic", {}).get(group, []):
            if set(entity["claimIds"]) <= kept and set(entity.get("operationIds", [])) <= available_operations:
                result["semantic"][group].append(entity)
                result["model"][group].append(entity)
            else:
                invalidated_semantic.append(entity["id"])
                reconstruction_scopes.update(state['scan'].get('claimScopes', {}).get(cid)
                                             for cid in entity['claimIds'])
    # A surviving scenario cannot retain a link to withdrawn interpretation.
    # Reopen its authoring scope rather than silently erasing authored flow.
    while True:
        scene_ids = {scene['id'] for scene in result['semantic']['scenarios']}
        withdrawn = [scene for scene in result['semantic']['scenarios']
                     if any(link['targetScenarioId'] not in scene_ids for link in scene.get('links', []))]
        if not withdrawn:
            break
        ids = {scene['id'] for scene in withdrawn}
        invalidated_semantic.extend(sorted(ids))
        for scene in withdrawn:
            reconstruction_scopes.update(state['scan'].get('claimScopes', {}).get(cid) for cid in scene['claimIds'])
        for collection in (result['semantic'], result['model']):
            collection['scenarios'] = [scene for scene in collection['scenarios'] if scene['id'] not in ids]
    for task in tasks:
        old = old_tasks.get(task["id"])
        claims = state.get("taskClaims", {}).get(task["id"], [])
        if (task.get('scopeId', task['id']) not in reconstruction_scopes
                and old and old["status"] == "completed" and claims and set(claims) <= kept
                and set(old["evidenceIds"]) == set(task["evidenceIds"])):
            task["status"] = "completed"
    for task in state['tasks']:
        if (task['kind'] == 'claim_review' and task['status'] == 'pending'
                and set(task.get('reviewClaimIds', [])) <= kept
                and set(task['evidenceIds']) <= available):
            tasks.append({**task, 'baseRevision': result['model']['revision']})
    validate_model(result["model"])
    history = directory / "history"
    if history.is_symlink():
        raise MoleError("UNSAFE_PATH", "History must not be a symlink.")
    history.mkdir(exist_ok=True)
    from molekit.snapshots import save
    save(history / (state["revision"] + ".json"), state["scan"]["model"], directory, atomic_json)
    updated = copy.deepcopy(state)
    updated.update(scan=result, revision=result["model"]["revision"], tasks=tasks, submissions={},
                   claimReviews={cid: review for cid, review in state.get('claimReviews', {}).items()
                                 if cid in kept and set(review.get('evidenceIds', [])) <= available},
                   taskClaims={tid: [cid for cid in ids if cid in kept] for tid, ids in state.get("taskClaims", {}).items()},
                   status="NEEDS_ANALYSIS" if any(t["status"] == "pending" for t in tasks) else "VALIDATING")
    report.update(reusedClaims=len(reused_claims), invalidatedClaims=invalidated, invalidatedSemanticIds=invalidated_semantic,
                  reopenedSemanticScopes=sorted(scope for scope in reconstruction_scopes if scope))
    updated["changeReport"] = report
    save_state(directory, updated, writer=atomic_json)
    return updated, report
