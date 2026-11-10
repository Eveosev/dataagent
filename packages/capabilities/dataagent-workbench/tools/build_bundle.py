#!/usr/bin/env python3
"""Materialize a self-contained local Mint installation closure."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess

HERE=Path(__file__).resolve().parents[1]
CAP=HERE.parent
IGNORE=shutil.ignore_patterns('__pycache__','*.pyc','.venv','node_modules','tests')


def stage(out: Path):
    out=out.resolve()
    if out.exists():
        if not (out/'.dataagent-build').is_file():
            raise ValueError('output exists without a DataAgent build marker')
        shutil.rmtree(out)
    out.mkdir(parents=True)
    (out/'.dataagent-build').write_text('local intake closure\n')
    wb=out/'workbench';wb.mkdir()
    names=[]
    for pkg in ['dataagent-workbench','dataagent-contracts','dataagent-runtime','dataagent-ontology']:
        src=CAP/pkg/'src'/pkg.replace('-','_')
        if src.exists():
            name=pkg.replace('-','_');names.append(f'"src/{name}"')
            shutil.copytree(src,wb/'src'/name,ignore=IGNORE)
    for name in ['mint.toml','.mcp.json']:
        shutil.copy2(HERE/name,wb/name)
    (wb/'pyproject.toml').write_text('''[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
[project]
name = "dataagent-workbench"
version = "0.1.0"
requires-python = ">=3.11,<3.14"
dependencies = ["pydantic>=2.7,<3", "fastapi>=0.115,<1", "uvicorn>=0.30,<1"]
[tool.hatch.build.targets.wheel]
packages = ['''+', '.join(names)+']\n')
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
        for pkg in ['workbench','data-layer']:
            subprocess.run(['uv','lock','--project',str(args.out/pkg)],check=True)
    manifest(args.out.resolve())
    print(args.out.resolve())


if __name__=='__main__': main()
