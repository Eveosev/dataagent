"""B16 实体对判分：实体对 F1 与错误合并率。

金标：`expected.pairs`，形如 `[{"left_id": "...", "right_id": "..."}]`；只来自数据集
自带的 perfectMapping，不由被测程序生成。

产出接受三种常见形状：
- `{"pairs": [{"left_id": "...", "right_id": "..."}]}`
- `{"matches": [{"left_id": "...", "right_id": "..."}]}` 或 `{"matches": ["right_id", ...]}`
- `{"clusters": [["id", "id", ...]]}`（同一簇内的左记录与右候选视为合并）

口径：
- `entity_pair_f1`：微观 F1，2TP / (2TP + FP + FN)，跨用例 pooled。
- `false_merge_rate`：错误合并占已预测合并的比例，FP / (TP + FP)；没有预测合并时记 0，
  表示没有发生错误合并。它只惩罚误合并，不惩罚漏合并；漏合并由 F1 反映。
- 返回 `value=None` 只在金标为空且没有预测时发生，由 grade.py 记进 missing，绝不当 0。
"""
from __future__ import annotations

import unicodedata

from .common import missing, result


def grade(case: dict, output: dict, cfg: dict) -> dict:
    scored = _score(case, output)
    if scored is None:
        return missing("entity_pair_f1", "金标无实体对", 0)
    tp, fp, fn, candidates, invalid, pred_count = scored
    denominator = 2 * tp + fp + fn
    f1 = (2 * tp / denominator) if denominator else 0.0
    return result(
        "entity_pair_f1",
        f1,
        2 * tp,
        denominator,
        f"tp={tp} fp={fp} fn={fn} predicted={pred_count} candidates={len(candidates)} invalid={invalid}",
    )


def false_merge(case: dict, output: dict, cfg: dict) -> dict:
    scored = _score(case, output)
    if scored is None:
        return missing("false_merge_rate", "金标无实体对", 0)
    tp, fp, fn, candidates, invalid, pred_count = scored
    merged = tp + fp
    rate = (fp / merged) if merged else 0.0
    note = f"tp={tp} fp={fp} fn={fn} predicted={pred_count} candidates={len(candidates)} invalid={invalid}"
    if not merged:
        note += "；无预测合并，按 0 计"
    return result("false_merge_rate", rate, fp, merged, note)


def _score(case: dict, output: dict):
    left_id, gold, candidates = _gold(case)
    pred, invalid = _pred(output, left_id, candidates)
    if not gold and not pred:
        return None
    tp = len(gold & pred)
    fp = len(pred - gold)
    fn = len(gold - pred)
    return tp, fp, fn, candidates, invalid, len(pred)


def _gold(case: dict):
    expected = case.get("expected") or {}
    left_id = _norm_id(expected.get("left_id") or expected.get("left") or "")
    candidate_ids = {_norm_id(value) for value in (expected.get("candidate_ids") or []) if _norm_id(value)}
    raw = expected.get("pairs") or expected.get("gold_pairs") or []
    gold = set()
    if isinstance(raw, dict) and ("left_id" in raw or "right_id" in raw):
        raw = [raw]
    if isinstance(raw, dict):
        for left, rights in raw.items():
            left_norm = _norm_id(left) or left_id
            if isinstance(rights, (list, tuple, set)):
                for right in rights:
                    right_norm = _norm_id(right)
                    if left_norm and right_norm:
                        gold.add((left_norm, right_norm))
            else:
                right_norm = _norm_id(rights)
                if left_norm and right_norm:
                    gold.add((left_norm, right_norm))
    else:
        for item in raw:
            pair = _pair(item, left_id)
            if pair:
                gold.add(pair)
    if not gold and left_id:
        for right_id in expected.get("right_ids") or []:
            if _norm_id(right_id):
                gold.add((left_id, _norm_id(right_id)))
    return left_id, gold, candidate_ids


def _pred(output: dict, left_id: str, candidates: set[str]):
    raw = None
    for key in ("pairs", "entity_pairs", "matches", "links", "alignment", "match_pairs"):
        if key in output:
            raw = output[key]
            break
    if raw is None and isinstance(output.get("output"), (dict, list)):
        return _pred(output["output"], left_id, candidates)
    if raw is None:
        if "right_ids" in output:
            raw = output["right_ids"]
        elif "right_id" in output and "match" in output:
            raw = [output["right_id"]] if output.get("match") else []
        elif "clusters" in output:
            raw = output["clusters"]
        elif "entities" in output and isinstance(output["entities"], list):
            raw = output["entities"]

    pred = set()
    if raw is None:
        return pred, 0
    if isinstance(raw, dict):
        if "left_id" in raw or "right_id" in raw or "right_ids" in raw:
            left = _norm_id(raw.get("left_id") or left_id)
            right_values = raw.get("right_ids") or [raw.get("right_id")]
            for right in right_values:
                right_id = _norm_id(right)
                if right_id:
                    pred.add((left, right_id))
        else:
            for left, right_values in raw.items():
                left_norm = _norm_id(left)
                if isinstance(right_values, (list, tuple, set)):
                    for right in right_values:
                        right_id = _norm_id(right)
                        if right_id:
                            pred.add((left_norm, right_id))
                else:
                    right_id = _norm_id(right_values)
                    if right_id:
                        pred.add((left_norm, right_id))
    elif isinstance(raw, (list, tuple)):
        for item in raw:
            if isinstance(item, (dict, list, tuple)) and not isinstance(item, str):
                if isinstance(item, (list, tuple)) and len(item) == 2:
                    pair = _pair(item, left_id)
                    if pair:
                        pred.add(pair)
                    continue
                if isinstance(item, dict):
                    pair = _pair(item, left_id)
                    if pair:
                        pred.add(pair)
                    continue
                if item and left_id:
                    ids = [_norm_id(value.get("id") if isinstance(value, dict) else value) for value in item]
                    if left_id in ids:
                        for right_id in ids:
                            if right_id and right_id != left_id:
                                pred.add((left_id, right_id))
                continue
            if isinstance(item, str):
                right_id = _norm_id(item)
                if right_id:
                    pred.add((left_id, right_id))

    invalid = sum(
        1 for left, right in pred
        if (left and left != left_id) or (candidates and right not in candidates)
    )
    return pred, invalid


def _pair(item, default_left: str):
    if isinstance(item, dict):
        left = item.get("left_id") or item.get("left") or item.get("source_id") or item.get("source")
        right = item.get("right_id") or item.get("right") or item.get("target_id") or item.get("target")
    elif isinstance(item, (list, tuple)) and len(item) == 2:
        left, right = item
    else:
        return None
    if isinstance(left, dict):
        left = left.get("id")
    if isinstance(right, dict):
        right = right.get("id")
    left_id = _norm_id(left) or default_left
    right_id = _norm_id(right)
    if not left_id or not right_id:
        return None
    return left_id, right_id


def _norm_id(value) -> str:
    if value is None:
        return ""
    return unicodedata.normalize("NFKC", str(value)).strip()
