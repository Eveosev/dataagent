"""Versioned-repository port for the data layer (06 §6).

The base contract (``get``/``current``/``save``/``save_content_addressed``/
``find_by_digest``) is the shared runtime's port; the data layer extends it
with ``ref_exists`` — the check used to refuse fabricated evidence refs
(06 §5 step 3).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from dataagent_runtime.ports.versioned import VersionedRepository as _SharedVersionedRepository


@runtime_checkable
class VersionedRepository(_SharedVersionedRepository, Protocol):
    """Explicit revisions with optimistic concurrency (06 §6)."""

    def ref_exists(self, ref: str) -> bool: ...
