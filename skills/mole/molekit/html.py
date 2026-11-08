"""Single-file offline explorer; no external script, style or model resources."""

import json
from pathlib import Path


def render(model, partial=False):
    assets = Path(__file__).resolve().parents[1] / "assets" / "explorer"
    css = (assets / "explorer.css").read_text(encoding="utf-8")
    script = (assets / "explorer.js").read_text(encoding="utf-8")
    data = json.dumps(model, ensure_ascii=True).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'none'; base-uri 'none'; form-action 'none'">
<title>MOLE · Workflow explorer</title><style>""" + css + """</style></head>
<body><header><strong>MOLE</strong><span>Follow the code. Find the why.</span></header>
<p id="warning" role="status">""" + ("PARTIAL: unresolved tasks or coverage limits remain. " if partial else "") + """Static candidates; runtime behavior is not verified.</p>
<main><aside><label for="search">Find a process</label><input id="search" type="search" placeholder="Search views">
<nav id="tree" aria-label="Process navigation"></nav></aside>
<section class="work"><div class="toolbar"><button id="back" type="button">Back</button><h1 id="title">Workflow explorer</h1>
<button id="zoom-out" aria-label="Zoom out" type="button">−</button><output id="zoom-label" aria-live="polite">100%</output>
<button id="zoom-in" aria-label="Zoom in" type="button">+</button><button id="fit" type="button" hidden>Fit</button></div>
<div id="viewport" tabindex="0" aria-label="Scrollable workflow diagram"><svg id="diagram" role="group" aria-label="Workflow diagram"></svg></div>
<section id="details" tabindex="-1" aria-label="Selection details"><h2>Select a node or connector</h2><p>Double-click a process to open its details. Use Back to return to its parent.</p></section>
</section></main><footer>Local artifact · edits, when available, remain in this browser</footer>
<script id="mole-model" type="application/json">""" + data + "</script><script>" + script + "</script></body></html>\n"
