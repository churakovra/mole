# MOLE

**Mapping Operations, Logic & Evidence** — Follow the code. Find the why.

MOLE is a self-contained Agent Skill (`$mole`) with a bundled Python engine,
`molekit`. It inventories source, asks the agent bounded evidence-backed questions,
and compiles a shared knowledge model into Markdown, offline HTML and draw.io.

**Current version: 0.1.0, an unreleased review candidate.** Implementation is
available locally; [release acceptance gaps](docs/release-readiness.md) remain.
Static candidates are not verified runtime behavior.

## Install

Copy the **entire** `skills/mole/` directory to your agent's supported skill
location. Keep its scripts, engine, schemas, references, assets and license
alongside SKILL.md. The installed skill requires a shell and Python 3.11+.
There is no pip/uv/npm installation, separate engine setup, Node, Docker, MCP,
API key or network bootstrap. Node/Chrome are development-only browser-test tools.

From any working directory, use the absolute installed path:

```bash
python3 /absolute/path/to/mole/scripts/mole.py doctor --json
python3 /absolute/path/to/mole/scripts/mole.py --version
python3 /absolute/path/to/mole/scripts/mole.py --help
```

On Windows, choose a Python 3.11+ interpreter and quote paths containing spaces.
An incomplete payload or unsupported interpreter produces an explicit error.

## Agent workflow

Ask a specific question for a concise sourced answer, trace a path, investigate a
failure, or request documentation in selected formats. Explicit text-only
requests do not require HTML. See the bundled
[delivery recipes](skills/mole/references/delivery-recipes.md).

For "explain how this service works", the default deliverable is a local HTML
business-process explorer: start with named processes, open their plain-language
steps and failure paths, then drill into implementation diagrams and source
evidence. Scenario explanations include triggers, actors, outcomes and unknowns.
Additional static scopes are grouped separately from authored business processes.
Labeled process handoffs and branch transitions cite authored claims; arrows do
not imply verified runtime behavior. Ordering alone does not create connectors.

Invoke `$mole` in a compatible shell-enabled agent with your question, audience,
and desired scope. The agent follows the bundled [protocol](skills/mole/references/agent-protocol.md):

1. Admit the original goal and deliverable with begin in a workspace outside the source repository.
2. Use next and paginated inspect to investigate source-backed tasks.
3. Submit revision-bound claims and canonical processes, steps and supported handoffs.
4. Use check and complete: chat needs no files; maps publish a validated Explorer generation.
5. Follow up using shared fresh knowledge; use diff/update after source changes.

Examples: `$mole Where is JWT checked?`, `$mole Explain verify_jwt`,
`$mole Trace POST /complete`, `$mole Investigate duplicate rewards`, and
`$mole Explain to me how this service works`. See [v2 delivery](docs/v2-delivery.md)
and the [test handoff](docs/ux-evaluation.md). The lower-level start/finish example
below is retained for legacy compatibility.

For example, after resolving the installed skill directory:

```bash
python3 /absolute/path/to/mole/scripts/mole.py start \
  --repo /absolute/target/repo --workspace /absolute/workspace \
  --mode standard --scope repository --json
python3 /absolute/path/to/mole/scripts/mole.py next --workspace /absolute/workspace --json
```

Scope can also be a repository-relative file or directory. The engine owns
state/validation and never calls an LLM API. Its tasks require the current agent's
reasoning; it does not claim to infer business intent by itself.

## Outputs and preservation

Markdown is always included: a workflow catalog, component architecture, process
pages, quality report, and glossary when supplied. HTML is a portable single file
with tree/search, evidence details, nested navigation, keyboard controls,
Fit-relative zoom, local scrolling/pan, and browser-local editing.
The draw.io export is multipage with stable IDs/internal links. Mermaid is
optional and explicitly lossy. Select only Markdown with `--format markdown`.
See the [CLI reference](docs/cli-reference.md) and [Confluence guide](skills/mole/references/confluence-export.md).

Generated Markdown/output sections are checked against their previous base.
Authored changes conflict rather than being silently overwritten; manual sections
survive updates. Changed evidence reopens affected tasks. Exact unique renames
retain semantic identity, while ambiguous cases remain explicit.
Browser-local edits use field hashes and portable JSON export/import. Conflicts
show previous/current generated values with explicit resolution choices. These
presentation edits do not change the canonical model or Markdown.

Exports publish immutable generations under a dedicated container. Open
`MOLE-OPEN.html` or resolve `current.json`; the returned `output` is the active
bundle. Previous generations remain intact, manual sections carry forward,
and untracked authored assets stop regeneration until preserved externally.

Inspect the [example catalog](docs/examples/workflows/README.md),
[offline explorer](docs/examples/workflows/explorer.html), and
[draw.io file](docs/examples/workflows/confluence/workflows.drawio).

## Boundaries

Python-first analysis uses host-version AST and detected-framework heuristics
for FastAPI/Starlette, Django, SQLAlchemy, asyncio and messaging candidates.
Dynamic dispatch, ambiguous cross-module references, broker guarantees, deployment order,
and business rules may remain unknown. Unsupported source languages receive
reduced-coverage text review; documents can represent intended workflows.
Ignore rules support ordinary glob, slash, ** and negation patterns; Git escaped
pattern edge cases are unsupported. Diagrams use SCC/layer topology with bounded gutter routes;
dense connector crossings are possible. Modes bound semantic task counts, not prove
coverage. See [security boundaries](docs/security-model.md).

No target-project code/tests/migrations are executed, no dependencies installed,
and no network, upload, commit, push or publication is performed by the engine.
Secret suppression is heuristic; review outputs before sharing them.

## Development and review

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 tools/evaluate.py --output /tmp/mole-evaluation.json
python3 tools/package_skill.py --output /tmp/mole-review.zip
python3 tools/package_source.py --output /tmp/mole-source-review.zip
```

The tests exercise an isolated copy of only the skill, complete CLI workflow
with network/process denial, persistence/update failures, source/JSON/security
boundaries, XML/XSD (when configured), and actual Chrome interactions/geometry.
See [evaluation evidence](docs/evaluation.md), [branch status](DEVELOPMENT-STATUS.md),
and [contribution guidance](CONTRIBUTING.md). The original development guide,
implementation plan and PR backlog remain unchanged references. The v2 workflow
and test handoff are documented in [delivery](docs/v2-delivery.md) and
[UX evaluation](docs/ux-evaluation.md).

Licensed under [Apache-2.0](LICENSE). The same license is included in the skill payload.
