"""Versioned previews and review decisions share one local transaction boundary."""
from datetime import datetime,timezone
from uuid import uuid4
from dataagent_contracts.ontology import MappingPreview,ReviewReceipt,DatasetRelease,OntologyRevision,OntologyPublication
from dataagent_runtime.ports.workbench_store import ChangeSet,Write,VersionConflict
from .identity import digest
from .mapping import materialize,_typed
from .registry import (REGISTRY_KIND,POINTER_KIND,POINTER_ID,build_entry,entries as registry_entries,
    entry_row,parse_entry,pointer_row,revision_record,DefaultTarget)
from .revisions import definition_diff


def _now():
    return datetime.now(timezone.utc).isoformat()


def _history_after_register(entry, previous, ontology, ctx):
    """Carry a host-swapped builtin revision into the visible history.

    ``register`` used to update only the row's current revision.  The library
    then showed the old history and hid the newly registered revision; keep the
    old definition as a synthesized first record for workspaces that predate
    ``revisions`` and append the new revision with its diff.
    """
    history = list(entry.revisions or [])
    if previous is not None and not any(
            item.get('revision') == entry.ontology_revision for item in history):
        history.append(revision_record(
            previous, published_at=entry.published_at,
            published_by=entry.published_by,
            source_snapshot=entry.source_snapshot,
            definition_digest=digest(previous.model_dump(mode='json'))))
    if not any(item.get('revision') == ontology.revision for item in history):
        diff = (definition_diff(previous, ontology)
                if previous is not None and previous.revision != ontology.revision
                else {})
        history.append(revision_record(
            ontology, published_at=_now(), published_by=ctx.subject_ref,
            source_snapshot=entry.source_snapshot,
            definition_digest=digest(ontology.model_dump(mode='json')),
            previous_revision=entry.ontology_revision, diff=diff,
            destructive=bool(diff.get('destructive'))))
    return history


class OntologyService:
    def __init__(self,store,*,scope,subject,authorization):
        self.store,self.scope=store,scope
        self.subject,self.authorization=subject,authorization

    def check(self,ctx):
        if (ctx.scope_ref,ctx.subject_ref,ctx.authorization_ref)!=(self.scope,self.subject,self.authorization):
            raise PermissionError('trusted workspace context required')

    def register(self,ontology,ctx):
        """Register a definition and keep its workspace registry entry current.

        Builtins are registered by the host at start.  A missing registry entry
        is created for workspaces that predate the registry; an active entry
        follows a host-swapped revision.  A retired entry is never revived.
        """
        self.check(ctx)
        current=self.store.current('ontology',ontology.id,scope=self.scope)
        body=ontology.model_dump(mode='json')
        writes=[]
        if not (current and current['body']==body):
            revision=str(int(current['revision'])+1) if current else '1'
            if ontology.revision!=revision:raise VersionConflict('ontology revision must advance exactly once')
            writes.append(Write('ontology',ontology.id,self.scope,body,current['revision'] if current else None))
        row=entry_row(self.store,self.scope,ontology.id)
        if row is None:
            writes.append(Write(REGISTRY_KIND,ontology.id,self.scope,
                build_entry(ontology).model_dump(mode='json')))
        else:
            entry=parse_entry(row)
            if entry.state=='active' and entry.ontology_revision!=ontology.revision:
                previous=(OntologyRevision.model_validate(current['body'])
                          if current is not None else None)
                updated=entry.model_copy(update={'ontology_revision':ontology.revision,
                    'concepts':list(ontology.concepts),
                    'default_concept':next(iter(ontology.concepts)),
                    'revisions':_history_after_register(entry,previous,ontology,ctx)})
                writes.append(Write(REGISTRY_KIND,ontology.id,self.scope,
                    updated.model_dump(mode='json'),row['revision']))
        if writes:self.store.commit(ChangeSet(writes=writes))

    def ensure_pointer(self,definition,ctx):
        """Create the workspace pointer once; never override an existing one.

        A workspace published before the pointer existed defaults to its newest
        active discovery ontology; otherwise the builtin stays the default.
        """
        self.check(ctx)
        if pointer_row(self.store,self.scope) is not None:return None
        published=[(entry,row) for entry,row in registry_entries(self.store,self.scope)
                   if entry.state=='active' and entry.origin=='discovery']
        if published:
            entry,_=max(published,key=lambda item:(item[0].published_at,item[0].id))
        else:
            entry=build_entry(definition)
        body={'ontology_id':entry.id,'concept':entry.default_concept,
              'updated_at':_now(),'updated_by':ctx.subject_ref}
        self.store.commit(ChangeSet(writes=[Write(POINTER_KIND,POINTER_ID,self.scope,body)]))
        return body

    def default_definition(self,ctx):
        """The exact revision a new task pins when it names no target.

        After a retirement the pointer is empty (or names the retired entry);
        new tasks then fall back to the active builtin.  Returning the concrete
        registered revision lets ``SessionService`` write
        ``ontology_id@revision`` into the task target instead of resolving the
        fallback later, when the pointer may have moved again.
        """
        self.check(ctx)
        row=pointer_row(self.store,self.scope)
        pointer=(row['body'] or {}) if row is not None else {}
        ontology_id=pointer.get('ontology_id')
        entry=parse_entry(entry_row(self.store,self.scope,ontology_id)) if ontology_id else None
        listed=registry_entries(self.store,self.scope)
        if entry is None or entry.state!='active':
            entry=next((entry for entry,_ in listed
                        if entry.origin=='builtin' and entry.state=='active'),None)
            pointer={}
        if entry is None:return None
        current=self.store.current('ontology',entry.id,scope=self.scope)
        if current is None:return None
        definition=OntologyRevision.model_validate(current['body'])
        concept=pointer.get('concept') or entry.default_concept
        if concept not in definition.concepts:
            concept=next(iter(definition.concepts))
        return DefaultTarget(definition,concept)

    def registry(self,ctx):
        """List workspace ontologies with their origin, state and pointer role.

        After a retirement the pointer is empty; new tasks then fall back to
        the builtin, so the listing reports that builtin as the effective
        default instead of claiming there is none.
        """
        self.check(ctx)
        row=pointer_row(self.store,self.scope)
        pointer=row['body'] if row is not None else None
        current_id=(pointer or {}).get('ontology_id')
        listed=registry_entries(self.store,self.scope)
        active={entry.id for entry,_ in listed if entry.state=='active'}
        default=(current_id if current_id in active else
                 next((entry.id for entry,_ in listed
                       if entry.state=='active' and entry.origin=='builtin'),None))
        items=[]
        for entry,registry_row in listed:
            items.append({**entry.model_dump(mode='json'),
                'registry_revision':registry_row['revision'],
                'is_default':entry.state=='active' and entry.id==default})
        items.sort(key=lambda item:(item['state']!='active',item['origin']!='builtin',
                                    item['id']))
        return {'ontologies':items,'default_ontology':default,'pointer':pointer}

    def retire(self,ontology_id,reason,ctx,*,expected_revision=None):
        """Retire one active ontology for new tasks; keep its revisions intact."""
        self.check(ctx)
        if not str(reason or '').strip():raise ValueError('retiring an ontology needs a reason')
        row=entry_row(self.store,self.scope,ontology_id)
        entry=parse_entry(row)
        if entry is None:raise KeyError('ontology not registered')
        if entry.origin=='builtin':
            raise ValueError('the builtin ontology is the workspace fallback and cannot be retired')
        if entry.state!='active':raise ValueError('ontology is already retired')
        if expected_revision is not None and str(expected_revision)!=row['revision']:
            raise VersionConflict('registry changed; reload before retiring')
        now=_now()
        retired=entry.model_copy(update={'state':'retired','retired_at':now,
            'retired_by':ctx.subject_ref,'retire_reason':reason})
        writes=[Write(REGISTRY_KIND,ontology_id,self.scope,
            retired.model_dump(mode='json'),row['revision'])]
        pointer=pointer_row(self.store,self.scope)
        if pointer is not None and (pointer['body'] or {}).get('ontology_id')==ontology_id:
            writes.append(Write(POINTER_KIND,POINTER_ID,self.scope,{
                'ontology_id':None,'concept':'','updated_at':now,
                'updated_by':ctx.subject_ref},pointer['revision']))
        publication=OntologyPublication(action='retire',ontology_id=ontology_id,
            ontology_revision=entry.ontology_revision,
            source_snapshot=entry.source_snapshot,subject_ref=ctx.subject_ref,
            recorded_at=now,reason=reason)
        audit_id=uuid4().hex
        writes.append(Write('ontology_publication',audit_id,self.scope,
            publication.model_dump(mode='json')))
        writes.append(Write('review',uuid4().hex,self.scope,{
            'decision':'retire','target_scope':'ontology','ontology_id':ontology_id,
            'subject_ref':ctx.subject_ref,'recorded_at':now,'reason':reason}))
        self.store.commit(ChangeSet(writes=writes))
        return {'ontology_id':ontology_id,'state':'retired','retired_at':now,
                'retired_by':ctx.subject_ref,'reason':reason,
                'publication_ref':audit_id}

    def definition(self,ref,ctx,concept=None):
        self.check(ctx)
        id,revision=ref.rsplit('@',1)
        row=self.store.get('ontology',id,revision,scope=self.scope)
        if row is None:raise KeyError('ontology not registered')
        model=OntologyRevision.model_validate(row['body'])
        if concept:model.resolve_concept(concept)
        return model

    def prepare_preview(self,mapping,observations,ctx,*,source_mappings=None,dispositions=None):
        self.check(ctx)
        ontology=self.definition(mapping.ontology_revision,ctx)
        result=materialize(ontology,mapping,observations,scope=self.scope,source_mappings=source_mappings,
                           dispositions=dispositions)
        if not result.instances:result.issues.append({'code':'ontology.no_records'})
        source_revisions={p.source_id:p.source_revision for p in observations}
        extensions={}
        if source_mappings is not None:
            extensions['intake.source_mappings'] = {
                key: value.model_dump(mode='json') for key, value in source_mappings.items()
            }
        if dispositions:
            # The preview revision pins the audited dispositions it was built
            # with, so a later save or report can reconstruct why a gap or
            # record no longer blocks.
            extensions['intake.dispositions'] = [dict(item) for item in dispositions]
        content={'ontology_revision':mapping.ontology_revision,'mapping':mapping.model_dump(mode='json'),
            'source_revisions':source_revisions,'instances':[i.model_dump(mode='json') for i in result.instances],
            'issues':result.issues}
        if extensions:
            content['extensions'] = extensions
        preview=MappingPreview(id=uuid4().hex,revision='1',digest=digest(content),
            **{k:v for k,v in content.items() if k!='instances'},instances=result.instances)
        body={**preview.model_dump(mode='json'),'assertions':[a.model_dump(mode='json') for a in result.assertions],
            'facts':[f.model_dump(mode='json') for f in result.facts],'review_state':'unreviewed'}
        return preview,body

    def preview(self,mapping,observations,ctx):
        preview,body=self.prepare_preview(mapping,observations,ctx)
        self.store.commit(ChangeSet(writes=[Write('preview',preview.id,self.scope,body)]))
        return preview

    def _current_preview(self,ref,expected_revision,ctx):
        self.check(ctx)
        id,revision=str(ref).rsplit('@',1)
        row=self.store.current('preview',id,scope=self.scope)
        if row is None:raise KeyError('preview not found')
        if row['revision']!=expected_revision:raise VersionConflict('preview changed; reload before review')
        return row

    def prepare_review(self,decision,expected_revision,ctx):
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
                raise ValueError('instance correction needs entity_id, property, value and reason '
                                 '(use entity_id, not entity)')
            ontology=self.definition(body['ontology_revision'],ctx)
            mapping=body.get('mapping') or {}
            _,concept=ontology.resolve_concept(mapping.get('concept','') if isinstance(mapping,dict) else '')
            prop=changes['property']
            if prop not in concept.properties:raise ValueError('unknown target property')
            targets=[i for i in body['instances'] if i['id']==changes['entity_id']]
            if len(targets)!=1:raise ValueError('unknown correction target')
            value=_typed(changes['value'],concept.properties[prop].value_type)
            if value is None and concept.properties[prop].required:raise ValueError('required property cannot be null')
            from pydantic_core import to_jsonable_python
            targets[0]['values'][prop]=to_jsonable_python(value)
            targets[0]['unresolved']=[item for item in targets[0].get('unresolved',[]) if item!=prop]
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
        writes=[
            Write('preview',row['id'],self.scope,body,row['revision']),
            Write('review',did,self.scope,{'decision':decision.model_dump(mode='json'),'subject_ref':ctx.subject_ref})]
        return ReviewReceipt(decision_ref=did+'@1',revision=next_revision,revalidate=revalidate),writes

    def prepare_partial_save(self,decision,expected_revision,ctx,*,plan,reason=''):
        """Release the objects without blocking issues and keep the rest pending.

        The stored preview keeps every object for the report, marks itself
        ``partially_published`` (so a later full publish cannot release the
        suspended objects), and records who/when/why in a new revision and an
        audit ``review`` record.  The release itself carries only the saved
        objects, assertions and facts.
        """

        row=self._current_preview(decision.preview_ref,expected_revision,ctx)
        if decision.preview_ref!=row['id']+'@'+row['revision']:
            raise VersionConflict('decision does not target current preview')
        body=row['body']
        saved_ids={item['entity_id'] for item in plan.get('saved',[])}
        if not saved_ids:
            raise ValueError('no objects can be saved')
        release_body={key:body[key] for key in ('ontology_revision','mapping','source_revisions')}
        release_body['instances']=[item for item in body['instances'] if item['id'] in saved_ids]
        release_body['issues']=[]
        # A fact may use an entity role other than ``subject`` (for example
        # ``price(invoice, amount, currency)``).  Keep an assertion only when
        # every entity it references is in this release, and keep a fact only
        # when every one of its assertions was kept as well.
        release_assertions=[]
        for item in body['assertions']:
            references=[role for role in item.get('role_bindings',[])
                        if role.get('value_type')=='reference']
            if references and all(role.get('value') in saved_ids for role in references):
                release_assertions.append(item)
        assertion_ids={item['id'] for item in release_assertions}
        release_facts=[]
        for item in body['facts']:
            references=[role for role in item.get('role_bindings',[])
                        if role.get('value_type')=='reference']
            refs=item.get('assertion_refs') or []
            if (references and refs
                    and all(role.get('value') in saved_ids for role in references)
                    and all(ref in assertion_ids for ref in refs)):
                release_facts.append(item)
        release_body['assertions']=release_assertions
        release_body['facts']=release_facts
        content={key:release_body[key]
                 for key in ('ontology_revision','mapping','source_revisions','instances','issues')}
        if body.get('extensions'):
            content['extensions']=body['extensions']
        release_body['digest']=digest(content)
        did=uuid4().hex
        recorded_at=datetime.now(timezone.utc).isoformat()
        audit={**plan,'release_ref':None,'reason':reason or '部分保存：保存无阻断的对象，冲突或缺必填的对象挂起',
               'recorded_at':recorded_at,'subject_ref':ctx.subject_ref,'decision_ref':did+'@1'}
        release_id='release:'+digest([row['id'],release_body['digest'],'partial'])
        audit['release_ref']=release_id+'@1'
        stored=dict(body)
        stored['review_state']='partially_published'
        stored['partial_save']=[*(body.get('partial_save') or []),audit]
        stored['suspended']=plan.get('suspended',[])
        stored['unidentified_records']=plan.get('unidentified_records',[])
        stored['revision']=str(int(row['revision'])+1)
        release,writes=self._release_writes(release_body,row['id'],row['revision'],
            decision.preview_ref,stored_body=stored,partial=True)
        writes.append(Write('review',did,self.scope,{
            'decision':decision.model_dump(mode='json'),'subject_ref':ctx.subject_ref,
            'recorded_at':recorded_at,'partial_save':audit}))
        receipt=ReviewReceipt(decision_ref=did+'@1',revision=stored['revision'],
            revalidate=['partial_save'],extensions={'intake.partial_save':audit})
        return receipt,writes

    def review(self,decision,expected_revision,ctx):
        receipt,writes=self.prepare_review(decision,expected_revision,ctx)
        self.store.commit(ChangeSet(writes=writes))
        return receipt

    def publish(self,candidate_ref,expected_revision,ctx):
        row=self._current_preview(candidate_ref,expected_revision,ctx)
        body=row['body']
        if body.get('review_state')!='approved' or body.get('approved_preview_ref')!=str(candidate_ref):
            raise ValueError('precise preview must be reviewed before publication')
        release,writes=self.release_writes(body,row['id'],row['revision'],str(candidate_ref))
        self.store.commit(ChangeSet(writes=writes))
        return release

    def _release_writes(self,body,preview_id,expected_revision,candidate_ref,*,stored_body=None,partial=False):
        if not partial and (body.get('review_state')!='approved'
                            or body.get('approved_preview_ref')!=str(candidate_ref)):
            raise ValueError('unapproved release')
        parts=[preview_id,body['digest']]+(['partial'] if partial else [])
        rid='release:'+digest(parts)
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
        stored=dict(stored_body if stored_body is not None else body)
        stored['review_state']='partially_published' if partial else 'published'
        stored['release_ref']=rid+'@1'
        if partial:stored['partial_release_ref']=rid+'@1'
        stored['revision']=str(int(expected_revision)+1)
        writes.append(Write('preview',preview_id,self.scope,stored,expected_revision))
        return release,writes

    def release_writes(self,body,preview_id,expected_revision,candidate_ref):
        return self._release_writes(body,preview_id,expected_revision,candidate_ref)
