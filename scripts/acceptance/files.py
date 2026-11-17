"""Files phase: scanned PDF through the installed workbench."""

import shutil

from .common import ROOT, call_workbench, remove_not_verified


def verify_scan(project, ocr_root):
    fixture = ROOT/'packages/capabilities/dataagent-scenarios/fixtures/intake/scan.pdf'
    shutil.copy2(fixture, project/'scan.pdf')
    shutil.copytree(ocr_root, project/'.dataagent/ocr', symlinks=True)
    args = {'session_id': call_workbench(project, 'intake_start', {
        'goal': '核对扫描发票的编号、金额和币种',
        'sources': [{'source_id': 'scan', 'kind': 'file', 'locator_ref': 'scan.pdf'}],
    })['session_id']}
    observed = call_workbench(project, 'intake_advance', args)
    source, = observed['sources']
    page, = source['document_excerpts']
    assert source['coverage'] == 'full'
    fields = {'number': 'INV-003', 'amount': '1260.00', 'currency': 'CNY'}
    assert all(value in page['text'] for value in fields.values())
    derived = call_workbench(project, 'intake_extract', {
        **args, 'expected_revision': observed['expected_revision'], 'source_id': 'scan',
        'fields': [{'row': page['rows'][0], 'page': page['page'], 'name': name, 'quote': quote}
                   for name, quote in fields.items()],
    })
    proposal = {**derived['proposal_template'], 'bindings': {
        name: {'source_field': name, 'transform': 'decimal' if name == 'amount' else 'identity'}
        for name in fields
    }}
    preview = call_workbench(project, 'intake_propose', {
        **args, 'expected_revision': derived['expected_revision'], 'proposal': proposal,
    })
    assert preview['instance_count'] == 1 and preview['issues'] == []
    call_workbench(project, 'mapping_apply', {
        **args, 'expected_revision': preview['session_revision'],
        'decision': {'preview_ref': preview['preview_ref'], 'target_scope': 'mapping'},
    })
    status = call_workbench(project, 'intake_status', args)
    assert status['phase'] == 'saved' and status['selected_versions']['release']
    replay = call_workbench(project, 'intake_propose', {
        **args, 'expected_revision': status['revision'], 'proposal': proposal,
    }, error=True)
    assert 'saved intake is closed' in replay['detail']
    assert call_workbench(project, 'intake_status', args) == status
    return {'session': status, 'observed_text': page['text'], 'values': fields,
            'source_revision': source['source_revision'], 'late_proposal': replay}


def apply(report, project, args, context):
    report['scan'] = verify_scan(project, args.ocr_root)
    remove_not_verified(report, 'file processing')
