#!/usr/bin/env python3
"""Materialize a self-contained local Mint installation closure."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tomllib

HERE=Path(__file__).resolve().parents[1]
CAP=HERE.parent
IGNORE=shutil.ignore_patterns('__pycache__','*.pyc','.venv','node_modules','tests')


def stage_runtime(out, package, vendored):
    source = CAP / package
    out.mkdir()
    names = []
    dependencies = set()
    for project_path in [source, *(CAP / name for name in vendored)]:
        module = project_path.name.replace('-', '_')
        names.append('src/' + module)
        shutil.copytree(project_path / 'src' / module, out / 'src' / module, ignore=IGNORE)
        project = tomllib.loads((project_path / 'pyproject.toml').read_text())['project']
        dependencies.update(dep for dep in project.get('dependencies', []) if not dep.startswith('dataagent-'))
    for name in ['mint.toml', '.mcp.json']:
        shutil.copy2(source / name, out / name)
    (out / 'pyproject.toml').write_text(f'''[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
[project]
name = "{package}"
version = "0.1.0"
requires-python = ">=3.11,<3.14"
dependencies = {json.dumps(sorted(dependencies))}
[tool.hatch.build.targets.wheel]
packages = {json.dumps(names)}
''')


def stage(out: Path):
    out=out.resolve()
    if out.exists():
        if not (out/'.dataagent-build').is_file():
            raise ValueError('output exists without a DataAgent build marker')
        shutil.rmtree(out)
    out.mkdir(parents=True)
    (out/'.dataagent-build').write_text('local intake closure\n')
    wb=out/'workbench'
    shared=['dataagent-contracts','dataagent-runtime']
    stage_runtime(wb,'dataagent-workbench',[*shared,'dataagent-ontology'])
    stage_runtime(out/'operations','dataagent-operations',shared)
    shutil.copytree(CAP/'dataagent-intake/skills',wb/'skills',ignore=IGNORE)
    data_script=CAP/'dataagent-data/scripts/build_bundle.py'
    spec=importlib.util.spec_from_file_location('data_bundle',data_script)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    mod.stage(out/'data-layer')
    ocr=CAP/'dataagent-ocr/src/dataagent_ocr'
    if ocr.exists():
        shutil.copytree(ocr,out/'data-layer/src/dataagent_ocr',ignore=IGNORE)
        project=out/'data-layer/pyproject.toml'
        project.write_text(project.read_text().replace('"src/dataagent_data",','"src/dataagent_data", "src/dataagent_ocr",'))
    shutil.copytree(CAP/'dataagent-cli',out/'cli',ignore=IGNORE)
    shutil.copytree(CAP/'dataagent-intake',out/'preset-intake',ignore=IGNORE)
    manifest(out)


def manifest(out):
    files={str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(out.rglob('*')) if p.is_file() and p.name!='manifest.json'}
    (out/'manifest.json').write_text(json.dumps({'files':files},sort_keys=True,indent=2))


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=Path('build/local'))
    p.add_argument('--no-lock',action='store_true');args=p.parse_args()
    stage(args.out)
    if not args.no_lock:
        for pkg in ['workbench','data-layer','operations']:
            subprocess.run(['uv','lock','--project',str(args.out/pkg)],check=True)
    manifest(args.out.resolve())
    print(args.out.resolve())


if __name__=='__main__': main()
