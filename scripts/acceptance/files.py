"""Files phase: eight sample classes compared with hand-written expectations,
plus the retained fixture assertions (invoice.pdf, mixed.pdf, invoices.xlsx,
the scanned-PDF intake loop and the runtime-generated policy docx).

The p1-files expectations under fixtures/intake/p1-files/expected/ were written
independently against the original files; this module only compares probe
output against them (coverage, completed/gap partitions, record counts, field
values and anchors) and never generates or rewrites them. Tolerances follow
the rules the expectation files state themselves (判断依据 / soft markers):
Excel dates may carry a midnight time, the text PDF may expose 11 or 12
records, low-confidence OCR values are soft-checked, and gap reasons are
compared by the accepted code categories.
"""

import json
import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
import time
from pathlib import Path

from .common import ROOT, call_workbench, remove_not_verified, run


INTAKE = ROOT/'packages/capabilities/dataagent-scenarios/fixtures/intake'
P1_FILES = INTAKE/'p1-files'
# The comparison order is the sample list of p1-files/README.md.
SAMPLE_ORDER = ['invoices.csv', 'invoices.tsv', 'invoices-regions.xlsx', 'invoices.json',
                'invoices.jsonl', 'invoice-lines.pdf', 'mixed-pages.pdf', 'scan.pdf']
# Fixed expectations for the runtime-generated policy docx (never taken from
# the probe output). T26 anchors are 1-based: paragraph:<n>,
# table:<t>/row:<r>/col:<c>.
DOCX_TITLE = '差旅费用报销规则'
DOCX_BODY = '第一条 出差住宿标准按城市等级执行。'
DOCX_TABLE = [['城市', '标准', '币种'], ['一线', '600', 'CNY'], ['其他', '400', 'CNY']]


def installed_cli(project):
    cli, = (project/'.mint/packages/dataagent').glob('cli@*/bin/dataagent')
    return cli


class Diffs:
    """Per-item differences (sample, check, expected, actual) for one run."""

    def __init__(self):
        self.items = []

    def add(self, sample, check, expected, actual):
        self.items.append({'sample': sample, 'check': check,
                           'expected': expected, 'actual': actual})

    def __bool__(self):
        return bool(self.items)


def _upload(project, name, source_id, fixture):
    """Upload one sample through the installed workbench; return the session
    args, the agent-visible request and the full data-layer probe result."""
    shutil.copy2(fixture, project/name)
    results = project/'.dataagent/results'
    before = set(results.glob('probe-*.json'))
    args = {'session_id': call_workbench(project, 'intake_start', {
        'goal': '核对样本文件内容',
        'sources': [{'source_id': source_id, 'kind': 'file', 'locator_ref': name}],
    })['session_id']}
    request = call_workbench(project, 'intake_advance', args)
    changed = set(results.glob('probe-*.json')) - before
    if not changed:
        raise RuntimeError(f'{name}: intake_advance produced no probe result')
    # A segmented probe writes one result per segment; the newest file holds
    # the accumulated profile.
    newest = max(changed, key=lambda path: path.stat().st_mtime_ns)
    return args, request, json.loads(newest.read_text())


def _anchor(profile, index, field):
    found = profile['anchors'].get(f'{index}.{field}')
    return found[0]['selector'] if found else None


def _record_set_anchor(record_set, index, field):
    found = record_set.get('anchors', {}).get(f'{index}.{field}')
    return found[0]['selector'] if found else None


def _value_equal(expected, actual):
    """Field comparison with the tolerances the expectation files state:
    numbers compare numerically, Excel dates may carry a midnight time
    (regions 判断依据 4), everything else is an exact comparison."""
    if isinstance(expected, bool) or isinstance(actual, bool):
        return expected is actual
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return expected == actual
    if expected == actual:
        return True
    return isinstance(expected, str) and isinstance(actual, str) \
        and actual == expected + 'T00:00:00'


def _ocr_contains(text, value):
    """Whitespace-insensitive containment for OCR pages: the expectations were
    written against the readable page while RapidOCR drops or adds spaces."""
    return ''.join(value.split()) in ''.join(text.split())


def _check_partitions(diffs, sample, spec, profile):
    if profile['coverage'] != spec['coverage']:
        diffs.add(sample, 'coverage', spec['coverage'], profile['coverage'])
    if profile['total_partitions'] != spec['total_partitions']:
        diffs.add(sample, 'total_partitions', spec['total_partitions'],
                  profile['total_partitions'])
    if profile['completed_partitions'] != spec['completed_partitions']:
        diffs.add(sample, 'completed_partitions', spec['completed_partitions'],
                  profile['completed_partitions'])
    expected_gaps = {gap['partition']: gap.get('accepted_codes')
                     for gap in spec.get('gaps', [])}
    actual_gaps = {gap['partition']: gap['code'] for gap in profile['gaps']}
    if set(actual_gaps) != set(expected_gaps):
        diffs.add(sample, 'gap partitions', sorted(map(str, expected_gaps)),
                  sorted(map(str, actual_gaps)))
    for partition, codes in expected_gaps.items():
        if partition in actual_gaps and codes and actual_gaps[partition] not in codes:
            diffs.add(sample, f'gap {partition} code', codes, actual_gaps[partition])


def _check_anchor_coverage(diffs, sample, profile):
    """PRD V1.1: every non-empty field of every record carries an anchor."""
    for index, record in enumerate(profile['records']):
        for field, value in record.items():
            if value is not None and _anchor(profile, index, field) is None:
                diffs.add(sample, f'record {index} field {field} anchor',
                          'anchor present', None)


def _compare_flat(diffs, expected, profile):
    """CSV, TSV, JSON and JSONL: values plus row/line/pointer anchors."""
    sample = expected['sample']
    _check_partitions(diffs, sample, expected, profile)
    if {f.lstrip('/') for f in expected['fields']} != {f.lstrip('/') for f in profile['fields']}:
        diffs.add(sample, 'fields', expected['fields'], profile['fields'])
    if len(profile['records']) != expected['record_count']:
        diffs.add(sample, 'record_count', expected['record_count'],
                  len(profile['records']))
    if 'delimiter' in expected:
        delimiter = expected['delimiter'].replace('\\t', '\t')
        if profile['metadata'].get('delimiter') != delimiter:
            diffs.add(sample, 'delimiter', delimiter,
                      profile['metadata'].get('delimiter'))
    if expected['kind'] in {'csv', 'tsv'} and profile['metadata'].get('quarantined_rows'):
        diffs.add(sample, 'quarantined_rows', [],
                  profile['metadata']['quarantined_rows'])
    for index, expected_record in enumerate(expected['records']):
        actual = profile['records'][index] if index < len(profile['records']) else {}
        for field, value in expected_record['fields'].items():
            if not _value_equal(value, actual.get(field)):
                diffs.add(sample, f'record {index} field {field}', value,
                          actual.get(field))
        for field, anchor in expected_record['anchors'].items():
            selector = _anchor(profile, index, field)
            if selector is None:
                diffs.add(sample, f'record {index} anchor {field}', anchor, None)
                continue
            if 'row' in anchor:
                ok = (selector['kind'] == 'record_key'
                      and selector['keys'].get('row') == anchor['row']
                      and selector['field'] == field)
            elif 'line' in anchor:
                ok = (selector['kind'] == 'record_key'
                      and selector['keys'].get('line') == anchor['line']
                      and selector['field'].lstrip('/') == anchor['pointer'].lstrip('/'))
            else:
                ok = (selector['kind'] == 'json_pointer'
                      and selector['pointer'] == anchor['pointer'])
            if not ok:
                diffs.add(sample, f'record {index} anchor {field}', anchor,
                          selector)
    _check_anchor_coverage(diffs, sample, profile)


def _compare_xlsx(diffs, expected, profile):
    """Merged headers and multiple regions: compare values per expected
    anchor cell (columns are identified by header_cells, not by the header
    spelling — regions 判断依据 2)."""
    sample = expected['sample']
    _check_partitions(diffs, sample, expected, profile)
    anchored = {}
    for key, found in profile['anchors'].items():
        selector = found[0]['selector']
        if selector['kind'] == 'excel_cell':
            anchored[(selector['sheet'], selector['range'])] = key
    data_rows = {row for region in expected['layout']['regions']
                 for row in region['data_rows']}
    for table in expected['tables']:
        for record in table['records']:
            for field, anchor in record['anchors'].items():
                key = anchored.get((anchor['sheet'], anchor['cell']))
                if key is None:
                    diffs.add(sample, f'{anchor["cell"]} value ({field})',
                              record['fields'][field],
                              'no record anchored at this cell')
                    continue
                index, anchored_field = key.split('.', 1)
                value = profile['records'][int(index)].get(anchored_field)
                if not _value_equal(record['fields'][field], value):
                    diffs.add(sample, f'{anchor["cell"]} value ({field})',
                              record['fields'][field], value)
    violations = {}
    for sheet, cell in anchored:
        row = int(''.join(ch for ch in cell if ch.isdigit()))
        if row not in data_rows:
            violations.setdefault(row, []).append(f'{sheet}!{cell}')
    for row, cells in sorted(violations.items()):
        diffs.add(sample,
                  f'row {row} must not appear as records (must_not_appear_as_records)',
                  'no record anchored on this row',
                  'records anchored at ' + ', '.join(sorted(cells)))
    if len(profile['records']) != expected['record_count']:
        diffs.add(sample, 'record_count', expected['record_count'],
                  len(profile['records']))
    _check_anchor_coverage(diffs, sample, profile)


def _span_text(pages, selector):
    text = pages.get(selector['page'], {}).get('text', '')
    return text[selector['char_start']:selector['char_end']]


def _bbox_texts(project, name, boxes):
    """Text inside pdf_bbox anchors, extracted with the installed data layer
    (pdfplumber); used to verify that a bbox anchor points at text that
    contains its value."""
    if not boxes:
        return {}
    python, = (project/'.mint/packages/dataagent').glob('data-layer@*/.venv/bin/python')
    code = ('import json,sys,pdfplumber\n'
            'data=json.loads(sys.stdin.read())\n'
            'out={}\n'
            'with pdfplumber.open(data["file"]) as pdf:\n'
            '    for page,boxes in data["boxes"].items():\n'
            '        sheet=pdf.pages[int(page)-1]\n'
            '        out[page]=[sheet.crop(box).extract_text() or "" for box in boxes]\n'
            'print(json.dumps(out))\n')
    result = subprocess.run([str(python), '-c', code], cwd=project,
                            input=json.dumps({'file': name,
                                              'boxes': {str(page): bboxes
                                                        for page, bboxes in boxes.items()}}),
                            capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f'bbox text extraction failed: {result.stderr[-2000:]}')
    extracted = json.loads(result.stdout)
    out = {}
    for page, bboxes in boxes.items():
        for bbox, text in zip(bboxes, extracted[str(page)]):
            out[(page, tuple(bbox))] = text
    return out


def _check_anchor_value(diffs, sample, selector, value, where, pages, cell_texts):
    """An anchor must point at original text containing the value (both span
    and bbox selectors; text pages compare exactly, OCR pages ignore
    whitespace)."""
    if selector['kind'] == 'pdf_text_span':
        text = _span_text(pages, selector)
    elif selector['kind'] == 'pdf_bbox':
        text = cell_texts.get((selector['page'], tuple(selector['bbox'])))
    else:
        return
    if text is None or value not in text:
        diffs.add(sample, f'{where} anchor text', f'contains {value!r}', text)


def _compare_text_pdf(diffs, expected, profile, cell_texts):
    """invoice-lines.pdf: cross-page table (one logical table, repeated header
    is not a record) plus document-level key: value fields. Records may be
    11 or 12 (判断依据 2), so rows are matched by field and anchor page."""
    sample = expected['sample']
    _check_partitions(diffs, sample, expected, profile)
    pages = {page['page']: page for page in profile['metadata']['pages']}
    for page, method in expected['page_types'].items():
        if pages.get(int(page), {}).get('method') != method:
            diffs.add(sample, f'page {page} type', method,
                      pages.get(int(page), {}).get('method'))
    document = expected['document_fields']
    matched = set()
    for field, value in document['fields'].items():
        anchor = document['anchors'][field]
        index = next((i for i, r in enumerate(profile['records']) if field in r), None)
        if index is None:
            diffs.add(sample, f'document field {field}', value, 'missing')
            continue
        matched.add(index)
        if not _value_equal(value, profile['records'][index][field]):
            diffs.add(sample, f'document field {field} value', value,
                      profile['records'][index][field])
        selector = _anchor(profile, index, field)
        if selector is None or selector.get('page') != anchor['page']:
            diffs.add(sample, f'document field {field} anchor page',
                      anchor['page'], selector and selector.get('page'))
        elif selector['kind'] == 'pdf_text_span':
            span = _span_text(pages, selector)
            if str(value) not in span:
                diffs.add(sample, f'document field {field} anchor text',
                          f'contains {value!r}', span)
        else:
            _check_anchor_value(diffs, sample, selector, str(value),
                                f'document field {field}', pages, cell_texts)
    for row in expected['logical_table']['records']:
        index = next((i for i, r in enumerate(profile['records'])
                      if str(r.get('line')) == row['fields']['line']), None)
        if index is None:
            diffs.add(sample, f'table row {row["fields"]["line"]}',
                      row['fields'], 'missing')
            continue
        matched.add(index)
        actual = profile['records'][index]
        for field, value in row['fields'].items():
            if not _value_equal(value, actual.get(field)):
                diffs.add(sample, f'row {row["fields"]["line"]} field {field}',
                          value, actual.get(field))
            selector = _anchor(profile, index, field)
            if selector is None or selector.get('page') != row['page']:
                diffs.add(sample,
                          f'row {row["fields"]["line"]} field {field} anchor page',
                          row['page'], selector and selector.get('page'))
            elif selector is not None:
                _check_anchor_value(diffs, sample, selector, value,
                                    f'row {row["fields"]["line"]} field {field}',
                                    pages, cell_texts)
    count = expected['record_count']
    if len(profile['records']) not in {count, count + 1}:
        diffs.add(sample, 'record_count',
                  f'{count} or {count + 1} (判断依据 2)', len(profile['records']))
    for index, record in enumerate(profile['records']):
        if index in matched:
            continue
        if any(field not in document['fields'] for field in record):
            diffs.add(sample, 'unexpected record (must_not_appear_as_records)',
                      'only document fields', record)
    _check_anchor_coverage(diffs, sample, profile)


def _compare_mixed_pdf(diffs, expected, profile):
    """mixed-pages.pdf: text page, failing page (gap) and low-confidence scan
    page, compared against the with_ocr branch (acceptance runs --ocr-root).
    The low-confidence page must be completed, its values are soft-checked,
    and it must carry the intake.low_ocr_confidence issue."""
    sample = expected['sample']
    # The with_ocr branch overrides coverage; the page count stays on the root.
    spec = {**expected, **expected['with_ocr']}
    _check_partitions(diffs, sample, spec, profile)
    pages = {page['page']: page for page in profile['metadata']['pages']}
    for key, found in profile['anchors'].items():
        for anchor in found:
            if anchor['selector'].get('page') == 2:
                diffs.add(sample, 'page 2 must not have records or anchors',
                          'none', key)
    first = expected['records'][0]
    index = next((i for i, r in enumerate(profile['records'])
                  if r.get('invoice_number') == first['fields']['invoice_number']), None)
    if index is None:
        diffs.add(sample, 'page 1 record', first['fields'], 'missing')
    else:
        for field, value in first['fields'].items():
            if not _value_equal(value, profile['records'][index].get(field)):
                diffs.add(sample, f'page 1 record field {field}', value,
                          profile['records'][index].get(field))
            selector = _anchor(profile, index, field)
            if selector is None or selector.get('page') != 1:
                diffs.add(sample, f'page 1 record field {field} anchor page',
                          1, selector and selector.get('page'))
            elif selector is not None:
                _check_anchor_value(diffs, sample, selector, value,
                                    f'page 1 record field {field}', pages, {})
    page_three = [i for i, r in enumerate(profile['records'])
                  if any(anchor['selector'].get('page') == 3
                         for key, found in profile['anchors'].items()
                         if key.startswith(f'{i}.') for anchor in found)]
    if not page_three:
        diffs.add(sample, 'page 3 record', 'values with page 3 anchors',
                  'no record anchored on page 3')
    for index in page_three:
        for field, value in profile['records'][index].items():
            selector = _anchor(profile, index, field)
            if value is not None and (selector is None or selector.get('page') != 3):
                diffs.add(sample, f'page 3 record field {field} anchor page', 3,
                          selector and selector.get('page'))
    if len(profile['records']) != expected['record_count_with_ocr']:
        diffs.add(sample, 'record_count', expected['record_count_with_ocr'],
                  len(profile['records']))
    for issue in spec.get('issues_expected', []):
        if not any(i.get('code') == issue['code'] and i.get('page') == issue['page']
                   for i in profile['issues']):
            diffs.add(sample, f'issue {issue["code"]} page {issue["page"]}',
                      'present', [i.get('code') for i in profile['issues']])
    _check_anchor_coverage(diffs, sample, profile)


def _compare_scan_pdf(diffs, expected, profile):
    """scan.pdf: a single scanned page whose OCR values appear in the page
    text and whose record fields carry page 1 anchors (facts only; the
    semantic values are covered by the retained intake loop below)."""
    sample = expected['sample']
    # The with_ocr branch overrides coverage; the page count stays on the root.
    spec = {**expected, **expected['with_ocr']}
    _check_partitions(diffs, sample, spec, profile)
    pages = {page['page']: page for page in profile['metadata']['pages']}
    for page, method in spec['page_types'].items():
        if pages.get(int(page), {}).get('method') != method:
            diffs.add(sample, f'page {page} type', method,
                      pages.get(int(page), {}).get('method'))
    for fact in expected['facts']:
        text = pages.get(1, {}).get('text', '')
        if not _ocr_contains(text, fact['value']):
            diffs.add(sample, f'fact {fact["label"]} in page text',
                      fact['value'], text)
    if len(profile['records']) != expected['record_count']:
        diffs.add(sample, 'record_count', expected['record_count'],
                  len(profile['records']))
    for index, record in enumerate(profile['records']):
        for field in record:
            selector = _anchor(profile, index, field)
            if selector is None or selector.get('page') != 1:
                diffs.add(sample, f'record {index} field {field} anchor page',
                          1, selector and selector.get('page'))
    _check_anchor_coverage(diffs, sample, profile)


def _collect_bbox_texts(project, name, profile):
    boxes = {}
    for found in profile['anchors'].values():
        for anchor in found:
            selector = anchor['selector']
            if selector['kind'] == 'pdf_bbox':
                boxes.setdefault(selector['page'], []).append(selector['bbox'])
    return _bbox_texts(project, name, boxes)


def _compare_sample(diffs, project, name):
    expected = json.loads((P1_FILES/'expected'/f'{name}.json').read_text())
    args, request, profile = _upload(project, name, name, P1_FILES/'samples'/name)
    if profile['source_revision'] != 'sha256:' + expected['sha256']:
        raise RuntimeError(f'{name}: probe revision does not match the expected sample')
    if isinstance(request, dict) and request.get('sources'):
        observed = request['sources'][0]
        spec = expected.get('with_ocr') or expected
        if observed.get('coverage') != spec['coverage']:
            diffs.add(name, 'observed coverage (inference request)',
                      spec['coverage'], observed.get('coverage'))
    if expected['kind'] in {'csv', 'tsv', 'json', 'jsonl'}:
        _compare_flat(diffs, expected, profile)
    elif expected['kind'] == 'xlsx':
        _compare_xlsx(diffs, expected, profile)
    elif name == 'invoice-lines.pdf':
        _compare_text_pdf(diffs, expected, profile,
                          _collect_bbox_texts(project, name, profile))
    elif name == 'mixed-pages.pdf':
        _compare_mixed_pdf(diffs, expected, profile)
    else:
        _compare_scan_pdf(diffs, expected, profile)
    return {'source_revision': profile['source_revision'],
            'coverage': profile['coverage'],
            'completed_partitions': profile['completed_partitions'],
            'gaps': [(gap['partition'], gap['code']) for gap in profile['gaps']],
            'records': len(profile['records']),
            'anchors': len(profile['anchors'])}


def verify_scan(project, ocr_root):
    fixture = ROOT/'packages/capabilities/dataagent-scenarios/fixtures/intake/scan.pdf'
    shutil.copy2(fixture, project/'scan.pdf')
    # The verified OCR directory is configured through the installed setup
    # command (07 §2.3 T20), which validates the pin; the workbench is not
    # handed a pre-seeded .dataagent/ocr.
    run([installed_cli(project), 'setup', '--ocr-root', str(ocr_root)], project)
    args = {'session_id': call_workbench(project, 'intake_start', {
        'goal': '核对扫描发票的编号、金额和币种',
        'sources': [{'source_id': 'scan', 'kind': 'file', 'locator_ref': 'scan.pdf'}],
    })['session_id']}
    observed = call_workbench(project, 'intake_advance', args)
    source, = observed['sources']
    assert source['coverage'] == 'full', (
        f"scanned page was not fully observed: coverage={source['coverage']}, "
        f"gaps={source.get('gaps')}; the data layer probe disables remote OCR "
        'providers (dataagent_data/observation/cli.py, '
        'remote_ocr_requires_governed_egress) and scan.pdf has no text layer, '
        'so a usable OCR engine is required')
    page, = source['document_excerpts']
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


def _preview_values(project, preview_ref):
    """Read the mapped instance values of a preview straight from the
    workbench store (the MCP tools only expose counts)."""
    id, revision = preview_ref.rsplit('@', 1)
    with sqlite3.connect(project/'.dataagent/db/workbench.sqlite3') as db:
        body, = db.execute(
            'SELECT body FROM wb_records WHERE kind=? AND id=? AND revision=?',
            ('preview', id, int(revision))).fetchone()
    return json.loads(body)['instances'][0]['values']


def verify_invoice(project):
    """invoice.pdf, the retained assertion M1-04 depends on: the original value
    126000 converts to 1260 through a minor_to_major mapping."""
    args, request, profile = _upload(project, 'invoice.pdf', 'invoice', INTAKE/'invoice.pdf')
    expected = {'number': 'INV-001', 'amount_minor': '126000', 'currency': 'CNY'}
    assert profile['coverage'] == 'full' and profile['records'] == [expected], profile
    proposal = {**request['proposal_template'], 'bindings': {
        'number': {'source_field': 'number'},
        'amount': {'source_field': 'amount_minor', 'transform': 'minor_to_major'},
        'currency': {'source_field': 'currency'},
    }}
    preview = call_workbench(project, 'intake_propose', {
        **args, 'expected_revision': request['expected_revision'], 'proposal': proposal,
    })
    assert preview['instance_count'] == 1 and preview['issues'] == []
    values = _preview_values(project, preview['preview_ref'])
    assert (values.get('number'), str(values.get('amount')), values.get('currency')) \
        == ('INV-001', '1260', 'CNY'), values
    call_workbench(project, 'mapping_apply', {
        **args, 'expected_revision': preview['session_revision'],
        'decision': {'preview_ref': preview['preview_ref'], 'target_scope': 'mapping'},
    })
    status = call_workbench(project, 'intake_status', args)
    assert status['phase'] == 'saved' and status['selected_versions']['release']
    return {'observed': expected, 'mapped': values, 'session': status}


def verify_mixed(project):
    """mixed.pdf, the retained partial-coverage assertion: pages 1 and 3 are
    completed while page 2 stays a gap."""
    _args, _request, profile = _upload(project, 'mixed.pdf', 'mixed', INTAKE/'mixed.pdf')
    assert profile['coverage'] == 'partial', profile['coverage']
    assert profile['completed_partitions'] == [1, 3], profile['completed_partitions']
    gaps = [gap['partition'] for gap in profile['gaps']]
    assert gaps == [2], gaps
    return {'completed': profile['completed_partitions'], 'gaps': gaps}


def verify_xlsx(project):
    """invoices.xlsx, the retained sparse-sheet assertion: the INV-002 amount
    evidence sits at B4 (the empty third row shifts it down)."""
    _args, _request, profile = _upload(project, 'invoices.xlsx', 'xlsx',
                                       INTAKE/'invoices.xlsx')
    assert profile['coverage'] == 'full', profile['coverage']
    index = next(i for i, r in enumerate(profile['records'])
                 if r.get('number') == 'INV-002')
    selector = _anchor(profile, index, 'amount_minor')
    assert selector is not None and selector['kind'] == 'excel_cell' \
        and selector['range'] == 'B4', selector
    assert profile['records'][index]['amount_minor'] == 90000
    return {'second_amount_cell': selector['range']}


def _build_docx(project, directory):
    """Generate the synthetic policy docx with the installed data layer's
    python-docx (the dependency T26b added to the installation closure).

    The binary is written under a temporary directory per run; the repository
    never carries a docx fixture.
    """
    python, = (project/'.mint/packages/dataagent').glob('data-layer@*/.venv/bin/python')
    path = Path(directory)/'policy.docx'
    code = '''\
import sys
from docx import Document

document = Document()
document.add_heading(sys.argv[2], level=1)
document.add_paragraph(sys.argv[3])
rows = [sys.argv[4:7], sys.argv[7:10], sys.argv[10:13]]
table = document.add_table(rows=len(rows), cols=len(rows[0]))
table.style = 'Table Grid'
for row_index, values in enumerate(rows):
    for column_index, value in enumerate(values):
        table.cell(row_index, column_index).text = value
document.save(sys.argv[1])
'''
    arguments = [str(path), DOCX_TITLE, DOCX_BODY, *sum(DOCX_TABLE, [])]
    result = subprocess.run([str(python), '-c', code, *arguments],
                            cwd=project, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f'docx fixture generation failed: {result.stderr[-2000:]}')
    return path


def _record_location(profile, index, *, locations=None):
    if locations is None:
        locations = profile['metadata'].get('record_locations', [])
    return next((location for location in locations
                 if location.get('record') == index), None)


def verify_docx(project):
    """T26/T26b: a runtime-generated policy docx through the installed
    artifact. Assertions use the fixed values above, not values derived from
    the probe: coverage is full, the body paragraph is readable from the
    paragraphs record set with a paragraph anchor, the default record view is
    the data table, and the 一线 row's 600 is anchored at table 1, row 2,
    column 2 (1-based per T26)."""
    with tempfile.TemporaryDirectory(prefix='dataagent-docx-') as directory:
        fixture = _build_docx(project, directory)
        _args, request, profile = _upload(project, 'policy.docx', 'policy', fixture)
    assert profile['coverage'] == 'full', profile['coverage']
    if isinstance(request, dict) and request.get('sources'):
        assert request['sources'][0]['coverage'] == 'full', request['sources'][0]

    # Title: a level-1 heading with exactly the requested text.
    assert any(paragraph['text'] == DOCX_TITLE and paragraph['heading_level'] == 1
               for paragraph in profile['metadata']['paragraphs']), \
        profile['metadata']['paragraphs']

    # Body paragraph: exact text plus a paragraph anchor (T26 paragraph:<n>).
    # The default profile contains the data table only; prose lives in the
    # separate paragraphs record set.
    paragraphs = profile['metadata']['record_sets']['paragraphs']
    index = next((i for i, record in enumerate(paragraphs['records'])
                  if record.get('text') == DOCX_BODY), None)
    assert index is not None, paragraphs['records']
    selector = _record_set_anchor(paragraphs, index, 'text')
    assert selector is not None and selector['kind'] == 'text_span', selector
    assert re.fullmatch(r'paragraph:\d+', selector['unit_ref'] or ''), selector
    body_anchor = selector['unit_ref']
    location = _record_location(
        profile, index, locations=paragraphs.get('record_locations', []))
    assert location is not None and location['kind'] == 'paragraph', location
    assert profile['metadata']['units'][body_anchor] == DOCX_BODY, selector

    # Table row 一线: the value 600 and its 1-based cell anchor.
    assert all('text' not in record for record in profile['records']), profile['records']
    rows = [record.get('城市') for record in profile['records']]
    assert rows.count('一线') == 1 and '其他' in rows, rows
    index = rows.index('一线')
    record = profile['records'][index]
    assert record.get('标准') == '600' and record.get('币种') == 'CNY', record
    selector = _anchor(profile, index, '标准')
    assert selector is not None and selector['kind'] == 'text_span', selector
    assert selector['unit_ref'] == 'table:1/row:2/col:2', selector
    assert profile['metadata']['units'][selector['unit_ref']] == '600', selector
    table = profile['metadata']['tables'][0]
    assert [table['headers'], *table['rows'][1:]] == DOCX_TABLE, table

    return {'coverage': profile['coverage'], 'body_anchor': body_anchor,
            'table_anchor': 'table:1/row:2/col:2',
            'records': len(profile['records']),
            'anchors': len(profile['anchors'])}


def _selected_profile(project, session_id, source_id):
    """Read the exact profile revision selected by the session."""
    with sqlite3.connect(project/'.dataagent/db/workbench.sqlite3') as db:
        body, = db.execute(
            "SELECT body FROM wb_records WHERE kind='session' AND id=? "
            'ORDER BY revision DESC LIMIT 1', (session_id,)).fetchone()
        selected = json.loads(body)['selected_versions']
        ref = selected['profile:'+source_id]
        profile_id, revision = ref.rsplit('@', 1)
        profile_body, = db.execute(
            "SELECT body FROM wb_records WHERE kind='profile' AND id=? AND revision=?",
            (profile_id, int(revision))).fetchone()
    return json.loads(profile_body)


def _bulk_sample(project):
    """Generate the 30 MB-class sample at run time (never committed)."""
    path = project/'bulk-30mb.csv'
    target = 30 * 1024 * 1024
    header = 'number,amount_minor,currency,note\n'
    with path.open('w', encoding='utf-8', newline='') as handle:
        handle.write(header)
        written = len(header.encode())
        index = 0
        while written < target:
            line = f'INV-{index:07d},126000,CNY,bulk row {index:07d} ' + 'x'*150 + '\n'
            handle.write(line)
            written += len(line.encode())
            index += 1
    return path, written, index


def _profile_view(profile):
    """Comparable evidence; worker_pid and other run-local fields are excluded."""
    return {
        'records': profile['records'],
        'anchors': profile['anchors'],
        'fields': profile['fields'],
        'coverage': profile['coverage'],
        'sampled': profile['sampled'],
        'total_partitions': profile['total_partitions'],
        'completed_partitions': profile['completed_partitions'],
        'gaps': profile['gaps'],
        'total_rows': profile['metadata']['total_rows'],
        'structure_fingerprint': profile['metadata']['structure_fingerprint'],
        'field_stats': profile['metadata']['field_stats'],
    }


def verify_segmented_sample(project):
    """T13: a 30 MB-class sample completes in bounded, resumable advances and
    produces the same evidence as a single unbounded probe."""
    path, size, rows = _bulk_sample(project)
    common_env = {**os.environ, 'DATAAGENT_PROBE_ROW_BUDGET': '2000'}
    one_started = call_workbench(project, 'intake_start', {
        'goal': '核对 30MB 样本内容',
        'sources': [{'source_id': 'bulk', 'kind': 'file', 'locator_ref': path.name}],
    })
    began = time.monotonic()
    one_request = call_workbench(project, 'intake_advance',
        {'session_id': one_started['session_id']},
        env={**common_env, 'DATAAGENT_INTAKE_BUDGET_SECONDS': '50',
             'DATAAGENT_PROBE_SEGMENT_ROWS': '100000'})
    one_wall = time.monotonic() - began
    assert one_wall < 55, f'one-shot advance took {one_wall:.1f}s'
    assert one_request['next_actions'] != ['retry_probe'], one_request
    one_shot = _selected_profile(project, one_started['session_id'], 'bulk')
    assert one_shot['sampled'] and len(one_shot['records']) == 2000, one_shot['coverage']

    started = call_workbench(project, 'intake_start', {
        'goal': '核对 30MB 样本内容（分段）',
        'sources': [{'source_id': 'bulk', 'kind': 'file', 'locator_ref': path.name}],
    })
    segmented_env = {**common_env, 'DATAAGENT_INTAKE_BUDGET_SECONDS': '0.1',
                     'DATAAGENT_PROBE_SEGMENT_ROWS': '250'}
    advances = 0
    walls = []
    while True:
        began = time.monotonic()
        request = call_workbench(project, 'intake_advance',
            {'session_id': started['session_id']}, env=segmented_env)
        walls.append(time.monotonic() - began)
        advances += 1
        assert walls[-1] < 55, f'advance {advances} took {walls[-1]:.1f}s'
        if request.get('next_actions') != ['retry_probe']:
            break
        source, = request['sources']
        assert source['resume'], source
        assert source['completed_partitions'] == [], source
        assert request.get('issues') == [], request.get('issues')
        assert advances < 400, 'segmented intake did not finish'
    segmented = _selected_profile(project, started['session_id'], 'bulk')
    assert advances > 1, advances
    assert segmented['sampled'] and len(segmented['records']) == 2000
    assert _profile_view(segmented) == _profile_view(one_shot)
    return {'size_bytes': size, 'rows': rows, 'advances': advances,
            'one_shot_seconds': round(one_wall, 2),
            'max_advance_seconds': round(max(walls), 2),
            'records': len(segmented['records']),
            'anchors': len(segmented['anchors']), 'matches_one_shot': True}


def apply(report, project, args, context):
    report['scan'] = verify_scan(project, args.ocr_root)
    report['legacy_fixtures'] = {'invoice': verify_invoice(project),
                                'mixed': verify_mixed(project),
                                'xlsx': verify_xlsx(project)}
    report['docx'] = verify_docx(project)
    diffs = Diffs()
    report['p1_files'] = {}
    for name in SAMPLE_ORDER:
        report['p1_files'][name] = _compare_sample(diffs, project, name)
    report['p1_files']['mismatches'] = diffs.items
    if diffs:
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output/'files-diffs.json').write_text(
            json.dumps(diffs.items, ensure_ascii=False, indent=2))
        # Evidence for the samples that did match, for the review that
        # adjudicates the remaining conflicts.
        report['status'] = 'mismatched'
        (args.output/'files-report-partial.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2))
        lines = [f'{item["sample"]} | {item["check"]} | expected {item["expected"]!r} '
                 f'| actual {item["actual"]!r}' for item in diffs.items]
        raise RuntimeError(f'p1-files 比对失败，{len(lines)} 处差异（样本 | 检查项 | '
                           '期望 | 实际）：\n' + '\n'.join(lines))
    report['segmented_30mb'] = verify_segmented_sample(project)
    remove_not_verified(report, 'file processing')
