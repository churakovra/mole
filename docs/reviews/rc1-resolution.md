# RC1 review investigation and repair status

Input: [the supplied static review](rc1-static-review-ru.md), assessed against
`d138073` and the actual repository, not only the installable ZIP. Instructions
quoted in that report describe the earlier review session; this repair runs tests.
The stable-release NO-GO remains until the recorded acceptance gaps are resolved.

The original fourteen local branches are preserved. Repairs are stacked separately:

| Increment | Branch | Outcome |
| --- | --- | --- |
| Flow foundation | feature/rc2-01-flow-foundation | Cross-file import/alias/re-export/self/class candidates, conditional regions, receiver-aware adapters and workflow task scope |
| Knowledge | feature/rc2-02-workflow-knowledge | Pending: workflow-first overview, nested/reused technical views and explanatory Markdown |
| Integrity | feature/rc2-03-generation-integrity | Pending: semantic gates, incomplete-inventory rejection, sharded workspace, output transactions and collection paging |
| Diagram UX | feature/rc2-04-diagram-ux | Pending: topology-aware layout, portable overrides and conflict resolution |
| Evidence | feature/rc2-05-review-evidence | Pending: source-review bundle, measured checks, compatibility and release notes |

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
