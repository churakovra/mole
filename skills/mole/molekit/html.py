"""Single-file offline explorer; no external script, style or model resources."""

import json
from string import Template
from pathlib import Path
from molekit.layout import layout


def render(model, partial=False, artifact_id="local-explorer", source_prefix=None, delivery_context=None):
    assets = Path(__file__).resolve().parents[1] / "assets" / "explorer"
    css = (assets / "explorer.css").read_text(encoding="utf-8")
    script = (assets / "explorer.js").read_text(encoding="utf-8")
    data = json.dumps(model, ensure_ascii=True).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    layouts = json.dumps({view["id"]: layout(model, view) for view in model["diagramViews"]}, ensure_ascii=True).replace("<", "\\u003c")
    overrides = (assets / "overrides.js").read_text(encoding="utf-8")
    # Legacy exports start at the overview even with one authored process, so
    # the process explanation and Back route remain reachable. Deep links still
    # select a specific subprocess explicitly.
    context = delivery_context or {}
    initial = context.get('initialViewId')
    config = json.dumps({"artifactId": artifact_id, "sourcePrefix": source_prefix, "initialViewId": initial,
                         "question": context.get('question'), "answer": context.get('answer')},ensure_ascii=True).replace("<", "\\u003c")
    template = Template((assets / "template.html").read_text(encoding="utf-8"))
    return template.substitute(
        style=css, script=script, model=data, config=config, layouts=layouts,
        blocks=(assets / "blocks.js").read_text(encoding="utf-8"), overrides=overrides,
        coverage_label="Partial source review" if partial else "Source review",
        coverage_notice=("PARTIAL: unresolved tasks or coverage limits remain. " if partial else "") +
                        "Source interpretation; runtime behavior is not verified.")
