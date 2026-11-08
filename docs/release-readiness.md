# Release readiness — 1.0.0rc1

Status: **REVIEW CANDIDATE; final 1.0.0 release is not accepted or published.**

The local implementation checkpoints cover PR-01 through PR-14. Original backlog
checkboxes remain untouched because implementation, external validation, user
acceptance and publication are different gates.

## Fresh local evidence

- Isolated skill copy and extracted archive run on Python 3.15.2/macOS without
  site packages or root-repository imports. Python 3.9 is rejected explicitly.
- Complete start/next/inspect/submit/finish loop passes with socket/subprocess
  creation denied and an inert target execution sentinel.
- Atomic checkpoint/recovery, locks/crash release, invalid transitions, corrupt
  inputs, real permission denial, semantic patch/provenance, source stale/update,
  rename identity, authored notes and field override regressions pass.
- Real Chrome tests pass against three source models, exact
  390/600/768/1280/1920 viewports, geometry, shared/cyclic navigation, trusted
  mouse pan, keyboard activation, edit/reload, storage failure and conflicts.
- XML/reference/link checks and official mxfile.xsd validation pass with local
  xmllint. The XSD was fetched to /tmp only; runtime does not download it.
- Archive tests compare identical bytes across two builds and run doctor from a
  clean extracted copy. No third-party runtime assets are bundled.
- The offline evaluator passes all three independent fixture pattern sets and
  records parser/cache measurements. It makes no token-saving or semantic-quality claim.

Final local suite: **82 tests passed**, with official XSD configured and real
Chrome enabled. Python 3.11 grammar checks and every command's --help passed;
the actual Python 3.11 runtime remains NOT_RUN. CI is defined but has not run on
a remote runner. Archive checksum and command output are recorded below after build.

## Acceptance gaps

| Gate | State | Remaining evidence |
| --- | --- | --- |
| Python 3.11/3.14, Linux/Windows runtime matrix | NOT_RUN | Execute configured CI and inspect results |
| Firefox/WebKit, touch acceptance | NOT_RUN | Run the viewer interaction suite in those environments |
| diagrams.net editor save round-trip | NOT_RUN | Import, navigate, save and re-open in a real editor |
| Mermaid external parser | NOT_RUN | Validate exported syntax in a supported Mermaid renderer |
| Confluence Cloud + draw.io app | NOT_RUN | Requires authorized test tenant/app; no page was published |
| Equal-quality LLM-led baseline | NOT_RUN | Same fixtures, conditions and blind quality criteria |
| Light/medium/strong model eval and telemetry | NOT_RUN | No endpoints or telemetry were configured |
| Combined user/code/product acceptance | PENDING | Review all stacked branches and remaining limitations |
| Final tag/release/publication | NOT_AUTHORIZED | Separate decision after acceptance |

Known scope limits are in README and the security model: static/name-based
candidates, conservative changed-line invalidation, explicit unresolved dynamic
and cross-module behavior, bounded grid layout/crossings, partial Git ignore
escape syntax, heuristic redaction, and weaker Windows concurrent-attacker
filesystem guarantees. These must not be described as universal runtime analysis.

## Candidate contract and rollback

Schema/protocol v1 reject unknown versions; the engine does not silently migrate
unrecognized state. Claims-only patches remain supported alongside optional
scenario/business/glossary authoring. Pending evidence can produce PARTIAL output
only with an explicit flag. Preserve workspaces and authored sections on errors.

The archive is a review artifact, not an installed or released skill. Roll back
local review by selecting the prior feature checkpoint; do not overwrite a newer
workspace with an older engine without checking its schema. Main is still an
unpopulated initial baseline, so the final merge arrangement needs an explicit
user decision after review. No automatic Git action is part of MOLE runtime.

## Review artifact

`artifacts/mole-1.0.0rc1.zip` (local, ignored by Git), 167437 bytes.

SHA256: `482601487f21e65791bf12bac4a42b2dbb39535f8d3c3ec3093d8da1ad563127`.

Build command: `python3 tools/package_skill.py --output artifacts/mole-1.0.0rc1.zip`.
The adjacent manifest lists every payload file hash.
