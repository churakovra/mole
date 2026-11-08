"""SKM v1 construction and structural/provenance validation."""

import json
from pathlib import Path
import re

from molekit.errors import MoleError

CLAIM_STATUSES = ["source_observed", "runtime_verified", "documented_intent",
                  "inferred", "unknown", "contradicted"]
RESOLUTIONS = ["resolved_static", "possible", "unresolved", "observed_runtime"]
COLLECTIONS = ["sources", "evidence", "claims", "symbols", "operations",
               "relationships", "scenarios", "businessSteps", "diagramViews",
               "glossary", "overrides", "qualityFindings"]


def empty_model(revision):
    return {"schemaVersion": 1, "revision": revision,
            **{name: [] for name in COLLECTIONS}}


def validate_schema(value, schema, location="$", depth=0):
    """Validate the deliberately small JSON Schema vocabulary in bundled schemas.

    This is not a general-purpose JSON Schema implementation. All bundled
    contracts use only type/enum/required/properties/items/additionalProperties.
    """
    if depth > 64:
        raise MoleError("SCHEMA_MISMATCH", "JSON nesting exceeds 64 levels.")
    types = {"object": dict, "array": list, "string": str, "integer": int,
             "boolean": bool, "null": type(None), "number": (int, float)}
    kind = schema.get("type")
    allowed = kind if isinstance(kind, list) else [kind] if kind else []
    if allowed and not any(isinstance(value, types[t]) and not
                           (t in ("integer", "number") and isinstance(value, bool)) for t in allowed):
        raise MoleError("SCHEMA_MISMATCH", location + ": invalid type")
    if "enum" in schema and value not in schema["enum"]:
        raise MoleError("SCHEMA_MISMATCH", location + ": invalid enum")
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                raise MoleError("SCHEMA_MISMATCH", location + ": missing " + key)
        properties = schema.get("properties", {})
        for key, item in value.items():
            if key not in properties and schema.get("additionalProperties") is False:
                raise MoleError("SCHEMA_MISMATCH", location + ": unexpected field " + key)
            if key in properties:
                validate_schema(item, properties[key], location + "." + key, depth + 1)
    if isinstance(value, list) and "items" in schema:
        for index, item in enumerate(value):
            validate_schema(item, schema["items"], location + "[" + str(index) + "]", depth + 1)


def contract(value, name):
    schema = json.loads((Path(__file__).resolve().parents[1] / "schemas" /
                         (name + ".v1.schema.json")).read_text(encoding="utf-8"))
    validate_schema(value, schema)


def validate_model(model):
    contract(model, "knowledge-model")
    lookup = {}
    groups = {}
    for collection in COLLECTIONS:
        groups[collection] = set()
        for item in model[collection]:
            identity = item["id"]
            if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,199}", identity) or identity in lookup:
                raise MoleError("INVALID_ID", "Duplicate or invalid model ID.")
            lookup[identity] = item
            groups[collection].add(identity)

    def refs(values, collection):
        if any(v not in groups[collection] for v in values):
            raise MoleError("DANGLING_REFERENCE", "Invalid " + collection + " reference.")

    for source in model["sources"]:
        path = Path(source["path"])
        if (path.is_absolute() or ".." in path.parts or "\\" in source["path"]
                or source["lineStart"] < 1 or source["lineEnd"] < source["lineStart"]
                or source["revision"] != model["revision"]):
            raise MoleError("INVALID_SOURCE", "Invalid source span or revision.")
    for evidence in model["evidence"]:
        refs([evidence["sourceId"]], "sources")
    for claim in model["claims"]:
        refs(claim["evidenceIds"], "evidence")
        if claim["status"] not in ("inferred", "unknown") and not claim["evidenceIds"]:
            raise MoleError("INSUFFICIENT_EVIDENCE", "Material claim requires evidence.")
        if claim["status"] in ("inferred", "unknown") and not claim["limitations"]:
            raise MoleError("INSUFFICIENT_EVIDENCE", "Uncertain claim requires limitations.")
        kinds = {lookup[e]["classification"] for e in claim["evidenceIds"]}
        if claim["status"] == "runtime_verified" and "runtime_trace" not in kinds:
            raise MoleError("INSUFFICIENT_EVIDENCE", "Static evidence does not verify runtime behavior.")
    for symbol in model["symbols"]:
        refs(symbol["sourceRefs"], "sources")
        if not symbol["sourceRefs"]:
            raise MoleError("INSUFFICIENT_EVIDENCE", "Symbol requires a source.")
    for operation in model["operations"]:
        refs(operation["evidenceIds"], "evidence")
        if not operation["evidenceIds"]:
            raise MoleError("INSUFFICIENT_EVIDENCE", "Operation requires evidence.")
    for relation in model["relationships"]:
        if any(relation[k] not in groups["symbols"] | groups["operations"]
               for k in ("source", "target")):
            raise MoleError("DANGLING_REFERENCE", "Invalid relationship endpoint.")
        refs(relation["evidenceIds"], "evidence")
        if not relation["evidenceIds"]:
            raise MoleError("INSUFFICIENT_EVIDENCE", "Relationship requires evidence.")
        if relation["resolution"] == "observed_runtime" and not any(
                lookup[e]["classification"] == "runtime_trace" for e in relation["evidenceIds"]):
            raise MoleError("INSUFFICIENT_EVIDENCE", "Static edge is not a runtime observation.")
    for scenario in model["scenarios"]:
        refs(scenario["operationIds"], "operations")
        refs(scenario["claimIds"], "claims")
    for step in model["businessSteps"]:
        refs(step["operationIds"], "operations")
        refs(step["claimIds"], "claims")
        if not step["operationIds"] and not step["claimIds"]:
            raise MoleError("INSUFFICIENT_EVIDENCE", "Business step requires grounding.")
    for view in model["diagramViews"]:
        refs(view["scenarioIds"], "scenarios")
        refs(view["childRefs"], "diagramViews")
        for node in view["nodes"]:
            if node["id"] not in groups["operations"] | groups["symbols"]:
                raise MoleError("DANGLING_REFERENCE", "Invalid diagram node.")
        refs(view["edgeIds"], "relationships")
        node_ids = [node["id"] for node in view["nodes"]]
        if len(node_ids) != len(set(node_ids)) or any(
                lookup[edge][endpoint] not in node_ids
                for edge in view["edgeIds"] for endpoint in ("source", "target")):
            raise MoleError("INVALID_VIEW", "View has duplicate nodes or absent edge endpoints.")
    for term in model["glossary"]:
        refs(term["claimIds"], "claims")
    for override in model["overrides"]:
        if override["targetId"] not in lookup:
            raise MoleError("DANGLING_REFERENCE", "Invalid override target.")
    for finding in model["qualityFindings"]:
        if any(identity not in lookup for identity in finding["affectedIds"]):
            raise MoleError("DANGLING_REFERENCE", "Invalid finding target.")
    return model
