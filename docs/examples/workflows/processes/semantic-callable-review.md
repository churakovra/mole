<!-- mole:generated:start id=processes/semantic-callable-review.md -->
# Callable review: app.create\_order

Snapshot: `f87ab5183c53141838a5d1f4bea31d156c6a7d03cb0b22441db331f0aa07707c`. Static analysis; runtime behavior is not verified.


Audience: maintainers investigating this static trace.

## Trigger and scope

A declaration is present in the supplied fixture

## Operations

The following are observed declarations/patterns, not a proven execution order.

- Callable review: app.create\_order (`scenario\_summary`)
- app.create\_order (`async\_function`)

## Interpretation and limits

- **source_observed**: The source declares this callable. Its business purpose and runtime execution are not established by this fixture.
  - Limitation: Static fixture analysis; no target code was executed.

## Business mapping

- What: app.create\_order. Why: The source declares this callable. Its business purpose and runtime execution are not established by this fixture.
  - Claim basis: `claim-task-20760a5900e3a2cc5ab7b77d` (source_observed)

## Outcomes and evidence boundaries

- A declaration was observed; runtime execution is unknown
- Business policy is not supplied by this fixture

## Evidence

- `ev-059827f9ad9cedc3a594f4dd`: [app.py](../../../../tests/fixtures/fastapi-db-events/app.py) lines 11–18; source\_code; Try control boundary
- `ev-0baebf3be555d17b9e5ec278`: [app.py](../../../../tests/fixtures/fastapi-db-events/app.py) lines 14–14; source\_code; Possible call to tasks.add\_task
- `ev-4862f3f66a50ceb9b6fc76d2`: [app.py](../../../../tests/fixtures/fastapi-db-events/app.py) lines 17–17; source\_code; Possible call to session.rollback
- `ev-4d6ec685a0bb20386ce6f78d`: [app.py](../../../../tests/fixtures/fastapi-db-events/app.py) lines 12–12; source\_code; Possible call to session.add
- `ev-7a88dcae7a86ba287aafc27c`: [app.py](../../../../tests/fixtures/fastapi-db-events/app.py) lines 10–18; source\_code; Declared async\_function app.create\_order
- `ev-864bcdbcdbb8bca96d1a44f6`: [app.py](../../../../tests/fixtures/fastapi-db-events/app.py) lines 13–13; source\_code; Possible call to session.commit
- `ev-afd7e3664a6e6ade5e0d2ef2`: [app.py](../../../../tests/fixtures/fastapi-db-events/app.py) lines 18–18; source\_code; Raise control boundary

[All processes](../README.md)
<!-- mole:generated:end id=processes/semantic-callable-review.md -->

<!-- mole:manual:start -->
<!-- mole:manual:end -->
