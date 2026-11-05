"""B02：文档解析与 OCR。

来源：OmniDocBench（opendatalab/OmniDocBench）：v1.5 标注 1,651 页，含版面元素、文本、公式与表格。
说明：仓库内只带 285 张页图；本轮只为有页图的页建用例，其余页留给后续补图。

用例形状：页图 → 阅读顺序下的文本 / 公式 / 表格。判分用 NED、TEDS 与阅读顺序，期望结构按 order 排序。
"""
from __future__ import annotations

import json

TEXT_CATS = {
    "text_block",
    "title",
    "header",
    "footer",
    "page_number",
    "page_footnote",
    "figure_footnote",
    "table_footnote",
    "reference",
    "list_group",
    "code_txt",
}


def build(ctx) -> dict:
    ctx.source("omnidocbench")
    ann = ctx.raw_path("omnidocbench", "OmniDocBench.json")
    pages = json.loads(ann.read_text(encoding="utf-8"))
    images = ctx.raw_path("omnidocbench", "images")
    have = {p.name for p in images.iterdir()} if images.exists() else set()

    n = 0
    skipped = 0
    for page in pages:
        info = page.get("page_info") or {}
        img = info.get("image_path")
        if not img or img not in have:
            skipped += 1
            continue
        dets = [d for d in page.get("layout_dets") or [] if not d.get("ignore")]
        ordered = sorted(dets, key=lambda d: (d.get("order") if d.get("order") is not None else 10**6))
        blocks = []
        text_parts = []
        tables = []
        for d in ordered:
            cat = d.get("category_type")
            if cat == "table":
                html = d.get("html") or d.get("text") or ""
                tables.append({"html": html, "order": d.get("order")})
                text_parts.append(html)
                blocks.append({"category": cat, "order": d.get("order"), "html": html[:200]})
            elif cat == "equation_isolated" or cat == "equation_semantic":
                latex = d.get("latex") or d.get("text") or ""
                text_parts.append(latex)
                blocks.append({"category": cat, "order": d.get("order"), "latex": latex})
            elif cat in TEXT_CATS or d.get("text"):
                text = d.get("text") or ""
                text_parts.append(text)
                blocks.append({"category": cat, "order": d.get("order"), "text": text})

        if not blocks:
            continue
        n += 1
        attr = info.get("page_attribute") or {}
        ctx.add(
            source="od",
            seq=n,
            inputs=[
                {
                    "kind": "file",
                    "ref": ctx.bench("omnidocbench", "images", img),
                    "digest": None,
                }
            ],
            expected={
                "kind": "document",
                "text": "\n".join(t for t in text_parts if t),
                "tables": tables,
                "blocks": blocks,
            },
            evidence=[ctx.bench("omnidocbench", "images", img)],
            tags=[
                "omnidocbench",
                str(attr.get("data_source") or "unknown"),
                str(attr.get("language") or "unknown"),
                str(attr.get("layout") or "unknown"),
                str(attr.get("subset") or "unknown"),
                "has_table" if tables else "no_table",
            ],
            gold={
                "source": "opendatalab/OmniDocBench",
                "page_no": info.get("page_no"),
                "image": img,
                "attribute": attr,
                "reading_order": [b.get("order") for b in blocks],
                "blocks": blocks,
                "tables": tables,
            },
            split_key=f"omnidoc:{img}",
        )

    if skipped:
        ctx.notes.append(f"{skipped} 页缺页图，未建用例")
    return {
        "policy": "只收有页图的页；期望按 order 排列。页图走 bench:// 引用，不复制进 docs。",
        "extra": {
            "coverage": {
                "covered_metrics": ["text_ned", "table_teds", "reading_order_accuracy"],
                "note": "断言式评分（olmOCR-Bench）待其数据到位后追加",
            },
            "pages_with_image": n,
            "pages_without_image": skipped,
        },
    }
