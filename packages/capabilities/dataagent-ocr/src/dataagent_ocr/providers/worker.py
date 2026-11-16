"""Client for OCR workers that run in their own process and environment.

Worker protocol (JSON lines over stdin/stdout, one request in flight):

    -> {"id": 1, "op": "hello"}
    <- {"id": 1, "engine": "paddleocr", "engine_version": "3.x.y"}
    -> {"id": 2, "op": "recognize", "image_b64": "...", "lang": "ch"}
    <- {"id": 2, "blocks": [{"text": "...", "bbox": [x0,y0,x1,y1], "confidence": 0.97}]}
    <- {"id": n, "error": {"code": "...", "message": "..."}}

Workers write logs to stderr only. Dependency-heavy engines (PaddleOCR,
EasyOCR, Tesseract bindings) run this way so their packages never enter the
DataAgent environment.
"""

from __future__ import annotations

import base64
import json
import os
import selectors
import subprocess
import time
from pathlib import Path

from dataagent_ocr.errors import ConfigError, EngineMissing, ProviderUnavailable
from dataagent_ocr.types import OcrBlock, RecognizeResult


class WorkerClient:
    def __init__(self, argv: list[str], *, cwd: Path | None = None, timeout_s: float = 300.0, startup_timeout_s: float = 600.0):
        self.argv = argv
        self.cwd = cwd
        self.timeout_s = timeout_s
        self.startup_timeout_s = startup_timeout_s
        self._proc: subprocess.Popen | None = None
        self._next = 0
        self._buf = b""
        self.engine: str | None = None
        self.engine_version: str | None = None

    def _start(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            return
        env = {k: v for k, v in os.environ.items() if k in {"PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "SYSTEMROOT"}}
        env["PYTHONUNBUFFERED"] = "1"
        try:
            self._proc = subprocess.Popen(
                self.argv,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                cwd=self.cwd,
                env=env,
                text=True,
                bufsize=1,
            )
            self._buf = b""
        except FileNotFoundError as exc:
            raise EngineMissing(
                f"OCR worker executable not found: {self.argv[0]}",
                action="install the engine (engine plan / engine install) or fix the command",
            ) from exc
        reply = self._call({"op": "hello"}, timeout=self.startup_timeout_s)
        self.engine = str(reply.get("engine") or "unknown")
        self.engine_version = str(reply.get("engine_version") or "unknown")

    def _call(self, request: dict, *, timeout: float) -> dict:
        assert self._proc is not None and self._proc.stdin and self._proc.stdout
        self._next += 1
        request = {"id": self._next, **request}
        try:
            self._proc.stdin.write(json.dumps(request) + "\n")
            self._proc.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            self.close()
            raise ProviderUnavailable(f"OCR worker exited: {type(exc).__name__}") from exc
        deadline = time.monotonic() + timeout
        while True:
            line = self._readline(deadline, timeout)
            try:
                reply = json.loads(line)
            except json.JSONDecodeError:
                continue  # stray stdout from the engine; the protocol line follows
            if isinstance(reply, dict) and reply.get("id") == request["id"]:
                break
        if "error" in reply:
            error = reply["error"] or {}
            code = error.get("code", "")
            message = str(error.get("message", "worker error"))[:500]
            if code == "engine_missing":
                raise EngineMissing(message, action="install the engine (engine plan / engine install)")
            if code == "bad_request":
                raise ConfigError(message)
            raise ProviderUnavailable(message)
        return reply

    def _readline(self, deadline: float, timeout: float) -> str:
        """Read one line from the worker's stdout fd without a hidden buffer."""

        assert self._proc is not None and self._proc.stdout
        fd = self._proc.stdout.fileno()
        while b"\n" not in self._buf:
            remaining = deadline - time.monotonic()
            selector = selectors.DefaultSelector()
            selector.register(fd, selectors.EVENT_READ)
            try:
                ready = remaining > 0 and selector.select(timeout=remaining)
            finally:
                selector.close()
            if not ready:
                self.close()
                raise ProviderUnavailable(f"OCR worker did not answer within {timeout:.0f}s")
            chunk = os.read(fd, 1 << 16)
            if not chunk:
                self.close()
                raise ProviderUnavailable("OCR worker exited without a reply")
            self._buf += chunk
        line, _, self._buf = self._buf.partition(b"\n")
        return line.decode("utf-8", "replace")

    def recognize(self, image_bytes: bytes, lang: str | None) -> RecognizeResult:
        self._start()
        started = time.monotonic()
        reply = self._call(
            {"op": "recognize", "image_b64": base64.b64encode(image_bytes).decode("ascii"), "lang": lang},
            timeout=self.timeout_s,
        )
        blocks = []
        for item in reply.get("blocks") or []:
            text = item.get("text")
            if not isinstance(text, str) or not text.strip():
                continue
            bbox = item.get("bbox") or []
            conf = item.get("confidence")
            blocks.append(
                OcrBlock(
                    text=text,
                    bbox=[float(v) for v in bbox] if isinstance(bbox, list) and len(bbox) == 4 else [],
                    confidence=float(conf) if isinstance(conf, (int, float)) else None,
                )
            )
        return RecognizeResult(
            blocks=blocks,
            confidence_source="engine" if any(b.confidence is not None for b in blocks) else "none",
            latency_ms=int((time.monotonic() - started) * 1000),
            output_format="engine",
        )

    def close(self) -> None:
        proc, self._proc = self._proc, None
        if proc is None:
            return
        try:
            if proc.stdin:
                proc.stdin.close()
            proc.wait(timeout=5)
        except Exception:  # noqa: BLE001 - best effort shutdown
            proc.kill()


class WorkerProvider:
    """Adapter from :class:`WorkerClient` to the provider protocol."""

    remote = False

    def __init__(self, client: WorkerClient, *, engine_ref: str, version_tag: str, lang: str | None = None):
        self.client = client
        self.engine_ref = engine_ref
        self._version_tag = version_tag
        self.default_lang = lang

    @property
    def engine_version(self) -> str:
        if self.client.engine_version:
            return f"{self.client.engine_version}|{self._version_tag}"
        return self._version_tag

    def recognize_page(self, image_bytes: bytes, *, lang: str | None = None) -> RecognizeResult:
        return self.client.recognize(image_bytes, lang or self.default_lang)

    def close(self) -> None:
        self.client.close()
