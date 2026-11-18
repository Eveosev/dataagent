"""Durable intake coordination over isolated probes and validated ontology proposals."""
import json
import os
import time
from pathlib import Path
from pydantic_core import to_jsonable_python
from dataagent_contracts.core.refs import SourceAnchor
from dataagent_contracts.intake import CoverageGap, SourceProfile
from dataagent_contracts.ontology import Assertion, MappingPreview, MappingSpec, RoleBinding
from dataagent_runtime.ports.workbench_store import Write,VersionConflict
from dataagent_ontology.facts import relation_key
from dataagent_ontology.identity import digest
from dataagent_ontology.mapping import _typed
from .adapters.layer_client import DataLayerProbeError, LayerClient,installed_data_package
from .inference_requests import mapping_request
from .document_fields import extract_fields, replay_fields
from .ontology_discovery import is_discovery


BUDGET_GAP = 'time_budget_exceeded'
_REST_RETRY_GAPS = {'connection_failed','rate_limited','http_error'}
_MIN_SEGMENT_SECONDS = 0.25
_MAX_SEGMENTS = 500
_DEFAULT_BUDGET_SECONDS = 50.0
_BUDGET_CAP_SECONDS = 50.0
_MAX_BUDGET_RESERVE_SECONDS = 5.0
_BUDGET_RESERVE_RATIO = 0.1
_MIN_PROBE_SECONDS = 0.01

_PREVIEW_BLOCK_DETAIL = 'preview contains unresolved issues'
_PENDING_CORRECTIONS = 'intake.pending_corrections'
_RESOLVABLE_ISSUES = {
    'ontology.conflicting_values', 'ontology.required_value_missing',
    'ontology.conversion_failed',
}
_ISSUE_REASONS = {
    'ontology.conflicting_values': '各来源的字段值不一致',
    'ontology.required_value_missing': '缺少必填值',
    'ontology.required_binding_missing': '必填属性没有映射',
    'ontology.identity_unresolved': '缺少单据号，无法确定对象',
    'ontology.conversion_failed': '值无法按目标类型转换',
    'ontology.evidence_missing': '值没有来源定位',
    'ontology.incomplete_source': '来源未完整读取',
    'ontology.relation_unresolved': '关联字段不完整',
    'ontology.correction_conflict': '网页纠正无法沿用',
    'ontology.no_records': '没有可映射的记录',
}


class PreviewBlocked(ValueError):
    """A save was refused; ``issues`` names affected objects and reasons.

    The detail string stays the stable contract expected by existing callers
    while the structured list carries the object-level explanation.
    """

    def __init__(self, issues):
        self.issues = list(issues)
        super().__init__(_PREVIEW_BLOCK_DETAIL)


def _rest_retryable(profile):
    return (profile.kind == 'rest' and profile.coverage == 'partial'
            and profile.metadata.get('source_version') is not None
            and profile.metadata.get('row_offset') == 0 and bool(profile.metadata.get('cursor'))
            and all(gap.code in _REST_RETRY_GAPS for gap in profile.gaps))


def _resumable(profile):
    """True when the profile carries a checkpoint produced by a segment budget."""
    state = profile.metadata.get('resume') if isinstance(profile.metadata, dict) else None
    return (isinstance(state, dict)
            and any(gap.code == BUDGET_GAP for gap in profile.gaps))


def _failure_state(profile):
    """Return (error, attempts, retryable) for a persisted failure, if any."""
    metadata = profile.metadata if isinstance(profile.metadata, dict) else {}
    error = metadata.get('probe_error')
    if not isinstance(error, dict):
        return None
    attempts = metadata.get('probe_attempts', 1)
    attempts = attempts if isinstance(attempts, int) else 1
    return error, attempts, bool(error.get('retryable'))


def _retryable_failure(profile):
    """A coded, transient failure may be probed again a bounded number of times."""
    state = _failure_state(profile)
    return bool(state and state[2] and state[1] < 2)


def _exhausted_failure(profile):
    """A failure that must not be retried automatically any more."""
    state = _failure_state(profile)
    return bool(state and (not state[2] or state[1] >= 2))


def _segment_budget(value):
    try:
        seconds = _DEFAULT_BUDGET_SECONDS if value is None else float(value)
    except (TypeError, ValueError):
        seconds = _DEFAULT_BUDGET_SECONDS
    # The host gives a tool call 60s. Keep the configured allowance at 50s or
    # less; _probe_deadline spends part of it on persistence/transport.
    return min(_BUDGET_CAP_SECONDS, max(0.1, seconds))


def _probe_deadline(seconds):
    """Wall deadline for probe work, reserving time to persist the result.

    The reserve grows with the allowance up to a fixed cap, so a small
    configured budget still performs useful work while a 50s budget leaves
    enough room for profile/session writes and the MCP round trip.
    """
    budget = min(_BUDGET_CAP_SECONDS, max(0.1, float(seconds)))
    reserve = min(_MAX_BUDGET_RESERVE_SECONDS, budget * _BUDGET_RESERVE_RATIO)
    return time.monotonic() + max(_MIN_PROBE_SECONDS, budget - reserve)


def _deadline_key(profile):
    state = profile.metadata.get('resume') if isinstance(profile.metadata, dict) else None
    return (json.dumps(state, sort_keys=True, default=str),
            len(profile.records), tuple(profile.completed_partitions))


class IntakeService:
    def __init__(self,wb):
        self.wb=wb
        self.budget_seconds=_segment_budget(os.environ.get('DATAAGENT_INTAKE_BUDGET_SECONDS'))

    def _profiles(self,session):
        out=[]
        for key,ref in session.selected_versions.items():
            if not key.startswith('profile:'):continue
            id,rev=ref.rsplit('@',1)
            row=self.wb.store.get('profile',id,rev,scope=self.wb.scope)
            if row is None:raise ValueError('selected source observation missing')
            out.append(SourceProfile.model_validate(row['body']))
        return out

    def _store_profile(self,session,versions,source,profile,ctx):
        wb=self.wb
        key='profile:'+source.source_id
        pid=session.id+':'+source.source_id
        previous_revision=versions[key].rsplit('@',1)[1] if key in versions else None
        revision=str(int(previous_revision)+1) if previous_revision else '1'
        versions[key]=pid+'@'+revision
        versions.pop('preview',None)
        return wb.sessions.update(session.id,session.revision,{'selected_versions':versions},ctx,
            extra_writes=[Write('profile',pid,wb.scope,profile.model_dump(mode='json'),previous_revision)])

    def _failure_profile(self,source,previous,*,code,detail,retryable):
        """Persist the evidence observed so far plus an explicit failure gap."""
        code=str(code or 'probe_failed')
        detail=str(detail)[:500]
        attempts=(int(previous.metadata.get('probe_attempts',0))+1
                  if previous is not None and isinstance(previous.metadata.get('probe_attempts',0),int)
                  else 1)
        if previous is not None:
            records=list(previous.records);anchors=dict(previous.anchors)
            completed=list(previous.completed_partitions);total=previous.total_partitions
            sampled=previous.sampled;issues=list(previous.issues)
            metadata=dict(previous.metadata)
            # Keep an in-flight checkpoint: a transient failure while a
            # segment is being continued must not throw away completed rows.
            gaps=[gap for gap in previous.gaps if gap.code != code]
            if not isinstance(previous.metadata.get('resume'),dict):
                metadata.pop('resume',None)
                gaps=[gap for gap in gaps if gap.code != BUDGET_GAP]
            revision=previous.source_revision;kind=previous.kind
        else:
            records=[];anchors={};completed=[];total=None;sampled=False;issues=[]
            metadata={'structure_fingerprint':digest([self.wb.scope,source.source_id,'unprobed'])}
            gaps=[];revision='sha256:'+digest([self.wb.scope,source.source_id,'probe-failed'])
            kind=Path(source.locator_ref).suffix.lstrip('.') if source.kind=='file' else source.kind
        partition=1
        state=previous.metadata.get('resume') if previous is not None else None
        if isinstance(state,dict):
            partition=(state.get('next_row') or state.get('next_page')
                       or state.get('next_block') or state.get('next_sheet') or 1)
            if not any(gap.code==BUDGET_GAP for gap in gaps):
                gaps.append(CoverageGap(partition=partition,code=BUDGET_GAP))
        gaps.append(CoverageGap(partition=partition,code=code,detail=detail[:200]))
        metadata.update({'probe_error':{'code':code,'detail':detail,
                                         'retryable':bool(retryable)},
                         'probe_attempts':attempts,
                         'structure_fingerprint':metadata.get('structure_fingerprint')
                             or digest([self.wb.scope,source.source_id,'unprobed'])})
        fields=list(dict.fromkeys(key for row in records for key in row))
        return SourceProfile(source_id=source.source_id,source_revision=revision,kind=kind,
            records=records,fields=fields,anchors=anchors,metadata=metadata,
            total_partitions=total,completed_partitions=completed,gaps=gaps,
            sampled=sampled,issues=issues),attempts

    def advance(self,session_id,ctx):
        wb=self.wb;s=wb.sessions.get(session_id,ctx)
        if s.phase == 'saved':return s
        prior_profiles = {profile.source_id: profile for profile in self._profiles(s)}
        if is_discovery(s) and prior_profiles and s.phase != 'probing' and 'retry_probe' not in s.next_actions:
            return s
        if s.phase == 'preview' and not any(_rest_retryable(profile) or _resumable(profile) for profile in prior_profiles.values()):
            return s
        if s.phase == 'needs_input' and 'retry_probe' not in s.next_actions:
            # A completed or permanently failed observation must not be probed
            # again just because the agent asked advance once more.  A newly
            # registered verified mapping is still picked up here.
            if s.next_actions == ['repair_source']:
                return s
            if not any(_resumable(profile) for profile in prior_profiles.values()):
                profiles=list(prior_profiles.values())
                if (not is_discovery(s) and profiles and not s.issues
                        and all(profile.coverage=='full' for profile in profiles)):
                    if self._reuse_verified_mapping(s,profiles,ctx):
                        return wb.sessions.get(s.id,ctx)
                return s
        client=wb.layer_client or LayerClient(installed_data_package(wb.workspace))
        versions=s.selected_versions.copy()
        job=wb.store.current('job',s.job_ref,scope=wb.scope)
        s=wb.sessions.update(s.id,s.revision,{'phase':'probing','issues':[]},ctx,
            extra_writes=[Write('job',s.job_ref,wb.scope,{**job['body'],'state':'running'},job['revision'])])
        errors=[];budget_exhausted=False;probed_any=False
        deadline=_probe_deadline(self.budget_seconds)
        for source in s.sources:
            if budget_exhausted:break
            previous = prior_profiles.get(source.source_id)
            if previous is not None and (_exhausted_failure(previous)
                    or not (_rest_retryable(previous) or _resumable(previous)
                            or _retryable_failure(previous))):
                continue
            selection = source
            if is_discovery(s):
                selection = source.model_copy(update={'options': {**source.options, 'sample_strategy': 'per_table'}})
            segments=0;last_progress=None
            while True:
                remaining=deadline-time.monotonic()
                if remaining <= _MIN_SEGMENT_SECONDS and (probed_any or segments):
                    budget_exhausted=True
                    break
                try:
                    profile=(client.probe(selection,ctx,wb.workspace,previous=previous,
                                          budget_seconds=max(remaining,0.05))
                             if previous is not None
                             else client.probe(selection,ctx,wb.workspace,
                                               budget_seconds=max(remaining,0.05)))
                except (DataLayerProbeError,ValueError,OSError,TimeoutError) as exc:
                    if isinstance(exc,DataLayerProbeError):
                        code,retryable=exc.code,bool(exc.retryable)
                    else:
                        # The data layer was never reached (for example the
                        # selected connection is not configured).  The agent
                        # can correct the selection, but only for one retry.
                        code,retryable='probe_failed',True
                    detail=str(exc)[:500]
                    profile,attempts=self._failure_profile(source,previous,
                        code=code,detail=detail,retryable=retryable)
                    errors.append({'code':'intake.probe_failed','source_id':source.source_id,
                        'target':source.source_id,'detail':detail,'error_code':str(code),
                        'attempts':attempts,'retryable':retryable})
                    s=self._store_profile(s,versions,source,profile,ctx)
                    probed_any=True
                    break
                probed_any=True
                s=self._store_profile(s,versions,source,profile,ctx)
                previous=profile
                segments+=1
                if _rest_retryable(profile) or not _resumable(profile):
                    break
                progress=_deadline_key(profile)
                if last_progress == progress:
                    errors.append({'code':'intake.probe_stalled','source_id':source.source_id,
                        'detail':'probe returned the same checkpoint without progress',
                        'retryable':False,'attempts':segments})
                    break
                last_progress=progress
                if segments >= _MAX_SEGMENTS:
                    errors.append({'code':'intake.probe_segment_limit','source_id':source.source_id,
                        'detail':'segment limit reached in one advance','retryable':False,
                        'attempts':segments})
                    break
                if time.monotonic() >= deadline:
                    budget_exhausted=True
                    break
        job=wb.store.current('job',s.job_ref,scope=wb.scope)
        profiles=self._profiles(s)
        resumable=any(_resumable(profile) for profile in profiles)
        exhausted=any(_exhausted_failure(profile) for profile in profiles)
        retryable_errors=[error for error in errors
                          if error.get('retryable') and error.get('attempts',1) < 2]
        permanent_errors=[error for error in errors if not error.get('retryable')]
        retry=(not exhausted and not permanent_errors
               and (bool(retryable_errors) or resumable or budget_exhausted
                    or not profiles
                    or any(_rest_retryable(profile) for profile in profiles)))
        if exhausted:
            next_action='select_source' if is_discovery(s) else 'repair_source'
        elif errors and not retry:
            next_action='select_source' if is_discovery(s) else 'repair_source'
        elif retry:
            next_action='retry_probe'
        elif is_discovery(s):
            next_action='propose_discovery' if profiles[0].metadata.get('tables') else 'select_source'
        else:
            next_action='propose_mapping'
        s=wb.sessions.update(s.id,s.revision,{'phase':'needs_input','issues':errors,
            'next_actions':[next_action]},ctx,
            extra_writes=[Write('job',s.job_ref,wb.scope,{**job['body'],'state':'needs_input','checkpoint':'profiles'},job['revision'])])
        if (not is_discovery(s) and profiles and not errors and not retry
                and all(profile.coverage=='full' for profile in profiles)):
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
                         'kind':record.get('kind'),'mapping':MappingSpec.model_validate(record['mapping']),
                         'derived_fields':record.get('derived_fields')}
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
            if cached is None:continue
            session,profiles=self._replay_derived_fields(session,profiles,cached,ctx)
            if self._reuse_cached_mapping(session,profiles,cached,ctx):
                return True
        return False

    def _match_cached_profile(self,record,profiles,sources):
        """Find the fresh profile described by one cached source record."""
        source_id=record.get('source_id')
        locator,kind=record.get('locator_ref'),record.get('kind')
        if source_id in profiles:
            selection=sources.get(source_id)
            if locator is not None and (selection is None or selection.locator_ref!=locator
                                        or selection.kind!=kind):
                return None
            return profiles[source_id]
        matches=[profile for profile in profiles.values()
                 if sources.get(profile.source_id) is not None
                 and sources[profile.source_id].locator_ref==locator
                 and sources[profile.source_id].kind==kind]
        return matches[0] if len(matches)==1 else None

    def _replay_derived_fields(self,session,profiles,cached,ctx):
        """Restore text-extracted fields before reusing a verified mapping.

        The fingerprint deliberately ignores extracted fields.  Replaying the
        recorded exact spans keeps a reusable mapping executable instead of
        submitting bindings for fields the fresh probe has not produced.
        """
        records=self._cached_sources(cached['body'])
        if not records:return session,profiles
        current={profile.source_id:profile for profile in profiles}
        sources={source.source_id:source for source in session.sources}
        updates={}
        for record in records:
            specs=record.get('derived_fields')
            if not specs:continue
            profile=self._match_cached_profile(record,current,sources)
            if profile is None or profile.source_id in updates:continue
            updated=replay_fields(profile,specs,
                                  identity_fields=tuple(self.wb.definition.identity_fields))
            if updated.model_dump(mode='json')!=profile.model_dump(mode='json'):
                updates[profile.source_id]=updated
        if not updates:return session,profiles
        versions=dict(session.selected_versions)
        writes=[]
        for source_id,updated in updates.items():
            ref=versions.get('profile:'+source_id)
            if ref is None:continue
            profile_id,revision=ref.rsplit('@',1)
            versions['profile:'+source_id]=f'{profile_id}@{int(revision)+1}'
            writes.append(Write('profile',profile_id,self.wb.scope,
                                updated.model_dump(mode='json'),revision))
        if not writes:return session,profiles
        session=self.wb.sessions.update(session.id,session.revision,
            {'selected_versions':versions},ctx,extra_writes=writes)
        return session,self._profiles(session)

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
            request=self.wb.discovery.request(s, profiles)
            if profiles:
                request['resume']=profiles[0].metadata.get('resume')
            request['issues']=list(s.issues)
            return request
        request=mapping_request(s, profiles, self.wb.definition, self.wb.allowed_model_fields)
        # The agent needs the failure code and the continuation point on the
        # same request that tells it to retry, not only in an internal log.
        request['issues']=list(s.issues)
        for item,profile in zip(request.get('sources',[]),profiles):
            item['completed_partitions']=profile.completed_partitions
            item['total_partitions']=profile.total_partitions
            item['resume']=profile.metadata.get('resume')
        return request

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
        updated = extract_fields(profile, fields, allowed, remember=True,
                                 identity_fields=tuple(self.wb.definition.identity_fields))
        versions = dict(session.selected_versions)
        if 'preview' in versions:
            # Re-proposing after extraction must still find the web corrections
            # that were applied to the preview being replaced.
            versions['corrections_from'] = versions['preview']
        versions.pop('preview', None)
        versions[key] = f'{profile_id}@{int(revision) + 1}'
        wb.sessions.update(session_id, expected_revision, {
            'phase': 'needs_input', 'selected_versions': versions,
            'issues': [], 'next_actions': ['propose_mapping'],
        }, ctx, extra_writes=[
            Write('profile', profile_id, wb.scope, updated.model_dump(mode='json'), revision),
        ])
        return self.inference_request(session_id, ctx)

    def _prior_preview(self, session):
        """Load the newest preview that still carries web corrections or pending ones."""
        for key in ('preview', 'corrections_from'):
            ref = session.selected_versions.get(key)
            if not ref:
                continue
            try:
                preview_id, revision = ref.rsplit('@', 1)
            except ValueError:
                continue
            row = self.wb.store.get('preview', preview_id, revision, scope=self.wb.scope)
            if row is None:
                continue
            body = row['body']
            pending = (body.get('extensions') or {}).get(_PENDING_CORRECTIONS)
            if body.get('corrections') or pending:
                return ref, body
        return None, None

    def _object_label(self, instance, names):
        values = instance.get('values') or {}
        keys = [str(values[field]) for field in self.wb.definition.identity_fields
                if values.get(field) not in (None, '')]
        if keys:
            return ' · '.join(keys)
        for anchors in (instance.get('source_anchors') or {}).values():
            for anchor in anchors or []:
                selector = anchor.get('selector') or {}
                source_id = anchor.get('source_ref')
                display = names.get(source_id, source_id or '来源')
                where = []
                if selector.get('page') is not None:
                    where.append(f'第 {selector["page"]} 页')
                row_keys = selector.get('keys')
                if isinstance(row_keys, dict) and row_keys.get('row') is not None:
                    where.append(f'第 {row_keys["row"]} 行')
                elif selector.get('range'):
                    where.append(str(selector['range']))
                suffix = ' ' + ' '.join(where) if where else ''
                return f'未识别单据（{display}{suffix}）'
        return '未识别单据'

    def _object_labels(self, session, body):
        names = {source.source_id: str(source.options.get('display_name') or source.locator_ref)
                 for source in session.sources}
        return {instance['id']: self._object_label(instance, names)
                for instance in body.get('instances', []) if instance.get('id')}

    def issue_summary(self, session, body):
        """Name the affected object and the reason for every preview issue."""
        labels = self._object_labels(session, body)
        names = {source.source_id: str(source.options.get('display_name') or source.locator_ref)
                 for source in session.sources}
        summary = []
        for issue in body.get('issues') or []:
            code = str(issue.get('code') or '')
            label = issue.get('object') or labels.get(issue.get('entity_id'))
            if label is None and issue.get('source_id') is not None:
                source_id = issue['source_id']
                label = '来源 ' + names.get(source_id, source_id)
            if label is None and issue.get('row') is not None:
                label = f'第 {int(issue["row"]) + 1} 行'
            item = {'code': code, 'target': issue.get('target'),
                    'object': label or '全部对象',
                    'reason': issue.get('detail') or _ISSUE_REASONS.get(code, code)}
            for key in ('entity_id', 'row', 'source_id'):
                if key in issue:
                    item[key] = issue[key]
            summary.append(item)
        return summary

    def _refresh_preview(self, body):
        fields = MappingPreview.model_fields
        data = {key: value for key, value in body.items() if key in fields}
        # The stored body is JSON; restore typed business values on a copy so
        # callers see the same decimals/integers the first materialization
        # produced without changing what is persisted.
        instances = []
        for instance in data.get('instances', []):
            instance = dict(instance)
            values = dict(instance.get('values') or {})
            for prop, definition in self.wb.definition.properties.items():
                if values.get(prop) is None:
                    continue
                try:
                    values[prop] = _typed(values[prop], definition.value_type)
                except (ValueError, ArithmeticError):
                    pass
            instance['values'] = values
            instances.append(instance)
        if instances:
            data['instances'] = instances
        return MappingPreview.model_validate(data)

    def _carry_corrections(self, session, body):
        """Re-apply web corrections to a freshly prepared preview.

        Valid corrections stay in the new preview with their manual evidence.
        A correction that can no longer be applied is reported as an explicit
        issue instead of being dropped silently.
        """
        prior_ref, prior = self._prior_preview(session)
        if prior is None:
            return prior_ref, [], [], []
        # A legacy preview may reference a prior preview through
        # corrections_from instead of carrying pending conflicts itself.
        bodies = []
        extra_ref = session.selected_versions.get('corrections_from')
        if extra_ref and extra_ref != prior_ref:
            try:
                preview_id, revision = extra_ref.rsplit('@', 1)
            except ValueError:
                pass
            else:
                row = self.wb.store.get('preview', preview_id, revision, scope=self.wb.scope)
                if row is not None:
                    bodies.append(row['body'])
        bodies.append(prior)
        # Pending conflicts must survive every subsequent proposal until they
        # are applied or explicitly replaced.  Aggregate by decision_ref so a
        # partially applied batch cannot hide the rest on the next round.
        collected = {}
        prior_labels = {}
        for source in bodies:
            prior_labels.update(self._object_labels(session, source))
            for correction in (*((source.get('extensions') or {}).get(_PENDING_CORRECTIONS) or []),
                               *(source.get('corrections') or [])):
                key = correction.get('decision_ref') or digest(correction)
                collected[key] = correction
        ontology = self.wb.definition
        mapping = body.get('mapping') or {}
        instances = {instance['id']: instance for instance in body.get('instances', [])}
        applied, conflicts, unresolved = [], [], []
        for correction in collected.values():
            label_hint = correction.get('object_label')
            correction = {key: value for key, value in correction.items()
                          if key != 'object_label'}
            entity_id = correction.get('entity_id')
            prop = correction.get('property')
            definition = ontology.properties.get(prop) if isinstance(prop, str) else None
            target = instances.get(entity_id)
            label = (prior_labels.get(entity_id) or label_hint
                     or entity_id or '未知对象')
            if target is None:
                conflicts.append((label, prop, '纠正对象在新预览中不存在'))
                unresolved.append({**correction, 'object_label': label})
                continue
            if definition is None:
                conflicts.append((label, prop, '目标属性不在当前本体中'))
                unresolved.append({**correction, 'object_label': label})
                continue
            if prop in ontology.identity_fields:
                conflicts.append((label, prop, '身份字段纠正会改变对象标识，需要在网页重新核对'))
                unresolved.append({**correction, 'object_label': label})
                continue
            try:
                value = _typed(correction.get('value'), definition.value_type)
            except (ValueError, ArithmeticError):
                conflicts.append((label, prop, '纠正值无法按目标类型解析'))
                unresolved.append({**correction, 'object_label': label})
                continue
            if value is None:
                conflicts.append((label, prop, '纠正值不能为空'))
                unresolved.append({**correction, 'object_label': label})
                continue
            target.setdefault('values', {})[prop] = to_jsonable_python(value)
            target['unresolved'] = [item for item in target.get('unresolved', []) if item != prop]
            evidence = SourceAnchor(
                source_ref=str(correction.get('decision_ref') or 'correction').rsplit('@', 1)[0] or 'correction',
                source_revision='1', selector={'kind': 'json_pointer',
                                               'pointer': '/decision/changes/value'},
            )
            target.setdefault('source_anchors', {}).setdefault(prop, []).append(
                evidence.model_dump(mode='json'))
            applied.append((correction, target, prop, value, evidence))
        if applied:
            touched = {(correction.get('entity_id'), correction.get('property'))
                       for correction, _, _, _, _ in applied}
            selected = [fact for fact in body.get('facts', [])
                        if not (fact.get('relation') in ontology.properties
                                and any((role.get('value'), fact.get('relation')) in touched
                                        for role in fact.get('role_bindings', [])
                                        if role.get('role') == 'subject'))]
            bindings = mapping.get('bindings') or {}
            relation_bindings = mapping.get('relation_bindings') or {}
            for correction, target, prop, value, evidence in applied:
                entity_id = target['id']
                roles = [RoleBinding(role='subject', value=entity_id, value_type='reference'),
                         RoleBinding(role='value', value=value,
                                     value_type=ontology.properties[prop].value_type)]
                relations = [(prop, roles)]
                binding = bindings.get(prop)
                for fact in list(selected):
                    role_map = relation_bindings.get(fact['relation'], {})
                    changed = [role for role, item in role_map.items()
                               if binding is not None and item == binding]
                    refers = any(role.get('value_type') == 'reference'
                                 and role.get('value') == entity_id
                                 for role in fact.get('role_bindings', []))
                    if changed and refers:
                        roles = [RoleBinding.model_validate({**role, 'value': value}
                                                            if role['role'] in changed else role)
                                 for role in fact['role_bindings']]
                        relations.append((fact['relation'], roles))
                        selected.remove(fact)
                decision_ref = str(correction.get('decision_ref') or f'correction:{prop}@1')
                for relation, relation_roles in relations:
                    fact_id = relation_key(self.wb.scope, relation, relation_roles)
                    assertion_id = 'assertion:' + digest([fact_id, decision_ref])
                    assertion = Assertion(
                        id=assertion_id, scope=self.wb.scope,
                        ontology_revision=body['ontology_revision'], relation=relation,
                        role_bindings=relation_roles, source_anchors=[evidence],
                        mapping_revision=f'{mapping["id"]}@{mapping["revision"]}',
                        extractor_version='user_correction',
                        extensions={'review.decision': decision_ref},
                    )
                    body.setdefault('assertions', []).append(assertion.model_dump(mode='json'))
                    selected = [fact for fact in selected if fact['id'] != fact_id]
                    selected.append({'id': fact_id, 'relation': relation,
                                     'role_bindings': [role.model_dump(mode='json')
                                                       for role in relation_roles],
                                     'assertion_refs': [assertion_id]})
            body['facts'] = selected
            body['corrections'] = [correction for correction, _, _, _, _ in applied]
            corrected = {(correction.get('entity_id'), correction.get('property'))
                         for correction, _, _, _, _ in applied}
            still_unresolved = {prop for instance in body.get('instances', [])
                                for prop in instance.get('unresolved', [])}
            def replaced(issue):
                key = (issue.get('entity_id'), issue.get('target'))
                if issue.get('entity_id') is not None:
                    return key in corrected
                return issue.get('target') not in still_unresolved
            body['issues'] = [issue for issue in body.get('issues', [])
                              if not (issue.get('code') in _RESOLVABLE_ISSUES
                                      and replaced(issue))]
        for label, prop, reason in conflicts:
            body.setdefault('issues', []).append({
                'code': 'ontology.correction_conflict',
                'target': prop or 'unknown', 'object': label, 'detail': reason,
            })
        extensions = dict(body.get('extensions') or {})
        if unresolved:
            extensions[_PENDING_CORRECTIONS] = unresolved
        else:
            extensions.pop(_PENDING_CORRECTIONS, None)
        if extensions:
            body['extensions'] = extensions
        else:
            body.pop('extensions', None)
        if applied or conflicts:
            content = {key: body[key] for key in
                       ('ontology_revision', 'mapping', 'source_revisions', 'instances', 'issues')}
            if body.get('extensions'):
                content['extensions'] = body['extensions']
            body['digest'] = digest(content)
        return prior_ref, applied, conflicts, unresolved

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
        prior_ref,_,conflicts,pending=self._carry_corrections(s,body)
        preview=self._refresh_preview(body)
        versions={**s.selected_versions,'preview':preview.id+'@1','mapping':mid+'@'+revision}
        if prior_ref and pending:versions['corrections_from']=prior_ref
        else:versions.pop('corrections_from',None)
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
        prior_ref,_,conflicts,pending=self._carry_corrections(session,body)
        preview=self._refresh_preview(body)
        versions.update(preview=preview.id+'@1', mapping=f'{primary.id}@{primary.revision}')
        if prior_ref and pending:versions['corrections_from']=prior_ref
        else:versions.pop('corrections_from',None)
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
        active=wb.store.get('preview',id,rev,scope=wb.scope)
        draft=wb.store.current('ui_draft',s.id,scope=wb.scope)
        if decision.target_scope=='mapping' and decision.decision=='save' and draft and active:
            from dataagent_contracts.ontology import FieldBinding
            def normalize(bindings):
                return {k:FieldBinding.model_validate(v).model_dump(mode='json',exclude_defaults=True,exclude_none=True) for k,v in bindings.items()}
            current=active['body']
            source_mappings=(current.get('extensions') or {}).get('intake.source_mappings', {})
            if any(key not in source_mappings or normalize(bindings)!=normalize(source_mappings[key]['bindings'])
                   for key,bindings in draft['body'].get('source_bindings', {}).items()):
                raise VersionConflict('draft changed; generate a new preview before saving')
            if 'bindings' in draft['body'] and normalize(draft['body']['bindings'])!=normalize(current['mapping']['bindings']):
                raise VersionConflict('draft changed; generate a new preview before saving')
        # A whole-batch save names the affected objects instead of only saying
        # that the preview still has issues.
        if (decision.decision=='save' and not decision.changes and active
                and active['body'].get('issues')):
            raise PreviewBlocked(self.issue_summary(s,active['body']))
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
            profiles={profile.source_id:profile for profile in self._profiles(s)}
            def record(source_id,locator_ref,kind,item):
                entry={'source_id':source_id,'locator_ref':locator_ref,'kind':kind,'mapping':item}
                profile=profiles.get(source_id) if source_id else None
                if profile is not None and profile.metadata.get('derived_fields'):
                    # Keep the exact text spans so the next intake can rebuild
                    # fields that the source structure alone cannot reproduce.
                    entry['derived_fields']=profile.metadata['derived_fields']
                return entry
            if source_mappings:
                records=[record(source_id,selections[source_id].locator_ref,
                                selections[source_id].kind,item)
                         for source_id,item in source_mappings.items() if source_id in selections]
            else:
                source=selections.get(next(iter(selected))) if len(selected)==1 else None
                records=[record(source.source_id if source else None,
                                source.locator_ref if source else None,
                                source.kind if source else None,mapping)]
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
        if body is not None:
            # The stored preview keeps the machine codes; the view adds the
            # affected object labels and reasons, and never truncates the list.
            body=dict(body)
            body['issues']=self.issue_summary(s,body)
            body['issue_count']=len(body['issues'])
            body['object_labels']=self._object_labels(s,body)
            body['object_count']=len(body.get('instances',[]))
        draft=self.wb.store.current('ui_draft',s.id,scope=wb.scope)
        profiles = self._profiles(s)
        return {'session':s.model_dump(mode='json'),'profiles':[p.model_dump(mode='json') for p in profiles],
            'discovery':wb.discovery.state(s, profiles),
            'ontology':wb.definition.model_dump(mode='json'),'preview':body,
            'draft':draft['body'] if draft else {},
            'issue_count':body['issue_count'] if body else len(s.issues),
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
