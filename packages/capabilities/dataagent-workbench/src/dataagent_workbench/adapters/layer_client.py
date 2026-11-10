"""Call the public probe port in its own dependency environment."""
import json
import os
from pathlib import Path
import subprocess
from dataagent_contracts.intake import SourceProfile


class LayerClient:
    def __init__(self, package_dir):
        self.package_dir=Path(package_dir).resolve()

    def probe(self, selection, ctx, workspace):
        python=self.package_dir/'.venv/bin/python'
        if not python.is_file():raise ValueError('data layer environment missing; run dataagent setup')
        workspace=Path(workspace).resolve()
        env={k:v for k,v in os.environ.items() if k in {'PATH','HOME','TMPDIR','LANG','TZ'} or k.startswith('LC_')}
        result=subprocess.run([str(python),'-m','dataagent_data.observation.cli','--workspace',str(workspace)],
            input=json.dumps({'source':selection.model_dump(mode='json'),'context':ctx.model_dump(mode='json')}),
            capture_output=True,text=True,timeout=120,env=env,cwd=workspace)
        if result.returncode:
            raise ValueError('data layer probe failed: '+result.stderr[-1500:])
        try:
            summary=json.loads(result.stdout)
            path=(workspace/summary['result_path']).resolve()
            if not path.is_relative_to(workspace/'.dataagent/results'):
                raise ValueError('invalid result location')
            return SourceProfile.model_validate_json(path.read_text())
        except (KeyError,OSError) as exc:
            raise ValueError('data layer returned no readable result') from exc


def installed_data_package(workspace):
    packages=list((Path(workspace)/'.mint/packages/dataagent').glob('data-layer@*'))
    if len(packages)==1:return packages[0]
    raise ValueError('exactly one installed data layer is required')
