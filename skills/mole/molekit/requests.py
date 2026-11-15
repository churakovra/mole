"""Strict goal/deliverable admission; intent is supplied by the host agent."""
import copy
import json
from pathlib import Path, PurePosixPath
import re

from molekit.errors import MoleError
from molekit.model import validate_schema
from molekit.scanner import redact

DEFAULT_LIMITS = {'maxProbeRounds': 12, 'maxEvidenceChars': 160000,
                  'maxProbeChars': 12000, 'maxGraphHops': 8, 'maxNodes': 200,
                  'noProgressRounds': 2}
SAFE_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}')


def schema(value, filename):
    specification = json.loads((Path(__file__).resolve().parents[1]/'schemas'/filename).read_text(encoding='utf-8'))
    try:
        validate_schema(value, specification)
    except MoleError as exc:
        # Unknown keys can themselves contain secrets. Do not echo input keys,
        # values, raw JSON, or paths in public errors.
        raise MoleError('INVALID_REQUEST', 'Request does not match its versioned schema.') from exc


def safe_scope(value):
    if value == 'repository':
        return
    # Scope syntax is portable repository-relative POSIX syntax, independent
    # of the host. On Windows Path('/root').is_absolute() is False because it
    # has no drive, although joining it would discard the repository prefix.
    path = PurePosixPath(value)
    if path.is_absolute() or '..' in path.parts or '\\' in value or ':' in value or any(ord(char)<32 for char in value) or not value.strip():
        raise MoleError('UNSAFE_SCOPE', 'Use a repository-relative source scope.')


def validate_request(value):
    schema(value, 'analysis-request.v2.schema.json')
    if not value['question'].strip():
        raise MoleError('INVALID_REQUEST', 'A nonempty original question is required.')
    result = copy.deepcopy(value)
    result.setdefault('audience', 'developer')
    result.setdefault('focus', [])
    result.setdefault('indexScope', 'repository')
    result.setdefault('answerScope', 'repository')
    result.setdefault('userOutputPreference', 'auto')
    result['limits'] = {**DEFAULT_LIMITS, **result.get('limits', {})}
    for key in ('indexScope', 'answerScope'):
        safe_scope(result[key])
    if result.get('requestId') and not SAFE_ID.fullmatch(result['requestId']):
        raise MoleError('INVALID_REQUEST', 'Invalid request identifier.')
    contract = result['deliverable']
    schema(contract, 'deliverable-contract.v1.schema.json')
    ids = [item['id'] for item in contract['requirements']]
    if len(ids) != len(set(ids)):
        raise MoleError('INVALID_REQUEST', 'Requirement identifiers must be unique.')
    artifact_type = contract['deliverableType'] in {'interactive_process_map', 'focused_map', 'explicit_artifacts'}
    if result['userOutputPreference'] == 'text_only' and (artifact_type or contract['formats']):
        raise MoleError('OUTPUT_PREFERENCE_CONFLICT', 'Text-only preference conflicts with an artifact contract.')
    if artifact_type and not contract['formats']:
        raise MoleError('INVALID_REQUEST', 'An artifact contract requires formats.')
    if contract['deliverableType'] in {'interactive_process_map', 'focused_map'} and 'html' not in contract['formats']:
        raise MoleError('INVALID_REQUEST', 'An interactive map requires HTML.')
    if contract['deliverableType'] == 'chat_answer' and contract['formats']:
        raise MoleError('OUTPUT_PREFERENCE_CONFLICT', 'A chat answer does not require artifact formats.')
    # Sanitize before hashing or writing any question-derived session data.
    def sanitize(node):
        if isinstance(node, str):
            return redact(node)
        if isinstance(node, list):
            return [sanitize(item) for item in node]
        if isinstance(node, dict):
            return {key:sanitize(item) for key,item in node.items()}
        return node
    result = sanitize(result)
    schema(result, 'analysis-request.v2.schema.json')
    return result
