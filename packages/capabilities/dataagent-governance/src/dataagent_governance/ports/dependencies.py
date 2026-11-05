"""Dependency version port (08 §5.3 dependency versions)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from dataagent_contracts.core import VersionedRef


@runtime_checkable
class DependencyPort(Protocol):
    """Report the dependency versions an acceptance run was made against."""

    def current_versions(self) -> list[VersionedRef]: ...
