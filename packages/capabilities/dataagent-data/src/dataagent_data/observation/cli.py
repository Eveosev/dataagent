"""Public source probe port used by an isolated, host-configured data process."""
import argparse
import json
import os
from pathlib import Path
import sys
from uuid import uuid4
from dataagent_contracts.core import CallContext
from dataagent_contracts.intake import SourceSelection
from .files import probe_file


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--workspace',type=Path,required=True)
    args=parser.parse_args();workspace=args.workspace.resolve()
    request=json.loads(sys.stdin.read())
    selection=SourceSelection.model_validate(request['source'])
    ctx=CallContext.model_validate(request['context'])
    engine=None;ocr_issue=None
    try:
        from dataagent_ocr.adapter import load_active_engine
        from dataagent_ocr.errors import OcrError
    except ImportError as exc:
        ocr_issue=type(exc).__name__
    else:
        try:
            engine=load_active_engine(workspace/'.dataagent')
            if engine.remote:
                engine.close();engine=None;ocr_issue='remote_ocr_requires_governed_egress'
        except (OcrError,ValueError,OSError) as exc:
            ocr_issue=type(exc).__name__
    try:
        profile=probe_file(selection,ctx,workspace=workspace,engine=engine,
            budget_rows=request.get('budget_rows',200))
        profile.metadata['worker_pid']=os.getpid()
        if ocr_issue:profile.metadata['ocr_setup_issue']=ocr_issue
        path=workspace/'.dataagent/results'/f'probe-{uuid4().hex}.json'
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(profile.model_dump_json(indent=2))
        print(json.dumps({'status':'partial' if profile.coverage=='partial' else 'ok',
            'result_path':str(path.relative_to(workspace)),'source_revision':profile.source_revision}))
    finally:
        if engine is not None:engine.close()


if __name__=='__main__':main()
