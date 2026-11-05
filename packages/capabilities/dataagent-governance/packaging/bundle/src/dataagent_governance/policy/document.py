"""Pattern matching for policy rules (08 §5.1)."""

from __future__ import annotations

from dataagent_contracts.core import VersionedRef

__all__ = ["subject_matches", "purpose_matches", "resource_matches"]


def subject_matches(pattern: str, subject_ref: str) -> bool:
    return pattern == "*" or pattern == subject_ref


def purpose_matches(pattern: str, purpose: str) -> bool:
    return pattern == "*" or pattern == purpose


def resource_matches(pattern: str, ref: VersionedRef) -> bool:
    """Resource patterns: exact, asset subtree, or asset type.

    - ``table:orders@r1`` — exact id and revision;
    - ``table:orders``    — the asset subtree at any revision;
    - ``table:*``        — the whole asset type.
    """

    if pattern.endswith("*"):
        prefix = pattern[:-1]
        return ref.id.startswith(prefix) or ref.id == prefix.rstrip(":")
    if "@" in pattern:
        return pattern == f"{ref.id}@{ref.revision}"
    if ref.id == pattern:
        return True
    return ref.id.startswith(pattern) and ref.id[len(pattern)] in {"/", ":"}
