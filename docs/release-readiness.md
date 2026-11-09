# Release readiness — 1.0.0rc2

Status: **LOCAL REVIEW CANDIDATE; stable 1.0.0 remains NO-GO.** No branch
has been pushed, merged, tagged or published. The original planning checkboxes
remain reference material, not automatic acceptance of implemented work.

## Observed local evidence

The repair suite covers cross-file HTTP → service → SQLAlchemy → publication →
registered consumer candidates, branch/rollback separation, receiver-aware
negative adapter cases, task-wide semantic authoring, revision-safe scenario
extensions, and reconstruction after one contributing task becomes stale.
It verifies span-aware claim reuse, incomplete-inventory rejection, sharded
workspace compatibility/corruption, per-scope semantic gates, explicit material
claim review, complete operation paging, and redacted diagnostic IDs.

Immutable export-generation tests cover staging failure, pointer publication
recovery, competing workspaces, changed intent, concurrent manual edits,
withdrawn formats, untracked/unreadable authored assets and symlink rejection.
Prior output remains authoritative until the single current.json commit.

Actual Chrome checks cover offline models, 390/600/768/1280/1920 viewports,
shared/cyclic navigation, view fragments, mouse capture, native touch scrolling,
keyboard and visible edit controls, portable JSON backups, old/new conflict
choices, storage failure, near-limit roundtrips and long-label bounds.
A dense-diagram screenshot was visually inspected locally. This is evidence for
these checks, not a WCAG certification or a physical-device browser matrix.
XML/reference/page-link checks and official mxfile.xsd validation run locally.

Final local suite: **125 tests passed**, with real Chrome and the official XSD.
Archive hashes are recorded in the adjacent build manifests. Tests use
Python 3.15.2/macOS and actual Chrome; optional checks are reported separately.

Four fixture pattern sets and a negative adapter check pass in
[evaluation-results.json](evaluation-results.json). The synthetic 10k/50k symbol
runs in [scale-results.json](scale-results.json) completed with PARTIAL coverage:

| Symbols | Scan/tasks/save | Markdown compose/export | Peak process RSS | Workspace bytes |
| --- | --- | --- | --- | --- |
| 10,000 | 3.64 s | 13.36 s | 542 MB | 98.8 MB |
| 50,000 | 23.18 s | 51.48 s | 2.34 GB | 439.6 MB |

Replies stayed below 3,000 bytes in these measurements. Task/view bounds remain
explicit; 50k is memory-heavy and these synthetic runs do not prove interactive
performance for every repository or semantic quality. No token-saving claim is made.

## Remaining acceptance gates

| Gate | State | Required evidence |
| --- | --- | --- |
| Python 3.11/3.14, Linux/Windows runtime matrix | NOT_RUN | Execute configured CI on those runtimes |
| Firefox/WebKit and physical touch devices | NOT_RUN | Equivalent interactions on those browsers/devices |
| diagrams.net editor save/reload and page-link interaction | BLOCKED_APPROVAL | Public-editor transfer rejected by automatic approval review; explicit authorization requested for synthetic fixture only |
| Mermaid external parser | NOT_RUN | Supported renderer/parser check |
| Confluence Cloud + draw.io app | NOT_RUN | Authorized tenant/app acceptance; no page was published |
| Equal-quality LLM baseline and blind semantic assessment | NOT_RUN | Same cases and independent quality rubric |
| Light/medium/strong model evaluation/telemetry | NOT_RUN | Configured endpoints and measured runs |
| Combined user/product acceptance | PENDING | Review the stacked checkpoints and explicit limits |
| Final merge/tag/release | NOT_AUTHORIZED | Separate decision after acceptance |

Static evidence and an explicit agent review do not prove claim truth or runtime
behavior. Unknown dispatch, broker delivery, retries, deployment startup and
business policy remain evidence boundaries. Redaction is heuristic. Windows
filesystem races have weaker guarantees than the POSIX descriptor-based reads.

## Artifacts, compatibility and recovery

`artifacts/mole-1.0.0rc2.zip` is the installable skill payload.
`artifacts/mole-1.0.0rc2-source-review.zip` is the combined tracked source snapshot
with tests, fixtures, tools, CI, docs and local branch provenance. Its manifest
states whether the source was dirty. Neither archive merges branches or includes
Git history. Both have adjacent SHA256/file manifests and are local artifacts.

CLI and semantic model remain protocol/schema v1 with optional authoring fields.
Workspace storage v2 shards the payload; legacy v1 state loads and migrates on
save. Unknown versions are rejected. Preserve the entire workspace including
.objects and history, and preserve all output generations. Older engines cannot
read storage-v2 pointers; roll back code using a separate compatible workspace.
Interrupted exports can retry or explicitly restart; update reconciles publication
before refreshing source. See the [agent protocol](../skills/mole/references/agent-protocol.md).

The extracted source snapshot runs its tests without Git history. Only the
source-repackaging provenance test requires a Git checkout and is skipped there;
the installable archive/isolated-runtime test still runs.
