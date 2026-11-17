"""B17：字段映射 / schema matching。

来源：Valentine 官方仓库 v1.1.1 的 `experiments/data/`（10 对表）。
- 仓库：https://github.com/delftdata/valentine
- 数据说明：`experiments/README.md` 记明这些表对由 Yurong Liu 整理，来自 NYC Open Data，
  经 LLM 做 schema/value 扰动，每对含 `source_table.csv`、`target_table.csv`、`ground_truth.json`。
- 许可：仓库 LICENSE 为 Apache-2.0（Delft University of Technology, 2021-2026）；
  数据文件随仓库分发，按 Apache-2.0 再分发并署名。原始 NYC Open Data 作为来源记在 manifest。

用例形状：一条用例对应一个源字段，给源表与目标表的列名、行数和少量样例值，
要求只返回该源字段的 top-1 目标列名；没有对应字段时显式返回 null/空数组。
金标只取 `ground_truth.json.matches`；未出现在 matches 里的源字段按该文件的
`has_false_positives=false` 口径视为无对应字段，不生成、不改写金标。

切分：按表对做固定 sha256 60/20/20；同一表对的全部源字段落在同一 split，避免同表跨 split
泄漏。10 个表对数量少，用固定盐 `valentine-pair-v1-000029` 让三个 split 都有样本；
盐只用于分桶，不参与用例内容或金标。
"""
from __future__ import annotations

import csv
import json
import re
import sys
import unicodedata
from pathlib import Path

SPLITS = ("development", "regression", "unseen_acceptance")
SPLIT_SALT = "valentine-pair-v1-000029"
SAMPLE_SCAN_ROWS = 20
SAMPLES_PER_COLUMN = 2
SAMPLE_MAX_CHARS = 80

SOURCE_ID = "valentine-schema-matching"
LICENSE = "Apache-2.0"
LICENSE_URL = "https://github.com/delftdata/valentine/blob/v1.1.1/LICENSE"
LICENSE_EVIDENCE = "https://github.com/delftdata/valentine/blob/v1.1.1/experiments/README.md"
LICENSE_EVIDENCE_QUOTE = (
    "The dataset pairs under `data/` were prepared by Yurong Liu. They are sourced from "
    "NYC Open Data with schema and value perturbations based on LLMs to create pairs of "
    "diverse matching difficulty levels. Each subdirectory contains a `source_table.csv`, "
    "`target_table.csv`, and `ground_truth.json`."
)
LICENSE_CHECKED_AT = "2026-11-18"
ATTRIBUTION = "Valentine (Delft University of Technology); data curated by Yurong Liu from NYC Open Data"

PAIRS = [
    {
        "dir": "City_Government__Capital_Projects",
        "slug": "capital-projects",
        "label": "Capital Projects",
    },
    {
        "dir": "City_Government__DCM_StreetCenterLine",
        "slug": "dcm-streetcenterline",
        "label": "DCM StreetCenterLine",
    },
    {
        "dir": "City_Government__DPR_AthleticFacilities_001",
        "slug": "dpr-athletic-facilities",
        "label": "DPR Athletic Facilities",
    },
    {
        "dir": "City_Government__DSNY_Districts_With_Disposal_Vendor_Assignments",
        "slug": "dsny-districts",
        "label": "DSNY Districts with Disposal Vendor Assignments",
    },
    {
        "dir": "City_Government__NYC_Municipal_Building_Energy_Benchmarking_Results",
        "slug": "nyc-energy-benchmarking",
        "label": "NYC Municipal Building Energy Benchmarking Results",
    },
    {
        "dir": "Education__COVID-19_Free_Meals_Locations",
        "slug": "covid-free-meals",
        "label": "COVID-19 Free Meals Locations",
    },
    {
        "dir": "Housing_&_Development__Housing_Maintenance_Code_Complaints_and_Problems",
        "slug": "housing-maintenance",
        "label": "Housing Maintenance Code Complaints and Problems",
    },
    {
        "dir": "Housing_&_Development__Public_Design_Commission_Outdoor_Public_Art_Invent",
        "slug": "public-art-inventory",
        "label": "Public Design Commission Outdoor Public Art Inventory",
    },
    {
        "dir": "Recreation__Swim_for_Life__2016_to_2020",
        "slug": "swim-for-life",
        "label": "Swim for Life 2016 to 2020",
    },
    {
        "dir": "Transportation__DOT_In-house_Street_Resurfacing_Projects",
        "slug": "street-resurfacing",
        "label": "DOT In-house Street Resurfacing Projects",
    },
]


def build(ctx) -> dict:
    source_rec = ctx.source(SOURCE_ID)
    source_rec.update(
        license=LICENSE,
        license_url=LICENSE_URL,
        license_evidence=LICENSE_EVIDENCE,
        license_checked_at=LICENSE_CHECKED_AT,
        attribution=ATTRIBUTION,
        revision_requested="v1.1.1",
    )
    base = ctx.raw_path(SOURCE_ID, "experiments", "data")
    counts = {
        "pairs": 0,
        "source_fields": 0,
        "positive_fields": 0,
        "no_match_fields": 0,
        "per_pair": {},
    }

    for spec in sorted(PAIRS, key=lambda item: item["dir"]):
        pair_dir = base / spec["dir"]
        if not pair_dir.is_dir():
            raise FileNotFoundError(f"{pair_dir} 不存在；先跑 tools/fetch.py --task B17")
        pair_counts = _build_pair(ctx, spec, pair_dir)
        counts["pairs"] += 1
        counts["source_fields"] += pair_counts["source_fields"]
        counts["positive_fields"] += pair_counts["positive_fields"]
        counts["no_match_fields"] += pair_counts["no_match_fields"]
        counts["per_pair"][spec["slug"]] = pair_counts
        ctx.notes.append(
            f"{spec['dir']}: fields={pair_counts['source_fields']} "
            f"positive={pair_counts['positive_fields']} no_match={pair_counts['no_match_fields']}"
        )

    counts["splits"] = _split_counts(ctx)
    return {
        "policy": (
            "一条用例一个源字段；fixture 只含两表列名、行数与每列至多 2 个截断样例值，不含完整行；"
            "金标只取 Valentine 数据的 ground_truth.json.matches，未出现的源字段按 "
            "has_false_positives=false 记为无对应字段；按表对固定 sha256 60/20/20 切分，"
            "同一表对不跨 split；top-1 判分，无对应字段必须显式返回 null/空。"
        ),
        "extra": {
            "coverage": {
                "covered_metrics": ["mapping_top1", "no_match_accuracy"],
                "partial_metrics": [],
                "missing_metrics": [],
                "coverage_gaps": [
                    {
                        "id": "private_lingcai_subset",
                        "status": "deferred",
                        "description": (
                            "私有子集（令才字段目录与报文映射）不在公开用例中；本轮只用 Valentine 公开子集。"
                        ),
                        "impact": (
                            "无法衡量模型在令才真实字段名、别名和报文结构上的 top-1 映射效果；"
                            "公开子集的分数不能替代私有子集验收。"
                        ),
                        "next_step": (
                            "由 T34b 接入令才字段目录与人工确认的映射后，按 private:// 解析补私有子集，"
                            "不把私有数据写进 Git 或日志正文。"
                        ),
                    },
                    {
                        "id": "business_data",
                        "status": "deferred",
                        "description": (
                            "业务数据（客户字段目录、人工映射与值域）尚未提供；当前 10 对表全部来自 NYC Open Data。"
                        ),
                        "impact": (
                            "跨行业、中文业务字段与客户命名习惯未覆盖；结论只适用于公开英文表结构。"
                        ),
                        "next_step": (
                            "由客户授权并脱敏后登记为独立来源，补 development/regression 用例；"
                            "unseen_acceptance 只放未暴露样本。"
                        ),
                    },
                ],
                "note": (
                    "公开子集覆盖 10 对表、146 个源字段，其中 77 个有目标字段、69 个无对应字段；"
                    "三个 split 都同时含正例与无匹配字段。按 Valentine 评测口径，"
                    "ground_truth.matches 之外的预测对计 FP，因此未列入 matches 的源字段按无匹配处理；"
                    "has_false_positives=false 进一步说明 matches 内没有错标。Valentine 原始论文数据集归档"
                    "（surfdrive）链接已 404，Wayback 快照只有 1 MB 截断 zip，不作来源；改用官方仓库 "
                    "v1.1.1 的 experiments/data 公开子集。"
                ),
                "license_audit": [
                    {
                        "candidate": "Valentine 官方仓库 v1.1.1 experiments/data（10 对表）",
                        "license": "Apache-2.0",
                        "decision": "采用；manifest 记 attribution",
                        "evidence": LICENSE_URL,
                        "evidence_quote": "Copyright 2021-2026 Delft University of Technology ... Licensed under the Apache License, Version 2.0",
                        "data_evidence": LICENSE_EVIDENCE,
                        "data_evidence_quote": LICENSE_EVIDENCE_QUOTE,
                        "evidence_checked_at": LICENSE_CHECKED_AT,
                        "datasets": [spec["dir"] for spec in sorted(PAIRS, key=lambda item: item["dir"])],
                    },
                    {
                        "candidate": "Valentine 原始论文数据集归档（surfdrive 分享）",
                        "license": "未声明；分享页已不可用",
                        "decision": "不采用；2026-11-18 访问返回 404，Wayback 快照 zip 截断为 1 MB",
                        "evidence": "https://surfdrive.surf.nl/files/index.php/s/QU5oxyNMuVguEku",
                        "evidence_checked_at": LICENSE_CHECKED_AT,
                    },
                    {
                        "candidate": "valentine-paper-results 仓库",
                        "license": "仓库含结果与可视化，未声明原始数据许可",
                        "decision": "不采用；只有算法输出，没有可直接判分的原始表对与金标",
                        "evidence": "https://github.com/delftdata/valentine-paper-results",
                        "evidence_checked_at": LICENSE_CHECKED_AT,
                    },
                    {
                        "candidate": "valentine-generator 仓库",
                        "license": "代码仓库，数据集不随仓库分发",
                        "decision": "不采用；生成器需要外部基础表，不能独立产出一致的数据快照",
                        "evidence": "https://github.com/delftdata/valentine-generator",
                        "evidence_checked_at": LICENSE_CHECKED_AT,
                    },
                    {
                        "candidate": "NYC Open Data（原始数据来源）",
                        "license": "NYC Open Data Terms of Use；作为来源署名，实际再分发许可以 Valentine 仓库 Apache-2.0 为准",
                        "decision": "作为 provenance 记录，不单独作为再分发许可",
                        "evidence": "https://opendata.cityofnewyork.us/overview/",
                        "evidence_checked_at": LICENSE_CHECKED_AT,
                    },
                ],
            },
            "counts": counts,
        },
    }


def _build_pair(ctx, spec: dict, pair_dir: Path) -> dict:
    source_path = pair_dir / "source_table.csv"
    target_path = pair_dir / "target_table.csv"
    gold_path = pair_dir / "ground_truth.json"
    for path in (source_path, target_path, gold_path):
        if not path.exists():
            raise FileNotFoundError(f"{path} 不存在")

    source_columns = _read_columns(source_path)
    target_columns = _read_columns(target_path)
    ground_truth = json.loads(gold_path.read_text(encoding="utf-8"))
    meta = ground_truth.get("meta") or {}
    matches = _read_matches(ground_truth, source_columns, target_columns)

    source_samples = _read_samples(source_path, source_columns)
    target_samples = _read_samples(target_path, target_columns)
    source_row_count = _dims(meta.get("source_dims"))
    target_row_count = _dims(meta.get("target_dims"))

    split_key = f"{SPLIT_SALT}:{spec['dir']}"
    positive = 0
    no_match = 0
    for index, source_field in enumerate(source_columns, 1):
        target_field = matches.get(source_field)
        if target_field is None:
            no_match += 1
        else:
            positive += 1
        case_id = f"B17-{spec['slug']}-{index:04d}"
        fixture = {
            "task": "schema_matching_top1",
            "instruction": (
                "给定源表、目标表和 source_field，只返回该源字段的 top-1 目标列名。"
                "没有对应字段时显式返回 null（或空数组），不要猜测；不要为其他源字段作答。"
            ),
            "source_table": {
                "name": f"{spec['dir']}/source_table.csv",
                "row_count": source_row_count,
                "columns": [
                    {"name": name, "samples": source_samples.get(name, [])}
                    for name in source_columns
                ],
            },
            "target_table": {
                "name": f"{spec['dir']}/target_table.csv",
                "row_count": target_row_count,
                "columns": [
                    {"name": name, "samples": target_samples.get(name, [])}
                    for name in target_columns
                ],
            },
            "source_field": source_field,
        }
        ref = ctx.fixture(f"{case_id}.json", json.dumps(fixture, ensure_ascii=False, indent=2) + "\n")
        expected = {
            "kind": "schema_mapping_top1",
            "source_dataset": SOURCE_ID,
            "license": LICENSE,
            "license_url": LICENSE_URL,
            "attribution": ATTRIBUTION,
            "source_table": f"{spec['dir']}/source_table.csv",
            "target_table": f"{spec['dir']}/target_table.csv",
            "source_field": source_field,
            "target_field": target_field,
            "candidate_targets": target_columns,
            "annotation": (
                "ground_truth.json.matches 的正例；未出现在 matches 的源字段按 "
                "meta.has_false_positives=false 视为无对应字段"
            ),
        }
        ctx.add(
            source=spec["slug"],
            seq=index,
            inputs=[{"kind": "table", "ref": ref, "digest": None}],
            expected=expected,
            evidence=[ref],
            tags=[
                "schema-matching",
                f"pair:{spec['slug']}",
                "gold:match" if target_field else "gold:no_match",
            ],
            gold={
                "source_dataset": SOURCE_ID,
                "source_table": f"{spec['dir']}/source_table.csv",
                "target_table": f"{spec['dir']}/target_table.csv",
                "source_field": source_field,
                "target_field": target_field,
                "license": LICENSE,
                "license_url": LICENSE_URL,
                "attribution": ATTRIBUTION,
            },
            split_key=split_key,
        )
    source_set = set(source_columns)
    target_set = set(target_columns)
    invalid_sources = sorted(
        {
            _clean(item.get("source_column"))
            for item in ground_truth.get("matches") or []
            if item.get("target_column")
            and _clean(item.get("source_column"))
            and _clean(item.get("source_column")) not in source_set
        }
    )
    invalid_targets = sorted(
        {
            _clean(item.get("target_column"))
            for item in ground_truth.get("matches") or []
            if item.get("target_column")
            and _clean(item.get("target_column"))
            and _clean(item.get("target_column")) not in target_set
        }
    )
    if invalid_sources or invalid_targets:
        raise ValueError(
            f"{spec['dir']}: ground_truth 含表头外列 "
            f"source={invalid_sources} target={invalid_targets}"
        )
    return {
        "source_columns": len(source_columns),
        "target_columns": len(target_columns),
        "source_fields": len(source_columns),
        "positive_fields": positive,
        "no_match_fields": no_match,
        "invalid_matches": {
            "source_not_in_header": invalid_sources,
            "target_not_in_header": invalid_targets,
        },
    }


def _read_columns(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration as exc:
            raise ValueError(f"{path} 为空") from exc
    columns = []
    seen = set()
    for raw in header:
        name = _clean(raw)
        if not name or name in seen:
            continue
        seen.add(name)
        columns.append(name)
    if not columns:
        raise ValueError(f"{path} 没有列名")
    return columns


def _read_matches(ground_truth: dict, source_columns: list[str], target_columns: list[str]) -> dict[str, str]:
    matches: dict[str, str] = {}
    source_set = set(source_columns)
    target_set = set(target_columns)
    for item in ground_truth.get("matches") or []:
        source = _clean(item.get("source_column"))
        target = _clean(item.get("target_column"))
        if not source or not target:
            continue
        if source in source_set and target in target_set:
            if source in matches:
                raise ValueError(f"ground_truth 对源字段 {source!r} 有多条匹配，top-1 金标不唯一")
            matches[source] = target
    return matches


def _read_samples(path: Path, columns: list[str]) -> dict[str, list[str]]:
    _raise_csv_field_limit()
    samples: dict[str, list[str]] = {name: [] for name in columns}
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        reader = csv.reader(handle)
        next(reader, None)
        for _ in range(SAMPLE_SCAN_ROWS):
            try:
                row = next(reader)
            except StopIteration:
                break
            for index, name in enumerate(columns):
                if len(samples[name]) >= SAMPLES_PER_COLUMN:
                    continue
                value = row[index] if index < len(row) else ""
                value = _sample(value)
                if value and value not in samples[name]:
                    samples[name].append(value)
    return samples


def _raise_csv_field_limit() -> None:
    limit = sys.maxsize
    while True:
        try:
            csv.field_size_limit(limit)
            return
        except OverflowError:
            limit //= 10


def _sample(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "")
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > SAMPLE_MAX_CHARS:
        text = text[: SAMPLE_MAX_CHARS - 1] + "…"
    return text


def _clean(value) -> str:
    if value is None:
        return ""
    return unicodedata.normalize("NFKC", str(value)).strip()


def _dims(value) -> int | None:
    if isinstance(value, (list, tuple)) and value:
        try:
            return int(value[0])
        except (TypeError, ValueError):
            return None
    return None


def _split_counts(ctx) -> dict:
    counts = {
        split: {"fields": 0, "positive": 0, "no_match": 0}
        for split in SPLITS
    }
    for split in SPLITS:
        for item in ctx.cases[split]:
            expected = (item.get("gold") or {}).get("expected") or {}
            counts[split]["fields"] += 1
            if expected.get("target_field"):
                counts[split]["positive"] += 1
            else:
                counts[split]["no_match"] += 1
    return counts
