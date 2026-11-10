"""Output-owned lock, immutable generations and a single publication pointer."""

import hashlib
import html
import json
import os
from pathlib import Path
import re
import uuid

from molekit.errors import MoleError
from molekit import markdown
from molekit.workspace import atomic_json, locked, read_json


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def safe_path(root, relative):
    path = Path(relative)
    if not path.parts or path.is_absolute() or '..' in path.parts or '\\' in relative:
        raise MoleError('UNSAFE_PATH', 'Invalid output manifest path.')
    result = Path(root) / path
    cursor = Path(root)
    if cursor.is_symlink():
        raise MoleError('UNSAFE_PATH', 'Output manifest traverses a symlink or escape.')
    for part in path.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise MoleError('UNSAFE_PATH', 'Output manifest traverses a symlink or escape.')
    return result


def current(root):
    root = Path(root).absolute()
    pointer_path = root / 'current.json'
    if not pointer_path.exists():
        return None, None, None
    pointer = read_json(pointer_path)
    if (not isinstance(pointer, dict) or pointer.get('schemaVersion') != 1
            or not isinstance(pointer.get('generation'), str) or not re.fullmatch('[a-f0-9]{64}', pointer['generation'])):
        raise MoleError('OUTPUT_CORRUPT', 'Invalid output generation pointer.', 5)
    generation = safe_path(root, '.mole-generations/' + pointer['generation'])
    manifest = read_json(safe_path(generation, '.mole-manifest.json'))
    if not isinstance(manifest, dict) or digest(manifest) != pointer.get('manifestDigest'):
        raise MoleError('OUTPUT_CORRUPT', 'Generation manifest digest mismatch.', 5)
    if (manifest.get('schemaVersion') != 1 or not isinstance(manifest.get('files'), dict)
            or not isinstance(manifest.get('bases'), dict)
            or set(manifest['files']) != set(manifest['bases'])
            or any(not isinstance(manifest.get(key), str) for key in ('project', 'revision', 'intent'))
            or not isinstance(manifest.get('formats'), list)):
        raise MoleError('OUTPUT_CORRUPT', 'Invalid generation file manifest.', 5)
    for relative, fingerprint in manifest['files'].items():
        if (not isinstance(relative, str) or not isinstance(fingerprint, str)
                or not re.fullmatch('[a-f0-9]{64}', fingerprint)
                or not isinstance(manifest['bases'][relative], str)
                or not re.fullmatch('[a-f0-9]{64}', manifest['bases'][relative])):
            raise MoleError('OUTPUT_CORRUPT', 'Invalid managed file entry.', 5)
        safe_path(generation, relative)
    return pointer, manifest, generation


def resolve_output(root):
    """Resolve one authoritative generation once, then read only that bundle."""
    pointer, manifest, generation = current(root)
    return generation if pointer else Path(root)


def fingerprints(root, files):
    result = {}
    for relative in files:
        path = safe_path(root, relative)
        if path.exists() and not path.is_file():
            raise MoleError('OUTPUT_CONFLICT', 'A managed output path is not a file.', 5)
        if path.exists():
            from molekit.safety import read_source
            result[relative] = hashlib.sha256(read_source(root, path, 256 * 1024 * 1024)).hexdigest()
        else:
            result[relative] = None
    return result


def check_untracked(root, files):
    """Never strand a manual relative link to an untracked authored asset."""
    allowed = set(files) | {'.mole-manifest.json'}
    allowed_directories = {parent.as_posix() for relative in files for parent in Path(relative).parents
                           if parent != Path('.')}
    count = 0
    def inaccessible(error):
        raise MoleError('OUTPUT_CONFLICT', 'Generation inventory is inaccessible; nothing was published.', 5) from error
    for directory, directories, names in os.walk(root, followlinks=False, onerror=inaccessible):
        for name in directories + names:
            count += 1
            if count > 100000:
                raise MoleError('OUTPUT_CONFLICT', 'Generation inventory exceeds the safety budget.', 5)
            path = Path(directory) / name
            if path.is_symlink():
                raise MoleError('UNSAFE_PATH', 'Generation contains a symlink.')
        for name in directories:
            if (Path(directory) / name).relative_to(root).as_posix() not in allowed_directories:
                raise MoleError('OUTPUT_CONFLICT', 'Generation contains an untracked authored directory.', 5,
                                'Preserve assets outside the generation and update manual links before regenerating.')
        for name in names:
            relative = (Path(directory) / name).relative_to(root).as_posix()
            if relative not in allowed:
                raise MoleError('OUTPUT_CONFLICT', 'Generation contains untracked authored assets: ' + relative, 5,
                                'Preserve assets outside the generation and update manual links before regenerating.')


def gateway_text(generation, files):
    links = ['<li><a href=".mole-generations/' + generation + '/' + html.escape(relative, quote=True) + '">' + html.escape(relative) + '</a></li>'
             for relative in ('README.md', 'explorer.html', 'confluence/workflows.drawio') if relative in files]
    return '<!-- mole:gateway:v1 --><!doctype html><meta charset="utf-8"><title>MOLE output</title><h1>MOLE output</h1><p>Open one complete generation. current.json is authoritative.</p><ul>' + ''.join(links) + '</ul>\n'


def write_gateway(root, pointer, files, allowed):
    path = safe_path(root, 'MOLE-OPEN.html')
    actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
    text = gateway_text(pointer['generation'], files)
    if actual not in allowed | {None, hashlib.sha256(text.encode()).hexdigest()}:
        raise MoleError('OUTPUT_CONFLICT', 'Gateway was authored/edited; preserve it and choose another output.', 5)
    markdown.atomic_text(path, text)


def publish(state, directory, root, formats, quality, build, persist, restart=False, adopt=False):
    root = Path(root).absolute()
    project = digest({'repo': state['manifest']['repo'], 'scope': state['manifest']['scope']})
    quality = {**quality, 'export': 'PASS'}
    intent = digest({'model': state['scan']['model'], 'quality': quality, 'formats': sorted(formats), 'project': project})
    with locked(root, create=True):
        pointer, manifest, active = current(root)
        pending = state.get('pendingExport')
        if pending and pending.get('version') != 2:
            raise MoleError('OUTPUT_CONFLICT', 'Finish the previous-engine export before migrating output storage.', 5)
        if pointer and manifest.get('project') != project:
            raise MoleError('OUTPUT_CONFLICT', 'Output belongs to a different repository/scope.', 5)
        gateway_path = safe_path(root, 'MOLE-OPEN.html')
        gateway_before = hashlib.sha256(gateway_path.read_bytes()).hexdigest() if gateway_path.exists() else None
        recovered = bool(pointer and pending and pointer.get('token') == pending.get('token') and manifest.get('intent') == intent)
        allowed_gateway = {None, pointer.get('gatewayHash') if pointer else None}
        if recovered:
            allowed_gateway.add(pending.get('gatewayBefore'))
        if gateway_before not in allowed_gateway:
            raise MoleError('OUTPUT_CONFLICT', 'Output gateway contains authored changes.', 5)
        expected = state.get('outputGeneration') if state.get('output') == str(root) else None
        if pointer and pointer['generation'] != expected and not recovered and not adopt:
            raise MoleError('OUTPUT_CONFLICT', 'Output generation changed or is owned by another workspace.', 5,
                            'Use a new output directory or explicitly --adopt-output after reviewing its ownership.')
        if pending and (pending.get('output') != str(root) or pending.get('intent') != intent) and not restart:
            raise MoleError('OUTPUT_CONFLICT', 'Interrupted export intent differs; retry unchanged or use --restart-export.', 5)
        bases = manifest['bases'] if pointer else state.get('exportBases', {}) if state.get('output') == str(root) else {}
        active = active or root
        old_files = manifest['files'] if pointer else bases
        if pointer:
            check_untracked(active, old_files)
        before = fingerprints(active, old_files)
        if pointer and manifest.get('intent') == intent and before == manifest['files']:
            write_gateway(root, pointer, manifest['files'], allowed_gateway)
            return {'output': str(active), 'logicalOutput': str(root), 'generation': pointer['generation'],
                    'manifest': manifest, 'files': sorted(manifest['files']), 'quality': quality}
        if recovered:
            # Publication already happened; do not rewrite even a user-edited
            # manual section while reconciling the workspace checkpoint.
            if any(value is None for value in before.values()):
                raise MoleError('OUTPUT_CORRUPT', 'Published generation is missing files.', 5)
            write_gateway(root, pointer, manifest['files'], allowed_gateway)
            return {'output': str(active), 'logicalOutput': str(root), 'generation': pointer['generation'],
                    'manifest': manifest, 'files': sorted(manifest['files']), 'quality': quality}
        if pending and not restart and pending.get('before') != before:
            raise MoleError('OUTPUT_CONFLICT', 'Output changed during an interrupted export; preserve edits and restart explicitly.', 5)
        token = pending['token'] if pending and not restart else uuid.uuid4().hex
        generation_id = digest({'intent': intent, 'previous': pointer['generation'] if pointer else None,
                                'before': before, 'publisher': state['runId'], 'token': token})
        generations = safe_path(root, '.mole-generations')
        generations.mkdir(exist_ok=True)
        final = safe_path(generations, generation_id)
        generated = build(final, bases)
        writes, next_bases = markdown.plan_writes(active, generated, bases)
        content = {path.relative_to(active).as_posix(): value for path, value in writes.items()}
        retired = sorted(set(old_files) - set(content))
        # Retiring a format never silently discards authored generated edits;
        # manual notes remain byte-for-byte in the retained prior generation.
        for relative in retired:
            path = safe_path(active, relative)
            if path.exists():
                markdown.plan_writes(active, {relative: ''}, bases)
        state['pendingExport'] = {'version': 2, 'output': str(root), 'intent': intent,
                                  'token': token, 'before': before, 'generation': generation_id,
                                  'gatewayBefore': gateway_before,
                                  'formats': sorted(formats)}
        state['status'] = 'EXPORTING'
        outputs = state['manifest'].setdefault('outputs', [])
        if str(root.resolve()) not in outputs:
            outputs.append(str(root.resolve()))
        persist()
        stage = safe_path(generations, '.stage-' + uuid.uuid4().hex)
        stage.mkdir(mode=0o700)
        for relative, body in content.items():
            markdown.atomic_text(safe_path(stage, relative), body)
        hashes = fingerprints(stage, content)
        generation_manifest = {'schemaVersion': 1, 'project': project, 'revision': state['revision'],
            'intent': intent, 'formats': sorted(formats), 'files': hashes,
            'bases': {key: value for key, value in next_bases.items() if key in content},
            'quality': quality, 'retired': retired,
            'previousGeneration': pointer['generation'] if pointer else None,
            'legacyRootRetained': not pointer and bool(bases)}
        atomic_json(stage / '.mole-manifest.json', generation_manifest)
        if fingerprints(active, old_files) != before:
            raise MoleError('OUTPUT_CONFLICT', 'Authored output changed while staging; nothing was published.', 5)
        if fingerprints(stage, content) != hashes:
            raise MoleError('OUTPUT_CONFLICT', 'Staged output changed before publication.', 5)
        if final.exists():
            existing = read_json(safe_path(final, '.mole-manifest.json'))
            if digest(existing) != digest(generation_manifest) or fingerprints(final, content) != hashes:
                raise MoleError('OUTPUT_CONFLICT', 'Unpublished generation changed; nothing was overwritten.', 5)
        else:
            stage.rename(final)
        gateway = gateway_text(generation_id, content)
        pointer = {'schemaVersion': 1, 'generation': generation_id, 'manifestDigest': digest(generation_manifest),
                   'token': token, 'gatewayHash': hashlib.sha256(gateway.encode()).hexdigest()}
        atomic_json(root / 'current.json', pointer)  # the bundle commit point
        write_gateway(root, pointer, content, {gateway_before})
        return {'output': str(final), 'logicalOutput': str(root), 'generation': generation_id,
                'manifest': generation_manifest, 'files': sorted(content), 'quality': quality}
