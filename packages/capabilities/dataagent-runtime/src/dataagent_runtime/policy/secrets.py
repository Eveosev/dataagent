"""Credential references resolved by the process that needs the value.

A connection manifest stores logical names, never the credential itself:

- ``keychain:<service>/<account>`` — recommended: macOS keychain, read-only
  through ``security find-generic-password -w``. The value stays outside the
  workspace and is managed by the user.
- ``env:<VAR>`` — read from this process's environment at call time.
- ``file:<name>`` — ``$HOME/.dataagent/secrets/<name>.key``. The external
  directory is 0700 and the file 0600. ``file:`` never reads outside the
  selected secrets directory. The name may contain ``/``-separated segments
  below ``secrets/`` (OCR keeps its keys under ``secrets/ocr/``).

The previous workspace location ``<data_root>/secrets/`` is still readable so
existing installations keep working, but resolving a value from it emits
:class:`LegacySecretLocationWarning`. New secrets should be stored outside the
workspace (``keychain:`` where possible, or the default external directory);
a secret inside the workspace can be read by shells and by the agent.

Resolved values are returned only to the caller. They never appear in
error messages, logs, profiles or results; callers should treat the returned
string as a secret and redact it if it could otherwise be echoed.
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import warnings
from pathlib import Path

__all__ = [
    "InvalidSecretRef",
    "LegacySecretLocationWarning",
    "SecretError",
    "SecretUnavailable",
    "default_secrets_dir",
    "redact",
    "resolve",
    "secrets_dir",
    "store_default_secret",
    "store_file_secret",
    "validate_ref",
    "workspace_secrets_dir",
]

_FILE_NAME = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_.-]*(?:/[A-Za-z0-9][A-Za-z0-9_.-]*)*$"
)
_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_KEYCHAIN_NAME = re.compile(r"^[^/\s]+/[^/\s]+$")
_ACTION = (
    "use keychain:<service>/<account> (recommended), env:<VAR>, or "
    "file:<name> stored in $HOME/.dataagent/secrets"
)
_SECRETS_DIR_ENV = "DATAAGENT_SECRETS_DIR"


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


class LegacySecretLocationWarning(UserWarning):
    """A ``file:`` reference was resolved from the legacy workspace directory."""


def workspace_secrets_dir(data_root: str | Path) -> Path:
    """The legacy workspace directory (``<data_root>/secrets``)."""

    return Path(data_root) / "secrets"


def default_secrets_dir() -> Path:
    """The default ``file:`` directory, outside the workspace.

    ``DATAAGENT_SECRETS_DIR`` may point the default at an absolute directory;
    it is an operator/test override, not a per-connection setting. Relative or
    empty values are ignored so a workspace-relative override cannot silently
    move credentials back inside the workspace.
    """

    override = os.environ.get(_SECRETS_DIR_ENV, "").strip()
    if override:
        path = Path(override).expanduser()
        if path.is_absolute():
            return path
    return Path.home() / ".dataagent" / "secrets"


def secrets_dir(data_root: str | Path | None = None) -> Path:
    """Return the default external directory, or the legacy workspace one.

    ``secrets_dir()`` is the location for new ``file:`` secrets. Passing
    ``data_root`` keeps the historical ``<data_root>/secrets`` meaning for
    callers that manage an explicit workspace; that path is read for
    compatibility and warns on resolution.
    """

    if data_root is None:
        return default_secrets_dir()
    return workspace_secrets_dir(data_root)


def _is_workspace_data_root(data_root: str | Path) -> bool:
    """True when ``data_root`` is the .dataagent of an actual Mint project.

    A bare ``.dataagent`` in a temporary directory is treated as an explicit
    custom root, not as a workspace: that keeps the historical behaviour for
    tests and for CLI users who pass an arbitrary data root.
    """

    root = Path(data_root)
    if root.name != ".dataagent":
        return False
    parent = root.parent
    return (parent / "mint.toml").is_file() or (parent / ".mint").is_dir()


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


def _check_parent_dirs(base: Path, parent: Path) -> None:
    """Every directory between ``base`` and ``parent`` must be private."""

    current = parent
    while True:
        _check_private_dir(current)
        if current == base:
            return
        current = current.parent


def _write_secret(base: Path, name: str, value: str) -> None:
    base = _ensure_private_dir(base)
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


def store_default_secret(name: str, value: str) -> str:
    """Write a secret outside the workspace and return its ``file:`` reference."""

    if not isinstance(name, str) or not _FILE_NAME.fullmatch(name):
        raise InvalidSecretRef("invalid secret name", action=_ACTION)
    value = value.strip() if isinstance(value, str) else ""
    if not value:
        raise SecretUnavailable("secret value is empty")
    _write_secret(default_secrets_dir(), name, value)
    return f"file:{name}"


def store_file_secret(
    data_root: str | Path | None = None,
    name: str = "",
    value: str = "",
    *,
    scope: str = "auto",
) -> str:
    """Write ``value`` and return its ``file:`` reference.

    ``scope="default"`` writes to the external default directory. In the
    historical call shape, a ``data_root`` under a real Mint workspace (its
    parent contains ``mint.toml`` or ``.mint``) now defaults outside the
    workspace; an arbitrary/custom data root keeps ``<data_root>/secrets`` for
    compatibility. New code should omit ``data_root`` or use
    ``store_default_secret``. ``scope="workspace"`` makes the legacy choice
    explicit.
    """

    if not isinstance(name, str) or not _FILE_NAME.fullmatch(name):
        raise InvalidSecretRef("invalid secret name", action=_ACTION)
    value = value.strip() if isinstance(value, str) else ""
    if not value:
        raise SecretUnavailable("secret value is empty")
    if scope == "auto":
        scope = (
            "default"
            if data_root is None or _is_workspace_data_root(data_root)
            else "workspace"
        )
    if scope == "default":
        _write_secret(default_secrets_dir(), name, value)
    elif scope == "workspace":
        if data_root is None:
            raise InvalidSecretRef(
                "workspace scope requires a data_root", action=_ACTION
            )
        _write_secret(workspace_secrets_dir(data_root), name, value)
    else:
        raise InvalidSecretRef("unknown secret scope", action=_ACTION)
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


def _read_file(base: Path, rest: str) -> str:
    base = base.expanduser()
    if base.is_symlink():
        raise SecretUnavailable("secret directory must not be a symlink")
    try:
        resolved_base = base.resolve()
        path = (base / f"{rest}.key").resolve()
    except (OSError, RuntimeError):
        raise SecretUnavailable("secret location is unavailable") from None
    if not path.is_relative_to(resolved_base):
        raise SecretUnavailable("secret is outside the selected secrets directory")
    if not path.is_file():
        raise SecretUnavailable("secret is missing", action=_ACTION)
    _check_parent_dirs(resolved_base, path.parent)
    mode = path.stat().st_mode & 0o777
    if mode & 0o077:
        raise SecretUnavailable(
            f"secret is readable by other users (mode {mode:o})",
            action=f"chmod 600 {path}",
        )
    return path.read_text(encoding="utf-8").strip()


def _file_value(rest: str, data_root: str | Path | None) -> str:
    candidates: list[tuple[Path, bool]] = [(default_secrets_dir(), False)]
    if data_root is not None:
        legacy = workspace_secrets_dir(data_root)
        if legacy != candidates[0][0]:
            candidates.append((legacy, True))
    for base, legacy in candidates:
        # Only an existing *file* is considered; a missing default falls
        # through to the legacy directory. An existing but unsafe file fails
        # closed instead of silently trying the next location.
        try:
            path = (base / f"{rest}.key").resolve()
            exists = path.is_file()
        except (OSError, RuntimeError):
            exists = False
        if not exists:
            continue
        value = _read_file(base, rest)
        if legacy:
            warnings.warn(
                "credential file is stored in the legacy workspace secrets "
                f"directory ({base}); move it to {default_secrets_dir()} or use "
                "keychain:<service>/<account>",
                LegacySecretLocationWarning,
                stacklevel=3,
            )
        return value
    raise SecretUnavailable("secret is missing", action=_ACTION)


def resolve(ref: str, data_root: str | Path | None = None) -> str:
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
