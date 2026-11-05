"""B14：数据建模与 ELT 管道。

来源：ELT-Bench（uiuc-kang-lab/ELT-Bench）：Snowflake / Redshift / Databricks 三个目标仓，
每个仓下若干数据源（movie、olympics、address…），给出源连接配置与目标模型规格（data_model.yaml）。

用例形状：源配置（config.yaml）+ 目标模型规格 → 期望的 staging/建模产物。
判分看产出的模型 schema 与列语义是否匹配 data_model.yaml；端到端跑数需要 Docker + Airbyte + 目标仓，
本轮只建「规格驱动」用例，端到端执行留给有基础设施的环境。

注意：ELT-Bench 的 data_model.yaml 本身是「需求规格」，不是参考答案实现；
本用例把它作为断言来源，gold 里同时存配置与规格，避免把需求当答案。
"""
from __future__ import annotations

import re

import yaml


def build(ctx) -> dict:
    ctx.source("elt-bench")
    base = ctx.raw_path("elt-bench", "elt-bench")
    if not base.exists():
        ctx.notes.append("ELT-Bench 仓内目录不存在")
        return {"policy": "", "extra": {}}

    n = 0
    per_wh = {}
    for wh_dir in sorted(p for p in base.iterdir() if p.is_dir()):
        warehouse = wh_dir.name
        per_wh[warehouse] = 0
        for pipe in sorted(p for p in wh_dir.iterdir() if p.is_dir()):
            cfg = pipe / "config.yaml"
            model = pipe / "data_model.yaml"
            if not cfg.exists() or not model.exists():
                continue
            n += 1
            per_wh[warehouse] += 1
            cfg_text = cfg.read_text(encoding="utf-8")
            model_text = model.read_text(encoding="utf-8")
            try:
                spec = yaml.safe_load(model_text) or {}
            except yaml.YAMLError:
                spec = {}
            models = spec.get("models") or []
            inputs = [
                {"kind": "config", "ref": ctx.fixture(f"elt-{warehouse}-{pipe.name}-config.yaml", cfg_text), "digest": None},
            ]
            ctx.add(
                source="elt",
                seq=n,
                inputs=inputs,
                expected={
                    "kind": "schema_spec",
                    "models": [
                        {"name": m.get("name"), "columns": [c.get("name") for c in (m.get("columns") or [])]}
                        for m in models
                    ],
                },
                evidence=[ctx.bench("elt-bench", "elt-bench", warehouse, pipe.name, "data_model.yaml")],
                tags=["elt-bench", warehouse, pipe.name, f"models:{len(models)}"],
                gold={
                    "source": "uiuc-kang-lab/ELT-Bench",
                    "warehouse": warehouse,
                    "pipeline": pipe.name,
                    "data_model": spec,
                    "config": cfg_text[:20000],
                },
                split_key=f"elt:{warehouse}:{pipe.name}",
            )

    if not n:
        ctx.notes.append("未找到 ELT 管道目录")
    return {
        "policy": "每个 (目标仓, 数据源) 一条用例；config 落 fixtures，规格留在 gold。split 按哈希。",
        "extra": {
            "coverage": {
                "covered_metrics": ["model_schema_match", "column_semantics_match"],
                "missing_metrics": ["pipeline_run_success", "data_freshness"],
                "note": "端到端跑通需要 Docker + Airbyte + Snowflake/Redshift/Databricks 凭证，本机不构建；Spider 2.0 的 dbt 任务（spider2-dbt）已决定延后，暂由 ELT-Bench 覆盖",
            },
            "counts": per_wh,
        },
    }
