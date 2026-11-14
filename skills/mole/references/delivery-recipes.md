# V2 goal-specific delivery recipes

Use the v2 `begin → next/inspect/submit → check → complete` workflow for every
new request. `doctor --json` checks the installed payload first. The host agent
chooses the user's goal and deliverable; MOLE validates them and preserves
source evidence. Read [the protocol](agent-protocol.md) for paging, recovery and
follow-up rules.

Every request has `requestVersion: "2.0"`, the original `question`, a newly
classified `intent`, and a `deliverable` with `contractVersion: "1.0"`, a
deliverable type, required requirements, and formats. Add audience, scope,
limits, focus and optional mechanical search seeds when useful. See
[`analysis-request.v2.schema.json`](../schemas/analysis-request.v2.schema.json).

## Locate

For “Where is JWT checked?”, use `intent: ["locate"]` and a `chat_answer`
contract requiring `question_answered` and `precise_location`. Inspect the
matching declaration and source evidence. Return its path, relevant lines,
actual behavior and limits. A bounded negative search is not proof that a
symbol or runtime behavior does not exist.

## Explain

For “Explain `verify_jwt`”, use `intent: ["explain"]` and `chat_answer`. Inspect
the function plus only the callers/effects needed to explain its behavior.
Describe purpose, inputs, actions, evidence and unknowns without implying that
the whole repository was covered.

## Trace

For “Trace `POST /orders` to publication”, use `intent: ["trace"]` and a
`chat_answer` with `trace_path` and `source_traceability` requirements. Start
with the route, follow bounded source relationships, and report the sequence,
conditions, effects and static/runtime boundary. Request an interactive map
only when the user asks for one.

## Investigate

For “Why are notifications duplicated?”, use `intent: ["investigate"]` and an
`investigation_report` or `chat_answer` requiring `hypotheses` and
`source_traceability`. Inspect publication, consumption, acknowledgement,
retry and exception paths. Separate evidence for and against each hypothesis;
name unchecked factors. Do not infer exactly-once, atomicity or security from
names or static source alone.

## Service orientation

For “Explain how this service works”, use `intent: ["system_orientation"]` and
an `interactive_process_map` contract with HTML plus the requested text format.
Author business processes, steps, transitions and explicit process handoffs in
the canonical `ProcessGraph`. A prose summary or technical component diagram
alone does not satisfy the map request. Follow [the v2 UX contract](ux-contract.md).

## Document

For “Document the payment pipeline in Markdown and HTML”, use `intent:
["document"]` and `explicit_artifacts` with exactly those requested formats.
Ground each process and assertion in inspected evidence, generate the requested
files with `complete`, then verify their integrity and links. Preserve authored
notes and previous output generations.

## Expected delivery and recovery

After `submit`, use `check` to review unmet requirements. Repair a specific gap
or explain a bounded limitation; do not fill tasks with generic unknowns. Run
`complete` only after checking the original question, cited claims, static vs
runtime scope, process handoffs and remaining gaps. Read-only repeated `next`
or identical `inspect` calls do not count as no progress. Update stale sources
before reusing their evidence. A follow-up is a new request with its own intent
and deliverable; fresh evidence may be reused. The legacy v1 `start/finish`
workflow remains available as a separate compatibility protocol.
