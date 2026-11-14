"""Goal-specific objective checks and source-bound answer/artifact completion."""
import hashlib
import json
from pathlib import Path
import re

from molekit.errors import MoleError
from molekit.requests import schema
from molekit.workspace import atomic_json,read_json,read_snapshot

BASE_MAP=('business_overview','supported_process_handoffs','subprocess_navigation','human_explanations','source_traceability','requested_artifacts')


def validate_answer(answer,session,scan):
    schema(answer,'answer-draft.v1.schema.json')
    if answer['requestId']!=session['requestId'] or answer['baseRevision']!=session['repositorySnapshotRef']:
        raise MoleError('ANSWER_STALE','Answer does not bind the current request/source revision.',5)
    from molekit.scanner import redact
    from urllib.parse import unquote
    def sensitive(value):
        if isinstance(value,str): return redact(value)!=value
        if isinstance(value,list): return any(sensitive(item) for item in value)
        if isinstance(value,dict): return any(sensitive(item) for item in value.values())
        return False
    if sensitive(answer):
        raise MoleError('SENSITIVE_INPUT','Answer contains sensitive-looking content.')
    if redact(answer['responseMarkdown'])!=answer['responseMarkdown']:
        raise MoleError('SENSITIVE_INPUT','Answer contains sensitive-looking content.')
    cited_evidence={eid for assertion in answer['assertions'] for eid in assertion['evidenceIds']}
    cited_sources={ev['sourceId'] for ev in scan['model']['evidence'] if ev['id'] in cited_evidence}
    sources=[source for source in scan['model']['sources'] if source['id'] in cited_sources]
    for raw_target in re.findall(r'\]\(([^)]+)\)',answer['responseMarkdown']):
        target,_,fragment=unquote(raw_target).partition('#')
        if target and (':' in target or target.startswith(('/', '\\')) or '..' in Path(target).parts):
            raise MoleError('UNSAFE_PATH','Answer source links must be safe repository-relative locators.')
        matches=[source for source in sources if source['path']==target]
        line=re.fullmatch(r'L(\d+)(?:-L?(\d+))?',fragment) if fragment else None
        if not matches or fragment and (not line or not any(source['lineStart']<=int(line[1])<=int(line[2] or line[1])<=source['lineEnd'] for source in matches)):
            raise MoleError('INSUFFICIENT_EVIDENCE','Answer source link must resolve within cited evidence.')
    claims={claim['id']:claim for claim in scan['model']['claims']}
    evidence={ev['id']:ev for ev in scan['model']['evidence']}
    for hypothesis in answer.get('hypotheses',[]):
        if not set(hypothesis['evidenceFor']+hypothesis['evidenceAgainst'])<=evidence.keys():
            raise MoleError('DANGLING_REFERENCE','Hypothesis cites unknown evidence.')
        if not hypothesis['unverified'] or not hypothesis['nextChecks']:
            raise MoleError('INVALID_ANSWER','Hypotheses must disclose unchecked factors and concrete next checks.')
    if answer['outcome']=='NOT_FOUND' and (not session.get('retrieval',{}).get('negativeSearch') or session['retrieval'].get('coverage')!='PASS'):
        raise MoleError('INSUFFICIENT_EVIDENCE','Incomplete static coverage permits only an explicitly limited negative result.')
    for assertion in answer['assertions']:
        if not set(assertion['claimIds'])<=claims.keys() or not set(assertion['evidenceIds'])<=evidence.keys():
            raise MoleError('DANGLING_REFERENCE','Answer cites unknown claims/evidence.')
        if assertion['category']=='negative_result':
            if not session.get('retrieval',{}).get('negativeSearch') or assertion.get('searchScope')!=session['request']['indexScope']:
                raise MoleError('INSUFFICIENT_EVIDENCE','A negative result requires the actual checked index scope.')
            continue
        if not assertion['claimIds'] or not assertion['evidenceIds']:
            raise MoleError('INSUFFICIENT_EVIDENCE','Material answer assertions require accepted claims and evidence.')
        supported={eid for cid in assertion['claimIds'] for eid in claims[cid]['evidenceIds']}
        if not set(assertion['evidenceIds'])<=supported:
            raise MoleError('INSUFFICIENT_EVIDENCE','Assertion evidence is not bound to its claims.')
        if any(claims[cid]['status'] in {'unknown','contradicted'} for cid in assertion['claimIds']) and assertion['category']!='hypothesis':
            raise MoleError('INSUFFICIENT_EVIDENCE','Unknown/contradicted claims cannot become confident observations.')
        if assertion['category']=='runtime_guarantee':
            if not assertion.get('guaranteeKind') or any(claims[cid]['status']!='runtime_verified' for cid in assertion['claimIds']) or not any(evidence[eid]['classification']=='runtime_trace' for eid in assertion['evidenceIds']):
                raise MoleError('INSUFFICIENT_EVIDENCE','A runtime guarantee needs explicit classification and runtime-trace claims.')
        elif assertion.get('guaranteeKind'):
            raise MoleError('INVALID_ANSWER','Guarantee classification is inconsistent with the assertion category.')
    if any(redact(value)!=value for value in answer['limitations']):
        raise MoleError('SENSITIVE_INPUT','Answer limitations contain sensitive-looking content.')
    return answer


def artifact_check(session):
    delivery=session.get('delivery')
    if not delivery: return False,'Requested artifacts have not been generated.'
    if delivery.get('semanticRef')!=session['semanticRef'] or delivery.get('answerRef')!=session.get('answerRef'):
        return False,'Output no longer matches the accepted semantics and answer.'
    from molekit.output import current
    try:
        pointer,manifest,root=current(delivery['logicalOutput'])
        if not pointer or pointer['generation']!=delivery['generation'] or manifest['revision']!=session['repositorySnapshotRef']:
            return False,'Output generation/revision no longer matches the request.'
        from molekit.output import safe_path
        for name,expected in manifest['files'].items():
            path=safe_path(root,name)
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
                return False,'An artifact or linked bundle file is missing or changed.'
        filenames={'html':'explorer.html','markdown':'README.md','drawio':'confluence/workflows.drawio','mermaid':'workflows.mmd'}
        for fmt in session['request']['deliverable']['formats']:
            name=filenames[fmt]; path=root/name
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=manifest['files'].get(name):
                return False,'A requested artifact is missing or changed since validation.'
            if fmt=='html':
                text=path.read_text(encoding='utf-8')
                match=re.search(r'<script id="mole-model"[^>]*>(.*?)</script>',text,re.S)
                if not match or "connect-src 'none'" not in text or re.search(r'<script\s+[^>]*src=',text,re.I):
                    return False,'Explorer structure/offline policy is invalid.'
                from molekit.model import validate_model
                validate_model(json.loads(match.group(1)))
        return True,'Requested files and structured navigation are valid; visual usability requires browser/user testing.'
    except (MoleError,OSError,ValueError,KeyError):
        return False,'Output cannot be validated safely.'


def assess(session,scan,answer=None):
    graph=scan.get('processGraph') or {'processes':[],'steps':[],'processHandoffs':[],'stepTransitions':[],'hierarchy':[]}
    claims={claim['id']:claim for claim in scan['model']['claims']}
    def known(ids): return bool(ids) and all(claims[cid]['status'] not in {'unknown','contradicted'} for cid in ids)
    has_answer=bool(answer and answer['responseMarkdown'].strip() and answer['selfReview']['goalMatched'] and answer['selfReview']['readabilityChecked'])
    source=bool(answer and answer['assertions'])
    cited={cid for assertion in (answer or {}).get('assertions',[]) for cid in assertion['claimIds']}
    cited|={cid for group in ('processes','steps','processHandoffs','stepTransitions') for item in graph[group] for cid in item['claimIds']}
    pending_reviews=[task for task in session['tasks'] if task['kind']=='claim_review' and task['status']!='completed' and cited.intersection(task.get('reviewClaimIds',[]))]
    if pending_reviews: source=False
    nav=bool(graph['processes']) and all(process['stepIds'] for process in graph['processes'])
    explanations=nav and all(known(p['claimIds']) for p in graph['processes']) and all(known(step['claimIds']) for step in graph['steps'])
    from molekit.process_graph import active_relation
    handoffs=bool(graph['processes'])
    for process in graph['processes']:
        review=process.get('handoffReview')
        incident=[edge for edge in graph['processHandoffs'] if process['id'] in (edge['fromProcessId'],edge['toProcessId']) and edge['kind']!='association' and active_relation(edge,claims)]
        if not review or review['status']=='unknown' or not known(review['claimIds']) or review['status']=='supported' and not incident or review['status']=='independent' and incident:
            handoffs=False
    if any(not active_relation(edge,claims) for edge in graph['processHandoffs']): handoffs=False
    artifacts,artifact_reason=artifact_check(session)
    facts={'question_answered':has_answer,'precise_location':has_answer and source,'scope_disclosed':bool(answer and answer['limitations']),
        'source_traceability':source,'business_overview':bool(graph['processes']),
        'supported_process_handoffs':handoffs,'subprocess_navigation':nav,'human_explanations':explanations,
        'requested_artifacts':artifacts,'hypotheses':bool(answer and answer.get('hypotheses')),
        'trace_path':bool(answer and answer.get('traceOperationIds'))}
    if facts['trace_path']:
        operations={op['id'] for op in scan['model']['operations']}; targets=answer['traceOperationIds']
        if not set(targets)<=operations: facts['trace_path']=False
        else:
            from dataclasses import replace
            from molekit.retrieval import query_for_request,search
            original,_=query_for_request(session['request'])
            anchors=search(scan,replace(original,max_depth=0),answer_scope=session['request']['answerScope'])['operationIds']
            from collections import defaultdict,deque
            adjacent=defaultdict(list)
            for edge in scan['model']['relationships']:
                if not edge['id'].startswith('view-edge-'): adjacent[edge['source']].append(edge['target'])
            seen=set();queue=deque([(targets[0],0)])
            while queue and len(seen)<session['request']['limits']['maxNodes']:
                oid,depth=queue.popleft()
                if oid in seen: continue
                seen.add(oid)
                if depth<session['request']['limits']['maxGraphHops']:
                    queue.extend((target,depth+1) for target in adjacent[oid])
            facts['trace_path']=targets[0] in anchors and set(targets)<=seen and len(targets)>1
    requirements=list(session['request']['deliverable']['requirements'])
    mandatory=['question_answered','source_traceability']
    dtype=session['request']['deliverable']['deliverableType']
    if dtype in {'interactive_process_map','focused_map'}: mandatory+=list(BASE_MAP)
    if session['request']['deliverable']['formats']: mandatory.append('requested_artifacts')
    if 'trace' in session['request']['intent']: mandatory.append('trace_path')
    if 'investigate' in session['request']['intent']: mandatory.append('hypotheses')
    present={item['kind'] for item in requirements if item['required']}
    requirements += [{'id':'base-'+kind,'kind':kind,'required':True} for kind in dict.fromkeys(mandatory) if kind not in present]
    rows=[{**item,'status':'SATISFIED' if facts.get(item['kind'],False) else 'MISSING',
        'reason':artifact_reason if item['kind']=='requested_artifacts' else 'Objective structure/source binding present; semantic truth requires review.' if facts.get(item['kind'],False) else 'Required answer or process structure is not established.'} for item in requirements]
    missing=[item['id'] for item in rows if item['required'] and item['status']!='SATISFIED']
    partial=bool(answer and (answer['outcome'] in {'PARTIAL','BLOCKED'} or answer['selfReview']['knownGaps']))
    return {'requirements':rows,'done':[item['id'] for item in rows if item['status']=='SATISFIED'],
        'missing':missing,'evidenceCoverage':session.get('retrieval',{}).get('coverage','PARTIAL'),
        'blockers':['MATERIAL_CLAIM_REVIEW_REQUIRED'] if pending_reviews else [],
        'goalStatus':'READY_TO_PRESENT' if not missing and not partial else 'PARTIAL_READY' if has_answer and answer['outcome']=='PARTIAL' and (not session['request']['deliverable']['formats'] or artifacts) else 'BLOCKED' if answer and answer['outcome']=='BLOCKED' else 'EVALUATING',
        'nextRecommendedAction':'present' if not missing and not partial else 'repair_deliverable','partial':partial}


def load_answer(directory,session):
    if not session.get('answerRef'): return None
    from molekit.output import safe_path
    from molekit.investigations import digest
    root=safe_path(directory,'repository')
    answer=read_snapshot(safe_path(root,'answers/'+session['answerRef']+'.json'),root)
    if digest(answer)!=session['answerRef']: raise MoleError('STATE_CORRUPT','Answer snapshot binding is invalid.',5)
    return answer


def complete(directory,manifest,session,scan,answer_path,output=None,allow_partial=False,restart_export=False):
    from molekit.investigations import _legacy,_save,_path,_fresh,digest,summary
    answer=validate_answer(read_json(answer_path,max_bytes=512*1024),session,scan)
    previous_answer=session.get('answerRef')
    result=assess(session,scan,answer)
    structural=[row for row in result['requirements'] if row['required'] and row['status']!='SATISFIED' and row['kind']!='requested_artifacts']
    limited=session.get('progress',{}).get('blockedReason')=='EVIDENCE_BUDGET_EXHAUSTED'
    if (structural or result['partial'] or limited) and not allow_partial:
        raise MoleError('DELIVERABLE_INCOMPLETE','Required goal criteria remain open; inspect check output and repair or explicitly return a limited result.',6)
    if allow_partial and (answer['outcome'] not in {'PARTIAL','BLOCKED'} or not answer['limitations']):
        raise MoleError('INVALID_ANSWER','Partial delivery must explicitly state its outcome and limitations.')
    formats=session['request']['deliverable']['formats']
    if formats and (scan.get('processGraph') or session['request']['deliverable']['deliverableType'] not in {'interactive_process_map','focused_map'}):
        from molekit.knowledge import compose
        from molekit.output import publish
        from molekit.pipeline import build_outputs
        repo=Path(manifest['repo']).resolve()
        output=Path(output or directory/'outputs'/session['requestId']).absolute()
        resolved=output.resolve()
        if resolved.is_relative_to(repo) or repo.is_relative_to(resolved) or directory.resolve().is_relative_to(resolved) or any(resolved.is_relative_to((directory/part).resolve()) for part in ('repository','investigations')):
            raise MoleError('UNSAFE_PATH','Use a dedicated artifact directory outside the target and knowledge stores.')
        compose(scan)
        legacy=_legacy(manifest,session,scan)
        legacy.update(session.get('publication',{}))
        legacy['deliveryIntent']={'requestId':session['requestId'],'answerRef':digest(answer),'semanticRef':session['semanticRef']}
        context={'question':session['request']['question'],'answer':answer['responseMarkdown']}
        if 'trace' in session['request']['intent'] or session['request']['deliverable']['deliverableType']=='focused_map':
            seeds=set(session.get('retrieval',{}).get('operationIds',[]))
            process=next((p for p in (scan.get('processGraph') or {}).get('processes',[]) if seeds.intersection(p['operationIds'])),None)
            if process:
                from molekit.scanner import identity
                scene_id=identity('semantic','process:'+process['id'])
                context['initialViewId']=next((v['id'] for v in scan['model']['diagramViews'] if scene_id in v.get('scenarioIds',[]) and v['id']!='view-overview'),None)
        legacy['deliveryContext']=context
        partial=bool(structural or result['partial'] or limited)
        quality={'technicalAnalysis':'PARTIAL' if scan.get('limitations') else 'PASS','semanticCoverage':'PARTIAL' if partial else 'PASS','export':'PASS','criticalUnknownCount':0,'reasons':[]}
        def persist():
            session['publication']={key:legacy[key] for key in ('pendingExport','output','outputGeneration','exportBases') if key in legacy}
            _save(directory,manifest,session)
        def build(physical,previous):
            from molekit.safety import relative_source_path
            from urllib.parse import quote,unquote
            prefix=relative_source_path(repo,physical)
            def source_link(match):
                label,target=match.groups()
                if prefix is None: return label+' (source: '+target+')'
                path,separator,fragment=unquote(target).partition('#')
                return '['+label+']('+quote(prefix+'/'+path,safe='/')+(separator+fragment if separator else '')+')'
            rendered_answer=re.sub(r'\[([^\]]+)\]\(([^)]+)\)',source_link,answer['responseMarkdown'])
            legacy['deliveryContext']={**context,'answer':rendered_answer}
            generated=build_outputs(legacy,physical,output,formats,partial,previous,quality)
            generated['answer.md']=rendered_answer+'\n\n## Limits\n\n'+'\n'.join('- '+value for value in answer['limitations'])+'\n'
            return generated
        published=publish(legacy,directory,output,formats,quality,build,persist,restart=restart_export)
        session['delivery']={key:published[key] for key in ('output','logicalOutput','generation','files')}
        session['delivery'].update(semanticRef=session['semanticRef'],answerRef=digest(answer))
        session['publication']={'output':str(output),'outputGeneration':published['generation'],'exportBases':published['manifest']['bases']}
    _fresh(directory,manifest,session,scan)
    # Bind before checking the newly generated files; persisted only after freshness.
    session['answerRef']=digest(answer)
    result=assess(session,scan,answer)
    status='READY_TO_PRESENT' if not result['missing'] and not result['partial'] and not limited else 'PARTIAL_READY' if (not formats or artifact_check(session)[0]) and answer['outcome']=='PARTIAL' else 'BLOCKED'
    from molekit.snapshots import save
    answer_ref=digest(answer);root=_path(directory,'repository');path=_path(root,'answers/'+answer_ref+'.json');path.parent.mkdir(exist_ok=True)
    save(path,answer,root,atomic_json)
    if previous_answer and previous_answer!=answer_ref:
        session.setdefault('answerHistory',[]).append({'answerRef':previous_answer,'repositorySnapshotRef':session['repositorySnapshotRef']})
    session.update(answerRef=answer_ref,investigationState=status,phase='PRESENT' if status!='BLOCKED' else 'EVALUATE')
    _save(directory,manifest,session)
    return {**summary(manifest,session,scan),**result,'investigationState':status,'goalStatus':status,
            'nextRecommendedAction':'present' if status!='BLOCKED' else 'repair_deliverable',
            'delivery':session.get('delivery'),'responseMarkdown':answer['responseMarkdown']}
