from __future__ import annotations

import json
import math

import pytest

from dataagent_ocr.errors import ConfigError, CredentialsError, ProviderUnavailable
from dataagent_ocr.probe import PROBE_LINES, render_probe
from dataagent_ocr.profiles import OcrProfile, OpenAICompatConfig
from dataagent_ocr.providers.openai_compat import OpenAICompatProvider, block_confidences, parse_blocks


def _profile(base_url: str, **overrides) -> OcrProfile:
    cfg = OpenAICompatConfig(base_url=base_url, model="qwen-vl-ocr", deployment="vendor_api", **overrides)
    return OcrProfile(profile_id="vl", revision=1, kind="openai_compat", openai_compat=cfg)


def _provider(server, **overrides):
    return OpenAICompatProvider(_profile(server.base_url, **overrides), server.api_key, sleep=lambda _s: None)


def test_blocks_bbox_and_logprob_confidence(fake_openai):
    result = _provider(fake_openai).recognize_page(render_probe().image)
    assert [b.text for b in result.blocks] == PROBE_LINES
    assert result.confidence_source == "logprobs"
    confidences = [b.confidence for b in result.blocks]
    assert confidences[1] < 0.5 < confidences[0]  # the fake server lowers line 2
    assert all(len(b.bbox) == 4 for b in result.blocks)
    assert result.reported_model == "qwen-vl-ocr-2026-01"
    request = fake_openai.requests[-1]
    assert request["temperature"] == 0 and request["response_format"] == {"type": "json_object"}
    image_part = request["messages"][1]["content"][1]
    assert image_part["image_url"]["url"].startswith("data:image/png;base64,")
    assert "Image size: 1100x" in request["messages"][1]["content"][0]["text"]


def test_logprobs_rejected_falls_back_without_confidence(fake_openai):
    fake_openai.reject_logprobs = True
    result = _provider(fake_openai).recognize_page(render_probe().image)
    assert [b.text for b in result.blocks] == PROBE_LINES
    assert result.confidence_source == "none"
    assert all(b.confidence is None for b in result.blocks)
    assert "logprobs" not in fake_openai.requests[-1]


def test_text_mode(fake_openai):
    fake_openai.mode = "text"
    result = _provider(fake_openai, json_mode=False).recognize_page(render_probe().image)
    assert [b.text for b in result.blocks] == PROBE_LINES
    assert "response_format" not in fake_openai.requests[-1]
    assert result.output_format == "text" and not result.format_error


def test_fenced_json_is_accepted(fake_openai):
    fake_openai.mode = "fenced"
    result = _provider(fake_openai).recognize_page(render_probe().image)
    assert [b.text for b in result.blocks] == PROBE_LINES and not result.format_error


def test_garbage_output_is_a_format_error(fake_openai):
    fake_openai.mode = "garbage"
    result = _provider(fake_openai).recognize_page(render_probe().image)
    assert result.format_error


def test_wrong_key_is_credentials_error_and_key_not_leaked(fake_openai):
    provider = OpenAICompatProvider(_profile(fake_openai.base_url), "sk-wrong-SECRET", sleep=lambda _s: None)
    with pytest.raises(CredentialsError) as info:
        provider.recognize_page(render_probe().image)
    assert "sk-wrong-SECRET" not in json.dumps(info.value.to_dict())
    assert len(fake_openai.requests) == 1  # no retry on auth failure


def test_transient_errors_retry_then_succeed(fake_openai):
    fake_openai.fail_statuses = [503, 429]
    result = _provider(fake_openai).recognize_page(render_probe().image)
    assert len(result.blocks) == 4 and len(fake_openai.requests) == 3


def test_persistent_errors_are_unavailable(fake_openai):
    fake_openai.fail_statuses = [503, 503, 503]
    with pytest.raises(ProviderUnavailable):
        _provider(fake_openai).recognize_page(render_probe().image)


def test_wrong_path_is_config_error(fake_openai):
    provider = OpenAICompatProvider(_profile(fake_openai.base_url.removesuffix("/v1")), fake_openai.api_key)
    with pytest.raises(ConfigError):
        provider.recognize_page(render_probe().image)


def test_bbox_outside_image_is_dropped():
    content = json.dumps({"blocks": [{"text": "a", "bbox": [0, 0, 5000, 10]}, {"text": "b", "bbox": [1, 1, 2, 2]}]})
    pairs, error = parse_blocks(content, (100, 100))
    assert pairs == [("a", []), ("b", [1.0, 1.0, 2.0, 2.0])] and not error


def test_confidence_needs_token_reconstruction():
    assert block_confidences("abc", ["abc"], [{"token": "ab", "logprob": 0.0}]) == [None]
    assert block_confidences("abc", ["abc"], [{"token": "abc", "logprob": 0.0}]) == [1.0]


def test_vllm_trailing_stop_token_still_maps_confidence():
    """vLLM appends the stop token (e.g. <|im_end|>) to logprobs.content
    with its literal text as ``token``; the mapping must survive it."""

    content = json.dumps({"blocks": [{"text": "INVOICE NO. 2026-1106-0042", "bbox": [1, 2, 3, 4]}]})
    pieces = [content[i : i + 4] for i in range(0, len(content), 4)]
    logprobs = [{"token": piece, "logprob": -0.02, "bytes": [ord(c) for c in piece], "top_logprobs": []}
                for piece in pieces]
    logprobs.append({"token": "<|im_end|>", "logprob": 0.0,
                     "bytes": [60, 124, 105, 109, 95, 101, 110, 100, 124, 62], "top_logprobs": []})
    assert block_confidences(content, ["INVOICE NO. 2026-1106-0042"], logprobs) == [
        pytest.approx(math.exp(-0.02), abs=5e-5)
    ]


def test_trailing_stop_token_does_not_mask_a_real_mismatch():
    content = '{"blocks": [{"text": "AB"}]}'
    logprobs = [{"token": "XY", "logprob": -0.01}, {"token": "<|im_end|>", "logprob": 0.0}]
    assert block_confidences(content, ["AB"], logprobs) == [None]


def test_base_url_rejects_embedded_credentials():
    with pytest.raises(ValueError):
        OpenAICompatConfig(base_url="https://user:pw@host/v1", model="m", deployment="vendor_api")
