"""Local content-addressed store with atomic writes (shared with 06 §6)."""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Callable, Iterator

_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


def canonical_bytes(data: bytes | str | dict[str, Any]) -> bytes:
    if isinstance(data, bytes):
        return data
    if isinstance(data, str):
        return data.encode("utf-8")
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def digest_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


class LocalContentStore:
    def __init__(self, root: str | os.PathLike[str]):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        # Optional read hook (r38 F3): fired on every ``get`` with the
        # content digest. The sample vault wires it to the gold-exposure
        # ledger so that *any* official read path — governance scanning,
        # egress checks, data-layer loads, CLI — records an exposure when
        # the bytes read are a registered gold expectation. Only the
        # acceptance evaluator's own trusted read suspends it.
        self.read_hook: Callable[[str], None] | None = None
        self._hook_suspended = 0

    @contextlib.contextmanager
    def suspend_read_hook(self) -> Iterator[None]:
        """Suspend the read hook for a trusted read (DA11.5.5's own)."""

        self._hook_suspended += 1
        try:
            yield
        finally:
            self._hook_suspended -= 1

    def _path(self, digest: str) -> Path:
        if not _DIGEST.match(digest):
            raise ValueError(f"invalid content digest: {digest!r}")
        hex_part = digest.split(":", 1)[1]
        return self.root / hex_part[:2] / hex_part

    def put(
        self, data: bytes | str | dict[str, Any], *, media_type: str = "application/json"
    ) -> str:
        payload = canonical_bytes(data)
        digest = digest_bytes(payload)
        path = self._path(digest)
        if path.exists():
            return digest
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        return digest

    def get(self, digest: str) -> bytes:
        path = self._path(digest)
        if not path.exists():
            raise FileNotFoundError(f"content not found: {digest}")
        payload = path.read_bytes()
        if self.read_hook is not None and not self._hook_suspended:
            self.read_hook(digest)
        return payload

    def get_json(self, digest: str) -> Any:
        return json.loads(self.get(digest))

    def get_text(self, digest: str) -> str:
        return self.get(digest).decode("utf-8")

    def exists(self, digest: str) -> bool:
        return bool(_DIGEST.match(digest)) and self._path(digest).exists()
