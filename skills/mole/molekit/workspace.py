"""Single-file transactional workspace with OS-owned crash-safe locks."""

from contextlib import contextmanager
import json
import os
import stat
from pathlib import Path
import tempfile

from molekit.errors import MoleError

MAX_JSON_BYTES = 16 * 1024 * 1024


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def invalid_constant(value):
    raise ValueError("Non-finite JSON number")


def check_complexity(value):
    pending = [(value, 0)]
    count = 0
    while pending:
        item, depth = pending.pop()
        count += 1
        if depth > 64 or count > 200000:
            raise MoleError("INVALID_JSON", "JSON complexity limit exceeded.")
        if isinstance(item, dict):
            pending.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            pending.extend((child, depth + 1) for child in item)


def read_json(path):
    path = Path(path)
    if path.is_symlink():
        raise MoleError("UNSAFE_PATH", "JSON files must not be symlinks.")
    try:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        with os.fdopen(os.open(path, flags), "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise MoleError("UNSAFE_PATH", "JSON input must be a regular file.")
            raw = stream.read(MAX_JSON_BYTES + 1)
        if len(raw) > MAX_JSON_BYTES:
            raise MoleError("INVALID_JSON", "JSON exceeds size limit.")
        value = json.loads(raw, object_pairs_hook=unique_object, parse_constant=invalid_constant)
        check_complexity(value)
        return value
    except (ValueError, RecursionError) as exc:
        raise MoleError("INVALID_JSON", "Malformed or excessively nested JSON.") from exc


def atomic_json(path, value):
    path = Path(path)
    check_complexity(value)
    encoded = (json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2,
                          allow_nan=False) + "\n").encode()
    if len(encoded) > MAX_JSON_BYTES:
        raise MoleError("INVALID_JSON", "Workspace exceeds size limit.")
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".mole-")
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def locked(directory, create=False):
    directory = Path(directory).absolute()
    if directory.is_symlink():
        raise MoleError("UNSAFE_PATH", "Workspace must not be a symlink.")
    if create:
        directory.mkdir(parents=True, exist_ok=True)
    if not directory.is_dir():
        raise MoleError("WORKSPACE_MISSING", "Workspace does not exist.")
    lock_path = directory / ".lock"
    if lock_path.is_symlink():
        raise MoleError("UNSAFE_PATH", "Workspace lock must not be a symlink.")
    descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
                         | getattr(os, "O_NONBLOCK", 0), 0o600)
    with os.fdopen(descriptor, "r+b") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise MoleError("UNSAFE_PATH", "Lock must be a regular file.")
        if os.name == "nt":
            import msvcrt
            if stream.seek(0, 2) == 0:
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise MoleError("WORKSPACE_BUSY", "Workspace is locked.", 4,
                                "Wait for the other operation to exit.") from exc
        else:
            import fcntl
            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise MoleError("WORKSPACE_BUSY", "Workspace is locked.", 4,
                                "Wait for the other operation to exit.") from exc
        try:
            yield directory
        finally:
            if os.name == "nt":
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def load(directory):
    state = read_json(Path(directory) / "state.json")
    if not isinstance(state, dict) or type(state.get("schemaVersion")) is not int or state["schemaVersion"] != 1:
        raise MoleError("SCHEMA_MISMATCH", "Unsupported workspace schema.")
    from molekit.pipeline import STATES
    if (not isinstance(state.get("status"), str) or state["status"] not in STATES
            or not isinstance(state.get("runId"), str)
            or not state["runId"] or "revision" not in state
            or not (state["revision"] is None or isinstance(state["revision"], str))
            or not isinstance(state.get("manifest"), dict)
            or any(not isinstance(state["manifest"].get(k), str)
                   for k in ("repo", "mode", "scope", "engineVersion"))
            or not isinstance(state.get("tasks"), list)
            or any(not isinstance(t, dict) or not isinstance(t.get("id"), str)
                   or t.get("status") not in ("pending", "completed") for t in state["tasks"])
            or not isinstance(state.get("submissions"), dict)
            or any(not isinstance(k, str) or not isinstance(v, str)
                   for k, v in state["submissions"].items())):
        raise MoleError("STATE_CORRUPT", "Workspace state is invalid.", 5)
    if (state["status"] not in {"NEW", "SCANNING", "BLOCKED", "FAILED"}
            or state["tasks"] or state["submissions"]) and "scan" not in state:
        raise MoleError("STATE_CORRUPT", "Advanced session is missing its scan.", 5)
    if "scan" in state:
        from molekit.model import contract, validate_model
        scan = state["scan"]
        if (not isinstance(scan, dict) or not isinstance(scan.get("model"), dict)
                or not isinstance(scan.get("index"), list)
                or any(not isinstance(item, dict) or not isinstance(item.get("path"), str)
                       or not isinstance(item.get("hash"), str) for item in scan["index"])):
            raise MoleError("STATE_CORRUPT", "Workspace scan is invalid.", 5)
        validate_model(scan["model"])
        if state["revision"] != scan["model"]["revision"]:
            raise MoleError("STATE_CORRUPT", "Workspace revisions disagree.", 5)
        task_ids = set()
        evidence_ids = {ev["id"] for ev in scan["model"]["evidence"]}
        operation_ids = {op["id"] for op in scan["model"]["operations"]}
        for task in state["tasks"]:
            contract(task, "task")
            if (task["id"] in task_ids or task["baseRevision"] != state["revision"]
                    or not set(task["evidenceIds"]) <= evidence_ids
                    or not set(task.get("operationIds", [])) <= operation_ids):
                raise MoleError("STATE_CORRUPT", "Task references or revision are invalid.", 5)
            task_ids.add(task["id"])
        if "semantic" in scan:
            semantic = scan["semantic"]
            if not isinstance(semantic, dict) or set(semantic) != {"scenarios", "businessSteps", "glossary"}:
                raise MoleError("STATE_CORRUPT", "Invalid authored knowledge groups.", 5)
            contract({"protocolVersion": "1.0", "taskId": "stored", "baseRevision": state["revision"],
                      "claims": [], **semantic}, "semantic-patch")
            validate_model({**scan["model"], **semantic, "diagramViews": []})
    return state
