"""Operations MCP tools using the shared DataAgent result and stdio protocol."""

import os
from pathlib import Path
from typing import Literal

from pydantic import Field, JsonValue, RootModel, ValidationError

from dataagent_contracts.core import CapabilityResult, CapabilityStatus, Continuation, Issue
from dataagent_contracts.environment import EnvironmentSnapshot, UIObservation
from dataagent_contracts.workflow import ActionRecord, WaitRecord, WorkflowDraft, WorkflowRun, WorkflowValidationReport
from dataagent_runtime.adapters.workbench_sqlite import SqliteWorkbenchStore
from dataagent_runtime.interfaces.mcp_server import serve
from dataagent_runtime.policy.context import ContextResolutionError, resolved_context
from dataagent_runtime.registry import OperationSpec

from .bindings import ConfigModel, HostConfig
from .service import OperationsService
from .store import AuthorityRevoked


class EnvironmentInput(ConfigModel):
    environment_id: str


class ObserveWebInput(EnvironmentInput):
    page_ref: str


class WebObservationInput(ConfigModel):
    observation_id: str


class DraftInput(ConfigModel):
    work_spec_id: str
    snapshot_id: str
    run_id: str | None = None


class ProposalInput(ConfigModel):
    draft_id: str
    spec: dict[str, JsonValue]


class StartInput(ConfigModel):
    proposal_id: str
    business_key: str
    inputs: dict[str, JsonValue]


class RunInput(ConfigModel):
    run_id: str


class AdvanceInput(RunInput):
    max_steps: int = Field(default=100, ge=1, le=100)


class ControlInput(RunInput):
    command: Literal["pause", "resume", "cancel", "provide_input"]
    values: dict[str, JsonValue] | None = None


def _operation(name, capability, method, input_model, output_model, description, *, writes):
    return OperationSpec(
        operation=name, capability_id=capability, source_file=__file__,
        input_model=input_model, output_model=output_model,
        handler=getattr(OperationsService, method), writes=writes,
        description=description, idempotent=False if writes else True,
    )


OPERATIONS = {
    spec.operation: spec for spec in (
        _operation("environment_discover", "DA01.8", "discover", EnvironmentInput, EnvironmentSnapshot,
                   "Observe the trusted API catalog and perform scoped read probes.", writes=True),
        _operation("environment_observe_web", "DA01.8", "observe_web", ObserveWebInput, UIObservation,
                   "Observe controls and page version at a host-configured local browser page.", writes=True),
        _operation("environment_web_observation", "DA01.8", "web_observation", WebObservationInput, UIObservation,
                   "Read a saved Web environment observation.", writes=False),
        _operation("workflow_draft", "DA06.6", "draft", DraftInput, WorkflowDraft,
                   "Create a workflow inference request pinned to a trusted WorkSpec and environment.", writes=True),
        _operation("workflow_submit_proposal", "DA06.7", "submit_proposal", ProposalInput, WorkflowValidationReport,
                   "Validate and persist a versioned workflow candidate for the draft.", writes=True),
        _operation("workflow_start", "DA14.6", "start", StartInput, WorkflowRun,
                   "Start or revise a durable run with the exact validated proposal.", writes=True),
        _operation("workflow_advance", "DA14.6", "advance", AdvanceInput, WorkflowRun,
                   "Advance a durable run, reconciling uncertain actions before any new dispatch.", writes=True),
        _operation("workflow_status", "DA14.8", "status", RunInput, WorkflowRun,
                   "Read the current run, completed steps, receipt references, and pending control point.", writes=False),
        _operation("workflow_control", "DA14.8", "control", ControlInput, WorkflowRun,
                   "Pause, resume, cancel, or provide input at an active human step.", writes=True),
        _operation("workflow_actions", "DA07.8", "actions", RunInput, RootModel[list[ActionRecord]],
                   "Read the real action ledger and its verified business receipts.", writes=False),
        _operation("workflow_waits", "DA14.8", "waits", RunInput, RootModel[list[WaitRecord]],
                   "Read durable business wait observations and consumption state.", writes=False),
    )
}


def _environment_path(variable, *, required=True):
    value = os.environ.get(variable)
    if not value and not required:
        return None
    if not value or not Path(value).is_absolute():
        raise OSError(f"{variable} must name an absolute host-owned path")
    return Path(value)


def load_service():
    config_path = _environment_path("DATAAGENT_OPERATIONS_CONFIG")
    database_path = _environment_path("DATAAGENT_OPERATIONS_DB")
    workbench_path = _environment_path("DATAAGENT_OPERATIONS_WORKBENCH_DB", required=False)
    config = HostConfig.model_validate_json(config_path.read_text(encoding="utf-8"))
    if workbench_path is not None and not workbench_path.is_file():
        raise OSError("trusted Workbench database is missing")
    workbench = SqliteWorkbenchStore(workbench_path) if workbench_path else None
    return OperationsService(database_path, config, workbench_store=workbench)


def _run_result(run, operation):
    if operation == "workflow_status":
        return CapabilityResult.ok(run)
    continuation = Continuation(job_ref=run.job_ref, resume_condition=run.state)
    if run.state in {"active", "waiting", "unknown", "paused"}:
        issues = []
        if run.state == "unknown":
            issues.append(Issue.standard("execution_unknown", run.message or "Business outcome remains unknown", retryable=True))
        return CapabilityResult(status=CapabilityStatus.pending, data=run, issues=issues, continuation=continuation)
    if run.state == "needs_input":
        issue = Issue.standard("invalid_input", run.message or "Human input is required", suggested_action="workflow_control")
        return CapabilityResult(status=CapabilityStatus.needs_input, data=run, issues=[issue], continuation=continuation)
    if run.state in {"failed", "revoked", "replan_required"}:
        codes = {"failed": "invalid_input", "revoked": "unauthorized", "replan_required": "source_changed"}
        issue = Issue.standard(codes[run.state], run.message or run.state)
        return CapabilityResult(status=CapabilityStatus.partial, data=run, issues=[issue])
    return CapabilityResult.ok(run)


def invoke(operation, payload, context):
    spec = OPERATIONS.get(operation)
    if spec is None:
        return CapabilityResult.failure(Issue.standard("not_found", "Unknown operations capability"))
    try:
        # R1: resolve through the one context resolver. A ResolvedContext from
        # the shared MCP entry passes through sealed; an older bare
        # CallContext/mapping is a hint (host _meta/environment -> local-owner).
        ctx = resolved_context(context).context
        args = spec.input_model.model_validate(payload)
    except (ContextResolutionError, ValidationError):
        return CapabilityResult.failure(Issue.standard("invalid_input", "Invalid operations input or CallContext"))
    try:
        service = load_service()
    except (OSError, ValidationError, ValueError):
        return CapabilityResult.failure(Issue.standard("dependency_unavailable", "Trusted operations host configuration is unavailable"))
    # R1: ``scope_ref`` is now the one workspace spelling, not the
    # operations host's business scope; the trusted capability handle in the
    # host config remains the authorization gate.
    if ctx.authorization_ref != service.config.authorization_ref:
        return CapabilityResult.failure(Issue.standard("unauthorized", "CallContext does not match trusted operations authorization"))
    try:
        value = spec.handler(service, **args.model_dump(mode="json"))
    except AuthorityRevoked as exc:
        return CapabilityResult.failure(Issue.standard("unauthorized", str(exc)))
    except ValueError as exc:
        return CapabilityResult.failure(Issue.standard("invalid_input", str(exc)))
    if isinstance(value, WorkflowRun):
        return _run_result(value, operation)
    return CapabilityResult.ok(value)


def main():
    return serve(
        server_name="dataagent-operations", server_version="0.1.0",
        list_operations=lambda: list(OPERATIONS.values()), invoke=invoke,
    )
