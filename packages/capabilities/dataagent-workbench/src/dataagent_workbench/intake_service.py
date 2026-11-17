"""Durable intake coordination over isolated probes and validated ontology proposals."""
from dataagent_contracts.intake import SourceProfile
from dataagent_contracts.ontology import MappingSpec
from dataagent_runtime.ports.workbench_store import Write,VersionConflict
from dataagent_ontology.identity import digest
from .adapters.layer_client import LayerClient,installed_data_package
from .inference_requests import mapping_request
from .document_fields import extract_fields
from .ontology_discovery import is_discovery


def _rest_retryable(profile):
    return (profile.kind == 'rest' and profile.coverage == 'partial'
            and profile.metadata.get('source_version') is not None
            and profile.metadata.get('row_offset') == 0 and bool(profile.metadata.get('cursor'))
            and all(gap.code in {'connection_failed','rate_limited','http_error'} for gap in profile.gaps))


class IntakeService:
    def __init__(self,wb):self.wb=wb

    def _profiles(self,session):
        out=[]
        for key,ref in session.selected_versions.items():
            if not key.startswith('profile:'):continue
            id,rev=ref.rsplit('@',1)
            row=self.wb.store.get('profile',id,rev,scope=self.wb.scope)
            if row is None:raise ValueError('selected source observation missing')
            out.append(SourceProfile.model_validate(row['body']))
        return out

    def advance(self,session_id,ctx):
        wb=self.wb;s=wb.sessions.get(session_id,ctx)
        if s.phase == 'saved':return s
        prior_profiles = {profile.source_id: profile for profile in self._profiles(s)}
        if is_discovery(s) and prior_profiles and s.phase != 'probing' and 'retry_probe' not in s.next_actions:
            return s
        if s.phase == 'preview' and not any(_rest_retryable(profile) for profile in prior_profiles.values()):
            return s
        client=wb.layer_client or LayerClient(installed_data_package(wb.workspace))
        versions=s.selected_versions.copy()
        job=wb.store.current('job',s.job_ref,scope=wb.scope)
        s=wb.sessions.update(s.id,s.revision,{'phase':'probing','issues':[]},ctx,
            extra_writes=[Write('job',s.job_ref,wb.scope,{**job['body'],'state':'running'},job['revision'])])
        errors=[]
        for source in s.sources:
            key = 'profile:'+source.source_id
            previous = prior_profiles.get(source.source_id)
            if previous is not None and not _rest_retryable(previous):continue
            selection = source
            if is_discovery(s):
                selection = source.model_copy(update={'options': {**source.options, 'sample_strategy': 'per_table'}})
            try:
                profile=(client.probe(selection,ctx,wb.workspace,previous=previous) if previous is not None
                         else client.probe(selection,ctx,wb.workspace))
            except (ValueError,OSError,TimeoutError) as exc:
                errors.append({'code':'intake.probe_failed','source_id':source.source_id,'detail':str(exc)})
                continue
            pid=s.id+':'+source.source_id
            previous_revision=versions[key].rsplit('@',1)[1] if key in versions else None
            revision=str(int(previous_revision)+1) if previous_revision else '1'
            versions[key]=pid+'@'+revision
            versions.pop('preview',None)
            s=wb.sessions.update(s.id,s.revision,{'selected_versions':versions},ctx,
                extra_writes=[Write('profile',pid,wb.scope,profile.model_dump(mode='json'),previous_revision)])
        job=wb.store.current('job',s.job_ref,scope=wb.scope)
        profiles=self._profiles(s)
        retry=errors or any(_rest_retryable(profile) for profile in profiles)
        next_action = 'propose_mapping'
        if is_discovery(s):
            next_action = 'propose_discovery' if profiles and profiles[0].metadata['tables'] else 'select_source'
        s=wb.sessions.update(s.id,s.revision,{'phase':'needs_input','issues':errors,
            'next_actions':['retry_probe'] if retry else [next_action]},ctx,
            extra_writes=[Write('job',s.job_ref,wb.scope,{**job['body'],'state':'needs_input','checkpoint':'profiles'},job['revision'])])
        if not is_discovery(s) and profiles and not errors and all(p.coverage=='full' for p in profiles):
            if self._reuse_verified_mapping(s,profiles,ctx):
                return wb.sessions.get(s.id,ctx)
        return s

    def _fingerprints(self,profiles):
        """Order-independent fingerprint set identifying the source combination."""
        return sorted({profile.metadata['structure_fingerprint'] for profile in profiles})

    def _verified_mapping_keys(self,profiles):
        wb=self.wb
        revision=f'{wb.definition.id}@{wb.definition.revision}'
        keys=[digest([wb.scope,self._fingerprints(profiles),revision])]
        # Older builds registered a single source under the bare fingerprint string.
        if len(profiles)==1:
            keys.append(digest([wb.scope,profiles[0].metadata['structure_fingerprint'],revision]))
        return keys

    @staticmethod
    def _mapping_body(mapping):
        ignored={'id','revision','scope'}
        return {key:value for key,value in mapping.model_dump(mode='json').items() if key not in ignored}

    def _same_mapping(self,left,right):
        return self._mapping_body(left)==self._mapping_body(right)

    def _cached_sources(self,body):
        records=body.get('sources')
        if records is not None:
            if not isinstance(records,list):return None
            try:
                return [{'source_id':record.get('source_id'),'locator_ref':record.get('locator_ref'),
                         'kind':record.get('kind'),'mapping':MappingSpec.model_validate(record['mapping'])}
                        for record in records]
            except (AttributeError,KeyError,TypeError,ValueError):return None
        mappings=body.get('mappings')
        if mappings is None and 'mapping' in body:mappings=[body['mapping']]
        if not isinstance(mappings,list):return None
        try:
            return [{'source_id':None,'locator_ref':None,'kind':None,'mapping':MappingSpec.model_validate(mapping)}
                    for mapping in mappings]
        except (TypeError,ValueError):return None

    def _group_mappings(self,profiles,records,sources):
        """Pair every source in one fingerprint group, refusing gaps or conflicts."""
        used=set()
        proposals={}
        for profile in profiles:
            selection=sources.get(profile.source_id)
            by_id=[index for index,record in enumerate(records)
                   if record['source_id'] is not None and record['source_id']==profile.source_id]
            by_locator=[]
            if selection is not None:
                by_locator=[index for index,record in enumerate(records)
                            if record['locator_ref'] is not None and record['locator_ref']==selection.locator_ref
                            and record['kind']==selection.kind]
            if len(by_id)>1 or len(by_locator)>1:return None
            if by_id:
                record=records[by_id[0]]
                if record['locator_ref'] is not None or record['kind'] is not None:
                    if (selection is None or record['locator_ref']!=selection.locator_ref
                            or record['kind']!=selection.kind):return None
            if by_id and by_locator and by_id[0]!=by_locator[0]:return None
            matches=by_id or by_locator
            if not matches or matches[0] in used:return None
            used.add(matches[0])
            proposals[profile.source_id]=records[matches[0]]['mapping']
        return proposals if len(used)==len(records) else None

    def _reuse_verified_mapping(self,session,profiles,ctx):
        for key in self._verified_mapping_keys(profiles):
            cached=self.wb.store.current('verified_mapping',key,scope=self.wb.scope)
            if cached is not None and self._reuse_cached_mapping(session,profiles,cached,ctx):
                return True
        return False

    def _reuse_cached_mapping(self,session,profiles,cached,ctx):
        records=self._cached_sources(cached['body'])
        if not records or len(records)!=len(profiles):return False
        groups={}
        for record in records:groups.setdefault(record['mapping'].source_fingerprint,[]).append(record)
        if sorted(groups)!=self._fingerprints(profiles):return False
        sources={source.source_id:source for source in session.sources}
        proposals={}
        for fingerprint,group in groups.items():
            current=[profile for profile in profiles
                     if profile.metadata['structure_fingerprint']==fingerprint]
            if len(current)!=len(group):return False
            if len(group)==1:
                proposals[current[0].source_id]=group[0]['mapping']
            elif all(self._same_mapping(record['mapping'],group[0]['mapping']) for record in group[1:]):
                proposals.update({profile.source_id:record['mapping']
                                  for profile,record in zip(current,group)})
            else:
                matched=self._group_mappings(current,group,sources)
                if matched is None:return False
                proposals.update(matched)
        if len(profiles)==1:
            self.submit_proposal(session.id,proposals[profiles[0].source_id],session.revision,ctx,reused=True)
        else:
            self.submit_source_proposals(session.id,proposals,session.revision,ctx,reused=True)
        return True

    def inference_request(self,session_id,ctx):
        s=self.wb.sessions.get(session_id,ctx)
        profiles = self._profiles(s)
        if is_discovery(s):
            return self.wb.discovery.request(s, profiles)
        return mapping_request(s, profiles, self.wb.definition, self.wb.allowed_model_fields)

    def extract_document_fields(self, session_id, source_id, fields, expected_revision, ctx):
        wb = self.wb
        session = wb.sessions.get(session_id, ctx)
        if session.revision != expected_revision:
            raise VersionConflict('session changed; reload source excerpts')
        key = 'profile:' + source_id
        ref = session.selected_versions.get(key)
        if ref is None:
            raise ValueError('source has no observation in this task')
        profile_id, revision = ref.rsplit('@', 1)
        record = wb.store.get('profile', profile_id, revision, scope=wb.scope)
        profile = SourceProfile.model_validate(record['body'])
        allowed = None if wb.allowed_model_fields is None else wb.allowed_model_fields.get(source_id, [])
        updated = extract_fields(profile, fields, allowed)
        versions = dict(session.selected_versions)
        versions.pop('preview', None)
        versions[key] = f'{profile_id}@{int(revision) + 1}'
        wb.sessions.update(session_id, expected_revision, {
            'phase': 'needs_input', 'selected_versions': versions,
            'issues': [], 'next_actions': ['propose_mapping'],
        }, ctx, extra_writes=[
            Write('profile', profile_id, wb.scope, updated.model_dump(mode='json'), revision),
        ])
        return self.inference_request(session_id, ctx)

    def submit_proposal(self,session_id,proposal,expected_revision,ctx,*,reused=False):
        wb=self.wb;s=wb.sessions.get(session_id,ctx)
        if is_discovery(s):
            raise ValueError('use ontology_discovery_propose for this intake')
        if s.revision!=expected_revision:raise VersionConflict('session changed; reload proposal inputs')
        if proposal.ontology_revision!=f'{wb.definition.id}@{wb.definition.revision}':raise ValueError('target ontology outside task')
        observations=[p for p in self._profiles(s) if p.metadata['structure_fingerprint']==proposal.source_fingerprint]
        if not observations:raise ValueError('proposal does not match a selected source')
        mid=s.id+':mapping'
        prior=wb.store.current('mapping',mid,scope=wb.scope)
        revision=str(int(prior['revision'])+1) if prior else '1'
        proposal=proposal.model_copy(update={'id':mid,'revision':revision,'scope':wb.scope})
        preview,body=wb.ontology.prepare_preview(proposal,observations,ctx)
        body['mapping_reused']=reused
        versions={**s.selected_versions,'preview':preview.id+'@1','mapping':mid+'@'+revision}
        wb.sessions.update(s.id,s.revision,{'phase':'preview','selected_versions':versions,
            'issues':preview.issues,'next_actions':['review_mapping']},ctx,extra_writes=[
            Write('preview',preview.id,wb.scope,body),
            Write('mapping',mid,wb.scope,proposal.model_dump(mode='json'),prior['revision'] if prior else None)])
        return preview

    def submit_source_proposals(self, session_id, proposals, expected_revision, ctx, *, reused=False):
        wb = self.wb
        session = wb.sessions.get(session_id, ctx)
        if is_discovery(session):
            raise ValueError('use ontology_discovery_propose for this intake')
        if session.revision != expected_revision:
            raise VersionConflict('session changed; reload proposal inputs')
        observations = self._profiles(session)
        selected = {source.source_id for source in session.sources}
        if set(proposals) != selected or {profile.source_id for profile in observations} != selected:
            raise ValueError('provide one mapping for each observed source')
        if {proposal.ontology_revision for proposal in proposals.values()} != {f'{wb.definition.id}@{wb.definition.revision}'}:
            raise ValueError('target ontology outside task')
        if len({proposal.identity_strategy for proposal in proposals.values()}) != 1:
            raise ValueError('all mappings must use the same identity strategy')
        versions = dict(session.selected_versions)
        writes = []
        mappings = {}
        for index, profile in enumerate(observations):
            key = profile.source_id
            mapping_id = f'{session.id}:source-mapping:{index}'
            current = wb.store.current('mapping', mapping_id, scope=wb.scope)
            revision = str(int(current['revision']) + 1) if current else '1'
            mapping = proposals[key].model_copy(update={'id': mapping_id, 'revision': revision, 'scope': wb.scope})
            mappings[key] = mapping
            versions['mapping:'+key] = f'{mapping_id}@{revision}'
            writes.append(Write('mapping', mapping_id, wb.scope, mapping.model_dump(mode='json'),
                                current['revision'] if current else None))
        primary = next(iter(mappings.values()))
        preview, body = wb.ontology.prepare_preview(primary, observations, ctx, source_mappings=mappings)
        body['mapping_reused'] = reused
        versions.update(preview=preview.id+'@1', mapping=f'{primary.id}@{primary.revision}')
        wb.sessions.update(session_id, expected_revision, {
            'phase': 'preview', 'selected_versions': versions, 'issues': preview.issues,
            'next_actions': ['review_mapping'],
        }, ctx, extra_writes=[*writes, Write('preview', preview.id, wb.scope, body)])
        return preview

    def apply(self,session_id,decision,expected_revision,ctx):
        wb=self.wb;s=wb.sessions.get(session_id,ctx)
        if s.revision!=expected_revision or s.selected_versions.get('preview')!=decision.preview_ref:
            raise VersionConflict('decision does not target the active task preview')
        id,rev=decision.preview_ref.rsplit('@',1)
        draft=wb.store.current('ui_draft',s.id,scope=wb.scope)
        if decision.target_scope=='mapping' and decision.decision=='save' and draft:
            from dataagent_contracts.ontology import FieldBinding
            active=wb.store.get('preview',id,rev,scope=wb.scope)['body']
            def normalize(bindings):
                return {k:FieldBinding.model_validate(v).model_dump(mode='json',exclude_defaults=True,exclude_none=True) for k,v in bindings.items()}
            source_mappings=(active.get('extensions') or {}).get('intake.source_mappings', {})
            if any(key not in source_mappings or normalize(bindings)!=normalize(source_mappings[key]['bindings'])
                   for key,bindings in draft['body'].get('source_bindings', {}).items()):
                raise VersionConflict('draft changed; generate a new preview before saving')
            if 'bindings' in draft['body'] and normalize(draft['body']['bindings'])!=normalize(active['mapping']['bindings']):
                raise VersionConflict('draft changed; generate a new preview before saving')
        receipt,writes=wb.ontology.prepare_review(decision,rev,ctx)
        preview_write=next(w for w in writes if w.kind=='preview')
        body=preview_write.body
        versions={**s.selected_versions,'preview':id+'@'+receipt.revision}
        phase='preview'
        if body['review_state']=='approved':
            selected={source.source_id for source in s.sources}
            if selected!=set(body['source_revisions']):raise ValueError('remaining sources require separate mapping')
            release,release_writes=wb.ontology.release_writes(body,id,rev,decision.preview_ref)
            writes=[w for w in writes if w.kind!='preview']+release_writes
            versions['release']=release.id+'@'+release.revision
            phase='saved'
            mapping=body['mapping']
            source_mappings=(body.get('extensions') or {}).get('intake.source_mappings') or {}
            selections={source.source_id:source for source in s.sources}
            if source_mappings:
                records=[{'source_id':source_id,'locator_ref':selections[source_id].locator_ref,
                          'kind':selections[source_id].kind,'mapping':item}
                         for source_id,item in source_mappings.items() if source_id in selections]
            else:
                source=selections.get(next(iter(selected))) if len(selected)==1 else None
                records=[{'source_id':source.source_id if source else None,
                          'locator_ref':source.locator_ref if source else None,
                          'kind':source.kind if source else None,'mapping':mapping}]
            if len(records)==len(selected):
                fingerprints=sorted({record['mapping']['source_fingerprint'] for record in records})
                key=digest([wb.scope,fingerprints,f'{wb.definition.id}@{wb.definition.revision}'])
                cached=wb.store.current('verified_mapping',key,scope=wb.scope)
                entry={'source_fingerprints':fingerprints,'sources':records,'release_ref':versions['release']}
                if len(records)==1:entry['mapping']=records[0]['mapping']
                writes.append(Write('verified_mapping',key,wb.scope,entry,cached['revision'] if cached else None))
            job=wb.store.current('job',s.job_ref,scope=wb.scope)
            writes.append(Write('job',s.job_ref,wb.scope,{**job['body'],'state':'completed','result_ref':versions['release']},job['revision']))
        wb.sessions.update(s.id,s.revision,{'phase':phase,'selected_versions':versions,
            'next_actions':receipt.revalidate},ctx,extra_writes=writes)
        return receipt

    def view(self,session_id,ctx):
        wb=self.wb;s=wb.sessions.get(session_id,ctx)
        body=None
        if 'preview' in s.selected_versions:
            id,rev=s.selected_versions['preview'].rsplit('@',1)
            row=wb.store.get('preview',id,rev,scope=wb.scope)
            body=row['body'] if row else None
        draft=self.wb.store.current('ui_draft',s.id,scope=wb.scope)
        profiles = self._profiles(s)
        return {'session':s.model_dump(mode='json'),'profiles':[p.model_dump(mode='json') for p in profiles],
            'discovery':wb.discovery.state(s, profiles),
            'ontology':wb.definition.model_dump(mode='json'),'preview':body,
            'draft':draft['body'] if draft else {},
            'mapping_reused':bool(body and body.get('mapping_reused'))}

    def save_draft(self,session_id,draft,expected_revision,ctx):
        wb=self.wb;s=wb.sessions.get(session_id,ctx)
        prior=wb.store.current('ui_draft',s.id,scope=wb.scope)
        revision=str(int(prior['revision'])+1) if prior else '1'
        return wb.sessions.update(s.id,expected_revision,
            {'selected_versions':{**s.selected_versions,'draft':s.id+'@'+revision}},ctx,
            extra_writes=[Write('ui_draft',s.id,wb.scope,draft,prior['revision'] if prior else None)])

    def revalidate(self,session_id,expected_revision,ctx):
        from dataagent_ontology.corrections import revalidate_corrections
        from dataagent_contracts.ontology import MappingPreview
        wb=self.wb;s=wb.sessions.get(session_id,ctx)
        if s.revision!=expected_revision:raise VersionConflict('session changed')
        id,rev=s.selected_versions['preview'].rsplit('@',1)
        row=wb.store.get('preview',id,rev,scope=wb.scope)
        if row['body']['review_state']!='needs_revalidation':raise ValueError('preview does not need correction validation')
        body=revalidate_corrections(row['body'],wb.definition,wb.scope)
        next_rev=str(int(rev)+1);body['revision']=next_rev
        wb.sessions.update(s.id,s.revision,{'selected_versions':{**s.selected_versions,'preview':id+'@'+next_rev},
            'issues':body['issues'],'next_actions':['review_mapping']},ctx,
            extra_writes=[Write('preview',id,wb.scope,body,rev)])
        fields=MappingPreview.model_fields
        return MappingPreview.model_validate({k:v for k,v in body.items() if k in fields})
