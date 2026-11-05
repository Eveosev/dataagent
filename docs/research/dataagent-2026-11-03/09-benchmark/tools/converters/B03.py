"""B03：字段抽取与锚点。

来源：ExtractBench（llamaindex/ExtractBench）：1,200+ 企业文档（10-K/13F/保险/表单），
每份文档给 JSON Schema（字段含 description 与 `[no-anchor]` 标记）、抽取规则与金标输出。

用例形状：PDF + 字段 Schema + 规则 → 结构化 JSON。判分按字段级 F1 与锚点命中：
- `[no-anchor]` 字段在文档里没有显式标签，需靠上下文推断；
- 锚点字段要求值与其印刷标签同时定位正确。

PDF 走 bench:// 引用，不复制进 docs；Schema 与规则落 fixtures。
"""
from __future__ import annotations

import hashlib
import json
import re

FILES = ("short.jsonl", "medium.jsonl", "long.jsonl")


def _leaf_count(schema: dict) -> int:
    if not isinstance(schema, dict):
        return 0
    if "properties" in schema:
        return sum(_leaf_count(v) for v in (schema.get("properties") or {}).values())
    if "items" in schema:
        return _leaf_count(schema.get("items"))
    if any(k in schema for k in ("anyOf", "oneOf", "allOf")):
        return sum(_leaf_count(x) for k in ("anyOf", "oneOf", "allOf") for x in schema.get(k) or [])
    return 1


def _anchored_fields(schema, prefix="") -> tuple[int, int]:
    """返回（锚点字段数, 无锚点字段数）。"""
    anchored = noanchor = 0
    if not isinstance(schema, dict):
        return 0, 0
    props = schema.get("properties") or {}
    for name, sub in props.items():
        if not isinstance(sub, dict):
            continue
        desc = str(sub.get("description") or "")
        if "[no-anchor]" in desc:
            noanchor += 1
        elif desc:
            anchored += 1
        a, b = _anchored_fields(sub, f"{prefix}.{name}")
        anchored += a
        noanchor += b
    if isinstance(schema.get("items"), dict):
        a, b = _anchored_fields(schema["items"], f"{prefix}[]")
        anchored += a
        noanchor += b
    return anchored, noanchor


PAGE_RE = re.compile(r"(?:page|p\.)\s*(\d+)", re.I)


def _page_map(schema, prefix="") -> dict:
    """从字段 description 里的 "page N" 提取字段 → 页码；没有页码提示的字段不进金标。"""
    out = {}
    if not isinstance(schema, dict):
        return out
    for name, sub in (schema.get("properties") or {}).items():
        if not isinstance(sub, dict):
            continue
        path = f"{prefix}.{name}" if prefix else str(name)
        match = PAGE_RE.search(str(sub.get("description") or ""))
        if match:
            out[path] = int(match.group(1))
        out.update(_page_map(sub, path))
    if isinstance(schema.get("items"), dict):
        out.update(_page_map(schema["items"], prefix + "[]"))
    return out


def _norm_token(text) -> str:
    return re.sub(r"\s+", "", str(text)).lower()


def _cord_spans(parsed: dict, fields: dict) -> list:
    """把 CORD 的 OCR 词序列对齐到字段值，产出词级证据片段。"""
    words = []
    for line in parsed.get("valid_line") or []:
        for word in line.get("words") or []:
            if word.get("text"):
                words.append(word["text"])
    tokens = [_norm_token(w) for w in words]
    spans = []
    for field, value in fields.items():
        if value is None or str(value).strip() == "":
            continue
        target = _norm_token(value)
        if not target:
            continue
        hit = None
        for i in range(len(tokens)):
            acc = ""
            for j in range(i, min(i + 6, len(tokens))):
                acc += tokens[j]
                if acc == target:
                    hit = (i, j)
                    break
                if len(acc) > len(target) + 2:
                    break
            if hit:
                break
        if hit:
            i, j = hit
            spans.append({"field": field, "text": " ".join(words[i:j + 1]), "page": 1})
    return spans


def build(ctx) -> dict:
    ctx.source("extractbench")
    n = 0
    per = {}
    for fname in FILES:
        path = ctx.raw_path("extractbench", fname)
        if not path.exists():
            continue
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                rows.append(json.loads(line))
        per[fname] = len(rows)
        for rec in rows:
            pdf = rec.get("pdf")
            schema_text = rec.get("data_schema") or "{}"
            expected_text = rec.get("expected_output") or "{}"
            if not pdf:
                continue
            try:
                schema = json.loads(schema_text)
            except json.JSONDecodeError:
                schema = {}
            try:
                expected = json.loads(expected_text)
            except json.JSONDecodeError:
                expected = expected_text
            anchored, noanchor = _anchored_fields(schema)
            pages = _page_map(schema)
            n += 1
            sref = ctx.fixture(f"eb-{rec.get('id','x').replace('/','-')}-schema.json", json.dumps(schema, ensure_ascii=False, indent=2))
            rref = ctx.fixture(
                f"eb-{rec.get('id','x').replace('/','-')}-rules.md",
                f"# 抽取规则\n\n{rec.get('field_rules') or ''}\n\n## 重复结构\n\n{rec.get('repeated_structure') or ''}\n",
            )
            ctx.add(
                source="eb",
                seq=n,
                inputs=[
                    {"kind": "file", "ref": ctx.bench("extractbench", pdf), "digest": None},
                    {"kind": "schema", "ref": sref, "digest": None},
                    {"kind": "rules", "ref": rref, "digest": None},
                ],
                expected={
                    "kind": "json",
                    "schema_ref": sref,
                    "value": expected,
                    "anchored_fields": anchored,
                    "no_anchor_fields": noanchor,
                    **({"pages": pages, "evidence_gold": {"source": "schema-description", "version": 1}} if pages else {}),
                },
                evidence=[ctx.bench("extractbench", pdf), sref, rref],
                tags=[
                    "extractbench",
                    rec.get("category") or fname.replace(".jsonl", ""),
                    *[f"tag:{t}" for t in (rec.get("tags") or [])],
                    f"fields:{_leaf_count(schema)}",
                ],
                gold={
                    "source": "llamaindex/ExtractBench",
                    "id": rec.get("id"),
                    "pdf": pdf,
                    "schema": schema,
                    "expected": expected,
                    "field_rules": rec.get("field_rules"),
                    "repeated_structure": rec.get("repeated_structure"),
                    "anchored_fields": anchored,
                    "no_anchor_fields": noanchor,
                },
                split_key=f"eb:{rec.get('id')}",
            )

    n += _cord(ctx, n)
    n += _funsd(ctx, n)

    return {
        "policy": "ExtractBench 三档全量 + CORD-v2 按 25% 抽样 + FUNSD 全量；PDF/图片走 bench://，Schema/规则/指令落 fixtures。split 按文档 id 哈希。",
        "extra": {
            "coverage": {
                "covered_metrics": ["value_f1", "record_completeness", "hallucination_rate", "evidence_span_f1", "evidence_page_f1"],
                "partial_metrics": ["no_anchor_recall"],
                "missing_metrics": ["table_row_alignment"],
                "note": "证据金标为派生：CORD 用 OCR 词序列把字段值对齐成词级 span（单页，page=1）；ExtractBench 从 schema description 的 'page N' 提取字段页码（约 14% 字段带页码提示，其余字段不进 page 分母）；FUNSD 只有 bbox，未产出 span/page。DocILE 因 gated 已用 CORD-v2 + FUNSD 替代。",
            },
            "counts": per,
        },
    }


def _flatten(obj, prefix="") -> dict:
    out = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.update(_flatten(v, f"{prefix}.{k}" if prefix else str(k)))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.update(_flatten(v, f"{prefix}[{i}]"))
    else:
        out[prefix] = obj
    return out


def _cord(ctx, start: int) -> int:
    base = ctx.raw_path("cord-v2")
    files = sorted((base / "data").glob("*.parquet"))
    if not files:
        ctx.notes.append("CORD-v2 尚未下载")
        return 0
    import pyarrow.parquet as pq

    ctx.source("cord-v2")
    n = 0
    for path in files:
        split = path.name.split("-")[0]
        rows = pq.read_table(path).to_pylist()
        for idx, rec in enumerate(rows):
            gt = rec.get("ground_truth")
            img = rec.get("image") or {}
            data = img.get("bytes") if isinstance(img, dict) else None
            if not gt or not data:
                continue
            # CORD 有 1,000 张，按 25% 抽样，避免压过 ExtractBench 的复杂业务文档；全量仍在原始目录
            if int(hashlib.sha1(f"cord:{split}:{idx}".encode()).hexdigest()[:8], 16) % 100 >= 25:
                continue
            n += 1
            rel_img = f"images/{split}-{idx:05d}.png"
            dest = base / rel_img
            if not dest.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
            try:
                parsed = json.loads(gt) if isinstance(gt, str) else gt
            except json.JSONDecodeError:
                continue
            gt_parse = parsed.get("gt_parse") if isinstance(parsed, dict) else None
            if not isinstance(gt_parse, dict):
                continue
            fields = _flatten(gt_parse)
            spans = _cord_spans(parsed, fields)
            iref = ctx.fixture(
                f"cord-{split}-{idx:05d}-task.md",
                "# 任务\n\n从这张收据图片中抽取全部字段，按 JSON 输出。\n\n"
                "## 字段结构\n\n- menu：菜品列表（nm 名称、cnt 数量、price 单价、itemsubtotal 小计）\n"
                "- sub_total：subtotal_price / discount_price / tax_price\n- total：total_price 等\n"
                "- 其余键按图片内容抽取\n\n## 要求\n\n- 金额保留原样（含千分位与小数点写法）\n- 缺失字段省略，不要编造\n",
            )
            ctx.add(
                source="cord",
                seq=start + n,
                inputs=[
                    {"kind": "image", "ref": ctx.bench("cord-v2", rel_img), "digest": None},
                    {"kind": "instruction", "ref": iref, "digest": None},
                ],
                expected={
                    "kind": "json",
                    "value": gt_parse,
                    "fields": fields,
                    "anchored_fields": 0,
                    "no_anchor_fields": len(fields),
                    "spans": spans,
                    "pages": {field: 1 for field in fields},
                    "evidence_gold": {"source": "cord-valid-line", "version": 1},
                },
                evidence=[ctx.bench("cord-v2", rel_img), iref],
                tags=["cord-v2", split, "doc:receipt", f"fields:{len(fields)}"],
                gold={"source": "naver-clova-ix/cord-v2", "split": split, "index": idx, "gt_parse": gt_parse},
                split_key=f"cord:{split}:{idx}",
            )
    return n


FUNSD_LABELS = {0: "O", 1: "B-HEADER", 2: "I-HEADER", 3: "B-QUESTION", 4: "I-QUESTION", 5: "B-ANSWER", 6: "I-ANSWER"}


def _funsd(ctx, start: int) -> int:
    base = ctx.raw_path("funsd")
    files = sorted((base / "data").glob("*.parquet"))
    if not files:
        ctx.notes.append("FUNSD 尚未下载")
        return 0
    import pyarrow.parquet as pq

    ctx.source("funsd")
    n = 0
    for path in files:
        split = path.name.split("-")[0]
        rows = pq.read_table(path).to_pylist()
        for rec in rows:
            words = rec.get("words") or []
            boxes = rec.get("bboxes") or []
            tags = rec.get("ner_tags") or []
            img = rec.get("image") or {}
            data = img.get("bytes") if isinstance(img, dict) else None
            if not words or not boxes or not data:
                continue
            n += 1
            doc_id = rec.get("id")
            rel_img = f"images/{split}-{doc_id}.png"
            dest = base / rel_img
            if not dest.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
            # 按 BIO 把单词合并成实体（HEADER/QUESTION/ANSWER）
            entities = []
            cur = None
            for word, box, tag in zip(words, boxes, tags):
                label = FUNSD_LABELS.get(tag, "O")
                base_label = label[2:] if label.startswith(("B-", "I-")) else None
                if label.startswith("B-") or (label.startswith("I-") and cur is None) or (base_label and cur and cur["label"] != base_label):
                    if cur:
                        entities.append(cur)
                    cur = {"label": base_label, "text": word, "box": box}
                elif label.startswith("I-") and cur:
                    cur["text"] += " " + word
                    b = cur["box"]
                    cur["box"] = [min(b[0], box[0]), min(b[1], box[1]), max(b[2], box[2]), max(b[3], box[3])]
                elif label == "O":
                    if cur:
                        entities.append(cur)
                        cur = None
            if cur:
                entities.append(cur)
            answers = [e for e in entities if e["label"] == "ANSWER"]
            iref = ctx.fixture(
                f"funsd-{split}-{doc_id}-task.md",
                "# 任务\n\n从这张表单图片中抽取键值对，输出实体列表：\n\n"
                "- `label`：HEADER / QUESTION / ANSWER\n- `text`：实体文本（按阅读顺序合并单词）\n"
                "- `box`：`[x0, y0, x1, y1]` 像素坐标\n\n## 要求\n\n- 不合并不同实体\n- 坐标以图片左上角为原点\n",
            )
            ctx.add(
                source="funsd",
                seq=start + n,
                inputs=[
                    {"kind": "image", "ref": ctx.bench("funsd", rel_img), "digest": None},
                    {"kind": "instruction", "ref": iref, "digest": None},
                ],
                expected={
                    "kind": "entities",
                    "entities": entities,
                    "answer_count": len(answers),
                    "anchored_fields": len(answers),
                    "no_anchor_fields": 0,
                },
                evidence=[ctx.bench("funsd", rel_img), iref],
                tags=["funsd", split, "doc:form", f"answers:{len(answers)}"],
                gold={"source": "nielsr/funsd", "split": split, "id": doc_id, "entities": entities},
                split_key=f"funsd:{split}:{doc_id}",
            )
    return n
