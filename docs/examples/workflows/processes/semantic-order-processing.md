<!-- mole:generated:start id=processes/semantic-order-processing.md -->
# Order processing \(static candidate\)

**PARTIAL: unresolved tasks or coverage limits remain.**

Snapshot: `a8fb55c9cd1e9eb9f6379a813e23c4b4c1e2167a07dfdada29b4dc4959721cf8`. Static analysis; runtime behavior is not verified.


Audience: maintainers and reviewers investigating this bounded workflow.

## Actors and preconditions

Actors: Requesting client \(inferred\), Registered worker callback \(static\)
Preconditions: Configured session and broker are assumptions, not verified deployment facts.

## Trigger and scope

HTTP order request

## Main path

Numbering is a static/authored candidate order, not proof of runtime reachability or delivery.

1. api.create\_order (`async\_function`; `op-08623c4113c609e1113ce9be`) — api.py:7
2. service.execute (`call\_candidate`; `call-f4432cb0c93cebec6c41c48b`) — api.py:9, api.py:2
3. repository.Store.save (`call\_candidate`; `call-224ecb47dab74f0ee69a9f0b`) — service.py:8, service.py:1
4. sqlalchemy.orm.Session.add (`db\_write`; `call-11ad12a535a4dbbc83375123`) — repository.py:7, repository.py:1
5. sqlalchemy.orm.Session.commit (`transaction\_boundary`; `call-5a3fa4630ddc6cde917744bc`) — repository.py:8, repository.py:1
6. publisher.publish\_order (`call\_candidate`; `call-a6ccf3d7057244ba8d57cd51`) — service.py:9, service.py:2
7. aio\_pika.Exchange.publish (`publish`; `call-7a194f23936534c744e83feb`) — publisher.py:4, publisher.py:1
8. worker.handle\_order (`async\_function`; `op-b1577e1682ca0dfd55998ca5`) — worker.py:3

## Alternative and failure paths

- Condition: ValueError in Store.save
  - sqlalchemy.orm.Session.rollback (`transaction\_boundary`)
  - Outcome: Matching handler attempts rollback; other failures remain unknown.

## Data, state and integration effects

- Static storage and publication candidates; neither transaction success nor message delivery was executed.

[Open workflow diagram](../explorer.html#view=view-6fe38e317b0c1634229171f2)


## Interpretation and limits

- **inferred**: Source contains connected HTTP, storage, publication and registered consumer candidates.
  - Limitation: Synthetic fixture; no target code or infrastructure was executed.

## Outcomes and evidence boundaries

- Source links the entry, service, store, publisher and registered consumer candidates.
- Runtime routing, registration startup, delivery, retries and business policy require independent evidence.

## Evidence

- `ev-0029cef699c0dc9382b8f687`: [api.py](../../../../tests/fixtures/cross-file-workflow/api.py) lines 7–9; source\_code; Declared async\_function api.create\_order
- `ev-067abab1aa7d1d6af36880f7`: [service.py](../../../../tests/fixtures/cross-file-workflow/service.py) lines 6–10; source\_code; Declared async\_function service.execute
- `ev-09757987ba310b53c3dfd729`: [repository.py](../../../../tests/fixtures/cross-file-workflow/repository.py) lines 11–11; source\_code; Call candidate Store.save: session.rollback \#0
- `ev-099954498e9bd7ee0d50c8a9`: [api.py](../../../../tests/fixtures/cross-file-workflow/api.py) lines 9–9; source\_code; Call candidate create\_order: run\_order \#0
- `ev-0ac273b2fbb1ba1c68519559`: [repository.py](../../../../tests/fixtures/cross-file-workflow/repository.py) lines 7–7; source\_code; Call candidate Store.save: session.add \#0
- `ev-16244f6a70d27e3fb2d433ff`: [worker.py](../../../../tests/fixtures/cross-file-workflow/worker.py) lines 1–1; source\_code; Import binding aio\_pika
- `ev-2570ab928741ad34221503eb`: [service.py](../../../../tests/fixtures/cross-file-workflow/service.py) lines 10–10; source\_code; execute: Return  \#0
- `ev-2907cdf4f1bef5993275478b`: [repository.py](../../../../tests/fixtures/cross-file-workflow/repository.py) lines 15–15; source\_code; Store.validate: Return  \#0
- `ev-2a6e32218a615d8638b52fb6`: [repository.py](../../../../tests/fixtures/cross-file-workflow/repository.py) lines 8–8; source\_code; Call candidate Store.save: session.commit \#0
- `ev-42dba25109642b37d718cbae`: [service.py](../../../../tests/fixtures/cross-file-workflow/service.py) lines 2–2; source\_code; Import binding publish\_order
- `ev-4e145f5bcc687fca2e595039`: [worker.py](../../../../tests/fixtures/cross-file-workflow/worker.py) lines 7–7; source\_code; Call candidate handle\_order: message.nack \#0
- `ev-4fa62ce9c3f9f623acd3daaa`: [publisher.py](../../../../tests/fixtures/cross-file-workflow/publisher.py) lines 1–1; source\_code; Import binding aio\_pika
- `ev-56060b2771b1e9a94b63e8af`: [publisher.py](../../../../tests/fixtures/cross-file-workflow/publisher.py) lines 4–4; source\_code; Call candidate publish\_order: exchange.publish \#0
- `ev-6132280cc70c7446fd41d78c`: [api.py](../../../../tests/fixtures/cross-file-workflow/api.py) lines 9–9; source\_code; create\_order: Return  \#0
- `ev-62da67e234bc1795534f1433`: [repository.py](../../../../tests/fixtures/cross-file-workflow/repository.py) lines 5–12; source\_code; Store.save: Try  \#0
- `ev-6c9b241a667730b5de3f428a`: [publisher.py](../../../../tests/fixtures/cross-file-workflow/publisher.py) lines 3–4; source\_code; Declared async\_function publisher.publish\_order
- `ev-77b51999e339896f0124294d`: [worker.py](../../../../tests/fixtures/cross-file-workflow/worker.py) lines 3–7; source\_code; Declared async\_function worker.handle\_order
- `ev-7803508d02cc9657dd44ec7a`: [repository.py](../../../../tests/fixtures/cross-file-workflow/repository.py) lines 4–12; source\_code; Declared function repository.Store.save
- `ev-7a6a9ab82ace2bff009b22dc`: [repository.py](../../../../tests/fixtures/cross-file-workflow/repository.py) lines 12–12; source\_code; Store.save: Raise  \#0
- `ev-7aac706bbc5378b208d4e632`: [repository.py](../../../../tests/fixtures/cross-file-workflow/repository.py) lines 14–15; source\_code; Declared function repository.Store.validate
- `ev-83d1997ac922aec120adc301`: [worker.py](../../../../tests/fixtures/cross-file-workflow/worker.py) lines 11–11; source\_code; Call candidate register: queue.consume \#0
- `ev-8da72c64824144701c2dcf75`: [worker.py](../../../../tests/fixtures/cross-file-workflow/worker.py) lines 5–5; source\_code; Call candidate handle\_order: message.ack \#0
- `ev-8f818703c2ae7bc28b4d36d5`: [repository.py](../../../../tests/fixtures/cross-file-workflow/repository.py) lines 3–15; source\_code; Declared class repository.Store
- `ev-90d2b9170d7e78e8f4bea6ff`: [service.py](../../../../tests/fixtures/cross-file-workflow/service.py) lines 1–1; source\_code; Import binding Store
- `ev-978d2c295f5b56eba2a69711`: [repository.py](../../../../tests/fixtures/cross-file-workflow/repository.py) lines 6–6; source\_code; Call candidate Store.save: self.validate \#0
- `ev-9958bb06a99d845fb0972ddc`: [service.py](../../../../tests/fixtures/cross-file-workflow/service.py) lines 7–7; source\_code; Call candidate execute: Store \#0
- `ev-99a42c8ff18eb9bd15b0c0b5`: [repository.py](../../../../tests/fixtures/cross-file-workflow/repository.py) lines 9–9; source\_code; Store.save: Return  \#0
- `ev-aa33a1c819a0a29bf9d7dd20`: [service.py](../../../../tests/fixtures/cross-file-workflow/service.py) lines 8–8; source\_code; Call candidate execute: store.save \#0
- `ev-d6e97df3ad1d8030ca2792f5`: [worker.py](../../../../tests/fixtures/cross-file-workflow/worker.py) lines 4–7; source\_code; handle\_order: Try  \#0
- `ev-de4958de7af16f2464833712`: [repository.py](../../../../tests/fixtures/cross-file-workflow/repository.py) lines 1–1; source\_code; Import binding Session
- `ev-df67d543d823137bbe785261`: [service.py](../../../../tests/fixtures/cross-file-workflow/service.py) lines 9–9; source\_code; Call candidate execute: publish\_order \#0
- `ev-febc5da01921e95ac0457334`: [api.py](../../../../tests/fixtures/cross-file-workflow/api.py) lines 2–2; source\_code; Import binding run\_order

[All processes](../README.md)
<!-- mole:generated:end id=processes/semantic-order-processing.md -->

<!-- mole:manual:start -->
<!-- mole:manual:end -->
