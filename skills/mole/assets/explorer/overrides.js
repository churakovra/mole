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
  function validate(raw) {
    if (typeof raw !== "string" || raw.length > 2000000) throw new Error("Edit file exceeds size limit");
    const stored = JSON.parse(raw);
    if (stored.schemaVersion !== 1 || typeof stored.artifactId !== "string" || !Array.isArray(stored.fields) || stored.fields.length > 10000) throw new Error("Incompatible edit file");
    const seen = new Set();
    for (const field of stored.fields) {
      if (!field || typeof field.targetId !== "string" || !allowed.has(field.fieldPath) ||
          typeof field.baseFieldHash !== "string" || typeof field.value !== "string" || field.value.length > 10000 ||
          (field.baseValue !== undefined && (typeof field.baseValue !== "string" || field.baseValue.length > 10000))) throw new Error("Invalid edit field");
      const identity = JSON.stringify([field.targetId, field.fieldPath]);
      if (seen.has(identity)) throw new Error("Duplicate edit field");
      seen.add(identity);
    }
    return stored;
  }
  function exportText() { return JSON.stringify({schemaVersion:1, artifactId, baseRevision:model.revision, fields:[...fields.values()]}); }
  function persist() {
    try {
      const encoded = JSON.stringify({schemaVersion:1, artifactId, baseRevision:model.revision, fields:[...fields.values()]});
      if (encoded.length > 2000000 || fields.size > 10000) throw new Error("storage limit");
      localStorage.setItem(key, encoded);
      return true;
    } catch { return false; }
  }
  function importText(raw, allowDifferentArtifact = false, replace = false) {
    const stored = validate(raw);
    if (stored.artifactId !== artifactId && !allowDifferentArtifact) throw new Error("Different artifact: explicitly allow migration first");
    const ids = new Set(["symbols","operations","relationships","claims","scenarios","glossary"].flatMap(group => model[group].map(item => item.id)));
    const next = replace ? new Map() : new Map(fields);
    for (const record of stored.fields) {
      if (!ids.has(record.targetId)) throw new Error("An imported target is absent from this snapshot");
      const identity = JSON.stringify([record.targetId, record.fieldPath]);
      if (!replace && next.has(identity) && JSON.stringify(next.get(identity)) !== JSON.stringify(record)) throw new Error("Existing edit differs; explicitly select replacement");
      next.set(identity, record);
    }
    const encoded = JSON.stringify({schemaVersion:1,artifactId,fields:[...next.values()]});
    if (encoded.length > 2000000 || next.size > 10000) throw new Error("Merged edits exceed storage limits");
    fields.clear(); for (const [identity, record] of next) fields.set(identity, record);
    conflicts.clear(); const saved = persist(); changed();
    message(saved ? "Imported edits saved in this browser. Check affected fields for generated-content conflicts." : "Imported edits are in memory only; browser storage is unavailable.");
  }
  function load() {
    try {
      const raw = localStorage.getItem(key);
      if (!raw) return;
      const stored = validate(raw);
      if (stored.artifactId !== artifactId) throw new Error("artifact");
      for (const field of stored.fields) fields.set(JSON.stringify([field.targetId, field.fieldPath]), field);
    } catch { message("Local edits could not be loaded: storage is blocked, malformed, or incompatible. Generated content remains available."); }
  }
  function value(id, field, generated, display = generated) {
    const record = fields.get(JSON.stringify([id, field]));
    if (!record) return display;
    if (record.baseFieldHash !== hash(generated) && record.value !== generated) {
      conflicts.add(JSON.stringify([id, field]));
      message("Conflicting local edits retained: generated fields changed. Review or edit the affected fields.");
    } else {
      conflicts.delete(JSON.stringify([id, field]));
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
    const record = fields.get(JSON.stringify([id, field]));
    const conflict = record && record.baseFieldHash !== hash(generated) && record.value !== generated;
    if (conflict) {
      const heading = document.createElement("h2"); heading.textContent = "Generated field changed";
      const before = document.createElement("p"); before.textContent = "Previous generated value: " + (record.baseValue ?? "Unavailable in older edits; hash " + record.baseFieldHash);
      const current = document.createElement("p"); current.textContent = "Current generated value: " + generated;
      dialog.append(heading, before, current);
    }
    const useGenerated = document.createElement("button"); useGenerated.type = "button"; useGenerated.id = "mole-use-generated"; useGenerated.textContent = "Use generated";
    useGenerated.hidden = !record;
    useGenerated.addEventListener("click", () => {
      const identity = JSON.stringify([id, field]); fields.delete(identity); conflicts.delete(identity);
      const saved = persist(); dialog.close(); changed();
      message(saved ? "Using the generated value." : "Using generated value in memory only; storage is unavailable.");
    });
    const save = document.createElement("button"); save.type = "button"; save.id = "mole-save"; save.textContent = conflict ? "Keep my edit" : "Save";
    const cancel = document.createElement("button"); cancel.type = "button"; cancel.textContent = "Cancel";
    cancel.addEventListener("click", () => dialog.close());
    save.addEventListener("click", () => {
      const identity = JSON.stringify([id, field]);
      fields.set(identity, {targetId:id, fieldPath:field, baseFieldHash:hash(generated), baseValue:String(generated).slice(0,10000), value:input.value,
        baseRevision:model.revision, changedAt:new Date().toISOString(), origin:"browser"});
      conflicts.delete(identity);
      const saved = persist();
      dialog.close(); changed();
      message(saved ? (conflicts.size ? "Local edit saved; other generated-field conflicts remain." : "Local edit saved in this browser.") : "Could not save to storage. This edit is in memory only.");
    });
    dialog.append(label, input, save, useGenerated, cancel); document.body.append(dialog); dialog.showModal(); input.focus();
  }
  function transfer(importing) {
    document.getElementById("mole-transfer")?.remove();
    const dialog = document.createElement("dialog"); dialog.id = "mole-transfer";
    const label = document.createElement("label"); label.textContent = importing ? "Paste an exported edits JSON file" : "Copy edits JSON to a file to move or back up your changes";
    const input = document.createElement("textarea"); input.id = "mole-transfer-value"; label.htmlFor = input.id;
    input.maxLength = 2000000; input.value = importing ? "" : exportText(); input.readOnly = !importing;
    const migrationLabel = document.createElement("label"), migration = document.createElement("input"); migration.type = "checkbox"; migration.id = "mole-migrate";
    migrationLabel.append(migration, " Allow migration from another artifact (matching targets required)");
    const replaceLabel = document.createElement("label"), replace = document.createElement("input"); replace.type = "checkbox"; replace.id = "mole-replace-edits";
    replaceLabel.append(replace, " Replace current edits with imported edits");
    const status = document.createElement("p"); status.setAttribute("role", "status"); status.id = "mole-transfer-status";
    const action = document.createElement("button"); action.type = "button"; action.id = "mole-transfer-action"; action.textContent = importing ? "Import" : "Select JSON";
    action.addEventListener("click", () => {
      if (!importing) { input.focus(); input.select(); return; }
      try { importText(input.value, migration.checked, replace.checked); dialog.close(); }
      catch(error) { status.textContent = "Import rejected: " + error.message; }
    });
    const close = document.createElement("button"); close.type = "button"; close.textContent = "Close"; close.addEventListener("click", () => dialog.close());
    dialog.append(label, input);
    if (importing) dialog.append(migrationLabel, replaceLabel);
    dialog.append(status, action, close); document.body.append(dialog); dialog.showModal(); input.focus();
  }
  document.getElementById("export-edits").addEventListener("click", () => transfer(false));
  document.getElementById("import-edits").addEventListener("click", () => transfer(true));
  load();
  return {value, edit, exportText, importText, onChange: callback => {changed = callback;}};
})();
