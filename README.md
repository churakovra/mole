# MOLE

**Mapping Operations, Logic & Evidence** — Follow the code. Find the why.

MOLE is being built as a self-contained Agent Skill with a bundled Python
engine, `molekit`. The current development version implements PR-01 bootstrap
diagnostics only. Repository analysis, persistent workspaces, documentation,
and diagram exports are planned; they are not available in this version.

## Install and check

Copy the entire `skills/mole/` directory to your agent's supported skill location.
It must retain `SKILL.md`, `scripts/`, `molekit/`, and the other bundled files.
Use a shell with Python 3.11+; no pip, uv, npm, MCP, API key, or engine setup is required.
From any working directory, using the absolute path to your installed copy:

```bash
python3 /absolute/path/to/mole/scripts/mole.py doctor --json
python3 /absolute/path/to/mole/scripts/mole.py --version
python3 /absolute/path/to/mole/scripts/mole.py --help
```

On Windows, use a Python 3.11+ interpreter and quote paths containing spaces.
Invoke `$mole` in a compatible agent to run diagnostics. A successful doctor
result confirms the bootstrap runtime only, not analysis or release readiness.
Diagnostics do not read target projects, install dependencies, or access the network.

`doctor` emits human-readable text by default; `--json` emits one JSON document.
Exit codes: `0` success, `2` invalid command line, `3` unsupported Python.
Errors emit JSON containing a code, message, recoverability, and suggested action.
The full versioned workflow protocol is reserved for PR-02.

## Development

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
git diff --check
```

Tests copy only the skill into a temporary location, run from outside the project,
disable site packages, and deny network/process creation inside the CLI process.
CI defines Python 3.11 and 3.14 checks on Linux, macOS, and Windows.

The skill payload owns all runtime imports. Tests and CI stay at repository level.
Version `0.1.0.dev1` identifies this bootstrap; it is not the planned `1.0.0` release.
Licensed under Apache-2.0; see [LICENSE](LICENSE).

### Persistent sessions (PR-02)

`start --repo PATH --workspace PATH [--mode quick|standard|deep]` creates a
session; repeating the same request resumes it. `status --workspace PATH`
reports the checkpoint. Workflow commands emit a versioned JSON envelope.
State is stored atomically in `state.json`, including the manifest; `.lock`
uses an OS-owned lock released on exit/crash. The state file is authoritative.
`next`, `inspect`, `submit`, and `finish` are reserved workflow boundaries;
source extraction, semantic validation, and export are enabled by later PRs.
They return explicit errors until their respective implementations are present.

### Static source scan (PR-04)

Run `next --workspace PATH --json` after `start` to inventory and parse sources.
The engine records AST symbols, imports, branches and possible calls without
importing target modules. Syntax incompatible with the host Python is reported
as `PARSER_UNSUPPORTED_SYNTAX`; install a newer interpreter explicitly if needed.
The scanner skips secret filenames, symlinks, binary and oversized files, uses
nested `.gitignore` rules, and bounds inventory time and file count. Ignore
matching supports ordinary glob/negation patterns; Git escaped-pattern edge
cases are not supported. UTF-8 text is the current source encoding contract.
A cache keyed by content hash and host parser version avoids reparsing unchanged
Python files. The source revision is a deterministic inventory hash, not a Git
commit or proof of runtime behavior.

### Framework candidates (PR-05)

Adapters activate only when imports detect FastAPI/Starlette, Django,
SQLAlchemy, asyncio, aio-pika, or aiokafka. They locate route decorators,
transaction/read/write patterns, async boundaries, publish/consume/ack patterns,
and branch boundaries. These are name-based candidates with source evidence,
not proof of dispatch, ordering, transaction scope, retries, or delivery guarantees.
Bounded forward/backward traces terminate cycles and report evidence boundaries.
Dynamic DI and broker configuration still require agent review.

### Agent task loop (PR-06)

After scanning, `next` returns a pending semantic task. Follow the bundled
[agent protocol](skills/mole/references/agent-protocol.md) to inspect bounded,
paginated source context and submit revision-bound claims. Submission validates
the patch shape, task-linked evidence, provenance, and current source hashes.
Identical submissions are idempotent; different replacements conflict. A stale
source requires rescan/update rather than accepting old analysis. Oversized
inspection metadata returns INVALID_BUDGET instead of exceeding the limit.

### Knowledge and Markdown (PR-07)

`finish --workspace PATH --output PATH --json` compiles a process catalog,
architecture inventory, process pages, and quality report from the same SKM.
Pending tasks/coverage limits require explicit `--allow-partial`; pending tasks
remain resumable after a partial export. Process ordering and business intent
are explained only to the extent supported by accepted claims.
Use a dedicated output directory that does not contain indexed inputs.
Generated sections are checked against their recorded base digest before an
update; authored changes conflict rather than being overwritten. Manual text
outside generated markers is preserved. An export journal permits interrupted
writes to resume. Unassociated accepted claims remain in the quality report.

### Offline explorer (PR-08)

`finish` also writes `explorer.html` with inline model, CSS and JavaScript.
Open it directly via `file://`. The same renderer supports each fixture model:
process tree/search, node/connector selection, evidence details, nested views,
leaf-safe double click, and Back along the actual containment route. Keyboard
Enter selects, ArrowRight drills, and Alt+ArrowLeft returns. A restrictive CSP
blocks connections; user strings are rendered as text nodes.

### Layout and navigation (PR-09)

HTML and diagram exporters share a deterministic bounded grid layout with
wrapped labels and exterior connector lanes. Dense graphs warn about possible
crossings and remain locally scrollable. Zoom is relative to Fit=100%; wheel
scrolling does not change zoom. Mouse background drag pans with pointer capture;
touch uses native scrolling. Browser tests use Chrome DevTools to enforce exact
390/600/768/1280/1920 CSS-pixel viewports and check geometry and page overflow.
The development-only harness needs Node and Chrome; the installed skill does not.

### Browser-local edits (PR-10)

Double-click a node/edge label, selected description/notes, or glossary field to
edit; F2 is the keyboard equivalent. Edits use `mole:<artifactId>:v1` localStorage
records with field IDs, generated base hashes, revision and timestamps. Compatible
regeneration retains edits; changed generated fields keep authored values with a
visible conflict warning. Malformed/blocked/quota-limited storage is reported;
a failed save remains in memory and does not replace the last persisted store.
Browser edits are not shared editing and do not modify Markdown or canonical SKM.
Moving files/origins or using another browser may change localStorage availability.

### Diagram interchange (PR-11)

Default export includes multipage `confluence/workflows.drawio` with stable
shape/page IDs and internal navigation. `--format markdown` selects Markdown
alone; repeat `--format` for html/drawio/mermaid. Mermaid is optional and explicitly
lossy. See the bundled [Confluence guide](skills/mole/references/confluence-export.md).
XML round-trip, escaping, reference/link checks and official XSD validation were
run locally. Editor save-round-trip, Mermaid external-parser and Confluence
Cloud/app acceptance remain NOT_RUN; these are not certified integrations.
For optional development XSD checks, set MOLE_DRAWIO_XSD to a local official
mxfile.xsd and provide xmllint. The runtime never downloads a schema.

### Incremental regeneration (PR-12)

`diff --workspace PATH` reports added/removed/changed files without changing
knowledge. `update --workspace PATH` rescans changed inputs, reuses unchanged
parser facts and evidence-valid claims, and reopens affected semantic tasks.
Old patches are rejected after revision changes. Exact, unique file renames
retain established symbol/operation IDs; ambiguous matches are reported, never
fuzzily guessed. New declarations reusing vacated names receive distinct IDs.
A previous model is saved under workspace history before the new checkpoint.
Run `finish`/`export` afterwards; change-report.md records invalidations and reuse.
Removed process files become retired notices while retaining manual notes.
No automatic deletion, merge, commit, or publication occurs.

### Security, evaluation and portability (PR-13)

Repository reads use bounded, symlink-resistant paths; contextual secret
suppression happens before inspection pagination. JSON complexity, duplicate
keys, non-finite values, output escapes and permission failures are checked.
Read [the security model](docs/security-model.md) for boundaries and limitations.
Document-only sources receive agent-review tasks; unsupported source languages
are explicitly reduced coverage rather than silently treated as Python.
Run `python3 tools/evaluate.py --output /tmp/mole-evaluation.json` for the actual
fixture/cache checks. See [evaluation scope](docs/evaluation.md) and the recorded
[results](docs/evaluation-results.json). Multi-model/baseline quality comparisons,
CI OS/runtime matrix, Firefox/WebKit/touch, and external integration acceptance
remain NOT_RUN. These gaps block a final 1.0.0 readiness claim.
