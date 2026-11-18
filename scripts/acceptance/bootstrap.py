"""Bootstrap phase: install build/local into a fresh Mint project and smoke the CLI."""

import hashlib
import json
import os
import re

from .common import ROOT, run


def package_digests():
    """One digest per package in build/local (M1-01 evidence: the report
    records which package contents the acceptance actually ran against)."""
    manifest = json.loads((ROOT / 'build/local/manifest.json').read_text())
    packages = {}
    for path, digest in manifest['files'].items():
        packages.setdefault(path.split('/', 1)[0], []).append(f'{path}:{digest}')
    return {
        name: 'sha256:' + hashlib.sha256('\n'.join(sorted(files)).encode()).hexdigest()
        for name, files in packages.items()
    }


def installed_dev_paths(packages):
    """V1.8: the installed closure must not embed the development checkout.

    Scan every installed file (and symlink target) under .mint/packages for the
    repository root's realpath; any hit is a failure and is listed by file.
    """
    needle = os.path.realpath(ROOT)
    encoded = needle.encode()
    hits = []
    for path in sorted(packages.rglob('*')):
        if path.is_symlink():
            target = os.readlink(path)
            resolved = os.path.realpath(path)
            if needle in target or needle in resolved:
                hits.append({'file': str(path), 'target': target, 'lines': []})
            continue
        if not path.is_file():
            continue
        data = path.read_bytes()
        if encoded not in data:
            continue
        try:
            lines = [number for number, line in enumerate(data.decode().splitlines(), 1)
                     if needle in line]
        except UnicodeDecodeError:
            lines = []
        hits.append({'file': str(path), 'lines': lines[:5]})
    return needle, hits


def check_installed_paths(packages):
    needle, hits = installed_dev_paths(packages)
    assert not hits, (
        f'installed packages contain the development checkout path {needle} '
        f'({len(hits)} file(s)):\n' + '\n'.join(hit['file'] for hit in hits))
    return {'needle': needle, 'hits': 0}


def prepare(project, mint):
    run([mint, 'init', '--no-preset', '--offline', '-y'], project)
    run([mint, 'add', 'path:' + str(ROOT / 'build/local/preset-intake'), '--offline', '-y'], project)
    cli = list((project / '.mint/packages/dataagent').glob('cli@*/bin/dataagent'))
    assert len(cli) == 1, 'exactly one installed CLI required'
    # The data layer's OCR dependency is configured through the installed
    # setup command from the verified local directory (07 §2.3 T20), not by
    # pre-seeding .dataagent behind its back.
    ocr_root = os.environ.get('OCR_ROOT', '').strip()
    if not ocr_root:
        raise RuntimeError(
            'OCR_ROOT is not set; source p1.env first — the bootstrap phase '
            'configures the verified local OCR directory through dataagent setup')
    run([cli[0], 'setup', '--ocr-root', ocr_root], project)
    # V1.8: the installed workspace must not point back at this checkout.
    installed_paths = check_installed_paths(project / '.mint/packages')
    doctor = run([cli[0], 'doctor'], project)
    # T20: doctor must report the OCR engine and its model version.
    assert re.search(r'^ocr:\s+\S+ \S+ version=\S+', doctor, re.M), doctor
    created = json.loads(run([cli[0], 'workbench', 'intake', '--goal', '本地接入验收',
                              '--source', 'invoice.csv'], project))
    session = created['result']['data']['session_id']
    status = json.loads(run([cli[0], 'workbench', 'status', session], project))
    assert status['result']['data']['job_ref'] == created['result']['data']['job_ref']
    assert status['result']['data']['phase'] == 'queued'
    return {'session_id': session, 'doctor': doctor, 'mint': mint,
            'installed_paths': installed_paths}


def base_report(args, context, project, mint):
    return {'phase': args.phase, 'status': 'passed', 'project': str(project),
            'session_id': context['session_id'],
            'mint': run([mint, '--version'], project).strip(), 'doctor': context['doctor'],
            'installed_paths': context['installed_paths'],
            'package_digests': package_digests(),
            'manifest': json.loads((ROOT / 'build/local/manifest.json').read_text()),
            'not_verified': ['file processing', 'TUI session', 'GUI session']}


def apply(report, project, args, context):
    return None
