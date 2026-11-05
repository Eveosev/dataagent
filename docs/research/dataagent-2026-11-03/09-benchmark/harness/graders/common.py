"""grader 公共件：输出装载、文本/数值归一、编辑距离与 F1。

约定：
- 输入 case 为用例 JSON，外加两个键：`gold`（expected/<case_id>.json 全文）与
  `expected`（其 `expected` 子对象）。
- `output` 为被测系统产出，允许内联，或用 `{"ref": "<run_dir 相对路径>"}` 指向文件。
- 任何判不了的指标返回 `{"value": None, ...}`，由调用方记进 missing，绝不当 0。
"""
from __future__ import annotations

import json
import math
import pathlib
import re
import unicodedata

NULLISH = {"", "null", "none", "n/a", "na", "-", "—", "无", "未提供"}


def load_output(output: dict, cfg: dict) -> dict:
    """把适配器出参展开成可判分的 dict；ref 相对 run_dir 解析。"""
    if not isinstance(output, dict):
        return {}
    ref = output.get("ref") or output.get("output_ref")
    if ref and len(output) <= 3:
        base = pathlib.Path((cfg or {}).get("run_dir") or ".")
        path = (base / str(ref)).resolve()
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
    inner = output.get("output")
    if isinstance(inner, dict) and len(output) <= 5:
        return inner
    return output


def norm_text(value) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value))
    text = text.replace("\u00a0", " ")
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def norm_cell(value) -> str:
    """单元格归一：去首尾空白与包裹引号，压缩空白，不改变大小写语义（统一小写）。"""
    text = norm_text(value)
    text = text.strip("\"'`“”‘’")
    text = text.replace(" ", "")
    return text


def parse_number(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = norm_text(value).replace(",", "").replace("，", "").replace("$", "").replace("¥", "")
    text = re.sub(r"(?<=\d)\s+(?=\d)", "", text)
    m = re.fullmatch(r"[-+]?\d+(?:\.\d+)?(?:e[-+]?\d+)?%?", text)
    if not m:
        return None
    pct = text.endswith("%")
    try:
        num = float(text.rstrip("%"))
    except ValueError:
        return None
    return num / 100.0 if pct else num


def numbers_equal(a, b, tol: float = 1e-9) -> bool:
    na, nb = parse_number(a), parse_number(b)
    if na is None or nb is None:
        return False
    return math.isclose(na, nb, rel_tol=1e-9, abs_tol=tol)


def values_equal(pred, gold) -> bool:
    """值相等：null 语义优先，其次数值，最后归一文本。"""
    gp, gg = pred is None or norm_text(pred) in NULLISH, gold is None or norm_text(gold) in NULLISH
    if gg:
        return gp
    if gp:
        return False
    if numbers_equal(pred, gold):
        return True
    return norm_cell(pred) == norm_cell(gold)


def flatten(obj, prefix: str = "") -> dict:
    """把嵌套 dict/list 展平成 路径 → 叶子 值。"""
    out = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.update(flatten(v, f"{prefix}.{k}" if prefix else str(k)))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.update(flatten(v, f"{prefix}[{i}]"))
    else:
        out[prefix] = obj
    return out


def edit_distance(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def prf(tp: int, fp: int, fn: int):
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def missing(metric: str, note: str, denominator: int = 0) -> dict:
    return {
        "metric": metric,
        "value": None,
        "numerator": None,
        "denominator": denominator,
        "judgeable": False,
        "notes": note,
    }


def result(metric: str, value, numerator, denominator: int, notes: str | None = None) -> dict:
    return {
        "metric": metric,
        "value": value,
        "numerator": numerator,
        "denominator": denominator,
        "judgeable": value is not None,
        "notes": notes,
    }


def case_split(case: dict) -> str:
    return case.get("split_role") or ""


def prediction_text(output: dict) -> str:
    """从产出里尽量取“正文文本”。"""
    for key in ("text", "markdown", "md", "content", "output_text"):
        if isinstance(output.get(key), str) and output[key].strip():
            return output[key]
    blocks = output.get("blocks")
    if isinstance(blocks, list):
        parts = [str(b.get("text") or "") for b in blocks if isinstance(b, dict)]
        return "\n".join(p for p in parts if p)
    return ""
