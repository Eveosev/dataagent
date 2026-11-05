"""DataAgent governance and evaluation layer (08-governance-layer-build-plan)."""

from .evaluation import (
    check_result_grain_and_merge,
    confirm_acceptance_criteria,
    draft_acceptance_criteria,
    evaluate_business_acceptance,
    isolate_acceptance_samples,
)
from .governance import check_access_scope, check_model_context_egress
from .registry import validate_registry

__version__ = "0.1.0"

__all__ = [
    "check_access_scope",
    "check_model_context_egress",
    "draft_acceptance_criteria",
    "isolate_acceptance_samples",
    "evaluate_business_acceptance",
    "check_result_grain_and_merge",
    "confirm_acceptance_criteria",
    "validate_registry",
    "__version__",
]
