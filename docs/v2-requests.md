# V2 request and investigation contract

This includes the PR-02 foundation and PR-03 ranked retrieval. Adaptive planning,
completion and selective follow-up reuse are later stages. V1 `start` is preserved; there is
no implicit migration, cleanup or overwrite of old workspaces or output bundles.

## Admission fields

The bundled JSON schemas are executable admission contracts. Unknown fields,
wrong types/enums, duplicate JSON keys, nonfinite numbers, excessive nesting,
oversized input and unsafe identifiers/scopes are rejected without echoing
request content. Sensitive-looking text is redacted before hashing/persistence.

| Field | Contract/default |
| --- | --- |
| requestVersion | Required string `2.0` |
| requestId | Optional ASCII alphanumeric/underscore/hyphen ID, maximum 80 characters; generated deterministically from repo and sanitized request when omitted |
| question | Required nonblank original question, maximum 8192 characters |
| intent | Required nonempty unique array drawn from locate/explain/trace/investigate/system_orientation/document |
| audience | String, maximum 200 characters; developer |
| focus | Up to 32 unique strings, 500 characters each; empty |
| indexScope | Repository or safe existing repo-relative path; repository |
| answerScope | Repository or safe existing repo-relative path; repository |
| userOutputPreference | auto/text_only/artifacts; auto |
| deliverable | Required nested DeliverableContract v1 |
| limits | Optional bounded integers, merged with defaults below |
| search | Optional bounded SearchQuery v1; see the retrieval contract |

DeliverableContract requires version `1.0`, a type (chat_answer, focused_map,
interactive_process_map, investigation_report or explicit_artifacts), 1–16
requirements and an explicit formats array. Each requirement has a safe unique
ID, a schema-defined kind and a Boolean required flag. Formats are selected from
markdown/html/drawio/mermaid. Interactive maps require HTML; artifact types need
at least one format; chat answers have none. Text-only preference cannot be
overridden by an artifact contract. These are validation rules, not inferred
intent defaults: the host must choose the contract.

Limits default to 12 probe rounds, 160000 total evidence characters, 12000
characters per probe, 8 graph hops, 200 nodes and 2 no-progress rounds. Accepted
ranges are in the schema. This stage stores limits; enforcement of investigative
rounds is introduced with the later bounded planner. Existing inspect response
limits remain enforced, including request metadata in v2's reply budget.

## Storage and recovery

```text
workspace/
  .mole-v2.json                    # repository binding + active request ID
  repository/
    current.json                  # shared latest source snapshot metadata
    scan-cache.json               # existing parser cache
    .objects/                     # existing content-addressed shards
    snapshots/<revision>.json     # immutable source graph
    semantic/<hash>.json           # accepted semantic overlays, source refs only
  investigations/<request-id>/
    state.json                    # small goal/tasks/pointers/history, never scan
```

The root lock serializes changes. Source/semantic snapshots are written before
session pointers. A failed new-session write may leave an unused immutable
snapshot, while existing sessions and active-request selection remain intact.
All generated child paths are confined and reject symlinks/traversal. A workspace
must neither contain nor be inside the target. Request input is data and never
commands; no target code, dependency installation or network operation is invoked.

Repeated begin with the same sanitized request binding resumes the session.
Changing a bound question or contract yields REQUEST_CONFLICT. Another repository
or index scope yields WORKSPACE_CONFLICT; start a separate store rather than
silently replacing source knowledge. Several requests share the same immutable
source snapshot and object store. An explicit request selector avoids active
request ambiguity; cross-request task references are rejected.

Source changes produce STALE. `diff` is observational. `update` writes a new
shared snapshot, retains the old source/semantic references in session history,
and reopens semantic work conservatively. Neither old objects nor prior artifact
generations are deleted. Questions, task completion and global source coverage
are separate facts. Goal completion is now assessed by `check` and `complete`;
see [completion and follow-up reuse](v2-delivery.md).
