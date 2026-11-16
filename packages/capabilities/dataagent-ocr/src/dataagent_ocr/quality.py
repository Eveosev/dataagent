"""Quality signals for the pinned provider and the degradation verdict.

Signals (per recognized page, recorded by the engine adapter):
``empty`` (no text), ``low_confidence`` (mean below policy, only when the
provider exposes confidence), ``format_error`` (model ignored the output
contract). User/agent feedback adds ``correction`` pages (wrong digits,
missed or garbled text found during review).

Verdict over the last ``window_pages`` usage records of the pinned
``profile@revision`` (feedback counted over the same span):

- fewer than ``min_pages`` records and no feedback → ``insufficient``;
- any rate at or above its threshold, or ``correction_pages`` reached → ``degraded``;
- otherwise ``ok``.

``degraded`` is the only automatic trigger for re-selection, and it only
*proposes* it: the provider keeps running until the user approves a switch.
Errors (credentials, network, timeouts) are not quality signals.
"""

from __future__ import annotations

import json
from collections import deque
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from dataagent_ocr.profiles import OcrProfile, ProfileStore, canonical, now_iso, sha256_hex


class UsageRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    at: str = Field(default_factory=now_iso)
    profile: str
    blocks: int
    empty: bool
    mean_confidence: float | None
    low_confidence: bool
    confidence_source: str
    format_error: bool
    latency_ms: int
    reported_model: str | None = None


class Feedback(BaseModel):
    model_config = ConfigDict(extra="forbid")
    at: str = Field(default_factory=now_iso)
    profile: str
    kind: Literal["correction", "missed_text", "garbled", "wrong_digits", "ok"]
    pages: int = Field(default=1, ge=1)
    document: str | None = None
    note: str | None = None


class Verdict(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verdict_id: str
    profile: str
    at: str = Field(default_factory=now_iso)
    status: Literal["ok", "degraded", "insufficient"]
    pages: int
    rates: dict[str, float]
    correction_pages: int
    reasons: list[str]


def _quality_dir(store: ProfileStore) -> Path:
    return store.root / "quality"


def _append(path: Path, record: BaseModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(record.model_dump_json() + "\n")


def record_usage(store: ProfileStore, record: UsageRecord) -> None:
    _append(_quality_dir(store) / "usage.jsonl", record)


def record_feedback(store: ProfileStore, feedback: Feedback) -> None:
    _append(_quality_dir(store) / "feedback.jsonl", feedback)
    store.event("feedback", profile=feedback.profile, kind=feedback.kind, pages=feedback.pages)


def _tail(path: Path, profile: str, limit: int) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    window: deque = deque(maxlen=limit)
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if item.get("profile") == profile:
                window.append(item)
    return list(window)


def evaluate(store: ProfileStore, profile: OcrProfile) -> Verdict:
    policy = profile.quality
    usage = _tail(_quality_dir(store) / "usage.jsonl", profile.ref, policy.window_pages)
    since = usage[0]["at"] if usage else None
    feedback = [
        item
        for item in _tail(_quality_dir(store) / "feedback.jsonl", profile.ref, 10_000)
        if since is None or item["at"] >= since
    ]
    pages = len(usage)
    bad_feedback = sum(item["pages"] for item in feedback if item["kind"] != "ok")
    rates: dict[str, float] = {}
    reasons: list[str] = []
    if pages:
        rates["empty"] = round(sum(1 for u in usage if u["empty"]) / pages, 4)
        rates["format_error"] = round(sum(1 for u in usage if u["format_error"]) / pages, 4)
        with_conf = [u for u in usage if u["mean_confidence"] is not None]
        if with_conf:
            rates["low_confidence"] = round(sum(1 for u in with_conf if u["low_confidence"]) / len(with_conf), 4)
    if bad_feedback >= policy.correction_pages:
        reasons.append(f"{bad_feedback} page(s) reported wrong by review (threshold {policy.correction_pages})")
    if pages >= policy.min_pages:
        if rates.get("empty", 0) >= policy.empty_rate:
            reasons.append(f"empty page rate {rates['empty']:.0%} ≥ {policy.empty_rate:.0%}")
        if rates.get("format_error", 0) >= policy.format_error_rate:
            reasons.append(f"output format error rate {rates['format_error']:.0%} ≥ {policy.format_error_rate:.0%}")
        if rates.get("low_confidence", 0) >= policy.low_confidence_rate:
            reasons.append(
                f"low-confidence page rate {rates['low_confidence']:.0%} ≥ {policy.low_confidence_rate:.0%}"
            )
    if reasons:
        status = "degraded"
    elif pages < policy.min_pages and not feedback:
        status = "insufficient"
    else:
        status = "ok"
    body = {"profile": profile.ref, "pages": pages, "rates": rates, "corrections": bad_feedback, "status": status}
    verdict = Verdict(
        verdict_id="qv-" + sha256_hex(canonical({**body, "last": usage[-1]["at"] if usage else None}))[:16],
        profile=profile.ref,
        status=status,
        pages=pages,
        rates=rates,
        correction_pages=bad_feedback,
        reasons=reasons,
    )
    path = _quality_dir(store) / "verdict.json"
    previous = None
    if path.is_file():
        try:
            previous = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            previous = None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(verdict.model_dump_json(indent=2), encoding="utf-8")
    if not previous or previous.get("status") != status or previous.get("profile") != profile.ref:
        store.event("quality_verdict", profile=profile.ref, status=status, verdict=verdict.verdict_id, reasons=reasons or None)
    return verdict


def last_verdict(store: ProfileStore) -> Verdict | None:
    path = _quality_dir(store) / "verdict.json"
    if not path.is_file():
        return None
    return Verdict.model_validate_json(path.read_text(encoding="utf-8"))
