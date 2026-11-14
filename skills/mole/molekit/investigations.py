"""Request-scoped v2 sessions referencing one shared immutable repository store.

The legacy pipeline is not migrated. All v2 mutations hold the root lock, write
immutable source/semantic snapshots first, and publish small session pointers.
"""
import copy
import hashlib
import json
from pathlib import Path
import re
from typing import TypedDict

from molekit import __version__
from molekit.errors import MoleError
from molekit.model import contract, validate_model
from molekit.output import safe_path
from molekit.requests import SAFE_ID, validate_request
from molekit.scanner import identity
from molekit.workspace import atomic_json, locked, read_json, read_snapshot

MANIFEST = '.mole-v2.json'
HASH = re.compile(r'[a-f0-9]{64}')


class RepositoryPointer(TypedDict):
    repoKey: str
    repo: str
    indexScope: str
    revision: str


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def is_workspace(workspace):
    path = Path(workspace)/MANIFEST
    return path.exists() or path.is_symlink()


def _path(root, relative):
    return safe_path(root, relative)


def _manifest(directory):
    value = read_json(_path(directory, MANIFEST))
    if (not isinstance(value, dict) or set(value) != {'workspaceVersion','repoKey','repo','indexScope','activeRequestId'}
            or value['workspaceVersion'] != 2 or not isinstance(value['repo'], str)
            or not isinstance(value['indexScope'], str) or not isinstance(value['repoKey'], str)
            or not HASH.fullmatch(value['repoKey']) or not isinstance(value['activeRequestId'], str)
            or not SAFE_ID.fullmatch(value['activeRequestId'])
            or digest(str(Path(value['repo']).resolve())) != value['repoKey']):
        raise MoleError('STATE_CORRUPT', 'Invalid investigation workspace manifest.', 5)
    return value


def _session_path(directory, request_id):
    if not isinstance(request_id, str) or not SAFE_ID.fullmatch(request_id):
        raise MoleError('INVALID_REQUEST', 'Invalid request identifier.')
    return _path(directory, 'investigations/'+request_id+'/state.json')


def _validate_session(session, manifest):
    from molekit.requests import schema
    schema(session, 'investigation-state.v2.schema.json')
    request = validate_request(session['request'])
    if (session['requestId'] != request['requestId'] or session['requestHash'] != digest(request)
            or session['repoKey'] != manifest['repoKey']):
        raise MoleError('STATE_CORRUPT', 'Request binding is invalid.', 5)
    if session['semanticRef'] is not None and not HASH.fullmatch(session['semanticRef']):
        raise MoleError('STATE_CORRUPT', 'Invalid semantic snapshot reference.', 5)
    if not HASH.fullmatch(session['repositorySnapshotRef']):
        raise MoleError('STATE_CORRUPT', 'Invalid repository snapshot reference.', 5)
    for task in session['tasks']:
        contract(task, 'task')
        if task['baseRevision'] != session['repositorySnapshotRef']:
            raise MoleError('STATE_CORRUPT', 'Task revision differs from its investigation.', 5)


def _session(directory, manifest, request_id=None):
    request_id = request_id or manifest['activeRequestId']
    path = _session_path(directory, request_id)
    if not path.is_file():
        raise MoleError('REQUEST_UNKNOWN', 'Investigation does not exist.')
    value = read_json(path, max_bytes=1024*1024)
    _validate_session(value, manifest)
    return value


def _save(directory, manifest, session):
    _validate_session(session, manifest)
    encoded = (json.dumps(session, ensure_ascii=True, sort_keys=True, indent=2, allow_nan=False)+'\n').encode()
    if len(encoded) > 1024*1024:
        raise MoleError('INVALID_JSON', 'Investigation state exceeds its bounded storage budget.')
    path = _session_path(directory, session['requestId'])
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_json(path, session)


def _index(directory, manifest):
    from molekit.adapters import enrich
    from molekit.scanner import scan
    from molekit.snapshots import save
    repository = _path(directory, 'repository')
    repository.mkdir(exist_ok=True)
    current_path = _path(repository, 'current.json')
    if current_path.exists():
        current = read_json(current_path)
        if (not isinstance(current, dict) or current.get('repoKey') != manifest['repoKey']
                or current.get('repo') != manifest['repo'] or current.get('indexScope') != manifest['indexScope']):
            raise MoleError('WORKSPACE_CONFLICT', 'Repository store belongs to another repository or index scope.', 5)
    result = enrich(scan(manifest['repo'], repository, scope=manifest['indexScope']))
    revision = result['model']['revision']
    target = _path(repository, 'snapshots/'+revision+'.json')
    target.parent.mkdir(exist_ok=True)
    if not target.exists():
        save(target, result, repository, atomic_json)
    else:
        prior = read_snapshot(target, repository)
        if digest({key:value for key,value in prior.items() if key != 'stats'}) != digest({key:value for key,value in result.items() if key != 'stats'}):
            raise MoleError('STATE_CORRUPT', 'Immutable repository snapshot content differs.', 5)
    # A failed session write can leave an unused source snapshot, never a
    # half-written active session. Retain old snapshots for other investigations.
    pointer: RepositoryPointer = {key:manifest[key] for key in ('repoKey','repo','indexScope')}
    pointer['revision'] = revision
    atomic_json(current_path, pointer)
    return result


def _knowledge(directory, session):
    repository = _path(directory, 'repository')
    scan = read_snapshot(_path(repository, 'snapshots/'+session['repositorySnapshotRef']+'.json'), repository)
    if not isinstance(scan, dict) or scan.get('model', {}).get('revision') != session['repositorySnapshotRef']:
        raise MoleError('STATE_CORRUPT', 'Invalid referenced repository snapshot.', 5)
    validate_model(scan['model'])
    if session['semanticRef']:
        semantic = read_snapshot(_path(repository, 'semantic/'+session['semanticRef']+'.json'), repository)
        if digest(semantic) != session['semanticRef'] or not {'claims','semantic','claimScopes'}<=set(semantic) or set(semantic)-{'claims','semantic','claimScopes','processGraph'}:
            raise MoleError('STATE_CORRUPT', 'Semantic snapshot binding is invalid.', 5)
        scan['model']['claims'] = semantic['claims']
        scan['semantic'] = semantic['semantic']
        scan['claimScopes'] = semantic['claimScopes']
        candidate = {**scan['model'], **semantic['semantic']}
        validate_model(candidate)
        scan['model'] = candidate
        if 'processGraph' in semantic:
            from molekit.process_graph import validate_process_graph
            validate_process_graph(semantic['processGraph'],candidate)
            scan['processGraph']=semantic['processGraph']
    operation_ids = {op['id'] for op in scan['model']['operations']}
    evidence_ids = {ev['id'] for ev in scan['model']['evidence']}
    if any(not set(task.get('operationIds', [])) <= operation_ids or not set(task['evidenceIds']) <= evidence_ids for task in session['tasks']):
        raise MoleError('STATE_CORRUPT', 'Task references escaped the repository snapshot.', 5)
    return scan


def _legacy(manifest, session, scan):
    return {'schemaVersion':1, 'runId':session['requestId'], 'status':'NEEDS_ANALYSIS' if any(t['status']=='pending' for t in session['tasks']) else 'VALIDATING',
            'manifest':{'repo':manifest['repo'], 'scope':manifest['indexScope'], 'mode':'standard','engineVersion':__version__},
            'revision':session['repositorySnapshotRef'], 'scan':scan, 'tasks':session['tasks'],
            'submissions':session['submissions'], 'taskClaims':session['taskClaims'], 'claimReviews':session['claimReviews']}


def _fresh(directory, manifest, session, scan):
    from molekit.agent import ensure_fresh
    ensure_fresh(_legacy(manifest, session, scan), _path(directory, 'repository'))


def _initial_tasks(request, scan, override=None):
    from dataclasses import asdict
    from molekit.retrieval import query_for_request, search
    query, supplied = query_for_request(request,override)
    result = search(scan,query,answer_scope='repository' if query.paths else request['answerScope'])
    query_hash = digest(asdict(query))
    ranked = {item['operationId']:item['rank'] for item in result['matchReasons']}
    ids = sorted(result['operationIds'],key=lambda oid:(-ranked.get(oid,0),oid))
    operations = {op['id']:op for op in scan['model']['operations']}
    limitations = list(result['truncation'])
    if result['negativeSearch']:
        limitations.append('No indexed candidates; absence is not runtime proof.')
    tasks = []
    for offset in range(0,len(ids),30):
        selected = ids[offset:offset+30]
        reasons = [reason for item in result['matchReasons'] if item['operationId'] in selected for reason in item['reasons']]
        task = {'id':identity('task',request['requestId']+scan['model']['revision']+query_hash+':'+str(offset)),
                'kind':'locate_evidence' if 'locate' in request['intent'] else 'trace_path' if 'trace' in request['intent'] else 'review_process',
                'priority':'critical','question':('Address the original request. Candidate selection: '+'; '.join(reasons))[:600],
                'scopeKind':'request','scopeId':request['requestId'],'operationIds':selected,
                'evidenceIds':sorted({eid for oid in selected for eid in operations[oid]['evidenceIds']}),
                'baseRevision':scan['model']['revision'],'status':'pending','responseSchema':'semantic-patch.v2','limitations':limitations}
        contract(task,'task')
        tasks.append(task)
    # Persist graph references, never a second copy of source relationships.
    retrieval = {key:value for key,value in result.items() if key!='relationships'}
    retrieval['edgeIds'] = [edge['id'] for edge in result['relationships']]
    retrieval['queryHash'] = query_hash
    retrieval['query'] = supplied
    retrieval['unresolvedCount'] = len(retrieval['unresolved'])
    retrieval['unresolved'] = retrieval['unresolved'][:100]
    retrieval['coverageLimitations'] = retrieval['coverageLimitations'][:100]
    return tasks,limitations,retrieval


def summary(manifest, session, scan, stale=False):
    pending = sum(task['status']=='pending' for task in session['tasks'])
    missing = [item['id'] for item in session['request']['deliverable']['requirements'] if item['required']]
    next_action = 'update' if stale else 'next' if pending else 'review_deliverable'
    question = session['request']['question']
    retrieval = session.get('retrieval',{})
    preview = {key:retrieval.get(key) for key in ('candidateCount','coverage','truncation','negativeSearch','frontierCount')}
    if preview['negativeSearch']:
        preview['negativeSearch']={**preview['negativeSearch'],'scope':preview['negativeSearch']['scope'][:200]}
    preview['ambiguityCount']=len(retrieval.get('ambiguities',[]))
    preview['previewTruncated']=False
    for field,maximum in (('ambiguities',5),('frontier',10),('matchReasons',10),('unresolved',5),('coverageLimitations',5)):
        preview[field]=[]
        values=retrieval.get(field,[])
        for item in values[:maximum]:
            candidate={**preview,field:preview[field]+[item]}
            if len(json.dumps(candidate,ensure_ascii=True))>3744:
                preview['previewTruncated']=True
                break
            preview[field].append(item)
        if len(preview[field])<len(values): preview['previewTruncated']=True
    return {'protocolVersion':'2.0','requestId':session['requestId'], 'currentGoal':question[:600],
            'progress':{**session['counters'],'blockedReason':session.get('progress',{}).get('blockedReason')},
            'goalTruncated':len(question)>600,
            'requiredDeliverable':session['request']['deliverable'], 'repositorySnapshotRef':session['repositorySnapshotRef'],
            'engineState':'STALE' if stale else 'READY', 'investigationState':session['investigationState'],
            'phase':session['phase'], 'done':[], 'missing':missing, 'pending':pending,
            'requirements':[{'id':item['id'],'status':'UNASSESSED'} for item in session['request']['deliverable']['requirements']],
            'nextAction':'review_blocker' if session['investigationState']=='BLOCKED' else next_action,
            'nextRecommendedAction':'review_blocker' if session['investigationState']=='BLOCKED' else next_action,
            'repositoryCoverage':'PARTIAL' if scan.get('limitations') or manifest['indexScope']!='repository' else 'PASS',
            'limitations':session['limitations'],'search':preview,
            'processGraph':({'hash':digest(scan['processGraph']),**{group+'Count':len(scan['processGraph'][group]) for group in ('processes','steps','processHandoffs','stepTransitions')}} if scan.get('processGraph') is not None else None)}


def begin(repo, workspace, request):
    raw = read_json(request, max_bytes=256*1024)
    parent_id=None
    if isinstance(raw,dict) and raw.get('action')=='followUp':
        parent_id=raw.get('parentRequestId')
        if not parent_id or not raw.get('turnId') or not raw.get('question'):
            raise MoleError('INVALID_REQUEST','A follow-up requires parentRequestId, turnId and a new question.')
        with locked(workspace) as parent_directory:
            parent_manifest=_manifest(parent_directory)
            parent=_session(parent_directory,parent_manifest,parent_id)
            inherited={key:copy.deepcopy(value) for key,value in parent['request'].items() if key not in {'requestId','action','parentRequestId','turnId','question'}}
            raw={**inherited,**raw}
    value = validate_request(raw)
    repo = Path(repo).resolve()
    root = Path(workspace).absolute()
    if not repo.is_dir():
        raise MoleError('INVALID_REPOSITORY', 'Repository must exist.')
    if root.resolve().is_relative_to(repo) or repo.is_relative_to(root.resolve()):
        raise MoleError('UNSAFE_PATH', 'Keep the v2 workspace outside and separate from the target.')
    if (root/'state.json').exists():
        raise MoleError('WORKSPACE_CONFLICT', 'Use a separate workspace for v2; the v1 workspace is preserved.', 5)
    for scope in (value['indexScope'], value['answerScope']):
        if scope != 'repository':
            target = repo/scope
            if not target.exists() or target.is_symlink() or not target.resolve().is_relative_to(repo):
                raise MoleError('UNSAFE_SCOPE', 'Source scope must exist within the target.')
    repo_key = digest(str(repo))
    value.setdefault('requestId', 'req-'+digest({'repoKey':repo_key,'request':value})[:32])
    manifest = {'workspaceVersion':2,'repoKey':repo_key,'repo':str(repo), 'indexScope':value['indexScope'],'activeRequestId':value['requestId']}
    with locked(root, create=True) as directory:
        if (directory/'state.json').exists() or (directory/'state.json').is_symlink():
            raise MoleError('WORKSPACE_CONFLICT', 'Use a separate workspace for v2; the v1 workspace is preserved.', 5)
        if is_workspace(directory):
            old = _manifest(directory)
            if any(old[key] != manifest[key] for key in ('repoKey','repo','indexScope')):
                raise MoleError('WORKSPACE_CONFLICT', 'Workspace repository/index binding differs.', 5)
        path = _session_path(directory, value['requestId'])
        if path.exists():
            session = _session(directory, manifest, value['requestId'])
            if session['requestHash'] != digest(value):
                raise MoleError('REQUEST_CONFLICT', 'Request identifier already binds a different question or contract.', 5)
            scan = _knowledge(directory, session)
            stale = False
            try:
                _fresh(directory, manifest, session, scan)
            except MoleError as exc:
                if exc.code != 'TASK_STALE':
                    raise
                stale = True
            atomic_json(_path(directory, MANIFEST), manifest)
            return {**summary(manifest,session,scan,stale),'resumed':True}
        parent=None
        if parent_id:
            parent=_session(directory,manifest,parent_id)
            scan=_knowledge(directory,parent)
            _fresh(directory,manifest,parent,scan)
        else:
            scan = _index(directory, manifest)
        tasks, limitations, retrieval = _initial_tasks(value, scan)
        session = {'schemaVersion':2,'requestId':value['requestId'],'requestHash':digest(value),'repoKey':repo_key,
                   'repositorySnapshotRef':scan['model']['revision'],'request':value,
                   'investigationState':'PLANNING','phase':'UNDERSTAND','tasks':tasks,'submissions':{},
                   'semanticRef':None,'history':[],'taskClaims':{},'claimReviews':{},'limitations':limitations,
                   'counters':{'probeRounds':0,'evidenceChars':0,'noProgressRounds':0},
                   'retrieval':retrieval,'queries':[{'hash':retrieval['queryHash'],'query':retrieval['query']}]}
        if parent:
            session.update(semanticRef=parent['semanticRef'],claimReviews=copy.deepcopy(parent['claimReviews']))
            # Reuse immutable knowledge, not the old goal/answer/completion state.
            inherited_tasks=copy.deepcopy([task for task in parent['tasks'] if task['status']=='completed' or task['kind']=='claim_review'])
            if len(inherited_tasks)+len(tasks)>128:
                raise MoleError('BUDGET_EXHAUSTED','Follow-up task history exceeds the bounded session budget.',6)
            session['tasks']=inherited_tasks+tasks
            session['taskClaims']=copy.deepcopy(parent['taskClaims'])
        _save(directory,manifest,session)
        atomic_json(_path(directory, MANIFEST), manifest)
        return {**summary(manifest,session,scan),'resumed':False}


def _record_page(directory,manifest,session,task,result,cursor):
    from molekit.planning import record_page
    try:
        record_page(session,task,result,cursor)
    finally:
        _save(directory,manifest,session)
    result.update(investigationState=session['investigationState'],phase=session['phase'])
    if session['investigationState']=='BLOCKED':
        result.update(nextAction='review_blocker',nextRecommendedAction='review_blocker')


def operate(command, workspace, request_id=None, **options):
    with locked(workspace) as directory:
        manifest = _manifest(directory)
        session = _session(directory,manifest,request_id)
        scan = _knowledge(directory,session)
        if command == 'status':
            stale = False
            try:
                _fresh(directory,manifest,session,scan)
            except MoleError as exc:
                if exc.code != 'TASK_STALE':
                    raise
                stale = True
            result=summary(manifest,session,scan,stale)
            if session.get('answerRef') and not stale:
                from molekit.delivery import load_answer,validate_answer,assess
                answer=validate_answer(load_answer(directory,session),session,scan)
                result.update(assess(session,scan,answer))
                result['investigationState']=result['goalStatus']
            if stale:
                result['investigationState']='BLOCKED'
            return result
        if command == 'check':
            from molekit.delivery import load_answer,validate_answer,assess
            try:
                _fresh(directory,manifest,session,scan)
            except MoleError as exc:
                if exc.code not in {'TASK_STALE','INCOMPLETE_INVENTORY'}: raise
                return {**summary(manifest,session,scan,True),'investigationState':'BLOCKED','goalStatus':'BLOCKED','blockers':[exc.code]}
            answer=load_answer(directory,session)
            if answer: validate_answer(answer,session,scan)
            result={**summary(manifest,session,scan),**assess(session,scan,answer)}
            result['investigationState']=result['goalStatus']
            return result
        if command == 'diff':
            from molekit.update import changes
            report = changes(_legacy(manifest,session,scan),_path(directory,'repository'))
            return {**summary(manifest,session,scan),'changes':report}
        if command == 'update':
            from molekit.update import changes
            report = changes(_legacy(manifest,session,scan),_path(directory,'repository'))
            if not report['inventory']['complete']:
                raise MoleError('INCOMPLETE_INVENTORY','Restore source access before updating.',6)
            if not report['parserChanged'] and not any(report[key] for key in ('added','removed','changed')):
                return {**summary(manifest,session,scan),'changes':report}
            updated = _index(directory,manifest)
            from molekit.reuse import retain
            retained=retain(session,scan,updated,report)
            candidate={**updated['model'],**retained['semantic'],'claims':retained['claims']}
            validate_model(candidate)
            if 'processGraph' in retained:
                from molekit.process_graph import validate_process_graph
                validate_process_graph(retained['processGraph'],candidate)
            retained_ids={claim['id'] for claim in retained['claims']}
            prior_reviews={cid:review for cid,review in session['claimReviews'].items() if cid in retained_ids}
            prior_task_claims={tid:[cid for cid in ids if cid in retained_ids] for tid,ids in session['taskClaims'].items() if retained_ids.intersection(ids)}
            retained_tasks=[{**task,'baseRevision':updated['model']['revision']} for task in session['tasks']
                            if task['id'] in prior_task_claims or task['kind']=='claim_review' and set(task.get('reviewClaimIds',[]))<=retained_ids]
            session['history'].append({'repositorySnapshotRef':session['repositorySnapshotRef'],'semanticRef':session['semanticRef']})
            session['tasks'],session['limitations'],session['retrieval'] = _initial_tasks(session['request'],updated)
            session['queries'] = [{'hash':session['retrieval']['queryHash'],'query':session['retrieval']['query']}]
            report['invalidatedClaims'] = [claim['id'] for claim in scan['model']['claims'] if claim['id'] not in retained_ids]
            report['reusedClaims']=len(retained_ids)
            session.update(repositorySnapshotRef=updated['model']['revision'],semanticRef=None,submissions={},taskClaims={},claimReviews={},investigationState='PLANNING',phase='PLAN')
            if retained_ids:
                from molekit.snapshots import save
                reference=digest(retained);repository=_path(directory,'repository')
                target=_path(repository,'semantic/'+reference+'.json');target.parent.mkdir(exist_ok=True)
                save(target,retained,repository,atomic_json)
                session['semanticRef']=reference
                session['claimReviews']=prior_reviews
                session['taskClaims']=prior_task_claims
                session['tasks']+=retained_tasks
            session.pop('progress',None)
            if session.get('answerRef'):
                session.setdefault('answerHistory',[]).append({'answerRef':session.pop('answerRef'),'repositorySnapshotRef':scan['model']['revision']})
            session.pop('delivery',None)
            session['counters']={'probeRounds':0,'evidenceChars':0,'noProgressRounds':0}
            _save(directory,manifest,session)
            return {**summary(manifest,session,updated),'changes':report}
        _fresh(directory,manifest,session,scan)
        if command == 'complete':
            from molekit.delivery import complete
            return complete(directory,manifest,session,scan,options['answer'],options.get('output'),options.get('allow_partial',False),options.get('restart_export',False))
        if command == 'next':
            if options.get('query'):
                override = read_json(options['query'],max_bytes=64*1024)
                tasks,limitations,retrieval = _initial_tasks(session['request'],scan,override)
                queries = session.setdefault('queries',[])
                if retrieval['queryHash'] not in {item['hash'] for item in queries}:
                    if len(queries)>=session['request']['limits']['maxProbeRounds']:
                        raise MoleError('PROBE_LIMIT','Request probe limit reached; preserve partial state and review missing proof.',6)
                    session['tasks'] = tasks+session['tasks']
                    session['retrieval'] = retrieval
                    session['limitations'] = limitations
                    queries.append({'hash':retrieval['queryHash'],'query':retrieval['query']})
            from molekit.planning import next_task
            task = next_task(session,scan)
            if session['investigationState']!='BLOCKED':
                session.update(investigationState='INVESTIGATING' if task else 'EVALUATING',phase='PROBE' if task else 'EVALUATE')
            _save(directory,manifest,session)
            return {**summary(manifest,session,scan),'task':task}
        if command == 'inspect':
            from molekit.agent import inspect
            task = next((task for task in session['tasks'] if task['id']==options['task']),None)
            if task is None:
                raise MoleError('TASK_UNKNOWN','Task is not part of this investigation.')
            budget = options.get('budget_chars',12000)
            if budget < 1024 or budget > 32000:
                raise MoleError('INVALID_BUDGET','Inspection budget must be 1024..32000 characters.')
            header = summary(manifest,session,scan)
            context_budget = budget-len(json.dumps(header,ensure_ascii=True))-128
            if context_budget < 1024:
                raise MoleError('INVALID_BUDGET','Increase the reply budget to fit request metadata.')
            cursor=options.get('cursor','0:0')
            if cursor.startswith('graph:'):
                graph=scan.get('processGraph')
                if graph is None:
                    raise MoleError('INVALID_CURSOR','This request has no authored process graph.')
                graph_hash=digest(graph)
                parts=cursor.split(':')
                try:
                    if len(parts)==2:
                        offset=int(parts[1])
                    elif len(parts)==3 and parts[1]==graph_hash:
                        offset=int(parts[2])
                    else:
                        raise ValueError('stale graph cursor')
                except ValueError as exc:
                    raise MoleError('TASK_CONFLICT','Graph cursor is invalid or its semantic snapshot changed.',5) from exc
                serialized=json.dumps(graph,sort_keys=True,ensure_ascii=True)
                if offset<0 or offset>len(serialized):
                    raise MoleError('INVALID_CURSOR','Graph cursor is outside the serialized graph.')
                low,high=0,min(len(serialized)-offset,budget)
                def reply(length):
                    end=offset+length
                    return {**header,'graphHash':graph_hash,'graphChunk':serialized[offset:end],
                        'graphChars':len(serialized),'nextCursor':'graph:'+graph_hash+':'+str(end) if end<len(serialized) else None}
                while low<high:
                    middle=(low+high+1)//2
                    if len(json.dumps(reply(middle),ensure_ascii=True))+128<=budget: low=middle
                    else: high=middle-1
                if not low and offset<len(serialized):
                    raise MoleError('INVALID_BUDGET','Increase budget to fit the graph page header.')
                result=reply(low)
                _record_page(directory,manifest,session,task,result,cursor)
                result['progress']=summary(manifest,session,scan)['progress']
                return result
            result = {**header,**inspect(_legacy(manifest,session,scan),task,context_budget,cursor)}
            if len(json.dumps(result,ensure_ascii=True))+16>budget:
                raise MoleError('INVALID_BUDGET','Increase the reply budget to fit request metadata.')
            _record_page(directory,manifest,session,task,result,cursor)
            result['progress']=summary(manifest,session,scan)['progress']
            return result
        if command == 'submit':
            from molekit.agent import accept_patch
            response = read_json(options['input'],max_bytes=256*1024)
            if not isinstance(response,dict) or not isinstance(response.get('taskId'),str):
                raise MoleError('INVALID_PATCH','Patch requires taskId.')
            task_id = response['taskId']
            fingerprint = digest(response)
            if task_id in session['submissions']:
                if session['submissions'][task_id] != fingerprint:
                    raise MoleError('TASK_CONFLICT','A different response was accepted.',5)
                return {**summary(manifest,session,scan),'duplicate':True}
            task = next((task for task in session['tasks'] if task['id']==task_id),None)
            if task is None:
                raise MoleError('TASK_UNKNOWN','Task is not part of this investigation.')
            if task['status']!='pending' or response.get('baseRevision') != session['repositorySnapshotRef']:
                raise MoleError('TASK_STALE','Patch does not match the active task/revision.',5)
            legacy = _legacy(manifest,session,scan)
            graph_patch=None
            if response.get('protocolVersion')=='2.0':
                from molekit.requests import schema
                schema(response,'semantic-patch.v2.schema.json')
                if response['requestId']!=session['requestId']:
                    raise MoleError('REQUEST_CONFLICT','Patch belongs to another investigation.',5)
                graph_patch=response.get('processGraph')
                if graph_patch is not None and task['kind']=='claim_review':
                    raise MoleError('INVALID_PATCH','Claim-review tasks cannot author process topology.')
                legacy_response={key:value for key,value in response.items() if key in {'taskId','baseRevision','claims','review'}}
                legacy_response['protocolVersion']='1.0'
            else:
                contract(response,'semantic-patch')
                legacy_response=response
                if scan.get('processGraph') is not None and any(response.get(group) for group in ('scenarios','businessSteps','glossary','scenarioAmendments')):
                    raise MoleError('INVALID_PATCH','Use the canonical v2 process graph for new process meaning.')
            if legacy_response['claims'] or task['kind']=='claim_review':
                accept_patch(legacy,task,legacy_response)
            elif graph_patch is not None:
                task['status']='completed'
            else:
                raise MoleError('INSUFFICIENT_EVIDENCE','Submit claims or grounded canonical process knowledge.')
            if graph_patch is not None:
                from molekit.process_graph import merge_graph
                if scan.get('semantic',{}).get('scenarios'):
                    raise MoleError('SEMANTIC_MIGRATION_REQUIRED','Preserve existing legacy scenarios and use a new canonical investigation; no implicit replacement is performed.',5)
                licensed=[item for item in session['tasks'] if item['status']=='completed' or item['id']==task_id]
                allowed_operations={oid for item in licensed for oid in item.get('operationIds',[])}
                allowed_evidence={eid for item in licensed for eid in item['evidenceIds']}
                scan['processGraph']=merge_graph(scan.get('processGraph'),graph_patch,scan['model'],allowed_operations,allowed_evidence)
            semantic = {'claims':scan['model']['claims'],'semantic':scan.get('semantic',{'scenarios':[],'businessSteps':[],'glossary':[]}), 'claimScopes':scan.get('claimScopes',{})}
            if scan.get('processGraph') is not None:
                semantic['processGraph']=scan['processGraph']
            if session['semanticRef'] is not None:
                session['history'].append({'repositorySnapshotRef':session['repositorySnapshotRef'],'semanticRef':session['semanticRef']})
            semantic_ref = digest(semantic)
            repository = _path(directory,'repository')
            target = _path(repository,'semantic/'+semantic_ref+'.json')
            target.parent.mkdir(exist_ok=True)
            from molekit.snapshots import save
            save(target,semantic,repository,atomic_json)
            session.update(semanticRef=semantic_ref,taskClaims=legacy.get('taskClaims',{}),claimReviews=legacy.get('claimReviews',{}),tasks=legacy['tasks'],investigationState='EVALUATING',phase='EVALUATE')
            session['submissions'][task_id] = fingerprint
            _save(directory,manifest,session)
            return summary(manifest,session,scan)
        raise MoleError('INVALID_REQUEST','This checkpoint supports v2 begin/status/next/inspect/submit/diff/update; completion is not yet available.')
