# RC1 review investigation and repair status

Input: [the supplied static review](rc1-static-review-ru.md), assessed against
`d138073` and the actual repository, not only the installable ZIP. Instructions
quoted in that report describe the earlier review session; this repair runs tests.
The stable-release NO-GO remains until the recorded acceptance gaps are resolved.

The original fourteen local branches are preserved. Repairs are stacked separately:

| Increment | Branch | Outcome |
| --- | --- | --- |
| Flow foundation | feature/rc2-01-flow-foundation | Cross-file import/alias/re-export/self/class candidates, conditional regions, receiver-aware adapters and workflow task scope |
| Knowledge | feature/rc2-02-workflow-knowledge | Implemented: workflow-first overview, connected module components, shared callable drill-downs and numbered Markdown paths/effects/failures |
| Integrity | feature/rc2-03-generation-integrity | Implemented: separate semantic/extraction/export gates, explicit claim review, incomplete-inventory rejection, sharded snapshots, immutable export generations and complete operation paging |
| Diagram UX | feature/rc2-04-diagram-ux | Implemented: SCC/layer topology and bounded gutter routes, draw.io waypoints, portable overrides and explicit old/new conflict choices |
| Scenario extension | feature/rc2-05-semantic-amendments | Implemented: revision-safe, task-evidence-bounded append-only extensions to related authored scenarios |
| Evidence | feature/rc2-06-review-evidence | Pending: source-review bundle, measured checks, compatibility and release notes |

Confirmed product gaps: P0-01/02, P1-01/02/03/04/05/07/08/09/10/12/13.
P1-06 is a fundamental semantic-truth limitation; explicit review/contradiction
and coverage gates are required, not a claim that scripts can prove meaning.
P0-03 and P2-01 concern evidence availability in the supplied archive: repository
tests/fixtures/CI/docs do exist. The skill payload intentionally excludes them;
a separate source-review artifact will make them independently inspectable.
P1-11 remains an external interoperability check, distinct from XML/XSD checks.
Confluence, model-comparison and other unavailable acceptance checks stay NOT_RUN.
Optional non-stdlib parser installation (P2-09) is not inferred authorization to
add a dependency or weaken the Python-first unsupported-syntax boundary.

## Reproductions and evidence

- Before repair: a five-file HTTP/service/store/publish/consumer fixture had no
  `workflow_review` task. SQLAlchemy import plus unrelated set.add produced db_write.
- After flow repair: one task can accept an authored scenario spanning all five
  files. Alias/re-export/self/class references resolve as static candidates;
  matching channel literals link producer and registered consumer without delivery proof.
- Branch regions keep except/rollback separate from unconditional lexical paths.
- Independent review found/fixed loop-condition literal persistence, stale import
  shadowing and custom `.objects` collection false positives. Regression tests
  inspect both returned data and cache; no target module is imported/executed.

RC2-02 review repairs: bounded shared/cyclic navigation, active diagram fragments,
and retained evidence-empty claim scope. The actual dense SCC browser test passed.

RC2-03 independent review identified and verified repairs for per-scope semantic
coverage and untracked/inaccessible authored output assets. Publication fails
closed; prior generations remain authoritative after interrupted staging.

## Finding disposition for RC2

| Review item | Disposition and evidence |
| --- | --- |
| P0-01 cross-file authoring | Workflow/component tasks carry full operation/evidence scopes; five-file fixture accepts one scenario. Later related tasks can append with expected hashes; stale contributor updates reopen reconstruction scopes. |
| P0-02 workflow documents | Authored workflow → component → shared callable views; numbered steps, actors, preconditions, state effects and failure/unknown sections. Unreviewed components remain explicitly unreviewed. |
| P0-03 / P2-01 evidence delivery | Separate installable skill and tracked source-review ZIP; tests, CI, fixtures, examples, tools and branch provenance included in the latter. Stable remains NO-GO. |
| P1-01 cross-module graph | Alias/relative/re-export/self/typed-receiver candidates, import-binding evidence, shadowing regression. Dynamic dispatch remains explicit. |
| P1-02 branch/failure model | Conditional lexical regions and separate handler/finally/return/raise candidates; no unconditional commit→rollback edge. This is bounded static control context, not a complete CFG proof. |
| P1-03 adapters | Receiver/framework provenance and known-channel checks; negative set.add/custom objects fixtures. Unclassified execute remains a candidate. |
| P1-04 task priority | Entrypoint workflows precede disconnected module components; configured task/node truncation is recorded as a limitation. |
| P1-05 completion semantics | Separate extraction, semantic and export outcomes; every task scope needs authored interpretation. Unknowns/unreviewed material claims prevent semantic PASS. |
| P1-06 semantic truth | Explicit material-claim review/contradiction tasks and honest truth boundary. Supported review records an agent judgment, not automated proof or independent sign-off. |
| P1-07 incremental identity | Span anchors/fingerprints survive unrelated same-file edits and offsets; rename and changed-span regressions. |
| P1-08 incomplete inventory | Missing inventory is unknown, never inferred deletion; update/freshness fail closed without invalidating prior knowledge. |
| P1-09 export integrity | Output-owned lock; immutable generations and current.json commit; recovery, intent, adoption, notes, withdrawn-format, untracked/unreadable asset and concurrent-edit tests. |
| P1-10 topology layout | SCC condensation, dependency columns, shared row-gap routes and draw.io waypoints; obstacle and edge-label geometry tests. Dense crossings remain possible. |
| P1-11 editor/Confluence | Local XML/XSD checks PASS. After explicit approval, live editor checks from file and loopback HTTP origins were INCONCLUSIVE: blank iframe, no initialization event, no XML load sent. Confluence remains NOT_RUN; no compatibility claim substituted. |
| P1-12 budgets/storage | Complete ops:N and scenes:N metadata paging; compact next previews; sharded cache/state/history/model and legacy-state migration tests. |
| P1-13 scale | Indexed graph/task/view/reconciliation paths; actual 10k/50k measurements in scale-results.json. 50k remains memory-heavy, task/view coverage intentionally PARTIAL. |
| P2-02 portable edits | JSON backup/import validates fields/targets/version/limits; explicit artifact migration/replacement; actual near-limit roundtrip. |
| P2-03 edit conflicts | Previous/current generated values and Keep my edit / Use generated choices. Canonical Markdown transfer remains an explicit human edit of its manual section. |
| P2-04 navigation | Arbitrary bounded-depth/shared graph routes, correct parent Back, cycle protection, bounded tree and working view fragments. |
| P2-05 architecture/links | Module component/dependency architecture, integration effects, Markdown diagram links and operation detail links to workflow documents/source. |
| P2-06 errors | Correctable versus nonretryable outcomes and private diagnostic IDs without exception text, source snippets or locals. |
| P2-07 browser/accessibility | Chrome viewport/geometry/screenshot, native mouse/touch, keyboard and visible editing checks. Physical devices, Firefox/WebKit and formal WCAG assessment remain NOT_RUN. Fit is intentionally relative to the initial fit baseline. |
| P2-08 export loss | Machine-readable export-losses.json describes draw.io/HTML/Mermaid presentation losses. |
| P2-09 multilingual parsing | Existing explicit host-grammar/unsupported-language limitation retained. Optional parser dependency recommendation deferred; no dependency installed. |
| P2-10 versions | Storage-v1 load → storage-v2 save/read and unknown-version/corrupt-shard tests; parser v6 forces semantic refresh after resolver change. Protocol/model stay v1 with optional fields. |

Each repair increment received targeted independent review of its actual diff;
verified findings were fixed and rechecked. These reviews do not replace the
pending combined user/product acceptance or the external release gates.
