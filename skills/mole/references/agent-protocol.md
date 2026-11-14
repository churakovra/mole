# Local task protocol

New investigations use the v2 goal protocol: `begin --repo <REPO> --workspace <WORKSPACE> --request <REQUEST_JSON> --json`, then `next/inspect/submit`, `check`, and `complete --answer <ANSWER_JSON> [--output <OUTPUT_DIR>]`. Requests use `schemas/analysis-request.v2.schema.json`; answers use `schemas/answer-draft.v1.schema.json`; canonical maps use [process graphs](process-graph.md). `check` is read-only. `complete` binds the answer and output generation to current source and semantics. Chat requires no export. Review material claims returned as `claim_review` tasks. For a deliberately limited result, state PARTIAL and limitations and use `--allow-partial`. After an interrupted artifact build whose intent changed, `complete --restart-export` safely restarts publication while preserving active generations and authored content.

## Legacy v1 compatibility


All commands below use `python3 <ABSOLUTE_SKILL_DIR>/scripts/mole.py`.

First establish original question, scope and required deliverable using
[delivery recipes](delivery-recipes.md). The task loop below is the v1 mechanical
protocol, not permission to expand a narrow question or force an export. For
chat-only goals, stop semantic investigation when the bounded answer is supported
and disclose its limits; for required artifacts, intermediate prose is not
delivery. After each meaningful stage reassess the original goal. Before final
presentation validate source freshness, claim support, format, artifact
existence/openability and important unknowns. After two rounds without new
evidence or a justified hypothesis, report a concrete blocker instead of looping.

1. `doctor --json` checks the interpreter.
2. `start --repo <REPO> --workspace <WORKSPACE> --mode standard --scope repository --json`
   creates or resumes a session. Prefer an external workspace for read-only analysis.
3. `next --workspace <WORKSPACE> --json` scans once and returns the highest-priority
   pending task. Repeated next is safe and does not complete tasks.
   When overview documents exist, a grouped service-orientation task comes first.
   Use it to author the opening business map as documented intent, then refine
   those processes with source-backed tasks; it does not establish source coverage.
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

For advanced v2 investigations, canonical process authoring uses the separate
[process graph contract](process-graph.md). V1 workflows below remain compatible.

## Named scenarios, business mappings and glossary

For a service explanation, author `scenarios` with ordered plain-language `steps`;
these form the process diagrams, with each step linking to its implementation.
Actors, trigger, outcomes, conditions and failure boundaries appear in the explorer.
Step connectors represent authored transitions, not verified execution; preserve
asynchronous and conditional boundaries in the descriptions and conditions.
Author `links: [{targetScenarioId, label, condition, claimIds}]` for inter-process
handoffs and `stepTransitions: [{fromStep, toStep, label, condition, claimIds}]`
for actual paths inside a process. Step indexes are zero-based, local to `steps`
and stable under append-only amendments. Multiple steps can use the same document
operation as evidence. Include failure outcomes as steps if they need connectors.
The renderer does not infer transition topology from array order. Each connection
must cite evidence-backed claims in its scenario; unknown or contradicted claims
cannot establish a new connector. If explicit claim review later downgrades a
supporting claim, the authored link remains for review but its arrow is withdrawn.
`addLinks` and `addStepTransitions` extend these arrays through normal amendments.
Patches may additionally include `businessSteps` and `glossary`
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

Later related tasks may append to an existing authored scenario. Inspect with
`--cursor scenes:0` and follow `nextCursor` for related scenario IDs and
`expectedHash` values. Add `scenarioAmendments` to a normal claims patch, using
`scenarioId`, `expectedHash`, `addOperationIds` and `addClaimIds`. Optional
`addSteps`, `addFailurePaths`, `addActors`, `addPreconditions`, `addStateEffects`,
`addOutcomes` and `addUnknowns` append without deleting prior meaning. Added
claims/operations must belong to the current task; existing operations must
overlap or connect through an observed static relationship. Stale hashes and
unrelated scopes are rejected without changing the workspace. This is a bounded
extension mechanism, not permission to rewrite earlier claims or erase unknowns.

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


## Bounded control flow and deferred scopes (0.1.0)

Parser v9 reconstructs argument evaluation, branch joins, loop back/exit paths,
and break/continue/return/raise boundaries from source AST. These are static
candidates. Context managers, comprehensions, lazy expressions, complex finally
completion and other unsupported regions produce explicit coverage limitations;
they do not establish runtime behavior. A parser-version update reopens semantic
review rather than silently retaining the previous graph.

Stacked HTTP routes have method/path-specific identities. A statically known
local router prefix is included; mounted router prefixes and deployment remain
unverified. Dynamic methods/paths stay explicitly unknown. Decorator/default
expressions are declaration evidence. `Depends` configuration is associated
with its callable through `dependency_declaration`, not an invocation-body
edge; injection order, runtime execution and cleanup lifecycle require review.
Document headings are redacted bounded search metadata, not semantic assertions.

Workflow tasks include `limitations` and `deferredOperationIds`. The latter lists
reachable operations omitted by the workflow node budget. They are metadata,
not additional authorized operations: claims and scenario additions must stay in
`operationIds`. `next` returns bounded previews and counts; use
`inspect --cursor deferred:0` and subsequent `nextCursor` values to page the full
omitted list. Narrow the requested repository scope for a complete smaller run.
Node-budget truncation remains a quality limitation even if every selected task
has been answered.

## Answer source locators

AnswerDraft Markdown links use repository-relative source paths and optional
`#LSTART-LEND` anchors, for example a link destination of `app.py#L7-L10`. The path/span
must be covered by evidence cited in assertions. Do not use desktop absolute
paths, `file://`, external URLs or `app.py:7` as link destinations. The artifact
publisher relocates safe source links to the generated output directory; across
incompatible volumes it shows a source locator instead.
