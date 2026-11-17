"""Generate a synthetic Word policy document for probe tests.

The fixture is code, never a checked-in binary: the repository must not carry
real policy originals.  It exercises headings, body paragraphs, a 3x3 table
with one vertical merge, and a header/footer that probes must ignore.
"""
from __future__ import annotations

from pathlib import Path


def build_policy_docx(path: Path, *, title_text: str = '费用报销制度',
                      body_text: str = '金额超过 5000 元须经部门负责人审批。',
                      title_style_level: int = 1, table_rows: int = 3,
                      with_header_footer: bool = True) -> None:
    from docx import Document

    document = Document()
    document.add_heading(title_text, level=title_style_level)
    document.add_paragraph('第一条 本制度适用于全体员工。')
    document.add_heading('审批权限', level=2)
    document.add_paragraph(body_text)

    table = document.add_table(rows=table_rows, cols=3)
    table.style = 'Table Grid'
    for column, value in enumerate(['项目', '金额', '说明']):
        table.cell(0, column).text = value
    if table_rows >= 2:
        table.cell(1, 0).text = '差旅费'
        table.cell(1, 1).text = '1200'
        table.cell(1, 2).text = '实报实销'
    if table_rows >= 3:
        table.cell(2, 0).text = '招待费'
        table.cell(2, 1).text = '800'
        # One merged cell: row 2's 说明 is the value owned by row 1.
        table.cell(1, 2).merge(table.cell(2, 2))
    if table_rows >= 4:
        table.cell(3, 0).text = '其他'
        table.cell(3, 1).text = '300'
        table.cell(3, 2).text = '按项目审批'

    if with_header_footer:
        section = document.sections[0]
        section.header.paragraphs[0].text = '页眉：内部资料'
        section.footer.paragraphs[0].text = '页脚：第 1 页'
    document.save(str(path))
