#!/usr/bin/env python3
"""端到端自测：金标回填的“完美预测”必须满分，扰动后必须掉分。

运行：python3 -I harness/tests/test_pipeline.py
需要 jsonschema 时再验一遍 scorecard 结构（未安装则跳过）。
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
BENCH = HERE.parent.parent
TASKS = {"B01": "irregular-table", "B02": "doc-parse-ocr", "B03": "field-extraction-anchor", "B04": "rule-applicability"}


def task_dir(tid: str) -> pathlib.Path:
    matches = list((BENCH / "tasks").glob(f"{tid}-*"))
    assert matches, tid
    return matches[0]


def gold_output(tid: str, expected: dict) -> dict:
    if tid == "B01":
        return {"answer": expected.get("answer")}
    if tid == "B02":
        return {"text": expected.get("text"), "blocks": expected.get("blocks") or [], "tables": expected.get("tables") or []}
    if tid == "B03":
        out = {"json": expected.get("value")} if "value" in expected else {"entities": expected.get("entities") or []}
        if expected.get("spans"):
            out["spans"] = expected["spans"]
        if expected.get("pages"):
            out["pages"] = expected["pages"]
        return out
    return {"label": expected.get("value")}


def build_preds(tid: str, out: pathlib.Path, degrade: bool = False) -> pathlib.Path:
    d = task_dir(tid) / "dataset"
    lines = []
    n = 0
    for split in ("development", "regression", "unseen_acceptance"):
        for path in sorted((d / "cases" / split).glob("*.json")):
            case = json.loads(path.read_text(encoding="utf-8"))
            expected = json.loads((d / "expected" / f"{case['case_id']}.json").read_text(encoding="utf-8"))["expected"]
            output = gold_output(tid, expected)
            if degrade and n % 4 == 0:
                output = {"answer": "n/a"} if tid == "B01" else ({} if tid == "B03" else {"label": "yes", "text": "x", "blocks": []})
            lines.append(json.dumps({"case_id": case["case_id"], "output": output}, ensure_ascii=False))
            n += 1
    path = out / f"{tid}.jsonl"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def run_grade(tid: str, pred: pathlib.Path, out: pathlib.Path) -> dict:
    card = out / f"scorecard.{tid}.json"
    proc = subprocess.run(
        [sys.executable, "-I", str(BENCH / "harness" / "grade.py"), "--task", tid,
         "--pred", str(pred), "--run-id", "x000-selftest", "--out", str(card)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr[-800:]
    return json.loads(card.read_text(encoding="utf-8"))


def value_of(card: dict, metric: str, split: str = "unseen_acceptance"):
    return card["split_scores"][split]["metrics"][metric]["value"]


class TestPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = pathlib.Path(cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_perfect_predictions_score_one(self):
        cases = {
            "B01": ("downstream_qa_accuracy", 1.0),
            "B02": ("text_ned", 0.0),
            "B03": ("value_f1", 1.0),
            "B04": ("rule_selection_accuracy", 1.0),
        }
        for tid, (metric, expect) in cases.items():
            card = run_grade(tid, build_preds(tid, self.out), self.out)
            self.assertAlmostEqual(value_of(card, metric), expect, places=4, msg=tid)

    def test_b01_primary_metrics_waiting_for_gold(self):
        # 表头/行保留率目前没有金标，必须如实报 missing 而不是 0
        card = run_grade("B01", build_preds("B01", self.out), self.out)
        self.assertIsNone(value_of(card, "header_cell_accuracy"))
        self.assertIsNone(value_of(card, "row_retention"))

    def test_unimplemented_metrics_are_missing_not_zero(self):
        card = run_grade("B02", build_preds("B02", self.out), self.out)
        self.assertIsNone(value_of(card, "assertion_pass_rate"))

    def test_b03_derived_evidence_gold_is_gradeable(self):
        card = run_grade("B03", build_preds("B03", self.out), self.out)
        self.assertAlmostEqual(value_of(card, "evidence_span_f1"), 1.0, places=4)
        self.assertAlmostEqual(value_of(card, "evidence_page_f1"), 1.0, places=4)

    def test_degraded_predictions_score_lower(self):
        for tid, metric, perfect in (
            ("B01", "downstream_qa_accuracy", 1.0),
            ("B02", "text_ned", 0.0),
            ("B03", "value_f1", 1.0),
            ("B04", "rule_selection_accuracy", 1.0),
        ):
            card = run_grade(tid, build_preds(tid, self.out, degrade=True), self.out)
            got = value_of(card, metric)
            if metric == "text_ned":
                self.assertGreater(got, perfect, tid)
            else:
                self.assertLess(got, perfect, tid)

    def test_scorecard_matches_schema(self):
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            self.skipTest("未安装 jsonschema")
        schema = json.loads((BENCH / "schema" / "scorecard.schema.json").read_text(encoding="utf-8"))
        card = run_grade("B02", build_preds("B02", self.out), self.out)
        Draft202012Validator(schema).validate(card)


if __name__ == "__main__":
    unittest.main(verbosity=2)
