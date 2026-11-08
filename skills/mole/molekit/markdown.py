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
                 "Audience: maintainers investigating this static trace.", "",
                 "## Trigger and scope", "", text(scenario["trigger"]), "",
                 "## Operations", "", "The following are observed declarations/patterns, not a proven execution order.", ""]
        refs = set()
        for op_id in scenario["operationIds"]:
            op = operations[op_id]
            lines.append("- " + text(op["title"]) + " (`" + text(op["kind"]) + "`)")
            refs.update(op["evidenceIds"])
        lines.extend(["", "## Interpretation and limits", ""])
        if not scenario["claimIds"]:
            lines.append("Business purpose is unknown; no semantic claim has been accepted for this trace.")
        for cid in scenario["claimIds"]:
            claim = claims[cid]
            lines.append("- **" + claim["status"] + "**: " + text(claim["statement"]))
            lines.extend("  - Limitation: " + text(value) for value in claim["limitations"])
            refs.update(claim["evidenceIds"])
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
    architecture = ["# Architecture inventory\n", heading,
                    "Components below are Python declarations, not a deployment or runtime dependency map.\n"]
    architecture.extend("- " + text(s["qualifiedName"]) + " (`" + text(s["kind"]) + "`)" for s in model["symbols"])
    documents["architecture.md"] = "\n".join(architecture) + "\n"
    quality = ["# Quality report\n", heading,
               "Schema and reference/provenance checks passed for this snapshot.",
               "Semantic truth, runtime reachability and complete branch coverage are not established.\n"]
    quality.extend("- " + f["severity"] + ": " + text(f["message"]) for f in model["qualityFindings"])
    if model["claims"]:
        quality.extend(["", "## All accepted claims", ""])
        for claim in model["claims"]:
            quality.append("- **" + claim["status"] + "** `" + text(claim["id"]) + "`: " + text(claim["statement"]))
            quality.extend("  - Limitation: " + text(value) for value in claim["limitations"])
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
        if path.exists():
            current = path.read_text(encoding="utf-8")
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
