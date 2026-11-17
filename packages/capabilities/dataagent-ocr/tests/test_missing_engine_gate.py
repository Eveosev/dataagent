"""07 §2.3 T20: a missing OCR engine is needs_input, never silent success.

Pins the contract the data layer relies on: ``load_active_engine`` raises an
``OcrError`` with ``needs_input=True`` when nothing (or nothing verifiable)
is pinned, and blocks without a confidence signal cross the ``OcrEngine``
bridge as ``0.0`` — the data layer flags the page for review instead of
treating unscored digits as confident output.
"""

from __future__ import annotations

import json

import pytest

from dataagent_ocr.adapter import PinnedOcrEngine, load_active_engine
from dataagent_ocr.errors import NotConfigured, NotVerified, PinMismatch
from dataagent_ocr.profiles import (
    ActivePin,
    OcrProfile,
    OpenAICompatConfig,
    ProfileStore,
    Verification,
)
from dataagent_ocr.types import OcrBlock, RecognizeResult


class _Provider:
    engine_ref = "stub:provider"
    engine_version = "stub@r1:000000000000"
    remote = False

    def __init__(self, result: RecognizeResult):
        self._result = result

    def recognize_page(self, image_bytes: bytes, *, lang: str | None = None) -> RecognizeResult:
        return self._result

    def close(self) -> None:
        return None


def _profile() -> OcrProfile:
    cfg = OpenAICompatConfig(base_url="http://127.0.0.1:9/v1", model="m", deployment="local")
    return OcrProfile(profile_id="vl", revision=1, kind="openai_compat", openai_compat=cfg)


def test_no_configured_engine_is_needs_input(tmp_path):
    with pytest.raises(NotConfigured) as info:
        load_active_engine(tmp_path)
    assert info.value.needs_input
    assert info.value.code == "ocr.not_configured"
    assert info.value.action  # the caller is told what to ask the user for


def test_pinned_profile_without_verification_is_needs_input(tmp_path):
    store = ProfileStore(tmp_path)
    profile, _ = store.save(_profile())
    store.save_verification(
        Verification(
            verification_id="ocrv-x",
            profile_ref=profile.ref,
            config_digest=profile.config_digest(),
            passed=True,
            fixtures=[],
            latency_ms=1,
            confidence_source="none",
        )
    )
    store.write_pin(
        ActivePin(
            profile_id=profile.profile_id,
            revision=profile.revision,
            config_digest=profile.config_digest(),
            verification_id="ocrv-x",
            reason="initial_setup",
        )
    )
    (tmp_path / "ocr" / "verifications" / "ocrv-x.json").unlink()
    # the missing verification is a pin problem, not a success
    with pytest.raises((NotVerified, PinMismatch)) as info:
        load_active_engine(tmp_path)
    assert info.value.needs_input
    assert info.value.code in ("ocr.not_verified", "ocr.pin_mismatch")


def test_unscored_blocks_cross_the_bridge_as_review_not_success(tmp_path):
    profile = _profile()
    pin = ActivePin(
        profile_id=profile.profile_id,
        revision=profile.revision,
        config_digest=profile.config_digest(),
        verification_id="ocrv-x",
        reason="initial_setup",
    )
    engine = PinnedOcrEngine(
        ProfileStore(tmp_path),
        pin,
        profile,
        _Provider(
            RecognizeResult(
                blocks=[OcrBlock(text="INVOICE NO. 2026-1106-0042", bbox=[0, 0, 10, 10], confidence=None)],
                confidence_source="none",
            )
        ),
    )
    blocks = engine.recognize(b"image")
    assert [block.confidence for block in blocks] == [0.0]  # below the data layer's review threshold
    assert engine.last_confidence_source == "none"
    # the usage record keeps "no signal" distinct from "really low"
    usage = json.loads((tmp_path / "ocr" / "quality" / "usage.jsonl").read_text().splitlines()[0])
    assert usage["confidence_source"] == "none" and usage["mean_confidence"] is None
