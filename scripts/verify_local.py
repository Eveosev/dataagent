"""Install actual local packages in a fresh project and verify their public CLI."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]


def run(command,cwd):
    result=subprocess.run([str(a) for a in command],cwd=cwd,capture_output=True,text=True)
    if result.returncode:
        raise RuntimeError(f'{command[0]} failed ({result.returncode}):\n{result.stdout[-6000:]}\n{result.stderr[-6000:]}')
    return result.stdout


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['bootstrap'],default='bootstrap')
    parser.add_argument('--output',type=Path,default=ROOT/'.superpowers/sdd/16-local-ingestion-workflow-build-plan/acceptance')
    args=parser.parse_args()
    mint=shutil.which('mint') or str(Path.home()/'.mint/bin/mint')
    project=Path(tempfile.mkdtemp(prefix='dataagent-intake-'))
    run([mint,'init','--no-preset'],project)
    run([mint,'add','path:'+str(ROOT/'build/local/preset-intake'),'--offline','-y'],project)
    cli=list((project/'.mint/packages/dataagent').glob('cli@*/bin/dataagent'))
    assert len(cli)==1,'exactly one installed CLI required'
    run([cli[0],'setup'],project)
    doctor=run([cli[0],'doctor'],project)
    created=json.loads(run([cli[0],'workbench','intake','--goal','本地接入验收','--source','invoice.csv'],project))
    session=created['result']['data']['session_id']
    status=json.loads(run([cli[0],'workbench','status',session],project))
    assert status['result']['data']['job_ref']==created['result']['data']['job_ref']
    assert status['result']['data']['phase']=='queued'
    args.output.mkdir(parents=True,exist_ok=True)
    report={'phase':args.phase,'status':'passed','project':str(project),'session_id':session,
        'mint':run([mint,'--version'],project).strip(),'doctor':doctor,
        'manifest':json.loads((ROOT/'build/local/manifest.json').read_text()),
        'not_verified':['file processing','TUI session','GUI session']}
    (args.output/f'{args.phase}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps({'status':'passed','project':str(project),'report':str(args.output/f'{args.phase}.json')},ensure_ascii=False))


if __name__=='__main__':main()
