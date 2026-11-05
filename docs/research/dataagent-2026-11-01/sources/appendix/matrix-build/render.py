# -*- coding: utf-8 -*-
"""把矩阵数据渲染成 Markdown 片段，注入报告模板。"""
import collections
import data
import overrides as o
import judgments

MODS = data.MODULES
CAPS = [c for m in MODS for c in m["caps"]]
BY_ID = {c[0]: c for c in CAPS}


def supply(c):
    return o.SUPPLY.get(c[0], c[6])


def star(c):
    return "★" if c[0] in o.MOAT else ""


def overview_table():
    rows = [
        "| 编号 | 一级模块 | 解决的问题 | 狭义形态 | 广义形态 | 二项 | P0 | 自研 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for m in MODS:
        caps = m["caps"]
        p0 = sum(1 for c in caps if c[3] == "P0")
        own = sum(1 for c in caps if supply(c) == "自研")
        rows.append(
            f"| {m['id']} | {m['name']} | {m['problem']} | {m['narrow']} | {m['broad']} | {len(caps)} | {p0} | {own} |"
        )
    tot_p0 = sum(1 for c in CAPS if c[3] == "P0")
    tot_own = sum(1 for c in CAPS if supply(c) == "自研")
    rows.append(f"| — | **合计 {len(MODS)} 个** | — | — | — | **{len(CAPS)}** | **{tot_p0}** | **{tot_own}** |")
    return "\n".join(rows)


def module_table(m):
    rows = [
        "| 编号 | 二级能力 | 是什么 | 狭义 | 广义 | 供给 | 验收口径 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for c in m["caps"]:
        rows.append(
            f"| {c[0]} | {star(c)}{c[1]} | {c[2]} | {c[3]} | {c[5]} | {supply(c)} | {c[7]} |"
        )
    return "\n".join(rows)


def module_sections():
    out = []
    for m in MODS:
        out.append(f"### {m['id']}｜{m['name']}\n")
        out.append(f"**职责边界：**{m['problem']}。狭义形态：{m['narrow']}；广义形态：{m['broad']}。\n")
        out.append("**接口契约**\n")
        out.append("```text")
        out.append(f"拥有的事实  {m['owns']}")
        out.append(f"输入        {m['inputs']}")
        out.append(f"输出        {m['outputs']}")
        out.append(f"关键不变量  {m['invariant']}")
        out.append(f"失败语义    {m['failure']}")
        out.append(f"责任角色    {m['role']}")
        out.append("```\n")
        out.append(module_table(m) + "\n")
        out.append("**关键判断**\n")
        for j in judgments.JUDGMENTS[m["id"]]:
            out.append(f"- {j}")
        out.append("")
    return "\n".join(out)


def batch_table(key):
    rows = [
        "| 编号 | 二级能力 | 闸门 | 供给 | 验收口径 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for cid in o.BATCH[key]:
        c = BY_ID[cid]
        rows.append(
            f"| {cid} | {star(c)}{c[1]} | {o.GATE.get(cid, '—')} | {supply(c)} | {c[7]} |"
        )
    return "\n".join(rows)


def broad_table():
    rows = [
        "| 模块 | 狭义形态 | 广义形态 | 判定 | 关键新增/扩大的二级能力 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for mid, narrow, broad, verdict, newcaps in data.BROAD:
        rows.append(f"| {mid} | {narrow} | {broad} | **{verdict}** | {newcaps} |")
    return "\n".join(rows)


def agentos_table():
    rows = ["| DataAgent 模块 | AgentOS 对应方向 | 分工 |", "| --- | --- | --- |"]
    for a, b, c in data.AGENTOS_MAP:
        rows.append(f"| {a} | {b} | {c} |")
    return "\n".join(rows)


def stats_table():
    p0 = [c for c in CAPS if c[3] == "P0"]
    p1 = [c for c in CAPS if c[3] == "P1"]
    p2 = [c for c in CAPS if c[3] == "P2"]
    sup = collections.Counter(supply(c) for c in CAPS)
    sup0 = collections.Counter(supply(c) for c in p0)
    rows = [
        "| 维度 | 数量 | 说明 |",
        "| --- | --- | --- |",
        f"| 一级模块 | {len(MODS)} | 12 个核心纵向 + 2 个横向契约 + 1 个广义纵向（DA15） |",
        f"| 二级能力 | {len(CAPS)} | 平均每模块 {len(CAPS)/len(MODS):.1f} 项 |",
        f"| 狭义 P0 | {len(p0)} | 缺失即无法交付可信答案（含 2 项企业/规模条件分支） |",
        f"| 狭义 P1 | {len(p1)} | 显著影响成功率、效率或规模化 |",
        f"| 广义 P2 | {len(p2)} | 广义阶段建设，狭义不做 |",
        f"| 自研 | {sup['自研']} | 其中核心自研（护城河）{len(o.MOAT)} 项 |",
        f"| 薄封装 | {sup['薄封装']} | 开源/引擎之上加契约与适配 |",
        f"| 集成 | {sup['集成']} | 直接使用成熟组件 |",
        f"| 平台 | {sup['平台']} | 由 AgentOS/运行时提供 |",
        f"| P0 中的自研 | {sup0['自研']} | 其余 {len(p0)-sup0['自研']} 项可集成、薄封装或由平台提供 |",
    ]
    return "\n".join(rows)


def moat_table():
    rows = ["| # | 编号 | 能力 | 为什么别人替不了 |", "| --- | --- | --- | --- |"]
    why = {
        "DA05.5": "语义→计划→SQL 的编译契约，决定口径能否被复用与解释",
        "DA06.1": "没有固定入口假设，新问题才能从最强线索进入，而不是被第一步选表锁死",
        "DA06.3": "反向定位（值→列→实体），是把业务语言映射到 schema 的关键",
        "DA06.5": "召回必须携带来源/版本/权限/新鲜度，否则答案无法审计、无法授权",
        "DA07.2": "把业务词绑定到稳定对象 ID 并保留多候选，决定“问的是不是这件事”",
        "DA07.3": "语义优先/受控兜底策略，决定准确率与可解释性的上限",
        "DA11.1": "查询级验证（空集/膨胀/守恒/时间/单位），是正确性的最后一道闸",
        "DA11.2": "口径验证（定义/版本/例外/as-of），是企业敢用的前提",
        "DA12.4": "黄金集与回归，是唯一能证明“变好了”的机制",
    }
    for i, cid in enumerate(o.MOAT, 1):
        c = BY_ID[cid]
        rows.append(f"| {i} | {cid} | {c[1]} | {why[cid]} |")
    return "\n".join(rows)


if __name__ == "__main__":
    import sys

    tpl = open("report_template.md", encoding="utf-8").read()
    repl = {
        "{{MODULES_OVERVIEW}}": overview_table(),
        "{{MODULE_SECTIONS}}": module_sections(),
        "{{BATCH_A}}": batch_table("A"),
        "{{BATCH_B}}": batch_table("B"),
        "{{BATCH_C}}": batch_table("C"),
        "{{BROAD_TABLE}}": broad_table(),
        "{{AGENTOS_TABLE}}": agentos_table(),
        "{{STATS_TABLE}}": stats_table(),
        "{{MOAT_TABLE}}": moat_table(),
    }
    for k, v in repl.items():
        tpl = tpl.replace(k, v)
    out = sys.argv[1] if len(sys.argv) > 1 else "report.md"
    open(out, "w", encoding="utf-8").write(tpl)
    print("written", out, len(tpl), "chars")
