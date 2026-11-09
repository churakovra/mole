"""Bounded source inspection and revision-bound semantic submissions."""

import json
from pathlib import Path

from molekit.errors import MoleError
from molekit.model import contract, validate_model
from molekit.scanner import identity, inventory, redact, redacted_lines, sha, PARSER_VERSION
from molekit.safety import read_source


def create_tasks(scan, mode):
    model = scan["model"]
    budget = {"quick": 20, "standard": 100, "deep": 500}[mode]
    tasks = []
    from molekit.flow import workflows
    candidates = workflows(scan)
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
    records, _ = inventory(state["manifest"]["repo"], directory, state["manifest"].get("outputs", []), state["manifest"]["scope"])
    current = [{"path": r["path"], "hash": r["hash"]} for r in records]
    if current != state["scan"]["index"]:
        raise MoleError("TASK_STALE", "Source snapshot changed; update/rescan before submitting.", 5,
                        "Run update to refresh affected tasks.")


def inspect(state, task, budget, cursor):
    if budget < 1024 or budget > 32000:
        raise MoleError("INVALID_BUDGET", "Inspection budget must be 1024..32000 characters.")
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
            for value in entity.values():
                values = value if isinstance(value, list) else [value]
                if any(isinstance(text, str) and redact(text) != text for text in values):
                    raise MoleError("SENSITIVE_INPUT", "Authored field contains sensitive-looking content.")
        candidate[group] = candidate[group] + additions
    validate_model(candidate)
    state["scan"]["model"] = candidate
    authored = state["scan"].setdefault("semantic", {group: [] for group in ("scenarios", "businessSteps", "glossary")})
    for group in authored:
        authored[group].extend(patch.get(group, []))
    state.setdefault("taskClaims", {})[task["id"]] = [claim["id"] for claim in patch["claims"]]
    task["status"] = "completed"
