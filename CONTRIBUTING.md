# Contributing

Use Python 3.11+ and the standard library for the installed engine. Keep every
runtime dependency under `skills/mole/`; test a copy outside the checkout.
Do not import or execute analyzed repositories, install their dependencies,
call a model API, fetch runtime resources, or publish outputs implicitly.

Use one bounded feature per branch. Later feature branches may depend on earlier
ones; record the base and validation. Do not combine unrelated changes, rewrite
user edits, or commit/push/merge without authorization. Add focused positive and
negative tests for changed contracts and preservation behavior.

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 tools/evaluate.py --output /tmp/mole-evaluation.json
python3 tools/package_skill.py --output /tmp/mole-review.zip
git diff --check
```

Chrome browser checks use a development-only Node 22+ DevTools harness. Set
`MOLE_BROWSER_EXECUTABLE` to a Chrome executable where needed. Optional official
XSD validation uses `MOLE_DRAWIO_XSD` plus xmllint. Missing tools must be reported
as NOT_RUN/skipped; do not claim those checks passed. No development tool is a
dependency of the installed skill.

Schema and protocol v1 are the candidate contracts. Reject unknown versions;
introduce an explicit migration/version decision for incompatible changes.
Require independent review for security, persistence, update, or data-loss risks.
User acceptance and all required release gates precede a final release/tag.
