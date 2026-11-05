#!/usr/bin/env python3
"""Score a filled code-landing audit against the binary rubric (v2.1).

Usage:
  python3 score_landing.py --template > result.json
  python3 score_landing.py --result result.json
  python3 score_landing.py --result result.json --partial
  python3 score_landing.py --result result.json --fail-under 80
  python3 score_landing.py --result result.json --json
  python3 score_landing.py --self-test

Result format:
  {
    "scope": "dataagent-governance",
    "profile": "capability",              # contracts | runtime | capability | service
    "date": "2026-11-05",
    "round": "r6",
    "facts_ref": "agent-kernel@c1231ab",
    "snapshot": {"dataagent-governance": "sha256:..."},
    "rubric_version": "2.1",
    "rules": {
      "A1.1": {"score": 1, "evidence": "quality_run: 1.2% (34/2810)"},
      "L3.3": {"score": null, "na_reason": "无外发路径：grep egress/http 0 处"}
    },
    "hard_rules": {"R01": {"light": "green", "evidence": "..."}},
    "checklist": {"source": "plan.md", "plan_version": "v0.3",
                  "items": [{"id": "5.2#a1b2c3", "text": "...", "verdict": "done", "evidence": "..."}]},
    "defects": [{"id": "D1", "severity": "P0", "status": "open", "title": "...",
                 "location": "file.py:12", "rules": ["L2.2"],
                 "repro": {"input": "...", "expected": "...", "actual": "..."}}]
  }

Rules:
- Binary scores only. null, or 0/1 without evidence, is "not measured": 0 points,
  GATE-UNMEASURED. na is accepted only for allow_na rules listed in the chosen
  profile's may_na, with a non-empty na_reason.
- A rule absent from the result counts as 0 unless --partial; it is always listed.
- Hard rules are non-compensatory. A light without evidence is unknown.
- checklist / defects set to null mean "not reviewed" and cap the total.
- Open or partial P0/P1 defects cap the total; P0 cannot be waived.
- Contradictions (hard rule vs mirror rule, open defect vs passing rule,
  L2.1 vs checklist) make the result invalid: exit 2, no score.
- Every cap is read from rubric["gates"]; --self-test checks the caps stay
  below the grade/publish boundaries so a relaxed rubric turns the test red.

Exit codes: 0 ok, 1 below --fail-under or gate triggered, 2 invalid input.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_RUBRIC = ROOT / "code-landing-rubric.json"
if not DEFAULT_RUBRIC.is_file():
    DEFAULT_RUBRIC = ROOT.parent / "references" / "rubric.json"
LIGHTS = ("green", "red", "unknown", "na")
GATE_CONDITIONS = (
    "hard_rule_red", "defect_p0_open", "defect_p1_open", "checklist_incomplete",
    "hard_rule_unknown", "rule_not_measured", "checklist_missing", "defects_missing",
)
SEVERITIES = ("P0", "P1", "P2")
DEFECT_STATUS = ("open", "partial", "fixed", "waived")
VERDICTS = ("done", "partial", "not_done", "na", "waived")
DOC_ONLY = re.compile(r"\.(md|txt|rst)\b", re.IGNORECASE)
CODE_REF = re.compile(r"\.(py|rs|ts|js|toml|json|sql|yaml|yml|sh)\b|:\d+|`[^`]+`|\$ |->|→|=>")


class InvalidResult(Exception):
    pass


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        sys.exit(f"file not found: {path}")
    except json.JSONDecodeError as exc:
        sys.exit(f"invalid JSON in {path}: {exc}")


def has_text(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def index_rules(rubric: dict) -> dict[str, dict]:
    rules: dict[str, dict] = {}
    for dim in rubric["dimensions"]:
        for rule in dim["rules"]:
            rid = rule["id"]
            if rid in rules:
                sys.exit(f"duplicate rule id: {rid}")
            rules[rid] = {**rule, "dimension": dim["id"], "dimension_name": dim["name"]}
    return rules


def index_hard(rubric: dict) -> dict[str, dict]:
    hard: dict[str, dict] = {}
    for rule in rubric["hard_rules"]:
        if rule["id"] in hard:
            sys.exit(f"duplicate hard rule id: {rule['id']}")
        hard[rule["id"]] = rule
    return hard


def caps(rubric: dict) -> dict[str, dict]:
    return {g["when"]: g for g in rubric.get("gates", [])}


def validate(rubric: dict, rules: dict[str, dict], hard: dict[str, dict]) -> None:
    total = sum(r["weight"] for r in rules.values())
    if total != 100:
        sys.exit(f"rubric rule weights must sum to 100, got {total}")
    dim_total = sum(d["weight"] for d in rubric["dimensions"])
    if dim_total != 100:
        sys.exit(f"dimension weights must sum to 100, got {dim_total}")
    for dim in rubric["dimensions"]:
        s = sum(r["weight"] for r in dim["rules"])
        if s != dim["weight"]:
            sys.exit(f"dimension {dim['id']} rules sum to {s}, expected {dim['weight']}")
    for hard_id, rule in hard.items():
        if rule.get("gate") not in LIGHTS:
            sys.exit(f"hard rule {hard_id} has invalid gate: {rule.get('gate')}")
        for mid in rule.get("mirror", []):
            if mid not in rules:
                sys.exit(f"hard rule {hard_id} mirrors unknown rule {mid}")
    seen = set()
    for gate in rubric.get("gates", []):
        if gate.get("when") not in GATE_CONDITIONS:
            sys.exit(f"gate {gate['id']} has unknown condition: {gate.get('when')}")
        if not isinstance(gate.get("cap"), int):
            sys.exit(f"gate {gate['id']} needs an integer cap")
        seen.add(gate["when"])
    missing = set(GATE_CONDITIONS) - seen
    if missing:
        sys.exit(f"rubric gates missing conditions: {sorted(missing)}")
    for name, profile in rubric.get("profiles", {}).items():
        for rid in profile.get("may_na", []):
            if rid not in rules or not rules[rid].get("allow_na"):
                sys.exit(f"profile {name} lists {rid} in may_na but the rule does not allow na")


def template(rubric: dict) -> dict:
    rules: dict[str, dict] = {}
    for dim in rubric["dimensions"]:
        for rule in dim["rules"]:
            rules[rule["id"]] = {
                "score": None,
                "evidence": "",
                **({"na_reason": ""} if rule.get("allow_na") else {}),
            }
    hard = {r["id"]: {"light": "unknown", "evidence": ""} for r in rubric["hard_rules"]}
    return {
        "scope": "",
        "profile": "",
        "date": "",
        "round": "",
        "facts_ref": "",
        "snapshot": {},
        "rubric_version": rubric["version"],
        "rules": rules,
        "hard_rules": hard,
        "checklist": None,
        "defects": None,
    }


def grade_for(score: float, rubric: dict) -> dict:
    for band in rubric["grades"]:
        if score >= band["min"]:
            return band
    return rubric["grades"][-1]


def rule_state(rid: str, rule: dict, entry: dict | None, may_na: set[str]) -> tuple[str, str]:
    """Return (state, note): state in pass/fail/na/unmeasured/missing/invalid."""
    if entry is None:
        return "missing", ""
    score = entry.get("score")
    if score is None:
        if has_text(entry.get("na_reason")):
            if rule.get("allow_na") and rid in may_na:
                return "na", entry["na_reason"].strip()
            return "unmeasured", "na 不在 profile.may_na 内"
        return "unmeasured", ""
    if score not in (0, 1) or isinstance(score, bool):
        return "invalid", f"score={score!r}"
    if not has_text(entry.get("evidence")):
        return "unmeasured", "无 evidence"
    return ("pass" if score == 1 else "fail"), ""


def check_checklist(checklist) -> dict:
    if checklist is None:
        return {"declared": False}
    items = checklist.get("items", []) if isinstance(checklist, dict) else []
    counts = {v: 0 for v in VERDICTS}
    counts["unjudged"] = 0
    open_items: list[str] = []
    problems: list[str] = []
    for item in items:
        iid = item.get("id", "?")
        verdict = item.get("verdict")
        if verdict not in VERDICTS:
            counts["unjudged"] += 1
            open_items.append(iid)
            continue
        if verdict == "done" and not has_text(item.get("evidence")):
            counts["unjudged"] += 1
            open_items.append(iid)
            problems.append(f"{iid}: done 无 evidence，按未完成计")
            continue
        if verdict == "na" and not has_text(item.get("evidence")):
            counts["unjudged"] += 1
            open_items.append(iid)
            problems.append(f"{iid}: na 无理由，按未完成计")
            continue
        if verdict == "waived" and not valid_waiver(item.get("waiver")):
            counts["unjudged"] += 1
            open_items.append(iid)
            problems.append(f"{iid}: waived 缺 waiver{{by,date,reason}}，按未完成计")
            continue
        counts[verdict] += 1
        if verdict in ("partial", "not_done"):
            open_items.append(iid)
    applicable = len(items) - counts["na"] - counts["waived"]
    rate = round(100 * counts["done"] / applicable, 1) if applicable else 100.0
    return {"declared": True, "total": len(items), "counts": counts, "applicable": applicable,
            "completion": rate, "open": open_items, "problems": problems,
            "complete": bool(items) and not open_items,
            "source": checklist.get("source", "") if isinstance(checklist, dict) else "",
            "plan_version": checklist.get("plan_version", "") if isinstance(checklist, dict) else ""}


def valid_waiver(waiver) -> bool:
    return isinstance(waiver, dict) and all(has_text(waiver.get(k)) for k in ("by", "date", "reason"))


def check_defects(defects) -> dict:
    if defects is None:
        return {"declared": False}
    if not isinstance(defects, list):
        raise InvalidResult("defects 必须是列表或 null")
    open_by: dict[str, list[str]] = {s: [] for s in SEVERITIES}
    problems: list[str] = []
    rows = []
    ids = set()
    for d in defects:
        did = d.get("id", "?")
        if did in ids:
            raise InvalidResult(f"缺陷 id 重复：{did}")
        ids.add(did)
        sev = d.get("severity")
        status = d.get("status")
        if sev not in SEVERITIES:
            raise InvalidResult(f"缺陷 {did} severity 非法：{sev!r}")
        if status not in DEFECT_STATUS:
            raise InvalidResult(f"缺陷 {did} status 非法：{status!r}")
        effective = status
        if status == "waived":
            if sev == "P0":
                problems.append(f"{did}: P0 不可豁免，按 open 计")
                effective = "open"
            elif not valid_waiver(d.get("waiver")):
                problems.append(f"{did}: waived 缺 waiver{{by,date,reason}}，按 open 计")
                effective = "open"
        if status == "fixed" and not has_text(d.get("fix_evidence")):
            problems.append(f"{did}: fixed 无 fix_evidence（复跑原复现的结果）")
        repro = d.get("repro") or {}
        if effective in ("open", "partial"):
            if not (isinstance(repro, dict) and all(has_text(repro.get(k)) for k in ("input", "expected", "actual"))):
                problems.append(f"{did}: 缺 repro{{input,expected,actual}}")
            if not has_text(d.get("location")):
                problems.append(f"{did}: 缺 location（file:line）")
            open_by[sev].append(did)
        rows.append({"id": did, "severity": sev, "status": status, "effective": effective,
                     "title": d.get("title", ""), "location": d.get("location", ""),
                     "rules": list(d.get("rules", []))})
    return {"declared": True, "rows": rows, "open": open_by, "problems": problems}


def evaluate(rubric: dict, result: dict, partial: bool, allow_version_mismatch: bool = False) -> dict:
    rules = index_rules(rubric)
    hard = index_hard(rubric)
    gate_def = caps(rubric)
    entries = result.get("rules", {}) or {}
    hard_entries = result.get("hard_rules", {}) or {}
    warnings: list[str] = []

    declared = result.get("rubric_version")
    if declared != rubric["version"]:
        msg = f"result.rubric_version={declared!r} 与 rubric {rubric['version']} 不一致"
        if not allow_version_mismatch:
            raise InvalidResult(msg + "；旧版本结果不重算，按新版本重新评测")
        warnings.append(msg)

    profiles = rubric.get("profiles", {})
    profile = result.get("profile") or ""
    if profiles and profile not in profiles:
        if allow_version_mismatch and not profile:
            warnings.append("未声明 profile（旧版本结果）：na 按规则自身 allow_na 判定")
            may_na: set[str] = {rid for rid, r in rules.items() if r.get("allow_na")}
        else:
            raise InvalidResult(f"result.profile 必填，取值 {sorted(profiles)}，当前 {profile!r}")
    else:
        may_na = set(profiles.get(profile, {}).get("may_na", []))

    unknown_ids = set(entries) - set(rules)
    if unknown_ids:
        raise InvalidResult(f"result 含未知规则 id：{sorted(unknown_ids)}")
    unknown_hard = set(hard_entries) - set(hard)
    if unknown_hard:
        raise InvalidResult(f"result 含未知硬规则 id：{sorted(unknown_hard)}")

    per_dim: dict[str, dict] = {
        d["id"]: {"name": d["name"], "weight": d["weight"], "num": 0.0, "den": 0.0,
                  "judged": 0, "total": len(d["rules"])}
        for d in rubric["dimensions"]
    }
    states: dict[str, str] = {}
    zeros: list[tuple[str, str]] = []
    missing: list[str] = []
    not_measured: list[tuple[str, str]] = []
    na: list[tuple[str, str]] = []
    invalid: list[str] = []
    na_weight = 0.0
    judged_weight = 0.0
    basis_weight: dict[str, float] = {}

    for rid, rule in rules.items():
        dim = per_dim[rule["dimension"]]
        entry = entries.get(rid)
        state, note = rule_state(rid, rule, entry, may_na)
        states[rid] = state
        if rule["weight"] == 0:
            dim["judged"] += 1 if state in ("pass", "fail") else 0
            continue
        if state == "missing":
            missing.append(rid)
            if partial:
                continue
            score = 0
        elif state == "na":
            na.append((rid, note))
            na_weight += rule["weight"]
            continue
        elif state == "unmeasured":
            not_measured.append((rid, note))
            score = 0
        elif state == "invalid":
            invalid.append(rid)
            score = 0
        else:
            score = 1 if state == "pass" else 0
            dim["judged"] += 1
            judged_weight += rule["weight"]
            basis = rule.get("basis", "?")
            basis_weight[basis] = basis_weight.get(basis, 0.0) + rule["weight"]
            ev = entries[rid].get("evidence", "")
            if DOC_ONLY.search(ev) and not CODE_REF.search(ev.replace(".md", "")):
                warnings.append(f"{rid}: 证据只引用文档")
        dim["num"] += rule["weight"] * score
        dim["den"] += rule["weight"]
        if score == 0:
            zeros.append((rid, rule["name"]))

    scored_weight = sum(d["den"] for d in per_dim.values())
    applicable = sum(r["weight"] for r in rules.values()) - na_weight
    coverage = round(100 * judged_weight / applicable, 1) if applicable else 0.0
    raw = round(100 * sum(d["num"] for d in per_dim.values()) / scored_weight, 1) if scored_weight else 0.0

    lights: dict[str, dict] = {}
    red: list[str] = []
    unknown_hard_list: list[str] = []
    for hid, rule in hard.items():
        entry = hard_entries.get(hid)
        light = "unknown" if entry is None else entry.get("light", "unknown")
        note = ""
        if light not in LIGHTS:
            invalid.append(hid)
            light = "unknown"
        if light in ("green", "red", "na") and not has_text((entry or {}).get("evidence")):
            note = f"{light} 无 evidence，按 unknown 计"
            light = "unknown"
        lights[hid] = {"name": rule["name"], "light": light, "note": note,
                       "evidence": "" if entry is None else entry.get("evidence", ""),
                       "basis": rule.get("basis", "")}
        if light == "red":
            red.append(hid)
        elif light == "unknown":
            unknown_hard_list.append(hid)

    contradictions: list[str] = []
    for hid, rule in hard.items():
        mirrors = rule.get("mirror", [])
        if not mirrors:
            continue
        light = lights[hid]["light"]
        ms = {m: states[m] for m in mirrors if states[m] != "missing"}
        if not ms:
            continue
        mode = rule.get("mirror_mode", "equivalent")
        if light == "red" and not any(s == "fail" for s in ms.values()):
            contradictions.append(f"{hid}=red，但镜像规则 {ms} 无 0")
        if mode == "equivalent":
            if light == "green" and not all(s == "pass" for s in ms.values()):
                contradictions.append(f"{hid}=green，但镜像规则 {ms} 不全为 1")
            if light == "unknown" and any(s in ("pass", "fail") for s in ms.values()):
                contradictions.append(f"{hid}=unknown，但镜像规则已判定 {ms}")
            if light == "na" and not all(s == "na" for s in ms.values()):
                contradictions.append(f"{hid}=na，但镜像规则 {ms} 不全为 na")

    checklist = check_checklist(result.get("checklist"))
    defects = check_defects(result.get("defects"))

    if checklist["declared"] and states.get("L2.1") == "pass" and not checklist["complete"]:
        contradictions.append(f"L2.1=1，但清单未完成：{checklist['open'][:5]}")
    if defects["declared"]:
        for row in defects["rows"]:
            if row["effective"] in ("open", "partial") and row["severity"] in ("P0", "P1"):
                for rid in row["rules"]:
                    if rid not in rules:
                        raise InvalidResult(f"缺陷 {row['id']} 关联未知规则 {rid}")
                    if states[rid] == "pass":
                        contradictions.append(f"缺陷 {row['id']}（{row['severity']} {row['status']}）关联 {rid}，但 {rid}=1")

    if contradictions:
        raise InvalidResult("判定矛盾：\n  " + "\n  ".join(contradictions))

    triggered: list[dict] = []

    def trigger(when: str, ids: list[str]) -> None:
        if ids:
            gate = gate_def[when]
            triggered.append({"gate": gate["id"], "cap": gate["cap"], "rules": ids, "reason": gate.get("reason", "")})

    trigger("hard_rule_red", red)
    if defects["declared"]:
        trigger("defect_p0_open", defects["open"]["P0"])
        trigger("defect_p1_open", defects["open"]["P1"])
    else:
        trigger("defects_missing", ["defects=null"])
    if checklist["declared"]:
        if not checklist["complete"]:
            trigger("checklist_incomplete", checklist["open"] or ["(空清单)"])
    else:
        trigger("checklist_missing", ["checklist=null"])
    trigger("hard_rule_unknown", unknown_hard_list)
    trigger("rule_not_measured", [rid for rid, _ in not_measured] + invalid)

    total = raw
    for gate in triggered:
        total = min(total, gate["cap"])
    total = round(total, 1)

    judged = sum(basis_weight.values())
    basis_share = {k: round(100 * v / judged, 1) for k, v in sorted(basis_weight.items())} if judged else {}
    if basis_share and basis_share.get("C", 0) + basis_share.get("D", 0) > 50:
        warnings.append("已判定权重中 C/D 级依据超过 50%：结论是假设，不是测量")

    return {
        "scope": result.get("scope", "(unnamed)"),
        "profile": profile,
        "round": result.get("round", ""),
        "date": result.get("date", ""),
        "facts_ref": result.get("facts_ref", ""),
        "snapshot": result.get("snapshot", {}),
        "raw": raw,
        "total": total,
        "grade": grade_for(total, rubric),
        "accepted": total >= rubric["publish_threshold"] and not triggered,
        "gates": triggered,
        "dimensions": per_dim,
        "lights": lights,
        "states": states,
        "zeros": zeros,
        "missing": missing,
        "not_measured": not_measured,
        "na": na,
        "invalid": invalid,
        "coverage": coverage,
        "basis_share": basis_share,
        "checklist": checklist,
        "defects": defects,
        "warnings": warnings,
        "partial": partial,
    }


def print_report(report: dict, rubric: dict) -> None:
    head = f"# 代码落地质检 — {report['scope']}"
    tail = "，".join(x for x in (report["round"], report["date"], f"profile={report['profile']}") if x)
    print(head + (f"（{tail}）" if tail else ""))
    if report.get("facts_ref"):
        print(f"facts_ref: {report['facts_ref']}")
    for name, digest in (report.get("snapshot") or {}).items():
        print(f"snapshot: {name} {digest}")
    print()
    verdict = "可验收" if report["accepted"] else "不可验收"
    print(f"总分: {fmt(report['total'])} / 100    等级: {report['grade']['grade']} "
          f"{report['grade']['label']}    结论: {verdict}    证据覆盖: {report['coverage']}%")
    if report["partial"]:
        print(f"（--partial：未填写规则不计入分母；原始加权分 {fmt(report['raw'])}）")
    if report["basis_share"]:
        print("依据等级（按已判定权重）：" + " / ".join(f"{k} {v}%" for k, v in report["basis_share"].items()))
    print()

    print("| 闸门 | 封顶 | 触发项 |")
    print("|-|-|-|")
    if report["gates"]:
        for gate in report["gates"]:
            ids = ", ".join(gate["rules"][:8]) + (" …" if len(gate["rules"]) > 8 else "")
            print(f"| {gate['gate']} | {gate['cap']} | {ids} |")
    else:
        print("| — | — | 无 |")
    print()

    print("| 硬规则 | 依据 | 灯 |")
    print("|-|-|-|")
    for hid, item in report["lights"].items():
        note = f"（{item['note']}）" if item["note"] else ""
        print(f"| {hid} {item['name']} | {item['basis']} | {item['light']}{note} |")
    print()

    cl = report["checklist"]
    if cl["declared"]:
        c = cl["counts"]
        print(f"方案清单：{cl['source'] or '—'} {cl['plan_version']}  共 {cl['total']} 条，"
              f"done {c['done']} / partial {c['partial']} / not_done {c['not_done']} / "
              f"未判定 {c['unjudged']} / na {c['na']} / waived {c['waived']}；完成率 {cl['completion']}%")
    else:
        print("方案清单：未提交（checklist=null）")
    df = report["defects"]
    if df["declared"]:
        open_text = "；".join(f"{s} {len(ids)}（{', '.join(ids)}）" for s, ids in df["open"].items() if ids) or "无"
        print(f"缺陷：共 {len(df['rows'])} 条；未关闭 {open_text}")
    else:
        print("缺陷：未声明（defects=null）")
    print()

    print("| 维度 | 权重 | 得分率 | 已判定 |")
    print("|-|-|-|-|")
    for dim in report["dimensions"].values():
        rate = 100 * dim["num"] / dim["den"] if dim["den"] else 0.0
        print(f"| {dim['name']} | {dim['weight']} | {rate:.1f}% | {dim['judged']}/{dim['total']} |")
    print()

    if report["zeros"]:
        print("得 0 的规则：")
        for rid, name in report["zeros"]:
            print(f"- {rid} {name}")
        print()
    if report["missing"]:
        print(f"未填写（按 0 计）：{', '.join(report['missing'])}")
    if report["not_measured"]:
        print("未测量（按 0 计）：" + ", ".join(f"{rid}" + (f"[{n}]" if n else "") for rid, n in report["not_measured"]))
    if report["na"]:
        print("不适用（出分母）：")
        for rid, reason in report["na"]:
            print(f"- {rid}：{reason}")
    if report["invalid"]:
        print(f"非法判定（按 0/unknown 计）：{', '.join(report['invalid'])}")
    problems = cl.get("problems", []) + df.get("problems", []) + report["warnings"]
    if problems:
        print()
        print("需复核：")
        for p in problems:
            print(f"- {p}")
    print()
    print(f"验收条件：总分 ≥{rubric['publish_threshold']}，且无闸门触发")


def fmt(value: float | None) -> str:
    return "—" if value is None else f"{value:.1f}"


def all_pass_result(rubric: dict) -> dict:
    rules = index_rules(rubric)
    hard = index_hard(rubric)
    return {
        "scope": "self-test",
        "profile": "capability",
        "rubric_version": rubric["version"],
        "rules": {rid: {"score": 1, "evidence": "synthetic `probe`"} for rid in rules},
        "hard_rules": {hid: {"light": "green", "evidence": "synthetic"} for hid in hard},
        "checklist": {"source": "plan.md", "items": [{"id": "1#aaaaaa", "text": "x", "verdict": "done", "evidence": "a.py:1"}]},
        "defects": [],
    }


def self_test(rubric: dict) -> int:
    """Check gate invariants, then mutate an all-pass result and assert the caps bite."""
    rules = index_rules(rubric)
    gate_def = caps(rubric)
    a_min = min(b["min"] for b in rubric["grades"] if b["grade"] == "A")
    d_min = min(b["min"] for b in rubric["grades"] if b["grade"] == "D")
    publish = rubric["publish_threshold"]
    cases: list[tuple[str, bool, str]] = []

    def cap(when: str) -> int:
        return gate_def[when]["cap"]

    cases.append(("red/P0 cap below grade D", cap("hard_rule_red") < d_min and cap("defect_p0_open") < d_min,
                  f"{cap('hard_rule_red')}/{cap('defect_p0_open')} < {d_min}"))
    cases.append(("P1/checklist cap below publish", cap("defect_p1_open") < publish and cap("checklist_incomplete") < publish,
                  f"{cap('defect_p1_open')}/{cap('checklist_incomplete')} < {publish}"))
    unknown_caps = [cap(w) for w in ("hard_rule_unknown", "rule_not_measured", "checklist_missing", "defects_missing")]
    cases.append(("unknown caps below grade A", all(c < a_min for c in unknown_caps), f"{unknown_caps} < {a_min}"))

    def run(mutate, partial=False):
        r = json.loads(json.dumps(all_pass_result(rubric)))
        mutate(r)
        try:
            return evaluate(rubric, r, partial=partial)
        except InvalidResult as exc:
            return {"invalid": str(exc)}

    rep = run(lambda r: None)
    cases.append(("all green", rep.get("total") == 100.0 and rep["accepted"], f"{rep.get('total')}"))

    rep = run(lambda r: (r["hard_rules"]["D1"].update(light="red"), r["rules"]["A1.1"].update(score=0)))
    cases.append(("red caps", rep.get("total") == cap("hard_rule_red"), f"{rep.get('total')}"))

    rep = run(lambda r: r["hard_rules"]["R13"].update(light="unknown"))
    cases.append(("unknown caps", rep.get("total") == cap("hard_rule_unknown"), f"{rep.get('total')}"))

    def add_defect(sev, status="open", rules_=None):
        def m(r):
            r["defects"].append({"id": "X1", "severity": sev, "status": status, "title": "t",
                                 "location": "a.py:1", "rules": rules_ or [],
                                 "repro": {"input": "i", "expected": "e", "actual": "a"}})
            for rid in rules_ or []:
                r["rules"][rid]["score"] = 0
        return m
    rep = run(add_defect("P0", rules_=["L2.2"]))
    cases.append(("open P0 caps", rep.get("total") == cap("defect_p0_open"), f"{rep.get('total')}"))
    rep = run(add_defect("P0", status="waived"))
    cases.append(("P0 cannot be waived", rep.get("total") == cap("defect_p0_open"), f"{rep.get('total')}"))
    rep = run(add_defect("P1", status="partial"))
    cases.append(("partial P1 caps", rep.get("total") == cap("defect_p1_open"), f"{rep.get('total')}"))
    rep = run(lambda r: r["defects"].append({"id": "X", "severity": "P1", "status": "open", "rules": ["L2.2"]}))
    cases.append(("open defect vs passing rule is invalid", "invalid" in rep, rep.get("invalid", "")[:40]))

    rep = run(lambda r: r.update(defects=None))
    cases.append(("defects=null caps", rep.get("total") == cap("defects_missing"), f"{rep.get('total')}"))
    rep = run(lambda r: r.update(checklist=None))
    cases.append(("checklist=null caps", rep.get("total") == cap("checklist_missing"), f"{rep.get('total')}"))

    def open_item(r):
        r["checklist"]["items"].append({"id": "2#bbbbbb", "text": "y", "verdict": "not_done"})
        r["rules"]["L2.1"]["score"] = 0
    rep = run(open_item)
    cases.append(("checklist incomplete caps", rep.get("total") == cap("checklist_incomplete"), f"{rep.get('total')}"))
    rep = run(lambda r: r["checklist"]["items"].append({"id": "2#bbbbbb", "text": "y", "verdict": "not_done"}))
    cases.append(("L2.1=1 with open checklist is invalid", "invalid" in rep, rep.get("invalid", "")[:40]))
    rep = run(lambda r: r["checklist"]["items"][0].update(evidence=""))
    cases.append(("done without evidence is open", "invalid" in rep or rep.get("total") == cap("checklist_incomplete"),
                  str(rep.get("total", "invalid"))))

    rep = run(lambda r: r["rules"]["A3.1"].update(evidence=""))
    cases.append(("score without evidence is unmeasured", rep.get("total") == cap("rule_not_measured"), f"{rep.get('total')}"))
    rep = run(lambda r: r["hard_rules"]["R13"].update(evidence=""))
    cases.append(("light without evidence is unknown", rep.get("total") == cap("hard_rule_unknown"), f"{rep.get('total')}"))
    rep = run(lambda r: r["rules"]["L3.3"].update(score=None, na_reason="无外发"))
    cases.append(("na in profile leaves denominator", rep.get("total") == 100.0 and rep["na"], f"{rep.get('total')}"))
    rep = run(lambda r: r["rules"]["L1.1"].update(score=None, na_reason="无入口"))
    cases.append(("na outside profile is unmeasured", rep.get("total") == cap("rule_not_measured"), f"{rep.get('total')}"))
    rep = run(lambda r: r["hard_rules"]["D1"].update(light="red"))
    cases.append(("hard red vs mirror 1 is invalid", "invalid" in rep, rep.get("invalid", "")[:40]))

    full = all_pass_result(rubric)
    del full["rules"]["L2.2"]
    rep = evaluate(rubric, full, partial=False)
    expected = round(100 * (100 - rules["L2.2"]["weight"]) / 100, 1)
    cases.append(("missing counts as 0", rep["total"] == expected, f"{rep['total']} expected {expected}"))

    rep = run(lambda r: r["hard_rules"]["R13"].update(light="green "))
    cases.append(("invalid light is unknown", rep.get("total") == cap("hard_rule_unknown"), f"{rep.get('total')}"))
    rep = run(lambda r: r.update(rubric_version="0.0"))
    cases.append(("version mismatch is invalid", "invalid" in rep, rep.get("invalid", "")[:40]))

    width = max(len(name) for name, _, _ in cases)
    failed = 0
    for name, ok, detail in cases:
        print(f"{'PASS' if ok else 'FAIL'}  {name:<{width}}  {detail}")
        failed += 0 if ok else 1
    print(f"[self-test] {len(cases) - failed}/{len(cases)} passed")
    return 0 if failed == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rubric", type=Path, default=DEFAULT_RUBRIC)
    parser.add_argument("--result", type=Path)
    parser.add_argument("--template", action="store_true")
    parser.add_argument("--partial", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--fail-under", type=float, default=None)
    parser.add_argument("--allow-version-mismatch", action="store_true",
                        help="read a result written for another rubric version (report only, never for acceptance)")
    args = parser.parse_args()

    rubric = load_json(args.rubric)
    validate(rubric, index_rules(rubric), index_hard(rubric))

    if args.self_test:
        return self_test(rubric)
    if args.template:
        print(json.dumps(template(rubric), ensure_ascii=False, indent=2))
        return 0
    if not args.result:
        parser.error("--result is required unless --template/--self-test is used")

    result = load_json(args.result)
    try:
        report = evaluate(rubric, result, args.partial, args.allow_version_mismatch)
    except InvalidResult as exc:
        print(f"结果无效：{exc}", file=sys.stderr)
        return 2
    report["rubric_version"] = rubric["version"]
    report["rubric_sha256"] = hashlib.sha256(args.rubric.read_bytes()).hexdigest()

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"rubric: {rubric['version']} sha256:{report['rubric_sha256'][:12]}")
        print()
        print_report(report, rubric)

    if args.fail_under is not None and (report["total"] < args.fail_under or report["gates"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
