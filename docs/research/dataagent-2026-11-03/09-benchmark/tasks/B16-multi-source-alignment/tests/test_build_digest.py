"""build_cases 内容摘要与版本幂等测试。"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import tempfile
import unittest

BENCH = pathlib.Path(__file__).resolve().parents[3]
BUILD_CASES = BENCH / "tools" / "build_cases.py"
spec = importlib.util.spec_from_file_location("build_cases_under_test", BUILD_CASES)
build_cases = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_cases)


class BuildDigestTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        self.dataset = self.root / "dataset"
        (self.dataset / "cases" / "development").mkdir(parents=True)
        (self.dataset / "expected").mkdir()
        (self.dataset / "fixtures").mkdir()
        (self.dataset / "cases" / "development" / "c1.json").write_text('{"case_id": "c1"}\n', encoding="utf-8")
        (self.dataset / "expected" / "c1.json").write_text('{"case_id": "c1"}\n', encoding="utf-8")
        (self.dataset / "fixtures" / "f1.txt").write_text("hello\n", encoding="utf-8")
        self.sources = [
            {"name": "s1", "digest": "sha256:111", "fetched_at": "2026-11-17T00:00:00", "files": 1},
            {"name": "s2", "digest": "sha256:222", "fetched_at": "2026-11-17T00:00:00", "files": 1},
        ]
        self.manifest = {
            "dataset_id": "test.dataset",
            "task_id": "B16",
            "revision": "v0.1",
            "status": "collecting",
            "updated": "2026-01-01",
            "sources": self.sources,
            "build": {
                "version": 1,
                "script": "tools/build_cases.py",
                "built_at": "2026-01-01",
                "policy": "test",
                "available": {},
                "selected": {},
                "caps": {},
            },
        }
        (self.dataset / "manifest.json").write_text(
            json.dumps(self.manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        self.ctx = object.__new__(build_cases.Context)
        self.ctx.dry = False
        self.ctx.task_id = "B16"
        self.ctx.task_dir = self.root
        self.ctx.dataset = self.dataset
        self.ctx.sources = [dict(source) for source in self.sources]
        self.ctx.previous_digest = None
        self.stats = {
            "selected": {"development": 1, "regression": 0, "unseen_acceptance": 0},
            "available": {"development": 1, "regression": 0, "unseen_acceptance": 0},
            "caps": {"development": 1, "regression": 0, "unseen_acceptance": 0},
        }

    def tearDown(self):
        self.temp.cleanup()

    def _publish(self):
        self.ctx.publish(self.stats, "test")
        return json.loads((self.dataset / "manifest.json").read_text(encoding="utf-8"))

    def test_fetched_at_does_not_change_revision(self):
        first = self._publish()
        self.assertEqual(first["revision"], "v0.1")

        self.ctx.sources = [
            {**source, "fetched_at": "2027-01-01T00:00:00"} for source in self.ctx.sources
        ]
        second = self._publish()

        self.assertEqual(second["revision"], "v0.1")
        self.assertEqual(second["build"]["content_digest"], first["build"]["content_digest"])
        self.assertEqual(second["sources"][0]["fetched_at"], "2027-01-01T00:00:00")

    def test_case_change_bumps_revision(self):
        first = self._publish()

        (self.dataset / "cases" / "development" / "c1.json").write_text(
            '{"case_id": "c1", "changed": true}\n', encoding="utf-8"
        )
        second = self._publish()

        self.assertEqual(second["revision"], "v0.2")
        self.assertNotEqual(second["build"]["content_digest"], first["build"]["content_digest"])


if __name__ == "__main__":
    unittest.main()
