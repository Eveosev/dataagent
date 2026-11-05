#!/usr/bin/env python3
"""Measure one package, optionally pre-fill the machine-measurable rubric rules, then score.

Usage:
  python3 quality_run.py --repo . --package packages/capabilities/foo
  python3 quality_run.py --repo . --package pkg --fill review/foo.score.json
  python3 quality_run.py --repo . --package pkg --result review/foo.score.json --out review/foo.report.md
  python3 quality_run.py --repo . --package pkgA --package pkgB          # measure only

Measurements: source snapshot, pytest, hygiene (TODO, bare/swallowing except via AST),
bundle drift, duplicate rate (package + sibling packages), cyclomatic complexity
(radon when installed, otherwise an AST implementation of radon's counting rules),
function/module size, and rubric/scorer copy drift.

--fill writes A1.1, A5.1, A5.2, A5.3, hard rule D1 and (only when it fails) A10.1
into the result file with measured_by=quality_run, plus scope/snapshot/rubric_version.
Every other rule stays for the reviewer. --fill and --result take exactly one package.

Exit codes: 0 pass, 1 gate failure, 2 bad input.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from snapshot import tree_digest  # noqa: E402

SKILL = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".venv", "venv", "__pycache__", ".pytest_cache", "node_modules", "dist", "build", ".git"}
FALLBACK_SKIP = {"tests", "test", "packaging", "examples", "scripts"}
PYTEST_TIMEOUT = 900
WINDOW = 5
DUP_LIMIT = 3.0
CC10_LIMIT = 7.3
CC25_LIMIT = 1.1
FUNC_LINES = 300
MODULE_LINES = 1500
TRIVIAL = re.compile(r"^[\W_]{0,3}$")


def sh(cmd: list[str], cwd: Path, timeout: int = PYTEST_TIMEOUT) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def py_files(root: Path, extra_skip: set[str] = frozenset()) -> list[Path]:
    out = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root).parts
        if any(part in SKIP_DIRS or part in extra_skip for part in rel):
            continue
        out.append(path)
    return sorted(out)


def production_files(pkg: Path) -> list[Path]:
    src = pkg / "src"
    if src.is_dir():
        return py_files(src)
    return py_files(pkg, FALLBACK_SKIP)


def rel(path: Path, repo: Path) -> str:
    try:
        return path.relative_to(repo).as_posix()
    except ValueError:
        return path.as_posix()


def python_for(pkg: Path) -> tuple[str, bool]:
    venv = pkg / ".venv" / "bin" / "python"
    if venv.exists():
        return str(venv), True
    return sys.executable, False


def parse(path: Path) -> ast.AST | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=str(path))
    except SyntaxError:
        return None


# ---------------------------------------------------------------- tests


def run_tests(pkg: Path) -> dict:
    python, isolated = python_for(pkg)
    cmd = [python, "-m", "pytest", "-p", "no:warnings"]
    try:
        proc = sh(cmd, pkg)
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "passed": None, "failed": None, "errors": None,
                "isolated_venv": isolated, "command": " ".join(cmd), "tail": ""}
    text = proc.stdout + proc.stderr

    def count(pattern: str) -> int:
        m = re.search(pattern, text)
        return int(m.group(1)) if m else 0

    if proc.returncode == 0:
        status = "ok"
    elif proc.returncode == 5:
        status = "no-tests"
    else:
        status = "fail"
    return {
        "status": status,
        "passed": count(r"(\d+) passed"),
        "failed": count(r"(\d+) failed"),
        "errors": count(r"(\d+) error"),
        "isolated_venv": isolated,
        "command": f"cd {pkg.name} && {'.venv/bin/python' if isolated else 'python3'} -m pytest -p no:warnings",
        "tail": "\n".join(text.strip().splitlines()[-3:]),
    }


# ---------------------------------------------------------------- hygiene


def hygiene(pkg: Path, repo: Path) -> dict:
    todo = 0
    bare: list[str] = []
    swallow: list[str] = []
    files = production_files(pkg)
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        todo += len(re.findall(r"\b(TODO|FIXME|XXX)\b", text))
        tree = parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            where = f"{rel(path, repo)}:{node.lineno}"
            if node.type is None:
                bare.append(where)
            if len(node.body) == 1 and isinstance(node.body[0], (ast.Pass, ast.Continue)):
                swallow.append(where)
            elif (len(node.body) == 1 and isinstance(node.body[0], ast.Expr)
                  and isinstance(node.body[0].value, ast.Constant) and node.body[0].value.value is Ellipsis):
                swallow.append(where)
    pyc = len([p for p in pkg.rglob("*.pyc") if not any(part in SKIP_DIRS - {"__pycache__"} for part in p.parts)])
    caches = len([p for p in pkg.rglob("__pycache__")
                  if p.is_dir() and not any(part in SKIP_DIRS - {"__pycache__"} for part in p.parts)])
    return {"files": len(files), "todo": todo, "bare_except": bare, "swallow": swallow,
            "pyc": pyc, "pycache_dirs": caches}


# ---------------------------------------------------------------- bundle drift


def package_module(pkg: Path) -> str | None:
    src = pkg / "src"
    if not src.is_dir():
        return None
    name = ""
    pyproject = pkg / "pyproject.toml"
    if pyproject.is_file():
        match = re.search(r'^name\s*=\s*"([^"]+)"', pyproject.read_text(encoding="utf-8"), re.MULTILINE)
        if match:
            name = match.group(1).replace("-", "_")
    if name and (src / name).is_dir():
        return name
    own = [d.name for d in src.iterdir() if d.is_dir() and d.name != "__pycache__" and not d.name.endswith(".egg-info")]
    return own[0] if len(own) == 1 else None


def bundle_drift(pkg: Path) -> dict | None:
    bundle_root = pkg / "packaging" / "bundle" / "src"
    module = package_module(pkg)
    if not (bundle_root.is_dir() and module):
        return None
    src = pkg / "src" / module
    bundle = bundle_root / module
    vendored = sorted(d.name for d in bundle_root.iterdir()
                      if d.is_dir() and d.name not in (module, "__pycache__"))
    if not bundle.is_dir():
        return {"changed": [], "missing": [module], "extra": [], "vendored": vendored, "ok": False}

    def tree(root: Path) -> dict:
        return {p.relative_to(root): p for p in root.rglob("*")
                if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"}

    left, right = tree(src), tree(bundle)
    changed = sorted(str(k) for k in left.keys() & right.keys() if digest(left[k]) != digest(right[k]))
    missing = sorted(str(k) for k in left.keys() - right.keys())
    extra = sorted(str(k) for k in right.keys() - left.keys())
    return {"changed": changed, "missing": missing, "extra": extra,
            "vendored": vendored, "ok": not (changed or missing or extra)}


# ---------------------------------------------------------------- duplication


def code_lines(path: Path) -> list[tuple[int, str]]:
    out = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#") or TRIVIAL.match(line):
            continue
        out.append((lineno, line))
    return out


def duplicate_rate(pkg: Path, peers: list[Path] | None = None, repo: Path | None = None) -> dict:
    """Share of the package's production lines inside a 5-line window seen twice or more.

    Windows run per file. A window repeated inside the package counts as internal;
    a window that also appears in a sibling package counts as cross-package.
    """
    repo = repo or pkg.parent
    own: list[tuple[Path, list[tuple[int, str]]]] = [(p, code_lines(p)) for p in production_files(pkg)]
    windows: dict[tuple[str, ...], list[tuple[str, Path, int]]] = defaultdict(list)

    def index(owner: str, path: Path, lines: list[tuple[int, str]]) -> None:
        for i in range(len(lines) - WINDOW + 1):
            windows[tuple(l for _, l in lines[i:i + WINDOW])].append((owner, path, i))

    for path, lines in own:
        index("self", path, lines)
    for peer in peers or []:
        for path in production_files(peer):
            index(peer.name, path, code_lines(path))

    total = sum(len(lines) for _, lines in own)
    internal: set[tuple[Path, int]] = set()
    cross: set[tuple[Path, int]] = set()
    groups = []
    lookup = dict(own)
    for key, hits in windows.items():
        mine = [h for h in hits if h[0] == "self"]
        if not mine or len(hits) < 2:
            continue
        others = [h for h in hits if h[0] != "self"]
        target = cross if others else internal
        for _, path, start in mine:
            target.update((path, start + k) for k in range(WINDOW))
        groups.append(hits)
    dup = internal | cross
    top = []
    shown: list[tuple[Path, int]] = []
    for hits in sorted(groups, key=len, reverse=True):
        if len(top) >= 5:
            break
        mine_starts = [(path, start) for owner, path, start in hits if owner == "self"]
        if any(p == q and abs(s - t) < WINDOW for p, s in mine_starts for q, t in shown):
            continue
        shown.extend(mine_starts)
        locs = []
        for owner, path, start in hits[:3]:
            lines = lookup.get(path) or code_lines(path)
            locs.append(f"{rel(path, repo)}:{lines[start][0]}")
        top.append(", ".join(locs) + (f" …(+{len(hits) - 3})" if len(hits) > 3 else ""))
    return {
        "rate": round(100 * len(dup) / total, 2) if total else 0.0,
        "dup_lines": len(dup),
        "internal_lines": len(internal - cross),
        "cross_lines": len(cross),
        "total_lines": total,
        "groups": len(groups),
        "peers": [p.name for p in peers or []],
        "top": top,
    }


# ---------------------------------------------------------------- complexity and size


class _CC(ast.NodeVisitor):
    """Cyclomatic complexity with radon's counting rules; nested defs are not added."""

    def __init__(self) -> None:
        self.value = 1

    def generic_visit(self, node: ast.AST) -> None:
        if isinstance(node, ast.Try) or type(node).__name__ == "TryStar":
            self.value += len(node.handlers) + bool(node.orelse)
        elif isinstance(node, ast.BoolOp):
            self.value += len(node.values) - 1
        elif isinstance(node, (ast.If, ast.IfExp)):
            self.value += 1
        elif isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
            self.value += 1 + bool(node.orelse)
        elif isinstance(node, ast.comprehension):
            self.value += 1 + len(node.ifs)
        elif isinstance(node, ast.Match):
            self.value += len([c for c in node.cases
                               if not (isinstance(c.pattern, ast.MatchAs) and c.pattern.pattern is None)])
        super().generic_visit(node)

    def visit_FunctionDef(self, node: ast.AST) -> None:  # nested defs are separate blocks
        return

    visit_AsyncFunctionDef = visit_FunctionDef
    visit_ClassDef = visit_FunctionDef
    visit_Lambda = generic_visit


def function_blocks(tree: ast.AST) -> list[ast.AST]:
    """Module-level functions and class methods (radon's top-level blocks)."""
    out = []
    for node in getattr(tree, "body", []):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append(node)
        elif isinstance(node, ast.ClassDef):
            out.extend(function_blocks(node))
    return out


def cc_of(fn: ast.AST) -> int:
    visitor = _CC()
    for child in fn.body:
        visitor.visit(child)
    return visitor.value


def complexity(pkg: Path, repo: Path) -> dict:
    files = production_files(pkg)
    numbered = {str(p): {n for n, _ in code_lines(p)} for p in files}
    total = sum(len(v) for v in numbered.values())

    def loc_of(path: Path, start: int, end: int) -> int:
        return max(1, sum(1 for n in numbered.get(str(path), ()) if start <= n <= end))

    if not total:
        return {"status": "unavailable", "reason": "no production lines"}
    blocks: list[tuple[str, int, int]] = []  # where, cc, loc
    method = ""
    python, _ = python_for(pkg)
    target = pkg / "src" if (pkg / "src").is_dir() else pkg
    try:
        proc = sh([python, "-m", "radon", "cc", "-j", str(target)], repo, timeout=300)
        data = json.loads(proc.stdout) if proc.returncode == 0 else None
    except (subprocess.TimeoutExpired, json.JSONDecodeError):
        data = None
    if isinstance(data, dict):
        method = "radon cc"
        wanted = {str(p) for p in files}
        for fname, block_list in data.items():
            if not isinstance(block_list, list) or str(Path(fname).resolve()) not in wanted:
                continue
            for block in block_list:
                if block.get("type") not in ("function", "method"):
                    continue
                path = Path(fname).resolve()
                loc = loc_of(path, block["lineno"], block.get("endline", block["lineno"]))
                blocks.append((f"{rel(path, repo)}:{block['lineno']}", block.get("complexity", 0), loc))
    else:
        method = "ast（radon 计数规则；radon 未安装）"
        for path in files:
            tree = parse(path)
            if tree is None:
                continue
            for fn in function_blocks(tree):
                loc = loc_of(path, fn.lineno, fn.end_lineno)
                blocks.append((f"{rel(path, repo)}:{fn.lineno}", cc_of(fn), loc))
    over10 = sum(loc for _, cc, loc in blocks if cc > 10)
    over25 = sum(loc for _, cc, loc in blocks if cc > 25)
    worst = sorted(blocks, key=lambda b: b[1], reverse=True)[:5]
    return {
        "status": "ok",
        "method": method,
        "functions": len(blocks),
        "total_lines": total,
        "share_cc10": round(100 * over10 / total, 2),
        "share_cc25": round(100 * over25 / total, 2),
        "worst": [f"{w} CC={cc}（{loc} 行代码）" for w, cc, loc in worst],
    }


def sizes(pkg: Path, repo: Path) -> dict:
    long_funcs: list[str] = []
    long_modules: list[str] = []
    for path in production_files(pkg):
        text = path.read_text(encoding="utf-8", errors="replace")
        n = len(text.splitlines())
        if n > MODULE_LINES:
            long_modules.append(f"{rel(path, repo)}（{n} 行）")
        tree = parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                loc = node.end_lineno - node.lineno + 1
                if loc > FUNC_LINES:
                    long_funcs.append(f"{rel(path, repo)}:{node.lineno} {node.name}（{loc} 行）")
    return {"long_functions": long_funcs, "long_modules": long_modules}


# ---------------------------------------------------------------- fill and score


def rule_entry(score: int, evidence: str) -> dict:
    return {"score": score, "evidence": evidence, "measured_by": "quality_run"}


def measured_rules(report: dict) -> tuple[dict, dict]:
    rules: dict[str, dict] = {}
    hard: dict[str, dict] = {}
    dup = report.get("dup")
    if dup:
        peers = f"；同级包 {len(dup['peers'])} 个" if dup["peers"] else "；仅包内"
        ev = (f"quality_run 重复率 {dup['rate']}%（{dup['dup_lines']}/{dup['total_lines']} 行，"
              f"包内 {dup['internal_lines']}、跨包 {dup['cross_lines']}{peers}）")
        if dup["top"]:
            ev += "；例：" + " | ".join(dup["top"][:2])
        ok = dup["rate"] <= DUP_LIMIT
        rules["A1.1"] = rule_entry(1 if ok else 0, ev)
        hard["D1"] = {"light": "green" if ok else "red", "evidence": ev, "measured_by": "quality_run"}
    cc = report.get("complexity", {})
    if cc.get("status") == "ok":
        worst = "；最高：" + " | ".join(cc["worst"][:2]) if cc["worst"] else ""
        rules["A5.1"] = rule_entry(1 if cc["share_cc10"] <= CC10_LIMIT else 0,
                                   f"{cc['method']}：CC>10 LOC 占比 {cc['share_cc10']}%（阈 {CC10_LIMIT}%）{worst}")
        rules["A5.2"] = rule_entry(1 if cc["share_cc25"] <= CC25_LIMIT else 0,
                                   f"{cc['method']}：CC>25 LOC 占比 {cc['share_cc25']}%（阈 {CC25_LIMIT}%）{worst}")
    size = report["sizes"]
    bad = size["long_functions"] + size["long_modules"]
    rules["A5.3"] = rule_entry(0 if bad else 1,
                               ("超长：" + "；".join(bad[:5])) if bad
                               else f"quality_run ast：无 >{FUNC_LINES} 行函数、无 >{MODULE_LINES} 行模块")
    hyg = report["hygiene"]
    if hyg["bare_except"] or hyg["swallow"]:
        locs = hyg["bare_except"][:3] + hyg["swallow"][:3]
        rules["A10.1"] = rule_entry(0, f"裸 except {len(hyg['bare_except'])} / 吞错 {len(hyg['swallow'])}：" + "；".join(locs))
    return rules, hard


def template_from(scorer: Path, rubric: Path) -> dict:
    proc = sh([sys.executable, str(scorer), "--rubric", str(rubric), "--template"], scorer.parent, timeout=60)
    if proc.returncode != 0:
        raise SystemExit(f"scorer --template failed: {proc.stderr.strip()[:300]}")
    return json.loads(proc.stdout)


def fill(path: Path, report: dict, scorer: Path, rubric: Path, pkg: Path) -> list[str]:
    base = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else template_from(scorer, rubric)
    rubric_data = json.loads(rubric.read_text(encoding="utf-8"))
    conflicts: list[str] = []
    rules, hard = measured_rules(report)
    for section, values, key in (("rules", rules, "score"), ("hard_rules", hard, "light")):
        target = base.setdefault(section, {})
        for rid, entry in values.items():
            old = target.get(rid) or {}
            if old.get(key) not in (None, "unknown") and old.get("measured_by") != "quality_run" \
                    and old.get(key) != entry[key]:
                conflicts.append(f"{rid}: 人工填写 {old.get(key)!r} 与测量 {entry[key]!r} 不一致，已按测量覆盖（原证据：{old.get('evidence', '')[:80]}）")
            target[rid] = {**{k: v for k, v in old.items() if k == "na_reason"}, **entry}
    base["scope"] = base.get("scope") or pkg.name
    base["rubric_version"] = rubric_data["version"]
    base.setdefault("snapshot", {})[pkg.name] = report["snapshot"]["digest"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(base, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return conflicts


def score(repo: Path, result: Path, rubric: Path, scorer: Path) -> dict:
    proc = sh([sys.executable, str(scorer), "--rubric", str(rubric), "--result", str(result), "--json"], repo)
    if proc.returncode == 2 or not proc.stdout.strip():
        return {"status": "invalid", "reason": (proc.stderr or proc.stdout).strip()[:600]}
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"status": "error", "reason": "scorer output is not JSON"}
    return {
        "status": "ok",
        "total": data["total"],
        "grade": data["grade"]["grade"],
        "label": data["grade"]["label"],
        "accepted": data["accepted"],
        "coverage": data["coverage"],
        "gates": data["gates"],
        "zeros": [z[0] for z in data["zeros"]],
        "not_measured": [z[0] for z in data["not_measured"]],
        "sha": data.get("rubric_sha256", "")[:12],
    }


# ---------------------------------------------------------------- report


def render(report: dict) -> str:
    lines = [f"# 质检报告 — {report['package']}", ""]
    snap = report["snapshot"]
    lines.append(f"snapshot: `{snap['digest']}`（{snap['files']} 文件）｜rubric: `{report['rubric']}`")
    lines.append("")
    lines.append("## 结论")
    lines.append("")
    sc = report.get("score", {})
    if sc.get("status") == "ok":
        gates = "；".join(f"{g['gate']} 封顶 {g['cap']}" for g in sc["gates"]) or "无"
        lines.append(f"- 总分 **{sc['total']}**（{sc['grade']} {sc['label']}），"
                     f"{'可验收' if sc['accepted'] else '不可验收'}，证据覆盖 {sc['coverage']}%，rubric sha {sc['sha']}")
        lines.append(f"- 闸门：{gates}")
    else:
        lines.append(f"- 未评分：{sc.get('reason', 'no --result')}")
    tests = report["tests"]
    lines.append(f"- 测试：{tests['status']}（{tests['passed']} passed / {tests['failed']} failed / "
                 f"{tests.get('errors')} errors），独立 venv={tests['isolated_venv']}")
    if tests.get("command"):
        lines.append(f"- 复跑：`{tests['command']}`")
    lines.append("")

    lines.append("## 测量")
    lines.append("")
    lines.append("| 项 | 结果 |")
    lines.append("|-|-|")
    hyg = report["hygiene"]
    lines.append(f"| 生产文件 | {hyg['files']} |")
    lines.append(f"| TODO/FIXME | {hyg['todo']} |")
    lines.append(f"| 裸 except / 吞错 | {len(hyg['bare_except'])} / {len(hyg['swallow'])} |")
    lines.append(f"| pyc / __pycache__ | {hyg['pyc']} / {hyg['pycache_dirs']} |")
    dup = report.get("dup")
    if dup:
        lines.append(f"| 重复率 | {dup['rate']}%（{dup['dup_lines']}/{dup['total_lines']} 行；包内 {dup['internal_lines']}，"
                     f"跨包 {dup['cross_lines']}；{dup['groups']} 组） |")
    else:
        lines.append("| 重复率 | 未测量（--skip-dup） |")
    drift = report["drift"]
    if drift is None:
        lines.append("| bundle 漂移 | 无 bundle |")
    else:
        vend = f"；vendored: {', '.join(drift['vendored'])}" if drift["vendored"] else ""
        state = "一致" if drift["ok"] else (f"不一致（改 {len(drift['changed'])} / 缺 {len(drift['missing'])} / "
                                           f"多 {len(drift['extra'])}）")
        lines.append(f"| bundle 漂移 | {state}{vend} |")
    cc = report["complexity"]
    if cc.get("status") == "ok":
        lines.append(f"| CC>10 / CC>25 LOC 占比 | {cc['share_cc10']}% / {cc['share_cc25']}%（{cc['method']}，{cc['functions']} 函数） |")
    else:
        lines.append(f"| 复杂度 | 未测量（{cc.get('reason', cc.get('status'))}） |")
    size = report["sizes"]
    lines.append(f"| 超长函数 / 模块 | {len(size['long_functions'])} / {len(size['long_modules'])} |")
    copies = report["copies"]
    lines.append(f"| rubric / scorer 副本 | {copies['rubric']} / {copies['scorer']} |")
    lines.append("")

    detail = []
    if hyg["bare_except"] or hyg["swallow"]:
        detail += [f"- except：{w}" for w in (hyg["bare_except"] + hyg["swallow"])[:10]]
    if dup and dup["top"]:
        detail += [f"- 重复组：{t}" for t in dup["top"]]
    if cc.get("worst"):
        detail += [f"- 复杂度：{w}" for w in cc["worst"]]
    detail += [f"- 超长：{w}" for w in size["long_functions"] + size["long_modules"]]
    if detail:
        lines.append("## 位置")
        lines.append("")
        lines.extend(detail)
        lines.append("")

    if report.get("filled"):
        lines.append("## 已预填规则")
        lines.append("")
        lines.append(", ".join(report["filled"]) + "（measured_by=quality_run；其余规则由评审人填写）")
        for c in report.get("conflicts", []):
            lines.append(f"- 冲突：{c}")
        lines.append("")

    if sc.get("status") == "ok":
        lines.append("## 未通过 / 未测量")
        lines.append("")
        lines.append(f"- 得 0：{', '.join(sc['zeros']) or '无'}")
        lines.append(f"- 未测量：{', '.join(sc['not_measured']) or '无'}")
        lines.append("")

    lines.append("## 下一步")
    lines.append("")
    if report["failures"]:
        lines.extend(f"- {item}" for item in report["failures"])
    else:
        lines.append("- 无阻塞项；把本报告与 score JSON 一起归档。")
    lines.append("")
    return "\n".join(lines)


def resolve_standard(repo: Path, explicit: Path | None, repo_rel: str, skill_rel: str) -> Path:
    if explicit:
        return explicit.resolve()
    candidate = repo / repo_rel
    return candidate.resolve() if candidate.is_file() else (SKILL / skill_rel).resolve()


def copy_state(repo_file: Path, skill_file: Path) -> str:
    if not repo_file.is_file():
        return "仅 skill 副本"
    if not skill_file.is_file():
        return "仅仓库副本"
    return "一致" if digest(repo_file) == digest(skill_file) else "不一致"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--package", type=Path, action="append", required=True)
    parser.add_argument("--fill", type=Path, help="write machine-measured rules into this result JSON")
    parser.add_argument("--result", type=Path, help="score this filled result JSON")
    parser.add_argument("--rubric", type=Path)
    parser.add_argument("--scorer", type=Path)
    parser.add_argument("--peers", type=Path, help="directory of sibling packages (default: the package's parent)")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--fail-under", type=float, default=80)
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--skip-dup", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if (args.fill or args.result) and len(args.package) != 1:
        print("--fill / --result take exactly one --package", file=sys.stderr)
        return 2
    repo = args.repo.resolve()
    rubric = resolve_standard(repo, args.rubric, "docs/standards/code-landing-rubric.json", "references/rubric.json")
    scorer = resolve_standard(repo, args.scorer, "docs/standards/score_landing.py", "scripts/score_landing.py")
    for path in (rubric, scorer):
        if not path.is_file():
            print(f"not found: {path}", file=sys.stderr)
            return 2
    copies = {
        "rubric": copy_state(repo / "docs/standards/code-landing-rubric.json", SKILL / "references/rubric.json"),
        "scorer": copy_state(repo / "docs/standards/score_landing.py", SKILL / "scripts/score_landing.py"),
    }

    reports = []
    exit_code = 0
    for raw in args.package:
        pkg = (raw if raw.is_absolute() else repo / raw).resolve()
        if not pkg.is_dir():
            print(f"package not found: {pkg}", file=sys.stderr)
            return 2
        peers_root = (args.peers.resolve() if args.peers else pkg.parent)
        peers = sorted(d for d in peers_root.iterdir()
                       if d.is_dir() and d.resolve() != pkg and not d.name.startswith(".") and production_files(d))
        report: dict = {"package": rel(pkg, repo), "repo": str(repo), "rubric": rel(rubric, repo), "copies": copies}
        report["snapshot"] = tree_digest(pkg)
        report["hygiene"] = hygiene(pkg, repo)
        report["tests"] = ({"status": "skipped", "passed": None, "failed": None, "errors": None,
                            "isolated_venv": None, "command": ""}
                           if args.skip_tests else run_tests(pkg))
        report["drift"] = bundle_drift(pkg)
        report["dup"] = None if args.skip_dup else duplicate_rate(pkg, peers, repo)
        report["complexity"] = complexity(pkg, repo)
        report["sizes"] = sizes(pkg, repo)

        if args.fill:
            report["conflicts"] = fill(args.fill.resolve(), report, scorer, rubric, pkg)
            report["filled"] = sorted(set(measured_rules(report)[0]) | set(measured_rules(report)[1]))
        report["score"] = (score(repo, args.result.resolve(), rubric, scorer) if args.result
                           else {"status": "skipped", "reason": "未给 --result"})

        failures = []
        if args.skip_tests or args.skip_dup:
            failures.append("使用了 --skip-tests/--skip-dup：本报告不能用于验收")
        if report["tests"]["status"] in ("fail", "timeout", "no-tests"):
            failures.append(f"测试 {report['tests']['status']}：{report['tests'].get('tail', '')}")
        if report["drift"] and not report["drift"]["ok"]:
            d = report["drift"]
            failures.append(f"bundle 与 src 漂移：改 {len(d['changed'])} / 缺 {len(d['missing'])} / 多 {len(d['extra'])}")
        if report["dup"] and report["dup"]["rate"] > DUP_LIMIT:
            failures.append(f"重复率 {report['dup']['rate']}% > {DUP_LIMIT}%（A1.1=0，D1 red）")
        if report["hygiene"]["bare_except"] or report["hygiene"]["swallow"]:
            failures.append("存在裸 except 或吞错（A10.1=0）")
        if "不一致" in copies.values():
            failures.append("docs/standards 与 skill 内的 rubric/scorer 副本不一致：先同步再评分")
        for c in report.get("conflicts", []):
            failures.append(f"预填冲突：{c}")
        sc = report["score"]
        if sc.get("status") == "ok":
            if sc["gates"]:
                failures.append("闸门触发：" + ", ".join(f"{g['gate']}({', '.join(g['rules'][:4])})" for g in sc["gates"]))
            if sc["total"] < args.fail_under:
                failures.append(f"总分 {sc['total']} < {args.fail_under}")
        elif args.result:
            failures.append(f"评分失败：{sc.get('reason')}")
        report["failures"] = failures
        if failures:
            exit_code = 1
        reports.append(report)

    text = "\n".join(render(r) for r in reports)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"wrote {args.out}", file=sys.stderr)
    if args.json:
        print(json.dumps(reports, ensure_ascii=False, indent=2))
    else:
        print(text)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
