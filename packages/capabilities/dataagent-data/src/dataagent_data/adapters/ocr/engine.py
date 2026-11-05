"""Optional OCR engine. Absence is reported, never silently degraded."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass
class OcrBlock:
    text: str
    bbox: list[float]
    confidence: float


@runtime_checkable
class OcrEngine(Protocol):
    engine_ref: str
    engine_version: str

    def recognize(self, image_bytes: bytes, *, lang: str | None = None) -> list[OcrBlock]: ...


class RapidOcrEngine:
    engine_ref = "rapidocr_onnxruntime"

    def __init__(self, instance: Any, version: str):
        self._instance = instance
        self.engine_version = version

    @classmethod
    def create(cls) -> "RapidOcrEngine | None":
        try:
            import rapidocr_onnxruntime  # noqa: PLC0415

            engine = rapidocr_onnxruntime.RapidOCR()
        except Exception:  # noqa: BLE001 - missing model/backends are optional
            return None
        version = getattr(rapidocr_onnxruntime, "__version__", "unknown")
        return cls(engine, version)

    def recognize(self, image_bytes: bytes, *, lang: str | None = None) -> list[OcrBlock]:
        result, _ = self._instance(image_bytes)
        blocks: list[OcrBlock] = []
        for item in result or []:
            box, text, score = item[0], item[1], item[2]
            xs = [point[0] for point in box]
            ys = [point[1] for point in box]
            blocks.append(
                OcrBlock(
                    text=text,
                    bbox=[float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys))],
                    confidence=float(score),
                )
            )
        return blocks
