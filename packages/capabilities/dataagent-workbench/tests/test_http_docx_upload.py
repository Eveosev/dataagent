"""Workbench upload accepts Word documents and the data layer profiles them."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from dataagent_workbench.adapters.layer_client import LayerClient
from dataagent_workbench.bootstrap import Workbench
from dataagent_workbench.interfaces.http_api import create_app


CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""

RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""

DOCUMENT = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>差旅费用报销规则</w:t></w:r></w:p>
    <w:p><w:r><w:t>第一条 出差住宿标准按城市等级执行。</w:t></w:r></w:p>
    <w:tbl>
      <w:tblPr/>
      <w:tblGrid><w:gridCol/><w:gridCol/></w:tblGrid>
      <w:tr><w:tc><w:p><w:r><w:t>城市</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>标准</w:t></w:r></w:p></w:tc></w:tr>
      <w:tr><w:tc><w:p><w:r><w:t>一线</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>600</w:t></w:r></w:p></w:tc></w:tr>
    </w:tbl>
    <w:sectPr/>
  </w:body>
</w:document>"""


def _docx_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", CONTENT_TYPES)
        archive.writestr("_rels/.rels", RELS)
        archive.writestr("word/document.xml", DOCUMENT)
    return buffer.getvalue()


def _client(tmp_path: Path) -> tuple[TestClient, dict[str, str]]:
    root = Path(__file__).resolve().parents[2]
    wb = Workbench(tmp_path, layer_client=LayerClient(root / "dataagent-data"))
    client = TestClient(create_app(wb))
    return client, {"x-dataagent-token": wb.token}


def test_upload_accepts_docx_and_intake_profiles_its_text(tmp_path):
    client, headers = _client(tmp_path)
    uploaded = client.post(
        "/api/files",
        headers={**headers, "x-file-name": "policy.docx"},
        content=_docx_bytes(),
    )
    assert uploaded.status_code == 200, uploaded.text
    selection = uploaded.json()
    assert selection["kind"] == "file"
    assert selection["locator_ref"].endswith(".docx")
    assert selection["options"]["display_name"] == "policy.docx"

    created = client.post(
        "/api/sessions",
        headers=headers,
        json={"goal": "接入制度", "sources": [selection]},
    )
    assert created.status_code == 200, created.text
    sid = created.json()["session_id"]
    advanced = client.post(f"/api/sessions/{sid}/advance", headers=headers)
    assert advanced.status_code == 200, advanced.text

    profile = client.get(f"/api/sessions/{sid}/view", headers=headers).json()["profiles"][0]
    assert profile["kind"] == "docx"
    assert profile["coverage"] == "full"
    texts = [record.get("text") for record in profile["records"]]
    assert "差旅费用报销规则" in texts
    assert any("出差住宿标准" in (text or "") for text in texts)


def test_upload_still_rejects_unlisted_type(tmp_path):
    client, headers = _client(tmp_path)
    uploaded = client.post(
        "/api/files",
        headers={**headers, "x-file-name": "policy.doc"},
        content=b"legacy word",
    )
    assert uploaded.status_code == 422
