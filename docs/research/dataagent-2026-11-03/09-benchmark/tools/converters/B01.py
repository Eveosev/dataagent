"""B01：不规则表格理解。

来源：
- MiMoTable（jyz111/mimotable）：641 英文 + 995 中文题目，问题指向具体工作簿，答案为自然语言。
- RealHiTBench（spzy/RealHiTBench）：708 张层级表 / 3,752 问答，含 csv/html/latex/png 四种表示。

用例形状：工作簿（bench:// 原始文件）+ 问题 → 答案。表格结构类标签（table_type、难度、操作类型）进 tags，供分层报分。
"""
from __future__ import annotations

import json


def build(ctx) -> dict:
    ctx.source("mimotable")
    seq = 0
    counts = {"mimotable": 0, "realthitbench": 0}

    for lang in ("english", "chinese"):
        path = ctx.raw_path("mimotable", "unzipped", "data", lang, "problems.json")
        if not path.exists():
            ctx.notes.append(f"缺少 {lang} problems.json")
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            seq += 1
            inputs = []
            for raw in rec.get("spreadsheet_list") or []:
                rel = raw.lstrip("./")
                inputs.append(
                    {
                        "kind": "table",
                        "ref": ctx.bench("mimotable", "unzipped", "data", lang, rel),
                        "digest": None,
                    }
                )
            if not inputs:
                continue
            ctx.add(
                source="mimo",
                seq=seq,
                inputs=inputs,
                expected={
                    "kind": "answer",
                    "question": rec.get("question"),
                    "answer": rec.get("answer"),
                },
                evidence=[f"{inputs[0]['ref']}#workbook"],
                tags=[
                    lang,
                    rec.get("table_type") or "unknown",
                    rec.get("table_difficulty") or "unknown",
                    *[f"op:{o}" for o in (rec.get("meta_operation_list") or [])],
                ],
                gold={
                    "source": "jyz111/mimotable",
                    "language": lang,
                    "question": rec.get("question"),
                    "answer": rec.get("answer"),
                    "table_type": rec.get("table_type"),
                    "table_difficulty": rec.get("table_difficulty"),
                    "meta_operation_list": rec.get("meta_operation_list"),
                    "question_difficulty": rec.get("question_difficulty"),
                },
            )
            counts["mimotable"] += 1

    counts["realthitbench"] = _realthitbench(ctx, start=seq)
    return {
        "policy": "MiMoTable 全量；RealHiTBench 在数据就位后按 QA 对入库。split 按题目 id 哈希 60/20/20。",
        "extra": {
            "coverage": {
                "covered_metrics": ["downstream_qa_accuracy"],
                "partial_metrics": ["header_cell_accuracy", "row_retention"],
                "note": "外部集只给问答答案；表头正确率与行保留率需用自建金标（结构标注）判定",
            },
            "counts": counts,
        },
    }


def _realthitbench(ctx, start: int) -> int:
    base = ctx.raw_path("realthitbench-data")
    qa = base / "QA_final.json"
    if not qa.exists():
        ctx.notes.append("RealHiTBench QA_final.json 尚未下载")
        return 0
    try:
        data = json.loads(qa.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        ctx.notes.append("RealHiTBench QA_final.json 解析失败")
        return 0
    items = data.get("queries") if isinstance(data, dict) else data
    if not items:
        ctx.notes.append("RealHiTBench QA_final.json 没有 queries")
        return 0
    ctx.source("realthitbench-data")
    n = 0
    for rec in items:
        table = rec.get("FileName") or rec.get("file_name")
        question = rec.get("Question") or rec.get("question")
        if not table or not question:
            continue
        answer = rec.get("ProcessedAnswer") or rec.get("FinalAnswer") or rec.get("answer")
        csv_ref = ctx.bench("realthitbench-data", "csv", f"{table}.csv")
        n += 1
        ctx.add(
            source="rht",
            seq=start + n,
            inputs=[{"kind": "table", "ref": csv_ref, "digest": None}],
            expected={"kind": "answer", "question": question, "answer": answer},
            evidence=[csv_ref],
            tags=[
                "realthitbench",
                rec.get("CompStrucCata") or "unknown",
                rec.get("QuestionType") or "unknown",
                rec.get("Source") or "unknown",
            ],
            gold={
                "source": "spzy/RealHiTBench",
                "id": rec.get("id"),
                "table": table,
                "structure": rec.get("CompStrucCata"),
                "question_type": rec.get("QuestionType"),
                "sub_type": rec.get("SubQType"),
                "answer": answer,
                "cot": rec.get("COT"),
            },
            split_key=f"rht:{table}:{rec.get('id')}",
        )
    return n
