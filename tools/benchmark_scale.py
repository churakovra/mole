#!/usr/bin/env python3
"""Synthetic static-analysis engineering benchmark; no LLM quality claims."""
import argparse
import json
from pathlib import Path
import platform
import resource
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/mole'))
from molekit.pipeline import start, operate
from molekit.workspace import load
from molekit.errors import MoleError


def measure(symbols):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        repo, workspace = root / 'repo', root / 'workspace'
        repo.mkdir()
        for offset in range(0, symbols, 100):
            (repo / ('module_' + str(offset // 100) + '.py')).write_text(''.join(
                'def function_' + str(index) + '(value):\n    return value\n' for index in range(offset, min(offset+100,symbols))))
        timings = {}
        def timed(name, function):
            started = time.perf_counter()
            result = function()
            timings[name] = round(time.perf_counter()-started, 4)
            return result
        try:
            timed('startSeconds', lambda: start(repo,workspace,'standard','repository'))
            reply = timed('scanTasksSaveSeconds', lambda: operate('next',workspace))
            state = timed('loadSeconds', lambda: load(workspace))
            page = timed('inspectSeconds', lambda: operate('inspect',workspace,task=reply['task']['id'],budget_chars=3000,cursor='ops:0'))
            result = timed('composeExportSeconds', lambda: operate('finish',workspace,output=root/'output',allow_partial=True,formats=['markdown']))
            repeat = timed('unchangedUpdateSeconds', lambda: operate('update',workspace))
            return {'requestedSymbols':symbols,'parsedSymbols':len(state['scan']['model']['symbols']),
                'parserVersion':state['scan']['parserVersion'],'status':'PASS','coverage':result['status'],'tasks':len(state['tasks']),
                'taskPayloadBytes':len(json.dumps(state['tasks']).encode()),'nextReplyBytes':len(json.dumps(reply).encode()),
                'inspectReplyBytes':len(json.dumps(page).encode()),'workspacePointerBytes':(workspace/'state.json').stat().st_size,
                'workspaceBytes':sum(path.stat().st_size for path in workspace.rglob('*') if path.is_file()),
                'sourceBytes':sum(path.stat().st_size for path in repo.glob('*.py')),
                'limitations':sorted({item['reason'] for item in load(workspace)['scan']['limitations']}),
                'timings':timings,'peakRssPlatformUnits':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
        except MoleError as error:
            return {'requestedSymbols':symbols,'status':'BOUNDED_FAILURE','code':error.code,'message':str(error),'timings':timings}


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--symbols',type=int,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result={'environment':{'python':platform.python_version(),'platform':platform.platform()},'measurement':measure(args.symbols),
            'limitations':['Synthetic independent functions, not real service semantic quality.',
                            'Task/view bounds intentionally produce partial coverage.',
                            'Peak RSS is bytes on macOS and KiB on Linux; process includes all benchmark phases.']}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
