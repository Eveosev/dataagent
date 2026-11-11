"""Call the public probe port in its own dependency environment."""
import json
import os
from pathlib import Path
import subprocess
from dataagent_contracts.intake import SourceProfile
from .source_connections import SourceConnections


class LayerClient:
    def __init__(self, package_dir):
        self.package_dir=Path(package_dir).resolve()
        self.connections=SourceConnections()

    def _call(self,selection,ctx,workspace,**operation):
        python=self.package_dir/'.venv/bin/python'
        if not python.is_file():raise ValueError('data layer environment missing; run dataagent setup')
        workspace=Path(workspace).resolve()
        env={k:v for k,v in os.environ.items() if k in {'PATH','HOME','TMPDIR','LANG','TZ'} or k.startswith('LC_')}
        try:
            result=subprocess.run([str(python),'-m','dataagent_data.observation.cli','--workspace',str(workspace)],
                input=json.dumps({'source':selection.model_dump(mode='json'),'context':ctx.model_dump(mode='json'),**operation}),
                capture_output=True,text=True,timeout=120,env=env,cwd=workspace)
        except subprocess.TimeoutExpired as exc:
            raise ValueError('data layer probe timed out; completed source observations remain available') from exc
        if result.returncode:
            if selection.kind in {'postgres','rest'}:
                raise ValueError('remote source probe failed; check the configured connection and read scope')
            raise ValueError('data layer probe failed: '+result.stderr[-1500:])
        return json.loads(result.stdout)

    def probe(self, selection, ctx, workspace, *, previous=None):
        workspace=Path(workspace).resolve()
        try:
            resolved, options=self.connections.resolve(selection)
            if previous is not None:
                options['previous'] = previous.model_dump(mode='json')
            summary=self._call(resolved,ctx,workspace,**options)
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
