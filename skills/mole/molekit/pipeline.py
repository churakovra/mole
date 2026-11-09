"""Persistent session operations; extraction plugs into advance()."""

import hashlib
import json
from pathlib import Path
import uuid

from molekit import __version__
from molekit.errors import MoleError
from molekit.workspace import atomic_json, load, locked, read_json, save_state

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
    from molekit.safety import confined_output
    confined_output(repo, workspace)
    if scope != "repository":
        scoped = Path(scope)
        if scoped.is_absolute() or ".." in scoped.parts or "\\" in scope:
            raise MoleError("UNSAFE_SCOPE", "Scope must be a repository-relative file or directory.")
        if not (repo / scoped).exists() or (repo / scoped).is_symlink() or not (repo / scoped).resolve().is_relative_to(repo):
            raise MoleError("UNSAFE_SCOPE", "Scope must exist inside the repository without a symlink escape.")
        scope = scoped.as_posix()
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
        save_state(directory, state, writer=atomic_json)
        return summary(state)


def summary(state):
    from molekit.quality import assess
    quality = assess(state)
    return {"status": state["status"], "runId": state["runId"],
            "revision": state["revision"],
            "summary": {"pendingTasks": sum(t.get("status") == "pending" for t in state["tasks"])},
            'quality': {key: quality[key] for key in ('technicalAnalysis', 'semanticCoverage', 'export', 'criticalUnknownCount')},
            "nextAction": {"NEW": "next", "NEEDS_ANALYSIS": "next", "VALIDATING": "finish"}.get(state["status"], "status")}


def advance(state, directory):
    from molekit.scanner import scan
    transition(state, "SCANNING")
    save_state(directory, state, writer=atomic_json)
    result = scan(state["manifest"]["repo"], directory, scope=state["manifest"]["scope"])
    from molekit.adapters import enrich
    enrich(result)
    transition(state, "EXTRACTING")
    state["scan"] = result
    state["revision"] = result["model"]["revision"]
    transition(state, "TRACING")
    from molekit.agent import create_tasks
    state["tasks"] = create_tasks(result, state["manifest"]["mode"])
    transition(state, "NEEDS_ANALYSIS" if state["tasks"] else "VALIDATING")
    save_state(directory, state, writer=atomic_json)


def operate(command, workspace, **options):
    with locked(workspace) as directory:
        state = load(directory)
        if command == "status":
            return summary(state)
        if command in ("diff", "update"):
            from molekit.update import changes, refresh
            if command == "diff":
                report = changes(state, directory)
                return {**summary(state), **({'status': 'PARTIAL', 'nextAction': 'restore_inventory'} if not report['inventory']['complete'] else {}), 'changes': report}
            state, report = refresh(state, directory)
            return {**summary(state), "changes": report}
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
                save_state(directory, state, writer=atomic_json)
            task = dict(pending[0]) if pending else None
            if task:
                for field in ('operationIds', 'evidenceIds'):
                    if field in task:
                        task[field + 'Count'] = len(task[field])
                        task[field] = task[field][:30]
                task['question'] = task['question'][:600]
            return {**summary(state), "task": task}
        if command == "inspect":
            task = next((t for t in state["tasks"] if t["id"] == options["task"]), None)
            if task is None:
                raise MoleError("TASK_UNKNOWN", "Task does not exist.")
            from molekit.agent import ensure_fresh, inspect
            ensure_fresh(state, directory)
            result = {**summary(state), **inspect(state, task, options["budget_chars"], options.get("cursor", "0:0"))}
            if len(json.dumps(result, ensure_ascii=True)) > options['budget_chars']:
                raise MoleError('INVALID_BUDGET', 'Budget cannot fit the complete reply metadata; increase it.')
            return result
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
            if task["status"] != "pending":
                raise MoleError("TASK_CONFLICT", "Task has already been completed.", 5)
            accept_patch(state, task, patch)
            state["submissions"][task_id] = fingerprint
            transition(state, "VALIDATING")
            if any(t["status"] == "pending" for t in state["tasks"]):
                transition(state, "NEEDS_ANALYSIS")
            save_state(directory, state, writer=atomic_json)
            return summary(state)
        if command in ("finish", "export"):
            return finish(state, directory, options["output"], options.get("allow_partial", False), options.get("formats"), options.get("restart_export", False), options.get("adopt_output", False))
        raise MoleError("INVALID_REQUEST", "Unknown operation.")


def finish(state, directory, output, allow_partial, formats=None, restart=False, adopt=False):
    from molekit.agent import ensure_fresh
    from molekit.knowledge import compose
    from molekit.quality import assess
    from molekit.output import publish
    from molekit.safety import confined_output
    if 'scan' not in state:
        raise MoleError('QUALITY_GATE_FAILED', 'Run next before exporting.', 6)
    ensure_fresh(state, directory)
    compose(state['scan'])
    quality = assess(state)
    partial = quality['semanticCoverage'] != 'PASS' or quality['technicalAnalysis'] != 'PASS'
    if partial and not allow_partial:
        raise MoleError('QUALITY_GATE_FAILED', '; '.join(quality['reasons']), 6,
                        'Resolve analysis/review gaps or explicitly export --allow-partial.')
    output = Path(output).absolute()
    confined_output(state['manifest']['repo'], output)
    if output.resolve() in {Path(state['manifest']['repo']).resolve(), directory.resolve()}:
        raise MoleError('UNSAFE_PATH', 'Use a dedicated output directory.')
    if any((Path(state['manifest']['repo']) / item['path']).resolve().is_relative_to(output.resolve()) for item in state['scan']['index']):
        raise MoleError('UNSAFE_PATH', 'Output contains indexed inputs; choose a dedicated empty directory.')
    formats = formats or ['markdown', 'html', 'drawio']
    published = publish(state, directory, output, formats, quality,
        lambda physical, previous: build_outputs(state, physical, output, formats, partial, previous, {**quality, 'export': 'PASS'}),
        lambda: save_state(directory, state, writer=atomic_json), restart, adopt)
    from molekit.snapshots import save
    save(directory / 'knowledge-model.json', state['scan']['model'], directory, atomic_json)
    state.update(exportBases=published['manifest']['bases'], output=str(output), outputGeneration=published['generation'],
                 quality=published['quality'], status='PARTIAL' if partial else 'COMPLETED')
    state.pop('pendingExport', None)
    save_state(directory, state, writer=atomic_json)
    return {**summary(state), **{key: published[key] for key in ('output', 'logicalOutput', 'generation', 'files')}}


def build_outputs(state, output, logical_output, formats, partial, previous, quality):
    from molekit.markdown import documents
    model = state['scan']['model']
    generated = documents(model, state["manifest"]["repo"], output, partial)
    if "changeReport" in state:
        from molekit.markdown import text
        report = state["changeReport"]
        lines = ["# Change report", "", "Snapshot: `" + state["revision"] + "`", ""]
        for key in ("added", "removed", "changed", "invalidatedClaims", "ambiguousRenames"):
            lines.extend(["## " + key, "", *["- " + text(item) for item in report[key]], ""])
        lines.extend(["Reused claims: " + str(report["reusedClaims"]), "", "Renames: " + text(report["renames"]), ""])
        if report.get("invalidatedSemanticIds"):
            lines.extend(["## Invalidated authored meaning", "", *["- " + text(identity) for identity in report["invalidatedSemanticIds"]], ""])
        if report.get("parserChanged"):
            lines.extend(["Parser version changed; semantic review was reopened.", ""])
        generated["change-report.md"] = "\n".join(lines)
    if "html" in formats:
        from molekit.html import render
        generated["explorer.html"] = render(model, partial, digest(str(Path(state["manifest"]["repo"]).resolve()) + str(logical_output.resolve()))[:24])
    else:
        generated["README.md"] = generated["README.md"].replace(" · [Explorer](explorer.html)", "")
    if "drawio" in formats and model["diagramViews"]:
        from molekit.drawio import render as drawio
        generated["confluence/workflows.drawio"] = drawio(model, partial)
    if "mermaid" in formats and model["diagramViews"]:
        from molekit.mermaid import render as mermaid
        generated["workflows.mmd"] = mermaid(model, partial)
    for relative in previous:
        if relative.startswith("processes/") and relative.endswith(".md") and relative not in generated:
            generated[relative] = "# Retired process\n\nThis generated trace is no longer present at snapshot `" + state["revision"] + "`. Manual notes below are retained.\n"
    generated['quality-report.json'] = json.dumps({**quality, 'revision': state['revision']}, sort_keys=True, indent=2) + '\n'
    losses = {'html': ['Browser-local notes are not canonical/shared edits'],
              'drawio': ['No HTML details drawer or localStorage editing', 'Evidence remains in Markdown/HTML sidecars'],
              'mermaid': ['No nested viewer navigation or editing', 'Flow representation may lose diagram semantics']}
    generated['export-losses.json'] = json.dumps({name: losses[name] for name in formats if name in losses}, sort_keys=True, indent=2) + '\n'
    return generated
