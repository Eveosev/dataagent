"""B16：多源对齐与实体解析。

来源（Leipzig DBS group，CC BY 4.0；DeepMatcher SIGMOD 2018 使用的同一批基准集）：
- DBLP-ACM：文献题录，1:1，结构化。
- Amazon-Google：商品，含多对一，字段与噪声更接近真实脏数据。
- Abt-Buy：商品，文本描述为主。

用例形状：一条左表记录 + 5–8 条右表候选 → 与左记录指向同一实体的候选实体对。
金标只来自数据集自带的 perfectMapping；候选里的非金标记录按 gold mapping 的排他性
视为非匹配（与 DeepMatcher / Magellan 的成对评测口径一致），不生成、不改写金标。

切分：按金标连通分量做固定 sha256 60/20/20，保证同一实体的记录不跨 split；
候选只从同 split 的右表记录里取，避免候选跨 split 泄漏。
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import unicodedata
from pathlib import Path

MAX_DISTRACTORS = 4
SPLITS = ("development", "regression", "unseen_acceptance")
# 与 tools/build_cases.py 的 split_of 保持一致；改一处必须同步另一处。
RATIOS = {"development": 60, "regression": 20, "unseen_acceptance": 20}

SOURCES = [
    {
        "id": "leipzig-dblp-acm",
        "slug": "dblp",
        "label": "DBLP → ACM",
        "left_file": "DBLP2.csv",
        "right_file": "ACM.csv",
        "mapping_file": "DBLP-ACM_perfectMapping.csv",
        "left_col": "idDBLP",
        "right_col": "idACM",
        "name_fields": ("title",),
        "domain": "bibliographic",
    },
    {
        "id": "leipzig-amazon-google",
        "slug": "amazon",
        "label": "Amazon → Google Products",
        "left_file": "Amazon.csv",
        "right_file": "GoogleProducts.csv",
        "mapping_file": "Amzon_GoogleProducts_perfectMapping.csv",
        "left_col": "idAmazon",
        "right_col": "idGoogleBase",
        "name_fields": ("title", "name"),
        "domain": "product",
    },
    {
        "id": "leipzig-abt-buy",
        "slug": "abt",
        "label": "Abt → Buy",
        "left_file": "Abt.csv",
        "right_file": "Buy.csv",
        "mapping_file": "abt_buy_perfectMapping.csv",
        "left_col": "idAbt",
        "right_col": "idBuy",
        "name_fields": ("name",),
        "domain": "product",
    },
]


def build(ctx) -> dict:
    counts = {}
    for spec in SOURCES:
        source_rec = ctx.source(spec["id"])
        if not source_rec.get("revision"):
            fetch_path = ctx.raw_path(spec["id"], "FETCH.json")
            if fetch_path.exists():
                fetched = json.loads(fetch_path.read_text(encoding="utf-8"))
                source_rec["revision"] = fetched.get("revision_requested")
        counts[spec["id"]] = _build_source(ctx, spec)
    return {
        "policy": (
            "金标只取数据集 perfectMapping；按金标连通分量做固定 sha256 60/20/20；"
            "每条用例取同 split 内与左记录最相似的非金标右记录 4 条作候选负例，"
            "候选顺序按哈希固定，避免金标总在首位。"
        ),
        "extra": {
            "coverage": {
                "covered_metrics": ["entity_pair_f1", "false_merge_rate"],
                "partial_metrics": [],
                "missing_metrics": ["conflict_retention_rate"],
                "note": (
                    "三个源只标注实体对，未标注跨源同对象的值冲突，冲突保留率按缺口记录；"
                    "非金标候选按数据集 gold mapping 的排他性视为非匹配，这是成对实体匹配评测的通行口径。"
                ),
                "license_audit": [
                    {
                        "candidate": "DeepMatcher UW-Madison Datasets.md 镜像",
                        "license": "未声明数据集许可（仓库 LICENSE 为 BSD-3-Clause，只覆盖代码）",
                        "decision": "不采用镜像；改用同一批数据的 Leipzig 原始发布（CC BY 4.0）",
                    },
                    {
                        "candidate": "Magellan GitHub",
                        "license": "MIT（当前仓库只含项目站点代码）",
                        "decision": "不采用；仓库不再分发基准数据，数据指向同一批 DeepMatcher/Leipzig 来源",
                    },
                    {
                        "candidate": "Fodors-Zagats / iTunes-Amazon / Walmart-Amazon / BeerAdvo-RateBeer / Company",
                        "license": "原始站点与 DeepMatcher 镜像均未声明可再分发许可",
                        "decision": "舍弃",
                    },
                    {
                        "candidate": "DBLP-ACM / Amazon-Google / Abt-Buy",
                        "license": "CC BY 4.0（Leipzig DBS group，2019-01 声明）",
                        "decision": "采用；manifest 记 attribution",
                    },
                ],
            },
            "counts": counts,
        },
    }


def _build_source(ctx, spec: dict) -> dict:
    base = ctx.raw_path(spec["id"])
    left_path = _locate(base, spec["left_file"])
    right_path = _locate(base, spec["right_file"])
    mapping_path = _locate(base, spec["mapping_file"])

    left = _read_table(left_path)
    right = _read_table(right_path)
    pairs, skipped = _read_mapping(mapping_path, spec, left, right)

    parent = _union_find(pairs)
    components: dict[str, list[str]] = {}
    for node in parent:
        components.setdefault(_find(parent, node), []).append(node)
    component_key = {
        root: f"{spec['id']}:component:" + "|".join(sorted(nodes))
        for root, nodes in components.items()
    }

    right_split = {}
    for rid in right:
        node = "R:" + rid
        if node in parent:
            right_split[rid] = _split_of(component_key[_find(parent, node)])
        else:
            right_split[rid] = _split_of(f"{spec['id']}:right:{rid}")

    pools = {split: [] for split in SPLITS}
    for rid in sorted(right):
        pools[right_split[rid]].append(rid)

    right_tokens = {rid: _tokens(_record_name(right[rid], spec["name_fields"])) for rid in right}
    mapping: dict[str, list[str]] = {}
    for left_id, right_id in pairs:
        mapping.setdefault(left_id, []).append(right_id)
    for left_id in mapping:
        mapping[left_id] = sorted(set(mapping[left_id]))

    split_counts = {split: 0 for split in SPLITS}
    seq = 0
    for left_id in sorted(mapping, key=lambda x: hashlib.sha256(f"{spec['id']}:{x}".encode()).hexdigest()):
        gold_rights = mapping[left_id]
        root = _find(parent, "L:" + left_id)
        split_key = component_key[root]
        split = _split_of(split_key)
        same_component_rights = {node[2:] for node in components[root] if node.startswith("R:")}

        left_name = _tokens(_record_name(left[left_id], spec["name_fields"]))
        scored = []
        for right_id in pools[split]:
            if right_id in same_component_rights:
                continue
            score = _jaccard(left_name, right_tokens[right_id])
            # 近乎同名的候选很可能是未进 gold mapping 的重复记录，不当负例。
            if score >= 0.95:
                continue
            tie = hashlib.sha256(f"{spec['id']}:{left_id}:{right_id}".encode()).hexdigest()
            scored.append((-score, tie, right_id))
        scored.sort()
        distractors = [item[2] for item in scored[:MAX_DISTRACTORS]]
        candidates = sorted(
            set(gold_rights) | set(distractors),
            key=lambda x: hashlib.sha256(f"{spec['id']}:candidate:{left_id}:{x}".encode()).hexdigest(),
        )

        seq += 1
        case_id = f"B16-{spec['slug']}-{seq:04d}"
        fixture = {
            "task": "entity_alignment",
            "source": spec["label"],
            "instruction": (
                "左侧记录与右侧候选来自两个数据源。找出右侧候选中与左侧记录指向同一实体的记录，"
                "返回实体对；没有匹配时返回空数组，不要猜测。"
            ),
            "left": {"id": left_id, **left[left_id]},
            "right_candidates": [{"id": rid, **right[rid]} for rid in candidates],
        }
        ref = ctx.fixture(f"{case_id}.json", json.dumps(fixture, ensure_ascii=False, indent=2) + "\n")
        expected_pairs = [{"left_id": left_id, "right_id": rid} for rid in gold_rights]
        ctx.add(
            source=spec["slug"],
            seq=seq,
            inputs=[{"kind": "record_pair", "ref": ref, "digest": None}],
            expected={
                "kind": "entity_pairs",
                "source_dataset": spec["id"],
                "license": "CC BY 4.0",
                "left_id": left_id,
                "candidate_ids": candidates,
                "pairs": expected_pairs,
            },
            evidence=[ref],
            tags=[
                "entity-matching",
                f"source:{spec['slug']}",
                f"domain:{spec['domain']}",
                f"gold:{len(gold_rights)}",
                f"candidates:{len(candidates)}",
            ],
            gold={
                "source": spec["id"],
                "source_label": spec["label"],
                "license": "CC BY 4.0",
                "license_url": "https://creativecommons.org/licenses/by/4.0/",
                "attribution": "Leipzig DBS group; Köpcke et al., VLDB 2010",
                "left_id": left_id,
                "gold_right_ids": gold_rights,
                "candidate_ids": candidates,
                "distractor_ids": distractors,
                "negative_policy": "候选集中除 gold_right_ids 外的记录按数据集 gold mapping 的排他性视为非匹配",
            },
            split_key=split_key,
        )
        split_counts[split] += 1

    ctx.notes.append(
        f"{spec['id']}: left={len(left)} right={len(right)} pairs={len(pairs)} "
        f"skipped_pairs={skipped} cases={seq}"
    )
    return {
        "left_records": len(left),
        "right_records": len(right),
        "gold_pairs": len(pairs),
        "skipped_pairs": skipped,
        "cases": seq,
        "splits": split_counts,
    }


def _locate(base: Path, filename: str) -> Path:
    direct = base / filename
    if direct.exists():
        return direct
    hits = sorted(base.rglob(filename))
    if not hits:
        raise FileNotFoundError(f"{base} 下找不到 {filename}")
    return hits[0]


def _decode(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def _read_table(path: Path) -> dict[str, dict]:
    rows = {}
    for row in csv.DictReader(io.StringIO(_decode(path.read_bytes()))):
        rid = _clean_id(row.get("id"))
        if not rid:
            continue
        rows[rid] = {key: value for key, value in row.items() if key != "id" and value not in (None, "")}
    return rows


def _read_mapping(path: Path, spec: dict, left: dict, right: dict) -> tuple[list[tuple[str, str]], int]:
    pairs = []
    skipped = 0
    for row in csv.DictReader(io.StringIO(_decode(path.read_bytes()))):
        left_id = _clean_id(row.get(spec["left_col"]))
        right_id = _clean_id(row.get(spec["right_col"]))
        if left_id in left and right_id in right:
            pairs.append((left_id, right_id))
        else:
            skipped += 1
    return pairs, skipped


def _clean_id(value) -> str:
    if value is None:
        return ""
    return unicodedata.normalize("NFKC", str(value)).strip()


def _record_name(record: dict, fields: tuple[str, ...]) -> str:
    for field in fields:
        value = record.get(field)
        if value:
            return str(value)
    return ""


def _tokens(text: str) -> frozenset[str]:
    normalized = unicodedata.normalize("NFKC", text or "").lower()
    return frozenset(re.findall(r"[a-z0-9]+", normalized))


def _jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _split_of(key: str) -> str:
    h = int(hashlib.sha256(key.encode()).hexdigest()[:8], 16) % 100
    if h < RATIOS["development"]:
        return "development"
    if h < RATIOS["development"] + RATIOS["regression"]:
        return "regression"
    return "unseen_acceptance"


def _union_find(pairs: list[tuple[str, str]]) -> dict[str, str]:
    parent: dict[str, str] = {}

    def find(node: str) -> str:
        parent.setdefault(node, node)
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    for left_id, right_id in pairs:
        left_node, right_node = "L:" + left_id, "R:" + right_id
        left_root, right_root = find(left_node), find(right_node)
        if left_root != right_root:
            parent[right_root] = left_root
    return parent


def _find(parent: dict[str, str], node: str) -> str:
    parent.setdefault(node, node)
    while parent[node] != node:
        parent[node] = parent[parent[node]]
        node = parent[node]
    return node
