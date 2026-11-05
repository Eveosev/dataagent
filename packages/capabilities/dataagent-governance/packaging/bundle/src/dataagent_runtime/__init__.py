"""DataAgent shared runtime (08 §2 / §4.3)."""

from .enforcement import (
    EnforcementConfig,
    EnforcementMode,
    access_recheck,
    egress_check,
    enforcement_from_env,
    guarded_inference,
)
from .errors import (
    CapabilityError,
    NeedsInputError,
    dependency_unavailable,
    execution_unknown,
    invalid_input,
    not_found,
    unsupported,
    version_conflict,
)
from .invoke import invoke
from .runtime import Runtime, default_runtime, reset_default_runtime, resolve_roots
from .registry import (
    OperationSpec,
    operation,
    get_spec,
    list_operations,
    load_operations,
    registry_errors,
    reset_registry,
    validate_registry,
)

__version__ = "0.1.0"

__all__ = [
    "EnforcementConfig",
    "EnforcementMode",
    "access_recheck",
    "egress_check",
    "enforcement_from_env",
    "guarded_inference",
    "CapabilityError",
    "NeedsInputError",
    "invalid_input",
    "unsupported",
    "not_found",
    "version_conflict",
    "dependency_unavailable",
    "execution_unknown",
    "invoke",
    "Runtime",
    "default_runtime",
    "reset_default_runtime",
    "resolve_roots",
    "OperationSpec",
    "operation",
    "get_spec",
    "list_operations",
    "load_operations",
    "registry_errors",
    "reset_registry",
    "validate_registry",
    "__version__",
]
