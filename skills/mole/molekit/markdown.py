"""Evidence-backed Markdown and preservation of authored sections."""

import hashlib
import html
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import quote

from molekit.errors import MoleError


def text(value):
    escaped = html.escape(str(value).replace("\r", " ").replace("\n", " "), quote=False)
    return re.sub(r"([\\`*_{}\[\]()#+!|>])", r"\\\1", escaped)


def documents(model, repo, output, partial=False):
    documents = {}
    claims = {c["id"]: c for c in model["claims"]}
    operations = {o["id"]: o for o in model["operations"]}
    evidence = {e["id"]: e for e in model["evidence"]}
    sources = {s["id"]: s for s in model["sources"]}
    prefix = "**PARTIAL: unresolved tasks or coverage limits remain.**\n\n" if partial else ""
    heading = prefix + "Snapshot: `" + model["revision"] + "`. Static analysis; runtime behavior is not verified.\n\n"
    catalog = ["# System workflows\n\n" + heading, "[Architecture](architecture.md) · [Quality report](quality-report.md) · [Explorer](explorer.html)\n"]
    for scenario in model["scenarios"]:
        filename = "processes/" + scenario["id"] + ".md"
        catalog.append("- [" + text(scenario["title"]) + "](" + filename + ")")
        lines = ["# " + text(scenario["title"]), "", heading,
                 "Audience: maintainers and reviewers investigating this bounded workflow.", "",
                 "## Actors and preconditions", "",
                 "Actors: " + (", ".join(text(value) for value in scenario.get("actors", [])) or "Unknown; not established by source evidence."),
                 "Preconditions: " + ("; ".join(text(value) for value in scenario.get("preconditions", [])) or "Unknown; review required."), "",
                 "## Trigger and scope", "", text(scenario["trigger"]), "",
                 "## Main path", "", "Numbering is a static/authored candidate order, not proof of runtime reachability or delivery.", ""]
        refs = set()
        steps = scenario.get("steps", [{"operationId": oid, "description": operations[oid]["title"], "claimIds": [], "condition": ""}
                                      for oid in scenario["operationIds"] if operations[oid]["kind"] not in {"scenario_summary", "component_summary"}])
        for index, step in enumerate(steps, 1):
            op = operations[step["operationId"]]
            refs.update(op["evidenceIds"])
            locations = []
            for ev_id in op["evidenceIds"]:
                source = sources[evidence[ev_id]["sourceId"]]
                locations.append(text(source["path"]) + ":" + str(source["lineStart"]))
            lines.append(str(index) + ". " + text(step["description"]) + " (`" + text(op["kind"]) + "`; `" + op["id"] + "`) — " + ", ".join(locations))
            if step["condition"]:
                lines.append("   - Condition: " + text(step["condition"]))
        lines.extend(["", "## Alternative and failure paths", ""])
        for branch in scenario.get("failurePaths", []):
            lines.append("- Condition: " + text(branch["condition"]))
            for oid in branch["operationIds"]:
                op = operations[oid]
                lines.append("  - " + text(op["title"]) + " (`" + text(op["kind"]) + "`)")
                refs.update(op["evidenceIds"])
            lines.append("  - Outcome: " + text(branch["outcome"]))
        if not scenario.get("failurePaths"):
            lines.append("No failure path has been established in this bounded model; absence is not proof that failures cannot occur.")
        lines.extend(["", "## Data, state and integration effects", ""])
        lines.extend("- " + text(value) for value in scenario.get("stateEffects", []))
        if not scenario.get("stateEffects"):
            lines.append("No state/integration effect has been established in this scope.")
        view_id = next((view["id"] for view in model["diagramViews"] if view["scenarioIds"] == [scenario["id"]] and view["title"] == scenario["title"]), None)
        if view_id:
            lines.extend(["", "[Open workflow diagram](../explorer.html#view=" + view_id + ")", ""])
        lines.extend(["", "## Interpretation and limits", ""])
        if not scenario["claimIds"]:
            lines.append("Business purpose is unknown; no semantic claim has been accepted for this trace.")
        for cid in scenario["claimIds"]:
            claim = claims[cid]
            lines.append("- **" + claim["status"] + "**: " + text(claim["statement"]))
            lines.extend("  - Limitation: " + text(value) for value in claim["limitations"])
            refs.update(claim["evidenceIds"])
        steps = [step for step in model["businessSteps"] if set(step["operationIds"]) & set(scenario["operationIds"])
                 and set(step["claimIds"]) <= set(scenario["claimIds"])]
        if steps:
            lines.extend(["", "## Business mapping", ""])
            for step in steps:
                lines.append("- What: " + text(step["what"]) + ". Why: " + text(step["why"]))
                lines.append("  - Claim basis: " + ", ".join("`" + cid + "` (" + claims[cid]["status"] + ")" for cid in step["claimIds"]))
        lines.extend(["", "## Outcomes and evidence boundaries", ""])
        lines.extend("- " + text(value) for value in scenario["outcomes"] + scenario["unknowns"])
        lines.extend(["", "## Evidence", ""])
        for ev_id in sorted(refs):
            ev = evidence[ev_id]
            source = sources[ev["sourceId"]]
            relative = os.path.relpath(Path(repo) / source["path"], Path(output) / "processes").replace(os.sep, "/")
            lines.append("- `" + ev_id + "`: [" + text(source["path"]) + "](" + quote(relative, safe="/.") + ")"
                         + " lines " + str(source["lineStart"]) + "–" + str(source["lineEnd"])
                         + "; " + text(ev["classification"]) + "; " + text(ev["observation"]))
        lines.extend(["", "[All processes](../README.md)", ""])
        documents[filename] = "\n".join(lines)
    if not model["scenarios"]:
        catalog.append("No supported callable traces were found. Coverage is limited to the source inventory.")
    documents["README.md"] = "\n".join(catalog) + "\n"
    from collections import defaultdict
    components = defaultdict(lambda: {"roles": set(), "operations": set()})
    op_paths = {}
    for op in model["operations"]:
        if op["kind"] in {"scenario_summary", "component_summary"}:
            continue
        for ev_id in op["evidenceIds"]:
            path = sources[evidence[ev_id]["sourceId"]]["path"]
            components[path]["roles"].add(op["kind"])
            components[path]["operations"].add(op["id"])
            op_paths.setdefault(op["id"], path)
    architecture = ["# Architecture components", "", heading,
                    "Components/dependencies below are source candidates, not a verified deployment map.", "",
                    "| Component | Source roles/patterns | Operations |", "| --- | --- | --- |"]
    for path, component in sorted(components.items()):
        architecture.append("| " + text(path) + " | " + text(", ".join(sorted(component["roles"]))) + " | " + str(len(component["operations"])) + " |")
    architecture.extend(["", "## Cross-component and integration candidates", ""])
    dependencies = set()
    for edge in model["relationships"]:
        if edge["id"].startswith("view-edge-"):
            continue
        source, target = op_paths.get(edge["source"]), op_paths.get(edge["target"])
        if source and target and source != target:
            dependencies.add((source, target, edge["kind"]))
    architecture.extend("- " + text(source) + " → " + text(target) + " (`" + text(kind) + "`, possible)" for source, target, kind in sorted(dependencies))
    architecture.extend(["", "## External effects and boundaries", ""])
    external = {(op_paths.get(op["id"], "unknown"), op["title"], op["kind"]) for op in model["operations"]
                if op["kind"] in {"publish", "consume", "db_read", "db_write", "db_execute_candidate", "transaction_boundary", "background_task"}}
    architecture.extend("- " + text(path) + ": " + text(title) + " (`" + text(kind) + "`; guarantees unverified)" for path, title, kind in sorted(external))
    documents["architecture.md"] = "\n".join(architecture) + "\n"
    if model["glossary"]:
        glossary = ["# Glossary", "", heading]
        for term in model["glossary"]:
            glossary.extend(["## " + text(term["term"]), "", text(term["definition"]), "",
                             "Claims: " + ", ".join("`" + cid + "` (" + claims[cid]["status"] + ")" for cid in term["claimIds"]), ""])
        documents["glossary.md"] = "\n".join(glossary)
        documents["README.md"] += "\n[Glossary](glossary.md)\n"
    quality = ["# Quality report\n", heading,
               "Schema and reference/provenance checks passed for this snapshot.",
               "Semantic truth, runtime reachability and complete branch coverage are not established.\n"]
    quality.extend("- " + f["severity"] + ": " + text(f["message"]) for f in model["qualityFindings"])
    if model["claims"]:
        quality.extend(["", "## All accepted claims", ""])
        for claim in model["claims"]:
            quality.append("- **" + claim["status"] + "** `" + text(claim["id"]) + "`: " + text(claim["statement"]))
            quality.extend("  - Limitation: " + text(value) for value in claim["limitations"])
    if model["businessSteps"]:
        quality.extend(["", "## All business mappings", ""])
        for step in model["businessSteps"]:
            quality.append("- `" + step["id"] + "`: " + text(step["what"]) + ". Why: " + text(step["why"]))
            quality.append("  - Claim basis: " + ", ".join("`" + cid + "` (" + claims[cid]["status"] + ")" for cid in step["claimIds"]))
    documents["quality-report.md"] = "\n".join(quality) + "\n"
    return documents


def atomic_text(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".mole-")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def plan_writes(output, generated, previous):
    """Preflight all managed files before writing any; retain unowned/manual text."""
    output = Path(output).absolute()
    if output.is_symlink():
        raise MoleError("UNSAFE_PATH", "Output directory must not be a symlink.")
    pending, bases, conflicts = {}, dict(previous), []
    for relative, body in generated.items():
        path = output / relative
        if not path.resolve().is_relative_to(output.resolve()) or path.is_symlink():
            raise MoleError("UNSAFE_PATH", "Output escaped its directory.")
        mermaid = path.suffix == ".mmd"
        start = ("%% mole:generated:start id=" + relative + "\n" if mermaid
                 else "<!-- mole:generated:start id=" + relative + " -->\n")
        end = ("%% mole:generated:end id=" + relative if mermaid
               else "<!-- mole:generated:end id=" + relative + " -->")
        digest = hashlib.sha256(body.encode()).hexdigest()
        if path.suffix == '.json':
            if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() != previous.get(relative):
                conflicts.append(relative)
                continue
            pending[path] = body
            bases[relative] = digest
            continue
        if path.exists():
            current = path.read_bytes().decode("utf-8")
            begin = current.find(start)
            finish = current.find(end)
            if begin < 0 or finish < begin or current.count(start) != 1 or current.count(end) != 1:
                conflicts.append(relative)
                continue
            old_body = current[begin + len(start):finish]
            accepted = previous.get(relative, [])
            accepted = accepted if isinstance(accepted, list) else [accepted]
            if hashlib.sha256(old_body.encode()).hexdigest() not in accepted:
                conflicts.append(relative)
                continue
            pending[path] = current[:begin + len(start)] + body + current[finish:]
        else:
            manual = "\n\n%% mole:manual:start\n%% mole:manual:end\n" if mermaid else "\n\n<!-- mole:manual:start -->\n<!-- mole:manual:end -->\n"
            pending[path] = start + body + end + manual
        bases[relative] = digest
    if conflicts:
        raise MoleError("OUTPUT_CONFLICT", "Edited or unowned generated files: " + ", ".join(conflicts), 5,
                        "Preserve edits, move them to manual sections, or choose a new output directory.")
    return pending, bases
