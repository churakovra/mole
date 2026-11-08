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
