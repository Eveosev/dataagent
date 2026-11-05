#!/usr/bin/env python3
"""Extract an acceptance checklist from a plan document.

Usage:
  python3 plan_checklist.py plan.md
  python3 plan_checklist.py plan.md --out checklist.json
  python3 plan_checklist.py plan.md --json
  python3 plan_checklist.py plan.md --all                    # every bullet/table row
  python3 plan_checklist.py plan.md --previous r5.checklist.json   # added / removed items
  python3 plan_checklist.py plan.md --into review/pkg.score.json   # merge into result.checklist

Item ids are "<section number>#<hash of normalised text>" (e.g. "5.2#3f9a1c"), so an
item keeps its id when sections are inserted or lines move; editing the text of an
item gives it a new id, which --previous reports as removed + added.

--into keeps the verdict/evidence of items whose id is unchanged, adds new items with
verdict null, and drops items no longer in the plan (listed on stderr).

Exit codes: 0 ok, 2 unreadable input, 3 no items found.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

MUST = re.compile(
    r"(MUST|SHALL|必须|不得|禁止|要求|验收|通过标准|质量门|门槛|不允许|只允许|至少|唯一|"
    r"\bonly\b|\bmust\b|\bmust not\b)",
    re.IGNORECASE,
)
ACCEPTANCE_SECTION = re.compile(r"(验收|测试|质量|门禁|门槛|约束|交付|acceptance|quality|test)", re.IGNORECASE)
IMPL_SECTION = re.compile(r"(S0|实现|实施|交付|验证|接口|调用|规则|quality)", re.IGNORECASE)
EXCLUDED_SECTION = re.compile(r"(背景|非目标|风险|变更|版本记录|目录|changelog|范围|前置条件|按需|S1 能力|第三方依赖)", re.IGNORECASE)
REQ_COLUMN = re.compile(r"(规则|实现|要求|验收|标准|约束|判定|内容|做法)", re.IGNORECASE)
HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
BULLET = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.*)$")
TABLE_ROW = re.compile(r"^\s*\|(.+)\|\s*$")
SEPARATOR = re.compile(r"^:?-+:?$")
SECTION_NO = re.compile(r"^§?\s*(\d+(?:\.\d+)*)(?:[.、)]|\s|$)")
MARKUP = re.compile(r"[`*_]|<!--.*?-->")


def section_key(heading: str) -> str:
    match = SECTION_NO.match(heading.strip())
    if match:
        return match.group(1)
    compact = re.sub(r"\s+", "", MARKUP.sub("", heading))
    return compact[:16] or "root"


def text_hash(text: str) -> str:
    norm = re.sub(r"\s+", " ", MARKUP.sub("", text)).strip().rstrip("；;。.，,").lower()
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()[:6]


def strip_frontmatter(text: str) -> tuple[dict[str, str], str, int]:
    meta: dict[str, str] = {}
    if not text.startswith("---"):
        return meta, text, 0
    lines = text.splitlines()
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return meta, text, 0
    for line in lines[1:end]:
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip().strip('"')
    return meta, "\n".join(lines[end + 1:]), end + 1


def cells(row: str) -> list[str]:
    return [c.strip() for c in row.strip().strip("|").split("|")]


def is_separator(row: str) -> bool:
    if not row.strip().startswith("|"):
        return False
    parts = cells(row)
    if not parts:
        return False
    return all(p and SEPARATOR.match(p.replace(" ", "")) for p in parts)


def extract(path: Path, include_all: bool) -> tuple[dict, list[dict]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    meta, body, offset = strip_frontmatter(text)
    lines = body.splitlines()

    section = "(root)"
    key = "root"
    in_fence = False
    items: list[dict] = []
    used: dict[str, int] = {}
    in_acceptance = False
    in_impl = False
    excluded = False
    header_cells: list[str] = []

    for index, raw in enumerate(lines):
        line_no = offset + index + 1
        stripped = raw.strip()

        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not stripped:
            continue

        heading = HEADING.match(raw)
        if heading:
            section = heading.group(2).strip()
            key = section_key(section)
            in_acceptance = bool(ACCEPTANCE_SECTION.search(section))
            in_impl = bool(IMPL_SECTION.search(section))
            excluded = bool(EXCLUDED_SECTION.search(section))
            header_cells = []
            continue

        candidate = None
        kind = ""
        bullet = BULLET.match(raw)
        table = TABLE_ROW.match(raw)

        if table and is_separator(raw):
            if index > 0:
                header_cells = cells(lines[index - 1])
            continue
        if table and index + 1 < len(lines) and is_separator(lines[index + 1]):
            header_cells = cells(raw)
            continue

        if bullet:
            candidate, kind = bullet.group(1).strip(), "bullet"
        elif table and not is_separator(raw):
            parts = cells(raw)
            if len(parts) >= 2 and parts[0] and parts[1] and not parts[1].startswith("-"):
                candidate, kind = f"{parts[0]}：{parts[1]}", "table"

        if not candidate or len(candidate) < 4:
            continue

        wanted_table = bool(header_cells and any(REQ_COLUMN.search(c) for c in header_cells[1:]))
        if not (include_all
                or MUST.search(candidate)
                or (kind == "bullet" and (in_acceptance or in_impl))
                or (kind == "table" and wanted_table and not excluded)):
            continue

        iid = f"{key}#{text_hash(candidate)}"
        used[iid] = used.get(iid, 0) + 1
        if used[iid] > 1:
            iid = f"{iid}-{used[iid]}"
        items.append({
            "id": iid,
            "section": section,
            "kind": kind,
            "must": bool(MUST.search(candidate)),
            "text": candidate,
            "line": line_no,
        })

    result = {
        "source": str(path),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "plan_status": meta.get("status", ""),
        "plan_version": meta.get("version", ""),
        "count": len(items),
        "items": items,
    }
    return result, items


def render_markdown(result: dict) -> str:
    out = [f"# 验收清单 — {Path(result['source']).name}", ""]
    if result["plan_version"] or result["plan_status"]:
        out.append(f"方案版本：{result['plan_version'] or '—'}｜状态：{result['plan_status'] or '—'}")
        out.append("")
    current = None
    for item in result["items"]:
        if item["section"] != current:
            current = item["section"]
            if out[-1] != "":
                out.append("")
            out.append(f"## {current}")
            out.append("")
        out.append(f"- [ ] `{item['id']}` {item['text']}  <!-- L{item['line']} -->")
    out.append("")
    out.append(f"共 {result['count']} 条；逐条判 done/partial/not_done/na/waived 后用 --into 并入 result.checklist。")
    return "\n".join(out)


def diff_previous(result: dict, previous: dict) -> str:
    now = {i["id"]: i for i in result["items"]}
    before = {i["id"]: i for i in previous.get("items", [])}
    added = [now[k] for k in now if k not in before]
    removed = [before[k] for k in before if k not in now]
    out = [f"# 清单变化 — {previous.get('plan_version') or '?'} → {result['plan_version'] or '?'}", ""]
    out.append(f"不变 {len(now) - len(added)}，新增 {len(added)}，移除 {len(removed)}")
    out.append("")
    for title, rows in (("新增", added), ("移除", removed)):
        if rows:
            out.append(f"## {title}")
            out.append("")
            out.extend(f"- `{r['id']}` {r['text']}" for r in rows)
            out.append("")
    return "\n".join(out)


def merge_into(path: Path, result: dict) -> tuple[int, int, list[str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    old = data.get("checklist") or {}
    keep = {i["id"]: i for i in old.get("items", []) if isinstance(i, dict) and "id" in i}
    items = []
    reused = 0
    for item in result["items"]:
        prev = keep.get(item["id"], {})
        if prev:
            reused += 1
        items.append({
            "id": item["id"],
            "section": item["section"],
            "text": item["text"],
            "line": item["line"],
            "verdict": prev.get("verdict"),
            "evidence": prev.get("evidence", ""),
            **({"waiver": prev["waiver"]} if "waiver" in prev else {}),
        })
    dropped = [k for k in keep if k not in {i["id"] for i in items}]
    data["checklist"] = {
        "source": result["source"],
        "plan_version": result["plan_version"],
        "items": items,
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return len(items), reused, dropped


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--out", type=Path, help="write JSON checklist here")
    parser.add_argument("--json", action="store_true", help="print JSON instead of Markdown")
    parser.add_argument("--all", action="store_true", help="include every bullet/table row")
    parser.add_argument("--previous", type=Path, help="earlier checklist JSON to diff against")
    parser.add_argument("--into", type=Path, help="result JSON whose checklist is replaced (verdicts kept by id)")
    args = parser.parse_args()

    if not args.plan.is_file():
        print(f"plan not found: {args.plan}", file=sys.stderr)
        return 2

    result, items = extract(args.plan, args.all)
    if not items:
        print("no checklist items found; try --all or check the document structure", file=sys.stderr)
        return 3

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {args.out} ({len(items)} items)", file=sys.stderr)

    if args.into:
        if not args.into.is_file():
            print(f"result not found: {args.into}（先用 score_landing.py --template 生成）", file=sys.stderr)
            return 2
        total, reused, dropped = merge_into(args.into, result)
        print(f"merged {total} items into {args.into}（保留判定 {reused}，移除 {len(dropped)}）", file=sys.stderr)
        for iid in dropped:
            print(f"  removed: {iid}", file=sys.stderr)

    if args.previous:
        print(diff_previous(result, json.loads(args.previous.read_text(encoding="utf-8"))))
    elif args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif not args.into:
        print(render_markdown(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
