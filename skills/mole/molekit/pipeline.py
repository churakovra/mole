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
            raise MoleError("QUALITY_GATE_FAILED", "This run has no validated knowledge to export.", 6)
        raise MoleError("INVALID_REQUEST", "Unknown operation.")
