"""Engine acquisition and version alignment (DA07.10.1, 07 §5.4).

S0 engines: ``duckdb`` (SQL execution) and the expression interpreter.
No network downloads: the installed distribution is inspected via
``importlib.metadata`` and compared against the expected binding; a
mismatch fails closed with ``da07.engine_version_mismatch``. Wheel digests
are verified when the distribution is a wheel; editable installs report
that the digest cannot be verified.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field as PydanticField

from dataagent_contracts.core import (
    CallContext,
    CapabilityResult,
    CapabilityStatus,
    EngineBinding,
    Issue,
    Severity,
)

from dataagent_application import helpers
from dataagent_runtime.errors import CapabilityError, invalid_input
from dataagent_runtime.registry import operation

ENGINE_PACKAGES = {
    "duckdb": "duckdb",
    "expression": "dataagent-application",
    "sqlglot": "sqlglot",
    "openpyxl": "openpyxl",
}

# The expression interpreter ships inside this package but is referenced by
# specs as the engine id ``dataagent-expression`` (07 §5.1).
ENGINE_ALIASES = {
    "expression": "expression",
    "dataagent-expression": "expression",
}

EXPRESSION_INTERPRETER_VERSION = "0.1.0"

MISMATCH_CODE = "da07.engine_version_mismatch"


class _IO(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AcquireAndAlignEngineInput(_IO):
    engine_id: str = PydanticField(min_length=1)
    expected_version: str | None = None
    wheel_digest: str | None = None


class AcquireAndAlignEngineOutput(_IO):
    binding: EngineBinding
    installed_version: str
    digest_verified: bool | None = None
    digest_note: str | None = None


def _installed_version(engine_id: str) -> str:
    package = ENGINE_PACKAGES.get(engine_id)
    if package is None:
        raise invalid_input(
            f"unknown engine_id {engine_id!r}; S0 engines: {sorted(ENGINE_PACKAGES)}",
            target="engine_id",
        )
    if engine_id == "expression":
        return EXPRESSION_INTERPRETER_VERSION
    try:
        return importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError as exc:
        raise invalid_input(
            f"engine {engine_id!r} ({package}) is not installed", target="engine_id"
        ) from exc


def installed_engine_version(engine_id: str) -> str:
    """Installed version of an engine, accepting the spec-facing aliases."""

    return _installed_version(ENGINE_ALIASES.get(engine_id, engine_id))


def _locked_version(engine_id: str) -> str | None:
    """Version pinned for this engine in the package's ``uv.lock`` (07 §5.4).

    The lock next to this package (dev checkout or bundle) is authoritative;
    when it cannot be located we fall back to the installed version only.
    """

    package = ENGINE_PACKAGES.get(ENGINE_ALIASES.get(engine_id, engine_id))
    if package is None or engine_id in ENGINE_ALIASES:
        return None
    for root in Path(__file__).resolve().parents:
        lock = root / "uv.lock"
        if lock.is_file():
            text = lock.read_text(encoding="utf-8")
            match = re.search(
                rf'name = "{re.escape(package)}"\nversion = "([^"]+)"', text
            )
            if match:
                return match.group(1)
            return None
    return None


def engine_binding_issue(
    binding: EngineBinding, *, expected_engine_id: str | None = None
) -> Issue | None:
    """07 §5.4 runtime comparison of a spec's ``EngineBinding``.

    Returns the failure issue when the bound engine is not the one this
    operation executes, is unknown, or its version differs from the
    installed distribution (and the ``uv.lock`` pin, when locatable).
    ``None`` means the binding is aligned.
    """

    if expected_engine_id is not None and binding.engine_id != expected_engine_id:
        return Issue(
            code="da07.engine_binding_mismatch",
            severity=Severity.error,
            message=(
                f"spec binds engine {binding.engine_id!r} but this operation executes "
                f"{expected_engine_id!r}"
            ),
            retryable=False,
            suggested_action="evaluate the spec with the operation matching its EngineBinding",
            target="spec.engine_binding.engine_id",
        )
    try:
        installed = installed_engine_version(binding.engine_id)
    except CapabilityError as exc:
        return Issue(
            code="da07.engine_binding_mismatch",
            severity=Severity.error,
            message=str(exc),
            retryable=False,
            suggested_action="align the spec's EngineBinding with an S0 engine",
            target="spec.engine_binding.engine_id",
        )
    if binding.engine_version != installed:
        return Issue(
            code=MISMATCH_CODE,
            severity=Severity.error,
            message=(
                f"engine {binding.engine_id} version mismatch: spec binds "
                f"{binding.engine_version}, installed {installed}"
            ),
            retryable=False,
            suggested_action="align the installed engine with the spec's EngineBinding; no network download happens here",
            target="spec.engine_binding.engine_version",
        )
    return None


def _wheel_digest(engine_id: str) -> tuple[bool | None, str | None, str | None]:
    """Verify the installed wheel digest when locatable."""

    package = ENGINE_PACKAGES.get(engine_id)
    if package is None or engine_id == "expression":
        return None, None, "interpreter ships inside dataagent-application; no wheel digest"
    try:
        distribution = importlib.metadata.distribution(package)
    except importlib.metadata.PackageNotFoundError:
        return None, None, None
    path = getattr(distribution, "_path", None)
    name = str(getattr(path, "name", "") or "")
    if name.endswith(".whl"):
        digest = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        return True, digest, None
    return False, None, "distribution is not a wheel (editable/path install); digest not verifiable"


@operation(
    "DA07.10.1",
    input_model=AcquireAndAlignEngineInput,
    output_model=AcquireAndAlignEngineOutput,
    description="引擎获取与版本对齐：坐标、版本、离线包与校验和；不联网（DA07.10.1）",
    idempotent=True,
)
def acquire_and_align_engine(
    data: AcquireAndAlignEngineInput, ctx: CallContext, runtime
) -> CapabilityResult[AcquireAndAlignEngineOutput]:
    installed = _installed_version(data.engine_id)
    # Default expectation is the version pinned in uv.lock (07 §5.4): the
    # standalone call is not a no-op when the caller omits expected_version.
    expected = data.expected_version or _locked_version(data.engine_id)
    if expected is not None and installed != expected:
        return CapabilityResult[AcquireAndAlignEngineOutput](
            status=CapabilityStatus.failed,
            issues=[
                Issue(
                    code=MISMATCH_CODE,
                    severity=Severity.error,
                    message=(
                        f"engine {data.engine_id} version mismatch: expected "
                        f"{expected}, installed {installed}"
                    ),
                    retryable=False,
                    suggested_action="align the installed engine with the locked version; no network download happens here",
                    target="expected_version",
                )
            ],
        )
    verified, digest, note = _wheel_digest(data.engine_id)
    if data.wheel_digest is not None:
        if digest is None:
            return CapabilityResult[AcquireAndAlignEngineOutput](
                status=CapabilityStatus.failed,
                issues=[
                    Issue(
                        code="da07.engine_digest_unavailable",
                        severity=Severity.error,
                        message=note or "wheel digest cannot be verified for this engine",
                        retryable=False,
                        suggested_action="install from the locked wheel to verify the digest",
                        target="wheel_digest",
                    )
                ],
            )
        if digest != data.wheel_digest:
            return CapabilityResult[AcquireAndAlignEngineOutput](
                status=CapabilityStatus.failed,
                issues=[
                    Issue(
                        code="da07.engine_version_mismatch",
                        severity=Severity.error,
                        message=(
                            f"engine {data.engine_id} wheel digest mismatch: expected "
                            f"{data.wheel_digest}, computed {digest}"
                        ),
                        retryable=False,
                        suggested_action="reinstall the locked wheel",
                        target="wheel_digest",
                    )
                ],
            )
    binding = EngineBinding(
        engine_id=data.engine_id,
        engine_version=installed,
        wheel_digest=digest if (data.wheel_digest is not None and verified) else data.wheel_digest,
    )
    return CapabilityResult[AcquireAndAlignEngineOutput](
        status=CapabilityStatus.ok,
        data=AcquireAndAlignEngineOutput(
            binding=binding,
            installed_version=installed,
            digest_verified=verified,
            digest_note=note,
        ),
        completeness=helpers.complete("engine alignment"),
    )
