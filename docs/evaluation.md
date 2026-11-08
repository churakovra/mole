# Evaluation method and observed scope

Run `python3 tools/evaluate.py --output /tmp/mole-evaluation.json` without a
network connection or third-party Python packages. The checked-in result records
the actual environment and measurements from this development session.

Three representative fixtures have independent expected pattern sets:
FastAPI/database/events, Django/transactions, and a consumer/acknowledgement
loop. The evaluator checks those patterns, forbids automatically verified
runtime edges, and measures initial/cached parsing and cache reuse.
It records source bytes and task payload bytes separately. A small fixture can
have a larger JSON task payload than source; no token/cost-saving claim follows.

The required equal-quality comparison against an LLM-led baseline, blind
semantic assessment, and light/medium/strong model eval remain NOT_RUN. No
corresponding endpoints or telemetry were configured. Tokens are unavailable.
These gaps block a final 1.0.0 readiness claim; parser timing is not a substitute.

Real Chrome tests cover offline rendering across three models, the exact
390/600/768/1280/1920 viewport matrix, geometry, shared/cyclic navigation,
selection/drill/Back, keyboard activation, actual mouse drag/pointer release,
local edit/reload, conflict handling and blocked/malformed/oversized storage.
Firefox/WebKit and touch-device acceptance have not been run.
