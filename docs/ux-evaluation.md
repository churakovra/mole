# Test handoff and independent acceptance

The predeclared registry contains 40 prompts across six fixture repositories in
`tests/fixtures/acceptance/prompts.json`. Its NOT_RUN labels are inputs, not test
results. Do not infer model quality from passing parser or browser assertions.
The game-settlement fixture covers documented TypeScript verification, Python
completion, eligibility, wallet failure and independent cosmetic purchase;
duplicate delivery and atomicity are deliberately unverified.

## Reproduce an installed-skill trial

```sh
python3 tools/package_skill.py --output /tmp/mole-skill.zip
python3 tools/evaluate_agent_workflows.py prepare \
  --archive /tmp/mole-skill.zip --output /tmp/mole-trials-new
```

Give a fresh agent ONLY the installed skill path and a registry prompt/target
from assignment.json. Workspaces and artifacts belong outside the fixture.
Never execute fixture code. Save the action/tool transcript, final response,
`check` receipt, source revision and concrete artifact paths. For critical locate
and orientation cases run at least three independent trials. The engine itself
needs Python only; Chrome/Node are development verification tools.

Receipt JSON fields: `caseId`, `trial`, `skillActivated` (agent attestation),
`workspace`, `transcript` (existing file), `artifacts` (absolute existing files),
`actualPrompt`, `finalResponse` (file), and optional runtime/model metadata.
Collect and summarize actual receipts:

```sh
python3 tools/evaluate_agent_workflows.py collect \
  --run-root /tmp/mole-trials-new --receipt /tmp/receipt.json
python3 tools/evaluate_agent_workflows.py summarize --run-root /tmp/mole-trials-new
```

The harness checks fixture hashes, installed-engine goal/freshness validation,
required deliverable, transcript existence and declared artifact files. Transcript
existence and activation attestation do not establish semantic correctness.
No run is manufactured for absent receipts; remaining cases stay NOT_RUN.

## Human test steps

For a concise question, check the named source and ensure no unrelated export is
forced. For service orientation, open the returned Explorer and identify what
starts each process, its conditions, success/failure outcome and unknowns. Open
two subprocesses, select an edge, inspect evidence and use Back. Repeat at desktop
and 390/320px widths. Confirm that purchase is independent and TypeScript is not
claimed runtime-verified. Ask a follow-up about duplicate completion or rollback;
then edit a contributing source in a disposable copy and confirm stale readiness
is revoked before update/reinvestigation. Preserve manual notes when regenerating.

## Blind rubric and release gates

An independent human receives artifacts with agent variant hidden. Score 1–5
for usefulness, correctness, completeness, navigability and clarity of unknowns;
record concrete unsupported claims, missing handoffs and broken navigation.
Use the same predeclared cases for plain-agent, v1 and new-version comparisons.
Keep raw scores, disagreements, prompt hashes and runtime metadata. Agent
self-review cannot supply this grade. Do not claim a causal improvement or token
savings without comparable measured runs.

Targets remain unmeasured until real human/baseline runs: at least 90% goal
completion on the full registry, 85% first-run completion and median usefulness
4/5. A missing required artifact with READY, invented runtime guarantee, secret
leak or silent target mutation is a critical failure requiring a regression fix.
The owner's private Doofy service and external app/editor acceptance are not
available in these fixtures; run them read-only on the owner's machine before a
stable release. No merge, deployment or release is part of this handoff.
