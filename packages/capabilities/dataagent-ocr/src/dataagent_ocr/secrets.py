"""Credential references for OCR providers.

OCR uses the platform credential resolver
(``dataagent_runtime.policy.secrets``) so every layer accepts the same
logical names: ``file:``, ``env:`` and ``keychain:``. New OCR keys live in
the default external directory, ``$HOME/.dataagent/secrets/ocr/`` (or
``DATAAGENT_SECRETS_DIR`` when it is an absolute path): the directory is 0700
and each key file 0600. The legacy ``<data_root>/secrets/ocr/`` location is
still read for existing installations and emits
``LegacySecretLocationWarning``. Profiles, digests, events, CLI output and
error text never contain the value.
"""

from __future__ import annotations

from pathlib import Path

from dataagent_runtime.policy import secrets as _secrets

from dataagent_ocr.errors import ConfigError, CredentialsError

__all__ = ["redact", "resolve", "secrets_dir", "store_file_secret", "validate_ref"]


def secrets_dir(data_root: Path) -> Path:
    """The default OCR secrets directory (``$HOME/.dataagent/secrets/ocr``)."""

    return _secrets.secrets_dir(data_root) / "ocr"


def _shared_ref(ref: str) -> str:
    """Map OCR's documented ``file:<name>`` onto ``secrets/ocr/<name>.key``."""

    if isinstance(ref, str) and ref.startswith("file:"):
        name = ref[5:]
        if "/" not in name:
            return f"file:ocr/{name}"
    return ref


def store_file_secret(data_root: Path, name: str, value: str) -> str:
    """Write ``value`` under the default ``.dataagent/secrets/ocr/`` and return its ref."""

    if not isinstance(name, str) or not name or len(name) > 64 or "/" in name:
        raise ConfigError("invalid secret name", action="use a plain OCR profile id")
    try:
        _secrets.store_default_secret(f"ocr/{name}", value)
    except _secrets.InvalidSecretRef:
        raise ConfigError("invalid secret name", action="use a plain OCR profile id") from None
    except _secrets.SecretUnavailable as exc:
        raise CredentialsError(exc.message, action="provide a non-empty api key") from None
    return f"file:{name}"


def validate_ref(ref: str) -> str:
    try:
        _secrets.validate_ref(_shared_ref(ref))
    except _secrets.InvalidSecretRef:
        raise ConfigError(
            "unsupported secret reference",
            action="use file:<name>, env:<VAR> or keychain:<service>/<account>",
        ) from None
    return ref


def resolve(ref: str, data_root: Path) -> str:
    """Resolve a ref from the default directory, falling back to the workspace."""

    try:
        return _secrets.resolve(_shared_ref(ref), data_root)
    except _secrets.InvalidSecretRef:
        raise ConfigError(
            "unsupported secret reference",
            action="use file:<name>, env:<VAR> or keychain:<service>/<account>",
        ) from None
    except _secrets.SecretUnavailable as exc:
        raise CredentialsError(exc.message, action=exc.action) from None


def redact(text: str, secret: str | None) -> str:
    return _secrets.redact(text, secret)
