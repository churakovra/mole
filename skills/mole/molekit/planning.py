"""Bounded request progress and structural repair tasks; no semantic reasoning."""
import hashlib
import json
from molekit.errors import MoleError
from molekit.scanner import identity


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=True).encode()).hexdigest()


def progress(session):
    return session.setdefault('progress',{'pages':[],'startedTasks':[],'evidenceIds':[],
        'lastNext':None,'blockedReason':None})


def block(session,reason):
    progress(session)['blockedReason']=reason
    session.update(investigationState='BLOCKED',phase='EVALUATE')


def record_page(session,task,page,cursor):
    state=progress(session)
    limits=session['request']['limits']; counters=session['counters']
    key=fingerprint([session['repositorySnapshotRef'],task['id'],cursor,
        page.get('context'),page.get('operations'),page.get('graphChunk'),page.get('nextCursor')])
    if key in state['pages']:
        counters['noProgressRounds']+=1
        if counters['noProgressRounds']>=limits['noProgressRounds']:
            block(session,'NO_NEW_EVIDENCE')
        return
    charge=sum(len(item.get('text','')) for item in page.get('context',[]))
    charge+=len(page.get('graphChunk',''))+len(json.dumps(page.get('operations',[]),ensure_ascii=True))
    started=task['id'] not in state['startedTasks']
    if (counters['evidenceChars']+charge>limits['maxEvidenceChars'] or
            started and counters['probeRounds']>=limits['maxProbeRounds'] or len(state['pages'])>=1024):
        block(session,'EVIDENCE_BUDGET_EXHAUSTED')
        raise MoleError('BUDGET_EXHAUSTED','Investigation evidence/round budget reached; preserve partial work and review missing proof.',6)
    if started:
        state['startedTasks'].append(task['id']); counters['probeRounds']+=1
    counters['evidenceChars']+=charge
    counters['noProgressRounds']=0
    state['pages'].append(key)
    state['evidenceIds']=sorted(set(state['evidenceIds'])|{item['evidenceId'] for item in page.get('context',[])})
    state['blockedReason']=None
    session.update(investigationState='INVESTIGATING',phase='INTERPRET')


def structural_gaps(session,scan):
    contract=session['request']['deliverable']
    graph=scan.get('processGraph')
    gaps=[]
    if contract['deliverableType'] in {'interactive_process_map','focused_map'}:
        if not graph or not graph['processes']:
            gaps.append({'kind':'review_process','requirement':'business_overview','processId':None,
                'reason':'Author source-backed business processes; extracted file groups do not satisfy the goal.'})
        else:
            claims={claim['id']:claim for claim in scan['model']['claims']}
            for process in graph['processes']:
                if not process['stepIds']:
                    gaps.append({'kind':'review_process','requirement':'subprocess_navigation','processId':process['id'],'reason':'Process has no authored steps.'})
                review=process.get('handoffReview')
                if not review or review['status']=='unknown' or any(claims[cid]['status'] in {'unknown','contradicted'} for cid in review['claimIds']):
                    gaps.append({'kind':'review_handoff','requirement':'supported_process_handoffs','processId':process['id'],
                        'reason':'Review supported handoffs or explicitly establish independence/terminal scope; never invent a connector.'})
    elif not scan['model']['claims'] and not session.get('retrieval',{}).get('negativeSearch'):
        gaps.append({'kind':'locate_evidence','requirement':'question_answered','processId':None,'reason':'The request has no accepted source-backed observations.'})
    return gaps


def next_task(session,scan):
    state=progress(session)
    signature=fingerprint([session['repositorySnapshotRef'],session['semanticRef'],session['counters']['evidenceChars']])
    if state['lastNext']==signature:
        session['counters']['noProgressRounds']+=1
    else:
        session['counters']['noProgressRounds']=0
    state['lastNext']=signature
    if state['blockedReason']=='EVIDENCE_BUDGET_EXHAUSTED' or session['counters']['noProgressRounds']>=session['request']['limits']['noProgressRounds']:
        block(session,state['blockedReason'] or 'NO_NEW_EVIDENCE')
        return None
    pending=next((task for task in session['tasks'] if task['status']=='pending'),None)
    if pending: return pending
    graph=scan.get('processGraph') or {'processes':[]}
    operations={op['id']:op for op in scan['model']['operations']}
    for gap in structural_gaps(session,scan):
        token=fingerprint([gap,session['semanticRef']])
        tid=identity('task',session['requestId']+':repair:'+token)
        if any(task['id']==tid for task in session['tasks']): continue
        ids=next((process['operationIds'] for process in graph['processes'] if process['id']==gap['processId']),session.get('retrieval',{}).get('operationIds',[]))[:30]
        if not ids: continue
        if len(session['tasks'])>=128:
            block(session,'TASK_BUDGET_EXHAUSTED'); return None
        task={'id':tid,'kind':gap['kind'],'priority':'critical','question':gap['reason'],
            'scopeKind':'request','scopeId':session['requestId'],'operationIds':ids,
            'evidenceIds':sorted({eid for oid in ids for eid in operations[oid]['evidenceIds']}),
            'baseRevision':session['repositorySnapshotRef'],'status':'pending','responseSchema':'semantic-patch.v2',
            'limitations':['Goal requirement: '+gap['requirement']]}
        session['tasks'].append(task)
        return task
    return None
