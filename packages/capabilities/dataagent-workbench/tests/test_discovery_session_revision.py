"""FDE3-05: a discovery proposal tells the caller its advanced revision."""

import pytest

from dataagent_runtime.ports.workbench_store import VersionConflict
from dataagent_workbench.service_tools import invoke


def test_discovery_propose_returns_the_advanced_session_revision(tmp_path):
    from test_publish_gate import full_completion, full_draft, workbench

    wb, sid, request = workbench(tmp_path)
    before = wb.sessions.get(sid, wb.ctx).revision
    draft = full_draft(wb, sid, request)
    assert draft['session_revision'] == wb.sessions.get(sid, wb.ctx).revision
    assert int(draft['session_revision']) == int(before) + 1

    completion = full_completion(wb, sid, draft)
    completion['expected_revision'] = before
    with pytest.raises(VersionConflict):
        invoke(wb, 'ontology_publish_prepare', completion)

    # The returned revision is the one unchanged inputs can be completed with.
    completion['expected_revision'] = draft['session_revision']
    prepared = invoke(wb, 'ontology_publish_prepare', completion)
    assert prepared.status == 'needs_input'
    assert prepared.data['candidate_ref']
