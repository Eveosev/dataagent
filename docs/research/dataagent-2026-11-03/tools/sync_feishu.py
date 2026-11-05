#!/usr/bin/env python3
"""把本地 v0.2（00–04）同步到飞书。

用法（在仓库根目录）：
    python3 -I docs/research/dataagent-2026-11-03/tools/sync_feishu.py prepare
    # 生成 feishu/ 下的推送片段与 plan.json，不写飞书

写入由 plan.json 中的命令逐条执行（lark-cli docs +update，带 --revision-id）。

- 分层文档：替换正文（标题块之后到“机器可读能力目录”之前），保留原 JSON 附件节；标题另行更新。
- 总规划：只做定点替换与插入，不整篇覆盖。
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
OUT = BASE / "feishu"
ROOT = BASE.parent.parent.parent  # 仓库根

URL = {
    "00-pluggable-dataagent.md": "https://modelbest.feishu.cn/docx/TlN4dygs9oJR3Qx1FaictiPEn3c",
    "01-data-layer.md": "https://modelbest.feishu.cn/docx/NXe7dMEEQoJ5wqxcPsRczoebn4d",
    "02-application-layer.md": "https://modelbest.feishu.cn/docx/ReDXdJzLWoihZDxqaO0clUxInKf",
    "03-governance-layer.md": "https://modelbest.feishu.cn/docx/QwN4dFvdroH7X3xI3Eycnkbon3b",
    "04-operations-fde-layer.md": "https://modelbest.feishu.cn/docx/NqS0dcV0CoaatHxJTTFc7amnnke",
    "05-contracts.md": "https://modelbest.feishu.cn/docx/VavsdOWFeoLBFrxOt9JcjAsInDe",
    "06-data-layer-build-plan.md": "https://modelbest.feishu.cn/docx/NvOsd04lAoZk60xY2Kpc4SrYnwf",
}
CATALOG_URL = "https://modelbest.feishu.cn/base/AjY0bNRutawmZ0s62MZcUSmQn4f"
LAYERS = ["01-data-layer.md", "02-application-layer.md", "03-governance-layer.md", "04-operations-fde-layer.md"]
LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
KEEP_TAG = re.compile(r"<br/>|</?callout[^>]*>")


def map_links(text: str, self_name: str) -> str:
    def repl(m: re.Match) -> str:
        label, target = m.group(1), m.group(2)
        if target.startswith("http"):
            return m.group(0)
        name = target.split("#")[0]
        if name in URL:
            return f"[{label}]({URL[name]})"
        if name.startswith("catalog/"):
            return f"[{label}]({CATALOG_URL})"
        if name == self_name:
            return label
        return f"{label}（AgentOS 仓库 `{name.lstrip('./')}`）"
    return LINK.sub(repl, text)


def emoji_quotes_to_callout(text: str) -> str:
    """把首行以 emoji 开头的引用块还原为飞书 callout。"""
    out, lines, i = [], text.split("\n"), 0
    while i < len(lines):
        m = re.match(r"^> ([^\x00-\x7F\*\[`「])\s(.*)$", lines[i])
        if m and not m.group(1).isalnum():
            emoji, body = m.group(1), [m.group(2)]
            i += 1
            while i < len(lines) and lines[i].startswith(">"):
                body.append(lines[i][1:].lstrip())
                i += 1
            out.append(f'<callout emoji="{emoji}">')
            out.extend(body)
            out.append("</callout>")
            continue
        out.append(lines[i])
        i += 1
    return "\n".join(out)


def escape_segment(seg: str) -> str:
    keep: list[str] = []

    def hold(m: re.Match) -> str:
        keep.append(m.group(0))
        return f"\x00{len(keep) - 1}\x00"

    seg = LINK.sub(hold, seg)
    seg = KEEP_TAG.sub(hold, seg)
    seg = re.sub(r"(?<!\\)([\[\]_<$~])", r"\\\1", seg)
    seg = re.sub(r"(?<![*\\])\*(?!\*)", r"\\*", seg)
    return re.sub(r"\x00(\d+)\x00", lambda m: keep[int(m.group(1))], seg)


def escape(text: str) -> str:
    out, fenced = [], False
    for line in text.split("\n"):
        if line.startswith("```"):
            fenced = not fenced
            out.append(line)
            continue
        if fenced:
            out.append(line)
            continue
        parts = re.split(r"(`[^`]*`)", line)
        out.append("".join(p if (p.startswith("`") and p.endswith("`") and len(p) > 1) else escape_segment(p) for p in parts))
    return "\n".join(out)


def to_feishu(text: str, self_name: str) -> str:
    return escape(emoji_quotes_to_callout(map_links(text, self_name)))


def split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---\n"):
        return "", text
    end = text.index("\n---\n", 4)
    return text[4:end], text[end + 5:].lstrip("\n")


def fetch_xml(url: str) -> tuple[list[ET.Element], int]:
    r = subprocess.run(["lark-cli", "docs", "+fetch", "--doc", url, "--as", "user", "--detail", "with-ids"],
                       capture_output=True, text=True, check=True)
    doc = json.loads(r.stdout)["data"]["document"]
    root = ET.fromstring("<root>" + doc["content"] + "</root>")
    return list(root), int(doc["revision_id"])


def text_of(e: ET.Element) -> str:
    return "".join(e.itertext()).strip()


def prepare() -> None:
    OUT.mkdir(exist_ok=True)
    plan = []
    # 分层文档
    for name in LAYERS:
        fm, src = split_frontmatter((BASE / name).read_text(encoding="utf-8"))
        title = src.split("\n", 1)[0].removeprefix("# ").strip()
        body = src.split("\n", 1)[1]
        body = body.split("\n# 机器可读能力目录")[0].strip("\n") + "\n"
        frag = OUT / name
        frag.write_text(f"```yaml\n{fm}\n```\n\n" + to_feishu(body, name), encoding="utf-8")
        kids, rev = fetch_xml(URL[name])
        body_kids = [k for k in kids if k.tag != "title"]
        cat = [i for i, k in enumerate(body_kids) if k.tag == "h1" and text_of(k) == "机器可读能力目录"]
        plan.append({"doc": name, "url": URL[name], "rev": rev, "op": "block_replace",
                     "start": body_kids[0].get("id"), "end": "-1",
                     "content": str(frag.relative_to(ROOT)), "title": title,
                     "drops_catalog_section": bool(cat)})
    if len(sys.argv) > 2 and sys.argv[2] == "layers":
        (OUT / "plan.json").write_text(json.dumps({"steps": plan}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"steps": plan}, ensure_ascii=False, indent=2))
        return
    # 总规划
    main = (BASE / "00-pluggable-dataagent.md").read_text(encoding="utf-8")
    kids, rev = fetch_xml(URL["00-pluggable-dataagent.md"])

    def kid(tag: str, startswith: str) -> ET.Element:
        hits = [k for k in kids if k.tag == tag and text_of(k).startswith(startswith)]
        assert len(hits) == 1, (tag, startswith, len(hits))
        return hits[0]

    def section(start: str, stop: str | None) -> str:
        i = main.index(start)
        j = main.index(stop, i) if stop else len(main)
        return main[i:j].strip("\n") + "\n"

    frags = {
        "main-2.3-2.4.md": section("## 2.3 平台对接待决", "\n---\n\n# 三、模块定义"),
        "main-3.md": section("# 三、模块定义", "\n---\n\n# 四、依赖关系"),
        "main-4.md": section("# 四、依赖关系", None),
    }
    for fn, txt in frags.items():
        (OUT / fn).write_text(to_feishu(txt, "00-pluggable-dataagent.md"), encoding="utf-8")
    # 索引表：在线 XML 上只改计数与版本标签
    table = kid("table", "设计文档覆盖模块")
    xml = re.sub(r' id="[^"]+"', "", ET.tostring(table, encoding="unicode"))
    for a, b in [(">160<", ">165<"), (">116<", ">126<"), (">67<", ">73<"), (">91<", ">94<"),
                 ("数据层 v0.1<", "数据层 v0.2<"), ("执行应用层 v0.1<", "执行应用层 v0.2<"),
                 ("评测与治理层 v0.1<", "评测与治理层 v0.2<"), ("持续运行与 FDE 交付 v0.1<", "持续运行与 FDE 交付 v0.2<")]:
        assert xml.count(a) == 1, a
        xml = xml.replace(a, b)
    (OUT / "main-index-table.xml").write_text(xml, encoding="utf-8")
    top = [k for k in kids if k.tag != "title"]
    sec3 = kid("h1", "三、模块定义")
    sec4 = kid("h1", "四、依赖关系")
    i3, i4 = top.index(sec3), top.index(sec4)
    rel = lambda fn: str((OUT / fn).relative_to(ROOT))
    main_url = URL["00-pluggable-dataagent.md"]
    plan += [
        {"doc": "00", "url": main_url, "op": "block_replace", "block": table.get("id"), "format": "xml",
         "content": rel("main-index-table.xml")},
        {"doc": "00", "url": main_url, "op": "block_insert_after", "block": kid("p", "硬/软描述主要职责").get("id"),
         "content": rel("main-2.3-2.4.md")},
        {"doc": "00", "url": main_url, "op": "block_replace", "start": sec3.get("id"), "end": top[i4 - 1].get("id"),
         "content": rel("main-3.md")},
        {"doc": "00", "url": main_url, "op": "block_replace", "start": sec4.get("id"), "end": "-1",
         "content": rel("main-4.md")},
    ]
    plan_meta = {"main_rev": rev, "steps": plan}
    (OUT / "plan.json").write_text(json.dumps(plan_meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(plan_meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    {"prepare": prepare}[sys.argv[1]]()
