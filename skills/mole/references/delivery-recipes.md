# Goal-specific v1 delivery recipes

Resolve `MOLE` below to `python3 <ABSOLUTE_SKILL_DIR>/scripts/mole.py` and use
external `REPO`, `WORKSPACE` and `OUTPUT` paths. These are agent-facing recipes,
not commands the end user must compose. Read the protocol for patch/paging details.
Every path begins with `MOLE doctor --json`.

## Locate

Example: "Where is JWT checked?" Determine a likely file from repository context;
use `start --repo REPO --workspace WORKSPACE --scope app.py --json`, `next`,
and paginated `inspect`. Explain the exact symbol/path/lines and what the source
actually checks. Submit the source-backed claim where appropriate. No `finish`
or output directory is needed for chat. If the symbol is absent, state the
searched scope and limitations; a missing AST edge is not proof of absence.

## Explain a narrow object

Example: "Explain verify_jwt." Use the same bounded file workflow, inspect the
function and necessary callers/effects, then give purpose, inputs, actions and
unknowns with citations. Do not require the entire repository task queue to
finish. An index/path boundary may limit the explanation; disclose it.

## Trace

Example: "Trace POST /orders to publication." Start with `--scope repository`
so dependencies outside the API directory remain available. `next`, `inspect`
and `submit` source-backed findings, distinguishing branch/order candidates
from runtime proof. Return the relevant path, conditions, effects and boundaries.
Generate a focused artifact only when requested; v1 cannot automatically filter
its global index to a question, so keep the answer bounded and state coverage.

## Investigate

Example: "Why duplicate notifications?" Inspect publication, consumption,
acknowledgement, retry/exception paths and negative evidence. Submit claims with
explicit inferred/unknown status when needed. Return hypotheses with supporting
and opposing evidence and concrete unchecked factors. Do not claim exactly-once,
atomicity or security guarantees from static names or an agent review verdict.
An investigation report can be delivered in chat unless a file was requested.

## Service orientation

Example: "Explain how this service works." Start a repository-scoped session,
use bounded `next/inspect/submit` work to author named business processes and
evidence-backed links/step transitions. Follow `ux-contract.md`. Continue the
justified task loop, then use `finish --workspace WORKSPACE --output OUTPUT
--format markdown --format html --json`. Use `--allow-partial` only for an
honestly partial deliverable with specific limitations. Open the returned
active bundle's Explorer and check navigation/evidence. Return its link plus
the key explanation. A prose-only summary is insufficient unless text-only
was explicitly requested. Text-only orientation uses the same investigation
but does not require export.

## Document

Example: "Document payment pipeline in Markdown and HTML." Investigate the
requested pipeline, submit evidence-backed semantic content, then
`finish --workspace WORKSPACE --output OUTPUT --format markdown --format html
--json`. Add `--format drawio` only when required; Markdown is always included
by v1. For Markdown-only use `--format markdown`. Verify requested files and
source/deep links, retain manual notes, and return usable artifact links.
On output conflict preserve authored content; resolve it or choose a new output.

## Recovery and completion

Repeated `next` does not mean progress. After meaningful work compare the result
with the original question. Use `diff/update` for stale sources and resume the
affected task; do not reuse stale proof. Retry malformed patches using the
specific error, not blind repetition. If two rounds produce no new evidence or
justified hypothesis, report the concrete blocker or scope limit. Engine
technical/semantic/export status and user-goal satisfaction are distinct.
