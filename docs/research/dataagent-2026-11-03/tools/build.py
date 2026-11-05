#!/usr/bin/env python3
"""从飞书快照（总规划 r1045）生成 v0.2。

用法（在仓库根目录）：
    python3 -I docs/research/dataagent-2026-11-03/tools/build.py

输入：docs/research/dataagent-2026-11-02/sources/feishu-r1045/*.md（只读）
输出：docs/research/dataagent-2026-11-03/ 下 00–04 五份文档与 catalog/。
每处修改都按原文精确匹配并断言出现次数；任何锚点失配都会中止，避免静默漏改。
修订依据：docs/research/dataagent-2026-11-02/online-r1024-review.md（R1–R8）。
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
SRC = OUT.parent / "dataagent-2026-11-02" / "sources" / "feishu-r1045"

FILES = {
    "M": ("M-main-r1045.md", "00-pluggable-dataagent.md"),
    "D": ("D-data-layer-r14.md", "01-data-layer.md"),
    "A": ("A-application-layer-r8.md", "02-application-layer.md"),
    "G": ("G-governance-layer-r7.md", "03-governance-layer.md"),
    "O": ("O-operations-fde-layer-r8.md", "04-operations-fde-layer.md"),
}
FEISHU = {
    "TlN4dygs9oJR3Qx1FaictiPEn3c": "00-pluggable-dataagent.md",
    "NXe7dMEEQoJ5wqxcPsRczoebn4d": "01-data-layer.md",
    "ReDXdJzLWoihZDxqaO0clUxInKf": "02-application-layer.md",
    "QwN4dFvdroH7X3xI3Eycnkbon3b": "03-governance-layer.md",
    "NqS0dcV0CoaatHxJTTFc7amnnke": "04-operations-fde-layer.md",
    "VavsdOWFeoLBFrxOt9JcjAsInDe": "05-contracts.md",
    "NvOsd04lAoZk60xY2Kpc4SrYnwf": "06-data-layer-build-plan.md",
}
CATALOG_REL = "catalog/atomic-capability-catalog.json"
EXPECTED = {  # 层 → (能力组, 原子)
    "D": (51, 165), "A": (41, 126), "G": (20, 73), "O": (29, 94),
}
EXPECTED_MAIN = (18, 141, 458)


class Doc:
    def __init__(self, key: str, text: str):
        self.key, self.text = key, text

    def rep(self, old: str, new: str, count: int = 1) -> None:
        n = self.text.count(old)
        if n != count:
            sys.exit(f"[{self.key}] 期望 {count} 处，实际 {n} 处：{old[:80]!r}")
        self.text = self.text.replace(old, new)

    def _line_index(self, prefix: str) -> tuple[list[str], int]:
        lines = self.text.split("\n")
        hits = [i for i, l in enumerate(lines) if l.startswith(prefix)]
        if len(hits) != 1:
            sys.exit(f"[{self.key}] 行前缀应唯一，实际 {len(hits)} 处：{prefix[:80]!r}")
        return lines, hits[0]

    def after(self, prefix: str, *new_lines: str) -> None:
        lines, i = self._line_index(prefix)
        lines[i + 1:i + 1] = list(new_lines)
        self.text = "\n".join(lines)

    def before(self, prefix: str, *new_lines: str) -> None:
        lines, i = self._line_index(prefix)
        lines[i:i] = list(new_lines)
        self.text = "\n".join(lines)

    def in_line(self, prefix: str, old: str, new: str) -> None:
        lines, i = self._line_index(prefix)
        if lines[i].count(old) != 1:
            sys.exit(f"[{self.key}] 行内应唯一：{old!r} in {lines[i][:80]!r}")
        lines[i] = lines[i].replace(old, new)
        self.text = "\n".join(lines)

    def set_last_cell(self, prefix: str, value: str) -> None:
        lines, i = self._line_index(prefix)
        cells = lines[i].rstrip().rstrip("|").rsplit("|", 1)
        lines[i] = f"{cells[0]}| {value} |"
        self.text = "\n".join(lines)

    def replace_line(self, prefix: str, new: str) -> None:
        lines, i = self._line_index(prefix)
        lines[i] = new
        self.text = "\n".join(lines)


def load() -> dict[str, Doc]:
    return {k: Doc(k, (SRC / src).read_text(encoding="utf-8")) for k, (src, _) in FILES.items()}


# ---------------------------------------------------------------------------
# 共用：转换飞书标记与链接
# ---------------------------------------------------------------------------
def localize(text: str) -> str:
    text = re.sub(r"^<title>(.*?)</title>$", r"# \1", text, count=1, flags=re.M)

    def callout(m: re.Match) -> str:
        emoji, body = m.group(1), m.group(2).strip("\n")
        out = []
        for j, line in enumerate(body.split("\n")):
            line = line.rstrip()
            out.append(f"> {emoji} {line}" if j == 0 else (f"> {line}" if line else ">"))
        return "\n".join(out)

    text = re.sub(r'<callout emoji="([^"]+)">\n(.*?)\n</callout>', callout, text, flags=re.S)
    text = re.sub(
        r'<figure view-type="Preview"><source name="([^"]+)"[^>]*/></figure>',
        lambda m: f"本层条目见 [`{CATALOG_REL}`]({CATALOG_REL})。",
        text,
    )

    def link(m: re.Match) -> str:
        label, token = m.group(1), m.group(2)
        if re.search(r"catalog|机器可读|原子能力目录|JSON", label):
            return f"[{label}]({CATALOG_REL})"
        return f"[{label}]({FEISHU[token]})"

    text = re.sub(r"\[([^\]]+)\]\(https://modelbest\.feishu\.cn/docx/([A-Za-z0-9]+)\)", link, text)
    # 标题中的版本号
    text = "\n".join(re.sub(r" v0\.\d\b", "", l) if l.startswith("#") else l for l in text.split("\n"))
    return text


CHANGES: dict[str, str] = {}


def layer_banner(key: str, adds: str) -> str:
    CHANGES[key] = adds.replace("本层新增", "新增").rstrip("。")
    return ""


# ---------------------------------------------------------------------------
# 总文档 M
# ---------------------------------------------------------------------------
SEC_2_3_2_4 = r"""
## 2.3 平台对接待决

实现前须定案。内核依据：`agent-kernel@f0fa521`，权威源 `kernel/iface/src`。

| 编号 | 待决项 | 当前做法 | 内核 / Mint 事实 | 选项 | 建议 | 最晚定案 |
|-|-|-|-|-|-|-|
| P1 | 写通道怎么强制 | Python `action_gateway.py`，靠端口约定 | `EffectLevel::SideEffect`；guard 为单一门 | A 进程隔离：写后端凭据只发给网关进程；B 语言隔离：Rust 网关；C 只靠约定 | **A**，语言可后定；拒绝 C | S1 回写之前 |
| P2 | 数据访问判定与内核 guard | DA12.1 自出 `AccessDecision`，多点复检 | guard 单一门、fail-closed（`kernel/core/src/guard/`） | A 单闸门；B 双闸门；C guard 判定 + DA12.1 策略源，复检只用于不经内核的路径 | **C**：经内核的调用以 guard 为准；缓存命中、导出、离线索引由 DA12.1 复检；两路共用同一策略版本 | S0 之前 |
| P3 | 档位与审批映射 | 自拟 `ApprovalRequestRef` | `ApprovalRequest` 仅 4 字段；`ReviewPosition` 四段 | A 扩充内核字段；B 证据包外置，`summary` 携带 `EvidencePackageRef` | **B**；A0→ReadOnly，A1→Advance + Plan 审查，A2→SideEffect + ToolParams 审查 | S1 之前 |
| P4 | 组合清单与发布格式 | 自拟 `component-specs` / `presets` YAML，一层一工作区 | `kind = "skill"`（`SKILL.md`）、`kind = "preset"`（`[dependencies]` + `preset.toml`）；`AssemblyIntent.payload` 承载声明式装配数据；`mint.toml` 有 `license` 与 `[capabilities]` | A 沿用 Mint 包格式；B 自拟；C 自拟后转换 | **A**：DA18.6 产出 skill 包，DA18.7 产出 preset 包，运行时组合参数序列化进 `AssemblyIntent.payload`；开发期可一层一工作区 | 首次发布 MintHub 之前 |
| P5 | 轨迹与记忆存储 | 自建 SQLite `TraceRepository` | `StoreContract` 已定义，仅内核内部使用：L-C 无组件可用的 append/read，command/WASM 组件拿不到存储句柄，mint-core 路径无内核；会话内游标，无跨会话查询；工具调用由 `TraceSink.record_input` 写前留痕 | A 轨迹落 `StoreContract`、作用域记忆自建；B 全部自建 | **A**，分两步：S0 先按 `StoreContract` 接口形状本地实现 DA04.1，事件携带 `kernel_session_id`/`kernel_call_id`，经内核调用时 DA04.1.2 只记数据层增量；内核提供组件事件接口（`store.ext_append`/`store.ext_read`，见 [06-data-layer-build-plan.md](06-data-layer-build-plan.md) 附录 A）后切换适配器。DA04.3 自建并冻结 `Scope` 形状 | 内核接口：S1 之前 |
| P6 | 编队与接管 | 未用内核原语 | `DelegationGrant`、`Lease`、`BlockedOnItem` | A 机制归 OS；B 能力层自建 | **A**：DA14.6、DA14.7、DA16.1 引用内核原语，能力层只做角色与子目标划分 | S2 之前 |
| P7 | 存储后端 | SQLite 起步，端口可替换 | — | — | 维持；DA17.5.2 环境预检检查并发、保留、审计要求是否超出 SQLite | 部署前 |

## 2.4 跨层契约

各层所引“总体跨层约定”即本节。

1. **契约包。** 共享类型提取为独立包 `dataagent-contracts`（第 0 层）。数据层、应用层、治理层、运行层只依赖它，互不导入对方实现。数据层 `src/dataagent_data/contracts/` 中的公共部分迁入该包，各层 `contracts/` 只保留本层特有类型。
2. **包内范围：**
   - 调用封套：`CallContext`、`CapabilityResult`、`Issue`、`ExecutionRef`、`Continuation`；
   - 引用：`AssetRef`、`ResourceRef`、`SnapshotRef`、`SourceAnchor`、`EvidenceRef`、`TaskContextRef`、`DeliveryRef`；
   - 统一词表：`LifecycleStatus`、`ActionTier`、`AccessDecision`、`ComponentMeta`（含 `license`）。
3. **`LifecycleStatus`：** `draft → candidate → validated → active → deprecated / invalidated / rejected`。经验用 `candidate/validated/active/deprecated`；治理资产用 `draft/validated/active/deprecated/invalidated`；程序用 `draft/validated/rejected`，是否已执行记为执行记录属性，不作为状态。
4. **依赖方向：** contracts ← data ← application；治理层、运行层只依赖 contracts，以及经端口注入的实现。
5. **类型完整度门槛：** 进入某个切片（§4.1）的原子，其输入输出类型必须在 contracts 中有字段定义；只有名字的类型不得进入切片验收。
6. **schema：** 先写类型、再生成 schema（`contracts/generated/`），不手写第二份。

类型与字段明细见 [05-contracts.md](05-contracts.md)。
"""

SEC_4_X = r"""
## 4.1 全局切片

切片按业务闭环定义，各层文档中的切片为层内细化。验收看实际业务输出、拒绝与未知项处理、可接管性；后一切片不要求前一切片的能力全部完成。

| 切片 | 目标 | 能力范围 | 入口条件 | 退出（验收）条件 |
|-|-|-|-|-|
| **S0 通用只读证据闭环** | 文件、文档或记录 → 带依据、可验收的结论；只读，不写回源系统 | 骨干：DA01.4/01.5、DA04.1、DA06.3.5、DA07.5、DA07.10.1、DA10.3、DA11.5、DA12.1；判定族增量：DA02.8、DA02.12、DA03.4.3、DA03.15、DA03.16；计算族增量：DA01.4.2/4.6、DA02.1/02.2/02.4、DA03.4.1、DA06.1、DA06.3.1、DA07.1.3、DA11.2.3、DA10.1.1 | §2.3 P2、P5 已定；契约包 core 字段完整（[05-contracts.md](05-contracts.md)） | 判定族、计算族各用至少一个应用样本，在未见验收样本上按 DA11.5.5 端到端验收；报告列出未覆盖范围与不可判定项；六类指标并报；任何应用都不需要修改 core |
| **S1 组合沉淀与回写** | S0 有效组合发布为 Mint 包；结论经审批回写源系统 | DA18.6/18.7（产出 Mint skill/preset 包）、DA05.8；DA15 A0/A1/A2、DA16.2、DA07.7/07.8、DA14.6 | §2.3 P1、P3、P4 已定；S0 通过验收 | 包能从 MintHub 安装并复现 S0 结果；回写全部经 DA07.7，执行结果未知时只对账；审批证据可审计 |
| **S2 持续运行与移交** | 客户环境长期运行并移交客户 | DA17.2/17.5、DA14.2/14.8、DA18.1–18.5、DA11.7/11.9 | §2.3 P6、P7 已定；S1 通过验收 | 影子运行与人工结果的差异在约定范围内；按环节放权；与 DA02.15 基线同口径比较 |

未列入切片的能力组为“按需”，如 DA09、DA13、DA02.13–15、DA12.9。

**切片与应用**：切片定义通用能力范围。应用按闭环族选择增量原子，提供领域资产（规则、指标、判据、样本）；新增 core 契约或能力编号须有至少两个应用或两层需要。

| 闭环族 | 回答的问题 | 应用示例 |
|-|-|-|
| 判定族 | 这些记录是否符合这些规范性条款，依据是什么 | 令才（制度提取与规则审核）、合同条款核查、合规巡检 |
| 计算族 | 这个指标或问题在这些数据上的结果是多少，口径与来源是什么 | 文件即席分析、报表问数、经营指标核对 |

## 4.2 唯一归属

每个概念一个归属方，其他位置只引用。

| # | 概念 | 唯一归属 | 其他位置 |
|-|-|-|-|
| 1 | 执行前影响面评估 | **DA12.11** | DA03.11.4 只描述业务影响与可逆条件；DA15.3.3 只声明评估要求；DA07.7.3 的预演差异作为 DA12.11 输入 |
| 2 | 引擎一致性比对 | **DA07.10.2**（唯一产出 `EngineConsistencyReport`） | DA11.4.5 编排固定样本并纳入回归结论 |
| 3 | 数据访问判定 | **DA12.1**（执行点见 §2.3 P2） | DA03.12 只声明权属模型 |
| 4 | 动作授权与审批 | **DA16** | DA07.7.1 消费 DA16 授权决定与 DA12.1 访问决定 |
| 5 | 审批策略 | 正式策略：**DA03.12.3**（定） | DA15.1.2 只映射档位到策略引用；DA16.2.1 运行时判定是否触发；DA12.11.3 提供分级阈值；DA06.7.2 只建议审批点 |
| 6 | 生命周期状态 | **`LifecycleStatus`**（§2.4） | 经验、治理资产、程序各用子集 |
| 7 | 组件、Skill、Preset 目录 | 存储：**DA04.4**；元数据：`ComponentMeta`；检索：**DA05.8** | DA15.4 只登记动作契约；DA05.8.1 输入含动作契约 |
| 8 | 版本固定 | 环境默认：**DA17.2**；任务实际固定：**DA04.5** | 全文统一称“默认版本”或“任务固定版本” |

---

# 附录 A：调研参照

外部调研：`../dataagent-landscape-2026-10-31/`、`../dataagent-retrieval-2026-10-31/`。

| 能力 | 调研参照 |
|-|-|
| DA03.9、DA06.8 | 02 §5（dbt/MetricFlow）、§7（Ossie 转换损失）；01 §4.2（Spotter、Looker） |
| DA03.3、DA06.2、DA11.2 | 02 §5.2、§6.1（SCD、复合键、多事实、倍增度量）；00 §3.3 |
| DA04.6、DA12.2.5 | 04 §3（LinkedIn 双存储）、§6（自动学习污染）；01 §4.4（Genie 反馈） |
| DA05.1、DA05.9、DA06.4 | retrieval 00 §1–3、§7 |
| DA07.2 | 03 §4.3（PandasAI 沙盒，issue #1801） |
| DA01.10、DA12.1、DA16.1 | 01 §4.5（身份与权限）；05 §4（dbt MCP 凭据）；03 §4.1（Vanna） |
| DA05.8、DA18.7 | 02 §5.1、03 §8–9（许可） |
| DA01.4、DA10.1 | 03 §5.1（日期系统、公式缓存、未改区域保护） |
| DA02.12、DA14.2 | 04 §4（Ramp：抽取标签版本与漂移） |
| DA09.1、DA09.3、DA11.3 | 03 §5.3–5.4（预测区间、求解器终态） |
| DA11.4–DA11.6 | 00 §7–8；01 §4.3、§5（各产品评测的局限） |

# 附录 B：修订记录

| 项 | 修订 | 位置 |
|-|-|-|
| R1 | 新增平台对接待决 P1–P7 | §2.3 |
| R2 | 新增跨层契约与 `dataagent-contracts`、统一 `LifecycleStatus`；DA01.4.4 与 DA02.3.3 衔接 | §2.4；数据层 |
| R3 | 唯一归属表；改写相关边界（DA03.12、DA04.4、DA05.8、DA07.7.1、DA11.4.5、DA12.11、DA15.1.2、DA15.3.3、DA15.4、DA16.2.1、DA12.11.3） | §4.2；各层 |
| R4 | 文字一致性：版本固定的旧称统一为默认版本 / 任务固定版本；DA03.14 边界；DA18 的 FDE 标注（45 → 43） | §三；各层 |
| R5 | 新增能力组 DA05.9、DA06.8；新增原子 24 项；修改 DA03.9.1、DA06.2、DA07.2、DA11.4.1、DA12.1、DA16.1、DA16.1.2 | §三；各层 |
| R6 | 全局切片 S0–S2 | §4.1 |
| R7 | DA18.6/18.7 发布为 Mint skill / preset 包 | DA18；§2.3 P4 |
| R8 | 调研参照 | 附录 A |

计数：模块 18，能力组 139 → 141，原子能力 434 → 458，硬能力组 30 → 31，FDE 能力组 45 → 43；各层原子数 160 / 116 / 67 / 91 → 165 / 126 / 73 / 94。
"""


def edit_main(d: Doc) -> None:
    for label in ["数据层", "执行应用层", "评测与治理层", "持续运行与 FDE 交付"]:
        d.rep(f"[{label} v0.1](", f"[{label}](")
    d.rep("[契约层 dataagent-contracts v0.1](", "[契约层 dataagent-contracts](")
    d.after("| [持续运行与 FDE 交付](", "| [数据层建设方案](06-data-layer-build-plan.md) | DA01–DA04（S0） | 32 | S0 数据层与契约包 core 的实现方案：包结构、调用约定、Agent 侧推理、存储与轨迹、Mint 打包、分步与验证；附内核组件事件接口提案 |")
    d.after("| [数据层建设方案](", "| [执行应用层建设方案](07-application-layer-build-plan.md) | DA05–DA10（非 FDE） | 110 | S0 13 项与按需能力的实现方案：表达式与 SQL 执行、需求绑定与澄清、交付；跨层类型迁移；阶段与并行流 |")
    d.after("| [执行应用层建设方案](", "| [评测与治理层建设方案](08-governance-layer-build-plan.md) | DA11–DA12（非 FDE） | 54 | S0 6 项与按需能力的实现方案：访问与外发判定、运行时复检、判据与样本隔离、端到端验收；S0 Preset |")
    d.after("| [评测与治理层建设方案](", "| [总 Catalog](catalog/atomic-capability-catalog.json) | DA01–DA18 | 458 | 全部原子能力：编号、名称、能力组、模块、所在层、形态、FDE、operation、源码文件、切片、S0 闭环族 |")
    d.rep("| DataAgent 形态 | FDE 形态 | FDE 叠加了什么 |", "| DataAgent 形态 | FDE 形态 | 延展 |")
    d.rep("| 从数据源扩到工作环境；密钥不出域 |", "| 从数据源扩到工作环境、文件系统 |")
    d.rep("| DA04.5 任务上下文 | DA17.2 版本钉定 + DA17.3 上下文派发 |",
          "| DA04.5 任务上下文 | DA17.2 环境版本配置 + DA17.3 上下文派发 |")
    for old, new in [("| DA01–DA04、DA13 | 160 |", "| DA01–DA04、DA13 | 165 |"),
                     ("| DA05–DA10 | 116 |", "| DA05–DA10 | 126 |"),
                     ("| DA11–DA12 | 67 |", "| DA11–DA12 | 73 |"),
                     ("| DA14–DA18 | 91 |", "| DA14–DA18 | 94 |"),
                     ("可替换和可评测的选择点 | 139 |", "可替换和可评测的选择点 | 141 |"),
                     ("内部可以组合其他能力 | 434 |", "内部可以组合其他能力 | 458 |")]:
        d.rep(old, new)
    d.after("硬/软描述主要职责，定是约束标记", *SEC_2_3_2_4.rstrip("\n").split("\n"))

    # DA01–DA04
    d.after("- `DA01.4.5` ", "- `DA01.4.6` 工作簿日期系统与公式缓存识别 — 识别 1900/1904 日期系统、公式缓存值与最后计算状态，标出需重算的单元")
    d.after("- `DA02.12.3` ", "- `DA02.12.4` 抽取标签体系版本化 — 为抽取目标结构和标签体系登记版本，抽取结果绑定该版本")
    d.after("- `DA03.3.3` ",
            "- `DA03.3.4` 键类型与复合键定义 — 定义主键、外键、自然键与复合键，复合键保留全部组成列",
            "- `DA03.3.5` SCD 有效期与粒度规则定义 — 定义缓慢变化维的有效期，以及按粗时间粒度取值的规则")
    d.in_line("- `DA03.9.1` ", "读取 dbt/MetricFlow/Cube 等定义", "读取 dbt/MetricFlow/Cube 等定义；已认证指标优先经 DA06.8 委托编译，导入副本仅用于检索与解释")
    d.after("- `DA03.9.4` ", "- `DA03.9.5` 语义导出与损失报告 — 导出为外部格式，同时给出支持矩阵和逐项损失报告")
    d.rep("不做运行时鉴权，鉴权归 DA16。", "不做运行时鉴权；数据访问判定归 DA12.1，动作委托与审批归 DA16。")
    d.rep("不复用内核的请求/任务状态语义。", "业务状态不复用内核的请求/任务状态语义；二者对应关系由 DA03.14.3 登记。")
    d.replace_line("- `DA03.14.3` ", "- `DA03.14.3` 与执行状态机的对应登记 — 记录业务状态与执行观测的对应关系，不改变任何一方语义")
    d.rep("复用 MintHub 或现有资产存储机制；保留可执行内容或有效引用，依赖关系复用已有血缘。",
          "复用 MintHub 或现有资产存储机制；保留可执行内容或有效引用，依赖关系复用已有血缘。组件、Skill、Preset 的目录存储归本组，元数据见 §2.4 `ComponentMeta`。")

    # DA05
    d.rep("复用能力目录及包元数据；只检索筛选，不安装执行，不承担目录存储或授权判定。",
          "复用能力目录及包元数据；只检索筛选，不安装执行；目录存储归 DA04.4，不承担授权判定。")
    d.after("| DA05.8 | ",
            "| DA05.9 | 检索充分性与停止 | 软 | 判断已召回对象是否足以回答本题：角色是否绑定、必要依赖是否齐全、空结果属于哪类，以及何时停止检索。 | 不做相关性排序（归 DA05.6），不判定业务正确（归 DA11）；依赖闭包缺失时报告缺口，不得假定缺失项不存在。 | 候选集与题目绑定 → 充分性判定、缺口清单与停止或继续建议 |")
    d.in_line("- `DA05.8.1` ", "查找候选组件及其可替换实现", "查找候选组件、动作契约及其可替换实现")
    d.after("- `DA05.8.3` ",
            "- `DA05.8.4` 许可与分发约束筛选 — 按许可证、权重或数据许可，以及分发场景筛选候选",
            "- `DA05.9.1` 题内角色绑定 — 把召回对象绑定为本题的度量、维度、过滤、时间或连接角色",
            "- `DA05.9.2` 必要依赖闭包检查 — 检查桥表、租户键、时间键、单位等必要依赖是否齐全",
            "- `DA05.9.3` 空结果与失败分类 — 区分未命中、覆盖不足、索引过期、权限截断与预算截断",
            "- `DA05.9.4` 检索停止判定 — 依据充分性、预算与边际收益给出停止、继续或转澄清")

    # DA06–DA07
    d.rep("物理实现可以是表列、业务接口或函数，不临时创造业务定义。",
          "存在认证定义时先走 DA06.8；物理实现可以是表列、业务接口或函数，不临时创造业务定义。")
    d.after("| DA06.7 | ",
            "| DA06.8 | 认证指标委托编译 | 硬 | 已有认证定义的指标委托外部语义层（MetricFlow、Cube、dbt Semantic Layer 等）编译取数，并回传编译计划与 SQL。 | 不改写认证定义；外部编译器不支持时显式降级到 DA06.2，并标注“非认证路径”。外部语义层经 DA01.1 连接，适配器按实现区分，不单列原子。 | 指标请求与认证定义引用 → 编译计划、SQL 与认证路径标记 |")
    d.after("- `DA06.2.2` ", "- `DA06.2.3` 多事实对齐与倍增度量展开 — 多事实先各自聚合再按合法公共粒度对齐；倍增度量走分支聚合")
    d.after("- `DA06.7.3` ",
            "- `DA06.8.1` 认证定义绑定 — 把请求中的指标绑定到已发布的认证定义及其版本",
            "- `DA06.8.2` 外部语义编译调用 — 调用外部语义层编译或解释接口，取回计划与 SQL",
            "- `DA06.8.3` 降级标注 — 外部编译不可用时记录原因，并把结果标为非认证路径")
    d.rep("依赖现有运行环境和沙盒，不负责选择分析方法。",
          "依赖现有运行环境和沙盒，不负责选择分析方法；无法确认隔离时失败关闭，不回退到宿主进程执行；运行镜像以 digest 固定。")

    # DA10–DA12
    d.after("- `DA10.1.3` ", "- `DA10.1.4` 既有工作簿受限编辑 — 只改指定区域，输出结构 diff，并用固定引擎重算")
    d.after("- `DA11.2.4` ", "- `DA11.2.5` 语义陷阱反例检查 — 用跨租户同 ID、复合键缺列、迟到退款、join 膨胀等反例验证计划与结果")
    d.replace_line("- `DA11.4.1` ", "- `DA11.4.1` 检索回归评测 — 评估必要集合全召回、误选后恢复与停止，不只看 TopK")
    d.replace_line("- `DA11.4.5` ", "- `DA11.4.5` 引擎一致性回归编排 — 在固定样本集上调用 DA07.10.2 并纳入回归结论，不另算一份")
    d.after("- `DA11.5.6` ", "- `DA11.5.7` 多角色越权用例构建 — 构造不同权限角色提同一问题的用例，验证可见范围随身份变化")
    d.after("- `DA11.6.3` ", "- `DA11.6.4` 接入与维护成本度量 — 首个可信答案耗时、首次接入工时、每次变更修复工时与专家处理比例")
    d.rep("复用平台和源端控制，并在各使用环节生效。",
          "复用平台和源端控制，并在各使用环节生效；执行权限与“数据可进入模型上下文”分别判定（DA12.1.4）。")
    d.after("- `DA12.1.3` ", "- `DA12.1.4` 模型上下文可见性与外发控制 — 判定哪些数据可进入模型上下文或发往外部模型服务")
    d.after("- `DA12.2.5` ", "- `DA12.2.6` 规范与转换器版本登记 — 外部规范与转换器版本与本方语义发布版本分开登记")
    d.after("- `DA12.10.4` ", "- `DA12.10.5` 请求者与执行身份双记录 — 每次访问和动作同时记录请求者与 Agent 执行身份")
    d.rep("不替代审批，审批归 DA16。", "执行前影响面评估以本组为唯一产出方，DA07.7.3 预演差异为输入；不替代审批，审批归 DA16。")
    d.replace_line("- `DA12.11.3` ", "- `DA12.11.3` 分级授权阈值 — 提供分级阈值，供 DA03.12.3 正式审批策略引用")

    # DA14–DA18
    d.after("- `DA14.2.3` ", "- `DA14.2.4` 抽取标签漂移监控 — 监控抽取标签分布与置信度的漂移")
    d.replace_line("- `DA15.1.2` ", "- `DA15.1.2` 档位与审批策略映射 — 把档位映射到 DA03.12.3 正式策略的引用")
    d.replace_line("- `DA15.3.3` ", "- `DA15.3.3` 影响面评估要求声明 — 声明执行前须由 DA12.11 评估的影响维度与上界要求")
    d.rep("动作检索由 DA05.8 复用本目录；运行时授权判定归 DA16 及执行控制。",
          "动作检索由 DA05.8 复用本目录（DA05.8.1 输入含动作契约）；组件与 Skill/Preset 目录存储归 DA04.4；运行时授权判定归 DA16 及执行控制。")
    d.rep("不复用人的凭据，不允许无限期继承。", "不复用人的凭据，不允许无限期继承；有效权限取请求者权限与 Agent 委托范围的交集。")
    d.replace_line("- `DA16.1.2` ", "- `DA16.1.2` 委托范围与时限 — 定义委托范围与时限；有效权限为请求者权限与 Agent 权限的交集，不得超出请求者")
    d.after("- `DA16.1.3` ", "- `DA16.1.4` 请求者身份传播 — 把请求者身份沿调用链传到取数与执行点，供权限取交集")
    d.replace_line("- `DA16.2.1` ", "- `DA16.2.1` 触发判据 — 按 DA03.12.3 正式策略在运行时判定是否触发审批")
    for i, what in enumerate(["数据快照", "本体与契约版本", "权限策略版本", "评测集与预算版本"], 1):
        d.in_line(f"- `DA17.2.{i}` ", f"钉住{what}", f"登记默认{what}")
    d.replace_line("- `DA17.5.4` ", "- `DA17.5.4` 健康检查 — 确认实例可用，且实际版本与默认版本或任务固定版本一致")
    d.rep("### DA18｜交付与交接 〔FDE〕", "### DA18｜交付与交接")
    for gid, name in [("DA18.1", "Runbook"), ("DA18.2", "自助界面"), ("DA18.3", "知识移交"),
                      ("DA18.4", "运营协议"), ("DA18.5", "交付效果度量")]:
        d.rep(f"| {gid} | {name} |", f"| {gid} | {name} 〔FDE〕 |")
    d.rep("| 业务要求与能力 → Skill 草案或修订 |", "| 业务要求与能力 → Skill 草案或修订；发布为 Mint `kind = \"skill\"` 包 |")
    d.rep("复用 DA05.8 检索、DA08.6 程序生成、DA11 验证及 DA12 版本发布；不在本模块重建执行引擎。 | 候选能力组合 → 可试运行与交付的组件包 |",
          "复用 DA05.8 检索、DA08.6 程序生成、DA11 验证及 DA12 版本发布；不在本模块重建执行引擎。发布形态见 §2.3 P4。 | 候选能力组合 → 可试运行与交付的组件包；发布为 Mint `kind = \"preset\"` 包 |")
    d.in_line("- `DA18.7.3` ", "将通过验收的组合封装为可复用包", "将通过验收的组合封装为可复用包；包元数据含 `license` 与 `[capabilities]` 声明")
    d.after("- `DA18.7.3` ", "- `DA18.7.4` 组合许可清单生成 — 生成依赖许可清单，并检查与分发场景是否兼容")

    # 四、依赖关系
    d.after("DA01/02 按需提供数据与探查；DA03 维护业务语义",
            "已认证指标经 DA06.8 委托外部语义层编译；新问题走 DA06.2/06.3，由 DA05.9 判断检索是否充分")
    d.text = d.text.rstrip("\n") + "\n" + SEC_4_X


# ---------------------------------------------------------------------------
# 数据层 D
# ---------------------------------------------------------------------------
def edit_data(d: Doc) -> None:
    d.rep("<title>DataAgent 数据层：模块与原子能力接口设计 v0.1</title>",
          "<title>DataAgent 数据层：模块与原子能力接口设计</title>"
          + layer_banner("D", "本层新增 DA01.4.6、DA02.12.4、DA03.3.4、DA03.3.5、DA03.9.5（160 → 165 项）。"))
    d.rep("本版依据 2026-11-02 更新后的飞书 revision 1022，保留原编号，拟定 **4 个核心模块 + 1 个扩展模块、51 个能力组、160 项原子能力**",
          "本版（v0.2，编号在 revision 1022 基础上追加）拟定 **4 个核心模块 + 1 个扩展模块、51 个能力组、165 项原子能力**")
    d.in_line("| 核心 | [DA01 数据接入]", "| 10 / 31 |", "| 10 / 32 |")
    d.in_line("| 核心 | [DA02 数据准备与探查]", "| 15 / 48 |", "| 15 / 49 |")
    d.in_line("| 核心 | [DA03 业务语义与关系]", "| 16 / 50 |", "| 16 / 53 |")
    d.rep("本版不新增能力编号。", "")
    d.rep("160 项编号均有明确入口", "165 项编号均有明确入口")
    d.rep("避免将 160 项全部放进", "避免将 165 项全部放进")
    d.rep("| 160 项初期会产生", "| 165 项初期会产生")
    d.after("| DA01.4.5 文本型 PDF 解析",
            "| DA01.4.6 工作簿日期系统与公式缓存识别 | `inspect_workbook_calc_state` | FileRef 或 WorkbookRef、sheet 范围、读取策略 | WorkbookCalcState；日期系统（1900/1904）、公式单元与缓存值、最后计算标记、需重算单元清单 | 只识别不重算；缓存值不当作已重算结果，重算归 DA10.1.3/10.1.4。 |")
    d.in_line("| DA02.3.3 嵌套字段展开", "| DataBatchRef、字段路径", "| DataBatchRef 或含嵌套记录的 DocumentRef（DA01.4.4 输出）、字段路径")
    d.after("| DA02.12.3 抽取结果原文锚定",
            "| DA02.12.4 抽取标签体系版本化 | `register_extraction_schema_version` | 目标结构/标签体系定义、变更说明、适用文档类型、上一版本引用 | ExtractionSchemaRef 新版本；字段/标签差异、兼容性说明 | 抽取结果必须绑定版本；版本变化不自动重抽历史文档，重抽经 DA12.7 计划。漂移监控归 DA14.2.4。 |")
    d.after("| DA03.3.3 时态关系定义",
            "| DA03.3.4 键类型与复合键定义 | `define_key_structures` | 实体/表映射、键候选（DA02.5）、业务唯一性依据、租户与时间维 | KeyDefinitionDraft；主键/外键/自然键/代理键、复合键组成列及顺序、唯一性验证需求 | 复合键保留全部组成列，不以拼接字符串替代，不静默丢列；值重合不等于键合法。 |",
            "| DA03.3.5 SCD 有效期与粒度规则定义 | `define_scd_rules` | 维度实体引用、有效期/当前标记字段、变更类型、查询时间粒度 | SCDRuleDraft；有效区间语义、开闭边界、粗粒度取值规则（期初/期末/逐笔）、冲突处理 | 明示粗粒度取值规则，不默认等于逐笔业务时点；实际 as-of Join 由 DA06/07 执行。 |")
    d.in_line("| DA03.9.1 外部语义层导入", "保留原定义引用，不声称不同语义系统完全等价。",
              "保留原定义引用，不声称不同语义系统完全等价；已认证指标优先经 DA06.8 委托编译，导入副本仅用于检索与解释。")
    d.after("| DA03.9.4 待确认项排序",
            "| DA03.9.5 语义导出与损失报告 | `export_semantics_with_loss_report` | 语义版本引用、目标格式与规范版本、导出范围 | ExportArtifactRef；支持矩阵、逐项损失/降级（指标、粒度、复合键、时间维）、不可导出项 | 导出通过 schema 不等于语义等价；损失项不得静默丢弃，迁移验收需在目标平台跑真实问题。规范版本登记归 DA12.2.6。 |")
    d.rep("边界：不做运行时鉴权，鉴权归 DA16。", "边界：不做运行时鉴权；数据访问判定归 DA12.1，动作委托与审批归 DA16。")
    d.rep("边界：不复用内核的请求/任务状态语义。", "边界：业务状态不复用内核的请求/任务状态语义；二者对应关系由 DA03.14.3 登记。")
    d.rep("经验的 `status` 暂用 `candidate / validated / active / deprecated`，",
          "经验的 `status` 使用共享 `LifecycleStatus` 的子集 `candidate / validated / active / deprecated`（见总文档 §2.4），")
    d.rep("# 共享类型的实现权威源", "# 本层特有类型；共享基础类型迁至 dataagent-contracts（总文档 §2.4）")


# ---------------------------------------------------------------------------
# 执行应用层 A
# ---------------------------------------------------------------------------
SEC_DA05_9 = """#### DA05.9 检索充分性与停止（软）

职责：判断已召回对象是否足以回答本题：对象在本题中的角色是否绑定、必要依赖是否齐全、空结果属于哪一类，以及何时停止检索。 边界：不做相关性排序（归 DA05.6），不判定业务正确（归 DA11）；依赖闭包缺失时报告缺口，不得假定缺失项不存在。

组输入输出：候选集与题目绑定 → 充分性判定、缺口清单与停止或继续建议。拟议文件：`src/dataagent_application/retrieval/sufficiency.py`。

| 原子能力 / 调用名 | 业务输入 | 业务输出 | 作用边界 |
|-|-|-|-|
| DA05.9.1 题内角色绑定  <br/>`bind_candidate_roles` | RequirementSpec（DA06.1）、SearchHit 候选、语义版本 | RoleBinding[]；候选作为度量/维度/过滤/时间/连接键的角色、绑定依据与冲突 | 只绑定不改定义；同一对象多角色或角色未定时保留候选并提示澄清。 |
| DA05.9.2 必要依赖闭包检查  <br/>`check_dependency_closure` | RoleBinding[]、关系与 Join 规则版本、租户/时间/单位要求 | ClosureReport；缺失的桥表、租户键、时间键、单位换算与可补来源 | 只报缺口不补造；关系未确认时标未知，不假定缺失项不存在。 |
| DA05.9.3 空结果与失败分类  <br/>`classify_retrieval_gaps` | 检索请求与回执、索引版本/新鲜度、权限过滤记录、预算消耗 | GapClassification[]；未命中/覆盖不足/索引过期/权限截断/预算截断及依据 | 权限截断不暴露被截对象内容；分类依据来自实际回执，不推测。 |
| DA05.9.4 检索停止判定  <br/>`decide_retrieval_stop` | ClosureReport、GapClassification[]、剩余预算、边际召回记录 | StopDecision；停止/继续/转澄清/转补数、理由与下一步建议 | 只给建议不执行下一步；预算耗尽时如实报告不充分，不当作已充分。 |
"""

SEC_DA06_8 = """#### DA06.8 认证指标委托编译（硬）

职责：已有认证定义的指标委托外部语义层（MetricFlow、Cube、dbt Semantic Layer 等）编译取数，并回传编译计划与 SQL。 边界：不改写认证定义；外部编译器不支持时显式降级到 DA06.2，并标注“非认证路径”。外部语义层经 DA01.1 连接，适配器按实现区分，不单列原子。

组输入输出：指标请求与认证定义引用 → 编译计划、SQL 与认证路径标记。拟议文件：`src/dataagent_application/planning/certified_compile.py`。

| 原子能力 / 调用名 | 业务输入 | 业务输出 | 作用边界 |
|-|-|-|-|
| DA06.8.1 认证定义绑定  <br/>`bind_certified_definitions` | RequirementSpec、已发布语义层定义引用及版本、认证状态 | CertifiedBinding；指标/维度到认证定义的绑定、版本、未覆盖项 | 只绑定已发布且认证的定义；草案或导入副本不算认证。 |
| DA06.8.2 外部语义编译调用  <br/>`compile_via_semantic_layer` | CertifiedBinding、外部语义层连接（DA01.1）、过滤/时间/粒度参数 | CompiledQuery；外部编译计划、SQL、方言、编译器版本与回执 | 只编译/解释不执行，执行仍经 DA07.1；不改写外部定义，外部报错原样返回。 |
| DA06.8.3 降级标注  <br/>`mark_noncertified_fallback` | 编译失败或不支持回执、请求范围、DA06.2 替代计划引用 | FallbackRecord；降级原因、受影响指标、非认证路径标记 | 降级结果必须带标记进入 DA11 验证与交付；不得以非认证路径冒充认证口径。 |
"""


def edit_application(d: Doc) -> None:
    d.rep("<title>DataAgent 执行应用层：模块与原子能力接口设计 v0.1</title>",
          "<title>DataAgent 执行应用层：模块与原子能力接口设计</title>"
          + layer_banner("A", "本层新增能力组 DA05.9、DA06.8，新增原子 DA05.8.4、DA05.9.1–4、DA06.2.3、DA06.8.1–3、DA10.1.4（116 → 126 项）。"))
    d.rep("保留 **DA05–DA10，6 个模块、39 个能力组、116 项原子能力**。新增的是接口与代码归属提案，没有新增能力编号。",
          "v0.2 共 **DA05–DA10，6 个模块、41 个能力组、126 项原子能力**。")
    d.in_line("| DA05 召回检索 |", "| 8 / 24 |", "| 9 / 29 |")
    d.in_line("| DA06 语义查询与计算计划 |", "| 7 / 25 |", "| 8 / 29 |")
    d.in_line("| DA10 表格、可视化与交互 |", "| 4 / 12 |", "| 4 / 13 |")
    d.rep("39 个组对应 39 个拟议能力组文件", "41 个组对应 41 个拟议能力组文件")
    d.rep("39 个能力组文件及其每个函数入口", "41 个能力组文件及其每个函数入口")
    d.rep("`generated/executed/validated/rejected` 为程序成熟度",
          "`draft/validated/rejected`（共享 `LifecycleStatus` 子集，见总文档 §2.4；是否已执行记为执行记录属性）为程序成熟度")
    d.rep("边界：复用能力目录及包元数据；只检索筛选，不安装执行，不承担目录存储或授权判定。",
          "边界：复用能力目录及包元数据；只检索筛选，不安装执行；目录存储归 DA04.4，不承担授权判定。")
    d.in_line("| DA05.8.1 组件与实现召回", "| 任务能力需求、I/O 类型", "| 任务能力需求或动作需求、I/O 类型")
    d.in_line("| DA05.8.1 组件与实现召回", "| ComponentCandidate[]；", "| ComponentCandidate[]（含 DA15.4 动作契约候选）；")
    d.after("| DA05.8.3 适用条件筛选",
            "| DA05.8.4 许可与分发约束筛选  <br/>`filter_component_licensing` | ComponentCandidate[]、包/权重/数据许可元数据、分发场景（内部/客户现场/MintHub 公开）、组织许可策略 | LicenseAssessment[]；允许/限制/禁止、许可来源与版本、需法务确认项 | 许可按具体版本判断，不从历史版本倒推；元数据缺失时标待确认，不默认允许。 |")
    d.before("### DA06 语义查询与计算计划", *SEC_DA05_9.split("\n"))
    d.rep("边界：物理实现可以是表列、业务接口或函数，不临时创造业务定义。",
          "边界：存在认证定义时先走 DA06.8；物理实现可以是表列、业务接口或函数，不临时创造业务定义。")
    d.after("| DA06.2.2 关系与约束展开",
            "| DA06.2.3 多事实对齐与倍增度量展开  <br/>`expand_multi_fact_alignment` | LogicalPlan、各事实表粒度与度量可加性、关系基数、公共维度 | 扩展 LogicalPlan；各自聚合步骤、合法公共粒度对齐、倍增风险度量的分支聚合、N:N 分摊需求 | 不直接明细互连多事实；无合法公共粒度时返回需澄清，不强行对齐。 |")
    d.before("### DA07 计算执行", *SEC_DA06_8.split("\n"))
    d.rep("边界：依赖现有运行环境和沙盒，不负责选择分析方法。",
          "边界：依赖现有运行环境和沙盒，不负责选择分析方法；无法确认隔离时失败关闭，不回退到宿主进程执行；运行镜像以 digest 固定。")
    d.in_line("| DA07.7.1 分档执行", "权限映射参考 DA03.12；授权消费 DA16/平台及 DA12 约束",
              "消费 DA16 授权决定与 DA12.1 访问决定（正式权属模型见 DA03.12）")
    d.after("| DA10.1.3 表格公式计算",
            "| DA10.1.4 既有工作簿受限编辑  <br/>`edit_existing_workbook` | 工作簿版本、允许修改的区域与对象、写入内容、计算引擎版本 | 新工作簿版本；结构 diff（单元格/公式/格式/命名区域）、重算回执、越界拒绝项 | 只改声明区域，其余区域逐字节保护；需重算时用固定引擎并回报实际状态，写回经 DA07。 |")
    d.in_line("| DA17/18 环境与交付", "版本钉定、", "环境默认版本、")
    d.rep("│   ├── retrieval/                    # DA05 8 组", "│   ├── retrieval/                    # DA05 9 组")
    d.rep("│   │   └── components.py             # DA05.8，只召回筛选",
          "│   │   ├── components.py             # DA05.8，只召回筛选\n│   │   └── sufficiency.py            # DA05.9 充分性与停止")
    d.rep("│   ├── planning/                     # DA06 7 组", "│   ├── planning/                     # DA06 8 组")
    d.rep("│   │   └── contracts.py              # DA06.7 FDE 草案",
          "│   │   ├── contracts.py              # DA06.7 FDE 草案\n│   │   └── certified_compile.py      # DA06.8 认证指标委托编译")


# ---------------------------------------------------------------------------
# 评测与治理层 G
# ---------------------------------------------------------------------------
def edit_governance(d: Doc) -> None:
    d.rep("<title>DataAgent 评测与治理层：模块与原子能力接口设计 v0.1</title>",
          "<title>DataAgent 评测与治理层：模块与原子能力接口设计</title>"
          + layer_banner("G", "本层新增 DA11.2.5、DA11.5.7、DA11.6.4、DA12.1.4、DA12.2.6、DA12.10.5，改写 DA11.4.1、DA11.4.5（67 → 73 项）。"))
    d.rep("保留 **2 个模块、20 个能力组、67 项原子能力**：DA11 为 9 组/34 项，DA12 为 11 组/33 项。",
          "v0.2 共 **2 个模块、20 个能力组、73 项原子能力**：DA11 为 9 组/37 项，DA12 为 11 组/36 项。")
    for prefix, n in [("| DA11.2 计算计划与结果验证 |", "5"), ("| DA11.5 评测判据与样本 |", "7"),
                      ("| DA11.6 持续改进度量 |", "4"), ("| DA12.1 权限与敏感信息管理 |", "4"),
                      ("| DA12.2 资产版本管理 |", "6"), ("| DA12.10 证据链与审计 〔FDE〕 |", "5")]:
        d.set_last_cell(prefix, n)
    d.rep("67 个唯一 operation 与入口，确保 JSON 目录与本文原子表一一对应", "73 个唯一 operation 与入口；目录由 `tools/build.py` 从正文生成，并校验与总文档一一对应")
    d.rep("无需为 67 个 ID", "无需为 73 个 ID")
    d.rep("生命周期状态 draft/validated/active/deprecated/invalidated 等是资产政策词表",
          "生命周期状态 draft/validated/active/deprecated/invalidated 是共享 `LifecycleStatus`（总文档 §2.4）的治理子集")
    d.rep("复用平台和源端控制，并在各使用环节生效。",
          "复用平台和源端控制，并在各使用环节生效；执行权限与“数据可进入模型上下文”分别判定（DA12.1.4）。")
    d.rep("不替代审批，审批归 DA16。", "执行前影响面评估以本组为唯一产出方，DA07.7.3 预演差异为输入；不替代审批，审批归 DA16。")
    d.after("| DA11.2.4 结果对照验证",
            "| DA11.2.5 语义陷阱反例检查 | `check_semantic_counterexamples` | 计划与结果引用、反例集版本（跨租户同 ID、复合键缺列、迟到/退款、join 膨胀、SCD 边界）、语义版本 | CounterexampleReport；逐反例通过/失败/不适用、最小失败样本 | 反例集由 DA11.5 管理；通过反例不等于业务正确，未覆盖的陷阱类型显式列出。 |")
    d.in_line("| DA11.4.1 检索回归评测", "RegressionReport；Recall/Precision/排序指标",
              "RegressionReport；必要集合全召回、误选后恢复与停止正确性（DA05.9）、Recall/Precision/排序指标")
    d.replace_line("| DA11.4.5 引擎一致性回归",
                   "| DA11.4.5 引擎一致性回归编排 | `orchestrate_engine_consistency_regression` | 固定版本化样本集、子集与权威引擎版本、规则语义映射、支持边界 | RegressionReport；引用 DA07.10.2 的 EngineConsistencyReport，一致/不一致/不支持/执行未知汇总、最小差异样本 | 比对本身由 DA07.10.2 产出，本原子只编排样本与汇总；权威引擎由业务配置确认，禁止猜测权威结果或补造子条件 trace。 |")
    d.after("| DA11.5.6 验收样本隔离",
            "| DA11.5.7 多角色越权用例构建 | `build_cross_role_cases` | 角色与权限策略版本、同题问题集、敏感字段/行规则 | 多角色评测用例；每个角色的期望可见范围与结果差异 | 使用受控测试身份，不以真实用户凭据构造；用例只存期望范围，不存敏感值。 |")
    d.after("| DA11.6.3 覆盖与交付成本度量",
            "| DA11.6.4 接入与维护成本度量 | `measure_onboarding_and_maintenance_cost` | 接入任务与变更记录、人工工时记录、首个可信答案时间点、专家介入记录 | CostMetricBundle；首个可信答案耗时、首次接入工时、每次变更修复工时、专家处理比例及分母 | 缺失记录显式报告；不以对话量或 SQL 执行率替代。 |")
    d.after("| DA12.1.3 数据脱敏",
            "| DA12.1.4 模型上下文可见性与外发控制 | `check_model_context_egress` | 拟送入模型的内容引用、模型/服务部署位置与数据处理条款、AccessDecision、脱敏策略 | EgressDecision；允许/脱敏后允许/拒绝、可见字段范围、外发目的地与回执 | 执行权限与“数据可进模型”分别判定；日志、缓存、提示词同样受限。 |")
    d.after("| DA12.2.5 沉积物回滚",
            "| DA12.2.6 规范与转换器版本登记 | `register_spec_and_converter_versions` | 外部规范名与版本、转换器版本、关联语义发布版本 | SpecVersionRecord；规范/转换器/语义版本三元关联 | 与本方语义发布版本分开登记；草案规范标记为草案，不当作稳定规范引用。 |")
    d.after("| DA12.10.4 判定依据关联",
            "| DA12.10.5 请求者与执行身份双记录 | `record_requester_and_executor` | 调用/动作回执、请求者主体、Agent 执行主体与委托引用 | IdentityPairRecord；请求者、执行者、委托链、权限交集依据 | 共享凭据场景仍逐请求者记录；缺请求者身份时标注断链，不补造。 |")


# ---------------------------------------------------------------------------
# 持续运行与 FDE 交付层 O
# ---------------------------------------------------------------------------
def edit_operations(d: Doc) -> None:
    d.rep("<title>DataAgent 持续运行与 FDE 交付：模块与原子能力接口设计 v0.1</title>",
          "<title>DataAgent 持续运行与 FDE 交付：模块与原子能力接口设计</title>"
          + layer_banner("O", "本层新增 DA14.2.4、DA16.1.4、DA18.7.4，改写 DA15.3.3、DA16.1.2、DA17.5.4，DA18.6/18.7 发布为 Mint 包（91 → 94 项）。"))
    d.rep("**范围为 DA14–DA18，5 个模块、29 个能力组、91 项原子能力**；编号及名称按 revision 1022 保留，未新增或删除。",
          "**范围为 DA14–DA18，5 个模块、29 个能力组、94 项原子能力**；编号在 revision 1022 基础上只追加、不重排。")
    d.in_line("| DA14 持续运行与监控 |", "| 8 / 20 |", "| 8 / 21 |")
    d.in_line("| DA16 委托、审批与人在环 |", "| 5 / 17 |", "| 5 / 18 |")
    d.in_line("| DA18 交付与交接 |", "| 7 / 22 |", "| 7 / 23 |")
    d.after("| DA14.2.3 结构漂移监控",
            "| DA14.2.4 抽取标签漂移监控 | `monitor_extraction_drift` | 抽取结果流、ExtractionSchemaRef、基线分布与置信度、观察窗口 | 漂移报告；标签分布/置信度/未定位率变化、告警候选 | 只记录漂移，不自动修改标签体系或重抽；修订经 DA02.12.4 与 DA12.7。 |")
    d.replace_line("| DA15.3.3 影响面预估",
                   "| DA15.3.3 影响面评估要求声明 | `declare_impact_assessment_requirements` | 契约影响声明、影响维度（对象数/金额/范围/可逆窗口）、必需的预演或只读估算依据 | ImpactAssessmentRequirement；评估维度、上界要求、所需依据与不可逆标注 | 只声明 DA12.11 须评什么；实际估算由 DA12.11 基于 DA07.7.3 预演完成，本原子不计算影响。 |")
    d.rep("动作检索由 DA05.8 复用本目录；运行时授权判定归 DA16 及执行控制。",
          "动作检索由 DA05.8 复用本目录（DA05.8.1 输入含动作契约）；组件与 Skill/Preset 目录存储归 DA04.4；运行时授权判定归 DA16 及执行控制。")
    d.rep("不复用人的凭据，不允许无限期继承。", "不复用人的凭据，不允许无限期继承；有效权限取请求者权限与 Agent 委托范围的交集。")
    d.in_line("| DA16.1.2 委托范围与时限", "不凭证据包扩大范围。",
              "不凭证据包扩大范围；有效权限取请求者权限与 Agent 委托范围的交集（DA16.1.4 传播请求者身份）。")
    d.after("| DA16.1.3 转委托限制",
            "| DA16.1.4 请求者身份传播 | `propagate_requester_identity` | 请求者主体引用、DelegationRef、下游调用描述 | 带请求者上下文的调用凭证引用；有效权限（请求者 ∩ Agent 委托范围） | 不复制人的凭据；后端无法传播请求者身份时标注为共享身份路径，并由 DA12.10.5 留痕。 |")
    d.in_line("| DA17.5.4 健康检查", "环境钉定版本", "环境默认版本（DA17.2）或任务固定版本（DA04.5）")
    d.in_line("| DA17.5.4 健康检查", "钉定差异", "与默认或固定版本的差异")
    d.rep("业务要求与能力 → Skill 草案或修订 |", "业务要求与能力 → Skill 草案或修订；发布为 Mint `kind = \"skill\"` 包 |")
    d.rep("候选能力组合 → 可试运行与交付的组件包 |", "候选能力组合 → 可试运行与交付的组件包；发布为 Mint `kind = \"preset\"` 包（总文档 §2.3 P4） |")
    d.in_line("| DA18.7.3 组合试运行与交付封装", "不重建引擎或要求复刻代码。",
              "不重建引擎或要求复刻代码；包元数据含 `license` 与 `[capabilities]` 声明。")
    d.after("| DA18.7.3 组合试运行与交付封装",
            "| DA18.7.4 组合许可清单生成 | `generate_bundle_license_manifest` | PresetBundleDraft、各依赖许可元数据（DA05.8.4）、分发场景 | LicenseManifest；依赖许可清单、冲突/限制项、待确认项 | 元数据缺失或冲突时阻止封装为可分发包，交有权主体确认。 |")


# ---------------------------------------------------------------------------
# 去除正文中的版本标签与元叙述；版本只在 frontmatter 声明
# ---------------------------------------------------------------------------
CATALOG_NOTE = "附本地接口与源码入口映射 JSON；本项目自拟目录，不是发行平台正式 manifest。\n\n"
SHARED_NOTE_OLD = ("本文件与 [共享契约](01-data-layer.md) 一起使用。下表仅列业务参数；所有调用另携带 `CallContext`，"
                   "所有输出套用 `CapabilityResult<T>`。表内对象名称是契约类型草案，不代表已存在的类或既有平台接口。")
SHARED_NOTE_NEW = "下表仅列业务参数；所有调用另携带 `CallContext`，所有输出套用 `CapabilityResult<T>`。"
CLEANUP = {
    "D": [
        ("line", "本版（v0.2，编号在 revision 1022 基础上追加）", None),
        ("sub", "# DataAgent 数据层设计草案\n", "# DataAgent 数据层设计\n", 1),
        ("sub", "# 代码目录与实现组织\n", "# 代码实现\n", 1),
        ("sub", "## 1. 推荐结构\n", "## 1. 目录结构\n", 1),
        ("line", "在 `packages/capabilities/dataagent-data/` 下建立一个可独立演进的工作区。", None),
        ("sub", "本版仅定义与这些模块的调用边界，不把它们整体并入数据层。", "本层只定义与这些模块的调用边界。", 1),
        ("sub", "| 容易重叠的对象 | 本版处理 |", "| 容易重叠的对象 | 处理 |", 1),
        ("sub", "## 5. 本版细化与保留项", "## 5. 细化与保留项", 1),
        ("line", "v0.1 先明确语义契约和目录映射；", "JSON Schema 的精确字段、类型系统、实际后端组合和生产容量在实现前收敛。"),
        ("drop_section", "## 6. 依据"),
        ("sub", SHARED_NOTE_OLD, SHARED_NOTE_NEW, 5),
        ("sub", "这里的命名与结构是 DataAgent 自拟草案，尚未对应任何平台 iface，也不假设已有组件已经实现。", "", 1),
        ("sub", "v0.1 可在同一个关系存储后端中按类型分区", "可在同一个关系存储后端中按类型分区", 1),
        ("line", "以下目录均为拟议结构，当前仅创建本设计文档。", None),
        ("sub", "## 6. 备选结构与本版取舍", "## 6. 备选结构与取舍", 1),
        ("sub", "| 方案 | 优点 | 代价 | 本版选择 |", "| 方案 | 优点 | 代价 | 选择 |", 1),
        ("sub", "| 推荐作为 v0.1 |", "| 推荐 |", 1),
        ("line", "各模块文档先给出能力组的作用与输入输出", None),
        ("sub", "- [代码目录与实现组织](01-data-layer.md)：", "- 代码实现：", 1),
    ],
    "A": [
        ("line", "本篇整合本地 v0.1 分层设计", None),
        ("sub", "本版是供整体讨论的本地设计文稿，不创建实现代码，也不向飞书回写。", "", 1),
        ("line", "本版依据 [revision 1022 XML 快照]", None),
        ("sub", "# DataAgent 执行应用层设计草案\n", "# DataAgent 执行应用层设计\n", 1),
        ("sub", "以下对象是本草案新增的业务协议，不宣称已有平台实现；实现类型拟置于 ", "以下为本层业务协议，类型置于 ", 1),
        ("sub", "另一种按每个 DA 编号拆仓库/进程会增加部署与跨模块协议负担，本版不采用；", "按 DA 编号拆仓库/进程会增加部署与跨模块协议负担，不采用；", 1),
        ("sub", "留到实现前收敛，不影响本版逐项判断输入、输出、边界与代码归属。", "在实现前收敛。", 1),
        ("line", "文档核对要求：", None),
        ("sub", "本文件只提出源码布局，没有创建下述实现文件。", "", 1),
    ],
    "G": [
        ("line", "本篇整合本地 v0.1 分层设计", None),
        ("line", "本版以 [revision 1022 本地完整快照]", None),
        ("sub", "# DataAgent 评测与治理层设计草案\n", "# DataAgent 评测与治理层设计\n", 1),
        ("line", "本版已按基线原子条目核对", "正式 schema、具体策略引擎、生产审计存储、统计置信方法、部署容量与实际发行规范在实现前收敛。"),
        ("sub", "本文件只提议代码组织，当前不创建以下代码、安装包或运行配置。", "", 1),
        ("line", "完整逐项映射见 [atomic-capability-catalog.json]", None),
        ("sub", "拟议 Python 工作区、20 个组文件、共享对象、端口/适配器和构建粒度见 [code-layout.md](03-governance-layer.md)。", "", 1),
        ("sub", "，治理扩展类型见 [README](03-governance-layer.md)。", "。", 1),
    ],
    "O": [
        ("line", "本篇整合本地 v0.1 分层设计", None),
        ("sub", "本草案将持续任务", "本层将持续任务", 1),
        ("sub", "；编号在 revision 1022 基础上只追加、不重排。", "。", 1),
        ("line", "本地文稿包括本文件、", None),
        ("sub", "源文件路径相对拟议工作区 `packages/capabilities/dataagent-operations/`，均尚未创建。", "源文件路径相对工作区 `packages/capabilities/dataagent-operations/`。", 1),
        ("line", "- 权威范围：", None),
        ("line", "- 目录覆盖：DA14 20", "- 目录覆盖：DA14 21、DA15 14、DA16 18、DA17 18、DA18 23，共 94；能力组分别 8/4/5/5/7，共 29。"),
        ("sub", "本文件仅定义拟议代码归属，**未创建以下工作区或实现**。", "", 1),
        ("sub", "这里未验证任何既有 GUI/TUI 或发行平台接口，接入需独立适配测试。", "接入既有 GUI/TUI 或发行平台接口需独立适配测试。", 1),
        ("sub", "；详见[目录树、端口和依赖规则](04-operations-fde-layer.md)。当前仅创建设计文稿，没有实现或注册运行工具。", "。", 1),
        ("sub", "再按 [README 场景切片](04-operations-fde-layer.md)形成可运行闭环", "再按场景切片形成可运行闭环", 1),
    ],
}
FRONT_COMMON = {"version": "v0.2", "date": "2026-11-03"}
VERSION_LABEL = re.compile(r"\bv0\.\d\b|revision 1022|\br10[0-9]{2}\b|本版")


COMMON = [
    ("sub", "\n[返回 Pluggable DataAgent 总规划与分层索引](00-pluggable-dataagent.md)\n",
     "\n> [返回 Pluggable DataAgent 总规划与分层索引](00-pluggable-dataagent.md)\n", None),
    ("sub", "[DataAgent 分层设计总导航](00-pluggable-dataagent.md)", "[Pluggable DataAgent 总规划与分层索引](00-pluggable-dataagent.md)", None),
]


def cleanup(d: Doc) -> None:
    for op in COMMON if d.key in "DAGO" else []:
        if op[1] in d.text:
            d.text = d.text.replace(op[1], op[2])
    for op in CLEANUP.get(d.key, []):
        if op[0] == "sub":
            d.rep(op[1], op[2], op[3])
        elif op[0] == "line":
            if op[2] is None:
                lines, i = d._line_index(op[1])
                del lines[i]
                d.text = "\n".join(lines)
            else:
                d.replace_line(op[1], op[2])
        elif op[0] == "drop_section":
            lines, i = d._line_index(op[1])
            level = len(op[1]) - len(op[1].lstrip("#"))
            j = i + 1
            while j < len(lines) and not (lines[j].startswith("#") and len(lines[j]) - len(lines[j].lstrip("#")) <= level):
                j += 1
            del lines[i:j]
            d.text = "\n".join(lines)
    if d.key in "DAGO":
        d.text = d.text.split("\n# 机器可读能力目录")[0].rstrip("\n") + "\n"
        d.text = re.sub(r"\[[^\]]*\]\(" + re.escape(CATALOG_REL) + r"\)", f"[总 Catalog]({CATALOG_REL})", d.text)
    self_name = FILES[d.key][1]
    d.text = re.sub(r"\[([^\]]+)\]\(" + re.escape(self_name) + r"(?:#[^)]*)?\)", r"\1", d.text)
    d.text = re.sub(r"\n{3,}", "\n\n", d.text)


def frontmatter(key: str) -> str:
    fm = dict(FRONT_COMMON)
    fm["baseline"] = "飞书总规划 r1045" if key == "M" else "总规划 r1045 编号"
    if key in CHANGES:
        fm["changes"] = CHANGES[key]
    return "---\n" + "".join(f"{k}: {v}\n" for k, v in fm.items()) + "---\n\n"


# ---------------------------------------------------------------------------
# 目录生成与校验
# ---------------------------------------------------------------------------
ROW_PLAIN = re.compile(r"^\| (DA\d+\.\d+\.\d+) ([^|]+?)\s*\| `([a-z0-9_]+)` \|")
ROW_BR = re.compile(r"^\| (DA\d+\.\d+\.\d+) (.+?)\s+<br/>`([a-z0-9_]+)` \|")
GROUP_HEAD = re.compile(r"^#{3,4} (DA\d+\.\d+) ")
FILE_MARK = re.compile(r"(?:实现位置|拟议文件)：`([^`]+)`")
O_GROUP_ROW = re.compile(r"^\| (DA\d+\.\d+) [^|]+\|.*\| `(src/[^`]+)` \|$")


def parse_main(text: str):
    modules, groups, atoms = {}, {}, {}
    cur_mod, mod_fde = None, False
    for line in text.split("\n"):
        m = re.match(r"^### (DA\d+)｜(.+?)( 〔FDE〕)?$", line)
        if m:
            cur_mod, mod_fde = m.group(1), bool(m.group(3))
            modules[cur_mod] = {"name": m.group(2).strip(), "fde": mod_fde}
            continue
        m = re.match(r"^\| (DA\d+\.\d+) \| ([^|]+?) \| ([^|]+?) \|", line)
        if m and cur_mod:
            name = m.group(2)
            groups[m.group(1)] = {"module": cur_mod, "name": name.replace(" 〔FDE〕", "").strip(),
                                  "form": m.group(3).strip(), "fde": mod_fde or "〔FDE〕" in name}
            continue
        m = re.match(r"^- `(DA\d+\.\d+\.\d+)` (.+?) — (.+)$", line)
        if m:
            atoms[m.group(1)] = {"name": m.group(2).strip(), "summary": m.group(3).strip()}
    return modules, groups, atoms


def parse_layer(key: str, text: str):
    rows, files, cur = {}, {}, None
    for line in text.split("\n"):
        g = GROUP_HEAD.match(line)
        if g:
            cur = g.group(1)
        f = FILE_MARK.search(line)
        if f and cur and cur not in files:
            files[cur] = f.group(1)
        if key == "O":
            og = O_GROUP_ROW.match(line)
            if og:
                files[og.group(1)] = og.group(2)
        m = ROW_BR.match(line) or ROW_PLAIN.match(line)
        if m:
            aid = m.group(1)
            if aid in rows:
                sys.exit(f"[{key}] 原子行重复：{aid}")
            rows[aid] = m.group(3)
    return rows, files


S1_GROUPS = {"DA05.8", "DA07.7", "DA07.8", "DA14.6", "DA15.1", "DA15.2", "DA15.3", "DA15.4", "DA16.2", "DA18.6", "DA18.7"}
S2_GROUPS = {"DA11.7", "DA11.9", "DA14.2", "DA14.8", "DA17.2", "DA17.5", "DA18.1", "DA18.2", "DA18.3", "DA18.4", "DA18.5"}
FAMILY_ROWS = {"骨干": "骨干", "判定族增量": "判定族", "计算族增量": "计算族"}


def s0_families() -> dict[str, str]:
    """从 05-contracts.md §3.1 的原子表读取 S0 原子及其闭环族。"""
    text = (OUT / "05-contracts.md").read_text(encoding="utf-8")
    sec = text.split("### 3.1")[1].split("### 3.2")[0]
    fam: dict[str, str] = {}
    for line in sec.split("\n"):
        m = re.match(r"^\| \*\*(骨干|判定族增量|计算族增量)\*\* \| (.+?) \| \d+ \|$", line)
        if not m:
            continue
        for mm, g, a, g2, a2 in re.findall(r"(?:DA)?(\d{2})\.(\d+)\.(\d+)(?:–(\d+)\.(\d+))?", m.group(2)):
            hi = int(a2) if a2 else int(a)
            for i in range(int(a), hi + 1):
                fam[f"DA{mm}.{g}.{i}"] = FAMILY_ROWS[m.group(1)]
    if len(fam) != 51:
        sys.exit(f"05 §3.1 解析出 {len(fam)} 项 S0 原子，应为 51")
    return fam


def build_catalog(docs: dict[str, Doc]) -> dict:
    modules, groups, atoms = parse_main(docs["M"].text)
    problems: list[str] = []
    if (len(modules), len(groups), len(atoms)) != EXPECTED_MAIN:
        problems.append(f"总文档计数 {len(modules)}/{len(groups)}/{len(atoms)} ≠ {EXPECTED_MAIN}")
    layer_of, entries, seen = {}, [], set()
    for key in "DAGO":
        rows, files = parse_layer(key, docs[key].text)
        gset = {a.rsplit(".", 1)[0] for a in rows}
        if (len(gset), len(rows)) != EXPECTED[key]:
            problems.append(f"[{key}] 计数 {len(gset)}/{len(rows)} ≠ {EXPECTED[key]}")
        for aid, op in rows.items():
            layer_of[aid] = key
            gid = aid.rsplit(".", 1)[0]
            if aid not in atoms:
                problems.append(f"[{key}] {aid} 不在总文档")
                continue
            if gid not in files:
                problems.append(f"[{key}] {gid} 缺源码文件")
            g = groups.get(gid, {})
            entries.append({
                "id": aid, "name": atoms[aid]["name"], "summary": atoms[aid]["summary"],
                "group": gid, "group_name": g.get("name"), "module": g.get("module"),
                "module_name": modules.get(g.get("module"), {}).get("name"),
                "form": g.get("form"), "fde": g.get("fde"), "layer": FILES[key][1],
                "operation": op, "source_file": files.get(gid),
            })
            seen.add(aid)
    missing = sorted(set(atoms) - seen)
    if missing:
        problems.append(f"总文档有、分层文档缺：{missing}")
    dup_ops = [op for op, n in Counter(e["operation"] for e in entries).items() if n > 1]
    if dup_ops:
        problems.append(f"operation 重名：{dup_ops}")
    if problems:
        sys.exit("校验失败：\n- " + "\n- ".join(problems))
    fam = s0_families()
    missing_s0 = sorted(set(fam) - {e["id"] for e in entries})
    if missing_s0:
        sys.exit(f"S0 原子不在目录中：{missing_s0}")
    for e in entries:
        e["slice"] = "S0" if e["id"] in fam else "S1" if e["group"] in S1_GROUPS else "S2" if e["group"] in S2_GROUPS else "按需"
        e["s0_family"] = fam.get(e["id"])
    entries.sort(key=lambda e: [int(x) for x in e["id"][2:].split(".")])
    fde_groups = sorted({e["group"] for e in entries if e["fde"]})
    return {
        "version": "0.2-local",
        "base": "feishu Pluggable DataAgent r1045; layer docs D r14 / A r8 / G r7 / O r8",
        "generated_by": "tools/build.py",
        "counts": {"modules": len(modules), "groups": len(groups), "atoms": len(entries),
                   "hard_groups": sum(1 for g in groups.values() if "硬" in g["form"]),
                   "fde_groups": len(fde_groups),
                   "atoms_by_layer": {FILES[k][1]: EXPECTED[k][1] for k in "DAGO"}},
        "atoms": entries,
    }


def main() -> None:
    docs = load()
    edit_main(docs["M"])
    edit_data(docs["D"])
    edit_application(docs["A"])
    edit_governance(docs["G"])
    edit_operations(docs["O"])
    for d in docs.values():
        d.text = localize(d.text)
        cleanup(d)
    catalog = build_catalog(docs)

    residue = []
    for k, d in docs.items():
        for i, line in enumerate(d.text.split("\n"), 1):
            if "feishu.cn" in line or "<callout" in line or "<figure" in line:
                residue.append(f"{FILES[k][1]}:{i} 残留飞书标记")
            if re.search(r"\]\(" + re.escape(FILES[k][1]) + r"[)#]", line):
                residue.append(f"{FILES[k][1]}:{i} 指向本文档的链接")
            if VERSION_LABEL.search(line):
                residue.append(f"{FILES[k][1]}:{i} 正文含版本标签：{line.strip()[:60]}")
            if re.search(r"钉定|钉住", line):
                residue.append(f"{FILES[k][1]}:{i} 残留“钉定/钉住”：{line.strip()[:60]}")
    if residue:
        sys.exit("残留检查失败：\n- " + "\n- ".join(residue))

    for k, d in docs.items():
        (OUT / FILES[k][1]).write_text(frontmatter(k) + d.text.rstrip("\n") + "\n", encoding="utf-8")
    (OUT / "catalog").mkdir(exist_ok=True)
    (OUT / CATALOG_REL).write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    c = catalog["counts"]
    print(f"OK 模块 {c['modules']} / 能力组 {c['groups']} / 原子 {c['atoms']} / 硬 {c['hard_groups']} / FDE {c['fde_groups']}")
    print("各层原子：", c["atoms_by_layer"])


if __name__ == "__main__":
    main()
