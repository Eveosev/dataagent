"""Verification fixtures and scoring.

The built-in probe is a synthetic image rendered locally (no user data):
uppercase words, an invoice number, a date and an amount. A user sample with
its expected transcription can be added; it is the only way to check the
user's own scenario (language, layout, print quality) and is recommended.

Score = ``difflib`` ratio of the normalized transcription against the
expected text. ``digits_ok`` requires every digit group of the expected
text to appear, in order, in the transcription — amounts and dates must be
exact regardless of the overall ratio.
"""

from __future__ import annotations

import difflib
import io
import re
import unicodedata
from dataclasses import dataclass

PROBE_LINES = [
    "DATAAGENT OCR PROBE",
    "INVOICE NO. 2026-1106-0042",
    "TOTAL AMOUNT 12,345.67",
    "DATE 2026-11-06",
]


@dataclass
class Fixture:
    fixture: str
    image: bytes
    expected: str


def render_probe() -> Fixture:
    from PIL import Image, ImageDraw, ImageFont

    try:
        font = ImageFont.load_default(size=40)
    except TypeError:  # Pillow < 10.1 has no sized default font
        font = ImageFont.load_default()
    width, line_h, pad = 1100, 64, 40
    image = Image.new("RGB", (width, pad * 2 + line_h * len(PROBE_LINES)), "white")
    draw = ImageDraw.Draw(image)
    for index, line in enumerate(PROBE_LINES):
        draw.text((pad, pad + index * line_h), line, fill="black", font=font)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=False)
    return Fixture(fixture="builtin:probe-v1", image=buffer.getvalue(), expected="\n".join(PROBE_LINES))


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).upper()
    return re.sub(r"\s+", " ", text).strip()


def digit_groups(text: str) -> list[str]:
    return re.findall(r"\d+", unicodedata.normalize("NFKC", text))


def digits_in_order(expected: str, actual: str) -> bool:
    remaining = iter(digit_groups(actual))
    return all(any(group == got for got in remaining) for group in digit_groups(expected))


def score(expected: str, actual: str) -> tuple[float, bool]:
    ratio = difflib.SequenceMatcher(None, normalize(expected), normalize(actual), autojunk=False).ratio()
    return round(ratio, 4), digits_in_order(expected, actual)
