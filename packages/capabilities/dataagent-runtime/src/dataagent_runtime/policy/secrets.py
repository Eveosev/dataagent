"""Credential references resolved by the process that needs the value.

A connection manifest stores logical names, never the credential itself:

- ``env:<VAR>`` — read from this process's environment at call time.
- ``keychain:<service>/<account>`` — macOS keychain, read-only through
  ``security find-generic-password -w``.
- ``file:<name>`` — ``<data_root>/secrets/<name>.key``. ``<data_root>`` is
  the workspace ``.dataagent`` directory; ``file:`` never reads outside
  ``.dataagent/secrets/``. The directory is 0700 and the file 0600. The name
  may contain ``/``-separated segments below ``secrets/`` (OCR keeps its
  keys under ``secrets/ocr/``).

Resolved values are returned only to the caller. They never appear in
error messages, logs, profiles or results; callers should treat the returned
string as a secret and redact it if it could otherwise be echoed.
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path

__all__ = [
    "InvalidSecretRef",
    "SecretError",
    "SecretUnavailable",
    "redact",
    "resolve",
    "secrets_dir",
    "store_file_secret",
    "validate_ref",
]

_FILE_NAME = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_.-]*(?:/[A-Za-z0-9][A-Za-z0-9_.-]*)*$"
)
_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_KEYCHAIN_NAME = re.compile(r"^[^/\s]+/[^/\s]+$")
_ACTION = "use file:<name>, env:<VAR> or keychain:<service>/<account>"


class SecretError(ValueError):
    """A credential reference cannot be used; no resolved value is included."""

    def __init__(self, message: str, *, action: str | None = None):
        super().__init__(message)
        self.message = message
        self.action = action


class InvalidSecretRef(SecretError):
    """The logical name is malformed or uses an unsupported scheme."""


class SecretUnavailable(SecretError):
    """The logical name is valid but its value cannot be read."""


def secrets_dir(data_root: str | Path) -> Path:
    """The only directory a ``file:`` reference may read from."""

    return Path(data_root) / "secrets"


def _ensure_private_dir(path: Path) -> Path:
    if path.is_symlink():
        raise SecretUnavailable("secret directory must not be a symlink")
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, 0o700)
    return path


def _check_private_dir(path: Path) -> None:
    if path.is_symlink():
        raise SecretUnavailable("secret directory must not be a symlink")
    mode = path.stat().st_mode & 0o777
    if mode & 0o077:
        raise SecretUnavailable(
            f"secret directory {path} is accessible by other users (mode {mode:o})",
            action=f"chmod 700 {path}",
        )


def store_file_secret(data_root: str | Path, name: str, value: str) -> str:
    """Write ``value`` to a 0600 file and return its ``file:`` reference."""

    if not isinstance(name, str) or not _FILE_NAME.fullmatch(name):
        raise InvalidSecretRef("invalid secret name", action=_ACTION)
    value = value.strip() if isinstance(value, str) else ""
    if not value:
        raise SecretUnavailable("secret value is empty")
    base = _ensure_private_dir(secrets_dir(data_root))
    parent = base
    for part in name.split("/")[:-1]:
        parent = _ensure_private_dir(parent / part)
    ignore = base / ".gitignore"
    if not ignore.exists() and not ignore.is_symlink():
        ignore.write_text("*\n", encoding="utf-8")
    target = parent / f"{name.rsplit('/', 1)[-1]}.key"
    fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=parent)
    try:
        os.fchmod(fd, 0o600)
        os.write(fd, value.encode("utf-8"))
    finally:
        os.close(fd)
    os.replace(tmp_name, target)
    return f"file:{name}"


def validate_ref(ref: str) -> str:
    """Return ``ref`` when it is a supported logical name."""

    if not isinstance(ref, str) or ":" not in ref:
        raise InvalidSecretRef("unsupported secret reference", action=_ACTION)
    kind, _, rest = ref.partition(":")
    if kind == "file" and _FILE_NAME.fullmatch(rest):
        return ref
    if kind == "env" and _ENV_NAME.fullmatch(rest):
        return ref
    if kind == "keychain" and _KEYCHAIN_NAME.fullmatch(rest):
        return ref
    raise InvalidSecretRef("unsupported secret reference", action=_ACTION)


def _file_value(rest: str, data_root: str | Path) -> str:
    base = secrets_dir(data_root)
    try:
        resolved_base = base.resolve()
        path = (base / f"{rest}.key").resolve()
    except (OSError, RuntimeError):
        raise SecretUnavailable("secret location is unavailable") from None
    if not path.is_relative_to(resolved_base):
        raise SecretUnavailable("secret is outside the workspace secrets directory")
    if not path.is_file():
        raise SecretUnavailable("secret is missing", action="store the secret again")
    _check_private_dir(base)
    _check_private_dir(path.parent)
    mode = path.stat().st_mode & 0o777
    if mode & 0o077:
        raise SecretUnavailable(
            f"secret is readable by other users (mode {mode:o})",
            action=f"chmod 600 {path}",
        )
    return path.read_text(encoding="utf-8").strip()


def resolve(ref: str, data_root: str | Path) -> str:
    """Resolve a logical name to its value; the value must not be echoed."""

    validate_ref(ref)
    kind, _, rest = ref.partition(":")
    if kind == "file":
        value = _file_value(rest, data_root)
    elif kind == "env":
        value = os.environ.get(rest, "").strip()
        if not value:
            raise SecretUnavailable(
                f"environment variable {rest} is not set in this process",
                action="inject the variable into the probing process only",
            )
    else:
        service, _, account = rest.partition("/")
        try:
            proc = subprocess.run(
                ["security", "find-generic-password", "-s", service, "-a", account, "-w"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise SecretUnavailable(
                f"keychain is not available: {type(exc).__name__}"
            ) from None
        if proc.returncode != 0:
            raise SecretUnavailable(f"keychain entry {service}/{account} not found")
        value = proc.stdout.strip()
    if not value:
        raise SecretUnavailable("secret is empty")
    return value


def redact(text: str, secret: str | None) -> str:
    """Remove a resolved value from text before it can be logged."""

    if secret and secret in text:
        return text.replace(secret, "***")
    return text
