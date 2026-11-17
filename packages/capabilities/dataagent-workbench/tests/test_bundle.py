import importlib.util
import json
from pathlib import Path
import tomllib


def test_local_closure_contains_independent_sources_and_no_repository_paths(tmp_path):
    root=Path(__file__).resolve().parents[1]
    script=root/'tools/build_bundle.py'
    assert script.exists(), 'local closure builder must ship with workbench'
    spec=importlib.util.spec_from_file_location('bundle',script)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    out=tmp_path/'closure'
    module.stage(out)
    preset=tomllib.loads((out/'preset-intake/mint.toml').read_text())
    assert preset['package']['kind']=='preset'
    for dependency in preset['dependencies'].values():
        assert (out/'preset-intake'/dependency['path']/'mint.toml').exists()
    project=tomllib.loads((out/'workbench/pyproject.toml').read_text())
    assert 'sources' not in project.get('tool',{}).get('uv',{})
    assert (out/'workbench/src/dataagent_runtime/jobs.py').exists()
    assert not list(out.rglob('*.pyc'))
    assert str(root.resolve()) not in (out/'workbench/pyproject.toml').read_text()
    assert json.loads((out/'manifest.json').read_text())['files']


def test_mcp_manifest_injects_the_connection_manifest_path():
    root=Path(__file__).resolve().parents[1]
    manifest=json.loads((root/'.mcp.json').read_text())
    env=manifest['mcpServers']['dataagent-workbench']['env']
    assert env['DATAAGENT_SOURCE_CONNECTIONS']=='.dataagent/source-connections.json'
