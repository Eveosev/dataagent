"""Capability errors mapped onto the closed StandardErrorCode vocabulary.

Mirrors the data-layer mapping (06 §14 item 5) so every layer converts the
errors it owns to ``CapabilityError`` and ``invoke`` never leaks a traceback.
"""

from __future__ import annotations

from dataclasses import dataclass

from dataagent_contracts.core import Issue, Severity, StandardErrorCode


@dataclass
class CapabilityError(Exception):
    code: StandardErrorCode | str
    message: str
    suggested_action: str | None = None
    retryable: bool = False
    target: str | None = None

    def __post_init__(self) -> None:
        super().__init__(self.message)

    def to_issue(self) -> Issue:
        severity = (
            Severity.warning
            if self.code
            in {StandardErrorCode.unsupported, StandardErrorCode.dependency_unavailable}
            else Severity.error
        )
        return Issue(
            code=self.code.value if isinstance(self.code, StandardErrorCode) else self.code,
            severity=severity,
            message=self.message,
            retryable=self.retryable,
            suggested_action=self.suggested_action,
            target=self.target,
        )


def invalid_input(message: str, *, target: str | None = None) -> CapabilityError:
    return CapabilityError(StandardErrorCode.invalid_input, message, target=target)


def unsupported(message: str, *, target: str | None = None) -> CapabilityError:
    return CapabilityError(StandardErrorCode.unsupported, message, target=target)


def dependency_unavailable(message: str, *, action: str | None = None) -> CapabilityError:
    return CapabilityError(
        StandardErrorCode.dependency_unavailable, message, suggested_action=action
    )


def not_found(message: str) -> CapabilityError:
    return CapabilityError(StandardErrorCode.not_found, message)


def version_conflict(message: str) -> CapabilityError:
    return CapabilityError(StandardErrorCode.version_conflict, message, retryable=True)


def source_changed(message: str) -> CapabilityError:
    return CapabilityError(StandardErrorCode.source_changed, message, retryable=True)


def execution_unknown(message: str, *, retryable: bool = False) -> CapabilityError:
    return CapabilityError(StandardErrorCode.execution_unknown, message, retryable=retryable)


class NeedsInputError(Exception):
    """Two-phase signal: the handler needs the agent's proposal.

    ``invoke`` maps this to ``status=needs_input`` with the attached Issue
    (suggested_action / inference_request ride on the issue).
    """

    def __init__(self, issue: Issue):
        super().__init__(issue.message)
        self.issue = issue
