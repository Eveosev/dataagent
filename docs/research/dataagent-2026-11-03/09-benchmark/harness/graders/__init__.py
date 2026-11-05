"""grader 注册表：文件名 → 指标实现。

新增 grader 只需在同目录加模块并在此登记；`task.json` 的 `metric.grader` 即键名。
"""
from __future__ import annotations

import importlib

REGISTRY = {
    # B01
    "header_cell_match": "header_cell_accuracy",
    "row_retention": "row_retention",
    "qa_exact_match": "downstream_qa_accuracy",
    # B02
    "ned_edit_distance": "text_ned",
    "teds": "table_teds",
    "order_accuracy": "reading_order_accuracy",
    "assertion_pass_rate": "assertion_pass_rate",
    # B03
    "field_value_f1": "value_f1",
    "record_recall": "record_completeness",
    "span_f1": "evidence_span_f1",
    "page_match": "evidence_page_f1",
    "hallucination_probe": "hallucination_rate",
    # B04
    "rule_choice_match": "rule_selection_accuracy",
    "direction_symmetry": "condition_direction_consistency",
    "decidability_classification": "decidability_accuracy",
    "unknown_preservation": "unknown_retention",
}


def load(name: str):
    if name not in REGISTRY:
        raise KeyError(f"未注册的 grader: {name}")
    module = importlib.import_module(f"graders.{name}")
    return module.grade
