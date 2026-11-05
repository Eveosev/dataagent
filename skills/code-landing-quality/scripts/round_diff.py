#!/usr/bin/env python3
"""Compare two review rounds of the same package and classify every change.

Usage:
  python3 round_diff.py r5.score.json r6.score.json
  python3 round_diff.py r5.score.json r6.score.json --out r6-diff.md --fail-on-regression

Both inputs are filled result JSONs (score_landing.py format). Output sections:
baseline (snapshot change), score and gates, defects, rules, checklist.

Defect verdicts (by defect id):
  已修复      previous open/partial  -> current fixed
  部分修复    previous open/partial  -> current partial
  未修复      previous open/partial  -> current open
  回归        previous fixed         -> current open/partial
  新缺陷      id not in previous
  未复核      previous open/partial, id absent from current (the reviewer must re-check it)
  已豁免      current waived

Exit codes: 0 ok, 1 regression found with --fail-on-regression, 2 bad input.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OPEN = ("open", "partial")


def load_scorer(path: Path):
    spec = importlib.util.spec_from_file_location("score_landing", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def evaluate(scorer, rubric: dict, result: dict) -> tuple[dict | None, str]:
    try:
        return scorer.evaluate(rubric, result, partial=False,
                               allow_version_mismatch=result.get("rubric_version") != rubric["version"]), ""
    except scorer.InvalidResult as exc:
        return None, str(exc)


def classify(prev: dict | None, cur: dict | None) -> str:
    if prev is None:
        return "新缺陷"
    if cur is None:
        return "未复核" if prev["status"] in OPEN else "上轮已关闭"
    if cur["status"] == "waived":
        return "已豁免"
    if prev["status"] in OPEN:
        return {"fixed": "已修复", "partial": "部分修复", "open": "未修复"}[cur["status"]]
    if prev["status"] == "fixed" and cur["status"] in OPEN:
        return "回归"
    if prev["status"] == "waived" and cur["status"] in OPEN:
        return "豁免撤销"
    return "保持关闭"


def by_id(rows) -> dict:
    return {r["id"]: r for r in rows or [] if isinstance(r, dict) and "id" in r}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("previous", type=Path)
    parser.add_argument("current", type=Path)
    parser.add_argument("--rubric", type=Path)
    parser.add_argument("--scorer", type=Path, default=HERE / "score_landing.py")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--fail-on-regression", action="store_true")
    args = parser.parse_args()

    for path in (args.previous, args.current, args.scorer):
        if not path.is_file():
            print(f"not found: {path}", file=sys.stderr)
            return 2
    scorer = load_scorer(args.scorer)
    rubric_path = args.rubric or scorer.DEFAULT_RUBRIC
    rubric = json.loads(Path(rubric_path).read_text(encoding="utf-8"))
    prev = json.loads(args.previous.read_text(encoding="utf-8"))
    cur = json.loads(args.current.read_text(encoding="utf-8"))
    p_rep, p_err = evaluate(scorer, rubric, prev)
    c_rep, c_err = evaluate(scorer, rubric, cur)

    out: list[str] = []
    name = lambda r, f: r.get("round") or f.stem  # noqa: E731
    pn, cn = name(prev, args.previous), name(cur, args.current)
    out.append(f"# 轮次对比 — {cur.get('scope') or prev.get('scope')}：{pn} → {cn}")
    out.append("")

    out.append("## 基线")
    out.append("")
    out.append("| 项 | " + pn + " | " + cn + " |")
    out.append("|-|-|-|")
    out.append(f"| 日期 | {prev.get('date', '')} | {cur.get('date', '')} |")
    out.append(f"| rubric | {prev.get('rubric_version', '')} | {cur.get('rubric_version', '')} |")
    pkgs = sorted(set(prev.get("snapshot", {})) | set(cur.get("snapshot", {})))
    unchanged = []
    for pkg in pkgs:
        a, b = prev.get("snapshot", {}).get(pkg, "—"), cur.get("snapshot", {}).get(pkg, "—")
        out.append(f"| snapshot {pkg} | `{a[:19]}` | `{b[:19]}` |")
        if a == b and a != "—":
            unchanged.append(pkg)
    out.append("")
    if unchanged:
        out.append(f"源码快照未变：{', '.join(unchanged)}。本轮结论与上轮不同只能来自判定变化，需说明原因。")
        out.append("")
    if prev.get("rubric_version") != cur.get("rubric_version"):
        out.append("两轮 rubric 版本不同：总分不可直接比较，只比较缺陷与清单。")
        out.append("")

    out.append("## 分数与闸门")
    out.append("")
    for label, rep, err in ((pn, p_rep, p_err), (cn, c_rep, c_err)):
        if rep is None:
            out.append(f"- {label}：结果无效（{err.splitlines()[0]}）")
        else:
            gates = ", ".join(f"{g['gate']}" for g in rep["gates"]) or "无"
            out.append(f"- {label}：{rep['total']}（{rep['grade']['grade']}），"
                       f"{'可验收' if rep['accepted'] else '不可验收'}；闸门 {gates}")
    out.append("")

    regressions: list[str] = []

    out.append("## 缺陷")
    out.append("")
    pd, cd = by_id(prev.get("defects")), by_id(cur.get("defects"))
    if prev.get("defects") is None or cur.get("defects") is None:
        out.append("至少一轮未声明缺陷清单（defects=null），无法逐条对比。")
        out.append("")
    rows = []
    for did in list(pd) + [k for k in cd if k not in pd]:
        verdict = classify(pd.get(did), cd.get(did))
        ref = cd.get(did) or pd.get(did)
        rows.append((did, ref.get("severity", ""), (pd.get(did) or {}).get("status", "—"),
                     (cd.get(did) or {}).get("status", "—"), verdict, ref.get("title", ""), ref.get("location", "")))
        if verdict in ("回归", "豁免撤销"):
            regressions.append(f"缺陷 {did} {verdict}")
    if rows:
        out.append(f"| ID | 级 | {pn} | {cn} | 结论 | 问题 | 位置 |")
        out.append("|-|-|-|-|-|-|-|")
        order = ["回归", "新缺陷", "未修复", "部分修复", "未复核", "豁免撤销", "已修复", "已豁免", "保持关闭", "上轮已关闭"]
        for row in sorted(rows, key=lambda r: (order.index(r[4]), r[1], r[0])):
            out.append("| " + " | ".join(str(x) for x in row) + " |")
        out.append("")
        counts: dict[str, int] = {}
        for row in rows:
            counts[row[4]] = counts.get(row[4], 0) + 1
        out.append("计数：" + "，".join(f"{k} {counts[k]}" for k in order if k in counts))
        out.append("")
    missing = [r[0] for r in rows if r[4] == "未复核"]
    if missing:
        out.append(f"未复核的上轮缺陷必须在本轮重跑原复现：{', '.join(missing)}")
        out.append("")

    out.append("## 规则")
    out.append("")
    if p_rep and c_rep:
        better, worse, lost = [], [], []
        for rid in c_rep["states"]:
            a, b = p_rep["states"].get(rid), c_rep["states"][rid]
            if a == b:
                continue
            if a == "fail" and b == "pass":
                better.append(rid)
            elif a == "pass" and b == "fail":
                worse.append(rid)
            elif a in ("pass", "fail") and b not in ("pass", "fail", "na"):
                lost.append(f"{rid}({a}→{b})")
        out.append(f"- 0→1：{', '.join(better) or '无'}")
        out.append(f"- 1→0（退化）：{', '.join(worse) or '无'}")
        out.append(f"- 已判定→未测量：{', '.join(lost) or '无'}")
        regressions += [f"规则 {r} 1→0" for r in worse]
        for hid, item in c_rep["lights"].items():
            before = p_rep["lights"].get(hid, {}).get("light")
            if before == "green" and item["light"] == "red":
                regressions.append(f"硬规则 {hid} green→red")
                out.append(f"- 硬规则 {hid}：green → red")
    else:
        out.append("至少一轮结果无效，跳过规则对比。")
    out.append("")

    out.append("## 方案清单")
    out.append("")
    pc, cc = prev.get("checklist"), cur.get("checklist")
    if not (isinstance(pc, dict) and isinstance(cc, dict)):
        out.append("至少一轮未提交清单（checklist=null）。")
    else:
        pi, ci = by_id(pc.get("items")), by_id(cc.get("items"))
        done = lambda items: sum(1 for i in items.values() if i.get("verdict") == "done")  # noqa: E731
        out.append(f"- 方案版本：{pc.get('plan_version', '')} → {cc.get('plan_version', '')}")
        out.append(f"- done：{done(pi)}/{len(pi)} → {done(ci)}/{len(ci)}")
        back = [k for k in ci if pi.get(k, {}).get("verdict") == "done" and ci[k].get("verdict") != "done"]
        new = [k for k in ci if k not in pi]
        gone = [k for k in pi if k not in ci]
        out.append(f"- done→未完成（退化）：{', '.join(back) or '无'}")
        out.append(f"- 新增条目：{len(new)}；移除条目：{len(gone)}")
        regressions += [f"清单 {k} done→{ci[k].get('verdict')}" for k in back]
    out.append("")

    out.append("## 退化汇总")
    out.append("")
    out.extend(f"- {r}" for r in regressions) if regressions else out.append("- 无")
    out.append("")

    text = "\n".join(out)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"wrote {args.out}", file=sys.stderr)
    print(text)
    return 1 if (regressions and args.fail_on_regression) else 0


if __name__ == "__main__":
    raise SystemExit(main())
