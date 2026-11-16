"""OCR profiles, verifications and the active pin under ``<data_root>/ocr/``.

Layout::

    ocr/profiles/<profile_id>/r<N>.json   immutable profile revisions
    ocr/verifications/<verification_id>.json
    ocr/active.json                       the pin (one active profile)
    ocr/quality/usage.jsonl               per-call usage records
    ocr/quality/feedback.jsonl            user/agent corrections
    ocr/quality/verdict.json              last quality verdict
    ocr/events.jsonl                      audit trail
    ocr/engines/<engine>/                 isolated engine environments

``config_digest`` covers every field that changes recognition output
(provider kind, endpoint, model, prompt version, request parameters, engine
lock and adapter digests, quality policy) and excludes the secret value,
revision number, timestamps and notes. The pin binds a profile revision, its
digest and a passed verification of that same digest.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from dataagent_ocr.errors import ConfigError, NotConfigured, NotVerified, PinMismatch

Deployment = Literal["local", "private_cloud", "vendor_api"]
ProviderKind = Literal["openai_compat", "engine", "command"]
PinReason = Literal["initial_setup", "user_request", "quality_degraded", "reverify"]

_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,47}$")


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def canonical(data: Any) -> bytes:
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OpenAICompatConfig(_Model):
    base_url: str
    model: str = Field(min_length=1)
    api_key_ref: str | None = None
    deployment: Deployment
    timeout_s: float = Field(default=120.0, gt=0, le=900)
    max_tokens: int = Field(default=4096, ge=256, le=65536)
    json_mode: bool = True
    logprobs: Literal["auto", "on", "off"] = "auto"
    prompt_version: str = "ocr-blocks-v1"
    max_retries: int = Field(default=2, ge=0, le=5)

    @field_validator("base_url")
    @classmethod
    def _url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("base_url must be an http(s) URL, e.g. https://host/v1")
        if parsed.username or parsed.password:
            raise ValueError("base_url must not embed credentials")
        return value.rstrip("/")


class EngineConfig(_Model):
    engine: str = Field(min_length=1)
    lock_digest: str = Field(min_length=16)
    worker_digest: str = Field(min_length=16)
    lang: str | None = None
    timeout_s: float = Field(default=300.0, gt=0, le=3600)


class CommandConfig(_Model):
    argv: list[str] = Field(min_length=1)
    # File whose bytes define the adapter (e.g. the script in argv); its digest
    # is part of the config digest so editing the adapter forces re-verification.
    adapter_path: str | None = None
    adapter_digest: str | None = None
    timeout_s: float = Field(default=300.0, gt=0, le=3600)

    @model_validator(mode="after")
    def _adapter_pair(self) -> "CommandConfig":
        if (self.adapter_path is None) != (self.adapter_digest is None):
            raise ValueError("adapter_path and adapter_digest go together")
        return self


class QualityPolicy(_Model):
    window_pages: int = Field(default=50, ge=5)
    min_pages: int = Field(default=20, ge=1)
    empty_rate: float = Field(default=0.15, ge=0, le=1)
    low_confidence: float = Field(default=0.6, ge=0, le=1)
    low_confidence_rate: float = Field(default=0.30, ge=0, le=1)
    format_error_rate: float = Field(default=0.10, ge=0, le=1)
    correction_pages: int = Field(default=3, ge=1)
    probe_min_score: float = Field(default=0.90, ge=0, le=1)
    sample_min_score: float = Field(default=0.90, ge=0, le=1)


class OcrProfile(_Model):
    profile_id: str
    revision: int = Field(default=0, ge=0)
    kind: ProviderKind
    openai_compat: OpenAICompatConfig | None = None
    engine: EngineConfig | None = None
    command: CommandConfig | None = None
    quality: QualityPolicy = Field(default_factory=QualityPolicy)
    created_at: str = Field(default_factory=now_iso)
    note: str | None = None

    @field_validator("profile_id")
    @classmethod
    def _pid(cls, value: str) -> str:
        if not _ID.match(value):
            raise ValueError("profile_id must match [a-z0-9][a-z0-9_-]{0,47}")
        return value

    @model_validator(mode="after")
    def _one_body(self) -> "OcrProfile":
        bodies = {
            "openai_compat": self.openai_compat,
            "engine": self.engine,
            "command": self.command,
        }
        if bodies[self.kind] is None or any(v is not None for k, v in bodies.items() if k != self.kind):
            raise ValueError(f"profile of kind {self.kind} must carry exactly the {self.kind} section")
        return self

    def config_digest(self) -> str:
        body = self.model_dump(mode="json", exclude={"revision", "created_at", "note"})
        if self.openai_compat is not None:
            # The reference identifies where the key lives; rotating the key
            # under the same reference keeps the digest (re-verify, no switch).
            body["openai_compat"].pop("api_key_ref", None)
        return "sha256:" + sha256_hex(canonical(body))

    @property
    def ref(self) -> str:
        return f"{self.profile_id}@r{self.revision}"

    @property
    def remote(self) -> bool:
        return self.kind == "openai_compat" and self.openai_compat.deployment != "local"

    def summary(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "profile": self.ref,
            "kind": self.kind,
            "config_digest": self.config_digest(),
        }
        if self.openai_compat:
            c = self.openai_compat
            out.update(
                base_url=c.base_url,
                model=c.model,
                deployment=c.deployment,
                api_key_ref=c.api_key_ref,
                json_mode=c.json_mode,
                logprobs=c.logprobs,
            )
        if self.engine:
            out.update(engine=self.engine.engine, lang=self.engine.lang)
        if self.command:
            out.update(argv=self.command.argv)
        return out


class FixtureScore(_Model):
    fixture: str
    image_digest: str
    expected_digest: str
    score: float
    digits_ok: bool
    passed: bool
    blocks: int
    bbox_blocks: int
    error: str | None = None


class Verification(_Model):
    verification_id: str
    profile_ref: str
    config_digest: str
    at: str = Field(default_factory=now_iso)
    passed: bool
    fixtures: list[FixtureScore]
    latency_ms: int
    confidence_source: str
    reported_model: str | None = None
    system_fingerprint: str | None = None
    engine_version: str | None = None


class ActivePin(_Model):
    profile_id: str
    revision: int
    config_digest: str
    verification_id: str
    pinned_at: str = Field(default_factory=now_iso)
    reason: PinReason
    evidence: str | None = None
    previous: str | None = None
    reported_model: str | None = None

    @property
    def ref(self) -> str:
        return f"{self.profile_id}@r{self.revision}"


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


class ProfileStore:
    def __init__(self, data_root: Path):
        self.data_root = Path(data_root)
        self.root = self.data_root / "ocr"

    # -- profiles -------------------------------------------------------
    def _profile_dir(self, profile_id: str) -> Path:
        return self.root / "profiles" / profile_id

    def revisions(self, profile_id: str) -> list[int]:
        directory = self._profile_dir(profile_id)
        if not directory.is_dir():
            return []
        return sorted(int(p.stem[1:]) for p in directory.glob("r*.json") if p.stem[1:].isdigit())

    def get(self, profile_id: str, revision: int | None = None) -> OcrProfile:
        revs = self.revisions(profile_id)
        if not revs:
            raise NotConfigured(f"OCR profile {profile_id!r} does not exist")
        rev = revs[-1] if revision is None else revision
        path = self._profile_dir(profile_id) / f"r{rev}.json"
        if not path.is_file():
            raise NotConfigured(f"OCR profile {profile_id}@r{rev} does not exist")
        return OcrProfile.model_validate_json(path.read_text(encoding="utf-8"))

    def resolve(self, ref: str) -> OcrProfile:
        profile_id, _, rev = ref.partition("@r")
        return self.get(profile_id, int(rev) if rev else None)

    def save(self, profile: OcrProfile) -> tuple[OcrProfile, bool]:
        """Store ``profile`` as a new revision unless the latest has the same digest."""

        revs = self.revisions(profile.profile_id)
        if revs:
            latest = self.get(profile.profile_id, revs[-1])
            same_ref = (
                latest.openai_compat is None
                or profile.openai_compat is None
                or latest.openai_compat.api_key_ref == profile.openai_compat.api_key_ref
            )
            if latest.config_digest() == profile.config_digest() and same_ref:
                return latest, False
        stored = profile.model_copy(update={"revision": (revs[-1] + 1) if revs else 1})
        path = self._profile_dir(stored.profile_id) / f"r{stored.revision}.json"
        _atomic_write(path, stored.model_dump_json(indent=2).encode("utf-8"))
        self.event("profile_saved", profile=stored.ref, config_digest=stored.config_digest())
        return stored, True

    def list_profiles(self) -> list[OcrProfile]:
        base = self.root / "profiles"
        if not base.is_dir():
            return []
        return [self.get(p.name) for p in sorted(base.iterdir()) if p.is_dir() and self.revisions(p.name)]

    # -- verifications --------------------------------------------------
    def save_verification(self, verification: Verification) -> None:
        path = self.root / "verifications" / f"{verification.verification_id}.json"
        _atomic_write(path, verification.model_dump_json(indent=2).encode("utf-8"))
        self.event(
            "verified",
            profile=verification.profile_ref,
            verification=verification.verification_id,
            passed=verification.passed,
        )

    def get_verification(self, verification_id: str) -> Verification:
        path = self.root / "verifications" / f"{verification_id}.json"
        if not path.is_file():
            raise PinMismatch(f"verification {verification_id} is missing")
        return Verification.model_validate_json(path.read_text(encoding="utf-8"))

    # -- pin ------------------------------------------------------------
    def active(self) -> ActivePin | None:
        path = self.root / "active.json"
        if not path.is_file():
            return None
        return ActivePin.model_validate_json(path.read_text(encoding="utf-8"))

    def write_pin(self, pin: ActivePin) -> None:
        _atomic_write(self.root / "active.json", pin.model_dump_json(indent=2).encode("utf-8"))
        self.event(
            "pinned",
            profile=pin.ref,
            reason=pin.reason,
            previous=pin.previous,
            verification=pin.verification_id,
            evidence=pin.evidence,
        )

    def load_pinned(self) -> tuple[ActivePin, OcrProfile, Verification]:
        """Return the pin with its profile and verification, checking all bindings."""

        pin = self.active()
        if pin is None:
            raise NotConfigured(
                "no OCR provider is configured",
                action="run the dataagent-ocr setup (configure + verify)",
            )
        profile = self.get(pin.profile_id, pin.revision)
        digest = profile.config_digest()
        if digest != pin.config_digest:
            raise PinMismatch(
                f"profile {pin.ref} changed after it was pinned",
                action="verify the profile again before use",
            )
        verification = self.get_verification(pin.verification_id)
        if not verification.passed or verification.config_digest != digest:
            raise NotVerified(
                f"pinned verification {pin.verification_id} does not cover {pin.ref}",
                action="verify the profile again before use",
            )
        return pin, profile, verification

    # -- audit ----------------------------------------------------------
    def event(self, name: str, /, **fields: Any) -> None:
        path = self.root / "events.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {"at": now_iso(), "event": name, **{k: v for k, v in fields.items() if v is not None}}
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def default_deployment(base_url: str) -> Deployment:
    host = (urlparse(base_url).hostname or "").lower()
    if host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".localhost"):
        return "local"
    return "vendor_api"


def validate_profile_id(value: str) -> str:
    if not _ID.match(value):
        raise ConfigError("profile id must match [a-z0-9][a-z0-9_-]{0,47}")
    return value
