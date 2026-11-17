"""B16 判分器单测：聚类展开、候选集外误合并、pooled 汇总。"""
from __future__ import annotations

import pathlib
import sys
import unittest

BENCH = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(BENCH / "harness"))

from grade import aggregate  # noqa: E402
from graders.entity_pair_f1 import false_merge, grade  # noqa: E402


def _case(pairs, candidates):
    return {
        "expected": {
            "left_id": "L",
            "candidate_ids": candidates,
            "pairs": [{"left_id": "L", "right_id": right} for right in pairs],
        }
    }


class EntityPairF1Test(unittest.TestCase):
    def test_cluster_outside_candidate_counts_as_fp(self):
        case = _case(["R1"], ["R1", "R2"])
        output = {"clusters": [["L", "R1", "OUTSIDE"]]}

        f1 = grade(case, output, {})
        fmr = false_merge(case, output, {})

        self.assertLess(f1["value"], 1.0)
        self.assertGreater(fmr["value"], 0.0)
        self.assertEqual(f1["notes"].split("invalid=")[1], "1")
        self.assertAlmostEqual(f1["value"], 2 / 3)
        self.assertAlmostEqual(fmr["value"], 0.5)

    def test_cluster_transitive_closure(self):
        case = _case(["R1", "R2"], ["R1", "R2"])
        output = {"clusters": [["L", "R1"], ["R1", "R2"]]}

        self.assertEqual(grade(case, output, {})["value"], 1.0)
        self.assertEqual(false_merge(case, output, {})["value"], 0.0)

    def test_false_merge_rate_is_pooled_by_predicted_pairs(self):
        metric = {"id": "false_merge_rate", "aggregation": "pooled"}
        rows = [
            {"value": 1.0, "numerator": 1, "denominator": 1, "judgeable": True, "missing": 0},
            {"value": 0.75, "numerator": 3, "denominator": 4, "judgeable": True, "missing": 0},
        ]
        self.assertEqual(aggregate(metric, rows)["value"], 0.8)

    def test_false_merge_rate_all_no_merge_is_null(self):
        metric = {"id": "false_merge_rate", "aggregation": "pooled"}
        rows = [
            {"value": 0.0, "numerator": 0, "denominator": 0, "judgeable": True, "missing": 0}
            for _ in range(3)
        ]
        self.assertIsNone(aggregate(metric, rows)["value"])


if __name__ == "__main__":
    unittest.main()
