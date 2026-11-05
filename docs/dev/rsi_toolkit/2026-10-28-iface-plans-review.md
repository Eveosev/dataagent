---
title: RSI IFace 模块化两方案评审
date: 2026-10-28
status: proposed
type: review
---

# RSI IFace 模块化两方案评审

> **2026-11-02 更新**：本文基线中的 `packages/kernel-iface` 已冻结为 0.1.0 历史快照，勿作对比基线；
> iface 契约现以 `packages/agent-kernel/kernel/iface/src` 为权威源，可读副本为
> `packages/agent-kernel/packages/iface-*`（0.1.2）。对比前先同步 agent-kernel，见 AgentOS 根 `README.md`。

## 评审对象与基线

**评审对象**

- **方案 A**：[RSI Toolkit 按 IFace 模块化设计](../../superpowers/specs/2026-10-28-rsi-iface-modularization-design.md)。内容是内部架构、事务所有权和契约语义。
- **方案 B**：[iface 拆分与 MintHub 发布方案](2026-10-28-iface-modularization-and-minthub.md)。内容是分发形态、Mint 平台约束和发布顺序。配套文档有 [Mint 平台笔记](2026-10-28-mint-platform-notes.md)、[取舍说明](2026-10-28-iface-plan-rationale.md) 和 [契约包生成器](mint-iface/README.md)。

**核验基线**

- RSI v0.2.0（`44235f1`）
- `packages/kernel-iface` v0.1.0 快照
- 本机 `mint 0.1.11`
- MintHub 2026-10-28 公开索引

本轮全部为只读核验，证据见 [附录 D](iface-review/D-verification-evidence.md)。

## 1. 结论

1. **两份方案是分工关系，不是竞争关系。** B 的 13 个模块直接沿用了 A。A 回答“怎么拆、边界和事务归谁”，B 回答“拆完以什么形态发到 MintHub”。
2. **以 A 为架构权威，B 修正后改作分发设计。** A 对 IFace 的处理是正确的：只做语义映射，不宣称兼容。它列出的 6 个缺口，经源码核验全部属实。B 的平台事实大多属实，但内部有多处自相矛盾，配套的生成器也违反了 B 自己定下的 D4 规则。
3. **两份方案都漏掉了源码层的硬阻塞**，其中最严重的是评测器指纹绑定了 Python 模块路径。因此，在任何拆包动作之前，先增加一个 **M0-pre 源码解耦** 阶段。
4. **合并后的方案**是：内部保留 15 个模块边界，首批对外只发 5 个包。用户端不执行 pip。通用能力契约先实现，同时留档，供上游沟通使用。

## 2. 已确认的决策（2026-10-28）

| 决策 | 内容 | 详见 |
| --- | --- | --- |
| scope 与许可证 | 不在本次范围内，文中用 `<scope>` 占位 | — |
| 首批包数量 | 首批合并为 5 个：`rsi-iface-data`、`rsi-foundation`、`rsi-model-client`、`rsi-evaluation`、`rsi-execution` | [附录 A](iface-review/A-first-batch-packages.md) A.2–A.3 |
| Mint 形态 | 统一用 `kind = "bundle"` | 附录 A A.3 |
| IFace 权威来源 | 以线上 `agentcpm/iface-*@0.1.0` 的 bundle 制品为准，固定 digest；本地快照只作参考。**2026-10-29 修正**：hub 制品已落后 master，改以 kernel repo 的 release tag + commit 为准 | [附录 B](iface-review/B-capability-contracts.md) B.1；[附录 F](iface-review/F-upstream-delta-2026-10-29.md) F.7 |
| 声明实现 | 用 `provides.interfaces`：契约包写自身，实现包写自己实现的已冻结契约；消费和提议关系另记在 `iface.toml` | 附录 A A.4 |
| 契约治理 | 分层治理：Kernel 机制契约只消费；通用能力契约先自有、后晋升；领域数据契约自有，但遵循同一套规则 | 附录 B B.1 |
| 安装方式 | 首批包只依赖标准库，bundle 带源码目录，由启动器按依赖闭包加载，不跑 pip；应用层的编译型依赖由 CI 按平台预构建 | 附录 A A.5 |
| 通用能力契约 | 先实现 C1–C7，草案留档，用于和开发者沟通 | 附录 B B.2–B.4 |

## 3. 用户目标与 IFace 实况的张力

用户的目标是“IFace 是权威入口，每个组件包都是 IFace 的实现实例”。核验发现的实况如下：

- kernel-iface 的 9 个契约都是**进程内 Rust trait**，没有 Python binding，也没有 wire schema。
- 唯一有跨进程路径的契约是 loop，但本机运行时还没有实现它。
- 现有 IFace 中没有一个能被 RSI 模块直接实现：
  - `iface-store` 是会话事件日志，不是内容存储或账本。
  - `iface-loop.step` 不是学习或实验工作流。
  - 没有 memory 契约。
- 可以成立的只有**消费关系**：model、env、policy。
- Mint 对“声明实现”不做任何校验：`provides.interfaces` 只是原样透传，也没有 `requires.interfaces`。

据此，可行的落地方式是：

- 把 RSI 领域契约和通用能力契约，做成与 `agentcpm/iface-*` 同形的契约包。
- 实现包用 `provides.interfaces` 声明自己实现了哪些契约，再由我们自己的 conformance 测试保证声明真实。

这样既以 IFace 体系为权威入口，又不冒充 Kernel 兼容。

## 4. 方案 A 评判

**成立**

- IFace 方法映射表准确。“语义映射不等于可调用实现”和“Rust trait 不是 Python ABI”这两条原则正确。
- 6 个缺口全部属实：
  - ingest 跨多个事务；
  - release 的审批弱于旧 Controller；
  - release_set 不驱动召回；
  - `execution_id` 没有统一校验；
  - IFace 文档存在漂移；
  - Selector 失败时回退。
- 事务所有权表、迁移期需保留的行为清单、source-ref 固定完整 SHA，这几项都是高质量的约束。
- 把 cpmrt 后置，不阻塞当前用 `mint run` 的路径。

**问题**

- **分发层留白过多**：没有决定 Mint kind，也没有给出“声明实现”的清单格式。
- **IFace 漂移只列了一部分**，也没有利用线上先例：官方 iface 包是 bundle 形态，native 包可以通过启动器拉起解释器。
- **门禁链太长**：M5 之前没有任何能在 Mint 上验证的产物，分发层的假设得不到早期反馈。
- **13 个模块各自发包，和代码规模不匹配**：13 个模块合计只占代码量的 13%，最小的模块只有 44 到 61 行。
- 有若干行号和计数偏差，见附录 D D.6。

## 5. 方案 B 评判

**成立**

- Mint 平台硬约束大多属实：
  - 没有 `kind=iface`；
  - 契约用 `pull` 拉取；
  - 没有 `inspect --abilities`；
  - bundle 只装载 `skills/`；
  - dry-run 不验证发布权限；
  - 没有 `requires.interfaces`。
- 方向正确的约束：
  - “拆契约，不拆进程”；
  - “数据契约不冒充调用契约”；
  - “控制工程与运行时工程永不合并”；
  - M1 的“同一调用方跑两个实现”硬门。

**问题**

1. **生成器违反 D4**：
   - 写出的是裸名 `rsi-host`，不是 `rsi-host.data`；
   - 包 README 教的是 `mint add`，与“契约用 pull”矛盾；
   - `repository` 字段没有 commit 和 digest。
2. **`rsi.host/v1` 的定位冲突**：A 判定它是要淘汰的旧边界，B 却把它作为已冻结契约放进首批发布。
3. **阶段和计数错误**：
   - 删掉了宿主适配阶段；
   - 说“7 个状态包”，实际只有 6 个；
   - mcp 入口依赖后一批才发布的状态包。
4. **平台判断过严或过时**：
   - “Python 不能用 plugin”说得太绝对，native 加启动器已有先例；
   - mcp 早已不是“路线图”，线上已有 4 个 mcp 包。
5. **28 个包的分发成本没有算清**：wheel 之间的依赖、venv 和卸载方式都没有回答。
6. **命名混乱**：把方案 A 称为“并行方案 B”。

## 6. 两份方案共同遗漏的阻塞

按严重度排列，详细证据见附录 D D.4。

1. 评测器和 verifier 的指纹绑定了模块路径，搬动代码会让已有的 qualification 全部失效。
2. `rsi/__init__` 和 `control/__init__` 会预先导入整个包，只导入一个纯函数也要加载 35 个模块。
3. rsi 和 toolkit 两个包之间存在循环依赖。
4. 机器清单里声明的依赖与代码不符。
5. 执行端口、schema loader、trace 归一、backup/restore 这几项职责，落在 13 个模块之外。
6. 存储层不足以支撑工作单元（UoW）：迁移只有一个文件、`tx` 不支持嵌套、存在直接写 SQL 的代码。
7. 模块规模失衡，各自发包的治理成本远高于复用带来的收益。

## 7. 合并后方案概要

- **文档权威**：A 是架构权威；分发设计、契约草案和阶段门禁以本文的附录为准。
- **两个轴**：
  - 内部模块共 15 个，即 A 的 13 个，加上 `contracts-runtime` 和 `execution-port`；
  - 发布包按“是否有第二个消费者”和“是否共享事务”合并，首批 5 个，后续 5 个。
- **阶段**：M0-pre 源码解耦 → M0 契约基线 → M1 首批 5 包与分发探针 → M2 执行组件 → M3 状态模块 → M4 宿主适配 → M5 应用组装 → M6 cpmrt（可选）。
- **上游沟通**：7 个通用能力契约附带具体问题清单。最优先的是 `runtime-executor/v1`，它决定 M4 和 M6 的路径。沟通不阻塞 M0 到 M3。

## 附录索引

| 附录 | 内容 |
| --- | --- |
| [A 首批包设计与分发](iface-review/A-first-batch-packages.md) | 内部模块与发布包的映射和合并理由；首批 5 包的内容、来源、IFace 关系、依赖；`provides.interfaces` 与 `iface.toml` 声明约定；不用 pip 的分发方式与 M1 分发探针 |
| [B 通用能力契约草案](iface-review/B-capability-contracts.md) | 契约分层与治理；C1 blob、C2 index、C3 evaluation、C4 evidence、C5 asset、C6 workspace-staging、C7 runtime-executor 各自的作用、设计要点、伪签名；与开发者沟通的问题清单 |
| [F 上游 master 复核（2026-10-29）](iface-review/F-upstream-delta-2026-10-29.md) | 拉取 kernel master 后对 C1–C7 的逐条判定；`runtime-executor` / `execution_id` 的检索证据与两条落地路线；修订后的沟通清单；需修订的文档与代码项 |
| [B 修订版（2026-10-29，已发布飞书）](iface-review/B-revised-2026-10-29.md) | 合并 B 的架构与 F 的结论后的对外版本：一页判定表、治理与权威来源修正、C1–C7 逐条（含上游现状与拟议签名）、不做清单、修订版沟通清单、复核依据；飞书 <https://modelbest.feishu.cn/docx/GNDkdtF2goAAopx8Nxtc2ylGnKb> |
| [C 阶段、门禁与文档修订](iface-review/C-phases-and-gates.md) | M0-pre 到 M6 的工作与门禁；首批测试迁移归属；相关文档的修订待办 |
| [D 核验证据](iface-review/D-verification-evidence.md) | kernel-iface、Mint CLI 和 MintHub 的实况；方案中平台说法的核对；源码阻塞与已确认缺口的 file:line 证据；模块规模 |
| [E 执行分工与协作约定](iface-review/E-execution-overview.md) | 本轮范围、分支、文件所有权、共享的包布局与清单格式、同步点 S0–S3 |
| [E1 Worker A 执行方案](iface-review/E1-worker-a.md) | 源码与契约：文档与清单修订、M0-pre 解耦（懒加载、断开循环、指纹 v2）、C1–C7 草案、首批 4 个能力包的源码迁移 |
| [E2 Worker B 执行方案](iface-review/E2-worker-b.md) | 分发与平台：文档修订、IFace 权威基线、清单校验器、`rsi-iface-data`、bundle 构建器、免 pip 启动器、M1 分发探针、上游问题包 |
