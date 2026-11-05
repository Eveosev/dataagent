#!/usr/bin/env python3
"""把 05-contracts.md 转成可直接导入飞书的自包含 Markdown。

用法（在仓库根目录）：
    python3 -I docs/research/dataagent-2026-11-03/tools/to_feishu.py

输出：docs/research/dataagent-2026-11-03/feishu/05-contracts.md
- 本地链接改为飞书链接；引用本地总文档 §2.3 / §4.1 的内容，改为本文附录 A / B（从 build.py 中取同一份文本）。
- 按飞书 Markdown 导入规则转义代码以外的 [ ] _ < * $ ~。
- 首段引用块转为 <callout>；标题由 lark-cli --title 传入，正文去掉 H1。
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
SRC = BASE / "05-contracts.md"
OUT = BASE / "feishu" / "05-contracts.md"

MAIN_URL = "https://modelbest.feishu.cn/docx/TlN4dygs9oJR3Qx1FaictiPEn3c"
DATA_URL = "https://modelbest.feishu.cn/docx/NXe7dMEEQoJ5wqxcPsRczoebn4d"
REVIEW_PATH = "docs/research/dataagent-2026-11-02/online-r1024-review.md"
SOURCE_PATH = "docs/research/dataagent-2026-11-03/05-contracts.md"


def load_build_sections() -> tuple[str, str]:
    spec = importlib.util.spec_from_file_location("build", HERE / "build.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # 只定义常量与函数，不执行 main()
    p_table = mod.SEC_2_3_2_4.split("## 2.4")[0]
    p_table = p_table[p_table.index("实现前须定案"):].strip()
    slices = mod.SEC_4_X.split("## 4.2")[0]
    slices = slices[slices.index("切片按业务闭环定义"):].strip()
    return p_table, slices


LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")


def escape_text(seg: str) -> str:
    links: list[str] = []

    def keep(m: re.Match) -> str:
        links.append(m.group(0))
        return f"\x00{len(links) - 1}\x00"

    seg = LINK.sub(keep, seg)
    for ch in "[]_<$~":
        seg = seg.replace(ch, "\\" + ch)
    seg = re.sub(r"(?<![*\\])\*(?!\*)", r"\\*", seg)
    return re.sub(r"\x00(\d+)\x00", lambda m: links[int(m.group(1))], seg)


def escape_line(line: str) -> str:
    parts = re.split(r"(`[^`]*`)", line)
    return "".join(p if p.startswith("`") and p.endswith("`") and len(p) > 1 else escape_text(p) for p in parts)


def localize_refs(text: str) -> str:
    text = text.replace("总文档 §2.3 ", "§2.3 ")
    text = re.sub(r"§2\.3 P(\d)", r"附录 A P\1", text)
    text = text.replace("§2.3 的 P", "附录 A 的 P")
    text = text.replace("评审 D2 / P3", "评审 D2，附录 A P3")
    text = text.replace("](01-data-layer.md)", f"]({DATA_URL})")
    return text


def split_frontmatter(text: str) -> tuple[str, str]:
    """返回 (frontmatter 内容, 其余正文)；无 frontmatter 时前者为空。"""
    if not text.startswith("---\n"):
        return "", text
    end = text.index("\n---\n", 4)
    return text[4:end], text[end + 5:].lstrip("\n")


def main() -> None:
    src = SRC.read_text(encoding="utf-8")
    fm, src = split_frontmatter(src)
    lines = src.split("\n")
    assert lines[0].startswith("# "), "首行应为标题"
    body = "\n".join(lines[1:]).lstrip("\n")

    # 首段引用块 → callout
    m = re.match(r"((?:>.*\n)+)", body)
    assert m, "缺少首段引用块"
    quote = m.group(1)
    # 源文件中每个引用行都是独立段落（“状态”“关联”等同块相邻行也分开）
    paras = [ql[1:].strip() for ql in quote.rstrip("\n").split("\n") if ql[1:].strip()]
    paras = [p for p in paras if not p.startswith("关联：")]
    paras[0] = paras[0].removeprefix("📌 ").strip()
    rest = body[m.end():]

    p_table, slices = load_build_sections()
    slices = slices.replace("（[05-contracts.md](05-contracts.md)）", "（本文 §3）")
    appendix = (
        "\n---\n\n## 附录 A：平台对接待决（P1–P7）\n\n"
        "本地优化版建议，未在总规划定案。\n\n"
        + p_table +
        "\n\n## 附录 B：全局切片（S0–S2）\n\n"
        "本地优化版建议，未在总规划定案；S0 的契约明细见本文 §3。\n\n"
        + slices +
        "\n\n## 附录 C：来源\n\n"
        f"源文件：AgentOS 仓库 `{SOURCE_PATH}`，经 `tools/to_feishu.py` 转换。\n"
    )
    rest = localize_refs(rest.rstrip("\n") + "\n" + localize_refs(appendix))

    out, fenced = [], False
    for line in rest.split("\n"):
        if line.startswith("```"):
            fenced = not fenced
            out.append(line)
            continue
        out.append(line if fenced else escape_line(line))

    callout = "<callout emoji=\"📌\">\n" + "\n\n".join(escape_line(p) for p in paras) + "\n</callout>\n\n"
    head = f"```yaml\n{fm}\n```\n\n" if fm else ""
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(head + callout + "\n".join(out).rstrip("\n") + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(BASE.parent.parent.parent)}")


if __name__ == "__main__":
    main()
