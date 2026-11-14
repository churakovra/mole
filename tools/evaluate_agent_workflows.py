#!/usr/bin/env python3
"""Prepare isolated installed-skill trials and audit actual agent delivery receipts.

No model calls or synthetic model-quality scores. Human grading and comparator
runs stay NOT_RUN until real independent receipts are supplied.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]

def inventory(root):
    return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*')) if p.is_file()}

def prepare(archive,output):
    output=Path(output)
    if output.exists(): raise ValueError('Choose a new isolated trial directory.')
    output.mkdir(parents=True)
    installed=output/'installed';installed.mkdir()
    with zipfile.ZipFile(archive) as source:
        for entry in source.infolist():
            relative=Path(entry.filename)
            if relative.is_absolute() or '..' in relative.parts or relative.parts[0]!='mole':
                raise ValueError('Unsafe skill archive path.')
        source.extractall(installed)
    fixtures=output/'fixtures'
    shutil.copytree(ROOT/'tests/fixtures',fixtures)
    cases=json.loads((fixtures/'acceptance/prompts.json').read_text())['cases']
    doctor=subprocess.run([sys.executable,str(installed/'mole/scripts/mole.py'),'doctor','--json'],capture_output=True,text=True,check=True)
    value={'version':1,'archiveSha256':hashlib.sha256(Path(archive).read_bytes()).hexdigest(),
        'installedSkill':str((installed/'mole').resolve()),'fixtureRoot':str(fixtures.resolve()),
        'sourceInventory':inventory(fixtures),'doctor':json.loads(doctor.stdout),
        'cases':[{**case,'status':'NOT_RUN','target':str((fixtures/case['fixture']).resolve())} for case in cases],
        'notMeasured':['Token usage','Plain-agent baseline','MOLE v1 baseline','Independent blind human usefulness']}
    (output/'assignment.json').write_text(json.dumps(value,indent=2)+'\n')
    return value

def collect(root,receipt):
    root=Path(root);assignment=json.loads((root/'assignment.json').read_text())
    receipt=json.loads(Path(receipt).read_text());case=next(c for c in assignment['cases'] if c['id']==receipt['caseId'])
    errors=[]
    if inventory(Path(assignment['fixtureRoot']))!=assignment['sourceInventory']: errors.append('target_mutation')
    transcript=Path(receipt['transcript'])
    if not transcript.is_file() or not transcript.read_text().strip(): errors.append('missing_transcript')
    if not receipt.get('skillActivated'): errors.append('skill_not_activated')
    command=[sys.executable,str(Path(assignment['installedSkill'])/'scripts/mole.py'),'check','--workspace',receipt['workspace'],'--json']
    checked=subprocess.run(command,capture_output=True,text=True)
    check=json.loads(checked.stdout) if checked.stdout.strip() else {}
    if checked.returncode or check.get('goalStatus') not in {'READY_TO_PRESENT','PARTIAL_READY'}:errors.append('incomplete_goal')
    if check.get('requiredDeliverable',{}).get('deliverableType')!=case['requiredDeliverable']:errors.append('wrong_deliverable')
    if case['requiredDeliverable']=='chat_answer' and receipt.get('artifacts'):errors.append('forced_export')
    for artifact in receipt.get('artifacts',[]):
        if not Path(artifact).is_file():errors.append('missing_artifact')
    result={**receipt,'machineStatus':'FAIL' if errors else 'PASS','errors':errors,'check':check,
            'semanticGrade':'NOT_RUN','humanGrade':'NOT_RUN'}
    destination=root/'receipts';destination.mkdir(exist_ok=True)
    (destination/(case['id']+'-'+str(receipt.get('trial',1))+'.json')).write_text(json.dumps(result,indent=2)+'\n')
    return result

def summarize(root):
    root=Path(root);assignment=json.loads((root/'assignment.json').read_text())
    receipts=[json.loads(path.read_text()) for path in sorted((root/'receipts').glob('*.json'))]
    return {'caseCount':len(assignment['cases']),'trialCount':len(receipts),
            'machinePass':sum(r['machineStatus']=='PASS' for r in receipts),
            'machineFail':sum(r['machineStatus']=='FAIL' for r in receipts),
            'notRunCases':[c['id'] for c in assignment['cases'] if c['id'] not in {r['caseId'] for r in receipts}],
            'notMeasured':assignment['notMeasured'],'receipts':receipts}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);commands=parser.add_subparsers(dest='command',required=True)
    prep=commands.add_parser('prepare');prep.add_argument('--archive',type=Path,required=True);prep.add_argument('--output',type=Path,required=True)
    audit=commands.add_parser('collect');audit.add_argument('--run-root',type=Path,required=True);audit.add_argument('--receipt',type=Path,required=True)
    report=commands.add_parser('summarize');report.add_argument('--run-root',type=Path,required=True)
    args=parser.parse_args()
    value=prepare(args.archive,args.output) if args.command=='prepare' else collect(args.run_root,args.receipt) if args.command=='collect' else summarize(args.run_root)
    print(json.dumps(value,indent=2))
