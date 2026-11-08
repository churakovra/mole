"""Persistent session operations; extraction plugs into advance()."""

import hashlib
import json
from pathlib import Path
import uuid

from molekit import __version__
from molekit.errors import MoleError
from molekit.workspace import atomic_json, load, locked, read_json

STATES = {"NEW", "SCANNING", "EXTRACTING", "TRACING", "NEEDS_ANALYSIS",
          "VALIDATING", "EXPORTING", "COMPLETED", "PARTIAL", "BLOCKED",
          "FAILED", "STALE"}
TRANSITIONS = {
    "NEW": {"SCANNING", "BLOCKED"},
    "SCANNING": {"EXTRACTING", "FAILED", "BLOCKED"},
    "EXTRACTING": {"TRACING", "FAILED", "BLOCKED"},
    "TRACING": {"NEEDS_ANALYSIS", "VALIDATING", "BLOCKED"},
    "NEEDS_ANALYSIS": {"VALIDATING", "BLOCKED", "STALE"},
    "VALIDATING": {"NEEDS_ANALYSIS", "EXPORTING", "BLOCKED", "STALE"},
    "EXPORTING": {"COMPLETED", "PARTIAL", "FAILED"},
    "BLOCKED": {"SCANNING", "NEEDS_ANALYSIS", "VALIDATING"},
    "FAILED": {"SCANNING", "EXPORTING"},
    "STALE": {"SCANNING"},
    "COMPLETED": {"SCANNING", "EXPORTING"},
    "PARTIAL": {"SCANNING", "EXPORTING", "NEEDS_ANALYSIS"},
}


def transition(state, target):
    if target not in TRANSITIONS.get(state["status"], set()):
        raise MoleError("INVALID_TRANSITION", "Invalid transition to " + target, 5)
    state["status"] = target


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def start(repo, workspace, mode, scope):
    repo = Path(repo).resolve()
    if not repo.is_dir():
        raise MoleError("INVALID_REPOSITORY", "Repository must be an existing directory.")
    manifest = {"repo": str(repo), "mode": mode, "scope": scope,
                "engineVersion": __version__}
    with locked(workspace, create=True) as directory:
        path = directory / "state.json"
        if path.exists():
            state = load(directory)
            if any(state["manifest"].get(k) != manifest[k] for k in ("repo", "mode", "scope")):
                raise MoleError("WORKSPACE_CONFLICT", "Workspace belongs to a different request.", 5)
            return summary(state)
        state = {"schemaVersion": 1, "runId": uuid.uuid4().hex, "status": "NEW",
                 "manifest": manifest, "tasks": [], "submissions": {}, "revision": None}
        atomic_json(path, state)
        return summary(state)


def summary(state):
    return {"status": state["status"], "runId": state["runId"],
            "revision": state["revision"],
            "summary": {"pendingTasks": sum(t.get("status") == "pending" for t in state["tasks"])},
            "nextAction": {"NEW": "next", "NEEDS_ANALYSIS": "next", "VALIDATING": "finish"}.get(state["status"], "status")}


def advance(state, directory):
    from molekit.scanner import scan
    transition(state, "SCANNING")
    atomic_json(directory / "state.json", state)
    result = scan(state["manifest"]["repo"], directory)
    from molekit.adapters import enrich
    enrich(result)
    transition(state, "EXTRACTING")
    state["scan"] = result
    state["revision"] = result["model"]["revision"]
    transition(state, "TRACING")
    from molekit.agent import create_tasks
    state["tasks"] = create_tasks(result, state["manifest"]["mode"])
    transition(state, "NEEDS_ANALYSIS" if state["tasks"] else "VALIDATING")
    atomic_json(directory / "state.json", state)


def operate(command, workspace, **options):
    with locked(workspace) as directory:
        state = load(directory)
        if command == "status":
            return summary(state)
        if command == "next":
            if state["status"] in ("NEW", "SCANNING", "FAILED"):
                if state["status"] == "SCANNING":
                    state["status"] = "NEW"  # resume from last fully committed input
                advance(state, directory)
            if "scan" in state:
                from molekit.agent import ensure_fresh
                ensure_fresh(state, directory)
            pending = [t for t in state["tasks"] if t.get("status") == "pending"]
            if state["status"] == "PARTIAL" and pending:
                transition(state, "NEEDS_ANALYSIS")
                atomic_json(directory / "state.json", state)
            return {**summary(state), "task": pending[0] if pending else None}
        if command == "inspect":
            task = next((t for t in state["tasks"] if t["id"] == options["task"]), None)
            if task is None:
                raise MoleError("TASK_UNKNOWN", "Task does not exist.")
            from molekit.agent import ensure_fresh, inspect
            ensure_fresh(state, directory)
            return {**summary(state), **inspect(state, task, options["budget_chars"], options.get("cursor", "0:0"))}
        if command == "submit":
            patch = read_json(options["input"])
            if not isinstance(patch, dict) or not isinstance(patch.get("taskId"), str):
                raise MoleError("INVALID_PATCH", "Patch requires taskId.")
            task_id = patch["taskId"]
            fingerprint = digest(patch)
            from molekit.agent import ensure_fresh, accept_patch
            if "scan" in state:
                ensure_fresh(state, directory)
            if task_id in state["submissions"]:
                if state["submissions"][task_id] != fingerprint:
                    raise MoleError("TASK_CONFLICT", "A different response was already accepted.", 5)
                return {**summary(state), "duplicate": True}
            task = next((t for t in state["tasks"] if t["id"] == task_id), None)
            if task is None:
                raise MoleError("TASK_UNKNOWN", "Task does not exist.")
            if state["status"] == "PARTIAL" and task["status"] == "pending":
                transition(state, "NEEDS_ANALYSIS")
            if state["status"] != "NEEDS_ANALYSIS" or patch.get("baseRevision") != state["revision"]:
                raise MoleError("TASK_STALE", "Patch does not match active revision.", 5)
            accept_patch(state, task, patch)
            state["submissions"][task_id] = fingerprint
            transition(state, "VALIDATING")
            if any(t["status"] == "pending" for t in state["tasks"]):
                transition(state, "NEEDS_ANALYSIS")
            atomic_json(directory / "state.json", state)
            return summary(state)
        if command == "finish":
            return finish(state, directory, options["output"], options.get("allow_partial", False))
        raise MoleError("INVALID_REQUEST", "Unknown operation.")


def finish(state, directory, output, allow_partial):
    from molekit.agent import ensure_fresh
    from molekit.knowledge import compose
    from molekit.markdown import documents, plan_writes, atomic_text
    if "scan" not in state:
        raise MoleError("QUALITY_GATE_FAILED", "Run next before exporting.", 6)
    pending = any(t["status"] == "pending" for t in state["tasks"])
    partial = pending or any(limitation["reason"] != "excluded_class" for limitation in state["scan"]["limitations"])
    if partial and not allow_partial:
        raise MoleError("QUALITY_GATE_FAILED", "Pending tasks or coverage limits require --allow-partial.", 6)
    ensure_fresh(state, directory)
    model = compose(state["scan"])
    output = Path(output).absolute()
    if output.resolve() == Path(state["manifest"]["repo"]).resolve() or output.resolve() == directory.resolve():
        raise MoleError("UNSAFE_PATH", "Use a dedicated output subdirectory or external directory.")
    if any((Path(state["manifest"]["repo"]) / item["path"]).resolve().is_relative_to(output.resolve())
           for item in state["scan"]["index"]):
        raise MoleError("UNSAFE_PATH", "Output directory contains indexed input sources; use a dedicated empty directory.")
    old_output = state.get("output")
    previous = state.get("exportBases", {}) if old_output == str(output) else {}
    if state.get("pendingExport", {}).get("output") == str(output):
        previous = {key: [previous.get(key), value]
                    for key, value in state["pendingExport"]["bases"].items()}
    generated = documents(model, state["manifest"]["repo"], output, partial)
    from molekit.html import render
    generated["explorer.html"] = render(model, partial)
    writes, bases = plan_writes(output, generated, previous)
    # Mark the journal before touching output. Interrupted exports can resume
    # from generated content without mistaking it for an authored edit.
    state["pendingExport"] = {"output": str(output), "bases": bases}
    if state["status"] == "NEEDS_ANALYSIS":
        transition(state, "VALIDATING")
    if state["status"] != "EXPORTING":
        transition(state, "EXPORTING")
    output_resolved = output.resolve()
    repo = Path(state["manifest"]["repo"]).resolve()
    if output_resolved.is_relative_to(repo):
        relative = output_resolved.relative_to(repo).as_posix() + "/"
        state["scan"]["index"] = [r for r in state["scan"]["index"] if not r["path"].startswith(relative)]
    state["manifest"].setdefault("outputs", [])
    if str(output_resolved) not in state["manifest"]["outputs"]:
        state["manifest"]["outputs"].append(str(output_resolved))
    atomic_json(directory / "state.json", state)
    for path, content in writes.items():
        atomic_text(path, content)
    atomic_json(directory / "knowledge-model.json", model)
    state.update(exportBases=bases, output=str(output))
    state.pop("pendingExport", None)
    transition(state, "PARTIAL" if partial else "COMPLETED")
    atomic_json(directory / "state.json", state)
    return {**summary(state), "output": str(output), "files": sorted(generated)}
