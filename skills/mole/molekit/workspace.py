"""Single-file transactional workspace with OS-owned crash-safe locks."""

from contextlib import contextmanager
import json
import os
from pathlib import Path
import tempfile

from molekit.errors import MoleError

MAX_JSON_BYTES = 16 * 1024 * 1024


def read_json(path):
    path = Path(path)
    if path.is_symlink():
        raise MoleError("UNSAFE_PATH", "JSON files must not be symlinks.")
    try:
        with path.open("rb") as stream:
            raw = stream.read(MAX_JSON_BYTES + 1)
        if len(raw) > MAX_JSON_BYTES:
            raise MoleError("INVALID_JSON", "JSON exceeds size limit.")
        return json.loads(raw)
    except (ValueError, RecursionError) as exc:
        raise MoleError("INVALID_JSON", "Malformed or excessively nested JSON.") from exc


def atomic_json(path, value):
    path = Path(path)
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
    with lock_path.open("a+b") as stream:
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
    if not isinstance(state, dict) or state.get("schemaVersion") != 1:
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
    return state
