# MOLE development status

All feature checkpoints are local and stacked: each branch starts from the prior
feature's commit. The user authorized local commits and deferred combined review
and merge. Nothing has been pushed, merged, tagged, installed globally or published.

Current branch: `feature/pr-14-release-preparation`.
Current candidate: `1.0.0rc1`. All checkpoints await user acceptance.
The repository had no commits before PR-01; no populated main branch was created.

| PR | Local branch | Checkpoint |
| --- | --- | --- |
| 01 | feature/pr-01-skill-bootstrap | e73e85b |
| 02 | feature/pr-02-workspace-protocol | 291f56a |
| 03 | feature/pr-03-knowledge-model | 29a7686 |
| 04 | feature/pr-04-python-scanner | be2593f |
| 05 | feature/pr-05-framework-traces | b5da805 |
| 06 | feature/pr-06-agent-protocol | 07120f6 |
| 07 | feature/pr-07-markdown-knowledge | a27a09a |
| 08 | feature/pr-08-offline-explorer | dc92a72 |
| 09 | feature/pr-09-layout-accessibility | 894b4f1 |
| 10 | feature/pr-10-field-overrides | 1a9c3dd |
| 11 | feature/pr-11-diagram-exports | 03dad92 |
| 12 | feature/pr-12-incremental-updates | 8378dfb |
| 13 | feature/pr-13-security-evals-portability | c3df833 |
| 14 | feature/pr-14-release-preparation | HEAD after final local commit |

PR-14 also closes candidate-contract audit gaps: bounded authored scenarios,
business mappings/glossary, safe narrow path scopes, matching JSON read/write
limits, and slash-aware ignore patterns. The optional semantic-patch additions
remain backward-compatible with claims-only v1 patches.

Independent targeted reviews covered bootstrap, persistence, model provenance,
scanner/cache, semantic protocol, authored-note preservation, browser overrides,
incremental identities, contextual secret suppression and authored knowledge.
Verified findings were repaired and rechecked. Combined product/release review
is still pending; targeted reviews are not acceptance of the entire product.

Fresh verification and remaining gaps are recorded in
[release readiness](docs/release-readiness.md). Evaluation data is in
[the checked-in report](docs/evaluation-results.json).

To review the root bootstrap: `git show --stat e73e85b`.
For later increments: `git diff <prior-branch>..<feature-branch>`.
For all later work together:
`git diff feature/pr-01-skill-bootstrap..feature/pr-14-release-preparation`.
Review the root bootstrap in addition to that combined diff.

Next action: combined user review, outstanding acceptance checks, then an
explicit decision on the initial main baseline and merge/release sequence.
