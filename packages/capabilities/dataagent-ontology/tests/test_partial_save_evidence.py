from dataagent_contracts.core import CallContext
from dataagent_contracts.ontology import MappingSpec, OntologyRevision, ReviewDecision
from dataagent_runtime.adapters.workbench_sqlite import SqliteWorkbenchStore
from dataagent_runtime.ports.workbench_store import ChangeSet
from dataagent_ontology.service import OntologyService
from test_mapping_semantics import profile


def test_partial_save_keeps_relation_assertions_for_saved_entities(tmp_path):
    ctx = CallContext(request_id='r', scope_ref='T', subject_ref='owner',
                      authorization_ref='auth')
    store = SqliteWorkbenchStore(tmp_path / 'db')
    service = OntologyService(store, scope='T', subject='owner', authorization='auth')
    ontology = OntologyRevision(
        id='invoice', revision='1', entity_type='Invoice',
        properties={
            'number': {'value_type': 'string', 'required': True},
            'company': {'value_type': 'string', 'required': True},
            'amount': {'value_type': 'decimal', 'required': True},
        },
        identity_fields=['company', 'number'],
        relations={'price': ['invoice', 'amount', 'currency']},
    )
    service.register(ontology, ctx)
    mapping = MappingSpec(
        id='m', revision='1', ontology_revision='invoice@1',
        source_fingerprint='schema',
        bindings={
            'number': {'source_field': 'number'},
            'company': {'source_field': 'company'},
            'amount': {'source_field': 'minor', 'transform': 'minor_to_major'},
        },
        relation_bindings={'price': {
            'invoice': {'source_field': '$entity'},
            'amount': {'source_field': 'minor'},
            'currency': {'source_field': 'currency'},
        }},
    )
    source = profile([
        {'number': 'A', 'company': 'C', 'minor': '100', 'currency': 'CNY'},
        {'number': 'B', 'company': 'C', 'minor': '200', 'currency': 'CNY'},
        {'number': 'B', 'company': 'C', 'minor': '300', 'currency': 'CNY'},
    ])
    preview = service.preview(mapping, [source], ctx)
    clean = next(item for item in preview.instances if item.values['number'] == 'A')
    conflicted = next(item for item in preview.instances if item.values['number'] == 'B')

    receipt, writes = service.prepare_partial_save(
        ReviewDecision(preview_ref=preview.id + '@' + preview.revision,
                       target_scope='mapping'),
        preview.revision, ctx,
        plan={'saved': [{'entity_id': clean.id}],
              'suspended': [{'entity_id': conflicted.id}]},
    )
    assert receipt.extensions['intake.partial_save']['release_ref'].startswith('release:')
    store.commit(ChangeSet(writes=writes))

    assertions = {row['id'] for row in store.query('assertion', 'T')}
    facts = [row['body'] for row in store.query('fact', 'T')]
    assert facts
    assert any(fact['relation'] == 'price' for fact in facts)
    assert all(set(fact['assertion_refs']) <= assertions for fact in facts)
    assert all({role['value'] for role in fact['role_bindings']
                if role['value_type'] == 'reference'} == {clean.id}
               for fact in facts)
