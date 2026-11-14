# Delivery and UX contract

## Built-in presentation

Normal generation uses MOLE's bundled explorer template and reusable blocks.
No frontend-design, Sites, template or visualization skill is needed. Author the
semantic content, then use `finish`; do not replace the generated explorer with
a separately designed page. The shipped layout, typography and information
placement are the default for every repository.

Keep step descriptions concise action labels. Put explanations in grounded
claims, conditions in their fields, and supporting details in evidence; do not
pack filenames, caveats or separator symbols into node titles. The renderer
places explanations together in one inspector and evidence/edits in disclosures.
For template maintenance or an explicitly requested redesign, read
[the explorer foundation](explorer-template.md).

## Deliver the process explorer

For requests such as "explain how this service works", deliver a local interactive
HTML explorer, starting with named business processes and drilling into their
steps and implementation. A prose answer or component/file diagram alone does
not fulfill this request. Respect an explicit request for text-only or another format.

First orient from entry points and project documentation: identify what users or
external actors accomplish, the main triggers and outcomes, and the service's
boundaries. Use this to interpret the engine's tasks; its static component groups
are investigation scopes, not the product's business-process names.

Author scenarios with meaningful titles, triggers, actors, preconditions, ordered
`steps` with plain-language descriptions, outcomes and relevant failure paths.
Each step's operation is an evidence anchor for its implementation drilldown.
Author `links` between scenarios for supported handoffs (which event, data or
actor action connects them), and `stepTransitions` for the paths inside each
scenario. Both cite the scenario's claims and carry a short label plus any
condition. Transition `fromStep`/`toStep` are zero-based indexes in that scenario's
`steps`; two steps may share an evidence anchor and still be different nodes.
Represent connected failure outcomes as steps too, with explicit branch edges;
`failurePaths` supplies their explanation. A general limitation is not a branch
condition. Do not infer connectors from array order or names.
Keep separate business processes separate; use scenario amendments when later
tasks supply evidence for the same process. Do not invent flow ordering between
independent processes. Preserve documented intent and unknown boundaries for
unsupported languages rather than silently changing the user's scope to Python.
Read the [semantic-patch schema](../schemas/semantic-patch.v1.schema.json) when constructing these patches.

Continue the inspect/submit loop through the selected scope, then finish with
HTML included. `PARTIAL` after the first scan describes pending work, not a
reason to abandon analysis. If a genuine source or coverage limit prevents full
analysis, export a useful, explicitly partial explorer with `--allow-partial`;
explain what remains unavailable. Do not fill the queue with generic unknown
claims merely to reach export. Follow the protocol's recovery guidance for errors.

Before delivery, check the generated overview, open a process, open one of its
step diagrams, and return to the parent. Check that explanations and evidence
are available and that known process handoffs and decision branches actually
have labeled connectors. A collection of disconnected cards is not a completed
process map when the evidence establishes relationships. If a relationship is
unknown, explain that gap rather than drawing an invented arrow.
Use a browser when available; otherwise report the interaction
check as unverified. Return a clickable absolute link to the generated
`explorer.html` and briefly describe its coverage. Never claim an artifact exists
without a successful export.


## Before presenting

Review the original question, source freshness, material claims, required format,
artifact existence/openability, and remaining gaps. A tool success or exhausted
task queue is not proof that the user got the requested result. Self-review is
not independent proof. Preserve unknowns and distinguish static evidence from
runtime verification. If blocked, identify the missing deliverable and proof.
