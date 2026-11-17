"""Public source probe port used by an isolated, host-configured data process.

The workbench calls this module once per probe segment.  A request may carry a
``budget_seconds`` wall-clock allowance and the ``previous`` profile to resume.
Each call returns a profile; when work remains it has ``metadata.resume`` and a
``time_budget_exceeded`` gap.  Failures are reported as structured JSON on
standard output with an error code and a retryability flag, never as a bare
traceback.
"""
import argparse
import json
import math
import os
from pathlib import Path
import sys
import time
from uuid import uuid4
from dataagent_contracts.core import CallContext
from dataagent_contracts.intake import CoverageGap, SourceProfile, SourceSelection
from dataagent_runtime.policy.secrets import SecretError, resolve as resolve_secret
from .files import probe_file,_safe_path


_BUDGET_GAP = 'time_budget_exceeded'
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


def _option(request, name, default, maximum):
    value = request.get(name, default)
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
        raise ValueError(f'{name} must be an integer between 1 and {maximum}')
    return value


def _deadline(request):
    seconds = request.get('budget_seconds')
    if seconds is None:
        return None
    if (isinstance(seconds, bool) or not isinstance(seconds, (int, float))
            or not math.isfinite(float(seconds)) or seconds <= 0):
        raise ValueError('budget_seconds must be a positive number')
    return time.monotonic() + min(float(seconds), 120.0)


class _RestSegmentStop(TimeoutError):
    """Raised inside the fetch wrapper when this segment's page allowance ends."""


def _segmented_rest(selection, ctx, workspace, *, budget_rows, credentials,
                    allowed_origins, previous, deadline, segment_pages):
    """Fetch at most ``segment_pages`` REST pages per call.

    ``probe_rest`` owns pagination/version/row-budget semantics.  We bound its
    page loop by wrapping the module's ``fetch`` for this call: the wrapper
    raises a TimeoutError at the segment boundary, which the existing probe
    already treats as a transport failure.  The synthetic failure is replaced
    by a resumable checkpoint so completed pages are never fetched again.
    """
    from . import http as http_module
    from .http import probe_rest
    if previous is not None:
        metadata = previous.metadata if isinstance(previous.metadata, dict) else {}
        if (previous.source_id != selection.source_id or previous.kind != 'rest'
                or metadata.get('row_offset') != 0
                or not metadata.get('cursor')
                # A version is preferred, but a versionless source can still
                # resume by its cursor; probe_rest marks the resulting
                # multi-page observation as snapshot-unverified.
                or 'source_version' not in metadata
                or not metadata.get('connection_revision')
                or not isinstance(metadata.get('pages'), list)
                or not isinstance(metadata.get('record_keys'), list)):
            # Not a verifiable page checkpoint: observe the source afresh.
            previous = None
    original = http_module.fetch
    state = {'remaining': max(1, int(segment_pages)), 'stopped': False}

    def limited_fetch(url, headers):
        if (state['stopped'] or state['remaining'] <= 0
                or (deadline is not None and time.monotonic() >= deadline)):
            state['stopped'] = True
            raise _RestSegmentStop()
        state['remaining'] -= 1
        return original(url, headers)

    http_module.fetch = limited_fetch
    try:
        profile = probe_rest(selection, ctx, workspace=workspace, budget_rows=budget_rows,
                             credentials=credentials, allowed_origins=allowed_origins,
                             previous=previous)
    finally:
        http_module.fetch = original
    if not state['stopped']:
        return profile
    blocked = len(profile.metadata.get('pages', [])) + 1
    gaps = [gap for gap in profile.gaps
            if gap.code != _BUDGET_GAP
            and not (gap.code == 'connection_failed' and gap.partition == blocked)]
    gaps.append(CoverageGap(partition=blocked, code=_BUDGET_GAP))
    issues = [issue for issue in profile.issues
              if issue.get('code') != 'connection_failed']
    metadata = {**profile.metadata, 'resume': {'kind': 'rest', 'next_page': blocked}}
    return profile.model_copy(update={'gaps': gaps, 'issues': issues, 'metadata': metadata})


def probe(selection, ctx, workspace, request):
    workspace = Path(workspace)
    budget = request.get('budget_rows', 200)
    if isinstance(budget, bool) or not isinstance(budget, int) or not 1 <= budget <= 10000:
        raise ValueError('row budget must be an integer between 1 and 10000')
    segment_rows = _option(request, 'segment_rows', 2000, 100000)
    segment_pages = _option(request, 'segment_pages', 10, 1000)
    segment_blocks = _option(request, 'segment_blocks', 200, 100000)
    segment_sheets = _option(request, 'segment_sheets', 5, 1000)
    deadline = _deadline(request)
    previous = (SourceProfile.model_validate(request['previous'])
                if request.get('previous') is not None else None)
    credentials = _credentials(selection, workspace, request)
    if selection.kind in {'sqlite', 'postgres'}:
        from .database import probe_database
        return probe_database(selection, ctx, workspace=workspace, budget_rows=budget, credentials=credentials)
    if selection.kind == 'rest':
        return _classify_rest_auth(_segmented_rest(selection, ctx, workspace,
            budget_rows=budget, credentials=credentials,
            allowed_origins=request.get('allowed_origins'), previous=previous,
            deadline=deadline, segment_pages=segment_pages))
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
        profile = probe_file(selection, ctx, workspace=workspace, engine=engine,
            budget_rows=budget, previous=previous, deadline=deadline,
            segment_rows=segment_rows, segment_pages=segment_pages,
            segment_blocks=segment_blocks, segment_sheets=segment_sheets)
        if ocr_issue:
            profile.metadata['ocr_setup_issue'] = ocr_issue
        return profile
    finally:
        if engine is not None:
            engine.close()


def _exception_chain(exc):
    seen = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        yield exc
        exc = getattr(exc, '__cause__', None) or getattr(exc, '__context__', None)


def _error_payload(exc):
    """Classify a probe failure without leaking a traceback to the caller."""
    code = getattr(exc, 'code', None)
    code = getattr(code, 'value', code)
    retryable = bool(getattr(exc, 'retryable', False))
    if not code:
        code, retryable = 'probe_failed', isinstance(exc, TimeoutError)
        for nested in _exception_chain(exc):
            if isinstance(nested, ImportError):
                code, retryable = 'dependency_missing', False
                break
            if isinstance(nested, (PermissionError, FileNotFoundError)):
                code, retryable = 'source_unreadable', False
                break
            if isinstance(nested, TimeoutError):
                code, retryable = 'probe_timeout', True
                break
    detail = f'{type(exc).__name__}: {exc}'
    return {'code': str(code), 'detail': detail[:1000], 'retryable': retryable}


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
    try:
        profile=probe(selection,ctx,workspace,request)
    except Exception as exc:  # noqa: BLE001 - structured failure for the workbench
        print(json.dumps({'status':'failed','error':_error_payload(exc)},ensure_ascii=False))
        raise SystemExit(2) from None
    profile.metadata['worker_pid']=os.getpid()
    path=workspace/'.dataagent/results'/f'probe-{uuid4().hex}.json'
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(profile.model_dump_json(indent=2))
    print(json.dumps({'status':'partial' if profile.coverage=='partial' else 'ok',
        'result_path':str(path.relative_to(workspace)),'source_revision':profile.source_revision}))


if __name__=='__main__':main()
