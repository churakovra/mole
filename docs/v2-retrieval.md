# Deterministic question-aware retrieval

The host chooses intent, focus, topics and direction. The engine does lexical,
exact-route and exact-symbol matching, then bounded traversal of the existing
static graph. It does not interpret business meaning or call an LLM/embedding
service. Assertions still need inspected source and accepted claims.

An optional request `search` object follows `search-query.v1.schema.json`:
`text`, `focusSymbols`, `paths`, `routeHints`, `topics`, `direction`, `limit`,
`maxDepth`, `maxNodes`, `maxEdges`. Lists contain at most 32 bounded strings;
direction is forward/reverse/both/none. Node/depth/seed limits are capped by the
admitted request. There is no second queue or additional probe command.

`next --workspace WORKSPACE --query QUERY.json --json` adds a justified probe to
the same queue. It preserves original request/hash, accepted knowledge and old
tasks, and rejects extension past the round limit. Equivalent probes reuse IDs.
V1 workspaces reject this flag. Query JSON is bounded, validated and redacted;
it is data, not a command.

## Ranking and boundaries

Exact method/path routes rank above exact qualified/basename symbols, followed
by lexical tokens and labeled curated candidate expansion. Snake/camel tokens,
source paths, operation kinds, static channel names, and bounded redacted
document headings participate. An unmatched route never falls back to an
unrelated handler with the same method. Root `/` is exact too. Router mounting
and runtime deployment remain unproven.

Symbol ambiguity is detected before seed truncation, with bounded ID/title
previews and full match counts. The engine never silently chooses one equally
matching independent declaration. Resolve it using context or a clarification.

Answer scope constrains seeds. Traversal can follow source relationships outside
that directory when index scope includes them. Limited indexing/missing
dependencies stay explicit. Unsupported languages remain text/intent evidence.
Negative results describe indexed search scope, not runtime nonexistence.

Nodes, edges, depth, discovered queue and frontier previews are bounded.
Relationships retain original endpoints/kind/resolution without dangling IDs.
Frontiers identify omitted candidates; `frontierCount` counts boundary records,
not necessarily unique symbols. Large frontiers and ambiguities disclose preview
truncation/counts. Budget gaps remain PARTIAL rather than asserting no link.

Replies include goal/deliverable and a roughly 4 KiB search preview prioritizing
ambiguity. Task evidence is paginated; inspect reserves its full header first.
Tasks contain at most 30 operations. Selected graphs reference the shared source
snapshot rather than storing another copy of its relationships.

Parser v9 adds index-scope metadata and bounded redacted document headings. Old
parser-bound work requires update/review, with prior snapshots retained.
Headings improve search without asserting semantic truth.

## Performance evidence

`tools/benchmark_retrieval.py --symbols 10000|50000 --output PATH` measures a
synthetic star, including the model in peak Python allocation. It measures
response bounds, not semantic recall, real-source accuracy, CLI latency or token
savings. Full lexical/adjacency indexing still uses memory proportional to the
graph. Actual versioned measurements are retained with implementation evidence.
