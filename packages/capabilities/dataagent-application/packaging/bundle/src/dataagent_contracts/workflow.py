"""Workflow proposals, persisted control state, waits, and action receipts."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, JsonValue

from .core._base import ExtModel
from .intake import WorkSpec

Pointer = Annotated[str, Field(pattern=r"^(/([^~]|~[01])*)?$")]
StepId = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")]


class Predicate(ExtModel):
    pointer: Pointer
    one_of: list[JsonValue] = Field(min_length=1)


class ApiArguments(ExtModel):
    path: dict[str, JsonValue] = Field(default_factory=dict)
    query: dict[str, JsonValue] = Field(default_factory=dict)
    body: dict[str, JsonValue] = Field(default_factory=dict)


class Step(ExtModel):
    id: StepId
    next: StepId | None = None


class ReadStep(Step):
    operation_id: str = Field(min_length=1)
    parameters: ApiArguments = Field(default_factory=ApiArguments)


class ObserveStep(ReadStep):
    kind: Literal["observe"]


class TransformStep(Step):
    kind: Literal["transform"]
    assign: dict[str, JsonValue]


class DecideStep(Step):
    kind: Literal["decide"]
    condition: Predicate
    otherwise: StepId


class ActStep(ReadStep):
    kind: Literal["act"]


class WaitStep(ReadStep):
    kind: Literal["wait"]
    condition: Predicate


class HumanStep(Step):
    kind: Literal["human"]
    prompt: str = Field(min_length=1)
    input_schema: dict[str, JsonValue]


class VerifyStep(ReadStep):
    kind: Literal["verify"]
    condition: Predicate
    criteria: list[int] = Field(min_length=1)


WorkflowNode = Annotated[
    ObserveStep | TransformStep | DecideStep | ActStep | WaitStep | HumanStep | VerifyStep,
    Field(discriminator="kind"),
]


class VerificationRequirement(ExtModel):
    operation_id: str
    condition: Predicate
    criteria: list[int] = Field(min_length=1)


class WorkflowSpec(ExtModel):
    entry: StepId
    input_schema: dict[str, JsonValue]
    nodes: list[WorkflowNode] = Field(min_length=1, max_length=100)


class WorkflowDraft(ExtModel):
    id: str
    work_spec: WorkSpec
    snapshot_id: str
    scope_ref: str
    run_id: str | None = None
    run_revision: int | None = None
    inference_request: dict[str, JsonValue]


class WorkflowValidationReport(ExtModel):
    id: str
    draft_id: str
    spec_digest: str
    spec: WorkflowSpec | None = None
    valid: bool
    issues: list[str] = Field(default_factory=list)
    validated_steps: list[str] = Field(default_factory=list)
    unobserved_steps: list[str] = Field(default_factory=list)


class WorkflowRun(ExtModel):
    id: str
    workflow_revision: str
    work_spec: WorkSpec
    snapshot_id: str
    scope_ref: str
    business_key: str
    inputs: dict[str, JsonValue]
    current_step: StepId | None
    revision: int = 1
    job_ref: str
    state: Literal[
        "active", "waiting", "needs_input", "paused", "cancelled", "revoked",
        "unknown", "failed", "completed", "replan_required",
    ] = "active"
    receipt_refs: list[str] = Field(default_factory=list)
    wait_ref: str | None = None
    unknown_action_ref: str | None = None
    outputs: dict[str, JsonValue] = Field(default_factory=dict)
    completed: list[StepId] = Field(default_factory=list)
    message: str | None = None


class WaitRecord(ExtModel):
    id: str
    run_id: str
    step_id: StepId
    state: Literal["waiting", "consumed", "cancelled"]
    observation: JsonValue = None
    observed_at: datetime


class ActionReceipt(ExtModel):
    id: str
    source: Literal["response", "reconciliation", "preexisting", "browser_reconciliation"]
    observed_at: datetime
    record: JsonValue
    response: JsonValue = None
    observation_ref: str | None = None


class ActionRecord(ExtModel):
    id: str
    operation_id: str
    action: str
    business_key: str
    parameters_digest: str
    state: Literal["reserved", "in_flight", "applied", "not_applied", "partial", "unknown"]
    dispatch_count: int = 0
    receipt: ActionReceipt | None = None
    message: str | None = None
