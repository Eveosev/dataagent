"""Bridge from the pinned provider to the data layer's ``OcrEngine`` protocol.

``dataagent_data.adapters.ocr.engine.OcrEngine`` expects ``engine_ref``,
``engine_version`` and ``recognize(image_bytes, lang) -> blocks`` with float
confidences. Blocks without a confidence signal are passed as ``0.0`` so the
data layer flags the page for review instead of trusting unscored digits;
``confidence_source`` tells the two apart for the W2 contract field.
Every page is recorded as a quality usage record.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dataagent_ocr import quality
from dataagent_ocr.profiles import ActivePin, OcrProfile, ProfileStore
from dataagent_ocr.providers import build_provider
from dataagent_ocr.types import OcrProvider


@dataclass
class DataLayerBlock:
    text: str
    bbox: list[float]
    confidence: float


class PinnedOcrEngine:
    def __init__(self, store: ProfileStore, pin: ActivePin, profile: OcrProfile, provider: OcrProvider):
        self.store = store
        self.pin = pin
        self.profile = profile
        self.provider = provider
        self.engine_ref = provider.engine_ref
        self.remote = provider.remote
        self.last_confidence_source = "none"
        self.drift: str | None = None

    @property
    def engine_version(self) -> str:
        return self.provider.engine_version

    def destination(self) -> dict[str, str] | None:
        return self.provider.destination() if hasattr(self.provider, "destination") else None

    def recognize(self, image_bytes: bytes, *, lang: str | None = None) -> list[DataLayerBlock]:
        result = self.provider.recognize_page(image_bytes, lang=lang)
        self.last_confidence_source = result.confidence_source
        if self.pin.reported_model and result.reported_model and result.reported_model != self.pin.reported_model:
            self.drift = f"provider reported model {result.reported_model!r}, pinned {self.pin.reported_model!r}"
            self.store.event("model_drift", profile=self.profile.ref, reported=result.reported_model, pinned=self.pin.reported_model)
        known = [b.confidence for b in result.blocks if b.confidence is not None]
        mean = sum(known) / len(known) if known else None
        quality.record_usage(
            self.store,
            quality.UsageRecord(
                profile=self.profile.ref,
                blocks=len(result.blocks),
                empty=not any(b.text.strip() for b in result.blocks),
                mean_confidence=round(mean, 4) if mean is not None else None,
                low_confidence=mean is not None and mean < self.profile.quality.low_confidence,
                confidence_source=result.confidence_source,
                format_error=result.format_error,
                latency_ms=result.latency_ms,
                reported_model=result.reported_model,
            ),
        )
        return [
            DataLayerBlock(text=b.text, bbox=list(b.bbox), confidence=b.confidence if b.confidence is not None else 0.0)
            for b in result.blocks
        ]

    def close(self) -> None:
        self.provider.close()


def load_active_engine(data_root: str | Path) -> PinnedOcrEngine:
    """The pinned engine, or an :class:`OcrError` (``needs_input``) explaining why not."""

    store = ProfileStore(Path(data_root))
    pin, profile, _verification = store.load_pinned()
    return PinnedOcrEngine(store, pin, profile, build_provider(Path(data_root), profile))
