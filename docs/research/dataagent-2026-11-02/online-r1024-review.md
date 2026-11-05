---
date: 2026-11-02
subject: 飞书总规划 r1024；分层接口设计四份（数据层 r11、执行应用层 r8、评测与治理层 r7、持续运行与 FDE 交付 r8）
compared: 本地 spec/00–04；dataagent-landscape-2026-10-31；agent-kernel@f0fa521
followup: ../dataagent-2026-11-03/
---

# 线上 Pluggable DataAgent 评估

---

## 0. 结论

契约质量高，落地路径弱。

- **优势**：434 项原子能力均有 operation 名、输入输出、边界、出错情形和代码归属；返回结构与版本表达统一；“执行结果未知时不重放”贯穿全部能力；评测与知识治理严于所调研竞品。
- **问题**：
  1. 平台对接退步且未标为待决：线上无任何内核或 Mint 原语。
  2. 共享契约无独立归属；约 100 个类型只有名字。
  3. 同一概念多处归属；改名后有旧说法残留。
  4. 与调研脱钩：认证指标编译、SCD 与复合键、身份传播与模型外发、分发许可、检索充分性均未成为能力。
  5. 范围过宽，无全局最小切片。

修订 R1–R8 后：模块 18，能力组 141（+2），原子能力 458（+24），FDE 能力组 43（DA18.6/18.7 去掉标记）。

---

## 1. 范围与方法

### 1.1 材料

| 简称 | 材料 | 版本 | 位置 |
|-|-|-|-|
| M | 主文档 Pluggable DataAgent | 飞书 r1024 | `sources/feishu-r1024/M-main-r1024.md` |
| D | 数据层 v0.1（DA01–DA04、DA13） | 飞书 r11 | `sources/feishu-r1024/D-data-layer-r11.md` |
| A | 执行应用层 v0.1（DA05–DA10） | 飞书 r8 | `sources/feishu-r1024/A-application-layer-r8.md` |
| G | 评测与治理层 v0.1（DA11–DA12） | 飞书 r7 | `sources/feishu-r1024/G-governance-layer-r7.md` |
| O | 持续运行与 FDE 交付 v0.1（DA14–DA18） | 飞书 r8 | `sources/feishu-r1024/O-operations-fde-layer-r8.md` |
| L00–L04 | 本地实现设计 | 本地 | `spec/00-data-layer.md` … `spec/04-decisions.md` |
| R | 外部调研 | 2026-10-31 | `../dataagent-landscape-2026-10-31/`、`../dataagent-retrieval-2026-10-31/` |
| K | AgentOS 内核与 Mint 包 | `agent-kernel@f0fa521` | `packages/agent-kernel/kernel/iface/src/`、`mint/packages/` |

`M:220` 等指快照文件行号。分层文档标注基于 r1022，与 r1024 的能力 ID 和名称一致。

### 1.2 方法

- 计数：脚本核对主文档与分层文档的 ID、名称、组归属，一一对应；原子 160 + 116 + 67 + 91 = 434，能力组 51 + 39 + 20 + 29 = 139。
- 比对：线上设计对本地 spec、线上设计对调研 01–05 及检索专题，两路逐条比对；结论均回原文抽查，更正见附录 C。
- 内核：按 AGENTS.md 快进 13 个提交至 `f0fa521`；`sync-iface-packages.sh --check` 报告漂移 diff=11，以 `kernel/iface/src` 为准，未改分发包。

### 1.3 限制

- 仓库无 DataAgent 运行时代码；“实现”指本地 spec。
- 分层文档附带的 JSON 目录未随导出保存。
- 调研不含制度抽取、合规审核类竞品。

---

## 2. 相对本地 spec 的变化

### 2.1 能力目录

本地 spec 基于 r953，419 项；线上基于 r1022，434 项。净增 15 项，无删除：

| 新增原子 | 用途 |
|-|-|
| DA05.8.1–3 | 组件与 Skill/Preset 检索 |
| DA06.4.4–6 | 方法替换、组件重选、子任务重组 |
| DA08.6.4 | 验证程序生成 |
| DA11.5.6 | 验收样本隔离 |
| DA11.6.3 | 覆盖与交付成本度量 |
| DA18.6.1–3 | 业务 Skill 构建 |
| DA18.7.1–3 | Preset/Bundle 组装 |

主要改名：

| 原子 | 原名 | 新名 |
|-|-|-|
| DA01.2.3 | MCP 工具能力探测 | MCP 返回结构读取（探测移至 DA01.9） |
| DA03.11.2–4 | 参数 schema / 前后置条件 / 影响面与可逆性 | 业务参数 / 业务前后状态 / 业务影响 |
| DA03.15.x | 可机器化 / 需人工 / 不适用 | 自动判断能力评估 / 补证与人工需求 / 范围标注 |
| DA04.5.2 | 子任务上下文派发 | 子任务上下文引用维护 |
| DA12.10.4 | 表达式级归因 | 判定依据关联 |
| DA17 | 现场上下文 | 业务环境配置与协作上下文 |

定义变化：原子能力为“最小复用单元，可组合其他能力”（M:55）；硬 / 软 / 定为职责与约束标记（M:59-65）；依赖关系不设固定主链（M:835-852）。

### 2.2 通用约定

| 项 | 本地 spec | 线上 |
|-|-|-|
| 调用形式 | 各原子各自签名 | `invoke(operation, input, CallContext) -> CapabilityResult<T>`（D:37） |
| 返回与错误 | `Err{kind, retryable, detail}`，6 类（L00 §0.3） | `CapabilityResult{status, issues[], execution_ref, provenance, completeness, continuation}`，5 种状态 + 错误码 |
| 引用类型 | SourceRef / ConnRef / DataRef / DocRef / Anchor / RecordSet | AssetRef / ResourceRef / ConnectionRef / CredentialBindingRef / SchemaRef / SourceAnchor / SnapshotRef + TableRef / DataBatchRef / DocumentUnitRef 等 |
| 版本 | 单一版本号 | revision、源版本、digest、生效时间分开 |
| 权限分类 | 工具命名即权限（L00 §0.2） | 运行时判档；“含写入的入口不得靠名称归 A0”（O:145） |
| 打包 | 一模块一 bundle、`mint.toml`、`skills/*/SKILL.md`（L00 §0.4） | 一层一个 Python 工作区；自拟 `component-specs/*.yaml`、`presets/*.yaml` |
| 存储 | PostgreSQL 起步（L04 D7） | SQLite + 本地受控文件起步，端口可替换（D:1173-1185） |

### 2.3 本地决策 D1–D12 的去向

| 决策 | 本地建议 | 线上 | 标为待决 |
|-|-|-|-|
| D1 DA04 存储 | 先自建、冻结形状，再下沉内核 | 自建 SQLite `TraceRepository`，无下沉计划 | 否 |
| D2 档位与审批映射 | A0/A1/A2 → `EffectLevel` + `ReviewPosition`；证据包引用放入 `ApprovalRequest.summary` | 自拟 `ApprovalRequestRef`（O:42） | 否 |
| D3 装配清单 | `mint.toml [assembly]` → `AssemblyIntent.payload` | 自拟 YAML + DA18.7 `PresetBundleDraft` | 否 |
| D4 发布粒度 | 一模块一 bundle | 一层一工作区，发布粒度延后 | 部分 |
| D5 schema 时机 | 先代码后回填 | 采纳：类型生成 `contracts/generated/` | 已决 |
| D6 写通道强制 | Rust 网关，Python 侧无写凭据 | Python `action_gateway.py`（A:629），端口约定 | 否 |
| D7 存储 | PostgreSQL 起步 | SQLite 起步 | 已决 |
| D8 访问控制 | 内核 guard 单闸门，DA12.1 为策略源 | DA12.1 自出 `AccessDecision`，多点复检（G:42、G:188） | 否 |
| D9 引擎与部署分工 | DA07.10 校验，DA17.5 部署 | 采纳（M:420、M:771） | 已决 |
| D10 首片只出报告 | 是 | 采纳（O:376） | 已决 |
| D11 拆五个宽能力组 | 下一版拆 | 只拆 DA06.4 | 否 |
| D12 编队机制归 OS | 用内核委派、租约、阻塞项 | 未用内核原语 | 否 |

---

## 3. 优势

| 方面 | 内容 | 位置 |
|-|-|-|
| 接口契约 | 每项有 operation、源文件、业务参数、输出类型与失败情形；`CapabilityResult` 表达部分完成与截断；四种版本分开 | D 共享契约节；R 00 §3.3、§5.4 |
| 结构修正 | DA01.8 来源下沉为适配器；DA04.5 为任务状态唯一权威；DA03.11 与 DA15.2 分开；DA07.4 复用 DA07.7；放弃工具命名即权限；原子可组合 | M:120-123、M:290、M:220、M:417、O:145、M:55 |
| 方法论 | 非线性依赖、多入口检索、计划重组；端到端验收允许中间方法不同；硬 / 软 / 定区分 | M:835-852、DA05.1、DA06.4、DA11.5.5、DA18.6；retrieval 00 §5、§7.2 |
| 评测与治理 | 三类样本隔离与暴露记录；六类指标并报；经验候选 → 验证 → 晋升 → 淘汰，沉积可回滚 | DA11.5.6、DA11.6.3、DA04.6、DA12.2.5；R 01 §4.3、§5 |
| 副作用与时态 | 幂等、预演、后置校验、未知只对账；密钥不出域；业务生效时间与记录时间分开；重现条件 | DA07.7/07.8、DA01.10、DA03.8、DA12.6 |
| 分析方法 | 预测不用未来真实值；求解器区分最优 / 可行 / 未知；贡献不当因果 | DA09.1.2、DA09.3.1、DA08.2.2、DA08.5.2；R 03 §5 |
| Skill/Preset 链 | 检索、构建、组装、修订提炼成链 | DA05.8、DA18.6、DA18.7、DA04.2.4 |

---

## 4. 问题

### 4.1 平台对接

五份快照中 `StoreContract`、`EffectLevel`、`ExtensionContract`、`AssemblyIntent`、`mint.toml` 出现 0 次；各层只声明“不做 Mint/iface 兼容结论”（D:11）。

| 内核原语（`f0fa521`） | 位置 | 线上状况 |
|-|-|-|
| `EffectLevel{ReadOnly, Advance, SideEffect}`；Advance 只改变本会话状态 | `kernel/iface/src/session/effect.rs:36` | 未映射 A0/A1/A2 |
| `ReviewPosition{Input, Plan, ToolParams, FinalResult}` | `policy/review.rs:13` | 未映射审批插入点 |
| `ApprovalRequest{session, call, summary, timeout_ms}` | `policy/mod.rs:28` | 证据包需以引用承载 |
| `DelegationGrant{grant_id, scope, depth_remaining, expires_at_ms, parent_grant}` | `policy/delegation.rs:56` | DA16.1 未引用 |
| `AssemblyIntent{session, act, payload}`，payload 为声明式装配数据 | `extension.rs:16` | DA18.7 另起 YAML |
| `StoreContract::append/read(session, from, limit)`，会话内游标 | `store.rs:119` | DA04.1 自建 `TraceRepository` |
| `Lease`、`BlockedOnItem` | `lease.rs:62`、`handoff.rs:136` | DA14.6/14.7 未引用 |
| 内核 guard（单一门） | `kernel/core/src/guard/` | 与 DA12.1 多点复检的关系未定义 |

Mint 已有包格式：`kind = "skill"`（`mint.toml` + `SKILL.md`，`mint/packages/skill-code-review/`）；`kind = "preset"`（`[dependencies]` + `preset.toml`，`mint/packages/preset-default/`）；`mint.toml` 含 `license`、`[capabilities]`、`[capabilities.reason]`（`mint/packages/tool-fs/mint.toml`）。

### 4.2 共享契约与类型

- 归属：数据层 `src/dataagent_data/contracts/` 为“共享类型的实现权威源”（D:1016）；应用层、治理层待“提取到共同契约包”（A:587、A:718、G:354、G:485）；FDE 层所引“总体跨层约定”在主文档中不存在（O:29）。
- 完整度：原子表点名的输出类型约 224 个，约 100 个无字段（如 `TierAssessment`、`ImpactEstimate`、`HealthReport`）；schema 推迟到“实现前收敛”（D:68、G:350、O:398）。
- 衔接：DA01.4.4 输出 `DocumentRef 或 DataBatchRef`，DA02.3.3 只接受 `DataBatchRef`（D:156、D:300）。

### 4.3 归属重叠与改名残留

| # | 问题 | 位置 |
|-|-|-|
| 1 | DA17.2 改为默认版本，仍有“钉定 / 钉住” | M:768；残留 M:20、M:778-781、O:277 |
| 2 | DA03.14 组边界与原子相反 | M:223、M:270 |
| 3 | 影响面评估 3–4 个产出方 | DA03.11.4（M:261）、DA15.3.3（M:723）、DA12.11.1（M:639）、DA07.7.3（M:441） |
| 4 | 引擎一致性两份报告 | DA07.10.2、DA11.4.5（A:369、G:125） |
| 5 | 鉴权归属三种说法 | M:221、G:303、A:331 |
| 6 | 审批策略 5 处定义 | DA03.12.3、DA06.7.2、DA12.11.3、DA15.1.2、DA16.2.1 |
| 7 | 生命周期 3 套词表 | D:949、G:46、A:51 |
| 8 | 动作检索缺口；组件目录存储无归属 | M:710、A:158-160、M:334 |
| 9 | DA18 整体标 FDE，DA18.6/18.7 为通用能力 | M:71、M:31、A:575 |
| 10 | 四个宽能力组未拆 | DA08.5、DA12.3、DA14.7、DA18.2 |

### 4.4 调研缺口

五份快照中，所调研产品（Genie、Spotter、Snowflake、Hex、Julius）与概念（SCD、复合键、OpenLineage、Ossie）出现 0 次；“交集”“请求者”出现 0 次。

| # | 调研结论 | 线上现状 | 风险 |
|-|-|-|-|
| a | 认证 KPI 绑定已发布定义，由受控编译器取数（R 00 §5.4；02 §8.3；01 §4.2） | DA06.2/06.3 全为“软”；DA03.9.1 导入为草案 | 高频 KPI 口径漂移 |
| b | SCD、复合键、多事实对齐、倍增度量（R 02 §5.2、§6.1） | 仅泛化的 DA02.5.3、DA03.3.3 | SQL 成功而结果错 |
| c | 身份传播与模型外发分开授权（R 01 §4.5、05 §4、03 §4.1） | DA01.10 只管密钥；DA16.1 无权限交集，无外发控制 | 越权取数；敏感数据进模型 |
| d | 分发许可按版本区分（R 02 §5.1、03 §8–9） | `ComponentCandidate` 无 license 字段（A:158） | 发布即分发 |
| e | 检索充分性与停止（retrieval 00 §3.2–3.4） | 无对应原子；DA11.4.1 只看 TopK | 漏召回无法归因 |
| f | 工作簿日期系统、公式缓存、未改区域保护（R 03 §5.1） | DA10.1 只生成新工作簿 | Excel 静默出错 |
| g | 抽取标签体系版本与漂移（R 04 §4） | DA02.12 无版本与漂移 | 抽取口径漂移 |
| h | 首个可信答案耗时、接入与变更工时（R 00 §7） | DA11.6.3 只计任务内人工 | 维护成本不可见 |
| i | 语义导出损失报告；规范版本漂移（R 00 §5.3；02 §3、§7） | 无导出；规范版本未单独记录 | 迁移验收无据 |
| j | 无沙盒时失败关闭（R 03 §4.3，PandasAI #1801） | DA07.2 无此约束 | 回退执行任意代码 |

### 4.5 范围与切片

- 434 项覆盖问数、分析工作台、建模、监控、预测优化、流程勘查、部署、跨租户沉淀、SLA，宽于任一被调研产品；FDE 部分 45 个能力组、约 145 项原子。调研建议限定业务域，先走通文件与企业数据两个入口（R 01 §1、00 §10）。
- 各层有层内切片（D:1250-1262、G:310-340、O:376），无全局最小切片；本地 spec 的数据层闭环（L00 §5.2）未保留。首片“DA18.6/7 + DA15 A0/A1”（O:376）牵连 DA05.8、DA08.6、DA11、DA12。

---

## 5. 修订

编号只追加、不重排。各项已在本地优化版落地：

| 项 | 修订 | 落地位置（`../dataagent-2026-11-03/`） |
|-|-|-|
| R1 | 平台对接待决 P1–P7（写通道、访问判定与 guard、档位与审批映射、发布格式、轨迹存储、编队、存储后端） | `00` §2.3 |
| R2 | 跨层契约：`dataagent-contracts` 第 0 层、`LifecycleStatus`、类型完整度门槛；DA01.4.4 / DA02.3.3 衔接 | `00` §2.4、`05`、`01` |
| R3 | 唯一归属：影响面、引擎一致性、数据访问、动作授权、审批策略、生命周期、组件目录、版本固定 | `00` §4.2；各层边界 |
| R4 | 文字一致性 11 处 | `00`–`04` |
| R5 | 新增 DA05.9、DA06.8 及 24 项原子；改写 DA03.9.1、DA06.2、DA07.2、DA11.4.1、DA12.1、DA16.1、DA16.1.2 | `00` §三；`01`–`04` |
| R6 | 全局切片：S0 通用只读证据闭环（判定族 / 计算族）→ S1 Mint 包与回写 → S2 持续运行与移交 | `00` §4.1；`05` §3.1 |
| R7 | DA18.6/18.7 发布为 Mint `kind = "skill"` / `"preset"` 包 | `00` DA18、§2.3 P4 |
| R8 | 能力与调研章节对照 | `00` 附录 A |

推进顺序：R3、R4 → 定 P2、P5 → R2 契约包与 S0 类型字段 → R5 中 S0 相关部分 → R6 → R7（S1 前）→ R8 持续维护。

---

## 附录 A：数量核对

| 项 | 主文档 | 分层文档 |
|-|-|-|
| 原子能力 | 434 | 160 + 116 + 67 + 91 |
| 能力组 | 139 | 51 + 39 + 20 + 29 |
| FDE 能力组 | 45（24 散落 + 21 位于 DA15–DA18） | — |

## 附录 B：内核与 Mint 核对

- `agent-kernel`：`git fetch` 时落后 13 个提交，`pull --ff-only` 至 `f0fa521e8bc45d6d96935ddeed28968c7e6ac30b`。
- `sync-iface-packages.sh --check`：`diff=11 missing=0 extra=0 uncovered=12`；未执行 `--write`。
- 读取文件：`session/effect.rs`、`policy/mod.rs`、`policy/review.rs`、`policy/delegation.rs`、`extension.rs`、`store.rs`、`lease.rs`、`handoff.rs`；`mint/packages/tool-fs/mint.toml`、`mint/packages/skill-code-review/`、`mint/packages/preset-default/`。

## 附录 C：评估中更正的说法

- 数据层切片 B 含 DA03（D:1250-1262）；准确表述为“无全局统一的最小切片”。
- O:29 的“共享输入输出契约”指向数据层文档（存在）；缺失的是主文档中的“总体跨层约定”。
- 原文禁止的是导入其他层的内部实现，不是共享类型（A:718、G:485）；准确表述为“共享契约无独立归属”。
