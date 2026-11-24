import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "skills/fde-engineer/scripts/sample_check.py"


class SampleCheckTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def sample(self, name, contents):
        path = Path(self.temp.name) / name
        path.write_text(contents, encoding="utf-8")
        return str(path)

    def run_check(self, status, *args):
        result = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)
        self.assertEqual(result.returncode, status, result.stderr or result.stdout)
        return json.loads(result.stdout)

    def test_profile_shows_when_candidate_key_has_wrong_grain(self):
        path = self.sample("events.csv", "site,day,n\nA,1,2\nA,1,9\n,2,1\nA,2,3\n")
        report = self.run_check(0, "profile", path, "--key", "site", "--key", "day")
        self.assertEqual(report["rows"], 4)
        self.assertEqual(report["duplicate_key_rows"], 1)
        self.assertEqual(report["blank_key_rows"], 1)
        self.assertEqual(report["blank_by_column"]["site"], 1)

    def test_replay_ignores_order_and_keeps_significant_text(self):
        expected = self.sample("expected.csv", "\ufeffid,n\n001,2\n002,3\n")
        actual = self.sample("actual.csv", "n,id\n3,002\n2,001\n")
        self.assertTrue(self.run_check(0, "compare", expected, actual, "--key", "id")["match"])
        actual = self.sample("actual.csv", "id,n\n001,02\n003,3\n")
        result = self.run_check(1, "compare", expected, actual, "--key", "id")
        self.assertEqual((result["missing_rows"], result["extra_rows"], result["changed_rows"]), (1, 1, 1))
        self.assertEqual(result["changed_by_column"], {"n": 1})

    def test_duplicate_effect_or_empty_evidence_never_passes_replay(self):
        path = self.sample("once.csv", "id,n\n1,2\n")
        for contents in ["id,n\n1,2\n1,2\n", "id,n\n,2\n", "id,total\n1,2\n"]:
            with self.subTest(contents=contents):
                actual = self.sample("twice.csv", contents)
                self.assertFalse(self.run_check(1, "compare", path, actual, "--key", "id")["match"])
        empty = self.sample("empty.csv", "id,n\n")
        self.assertFalse(self.run_check(1, "compare", empty, empty, "--key", "id")["match"])

    def test_rejects_ambiguous_or_malformed_samples(self):
        for contents in ["id,id\n1,2\n", "id,n\n1\n", "n,total\n1,2\n"]:
            with self.subTest(contents=contents):
                path = self.sample("bad.csv", contents)
                self.assertTrue(self.run_check(2, "profile", path, "--key", "id")["error"])
