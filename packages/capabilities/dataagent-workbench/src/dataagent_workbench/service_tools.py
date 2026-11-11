"""Host-bound aggregate tools shared by CLI and MCP."""
import json
from uuid import uuid4
from dataagent_contracts.core import CapabilityResult, CapabilityStatus, Continuation, VersionedRef
from dataagent_contracts.intake import WorkSpec, SourceSelection
from dataagent_contracts.core import Issue
from .tool_schema import MODELS


def invoke(wb, name, args):
    if name not in MODELS:raise ValueError('unknown aggregate tool')
    typed=MODELS[name].model_validate(args)
    args=typed.model_dump(mode='json')
    if name == 'intake_start':
        goal = WorkSpec(id=uuid4().hex,goal=args['goal'],
            acceptance_criteria=args.get('acceptance_criteria',['来源可核对']),authorization_ref=wb.authorization)
        handle = wb.sessions.start([SourceSelection.model_validate(s) for s in args['sources']],goal,wb.ctx)
        return CapabilityResult(status=CapabilityStatus.pending,data=handle.model_dump(mode='json'),
            continuation=Continuation(job_ref=handle.job_ref))
    if name == 'intake_status':
        data=wb.sessions.get(args['session_id'],wb.ctx).model_dump(mode='json')
        data['issues']=[{k:i[k] for k in ['code','source_id','target'] if k in i} for i in data['issues']]
        return CapabilityResult.ok(data)
    if name in {'intake_advance','intake_inference'}:
        session=(wb.intake.advance(args['session_id'],wb.ctx) if name=='intake_advance'
            else wb.sessions.get(args['session_id'],wb.ctx))
        request=wb.intake.inference_request(session.id,wb.ctx)
        if session.phase=='needs_input':
            return CapabilityResult(status=CapabilityStatus.needs_input,data=request,
                issues=[Issue(code='intake.proposal_required',message='来源已探查，需要映射提案或补充材料',
                    severity='warning',retryable=False,
                    suggested_action='根据获准样本提交 intake_propose；有关键歧义时请用户补充',
                    inference_request=request)])
        return CapabilityResult.ok({'session_id':session.id,'phase':session.phase,'revision':session.revision})
    if name == 'intake_extract':
        return CapabilityResult.ok(wb.intake.extract_document_fields(
            typed.session_id, typed.source_id, typed.fields, typed.expected_revision, wb.ctx,
        ))
    if name in {'intake_propose','intake_propose_sources'}:
        if name=='intake_propose_sources':
            preview=wb.intake.submit_source_proposals(typed.session_id,typed.proposals,typed.expected_revision,wb.ctx)
        else:
            preview=wb.intake.submit_proposal(typed.session_id,typed.proposal,typed.expected_revision,wb.ctx)
        return CapabilityResult.ok({'preview_ref':preview.id+'@'+preview.revision,
            'session_revision':wb.sessions.get(args['session_id'],wb.ctx).revision,
            'next_tool':'mapping_apply' if not preview.issues else 'intake_propose',
            'instance_count':len(preview.instances),'issues':[{k:i[k] for k in ['code','target'] if k in i} for i in preview.issues]})
    if name=='mapping_preview':
        view=wb.intake.view(args['session_id'],wb.ctx);preview=view['preview']
        return CapabilityResult.ok(None if preview is None else {'preview_ref':preview['id']+'@'+preview['revision'],
            'review_state':preview['review_state'],'instance_count':len(preview['instances']),
            'issues':[{k:i[k] for k in ['code','target'] if k in i} for i in preview['issues']]})
    if name=='mapping_apply':
        return CapabilityResult.ok(wb.intake.apply(args['session_id'],typed.decision,args['expected_revision'],wb.ctx).model_dump(mode='json'))
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
    raise ValueError('unknown aggregate tool')


def result_summary(wb, result):
    payload = result.model_dump(mode='json')
    path = wb.root/'results'/f'{uuid4().hex}.json'
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(payload,ensure_ascii=False,indent=2))
    summary = {'status':payload['status'],'result_path':str(path.relative_to(wb.workspace))}
    encoded = json.dumps(payload,ensure_ascii=False)
    if len(encoded.encode()) < 24000:
        summary['result'] = payload
    return summary
