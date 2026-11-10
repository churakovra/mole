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

The stdlib validator implements only the JSON Schema vocabulary actually used
in these bundled contracts. It is not a validator for arbitrary third-party schemas.
Unsupported schema versions are rejected; no migration from unknown versions
is attempted. Semantic IDs are independent of labels and layout coordinates.
