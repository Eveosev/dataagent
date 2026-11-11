"""Versioned observations of an authorized business environment."""

from datetime import datetime
from typing import Literal

from pydantic import Field, JsonValue

from .core._base import ExtModel


class ActionBinding(ExtModel):
    action: str
    operation_id: str
    channel: Literal["api"] = "api"
    lookup_operation: str
    method: str
    path: str
    remote_idempotency: bool
    remote_fencing: bool
    precondition: dict[str, JsonValue] | None = None
    expected_effect: dict[str, JsonValue]


class CapabilityObservation(ExtModel):
    operation_id: str
    method: str
    path: str
    title: str = ""
    description: str = ""
    parameters: dict[str, dict[str, JsonValue]] = Field(default_factory=dict)
    required_parameters: dict[str, list[str]] = Field(default_factory=dict)
    request_schema: dict[str, JsonValue] | None = None
    request_required: bool = False
    response_schema: dict[str, JsonValue] | None = None
    authorized: bool = False
    verification: Literal["described", "observed"] = "described"
    action: str | None = None
    binding: ActionBinding | None = None
    evidence: dict[str, JsonValue] | None = None


class EnvironmentSnapshot(ExtModel):
    id: str
    revision: str
    environment_id: str
    environment_identity: str
    tenant: str
    scope_ref: str
    authorization_ref: str
    observed_at: datetime
    title: str
    capabilities: dict[str, CapabilityObservation]
    gaps: list[str] = Field(default_factory=list)


class UIControl(ExtModel):
    id: str
    name: str
    role: str
    required: bool = False
    enabled: bool = True


class UIObservation(ExtModel):
    id: str
    environment_id: str
    page_ref: str
    page_version: str
    scope_ref: str
    observed_at: datetime
    state: Literal['observed', 'login_required', 'unavailable']
    controls: list[UIControl] = Field(default_factory=list)
    status_text: str | None = None
    record_evidence: dict[str, str] | None = None
    screenshot_ref: str | None = None
    screenshot_digest: str | None = None
