"""B04 条件方向一致率：同一条件正反两问的判定必须互为镜像。

金标需要成对用例：expected.pair_id + expected.direction（"forward" / "reversed"），
且两问共享同一规则集。现有 DeonticBench 抽样没带配对信息，返回 None 记 missing；
补配对标注后按“两问判定是否同时正确且方向相反”计分。
"""
from __future__ import annotations

from .common import missing


def grade(case: dict, output: dict, cfg: dict) -> dict:
    expected = case.get("expected") or {}
    if not expected.get("pair_id") or not expected.get("direction"):
        return missing("condition_direction_consistency", "金标无配对信息（pair_id/direction）")
    return missing("condition_direction_consistency", "配对判分需成对读取两条用例，当前 runner 逐条调用")
