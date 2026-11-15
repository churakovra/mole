#!/usr/bin/env python3
"""Archive review working-tree sources and provenance; never include Git internals."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PREFIXES = {'.github', 'skills', 'tests', 'tools', 'docs'}
TOP_FILES = {'.gitignore', 'LICENSE', 'README.md', 'CONTRIBUTING.md', 'DEVELOPMENT-STATUS.md', 'CHANGELOG.md', 'SECURITY.md'}
PLANNING_SUFFIXES = ('-DEVELOPMENT-GUIDE.md', '-IMPLEMENTATION-PLAN.md', '-PR-BACKLOG.md')


def git(*args, root=ROOT):
    return subprocess.check_output(['git', '-C', str(root), *args])


def package_source(output, root=ROOT):
    root, output = Path(root).resolve(), Path(output)
    paths = set(git('ls-files', '--cached', '--others', '--exclude-standard', '-z', root=root).decode().split('\0'))
    deleted = set(git('ls-files', '--deleted', '-z', root=root).decode().split('\0'))
    paths -= deleted
    files = []
    for name in sorted(filter(None, paths)):
        relative = Path(name)
        planning = len(relative.parts) == 1 and name.startswith('MOLE-') and name.endswith(PLANNING_SUFFIXES)
        if relative.parts[0] not in PREFIXES and name not in TOP_FILES and not planning:
            continue
        if any(part in {'__pycache__', '.git', '.objects', '.diagnostics', '.mole-generations'} for part in relative.parts):
            continue
        path = root / relative
        if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent != root):
            raise ValueError('Review source symlinks are forbidden')
        if not path.is_file():
            raise ValueError('Tracked review source is missing: ' + name)
        if path.resolve() == output.resolve():
            raise ValueError('Archive must not replace a review source')
        files.append((name, path.read_bytes()))
    refs = git('for-each-ref', '--format=%(refname:short) %(objectname)', 'refs/heads', root=root).decode().splitlines()
    provenance = {'revision':git('rev-parse','HEAD',root=root).decode().strip(),
                  'workingTreeDirty':bool(git('status','--porcelain','--untracked-files=normal',root=root).strip()),
                  'localBranchHeads':dict(line.split(' ',1) for line in refs),
                  'contents':'Combined working-tree source snapshot; branches are stacked, not merged. Git history is not included.'}
    files.append(('REVIEW-PROVENANCE.json',(json.dumps(provenance,sort_keys=True,indent=2)+'\n').encode()))
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for name, data in files:
            item=zipfile.ZipInfo('mole-source/'+name,date_time=(1980,1,1,0,0,0))
            item.create_system=3
            item.external_attr=0o100644 << 16
            item.compress_type=zipfile.ZIP_DEFLATED
            archive.writestr(item,data)
    manifest={'archiveSha256':hashlib.sha256(output.read_bytes()).hexdigest(),**provenance,
              'files':{name:hashlib.sha256(data).hexdigest() for name,data in files}}
    output.with_suffix('.manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
    return manifest


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=package_source(args.output)
    print(json.dumps({key:value for key,value in result.items() if key!='files'},sort_keys=True))
