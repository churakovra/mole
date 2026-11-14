# V2 delivery and process map contract

## Built-in presentation

MOLE renders its canonical `ProcessGraph` with the bundled offline explorer. The
host agent authors evidence-backed process meaning; do not replace the renderer
or generate a second diagram representation. A normal “explain how this service
works” request asks for an interactive HTML map plus a concise explanation.
Honor explicit text-only or other format requests.

## Canonical graph

Read the [process graph contract](process-graph.md) and
[`process-graph.v1.schema.json`](../schemas/process-graph.v1.schema.json).
Author these groups:

- `processes`: meaningful user/business outcomes, triggers, actors, conditions,
  outcomes, unknowns, operation/claim references and a `handoffReview`.
- `steps`: ordered, concise actions within one process, each linked to source
  operations, claims and evidence.
- `stepTransitions`: explicit paths between steps, labeled with branch or
  condition details and supported by evidence-backed claims.
- `processHandoffs`: explicit event/data/actor links between processes, with
  their own kind, label, condition, resolution, evidence and limitations.
- `hierarchy`: use only when one process is a meaningful subprocess of another;
  do not use it to imply execution order.

Transitions and handoffs are not inferred from array order, shared operation
names or visual grouping. Include a connected failure step when evidence
establishes that path. Keep independent processes separate. For undocumented,
dynamic or runtime behavior, preserve the unknown or mark documented intent;
never invent a connector.

## Relationship confidence and delivery

An `inferred` relationship may appear in the explorer as a possibility, with its
uncertainty visible. It does not satisfy the `supported_process_handoffs`
delivery requirement. `observed_static` must reflect an actual static source
relationship. `observed_runtime` requires a cited runtime trace and a reviewed
runtime claim. `documented_intent` remains explicitly labeled as documented
intent. A process with no outgoing handoff must have a deliberate
`handoffReview.status` such as `independent` or `terminal`; `unknown` remains an
open requirement. Downgraded or contradicted claims withdraw dependent arrows
without erasing the authored record.

## Usability and evidence

Keep titles short. Put explanation in claims and step descriptions, conditions
in transition fields, and limitations in their explicit fields. Every process
must open to its steps; each step should lead to useful source details where
the evidence permits. Verify that selecting a process, opening evidence and
returning to the parent work in a browser when available. Without a browser,
report interaction checks as unverified. A generated file or machine-ready
status does not establish business correctness or visual usability; the owner
performs product acceptance.
