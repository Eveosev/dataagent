"""B09：表格计算、图表与报告。

来源：
- SpreadsheetBench（KAKA22/SpreadsheetBench）：912 条真实 Excel 操作题，含起始工作簿与答案单元格。
- VisEval / nvBench2.0：可视化问答与图表生成，数据到位后追加。

用例形状：工作簿 + 指令 → 目标区域的计算结果/图表规格。判分看单元格值、区域位置与图表类型。
"""
from __future__ import annotations

import json
import tarfile


def _extract(tar: "tarfile.TarFile", dest):
    for member in tar.getmembers():
        if member.name.startswith("/") or ".." in member.name:
            continue
        tar.extract(member, dest)


def _rows(path):
    text = path.read_text(encoding="utf-8").strip()
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass
    out = []
    for line in text.splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def build(ctx) -> dict:
    base = ctx.raw_path("spreadsheetbench")
    n = 0
    per_split = {}
    for archive in ("spreadsheetbench_912_v0.1.tar.gz", "spreadsheetbench_verified_400.tar.gz"):
        tar_path = base / archive
        if not tar_path.exists():
            continue
        dest = base / archive.replace(".tar.gz", "")
        dest.mkdir(parents=True, exist_ok=True)
        if not any(dest.iterdir()):
            with tarfile.open(tar_path) as tar:
                _extract(tar, dest)
        entries = sorted(dest.rglob("dataset.json"))
        if not entries:
            continue
        data_root = entries[0].parent
        ctx.source("spreadsheetbench")
        rows = _rows(entries[0])
        per_split[archive] = len(rows)
        for rec in rows:
            instruction = rec.get("instruction")
            xlsx = rec.get("spreadsheet_path") or rec.get("spreadsheet")
            if not instruction or not xlsx:
                continue
            local = data_root / xlsx
            if local.is_dir():
                found = sorted(p for p in local.iterdir() if p.suffix.lower() in {".xlsx", ".xls", ".xlsm"})
                if found:
                    xlsx = str(found[0].relative_to(data_root))
            rel = (data_root / xlsx).relative_to(base).as_posix()
            n += 1
            iref = ctx.fixture(f"ssb-{rec.get('id') or n}-instruction.md", str(instruction))
            ctx.add(
                source="ssb",
                seq=n,
                inputs=[
                    {"kind": "table", "ref": ctx.bench("spreadsheetbench", rel), "digest": None},
                    {"kind": "instruction", "ref": iref, "digest": None},
                ],
                expected={
                    "kind": "sheet_answer",
                    "instruction": instruction,
                    "answer": rec.get("answer"),
                    "answer_sheet": rec.get("answer_sheet"),
                    "answer_position": rec.get("answer_position"),
                    "data_position": rec.get("data_position"),
                    "instruction_type": rec.get("instruction_type"),
                },
                evidence=[iref, ctx.bench("spreadsheetbench", rel)],
                tags=["spreadsheetbench", archive.replace(".tar.gz", ""), str(rec.get("instruction_type") or "unknown")],
                gold={"source": "KAKA22/SpreadsheetBench", "raw": rec},
                split_key=f"ssb:{rec.get('id')}",
            )

    n += _nvbench2(ctx, n)

    if not n:
        ctx.notes.append("SpreadsheetBench / nvBench2 尚未下载")
    return {
        "policy": "两档数据集各自解压后按题目 id 入库；工作簿走 bench:// 引用。split 按 id 哈希。",
        "extra": {
            "coverage": {
                "covered_metrics": ["cell_accuracy", "region_iou"],
                "missing_metrics": ["report_factuality"],
                "note": "图表类由 nvBench2 覆盖（mark/encoding 结构匹配）；报告成稿质量待 VisEval 数据",
            },
            "counts": per_split,
        },
    }


def _nvbench2(ctx, start: int) -> int:
    base = ctx.raw_path("nvbench2")
    files = sorted((base / "data").glob("*.parquet"))
    if not files:
        ctx.notes.append("nvBench2 尚未下载")
        return 0
    import pyarrow.parquet as pq

    ctx.source("nvbench2")
    n = 0
    for path in files:
        split = path.name.split("-")[0]
        if split not in {"dev", "test"}:
            continue
        rows = pq.read_table(path).to_pylist()
        for rec in rows:
            query = rec.get("nl_query")
            if not query:
                continue
            n += 1
            schema = rec.get("table_schema")
            doc = f"# nvBench2 {split}\n\n## 问题\n\n{query}\n\n## 表结构\n\n{schema}\n"
            ref = ctx.fixture(f"nvb-{split}-{n:04d}.md", doc)
            gold = rec.get("gold_answer") or []
            mark = None
            if isinstance(gold, list) and gold and isinstance(gold[0], dict):
                mark = gold[0].get("mark")
            ctx.add(
                source="nvb",
                seq=start + n,
                inputs=[{"kind": "query", "ref": ref, "digest": None}],
                expected={"kind": "chart", "spec": gold, "mark": mark},
                evidence=[ref],
                tags=["nvbench2", split, str(mark or "unknown")],
                gold={
                    "source": "TianqiLuo/nvBench2.0",
                    "nl_query": query,
                    "table_schema": schema,
                    "gold_answer": gold,
                    "steps": rec.get("steps"),
                },
                split_key=f"nvb:{split}:{n}",
            )
    return n
