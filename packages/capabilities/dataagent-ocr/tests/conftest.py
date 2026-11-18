from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from dataagent_ocr.probe import PROBE_LINES


class FakeOpenAI:
    """Minimal OpenAI-compatible /v1/chat/completions server for tests."""

    def __init__(self):
        self.api_key = "sk-test-123"
        self.lines = list(PROBE_LINES)
        self.mode = "blocks"  # blocks | text | garbage | fenced
        self.reject_logprobs = False
        self.fail_statuses: list[int] = []
        self.model_reported = "qwen-vl-ocr-2026-01"
        self.requests: list[dict] = []
        self.headers: list[dict] = []
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                return

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                server.requests.append(body)
                server.headers.append(dict(self.headers))
                if self.path != "/v1/chat/completions":
                    return self._send(404, {"error": {"message": "not found"}})
                if self.headers.get("Authorization") != f"Bearer {server.api_key}":
                    return self._send(401, {"error": {"message": "invalid api key"}})
                if server.fail_statuses:
                    return self._send(server.fail_statuses.pop(0), {"error": {"message": "busy"}})
                if server.reject_logprobs and body.get("logprobs"):
                    return self._send(400, {"error": {"message": "logprobs is not supported for this model"}})
                content, logprobs = server.render(body)
                choice = {"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}
                if body.get("logprobs") and logprobs is not None:
                    choice["logprobs"] = {"content": logprobs}
                return self._send(
                    200,
                    {"id": "x", "model": server.model_reported, "system_fingerprint": "fp_1", "choices": [choice]},
                )

            def _send(self, status, payload):
                data = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.httpd.server_address[1]}/v1"

    def render(self, body):
        if self.mode == "garbage":
            return "Sorry, I cannot read that image.", None
        if self.mode == "text":
            content = "\n".join(self.lines)
        else:
            blocks = [{"text": line, "bbox": [10, 10 + 60 * i, 900, 60 + 60 * i]} for i, line in enumerate(self.lines)]
            content = json.dumps({"blocks": blocks}, ensure_ascii=False)
            if self.mode == "fenced":
                content = "```json\n" + content + "\n```"
        # Tokenize into 4-char pieces; low confidence on the second line.
        tokens = []
        second = self.lines[1] if len(self.lines) > 1 else None
        start = content.find(second) if second else -1
        for i in range(0, len(content), 4):
            piece = content[i : i + 4]
            low = start >= 0 and start <= i < start + len(second)
            tokens.append({"token": piece, "logprob": -1.2 if low else -0.01})
        return content, tokens

    def close(self):
        self.httpd.shutdown()


@pytest.fixture
def fake_openai():
    server = FakeOpenAI()
    yield server
    server.close()


@pytest.fixture
def home(tmp_path: Path, monkeypatch) -> Path:
    """An isolated HOME so default file: secrets never touch the real one."""

    path = tmp_path / "home"
    path.mkdir()
    monkeypatch.setenv("HOME", str(path))
    monkeypatch.delenv("DATAAGENT_SECRETS_DIR", raising=False)
    return path


@pytest.fixture
def data_root(tmp_path: Path, home: Path, monkeypatch) -> Path:
    root = tmp_path / ".dataagent"
    monkeypatch.setenv("DATAAGENT_DATA_ROOT", str(root))
    monkeypatch.delenv("DATAAGENT_ENFORCEMENT_MODE", raising=False)
    return root
