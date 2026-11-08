"use strict";
// Field overrides are presentation-only; they never rewrite generated SKM.
window.moleOverrides = (() => {
  const model = JSON.parse(document.getElementById("mole-model").textContent);
  const {artifactId} = JSON.parse(document.getElementById("mole-config").textContent);
  const key = "mole:" + artifactId + ":v1";
  const fields = new Map();
  const conflicts = new Set();
  const allowed = new Set(["label", "description", "notes", "definition", "term"]);
  let changed = () => {};
  function message(text) { document.getElementById("warning").textContent = text; }
  function hash(text) {
    let value = 2166136261;
    for (const char of String(text)) value = Math.imul(value ^ char.codePointAt(0), 16777619);
    return "fnv1a-v1:" + (value >>> 0).toString(16);
  }
  function load() {
    try {
      const raw = localStorage.getItem(key);
      if (!raw) return;
      if (raw.length > 2000000) throw new Error("size");
      const stored = JSON.parse(raw);
      if (stored.schemaVersion !== 1 || stored.artifactId !== artifactId || !Array.isArray(stored.fields) || stored.fields.length > 10000) throw new Error("schema");
      for (const field of stored.fields) {
        if (!field || typeof field.targetId !== "string" || !allowed.has(field.fieldPath) ||
            typeof field.baseFieldHash !== "string" || typeof field.value !== "string" || field.value.length > 10000) throw new Error("field");
      }
      for (const field of stored.fields) fields.set(JSON.stringify([field.targetId, field.fieldPath]), field);
    } catch { message("Local edits could not be loaded: storage is blocked, malformed, or incompatible. Generated content remains available."); }
  }
  function value(id, field, generated, display = generated) {
    const record = fields.get(JSON.stringify([id, field]));
    if (!record) return display;
    if (record.baseFieldHash !== hash(generated) && record.value !== generated) {
      conflicts.add(JSON.stringify([id, field]));
      message("Conflicting local edits retained: generated fields changed. Review or edit the affected fields.");
    }
    return record.value;
  }
  function edit(id, field, generated, display = generated) {
    if (!allowed.has(field)) return;
    const existing = document.getElementById("mole-editor");
    if (existing) existing.remove();
    const dialog = document.createElement("dialog"); dialog.id = "mole-editor";
    const label = document.createElement("label"); label.textContent = "Edit " + field + " (local to this browser)";
    const input = document.createElement("textarea"); input.id = "mole-edit-value"; input.maxLength = 10000;
    input.value = value(id, field, generated, display); label.htmlFor = input.id;
    const save = document.createElement("button"); save.type = "button"; save.id = "mole-save"; save.textContent = "Save";
    const cancel = document.createElement("button"); cancel.type = "button"; cancel.textContent = "Cancel";
    cancel.addEventListener("click", () => dialog.close());
    save.addEventListener("click", () => {
      const identity = JSON.stringify([id, field]);
      fields.set(identity, {targetId:id, fieldPath:field, baseFieldHash:hash(generated), value:input.value,
        baseRevision:model.revision, changedAt:new Date().toISOString(), origin:"browser"});
      conflicts.delete(identity);
      let saved = true;
      try {
        const encoded = JSON.stringify({schemaVersion:1, artifactId, baseRevision:model.revision, fields:[...fields.values()]});
        if (encoded.length > 2000000 || fields.size > 10000) throw new Error("storage limit");
        localStorage.setItem(key, encoded);
      } catch { saved = false; }
      dialog.close(); changed();
      message(saved ? (conflicts.size ? "Local edit saved; other generated-field conflicts remain." : "Local edit saved in this browser.") : "Could not save to storage. This edit is in memory only.");
    });
    dialog.append(label, input, save, cancel); document.body.append(dialog); dialog.showModal(); input.focus();
  }
  load();
  return {value, edit, onChange: callback => {changed = callback;}};
})();
