"""Bounded repository reads that do not follow source symlinks."""

import os
import stat
from pathlib import Path

from molekit.errors import MoleError


def relative_source_path(target, output):
    """Return a portable relative link, or None for different Windows volumes.

    Callers retain a repository-relative source locator when a link cannot be
    made. Never fall back to an absolute file URI exposing local paths.
    """
    try:
        return os.path.relpath(target, output).replace(os.sep, '/')
    except ValueError:
        return None


def read_source(root, path, limit=1024 * 1024):
    root = Path(root).resolve()
    path = Path(path).absolute()
    if not path.is_relative_to(root):
        alias = next((parent for parent in path.parents if parent.resolve() == root), None)
        if alias is not None:
            path = root / path.relative_to(alias)
    if not path.is_relative_to(root) or not path.resolve().is_relative_to(root):
        raise MoleError("UNSAFE_PATH", "Source path escaped the repository.")
    components = path.relative_to(root).parts
    if not components:
        raise MoleError("UNSAFE_PATH", "Source must be a file.")
    descriptors = []
    try:
        if os.name == "posix" and hasattr(os, "O_NOFOLLOW"):
            current = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
            descriptors.append(current)
            for component in components[:-1]:
                current = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current)
                descriptors.append(current)
            descriptor = os.open(components[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=current)
        else:
            current = root
            for component in components:
                current = current / component
                if current.is_symlink():
                    raise MoleError("UNSAFE_PATH", "Source symlinks are excluded.")
            descriptor = os.open(path, os.O_RDONLY)
        with os.fdopen(descriptor, "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise MoleError("UNSAFE_PATH", "Source must be a regular file.")
            raw = stream.read(limit + 1)
        if len(raw) > limit:
            raise MoleError("SOURCE_TOO_LARGE", "Source exceeds size budget.")
        return raw
    except OSError as exc:
        raise MoleError("SOURCE_UNAVAILABLE", "Source changed, is inaccessible, or uses a symlink.", 5,
                        "Inspect source permissions and refresh the snapshot.") from exc
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def confined_output(repo, output):
    repo = Path(repo).resolve()
    output = Path(output).absolute()
    inside = output.is_relative_to(repo) or any(parent.resolve() == repo for parent in output.parents)
    if inside and not output.resolve().is_relative_to(repo):
        raise MoleError("UNSAFE_PATH", "A repository output path traverses an escaping symlink.")
