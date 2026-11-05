"""B10：持续监控与漂移告警。

来源：TSB-AD（TheDatumOrg/TSB-AD）：TSB-AD-U（350 条单变量）+ TSB-AD-M（180 条多变量）时序，
每条一个 CSV，含时间戳、数值与人工标注的异常区间。File_List 给出官方评测/调参划分。

用例形状：序列（bench:// 原始 CSV，评测时剥掉 label 列）→ 异常区间。
判分用 VUS-PR / affiliation-F1 / 区间召回；告警条数与巡检成本一起看，避免「全报警」拿高分。
"""
from __future__ import annotations

import csv
import json

RAW_TASK = None  # 由 build 注入

EVA_FILES = {
    "tsb-ad-u": ("Datasets/File_List/TSB-AD-U-Eva.csv", "u"),
    "tsb-ad-m": ("Datasets/File_List/TSB-AD-M-Eva.csv", "m"),
}


def _read_labels(path, col="Label"):
    try:
        with path.open(newline="", encoding="utf-8", errors="replace") as fh:
            reader = csv.DictReader(fh)
            if not reader.fieldnames or col not in reader.fieldnames:
                return None
            labels = [str(row.get(col) or "0").strip() for row in reader]
        idx = [i for i, v in enumerate(labels) if v not in {"0", "", "0.0", "False", "false"}]
        return {"n": len(labels), "anomaly_count": len(idx), "anomalies": idx[:5000]}
    except OSError:
        return None


def build(ctx) -> dict:
    global RAW_TASK
    RAW_TASK = ctx.raw_path("tsb-ad")
    n = 0
    per = {}
    for source_id, (list_path, kind) in EVA_FILES.items():
        root = ctx.raw_path(source_id)
        if not root.exists():
            ctx.notes.append(f"{source_id} 尚未下载")
            continue
        ctx.source(source_id)
        listing = root / list_path
        if not listing.exists():
            listing = RAW_TASK / list_path
        if not listing.exists():
            ctx.notes.append(f"{source_id} 缺 File_List")
            continue
        names = []
        with listing.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                name = (row.get("file_name") or "").strip()
                if name:
                    names.append(name)
        per[kind] = 0
        for name in names:
            sub = "TSB-AD-U" if kind == "u" else "TSB-AD-M"
            candidates = [
                root / sub / name,
                root / "Datasets" / sub / name,
                root / "Datasets" / name,
                root / name,
            ]
            candidate = next((c for c in candidates if c.exists()), None)
            if candidate is None:
                continue
            rel = candidate.relative_to(root).as_posix()
            labels = _read_labels(candidate)
            n += 1
            per[kind] += 1
            tags = ["tsb-ad", kind]
            for domain in ("Web Service", "Sensor", "Environment", "Traffic", "Finance", "Facility", "Medical", "Synthetic"):
                if f"_{domain.replace(' ', '')}_" in name or f"_{domain}_" in name:
                    tags.append(domain)
            ctx.add(
                source="tsbad" if kind == "u" else "tsbad-m",
                seq=n,
                inputs=[
                    {
                        "kind": "series",
                        "ref": ctx.bench(source_id, rel),
                        "digest": None,
                    }
                ],
                expected={
                    "kind": "anomaly",
                    "series_ref": ctx.bench(source_id, rel),
                    "label_column": "Label",
                    "labels": labels,
                },
                evidence=[ctx.bench(source_id, rel)],
                tags=tags,
                gold={
                    "source": "TheDatumOrg/TSB-AD",
                    "series": name,
                    "label_ranges": labels,
                    "file_list": list_path,
                },
                split_key=f"tsbad:{name}",
            )

    if not n:
        ctx.notes.append("TSB-AD 序列文件尚未解压，等待 tsb-ad-u / tsb-ad-m")
    return {
        "policy": "按官方 Eva 列表入库；label 列由 harness 在评测时剥离，避免标签泄漏。split 按文件名哈希。",
        "extra": {
            "coverage": {
                "covered_metrics": ["vus_pr", "affiliation_f1"],
                "missing_metrics": ["alert_budget_compliance"],
                "note": "告警预算需 harness 统计巡检次数；先由 scorecard 记录 alert_count",
            },
            "counts": per,
        },
    }
