from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from dataagent_contracts.core import CallContext, FileRef
from dataagent_data.runtime import Runtime, create as create_runtime


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    path = tmp_path / "workspace"
    path.mkdir()
    return path


@pytest.fixture()
def runtime(workspace: Path, tmp_path: Path) -> Runtime:
    return create_runtime(workspace_root=workspace, data_root=tmp_path / "data")


@pytest.fixture()
def ctx() -> CallContext:
    return CallContext(
        request_id="req:test",
        scope_ref="tenant:test/project:p1",
        authorization_ref="policy:test-read",
    )


def write_file(workspace: Path, name: str, payload: bytes) -> str:
    path = workspace / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return name


def file_ref(workspace: Path, name: str, **kwargs) -> FileRef:
    payload = (workspace / name).read_bytes()
    digest = "sha256:" + hashlib.sha256(payload).hexdigest()
    return FileRef(
        id=kwargs.pop("id", f"file:{digest[7:23]}"),
        kind="file",
        scope_ref=kwargs.pop("scope_ref", "tenant:test/project:p1"),
        revision=kwargs.pop("revision", digest),
        resolver="workspace",
        locator=name,
        digest=digest,
        media_type=kwargs.pop("media_type", "application/octet-stream"),
        filename=kwargs.pop("filename", Path(name).name),
        size_bytes=len(payload),
        content_digest=kwargs.pop("content_digest", digest),
        **kwargs,
    )


def build_xlsx(path: Path, sheets: dict[str, list[list[object]]], *, date1904: bool = False) -> None:
    from openpyxl import Workbook
    from openpyxl.utils.datetime import CALENDAR_MAC_1904

    wb = Workbook()
    if date1904:
        wb.epoch = CALENDAR_MAC_1904
    first = True
    for name, rows in sheets.items():
        ws = wb.active if first else wb.create_sheet()
        ws.title = name
        first = False
        for row in rows:
            ws.append(row)
    wb.save(path)


def build_pdf(path: Path, lines: list[str]) -> None:
    build_pdf_pages(path, [lines])


def build_pdf_pages(path: Path, pages: list[list[str]]) -> None:
    """Write a text PDF with one page per entry (used for page-number tests)."""

    def stream(lines: list[str]) -> str:
        return "BT /F1 12 Tf 72 760 Td 14 TL\n" + "\n".join(
            f"({line.replace('(', chr(92) + '(').replace(')', chr(92) + ')')}) Tj T*"
            for line in lines
        ) + "\nET"

    count = len(pages)
    kids = " ".join(f"{4 + 2 * index} 0 R" for index in range(count))
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {count} >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    for index, lines in enumerate(pages):
        content = stream(lines)
        objects.append(
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {5 + 2 * index} 0 R >>"
        )
        objects.append(
            f"<< /Length {len(content.encode())} >>\nstream\n{content}\nendstream"
        )
    out = b"%PDF-1.4\n"
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n{obj}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets[1:]:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n"
    ).encode()
    path.write_bytes(out)


def call(operation: str, payload: dict, ctx: CallContext, runtime):
    from dataagent_data.invoke import invoke

    return invoke(operation, payload, ctx, runtime=runtime)
