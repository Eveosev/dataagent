"""Tests for the code-landing-quality scripts.

Run: python3 -m unittest discover -s skills/code-landing-quality/tests
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL / "scripts"
REPO = SKILL.parents[1]
sys.path.insert(0, str(SCRIPTS))

import plan_checklist  # noqa: E402
import quality_run  # noqa: E402
import round_diff  # noqa: E402
import score_landing  # noqa: E402
import snapshot  # noqa: E402

PLAN = """---
version: v0.1
status: 实施中
---

## 1. 背景

- 这一节只有背景，不应进入清单。

## 2. 实现

| 项 | 规则 |
|-|-|
| 表示 | 必须使用封闭算子集合 |
| 校验 | 拒绝多语句 |

### 2.1 验收

- 每个原子有正例与反例。
"""

BLOCK = "\n".join(f"value_{i} = compute({i}, factor={i * 3})" for i in range(8)) + "\n"


def run(*args: str, cwd: Path = REPO) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, *args], cwd=cwd, capture_output=True, text=True)


def write_plan(tmp: Path, text: str = PLAN) -> Path:
    path = tmp / "plan.md"
    path.write_text(text, encoding="utf-8")
    return path


def make_pkg(root: Path, name: str, files: dict[str, str]) -> Path:
    pkg = root / name
    for rel, text in files.items():
        path = pkg / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return pkg


class PlanChecklistTest(unittest.TestCase):
    def test_extracts_requirements_and_skips_background(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result, items = plan_checklist.extract(write_plan(Path(tmp)), include_all=False)
        texts = " ".join(item["text"] for item in items)
        self.assertIn("封闭算子集合", texts)
        self.assertIn("拒绝多语句", texts)
        self.assertNotIn("只有背景", texts)
        self.assertEqual(result["plan_version"], "v0.1")

    def test_ids_use_section_number_and_survive_inserted_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, before = plan_checklist.extract(write_plan(Path(tmp)), include_all=False)
            shifted = PLAN.replace("## 2. 实现", "## 1.5 新增\n\n- 必须新增一条。\n\n## 2. 实现")
            _, after = plan_checklist.extract(write_plan(Path(tmp), shifted), include_all=False)
        ids_before = {i["id"] for i in before}
        ids_after = {i["id"] for i in after}
        self.assertTrue(all(i.split("#")[0] in ("2", "2.1") for i in ids_before))
        self.assertTrue(ids_before <= ids_after)
        self.assertEqual(len(ids_after - ids_before), 1)

    def test_into_keeps_verdicts_by_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            plan = write_plan(tmp)
            result, items = plan_checklist.extract(plan, include_all=False)
            target = tmp / "r.json"
            target.write_text(json.dumps({"checklist": {"items": [
                {"id": items[0]["id"], "verdict": "done", "evidence": "a.py:1"},
                {"id": "9#ffffff", "verdict": "done", "evidence": "gone"}]}}), encoding="utf-8")
            total, reused, dropped = plan_checklist.merge_into(target, result)
            merged = json.loads(target.read_text(encoding="utf-8"))["checklist"]["items"]
        self.assertEqual((total, reused, dropped), (len(items), 1, ["9#ffffff"]))
        self.assertEqual(merged[0]["verdict"], "done")
        self.assertIsNone(merged[1]["verdict"])

    def test_single_dash_separator_is_recognized(self) -> None:
        self.assertTrue(plan_checklist.is_separator("|-|-|"))
        self.assertTrue(plan_checklist.is_separator("| --- | :---: |"))
        self.assertFalse(plan_checklist.is_separator("| 项 | 规则 |"))


class DuplicateRateTest(unittest.TestCase):
    def test_repeated_block_is_counted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pkg = make_pkg(Path(tmp), "p", {"src/a.py": BLOCK, "src/b.py": BLOCK})
            result = quality_run.duplicate_rate(pkg)
        self.assertGreater(result["rate"], 50.0)
        self.assertEqual(result["cross_lines"], 0)

    def test_cross_package_copy_is_counted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pkg = make_pkg(root, "p", {"src/a.py": BLOCK, "src/own.py": "x = 1\n"})
            peer = make_pkg(root, "q", {"src/copy.py": BLOCK})
            alone = quality_run.duplicate_rate(pkg)
            with_peer = quality_run.duplicate_rate(pkg, [peer], root)
        self.assertEqual(alone["rate"], 0.0)
        self.assertGreater(with_peer["cross_lines"], 0)
        self.assertGreater(with_peer["rate"], 50.0)

    def test_fallback_layout_ignores_tests_and_packaging(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pkg = make_pkg(Path(tmp), "p", {"mod.py": "x = 1\n", "tests/t.py": BLOCK,
                                            "packaging/bundle/src/m/a.py": BLOCK})
            files = quality_run.production_files(pkg)
        self.assertEqual([f.name for f in files], ["mod.py"])


class HygieneTest(unittest.TestCase):
    def test_counts_bare_except_and_swallow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pkg = make_pkg(Path(tmp), "p", {"src/a.py": (
                "def f():\n    try:\n        pass\n    except:\n        pass\n"
                "def g():\n    try:\n        pass\n    except Exception:\n        pass\n"
                "def h():\n    try:\n        pass\n    except (ValueError,\n            KeyError):\n        ...\n"
                "def ok():\n    try:\n        pass\n    except ValueError as exc:\n        raise RuntimeError() from exc\n")})
            result = quality_run.hygiene(pkg, pkg)
        self.assertEqual(len(result["bare_except"]), 1)
        self.assertEqual(len(result["swallow"]), 3)
        self.assertEqual(result["todo"], 0)


class ComplexityTest(unittest.TestCase):
    def test_matches_radon_counting_rules(self) -> None:
        src = (
            "def f(xs, a, b):\n"
            "    if a and b or a:\n"           # if +1, boolop +2
            "        pass\n"
            "    elif b:\n"                    # +1
            "        pass\n"
            "    for x in xs:\n"               # +1
            "        pass\n"
            "    else:\n"                      # for-else +1
            "        pass\n"
            "    try:\n"
            "        pass\n"
            "    except ValueError:\n"         # +1
            "        pass\n"
            "    except KeyError:\n"           # +1
            "        pass\n"
            "    ys = [x for x in xs if x if x > 1]\n"  # comprehension +1, ifs +2
            "    def inner():\n"
            "        if a:\n"                  # not added to f
            "            pass\n"
            "    return 1 if a else 2\n"        # +1
        )
        fn = ast.parse(src).body[0]
        self.assertEqual(quality_run.cc_of(fn), 1 + 3 + 1 + 2 + 2 + 3 + 1)

    def test_methods_are_blocks(self) -> None:
        tree = ast.parse("class A:\n    def m(self):\n        pass\n\ndef f():\n    pass\n")
        self.assertEqual([b.name for b in quality_run.function_blocks(tree)], ["m", "f"])


class QualityRunCliTest(unittest.TestCase):
    def test_no_bundle_and_skip_dup_do_not_crash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pkg = make_pkg(Path(tmp), "p", {"src/p/__init__.py": "x = 1\n"})
            proc = run(str(SCRIPTS / "quality_run.py"), "--repo", tmp, "--package", str(pkg),
                       "--skip-tests", "--skip-dup", "--rubric", str(SKILL / "references/rubric.json"),
                       "--scorer", str(SCRIPTS / "score_landing.py"))
        self.assertNotIn("Traceback", proc.stderr)
        self.assertIn("无 bundle", proc.stdout)
        self.assertIn("不能用于验收", proc.stdout)
        self.assertEqual(proc.returncode, 1)

    def test_fill_writes_measured_rules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pkg = make_pkg(Path(tmp), "p", {"src/p/__init__.py": "def f(a):\n    return a\n"})
            result = Path(tmp) / "r.json"
            proc = run(str(SCRIPTS / "quality_run.py"), "--repo", tmp, "--package", str(pkg),
                       "--skip-tests", "--fill", str(result),
                       "--rubric", str(SKILL / "references/rubric.json"),
                       "--scorer", str(SCRIPTS / "score_landing.py"))
            data = json.loads(result.read_text(encoding="utf-8"))
        self.assertNotIn("Traceback", proc.stderr)
        self.assertEqual(data["rules"]["A1.1"]["score"], 1)
        self.assertEqual(data["rules"]["A1.1"]["measured_by"], "quality_run")
        self.assertEqual(data["hard_rules"]["D1"]["light"], "green")
        self.assertIn("A5.1", data["rules"])
        self.assertTrue(data["snapshot"]["p"].startswith("sha256:"))
        self.assertIsNone(data["checklist"])
        self.assertIsNone(data["defects"])

    def test_fill_and_result_need_one_package(self) -> None:
        proc = run(str(SCRIPTS / "quality_run.py"), "--package", "a", "--package", "b", "--fill", "x.json")
        self.assertEqual(proc.returncode, 2)


class SnapshotTest(unittest.TestCase):
    def test_digest_ignores_caches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pkg = make_pkg(Path(tmp), "p", {"src/a.py": "x = 1\n"})
            first = snapshot.tree_digest(pkg)
            make_pkg(Path(tmp), "p", {"src/__pycache__/a.cpython-315.pyc": "junk", ".venv/x.py": "y"})
            second = snapshot.tree_digest(pkg)
            make_pkg(Path(tmp), "p", {"src/a.py": "x = 2\n"})
            third = snapshot.tree_digest(pkg)
        self.assertEqual(first, second)
        self.assertNotEqual(first["digest"], third["digest"])


class ScorerTest(unittest.TestCase):
    def test_self_test_passes(self) -> None:
        proc = run(str(SCRIPTS / "score_landing.py"), "--self-test")
        self.assertEqual(proc.returncode, 0, proc.stdout)

    def test_repo_copies_match_skill(self) -> None:
        repo_rubric = REPO / "docs/standards/code-landing-rubric.json"
        repo_scorer = REPO / "docs/standards/score_landing.py"
        if not repo_rubric.is_file():
            self.skipTest("no docs/standards in this repository")
        self.assertEqual(repo_rubric.read_bytes(), (SKILL / "references/rubric.json").read_bytes())
        self.assertEqual(repo_scorer.read_bytes(), (SCRIPTS / "score_landing.py").read_bytes())

    def test_semantic_failure_no_longer_reaches_a(self) -> None:
        rubric = json.loads((SKILL / "references/rubric.json").read_text(encoding="utf-8"))
        result = score_landing.all_pass_result(rubric)
        for rid in ("L2.1", "L2.2", "L2.3"):
            result["rules"][rid]["score"] = 0
        result["checklist"]["items"].append({"id": "5.2#000000", "text": "x", "verdict": "not_done"})
        result["defects"].append({"id": "D1", "severity": "P0", "status": "open", "title": "decoy 放行",
                                  "location": "a.py:1", "rules": ["L2.2"],
                                  "repro": {"input": "i", "expected": "reject", "actual": "ok"}})
        report = score_landing.evaluate(rubric, result, partial=False)
        self.assertEqual(report["total"], 59.0)
        self.assertFalse(report["accepted"])


class RoundDiffTest(unittest.TestCase):
    def test_classify(self) -> None:
        d = lambda s: {"status": s}  # noqa: E731
        self.assertEqual(round_diff.classify(d("open"), d("fixed")), "已修复")
        self.assertEqual(round_diff.classify(d("open"), d("partial")), "部分修复")
        self.assertEqual(round_diff.classify(d("partial"), d("open")), "未修复")
        self.assertEqual(round_diff.classify(d("fixed"), d("open")), "回归")
        self.assertEqual(round_diff.classify(None, d("open")), "新缺陷")
        self.assertEqual(round_diff.classify(d("open"), None), "未复核")

    def test_cli_reports_regression(self) -> None:
        rubric = json.loads((SKILL / "references/rubric.json").read_text(encoding="utf-8"))
        prev = score_landing.all_pass_result(rubric)
        prev["defects"] = [{"id": "D1", "severity": "P2", "status": "fixed", "title": "t", "fix_evidence": "x"}]
        cur = json.loads(json.dumps(prev))
        cur["defects"][0].update(status="open", location="a.py:1",
                                 repro={"input": "i", "expected": "e", "actual": "a"})
        cur["defects"].append({"id": "D2", "severity": "P1", "status": "open", "title": "n", "rules": ["L4.3"],
                               "location": "b.py:2", "repro": {"input": "i", "expected": "e", "actual": "a"}})
        cur["rules"]["L4.3"]["score"] = 0
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / "r1.json", Path(tmp) / "r2.json"
            a.write_text(json.dumps(prev), encoding="utf-8")
            b.write_text(json.dumps(cur), encoding="utf-8")
            proc = run(str(SCRIPTS / "round_diff.py"), str(a), str(b), "--fail-on-regression")
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("| D1 | P2 | fixed | open | 回归", proc.stdout)
        self.assertIn("新缺陷", proc.stdout)
        self.assertIn("L4.3", proc.stdout)


if __name__ == "__main__":
    unittest.main()
