"""DataAgent OCR providers, verification and pinning (13-ocr-component-plan)."""

from dataagent_ocr.adapter import PinnedOcrEngine, load_active_engine
from dataagent_ocr.errors import OcrError
from dataagent_ocr.profiles import OcrProfile, ProfileStore
from dataagent_ocr.types import OcrBlock, RecognizeResult

__all__ = [
    "OcrBlock",
    "OcrError",
    "OcrProfile",
    "PinnedOcrEngine",
    "ProfileStore",
    "RecognizeResult",
    "load_active_engine",
]
__version__ = "0.1.0"
