"""Sources phase: file, SQLite and REST, plus PostgreSQL when a locator is given.

The REST fixture requires ``Authorization: Bearer <token>``. Its token is a
sentinel injected through the connection manifest's logical name
(``file:rest-token``), never written to the manifest or the report. After the
phase the temporary workspace (except ``.dataagent/secrets/``), the output
directory, Mint session logs and the report are scanned for the sentinel; any
hit fails the phase.

T25 adds an independently written cross-source sample group
(``fixtures/intake/cross-source/``): PDF, SQLite and paginated REST records
share ten document numbers and contain five (object, field) conflicts on four
objects plus three keyless records. The phase compares the mapped preview
against ``gold.json`` without ever rewriting it.
"""

import json
import os
from decimal import Decimal
from pathlib import Path
import shutil
import sqlite3
import time

from .common import ROOT, call_workbench, loopback, remove_not_verified

SENTINEL = 'T14-SENTINEL-5f0c9a7d2b8e4c61'
WRONG_TOKEN = 'T14-WRONG-2a7e4c9b6d1f8035'
PREVIEW_BLOCK_DETAIL = 'preview contains unresolved issues'
CROSS_SOURCE = ROOT/'packages/capabilities/dataagent-scenarios/fixtures/intake/cross-source'
_CREDENTIAL_KEYS = {
    'token', 'password', 'secret', 'credentials', 'credential_refs',
    'credential_options', 'credential_binding_ref', 'authorization',
}


def _assert_no_credentials(value, path='intake'):
    """Reject credential fields and sentinel values in agent-visible output."""

    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in _CREDENTIAL_KEYS:
                raise AssertionError(f'credential field {path}.{key} leaked into output')
            _assert_no_credentials(item, f'{path}.{key}')
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _assert_no_credentials(item, f'{path}[{index}]')
    elif isinstance(value, str):
        for label, secret in (('sentinel', SENTINEL), ('wrong token', WRONG_TOKEN)):
            if secret in value:
                raise AssertionError(f'{label} leaked into output at {path}')


def _read_contains(path, needles):
    overlap = max((len(needle) for needle in needles), default=1) - 1
    tail = b''
    try:
        with path.open('rb') as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    return False
                data = tail + chunk
                if any(needle in data for needle in needles):
                    return True
                tail = data[-overlap:] if overlap else b''
    except OSError as exc:
        raise RuntimeError(f'credential scan could not read {path}: {exc}') from None


def _mint_log_roots(project):
    """Where Mint keeps session logs.

    Mint writes project-session logs under ``<project>/.mint/logs`` (already
    covered by the project walk); ``MINT_HOME/logs`` is the other location.
    """

    mint_home = os.environ.get('MINT_HOME')
    return [project / '.mint/logs',
            (Path(mint_home).expanduser() if mint_home else Path.home() / '.mint') / 'logs']


def _scan_for_credentials(project, output, report, *, extra_roots=(), since=0.0):
    """Fail when a sentinel appears outside ``.dataagent/secrets/`` or the report."""

    needles = [SENTINEL.encode(), WRONG_TOKEN.encode()]
    secrets_dir = (project / '.dataagent/secrets').resolve()
    hits = []
    roots = [(project, False), (output, False)]
    roots.extend((root, True) for root in extra_roots)
    for root, fresh_only in roots:
        if not root.exists():
            continue
        paths = [root] if root.is_file() else root.rglob('*')
        for path in paths:
            if not path.is_file():
                continue
            try:
                resolved = path.resolve()
                if resolved == secrets_dir or secrets_dir in resolved.parents:
                    continue
                if fresh_only and since and path.stat().st_mtime < since - 2:
                    continue
            except OSError as exc:
                raise RuntimeError(f'credential scan could not inspect {path}: {exc}') from None
            if _read_contains(resolved, needles):
                hits.append(str(path))
    rendered = json.dumps(report, ensure_ascii=False)
    for label, secret in (('sentinel', SENTINEL), ('wrong token', WRONG_TOKEN)):
        if secret in rendered:
            hits.append(f'report:{label}')
    if hits:
        raise RuntimeError('credential sentinel leaked into: ' + ', '.join(hits[:5]))


class Diffs:
    """Per-item differences (object, field, expected, actual) for one run."""

    def __init__(self):
        self.items = []

    def add(self, object, field, expected, actual):
        self.items.append({'object': object, 'field': field,
                           'expected': _plain(expected), 'actual': _plain(actual)})

    def __bool__(self):
        return bool(self.items)


def _plain(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, set):
        return sorted(_plain(item) for item in value)
    return value


def _same_value(field, expected, actual):
    """Amount compares as decimal; other ontology fields compare exactly."""

    if field == 'amount':
        if expected is None or actual is None:
            return expected is None and actual is None
        try:
            return Decimal(str(expected)) == Decimal(str(actual))
        except (ArithmeticError, ValueError):
            return False
    return expected == actual


def _stored_record(project, kind, ref):
    """Read one immutable workbench record (the MCP tools expose summaries)."""

    record_id, revision = str(ref).rsplit('@', 1)
    with sqlite3.connect(project/'.dataagent/db/workbench.sqlite3') as db:
        row = db.execute('SELECT body FROM wb_records WHERE kind=? AND id=? AND revision=?',
                         (kind, record_id, int(revision))).fetchone()
    if row is None:
        raise RuntimeError(f'{kind} record {ref} is missing from the acceptance workspace')
    return json.loads(row[0])


def _conflict_issues(body):
    """Dedupe conflicting-value events by (object number, field) (gold J3)."""

    numbers = {instance['id']: instance['values'].get('number') for instance in body['instances']}
    found = {}
    for issue in body['issues']:
        if issue.get('code') == 'ontology.conflicting_values':
            found[(numbers.get(issue.get('entity_id')), issue.get('target'))] = issue
    return found


def _assertion_values(body, entity_id, field):
    """Original per-source values kept as assertions, keyed by source id."""

    values = {}
    for assertion in body.get('assertions', []):
        if assertion.get('relation') != field:
            continue
        roles = {role['role']: role['value'] for role in assertion.get('role_bindings', [])}
        if roles.get('subject') != entity_id:
            continue
        for anchor in assertion.get('source_anchors', []):
            values.setdefault(anchor['source_ref'], roles.get('value'))
    return values


def _keyless_details(instances, rest_profile):
    """Source and position of every identity-unresolved preview candidate."""

    details = []
    for instance in instances:
        if instance['values'].get('number'):
            continue
        anchors = [anchor for field_anchors in instance.get('source_anchors', {}).values()
                   for anchor in field_anchors]
        sources = sorted({anchor['source_ref'] for anchor in anchors})
        detail = {'id': instance['id'], 'source': sources[0] if len(sources) == 1 else sources,
                  'values': instance['values'], 'unresolved': instance.get('unresolved', []),
                  'pointers': set()}
        for anchor in anchors:
            selector = anchor.get('selector', {})
            if selector.get('kind') == 'pdf_text_span':
                detail['page'] = selector.get('page')
            elif selector.get('kind') == 'json_pointer':
                detail['pointers'].add(selector.get('pointer', '').rsplit('/', 1)[0])
            elif selector.get('kind') == 'record_key':
                keys = selector.get('keys', {})
                if isinstance(keys, dict) and isinstance(keys.get('primary_key'), dict):
                    detail['primary_key'] = keys['primary_key']
        details.append(detail)
    # REST anchors carry JSON pointers but not page numbers. Match the keyless
    # record by its values against the REST profile to read page/row evidence.
    record_keys = rest_profile['metadata'].get('record_keys', [])
    for detail in details:
        if detail['source'] != 'rest':
            continue
        for index, record in enumerate(rest_profile['records']):
            if record.get('/code') not in (None, ''):
                continue
            if all(_same_value(field, detail['values'].get(field), record.get('/' + field))
                   for field in ('amount', 'currency', 'issuer')):
                position = record_keys[index]
                detail['page'] = position.get('page')
                detail['row'] = position.get('row')
                break
    return details


def _compare_cross_source(preview_body, profiles, diffs, gold):
    """Compare the mapped preview against the hand-written gold object by object."""

    expected = gold['expected']
    instances = preview_body['instances']
    keyed, keyless = {}, []
    for instance in instances:
        number = instance['values'].get('number')
        if number:
            keyed[number] = instance
        else:
            keyless.append(instance)

    if len(keyed) != expected['keyed_object_count']:
        diffs.add('（全部）', 'keyed_object_count', expected['keyed_object_count'], len(keyed))
    if len(keyless) != expected['keyless_candidate_count']:
        diffs.add('（全部）', 'keyless_candidate_count', expected['keyless_candidate_count'], len(keyless))
    if len(instances) not in {expected['keyed_object_count'],
                              expected['instance_count_including_keyless_candidates']}:
        diffs.add('（全部）', 'instance_count',
                  expected['instance_count_including_keyless_candidates'], len(instances))

    for obj in gold['objects']:
        number = obj['number']
        actual = keyed.get(number)
        if actual is None:
            diffs.add(number, 'instance', '有键对象', '缺失')
            continue
        for field in ('amount', 'currency', 'issuer'):
            if not _same_value(field, obj['values'].get(field), actual['values'].get(field)):
                diffs.add(number, field, obj['values'].get(field), actual['values'].get(field))
        for field in ('number', 'amount'):
            observed = len(actual.get('source_anchors', {}).get(field, []))
            if observed != len(obj['records']):
                diffs.add(number, f'{field} 来源记录数', len(obj['records']), observed)
        expected_sources = sorted({record['source'] for record in obj['records']})
        observed_sources = sorted({anchor['source_ref']
                                   for anchor in actual.get('source_anchors', {}).get('number', [])})
        if observed_sources != expected_sources:
            diffs.add(number, 'sources', expected_sources, observed_sources)

    known = {obj['number'] for obj in gold['objects']}
    for number in sorted(set(keyed) - known):
        diffs.add(number, 'instance', '（金标未列）', '多出')

    actual_conflicts = _conflict_issues(preview_body)
    expected_conflicts = {(conflict['number'], conflict['field']): conflict
                          for conflict in gold['conflicts']}
    if len(actual_conflicts) != expected['conflict_field_count']:
        diffs.add('（全部）', 'conflict_field_count',
                  expected['conflict_field_count'], len(actual_conflicts))
    observed_objects = sorted({number for number, _ in actual_conflicts if number})
    if len(observed_objects) != expected['conflict_object_count']:
        diffs.add('（全部）', 'conflict_object_count',
                  expected['conflict_object_count'], len(observed_objects))
    if observed_objects != sorted(expected['conflict_object_numbers']):
        diffs.add('（全部）', 'conflict_object_numbers',
                  sorted(expected['conflict_object_numbers']), observed_objects)
    observed_free = sorted(set(keyed) - set(observed_objects))
    if observed_free != sorted(expected['conflict_free_object_numbers']):
        diffs.add('（全部）', 'conflict_free_object_numbers',
                  sorted(expected['conflict_free_object_numbers']), observed_free)
    for key in sorted(set(expected_conflicts) | set(actual_conflicts),
                      key=lambda item: (str(item[0]), str(item[1]))):
        if key not in actual_conflicts:
            diffs.add(key[0], key[1], '冲突', '无冲突')
        elif key not in expected_conflicts:
            diffs.add(key[0], key[1], '无冲突', '冲突')

    by_number_id = {instance['values'].get('number'): instance['id']
                    for instance in instances if instance['values'].get('number')}
    for key, conflict in expected_conflicts.items():
        entity_id = by_number_id.get(key[0])
        if entity_id is None:
            continue
        values = _assertion_values(preview_body, entity_id, key[1])
        for source, expected_value in conflict['values'].items():
            actual_value = values.get(source, '<missing>')
            if not _same_value(key[1], expected_value, actual_value):
                diffs.add(key[0], f'{key[1]} 断言[{source}]', expected_value, actual_value)
        for source in sorted(set(values) - set(conflict['values'])):
            diffs.add(key[0], f'{key[1]} 断言[{source}]', '（金标未列）', values[source])

    details = _keyless_details(keyless, profiles['rest'])
    if len({detail['id'] for detail in details}) != len(details):
        diffs.add('（全部）', 'keyless_candidates', '每条缺键记录独立', '出现重复候选')
    merged = {instance['id'] for instance in keyed.values()} & {detail['id'] for detail in details}
    if merged:
        diffs.add('（全部）', 'keyless_merge', '不与有键对象合并', sorted(merged))

    for record in gold['keyless_records']:
        source = record['source']
        candidates = [detail for detail in details if detail['source'] == source]
        if source == 'pdf':
            matched = [detail for detail in candidates if detail.get('page') == record['page']]
        elif source == 'sqlite':
            matched = [detail for detail in candidates
                       if detail.get('primary_key', {}).get('id') == record['id']]
        else:
            matched = [detail for detail in candidates
                       if detail.get('page') == record['page']
                       and record['pointer'] in detail['pointers']]
        label = f'{source} 缺键记录'
        if len(matched) != 1:
            position = {key: record[key] for key in ('page', 'table', 'id', 'pointer') if key in record}
            actual = [{'source': detail['source'], 'page': detail.get('page'),
                       'primary_key': detail.get('primary_key'),
                       'pointers': sorted(detail['pointers'])} for detail in candidates]
            diffs.add(label, '位置', position, actual)
            continue
        detail = matched[0]
        for field in ('amount', 'currency', 'issuer'):
            if not _same_value(field, record['values'].get(field), detail['values'].get(field)):
                diffs.add(label, field, record['values'].get(field), detail['values'].get(field))
        if 'number' not in detail['unresolved']:
            diffs.add(label, 'unresolved', '包含 number', detail['unresolved'])

    return {
        'keyed_object_count': len(keyed),
        'keyless_candidate_count': len(keyless),
        'instance_count': len(instances),
        'conflict_event_count': sum(1 for issue in preview_body['issues']
                                    if issue.get('code') == 'ontology.conflicting_values'),
        'conflict_field_count': len(actual_conflicts),
        'conflict_object_count': len(observed_objects),
        'conflict_object_numbers': observed_objects,
        'conflict_free_object_numbers': observed_free,
        'conflicts': [{'number': number, 'field': field}
                      for number, field in sorted(actual_conflicts,
                                                  key=lambda item: (str(item[0]), str(item[1])))],
        'keyless_records': [{'source': detail['source'], 'page': detail.get('page'),
                             'row': detail.get('row'),
                             'primary_key': detail.get('primary_key'),
                             'pointers': sorted(detail['pointers']),
                             'values': _plain(detail['values'])} for detail in details],
    }


def _verify_partial_save(project, args, env, before, preview, preview_body, gold, diffs):
    """FDE-3: allow_partial saves clean objects, suspends conflicts, lists keyless."""

    partial = call_workbench(project, 'mapping_apply', {
        **args, 'expected_revision': before['revision'],
        'decision': {'preview_ref': preview['preview_ref'], 'target_scope': 'mapping'},
        'allow_partial': True,
        'reason': '先保存无冲突对象；冲突与缺必填的对象挂起，缺键记录单列',
    }, env=env)
    expected = gold['expected']
    saved = {item['values'].get('number') for item in partial.get('saved', [])}
    suspended = {item['values'].get('number') for item in partial.get('suspended', [])}
    if partial.get('partial') is not True:
        diffs.add('（全部）', 'partial_save.partial', True, partial.get('partial'))
    if saved != set(expected['conflict_free_object_numbers']):
        diffs.add('（全部）', 'partial_save.saved',
                  sorted(expected['conflict_free_object_numbers']), sorted(saved))
    if suspended != set(expected['blocked_object_numbers']):
        diffs.add('（全部）', 'partial_save.suspended',
                  sorted(expected['blocked_object_numbers']), sorted(suspended))
    if saved & suspended:
        diffs.add('（全部）', 'partial_save.overlap', '无交集', sorted(saved & suspended))
    for item in partial.get('suspended', []):
        codes = {reason.get('code') for reason in item.get('reasons', [])}
        if not codes & {'ontology.conflicting_values', 'ontology.required_value_missing'}:
            diffs.add(item.get('object'), 'partial_save.suspended_reason',
                      '冲突或缺必填', sorted(codes))

    unidentified = partial.get('unidentified_records', [])
    if len(unidentified) != expected['keyless_candidate_count']:
        diffs.add('（全部）', 'partial_save.unidentified_count',
                  expected['keyless_candidate_count'], len(unidentified))
    for record in gold['keyless_records']:
        source = record['source']
        candidates = [item for item in unidentified
                      if {entry['source_id'] for entry in item.get('sources', [])} == {source}]
        matched = []
        for item in candidates:
            locations = ' '.join(location for entry in item.get('sources', [])
                                 for location in entry.get('locations', []))
            if source == 'pdf' and f'第 {record["page"]} 页' not in locations:
                continue
            if source == 'sqlite' and f'id={record["id"]}' not in locations:
                continue
            if source == 'rest' and record['pointer'] not in locations:
                continue
            if not all(_same_value(field, record['values'].get(field), item['values'].get(field))
                       for field in ('amount', 'currency', 'issuer')):
                continue
            if 'number' not in (item.get('unresolved') or []):
                continue
            matched.append(item)
        label = f'{source} 缺键记录（部分保存）'
        if len(matched) != 1:
            diffs.add(label, '单列记录', 1, len(matched))

    status = call_workbench(project, 'intake_status', args, env=env)
    if status['phase'] != 'saved':
        diffs.add('（全部）', 'partial_save.phase', 'saved', status['phase'])
    release_ref = status['selected_versions'].get('release')
    if not release_ref or not partial.get('release_ref'):
        diffs.add('（全部）', 'partial_save.release', '存在', release_ref)
    elif release_ref != partial['release_ref']:
        diffs.add('（全部）', 'partial_save.release_ref', release_ref, partial['release_ref'])
    else:
        release = _stored_record(project, 'release', release_ref)
        if not release.get('digest'):
            diffs.add('（全部）', 'partial_save.release_digest', '非空', release.get('digest'))

    preview_state = _stored_record(project, 'preview', status['selected_versions']['preview'])
    audit = (preview_state.get('partial_save') or [None])[-1]
    if not audit or not audit.get('subject_ref') or not audit.get('recorded_at') or not audit.get('reason'):
        diffs.add('（全部）', 'partial_save.audit', '谁/何时/原因', audit)
    return {
        'saved_object_numbers': sorted(saved),
        'suspended_object_numbers': sorted(suspended),
        'suspended': partial.get('suspended', []),
        'unidentified_records': unidentified,
        'release_ref': release_ref,
        'phase': status['phase'],
        'audit': audit,
    }


def verify_cross_source(project, url, token_ref, diffs, cross_reads, cross_unauthorized):
    """T25: PDF + SQLite + paginated REST mapped together, compared to gold."""

    import http.client
    from urllib.parse import urlsplit

    fixture = CROSS_SOURCE
    # The cross-source service must reject a request without the bearer token;
    # the 401 is verified before the successful probe resets the counter.
    parts = urlsplit(url)
    connection = http.client.HTTPConnection(parts.hostname, parts.port, timeout=5)
    try:
        connection.request('GET', '/page1.json')
        response = connection.getresponse()
        response.read()
        if response.status != 401:
            raise RuntimeError(f'跨源 REST 无令牌请求返回 {response.status}，期望 401')
    finally:
        connection.close()
    cross_unauthorized['count'] = 0
    shutil.copy2(fixture/'samples/invoices.pdf', project/'invoices.pdf')
    shutil.copy2(fixture/'samples/ledger.db', project/'ledger.db')
    config = project/'cross-source-connections.json'
    config.write_text(json.dumps({'accounting': {
        'kind': 'rest', 'label': 'T25 发票 API', 'locator': url + '/page1.json',
        'allowed_origins': [url],
        'credential_options': {'auth': 'bearer'},
        'credential_refs': {'token': token_ref},
        'options': {'records_path': '/items', 'keys': ['/code'],
                    'source_version_path': '/version',
                    'pagination': {'next_path': '/next'}},
    }}))
    env = {**os.environ, 'DATAAGENT_SOURCE_CONNECTIONS': str(config)}
    args = {'session_id': call_workbench(project, 'intake_start', {
        'goal': '对齐 PDF、SQLite 与 REST 中共享单据号的合成发票',
        'sources': [
            {'source_id': 'pdf', 'kind': 'file', 'locator_ref': 'invoices.pdf'},
            {'source_id': 'sqlite', 'kind': 'sqlite', 'locator_ref': 'ledger.db'},
            {'source_id': 'rest', 'kind': 'rest', 'locator_ref': 'accounting'},
        ],
    }, env=env)['session_id']}
    observed = call_workbench(project, 'intake_advance', args, env=env)
    by_source = {source['source_id']: source for source in observed['sources']}
    # The REST probe reports a missing record key as a ``key_missing`` gap; it
    # is the expected keyless record, not an unread page or a transport gap.
    incomplete = {}
    for source_id, source in by_source.items():
        unexpected = [gap for gap in source.get('gaps', [])
                      if not (source_id == 'rest' and gap.get('code') == 'key_missing')]
        if unexpected or (source_id != 'rest' and source['coverage'] != 'full'):
            incomplete[source_id] = {'coverage': source['coverage'], 'gaps': source.get('gaps')}
    if incomplete:
        raise RuntimeError('跨源来源探查未读全：' + json.dumps(incomplete, ensure_ascii=False))
    if observed.get('next_actions') != ['propose_mapping']:
        raise RuntimeError('跨源来源探查未进入映射提案：'
                           + json.dumps(observed.get('next_actions'), ensure_ascii=False))

    session = call_workbench(project, 'intake_status', args, env=env)
    missing = [source_id for source_id in ('pdf', 'sqlite', 'rest')
               if 'profile:' + source_id not in session['selected_versions']]
    if missing:
        raise RuntimeError('跨源来源缺少探查结果：' + ', '.join(missing))
    profiles = {source_id: _stored_record(project, 'profile',
                                          session['selected_versions']['profile:' + source_id])
                for source_id in ('pdf', 'sqlite', 'rest')}
    gold = json.loads((fixture/'gold.json').read_text(encoding='utf-8'))

    observed_total = sum(len(profiles[source_id]['records'])
                         for source_id in ('pdf', 'sqlite', 'rest'))
    if observed_total != gold['expected']['total_source_records']:
        diffs.add('（全部）', 'total_source_records',
                  gold['expected']['total_source_records'], observed_total)
    for source_id, spec in gold['sources'].items():
        records = profiles[source_id]['records']
        if len(records) != spec['record_count']:
            diffs.add(f'来源 {source_id}', 'record_count', spec['record_count'], len(records))
        key_field = '/code' if source_id == 'rest' else 'number'
        keyed_count = sum(1 for record in records if record.get(key_field) not in (None, ''))
        if keyed_count != spec['keyed']:
            diffs.add(f'来源 {source_id}', 'keyed_record_count', spec['keyed'], keyed_count)
        if len(records) - keyed_count != spec['keyless']:
            diffs.add(f'来源 {source_id}', 'keyless_record_count',
                      spec['keyless'], len(records) - keyed_count)
    rest_profile = profiles['rest']
    if rest_profile['completed_partitions'] != [1, 2, 3]:
        diffs.add('来源 rest', 'completed_partitions', [1, 2, 3],
                  rest_profile['completed_partitions'])
    if rest_profile['total_partitions'] != 3:
        diffs.add('来源 rest', 'total_partitions', 3, rest_profile['total_partitions'])
    if rest_profile['metadata'].get('source_version') != 't25-fixture-1':
        diffs.add('来源 rest', 'source_version', 't25-fixture-1',
                  rest_profile['metadata'].get('source_version'))
    unexpected_gaps = [gap for gap in rest_profile['gaps'] if gap['code'] != 'key_missing']
    if unexpected_gaps:
        diffs.add('来源 rest', 'unexpected_gaps', '仅允许缺键记录的 key_missing',
                  [(gap['partition'], gap['code']) for gap in unexpected_gaps])
    for page in ('page1', 'page2', 'page3'):
        if cross_reads[page] != 1:
            diffs.add('来源 rest', f'request {page}.json', 1, cross_reads[page])
    if cross_unauthorized['count']:
        diffs.add('来源 rest', 'unauthorized_requests', 0, cross_unauthorized['count'])

    template = observed['proposal_template']

    def mapping(source_id, bindings, unmapped):
        return {**template, 'source_fingerprint': by_source[source_id]['structure_fingerprint'],
                'bindings': bindings, 'unmapped': unmapped}

    common_bindings = {
        'number': {'source_field': 'number'},
        'amount': {'source_field': 'amount', 'transform': 'decimal'},
        'currency': {'source_field': 'currency'},
        'issuer': {'source_field': 'issuer'},
    }
    proposals = {
        'pdf': mapping('pdf', common_bindings, {'posted_on': 'unresolved'}),
        'sqlite': mapping('sqlite', common_bindings, {'id': 'exclude', 'posted_on': 'unresolved'}),
        'rest': mapping('rest', {
            'number': {'source_field': '/code'},
            'amount': {'source_field': '/amount', 'transform': 'decimal'},
            'currency': {'source_field': '/currency'},
            'issuer': {'source_field': '/issuer'},
        }, {'/posted_on': 'unresolved'}),
    }
    preview = call_workbench(project, 'intake_propose_sources', {
        **args, 'proposals': proposals, 'expected_revision': observed['expected_revision'],
    }, env=env)
    preview_body = _stored_record(project, 'preview', preview['preview_ref'])
    summary = _compare_cross_source(preview_body, profiles, diffs, gold)

    before = call_workbench(project, 'intake_status', args, env=env)
    blocked = call_workbench(project, 'mapping_apply', {
        **args, 'expected_revision': before['revision'],
        'decision': {'preview_ref': preview['preview_ref'], 'target_scope': 'mapping'},
    }, env=env, error=True)
    after = call_workbench(project, 'intake_status', args, env=env)
    if after['phase'] != 'preview' or 'release' in after['selected_versions']:
        raise RuntimeError('冲突预览被保存了：phase=%s release=%s' % (
            after['phase'], after['selected_versions'].get('release')))
    numbers = {instance['id']: instance['values'].get('number')
               for instance in preview_body['instances']}
    blocking = []
    for issue in preview_body['issues']:
        object_number = numbers.get(issue.get('entity_id'))
        if object_number is None and issue.get('code') == 'ontology.identity_unresolved':
            object_number = '缺键记录'
        blocking.append({'code': issue.get('code'), 'object': object_number,
                         'field': issue.get('target')})
    blocked_fields = {(item['object'], item['field']) for item in blocking
                      if item['code'] == 'ontology.conflicting_values'}
    for conflict in gold['conflicts']:
        key = (conflict['number'], conflict['field'])
        if key not in blocked_fields:
            diffs.add(key[0], key[1], '保存阻断问题', '未出现')
    error_code = blocked.get('error')
    detail = blocked.get('detail', '')
    if not isinstance(detail, str):
        detail = repr(detail)
    preview_has_issues = bool(preview_body['issues'])
    # Require the save to be blocked by the unresolved preview, not by a bad
    # argument or revision. The MCP error payload carries the service's detail
    # string; a revision/argument failure has a different detail.
    preview_block = detail == PREVIEW_BLOCK_DETAIL and preview_has_issues
    if detail != PREVIEW_BLOCK_DETAIL:
        diffs.add('（全部）', 'mapping_apply.detail', PREVIEW_BLOCK_DETAIL, detail)
    if not preview_has_issues:
        diffs.add('（全部）', 'mapping_apply.preview_issues', '非空', '空')
    # Gold J5 accepts a whole-batch block. The preview issues name the four
    # conflict objects and fields; the MCP error detail itself is generic.
    summary['save_block'] = {
        'request': 'mapping_apply save',
        'blocked': preview_block,
        'error': error_code,
        'detail': detail,
        'expected_detail': PREVIEW_BLOCK_DETAIL,
        'preview_has_issues': preview_has_issues,
        'blocking_issues': blocking,
        'error_detail_names_conflict_objects': [
            number for number in gold['expected']['conflict_object_numbers'] if number in detail],
        'phase_after': after['phase'],
        'release_after': after['selected_versions'].get('release'),
    }
    summary['partial_save'] = _verify_partial_save(
        project, args, env, after, preview, preview_body, gold, diffs)
    summary['sources'] = {source_id: {'records': len(profiles[source_id]['records']),
                                      'coverage': profiles[source_id]['coverage'],
                                      'source_revision': profiles[source_id]['source_revision']}
                          for source_id in ('pdf', 'sqlite', 'rest')}
    summary['rest_pages'] = {
        'completed': rest_profile['completed_partitions'],
        'total': rest_profile['total_partitions'],
        'version': rest_profile['metadata'].get('source_version'),
        'gaps': [(gap['partition'], gap['code']) for gap in rest_profile['gaps']],
        'requests': dict(cross_reads),
        'unauthorized': cross_unauthorized['count'],
        'unauthenticated_probe_status': 401,
    }
    summary['gold'] = str(fixture/'gold.json')
    summary['diffs'] = diffs.items
    return summary


def verify_sources(project, postgres_locator, postgres_user):
    from dataagent_runtime.policy.secrets import store_file_secret
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse, Response

    app = FastAPI()
    with sqlite3.connect(project/'invoice.db') as db:
        db.execute('CREATE TABLE invoice (number TEXT PRIMARY KEY, amount INTEGER, currency TEXT)')
        db.execute("INSERT INTO invoice VALUES ('INV-003', 1260, 'CNY')")
    (project/'invoice.csv').write_text('number,amount_minor,currency\nINV-003,126000,CNY\n')

    token_ref = store_file_secret(project/'.dataagent', 'rest-token', SENTINEL)
    wrong_ref = store_file_secret(project/'.dataagent', 'rest-token-wrong', WRONG_TOKEN)
    reads = {'first': 0, 'second': 0, 'unauthorized': 0}

    def authorized(request):
        if request.headers.get('authorization') == f'Bearer {SENTINEL}':
            return True
        reads['unauthorized'] += 1
        return False

    @app.get('/invoices')
    def invoices(request: Request):
        if not authorized(request):
            return JSONResponse({'error': 'unauthorized'}, status_code=401)
        reads['first'] += 1
        return {'version': 'fixture-1', 'items': [{'code': 'INV-003', 'amount': '1260.00', 'currency': 'CNY'}],
                'next': '/invoices-more'}

    @app.get('/invoices-more')
    def invoices_more(request: Request):
        if not authorized(request):
            return JSONResponse({'error': 'unauthorized'}, status_code=401)
        reads['second'] += 1
        if reads['second'] == 1:
            return JSONResponse({}, status_code=429)
        return {'version': 'fixture-1', 'items': [], 'next': None}

    cross_reads = {'page1': 0, 'page2': 0, 'page3': 0}
    cross_unauthorized = {'count': 0}

    def cross_page(request, name):
        if request.headers.get('authorization') != f'Bearer {SENTINEL}':
            cross_unauthorized['count'] += 1
            return JSONResponse({'error': 'unauthorized'}, status_code=401)
        cross_reads[name] += 1
        return Response((CROSS_SOURCE/'samples'/'rest'/f'{name}.json').read_bytes(),
                        media_type='application/json')

    @app.get('/page1.json')
    def cross_page1(request: Request):
        return cross_page(request, 'page1')

    @app.get('/page2.json')
    def cross_page2(request: Request):
        return cross_page(request, 'page2')

    @app.get('/page3.json')
    def cross_page3(request: Request):
        return cross_page(request, 'page3')

    with loopback(app) as url:
        config = project/'source-connections.json'
        connections = {
            'accounting': {
                'kind': 'rest', 'locator': url+'/invoices', 'allowed_origins': [url],
                'options': {'records_path': '/items', 'keys': ['/code'], 'source_version_path': '/version',
                            'pagination': {'next_path': '/next'}},
                'credential_options': {'auth': 'bearer'},
                'credential_refs': {'token': token_ref},
            },
        }
        if postgres_locator:
            connections['ledger'] = {
                'kind': 'postgres', 'locator': postgres_locator, 'scope': {'tables': ['invoice']},
                'credential_options': {'user': postgres_user},
            }
        config.write_text(json.dumps(connections))
        env = {**os.environ, 'DATAAGENT_SOURCE_CONNECTIONS': str(config)}
        inputs = [('file', 'invoice.csv'), ('sqlite', 'invoice.db')]
        if postgres_locator:
            inputs.append(('postgres', 'ledger'))
        inputs.append(('rest', 'accounting'))
        args = {'session_id': call_workbench(project, 'intake_start', {
            'goal': '从多种来源核对同一张合成发票',
            'sources': [{'source_id': kind, 'kind': kind, 'locator_ref': locator} for kind, locator in inputs],
        }, env=env)['session_id']}
        partial = call_workbench(project, 'intake_advance', args, env=env)
        rest = next(source for source in partial['sources'] if source['source_id'] == 'rest')
        assert rest['coverage'] == 'partial' and partial['next_actions'] == ['retry_probe']
        assert rest['gaps'] == [{'partition': 2, 'code': 'rate_limited'}]
        inference = call_workbench(project, 'intake_inference', args, env=env)
        _assert_no_credentials(inference, 'intake_inference')
        observed = call_workbench(project, 'intake_advance', args, env=env)
        assert reads == {'first': 1, 'second': 2, 'unauthorized': 0}
        expected = {kind for kind, _ in inputs}
        assert {source['source_id'] for source in observed['sources']} == expected
        assert all(source['coverage'] == 'full' for source in observed['sources'])
        if postgres_locator:
            assert next(source for source in observed['sources']
                        if source['source_id'] == 'postgres')['samples'][0]['posted_on'] == '2026-11-11'
        proposals = {}
        for source in observed['sources']:
            kind = source['source_id']
            proposals[kind] = {
                **observed['proposal_template'], 'source_fingerprint': source['structure_fingerprint'],
                'bindings': {
                    'number': {'source_field': '/code' if kind == 'rest' else 'number'},
                    'currency': {'source_field': '/currency' if kind == 'rest' else 'currency'},
                    'amount': {'source_field': 'amount_minor' if kind == 'file' else '/amount' if kind == 'rest' else 'amount',
                               'transform': 'minor_to_major' if kind == 'file' else 'decimal'},
                },
            }
        preview = call_workbench(project, 'intake_propose_sources', {
            **args, 'proposals': proposals, 'expected_revision': observed['expected_revision'],
        }, env=env)
        assert preview['instance_count'] == 1 and preview['issues'] == []
        call_workbench(project, 'mapping_apply', {
            **args, 'expected_revision': preview['session_revision'],
            'decision': {'preview_ref': preview['preview_ref'], 'target_scope': 'mapping'},
        }, env=env)
        status = call_workbench(project, 'intake_status', args, env=env)
        assert status['phase'] == 'saved'
        _assert_no_credentials(status, 'intake_status')

        bad_config = project/'source-connections-wrong.json'
        bad_config.write_text(json.dumps({'accounting-bad': {
            'kind': 'rest', 'locator': url+'/invoices', 'allowed_origins': [url],
            'options': connections['accounting']['options'],
            'credential_options': {'auth': 'bearer'},
            'credential_refs': {'token': wrong_ref},
        }}))
        bad_env = {**os.environ, 'DATAAGENT_SOURCE_CONNECTIONS': str(bad_config)}
        bad = call_workbench(project, 'intake_advance', {'session_id': call_workbench(project, 'intake_start', {
            'goal': '用错误凭据核对同一张合成发票',
            'sources': [{'source_id': 'rest-bad', 'kind': 'rest', 'locator_ref': 'accounting-bad'}],
        }, env=bad_env)['session_id']}, env=bad_env)
        bad_source, = bad['sources']
        assert bad_source['gaps'] == [{'partition': 1, 'code': 'authentication_failed'}]
        assert reads['unauthorized'] >= 1
        _assert_no_credentials(bad, 'intake_advance (wrong token)')

        diffs = Diffs()
        cross_source = verify_cross_source(project, url, token_ref, diffs,
                                           cross_reads, cross_unauthorized)
    return {'session': status, 'sources': observed['sources'], 'instance_count': preview['instance_count'],
            'rest_partial': rest, 'rest_requests': reads, 'postgres_included': bool(postgres_locator),
            'cross_source': cross_source}


def apply(report, project, args, context):
    started = time.time()
    report['sources'] = verify_sources(project, args.postgres_locator, args.postgres_user)
    _scan_for_credentials(project, args.output, report,
                          extra_roots=_mint_log_roots(project), since=started)
    diffs = report['sources']['cross_source']['diffs']
    if diffs:
        (args.output/'sources-diffs.json').write_text(
            json.dumps(diffs, ensure_ascii=False, indent=2))
        report['status'] = 'mismatched'
        (args.output/'sources-report-partial.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2))
        lines = [f'{item["object"]} | {item["field"]} | 期望 {item["expected"]!r} '
                 f'| 实际 {item["actual"]!r}' for item in diffs]
        raise RuntimeError(f'跨源金标比对失败，{len(lines)} 处差异（对象 | 字段 | 期望 | 实际）：\n'
                           + '\n'.join(lines))
    remove_not_verified(report, 'file processing')
