# Security boundaries and evidence limits

MOLE treats the target repository and agent patches as untrusted data. Target
code is parsed rather than imported, tested, or executed. No engine operation
uses a network client, launches an LLM, installs dependencies, or publishes data.
The installed-copy integration test denies socket and subprocess events while
running start → next → inspect → submit → finish and checking all default outputs.

Source traversal excludes symlinks, credential filenames, binary/oversized
files, ignored paths and the workspace. Reads are bounded to 1 MiB per file and
64 MiB per inventory, with 10,000-file and traversal-time limits. POSIX source
reads open path components using directory descriptors and O_NOFOLLOW. The
Windows fallback checks symlinks and resolved bounds but does not provide the
same descriptor-based protection against a concurrent filesystem attacker.
Keep workspace/output in directories controlled by the invoking user.

JSON reads reject duplicate keys, non-finite values, non-regular files and
excessive size/depth/complexity. Semantic patches are task/revision/evidence
bound. Atomic state replacement and OS locks prevent ordinary interruption and
concurrent writers from corrupting a checkpoint. Generated output conflicts
with authored changes rather than overwriting them. Repository-relative output
paths that escape through symlinks are rejected.

Inspection checks the current excerpt hash and applies contextual redaction
before pagination, including common credential assignments, tokens, connection
URIs, multiline configuration values and PEM private-key blocks. Redaction is
heuristic: it cannot identify every secret or PII value. Do not analyze content
you are not authorized to expose to the current agent, and inspect artifacts
before sharing them. Source bodies are not embedded in exported diagrams.

HTML uses text nodes and an inline escaped JSON payload with a no-network CSP.
It has no eval, remote scripts/fonts, dynamic imports or arbitrary links.
Draw.io labels are plain text; links are restricted to existing internal pages.
Mermaid labels use numeric entities and contain no click handlers. Browser
overrides are presentation-only and do not rewrite the canonical model.

These controls do not prove semantic truth, complete branch coverage, runtime
reachability, broker guarantees, or external viewer compatibility. Known release
evidence gaps are maintained in DEVELOPMENT-STATUS.md. A configured CI job is
not evidence that its OS/runtime checks have run.
