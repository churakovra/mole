"use strict";
// Shared presentation blocks. Content stays text, including repository text.
window.moleBlocks = (() => {
  function text(parent, value, tag = "p", className = "") {
    const element = document.createElement(tag);
    element.textContent = value;
    if (className) element.className = className;
    parent.append(element);
    return element;
  }
  function button(parent, label, action, id = "") {
    const element = text(parent, label, "button");
    element.type = "button";
    if (id) element.id = id;
    element.addEventListener("click", action);
    return element;
  }
  function section(parent, title) {
    const element = document.createElement("section");
    element.className = "detail-section";
    parent.append(element);
    text(element, title, "h3");
    return element;
  }
  function disclosure(parent, title) {
    const element = document.createElement("details");
    element.className = "detail-disclosure";
    parent.append(element);
    text(element, title, "summary");
    const body = document.createElement("div");
    element.append(body);
    return body;
  }
  function fields(parent, entries) {
    const list = document.createElement("dl");
    for (const [label, values] of entries) {
      const items = Array.isArray(values) ? values : [values];
      if (!items.some(Boolean)) continue;
      text(list, label, "dt");
      const description = document.createElement("dd");
      for (const item of items) if (item) text(description, item);
      list.append(description);
    }
    if (list.childNodes.length) parent.append(list);
    return list;
  }
  function process(parent, scene, includeTitle = false) {
    if (includeTitle) text(parent, scene.title, "h3");
    fields(parent, [["Why", scene.purpose], ["Starts when", scene.trigger], ["Actors", scene.actors || []],
      ["Preconditions", scene.preconditions || []], ["Outcomes", scene.outcomes || []]]);
    if ((scene.unknowns || []).length) {
      const unknown = section(parent, "Not established");
      for (const value of scene.unknowns) text(unknown, value);
    }
    if ((scene.failurePaths || []).length || (scene.stateEffects || []).length) {
      const extra = disclosure(parent, "Other paths and state changes");
      fields(extra, [["State changes", scene.stateEffects || []],
        ...((scene.failurePaths || []).map(path => [path.condition, path.outcome]))]);
    }
  }
  return { text, button, section, disclosure, fields, process };
})();
