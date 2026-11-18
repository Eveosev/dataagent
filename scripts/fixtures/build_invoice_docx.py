#!/usr/bin/env python3
"""Build the F10 invoice.docx sample (offline-input-cases.md 文件输入).

The content matches ``build_invoice_docx`` in
``packages/capabilities/dataagent-data/tests/observation/test_docx_record_sets.py``:
a「采购单」heading, one table with a header row and 3 data rows, and a trailing
remark paragraph.  F10's fixed expectations: 3 objects (INV-301 1260.00,
INV-302 900.50, INV-303 3300.00 CNY), the header row is labels, the remark
paragraph is a separate record set, and the first amount anchor is
``table:1/row:2/col:2``.

Run with an interpreter that has python-docx (the dataagent-data venv does):

    uv run --frozen --project packages/capabilities/dataagent-data \
        python scripts/fixtures/build_invoice_docx.py invoice.docx
"""
from __future__ import annotations

import sys
from pathlib import Path

from docx import Document

HEADERS = ['number', 'amount', 'currency']
ROWS = [
    ['INV-301', '1260.00', 'CNY'],
    ['INV-302', '900.50', 'CNY'],
    ['INV-303', '3300.00', 'CNY'],
]


def build_invoice_docx(path: Path) -> None:
    document = Document()
    document.add_heading('采购单', level=1)
    table = document.add_table(rows=len(ROWS) + 1, cols=len(HEADERS))
    table.style = 'Table Grid'
    for column, value in enumerate(HEADERS):
        table.cell(0, column).text = value
    for row_index, row in enumerate(ROWS, 1):
        for column, value in enumerate(row):
            table.cell(row_index, column).text = value
    document.add_paragraph('备注：发票登记表由财务复核。')
    document.save(str(path))


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    build_invoice_docx(Path(argv[1]))
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
