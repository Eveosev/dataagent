#!/usr/bin/env python3
"""grader 自测：每条手算期望值钉住口径。

运行：python3 -I harness/tests/test_graders.py
"""
from __future__ import annotations

import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "graders"))

from graders import (  # noqa: E402
    decidability_classification,
    field_value_f1,
    hallucination_probe,
    header_cell_match,
    ned_edit_distance,
    order_accuracy,
    qa_exact_match,
    record_recall,
    row_retention,
    rule_choice_match,
    teds,
    unknown_preservation,
)


def case(expected: dict) -> dict:
    return {"case_id": "B0X-test-001", "expected": expected, "gold": {"expected": expected}}


class TestB01(unittest.TestCase):
    def test_numeric_answer(self):
        row = qa_exact_match.grade(case({"answer": "262.5"}), {"answer": "262.50"}, {})
        self.assertEqual(row["value"], 1.0)

    def test_text_answer_mismatch(self):
        row = qa_exact_match.grade(case({"answer": "A4 Paper"}), {"answer": "A3 Paper"}, {})
        self.assertEqual(row["value"], 0.0)

    def test_long_answer_partial_is_zero(self):
        gold = "the paper with the largest specification is a4 paper which has four square meters"
        row = qa_exact_match.grade(case({"answer": gold}), {"answer": "a4 paper"}, {})
        self.assertEqual(row["value"], 0.0)

    def test_header_without_gold_is_missing(self):
        row = header_cell_match.grade(case({"answer": "x"}), {"headers": ["a"]}, {})
        self.assertIsNone(row["value"])

    def test_header_half_match(self):
        row = header_cell_match.grade(case({"headers": ["Name", "Qty"]}), {"headers": ["name", "Price"]}, {})
        self.assertEqual(row["value"], 0.5)

    def test_row_retention_dropped_rows(self):
        self.assertEqual(row_retention.grade(case({"row_count": 10}), {"rows": [[1]] * 8}, {})["value"], 0.8)
        self.assertEqual(row_retention.grade(case({"row_count": 10}), {"rows": [[1]] * 12}, {})["value"], 1.0)


class TestB02(unittest.TestCase):
    def test_ned_identical(self):
        self.assertEqual(ned_edit_distance.grade(case({"text": "hello world"}), {"text": "Hello   World"}, {})["value"], 0.0)

    def test_ned_one_char(self):
        # "cat" → "car"：距离 1，最长 3
        row = ned_edit_distance.grade(case({"text": "cat"}), {"text": "car"}, {})
        self.assertAlmostEqual(row["value"], 1 / 3, places=6)

    def test_teds_identical(self):
        html = "<table><tr><td>A</td><td>B</td></tr></table>"
        self.assertAlmostEqual(teds.grade(case({"tables": [{"html": html}]}), {"tables": [{"html": html}]}, {})["value"], 1.0)

    def test_teds_one_cell_changed(self):
        a = "<table><tr><td>A</td><td>B</td></tr></table>"
        b = "<table><tr><td>A</td><td>C</td></tr></table>"
        # 6 个节点（table/tr/2×td/2×text），替换 1 个文本叶子
        self.assertAlmostEqual(teds.grade(case({"tables": [{"html": a}]}), {"tables": [{"html": b}]}, {})["value"], 1 - 1 / 6, places=6)

    def test_order_reversed_is_zero(self):
        gold = {"blocks": [{"order": 1, "text": "a"}, {"order": 2, "text": "b"}, {"order": 3, "text": "c"}]}
        pred = {"blocks": [{"text": "c"}, {"text": "b"}, {"text": "a"}]}
        self.assertEqual(order_accuracy.grade(case(gold), pred, {})["value"], 0.0)

    def test_order_partial(self):
        gold = {"blocks": [{"order": 1, "text": "a"}, {"order": 2, "text": "b"}, {"order": 3, "text": "c"}]}
        pred = {"blocks": [{"text": "a"}, {"text": "c"}, {"text": "b"}]}
        # 逆序对 1（b,c），总数 3
        self.assertAlmostEqual(order_accuracy.grade(case(gold), pred, {})["value"], 2 / 3, places=6)


class TestB03(unittest.TestCase):
    def test_field_f1_missing_null_counts_as_hit(self):
        gold = {"value": {"a": "1", "b": None}}
        row = field_value_f1.grade(case(gold), {"json": {"a": "1"}}, {})
        self.assertEqual(row["value"], 1.0)

    def test_field_f1_wrong_value(self):
        gold = {"value": {"a": "1"}}
        row = field_value_f1.grade(case(gold), {"json": {"a": "2"}}, {})
        self.assertEqual(row["value"], 0.0)

    def test_field_f1_half(self):
        gold = {"value": {"a": "1", "b": "2"}}
        row = field_value_f1.grade(case(gold), {"json": {"a": "1", "c": "9"}}, {})
        # tp=1, fp=1(c), fn=1(b) → 2/(2+1+1)=0.5
        self.assertAlmostEqual(row["value"], 0.5, places=6)

    def test_record_recall_half(self):
        gold = {"value": {"menu": [{"nm": "A", "price": "1"}, {"nm": "B", "price": "2"}]}}
        pred = {"json": {"menu": [{"nm": "A", "price": "1"}]}}
        self.assertEqual(record_recall.grade(case(gold), pred, {})["value"], 0.5)

    def test_hallucination_none_when_no_null(self):
        self.assertIsNone(hallucination_probe.grade(case({"value": {"a": "1"}}), {}, {})["value"])

    def test_hallucination_filled_null(self):
        gold = {"value": {"a": None, "b": None}}
        row = hallucination_probe.grade(case(gold), {"json": {"a": "x", "b": None}}, {})
        self.assertEqual(row["value"], 0.5)


class TestB04(unittest.TestCase):
    def test_label_case_insensitive(self):
        self.assertEqual(rule_choice_match.grade(case({"value": "yes"}), {"label": "Yes"}, {})["value"], 1.0)

    def test_label_mismatch(self):
        self.assertEqual(rule_choice_match.grade(case({"value": "no"}), {"label": "yes"}, {})["value"], 0.0)

    def test_decidability_missing_gold_is_none(self):
        # DeonticBench 只有 yes/no/unknown，没有三分类标注
        self.assertIsNone(decidability_classification.grade(case({"value": "unknown"}), {"label": "unknown"}, {})["value"])

    def test_decidability_with_gold(self):
        row = decidability_classification.grade(case({"decidability": "needs_evidence"}), {"decidable": "needs_evidence"}, {})
        self.assertEqual(row["value"], 1.0)

    def test_unknown_only_on_unknown_gold(self):
        self.assertIsNone(unknown_preservation.grade(case({"value": "yes"}), {"label": "yes"}, {})["value"])
        self.assertEqual(unknown_preservation.grade(case({"value": "unknown"}), {"label": "unknown"}, {})["value"], 1.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
