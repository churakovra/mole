#!/usr/bin/env python3
"""Offline fixture/caching measurements; does not pretend to evaluate an LLM."""

import argparse
import json
from pathlib import Path
import platform
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/mole"))
from molekit.adapters import enrich
from molekit.agent import create_tasks
from molekit.scanner import scan

EXPECTED = {
    "fastapi-db-events": {"http_entry", "db_write", "transaction_boundary", "publish", "background_task"},
    "django-transactions": {"http_route_candidate", "db_write", "transaction_boundary"},
    "consumer-retry-idempotency": {"consume", "acknowledgement", "async_boundary"},
    "cross-file-workflow": {"http_entry", "db_write", "transaction_boundary", "publish", "consume", "acknowledgement"},
}


def evaluate():
    results = []
    for fixture, expected in EXPECTED.items():
        repo = ROOT / "tests/fixtures" / fixture
        with tempfile.TemporaryDirectory() as tmp:
            started = time.perf_counter()
            first = enrich(scan(repo, tmp))
            first_seconds = time.perf_counter() - started
            started = time.perf_counter()
            second = enrich(scan(repo, tmp))
            second_seconds = time.perf_counter() - started
            actual = {operation["kind"] for operation in first["model"]["operations"]}
            missing = sorted(expected - actual)
            tasks = create_tasks(first, "standard")
            workflow_check = True
            if fixture == 'cross-file-workflow':
                sources = {source['id']: source['path'] for source in first['model']['sources']}
                evidence = {item['id']: sources[item['sourceId']] for item in first['model']['evidence']}
                workflow_check = any(task['kind'] == 'workflow_review' and
                    {'api.py','service.py','repository.py','publisher.py','worker.py'} <= {evidence[eid] for eid in task['evidenceIds']}
                    for task in tasks)
            results.append({"fixture": fixture, "goldenPatterns": "PASS" if not missing else "FAIL",
                'workflowScope': 'PASS' if workflow_check else 'FAIL',
                "missingPatterns": missing, "sourceBytes": sum(path.stat().st_size for path in repo.rglob("*.py")),
                "taskPayloadBytes": len(json.dumps(tasks).encode()), "firstScanSeconds": first_seconds,
                "cachedScanSeconds": second_seconds, "cache": second["stats"],
                "staticEdgesOnly": all(edge["resolution"] != "observed_runtime" for edge in first["model"]["relationships"])})
    with tempfile.TemporaryDirectory() as tmp:
        repo, workspace = Path(tmp) / 'negative', Path(tmp) / 'workspace'
        repo.mkdir()
        workspace.mkdir()
        (repo / 'app.py').write_text('from sqlalchemy.orm import Session\nclass Cache:\n    objects = set()\ndef local_only():\n    values=set()\n    values.add(1)\n    Cache.objects.add(2)\n')
        negative = enrich(scan(repo,workspace))
        adapter_negative = not any(op['kind'] in {'db_write','db_read'} for op in negative['model']['operations'])
    return {"environment": {"python": platform.python_version(), "platform": platform.system()},
            "fixtures": results, "tokens": "unavailable", "llmLedBaseline": "NOT_RUN",
            'negativeAdapterCheck': 'PASS' if adapter_negative else 'FAIL',
            "multiModelEval": "NOT_RUN", "semanticBlindReview": "NOT_RUN",
            "limitations": ["Measures parser/cache and fixture pattern checks only.",
                            "Task payload bytes are not token usage or demonstrated savings.",
                            "No light/medium/strong LLM endpoints or telemetry configured."]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    raise SystemExit(result['negativeAdapterCheck'] != 'PASS' or any(item["goldenPatterns"] != "PASS" or item['workflowScope'] != 'PASS' for item in result["fixtures"]))
