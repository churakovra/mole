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

PARSER_VERSION = "python-ast-v2-" + str(sys.version_info.major) + "." + str(sys.version_info.minor)
IGNORED = {".git", ".mole", "node_modules", ".venv", "venv", "dist", "build", "__pycache__"}
SECRET_NAMES = {"credentials", "credentials.json", "id_rsa", "id_ed25519", ".netrc", ".npmrc"}
MAX_FILE_BYTES = 1024 * 1024
MAX_FILES = 10000


def sha(value):
    return hashlib.sha256(value).hexdigest()


def identity(kind, value):
    return kind + "-" + sha(value.encode())[:24]


def sensitive(text):
    return bool(re.search(r"-----BEGIN .*PRIVATE KEY|(?:password|secret|api[_-]?key|token)\s*[:=]\s*['\"][^'\"]{4,}",
                          text, re.IGNORECASE))


def redact(text):
    if sensitive(text):
        return "[sensitive source line suppressed]"
    return text


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
        if fnmatch.fnmatchcase(candidate, pattern):
            result = not negative
    return result


def inventory(repo, workspace):
    root = Path(repo).resolve()
    workspace = Path(workspace).resolve()
    records, limitations = [], []
    started = time.monotonic()

    def visit(directory, inherited):
        nonlocal records
        if time.monotonic() - started > 30 or len(records) >= MAX_FILES:
            limitations.append({"path": ".", "reason": "inventory_budget_exceeded"})
            return
        rules = list(inherited)
        ignore_file = directory / ".gitignore"
        if ignore_file.is_file() and not ignore_file.is_symlink() and ignore_file.stat().st_size <= MAX_FILE_BYTES:
            for line in ignore_file.read_text(encoding="utf-8", errors="replace").splitlines():
                pattern = line.strip()
                if pattern and not pattern.startswith("#"):
                    rules.append(("" if directory == root else directory.relative_to(root).as_posix(), pattern))
        for child in sorted(directory.iterdir()):
            if time.monotonic() - started > 30 or len(records) >= MAX_FILES:
                limitations.append({"path": ".", "reason": "inventory_budget_exceeded"})
                return
            relative = child.relative_to(root).as_posix()
            if child.is_symlink():
                limitations.append({"path": relative, "reason": "symlink_excluded"})
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
                raw = child.read_bytes()
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


def called_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = called_name(node.value)
        return (parent + "." if parent else "") + node.attr
    return "<dynamic>"


class Extractor(ast.NodeVisitor):
    def __init__(self):
        self.owner = []
        self.symbols = []
        self.calls = []
        self.branches = []
        self.imports = []

    def visit_Import(self, node):
        self.imports.extend({"module": alias.name, "alias": alias.asname or alias.name,
                             "line": node.lineno} for alias in node.names)

    def visit_ImportFrom(self, node):
        self.imports.extend({"module": (node.module or "") + "." + alias.name,
                             "alias": alias.asname or alias.name, "line": node.lineno}
                            for alias in node.names)

    def visit_FunctionDef(self, node):
        self.symbol(node, "function")

    def visit_AsyncFunctionDef(self, node):
        self.symbol(node, "async_function")

    def visit_ClassDef(self, node):
        self.symbol(node, "class")

    def symbol(self, node, kind):
        self.owner.append(node.name)
        name = ".".join(self.owner)
        self.symbols.append({"name": name, "kind": kind, "line": node.lineno,
                             "end": node.end_lineno,
                             "decorators": [called_name(d.func if isinstance(d, ast.Call) else d)
                                            for d in node.decorator_list]})
        self.generic_visit(node)
        self.owner.pop()

    def visit_Call(self, node):
        self.calls.append({"owner": ".".join(self.owner) if self.owner else "<module>",
                           "target": called_name(node.func), "line": node.lineno,
                           "end": node.end_lineno, "column": node.col_offset})
        self.generic_visit(node)

    def generic_visit(self, node):
        if self.owner and isinstance(node, (ast.If, ast.For, ast.While, ast.Try, ast.Raise,
                                            ast.Await, ast.With, ast.AsyncWith, ast.Return)):
            self.branches.append({"owner": ".".join(self.owner), "kind": type(node).__name__,
                                  "line": node.lineno, "end": node.end_lineno})
        super().generic_visit(node)


def extract(content, path):
    try:
        tree = ast.parse(content, filename=path)
    except SyntaxError:
        return {"symbols": [], "calls": [], "branches": [], "imports": [],
                "limitation": "PARSER_UNSUPPORTED_SYNTAX"}
    except (ValueError, RecursionError):
        return {"symbols": [], "calls": [], "branches": [], "imports": [], "limitation": "PARSER_LIMIT_EXCEEDED"}
    extractor = Extractor()
    try:
        extractor.visit(tree)
    except RecursionError:
        return {"symbols": [], "calls": [], "branches": [], "imports": [], "limitation": "PARSER_LIMIT_EXCEEDED"}
    return {"symbols": extractor.symbols, "calls": extractor.calls,
            "branches": extractor.branches, "imports": extractor.imports}


def scan(repo, workspace):
    records, limitations = inventory(repo, workspace)
    cache_path = Path(workspace) / "scan-cache.json"
    cache = read_json(cache_path) if cache_path.exists() else {}
    if not isinstance(cache, dict):
        cache = {}
    revision = sha("\n".join(r["path"] + ":" + r["hash"] for r in records).encode())
    model = empty_model(revision)
    facts = {}
    reused = 0
    symbols = {}

    def evidence(record, line, end, observation):
        source_id = identity("src", record["path"] + ":" + str(line) + ":" + str(end) + ":" + record["hash"])
        ev_id = identity("ev", source_id + observation)
        if not any(s["id"] == source_id for s in model["sources"]):
            model["sources"].append({"id": source_id, "path": record["path"], "revision": revision,
                                      "lineStart": line, "lineEnd": end, "kind": "source_code"})
        if not any(e["id"] == ev_id for e in model["evidence"]):
            lines = record["content"].splitlines()[line - 1:end]
            model["evidence"].append({"id": ev_id, "sourceId": source_id, "observation": observation,
                                       "extractor": PARSER_VERSION, "excerptHash": sha("\n".join(lines).encode()),
                                       "classification": "test_source" if "test" in record["path"] else "source_code"})
        return source_id, ev_id

    for record in records:
        path = record["path"]
        if not path.endswith(".py"):
            continue
        previous = cache.get(path, {})
        cached = previous.get("facts") if isinstance(previous, dict) else None
        valid_cache = isinstance(cached, dict) and all(isinstance(cached.get(k), list)
                                                     for k in ("symbols", "calls", "branches", "imports"))
        if valid_cache:
            for key, required in {"symbols": {"name": str, "kind": str, "line": int, "end": int, "decorators": list},
                                  "calls": {"owner": str, "target": str, "line": int, "end": int, "column": int},
                                  "branches": {"owner": str, "kind": str, "line": int, "end": int},
                                  "imports": {"module": str, "alias": str, "line": int}}.items():
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
            source, ev = evidence(record, symbol["line"], symbol["end"], "Declared " + symbol["kind"] + " " + qualified)
            existing = next((s for s in model["symbols"] if s["id"] == sid), None)
            if existing:
                if source not in existing["sourceRefs"]:
                    existing["sourceRefs"].append(source)
                operation = next(o for o in model["operations"] if o["id"] == identity("op", qualified))
                if ev not in operation["evidenceIds"]:
                    operation["evidenceIds"].append(ev)
            else:
                model["symbols"].append({"id": sid, "kind": symbol["kind"], "qualifiedName": qualified, "sourceRefs": [source]})
                model["operations"].append({"id": identity("op", qualified), "kind": symbol["kind"],
                                             "title": qualified, "evidenceIds": [ev]})
            symbols[(path, symbol["name"])] = sid

    unresolved = []
    for record in records:
        path = record["path"]
        if path not in facts:
            continue
        for call in facts[path]["facts"]["calls"]:
            source = symbols.get((path, call["owner"]))
            candidates = [sid for (p, name), sid in symbols.items() if p == path and name == call["target"]]
            _, ev = evidence(record, call["line"], call["end"], "Possible call to " + call["target"])
            if source and len(candidates) == 1:
                model["relationships"].append({"id": identity("edge", path + str(call["line"]) + ":" + str(call["column"]) + call["owner"] + call["target"]),
                    "source": source, "target": candidates[0], "kind": "calls", "resolution": "possible",
                    "evidenceIds": [ev], "condition": "Static call site; runtime reachability unproven"})
            else:
                unresolved.append({"evidenceId": ev, "target": call["target"], "owner": source})
        for branch in facts[path]["facts"]["branches"]:
            evidence(record, branch["line"], branch["end"], branch["kind"] + " control boundary")
    atomic_json(cache_path, facts)
    validate_model(model)
    index = [{"path": r["path"], "hash": r["hash"]} for r in records]
    return {"model": model, "index": index, "facts": facts, "unresolved": unresolved,
            "limitations": limitations, "stats": {"files": len(index), "parsed": len(facts) - reused, "reused": reused}}
