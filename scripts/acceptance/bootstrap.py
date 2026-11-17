"""Bootstrap phase: install build/local into a fresh Mint project and smoke the CLI."""

import json

from .common import ROOT, run


def prepare(project, mint):
    run([mint, 'init', '--no-preset', '--offline', '-y'], project)
    run([mint, 'add', 'path:' + str(ROOT / 'build/local/preset-intake'), '--offline', '-y'], project)
    cli = list((project / '.mint/packages/dataagent').glob('cli@*/bin/dataagent'))
    assert len(cli) == 1, 'exactly one installed CLI required'
    run([cli[0], 'setup'], project)
    doctor = run([cli[0], 'doctor'], project)
    created = json.loads(run([cli[0], 'workbench', 'intake', '--goal', '本地接入验收',
                              '--source', 'invoice.csv'], project))
    session = created['result']['data']['session_id']
    status = json.loads(run([cli[0], 'workbench', 'status', session], project))
    assert status['result']['data']['job_ref'] == created['result']['data']['job_ref']
    assert status['result']['data']['phase'] == 'queued'
    return {'session_id': session, 'doctor': doctor, 'mint': mint}


def base_report(args, context, project, mint):
    return {'phase': args.phase, 'status': 'passed', 'project': str(project),
            'session_id': context['session_id'],
            'mint': run([mint, '--version'], project).strip(), 'doctor': context['doctor'],
            'manifest': json.loads((ROOT / 'build/local/manifest.json').read_text()),
            'not_verified': ['file processing', 'TUI session', 'GUI session']}


def apply(report, project, args, context):
    return None
