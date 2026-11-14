"""Deterministic lexical/route search and bounded graph traversal, never an LLM."""
from collections import defaultdict, deque
from dataclasses import dataclass
import re

from molekit.errors import MoleError
from molekit.requests import safe_scope

STOP = set('where what why how when which is are does do this the a an to of for in with me explain trace service works code function где как что это и в на'.split())
EXPANSIONS = {'duplicate':{'ack','nack','retry','consume','publish','sleep'},
              'duplicates':{'ack','nack','retry','consume','publish','sleep'},
              'notifications':{'ack','nack','consume','publish','send'},
              'rollback':{'rollback','transaction'},'jwt':{'jwt','token','auth'}}
ROUTE = re.compile(r'\b(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS|WEBSOCKET)\s+(/[^\s?`"\']*)',re.I)


@dataclass(frozen=True)
class SearchQuery:
    text: str = ''
    focus_symbols: tuple = ()
    paths: tuple = ()
    route_hints: tuple = ()
    topics: tuple = ()
    direction: str = 'forward'
    limit: int = 20
    max_depth: int = 16
    max_nodes: int = 200
    max_edges: int = 1000

    def validate(self):
        if (not isinstance(self.text,str) or len(self.text)>8192 or not isinstance(self.direction,str) or self.direction not in {'forward','reverse','both','none'}
                or type(self.limit) is not int or not 1<=self.limit<=1000
                or type(self.max_depth) is not int or not 0<=self.max_depth<=32
                or type(self.max_nodes) is not int or not 1<=self.max_nodes<=1000
                or type(self.max_edges) is not int or not 1<=self.max_edges<=10000):
            raise MoleError('INVALID_QUERY','Search query exceeds its bounded contract.')
        for values in (self.focus_symbols,self.paths,self.route_hints,self.topics):
            if not isinstance(values,(tuple,list)) or len(values)>32 or any(not isinstance(item,str) or len(item)>500 for item in values):
                raise MoleError('INVALID_QUERY','Invalid bounded query fields.')
        for path in self.paths:
            safe_scope(path)


def tokens(text):
    text=re.sub(r'([a-z0-9])([A-Z])',r'\1 \2',text)
    return set(re.findall(r'[^\W_]+',text.casefold(),re.UNICODE))-STOP


def _within(paths,scope):
    return scope=='repository' or any(path==scope or path.startswith(scope.rstrip('/')+'/') for path in paths)


def search(scan,query,answer_scope='repository'):
    query.validate()
    safe_scope(answer_scope)
    model=scan['model']
    operations={op['id']:op for op in model['operations'] if op['kind'] not in {'scenario_summary','component_summary'}}
    evidence={item['id']:item for item in model['evidence']}
    sources={item['id']:item for item in model['sources']}
    paths={oid:{sources[evidence[eid]['sourceId']]['path'] for eid in op['evidenceIds']} for oid,op in operations.items()}
    channels=defaultdict(list)
    for call in scan.get('callSites',[]):
        channels[call['operationId']].extend(call.get('channels',{}).values())
    routes=[(method.upper(),path.rstrip('.,;')) for method,path in ROUTE.findall(query.text)]
    for hint in query.route_hints:
        routes.extend((method.upper(),path.rstrip('.,;')) for method,path in ROUTE.findall(hint))
    words=tokens(' '.join((query.text,*query.focus_symbols,*query.topics)))
    expanded=set().union(*(EXPANSIONS.get(word,set()) for word in words)) if words else set()
    browse=not words and not routes and not query.focus_symbols and not query.topics
    ranked=[]
    for oid,op in operations.items():
        if not _within(paths[oid],answer_scope) or (query.paths and not any(_within(paths[oid],scope) for scope in query.paths)):
            continue
        title=op['title'].casefold()
        op_words=tokens(' '.join((op['title'],op['kind'],*paths[oid],*channels[oid],*op.get('searchTerms',[]))))
        reasons=[]
        score=0
        exact_route=(op.get('routeMethod','').upper(),op.get('routePath')) in routes
        if routes:
            # A method-only lexical hit cannot substitute for a missing route.
            if not exact_route:
                continue
            score=2000
            reasons.append('exact route method and local path; deployment unverified')
        for focus in query.focus_symbols:
            if title==focus.casefold() or title.endswith('.'+focus.casefold()):
                score+=1000
                reasons.append('exact symbol candidate: '+focus)
        matched=words & op_words
        if matched:
            score+=30*len(matched)
            reasons.append('lexical tokens: '+', '.join(sorted(matched)))
        synonyms=expanded & op_words
        if synonyms:
            score+=15*len(synonyms)
            reasons.append('candidate expansion only: '+', '.join(sorted(synonyms)))
        if browse:
            score={'documented_input':120,'function':100,'async_function':100,'class':90}.get(op['kind'],80)
            reasons.append('explicit source-scope browse; business meaning requires agent review')
        if score:
            ranked.append((score,oid,reasons))
    ranked.sort(key=lambda item:(-item[0],operations[item[1]]['title'],item[1]))
    if query.focus_symbols and ranked and ranked[0][0]>=1000 and not routes:
        ranked=[item for item in ranked if item[0]>=1000]
    candidates=len(ranked)
    seeds=ranked[:query.limit]
    truncation=['seed_limit'] if candidates>query.limit else []
    outgoing,incoming=defaultdict(list),defaultdict(list)
    relationships={edge['id']:edge for edge in model['relationships'] if edge['source'] in operations and edge['target'] in operations and not edge['id'].startswith('view-edge-')}
    for edge in relationships.values():
        outgoing[edge['source']].append((edge['target'],edge))
        incoming[edge['target']].append((edge['source'],edge))
    for adjacency in (outgoing,incoming):
        for values in adjacency.values(): values.sort(key=lambda item:(item[1]['id'],item[0]))
    queue=deque()
    discovered=set()
    visited={}
    frontier=[]
    frontier_count=0
    frontier_keys=set()
    def boundary(item):
        nonlocal frontier_count
        frontier_count+=1
        key=(item['operationId'],item.get('edgeId'),item['reason'])
        if len(frontier)<100 and key not in frontier_keys:
            frontier.append(item)
            frontier_keys.add(key)
    for _,oid,_ in seeds:
        if len(discovered)>=query.max_nodes:
            boundary({'operationId':oid,'reason':'node_budget'})
        elif oid not in discovered:
            discovered.add(oid)
            queue.append((oid,0))
    while queue:
        oid,depth=queue.popleft()
        if oid in visited:
            continue
        visited[oid]=depth
        adjacent=[]
        if query.direction in {'forward','both'}: adjacent+=outgoing.get(oid,[])
        if query.direction in {'reverse','both'}: adjacent+=incoming.get(oid,[])
        for target,edge in adjacent:
            if target in discovered: continue
            if depth>=query.max_depth:
                boundary({'operationId':target,'fromOperationId':oid,'edgeId':edge['id'],'reason':'depth_budget'})
            elif len(discovered)>=query.max_nodes:
                boundary({'operationId':target,'fromOperationId':oid,'edgeId':edge['id'],'reason':'node_budget'})
            else:
                discovered.add(target)
                queue.append((target,depth+1))
    if frontier: truncation.append('graph_frontier')
    ids=set(visited)
    edges=sorted((edge for edge in relationships.values() if edge['source'] in ids and edge['target'] in ids),key=lambda edge:edge['id'])
    if len(edges)>query.max_edges:
        truncation.append('edge_budget')
        for edge in edges[query.max_edges:query.max_edges+100]:
            boundary({'operationId':edge['target'],'fromOperationId':edge['source'],'edgeId':edge['id'],'reason':'edge_budget'})
        frontier_count+=max(0,len(edges)-query.max_edges-100)
        edges=edges[:query.max_edges]
    selected_paths=set().union(*(paths[oid] for oid in ids)) if ids else set()
    coverage=[item for item in scan.get('limitations',[]) if item.get('path')=='.' or item.get('path') in selected_paths]
    if not seeds:
        coverage=[item for item in scan.get('limitations',[]) if item.get('path')=='.' or _within({item.get('path','')},answer_scope)]
        if routes:
            for oid,op in operations.items():
                if op['kind']=='http_entry' and _within(paths[oid],answer_scope) and any(
                    op.get('routeMethod') in {method,'<DYNAMIC>'} and op.get('routePath') in {path,'<dynamic>'}
                    for method,path in routes):
                    coverage.append({'path':sorted(paths[oid])[0],'reason':'dynamic_route_registration_unresolved'})
    index_scope=scan.get('indexScope','repository')
    if index_scope!='repository' and (answer_scope=='repository' or not _within({answer_scope},index_scope)):
        coverage.append({'path':index_scope,'reason':'index_scope_boundary'})
    unresolved=[item for item in scan.get('unresolved',[]) if item.get('operationId') in ids]
    ambiguities=[]
    for focus in query.focus_symbols:
        matches=[oid for _,oid,_ in ranked if operations[oid]['kind'] in {'function','async_function','class'} and
                 (operations[oid]['title'].casefold()==focus.casefold() or operations[oid]['title'].casefold().endswith('.'+focus.casefold()))]
        if len(matches)>1:
            matches=sorted(matches)
            ambiguities.append({'query':focus[:200],'operationIds':matches[:20],
                'titles':[operations[oid]['title'][:120] for oid in matches[:20]],
                'matchCount':len(matches),'previewTruncated':len(matches)>20})
    for method,path in sorted(set(routes)):
        matches=sorted(oid for _,oid,_ in ranked if (operations[oid].get('routeMethod'),operations[oid].get('routePath'))==(method,path))
        if len(matches)>1:
            ambiguities.append({'query':method+' '+path[:200],'operationIds':matches[:20],
                'titles':[operations[oid]['title'][:120] for oid in matches[:20]],
                'matchCount':len(matches),'previewTruncated':len(matches)>20})
    evidence_ids=sorted({eid for oid in ids for eid in operations[oid]['evidenceIds']} | {eid for edge in edges for eid in edge['evidenceIds']})
    match_reasons=[{'operationId':oid,'rank':score,'reasons':[reason[:200] for reason in reasons[:4]]} for score,oid,reasons in seeds if oid in ids]
    for oid in sorted(ids-{item['operationId'] for item in match_reasons}):
        match_reasons.append({'operationId':oid,'rank':max(1,100-visited[oid]),'reasons':['connected static graph candidate, distance '+str(visited[oid])]})
    # Frontier is bounded independently of graph fan-out. Disclose omissions.
    if frontier_count>len(frontier): truncation.append('frontier_preview_limit')
    return {'operationIds':sorted(ids),'evidenceIds':evidence_ids,
            'relationships':sorted(edges,key=lambda edge:edge['id']),'matchReasons':match_reasons,
            'candidateCount':candidates,'frontier':frontier,'frontierCount':frontier_count,
            'truncation':truncation,'ambiguities':ambiguities,'unresolved':unresolved,
            'coverageLimitations':coverage,'coverage':'PARTIAL' if coverage or truncation or unresolved else 'PASS',
            'negativeSearch':None if seeds else {'scope':'indexed static candidates within '+answer_scope,
                'reason':'No exact indexed route' if routes else 'No lexical/exact indexed candidates',
                'notRuntimeAbsenceProof':True}}


def query_for_request(request, override=None):
    """Apply host-supplied query primitives, bounded by the admitted request."""
    from molekit.requests import schema
    from molekit.scanner import redact
    admitted=request.get('search',{})
    seed_fields={'text','focusSymbols','paths','routeHints','topics'}
    if override is None:
        data=admitted
    else:
        schema(override,'search-query.v1.schema.json')
        base={key:value for key,value in admitted.items() if key not in seed_fields} if seed_fields & override.keys() else admitted
        data={**base,**override}
    schema(data,'search-query.v1.schema.json')
    data={key:[redact(item) for item in value] if isinstance(value,list) else redact(value) if isinstance(value,str) else value for key,value in data.items()}
    browse='system_orientation' in request['intent'] and not request['focus'] and not data
    direction='forward' if 'trace' in request['intent'] else 'both' if 'investigate' in request['intent'] else 'none'
    explicit_seeds=bool(seed_fields & data.keys())
    # A new literal symbol/topic/path probe must not accidentally retain an
    # exact route or focus from the original goal and drown out the new seed.
    query=SearchQuery(text=data.get('text','' if browse or explicit_seeds else request['question']),
        focus_symbols=tuple(data.get('focusSymbols',[] if explicit_seeds else request['focus'])),paths=tuple(data.get('paths',[])),
        route_hints=tuple(data.get('routeHints',[])),topics=tuple(data.get('topics',[])),
        direction=data.get('direction',direction),limit=min(data.get('limit',request['limits']['maxNodes'] if browse else 20),request['limits']['maxNodes']),
        max_depth=min(data.get('maxDepth',request['limits']['maxGraphHops']),request['limits']['maxGraphHops']),
        max_nodes=min(data.get('maxNodes',request['limits']['maxNodes']),request['limits']['maxNodes']),max_edges=data.get('maxEdges',1000))
    query.validate()
    return query,data
