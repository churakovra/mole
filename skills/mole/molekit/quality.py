"""Separate extraction, semantic coverage and export outcomes."""

import re

MATERIAL = re.compile(r'exactly.once|at.least.once|guarantee|atomic|transaction|deliver|retry|retries|acknowledg|no.data.loss', re.I)


def assess(state):
    scan = state.get('scan')
    if not scan:
        return {'technicalAnalysis': 'NOT_RUN', 'semanticCoverage': 'NOT_RUN', 'export': 'NOT_RUN',
                'criticalUnknownCount': 0, 'reasons': ['No analysis snapshot']}
    reasons = []
    limitations = [item for item in scan['limitations'] if item['reason'] != 'excluded_class']
    if limitations:
        reasons.append('Source/model coverage limitations remain')
    pending = sum(task['status'] == 'pending' for task in state['tasks'])
    if pending:
        reasons.append('Pending analysis/review tasks: ' + str(pending))
    claims = scan['model']['claims']
    uncertain = sum(claim['status'] in {'unknown', 'contradicted'} for claim in claims)
    unresolved = sum(item.get('kind') in {'unresolved_dispatch', 'message_destination_unresolved'} for item in scan.get('unresolved', []))
    unreviewed = sum(bool(MATERIAL.search(claim['statement'])) and state.get('claimReviews', {}).get(claim['id'], {}).get('verdict') != 'supported' for claim in claims)
    scenes = scan.get('semantic', {}).get('scenarios', [])
    if not scenes:
        reasons.append('No authored workflow/scenario interpretation')
    if len(scenes) > 1 and not any(scene.get('links') for scene in scenes):
        reasons.append('No inter-process handoffs authored; overview remains a process catalog')
    for scene in scenes:
        if len(scene.get('steps', [])) > 1 and not scene.get('stepTransitions'):
            reasons.append(scene['id'] + ': no explicit step transitions; paths remain unconnected')
    scopes = scan.get('claimScopes', {})
    covered = {scopes[cid] for scene in scenes for cid in scene['claimIds'] if cid in scopes}
    uncovered = [task for task in state['tasks'] if task['kind'] in {'workflow_review', 'component_review', 'document_review'}
                 and task.get('scopeId', task['id']) not in covered]
    if uncovered:
        reasons.append('Scopes without authored interpretation: ' + str(len(uncovered)))
    incomplete = sum(not all(scene.get(key) for key in ('actors', 'preconditions', 'steps', 'outcomes', 'failurePaths'))
                     or bool(scene.get('unknowns'))
                     or any(not path.get('operationIds') for path in scene.get('failurePaths', [])) for scene in scenes)
    if incomplete:
        reasons.append('Authored scope/outcome/failure coverage remains incomplete')
        for scene in scenes:
            missing = [key for key in ('actors', 'preconditions', 'steps', 'outcomes', 'failurePaths') if not scene.get(key)]
            gaps = (['missing ' + ', '.join(missing)] if missing else [])
            if scene.get('unknowns'):
                gaps.append('explicit unknown boundaries: ' + str(len(scene['unknowns'])))
            if any(not path.get('operationIds') for path in scene.get('failurePaths', [])):
                gaps.append('failure paths without operation evidence')
            if gaps:
                reasons.append(scene['id'] + ': ' + '; '.join(gaps))
    if uncertain:
        reasons.append('Unknown or contradicted claims: ' + str(uncertain))
    if unresolved:
        reasons.append('Unresolved dispatch/message boundaries: ' + str(unresolved))
    if unreviewed:
        reasons.append('Material claims awaiting explicit evidence review: ' + str(unreviewed))
    return {'technicalAnalysis': 'PARTIAL' if limitations else 'PASS',
            'semanticCoverage': 'PARTIAL' if reasons else 'PASS',
            'export': state.get('quality', {}).get('export', 'NOT_RUN'),
            'criticalUnknownCount': uncertain + unresolved + unreviewed,
            'reasons': reasons, 'pendingTasks': pending,
            'semanticTruth': 'Not proven by structural validation; agent review remains evidence-bounded'}
