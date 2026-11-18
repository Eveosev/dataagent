"""Clause paragraphs become typed records with paragraph anchors (D3).

A synthetic travel-expense policy keeps its standards in one prose clause
instead of a table: the agent reads the disclosed clause candidate and submits
one record per standard, every value quoting its evidence.  The service never
trusts that submission: quotes must match the observed paragraph text
verbatim, properties must belong to the pinned concept and missing required
attributes stay explicit gaps.  The accepted records enter the normal mapping
preview and save flow, and a later intake of the same file replays them or
refuses reuse with a Chinese reason when the file changed.
"""
import io
import zipfile
from pathlib import Path

import pytest

from dataagent_contracts.intake import SourceAnchor, SourceProfile
from dataagent_contracts.ontology import MappingSpec, OntologyRevision, ReviewDecision
from dataagent_ontology.identity import digest
from dataagent_workbench.adapters.layer_client import LayerClient
from dataagent_workbench.bootstrap import Workbench
from dataagent_workbench.service_tools import invoke


PACKAGES = Path(__file__).resolve().parents[2]

CLAUSE = ('第三条 一类城市：经理级住宿 800 元/晚，员工级住宿 500 元/晚；'
          '二类城市：经理级住宿 600 元/晚，员工级住宿 400 元/晚。')
PARAGRAPHS = [
    ('差旅报销标准', 1),
    ('总则', 2),
    ('第一条 本标准适用于全体员工出差费用报销。', None),
    ('第二条 城市等级分为一类、二类两档。', None),
    ('费用标准', 2),
    ('CLAUSE', None),
    ('附则', 2),
    ('第四条 本标准自发布之日起执行。', None),
]
CLAUSE_PARAGRAPH = 6
PROPERTY_NAMES = ['城市等级', '职级', '费用类型', '限额', '币种']


def _offset(quote, occurrence=1):
    start = -1
    for _ in range(occurrence):
        start = CLAUSE.index(quote, start + 1)
    return start


def _span_end(quote, occurrence=1):
    return _offset(quote, occurrence) + len(quote)


def _record_span(rank, rank_occurrence, currency_occurrence):
    """The clause fragment one standard is attributed to, e.g. 经理级住宿 800 元/晚."""
    return {'paragraph': CLAUSE_PARAGRAPH,
            'char_start': _offset(rank, rank_occurrence),
            'char_end': _span_end('元/晚', currency_occurrence)}


def clause_records():
    """Four standards read from one clause; repeated quotes cite char_start."""
    return [
        {'record_span': _record_span('经理级', 1, 1),
         'values': [
            {'property': '城市等级', 'value': '一类', 'quote': '一类城市',
             'paragraph': CLAUSE_PARAGRAPH},
            {'property': '职级', 'value': '经理级', 'quote': '经理级',
             'paragraph': CLAUSE_PARAGRAPH, 'char_start': _offset('经理级', 1)},
            {'property': '费用类型', 'value': '住宿', 'quote': '住宿',
             'paragraph': CLAUSE_PARAGRAPH, 'char_start': _offset('住宿', 1)},
            {'property': '限额', 'value': '800', 'quote': '800',
             'paragraph': CLAUSE_PARAGRAPH},
            {'property': '币种', 'value': 'CNY', 'quote': '元/晚',
             'paragraph': CLAUSE_PARAGRAPH, 'char_start': _offset('元/晚', 1)},
        ]},
        {'record_span': _record_span('员工级', 1, 2),
         'values': [
            {'property': '城市等级', 'value': '一类', 'quote': '一类城市',
             'paragraph': CLAUSE_PARAGRAPH},
            {'property': '职级', 'value': '员工级', 'quote': '员工级',
             'paragraph': CLAUSE_PARAGRAPH, 'char_start': _offset('员工级', 1)},
            {'property': '费用类型', 'value': '住宿', 'quote': '住宿',
             'paragraph': CLAUSE_PARAGRAPH, 'char_start': _offset('住宿', 2)},
            {'property': '限额', 'value': '500', 'quote': '500',
             'paragraph': CLAUSE_PARAGRAPH},
            {'property': '币种', 'value': 'CNY', 'quote': '元/晚',
             'paragraph': CLAUSE_PARAGRAPH, 'char_start': _offset('元/晚', 2)},
        ]},
        {'record_span': _record_span('经理级', 2, 3),
         'values': [
            {'property': '城市等级', 'value': '二类', 'quote': '二类城市',
             'paragraph': CLAUSE_PARAGRAPH},
            {'property': '职级', 'value': '经理级', 'quote': '经理级',
             'paragraph': CLAUSE_PARAGRAPH, 'char_start': _offset('经理级', 2)},
            {'property': '费用类型', 'value': '住宿', 'quote': '住宿',
             'paragraph': CLAUSE_PARAGRAPH, 'char_start': _offset('住宿', 3)},
            {'property': '限额', 'value': '600', 'quote': '600',
             'paragraph': CLAUSE_PARAGRAPH},
            {'property': '币种', 'value': 'CNY', 'quote': '元/晚',
             'paragraph': CLAUSE_PARAGRAPH, 'char_start': _offset('元/晚', 3)},
        ]},
        {'record_span': _record_span('员工级', 2, 4),
         'values': [
            {'property': '城市等级', 'value': '二类', 'quote': '二类城市',
             'paragraph': CLAUSE_PARAGRAPH},
            {'property': '职级', 'value': '员工级', 'quote': '员工级',
             'paragraph': CLAUSE_PARAGRAPH, 'char_start': _offset('员工级', 2)},
            {'property': '费用类型', 'value': '住宿', 'quote': '住宿',
             'paragraph': CLAUSE_PARAGRAPH, 'char_start': _offset('住宿', 4)},
            {'property': '限额', 'value': '400', 'quote': '400',
             'paragraph': CLAUSE_PARAGRAPH},
            {'property': '币种', 'value': 'CNY', 'quote': '元/晚',
             'paragraph': CLAUSE_PARAGRAPH, 'char_start': _offset('元/晚', 4)},
        ]},
    ]


def _docx_zip(document):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml', (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            '</Types>'))
        archive.writestr('_rels/.rels', (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            '</Relationships>'))
        archive.writestr('word/document.xml', document)
    return buffer.getvalue()


def _paragraph(text, level=None):
    # An explicit outline level marks the heading without needing styles.xml.
    properties = (f'<w:pPr><w:outlineLvl w:val="{level - 1}"/></w:pPr>'
                  if level is not None else '')
    return f'<w:p>{properties}<w:r><w:t>{text}</w:t></w:r></w:p>'


def write_policy_docx(path, first_limit='800'):
    text = CLAUSE if first_limit == '800' else CLAUSE.replace('800', first_limit)
    parts = [_paragraph(text if content == 'CLAUSE' else content, level)
             for content, level in PARAGRAPHS]
    document = (
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:body>' + ''.join(parts) + '<w:sectPr/></w:body></w:document>')
    path.write_bytes(_docx_zip(document))


def expense_policy_ontology():
    return OntologyRevision.model_validate({
        'id': 'expense-policy', 'revision': '1',
        'concepts': {'费用标准': {
            'entity_type': 'ExpenseStandard',
            'properties': {'城市等级': {'value_type': 'string'},
                           '职级': {'value_type': 'string'},
                           '费用类型': {'value_type': 'string'},
                           '限额': {'value_type': 'decimal', 'required': True},
                           '币种': {'value_type': 'string'}},
            'identity_fields': ['城市等级', '职级', '费用类型']}}})


def allowed_policy():
    # 'text' is the paragraphs record set field; allowing it discloses the
    # clause text the agent quotes from.
    return {'policy': ['text', *PROPERTY_NAMES]}


def workbench(tmp_path, allowed):
    return Workbench(tmp_path, layer_client=LayerClient(PACKAGES / 'dataagent-data'),
                     allowed_model_fields=allowed)


def start_policy_session(wb, goal='把条款段落整理成费用标准记录'):
    result = invoke(wb, 'intake_start', {
        'goal': goal,
        'target': {'ontology_id': 'expense-policy', 'concept': '费用标准'},
        'sources': [{'source_id': 'policy', 'kind': 'file', 'locator_ref': 'policy.docx'}],
    })
    return wb.intake.advance(result.data['session_id'], wb.ctx)


def setup(tmp_path, allowed=None, first_limit='800'):
    write_policy_docx(tmp_path / 'policy.docx', first_limit)
    wb = workbench(tmp_path, allowed_policy() if allowed is None else allowed)
    wb.ontology.register(expense_policy_ontology(), wb.ctx)
    return wb, start_policy_session(wb)


def extract_records(wb, session, records, source_id='policy'):
    return invoke(wb, 'intake_extract_records', {
        'session_id': session.id, 'source_id': source_id,
        'expected_revision': session.revision, 'records': records})


def standard_proposal(wb, session):
    request = wb.intake.inference_request(session.id, wb.ctx)
    return MappingSpec(id='candidate', revision='1', ontology_revision='expense-policy@1',
                       concept='费用标准',
                       source_fingerprint=request['sources'][0]['structure_fingerprint'],
                       bindings={'城市等级': {'source_field': '城市等级'},
                                 '职级': {'source_field': '职级'},
                                 '费用类型': {'source_field': '费用类型'},
                                 '限额': {'source_field': '限额', 'transform': 'decimal'},
                                 '币种': {'source_field': '币种'}})


def save_clause_mapping(wb, session, records=None):
    extract_records(wb, session, clause_records() if records is None else records)
    session = wb.sessions.get(session.id, wb.ctx)
    preview = wb.intake.submit_proposal(session.id, standard_proposal(wb, session),
                                        session.revision, wb.ctx)
    assert not preview.issues
    session = wb.sessions.get(session.id, wb.ctx)
    wb.intake.apply(session.id, ReviewDecision(
        preview_ref=preview.id + '@' + preview.revision, target_scope='mapping'),
        session.revision, wb.ctx)
    assert wb.sessions.get(session.id, wb.ctx).phase == 'saved'


def test_one_clause_yields_multiple_records_with_replayable_anchors(tmp_path):
    wb, session = setup(tmp_path)
    result = extract_records(wb, session, clause_records()).data

    summary = result['clause_records']
    assert summary['record_set'] == 'clause_records:费用标准'
    assert summary['count'] == 4 and summary['gaps'] == []
    # 正常归属：每条记录的非共享引文都在自己的 record_span 内。
    assert summary['attribution_issues'] == []
    shared = {(tuple(item['properties']), tuple(item['records']), item['value'])
              for item in summary['shared_spans']}
    # The clause names each city class once for two standards (one per rank):
    # those two source spans are shared evidence across their records.  The
    # rank and expense-type quotes each cite a different occurrence, so they
    # are not shared.
    assert (('城市等级',), (0, 1), '一类') in shared
    assert (('城市等级',), (2, 3), '二类') in shared
    assert len(summary['shared_spans']) == 2

    view = wb.intake.view(session.id, wb.ctx)
    profile = view['profiles'][0]
    assert profile['metadata']['selected_record_set'] == 'clause_records:费用标准'
    entry = profile['metadata']['record_sets']['clause_records:费用标准']
    assert entry['kind'] == 'clause' and entry['concept'] == '费用标准'
    assert len(profile['records']) == 4
    assert profile['records'][0]['限额'] == '800'

    # Every value's anchor replays to the exact clause paragraph span.
    paragraph = profile['metadata']['paragraphs'][CLAUSE_PARAGRAPH - 1]
    assert paragraph['paragraph'] == CLAUSE_PARAGRAPH
    for row_index, record in enumerate(clause_records()):
        for item in record['values']:
            anchor = profile['anchors'][f'{row_index}.{item["property"]}'][0]
            selector = anchor['selector']
            assert selector['kind'] == 'text_span'
            assert selector['unit_ref'] == f'paragraph:{CLAUSE_PARAGRAPH}'
            assert paragraph['text'][selector['char_start']:selector['char_end']] \
                == item['quote']
    # The remembered specs keep what a later intake replays.
    remembered = profile['metadata']['clause_records']
    assert remembered['concept'] == '费用标准'
    assert remembered['records'][0]['values'][3]['quote'] == '800'

    # The records enter the normal mapping preview and save flow.
    session = wb.sessions.get(session.id, wb.ctx)
    preview = wb.intake.submit_proposal(session.id, standard_proposal(wb, session),
                                        session.revision, wb.ctx)
    assert len(preview.instances) == 4 and not preview.issues
    first = preview.instances[0]
    assert first.values['城市等级'] == '一类'
    assert str(first.values['限额']) == '800'
    span = first.source_anchors['限额'][0].selector
    assert span.unit_ref == 'paragraph:6'
    assert paragraph['text'][span.char_start:span.char_end] == '800'
    session = wb.sessions.get(session.id, wb.ctx)
    wb.intake.apply(session.id, ReviewDecision(
        preview_ref=preview.id + '@' + preview.revision, target_scope='mapping'),
        session.revision, wb.ctx)
    assert wb.sessions.get(session.id, wb.ctx).phase == 'saved'


@pytest.mark.parametrize(('change', 'message'), [
    # A quote that does not match the observed text at its cited position.
    (lambda r: r[0]['values'][3].update(quote='999', char_start=_offset('800')),
     '引文与第 6 段原文不一致'),
    # A position outside the observed paragraph.
    (lambda r: r[0]['values'][3].update(quote='800', char_start=10000),
     '定位超出第 6 段原文范围'),
    # A property the pinned concept does not define.
    (lambda r: r[0]['values'][0].update(property='备注'), '不在目标概念中'),
    # A value the ontology value type cannot parse.
    (lambda r: r[0]['values'][3].update(value='免费'), '无法按目标类型解析'),
    # A record without its identity fields cannot name an object.
    (lambda r: r[0].update(values=[r[0]['values'][3]]), '记录缺少身份字段'),
    # A paragraph this task never observed.
    (lambda r: r[0]['values'][3].update(paragraph=60), '第 60 段未在本任务观测到'),
    # The same source span must carry the same value in every record.
    (lambda r: r[2]['values'][0].update(value='二类', quote='一类城市',
                                        char_start=_offset('一类城市')),
     '同一引文必须携带同一个值'),
    # The same span reused for a different property must still carry the
    # same value: the span, not the property name, identifies the evidence.
    (lambda r: r[1]['values'][1].update(quote='一类城市', value='员工级',
                                        char_start=None),
     '同一引文必须携带同一个值'),
    # A number, amount or date must equal what its own quote parses to.
    (lambda r: r[0]['values'][3].update(value='900'),
     '提交值与引文不一致'),
    # A numeric property whose quote is not itself a number: the value can
    # no longer be verified against the source, so it is refused.
    (lambda r: r[0]['values'][3].update(quote='住宿', value='800',
                                        char_start=_offset('住宿', 1)),
     '引文无法按目标类型解析'),
    # An identity value that is empty or whitespace-only names no object.
    (lambda r: r[0]['values'][0].update(value='   '),
     '身份字段的值不能为空'),
    # A quote that is not in the paragraph at all and has no char_start.
    (lambda r: r[0]['values'][3].update(quote='999', char_start=None),
     '引文在第 6 段中不唯一或不存在'),
    # A record_span outside the observed paragraph.
    (lambda r: r[0]['record_span'].update(char_start=50, char_end=10000),
     '记录区间超出第 6 段原文范围'),
])
def test_invalid_clause_submissions_are_rejected(tmp_path, change, message):
    wb, session = setup(tmp_path)
    records = clause_records()
    change(records)
    with pytest.raises(ValueError, match=message):
        extract_records(wb, session, records)
    # A rejected submission leaves the task untouched.
    assert wb.sessions.get(session.id, wb.ctx).revision == session.revision
    view = wb.intake.view(session.id, wb.ctx)
    assert view['profiles'][0]['metadata'].get('selected_record_set') == 'paragraphs'


def test_missing_required_property_is_a_gap_not_an_invention(tmp_path):
    wb, session = setup(tmp_path)
    records = clause_records()
    records[0]['values'] = [item for item in records[0]['values']
                             if item['property'] != '限额']
    result = extract_records(wb, session, records).data

    summary = result['clause_records']
    assert summary['gaps'] == [{'record': 0, 'property': '限额'}]
    view = wb.intake.view(session.id, wb.ctx)
    profile = view['profiles'][0]
    # The record exists, but the clause never stated the limit: no value.
    assert '限额' not in profile['records'][0]
    assert '限额' in profile['fields']

    # The gap surfaces as a preview issue on that record and can be disposed.
    session = wb.sessions.get(session.id, wb.ctx)
    preview = wb.intake.submit_proposal(session.id, standard_proposal(wb, session),
                                        session.revision, wb.ctx)
    missing = [issue for issue in preview.issues
               if issue.get('code') == 'ontology.required_value_missing']
    assert missing and missing[0]['row'] == 0 and missing[0]['target'] == '限额'
    assert len(preview.instances) == 4
    assert preview.instances[0].values.get('限额') is None
    assert '限额' in preview.instances[0].unresolved

    body = wb.intake.view(session.id, wb.ctx)['preview']
    options = wb.intake.disposition_options(wb.sessions.get(session.id, wb.ctx), body)
    assert [option for option in options
            if option['action'] == 'exclude_record' and option['record'] == 0]
    session = wb.sessions.get(session.id, wb.ctx)
    invoke(wb, 'intake_dispose', {
        'session_id': session.id, 'expected_revision': session.revision,
        'action': 'exclude_record', 'source_id': 'policy', 'record': 0,
        'reason': '该条款记录缺限额，先排除'})
    session = wb.sessions.get(session.id, wb.ctx)
    preview = wb.intake.submit_proposal(session.id, standard_proposal(wb, session),
                                        session.revision, wb.ctx)
    assert len(preview.instances) == 3 and not preview.issues


def test_clause_records_require_paragraph_text_disclosure(tmp_path):
    # A policy that allows the table columns but not the paragraph text field
    # keeps the clause prose hidden, exactly like D2b discovery evidence.
    wb, session = setup(tmp_path, allowed={'policy': PROPERTY_NAMES})
    with pytest.raises(PermissionError):
        extract_records(wb, session, clause_records())


def test_clause_records_allowed_without_a_disclosure_policy(tmp_path):
    # No model-context.json at all is the local-owner mode; the mapping path
    # (intake_extract / extract_fields) grants the text in that case.
    write_policy_docx(tmp_path / 'policy.docx')
    wb = workbench(tmp_path, None)
    wb.ontology.register(expense_policy_ontology(), wb.ctx)
    session = start_policy_session(wb)
    result = extract_records(wb, session, clause_records()).data
    assert result['clause_records']['count'] == 4


def test_tightened_disclosure_refuses_clause_record_replay(tmp_path):
    # 提交与重放同一口径：显式策略不含段落文本字段时都拒绝。这里先在放行
    # 披露的工作区保存，再于同一工作区收紧策略，重放被拒绝并给出中文原因。
    wb, session = setup(tmp_path)
    save_clause_mapping(wb, session)
    tight = workbench(tmp_path, {'policy': PROPERTY_NAMES})
    second = start_policy_session(tight)
    assert second.phase == 'needs_input'
    assert second.next_actions == ['intake_extract_records']
    issue = next(item for item in second.issues
                 if item['code'] == 'intake.mapping_replay_failed')
    assert '段落文本不在披露范围内' in issue['detail'] or \
        any('段落文本不在披露范围内' in field.get('reason', '')
            for field in issue['fields'])
    view = tight.intake.view(second.id, tight.ctx)
    assert view['mapping_reused'] is False
    assert view['preview'] is None


def test_swapped_limit_quotes_flag_attribution_and_dispose(tmp_path):
    # 第三条里把 800 与 500 的引文和值互换：这两条记录的限额引文落在对方
    # 的记录区间里，归属无法核实，但整批不被拒绝、其余记录不受影响。
    wb, session = setup(tmp_path)
    records = clause_records()
    records[0]['values'][3] = {'property': '限额', 'value': '500', 'quote': '500',
                               'paragraph': CLAUSE_PARAGRAPH}
    records[1]['values'][3] = {'property': '限额', 'value': '800', 'quote': '800',
                               'paragraph': CLAUSE_PARAGRAPH}
    result = extract_records(wb, session, records).data
    flagged = {item['record'] for item in result['clause_records']['attribution_issues']}
    assert flagged == {0, 1}
    assert all('引文落在记录区间之外' in item['reason']
               for item in result['clause_records']['attribution_issues'])
    # The records are still installed; only their attribution is unverified.
    view = wb.intake.view(session.id, wb.ctx)
    assert len(view['profiles'][0]['records']) == 4

    session = wb.sessions.get(session.id, wb.ctx)
    preview = wb.intake.submit_proposal(session.id, standard_proposal(wb, session),
                                        session.revision, wb.ctx)
    issues = [issue for issue in preview.issues
              if issue.get('code') == 'record_attribution_unverified']
    assert {issue['row'] for issue in issues} == {0, 1}
    assert all(issue.get('entity_id') for issue in issues)
    assert len(preview.instances) == 4

    # The flagged records can be disposed; the unflagged ones then save.
    body = wb.intake.view(session.id, wb.ctx)['preview']
    options = wb.intake.disposition_options(wb.sessions.get(session.id, wb.ctx), body)
    assert {option['record'] for option in options
            if option['action'] == 'exclude_record'} == {0, 1}
    for row in (0, 1):
        session = wb.sessions.get(session.id, wb.ctx)
        invoke(wb, 'intake_dispose', {
            'session_id': session.id, 'expected_revision': session.revision,
            'action': 'exclude_record', 'source_id': 'policy', 'record': row,
            'reason': '限额引文归属未核实，先排除'})
    session = wb.sessions.get(session.id, wb.ctx)
    preview = wb.intake.submit_proposal(session.id, standard_proposal(wb, session),
                                        session.revision, wb.ctx)
    assert len(preview.instances) == 2 and not preview.issues
    session = wb.sessions.get(session.id, wb.ctx)
    wb.intake.apply(session.id, ReviewDecision(
        preview_ref=preview.id + '@' + preview.revision, target_scope='mapping'),
        session.revision, wb.ctx)
    assert wb.sessions.get(session.id, wb.ctx).phase == 'saved'


def test_changed_source_breaks_clause_record_replay(tmp_path):
    wb, session = setup(tmp_path)
    save_clause_mapping(wb, session)

    # Same structure, but the first limit changed 800 -> 900: the recorded
    # quote no longer resolves and reuse must be refused with a reason.
    write_policy_docx(tmp_path / 'policy.docx', '900')
    second = start_policy_session(wb, goal='再次接入差旅报销标准')
    assert second.phase == 'needs_input'
    assert second.next_actions == ['intake_extract_records']
    issue = next(item for item in second.issues
                 if item['code'] == 'intake.mapping_replay_failed')
    assert issue['next_action'] == 'intake_extract_records'
    assert issue['fields'][0]['name'] == '限额'
    assert '引文' in issue['detail'] or '引文' in issue['fields'][0]['reason']
    view = wb.intake.view(second.id, wb.ctx)
    assert view['mapping_reused'] is False
    assert view['preview'] is None
    # The stale clause records were not persisted onto the fresh observation.
    profile, = view['profiles']
    assert profile['metadata']['selected_record_set'] == 'paragraphs'
    assert '限额' not in profile['fields']

    # The agent can read the new value from the changed original.
    records = clause_records()
    records[0]['values'][3] = {'property': '限额', 'value': '900', 'quote': '900',
                               'paragraph': CLAUSE_PARAGRAPH}
    save_clause_mapping(wb, second, records)


def test_unchanged_source_replays_clause_records_and_reuses_the_mapping(tmp_path):
    wb, session = setup(tmp_path)
    save_clause_mapping(wb, session)

    second = start_policy_session(wb, goal='再次接入差旅报销标准')
    assert second.phase == 'preview'
    view = wb.intake.view(second.id, wb.ctx)
    assert view['mapping_reused'] is True
    assert view['mapping_reuse_reason'] is None
    profile, = view['profiles']
    assert profile['metadata']['selected_record_set'] == 'clause_records:费用标准'
    assert len(profile['records']) == 4
    preview = view['preview']
    assert preview['issues'] == []
    assert str(preview['instances'][0]['values']['限额']) == '800'


class StubProbeClient:
    """Return a prebuilt text-PDF profile; the data layer is not needed."""

    def __init__(self, profile):
        self.profile = profile

    def probe(self, selection, ctx, workspace, *, previous=None, budget_seconds=None):
        return self.profile


def lodging_ontology():
    return OntologyRevision.model_validate({
        'id': 'pdf-policy', 'revision': '1',
        'concepts': {'住宿标准': {
            'entity_type': 'LodgingStandard',
            'properties': {'城市': {'value_type': 'string'},
                           '限额': {'value_type': 'decimal', 'required': True}},
            'identity_fields': ['城市']}}})


PDF_TEXT = '报销制度\n第三条 住宿标准为每晚 400 元，适用于一类城市。'


def pdf_profile():
    return SourceProfile(
        source_id='manual', source_revision='sha256:manual', kind='pdf',
        records=[{'text': PDF_TEXT}], fields=['text'],
        anchors={'0.text': [SourceAnchor(
            source_ref='manual', source_revision='sha256:manual',
            selector={'kind': 'pdf_text_span', 'page': 1,
                      'char_start': 0, 'char_end': len(PDF_TEXT)})]},
        metadata={'structure_fingerprint': digest(['manual', 'pdf-clause']),
                  'pages': [{'page': 1, 'text': PDF_TEXT, 'method': 'text'}],
                  'total_pages': 1},
        total_partitions=1, completed_partitions=[1])


def test_text_pdf_clause_records_minimal_positive(tmp_path):
    wb = Workbench(tmp_path)
    wb.layer_client = StubProbeClient(pdf_profile())
    wb.ontology.register(lodging_ontology(), wb.ctx)
    task = invoke(wb, 'intake_start', {
        'goal': '从文本 PDF 条款生成记录',
        'target': {'ontology_id': 'pdf-policy', 'concept': '住宿标准'},
        'sources': [{'source_id': 'manual', 'kind': 'file',
                     'locator_ref': 'manual.pdf'}]})
    session = wb.intake.advance(task.data['session_id'], wb.ctx)
    result = invoke(wb, 'intake_extract_records', {
        'session_id': session.id, 'source_id': 'manual',
        'expected_revision': session.revision,
        'records': [{'record_span': {'page': 1,
                                     'char_start': PDF_TEXT.index('第三条'),
                                     'char_end': len(PDF_TEXT)},
                     'values': [
            {'property': '城市', 'value': '一类城市', 'quote': '一类城市', 'page': 1},
            {'property': '限额', 'value': '400', 'quote': '400', 'page': 1},
        ]}]}).data
    assert result['clause_records'] == {
        'record_set': 'clause_records:住宿标准', 'count': 1,
        'fields': ['城市', '限额'], 'gaps': [], 'shared_spans': [],
        'attribution_issues': []}

    view = wb.intake.view(session.id, wb.ctx)
    profile = view['profiles'][0]
    selector = profile['anchors']['0.限额'][0]['selector']
    assert selector['kind'] == 'pdf_text_span' and selector['page'] == 1
    assert PDF_TEXT[selector['char_start']:selector['char_end']] == '400'

    session = wb.sessions.get(session.id, wb.ctx)
    request = wb.intake.inference_request(session.id, wb.ctx)
    preview = wb.intake.submit_proposal(session.id, MappingSpec(
        id='candidate', revision='1', ontology_revision='pdf-policy@1',
        concept='住宿标准',
        source_fingerprint=request['sources'][0]['structure_fingerprint'],
        bindings={'城市': {'source_field': '城市'},
                  '限额': {'source_field': '限额', 'transform': 'decimal'}}),
        session.revision, wb.ctx)
    assert len(preview.instances) == 1 and not preview.issues
    assert str(preview.instances[0].values['限额']) == '400'


PDF_LINES = ['Travel Expense Policy',
             'Article 3: First-class city lodging limit is 400 CNY per night.']


def write_text_pdf(path, lines):
    """A minimal one-page text PDF; the probe extracts its text layer."""
    stream = ('BT\n/F1 12 Tf\n72 720 Td\n14 TL\n'
              + ''.join(f'({line}) Tj\nT*\n' for line in lines) + 'ET\n')
    objects = [
        '<< /Type /Catalog /Pages 2 0 R >>',
        '<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] '
        '/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
        '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
        f'<< /Length {len(stream)} >>\nstream\n{stream}endstream',
    ]
    out = bytearray(b'%PDF-1.4\n')
    offsets = []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += f'{number} 0 obj\n{body}\nendobj\n'.encode()
    xref = len(out)
    out += f'xref\n0 {len(objects) + 1}\n0000000000 65535 f \n'.encode()
    for offset in offsets:
        out += f'{offset:010d} 00000 n \n'.encode()
    out += (f'trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n'
            f'startxref\n{xref}\n%%EOF\n').encode()
    path.write_bytes(bytes(out))


def test_real_text_pdf_clause_records_end_to_end(tmp_path):
    write_text_pdf(tmp_path / 'policy.pdf', PDF_LINES)
    wb = workbench(tmp_path, {'policy': ['text', '城市', '限额']})
    wb.ontology.register(lodging_ontology(), wb.ctx)
    task = invoke(wb, 'intake_start', {
        'goal': '从文本 PDF 条款生成住宿标准记录',
        'target': {'ontology_id': 'pdf-policy', 'concept': '住宿标准'},
        'sources': [{'source_id': 'policy', 'kind': 'file',
                     'locator_ref': 'policy.pdf'}]})
    session = wb.intake.advance(task.data['session_id'], wb.ctx)
    # The agent reads the observed page text and attributes one record to the
    # clause line it sits in.
    page_text = (wb.intake.view(session.id, wb.ctx)['profiles'][0]
                 ['metadata']['pages'][0]['text'])
    result = invoke(wb, 'intake_extract_records', {
        'session_id': session.id, 'source_id': 'policy',
        'expected_revision': session.revision,
        'records': [{'record_span': {'page': 1,
                                     'char_start': page_text.index('Article 3'),
                                     'char_end': page_text.index('per night.')
                                     + len('per night.')},
                     'values': [
            {'property': '城市', 'value': 'First-class', 'quote': 'First-class',
             'page': 1},
            {'property': '限额', 'value': '400', 'quote': '400', 'page': 1},
        ]}]}).data
    assert result['clause_records']['count'] == 1
    assert result['clause_records']['attribution_issues'] == []

    view = wb.intake.view(session.id, wb.ctx)
    profile = view['profiles'][0]
    page = profile['metadata']['pages'][0]
    selector = profile['anchors']['0.限额'][0]['selector']
    assert selector['kind'] == 'pdf_text_span' and selector['page'] == 1
    assert page['text'][selector['char_start']:selector['char_end']] == '400'

    session = wb.sessions.get(session.id, wb.ctx)
    request = wb.intake.inference_request(session.id, wb.ctx)
    preview = wb.intake.submit_proposal(session.id, MappingSpec(
        id='candidate', revision='1', ontology_revision='pdf-policy@1',
        concept='住宿标准',
        source_fingerprint=request['sources'][0]['structure_fingerprint'],
        bindings={'城市': {'source_field': '城市'},
                  '限额': {'source_field': '限额', 'transform': 'decimal'}}),
        session.revision, wb.ctx)
    assert len(preview.instances) == 1 and not preview.issues
    assert preview.instances[0].values['城市'] == 'First-class'
    assert str(preview.instances[0].values['限额']) == '400'
