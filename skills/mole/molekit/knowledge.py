"""Compose technical scenarios without inventing business semantics."""

from molekit.adapters import trace
from molekit.model import validate_model
from molekit.scanner import identity


def compose(scan):
    model = scan["model"]
    model["operations"] = [op for op in model["operations"] if op["kind"] != "scenario_summary"]
    # Derived views are regenerated; semantic claims remain canonical.
    for group in ("scenarios", "businessSteps", "diagramViews", "glossary", "qualityFindings"):
        model[group] = []
    operations = {o["id"]: o for o in model["operations"]}
    all_nodes = {s["id"]: s["qualifiedName"] for s in model["symbols"]}
    all_nodes.update({o["id"]: o["title"] for o in model["operations"]})
    overview = {"id": "view-overview", "title": "System overview", "scenarioIds": [],
                "nodes": [], "edgeIds": [], "childRefs": []}
    for symbol in model["symbols"]:
        if symbol["kind"] == "class":
            continue
        operation = next(op for op in model["operations"] if op["title"] == symbol["qualifiedName"]
                         and op["kind"] == symbol["kind"])
        traced = trace(model, symbol["id"])
        node_ids = set(traced["nodeIds"]) | {operation["id"]}
        related_ops = [operation["id"]] + [oid for oid in operations if oid in node_ids and oid != operation["id"]]
        evidence_ids = set(operation["evidenceIds"])
        for edge in model["relationships"]:
            if edge["id"] in traced["edgeIds"]:
                evidence_ids.update(edge["evidenceIds"])
        claims = [c for c in model["claims"] if evidence_ids & set(c["evidenceIds"])]
        scenario_id = identity("scenario", symbol["id"])
        view_id = identity("view", scenario_id)
        model["scenarios"].append({"id": scenario_id, "title": "Static trace: " + symbol["qualifiedName"],
            "trigger": "Entry into the declared callable; actual dispatch is unproven",
            "operationIds": related_ops, "claimIds": [c["id"] for c in claims],
            "outcomes": ["Static evidence boundary at " + all_nodes.get(b["nodeId"], b["nodeId"])
                         for b in traced["boundaries"]],
            "unknowns": [*traced["limitations"], *[c["statement"] for c in claims if c["status"] == "unknown"]]})
        model["diagramViews"].append({"id": view_id, "title": symbol["qualifiedName"],
            "scenarioIds": [scenario_id], "nodes": [{"id": node, "label": all_nodes[node]} for node in sorted(node_ids)],
            "edgeIds": [e["id"] for e in model["relationships"] if e["id"] in traced["edgeIds"]
                        and e["source"] in node_ids and e["target"] in node_ids], "childRefs": []})
        overview["scenarioIds"].append(scenario_id)
        overview["nodes"].append({"id": operation["id"], "label": symbol["qualifiedName"]})
        overview["childRefs"].append(view_id)
        for claim in claims:
            model["businessSteps"].append({"id": identity("business", scenario_id + claim["id"]),
                "what": operation["title"], "why": claim["statement"],
                "operationIds": [operation["id"]], "claimIds": [claim["id"]]})
    for operation in model["operations"]:
        if operation["kind"] not in {"documented_input", "text_input"}:
            continue
        sid = identity("scenario", operation["id"])
        vid = identity("view", sid)
        claims = [c["id"] for c in model["claims"] if set(c["evidenceIds"]) & set(operation["evidenceIds"])]
        model["scenarios"].append({"id": sid, "title": "Document-assisted review: " + operation["title"],
            "trigger": "Provided text; intended behavior requires agent interpretation, not AST/runtime proof",
            "operationIds": [operation["id"]], "claimIds": claims, "outcomes": ["Document evidence boundary"],
            "unknowns": ["No source-code call graph or runtime guarantees are derived from this text."]})
        model["diagramViews"].append({"id": vid, "title": operation["title"], "scenarioIds": [sid],
            "nodes": [{"id": operation["id"], "label": operation["title"]}], "edgeIds": [], "childRefs": []})
        overview["scenarioIds"].append(sid)
        overview["nodes"].append({"id": operation["id"], "label": operation["title"]})
        overview["childRefs"].append(vid)
    authored = scan.get("semantic", {})
    model["businessSteps"].extend(authored.get("businessSteps", []))
    model["glossary"].extend(authored.get("glossary", []))
    for scenario in authored.get("scenarios", []):
        evidence_ids = sorted({ev for oid in scenario["operationIds"] for ev in operations[oid]["evidenceIds"]})
        summary_id = identity("scenario-summary", scenario["id"])
        model["operations"].append({"id": summary_id, "title": scenario["title"], "kind": "scenario_summary", "evidenceIds": evidence_ids})
        derived = {**scenario, "operationIds": [summary_id, *scenario["operationIds"]]}
        model["scenarios"].append(derived)
        vid = identity("view", scenario["id"])
        model["diagramViews"].append({"id": vid, "title": scenario["title"], "scenarioIds": [scenario["id"]],
            "nodes": [{"id": summary_id, "label": scenario["title"]}] +
                     [{"id": oid, "label": operations[oid]["title"]} for oid in scenario["operationIds"]],
            "edgeIds": [edge["id"] for edge in model["relationships"] if
                        edge["source"] in scenario["operationIds"] and edge["target"] in scenario["operationIds"]],
            "childRefs": []})
        overview["scenarioIds"].append(scenario["id"])
        overview["nodes"].append({"id": summary_id, "label": scenario["title"]})
        overview["childRefs"].append(vid)
    if overview["nodes"]:
        model["diagramViews"].insert(0, overview)
    for index, limitation in enumerate(scan["limitations"]):
        model["qualityFindings"].append({"id": "finding-" + str(index), "severity": "major",
            "message": limitation["path"] + ": " + limitation["reason"], "affectedIds": []})
    validate_model(model)
    return model
