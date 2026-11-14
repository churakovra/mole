"use strict";
(() => {
  const model = JSON.parse(document.getElementById("mole-model").textContent);
  const edits = window.moleOverrides;
  const layouts = JSON.parse(document.getElementById("mole-layouts").textContent);
  const config = JSON.parse(document.getElementById('mole-config').textContent);
  const $ = id => document.getElementById(id);
  const blocks = window.moleBlocks;
  let fitted = false;
  const ns = "http://www.w3.org/2000/svg";
  const views = new Map(model.diagramViews.map(v => [v.id, v]));
  const entities = new Map(["symbols", "operations", "relationships", "claims", "scenarios", "glossary"].flatMap(k => model[k].map(x => [x.id, x])));
  const evidence = new Map(model.evidence.map(x => [x.id, x]));
  const sources = new Map(model.sources.map(x => [x.id, x]));
  const baseWarning = $("warning").textContent;
  let route = views.size ? [model.diagramViews[0].id] : [];
  let selected = null;
  let zoom = 1;
  let baseScale = 1, sizedView = null;
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
  if (config.question) {
    const goal = paragraph(document.querySelector('.process-header'), config.question);
    goal.className = 'request-context';
  }
  if (config.answer) {
    const answer = blocks.disclosure(document.querySelector('.navigation'), 'Investigation answer');
    paragraph(answer, config.answer).className = 'answer-text';
  }
  function childFor(view, node) {
    if (node.childViewId && view.childRefs.includes(node.childViewId)) return views.get(node.childViewId);
    return (view.childRefs || []).map(id => views.get(id)).find(child => child && child.scenarioIds.some(id => {
      const scenario = entities.get(id);
      return scenario && scenario.operationIds[0] === node.id;
    }));
  }
  function canonicalLabel(id, fallback) {
    const entity = entities.get(id);
    if (entity && entity.kind === 'authored_step_sequence') return 'Next step';
    if (entity && ['business_handoff','business_transition'].includes(entity.kind)) return entity.condition;
    if (entity && entity.source && entity.target) return entity.kind + (entity.condition ? ': ' + entity.condition : '');
    return entity ? entity.title || entity.qualifiedName || entity.statement || entity.term || entity.kind || fallback : fallback;
  }
  function editable(element, id, field, base, display = base) {
    element.tabIndex = 0; element.setAttribute("role", "button");
    element.setAttribute("aria-label", "Edit " + field + "; double click or F2");
    element.addEventListener("dblclick", event => {event.stopPropagation(); edits.edit(id, field, base, display);});
    element.addEventListener("keydown", event => {if(event.key === "F2") {event.preventDefault(); event.stopPropagation(); edits.edit(id, field, base, display);}});
  }
  function explainProcess(parent, scene) {
    blocks.process(parent, scene);
    for (const link of [...(scene.links || []), ...(scene.stepTransitions || [])]) {
      if (link.claimIds.some(id => !entities.get(id) || ['unknown','contradicted'].includes(entities.get(id).status))) {
        paragraph(parent, 'Not established: ' + link.label);
      }
    }
  }
  function select(id) {
    selected = id;
    document.querySelectorAll('.selected').forEach(element => element.classList.remove('selected'));
    for (const element of $('diagram').querySelectorAll('[data-id]')) {
      if (element.dataset.id === id) element.classList.add('selected');
    }
    const detail = $('details');
    detail.replaceChildren();
    const entity = entities.get(id);
    if (!entity) return;
    const baseLabel = canonicalLabel(id, id);
    const heading = paragraph(detail, edits.value(id, 'label', baseLabel), 'h2');
    editable(heading, id, 'label', baseLabel);
    const currentView = views.get(route[route.length - 1]);
    const currentNode = currentView && currentView.nodes.find(node => node.id === id);
    const child = currentNode && childFor(currentView, currentNode);
    if (child) blocks.button(detail, 'Open subprocess', () => open(child), 'open-details').className = 'primary-action';
    const directScene = model.scenarios.find(scene => scene.operationIds[0] === id);
    const ids = new Set(entity.evidenceIds || []);
    if (entity.sourceRefs) for (const ev of model.evidence) if (entity.sourceRefs.includes(ev.sourceId)) ids.add(ev.id);
    const supporting = model.claims.filter(claim => entity.claimIds ? entity.claimIds.includes(claim.id) : claim.evidenceIds.some(ev => ids.has(ev)));
    if (directScene) explainProcess(detail, directScene);
    else if (entity.source && entity.target) {
      blocks.fields(detail, [['From', canonicalLabel(entity.source, entity.source)], ['To', canonicalLabel(entity.target, entity.target)]]);
    } else {
      if (entity.condition) blocks.fields(detail, [['Applies when', entity.condition]]);
      const description = edits.value(id, 'description', entity.description || '');
      if (description) blocks.fields(detail, [['What', description]]);
      if (entity.purpose) blocks.fields(detail, [['Why', entity.purpose]]);
      for (const claim of supporting.slice(0, 2)) {
        paragraph(detail, (['unknown', 'contradicted'].includes(claim.status) ? 'Not established: ' : '') + claim.statement);
      }
      if (!description && !supporting.length) paragraph(detail, 'This is a static implementation step. Its business meaning has not been authored.');
    }
    const outgoing = currentView ? currentView.edgeIds.map(eid => entities.get(eid)).filter(edge => edge.source === id) : [];
    if (outgoing.length) {
      const next = blocks.section(detail, 'What happens next'); next.classList.add('next-steps');
      for (const edge of outgoing) blocks.button(next, canonicalLabel(edge.target, edge.target), () => select(edge.target));
    }
    const proof = blocks.disclosure(detail, 'Supporting evidence');
    if (entity.resolution || entity.evidenceStatus) blocks.fields(proof, [['Evidence basis', entity.evidenceStatus || entity.resolution], ['Connection', entity.condition]]);
    for (const claim of supporting) {
      const item = document.createElement('div'); item.className = 'evidence-item'; proof.append(item);
      paragraph(item, claim.status + ': ' + claim.statement);
      for (const limitation of claim.limitations) paragraph(item, 'Limitation: ' + limitation);
    }
    for (const eid of ids) {
      const ev = evidence.get(eid), source = ev && sources.get(ev.sourceId);
      if (!source) continue;
      const item = document.createElement('div'); item.className = 'evidence-item'; proof.append(item);
      blocks.fields(item, [['Source', source.path + ':' + source.lineStart + '–' + source.lineEnd],
        ['Evidence type', ev.classification], ['Observation', ev.observation]]);
      if (typeof config.sourcePrefix === 'string') {
        const link = paragraph(item, 'Open source', 'a');
        link.href = config.sourcePrefix.split('/').map(encodeURIComponent).join('/') + '/' + source.path.split('/').map(encodeURIComponent).join('/');
      }
    }
    for (const scene of model.scenarios) {
      if (!scene.operationIds.includes(id) && !(entity.kind === 'component_summary' && currentView && currentView.scenarioIds.includes(scene.id))) continue;
      const link = paragraph(proof, 'Workflow document: ' + scene.title, 'a');
      link.href = 'processes/' + encodeURIComponent(scene.id) + '.md';
    }
    if (!ids.size) paragraph(proof, 'No direct evidence attached; consult the containing process.');
    const author = blocks.disclosure(detail, 'Notes and edits');
    paragraph(author, 'ID: ' + id);
    blocks.button(author, 'Edit label', () => edits.edit(id, 'label', baseLabel));
    for (const field of ['description', 'notes']) {
      const base = entity[field] || '';
      const value = edits.value(id, field, base);
      if (value) paragraph(author, value);
      blocks.button(author, 'Edit ' + field, () => edits.edit(id, field, base));
    }
  }
  function open(child) {
    if (!child || route.includes(child.id)) return;
    fitted = false;
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
      button.textContent = view.title;
      button.type = "button";
      if (id === route[route.length - 1] && JSON.stringify(ancestors) === JSON.stringify(route.slice(0,-1))) button.setAttribute("aria-current", "page");
      button.addEventListener("click", () => { route = [...ancestors, id]; fitted = false; selected = null; zoom = 1; render(); });
      if (!query || view.title.toLowerCase().includes(query)) item.append(button);
      if (!shared && (query || route.includes(id))) for (const child of view.childRefs) branch(child, [...ancestors, id], item);
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
    const fitScale = Math.min(width / baseWidth, height / baseHeight, 1);
    if (fitted) baseScale = fitScale;
    $('diagram').style.width = baseWidth * baseScale * zoom + 'px';
    $('diagram').style.height = baseHeight * baseScale * zoom + 'px';
    $('zoom-label').textContent = Math.round(zoom * 100) + '%';
    $('fit').hidden = Math.abs(baseScale * zoom - fitScale) < .001;
  }
  function render() {
    const diagram = $("diagram");
    diagram.replaceChildren();
    tree();
    $("back").disabled = route.length < 2;
    const view = views.get(route[route.length - 1]);
    if (!view) { $("title").textContent = "No supported diagram views"; return; }
    if (sizedView !== view.id) { baseScale = 1; sizedView = view.id; }
    $("title").textContent = view.title;
    $('breadcrumbs').replaceChildren();
    for (const [index, vid] of route.slice(0, -1).entries()) {
      blocks.button($('breadcrumbs'), views.get(vid).title, () => { route = route.slice(0, index + 1); selected = null; fitted = false; zoom = 1; render(); });
    }
    $('view-kind').textContent = view.id === model.diagramViews[0].id ? 'Process map' : 'Process flow';
    if (!selected) {
      $("details").replaceChildren();
      paragraph($('details'), 'Process details', 'h2');
      const scenes = view.scenarioIds.map(id => entities.get(id)).filter(Boolean);
      if (scenes.length === 1) explainProcess($('details'), scenes[0]);
      else paragraph($('details'), 'Select a process or step to read its explanation.');
    }
    const geometry = JSON.parse(JSON.stringify(layouts[view.id]));
    const rowCount = Math.max(0, ...Object.values(geometry.nodes).map(point => point.row + 1));
    const rowHeights = Array(rowCount).fill(88);
    for (const node of view.nodes) {
      const point = geometry.nodes[node.id];
      const display = edits.value(node.id, "label", canonicalLabel(node.id, node.label), node.label);
      const lines = display.split(/\r?\n/u).flatMap(line => line.match(/.{1,28}/gu) || [""]);
      point.lines = lines.slice(0,12); point.truncated = lines.length > 12;
      point.height = Math.max(88, 40 + point.lines.length * 18);
      rowHeights[point.row] = Math.max(rowHeights[point.row], point.height);
    }
    const rowTops = [];
    let top = 64;
    for (const height of rowHeights) { rowTops.push(top); top += height + 76; }
    for (const point of Object.values(geometry.nodes)) point.y = rowTops[point.row];
    geometry.height = Math.max(240, top);
    for (const edgeId of view.edgeIds) {
      const edge = entities.get(edgeId), a = geometry.nodes[edge.source], b = geometry.nodes[edge.target];
      const x1 = a.x+a.width, y1 = a.y+a.height/2, x2 = b.x, y2 = b.y+b.height/2;
      const connector = geometry.edges[edgeId];
      if (connector.direct) {
        const middle = (x1+x2)/2;
        connector.d = `M ${x1} ${y1} L ${middle} ${y1} L ${middle} ${y2} L ${x2} ${y2}`;
        connector.x = middle; connector.y = y1-7;
      } else {
        const lane = rowTops[Math.min(a.row,b.row)]-16-connector.track*5;
        connector.d = `M ${x1} ${y1} L ${x1+24} ${y1} L ${x1+24} ${lane} L ${x2-24} ${lane} L ${x2-24} ${y2} L ${x2} ${y2}`;
        connector.x = (x1+x2)/2; connector.y = lane-5;
      }
    }
    const positions = new Map(Object.entries(geometry.nodes));
    baseWidth = geometry.width;
    baseHeight = geometry.height;
    if (!$("warning").textContent) $("warning").textContent = baseWarning;
    diagram.setAttribute("viewBox", "0 0 " + baseWidth + " " + baseHeight);
    const defs = svg("defs", {}, diagram);
    const marker = svg("marker", { id: "arrow", viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 6, markerHeight: 6, orient: "auto-start-reverse" }, defs);
    svg("path", { d: "M 0 0 L 10 5 L 0 10 z", fill: "#839ab9" }, marker);
    for (const edgeId of view.edgeIds) {
      const edge = entities.get(edgeId), a = edge && positions.get(edge.source), b = edge && positions.get(edge.target);
      if (!a || !b) continue;
      const certainty = edge.evidenceStatus || edge.resolution || 'observed_static';
      const group = svg("g", { class: "edge " + certainty, "data-id": edge.id, tabindex: 0, role: "button", "aria-label": canonicalLabel(edge.id,edge.kind) + '; ' + certainty }, diagram);
      const path = geometry.edges[edgeId].d;
      svg("path", { d: path, "marker-end": "url(#arrow)" }, group);
      svg("path", { d: path, class: "hit" }, group);
      const label = svg("text", { x: geometry.edges[edgeId].x, y: geometry.edges[edgeId].y, "text-anchor": "middle" }, group);
      const display = edits.value(edge.id, "label", canonicalLabel(edge.id, edge.kind));
      const available = Math.max(30, Math.min(320, 2*Math.min(geometry.edges[edgeId].x, geometry.width-geometry.edges[edgeId].x)-20));
      const characters = Math.max(3, Math.floor(available/7));
      label.textContent = display.length > characters ? display.slice(0,characters-1) + '…' : display;
      if (label.getComputedTextLength() > available) { label.setAttribute('textLength', available); label.setAttribute('lengthAdjust','spacingAndGlyphs'); }
      svg('title', {}, group).textContent = display;
      editable(label, edge.id, "label", canonicalLabel(edge.id, edge.kind));
      group.addEventListener("click", () => select(edge.id));
      group.addEventListener("keydown", event => { if (event.key === "Enter") select(edge.id); });
    }
    for (const node of view.nodes) {
      const point = positions.get(node.id), child = childFor(view, node);
      const group = svg("g", { class: "node", "data-id": node.id, tabindex: 0, role: "button", "aria-label": edits.value(node.id, "label", canonicalLabel(node.id, node.label), node.label) + (child ? "; open with ArrowRight" : "") }, diagram);
      svg("rect", { x: point.x, y: point.y, width: point.width, height: point.height, rx: 4 }, group);
      const tooltip = svg("title", {}, group); tooltip.textContent = edits.value(node.id, "label", canonicalLabel(node.id, node.label), node.label);
      const label = svg("text", { x: point.x + 12, y: point.y + 24 }, group);
      point.lines.forEach((line, index) => { const span = svg("tspan", { x: point.x + 12, dy: index ? 18 : 0 }, label); span.textContent = line + (point.truncated && index === point.lines.length - 1 ? "…" : ""); if (span.getComputedTextLength() > point.width - 24) { span.setAttribute("textLength", point.width - 24); span.setAttribute("lengthAdjust", "spacingAndGlyphs"); } });
      if (child) { const hint = svg("text", { class: "drill-hint", x: point.x + point.width - 85, y: point.y + point.height - 12 }, group); hint.textContent = "Subprocess"; }
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
  function back() { if (route.length > 1) { route.pop(); selected = null; fitted = false; zoom = 1; render(); } }
  $("back").addEventListener("click", back);
  $("search").addEventListener("input", tree);
  $("zoom-in").addEventListener("click", () => { fitted = false; zoom = Math.min(64, zoom * 1.25); sizing(); });
  $("zoom-out").addEventListener("click", () => { fitted = false; zoom = Math.max(.05, zoom / 1.25); sizing(); });
  $("fit").addEventListener("click", () => { fitted = true; zoom = 1; sizing(); $("viewport").scrollTo(0, 0); });
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
    const requested = new URLSearchParams(location.hash.slice(1)).get("view") || config.initialViewId;
    if (!requested || !views.has(requested) || !model.diagramViews.length) return;
    const queue = [[model.diagramViews[0].id]], seen = new Set();
    while (queue.length) {
      const path = queue.shift(), id = path[path.length-1];
      if (seen.has(id)) continue;
      seen.add(id);
      if (id === requested) { route = path; selected = null; fitted = false; zoom = 1; return; }
      for (const child of views.get(id).childRefs) if (views.has(child)) queue.push([...path, child]);
    }
  }
  window.addEventListener("hashchange", () => { applyViewLink(); render(); });
  applyViewLink();
  edits.onChange(() => { render(); if(selected) select(selected); });
  new MutationObserver(() => {
    if ($('warning').textContent !== baseWarning) { $('coverage-details').open = true; $('coverage-label').textContent = 'Workspace notice'; }
  }).observe($('warning'), {childList: true, characterData: true, subtree: true});
  render();
})();
