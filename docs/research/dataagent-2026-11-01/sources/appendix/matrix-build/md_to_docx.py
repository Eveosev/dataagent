# -*- coding: utf-8 -*-
"""Markdown -> DOCX（面向本报告的固定结构：标题/段落/表格/代码/列表/引用/链接）。"""
import re
import sys
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

CJK = "PingFang SC"
BODY = "Calibri"
NAVY = RGBColor(0x1F, 0x38, 0x64)
GRAY = RGBColor(0x59, 0x59, 0x59)
CODE_BG = "F2F4F7"
HEAD_BG = "1F3864"
ALT_BG = "F7F9FC"


def set_east_asia(run, font=CJK):
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:eastAsia"), font)
    rfonts.set(qn("w:ascii"), BODY)
    rfonts.set(qn("w:hAnsi"), BODY)


def shade(paragraph_or_cell, color):
    el = paragraph_or_cell._element
    pr = el.get_or_add_tcPr() if el.tag.endswith("tc") else el.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), color)
    pr.append(shd)


def add_hyperlink(paragraph, url, text, size=None, color="1F4E79"):
    part = paragraph.part
    r_id = part.relate_to(
        url,
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
        is_external=True,
    )
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), r_id)
    new_run = OxmlElement("w:r")
    rPr = OxmlElement("w:rPr")
    c = OxmlElement("w:color")
    c.set(qn("w:val"), color)
    rPr.append(c)
    u = OxmlElement("w:u")
    u.set(qn("w:val"), "single")
    rPr.append(u)
    if size:
        sz = OxmlElement("w:sz")
        sz.set(qn("w:val"), str(int(size * 2)))
        rPr.append(sz)
    new_run.append(rPr)
    t = OxmlElement("w:t")
    t.text = text
    t.set(qn("xml:space"), "preserve")
    new_run.append(t)
    hyperlink.append(new_run)
    paragraph._p.append(hyperlink)


INLINE = re.compile(r"(\*\*.+?\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\))")


def add_inline(paragraph, text, size=None, bold=False, color=None):
    for part in INLINE.split(text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            r = paragraph.add_run(part[2:-2])
            r.bold = True
        elif part.startswith("`") and part.endswith("`"):
            r = paragraph.add_run(part[1:-1])
            r.font.name = "Menlo"
            r.font.size = Pt((size or 10.5) - 0.5)
            r.font.color.rgb = RGBColor(0xA3, 0x1D, 0x1D)
            shade_run = OxmlElement("w:shd")
            shade_run.set(qn("w:val"), "clear")
            shade_run.set(qn("w:fill"), "F3F3F3")
            r._element.get_or_add_rPr().append(shade_run)
        elif part.startswith("[") and "](" in part:
            m = re.match(r"\[([^\]]+)\]\(([^)]+)\)", part)
            add_hyperlink(paragraph, m.group(2), m.group(1), size=size)
            continue
        else:
            r = paragraph.add_run(part)
            if bold:
                r.bold = True
        if part.startswith("**") or (not part.startswith("[")):
            if size:
                r.font.size = Pt(size)
            if color:
                r.font.color.rgb = color
            set_east_asia(r)


def body_style(doc):
    st = doc.styles["Normal"]
    st.font.name = BODY
    st.font.size = Pt(10.5)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), CJK)
    pf = st.paragraph_format
    pf.line_spacing = 1.45
    pf.space_after = Pt(5)
    pf.space_before = Pt(0)


def heading_style(doc, name, size, color=NAVY, before=14, after=6):
    st = doc.styles[name]
    st.font.name = BODY
    st.font.size = Pt(size)
    st.font.bold = True
    st.font.color.rgb = color
    st.element.rPr.rFonts.set(qn("w:eastAsia"), CJK)
    st.paragraph_format.space_before = Pt(before)
    st.paragraph_format.space_after = Pt(after)
    st.paragraph_format.keep_with_next = True


def add_page_number(paragraph):
    run = paragraph.add_run()
    fld1 = OxmlElement("w:fldChar"); fld1.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText"); instr.set(qn("xml:space"), "preserve"); instr.text = " PAGE "
    fld2 = OxmlElement("w:fldChar"); fld2.set(qn("w:fldCharType"), "end")
    run._r.append(fld1); run._r.append(instr); run._r.append(fld2)
    run.font.size = Pt(9)


def add_table(doc, rows):
    header, body = rows[0], rows[1:]
    ncol = len(header)
    table = doc.add_table(rows=1, cols=ncol)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    hdr = table.rows[0].cells
    for i, txt in enumerate(header):
        cell = hdr[i]
        cell.text = ""
        p = cell.paragraphs[0]
        p.paragraph_format.space_after = Pt(1)
        p.paragraph_format.line_spacing = 1.0
        add_inline(p, txt, size=8.5, bold=True)
        for r in p.runs:
            r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
            r.bold = True
        shade(cell, HEAD_BG)
    for ri, row in enumerate(body):
        cells = table.add_row().cells
        for ci in range(ncol):
            cell = cells[ci]
            cell.text = ""
            p = cell.paragraphs[0]
            p.paragraph_format.space_after = Pt(1)
            p.paragraph_format.line_spacing = 1.0
            txt = row[ci] if ci < len(row) else ""
            add_inline(p, txt, size=8.5)
            if ri % 2 == 1:
                shade(cell, ALT_BG)
    # 列宽：首列窄，末列宽
    total = 17.2
    if ncol == 8:
        widths = [1.15, 3.0, 3.7, 2.6, 3.1, 0.9, 0.8, 0.8]
    elif ncol == 7:
        widths = [1.45, 3.15, 4.3, 1.05, 1.2, 1.35, 4.7]
    elif ncol == 6:
        widths = [1.5, 3.4, 5.0, 1.2, 1.4, 4.7]
    elif ncol == 5:
        widths = [1.6, 4.4, 4.4, 1.6, 5.2]
    elif ncol == 4:
        widths = [2.4, 5.4, 4.6, 4.8]
    elif ncol == 3:
        widths = [3.2, 8.6, 5.4]
    else:
        widths = [total / ncol] * ncol
    scale = total / sum(widths)
    for ci, w in enumerate(widths):
        for row in table.rows:
            row.cells[ci].width = Cm(w * scale)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return table


def add_code(doc, lines):
    for i, line in enumerate(lines):
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.line_spacing = 1.0
        p.paragraph_format.left_indent = Cm(0.3)
        p.paragraph_format.right_indent = Cm(0.2)
        r = p.add_run(line if line else " ")
        r.font.name = "Menlo"
        r.font.size = Pt(8.2)
        r.font.color.rgb = RGBColor(0x24, 0x29, 0x2E)
        set_east_asia(r, CJK)
        shade(p, CODE_BG)
    doc.add_paragraph().paragraph_format.space_after = Pt(3)


def is_table_sep(line):
    return bool(re.match(r"^\|[\s:\-|]+\|$", line.strip()))


def split_row(line):
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def convert(md_path, out_path):
    raw = open(md_path, encoding="utf-8").read().splitlines()
    meta = {}
    i = 0
    if raw and raw[0].strip() == "---":
        i = 1
        while i < len(raw) and raw[i].strip() != "---":
            if ":" in raw[i]:
                k, v = raw[i].split(":", 1)
                meta[k.strip()] = v.strip().strip('"')
            i += 1
        i += 1
    lines = raw[i:]

    doc = Document()
    body_style(doc)
    heading_style(doc, "Heading 1", 16, before=18, after=8)
    heading_style(doc, "Heading 2", 13, before=14, after=5)
    heading_style(doc, "Heading 3", 11.5, before=10, after=4)

    sec = doc.sections[0]
    sec.page_width = Cm(21)
    sec.page_height = Cm(29.7)
    sec.left_margin = Cm(1.9)
    sec.right_margin = Cm(1.9)
    sec.top_margin = Cm(2.0)
    sec.bottom_margin = Cm(1.8)

    # 封面
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(120)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("DataAgent 模块化能力拆分调研报告")
    r.font.size = Pt(26); r.bold = True; r.font.color.rgb = NAVY
    set_east_asia(r)

    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(meta.get("subtitle", ""))
    r.font.size = Pt(14); r.font.color.rgb = GRAY
    set_east_asia(r)

    for text in [
        "",
        "15 个一级模块 · 92 项二级能力 · 30 项 P0 · 9 项核心自研",
        "",
        f"基于 DataAgent Brainstorm（revision 272）与六方向补充调研",
        "2026-11-01 · Asia/Shanghai · 调研稿（待评审）",
    ]:
        p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(text)
        r.font.size = Pt(10.5); r.font.color.rgb = GRAY
        set_east_asia(r)

    doc.add_page_break()

    # 目录（静态，仅列到二级标题）
    p = doc.add_paragraph()
    r = p.add_run("目录")
    r.font.size = Pt(16); r.bold = True; r.font.color.rgb = NAVY
    set_east_asia(r)
    p.paragraph_format.space_after = Pt(8)
    for ln in lines:
        if ln.startswith("## ") and not ln.startswith("### "):
            txt = ln[3:].strip()
            q = doc.add_paragraph()
            q.paragraph_format.space_after = Pt(2)
            q.paragraph_format.line_spacing = 1.2
            rr = q.add_run(txt)
            rr.font.size = Pt(10)
            set_east_asia(rr)
    doc.add_page_break()

    in_code = False
    code_buf = []
    idx = 0
    first_h1 = True
    while idx < len(lines):
        line = lines[idx]
        stripped = line.strip()

        if stripped.startswith("```"):
            if in_code:
                add_code(doc, code_buf)
                code_buf = []
                in_code = False
            else:
                in_code = True
            idx += 1
            continue
        if in_code:
            code_buf.append(line)
            idx += 1
            continue

        if not stripped:
            idx += 1
            continue

        if stripped == "---":
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(2)
            pPr = p._p.get_or_add_pPr()
            pbdr = OxmlElement("w:pBdr")
            bottom = OxmlElement("w:bottom")
            bottom.set(qn("w:val"), "single"); bottom.set(qn("w:sz"), "6")
            bottom.set(qn("w:color"), "D0D7E2")
            pbdr.append(bottom); pPr.append(pbdr)
            idx += 1
            continue

        if stripped.startswith("# "):
            txt = stripped[2:].strip()
            if first_h1:
                first_h1 = False
                p = doc.add_paragraph()
                r = p.add_run(txt)
                r.font.size = Pt(20); r.bold = True; r.font.color.rgb = NAVY
                set_east_asia(r)
                p.paragraph_format.space_after = Pt(8)
            idx += 1
            continue

        if stripped.startswith("## "):
            doc.add_heading(stripped[3:].strip(), level=1)
            idx += 1
            continue
        if stripped.startswith("### "):
            doc.add_heading(stripped[4:].strip(), level=2)
            idx += 1
            continue
        if stripped.startswith("#### "):
            doc.add_heading(stripped[5:].strip(), level=3)
            idx += 1
            continue

        # 表格
        if stripped.startswith("|") and idx + 1 < len(lines) and is_table_sep(lines[idx + 1]):
            rows = [split_row(stripped)]
            idx += 2
            while idx < len(lines) and lines[idx].strip().startswith("|"):
                rows.append(split_row(lines[idx]))
                idx += 1
            add_table(doc, rows)
            continue

        # 引用
        if stripped.startswith(">"):
            buf = []
            while idx < len(lines) and lines[idx].strip().startswith(">"):
                buf.append(lines[idx].strip().lstrip(">").strip())
                idx += 1
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(0.5)
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(6)
            pPr = p._p.get_or_add_pPr()
            pbdr = OxmlElement("w:pBdr")
            left = OxmlElement("w:left")
            left.set(qn("w:val"), "single"); left.set(qn("w:sz"), "18")
            left.set(qn("w:space"), "8"); left.set(qn("w:color"), "1F3864")
            pbdr.append(left); pPr.append(pbdr)
            add_inline(p, " ".join(buf), size=10, color=GRAY)
            continue

        # 列表
        m = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", line)
        if m:
            indent, marker, txt = m.group(1), m.group(2), m.group(3)
            level = min(len(indent) // 2, 2)
            style = "List Number" if re.match(r"\d+\.", marker) else "List Bullet"
            p = doc.add_paragraph(style=style)
            p.paragraph_format.left_indent = Cm(0.75 + level * 0.6)
            p.paragraph_format.space_after = Pt(2)
            p.paragraph_format.line_spacing = 1.35
            add_inline(p, txt, size=10.5)
            idx += 1
            continue

        # 普通段落
        p = doc.add_paragraph()
        p.paragraph_format.first_line_indent = Cm(0)
        add_inline(p, stripped, size=10.5)
        idx += 1

    if code_buf:
        add_code(doc, code_buf)

    # 页脚页码
    footer = doc.sections[0].footer
    fp = footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fr = fp.add_run("DataAgent 模块化能力拆分调研报告 · 2026-11-01 · 第 ")
    fr.font.size = Pt(9); fr.font.color.rgb = GRAY
    set_east_asia(fr)
    add_page_number(fp)
    fr2 = fp.add_run(" 页")
    fr2.font.size = Pt(9); fr2.font.color.rgb = GRAY
    set_east_asia(fr2)

    doc.save(out_path)
    print("saved", out_path)


if __name__ == "__main__":
    convert(sys.argv[1], sys.argv[2])
