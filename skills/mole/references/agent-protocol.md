# Local task protocol

All commands below use `python3 <ABSOLUTE_SKILL_DIR>/scripts/mole.py`.

1. `doctor --json` checks the interpreter.
2. `start --repo <REPO> --workspace <WORKSPACE> --mode standard --scope repository --json`
   creates or resumes a session. Prefer an external workspace for read-only analysis.
3. `next --workspace <WORKSPACE> --json` scans once and returns the highest-priority
   pending task. Repeated next is safe and does not complete tasks.
4. `inspect --workspace <WORKSPACE> --task <TASK_ID> --budget-chars 12000 --json`
   returns source-located context. Continue with `--cursor <nextCursor>` until null.
5. Write a semantic-patch JSON file and pass it to
   `submit --workspace <WORKSPACE> --input <PATCH_FILE> --json`.
   Use protocolVersion `1.0`, taskId, baseRevision, and a nonempty claims array.
   Each claim has id, statement, status, evidenceIds, limitations.
   Cite only evidence IDs on that task. Prefer `unknown` with a limitation to
   guessing. Never claim runtime verification from source code alone.
6. Repeat until status is VALIDATING. Use `status` to resume after interruption.

Duplicate identical patches are safe; changed duplicate responses conflict.
Changed source returns TASK_STALE; refresh before resubmitting. Quality gates
and export are owned by the engine. Completion must not be inferred from the chat.
quick/standard/deep limit semantic task counts to 20/100/500 respectively;
truncation is explicitly recorded as a limitation, not full coverage.
No LLM API calls occur inside the engine.
