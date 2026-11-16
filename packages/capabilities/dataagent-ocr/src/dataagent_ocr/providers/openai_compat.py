"""OCR over an OpenAI-compatible ``/chat/completions`` endpoint.

Works with any server that accepts ``image_url`` content parts with a
``data:`` URL (OpenAI, vLLM / SGLang deployments of VL models, vendor
"compatible mode" endpoints). Only the standard library is used for HTTP.

Output contract asked of the model (``ocr-blocks-v1``)::

    {"blocks": [{"text": "...", "bbox": [x0, y0, x1, y1] | null}, ...]}

one block per printed line, reading order, pixel coordinates of the submitted
image. ``json_mode=False`` asks for plain text, one line per line.

Confidence: when the server returns token ``logprobs`` each block gets
``exp(mean logprob)`` over the tokens that produced its text; otherwise
``confidence`` stays ``None`` (``confidence_source = "none"``).
"""

from __future__ import annotations

import base64
import io
import json
import math
import re
import socket
import time
import urllib.error
import urllib.request
from typing import Any, Callable
from urllib.parse import urlparse

from dataagent_ocr.errors import ConfigError, CredentialsError, ProviderUnavailable
from dataagent_ocr.profiles import OcrProfile
from dataagent_ocr.secrets import redact
from dataagent_ocr.types import OcrBlock, RecognizeResult

PROMPTS: dict[str, dict[str, str]] = {
    "ocr-blocks-v1": {
        "system": (
            "You are an OCR engine. Transcribe every piece of printed or handwritten text in the "
            "image exactly as it appears: keep original language, digits, punctuation, units and "
            "currency symbols. Do not translate, correct, summarize, explain or add any text. "
            "Return only JSON of the form "
            '{"blocks":[{"text":"<one text line>","bbox":[x0,y0,x1,y1]}]} '
            "with one block per text line in reading order. bbox uses pixel coordinates of the "
            "given image (origin top-left); use null when unsure. Return {\"blocks\":[]} when the "
            "image has no text."
        ),
        "text_system": (
            "You are an OCR engine. Transcribe every piece of text in the image exactly as it "
            "appears, one output line per text line, in reading order. Do not translate, correct, "
            "summarize, explain or add any text. Output nothing else."
        ),
    }
}

_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.S)


def _image_size(image_bytes: bytes) -> tuple[int, int] | None:
    try:
        from PIL import Image

        with Image.open(io.BytesIO(image_bytes)) as image:
            return image.size
    except Exception:  # noqa: BLE001 - size is only a prompt hint
        return None


def _media_type(image_bytes: bytes) -> str:
    if image_bytes.startswith(b"\x89PNG"):
        return "image/png"
    if image_bytes[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if image_bytes[:4] in (b"RIFF",) and image_bytes[8:12] == b"WEBP":
        return "image/webp"
    return "image/png"


def _valid_bbox(value: Any, size: tuple[int, int] | None) -> list[float]:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return []
    try:
        x0, y0, x1, y1 = (float(v) for v in value)
    except (TypeError, ValueError):
        return []
    if not all(math.isfinite(v) for v in (x0, y0, x1, y1)) or x1 <= x0 or y1 <= y0 or x0 < 0 or y0 < 0:
        return []
    if size is not None:
        width, height = size
        # Allow 2% slack for rounding by the model; anything beyond is not a box of this image.
        if x1 > width * 1.02 or y1 > height * 1.02:
            return []
        x1, y1 = min(x1, float(width)), min(y1, float(height))
    return [round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)]


def parse_blocks(content: str, size: tuple[int, int] | None) -> tuple[list[tuple[str, list[float]]], bool]:
    """Parse model output into ``(text, bbox)`` pairs; second item flags a format error."""

    text = content.strip()
    fenced = _FENCE.match(text)
    if fenced:
        text = fenced.group(1)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        try:
            data = json.loads(text[start : end + 1]) if start >= 0 and end > start else None
        except json.JSONDecodeError:
            data = None
    if isinstance(data, dict) and isinstance(data.get("blocks"), list):
        out = []
        for item in data["blocks"]:
            if isinstance(item, dict) and isinstance(item.get("text"), str) and item["text"].strip():
                out.append((item["text"], _valid_bbox(item.get("bbox"), size)))
            elif isinstance(item, str) and item.strip():
                out.append((item, []))
        return out, False
    # Not the requested JSON: keep the transcription as lines, flag the format error.
    lines = [line for line in content.splitlines() if line.strip() and not line.strip().startswith("```")]
    return [(line, []) for line in lines], True


def parse_text(content: str) -> list[tuple[str, list[float]]]:
    return [(line, []) for line in content.splitlines() if line.strip()]


def block_confidences(content: str, texts: list[str], logprobs: list[dict[str, Any]] | None) -> list[float | None]:
    """Map token logprobs onto block texts by locating each text in ``content``."""

    if not logprobs:
        return [None] * len(texts)
    spans: list[tuple[int, int, float]] = []
    cursor = 0
    for token in logprobs:
        piece = token.get("token")
        lp = token.get("logprob")
        if not isinstance(piece, str) or not isinstance(lp, (int, float)):
            return [None] * len(texts)
        spans.append((cursor, cursor + len(piece), float(lp)))
        cursor += len(piece)
    if cursor != len(content):
        # Tokens do not reconstruct the content (server-side post-processing); no mapping.
        return [None] * len(texts)
    out: list[float | None] = []
    search_from = 0
    for text in texts:
        found = -1
        needle = text
        for candidate in (text, json.dumps(text, ensure_ascii=False)[1:-1], json.dumps(text)[1:-1]):
            found = content.find(candidate, search_from)
            if found >= 0:
                needle = candidate
                break
        if found < 0:
            out.append(None)
            continue
        end = found + len(needle)
        values = [lp for s, e, lp in spans if s < end and e > found]
        search_from = end
        out.append(round(math.exp(sum(values) / len(values)), 4) if values else None)
    return out


Transport = Callable[[str, dict[str, str], bytes, float], tuple[int, bytes]]


def urllib_transport(url: str, headers: dict[str, str], body: bytes, timeout: float) -> tuple[int, bytes]:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - user-configured endpoint
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read() if exc.fp else b""


class OpenAICompatProvider:
    def __init__(
        self,
        profile: OcrProfile,
        api_key: str | None,
        *,
        transport: Transport = urllib_transport,
        sleep: Callable[[float], None] = time.sleep,
    ):
        if profile.openai_compat is None:
            raise ConfigError("profile is not an openai_compat profile")
        self.profile = profile
        self.config = profile.openai_compat
        self._api_key = api_key
        self._transport = transport
        self._sleep = sleep
        self._logprobs = self.config.logprobs != "off"
        self.engine_ref = f"openai_compat:{self.config.model}"
        self.engine_version = f"{profile.ref}:{profile.config_digest()[7:19]}"
        self.remote = profile.remote
        self.host = urlparse(self.config.base_url).netloc

    def destination(self) -> dict[str, str]:
        return {"model_ref": self.engine_ref, "deployment": self.config.deployment}

    def _request_body(self, image_bytes: bytes, lang: str | None, size: tuple[int, int] | None) -> dict[str, Any]:
        prompts = PROMPTS.get(self.config.prompt_version)
        if prompts is None:
            raise ConfigError(f"unknown prompt_version {self.config.prompt_version!r}")
        hint = f"Image size: {size[0]}x{size[1]} pixels. " if size else ""
        hint += f"Language hint: {lang or 'auto'}."
        data_url = f"data:{_media_type(image_bytes)};base64,{base64.b64encode(image_bytes).decode('ascii')}"
        body: dict[str, Any] = {
            "model": self.config.model,
            "temperature": 0,
            "max_tokens": self.config.max_tokens,
            "messages": [
                {
                    "role": "system",
                    "content": prompts["system"] if self.config.json_mode else prompts["text_system"],
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": hint},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
        }
        if self.config.json_mode:
            body["response_format"] = {"type": "json_object"}
        if self._logprobs:
            body["logprobs"] = True
        return body

    def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.config.base_url}/chat/completions"
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        attempts = self.config.max_retries + 1
        last: str = ""
        for attempt in range(attempts):
            try:
                status, raw = self._transport(
                    url, headers, json.dumps(body).encode("utf-8"), self.config.timeout_s
                )
            except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, OSError) as exc:
                last = f"{type(exc).__name__}: {redact(str(exc), self._api_key)}"
                status, raw = 0, b""
            if status == 200:
                try:
                    return json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise ProviderUnavailable(f"{self.host} returned a non-JSON response") from exc
            detail = redact(raw[:300].decode("utf-8", "replace"), self._api_key)
            if status in (401, 403):
                raise CredentialsError(
                    f"{self.host} rejected the api key (HTTP {status})",
                    action="ask the user for a valid api key and run set-key, then verify",
                )
            if status == 400 and self._logprobs and "logprob" in detail.lower() and self.config.logprobs == "auto":
                self._logprobs = False
                body = {k: v for k, v in body.items() if k != "logprobs"}
                continue
            if status == 400 and "response_format" in body and "response_format" in detail.lower():
                raise ConfigError(
                    f"{self.host} does not accept response_format=json_object: {detail}",
                    action="configure the profile with --no-json-mode",
                )
            if status in (400, 404, 422):
                raise ConfigError(
                    f"{self.host} rejected the request (HTTP {status}): {detail}",
                    action="check base_url (it usually ends with /v1) and the model name",
                )
            if status:
                last = f"HTTP {status}: {detail}"
            if attempt + 1 < attempts:
                self._sleep(min(8.0, 0.5 * 2**attempt))
        raise ProviderUnavailable(f"{self.host} unavailable after {attempts} attempt(s): {last}")

    def recognize_page(self, image_bytes: bytes, *, lang: str | None = None) -> RecognizeResult:
        size = _image_size(image_bytes)
        started = time.monotonic()
        payload = self._post(self._request_body(image_bytes, lang, size))
        latency = int((time.monotonic() - started) * 1000)
        try:
            choice = payload["choices"][0]
            content = choice["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderUnavailable(f"{self.host} returned no choices") from exc
        if isinstance(content, list):  # some servers return content parts
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        if self.config.json_mode:
            pairs, format_error = parse_blocks(content, size)
            output_format = "blocks_json"
        else:
            pairs, format_error = parse_text(content), False
            output_format = "text"
        logprobs = None
        if isinstance(choice.get("logprobs"), dict):
            logprobs = choice["logprobs"].get("content")
        confidences = block_confidences(content, [t for t, _ in pairs], logprobs)
        blocks = [OcrBlock(text=t, bbox=b, confidence=c) for (t, b), c in zip(pairs, confidences)]
        source = "logprobs" if any(c is not None for c in confidences) else "none"
        return RecognizeResult(
            blocks=blocks,
            confidence_source=source,
            latency_ms=latency,
            reported_model=payload.get("model"),
            system_fingerprint=payload.get("system_fingerprint"),
            output_format=output_format,
            format_error=format_error,
        )

    def close(self) -> None:
        return None
