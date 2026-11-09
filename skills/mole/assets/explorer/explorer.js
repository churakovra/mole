"use strict";
(() => {
  const model = JSON.parse(document.getElementById("mole-model").textContent);
  const edits = window.moleOverrides;
  const layouts = JSON.parse(document.getElementById("mole-layouts").textContent);
  const $ = id => document.getElementById(id);
  const ns = "http://www.w3.org/2000/svg";
  const views = new Map(model.diagramViews.map(v => [v.id, v]));
  const entities = new Map(["symbols", "operations", "relationships", "claims", "scenarios", "glossary"].flatMap(k => model[k].map(x => [x.id, x])));
  const evidence = new Map(model.evidence.map(x => [x.id, x]));
  const sources = new Map(model.sources.map(x => [x.id, x]));
  const baseWarning = $("warning").textContent;
  let route = views.size ? [model.diagramViews[0].id] : [];
  let selected = null;
  let zoom = 1;
  let baseWidth = 1, baseHeight = 1;
  const svg = (tag, attrs, parent) => {
    const element = document.createElementNS(ns, tag);
    for (const [key, value] of Object.entries(attrs || {})) element.setAttribute(key, value);
    if (parent) parent.append(element);
    return element;
  };
  const paragraph = (parent, value, tag = "p") => {
    const element = document.createElement(tag);
    element.textContent = value;
    parent.append(element);
    return element;
  };
  function childFor(view, node) {
    if (node.childViewId && view.childRefs.includes(node.childViewId)) return views.get(node.childViewId);
    return (view.childRefs || []).map(id => views.get(id)).find(child => child && child.scenarioIds.some(id => {
      const scenario = entities.get(id);
      return scenario && scenario.operationIds[0] === node.id;
    }));
  }
  function canonicalLabel(id, fallback) {
    const entity = entities.get(id);
    return entity ? entity.title || entity.qualifiedName || entity.statement || entity.term || entity.kind || fallback : fallback;
  }
  function editable(element, id, field, base, display = base) {
    element.tabIndex = 0; element.setAttribute("role", "button");
    element.setAttribute("aria-label", "Edit " + field + "; double click or F2");
    element.addEventListener("dblclick", event => {event.stopPropagation(); edits.edit(id, field, base, display);});
    element.addEventListener("keydown", event => {if(event.key === "F2") {event.preventDefault(); event.stopPropagation(); edits.edit(id, field, base, display);}});
  }
  function select(id) {
    selected = id;
    document.querySelectorAll(".selected").forEach(e => e.classList.remove("selected"));
    for (const element of $("diagram").querySelectorAll("[data-id]")) {
      if (element.dataset.id === id) element.classList.add("selected");
    }
    const detail = $("details");
    detail.replaceChildren();
    const entity = entities.get(id);
    if (!entity) return;
    const baseLabel = entity.title || entity.qualifiedName || entity.statement || entity.term || entity.kind;
    const heading = paragraph(detail, edits.value(id, "label", baseLabel), "h2");
    editable(heading, id, "label", baseLabel);
    for (const field of ["description", "notes"]) {
      const base = entity[field] || "";
      const element = paragraph(detail, edits.value(id, field, base) || "Add " + field);
      editable(element, id, field, base);
    }
    paragraph(detail, "ID: " + id);
    if (entity.resolution) paragraph(detail, "Resolution: " + entity.resolution + ". " + entity.condition);
    const ids = new Set(entity.evidenceIds || []);
    if (entity.sourceRefs) for (const ev of model.evidence) if (entity.sourceRefs.includes(ev.sourceId)) ids.add(ev.id);
    for (const claim of model.claims) {
      if (claim.evidenceIds.some(ev => ids.has(ev))) {
        paragraph(detail, claim.status + ": " + claim.statement);
        for (const limitation of claim.limitations) paragraph(detail, "Limitation: " + limitation);
      }
    }
    if (!ids.size) paragraph(detail, "No direct evidence attached; consult the containing process.");
    for (const id of ids) {
      const ev = evidence.get(id), source = ev && sources.get(ev.sourceId);
      if (source) paragraph(detail, source.path + ":" + source.lineStart + "–" + source.lineEnd + " · " + ev.classification + " · " + ev.observation);
    }
  }
  function open(child) {
    if (!child || route.includes(child.id)) return;
    route.push(child.id);
    selected = null;
    zoom = 1;
    render();
  }
  function tree() {
    const nav = $("tree");
    nav.replaceChildren();
    const query = $("search").value.toLowerCase();
    const expanded = new Set();
    let rendered = 0;
    function branch(id, ancestors, parent) {
      if (rendered >= 600) return;
      const view = views.get(id);
      if (!view || ancestors.includes(id)) return;
      rendered += 1;
      const shared = expanded.has(id);
      expanded.add(id);
      const list = document.createElement("ul"), item = document.createElement("li");
      const button = document.createElement("button");
      button.textContent = (shared ? "↪ " : "") + view.title;
      button.type = "button";
      if (id === route[route.length - 1] && JSON.stringify(ancestors) === JSON.stringify(route.slice(0,-1))) button.setAttribute("aria-current", "page");
      button.addEventListener("click", () => { route = [...ancestors, id]; zoom = 1; render(); });
      if (!query || view.title.toLowerCase().includes(query)) item.append(button);
      if (!shared) for (const child of view.childRefs) branch(child, [...ancestors, id], item);
      if (item.childNodes.length) { list.append(item); parent.append(list); }
    }
    if (model.diagramViews.length) branch(model.diagramViews[0].id, [], nav);
    if (rendered >= 600) paragraph(nav, "Navigation list is bounded; use diagram drill-down or a direct view link for additional detail.");
    if (model.glossary.length) {
      paragraph(nav, "Glossary", "h2");
      for (const term of model.glossary) {
        const button = document.createElement("button"); button.type = "button";
        button.textContent = edits.value(term.id, "term", term.term); button.addEventListener("click", () => {
          select(term.id); const definition = paragraph($("details"), edits.value(term.id, "definition", term.definition));
          editable(definition, term.id, "definition", term.definition);
          const termLabel = paragraph($("details"), edits.value(term.id, "term", term.term));
          editable(termLabel, term.id, "term", term.term);
        }); nav.append(button);
      }
    }
  }
  function sizing() {
    const width = Math.max(1, $("viewport").clientWidth - 2);
    const height = Math.max(1, $("viewport").clientHeight - 2);
    const scale = Math.min(width / baseWidth, height / baseHeight, 1) * zoom;
    $("diagram").style.width = baseWidth * scale + "px";
    $("diagram").style.height = baseHeight * scale + "px";
    $("zoom-label").textContent = Math.round(zoom * 100) + "%";
    $("fit").hidden = Math.abs(zoom - 1) < .001;
  }
  function render() {
    const diagram = $("diagram");
    diagram.replaceChildren();
    tree();
    $("back").disabled = route.length < 2;
    const view = views.get(route[route.length - 1]);
    if (!view) { $("title").textContent = "No supported diagram views"; return; }
    $("title").textContent = view.title;
    const geometry = JSON.parse(JSON.stringify(layouts[view.id]));
    const rows = [...new Set(Object.values(geometry.nodes).map(p => p.y))].sort((a,b)=>a-b);
    const rowGroups = rows.map(row => view.nodes.filter(node => geometry.nodes[node.id].y === row));
    let heightDelta = 0;
    for (const rowNodes of rowGroups) {
      const oldHeight = Math.max(...rowNodes.map(node => geometry.nodes[node.id].height));
      for (const node of rowNodes) {
        const point = geometry.nodes[node.id];
        const display = edits.value(node.id, "label", canonicalLabel(node.id, node.label), node.label);
        const lines = display.split(/\r?\n/u).flatMap(line => line.match(/.{1,28}/gu) || [""]);
        point.lines = lines.slice(0,12); point.truncated = lines.length > 12;
        point.height = Math.max(88, 40 + point.lines.length * 18);
        point.y += heightDelta;
      }
      heightDelta += Math.max(...rowNodes.map(node=>geometry.nodes[node.id].height)) - oldHeight;
    }
    geometry.height += heightDelta;
    for (const edgeId of view.edgeIds) {
      const edge = entities.get(edgeId), a = geometry.nodes[edge.source], b = geometry.nodes[edge.target];
      const x1 = a.x+a.width, y1 = a.y+a.height/2, x2 = b.x, y2 = b.y+b.height/2;
      const lane = geometry.edges[edgeId].y + 5;
      geometry.edges[edgeId].d = `M ${x1} ${y1} H ${x1+30} V ${lane} H ${x2-30} V ${y2} H ${x2}`;
    }
    const positions = new Map(Object.entries(geometry.nodes));
    baseWidth = geometry.width;
    baseHeight = geometry.height;
    $("warning").textContent = baseWarning + (geometry.warning ? " " + geometry.warning : "");
    diagram.setAttribute("viewBox", "0 0 " + baseWidth + " " + baseHeight);
    const defs = svg("defs", {}, diagram);
    const marker = svg("marker", { id: "arrow", viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 6, markerHeight: 6, orient: "auto-start-reverse" }, defs);
    svg("path", { d: "M 0 0 L 10 5 L 0 10 z", fill: "#607c63" }, marker);
    for (const edgeId of view.edgeIds) {
      const edge = entities.get(edgeId), a = edge && positions.get(edge.source), b = edge && positions.get(edge.target);
      if (!a || !b) continue;
      const group = svg("g", { class: "edge", "data-id": edge.id, tabindex: 0, role: "button", "aria-label": edge.kind }, diagram);
      const path = geometry.edges[edgeId].d;
      svg("path", { d: path, "marker-end": "url(#arrow)" }, group);
      svg("path", { d: path, class: "hit" }, group);
      const label = svg("text", { x: geometry.edges[edgeId].x, y: geometry.edges[edgeId].y, "text-anchor": "middle" }, group);
      label.textContent = edits.value(edge.id, "label", edge.kind);
      editable(label, edge.id, "label", edge.kind);
      group.addEventListener("click", () => select(edge.id));
      group.addEventListener("keydown", event => { if (event.key === "Enter") select(edge.id); });
    }
    for (const node of view.nodes) {
      const point = positions.get(node.id), child = childFor(view, node);
      const group = svg("g", { class: "node", "data-id": node.id, tabindex: 0, role: "button", "aria-label": edits.value(node.id, "label", canonicalLabel(node.id, node.label), node.label) + (child ? "; open with ArrowRight" : "") }, diagram);
      svg("rect", { x: point.x, y: point.y, width: point.width, height: point.height, rx: 10 }, group);
      const tooltip = svg("title", {}, group); tooltip.textContent = edits.value(node.id, "label", canonicalLabel(node.id, node.label), node.label);
      const label = svg("text", { x: point.x + 12, y: point.y + 24 }, group);
      point.lines.forEach((line, index) => { const span = svg("tspan", { x: point.x + 12, dy: index ? 18 : 0 }, label); span.textContent = line + (point.truncated && index === point.lines.length - 1 ? "…" : ""); if (span.getComputedTextLength() > point.width - 24) { span.setAttribute("textLength", point.width - 24); span.setAttribute("lengthAdjust", "spacingAndGlyphs"); } });
      if (child) { const hint = svg("text", { x: point.x + point.width - 22, y: point.y + point.height - 12 }, group); hint.textContent = "↗"; }
      editable(label, node.id, "label", canonicalLabel(node.id, node.label), node.label);
      group.addEventListener("click", () => select(node.id));
      group.addEventListener("dblclick", () => open(child));
      group.addEventListener("keydown", event => {
        if (event.key === "Enter" || event.key === " ") { event.preventDefault(); select(node.id); }
        if (event.key === "F2") { event.preventDefault(); edits.edit(node.id, "label", canonicalLabel(node.id, node.label), node.label); }
        if (event.key === "ArrowRight") { event.preventDefault(); open(child); }
      });
    }
    sizing();
    $("viewport").scrollTo(0, 0);
    if (selected) select(selected);
  }
  function back() { if (route.length > 1) { route.pop(); selected = null; zoom = 1; render(); } }
  $("back").addEventListener("click", back);
  $("search").addEventListener("input", tree);
  $("zoom-in").addEventListener("click", () => { zoom = Math.min(64, zoom * 1.25); sizing(); });
  $("zoom-out").addEventListener("click", () => { zoom = Math.max(.25, zoom / 1.25); sizing(); });
  $("fit").addEventListener("click", () => { zoom = 1; sizing(); $("viewport").scrollTo(0, 0); });
  document.addEventListener("keydown", event => { if (event.altKey && event.key === "ArrowLeft") { event.preventDefault(); back(); } });
  new ResizeObserver(sizing).observe($("viewport"));
  const viewport = $("viewport");
  let drag = null;
  viewport.addEventListener("pointerdown", event => {
    if (event.pointerType !== "mouse" || event.button !== 0 || event.target.closest(".node,.edge")) return;
    drag = {x:event.clientX,y:event.clientY,left:viewport.scrollLeft,top:viewport.scrollTop};
    viewport.setPointerCapture(event.pointerId); viewport.classList.add("dragging");
  });
  viewport.addEventListener("pointermove", event => {
    if (!drag) return;
    viewport.scrollLeft = drag.left - event.clientX + drag.x;
    viewport.scrollTop = drag.top - event.clientY + drag.y;
  });
  const endDrag = () => { drag = null; viewport.classList.remove("dragging"); };
  viewport.addEventListener("pointerup", event => {
    if (viewport.hasPointerCapture(event.pointerId)) viewport.releasePointerCapture(event.pointerId);
    endDrag();
  });
  viewport.addEventListener("pointercancel", endDrag);
  viewport.addEventListener("lostpointercapture", endDrag);
  viewport.addEventListener("keydown", event => {
    if (event.key === "+" || event.key === "=") { event.preventDefault(); $("zoom-in").click(); }
    if (event.key === "-") { event.preventDefault(); $("zoom-out").click(); }
    if (event.key === "0") { event.preventDefault(); $("fit").click(); }
  });
  function applyViewLink() {
    const requested = new URLSearchParams(location.hash.slice(1)).get("view");
    if (!requested || !views.has(requested) || !model.diagramViews.length) return;
    const queue = [[model.diagramViews[0].id]], seen = new Set();
    while (queue.length) {
      const path = queue.shift(), id = path[path.length-1];
      if (seen.has(id)) continue;
      seen.add(id);
      if (id === requested) { route = path; selected = null; zoom = 1; return; }
      for (const child of views.get(id).childRefs) if (views.has(child)) queue.push([...path, child]);
    }
  }
  window.addEventListener("hashchange", () => { applyViewLink(); render(); });
  applyViewLink();
  edits.onChange(() => { render(); if(selected) select(selected); });
  render();
})();
