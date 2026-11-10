"""Content-addressed bounded shards, committed by one small state pointer."""

import hashlib
import json
from pathlib import Path
import re

from molekit.errors import MoleError

CHUNK_ITEMS = 128
CHUNK_BYTES = 256 * 1024
MAX_NODES = 5000000


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()


def save(path, value, root, writer):
    root = Path(root)
    objects = root / '.objects'
    if objects.is_symlink():
        raise MoleError('UNSAFE_PATH', 'Snapshot object directory must not be a symlink.')
    objects.mkdir(exist_ok=True)
    count = 0

    def reference(node):
        key = digest(node)
        target = objects / (key + '.json')
        if target.exists():
            from molekit.workspace import read_json
            if digest(read_json(target)) != key:
                raise MoleError('STATE_CORRUPT', 'Snapshot object digest mismatch.', 5)
        else:
            writer(target, node)
        return {'t': 'ref', 'v': key}

    def encode(item, depth=0):
        nonlocal count
        count += 1
        if depth > 64 or count > MAX_NODES:
            raise MoleError('INVALID_JSON', 'Snapshot complexity budget exceeded.')
        if not isinstance(item, (dict, list)):
            return item
        kind = 'map' if isinstance(item, dict) else 'list'
        entries = [[key, encode(child, depth + 1)] for key, child in item.items()] if kind == 'map' else [encode(child, depth + 1) for child in item]
        groups, group, size = [], [], 0
        for entry in entries:
            entry_size = len(json.dumps(entry, ensure_ascii=True))
            if group and (len(group) >= CHUNK_ITEMS or size + entry_size > CHUNK_BYTES):
                groups.append(reference({'t': kind, 'v': group}))
                group, size = [], 0
            group.append(entry)
            size += entry_size
        if groups:
            if group:
                groups.append(reference({'t': kind, 'v': group}))
            return {'t': kind + '_chunks', 'v': groups}
        node = {'t': kind, 'v': group}
        return reference(node) if size > CHUNK_BYTES or (depth > 0 and depth % 12 == 0) else node

    encoded = encode(value)
    writer(Path(path), {'schemaVersion': 2, 'state': encoded})


def restore(header, root):
    from molekit.workspace import read_json
    root = Path(root)
    if set(header) != {'schemaVersion', 'state'}:
        raise MoleError('SCHEMA_MISMATCH', 'Invalid snapshot pointer.')
    objects = root / '.objects'
    if objects.is_symlink():
        raise MoleError('UNSAFE_PATH', 'Snapshot object directory must not be a symlink.')
    count = 0
    stack = set()
    cache = {}

    def decode(node, depth=0):
        nonlocal count
        count += 1
        if depth > 256 or count > MAX_NODES:
            raise MoleError('STATE_CORRUPT', 'Snapshot complexity budget exceeded.', 5)
        if not isinstance(node, dict):
            if isinstance(node, list):
                raise MoleError('STATE_CORRUPT', 'Invalid snapshot container.', 5)
            return node
        if set(node) != {'t', 'v'}:
            raise MoleError('STATE_CORRUPT', 'Invalid snapshot node.', 5)
        kind, value = node['t'], node['v']
        if kind == 'ref':
            if not isinstance(value, str) or not re.fullmatch('[a-f0-9]{64}', value) or value in stack:
                raise MoleError('STATE_CORRUPT', 'Invalid or cyclic snapshot reference.', 5)
            if value not in cache:
                cache[value] = read_json(objects / (value + '.json'))
                if digest(cache[value]) != value:
                    raise MoleError('STATE_CORRUPT', 'Snapshot object digest mismatch.', 5)
            stack.add(value)
            try:
                return decode(cache[value], depth + 1)
            finally:
                stack.remove(value)
        if kind not in {'map', 'list', 'map_chunks', 'list_chunks'} or not isinstance(value, list):
            raise MoleError('STATE_CORRUPT', 'Invalid snapshot type.', 5)
        if kind == 'list':
            return [decode(child, depth + 1) for child in value]
        if kind == 'map':
            result = {}
            for pair in value:
                if not isinstance(pair, list) or len(pair) != 2 or not isinstance(pair[0], str) or pair[0] in result:
                    raise MoleError('STATE_CORRUPT', 'Invalid snapshot mapping.', 5)
                result[pair[0]] = decode(pair[1], depth + 1)
            return result
        result = {} if kind == 'map_chunks' else []
        for chunk in value:
            child = decode(chunk, depth + 1)
            if kind == 'map_chunks':
                if not isinstance(child, dict) or set(result) & set(child):
                    raise MoleError('STATE_CORRUPT', 'Invalid snapshot map chunks.', 5)
                result.update(child)
            else:
                if not isinstance(child, list):
                    raise MoleError('STATE_CORRUPT', 'Invalid snapshot list chunks.', 5)
                result.extend(child)
        return result
    return decode(header['state'])
