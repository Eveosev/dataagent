"""Versioned previews and review decisions share one local transaction boundary."""
from uuid import uuid4
from dataagent_contracts.ontology import MappingPreview,ReviewReceipt,DatasetRelease,OntologyRevision
from dataagent_runtime.ports.workbench_store import ChangeSet,Write,VersionConflict
from .identity import digest
from .mapping import materialize,_typed


class OntologyService:
    def __init__(self,store,*,scope,subject,authorization):
        self.store,self.scope=store,scope
        self.subject,self.authorization=subject,authorization

    def check(self,ctx):
        if (ctx.scope_ref,ctx.subject_ref,ctx.authorization_ref)!=(self.scope,self.subject,self.authorization):
            raise PermissionError('trusted workspace context required')

    def register(self,ontology,ctx):
        self.check(ctx)
        current=self.store.current('ontology',ontology.id,scope=self.scope)
        body=ontology.model_dump(mode='json')
        if current and current['body']==body:return
        revision=str(int(current['revision'])+1) if current else '1'
        if ontology.revision!=revision:raise VersionConflict('ontology revision must advance exactly once')
        self.store.commit(ChangeSet(writes=[Write('ontology',ontology.id,self.scope,body,current['revision'] if current else None)]))

    def definition(self,ref,ctx):
        self.check(ctx)
        id,revision=ref.rsplit('@',1)
        row=self.store.get('ontology',id,revision,scope=self.scope)
        if row is None:raise KeyError('ontology not registered')
        return OntologyRevision.model_validate(row['body'])

    def preview(self,mapping,observations,ctx):
        self.check(ctx)
        ontology=self.definition(mapping.ontology_revision,ctx)
        result=materialize(ontology,mapping,observations,scope=self.scope)
        if not result.instances:result.issues.append({'code':'ontology.no_records'})
        source_revisions={p.source_id:p.source_revision for p in observations}
        content={'ontology_revision':mapping.ontology_revision,'mapping':mapping.model_dump(mode='json'),
            'source_revisions':source_revisions,'instances':[i.model_dump(mode='json') for i in result.instances],
            'issues':result.issues}
        preview=MappingPreview(id=uuid4().hex,revision='1',digest=digest(content),**content)
        body={**preview.model_dump(mode='json'),'assertions':[a.model_dump(mode='json') for a in result.assertions],
            'facts':[f.model_dump(mode='json') for f in result.facts],'review_state':'unreviewed'}
        self.store.commit(ChangeSet(writes=[Write('preview',preview.id,self.scope,body)]))
        return preview

    def _current_preview(self,ref,expected_revision,ctx):
        self.check(ctx)
        id,revision=str(ref).rsplit('@',1)
        row=self.store.current('preview',id,scope=self.scope)
        if row is None:raise KeyError('preview not found')
        if row['revision']!=expected_revision:raise VersionConflict('preview changed; reload before review')
        return row

    def review(self,decision,expected_revision,ctx):
        row=self._current_preview(decision.preview_ref,expected_revision,ctx)
        if decision.preview_ref!=row['id']+'@'+row['revision']:
            raise VersionConflict('decision does not target current preview')
        body=row['body'];next_revision=str(int(row['revision'])+1)
        revalidate=[];did=uuid4().hex
        if decision.decision=='reject':
            body['review_state']='rejected'
        elif decision.target_scope=='ontology':
            body['review_state']='needs_revalidation';revalidate=['ontology_draft']
            body['ontology_draft']=decision.changes
        elif decision.target_scope=='instance':
            changes=decision.changes
            if not {'entity_id','property','value','reason'}<=changes.keys() or not changes['reason']:
                raise ValueError('instance correction needs entity/property/value/reason')
            ontology=self.definition(body['ontology_revision'],ctx)
            prop=changes['property']
            if prop not in ontology.properties:raise ValueError('unknown target property')
            targets=[i for i in body['instances'] if i['id']==changes['entity_id']]
            if len(targets)!=1:raise ValueError('unknown correction target')
            value=_typed(changes['value'],ontology.properties[prop].value_type)
            if value is None and ontology.properties[prop].required:raise ValueError('required property cannot be null')
            from pydantic_core import to_jsonable_python
            targets[0]['values'][prop]=to_jsonable_python(value)
            body.setdefault('corrections',[]).append({'decision_ref':did+'@1',**changes})
            body['review_state']='needs_revalidation';revalidate=['preview']
        elif decision.changes:
            body['mapping_proposal']=decision.changes
            body['review_state']='needs_revalidation';revalidate=['mapping']
        else:
            if body['issues']:raise ValueError('preview contains unresolved issues')
            body['review_state']='approved';body['approved_preview_ref']=decision.preview_ref
        body['revision']=next_revision
        body['last_decision_ref']=did+'@1'
        self.store.commit(ChangeSet(writes=[
            Write('preview',row['id'],self.scope,body,row['revision']),
            Write('review',did,self.scope,{'decision':decision.model_dump(mode='json'),'subject_ref':ctx.subject_ref})]))
        return ReviewReceipt(decision_ref=did+'@1',revision=next_revision,revalidate=revalidate)

    def publish(self,candidate_ref,expected_revision,ctx):
        row=self._current_preview(candidate_ref,expected_revision,ctx)
        body=row['body']
        if body.get('review_state')!='approved' or body.get('approved_preview_ref')!=str(candidate_ref):
            raise ValueError('precise preview must be reviewed before publication')
        rid='release:'+digest([row['id'],body['digest']])
        release=DatasetRelease(id=rid,revision='1',preview_ref=str(candidate_ref),digest=body['digest'])
        writes=[Write('release',rid,self.scope,release.model_dump(mode='json'))]
        # Assertions are immutable provenance; repeated identical facts union assertion refs.
        for a in body['assertions']:
            if self.store.current('assertion',a['id'],scope=self.scope) is None:
                writes.append(Write('assertion',a['id'],self.scope,a))
        for f in body['facts']:
            prior=self.store.current('fact',f['id'],scope=self.scope)
            if prior:
                f={**f,'assertion_refs':sorted(set(f['assertion_refs']+prior['body']['assertion_refs']))}
            writes.append(Write('fact',f['id'],self.scope,f,prior['revision'] if prior else None))
        body['review_state']='published';body['release_ref']=rid+'@1'
        body['revision']=str(int(row['revision'])+1)
        writes.append(Write('preview',row['id'],self.scope,body,row['revision']))
        self.store.commit(ChangeSet(writes=writes))
        return release
