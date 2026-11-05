"""B05：指标定义与语义查询编译。

来源：
- BIRD mini-dev（birdsql/bird_mini_dev）：500 题，question + evidence + 金标 SQL + 库 schema。
- data.world CWD（datadotworld/cwd-benchmark-data）：保险领域 43 个 inquiry，每个同时给 SQL 与 SPARQL。
- Spider 2.0 lite（xlangai/spider2-lite）：企业级查询，仅存问题与金标 SQL（数据库不进库）。

用例形状：问题 + 库 schema（落 fixtures） → 金标 SQL。CWD 的 SPARQL 与 SQL 成对，用于口径一致率。
"""
from __future__ import annotations

import hashlib
import json
import re


def build(ctx) -> dict:
    counts = {}
    counts["bird"] = _bird(ctx)
    counts["cwd"] = _cwd(ctx)
    counts["spider2"] = _spider2(ctx)
    counts["beaver"] = _beaver(ctx)
    return {
        "policy": "四类来源合计入库（BEAVER 按 8% 确定性抽样，全量见 available）；BIRD 只带 schema 不带库，CWD 带完整 CSV 与 DDL，Spider2 lite 与 BEAVER 只有查询与表线索。split 按题目 id 哈希。",
        "extra": {
            "coverage": {
                "covered_metrics": ["execution_accuracy", "unexpressible_refusal_rate"],
                "partial_metrics": ["metric_definition_consistency"],
                "note": "执行准确率需本地起库：CWD 可用 CSV 建库；BEAVER 已取 beaver_db.zip（dw/nova/neutron 的 MySQL dump，解压 2.1 GB），装载后可按 SQL 执行比对；BIRD 与 Spider2 的库仍需另行申请。BEAVER 全量 7,978 条按 8% 抽样 592 条入库，全量留在原始目录；任务卡已并入 beaver-table 的列名/类型/示例行（381 张表），join_keys 与 domain_knowledge 用于口径与连接语义判分",
            },
            "counts": counts,
        },
    }


def _bird(ctx) -> int:
    ctx.source("bird-mini-dev")
    path = ctx.raw_path("bird-mini-dev", "data", "mini_dev_sqlite.jsonl")
    if not path.exists():
        ctx.notes.append("缺少 BIRD mini sqlite jsonl")
        return 0
    schemas = {}
    sp = ctx.raw_path("bird-mini-dev", "baseline_inference", "schemas", "sqlite.json")
    if sp.exists():
        raw = json.loads(sp.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            schemas = raw
        else:
            for item in raw:
                schemas[item.get("db_id")] = item.get("schema") or item.get("ddl")

    n = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        n += 1
        db = rec.get("db_id")
        schema = schemas.get(db) or ""
        ref = ctx.fixture(
            f"bird-{rec.get('question_id')}-{db}.md",
            f"# BIRD mini / {db}\n\n## 问题\n\n{rec.get('question')}\n\n## 提示\n\n{rec.get('evidence') or ''}\n\n## Schema\n\n{schema}\n",
        )
        ctx.add(
            source="bird",
            seq=n,
            inputs=[
                {"kind": "question", "ref": ref, "digest": None},
                {"kind": "corpus", "ref": ctx.bench("bird-mini-dev", "data", "mini_dev_sqlite.jsonl"), "digest": None},
            ],
            expected={"kind": "sql", "sql": rec.get("SQL"), "db_id": db, "evidence": rec.get("evidence")},
            evidence=[f"{ref}#schema", ctx.bench("bird-mini-dev", "data", "mini_dev_sqlite.jsonl")],
            tags=["bird", "sqlite", db],
            gold={
                "source": "birdsql/bird_mini_dev",
                "question_id": rec.get("question_id"),
                "question": rec.get("question"),
                "evidence": rec.get("evidence"),
                "gold_sql": rec.get("SQL"),
                "db_id": db,
            },
            split_key=f"bird:{db}:{rec.get('question_id')}",
        )
    return n


_TTL_BLOCK = re.compile(r"\n(dwt:[A-Za-z0-9_-]+)\s*\n(.*?)(?=\ndwt:|\Z)", re.S)
_TTL_PROP = re.compile(r"(\S+?)\s+(\"(?:[^\"\\]|\\.)*\"|[^;\s]+(?:\s*,\s*[^;\s]+)*)\s*[;\\.]", re.S)


def _parse_ttl(path):
    text = path.read_text(encoding="utf-8")
    blocks = {}
    for ident, body in _TTL_BLOCK.findall(text):
        props = {}
        for key, value in _TTL_PROP.findall(body):
            props.setdefault(key, value)
        blocks[ident] = props

    def lit(v):
        if v and v.startswith('"') and v.endswith('"'):
            return v[1:-1].replace("\\n", "\n").replace('\\"', '"')
        return v

    inquiries = []
    for ident, props in blocks.items():
        if props.get("rdf:type") != "QandA:Inquiry":
            continue
        expects = [x.strip() for x in (props.get("QandA:expects") or "").split(",") if x.strip()]
        sqls, sparqls = [], []
        for e in expects:
            q = blocks.get(e, {})
            qtype = q.get("rdf:type")
            body = lit(q.get("QandA:queryText"))
            if qtype == "dwt:SqlQuery":
                sqls.append(body)
            elif qtype == "dwt:SparqlQuery":
                sparqls.append(body)
        inquiries.append(
            {
                "id": ident.replace("dwt:", ""),
                "prompt": lit(props.get("QandA:prompt")),
                "sql": sqls,
                "sparql": sparqls,
            }
        )
    return inquiries


def _cwd(ctx) -> int:
    ctx.source("cwd")
    ttl = ctx.raw_path("cwd", "ACME_Insurance", "investigation", "acme-benchmark.ttl")
    if not ttl.exists():
        ctx.notes.append("缺少 CWD inquiry TTL")
        return 0
    ddl = ctx.raw_path("cwd", "ACME_Insurance", "DDL", "ACME_small.ddl")
    ddl_ref = ctx.fixture("cwd-acme.ddl", ddl.read_text(encoding="utf-8")) if ddl.exists() else None

    n = 0
    for inq in _parse_ttl(ttl):
        n += 1
        inputs = []
        if ddl_ref:
            inputs.append({"kind": "schema", "ref": ddl_ref, "digest": None})
        inputs.append({"kind": "data", "ref": ctx.bench("cwd", "ACME_Insurance", "data"), "digest": None})
        ctx.add(
            source="cwd",
            seq=n,
            inputs=inputs,
            expected={
                "kind": "query",
                "question": inq["prompt"],
                "sql": inq["sql"][0] if inq["sql"] else None,
                "alternate_sql": inq["sql"][1:],
                "sparql": inq["sparql"],
            },
            evidence=[ctx.bench("cwd", "ACME_Insurance", "data")],
            tags=["cwd", "insurance", "bilingual-query"],
            gold={
                "source": "datadotworld/cwd-benchmark-data",
                "inquiry_id": inq["id"],
                "prompt": inq["prompt"],
                "sql": inq["sql"],
                "sparql": inq["sparql"],
            },
        )
    return n


def _spider2(ctx) -> int:
    path = ctx.raw_path("spider2-lite", "spider2-lite.jsonl")
    if not path.exists():
        ctx.notes.append("Spider2 lite 尚未下载")
        return 0
    ctx.source("spider2-lite")
    n = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        n += 1
        q = rec.get("question") or rec.get("instruction") or ""
        qref = ctx.fixture(f"spider2-{rec.get('instance_id') or n}.md", q)
        ctx.add(
            source="spider2",
            seq=n,
            inputs=[
                {"kind": "question", "ref": qref, "digest": None},
                {"kind": "corpus", "ref": ctx.bench("spider2-lite", "spider2-lite.jsonl"), "digest": None},
            ],
            expected={
                "kind": "sql",
                "instance_id": rec.get("instance_id"),
                "sql": rec.get("sql") or rec.get("query"),
                "db": rec.get("db") or rec.get("db_id"),
            },
            evidence=[qref],
            tags=["spider2", str(rec.get("db") or "unknown")],
            gold={"source": "xlangai/spider2-lite", "raw": rec},
            split_key=f"spider2:{rec.get('instance_id')}",
        )
    return n


def _beaver(ctx) -> int:
    """BEAVER：私有数仓（812 表）上的语义查询，带 join_keys / column_mapping / domain_knowledge。"""
    base = ctx.raw_path("beaver")
    files = sorted((base / "data").glob("*.parquet"))
    if not files:
        ctx.notes.append("BEAVER 尚未下载（HF gated，需先接受条款）")
        return 0
    import pyarrow.parquet as pq

    table_meta = _beaver_tables(ctx)
    ctx.source("beaver")
    n = 0
    for path in files:
        split = path.name.split("-")[0]
        rows = pq.read_table(path).to_pylist()
        for rec in rows:
            question = rec.get("question")
            sql = rec.get("sql")
            if not question or not sql:
                continue
            # 7,978 条按 8% 确定性抽样，避免压过 BIRD/CWD/Spider2；全量留在 manifest.build.available
            if int(hashlib.sha1(str(rec.get("id") or question).encode()).hexdigest()[:8], 16) % 100 >= 8:
                continue
            n += 1
            schema_block = _beaver_schema_block(rec, table_meta)
            qref = ctx.fixture(
                f"beaver-{split}-{n:05d}-task.md",
                f"# 查询任务（{split}）\n\n## 问题\n\n{question}\n\n"
                f"## 库\n\n{rec.get('db') or ''}\n\n"
                f"## 涉及表\n\n{rec.get('tables') or ''}\n\n"
                f"## 连接键\n\n{rec.get('join_keys') or ''}\n\n"
                f"## 列映射\n\n{rec.get('column_mapping') or ''}\n\n"
                f"## 领域知识\n\n{rec.get('domain_knowledge') or '无'}\n\n"
                f"{schema_block}"
                f"## 子问题\n\n{rec.get('sub_questions') or '无'}\n",
            )
            ctx.add(
                source="beaver",
                seq=n,
                inputs=[{"kind": "query", "ref": qref, "digest": None}],
                expected={
                    "kind": "sql",
                    "sql": sql,
                    "sub_sqls": rec.get("sub_sqls"),
                    "db": rec.get("db"),
                    "tables": rec.get("tables"),
                    "join_keys": rec.get("join_keys"),
                    "column_mapping": rec.get("column_mapping"),
                    "category": rec.get("category"),
                    "db_archive": "bench://beaver-table/beaver_db.zip" if (ctx.raw_path("beaver-table") / "beaver_db.zip").exists() else None,
                },
                evidence=[qref],
                tags=[
                    "beaver",
                    split,
                    str(rec.get("category") or "unknown"),
                    str(rec.get("detailed_category") or "unknown"),
                    "domain_knowledge" if rec.get("contains_domain_knowledge") else "no_domain_knowledge",
                ],
                gold={
                    "source": "beaverbench/beaver-query",
                    "id": rec.get("id"),
                    "db": rec.get("db"),
                    "question": question,
                    "sql": sql,
                    "tables": rec.get("tables"),
                    "join_keys": rec.get("join_keys"),
                    "column_mapping": rec.get("column_mapping"),
                    "domain_knowledge": rec.get("domain_knowledge"),
                    "sub_questions": rec.get("sub_questions"),
                    "sub_sqls": rec.get("sub_sqls"),
                    "category": rec.get("category"),
                    "detailed_category": rec.get("detailed_category"),
                },
                split_key=f"beaver:{rec.get('id') or n}",
            )
    return n


def _beaver_tables(ctx) -> dict:
    """beaver-table：db/table 的列名、类型、示例行；授权才可取，缺失时静默跳过。"""
    base = ctx.raw_path("beaver-table")
    files = sorted((base / "data").glob("*.parquet"))
    if not files:
        return {}
    import pyarrow.parquet as pq

    ctx.source("beaver-table")
    meta = {}
    for path in files:
        for rec in pq.read_table(path).to_pylist():
            db = rec.get("db")
            table = rec.get("table_name")
            if not db or not table:
                continue
            meta[(str(db), str(table))] = {
                "columns": rec.get("column_names"),
                "types": rec.get("column_types"),
                "example_rows": rec.get("example_rows"),
                "example_columns": rec.get("example_columns"),
            }
    return meta


def _beaver_schema_block(rec: dict, meta: dict) -> str:
    if not meta:
        return ""
    tables = rec.get("tables") or ""
    names = []
    for chunk in re.split(r"[,;\n]", str(tables)):
        name = chunk.strip().strip("`'\"").split(".")[-1]
        if name:
            names.append(name)
    db = str(rec.get("db") or "")
    lines = []
    for name in names:
        info = meta.get((db, name)) or next((v for (d, t), v in meta.items() if t == name), None)
        if not info:
            continue
        lines.append(f"### {name}\n\n- 列：{info.get('columns')}\n- 类型：{info.get('types')}\n- 示例：{str(info.get('example_rows'))[:400]}")
    if not lines:
        return ""
    return "## 表结构\n\n" + "\n\n".join(lines) + "\n\n"
