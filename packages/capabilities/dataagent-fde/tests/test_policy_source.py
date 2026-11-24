import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]
HELPER = PACKAGE / "skills/fde-engineer/scripts/policy_source.py"
EXAMPLES = PACKAGE / "examples/reimbursement"
OCT = EXAMPLES / "费用办法（10月）.md"
NOV = EXAMPLES / "费用办法（11月）.md"


class PolicySourceTest(unittest.TestCase):
    def call(self, *args, evidence=None, code=0):
        run = subprocess.run(
            [sys.executable, str(HELPER), *map(str, args)],
            input=json.dumps(evidence, ensure_ascii=False) if evidence is not None else "",
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(run.returncode, code, run.stderr or run.stdout)
        return json.loads(run.stdout)

    def test_missing_material_and_ambiguous_versions_do_not_open_files(self):
        self.assertEqual(self.call("read")["status"], "need_source")
        # Unreadable candidates would fail if either was opened before clarification.
        with tempfile.TemporaryDirectory() as directory:
            candidates = [str(Path(directory) / f"制度{month}月.md") for month in (10, 11)]
            response = self.call("read", *candidates)
            self.assertEqual(response["status"], "choose_source")
            self.assertEqual(response["choices"], candidates)
            self.assertNotIn("lines", response)

    def test_selected_version_pagination_and_rule_with_separate_exception(self):
        self.assertEqual(self.call("read", OCT, NOV)["status"], "choose_source")
        first = self.call("read", NOV, "--limit", 4)
        self.assertEqual(first["next_line"], 5)
        second = self.call("read", NOV, "--start-line", 5, "--digest", first["digest"])
        self.assertEqual(second["lines"][0]["number"], 5)
        self.assertIsNone(second["next_line"])
        self.assertEqual(first["digest"], hashlib.sha256(NOV.read_bytes()).hexdigest())
        quotes = [
            {"id": "rule", "line": 5, "quote": "电子票据与纸质票据均可。"},
            {"id": "exception", "line": 8, "quote": "交通票据仍须提交。"},
        ]
        checked = self.call("verify", NOV, "--digest", first["digest"], evidence=quotes)
        self.assertEqual(checked["status"], "verified")
        self.assertEqual(checked["source"], str(NOV))
        self.assertEqual([e["line"] for e in checked["verified"]], [5, 8])

    def test_partial_correction_keeps_only_supported_evidence(self):
        snapshot = self.call("read", NOV, NOV)
        items = [
            {"id": "limit", "line": 6, "quote": "普通市内通勤不在差旅报销范围内。"},
            {"id": "wrong-place", "line": 4, "quote": "交通票据仍须提交。"},
            {"id": "outdated", "line": 5, "quote": "纸质交通票据"},
        ]
        checked = self.call("verify", NOV, "--digest", snapshot["digest"], evidence=items, code=1)
        self.assertEqual(checked["status"], "needs_review")
        self.assertEqual([e["id"] for e in checked["verified"]], ["limit"])
        self.assertEqual([e["id"] for e in checked["unresolved"]], ["wrong-place", "outdated"])

    def test_edit_between_pages_or_before_delivery_invalidates_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "费用制度.txt"
            source.write_bytes(b"old\nkeep")
            digest = self.call("read", source, "--limit", 1)["digest"]
            source.write_bytes(b"new\nkeep")
            item = [{"id": "R1", "line": 2, "quote": "keep"}]
            for result in (
                self.call("read", source, "--start-line", 2, "--digest", digest, code=1),
                self.call("verify", source, "--digest", digest, evidence=item, code=1),
            ):
                self.assertEqual(result["status"], "source_changed")
                self.assertFalse(result.get("verified"))
                self.assertNotIn("lines", result)

    def test_multiline_quote_with_bom_and_crlf(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "制度.txt"
            source.write_bytes("第一条 凭票\r\n可报销。\r\n".encode("utf-8-sig"))
            snapshot = self.call("read", source)
            self.assertEqual(snapshot["lines"][0]["text"], "第一条 凭票")
            item = [{"id": "R1", "line": 1, "quote": "凭票\n可报销。"}]
            checked = self.call("verify", source, "--digest", snapshot["digest"], evidence=item)
            self.assertEqual(checked["verified"][0]["end_line"], 2)

    def test_empty_unreadable_and_nontext_sources_do_not_look_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "制度.md"
            self.assertEqual(self.call("read", source, code=1)["status"], "unreadable")
            source.write_text("  \n", encoding="utf-8")
            self.assertEqual(self.call("read", source, code=1)["status"], "empty_source")
            source.write_bytes(b"hello\x00world")
            self.assertEqual(self.call("read", source, code=1)["status"], "unsupported")
            self.assertEqual(self.call("read", NOV.with_suffix(".pdf"), code=1)["status"], "unsupported")

    def test_empty_or_malformed_evidence_cannot_pass(self):
        digest = self.call("read", NOV)["digest"]
        item = {"id": "R1", "line": 1, "quote": "费用办法"}
        for payload in ([], {}, [item, item], [dict(item, line=True)], [dict(item, quote=" ")]):
            with self.subTest(payload=payload):
                reply = self.call("verify", NOV, "--digest", digest, evidence=payload, code=1)
                self.assertEqual(reply["status"], "invalid_request")
                self.assertFalse(reply.get("verified"))


if __name__ == "__main__":
    unittest.main()
