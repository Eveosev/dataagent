"""Host-bound aggregate tools shared by CLI and MCP."""
import json
from uuid import uuid4
from dataagent_contracts.core import CapabilityResult, CapabilityStatus, Continuation, VersionedRef
from dataagent_contracts.intake import WorkSpec, SourceSelection


def invoke(wb, name, args):
    if name == 'intake_start':
        goal = WorkSpec(id=uuid4().hex,goal=args['goal'],
            acceptance_criteria=args.get('acceptance_criteria',['来源可核对']),authorization_ref=wb.authorization)
        handle = wb.sessions.start([SourceSelection.model_validate(s) for s in args['sources']],goal,wb.ctx)
        return CapabilityResult(status=CapabilityStatus.pending,data=handle.model_dump(mode='json'),
            continuation=Continuation(job_ref=handle.job_ref))
    if name == 'intake_status':
        return CapabilityResult.ok(wb.sessions.get(args['session_id'],wb.ctx).model_dump(mode='json'))
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
