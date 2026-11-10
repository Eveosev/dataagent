import pytest
from dataagent_contracts.core import CallContext,VersionedRef
from dataagent_contracts.ontology import ReviewDecision
from dataagent_runtime.adapters.workbench_sqlite import SqliteWorkbenchStore
from dataagent_runtime.ports.workbench_store import VersionConflict
from dataagent_ontology.service import OntologyService
from test_mapping_semantics import ontology,mapping,profile


def setup(tmp_path):
    ctx=CallContext(request_id='r',scope_ref='T',subject_ref='owner',authorization_ref='auth')
    store=SqliteWorkbenchStore(tmp_path/'db')
    service=OntologyService(store,scope='T',subject='owner',authorization='auth')
    service.register(ontology(),ctx)
    return service,ctx,store


def test_review_checks_precise_revision_and_publish_persists_evidence(tmp_path):
    svc,ctx,store=setup(tmp_path)
    preview=svc.preview(mapping(),[profile([{'number':'A','company':'C','minor':'126000'}])],ctx)
    ref=preview.id+'@'+preview.revision
    receipt=svc.review(ReviewDecision(preview_ref=ref,target_scope='mapping'),preview.revision,ctx)
    release=svc.publish(VersionedRef.model_validate(ref),receipt.revision,ctx)
    assert release.digest==preview.digest
    assert store.current('release',release.id,scope='T') is not None
    assert store.query('assertion','T')
    assert store.query('fact','T')
    with pytest.raises(VersionConflict):
        svc.review(ReviewDecision(preview_ref=ref,target_scope='mapping'),preview.revision,ctx)


def test_missing_required_fields_block_publish(tmp_path):
    svc,ctx,_=setup(tmp_path)
    m=mapping();m.bindings.pop('amount')
    preview=svc.preview(m,[profile([{'number':'A','company':'C','minor':'100'}])],ctx)
    ref=f'{preview.id}@1'
    with pytest.raises(ValueError,match='unresolved'):
        svc.review(ReviewDecision(preview_ref=ref,target_scope='mapping'),'1',ctx)


def test_instance_correction_does_not_mutate_mapping_and_requires_new_preview(tmp_path):
    svc,ctx,store=setup(tmp_path)
    p=svc.preview(mapping(),[profile([{'number':'A','company':'C','minor':'126000'}])],ctx)
    decision=ReviewDecision(preview_ref=p.id+'@1',target_scope='instance',
        changes={'entity_id':p.instances[0].id,'property':'amount','value':'1250.00','reason':'发票修正'})
    receipt=svc.review(decision,'1',ctx)
    assert receipt.revalidate==['preview']
    latest=store.current('preview',p.id,scope='T')['body']
    assert latest['instances'][0]['values']['amount']=='1250.00'
    assert latest['mapping']['bindings']['amount']['transform']=='minor_to_major'
    assert latest['review_state']=='needs_revalidation'
    with pytest.raises(ValueError):svc.publish(VersionedRef(id=p.id,revision='2'),'2',ctx)


def test_authority_is_checked_at_every_read_and_write(tmp_path):
    svc,ctx,_=setup(tmp_path)
    with pytest.raises(PermissionError):
        svc.preview(mapping(),[],ctx.model_copy(update={'subject_ref':'attacker'}))
