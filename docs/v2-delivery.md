# Goal completion, presentation and reuse

New investigations use `begin --request request.json`; v1 `start/finish` remains
compatible. The host agent supplies meaning and authored claims. The deterministic
engine never calls a model or executes the target.

`check --workspace PATH --json` is read-only. It reports current goal criteria,
missing requirements, evidence versus repository coverage and blockers. A task
queue finishing is not goal completion. `complete --workspace PATH --answer
answer.json [--output PATH] --json` validates the bundled answer-draft.v1 schema,
request and source revision, accepted claims, cited source paths/spans, relevant
material-claim reviews and requested output. A trace must begin at an original
query anchor and follow indexed edges within admitted bounds. Hypotheses cite
known evidence, remain unverified, and name next checks. Static sources cannot
satisfy typed runtime guarantees.

Chat answers create no output folder. Artifacts use the existing atomic generation
publisher. Publication intent includes request, answer and semantic snapshot
hashes. All manifest-owned files are checked, including linked documents.
Changing source, semantics, answer or files revokes readiness. Partial delivery
requires explicit PARTIAL/BLOCKED outcome, limitations and `--allow-partial`;
READY_TO_PRESENT is never a forced-completion flag. Interrupted publication can
retry unchanged or use `--restart-export` after correcting input. Preserve the
workspace, active generation and authored notes.

The HTML explorer includes the original redacted question and answer. Orientation
starts with business processes; focused maps/trace start with the matching process
when present. Process handoffs and step transitions retain provenance, conditions
and branches. Static, documented and inferred edges have accessible evidence
labels and different line patterns. Unknown boundaries remain explicit. Source
locators degrade to text across incompatible volumes. Browser-local edits are
presentation only.

A follow-up is another `begin` request with `action: "followUp"`,
`parentRequestId`, `turnId` and a new question. Omitted intent, focus and constraints
inherit; explicit replacements win. Source freshness is checked before sharing
immutable semantic knowledge. Original goals and answers remain independent;
no READY state is inherited. Use a new requestId or allow deterministic allocation.
A stale parent must be updated first.

`update` retains claims only when cited evidence and their authoring task scopes
remain unchanged, with unchanged parser version. It retains grounded legacy
meaning and canonical processes; affected claims/links are withdrawn and handoff
reviews reopen. New snapshots validate before the session pointer is saved.
Old source, semantic and answer hashes stay in history. Renames conservatively
invalidate v2 meaning; no identity is guessed. Full inventory freshness checks
remain enabled: performance has not been traded for stale-proof risk.

Machine checks verify structure, provenance and files, not semantic truth or
human usefulness. Model self-review is not an independent human grade. Browser
usability and business correctness still need the test handoff described in
[UX evaluation](ux-evaluation.md).
