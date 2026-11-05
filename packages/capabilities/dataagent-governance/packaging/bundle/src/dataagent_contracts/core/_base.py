"""Shared model base for the S0 core contract.

``extra="forbid"`` keeps the contract closed: unknown top-level fields are
rejected. Vendor-specific data travels in the explicit, optional
``extensions`` map (05-contracts.md §2.1) rather than as implicit extra keys.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

__all__ = ["ExtModel", "NAMESPACE_PATTERN"]

# ``<ns>.<name>`` with at least one dot; no colon (05 §2.4 / 06 §14 item 3).
NAMESPACE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")


class ExtModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    extensions: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Namespaced vendor extensions. Core logic never interprets this map; "
            "unknown top-level fields are still rejected."
        ),
    )

    @field_validator("extensions")
    @classmethod
    def _extensions_are_namespaced(
        cls, value: dict[str, Any] | None
    ) -> dict[str, Any] | None:
        if value is None:
            return value
        for key in value:
            if not isinstance(key, str) or not NAMESPACE_PATTERN.match(key):
                raise ValueError(
                    f"extension key {key!r} must be a dotted namespace like "
                    "'app.vendor_field'"
                )
        return value
