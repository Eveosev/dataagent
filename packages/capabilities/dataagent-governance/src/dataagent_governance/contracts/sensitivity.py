"""Sensitivity reports and masked artifacts (08 §5.1).

Reports never carry the sensitive values themselves: each finding carries a
count and the digest of one verifiable occurrence. Masked artifacts keep a
per-entry mapping from masked location back to the digest of the original
value, so a later proposal check can still verify against the original
evidence without re-exposing it (feasibility review §8).
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from dataagent_contracts.core._base import ExtModel

__all__ = ["SensitivityFinding", "SensitivityReport", "MaskedEntry", "MaskedArtifactRef"]

SensitiveKind = Literal["id_card", "phone", "email", "bank_card", "declared_field"]


class SensitivityFinding(ExtModel):
    kind: SensitiveKind
    # Field name for structured content; None for free text.
    field: str | None = None
    count: int = Field(ge=1)
    # Digest of one occurrence: verifiable without leaking the value.
    sample_digest: str = Field(min_length=1)
    locator: str | None = None


class SensitivityReport(ExtModel):
    content_ref: str = Field(min_length=1)
    findings: list[SensitivityFinding] = Field(default_factory=list)

    @property
    def sensitive(self) -> bool:
        return bool(self.findings)

    @property
    def kinds(self) -> list[str]:
        return sorted({f.kind for f in self.findings})


class MaskedEntry(ExtModel):
    field: str | None = None
    # Location of the masked value: row index, JSON pointer or char span.
    locator: str = Field(min_length=1)
    replacement: str = Field(min_length=1)
    # Digest of the original value; anchors masked content to the evidence.
    original_digest: str = Field(min_length=1)


class MaskedArtifactRef(ExtModel):
    mask_id: str = Field(min_length=1)
    source_content_ref: str = Field(min_length=1)
    # Content-addressed digest of the masked payload.
    masked_content_ref: str = Field(min_length=1)
    entries: list[MaskedEntry] = Field(default_factory=list)
