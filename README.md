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
