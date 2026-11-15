# Canonical v2 business process knowledge

The host authors meaning; the engine validates source binding, references,
certainty, ownership and topology. This is separate from extracted operations
and is the canonical business graph for a v2 investigation. Diagram views are
deterministic projections; file/module groups remain technical drilldowns.

Use [ProcessGraph v1](../schemas/process-graph.v1.schema.json) through
[SemanticPatch v2](../schemas/semantic-patch.v2.schema.json). A v2 patch has
`protocolVersion: "2.0"`, requestId, taskId, baseRevision, claims and optional
processGraph. Existing claim-only v1 patches remain compatible. Once canonical
process knowledge exists, author new processes through the v2 contract rather
than adding a second independent legacy scenario representation.

## Entity contract

- Process: `id,title,purpose,trigger,actors,preconditions,stepIds,operationIds,
  claimIds,outcomes,unknowns`; optional handoffReview.
- Step: `id,processId,title,description,kind,operationIds,claimIds,evidenceIds`.
  Kind is action/decision/wait/failure/success/unknown. Steps may share a source
  anchor and remain distinct business nodes.
- StepTransition: `id,fromStepId,toStepId,label,condition,kind,resolution,
  claimIds,evidenceIds,limitations`. Endpoints belong to the same process.
- ProcessHandoff: same relation fields, with fromProcessId/toProcessId instead.
  It crosses distinct processes and never follows implicitly from array order.
- Hierarchy: `id,parentProcessId,childProcessId,claimIds,evidenceIds` and optional
  entryStepId belonging to the child. Parent/child pairs are unique; no cycles.

IDs use process-/step-/transition-/handoff-/hierarchy- prefixes. References point
to existing current-revision source operations, claims and evidence. New meaning
may cite the current task or previously investigated task scopes in this same
request; another request's selected task does not authorize a patch.

Relations distinguish observed_static/documented_intent/inferred/unknown/
observed_runtime. Inferred/unknown relations require explicit limitations.
Observed runtime requires actual runtime-trace evidence; AST is insufficient.
Evidence belongs to endpoint scopes and supporting claims. An unsupported or
downgraded relationship stays canonical for review but produces no established
connector. Do not invent edges between independent capabilities.

HandoffReview explicitly records supported/independent/terminal/unknown status
with supporting claimIds and limitations. It is an agent-authored review, not
independent proof. Goal assessment is introduced in the completion stage.

## Safe incremental patches

ProcessGraph patches contain processGraphVersion `1.0`, current baseRevision
and the groups being authored: processes, steps, stepTransitions,
processHandoffs, hierarchy. New IDs append. Replacing an existing entity requires
the current baseGraphHash. Explicit removeIds also requires that hash, may remove
only canonical graph entities, and must leave no dangling references. Prior
semantic snapshots remain in session history; no source or earlier output is
deleted. A graph-only patch may reuse accepted claims without inventing new ones.
Claim-review tasks cannot author topology.

`status.processGraph` gives the current hash and counts. For full inspection,
use a known task with `inspect --cursor graph:0` and follow nextCursor. The
graphChunk strings concatenate to canonical JSON. Later cursors bind its hash;
concurrent semantic changes reject an old cursor rather than mixing versions.
Pages respect the total reply budget, including goal metadata. Canonical graph
storage is capped at 8 MiB in addition to schema/entity and patch size limits.

Legacy glossary and business mappings remain available in projection. Existing
authored legacy scenarios are not silently converted or suppressed: activating
a nonempty canonical graph in such a session yields SEMANTIC_MIGRATION_REQUIRED.
Preserve that session and create a new canonical investigation against the
shared source store. V1 workspaces/exports keep their original path; no implicit
destructive migration is performed.
