"""Error vocabulary: re-exported from the shared runtime.

The constructors live in ``dataagent_runtime.errors``; binding them as
module attributes (instead of restating the runtime's import block) keeps
this module a pure façade — one source of truth for the names, no drifting
copy of the list.
"""

from dataagent_runtime import errors

CapabilityError = errors.CapabilityError
dependency_unavailable = errors.dependency_unavailable
execution_unknown = errors.execution_unknown
invalid_input = errors.invalid_input
not_found = errors.not_found
unsupported = errors.unsupported
version_conflict = errors.version_conflict

__all__ = [
    "CapabilityError",
    "dependency_unavailable",
    "execution_unknown",
    "invalid_input",
    "not_found",
    "unsupported",
    "version_conflict",
]
