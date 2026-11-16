"""Verification (the test call) and the pin policy.

A profile becomes active only through a passed verification of its exact
``config_digest``. Replacing an active provider with a different one needs
one of two reasons:

- ``user_request`` — the user explicitly asked to change the OCR model; the
  user's instruction is recorded verbatim as evidence;
- ``quality_degraded`` — the current quality verdict of the pinned profile is
  ``degraded``; the verdict id is recorded as evidence.

Re-verifying the pinned profile itself (key rotation, periodic check) keeps
the pin with reason ``reverify``. Everything else is refused.
"""

from __future__ import annotations

import time
import uuid

from dataagent_ocr import probe, quality
from dataagent_ocr.errors import OcrError, SwitchRefused
from dataagent_ocr.profiles import ActivePin, OcrProfile, PinReason, ProfileStore, sha256_hex
from dataagent_ocr.probe import Fixture
from dataagent_ocr.profiles import FixtureScore, Verification
from dataagent_ocr.types import OcrProvider


def run_verification(store: ProfileStore, profile: OcrProfile, provider: OcrProvider, samples: list[Fixture] | None = None) -> Verification:
    fixtures = [probe.render_probe(), *(samples or [])]
    scores: list[FixtureScore] = []
    latency = 0
    reported_model = fingerprint = None
    confidence_source = "none"
    for index, fixture in enumerate(fixtures):
        threshold = profile.quality.probe_min_score if index == 0 else profile.quality.sample_min_score
        started = time.monotonic()
        try:
            result = provider.recognize_page(fixture.image, lang=None)
        except OcrError:
            raise
        latency = max(latency, int((time.monotonic() - started) * 1000))
        text = "\n".join(block.text for block in result.blocks)
        ratio, digits_ok = probe.score(fixture.expected, text)
        scores.append(
            FixtureScore(
                fixture=fixture.fixture,
                image_digest="sha256:" + sha256_hex(fixture.image),
                expected_digest="sha256:" + sha256_hex(fixture.expected.encode("utf-8")),
                score=ratio,
                digits_ok=digits_ok,
                passed=ratio >= threshold and digits_ok and not result.format_error,
                blocks=len(result.blocks),
                bbox_blocks=sum(1 for block in result.blocks if block.bbox),
                error="output did not follow the requested format" if result.format_error else None,
            )
        )
        reported_model = result.reported_model or reported_model
        fingerprint = result.system_fingerprint or fingerprint
        if result.confidence_source != "none":
            confidence_source = result.confidence_source
    verification = Verification(
        verification_id="ocrv-" + uuid.uuid4().hex[:16],
        profile_ref=profile.ref,
        config_digest=profile.config_digest(),
        passed=all(item.passed for item in scores),
        fixtures=scores,
        latency_ms=latency,
        confidence_source=confidence_source,
        reported_model=reported_model,
        system_fingerprint=fingerprint,
        engine_version=getattr(provider, "engine_version", None),
    )
    store.save_verification(verification)
    return verification


def authorize_pin(
    store: ProfileStore,
    profile: OcrProfile,
    *,
    reason: PinReason | None,
    user_instruction: str | None = None,
) -> tuple[PinReason, str | None]:
    """Return the (reason, evidence) to pin ``profile`` with, or raise."""

    current = store.active()
    if current is None:
        return "initial_setup", None
    if current.profile_id == profile.profile_id:
        pinned = store.get(current.profile_id, current.revision)
        if pinned.config_digest() == profile.config_digest():
            return "reverify", None
    if reason == "user_request":
        if not user_instruction or not user_instruction.strip():
            raise SwitchRefused(
                "switching the OCR provider on user request needs the user's instruction",
                action="pass the user's own words with --user-instruction",
            )
        return "user_request", user_instruction.strip()
    if reason == "quality_degraded":
        pinned = store.get(current.profile_id, current.revision)
        verdict = quality.evaluate(store, pinned)
        if verdict.status != "degraded":
            raise SwitchRefused(
                f"quality of {current.ref} is {verdict.status}, not degraded",
                action="keep the pinned provider; switch only on the user's explicit request",
            )
        return "quality_degraded", verdict.verdict_id
    raise SwitchRefused(
        f"{current.ref} is pinned; a different provider needs --reason user_request or quality_degraded",
        action="keep the pinned provider unless the user asks to change it or quality is degraded",
    )


def pin(store: ProfileStore, profile: OcrProfile, verification: Verification, *, reason: PinReason, evidence: str | None) -> ActivePin:
    if not verification.passed or verification.config_digest != profile.config_digest():
        raise SwitchRefused("only a passed verification of this exact profile can be pinned")
    current = store.active()
    record = ActivePin(
        profile_id=profile.profile_id,
        revision=profile.revision,
        config_digest=profile.config_digest(),
        verification_id=verification.verification_id,
        reason=reason,
        evidence=evidence,
        previous=current.ref if current and current.ref != profile.ref else (current.previous if current else None),
        reported_model=verification.reported_model,
    )
    store.write_pin(record)
    return record
