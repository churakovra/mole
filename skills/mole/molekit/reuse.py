"""Conservative v2 reuse: unchanged files and authoring scopes, never stale proof."""
import copy


def retain(session,old,new,report):
    available={e['id'] for e in new['model']['evidence']}
    operations={o['id']:o for o in new['model']['operations']}
    old_operations={o['id']:o for o in old['model']['operations']}
    sources={s['id']:s for s in old['model']['sources']}
    evidence={e['id']:e for e in old['model']['evidence']}
    changed=set(report['changed']+report['removed']+report['added'])
    def safe_evidence(ids):
        return bool(ids) and set(ids)<=available and all(sources[evidence[e]['sourceId']]['path'] not in changed for e in ids)
    def safe_operations(ids):
        return all(oid in operations and operations[oid]==old_operations.get(oid) and safe_evidence(operations[oid]['evidenceIds']) for oid in ids)
    claims=[]
    for claim in old['model']['claims']:
        scopes=[t for t in session['tasks'] if claim['id'] in session.get('taskClaims',{}).get(t['id'],[])]
        if not report['parserChanged'] and safe_evidence(claim['evidenceIds']) and scopes and all(safe_operations(t.get('operationIds',[])) and safe_evidence(t['evidenceIds']) for t in scopes):
            claims.append(copy.deepcopy(claim))
    kept={c['id'] for c in claims}
    overlay={'claims':claims,'claimScopes':{cid:scope for cid,scope in old.get('claimScopes',{}).items() if cid in kept},
             'semantic':{'scenarios':[],'businessSteps':[],'glossary':[]}}
    for group in overlay['semantic']:
        overlay['semantic'][group]=[copy.deepcopy(item) for item in old.get('semantic',{}).get(group,[])
            if set(item['claimIds'])<=kept and safe_operations(item.get('operationIds',[]))]
    while True:
        scene_ids={scene['id'] for scene in overlay['semantic']['scenarios']}
        withdrawn={scene['id'] for scene in overlay['semantic']['scenarios'] if any(link['targetScenarioId'] not in scene_ids for link in scene.get('links',[]))}
        if not withdrawn: break
        overlay['semantic']['scenarios']=[scene for scene in overlay['semantic']['scenarios'] if scene['id'] not in withdrawn]
    graph=old.get('processGraph')
    if graph:
        graph=copy.deepcopy(graph);graph['baseRevision']=new['model']['revision']
        good=lambda item:set(item['claimIds'])<=kept and safe_operations(item.get('operationIds',[])) and (not item.get('evidenceIds') or safe_evidence(item['evidenceIds']))
        steps={s['id']:s for s in graph['steps'] if good(s)}
        graph['processes']=[p for p in graph['processes'] if good(p) and set(p['stepIds'])<=steps.keys()]
        pids={p['id'] for p in graph['processes']}
        graph['steps']=[s for s in steps.values() if s['processId'] in pids];sids={s['id'] for s in graph['steps']}
        graph['stepTransitions']=[e for e in graph['stepTransitions'] if good(e) and {e['fromStepId'],e['toStepId']}<=sids]
        withdrawn=[e for e in graph['processHandoffs'] if not good(e) or not {e['fromProcessId'],e['toProcessId']}<=pids]
        graph['processHandoffs']=[e for e in graph['processHandoffs'] if e not in withdrawn]
        for process in graph['processes']:
            review=process.get('handoffReview')
            if review and (not set(review['claimIds'])<=kept or any(process['id'] in (e['fromProcessId'],e['toProcessId']) for e in withdrawn)):
                process.pop('handoffReview',None)
                process['unknowns']=list(dict.fromkeys(process['unknowns']+['Source change requires renewed handoff review.']))
        graph['hierarchy']=[e for e in graph['hierarchy'] if good(e) and {e['parentProcessId'],e['childProcessId']}<=pids and (not e.get('entryStepId') or e['entryStepId'] in sids)]
        overlay['processGraph']=graph
    return overlay
