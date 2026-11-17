"""Public source probe port used by an isolated, host-configured data process."""
import argparse
import json
import os
from pathlib import Path
import sys
from uuid import uuid4
from dataagent_contracts.core import CallContext
from dataagent_contracts.intake import SourceProfile, SourceSelection
from dataagent_runtime.policy.secrets import SecretError, resolve as resolve_secret
from .files import probe_file,_safe_path


_SECRET_OPTION_KEYS = {'token', 'password', 'secret', 'api_key', 'apikey', 'authorization'}
_SECRET_FRAGMENTS = ('token', 'secret', 'password', 'apikey', 'api_key',
                     'authorization', 'credential', 'private_key', 'cookie')


def _is_secret_option(name):
    normalized = str(name).strip().lower().replace('-', '_')
    return (normalized in _SECRET_OPTION_KEYS
            or any(fragment in normalized for fragment in _SECRET_FRAGMENTS))


def _credentials(selection, workspace, request):
    """Resolve logical credential names inside the probing process only."""
    if 'credentials' in request:
        raise ValueError('plaintext credentials are not accepted; pass logical references')
    options = request.get('credential_options') or {}
    refs = request.get('credential_refs') or {}
    if not isinstance(options, dict) or not isinstance(refs, dict):
        raise ValueError('unsupported credential configuration')
    if any(_is_secret_option(name) for name in options):
        raise ValueError('plaintext credentials are not accepted; pass logical references')
    values = dict(options)
    if selection.kind not in {'postgres', 'rest'}:
        if refs:
            raise ValueError('this source kind does not accept credentials')
        return None
    # Credential files are scoped to this workspace; a host environment
    # variable must not redirect them to another data root.
    data_root = Path(workspace).resolve() / '.dataagent'
    for name, ref in refs.items():
        if not isinstance(name, str) or not isinstance(ref, str):
            raise ValueError('unsupported credential configuration')
        try:
            values[name] = resolve_secret(ref, data_root)
        except SecretError:
            raise ValueError('configured source credential is unavailable') from None
    return values


def _classify_rest_auth(profile):
    """A 401/403 is an authentication failure, not a retryable transport error."""
    failed = any(issue.get('code') == 'http_error' and issue.get('status') in {401, 403}
                 for issue in profile.issues)
    if not failed:
        return profile
    gaps = [gap.model_copy(update={'code': 'authentication_failed'})
            if gap.code == 'http_error' else gap for gap in profile.gaps]
    if gaps == profile.gaps:
        return profile
    return profile.model_copy(update={'gaps': gaps})


def probe(selection, ctx, workspace, request):
    budget = request.get('budget_rows', 200)
    credentials = _credentials(selection, workspace, request)
    if selection.kind in {'sqlite', 'postgres'}:
        from .database import probe_database
        return probe_database(selection, ctx, workspace=workspace, budget_rows=budget, credentials=credentials)
    if selection.kind == 'rest':
        from .http import probe_rest, resume_rest
        options = {'workspace':workspace, 'budget_rows':budget, 'credentials':credentials,
                   'allowed_origins':request.get('allowed_origins')}
        if request.get('previous'):
            return _classify_rest_auth(
                resume_rest(selection, SourceProfile.model_validate(request['previous']), ctx, **options))
        return _classify_rest_auth(probe_rest(selection, ctx, **options))
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
