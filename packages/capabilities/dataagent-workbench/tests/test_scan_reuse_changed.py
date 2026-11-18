"""Changed scans must be re-extracted instead of reusing a verified mapping.

A verified mapping remembers text-extracted values as exact quotes.  The
second week's scan has the same page structure but a new invoice number and
amount, so some quotes moved.  Reuse must then be refused with a reason and
``intake_extract`` must rebuild the values.  An identical scan may still reuse
the verified mapping without re-extraction.
"""
from dataagent_contracts.core.refs import SourceAnchor
from dataagent_contracts.intake import SourceProfile, SourceSelection, WorkSpec
from dataagent_contracts.ontology import MappingSpec, ReviewDecision
from dataagent_ontology.identity import digest
from dataagent_workbench.bootstrap import Workbench
from dataagent_workbench.service_tools import invoke

SOURCE_ID = 'scan'
# Same structure fingerprint for both weeks: only the OCR text changes.
FINGERPRINT = digest(['scan', 'one scanned page'])


class StubProbeClient:
    """Return the prebuilt OCR profiles; the data layer is not needed."""

    def __init__(self, profile):
        self.profile = profile

    def probe(self, selection, ctx, workspace, *, previous=None, budget_seconds=None):
        return self.profile


def scan_profile(number, amount):
    """A one-page scanned invoice where OCR glues amount and currency."""
    token = f'{amount}CNY'
    text = f'Invoice {number}\nAmount: {token}'
    start = text.index(token)
    return SourceProfile(
        source_id=SOURCE_ID, source_revision='sha256:scan', kind='pdf',
        records=[{'Am0unt': token}], fields=['Am0unt'],
        anchors={'0.Am0unt': [SourceAnchor(
            source_ref=SOURCE_ID, source_revision='sha256:scan',
            selector={'kind': 'pdf_text_span', 'page': 1,
                      'char_start': start, 'char_end': start + len(token)})]},
        metadata={'structure_fingerprint': FINGERPRINT,
                  'pages': [{'page': 1, 'text': text}], 'total_pages': 1},
        total_partitions=1, completed_partitions=[1])


def start(wb, goal_id):
    goal = WorkSpec(id=goal_id, goal='接入采购资料', acceptance_criteria=['来源可核对'],
                    authorization_ref=wb.authorization)
    handle = wb.sessions.start([SourceSelection(
        source_id=SOURCE_ID, kind='file', locator_ref='scan.pdf')], goal, wb.ctx)
    return wb.intake.advance(handle.session_id, wb.ctx)


def extract(wb, session, number, amount):
    return invoke(wb, 'intake_extract', {
        'session_id': session.id, 'source_id': SOURCE_ID,
        'expected_revision': session.revision,
        'fields': [{'row': 0, 'name': name, 'page': 1, 'quote': quote}
                   for name, quote in [('number', number), ('amount', amount),
                                       ('currency', 'CNY')]],
    }).data


def proposal_for(request):
    source = request['sources'][0]
    return MappingSpec(
        id='candidate', revision='1', ontology_revision='procurement@1',
        source_fingerprint=source['structure_fingerprint'],
        bindings={'number': {'source_field': 'number'},
                  'amount': {'source_field': 'amount', 'transform': 'decimal'},
                  'currency': {'source_field': 'currency'}})


def save_first_scan(wb):
    session = start(wb, 'g1')
    request = extract(wb, session, 'INV-003', '1260.00')
    session = wb.sessions.get(session.id, wb.ctx)
    preview = wb.intake.submit_proposal(
        session.id, proposal_for(request), session.revision, wb.ctx)
    session = wb.sessions.get(session.id, wb.ctx)
    wb.intake.apply(session.id, ReviewDecision(
        preview_ref=preview.id + '@' + preview.revision,
        target_scope='mapping'), session.revision, wb.ctx)
    assert wb.sessions.get(session.id, wb.ctx).phase == 'saved'


def test_changed_scan_is_not_reused_and_is_extracted_again(tmp_path):
    wb = Workbench(tmp_path)
    wb.layer_client = StubProbeClient(scan_profile('INV-003', '1260.00'))
    save_first_scan(wb)

    # Same structure, but both the document number and amount changed.  The
    # old quotes for number and amount cannot be relocated; currency "CNY"
    # still resolves, so this also covers a partial replay.
    wb.layer_client = StubProbeClient(scan_profile('INV-004', '1580.00'))
    session = start(wb, 'g2')
    assert session.phase == 'needs_input'
    assert session.next_actions == ['intake_extract']
    view = wb.intake.view(session.id, wb.ctx)
    assert view['mapping_reused'] is False
    assert view['preview'] is None
    assert 'number' in view['mapping_reuse_reason']
    assert 'amount' in view['mapping_reuse_reason']

    issue = next(item for item in session.issues
                 if item['code'] == 'intake.mapping_replay_failed')
    assert issue['source_id'] == SOURCE_ID
    assert issue['next_action'] == 'intake_extract'
    assert {field['name'] for field in issue['fields']} == {'number', 'amount'}

    # A partial replay must not be persisted: the fresh profile still carries
    # only the OCR token, not the old number/amount/currency fields.
    profile, = view['profiles']
    assert profile['records'] == [{'Am0unt': '1580.00CNY'}]
    assert not {'number', 'amount', 'currency'} & set(profile['fields'])

    # The tool payload, not only the internal session, carries the refusal.
    advanced = invoke(wb, 'intake_advance', {'session_id': session.id})
    assert advanced.data['mapping_reused'] is False
    assert advanced.data['mapping_reuse_reason']
    assert advanced.data['mapping_reuse_blocked']['next_action'] == 'intake_extract'

    # The reason sends the agent back through the extraction flow, which can
    # read the new values from the changed original.
    request = extract(wb, session, 'INV-004', '1580.00')
    assert request['sources'][0]['samples'][0]['number'] == 'INV-004'
    session = wb.sessions.get(session.id, wb.ctx)
    preview = wb.intake.submit_proposal(
        session.id, proposal_for(request), session.revision, wb.ctx)
    assert preview.issues == []
    assert preview.instances[0].values['number'] == 'INV-004'
    assert str(preview.instances[0].values['amount']) == '1580.00'
    session = wb.sessions.get(session.id, wb.ctx)
    assert not wb.intake.view(session.id, wb.ctx)['mapping_reused']
    wb.intake.apply(session.id, ReviewDecision(
        preview_ref=preview.id + '@' + preview.revision,
        target_scope='mapping'), session.revision, wb.ctx)
    assert wb.sessions.get(session.id, wb.ctx).phase == 'saved'


def test_identical_scan_still_reuses_verified_mapping(tmp_path):
    wb = Workbench(tmp_path)
    wb.layer_client = StubProbeClient(scan_profile('INV-003', '1260.00'))
    save_first_scan(wb)

    wb.layer_client = StubProbeClient(scan_profile('INV-003', '1260.00'))
    session = start(wb, 'g2')
    assert session.phase == 'preview'
    view = wb.intake.view(session.id, wb.ctx)
    assert view['mapping_reused'] is True
    assert view['mapping_reuse_reason'] is None
    profile, = view['profiles']
    assert {'number', 'amount', 'currency'} <= set(profile['fields'])
    preview = view['preview']
    assert preview['issues'] == []
    assert preview['instances'][0]['values']['number'] == 'INV-003'
    assert preview['instances'][0]['values']['amount'] == '1260.00'
