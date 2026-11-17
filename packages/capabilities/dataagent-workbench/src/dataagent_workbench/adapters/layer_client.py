"""Call the public probe port in its own dependency environment."""
import json
import os
from pathlib import Path
import subprocess
from dataagent_contracts.intake import SourceProfile
from .source_connections import SourceConnections, validate_forwarded

_PROBE_ENV = {'PATH', 'HOME', 'TMPDIR', 'LANG', 'TZ'}
_SEGMENT_ENV = {
    'budget_rows': ('DATAAGENT_PROBE_ROW_BUDGET', 10000),
    'segment_rows': ('DATAAGENT_PROBE_SEGMENT_ROWS', 100000),
    'segment_pages': ('DATAAGENT_PROBE_SEGMENT_PAGES', 1000),
    'segment_blocks': ('DATAAGENT_PROBE_SEGMENT_BLOCKS', 100000),
    'segment_sheets': ('DATAAGENT_PROBE_SEGMENT_SHEETS', 1000),
}


class DataLayerProbeError(ValueError):
    """A coded probe failure that the intake coordinator can classify."""

    def __init__(self, code, detail, *, retryable=False):
        super().__init__(detail)
        self.code = str(code or 'probe_failed')
        self.detail = str(detail)
        self.retryable = bool(retryable)


def _segment_options():
    options = {}
    for name, (variable, maximum) in _SEGMENT_ENV.items():
        raw = os.environ.get(variable)
        if raw is None:
            continue
        try:
            value = int(raw)
        except (TypeError, ValueError):
            raise ValueError(f'{variable} must be an integer between 1 and {maximum}') from None
        if not 1 <= value <= maximum:
            raise ValueError(f'{variable} must be an integer between 1 and {maximum}')
        options[name] = value
    return options


def _clean_child_environment(allowed):
    """Run in the forked probe child before exec; do not read values here."""

    for name in list(os.environ):
        if name not in allowed:
            os.environ.pop(name, None)


class LayerClient:
    def __init__(self, package_dir):
        self.package_dir=Path(package_dir).resolve()
        self.connections=SourceConnections()

    def _call(self,selection,ctx,workspace,**operation):
        python=self.package_dir/'.venv/bin/python'
        if not python.is_file():raise ValueError('data layer environment missing; run dataagent setup')
        if 'credentials' in operation:
            raise ValueError('plaintext credentials must not cross the process boundary')
        validate_forwarded(selection.options, 'source.options')
        validate_forwarded(selection.requested_scope, 'source.scope')
        validate_forwarded(operation.get('credential_options') or {}, 'credential_options')
        workspace=Path(workspace).resolve()
        # The probe child gets a minimal environment. For ``env:`` references
        # it starts from the inherited environment and drops everything except
        # the named variables in the forked child before exec; the workbench
        # never reads or copies a credential value.
        refs = operation.get('credential_refs')
        if not isinstance(refs, dict):
            refs = {}
        env_names = {ref[4:] for ref in refs.values()
                     if isinstance(ref, str) and ref.startswith('env:')}
        preexec_fn = None
        if env_names:
            env = None
            allowed = _PROBE_ENV | env_names
            preexec_fn = lambda: _clean_child_environment(allowed)
        else:
            env = {name: os.environ[name] for name in _PROBE_ENV if name in os.environ}
        # The child receives logical names only; it resolves them inside its own process.
        payload={'source':selection.model_dump(mode='json'),'context':ctx.model_dump(mode='json'),**operation}
        budget = operation.get('budget_seconds')
        timeout = 120.0
        if isinstance(budget, (int, float)) and not isinstance(budget, bool) and budget > 0:
            timeout = min(120.0, max(5.0, float(budget) + 2.0))
        try:
            result=subprocess.run([str(python),'-m','dataagent_data.observation.cli','--workspace',str(workspace)],
                input=json.dumps(payload),
                capture_output=True,text=True,timeout=timeout,env=env,cwd=workspace,
                preexec_fn=preexec_fn)
        except subprocess.TimeoutExpired as exc:
            raise DataLayerProbeError('probe_timeout',
                'data layer probe timed out; completed source observations remain available',
                retryable=True) from exc
        if result.returncode:
            error = {}
            try:
                response = json.loads(result.stdout)
                if isinstance(response, dict) and isinstance(response.get('error'), dict):
                    error = response['error']
            except (TypeError, ValueError):
                pass
            code = error.get('code') or 'probe_failed'
            retryable = bool(error.get('retryable'))
            if selection.kind in {'postgres','rest'}:
                # Remote diagnostics may name a connection or read scope; keep
                # the agent-visible text generic while preserving the code.
                raise DataLayerProbeError(code,
                    'remote source probe failed; check the configured connection and read scope',
                    retryable=retryable)
            detail = error.get('detail') or result.stderr[-1500:]
            raise DataLayerProbeError(code, 'data layer probe failed: '+str(detail)[-1500:],
                retryable=retryable)
        return json.loads(result.stdout)

    def probe(self, selection, ctx, workspace, *, previous=None, budget_seconds=None):
        workspace=Path(workspace).resolve()
        try:
            resolved, options=self.connections.resolve(selection)
            operation=dict(options)
            # The coordinator owns the resume checkpoint and budget; a source
            # manifest may configure what to read, never how far this call runs.
            for key in ('previous','budget_seconds',*_SEGMENT_ENV):
                operation.pop(key,None)
            operation.update(_segment_options())
            if previous is not None:
                operation['previous'] = previous.model_dump(mode='json')
            if budget_seconds is not None:
                operation['budget_seconds'] = max(0.05, float(budget_seconds))
            summary=self._call(resolved,ctx,workspace,**operation)
            path=(workspace/summary['result_path']).resolve()
            if not path.is_relative_to(workspace/'.dataagent/results'):
                raise ValueError('invalid result location')
            return SourceProfile.model_validate_json(path.read_text())
        except (KeyError,OSError) as exc:
            raise ValueError('data layer returned no readable result') from exc

    def render_page(self,profile,page,ctx,workspace):
        from dataagent_contracts.intake import SourceSelection
        source=SourceSelection(source_id=profile.source_id,kind='file',locator_ref=profile.metadata['snapshot_ref'])
        result=self._call(source,ctx,workspace,operation='render_page',source_revision=profile.source_revision,page=page)
        path=(Path(workspace)/result['result_path']).resolve()
        if not path.is_relative_to((Path(workspace)/'.dataagent/content').resolve()):
            raise PermissionError('invalid rendered page location')
        return path


def installed_data_package(workspace):
    packages=list((Path(workspace)/'.mint/packages/dataagent').glob('data-layer@*'))
    if len(packages)==1:return packages[0]
    raise ValueError('exactly one installed data layer is required')
