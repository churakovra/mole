"""Bounded source inspection and revision-bound semantic submissions."""

import json
from pathlib import Path

from molekit.errors import MoleError
from molekit.model import contract, validate_model
from molekit.scanner import identity, inventory, redact, redacted_lines, sha
from molekit.safety import read_source


def create_tasks(scan, mode):
    model = scan["model"]
    budget = {"quick": 20, "standard": 100, "deep": 500}[mode]
    tasks = []
    for symbol in model["symbols"]:
        evidence = [e["id"] for e in model["evidence"] if e["sourceId"] in symbol["sourceRefs"]]
        related = [r for r in model["relationships"] if r["source"] == symbol["id"]]
        for edge in related:
            evidence.extend(edge["evidenceIds"])
        critical = any(e["ownerId"] == symbol["id"] and e["kind"] in
                       {"publish", "acknowledgement", "transaction_boundary", "db_write"}
                       for e in scan.get("events", []))
        task = {"id": identity("task", symbol["id"]), "kind": "semantic_review",
                "priority": "critical" if critical else "normal",
                "question": "Explain purpose, success/failure paths and evidence limits of " + symbol["qualifiedName"],
                "evidenceIds": list(dict.fromkeys(evidence))[:30],
                "baseRevision": model["revision"], "status": "pending",
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
    tasks.sort(key=lambda task: (task["priority"] != "critical", task["id"]))
    if len(tasks) > budget:
        scan["limitations"].append({"path": ".", "reason": "semantic_task_budget_exceeded"})
    return tasks[:budget]


def ensure_fresh(state, directory):
    records, _ = inventory(state["manifest"]["repo"], directory, state["manifest"].get("outputs", []))
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
    result = {"taskId": task["id"], "baseRevision": state["revision"], "context": [], "nextCursor": None}
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
    validate_model(candidate)
    state["scan"]["model"] = candidate
    state.setdefault("taskClaims", {})[task["id"]] = [claim["id"] for claim in patch["claims"]]
    task["status"] = "completed"
