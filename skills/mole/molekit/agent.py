"""Bounded source inspection and revision-bound semantic submissions."""

import json
from pathlib import Path

from molekit.errors import MoleError
from molekit.model import contract, validate_model
from molekit.scanner import identity, inventory, inventory_status, redact, redacted_lines, sha, PARSER_VERSION
from molekit.safety import read_source


def create_tasks(scan, mode):
    model = scan["model"]
    budget = {"quick": 20, "standard": 100, "deep": 500}[mode]
    tasks = []
    from molekit.flow import workflows
    candidates = workflows(scan, max_candidates=budget)
    for workflow in candidates:
        task = {"id": identity("task", workflow["id"]), "kind": "workflow_review" if workflow["kind"] == "workflow" else "component_review",
                "priority": "critical" if workflow["critical"] else "normal",
                "question": "Reconstruct the bounded workflow, purpose, ordered paths, exceptions and evidence limits: " + workflow["title"],
                "scopeKind": workflow["kind"], "scopeId": workflow["id"], "operationIds": workflow["operationIds"],
                "evidenceIds": workflow["evidenceIds"], "baseRevision": model["revision"], "status": "pending",
                "responseSchema": "semantic-patch.v1"}
        contract(task, "task")
        tasks.append(task)
    for operation in model["operations"]:
        if operation["kind"] in {"documented_input", "text_input"}:
            task = {"id": identity("task", operation["id"]), "kind": "document_review", "priority": "normal",
                    "question": "Explain intended workflows and unknowns from " + operation["title"] + "; do not infer verified runtime behavior.",
                    "evidenceIds": operation["evidenceIds"], "baseRevision": model["revision"],
                    "status": "pending", "responseSchema": "semantic-patch.v1"}
            contract(task, "task")
            tasks.append(task)
    tasks.sort(key=lambda task: (task["priority"] != "critical", task.get("scopeKind") != "workflow", task["id"]))
    if len(tasks) > budget:
        scan["limitations"].append({"path": ".", "reason": "semantic_task_budget_exceeded"})
    return tasks[:budget]


def ensure_fresh(state, directory):
    if state["scan"].get("parserVersion") != PARSER_VERSION:
        raise MoleError("TASK_STALE", "Parser version changed; update before continuing.", 5, "Run update.")
    records, limitations = inventory(state["manifest"]["repo"], directory, state["manifest"].get("outputs", []), state["manifest"]["scope"])
    if not inventory_status(records, limitations, state['scan']['index'])['complete']:
        raise MoleError('INCOMPLETE_INVENTORY', 'Cannot establish freshness from incomplete inventory.', 6,
                        'Restore source access or narrow scope before continuing.')
    current = [{"path": r["path"], "hash": r["hash"]} for r in records]
    if current != state["scan"]["index"]:
        raise MoleError("TASK_STALE", "Source snapshot changed; update/rescan before submitting.", 5,
                        "Run update to refresh affected tasks.")


def scenario_hash(scene):
    return sha(json.dumps(scene, sort_keys=True, ensure_ascii=True).encode())


def related_scenarios(state, task):
    operations = set(task.get('operationIds', []))
    if not operations:
        evidence = set(task['evidenceIds'])
        operations = {op['id'] for op in state['scan']['model']['operations'] if evidence & set(op['evidenceIds'])}
    nearby = set(operations)
    for edge in state['scan']['model']['relationships']:
        if edge['source'] in operations:
            nearby.add(edge['target'])
        if edge['target'] in operations:
            nearby.add(edge['source'])
    return [scene for scene in state['scan'].get('semantic', {}).get('scenarios', [])
            if nearby & set(scene['operationIds'])]


def inspect(state, task, budget, cursor):
    if budget < 1024 or budget > 32000:
        raise MoleError("INVALID_BUDGET", "Inspection budget must be 1024..32000 characters.")
    if cursor.startswith('scenes:'):
        try:
            offset = int(cursor[7:])
        except ValueError as exc:
            raise MoleError('INVALID_CURSOR', 'Scenario cursor must be scenes:N.') from exc
        scenes = related_scenarios(state, task)
        if offset < 0 or offset > len(scenes):
            raise MoleError('INVALID_CURSOR', 'Scenario cursor is outside related scope.')
        result = {'taskId': task['id'], 'baseRevision': state['revision'], 'scenarios': [], 'nextCursor': None}
        for index in range(offset, len(scenes)):
            scene = scenes[index]
            item = {'id': scene['id'], 'title': scene['title'][:200], 'expectedHash': scenario_hash(scene),
                    'operationIdsCount': len(scene['operationIds']), 'claimIdsCount': len(scene['claimIds'])}
            if len(json.dumps({**result, 'scenarios': result['scenarios'] + [item]})) > budget - 768:
                if not result['scenarios']:
                    raise MoleError('INVALID_BUDGET', 'Increase budget for scenario metadata.')
                result['nextCursor'] = 'scenes:' + str(index)
                break
            result['scenarios'].append(item)
        return result
    if cursor.startswith('ops:'):
        try:
            offset = int(cursor[4:])
        except ValueError as exc:
            raise MoleError('INVALID_CURSOR', 'Operation cursor must be ops:N.') from exc
        operations = [op for op in state['scan']['model']['operations']
                      if op['kind'] not in {'scenario_summary', 'component_summary'}
                      and set(op['evidenceIds']) & set(task['evidenceIds'])
                      and ('operationIds' not in task or op['id'] in task['operationIds'])]
        if offset < 0 or offset > len(operations):
            raise MoleError('INVALID_CURSOR', 'Operation cursor is outside task scope.')
        result = {'taskId': task['id'], 'baseRevision': state['revision'], 'operations': [], 'nextCursor': None}
        for index in range(offset, len(operations)):
            item = {key: operations[index][key] for key in ('id', 'title', 'kind', 'evidenceIds')}
            candidate = {**result, 'operations': result['operations'] + [item], 'nextCursor': 'ops:' + str(index)}
            if len(json.dumps(candidate, ensure_ascii=True)) > budget - 768:
                if not result['operations']:
                    raise MoleError('INVALID_BUDGET', 'Budget cannot fit operation metadata; increase --budget-chars.')
                result['nextCursor'] = 'ops:' + str(index)
                return result
            result['operations'].append(item)
        return result
    try:
        evidence_index, line_offset = map(int, cursor.split(":"))
        if min(evidence_index, line_offset) < 0 or evidence_index > len(task["evidenceIds"]):
            raise ValueError()
    except ValueError as exc:
        raise MoleError("INVALID_CURSOR", "Cursor must be an index:offset pair.") from exc
    model = state["scan"]["model"]
    lookup = {e["id"]: e for e in model["evidence"]}
    sources = {s["id"]: s for s in model["sources"]}
    repo = Path(state["manifest"]["repo"]).resolve()
    operations = [{"id": op["id"], "title": op["title"][:200]} for op in model["operations"]
                  if op["kind"] != "scenario_summary" and set(op["evidenceIds"]) & set(task["evidenceIds"])
                  and ("operationIds" not in task or op["id"] in task["operationIds"])]
    result = {"taskId": task["id"], "baseRevision": state["revision"], "context": [], "nextCursor": None}
    if evidence_index == 0 and line_offset == 0:
        result["operations"] = []
        for operation in operations:
            candidate = {**result, "operations": result["operations"] + [operation]}
            if len(json.dumps(candidate)) > budget // 3:
                break
            result["operations"].append(operation)
        result["operationsTruncated"] = len(result["operations"]) != len(operations)
        result['nextOperationsCursor'] = 'ops:' + str(len(result['operations'])) if result['operationsTruncated'] else None
    for index in range(evidence_index, len(task["evidenceIds"])):
        evidence = lookup[task["evidenceIds"][index]]
        source = sources[evidence["sourceId"]]
        path = repo / source["path"]
        if path.is_symlink() or not path.resolve().is_relative_to(repo):
            raise MoleError("UNSAFE_PATH", "Evidence path escaped the repository.")
        content = read_source(repo, path).decode("utf-8")
        lines = content.splitlines()[source["lineStart"] - 1:source["lineEnd"]]
        if sha("\n".join(lines).encode()) != evidence["excerptHash"]:
            raise MoleError("TASK_STALE", "Evidence changed while inspecting.", 5)
        lines = redacted_lines(content)[source["lineStart"] - 1:source["lineEnd"]]
        if line_offset > len(lines):
            raise MoleError("INVALID_CURSOR", "Line offset exceeds source span.")
        for offset in range(line_offset, len(lines)):
            item = {"evidenceId": evidence["id"], "path": source["path"],
                    "line": source["lineStart"] + offset, "text": redact(lines[offset])[:600]}
            candidate = {**result, "context": result["context"] + [item], "nextCursor": str(index) + ":" + str(offset)}
            # Reserve space for CLI envelope and summary, so the full reply stays bounded.
            if len(json.dumps(candidate, ensure_ascii=True)) > budget - 512:
                if not result["context"]:
                    overage = len(json.dumps(candidate, ensure_ascii=True)) - (budget - 512)
                    item["text"] = item["text"][:max(0, len(item["text"]) - overage - 40)] + " [line truncated]"
                    if len(json.dumps({**result, "context": [item], "nextCursor": str(index) + ":" + str(offset + 1)}, ensure_ascii=True)) > budget - 512:
                        raise MoleError("INVALID_BUDGET", "Budget cannot fit source location; increase --budget-chars.")
                    result["context"].append(item)
                    result["nextCursor"] = str(index) + ":" + str(offset + 1)
                    return result
                result["nextCursor"] = str(index) + ":" + str(offset)
                return result
            result["context"].append(item)
        line_offset = 0
    return result


def accept_patch(state, task, patch):
    contract(patch, "semantic-patch")
    if task['kind'] == 'claim_review':
        review = patch.get('review')
        if not review or set(review['claimIds']) != set(task['reviewClaimIds']) or not review['rationale']:
            raise MoleError('INVALID_PATCH', 'Review must address every assigned claim with a rationale.')
        if redact(review['rationale']) != review['rationale']:
            raise MoleError('SENSITIVE_INPUT', 'Review rationale contains sensitive-looking content.')
        if not set(review['evidenceIds']) <= set(task['evidenceIds']) or (review['verdict'] == 'supported' and not review['evidenceIds']):
            raise MoleError('INSUFFICIENT_EVIDENCE', 'Review requires task-linked evidence for support.')
        if patch['claims'] or any(patch.get(group) for group in ('scenarios', 'businessSteps', 'glossary', 'scenarioAmendments')):
            raise MoleError('INVALID_PATCH', 'Claim review does not author unrelated new entities.')
        for claim in state['scan']['model']['claims']:
            if claim['id'] in review['claimIds']:
                state.setdefault('claimReviews', {})[claim['id']] = {**review, 'taskId': task['id']}
                if review['verdict'] in {'unknown', 'contradicted'}:
                    claim['status'] = review['verdict']
                    claim['limitations'] = list(dict.fromkeys([*claim['limitations'], review['rationale']]))
        validate_model(state['scan']['model'])
        task['status'] = 'completed'
        return
    if not patch["claims"]:
        raise MoleError("INSUFFICIENT_EVIDENCE", "Submit at least one claim, including unknown if necessary.")
    existing = {claim["id"] for claim in state["scan"]["model"]["claims"]}
    for claim in patch["claims"]:
        if claim["id"] in existing:
            raise MoleError("TASK_CONFLICT", "Claim ID already exists.", 5)
        if not set(claim["evidenceIds"]) <= set(task["evidenceIds"]):
            raise MoleError("INSUFFICIENT_EVIDENCE", "Claim cites evidence outside its task.")
        # Source and agent text are untrusted. Never store obvious secret material.
        for text in [claim["statement"], *claim["limitations"]]:
            if redact(text) != text:
                raise MoleError("SENSITIVE_INPUT", "Patch contains sensitive-looking content.")
    candidate = {**state["scan"]["model"], "claims": state["scan"]["model"]["claims"] + patch["claims"]}
    claim_ids = {claim["id"] for claim in patch["claims"]}
    allowed_operations = {op["id"] for op in candidate["operations"]
                          if op["kind"] != "scenario_summary" and set(op["evidenceIds"]) & set(task["evidenceIds"])}
    if "operationIds" in task:
        allowed_operations &= set(task["operationIds"])
    amendments = patch.get('scenarioAmendments', [])
    related = {scene['id']: scene for scene in related_scenarios(state, task)} if amendments else {}
    amended = {}
    for amendment in amendments:
        scenario_id = amendment['scenarioId']
        scene = related.get(scenario_id)
        if scene is None or scenario_id in amended:
            raise MoleError('INSUFFICIENT_EVIDENCE', 'Amendment must target one related authored scenario once.')
        if amendment['expectedHash'] != scenario_hash(scene):
            raise MoleError('TASK_CONFLICT', 'Scenario changed; inspect scenes:0 before extending it.', 5)
        if (not amendment['addClaimIds'] or not set(amendment['addClaimIds']) <= claim_ids
                or not set(amendment['addOperationIds']) <= allowed_operations):
            raise MoleError('INSUFFICIENT_EVIDENCE', 'Scenario additions must cite this task claims/operations.')
        updated = dict(scene)
        for key, values in amendment.items():
            if key.startswith('add'):
                field = key[3:4].lower() + key[4:]
                updated[field] = list(scene.get(field, []))
                for value in values:
                    if value not in updated[field]:
                        updated[field].append(value)
        for step in amendment.get('addSteps', []):
            if step['operationId'] not in allowed_operations or not step['claimIds'] or not set(step['claimIds']) <= claim_ids:
                raise MoleError('INSUFFICIENT_EVIDENCE', 'Added steps require current task evidence.')
        for branch in amendment.get('addFailurePaths', []):
            if not branch['operationIds'] or not set(branch['operationIds']) <= allowed_operations or not branch['claimIds'] or not set(branch['claimIds']) <= claim_ids:
                raise MoleError('INSUFFICIENT_EVIDENCE', 'Added failure paths require current task evidence.')
        pending = [amendment]
        while pending:
            value = pending.pop()
            if isinstance(value, dict):
                pending.extend(value.values())
            elif isinstance(value, list):
                pending.extend(value)
            elif isinstance(value, str) and redact(value) != value:
                raise MoleError('SENSITIVE_INPUT', 'Scenario amendment contains sensitive-looking content.')
        amended[scenario_id] = updated
    candidate['scenarios'] = [amended.get(scene['id'], scene) for scene in candidate['scenarios']]
    for group in ("scenarios", "businessSteps", "glossary"):
        additions = patch.get(group, [])
        for entity in additions:
            if not entity["id"].startswith("semantic-"):
                raise MoleError("INVALID_ID", "Authored scenario/business/glossary IDs must start with semantic-.")
            if not entity["claimIds"] or not set(entity["claimIds"]) <= claim_ids:
                raise MoleError("INSUFFICIENT_EVIDENCE", "Authored meaning must cite claims from its submitted task.")
            if group != "glossary" and (not entity["operationIds"] or not set(entity["operationIds"]) <= allowed_operations):
                raise MoleError("INSUFFICIENT_EVIDENCE", "Authored scenario/step operations must belong to task evidence.")
            if group != "glossary" and len(entity["operationIds"]) != len(set(entity["operationIds"])):
                raise MoleError("INVALID_ID", "Duplicate authored operation references.")
            if group == "scenarios" and not entity["outcomes"] and not entity["unknowns"]:
                raise MoleError("INSUFFICIENT_EVIDENCE", "Scenario requires an outcome or explicit evidence boundary.")
            if group == "scenarios":
                for step in entity.get("steps", []):
                    if step["operationId"] not in entity["operationIds"] or not step["claimIds"] or not set(step["claimIds"]) <= claim_ids:
                        raise MoleError("INSUFFICIENT_EVIDENCE", "Authored step needs task-grounded operations and claims.")
                for branch in entity.get("failurePaths", []):
                    if not set(branch["operationIds"]) <= set(entity["operationIds"]) or not branch["claimIds"] or not set(branch["claimIds"]) <= claim_ids:
                        raise MoleError("INSUFFICIENT_EVIDENCE", "Authored failure path needs task-grounded operations and claims.")
            pending_values = list(entity.values())
            while pending_values:
                value = pending_values.pop()
                if isinstance(value, dict):
                    pending_values.extend(value.values())
                elif isinstance(value, list):
                    pending_values.extend(value)
                elif isinstance(value, str) and redact(value) != value:
                    raise MoleError("SENSITIVE_INPUT", "Authored field contains sensitive-looking content.")
        candidate[group] = candidate[group] + additions
    validate_model(candidate)
    state["scan"]["model"] = candidate
    authored = state["scan"].setdefault("semantic", {group: [] for group in ("scenarios", "businessSteps", "glossary")})
    authored['scenarios'] = [amended.get(scene['id'], scene) for scene in authored['scenarios']]
    for group in authored:
        authored[group].extend(patch.get(group, []))
    state.setdefault("taskClaims", {})[task["id"]] = [claim["id"] for claim in patch["claims"]]
    for claim in patch["claims"]:
        state["scan"].setdefault("claimScopes", {})[claim["id"]] = task.get("scopeId", task["id"])
    task["status"] = "completed"
    from molekit.quality import MATERIAL
    material = [claim for claim in patch['claims'] if MATERIAL.search(claim['statement'])]
    if material:
        review_task = {**task, 'id': identity('review', task['id'] + sha(json.dumps(material, sort_keys=True).encode())),
            'kind': 'claim_review', 'status': 'pending', 'priority': 'critical',
            'reviewClaimIds': [claim['id'] for claim in material],
            'question': 'Check whether evidence supports the material claims, identify contradictions, and return an explicit review verdict.'}
        state['tasks'].append(review_task)
