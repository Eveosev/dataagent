"""B17 字段映射判分：每个源字段的 top-1 目标字段是否正确。

口径：
- 金标来自用例 `expected`：`source_field` + `target_field`（`null` 表示无对应字段），
  也接受 `fields` / `mappings` 的多字段形状。金标只来自数据集自带的
  `ground_truth.json`，不由被测程序生成。
- `mapping_top1`：每个源字段只看 top-1 目标字段；正确得 1，错误或没有作答得 0。
  无对应字段时，必须显式返回 `null` / 空数组；省略该字段不算作答，按 0 计。
  跨用例 pooled：总正确字段数 / 总源字段数。
- `no_match_accuracy`：只在金标无对应字段的子集上计分，检查是否显式返回空；
  没有无匹配字段的用例记 `value=None`，不进分母。
- 列名归一：NFKC、大小写不敏感，忽略空格/下划线/连字符；因此 `First Name`、
  `first_name`、`firstName` 视为同一列。目标列必须落在 `candidate_targets` 内；
  落在候选外的预测仍判错，并在 notes 的 `invalid` 计数里记数。
- 产出接受 `target_field` / `target` / `mappings` / `mapping` / `matches` / `pairs`
  等常见形状；同一源字段出现多次时取第一次（top-1）。
"""
from __future__ import annotations

import re
import unicodedata

from .common import missing, result

NULLISH = {
    "",
    "null",
    "none",
    "n/a",
    "na",
    "-",
    "—",
    "无",
    "未提供",
    "no match",
    "no_match",
    "unmatched",
}


def grade(case: dict, output: dict, cfg: dict) -> dict:
    fields = _gold_fields(case.get("expected") or {})
    if not fields:
        return missing("mapping_top1", "金标无源字段", 0)
    default_source = fields[0]["source"] if len(fields) == 1 else None
    parsed = _parse_output(output, default_source)
    candidates = _candidates(case.get("expected") or {})
    correct = 0
    no_answer = 0
    wrong = 0
    invalid = 0
    positive = sum(1 for field in fields if field["target"] is not None)
    for field in fields:
        key = _norm_col(field["source"])
        if key not in parsed:
            no_answer += 1
            continue
        predicted = parsed[key]
        if predicted is None:
            if field["target"] is None:
                correct += 1
            else:
                wrong += 1
            continue
        if field["target"] is not None and _norm_col(predicted) == _norm_col(field["target"]):
            correct += 1
        else:
            wrong += 1
        if candidates and _norm_col(predicted) not in candidates:
            invalid += 1
    value = correct / len(fields)
    notes = (
        f"correct={correct} total={len(fields)} positive={positive} "
        f"no_match={len(fields) - positive} no_answer={no_answer} wrong={wrong} invalid={invalid}"
    )
    return result("mapping_top1", value, correct, len(fields), notes)


def no_match(case: dict, output: dict, cfg: dict) -> dict:
    fields = [field for field in _gold_fields(case.get("expected") or {}) if field["target"] is None]
    if not fields:
        return missing("no_match_accuracy", "该用例无无匹配字段", 0)
    default_source = fields[0]["source"] if len(fields) == 1 else None
    parsed = _parse_output(output, default_source)
    correct = 0
    no_answer = 0
    wrong = 0
    for field in fields:
        key = _norm_col(field["source"])
        if key not in parsed:
            no_answer += 1
            continue
        if parsed[key] is None:
            correct += 1
        else:
            wrong += 1
    value = correct / len(fields)
    notes = f"correct={correct} total={len(fields)} no_answer={no_answer} wrong={wrong}"
    return result("no_match_accuracy", value, correct, len(fields), notes)


def _gold_fields(expected: dict) -> list[dict]:
    fields: list[dict] = []
    raw_fields = expected.get("fields")
    if isinstance(raw_fields, list):
        for item in raw_fields:
            if not isinstance(item, dict):
                continue
            source = item.get("source_field") or item.get("source") or item.get("source_column")
            if source is None:
                continue
            fields.append({"source": str(source), "target": _gold_target(item.get("target_field", item.get("target")))})
    if not fields:
        raw_mappings = expected.get("mappings")
        if isinstance(raw_mappings, dict):
            for source, target in raw_mappings.items():
                fields.append({"source": str(source), "target": _gold_target(target)})
    if not fields and expected.get("source_field") is not None:
        fields.append(
            {
                "source": str(expected["source_field"]),
                "target": _gold_target(expected.get("target_field")),
            }
        )
    if not fields:
        raw_pairs = expected.get("pairs")
        if isinstance(raw_pairs, list):
            for item in raw_pairs:
                if isinstance(item, dict):
                    source = item.get("source_field") or item.get("source") or item.get("left_id")
                    if source is None:
                        continue
                    fields.append(
                        {
                            "source": str(source),
                            "target": _gold_target(item.get("target_field", item.get("target", item.get("right_id")))),
                        }
                    )
    return fields


def _gold_target(value):
    target = _target_from(value)
    return target


def _candidates(expected: dict) -> set[str]:
    raw = expected.get("candidate_targets") or expected.get("candidates") or []
    if isinstance(raw, str):
        raw = [raw]
    return {_norm_col(value) for value in raw if value is not None and _norm_col(value)}


def _parse_output(output, default_source: str | None) -> dict[str, str | None]:
    parsed: dict[str, str | None] = {}
    if output is None:
        return parsed
    if isinstance(output, str):
        if default_source is not None:
            _add_mapping(parsed, default_source, output)
        return parsed
    if isinstance(output, (list, tuple)):
        _consume(parsed, output, default_source)
        return parsed
    if not isinstance(output, dict):
        return parsed

    nested = output.get("output")
    if isinstance(nested, (dict, list, str)):
        nested_parsed = _parse_output(nested, default_source)
        for key, value in nested_parsed.items():
            parsed.setdefault(key, value)

    source = output.get("source_field") or output.get("source_column") or output.get("source")
    for key in ("target_field", "target_column", "target", "match", "right_id"):
        if key in output:
            if source is not None:
                _add_mapping(parsed, source, output[key])
            elif default_source is not None:
                _add_mapping(parsed, default_source, output[key])
            break

    for key in ("mappings", "mapping", "fields", "pairs", "matches", "links", "alignment", "match_pairs", "answers"):
        if key in output:
            _consume(parsed, output[key], default_source)
    if "right_ids" in output and default_source is not None:
        _add_mapping(parsed, default_source, output["right_ids"])
    if "target_ids" in output and default_source is not None:
        _add_mapping(parsed, default_source, output["target_ids"])
    return parsed


def _consume(parsed: dict, raw, default_source: str | None) -> None:
    if raw is None:
        if default_source is not None:
            _add_mapping(parsed, default_source, None)
        return
    if isinstance(raw, dict):
        if any(key in raw for key in ("source_field", "source_column", "source", "left_id")):
            source = raw.get("source_field") or raw.get("source_column") or raw.get("source") or raw.get("left_id")
            if source is not None:
                _add_mapping(
                    parsed,
                    source,
                    raw.get("target_field", raw.get("target_column", raw.get("target", raw.get("right_id")))),
                )
            return
        if any(key in raw for key in ("target_field", "target_column", "target", "right_id")):
            if default_source is not None:
                _add_mapping(
                    parsed,
                    default_source,
                    raw.get("target_field", raw.get("target_column", raw.get("target", raw.get("right_id")))),
                )
            return
        if not raw and default_source is not None:
            _add_mapping(parsed, default_source, None)
            return
        for source, target in raw.items():
            _add_mapping(parsed, source, target)
        return
    if not isinstance(raw, (list, tuple)):
        if default_source is not None:
            _add_mapping(parsed, default_source, raw)
        return
    if not raw:
        if default_source is not None:
            _add_mapping(parsed, default_source, None)
        return
    for item in raw:
        if isinstance(item, dict):
            source = item.get("source_field") or item.get("source_column") or item.get("source") or item.get("left_id")
            if source is None and any(key in item for key in ("target_field", "target_column", "target", "right_id")):
                source = default_source
            if source is None:
                continue
            _add_mapping(
                parsed,
                source,
                item.get("target_field", item.get("target_column", item.get("target", item.get("right_id")))),
            )
            continue
        if isinstance(item, (list, tuple)) and len(item) == 2:
            _add_mapping(parsed, item[0], item[1])
            continue
        if isinstance(item, str):
            if default_source is not None:
                _add_mapping(parsed, default_source, item)
            continue
        if default_source is not None:
            _add_mapping(parsed, default_source, item)


def _add_mapping(parsed: dict, source, target) -> None:
    key = _norm_col(source)
    if not key:
        return
    if key in parsed:
        return
    parsed[key] = _target_from(target)


def _target_from(value):
    if value is None:
        return None
    if isinstance(value, str):
        text = _norm_text(value)
        if text in NULLISH:
            return None
        return text
    if isinstance(value, (list, tuple)):
        if not value:
            return None
        return _target_from(value[0])
    if isinstance(value, dict):
        for key in ("target_field", "target_column", "target", "column", "name", "id", "right_id"):
            if key in value:
                return _target_from(value[key])
        return None
    text = _norm_text(value)
    return text or None


def _norm_text(value) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value))
    text = text.replace("\u00a0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _norm_col(value) -> str:
    text = _norm_text(value)
    if not text:
        return ""
    text = re.sub(r"[\s_\-]+", "", text)
    return text.strip("\"'`“”‘’").casefold()
