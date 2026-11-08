<!-- mole:generated:start id=processes/scenario-20760a5900e3a2cc5ab7b77d.md -->
# Static trace: app.create\_order

Snapshot: `f87ab5183c53141838a5d1f4bea31d156c6a7d03cb0b22441db331f0aa07707c`. Static analysis; runtime behavior is not verified.


Audience: maintainers investigating this static trace.

## Trigger and scope

Entry into the declared callable; actual dispatch is unproven

## Operations

The following are observed declarations/patterns, not a proven execution order.

- app.create\_order (`async\_function`)
- app.post decorator on create\_order (`http\_entry`)
- Async declaration create\_order (`async\_function`)
- session.add candidate (`db\_write`)
- session.commit candidate (`transaction\_boundary`)
- tasks.add\_task candidate (`background\_task`)
- session.rollback candidate (`transaction\_boundary`)
- Try boundary (`control\_try`)
- Raise boundary (`control\_raise`)

## Interpretation and limits

- **source_observed**: The source declares this callable. Its business purpose and runtime execution are not established by this fixture.
  - Limitation: Static fixture analysis; no target code was executed.

## Business mapping

- What: app.create\_order. Why: The source declares this callable. Its business purpose and runtime execution are not established by this fixture.
  - Claim basis: `claim-task-20760a5900e3a2cc5ab7b77d` (source_observed)

## Outcomes and evidence boundaries

- Static evidence boundary at app.post decorator on create\_order
- Static evidence boundary at Async declaration create\_order
- Static evidence boundary at session.add candidate
- Static evidence boundary at session.commit candidate
- Static evidence boundary at tasks.add\_task candidate
- Static evidence boundary at session.rollback candidate
- Static evidence boundary at Try boundary
- Static evidence boundary at Raise boundary
- Static candidates only; runtime ordering and delivery guarantees are unproven.

## Evidence

- `ev-059827f9ad9cedc3a594f4dd`: [app.py](../../../../tests/fixtures/fastapi-db-events/app.py) lines 11–18; source\_code; Try control boundary
- `ev-0baebf3be555d17b9e5ec278`: [app.py](../../../../tests/fixtures/fastapi-db-events/app.py) lines 14–14; source\_code; Possible call to tasks.add\_task
- `ev-4862f3f66a50ceb9b6fc76d2`: [app.py](../../../../tests/fixtures/fastapi-db-events/app.py) lines 17–17; source\_code; Possible call to session.rollback
- `ev-4d6ec685a0bb20386ce6f78d`: [app.py](../../../../tests/fixtures/fastapi-db-events/app.py) lines 12–12; source\_code; Possible call to session.add
- `ev-7a88dcae7a86ba287aafc27c`: [app.py](../../../../tests/fixtures/fastapi-db-events/app.py) lines 10–18; source\_code; Declared async\_function app.create\_order
- `ev-864bcdbcdbb8bca96d1a44f6`: [app.py](../../../../tests/fixtures/fastapi-db-events/app.py) lines 13–13; source\_code; Possible call to session.commit
- `ev-afd7e3664a6e6ade5e0d2ef2`: [app.py](../../../../tests/fixtures/fastapi-db-events/app.py) lines 18–18; source\_code; Raise control boundary

[All processes](../README.md)
<!-- mole:generated:end id=processes/scenario-20760a5900e3a2cc5ab7b77d.md -->

<!-- mole:manual:start -->
<!-- mole:manual:end -->
