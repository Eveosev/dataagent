"""Provider-neutral OCR result types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable

ConfidenceSource = Literal["engine", "logprobs", "none"]


@dataclass(frozen=True)
class OcrBlock:
    """One recognized text line.

    ``bbox`` is ``[x0, y0, x1, y1]`` in pixels of the submitted image, or empty
    when the provider gave no usable box. ``confidence`` is ``None`` when the
    provider exposes no confidence signal; it is never invented.
    """

    text: str
    bbox: list[float] = field(default_factory=list)
    confidence: float | None = None


@dataclass
class RecognizeResult:
    blocks: list[OcrBlock]
    confidence_source: ConfidenceSource
    latency_ms: int = 0
    # Model identity reported by the provider (OpenAI-compatible ``model`` /
    # ``system_fingerprint``); compared with the pinned profile for drift.
    reported_model: str | None = None
    system_fingerprint: str | None = None
    output_format: Literal["blocks_json", "text", "engine"] = "engine"
    format_error: bool = False


@runtime_checkable
class OcrProvider(Protocol):
    engine_ref: str
    engine_version: str
    remote: bool

    def recognize_page(self, image_bytes: bytes, *, lang: str | None = None) -> RecognizeResult: ...

    def close(self) -> None: ...
