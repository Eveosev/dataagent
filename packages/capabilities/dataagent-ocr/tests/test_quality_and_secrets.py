from __future__ import annotations

import os
import stat

import pytest

from dataagent_ocr import quality, secrets
from dataagent_ocr.errors import ConfigError, CredentialsError
from dataagent_ocr.probe import score
from dataagent_ocr.profiles import OcrProfile, OpenAICompatConfig, ProfileStore, QualityPolicy


def _profile(**policy) -> OcrProfile:
    cfg = OpenAICompatConfig(base_url="https://h/v1", model="m", deployment="vendor_api")
    return OcrProfile(profile_id="p", revision=1, kind="openai_compat", openai_compat=cfg, quality=QualityPolicy(**policy))


def _usage(profile, **kw):
    base = dict(profile=profile.ref, blocks=3, empty=False, mean_confidence=0.9, low_confidence=False,
                confidence_source="logprobs", format_error=False, latency_ms=5)
    base.update(kw)
    return quality.UsageRecord(**base)


def test_verdict_insufficient_ok_degraded(data_root):
    store = ProfileStore(data_root)
    profile = _profile(min_pages=5, window_pages=10)
    assert quality.evaluate(store, profile).status == "insufficient"
    for _ in range(5):
        quality.record_usage(store, _usage(profile))
    assert quality.evaluate(store, profile).status == "ok"
    for _ in range(3):
        quality.record_usage(store, _usage(profile, empty=True, blocks=0))
    verdict = quality.evaluate(store, profile)
    assert verdict.status == "degraded" and "empty page rate" in verdict.reasons[0]


def test_unscored_pages_do_not_count_as_low_confidence(data_root):
    store = ProfileStore(data_root)
    profile = _profile(min_pages=3)
    for _ in range(5):
        quality.record_usage(store, _usage(profile, mean_confidence=None, confidence_source="none"))
    verdict = quality.evaluate(store, profile)
    assert verdict.status == "ok" and "low_confidence" not in verdict.rates


def test_window_only_counts_recent_pages(data_root):
    store = ProfileStore(data_root)
    profile = _profile(min_pages=5, window_pages=5)
    for _ in range(5):
        quality.record_usage(store, _usage(profile, empty=True))
    for _ in range(5):
        quality.record_usage(store, _usage(profile))
    assert quality.evaluate(store, profile).status == "ok"


def test_score_digits_must_match():
    ratio, digits_ok = score("TOTAL 12,345.67", "TOTAL 12,845.67")
    assert ratio > 0.9 and not digits_ok
    assert score("合计 12.50 元", "合计 12.50 元") == (1.0, True)


def test_secret_refs(data_root, monkeypatch):
    ref = secrets.store_file_secret(data_root, "ocr-x", "  sk-1  \n")
    assert ref == "file:ocr-x" and secrets.resolve(ref, data_root) == "sk-1"
    path = data_root / "secrets" / "ocr" / "ocr-x.key"
    os.chmod(path, 0o644)
    with pytest.raises(CredentialsError, match="readable by other users"):
        secrets.resolve(ref, data_root)
    monkeypatch.setenv("OCR_KEY", "sk-env")
    assert secrets.resolve("env:OCR_KEY", data_root) == "sk-env"
    with pytest.raises(ConfigError):
        secrets.validate_ref("plain:sk-123")
    with pytest.raises(CredentialsError):
        secrets.store_file_secret(data_root, "ocr-y", "   ")
    assert stat.S_IMODE((data_root / "secrets" / "ocr").stat().st_mode) == 0o700
