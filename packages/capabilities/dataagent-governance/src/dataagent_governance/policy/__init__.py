"""Local policy document model and evaluator (08 §5.1)."""

from .document import resource_matches, subject_matches
from .evaluator import evaluate_access, evaluate_egress

__all__ = ["evaluate_access", "evaluate_egress", "resource_matches", "subject_matches"]
