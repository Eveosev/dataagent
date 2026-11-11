"""Public source probe port used by an isolated, host-configured data process."""
import argparse
import json
import os
from pathlib import Path
import sys
from uuid import uuid4
from dataagent_contracts.core import CallContext
from dataagent_contracts.intake import SourceProfile, SourceSelection
from .files import probe_file,_safe_path


def probe(selection, ctx, workspace, request):
    budget = request.get('budget_rows', 200)
    credentials = request.get('credentials')
    if selection.kind in {'sqlite', 'postgres'}:
        from .database import probe_database
        return probe_database(selection, ctx, workspace=workspace, budget_rows=budget, credentials=credentials)
    if selection.kind == 'rest':
        from .http import probe_rest, resume_rest
        options = {'workspace':workspace, 'budget_rows':budget, 'credentials':credentials,
                   'allowed_origins':request.get('allowed_origins')}
        if request.get('previous'):
            return resume_rest(selection, SourceProfile.model_validate(request['previous']), ctx, **options)
        return probe_rest(selection, ctx, **options)
    if selection.kind != 'file':
        raise ValueError('unsupported source kind')
    engine = None
    ocr_issue = None
    try:
        from dataagent_ocr.adapter import load_active_engine
        from dataagent_ocr.errors import OcrError
    except ImportError as exc:
        ocr_issue = type(exc).__name__
    else:
        try:
            engine = load_active_engine(workspace / '.dataagent')
            if engine.remote:
                engine.close()
                engine = None
                ocr_issue = 'remote_ocr_requires_governed_egress'
        except (OcrError, ValueError, OSError) as exc:
            ocr_issue = type(exc).__name__
    try:
        profile = probe_file(selection, ctx, workspace=workspace, engine=engine, budget_rows=budget)
        if ocr_issue:
            profile.metadata['ocr_setup_issue'] = ocr_issue
        return profile
    finally:
        if engine is not None:
            engine.close()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--workspace',type=Path,required=True)
    args=parser.parse_args();workspace=args.workspace.resolve()
    request=json.loads(sys.stdin.read())
    selection=SourceSelection.model_validate(request['source'])
    ctx=CallContext.model_validate(request['context'])
    if request.get('operation')=='render_page':
        import hashlib
        import pdfplumber
        path=_safe_path(workspace,selection.locator_ref)
        payload=path.read_bytes()
        if 'sha256:'+hashlib.sha256(payload).hexdigest()!=request['source_revision']:
            raise ValueError('snapshot revision mismatch')
        page_number=int(request['page'])
        with pdfplumber.open(path) as pdf:
            if not 1<=page_number<=len(pdf.pages):raise ValueError('page outside document')
            page=pdf.pages[page_number-1]
            if page.width*page.height*4>16000000:raise ValueError('page render exceeds pixel budget')
            image=page.to_image(resolution=144).original
            out=workspace/'.dataagent/content'/f'{path.stem}-page-{page_number}.png'
            image.save(out,format='PNG')
        print(json.dumps({'result_path':str(out.relative_to(workspace))}));return
    profile=probe(selection,ctx,workspace,request)
    profile.metadata['worker_pid']=os.getpid()
    path=workspace/'.dataagent/results'/f'probe-{uuid4().hex}.json'
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(profile.model_dump_json(indent=2))
    print(json.dumps({'status':'partial' if profile.coverage=='partial' else 'ok',
        'result_path':str(path.relative_to(workspace)),'source_revision':profile.source_revision}))


if __name__=='__main__':main()
