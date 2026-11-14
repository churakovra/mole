"""Canonical authored process knowledge and deterministic legacy-view projection."""
import copy
import json
from collections import defaultdict

from molekit.errors import MoleError
from molekit.requests import schema
from molekit.scanner import identity,redact

GROUPS=('processes','steps','stepTransitions','processHandoffs','hierarchy')
MAX_GRAPH_BYTES=8*1024*1024


def empty_graph(revision):
    return {'processGraphVersion':'1.0','baseRevision':revision,**{group:[] for group in GROUPS}}


def validate_process_graph(graph,model,allowed_operations=None,allowed_evidence=None):
    schema(graph,'process-graph.v1.schema.json')
    if len(json.dumps(graph,ensure_ascii=True).encode())>MAX_GRAPH_BYTES:
        raise MoleError('PROCESS_GRAPH_LIMIT','Canonical process knowledge exceeds its bounded storage budget.',6)
    if graph['baseRevision']!=model['revision']:
        raise MoleError('TASK_STALE','Process graph does not match the source revision.',5)
    operations={op['id']:op for op in model['operations'] if op['kind'] not in {'scenario_summary','component_summary'}}
    evidence={ev['id']:ev for ev in model['evidence']}
    claims={claim['id']:claim for claim in model['claims']}
    used=set()
    reserved={item['id'] for key,value in model.items() if isinstance(value,list) and key not in {'operations','relationships','diagramViews','scenarios'} for item in value if isinstance(item,dict) and 'id' in item}
    reserved|=set(operations)
    reserved|={edge['id'] for edge in model['relationships'] if not edge['id'].startswith('view-edge-')}
    for group in GROUPS:
        for item in graph[group]:
            if item['id'] in used or item['id'] in reserved:
                raise MoleError('INVALID_ID','Duplicate process graph identifier.')
            used.add(item['id'])
    processes={item['id']:item for item in graph['processes']}
    steps={item['id']:item for item in graph['steps']}
    def refs(values,lookup):
        if any(value not in lookup for value in values):
            raise MoleError('DANGLING_REFERENCE','Process knowledge references unknown entities.')
    def basis(entity,ops=None):
        refs(entity['claimIds'],claims)
        if ops is not None:
            refs(ops,operations)
            if allowed_operations is not None and not set(ops)<=allowed_operations:
                raise MoleError('INSUFFICIENT_EVIDENCE','Process operations are outside investigated task scopes.')
            supporting={ev for cid in entity['claimIds'] for ev in claims[cid]['evidenceIds']}
            anchors={ev for oid in ops for ev in operations[oid]['evidenceIds']}
            if supporting and not supporting & anchors:
                raise MoleError('INSUFFICIENT_EVIDENCE','Process claims do not intersect their operation evidence.')
        if 'evidenceIds' in entity:
            refs(entity['evidenceIds'],evidence)
            if allowed_evidence is not None and not set(entity['evidenceIds'])<=allowed_evidence:
                raise MoleError('INSUFFICIENT_EVIDENCE','Process evidence is outside investigated task scopes.')
            supported={ev for cid in entity['claimIds'] for ev in claims[cid]['evidenceIds']}
            if not set(entity['evidenceIds'])<=supported:
                raise MoleError('INSUFFICIENT_EVIDENCE','Process evidence must be supported by its claims.')
            if ops is not None and not set(entity['evidenceIds'])<={ev for oid in ops for ev in operations[oid]['evidenceIds']}:
                raise MoleError('INSUFFICIENT_EVIDENCE','Step evidence does not belong to its operation anchors.')
    for process in processes.values():
        if any(not process[field].strip() for field in ('title','purpose','trigger')):
            raise MoleError('INVALID_PROCESS_GRAPH','Process explanations must be nonblank.')
        basis(process,process['operationIds'])
        refs(process['stepIds'],steps)
        if any(steps[sid]['processId']!=process['id'] for sid in process['stepIds']):
            raise MoleError('DANGLING_REFERENCE','A process step belongs to another process.')
        if 'handoffReview' in process:
            refs(process['handoffReview']['claimIds'],claims)
    for step in steps.values():
        if not step['title'].strip() or not step['description'].strip():
            raise MoleError('INVALID_PROCESS_GRAPH','Step explanations must be nonblank.')
        refs([step['processId']],processes)
        parent=processes[step['processId']]
        if step['id'] not in parent['stepIds'] or not set(step['operationIds'])<=set(parent['operationIds']):
            raise MoleError('DANGLING_REFERENCE','Step ownership or process operation scope is inconsistent.')
        basis(step,step['operationIds'])
    for group in ('stepTransitions','processHandoffs'):
        for edge in graph[group]:
            basis(edge)
            if group=='stepTransitions':
                refs([edge['fromStepId'],edge['toStepId']],steps)
                if steps[edge['fromStepId']]['processId']!=steps[edge['toStepId']]['processId']:
                    raise MoleError('DANGLING_REFERENCE','Use a process handoff for cross-process relationships.')
                endpoint_operations=set(steps[edge['fromStepId']]['operationIds'])|set(steps[edge['toStepId']]['operationIds'])
            else:
                refs([edge['fromProcessId'],edge['toProcessId']],processes)
                if edge['fromProcessId']==edge['toProcessId']:
                    raise MoleError('INVALID_PROCESS_GRAPH','A process handoff must cross processes.')
                endpoint_operations=set(processes[edge['fromProcessId']]['operationIds'])|set(processes[edge['toProcessId']]['operationIds'])
            if not edge['label'].strip() or not set(edge['evidenceIds'])<={ev for oid in endpoint_operations for ev in operations[oid]['evidenceIds']}:
                raise MoleError('INSUFFICIENT_EVIDENCE','Relationship evidence must belong to its endpoint scopes, with a nonblank label.')
            if edge['resolution'] in {'inferred','unknown'} and not edge['limitations']:
                raise MoleError('INSUFFICIENT_EVIDENCE','Uncertain process relationships need explicit limitations.')
            kinds={evidence[eid]['classification'] for eid in edge['evidenceIds']}
            statuses={claims[cid]['status'] for cid in edge['claimIds']}-{'unknown','contradicted'}
            if edge['resolution']=='observed_runtime' and ('runtime_trace' not in kinds or (statuses and 'runtime_verified' not in statuses)):
                raise MoleError('INSUFFICIENT_EVIDENCE','Static evidence does not verify runtime process behavior.')
            if edge['resolution']=='observed_static' and statuses and ('source_observed' not in statuses or not kinds & {'source_code','test_source'}):
                raise MoleError('INSUFFICIENT_EVIDENCE','Observed-static relationships need source-observed code support.')
            if edge['resolution']=='documented_intent' and statuses and 'documented_intent' not in statuses:
                raise MoleError('INSUFFICIENT_EVIDENCE','Documented relationships require an intended-behavior claim.')
    hierarchy=defaultdict(list)
    hierarchy_pairs=set()
    for relation in graph['hierarchy']:
        basis(relation)
        refs([relation['parentProcessId'],relation['childProcessId']],processes)
        pair=(relation['parentProcessId'],relation['childProcessId'])
        if pair in hierarchy_pairs:
            raise MoleError('INVALID_PROCESS_GRAPH','Duplicate parent/child hierarchy relationship.')
        hierarchy_pairs.add(pair)
        endpoint_operations=set(processes[relation['parentProcessId']]['operationIds'])|set(processes[relation['childProcessId']]['operationIds'])
        if not set(relation['evidenceIds'])<={ev for oid in endpoint_operations for ev in operations[oid]['evidenceIds']}:
            raise MoleError('INSUFFICIENT_EVIDENCE','Hierarchy evidence must belong to its endpoint scopes.')
        if 'entryStepId' in relation:
            refs([relation['entryStepId']],steps)
            if steps[relation['entryStepId']]['processId']!=relation['childProcessId']:
                raise MoleError('DANGLING_REFERENCE','Hierarchy entry step must belong to the child process.')
        hierarchy[relation['parentProcessId']].append(relation['childProcessId'])
    visiting,done=set(),set()
    def visit(pid):
        if pid in visiting:
            raise MoleError('INVALID_PROCESS_GRAPH','Process hierarchy contains a cycle.')
        if pid in done: return
        visiting.add(pid)
        for child in hierarchy[pid]: visit(child)
        visiting.remove(pid)
        done.add(pid)
    for pid in processes: visit(pid)
    pending=[graph]
    while pending:
        item=pending.pop()
        if isinstance(item,dict): pending.extend(item.values())
        elif isinstance(item,list): pending.extend(item)
        elif isinstance(item,str) and redact(item)!=item:
            raise MoleError('SENSITIVE_INPUT','Process knowledge contains sensitive-looking text.')
    return graph


def merge_graph(previous,delta,model,allowed_operations=None,allowed_evidence=None):
    from molekit.investigations import digest
    result=copy.deepcopy(previous or empty_graph(model['revision']))
    if not isinstance(delta,dict) or not {'processGraphVersion','baseRevision'}<=set(delta) or set(delta)-set(GROUPS)-{'processGraphVersion','baseRevision','baseGraphHash','removeIds'}:
        raise MoleError('INVALID_PATCH','Invalid process patch fields.')
    schema({**empty_graph(model['revision']),**{key:value for key,value in delta.items() if key not in {'baseGraphHash','removeIds'}}},'process-graph.v1.schema.json')
    if delta.get('processGraphVersion')!='1.0' or delta.get('baseRevision')!=model['revision']:
        raise MoleError('TASK_STALE','Process patch revision/version differs.',5)
    if not any(delta.get(group) for group in GROUPS) and not delta.get('removeIds'):
        raise MoleError('INVALID_PATCH','A process patch must author knowledge.')
    if delta.get('removeIds'):
        if not isinstance(delta['removeIds'],list) or len(delta['removeIds'])>1000 or any(not isinstance(item,str) for item in delta['removeIds']):
            raise MoleError('INVALID_PATCH','Invalid process removal identifiers.')
        if delta.get('baseGraphHash')!=digest(previous):
            raise MoleError('TASK_CONFLICT','Process removal requires the current graph hash.',5)
        existing={item['id'] for group in GROUPS for item in result[group]}
        if not set(delta['removeIds'])<=existing:
            raise MoleError('DANGLING_REFERENCE','Removal may only target existing process knowledge.')
        for group in GROUPS:
            result[group]=[item for item in result[group] if item['id'] not in delta['removeIds']]
    changed=[]
    for group in GROUPS:
        lookup={item['id']:index for index,item in enumerate(result[group])}
        ids=set()
        for entity in delta.get(group,[]):
            if entity['id'] in ids:
                raise MoleError('INVALID_ID','Duplicate entity in process patch.')
            ids.add(entity['id'])
            index=lookup.get(entity['id'])
            if index is not None:
                if result[group][index]==entity: continue
                if delta.get('baseGraphHash')!=digest(previous):
                    raise MoleError('TASK_CONFLICT','Process graph changed; inspect its current hash before replacing an entity.',5)
                result[group][index]=copy.deepcopy(entity)
            else:
                result[group].append(copy.deepcopy(entity))
            changed.append((group,entity))
    validate_process_graph(result,model,allowed_operations,allowed_evidence)
    claims={claim['id']:claim for claim in model['claims']}
    for group,entity in changed:
        if (group=='hierarchy' or group in {'stepTransitions','processHandoffs'} and entity['resolution']!='unknown') and any(claims[cid]['status'] in {'unknown','contradicted'} for cid in entity['claimIds']):
            raise MoleError('INSUFFICIENT_EVIDENCE','A new established process relationship cannot cite withdrawn/unknown claims.')
    return result


def active_relation(edge,claims):
    return edge.get('resolution')!='unknown' and all(claims[cid]['status'] not in {'unknown','contradicted'} for cid in edge['claimIds'])


def project(scan):
    """Project canonical knowledge; module grouping only supplies technical views."""
    from molekit.knowledge import compose,MAX_VIEWS
    from molekit.model import validate_model
    graph=scan['processGraph']
    if graph['processes'] and scan.get('semantic',{}).get('scenarios'):
        raise MoleError('SEMANTIC_MIGRATION_REQUIRED','Legacy authored scenarios cannot be silently replaced by canonical processes; preserve this session and author a new canonical investigation.',5)
    model=scan['model']
    model['operations']=[op for op in model['operations'] if op['kind'] not in {'scenario_summary','component_summary'}]
    model['relationships']=[edge for edge in model['relationships'] if not edge['id'].startswith('view-edge-')]
    validate_process_graph(graph,model)
    authored=scan.get('semantic',{})
    technical={**scan,'processGraph':None,'semantic':{'scenarios':authored.get('scenarios',[]),
        'businessSteps':authored.get('businessSteps',[]),'glossary':authored.get('glossary',[])}}
    available=max(0,MAX_VIEWS-len(graph['processes'])-1)
    if available:
        compose(technical,view_budget=max(0,available-1))
        technical_views=list(model['diagramViews'])
    else:
        for group in ('scenarios','businessSteps','diagramViews','glossary','qualityFindings'):
            model[group]=[]
        model['businessSteps']=copy.deepcopy(authored.get('businessSteps',[]))
        model['glossary']=copy.deepcopy(authored.get('glossary',[]))
        technical_views=[]
    if technical_views and technical_views[0]['id']=='view-overview':
        technical_views[0]={**technical_views[0],'id':'view-technical-overview','title':'Technical source scopes'}
    views={view['id']:view for view in technical_views}
    operations={op['id']:op for op in model['operations']}
    source_operations={op['id']:op for op in model['operations'] if op['kind'] not in {'scenario_summary','component_summary'}}
    claims={claim['id']:claim for claim in model['claims']}
    processes={process['id']:process for process in graph['processes']}
    steps={step['id']:step for step in graph['steps']}
    process_views={pid:identity('view','process:'+pid) for pid in processes}
    overview={'id':'view-overview','title':'Business processes','scenarioIds':[],'nodes':[],'edgeIds':[],'childRefs':[]}
    def operation(oid,title,kind,operation_ids,claim_ids,description='',purpose=''):
        item={'id':oid,'title':title,'kind':kind,'evidenceIds':sorted({ev for source in operation_ids for ev in source_operations[source]['evidenceIds']}),
              'claimIds':list(claim_ids),'description':description,'purpose':purpose}
        model['operations'].append(item)
        operations[oid]=item
    def technical_child(step):
        for oid in step['operationIds']:
            anchor=oid if source_operations[oid]['kind'] in {'function','async_function','class'} else source_operations[oid].get('ownerId',oid)
            candidate=identity('view','callable:'+anchor)
            if candidate in views: return candidate
        anchor=step['operationIds'][0]
        candidate=identity('view','source-detail:'+anchor)
        if candidate not in views and len(views)+len(processes)+1<MAX_VIEWS:
            views[candidate]={'id':candidate,'title':'Source: '+source_operations[anchor]['title'],'scenarioIds':[],
                'nodes':[{'id':oid,'label':source_operations[oid]['title']} for oid in step['operationIds']], 'edgeIds':[],'childRefs':[]}
        return candidate if candidate in views else None
    def edge_projection(edge,source,target,kind):
        eid=identity('view-edge','process:'+edge['id'])
        resolution={'observed_static':'resolved_static','documented_intent':'possible','inferred':'possible','unknown':'unresolved','observed_runtime':'observed_runtime'}[edge['resolution']]
        model['relationships'].append({'id':eid,'source':source,'target':target,'kind':'business_association' if edge['kind']=='association' else kind,
            'resolution':resolution,'evidenceStatus':edge['resolution'],'semanticKind':edge['kind'],'claimIds':edge['claimIds'],
            'evidenceIds':edge['evidenceIds'],'condition':edge['label']+(': '+edge['condition'] if edge['condition'] else '')})
        return eid
    canonical_scenes=[]
    for pid,process in processes.items():
        step_ids=process['stepIds']
        scene_id=identity('semantic','process:'+pid)
        related_claims=set(process['claimIds'])|{cid for sid in step_ids for cid in steps[sid]['claimIds']}
        related_claims|={cid for edge in graph['stepTransitions'] if steps[edge['fromStepId']]['processId']==pid for cid in edge['claimIds']}
        related_claims|={cid for edge in graph['processHandoffs'] if edge['fromProcessId']==pid for cid in edge['claimIds']}
        operation(pid,process['title'],'scenario_summary',process['operationIds'],sorted(related_claims),purpose=process['purpose'])
        view={'id':process_views[pid],'title':process['title'],'scenarioIds':[scene_id],'nodes':[],'edgeIds':[],'childRefs':[]}
        for sid in step_ids:
            step=steps[sid]
            operation(sid,step['title'],'component_summary',step['operationIds'],step['claimIds'],step['description'],process['purpose'])
            node={'id':sid,'label':step['title']}
            child=technical_child(step)
            if child:
                node['childViewId']=child
                view['childRefs'].append(child)
            else:
                if not any(item.get('reason')=='process_technical_drilldown_budget' for item in scan['limitations']):
                    scan['limitations'].append({'path':'.','reason':'process_technical_drilldown_budget'})
            view['nodes'].append(node)
        for edge in graph['stepTransitions']:
            if steps[edge['fromStepId']]['processId']==pid and active_relation(edge,claims):
                view['edgeIds'].append(edge_projection(edge,edge['fromStepId'],edge['toStepId'],'business_transition'))
        for relation in graph['hierarchy']:
            if relation['parentProcessId']==pid and active_relation(relation,claims):
                child=relation['childProcessId']
                view['nodes'].append({'id':child,'label':processes[child]['title'],'childViewId':process_views[child]})
                view['childRefs'].append(process_views[child])
        view['childRefs']=sorted(set(view['childRefs']))
        views[view['id']]=view
        unknowns=list(process['unknowns'])
        for group in ('stepTransitions','processHandoffs'):
            for edge in graph[group]:
                belongs=(steps[edge['fromStepId']]['processId']==pid) if group=='stepTransitions' else edge['fromProcessId']==pid
                if belongs and not active_relation(edge,claims):
                    unknowns.append('Not established: '+edge['label']+(' — '+'; '.join(edge['limitations']) if edge['limitations'] else '; supporting claims need review.'))
        canonical_scenes.append({'id':scene_id,'kind':'authored_workflow','title':process['title'],'purpose':process['purpose'],
            'trigger':process['trigger'],'actors':process['actors'],'preconditions':process['preconditions'],
            'operationIds':[pid,*process['operationIds']],'claimIds':sorted(related_claims),'outcomes':process['outcomes'],'unknowns':unknowns,
            'steps':[{'operationId':steps[sid]['operationIds'][0],'description':steps[sid]['title'],'condition':'','claimIds':steps[sid]['claimIds']} for sid in step_ids],
            'failurePaths':[],'stateEffects':[]})
        overview['nodes'].append({'id':pid,'label':process['title'],'childViewId':view['id']})
        overview['childRefs'].append(view['id'])
        overview['scenarioIds'].append(scene_id)
    for edge in graph['processHandoffs']:
        if active_relation(edge,claims):
            overview['edgeIds'].append(edge_projection(edge,edge['fromProcessId'],edge['toProcessId'],'business_handoff'))
    model['scenarios']=canonical_scenes+model['scenarios']
    model['diagramViews']=[overview,*views.values()] if processes else technical_views
    validate_model(model)
    return model
