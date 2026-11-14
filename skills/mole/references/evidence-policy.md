# Evidence and SKM v1

The canonical SKM separates source spans, observations, claims, symbols,
operations, relationships, scenarios, business steps, views, glossary,
overrides, revision, and quality findings. Bundled JSON schemas define shapes;
the engine additionally checks IDs, references, revision and provenance.

Static calls are `possible` or `resolved_static`, never automatically
`observed_runtime`. Claims distinguish `source_observed`, `runtime_verified`,
`documented_intent`, `inferred`, `unknown`, and `contradicted`.
Uncertain claims require stated limitations. Runtime verification requires
runtime-trace evidence. A schema-valid patch is not proof of semantic truth.

Agent self-review and supported claim-review verdicts are declarations, not
independent evidence. Investigations must show supporting/opposing facts and
unchecked hypotheses. Do not infer nonexistence from missing static relationships
when dynamic dispatch, restricted indexing or unsupported languages may explain
the gap. Completion must address the user's original question and requested
deliverable; distinguish global coverage limits from a bounded useful answer.

The stdlib validator implements only the JSON Schema vocabulary actually used
in these bundled contracts. It is not a validator for arbitrary third-party schemas.
Unsupported schema versions are rejected; no migration from unknown versions
is attempted. Semantic IDs are independent of labels and layout coordinates.
