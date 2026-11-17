"""07 §2.3 T20: a missing OCR engine is needs_input, never silent success.

Pins the contract the data layer relies on: ``load_active_engine`` raises an
``OcrError`` with ``needs_input=True`` when nothing (or nothing verifiable)
is pinned, and blocks without a confidence signal cross the ``OcrEngine``
bridge as ``0.0`` — the data layer flags the page for review instead of
treating unscored digits as confident output. The data layer maps these
errors to the ``ocr_engine_missing`` page gap (partial coverage).
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from dataagent_ocr.adapter import PinnedOcrEngine, load_active_engine
from dataagent_ocr.cli import main
from dataagent_ocr.errors import EngineMissing, NotConfigured, NotVerified, PinMismatch
from dataagent_ocr.profiles import (
    ActivePin,
    EngineConfig,
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


def _pin_engine_profile(tmp_path: Path) -> None:
    """Pin an engine profile whose engine is not installed under data_root."""
    store = ProfileStore(tmp_path)
    cfg = EngineConfig(engine="rapidocr", lock_digest="a" * 64, worker_digest="b" * 64)
    profile, _ = store.save(OcrProfile(profile_id="rc", kind="engine", engine=cfg))
    store.save_verification(
        Verification(
            verification_id="ocrv-rc",
            profile_ref=profile.ref,
            config_digest=profile.config_digest(),
            passed=True,
            fixtures=[],
            latency_ms=1,
            confidence_source="none",
            engine_version="test",
        )
    )
    store.write_pin(
        ActivePin(
            profile_id=profile.profile_id,
            revision=profile.revision,
            config_digest=profile.config_digest(),
            verification_id="ocrv-rc",
            reason="initial_setup",
        )
    )


def test_engine_profile_without_installation_is_needs_input(tmp_path):
    """A profile pinned to an engine that is not installed is the second
    "missing engine" shape: loading must fail closed with needs_input (the
    data layer turns it into the ocr_engine_missing page gap), not return an
    engine that would fail per page."""
    _pin_engine_profile(tmp_path)
    with pytest.raises(EngineMissing) as info:
        load_active_engine(tmp_path)
    assert info.value.needs_input
    assert info.value.code == "ocr.engine_missing"
    assert "engine plan" in (info.value.action or "")


def test_cli_status_without_engine_is_needs_input(tmp_path, capsys, monkeypatch):
    """The user-facing surface agrees: `dataagent-ocr status` with nothing
    configured reports needs_input (exit 3), never success."""
    monkeypatch.setattr("sys.stdin", io.StringIO())
    code = main(["--data-root", str(tmp_path), "status"])
    out = json.loads(capsys.readouterr().out)
    assert code == 3
    assert out["status"] == "needs_input"
    assert out["error"]["code"] == "ocr.not_configured"
    assert out["error"]["needs_input"] is True
