"""DataAgent application layer (07 application-layer build plan, S0)."""

from dataagent_application.registry import (
    get_spec,
    list_operations,
    load_operations,
    validate_registry,
)

__version__ = "0.1.0"

__all__ = [
    "get_spec",
    "list_operations",
    "load_operations",
    "validate_registry",
    "__version__",
]
