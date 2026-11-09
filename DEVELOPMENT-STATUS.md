# MOLE development status

All feature checkpoints are local and stacked: each branch starts from the prior
feature's commit. The user authorized local commits and deferred combined review
and merge. Nothing has been pushed, merged, tagged, installed globally or published.

Current branch: `feature/rc2-06-review-evidence`.
Current candidate: `1.0.0rc2`. All checkpoints await user acceptance.
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
| 14 | feature/pr-14-release-preparation | d138073 |

The RC1 static review was investigated against repository sources and repaired
on six additional stacked branches:

| Increment | Local branch | Checkpoint |
| --- | --- | --- |
| Flow foundation | feature/rc2-01-flow-foundation | 4e0ba35 |
| Workflow knowledge | feature/rc2-02-workflow-knowledge | ead3f64 |
| Generation integrity | feature/rc2-03-generation-integrity | f665a94 |
| Diagram usability | feature/rc2-04-diagram-ux | 26210ce |
| Semantic extensions | feature/rc2-05-semantic-amendments | b104e2f |
| Review evidence | feature/rc2-06-review-evidence | HEAD after final local commit |

Independent targeted reviews covered flow resolution, workflow/nav compilation,
snapshot/publication integrity, semantic gates, portable overrides/layout,
scenario extension/update lineage and final evidence packaging. Verified findings
were fixed and rechecked. See [finding dispositions](docs/reviews/rc1-resolution.md)
and [fresh checks and acceptance gaps](docs/release-readiness.md).

The installable ZIP contains only the complete skill payload. The source-review
ZIP contains the combined tracked source snapshot, tests/fixtures/CI/docs and
local branch provenance. Neither archive merges branches or includes Git history.
The repository retains every branch and local commit for review.

To review bootstrap: `git show --stat e73e85b`.
For each increment: `git diff <prior-branch>..<feature-branch>`.
For RC2 repairs together:
`git diff feature/pr-14-release-preparation..feature/rc2-06-review-evidence`.
Review original PR-01..14 as well when evaluating the entire implementation.

Next action: combined user review and outstanding acceptance checks, followed by
an explicit decision on the initial main baseline and merge/release sequence.
No branch has been merged, pushed, tagged or published.
