"use strict";
(() => {
  const model = JSON.parse(document.getElementById("mole-model").textContent);
  const $ = id => document.getElementById(id);
  const ns = "http://www.w3.org/2000/svg";
  const views = new Map(model.diagramViews.map(v => [v.id, v]));
  const entities = new Map(["symbols", "operations", "relationships", "claims", "scenarios", "glossary"].flatMap(k => model[k].map(x => [x.id, x])));
  const evidence = new Map(model.evidence.map(x => [x.id, x]));
  const sources = new Map(model.sources.map(x => [x.id, x]));
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
    return (view.childRefs || []).map(id => views.get(id)).find(child => child && child.scenarioIds.some(id => {
      const scenario = entities.get(id);
      return scenario && scenario.operationIds[0] === node.id;
    }));
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
    paragraph(detail, entity.title || entity.qualifiedName || entity.statement || entity.term || entity.kind, "h2");
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
    function branch(id, ancestors, parent) {
      const view = views.get(id);
      if (!view || ancestors.includes(id)) return;
      const list = document.createElement("ul"), item = document.createElement("li");
      const button = document.createElement("button");
      button.textContent = view.title;
      button.type = "button";
      if (id === route[route.length - 1]) button.setAttribute("aria-current", "page");
      button.addEventListener("click", () => { route = [...ancestors, id]; zoom = 1; render(); });
      if (!query || view.title.toLowerCase().includes(query)) item.append(button);
      for (const child of view.childRefs) branch(child, [...ancestors, id], item);
      if (item.childNodes.length) { list.append(item); parent.append(list); }
    }
    if (model.diagramViews.length) branch(model.diagramViews[0].id, [], nav);
    if (model.glossary.length) {
      paragraph(nav, "Glossary", "h2");
      for (const term of model.glossary) {
        const button = document.createElement("button"); button.type = "button";
        button.textContent = term.term; button.addEventListener("click", () => { select(term.id); paragraph($("details"), term.definition); }); nav.append(button);
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
    const positions = new Map(view.nodes.map((node, index) => [node.id, { x: 40 + (index % 3) * 260, y: 40 + Math.floor(index / 3) * 160 }]));
    baseWidth = Math.min(3, Math.max(1, view.nodes.length)) * 260 + 40;
    baseHeight = Math.max(1, Math.ceil(view.nodes.length / 3)) * 160 + 40;
    diagram.setAttribute("viewBox", "0 0 " + baseWidth + " " + baseHeight);
    const defs = svg("defs", {}, diagram);
    const marker = svg("marker", { id: "arrow", viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 6, markerHeight: 6, orient: "auto-start-reverse" }, defs);
    svg("path", { d: "M 0 0 L 10 5 L 0 10 z", fill: "#607c63" }, marker);
    for (const edgeId of view.edgeIds) {
      const edge = entities.get(edgeId), a = edge && positions.get(edge.source), b = edge && positions.get(edge.target);
      if (!a || !b) continue;
      const group = svg("g", { class: "edge", "data-id": edge.id, tabindex: 0, role: "button", "aria-label": edge.kind }, diagram);
      const path = "M " + (a.x + 200) + " " + (a.y + 40) + " C " + (a.x + 240) + " " + (a.y + 40) + "," + (b.x - 40) + " " + (b.y + 40) + "," + b.x + " " + (b.y + 40);
      svg("path", { d: path, "marker-end": "url(#arrow)" }, group);
      svg("path", { d: path, class: "hit" }, group);
      const label = svg("text", { x: (a.x + b.x + 200) / 2, y: (a.y + b.y) / 2 + 28, "text-anchor": "middle" }, group);
      label.textContent = edge.kind;
      group.addEventListener("click", () => select(edge.id));
      group.addEventListener("keydown", event => { if (event.key === "Enter") select(edge.id); });
    }
    for (const node of view.nodes) {
      const point = positions.get(node.id), child = childFor(view, node);
      const group = svg("g", { class: "node", "data-id": node.id, tabindex: 0, role: "button", "aria-label": node.label + (child ? "; open with ArrowRight" : "") }, diagram);
      svg("rect", { x: point.x, y: point.y, width: 200, height: 80, rx: 10 }, group);
      const label = svg("text", { x: point.x + 12, y: point.y + 24 }, group);
      const chunks = node.label.match(/.{1,26}/gu) || [""];
      chunks.slice(0, 3).forEach((line, index) => { const span = svg("tspan", { x: point.x + 12, dy: index ? 17 : 0 }, label); span.textContent = line; });
      if (child) { const hint = svg("text", { x: point.x + 180, y: point.y + 68 }, group); hint.textContent = "↗"; }
      group.addEventListener("click", () => select(node.id));
      group.addEventListener("dblclick", () => open(child));
      group.addEventListener("keydown", event => {
        if (event.key === "Enter" || event.key === " ") { event.preventDefault(); select(node.id); }
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
  $("zoom-in").addEventListener("click", () => { zoom = Math.min(8, zoom * 1.25); sizing(); });
  $("zoom-out").addEventListener("click", () => { zoom = Math.max(.25, zoom / 1.25); sizing(); });
  $("fit").addEventListener("click", () => { zoom = 1; sizing(); $("viewport").scrollTo(0, 0); });
  document.addEventListener("keydown", event => { if (event.altKey && event.key === "ArrowLeft") { event.preventDefault(); back(); } });
  new ResizeObserver(sizing).observe($("viewport"));
  render();
})();
