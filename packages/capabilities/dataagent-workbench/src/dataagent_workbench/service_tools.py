"""Host-bound aggregate tools shared by CLI and MCP."""
import json
from uuid import uuid4
from dataagent_contracts.core import CapabilityResult, CapabilityStatus, Continuation, VersionedRef
from dataagent_contracts.intake import WorkSpec, SourceSelection
from dataagent_contracts.core import Issue
from dataagent_contracts.ontology import ReviewDecision
from .ontology_discovery import DISCOVERY_MODE, discovery_detail, evidence_summary
from .tool_schema import MODELS


def _public_output(value):
    """Remove credential-bearing fields before a result leaves the workbench."""

    if isinstance(value, dict):
        return {key: _public_output(item) for key, item in value.items()
                if not str(key).lower().rsplit('.', 1)[-1].startswith('credential')}
    if isinstance(value, list):
        return [_public_output(item) for item in value]
    return value


def invoke(wb, name, args):
    result = _invoke(wb, name, args)
    data = _public_output(result.data)
    return result if data == result.data else result.model_copy(update={'data': data})


def _review_decision(value):
    """Convert the explicit per-target_scope tool decision into the contract model."""
    if isinstance(value, ReviewDecision):
        return value
    changes = (value.changes.model_dump(mode='json', exclude_unset=True)
               if getattr(value, 'changes', None) is not None else {})
    return ReviewDecision(preview_ref=value.preview_ref, target_scope=value.target_scope,
                          changes=changes, decision=value.decision)


def _with_discovery_detail(request, typed):
    """Attach one on-demand table/section view to a discovery request.

    The base request stays complete in memory (and in the result file); only
    the named slice is added under a private key so the model-facing summary
    can expose it as ``details`` without reading the result file repeatedly.
    """
    wants_detail = bool(typed.detail_table or typed.detail_section)
    if not wants_detail:
        if typed.detail_offset or typed.detail_limit != 50:
            raise ValueError(
                'detail_offset/detail_limit require detail_table or detail_section')
        return request
    if request.get('kind') != DISCOVERY_MODE:
        raise ValueError(
            'detail_table/detail_section are only available for ontology discovery evidence')
    return {**request, '_discovery_detail': discovery_detail(
        request, table=typed.detail_table, section=typed.detail_section,
        offset=typed.detail_offset, limit=typed.detail_limit)}


def _invoke(wb, name, args):
    if name not in MODELS:raise ValueError('unknown aggregate tool')
    typed=MODELS[name].model_validate(args)
    args=typed.model_dump(mode='json')
    if name == 'intake_start':
        goal = WorkSpec(id=uuid4().hex,goal=args['goal'],
            acceptance_criteria=args.get('acceptance_criteria',['来源可核对']),authorization_ref=wb.authorization)
        handle = wb.sessions.start([SourceSelection.model_validate(s) for s in args['sources']],goal,wb.ctx,
            mode=typed.mode,target=typed.target)
        return CapabilityResult(status=CapabilityStatus.pending,data=handle.model_dump(mode='json'),
            continuation=Continuation(job_ref=handle.job_ref))
    if name == 'intake_status':
        data=wb.sessions.get(args['session_id'],wb.ctx).model_dump(mode='json')
        data['issues']=[{k:i[k] for k in ['code','source_id','target','detail'] if k in i} for i in data['issues']]
        data['issue_count']=len(data['issues'])
        return CapabilityResult.ok(data)
    if name in {'intake_advance','intake_inference'}:
        session=(wb.intake.advance(args['session_id'],wb.ctx) if name=='intake_advance'
            else wb.sessions.get(args['session_id'],wb.ctx))
        request=wb.intake.inference_request(session.id,wb.ctx)
        if request.get('kind') == DISCOVERY_MODE:
            request = _with_discovery_detail(request, typed)
        elif (typed.detail_table or typed.detail_section
              or typed.detail_offset or typed.detail_limit != 50):
            raise ValueError(
                'detail_table/detail_section are only available for ontology discovery evidence')
        if request['kind'] == 'ontology_discovery':
            if session.phase == 'needs_input':
                action, = session.next_actions
                code, message, suggestion = {
                    'retry_probe': ('intake.probe_failed', 'SQLite 来源待探查', '检查来源后继续探查'),
                    'select_source': ('intake.discovery_no_tables', '未找到可探查的表', '选择含业务表的 SQLite 文件'),
                    'propose_discovery': ('intake.discovery_proposal_required', '来源已探查，需要本体提案',
                                          '提交 ontology_discovery_propose'),
                }[action]
                return CapabilityResult(status=CapabilityStatus.needs_input, data=request, issues=[
                    Issue(code=code, message=message, severity='warning', retryable=action == 'retry_probe',
                          suggested_action=suggestion),
                ])
            return CapabilityResult.ok(request)
        if session.phase=='needs_input':
            return CapabilityResult(status=CapabilityStatus.needs_input,data=request,
                issues=[Issue(code='intake.proposal_required',message='来源已探查，需要映射提案或补充材料',
                    severity='warning',retryable=False,
                    suggested_action='根据获准样本提交 intake_propose；有关键歧义时请用户补充',
                    inference_request=request)])
        return CapabilityResult.ok({'session_id':session.id,'phase':session.phase,'revision':session.revision})
    if name == 'ontology_discovery_propose':
        return CapabilityResult.ok(wb.discovery.propose(
            typed.session_id, typed.proposal, typed.expected_revision, wb.ctx,
        ))
    if name == 'ontology_registry':
        data = wb.ontology.registry(wb.ctx)
        if not typed.include_deactivated:
            data = {**data, 'ontologies': [
                item for item in data['ontologies']
                if item.get('state') == 'active']}
        return CapabilityResult.ok(data)
    if name == 'ontology_query':
        # Read-only: published snapshots only, never the fact table.
        return CapabilityResult.ok(wb.queries.query(typed, wb.ctx))
    if name == 'ontology_instances_summary':
        return CapabilityResult.ok(wb.queries.summary(typed, wb.ctx))
    if name == 'ontology_publish_prepare':
        candidate = wb.publisher.prepare(typed, wb.ctx)
        return CapabilityResult(status=CapabilityStatus.needs_input, data=candidate, issues=[Issue(
            code='ontology.human_confirmation_required',
            message='本体候选已生成；发布必须由人在工作台网页确认，Agent 工具不能代为确认',
            severity='warning', retryable=False,
            suggested_action='打开工作台核对草案修订、来源快照摘要与候选定义摘要后确认发布',
        )])
    if name == 'ontology_publish_confirm':
        # The confirmation fact itself must arrive through the local web
        # channel with the host subject.  A tool call can only report that.
        return CapabilityResult(status=CapabilityStatus.needs_input, data={
            'candidate_ref': typed.candidate_ref,
            'session_id': typed.session_id,
            'human_confirmation_required': True,
            'confirm_route': '/api/sessions/%s/publish/confirm' % typed.session_id,
        }, issues=[Issue(
            code='ontology.human_confirmation_required',
            message='本体发布必须由人在工作台网页确认；MCP 工具不得代为确认',
            severity='warning', retryable=False,
            suggested_action='在工作台网页核对草案修订、来源快照摘要与候选定义摘要后确认',
        )])
    if name == 'intake_extract':
        return CapabilityResult.ok(wb.intake.extract_document_fields(
            typed.session_id, typed.source_id, typed.fields, typed.expected_revision, wb.ctx,
        ))
    if name in {'intake_propose','intake_propose_sources'}:
        if name=='intake_propose_sources':
            preview=wb.intake.submit_source_proposals(typed.session_id,typed.proposals,typed.expected_revision,wb.ctx)
        else:
            preview=wb.intake.submit_proposal(typed.session_id,typed.proposal,typed.expected_revision,wb.ctx)
        view=wb.intake.view(args['session_id'],wb.ctx);body=view['preview'] or {}
        return CapabilityResult.ok({'preview_ref':preview.id+'@'+preview.revision,
            'session_revision':wb.sessions.get(args['session_id'],wb.ctx).revision,
            'next_tool':'mapping_apply' if not preview.issues else 'intake_propose',
            'instance_count':len(preview.instances),
            'issue_count':body.get('issue_count',len(preview.issues)),
            'issues':body.get('issues',[]),
            'object_labels':body.get('object_labels',{}),
            'conflicts':body.get('conflicts',[]),
            'disposition_options':body.get('disposition_options',[]),
            'inheritance':body.get('inheritance')})
    if name=='mapping_preview':
        view=wb.intake.view(args['session_id'],wb.ctx);preview=view['preview']
        return CapabilityResult.ok(None if preview is None else {'preview_ref':preview['id']+'@'+preview['revision'],
            'review_state':preview['review_state'],'instance_count':len(preview['instances']),
            'issue_count':preview.get('issue_count',len(preview['issues'])),
            'issues':preview['issues'],'object_labels':preview.get('object_labels',{}),
            'conflicts':preview.get('conflicts',[]),
            'inheritance':preview.get('inheritance'),
            'dispositions':preview.get('dispositions',[]),
            'disposition_options':preview.get('disposition_options',[]),
            'suspended':preview.get('suspended',[]),
            'unidentified_records':preview.get('unidentified_records',[])})
    if name=='mapping_apply':
        receipt=wb.intake.apply(args['session_id'],_review_decision(typed.decision),
            args['expected_revision'],wb.ctx,allow_partial=typed.allow_partial,reason=typed.reason)
        data=receipt.model_dump(mode='json')
        partial=(data.get('extensions') or {}).pop('intake.partial_save',None)
        if partial:
            for key in ('saved','suspended','unidentified_records','release_ref',
                        'reason','recorded_at','subject_ref'):
                if key in partial:data[key]=partial[key]
            data['partial']=True
        return CapabilityResult.ok(data)
    if name=='intake_dispose':
        return CapabilityResult.ok(wb.intake.dispose(args['session_id'],typed,args['expected_revision'],wb.ctx))
    if name=='intake_inherit':
        return CapabilityResult.ok(wb.intake.inherit_corrections(
            args['session_id'],args['expected_revision'],typed.decision_refs,wb.ctx))
    if name == 'source_connections':
        from .adapters.source_connections import SourceConnections
        return CapabilityResult.ok({'connections':SourceConnections().list()})
    if name == 'workflow_call':
        from .adapters.operations_client import call_operations
        return call_operations(wb, typed.operation, typed.arguments)
    if name == 'workflow_view':
        from .launcher import open_view
        return CapabilityResult.ok(open_view(wb, run_id=typed.run_id))
    if name == 'workbench_view':
        from .launcher import open_view
        wb.sessions.get(args['session_id'],wb.ctx)
        return CapabilityResult.ok(open_view(wb,args['session_id']))
    if name == 'intake_extract_records':
        return CapabilityResult.ok(wb.intake.extract_clause_records(
            typed.session_id, typed.source_id, typed.records, typed.expected_revision, wb.ctx,
        ))
    raise ValueError('unknown aggregate tool')


def result_summary(wb, result):
    payload = result.model_dump(mode='json')
    path = wb.root/'results'/f'{uuid4().hex}.json'
    path.parent.mkdir(exist_ok=True)
    data = payload.get('data')
    if (isinstance(data, dict) and data.get('kind') == DISCOVERY_MODE
            and isinstance(data.get('catalog'), dict)):
        # The model sees the structural summary (plus one requested detail
        # slice); the result file stays complete for the web and for an
        # explicit single read by a human or agent.
        detail = data.pop('_discovery_detail', None)
        summary = evidence_summary(data)
        if detail is not None:
            summary['details'] = detail
        path.write_text(json.dumps(payload,ensure_ascii=False,indent=2))
        return {'status':payload['status'],
                'result_path':str(path.relative_to(wb.workspace)),
                'summary':True,'result':summary}
    path.write_text(json.dumps(payload,ensure_ascii=False,indent=2))
    summary = {'status':payload['status'],'result_path':str(path.relative_to(wb.workspace))}
    encoded = json.dumps(payload,ensure_ascii=False)
    if len(encoded.encode()) < 24000:
        summary['result'] = payload
    return summary
