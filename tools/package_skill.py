#!/usr/bin/env python3
"""Build a reproducible self-contained skill archive without publishing it."""

import argparse
import ast
import hashlib
import json
from pathlib import Path
import zipfile

SOURCE = Path(__file__).resolve().parents[1] / "skills/mole"


def package(output, source=SOURCE):
    source = Path(source).resolve()
    output = Path(output)
    if output.resolve().is_relative_to(source):
        raise ValueError("Archive output must be outside the skill payload.")
    required = ("SKILL.md", "LICENSE", "agents/openai.yaml", "scripts/mole.py", "molekit/__init__.py")
    if not all((source / item).is_file() for item in required):
        raise ValueError("Incomplete skill payload")
    module = ast.parse((source / "molekit/__init__.py").read_text(encoding="utf-8"))
    version = next(ast.literal_eval(node.value) for node in module.body if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets))
    files = []
    for path in sorted(source.rglob("*")):
        if path.is_symlink():
            raise ValueError("Skill payload must not contain symlinks")
        if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc" or path.name == ".DS_Store":
            continue
        name = path.relative_to(source).as_posix()
        data = path.read_bytes()
        if name == "SKILL.md":
            text = data.decode("utf-8")
            frontmatter_end = text.find("\n---\n")
            if not text.startswith("---\n") or frontmatter_end < 0:
                raise ValueError("SKILL.md must start with YAML frontmatter")
            frontmatter = text[:frontmatter_end]
            if "\nmetadata:" in frontmatter:
                raise ValueError("SKILL.md source must not duplicate the canonical version")
            text = text[:frontmatter_end] + f'\nmetadata:\n  version: "{version}"' + text[frontmatter_end:]
            data = text.encode("utf-8")
        files.append((name, data))
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, data in files:
            item = zipfile.ZipInfo("mole/" + name, date_time=(1980, 1, 1, 0, 0, 0))
            item.create_system = 3
            item.external_attr = 0o100644 << 16
            archive.writestr(item, data)
    manifest = {"version": version, "archiveSha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                "files": {name: hashlib.sha256(data).hexdigest() for name, data in files}}
    output.with_suffix(".manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(package(args.output), sort_keys=True, indent=2))
