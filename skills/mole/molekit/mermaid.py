"""Explicitly lossy flow export; no executable click links."""


def label(value):
    # Mermaid numeric entities keep user text out of the syntax grammar.
    return "".join(char if char.isalnum() or char in " ._-" else "#" + str(ord(char)) + ";" for char in value)


def render(model, partial=False):
    lines = ["%% MOLE snapshot " + model["revision"],
             "%% Losses: nested navigation, evidence drawer, local edits, and full diagram semantics.",
             "%% Static candidates only; runtime behavior is not verified."]
    if partial:
        lines.append("%% PARTIAL")
    lines.append("flowchart LR")
    nodes = {node["id"]: node["label"] for view in model["diagramViews"] for node in view["nodes"]}
    mapping = {identity: "n" + str(index) for index, identity in enumerate(sorted(nodes))}
    for identity, name in sorted(nodes.items()):
        lines.append("  %% semantic-id " + identity)
        lines.append('  ' + mapping[identity] + '["' + label(name) + '"]')
    used_edges = {edge for view in model["diagramViews"] for edge in view["edgeIds"]}
    for edge in model["relationships"]:
        if edge["id"] in used_edges:
            lines.append("  " + mapping[edge["source"]] + ' -. "' + label(edge["kind"]) + '" .-> ' + mapping[edge["target"]])
    return "\n".join(lines) + "\n"
