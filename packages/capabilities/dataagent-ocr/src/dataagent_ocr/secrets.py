"""Credential references for OCR providers.

A profile stores a *reference*, never the key itself:

- ``file:<name>`` — ``<data_root>/secrets/ocr/<name>.key``, directory 0700,
  file 0600, written atomically; ``<data_root>/secrets/.gitignore`` ignores
  everything. Default for keys the user types in.
- ``env:<VAR>`` — read from the process environment at call time. Under Mint
  the child environment is cleared, so this only works where the host
  injects the variable.
- ``keychain:<service>/<account>`` — macOS keychain, read-only via
  ``security find-generic-password -w``; the user creates the entry.

Keys never appear in profiles, digests, events, CLI output or error text.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from dataagent_ocr.errors import ConfigError, CredentialsError

_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


def secrets_dir(data_root: Path) -> Path:
    return data_root / "secrets" / "ocr"


def _ensure_dir(data_root: Path) -> Path:
    base = data_root / "secrets"
    base.mkdir(parents=True, exist_ok=True)
    os.chmod(base, 0o700)
    ignore = base / ".gitignore"
    if not ignore.exists():
        ignore.write_text("*\n", encoding="utf-8")
    target = secrets_dir(data_root)
    target.mkdir(parents=True, exist_ok=True)
    os.chmod(target, 0o700)
    return target


def store_file_secret(data_root: Path, name: str, value: str) -> str:
    """Write ``value`` to a 0600 file and return its ``file:`` reference."""

    if not _NAME.match(name):
        raise ConfigError(f"invalid secret name {name!r}")
    value = value.strip()
    if not value:
        raise CredentialsError("api key is empty", action="provide a non-empty api key")
    target = _ensure_dir(data_root) / f"{name}.key"
    tmp = target.with_suffix(".key.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, value.encode("utf-8"))
    finally:
        os.close(fd)
    os.chmod(tmp, 0o600)
    os.replace(tmp, target)
    return f"file:{name}"


def validate_ref(ref: str) -> str:
    kind, _, rest = ref.partition(":")
    if kind == "file" and _NAME.match(rest):
        return ref
    if kind == "env" and re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", rest):
        return ref
    if kind == "keychain" and re.match(r"^[^/\s]+/[^/\s]+$", rest):
        return ref
    raise ConfigError(
        f"unsupported secret reference {ref!r}",
        action="use file:<name>, env:<VAR> or keychain:<service>/<account>",
    )


def resolve(ref: str, data_root: Path) -> str:
    validate_ref(ref)
    kind, _, rest = ref.partition(":")
    if kind == "file":
        path = secrets_dir(data_root) / f"{rest}.key"
        if not path.is_file():
            raise CredentialsError(
                f"secret {ref} is missing", action="set the api key again (set-key)"
            )
        mode = path.stat().st_mode & 0o777
        if mode & 0o077:
            raise CredentialsError(
                f"secret {ref} is readable by other users (mode {mode:o})",
                action=f"chmod 600 {path}",
            )
        value = path.read_text(encoding="utf-8").strip()
    elif kind == "env":
        value = os.environ.get(rest, "").strip()
        if not value:
            raise CredentialsError(
                f"environment variable {rest} is not set in this process",
                action="store the key with --api-key-stdin instead (Mint clears child environments)",
            )
    else:
        service, _, account = rest.partition("/")
        try:
            proc = subprocess.run(
                ["security", "find-generic-password", "-s", service, "-a", account, "-w"],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise CredentialsError(f"keychain is not available: {type(exc).__name__}") from exc
        if proc.returncode != 0:
            raise CredentialsError(f"keychain entry {service}/{account} not found")
        value = proc.stdout.strip()
    if not value:
        raise CredentialsError(f"secret {ref} is empty")
    return value


def redact(text: str, secret: str | None) -> str:
    if secret and secret in text:
        return text.replace(secret, "***")
    return text
