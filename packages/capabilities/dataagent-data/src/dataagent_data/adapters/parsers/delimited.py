"""CSV/TSV parsing with encoding and delimiter detection."""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

from dataagent_data.adapters.parsers.excel import dedupe_names
from dataagent_runtime.errors import invalid_input

ENCODINGS = ("utf-8-sig", "utf-8", "gb18030", "latin-1")


def detect_text(payload: bytes, encoding: str | None) -> tuple[str, str, list[str]]:
    candidates = [encoding] if encoding else list(ENCODINGS)
    problems: list[str] = []
    for candidate in candidates:
        if not candidate:
            continue
        try:
            return payload.decode(candidate), candidate, problems
        except UnicodeDecodeError as exc:
            problems.append(f"{candidate}: {exc.reason} at byte {exc.start}")
    raise invalid_input("cannot decode file with tried encodings: " + ", ".join(problems))


def detect_delimiter(text: str, delimiter: str | None, path: str) -> str:
    if delimiter:
        if len(delimiter) != 1:
            raise invalid_input("delimiter must be a single character")
        return delimiter
    sample = "\n".join(text.splitlines()[:20])
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        return "\t" if path.lower().endswith((".tsv", ".tab")) else ","


def parse_delimited(
    payload: bytes,
    *,
    filename: str,
    encoding: str | None = None,
    delimiter: str | None = None,
    has_header: bool = True,
) -> tuple[list[str], list[list[Any]], list[dict[str, Any]], str, str]:
    text, used_encoding, _ = detect_text(payload, encoding)
    used_delimiter = detect_delimiter(text, delimiter, filename)
    reader = csv.reader(io.StringIO(text), delimiter=used_delimiter)
    raw_rows = [row for row in reader]
    if not raw_rows:
        raise invalid_input("delimited file has no rows")
    width = len(raw_rows[0]) if has_header else max(len(row) for row in raw_rows)
    bad_rows: list[dict[str, Any]] = []
    rows: list[list[Any]] = []
    for index, row in enumerate(raw_rows, start=1):
        if len(row) != width:
            # A row whose width does not match the header is quarantined: it is
            # reported with its original cells and never padded/truncated into
            # the table (06 §14 item 6).
            bad_rows.append(
                {
                    "row": index,
                    "expected_columns": width,
                    "actual_columns": len(row),
                    "reason": "column_count_mismatch",
                    "cells": list(row),
                }
            )
            continue
        rows.append([cell if cell != "" else None for cell in row])
    if has_header:
        header = [str(cell) if cell is not None else "" for cell in rows[0]]
        data_rows = rows[1:]
    else:
        header = [f"column_{i + 1}" for i in range(width)]
        data_rows = rows
    return dedupe_names(header), data_rows, bad_rows, used_encoding, used_delimiter
