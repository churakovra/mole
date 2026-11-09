# Local task protocol

All commands below use `python3 <ABSOLUTE_SKILL_DIR>/scripts/mole.py`.

1. `doctor --json` checks the interpreter.
2. `start --repo <REPO> --workspace <WORKSPACE> --mode standard --scope repository --json`
   creates or resumes a session. Prefer an external workspace for read-only analysis.
3. `next --workspace <WORKSPACE> --json` scans once and returns the highest-priority
   pending task. Repeated next is safe and does not complete tasks.
4. `inspect --workspace <WORKSPACE> --task <TASK_ID> --budget-chars 12000 --json`
   returns source-located context. Continue with `--cursor <nextCursor>` until null.
5. Write a semantic-patch JSON file and pass it to
   `submit --workspace <WORKSPACE> --input <PATCH_FILE> --json`.
   Use protocolVersion `1.0`, taskId, baseRevision, and a nonempty claims array.
   Each claim has id, statement, status, evidenceIds, limitations.
   Cite only evidence IDs on that task. Prefer `unknown` with a limitation to
   guessing. Never claim runtime verification from source code alone.
6. Repeat until status is VALIDATING. Use `status` to resume after interruption.
7. `finish --workspace <WORKSPACE> --output <OUTPUT_DIR> --json` compiles
   Markdown, offline HTML and draw.io. Use a dedicated output directory.
   `--format markdown` selects Markdown alone; repeat `--format` to add html,
   drawio or mermaid. If quality gates report pending tasks or reduced coverage,
   explain the limitations and use `--allow-partial` only for an appropriate
   partial deliverable. Never describe PARTIAL as complete coverage.
8. For changed inputs, `diff --workspace <WORKSPACE> --json` reports changes;
   `update --workspace <WORKSPACE> --json` refreshes evidence and tasks. Continue
   the task loop and run finish/export. Identical repeats are safe.

Scope is `repository` or a repository-relative file/directory. Choose a narrow
path scope when it covers the user's question. A broader scope must not imply
complete behavior coverage. Document-only inputs support intended workflows;
unsupported programming languages remain reduced-coverage text review.

OUTPUT_CONFLICT requires preserving authored content and resolving the conflict
or selecting a new directory. Do not delete/edit manual notes to force success.
Browser overrides are local presentation edits, not shared or canonical changes.
Use the explorer's Export edits to copy a portable JSON backup, then Import edits
in another browser. Imports validate size, version, fields and matching target
IDs; migration from a different artifact and replacement of existing edits each
require an explicit checkbox. Conflicts retain authored text and show previous
and current generated values; choose Keep my edit or Use generated. Older edit
files may have only a previous-value hash. Browser storage under file:// varies;
JSON backups are the portable transfer mechanism. A selected node has visible
Edit and Open details controls for touch as well as keyboard/double-click paths.

Duplicate identical patches are safe; changed duplicate responses conflict.
Changed source returns TASK_STALE; refresh before resubmitting. Quality gates
and export are owned by the engine. Completion must not be inferred from the chat.
quick/standard/deep limit semantic task counts to 20/100/500 respectively;
truncation is explicitly recorded as a limitation, not full coverage.
No LLM API calls occur inside the engine.

## Named scenarios, business mappings and glossary

Patches may additionally include `scenarios`, `businessSteps` and `glossary`
arrays following the bundled semantic-patch schema. Their IDs must start with
`semantic-`; they must cite claims in the same patch. Scenario and business-step
operationIds must belong to the task's evidence. Inspect returns bounded operation
IDs/titles. `next.task` previews at most 30 operation/evidence IDs and includes
their full counts; the stored task remains complete. For every operation use
`inspect --cursor ops:0` and follow `nextCursor` until null. Source pages use
the separate `0:0` cursor stream. Do not guess IDs or treat a preview as complete.

Each scenario includes title, trigger, operationIds, claimIds, outcomes and
unknowns. State an explicit unknown boundary when no outcome is established.
Business steps include what, why, operationIds and claimIds. Glossary terms
include term, definition and claimIds. Preserve inferred/unknown claim status
instead of presenting names or documentation as proof of runtime behavior.
Unassociated accepted meaning remains in the quality report. Changes invalidating
its supporting claims reopen the task and invalidate dependent authored knowledge.

## Coverage and explicit claim review

`technicalAnalysis`, `semanticCoverage` and `export` are separate quality outcomes.
Completing tasks alone does not establish semantic completion. Missing authored
actors, preconditions, steps, outcomes or failure boundaries, unknown claims,
unresolved calls and reduced source coverage keep the result PARTIAL.
Material delivery/transaction/retry guarantees create a `claim_review` task.
Its patch uses `claims: []` and `review: {claimIds, evidenceIds, rationale,
verdict}`; verdict is supported, unknown or contradicted. A supported verdict
requires cited task evidence. This records an explicit agent review, not an
independent proof of runtime behavior. Never upgrade an unsupported guarantee.

## Output generations and recovery

`finish` returns `output`, the complete active bundle, and `logicalOutput`, its
container. Open `MOLE-OPEN.html` or resolve `current.json` once to select a bundle.
Files live under `.mole-generations/<generation>/`; the single pointer publication
is the commit point. Previous generations and manual notes are retained.
The workspace uses content-addressed `.objects` with a small state.json pointer;
copy the whole workspace to preserve it. Version-1 workspaces load and migrate
on the next save; unknown workspace formats are rejected.

Retry an interrupted export with the same options. `--restart-export` explicitly
abandons unpublished staging when options/notes changed. `update` reconciles a
published pointer or abandons unpublished staging before refreshing changed
sources. No prior generation is deleted. Another workspace must use a new output
or explicitly `--adopt-output`; the repository/scope must still match. Withdrawn
formats disappear from the new generation and remain in the previous one, listed
by its retirement manifest. Legacy root files are retained during migration.
Unpublished `.stage-*` directories are not active bundles and may be removed
manually after preserving any edits. JSON quality/loss sidecars describe limits.
