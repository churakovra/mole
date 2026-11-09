<!-- mole:generated:start id=architecture.md -->
# Architecture components

**PARTIAL: unresolved tasks or coverage limits remain.**

Snapshot: `a8fb55c9cd1e9eb9f6379a813e23c4b4c1e2167a07dfdada29b4dc4959721cf8`. Static analysis; runtime behavior is not verified.


Components/dependencies below are source candidates, not a verified deployment map.

| Component | Source roles/patterns | Operations |
| --- | --- | --- |
| api.py | async\_function, call\_candidate, control\_return, http\_entry | 5 |
| publisher.py | async\_function, publish | 2 |
| repository.py | call\_candidate, class, control\_raise, control\_return, control\_try, db\_write, function, transaction\_boundary | 11 |
| service.py | async\_function, call\_candidate, control\_return | 5 |
| worker.py | acknowledgement, async\_function, call\_candidate, consume, control\_try | 7 |

## Cross-component and integration candidates

- api.py → service.py (`calls`, possible)
- publisher.py → worker.py (`message\_channel\_candidate`, possible)
- service.py → publisher.py (`calls`, possible)
- service.py → repository.py (`calls`, possible)

## External effects and boundaries

- publisher.py: aio\_pika.Exchange.publish (`publish`; guarantees unverified)
- repository.py: sqlalchemy.orm.Session.add (`db\_write`; guarantees unverified)
- repository.py: sqlalchemy.orm.Session.commit (`transaction\_boundary`; guarantees unverified)
- repository.py: sqlalchemy.orm.Session.rollback (`transaction\_boundary`; guarantees unverified)
- worker.py: aio\_pika.Channel.declare\_queue.consume (`consume`; guarantees unverified)
<!-- mole:generated:end id=architecture.md -->

<!-- mole:manual:start -->
<!-- mole:manual:end -->
