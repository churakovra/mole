"""Receiver-aware framework patterns, with explicit static uncertainties."""

from collections import defaultdict, deque

from molekit.flow import Resolver
from molekit.model import validate_model
from molekit.scanner import identity, redact


def enrich(result):
    model = result['model']
    operations = {op['id']: op for op in model['operations']}
    symbols = {}
    source_lookup = {source["id"]: source for source in model["sources"]}
    for symbol in model['symbols']:
        for source in symbol['sourceRefs']:
            span = source_lookup[source]
            prefix = span['path'].removesuffix('.py').replace('/', '.') + '.'
            symbols[(span['path'], symbol['qualifiedName'][len(prefix):])] = symbol['id']
    resolver = Resolver(result['facts'], symbols, result['symbolOperations'])
    model_types = set()
    for path, entry in result['facts'].items():
        for symbol in entry['facts']['symbols']:
            if symbol['kind'] == 'class' and any(resolver.canonical(base, path, '').startswith('django.db.models.Model') for base in symbol.get('bases', [])):
                from molekit.flow import module_name
                model_types.add(module_name(path) + '.' + symbol['name'])
    events, entries = [], []
    detected = set()
    queue_labels = {}
    consumer_handlers = set()
    consumers, publishers = [], []

    def edge(source, target, kind, evidence, condition):
        model['relationships'].append({'id': identity('edge', source + target + kind), 'source': source,
            'target': target, 'kind': kind, 'resolution': 'possible', 'evidenceIds': list(dict.fromkeys(evidence)),
            'condition': condition})

    def mark(call, kind, pattern, uncertainty=()):
        op = operations[call['operationId']]
        op.update(kind=kind, sourcePattern=pattern, uncertainty=list(uncertainty))
        events.append({'operationId': op['id'], 'ownerId': call['ownerOperationId'], 'ownerOperationId': call['ownerOperationId'],
                       'kind': kind, 'path': call['path'], 'line': call['line']})

    for path, entry in result['facts'].items():
        detected.update(i['module'].split('.')[0] for i in entry['facts']['imports']
                        if i['module'].split('.')[0] in {'fastapi', 'starlette', 'django', 'sqlalchemy', 'aio_pika', 'aiokafka', 'asyncio'})
        for symbol in entry['facts']['symbols']:
            owner = resolver.local[(path, symbol['name'])]
            for decorator in symbol.get('decoratorCalls', []):
                canonical = resolver.canonical(decorator['target'], path, '')
                root, _, method = canonical.rpartition('.')
                if root in {'fastapi.FastAPI', 'fastapi.APIRouter', 'starlette.routing.Router', 'starlette.applications.Starlette'} and method in {'get', 'post', 'put', 'patch', 'delete', 'head', 'options', 'route', 'api_route', 'websocket'}:
                    prefix = ''
                    receiver = decorator['target'].rpartition('.')[0]
                    bindings = [binding for binding in entry['facts'].get('bindings', [])
                                if binding['name'] == receiver and binding['owner'] == '']
                    if len(bindings) == 1:
                        prefix = bindings[0].get('routePrefix')
                        if prefix is None and 'routePrefix' not in bindings[0]:
                            prefix = ''
                    route_path = (prefix + decorator['path']) if prefix is not None and decorator['path'] is not None else '<dynamic>'
                    if method in {'route', 'api_route'}:
                        methods = decorator['methods'] if decorator.get('methodsSpecified') else ['GET']
                        methods = [value if isinstance(value, str) else '<DYNAMIC>' for value in methods] or ['<DYNAMIC>']
                    else:
                        methods = [method.upper()]
                    for route_method in sorted(set(value.upper() for value in methods if isinstance(value, str))):
                        route_key = owner + canonical + route_method + ':' + route_path
                        if route_path == '<dynamic>':
                            route_key += ':' + str(decorator['line'])
                        oid = identity('entry', route_key)
                        if oid in operations:
                            continue  # Repeated identical registration is one static candidate.
                        op = {'id': oid, 'kind': 'http_entry', 'title': 'HTTP route: ' + route_method + ' ' + route_path,
                          'routeMethod': route_method, 'routePath': route_path,
                          'evidenceIds': operations[owner]['evidenceIds'], 'sourcePattern': canonical,
                          'uncertainty': ['Local router prefix only; router inclusion and runtime deployment require review']}
                        model['operations'].append(op)
                        operations[oid] = op
                        edge(oid, owner, 'dispatch_candidate', op['evidenceIds'], 'Observed decorator and router constructor; deployment not proven')
                        entries.append({'id': oid, 'kind': 'http'})
                        events.append({'operationId': oid, 'ownerId': owner, 'ownerOperationId': owner,
                                   'kind': 'http_entry', 'path': path, 'line': symbol['line']})

    # Registration ties callback parameters to broker behavior and static
    # channel names. Matching channels remain candidates, never delivery proof.
    for call in result['callSites']:
        target = call['canonicalTarget']
        if '.declare_queue' in target and call.get('channels', {}).get('channel'):
            for binding in result['facts'][call['path']]['facts'].get('bindings', []):
                if binding['owner'] == call['owner'] and binding['line'] == call['line']:
                    queue_labels[(call['path'], call['owner'], binding['name'])] = redact(call['channels']['channel'])
        if target.endswith('.consume') and (target.startswith('aio_pika.') or '.declare_queue.' in target):
            channel = queue_labels.get((call['path'], call['owner'], call['target'].split('.')[0]))
            callback = resolver.find(call['arguments'][0], call['path'], call['owner']) if call.get('arguments') else None
            consumers.append((call, channel, callback))
            if callback:
                consumer_handlers.add(callback)
                edge(call['operationId'], callback, 'invokes_handler_candidate', [call['evidenceId']], 'Registered callback; broker invocation unverified')
            entries.append({'id': call['operationId'], 'kind': 'consumer'})

    for call in result['callSites']:
        target = call['canonicalTarget']
        tail = target.split('.')[-1]
        kind, pattern, uncertainty = None, target, []
        if target.startswith('sqlalchemy.') and target.rpartition('.')[0].split('.')[-1] in {'Session', 'AsyncSession', 'Connection', 'AsyncConnection'}:
            if tail in {'commit', 'rollback', 'begin', 'begin_nested'}:
                kind = 'transaction_boundary'
            elif tail in {'add', 'add_all', 'delete', 'flush', 'merge'}:
                kind = 'db_write'
            elif tail in {'query', 'get', 'scalars', 'scalar'}:
                kind = 'db_read'
            elif tail == 'execute':
                argument = resolver.canonical(call['arguments'][0], call['path'], call['owner']) if call.get('arguments') else ''
                kind = 'db_read' if argument == 'sqlalchemy.select' else 'db_write' if argument in {'sqlalchemy.insert', 'sqlalchemy.update', 'sqlalchemy.delete'} else 'db_execute_candidate'
                if kind == 'db_execute_candidate':
                    uncertainty.append('SQL statement effects are unresolved')
        elif '.objects.' in target and target.split('.objects.', 1)[0] in model_types and tail in {'create', 'save', 'update', 'delete', 'bulk_create', 'add', 'filter', 'get', 'all', 'first'}:
            kind = 'db_read' if tail in {'filter', 'get', 'all', 'first'} else 'db_write'
            pattern = 'Django ORM manager/result pattern: ' + target
            uncertainty.append('Model/manager dispatch remains a static candidate')
        elif target == 'django.db.transaction.atomic':
            kind = 'transaction_boundary'
        if target in {'django.urls.path', 'django.urls.re_path'}:
            kind = 'http_route_candidate'
            callback = resolver.find(call['arguments'][1], call['path'], call['owner']) if len(call.get('arguments', [])) > 1 else None
            if callback:
                edge(call['operationId'], callback, 'dispatch_candidate', [call['evidenceId']], 'Django URL callback; URL inclusion unverified')
                entries.append({'id': call['operationId'], 'kind': 'http'})
        if target.startswith('asyncio.') and tail in {'create_task', 'gather', 'wait_for', 'timeout', 'cancel', 'sleep'}:
            kind = 'async_boundary'
        if target == 'fastapi.Depends':
            kind = 'dependency'
            uncertainty.append('Dependency declaration only; injection, invocation and cleanup lifecycle are unverified')
            declaration_owner = resolver.local.get((call['path'], call.get('declarationFor')))
            if declaration_owner:
                edge(declaration_owner, call['operationId'], 'dependency_declaration', [call['evidenceId']],
                     'Declared dependency configuration; not per-invocation execution or cleanup proof')
        if target in {'fastapi.BackgroundTasks.add_task', 'starlette.background.BackgroundTasks.add_task'}:
            kind = 'background_task'
            callback = resolver.find(call['arguments'][0], call['path'], call['owner']) if call.get('arguments') else None
            if callback:
                edge(call['operationId'], callback, 'schedules_candidate', [call['evidenceId']], 'Scheduled callback; lifecycle/execution unverified')
        if target.startswith(('aio_pika.', 'aiokafka.')):
            if tail in {'publish', 'send', 'send_and_wait'}:
                kind = 'publish'
                publishers.append((call, redact(call.get('channels', {}).get('channel', ''))))
            elif tail in {'consume', 'iterator', 'getone', 'getmany'}:
                kind = 'consume'
            elif tail in {'ack', 'nack', 'reject'}:
                kind = 'acknowledgement'
        if call['ownerOperationId'] in consumer_handlers and tail in {'ack', 'nack', 'reject'}:
            kind = 'acknowledgement'
            pattern = 'Registered broker callback parameter method: ' + target
            uncertainty.append('Parameter type inferred from callback registration')
        if kind:
            mark(call, kind, pattern, uncertainty)
    for publisher, channel in publishers:
        matches = [(consumer, callback) for consumer, label, callback in consumers if channel and channel == label and not channel.startswith('[')]
        for consumer, callback in matches:
            edge(publisher['operationId'], consumer['operationId'], 'message_channel_candidate',
                 [publisher['evidenceId'], consumer['evidenceId']],
                 'Matching static channel ' + channel + '; routing, delivery and registration startup unverified')
        if not matches:
            result['unresolved'].append({'operationId': publisher['operationId'], 'owner': publisher['ownerOperationId'],
                'evidenceId': publisher['evidenceId'], 'target': 'message destination', 'kind': 'message_destination_unresolved'})
    result.update(adapters=sorted(detected), events=events, entryPoints=entries)
    # Typed framework boundaries replace an untyped unresolved-dispatch entry;
    # genuine missing internal references and broker destinations remain visible.
    known = {event['operationId'] for event in events}
    result['unresolved'] = [item for item in result['unresolved'] if item.get('kind') == 'message_destination_unresolved' or item.get('operationId') not in known]
    validate_model(model)
    return result


def model_title(operation):
    return operation['title']


def trace(model, origin, direction='forward', max_depth=8, max_nodes=200):
    graph = defaultdict(list)
    for edge in model['relationships']:
        graph[edge['source' if direction == 'forward' else 'target']].append(edge)
    seen, edges, boundaries = set(), set(), []
    queue = deque([(origin, 0)])
    while queue:
        node, depth = queue.popleft()
        if node in seen:
            continue
        if len(seen) >= max_nodes or depth >= max_depth:
            boundaries.append({'nodeId': node, 'reason': 'trace_budget'})
            continue
        seen.add(node)
        adjacent = graph.get(node, [])
        if not adjacent:
            boundaries.append({'nodeId': node, 'reason': 'static_evidence_boundary'})
        for edge in adjacent:
            edges.add(edge['id'])
            queue.append((edge['target' if direction == 'forward' else 'source'], depth + 1))
    return {'nodeIds': sorted(seen), 'edgeIds': sorted(edges), 'boundaries': boundaries,
            'limitations': ['Static candidates only; runtime ordering and delivery guarantees are unproven.']}
