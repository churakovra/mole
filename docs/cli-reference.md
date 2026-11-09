# CLI v1 candidate

Run `python3 <ABSOLUTE_SKILL_DIR>/scripts/mole.py` with the following commands.
All workflow commands return one JSON document on stdout; `--json` is accepted
explicitly. Help/version and human-readable doctor output are the exceptions.

| Command | Required arguments | Purpose |
| --- | --- | --- |
| doctor | none | Interpreter and payload checks; use --json for structured output |
| start | --repo PATH --workspace PATH | Create/resume a session |
| next | --workspace PATH | Scan if needed, then return highest-priority pending task |
| inspect | --workspace PATH --task ID | Paginated source context |
| submit | --workspace PATH --input PATCH.json | Validate and accept bounded claims |
| status | --workspace PATH | Read current checkpoint |
| finish / export | --workspace PATH --output PATH | Compile validated or explicit partial output |
| diff | --workspace PATH | Report changed inputs |
| update | --workspace PATH | Refresh affected evidence and semantic tasks |

start accepts `--mode quick|standard|deep` (default standard), limiting semantic
task counts to 20/100/500. `--scope repository` is default; a relative file or
directory restricts inventory. Cross-scope runtime effects remain unknown.
Python is parsed using the host grammar. Unsupported syntax and languages are
reported rather than treated as successfully analyzed Python.

inspect accepts `--budget-chars 1024..32000` (default 12000) and `--cursor I:OFFSET`.
Use returned nextCursor until null. `ops:N` pages complete operation metadata;
`scenes:N` pages related authored scenario IDs/hashes for bounded amendments.
The default `I:OFFSET` stream pages source context. `next.task` is a preview,
with full collection counts. Metadata too large for the budget produces
INVALID_BUDGET; increase it. Secret-like blocks are suppressed before pagination.

finish/export include Markdown and default to HTML + draw.io. Repeat `--format`
with markdown/html/drawio/mermaid to select formats; Markdown is always included.
Pending tasks or material coverage limits require `--allow-partial`. A PARTIAL
session can continue through next/inspect/submit. COMPLETED describes this
session's implemented checks, not release certification or proof of runtime truth.

Output must be a dedicated directory without indexed inputs. Generated sections
are checked against prior bases. OUTPUT_CONFLICT preserves authored data; choose
a new directory or resolve edits without deleting manual content. Repeated export
is safe and publishes immutable `.mole-generations` bundles through `current.json`.
Open `MOLE-OPEN.html` or the returned active output path. Previous generations
remain intact; withdrawn formats are absent from the new one and listed retired.
`--restart-export` explicitly replaces an interrupted staging intent;
`--adopt-output` explicitly acknowledges another workspace generation for the
same repository/scope. `update` reconciles interrupted publication. Removed
processes retain notes as retired notices; previous SKMs remain in history.

Exit codes: 0 success (including explicit PARTIAL), 2 invalid request/schema,
3 environment/runtime, 4 lock/permission/I/O, 5 conflict/stale/corrupt state,
6 quality/export gate failure, 10 unexpected internal error. Errors contain code,
message, recoverable and suggestedAction. Use the code and nextAction, not chat
memory, to decide whether to retry, update, or stop. Internal errors include a
diagnosticId with engine-frame locations under workspace/.diagnostics; exception
messages, source snippets and locals are excluded. Corrupt/unsupported formats
and internal failures do not claim automatic recoverability.
