#!/usr/bin/env python3
"""Measure bounded retrieval on a synthetic star, not user-goal accuracy."""
import argparse
import json
from pathlib import Path
import platform
import sys
import time
import tracemalloc

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/mole'))
from molekit.retrieval import SearchQuery, search
from molekit.scanner import PARSER_VERSION


def benchmark(symbols):
    tracemalloc.start()
    operations=[{'id':'op-'+str(i),'kind':'function','title':'service.start' if i==0 else 'worker.operation_'+str(i),'evidenceIds':['synthetic-ev']} for i in range(symbols)]
    model={'operations':operations,'sources':[{'id':'synthetic-src','path':'synthetic.py'}],
           'evidence':[{'id':'synthetic-ev','sourceId':'synthetic-src'}],
           'relationships':[{'id':'edge-'+str(i),'source':'op-0','target':'op-'+str(i),'kind':'calls','resolution':'possible','evidenceIds':['synthetic-ev']} for i in range(1,symbols)]}
    started=time.perf_counter()
    result=search({'model':model},SearchQuery(focus_symbols=('service.start',),max_nodes=200))
    elapsed=time.perf_counter()-started
    _,peak=tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {'method':'synthetic star; shared dummy source locator; no source accuracy claim',
            'symbols':symbols,'parserVersion':PARSER_VERSION,'python':platform.python_version(),'platform':platform.system(),
            'searchSeconds':elapsed,'peakPythonBytesIncludingModel':peak,'returnedNodes':len(result['operationIds']),
            'returnedEdges':len(result['relationships']),'frontierRecords':result['frontierCount'],
            'frontierPreview':len(result['frontier']),'responseBytes':len(json.dumps(result).encode()),
            'truncation':result['truncation'],'tokens':'NOT_MEASURED','semanticAccuracy':'NOT_MEASURED'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--symbols',type=int,choices=(10000,50000),required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=benchmark(args.symbols)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
