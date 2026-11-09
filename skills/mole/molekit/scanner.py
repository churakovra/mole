"""Bounded offline source inventory and Python AST extraction."""

import ast
import fnmatch
import hashlib
import os
from pathlib import Path
import re
import sys
import time

from molekit.errors import MoleError
from molekit.model import empty_model, validate_model
from molekit.workspace import atomic_json, read_json
from molekit.safety import read_source

PARSER_VERSION = "python-ast-v5-" + str(sys.version_info.major) + "." + str(sys.version_info.minor)
IGNORED = {".git", ".mole", "node_modules", ".venv", "venv", "dist", "build", "__pycache__"}
SECRET_NAMES = {"credentials", "credentials.json", "id_rsa", "id_ed25519", ".netrc", ".npmrc"}
MAX_FILE_BYTES = 1024 * 1024
MAX_FILES = 10000


def sha(value):
    return hashlib.sha256(value).hexdigest()


def identity(kind, value):
    return kind + "-" + sha(value.encode())[:24]


SECRET_PATTERN = re.compile(r"-----BEGIN .*PRIVATE KEY|(?:password|secret|api[_-]?key|token)[\"']?\s*[:=]\s*(?:['\"][^'\"]{4,}|[^\s,;]{4,})|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|Bearer\s+[A-Za-z0-9_.-]{12,}|[a-z]+://[^\s/:]+:[^\s/@]+@", re.IGNORECASE)


def sensitive(text):
    return bool(SECRET_PATTERN.search(text))


def redact(text):
    if sensitive(text):
        return "[sensitive source line suppressed]"
    return text


def redacted_lines(content):
    """Detect secrets before pagination so multiline values cannot lose context."""
    content = "\n".join(content.splitlines())
    lines = content.splitlines()
    suppressed = set()
    patterns = [SECRET_PATTERN,
                re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----[\s\S]*?(?:-----END [A-Z0-9 ]*PRIVATE KEY-----|$)"),
                re.compile(r"(?:password|secret|api[_-]?key|token)\s*=\s*(?P<quote>\"\"\"|''')[\s\S]*?(?P=quote)", re.I)]
    for pattern in patterns:
        for match in pattern.finditer(content):
            start = content.count("\n", 0, match.start())
            end = content.count("\n", 0, match.end())
            suppressed.update(range(start, end + 1))
    for index, line in enumerate(lines):
        if re.search(r"(?:password|secret|api[_-]?key|token)[\"']?\s*:\s*[|>][-+]?\s*$", line, re.I):
            suppressed.add(index)
            indent = len(line) - len(line.lstrip())
            for offset in range(index + 1, len(lines)):
                following = lines[offset]
                if following.strip() and len(following) - len(following.lstrip()) <= indent:
                    break
                suppressed.add(offset)
    return ["[sensitive source line suppressed]" if index in suppressed else line
            for index, line in enumerate(lines)]


def ignored(path, rules, is_dir=False):
    result = False
    for base, pattern in rules:
        negative = pattern.startswith("!")
        pattern = pattern.lstrip("!")
        directory_only = pattern.endswith("/")
        pattern = pattern.rstrip("/")
        if directory_only and not is_dir:
            continue
        relative = path[len(base):].lstrip("/") if base else path
        if base and not path.startswith(base + "/"):
            continue
        anchored = pattern.startswith("/")
        pattern = pattern.lstrip("/")
        candidate = relative if anchored or "/" in pattern else relative.split("/")[-1]
        patterns = pattern.split("/")
        active = {0}
        def expand(indices):
            expanded = set(indices)
            for index in sorted(indices):
                while index < len(patterns) and patterns[index] == "**":
                    index += 1
                    expanded.add(index)
            return expanded
        for component in candidate.split("/"):
            active = expand(active)
            active = {index if patterns[index] == "**" else index + 1 for index in active
                      if index < len(patterns) and (patterns[index] == "**" or fnmatch.fnmatchcase(component, patterns[index]))}
        if len(patterns) in expand(active):
            result = not negative
    return result


def inventory(repo, workspace, excluded=(), scope="repository"):
    root = Path(repo).resolve()
    workspace = Path(workspace).resolve()
    excluded = {Path(p).resolve() for p in excluded}
    scoped = root if scope == "repository" else root / scope
    records, limitations = [], []
    total_bytes = 0
    started = time.monotonic()

    def visit(directory, inherited):
        nonlocal records, total_bytes
        if len(directory.relative_to(root).parts) > 128:
            limitations.append({"path": directory.relative_to(root).as_posix(), "reason": "directory_depth_budget_exceeded"})
            return
        if time.monotonic() - started > 30 or len(records) >= MAX_FILES:
            limitations.append({"path": ".", "reason": "inventory_budget_exceeded"})
            return
        rules = list(inherited)
        ignore_file = directory / ".gitignore"
        if ignore_file.is_file() and not ignore_file.is_symlink() and ignore_file.stat().st_size <= MAX_FILE_BYTES:
            for line in read_source(root, ignore_file).decode("utf-8", errors="replace").splitlines():
                pattern = line.strip()
                if pattern and not pattern.startswith("#"):
                    if len(pattern) > 1024 or len(rules) >= 512:
                        limitations.append({"path": ignore_file.relative_to(root).as_posix(), "reason": "ignore_rules_budget_exceeded"})
                        break
                    rules.append(("" if directory == root else directory.relative_to(root).as_posix(), pattern))
        for child in sorted(directory.iterdir()):
            if time.monotonic() - started > 30 or len(records) >= MAX_FILES or total_bytes >= 64 * 1024 * 1024:
                limitations.append({"path": ".", "reason": "inventory_budget_exceeded"})
                return
            relative = child.relative_to(root).as_posix()
            if child != scoped and not child.is_relative_to(scoped) and not scoped.is_relative_to(child):
                continue
            if child.is_symlink():
                limitations.append({"path": relative, "reason": "symlink_excluded"})
                continue
            if child.resolve() in excluded:
                continue
            if child.resolve() == workspace or child.name in IGNORED or child.name in SECRET_NAMES or child.name.startswith(".env"):
                limitations.append({"path": relative, "reason": "excluded_class"})
                continue
            if ignored(relative, rules, child.is_dir()):
                continue
            if child.is_dir():
                visit(child, rules)
            elif child.is_file():
                if child.stat().st_size > MAX_FILE_BYTES:
                    limitations.append({"path": relative, "reason": "file_too_large"})
                    continue
                try:
                    raw = read_source(root, child, min(MAX_FILE_BYTES, 64 * 1024 * 1024 - total_bytes))
                except MoleError:
                    limitations.append({"path": relative, "reason": "source_unavailable_or_budget"})
                    continue
                total_bytes += len(raw)
                if b"\x00" in raw:
                    continue
                try:
                    content = raw.decode("utf-8")
                except UnicodeDecodeError:
                    limitations.append({"path": relative, "reason": "non_utf8"})
                    continue
                records.append({"path": relative, "hash": sha(raw), "content": content})
                if len(records) >= MAX_FILES:
                    return
    visit(root, [])
    return records, limitations


from molekit.python_ast import Extractor


def extract(content, path):
    try:
        tree = ast.parse(content, filename=path)
    except SyntaxError:
        return {"symbols": [], "calls": [], "branches": [], "imports": [], "bindings": [],
                "limitation": "PARSER_UNSUPPORTED_SYNTAX"}
    except (ValueError, RecursionError):
        return {"symbols": [], "calls": [], "branches": [], "imports": [], "bindings": [], "limitation": "PARSER_LIMIT_EXCEEDED"}
    extractor = Extractor(redact)
    try:
        extractor.visit(tree)
    except RecursionError:
        return {"symbols": [], "calls": [], "branches": [], "imports": [], "bindings": [], "limitation": "PARSER_LIMIT_EXCEEDED"}
    if sum(len(items) for items in (extractor.symbols, extractor.calls, extractor.branches, extractor.imports)) > 10000:
        return {"symbols": [], "calls": [], "branches": [], "imports": [], "bindings": [], "limitation": "PARSER_LIMIT_EXCEEDED"}
    return {"symbols": extractor.symbols, "calls": extractor.calls,
            "branches": extractor.branches, "imports": extractor.imports, "bindings": extractor.bindings}


def scan(repo, workspace, excluded=(), scope="repository"):
    deadline = time.monotonic() + 60
    records, limitations = inventory(repo, workspace, excluded, scope)
    cache_path = Path(workspace) / "scan-cache.json"
    cache = read_json(cache_path) if cache_path.exists() else {}
    if not isinstance(cache, dict):
        cache = {}
    revision = sha((PARSER_VERSION + "\n" + "\n".join(r["path"] + ":" + r["hash"] for r in records)).encode())
    model = empty_model(revision)
    facts = {}
    reused = 0
    symbols = {}
    source_spans, evidence_ids, symbol_records, operation_records = {}, set(), {}, {}
    span_occurrences = {}
    record_lines = {r["path"]: r["content"].splitlines() for r in records}

    def evidence(record, line, end, observation, kind="source_code"):
        lines = record_lines[record["path"]][line - 1:end]
        fingerprint = sha("\n".join(lines).encode())
        key = (record["path"], line, end)
        if key not in source_spans:
            anchor = observation
            # Disambiguate equal text/observations without baking line numbers
            # into identity. Unrelated insertions then retain unchanged spans.
            counter_key = (record["path"], fingerprint, anchor)
            occurrence = span_occurrences.get(counter_key, 0)
            span_occurrences[counter_key] = occurrence + 1
            source_id = identity("src", record["path"] + ":" + anchor + ":" + fingerprint + ":" + str(occurrence))
            source_spans[key] = (source_id, fingerprint, anchor)
            model["sources"].append({"id": source_id, "path": record["path"], "revision": revision,
                                      "lineStart": line, "lineEnd": end, "kind": kind})
        source_id = source_spans[key][0]
        ev_id = identity("ev", source_id + observation)
        if ev_id not in evidence_ids:
            evidence_ids.add(ev_id)
            model["evidence"].append({"id": ev_id, "sourceId": source_id, "observation": observation,
                "extractor": PARSER_VERSION, "excerptHash": fingerprint,
                "classification": kind if kind != "source_code" else
                "test_source" if "tests" in Path(record["path"]).parts or Path(record["path"]).name.startswith("test_") else "source_code"})
        return source_id, ev_id

    for record in records:
        if time.monotonic() > deadline:
            limitations.append({"path": ".", "reason": "analysis_time_budget_exceeded"})
            break
        path = record["path"]
        if not path.endswith(".py"):
            suffix = Path(path).suffix.lower()
            if suffix in {".md", ".txt", ".rst", ".json", ".toml", ".yaml", ".yml", ".js", ".ts", ".java", ".go", ".rs"}:
                kind = "documentation" if suffix in {".md", ".txt", ".rst"} else "config" if suffix in {".json", ".toml", ".yaml", ".yml"} else "source_code"
                _, ev = evidence(record, 1, max(1, len(record["content"].splitlines())), "Text input; agent interpretation required", kind)
                model["operations"].append({"id": identity("document", path), "kind": "documented_input" if kind != "source_code" else "text_input",
                                             "title": path, "evidenceIds": [ev]})
                if kind == "source_code":
                    limitations.append({"path": path, "reason": "reduced_coverage_no_ast_adapter"})
            continue
        previous = cache.get(path, {})
        cached = previous.get("facts") if isinstance(previous, dict) else None
        valid_cache = isinstance(cached, dict) and all(isinstance(cached.get(k), list)
                                                     for k in ("symbols", "calls", "branches", "imports", "bindings"))
        if valid_cache:
            for key, required in {"symbols": {"name": str, "kind": str, "line": int, "end": int, "decorators": list},
                                  "calls": {"owner": str, "target": str, "line": int, "end": int, "column": int},
                                  "branches": {"owner": str, "kind": str, "line": int, "end": int},
                                  "imports": {"module": str, "alias": str, "line": int},
                                  "bindings": {"owner": str, "name": str, "type": str, "line": int}}.items():
                valid_cache = valid_cache and all(isinstance(item, dict) and all(
                    isinstance(item.get(field), kind) for field, kind in required.items()) for item in cached[key])
        if valid_cache and previous.get("hash") == record["hash"] and previous.get("parser") == PARSER_VERSION:
            extracted = previous["facts"]
            reused += 1
        else:
            extracted = extract(record["content"], path)
        facts[path] = {"hash": record["hash"], "parser": PARSER_VERSION, "facts": extracted}
        if extracted.get("limitation"):
            limitations.append({"path": path, "reason": extracted["limitation"]})
        for symbol in extracted["symbols"]:
            qualified = path.removesuffix(".py").replace("/", ".") + "." + symbol["name"]
            sid = identity("symbol", qualified)
            source, ev = evidence(record, symbol.get("decoratorLine", symbol["line"]), symbol["end"], "Declared " + symbol["kind"] + " " + qualified)
            existing = symbol_records.get(sid)
            if existing:
                if source not in existing["sourceRefs"]:
                    existing["sourceRefs"].append(source)
                operation = operation_records[identity("op", qualified)]
                if ev not in operation["evidenceIds"]:
                    operation["evidenceIds"].append(ev)
            else:
                model["symbols"].append({"id": sid, "kind": symbol["kind"], "qualifiedName": qualified, "sourceRefs": [source]})
                model["operations"].append({"id": identity("op", qualified), "kind": symbol["kind"],
                                             "title": qualified, "evidenceIds": [ev]})
            symbol_records[sid] = model["symbols"][-1] if not existing else existing
            operation_records[identity("op", qualified)] = model["operations"][-1] if not existing else operation
            symbols[(path, symbol["name"])] = sid

    from molekit.flow import connect
    graph = connect(model, facts, symbols, records, evidence)
    atomic_json(cache_path, facts)
    validate_model(model)
    index = [{"path": r["path"], "hash": r["hash"]} for r in records]
    return {"model": model, "parserVersion": PARSER_VERSION, "index": index, "facts": facts, "unresolved": graph["unresolved"], **graph,
            "limitations": limitations, "stats": {"files": len(index), "parsed": len(facts) - reused, "reused": reused}}
