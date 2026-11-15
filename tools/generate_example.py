#!/usr/bin/env python3
"""Rebuild the checked-in synthetic, explicitly partial workflow example."""
import argparse
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/mole'))
from molekit.pipeline import start, operate, build_outputs
from molekit.knowledge import compose
from molekit.quality import assess
from molekit.workspace import load, read_json, atomic_json
from molekit.markdown import plan_writes, atomic_text


def generate(output, replace_generated=False):
    output = Path(output).absolute()
    if output.is_symlink():
        raise ValueError("Sample root must not be a symlink")
    output = output.resolve()
    repo = ROOT/'tests/fixtures/cross-file-workflow'
    with tempfile.TemporaryDirectory() as tmp:
        workspace = Path(tmp)/'workspace'
        start(repo,workspace,'standard','repository')
        first = True
        while (task := operate('next',workspace)['task']):
            state = load(workspace)
            task = next(item for item in state['tasks'] if item['id']==task['id'])
            claim = 'example-order' if first else 'example-' + task['id']
            patch = {'protocolVersion':'1.0','taskId':task['id'],'baseRevision':task['baseRevision'],
                'claims':[{'id':claim,'statement':'Source contains connected HTTP, storage, publication and registered consumer candidates.' if first else 'This bounded component needs separate purpose review.',
                           'status':'inferred' if first else 'unknown','evidenceIds':task['evidenceIds'] if first else [],
                           'limitations':['Synthetic fixture; no target code or infrastructure was executed.']}]}
            if first:
                operations = {op['title']:op['id'] for op in state['scan']['model']['operations']}
                titles = ['api.create_order','service.execute','repository.Store.save','sqlalchemy.orm.Session.add',
                          'sqlalchemy.orm.Session.commit','publisher.publish_order','aio_pika.Exchange.publish','worker.handle_order']
                patch['scenarios']=[{'id':'semantic-order-processing','title':'Order processing (static candidate)',
                    'trigger':'HTTP order request','actors':['Requesting client (inferred)','Registered worker callback (static)'],
                    'preconditions':['Configured session and broker are assumptions, not verified deployment facts.'],
                    'operationIds':task['operationIds'],'claimIds':[claim],
                    'steps':[{'operationId':operations[title],'description':title,'claimIds':[claim],'condition':''} for title in titles],
                    'stepTransitions':[{'fromStep':i,'toStep':i+1,'label':'Order processing path',
                        'condition':'Static interpretation; execution unverified','claimIds':[claim]} for i in range(len(titles)-1)],
                    'failurePaths':[{'condition':'ValueError in Store.save','operationIds':[operations['sqlalchemy.orm.Session.rollback']],
                        'outcome':'Matching handler attempts rollback; other failures remain unknown.','claimIds':[claim]}],
                    'stateEffects':['Static storage and publication candidates; neither transaction success nor message delivery was executed.'],
                    'outcomes':['Source links the entry, service, store, publisher and registered consumer candidates.'],
                    'unknowns':['Runtime routing, registration startup, delivery, retries and business policy require independent evidence.']}]
            path = Path(tmp)/'patch.json'
            path.write_text(json.dumps(patch))
            operate('submit',workspace,input=path)
            first = False
        state=load(workspace)
        compose(state['scan'])
        generated=build_outputs(state,output,output,['markdown','html','drawio','mermaid'],True,{},assess(state))
        # Baselines protect generated bodies; the normal writer retains both
        # Markdown and Mermaid manual sections without rewriting authored text.
        entries=list(output.rglob('*'))
        if any(path.is_symlink() for path in entries):
            raise ValueError('Sample symlinks are forbidden')
        known={path.relative_to(output).as_posix() for path in entries if path.is_file()}
        baseline_path=output/'.sample-bases.json'
        previous=read_json(baseline_path) if baseline_path.exists() else {}
        managed=known-{'.sample-bases.json'}
        if managed and not previous and not replace_generated:
            raise ValueError('Existing sample has no baseline; explicitly --replace-generated after review')
        if previous and (not isinstance(previous,dict) or any(not isinstance(key,str) or not isinstance(value,str) for key,value in previous.items())):
            raise ValueError('Invalid sample baseline')
        stale=managed-set(generated)
        for relative in managed:
            content=(output/relative).read_text(encoding='utf-8')
            if relative not in {'quality-report.json','export-losses.json'} and 'mole:generated:' not in content:
                raise ValueError('Preserve unknown sample file before rebuilding: '+relative)
        for relative in stale:
            content=(output/relative).read_text(encoding='utf-8')
            for start_marker,end_marker in [('<!-- mole:manual:start -->','<!-- mole:manual:end -->'),('%% mole:manual:start','%% mole:manual:end')]:
                if start_marker in content and content.split(start_marker,1)[1].split(end_marker,1)[0].strip():
                    raise ValueError('Retired sample contains manual notes: '+relative)
            if not relative.endswith('.json'):
                start_marker=('%% mole:generated:start id='+relative+'\n' if relative.endswith('.mmd') else '<!-- mole:generated:start id='+relative+' -->\n')
                end_marker=('%% mole:generated:end id='+relative if relative.endswith('.mmd') else '<!-- mole:generated:end id='+relative+' -->')
                if content.count(start_marker)!=1 or content.count(end_marker)!=1:
                    raise ValueError('Malformed retired sample: '+relative)
                outside=content.split(start_marker,1)[0]+content.split(end_marker,1)[1]
                for marker in ('<!-- mole:manual:start -->','<!-- mole:manual:end -->','%% mole:manual:start','%% mole:manual:end'):
                    outside=outside.replace(marker,'')
                if outside.strip():
                    raise ValueError('Retired sample contains authored prefix/suffix: '+relative)
        if replace_generated:
            # Explicit replacement still retains manual text via valid current
            # body fingerprints, rather than deleting/recreating files.
            import hashlib
            for relative in managed:
                content=(output/relative).read_text(encoding='utf-8')
                if relative.endswith('.json'):
                    body=content
                else:
                    start_marker=('%% mole:generated:start id='+relative+'\n' if relative.endswith('.mmd') else '<!-- mole:generated:start id='+relative+' -->\n')
                    end_marker=('%% mole:generated:end id='+relative if relative.endswith('.mmd') else '<!-- mole:generated:end id='+relative+' -->')
                    if content.count(start_marker)!=1 or content.count(end_marker)!=1:
                        raise ValueError('Malformed generated sample: '+relative)
                    body=content.split(start_marker,1)[1].split(end_marker,1)[0]
                previous[relative]=hashlib.sha256(body.encode()).hexdigest()
        writes,bases=plan_writes(output,generated,previous)
        for relative in stale:
            plan_writes(output,{relative:''},previous)
        for path,body in writes.items():
            atomic_text(path,body)
        for relative in stale:
            (output/relative).unlink()
        atomic_json(baseline_path,{key:value for key,value in bases.items() if key in generated})
        return {'files':len(writes),'status':'PARTIAL','authoredScenarios':len(state['scan']['semantic']['scenarios'])}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--replace-generated',action='store_true',help='Explicitly replace edited generated bodies, retaining manual sections')
    args=parser.parse_args()
    print(json.dumps(generate(ROOT/'docs/examples/workflows',args.replace_generated)))
