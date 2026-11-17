"""B17 判分器单测：top-1、显式空答案、无匹配子集与列名归一。"""
from __future__ import annotations

import pathlib
import sys
import unittest

BENCH = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(BENCH / "harness"))

from graders.mapping_top1 import grade, no_match  # noqa: E402


def case(source="src", target="tgt", candidates=None, fields=None):
    expected = {
        "source_field": source,
        "target_field": target,
        "candidate_targets": candidates or (["tgt", "other"] if target else ["other"]),
    }
    if fields is not None:
        expected = {"fields": fields, "candidate_targets": ["a", "b", "c"]}
    return {"case_id": "B17-test-0001", "expected": expected}


class MappingTop1Test(unittest.TestCase):
    def test_exact_match(self):
        row = grade(case(), {"target_field": "tgt"}, {})
        self.assertEqual(row["value"], 1.0)
        self.assertEqual((row["numerator"], row["denominator"]), (1, 1))

    def test_wrong_target(self):
        row = grade(case(), {"target_field": "other"}, {})
        self.assertEqual(row["value"], 0.0)

    def test_explicit_null_is_correct_for_no_match(self):
        row = grade(case(target=None), {"source_field": "src", "target_field": None}, {})
        self.assertEqual(row["value"], 1.0)
        self.assertEqual(no_match(case(target=None), {"target_field": None}, {})["value"], 1.0)

    def test_missing_answer_is_wrong_even_for_no_match(self):
        row = grade(case(target=None), {}, {})
        self.assertEqual(row["value"], 0.0)
        self.assertEqual(no_match(case(target=None), {}, {})["value"], 0.0)

    def test_empty_container_is_explicit_null(self):
        row = grade(case(target=None), {"mappings": []}, {})
        self.assertEqual(row["value"], 1.0)

    def test_column_name_normalization(self):
        row = grade(case(source="First Name", target="First_Name"), {"target_field": "first name"}, {})
        self.assertEqual(row["value"], 1.0)

    def test_top1_list_takes_first(self):
        self.assertEqual(grade(case(), {"target_field": ["tgt", "other"]}, {})["value"], 1.0)
        self.assertEqual(grade(case(), {"target_field": ["other", "tgt"]}, {})["value"], 0.0)

    def test_mappings_dict_with_null(self):
        row = grade(case(target=None), {"mappings": {"src": None}}, {})
        self.assertEqual(row["value"], 1.0)

    def test_top_level_list_takes_first(self):
        self.assertEqual(grade(case(), ["tgt", "other"], {})["value"], 1.0)

    def test_multiple_fields_pooled(self):
        fields = [
            {"source_field": "s1", "target_field": "a"},
            {"source_field": "s2", "target_field": "b"},
            {"source_field": "s3", "target_field": None},
        ]
        output = {
            "mappings": [
                {"source_field": "s1", "target_field": "a"},
                {"source_field": "s2", "target_field": "c"},
            ]
        }
        row = grade(case(fields=fields), output, {})
        self.assertAlmostEqual(row["value"], 1 / 3)
        self.assertEqual((row["numerator"], row["denominator"]), (1, 3))

    def test_invalid_target_is_wrong_and_counted(self):
        row = grade(case(), {"target_field": "outside"}, {})
        self.assertEqual(row["value"], 0.0)
        self.assertIn("invalid=1", row["notes"])

    def test_no_match_metric_missing_without_null_fields(self):
        self.assertIsNone(no_match(case(), {"target_field": "tgt"}, {})["value"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
