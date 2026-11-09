"""Workflow-first knowledge views; raw declarations remain technical drilldowns."""

from collections import defaultdict, deque

from molekit.flow import adjacency, workflows
from molekit.model import validate_model
from molekit.scanner import identity

MAX_VIEWS = 256
MAX_DETAIL_NODES = 80


def compose(scan):
    model = scan['model']
    model['operations'] = [op for op in model['operations'] if op['kind'] not in {'scenario_summary', 'component_summary'}]
    model['relationships'] = [edge for edge in model['relationships'] if not edge['id'].startswith('view-edge-')]
    for group in ('scenarios', 'businessSteps', 'diagramViews', 'glossary', 'qualityFindings'):
        model[group] = []
    operations = {op['id']: op for op in model['operations']}
    evidence = {ev['id']: ev for ev in model['evidence']}
    sources = {source['id']: source for source in model['sources']}
    graph = adjacency(model)
    edge_lookup = {edge['id']: edge for edge in model['relationships']}
    candidates = scan.get('workflows') or workflows(scan)
    authored = scan.get('semantic', {})
    model['businessSteps'] = list(authored.get('businessSteps', []))
    model['glossary'] = list(authored.get('glossary', []))
    views, function_views = {}, {}
    owner_ops = defaultdict(set)
    for op in operations.values():
        if op.get('ownerId'):
            owner_ops[op['ownerId']].add(op['id'])
    declarations = {symbol['id']: symbol for symbol in model['symbols']}
    declared_ops = set(scan.get('symbolOperations', {}).values())
    limited = set()

    def path(oid):
        op = operations[oid]
        return sources[evidence[op['evidenceIds'][0]]['sourceId']]['path'] if op['evidenceIds'] else 'unknown'

    def order(ids):
        return sorted(ids, key=lambda oid: (path(oid), operations[oid].get('sourceOrder', -1), operations[oid]['title'], oid))

    def traversal(origin, ids):
        allowed = set(ids)
        seen, result, stack = set(), [], [origin]
        while stack:
            oid = stack.pop()
            if oid in seen or oid not in allowed:
                continue
            seen.add(oid)
            result.append(oid)
            edges = sorted(graph.get(oid, []), key=lambda edge: (
                edge['kind'] in {'exception_path_candidate', 'branch_false_candidate', 'finally_candidate'},
                operations[edge['target']].get('sourceOrder', -1), edge['target']))
            stack.extend(edge['target'] for edge in reversed(edges))
        result.extend(oid for oid in order(allowed - seen))
        return result

    def add_view(vid, title, nodes, edge_ids=(), children=(), scenario_ids=()):
        if vid in views:
            return views[vid]
        if len(views) >= MAX_VIEWS:
            limited.add('diagram_view_budget_exceeded')
            return None
        node_set = {node['id'] for node in nodes}
        edge_set = set(edge_ids)
        edge_ids = [eid for eid in sorted(edge_set) if eid in edge_lookup and
                    edge_lookup[eid]['source'] in node_set and edge_lookup[eid]['target'] in node_set]
        view = {'id': vid, 'title': title, 'nodes': nodes, 'edgeIds': edge_ids,
                'childRefs': list(dict.fromkeys(children)), 'scenarioIds': list(scenario_ids)}
        views[vid] = view
        return view

    def summary(kind, key, title, ids):
        oid = identity(kind, key)
        if oid not in operations:
            evs = sorted({ev for item in ids for ev in operations[item]['evidenceIds']})
            op = {'id': oid, 'kind': 'scenario_summary' if kind == 'scenario-summary' else 'component_summary',
                  'title': title, 'evidenceIds': evs}
            operations[oid] = op
            model['operations'].append(op)
        return oid

    active = {oid for candidate in candidates for oid in candidate['operationIds']}
    for scenario in authored.get('scenarios', []):
        active.update(scenario['operationIds'])
    # A callable view is shared wherever that callable is reused. Cross-call
    # links retain actual containment routes rather than an arbitrary click history.
    for oid in order(active & declared_ops):
        if len(function_views) + 32 >= MAX_VIEWS:
            limited.add('diagram_view_budget_exceeded')
            break
        function_views[oid] = identity('view', 'callable:' + oid)
    for oid, vid in function_views.items():
        ids = {oid} | (owner_ops[oid] & active)
        ids.update(edge['target'] for item in list(ids) for edge in graph.get(item, []) if edge['kind'] == 'calls')
        if len(ids) > MAX_DETAIL_NODES:
            ids = {oid, *order(ids - {oid})[:MAX_DETAIL_NODES - 1]}
            limited.add('diagram_node_budget_exceeded')
        children = []
        nodes = []
        for item in order(ids):
            node = {'id': item, 'label': operations[item]['title']}
            target = function_views.get(item)
            if target and target != vid:
                node['childViewId'] = target
                children.append(target)
            nodes.append(node)
        edges = [edge['id'] for item in ids for edge in graph.get(item, []) if edge['target'] in ids]
        add_view(vid, operations[oid]['title'], nodes, edges, children)
    claims_by_evidence = defaultdict(set)
    for claim in model['claims']:
        for ev in claim['evidenceIds']:
            claims_by_evidence[ev].add(claim['id'])
    claims_by_scope = defaultdict(set)
    for cid, scope in scan.get('claimScopes', {}).items():
        claims_by_scope[scope].add(cid)
    covered = set()
    scenes = []
    for original in authored.get('scenarios', []):
        scene = {**original, 'kind': 'authored_workflow'}
        scenes.append(scene)
        covered.update(scene['operationIds'])
    for candidate in candidates:
        if set(candidate['operationIds']) <= covered:
            continue
        ids = candidate['operationIds']
        scope_evidence = set(candidate['evidenceIds'])
        claims = sorted(set().union(*(claims_by_evidence[ev] for ev in scope_evidence)) | claims_by_scope[candidate['id']])
        scenes.append({'id': identity('scenario', candidate['id']), 'kind': candidate['kind'] + '_candidate',
            'title': ('Workflow candidate: ' if candidate['kind'] == 'workflow' else 'Component review: ') + candidate['title'],
            'trigger': candidate['trigger'], 'operationIds': ids, 'claimIds': claims,
            'outcomes': [], 'unknowns': ['Business purpose/actors require semantic review.'] +
                [item['kind'] + ': ' + item['target'] for item in candidate['boundaries']],
            'entryOperationId': candidate['entryOperationId']})
    overview = {'id': 'view-overview', 'title': 'System workflows', 'scenarioIds': [], 'nodes': [], 'edgeIds': [], 'childRefs': []}
    for scene in scenes:
        ids = set(scene['operationIds'])
        origin = scene.get('entryOperationId', scene['operationIds'][0])
        ordered = traversal(origin, ids)
        steps, alternatives, effects = [], defaultdict(list), []
        for oid in ordered:
            op = operations[oid]
            context = op.get('control', [])
            step = {'operationId': oid, 'description': op['title'], 'claimIds': [], 'condition': '; '.join(context)}
            if any(' except ' in item or ' false:' in item or ' finally' in item or ' else' in item for item in context):
                alternatives['; '.join(context)].append(oid)
            else:
                steps.append(step)
            if op['kind'] in {'db_write', 'db_read', 'db_execute_candidate', 'transaction_boundary', 'publish', 'consume', 'acknowledgement', 'background_task'}:
                effects.append(op['kind'] + ': ' + op['title'])
        scene.setdefault('steps', steps)
        scene.setdefault('actors', [])
        scene.setdefault('preconditions', [])
        scene.setdefault('stateEffects', effects)
        scene.setdefault('failurePaths', [{'condition': condition, 'operationIds': values,
            'outcome': 'Static alternative/failure path; runtime outcome requires review', 'claimIds': []}
            for condition, values in alternatives.items()])
        if not scene['outcomes']:
            scene['outcomes'] = ['Static return/raise boundaries are documented; business outcome is not established.']
        root_id = summary('scenario-summary', scene['id'], scene['title'], ids)
        scene['operationIds'] = [root_id, *ordered]
        model['scenarios'].append(scene)
        vid = identity('view', scene['id'])
        modules = defaultdict(list)
        for oid in ordered:
            modules[path(oid)].append(oid)
        module_nodes, module_children, membership = [], [], {}
        for module, module_ids in sorted(modules.items()):
            key = ':'.join(sorted(module_ids))
            module_vid = identity('view', 'module:' + key)
            nodes, children = [], []
            for oid in order(module_ids)[:MAX_DETAIL_NODES]:
                node = {'id': oid, 'label': operations[oid]['title']}
                child = function_views.get(oid)
                if child and child in views:
                    node['childViewId'] = child
                    children.append(child)
                nodes.append(node)
            if len(module_ids) > MAX_DETAIL_NODES:
                limited.add('diagram_node_budget_exceeded')
            edges = [edge['id'] for oid in module_ids for edge in graph.get(oid, []) if edge['target'] in set(module_ids)]
            module_view = add_view(module_vid, module, nodes, edges, children, [scene['id']])
            anchor = next((oid for oid in module_ids if oid in declared_ops), module_ids[0])
            module_oid = summary('component-summary', scene['id'] + ':' + anchor, module, module_ids)
            node = {'id': module_oid, 'label': module}
            if module_view:
                node['childViewId'] = module_vid
                module_children.append(module_vid)
            module_nodes.append(node)
            for oid in module_ids:
                membership[oid] = module_oid
        module_edges = {}
        for oid in ordered:
            for edge in graph.get(oid, []):
                target = edge['target']
                if target not in membership or membership[oid] == membership[target]:
                    continue
                key = (membership[oid], membership[target], edge['kind'])
                if key not in module_edges:
                    module_edges[key] = {'id': identity('view-edge', vid + str(key)), 'source': key[0], 'target': key[1],
                        'kind': edge['kind'], 'resolution': 'possible', 'evidenceIds': [],
                        'condition': 'Aggregated static candidates; inspect linked subprocesses for branches and limitations'}
                module_edges[key]['evidenceIds'].extend(edge['evidenceIds'])
        for edge in module_edges.values():
            edge['evidenceIds'] = sorted(set(edge['evidenceIds']))
            model['relationships'].append(edge)
            edge_lookup[edge['id']] = edge
        add_view(vid, scene['title'], module_nodes, [edge['id'] for edge in module_edges.values()], module_children, [scene['id']])
        overview['scenarioIds'].append(scene['id'])
        overview['nodes'].append({'id': root_id, 'label': scene['title'], 'childViewId': vid})
        overview['childRefs'].append(vid)
    # Referenced views that could not be allocated become explicit leaves.
    for view in views.values():
        view['childRefs'] = [child for child in view['childRefs'] if child in views]
        for node in view['nodes']:
            if node.get('childViewId') not in view['childRefs']:
                node.pop('childViewId', None)
    overview['childRefs'] = [child for child in overview['childRefs'] if child in views]
    for node in overview['nodes']:
        if node.get('childViewId') not in overview['childRefs']:
            node.pop('childViewId', None)
    model['diagramViews'] = [overview, *views.values()] if overview['nodes'] else []
    for reason in sorted(limited):
        if not any(item['reason'] == reason for item in scan['limitations']):
            scan['limitations'].append({'path': '.', 'reason': reason})
    for index, limitation in enumerate(scan['limitations']):
        model['qualityFindings'].append({'id': 'finding-' + str(index), 'severity': 'major',
            'message': limitation['path'] + ': ' + limitation['reason'], 'affectedIds': []})
    validate_model(model)
    return model
