---
title: 附录 F：上游 IFace master 复核与 C1–C7 判定
date: 2026-10-29
status: review
parent: ../2026-10-28-iface-plans-review.md
scope: 只复核"上游现在有什么、够不够"，不改 C1–C7 的需求定义
---

# 附录 F：上游 IFace master 复核与 C1–C7 判定

本附录是[附录 B](B-capability-contracts.md) 的**事实层复核**。B 的需求（C1–C7 要解决什么问题）继续有效；
B 里关于"IFace 现在有什么""上游缺什么"的判断，以本文为准。

## F.1 复核口径

| 项 | 值 |
| --- | --- |
| 上游仓库 | `packages/agent-kernel`（`agent-kernel.git`），`master` |
| 复核 commit | `d950766`（2026-10-28 22:59 +0800），`git pull --ff-only` 后工作区干净 |
| iface 源码 | `kernel/iface/src`（22 个 trait）；分发副本 `packages/iface-*`（10 个包） |
| 运行时 | `cpmrt 0.1.14`（hub 上 `mint/core` 的最新版），本机 `~/.mint/cores/0.1.14-std/bin/cpmrt` |
| 线上契约包 | MintHub `agentcpm/iface-*@0.1.0`，`updated_at = 2026-10-27T07:37Z`（= 15:37 +0800），此后未再发布 |

三点必须先说清楚，否则后面会误判：

1. **`packages/kernel-iface/` 在本机不是 git 仓库**，它只是 10 个包的 v0.1.0 快照（复核时为 27 个 `.rs` / 2853 行；
   2026-10-29 已按本 commit 同步为 44 个 `.rs` / 6292 行 / 22 个 trait，见 F.7 第 2 条）。
   真正的 iface 源码在 `packages/agent-kernel` 的 `kernel/iface/src`。本文拉取的是后者。
2. **上游契约面比 B 写的时候大得多**：同步前的快照是 10 个 trait / 约 68 个方法，master 是 22 个 trait / 91 个方法
   （`kernel/iface/api-baseline.txt` 计数）。新增的 12 个 trait 基本都落在本轮关心的范围里。
3. **hub 上的 0.1.0 制品落后于 master**。`iface-*` 全部在 2026-10-27 15:37 +0800 发布且再未更新；
   此后 master 上又有多轮提交动了 iface（D93 模型流式、D96 模型会话、分发副本对齐、API 门禁收紧）。
   所以 B.1 说的"线上 `agentcpm/iface-*@0.1.0` 是权威来源"**今天会把我们带偏**，见 F.7。

## F.2 结论速览

| 契约 | 判定 | 上游现在有什么 | 一句话缺口 |
| --- | --- | --- | --- |
| C1 `blob/v1` | **不满足** | 无内容寻址存储。最近的是打包层的 sha256/dirhash 与 hub 的 blob digest | 运行时没有"按 digest 存取任意内容"的契约 |
| C2 `index/v1` | **部分满足** | `mint-api` 的 `MemoryProvider`（store/recall/consolidate）+ WIT `memory.wit` + cpmrt 内置 `file-jsonl` | 没有不可变快照/`bank_hash`，库是可改写的"活记忆" |
| C3 `evaluation/v1` | **不满足** | 无任何评测/打分契约 | 从零开始，但 `Unknown` 语义有先例可引 |
| C4 `evidence/v1` | **部分满足** | `ModelUsage`（input/output/total）+ `ModelResponse.model` + `Secret<T>` 打码 | 没有 seal/verify/redact，没有观测方指纹、没有 cost/cached |
| C5 `asset/v1` | **不满足** | `ExtensionContract` 的装配状态机；`mint.lock` 的包账本 | 没有"版本 + 当前激活集合 + 期望版本 + 一次性授权" |
| C6 `workspace-staging/v1` | **不满足** | `FsBackend` 4 方法 + 4 个粗能力位；`ToolStaging` 证明窄契约可行 | 没有 mkdir / 原子替换 / 按名拒绝 / 细粒度能力声明 |
| C7 `runtime-executor/v1` | **部分满足（语义有，接口无）** | `RequestState`(含 Unknown)、`operation.*` 作业视图、`idempotency_key`、五类终止、ACP | 没有 task 级、调用方给 id 的 submit/status/result |

**逐条结论**
- 七个契约里，**没有一条被上游完整满足**；C2、C4 是"接口像但语义差"，C7 是"语义有但入口不对"。
- C3、C5、C6 的需求成立，但 C6 的**形态**要改：不是新契约，是 `iface-env` 的增补（见 F.4-C6）。
- 你提到的"`runtime-executor` 及 `execution_id` 已有 cpmrt 支持"——**在 master 与 0.1.14 里都不存在**，
  证据摊在 F.5；最接近的两处是 `LoopContract` 的 `ExecutionIdentity` 与 `ModelSession` 的
  `client_message_id`，作用域都不是"一次任务执行"。

## F.3 上游这轮新增了什么（只列与 C1–C7 相关的）

| 新增能力 | 位置 | 相关 | 对我们的意义 |
| --- | --- | --- | --- |
| `ExecutionIdentity{run_id, operation_id, idempotency_key?, deadline_ms?}` | `kernel/iface/src/types/loop_payload.rs:183` | C7 | "每次推进可归因、可幂等"的形状，可直接借 |
| `StepOutcome::Unknown{reconcile}` | `kernel/iface/src/loop_.rs:40` | C7 | "未知 ≠ 失败、禁止自动重放"的上游先例 |
| `InterruptOutcome{Accepted, AlreadyTerminal, TooLate, Unsupported}` | `types/loop_payload.rs:355` | C7 | 取消四态；有 TooLate，**没有 Unknown** |
| `HandoffKernel`（session.create/get/watch/close/deliver + operation.get/list/cancel） | `kernel/iface/src/handoff.rs:273` | C7/C5 | 会话与作业的最小端口，注释还停留在 V1"未实现"（已漂移） |
| L-C 方法表：v2b-1 固定 40 条 + v2b-2 24 条 | `kernel/host/src/transport/method_table.rs:168` | C7 | `session.deliver` 强制幂等键、`operation.get` 统一作业视图 |
| `ModelSession` / `InputEnvelope.client_message_id` | `kernel/iface/src/model_session/input.rs:52` | C7 | **调用方生成 id** 的先例（幂等作用域 = 主体+会话+方法） |
| `ContractMeta` + `ContractDescriptor{name, version, capabilities}` + `require_capabilities` | `kernel/iface/src/version.rs:51` | C5/C6 | 能力协商/拒绝的标准做法，别自己再造 struct |
| `ToolStaging{contains, register_stub, remove_stub}` | `kernel/iface/src/tool.rs:59` | C6 | "按能力切窄契约 + 失败回滚不留半装"的现成范式 |
| `LeaseStore`（acquire/renew/release/check/generation） | `kernel/iface/src/lease.rs` | C5 | 租约、代次、单次持有的机制已有 |
| `TraceSink` / `AuditSink` | `kernel/iface/src/trace.rs`、`audit.rs` | C4 | 留痕与审计是契约，但都不是"可校验证据" |
| `ModelStreamContract` / `ModelCompletion.usage` / `ModelUsage` | `kernel/iface/src/model_stream.rs:25` | C4 | usage 字段的唯一真源 |
| `MemoryProvider` + WIT `memory.wit` | `mint/crates/mint-api/src/lib.rs:483`、`mint/crates/mint-api/wit/memory.wit` | C2 | **B 说"还在建设中"已经过时**，接口已落地 |

## F.4 逐条判定

### C1 `blob/v1`：不满足，维持自有

**上游现状**：没有任何"按 digest 存内容"的契约。相关但不解决的东西有三处：
- `StoreContract.verify_checkpoint` 返回 `(cursor, digest)`——只校验会话日志；
- `mint-pack` 的 `sha256` / `h1: dirhash` / `cksum`——打包与安装完整性，不是运行时 API；
- hub 用 digest 存单元 blob——平台内部实现。

**判定**：B 的判断仍然成立，`iface-store` 是事件日志，不能拿来存内容。

**复核后要补的一条**：digest 的**命名空间**要跟上游区分开。mint 用 `sha256:<hex>` 与 `h1:<base64>` 两种写法，
B 草案里用 `sha256:`。建议我们只写 `sha256:`，明确不占 `h1:`，并在契约里写一句
"本 digest 不参与 mint 的包完整性校验"。

**沟通动作**：C1 的优先级可以降到最低，不改问题内容。

### C2 `index/v1`：部分满足，改策略为"先谈扩展，不新造"

**上游现状**（B 写的时候没有，现在有了）：
- `mint-api` 的 `MemoryProvider`：`store` / `recall` / `consolidate`（+ 默认实现），
  `MemoryQuery{text, scopes, k, kinds, exclude_session}`、`MemoryHit{score, item}`、
  `MemoryCaps{index, curate}`（`mint/crates/mint-api/src/lib.rs:431-505`）；
- 同名 WIT 接口 `memory.wit`（store/recall/consolidate/forget），说明它被设计成**可替换 provider**；
- cpmrt 内置 `file-jsonl` 实现（`mint/crates/mint-core/src/memory.rs:312`），
  配置 `[memory] index = ["file-jsonl"]`、`scopes`、`recall_k`、`recall_tokens`、`consolidate`；
- 挂在 `hook.before_model`（召回）/ `hook.turn_end`（写入）/ `hook.session_end`（整理）。

**差距**（不是"有没有"，是"保不保真"）：
1. **没有不可变快照**：召回读的是当前文件，`consolidate` 会在后台合并/删除条目 → 同一问题两次召回可以不同。
   这直接违背 C2 的"同快照同查询结果一致"。
2. **没有 `bank_hash` / `index_hash` / 每条命中的 revision hash**，评测无法锚定。
3. **没有 `budget{max_chars}`**：cpmrt 用 `recall_tokens * 3` 估算字符预算；
4. **没有 lexical|vector 的显式 `kind`**：当前是关键词 + CJK 分词；
5. 语义是"记忆库"（条目有 `valid_to`/`superseded_by`，可被整理掉），不是"冻结集合上的检索索引"。

**判定**：**部分满足**。接口形状高度重合，但 C2 存在的理由——**可复现**——恰恰是它没有的。

**动作（改的是策略，不是需求）**：
- 不要提"请给我一个新的 index 契约"，改提："`MemoryProvider` 能否加一个只读快照维度？
  即 `recall` 之前先 `snapshot(bank_rev) -> handle`，命中带条目 revision。"
- 如果上游只要"活记忆"、不要快照，我们保留自有 `index/v1`，但在 `iface.toml` 里把
  `consumes`（memory.provider）与 `proposes`（index/v1）分开写清楚——两者不是同一层。
- 硬约束写进我们自己的实现：**评测路径禁止直连可整理的 memory provider**，必须走冻结快照，
  否则 baseline/candidate 的对比会被后台 consolidate 污染。

### C3 `evaluation/v1`：完全不满足，从零开始

**上游现状**：`grep -i "evaluat|score|benchmark|qualif"` 在 `kernel/iface/src` 零命中。
最接近的是 `PolicyContract.review` 的 `ReviewVerdict{Approve, Reject, NeedsHuman, Revise}`
（审核判决，不是分数）和 `AuditSink`（审计，不是评测）。

**判定**：**不满足**，B 的判断成立。

**复核后的两点增量**：
- `unscored ≠ 0` 这条纪律可以直接引上游先例：`StepOutcome::Unknown`、
  `SessionState::Unknown`、`BackendStopStatus::Unknown` 都是"显式未知、不许伪装成功"，
  我们要求 `unscored` 有同样的地位，不是特例。
- 指纹用"显式稳定 ID + 版本 + 能力标签"而不是模块路径，与上游
  `ContractDescriptor{name, version, capabilities}` 是同一思路；建议我们的 fingerprint 也带
  `capabilities: []`，而不是一个自由拼接的字符串。

**动作**：问题不变，优先级不变（中）。

### C4 `evidence/v1`：部分满足（usage 有，证据没有），字段要向上游改

**上游现状**：
- `ModelUsage{input_tokens: Option<u64>, output_tokens: Option<u64>, total_tokens: Option<u64>}`
  挂在 `ModelCompletion.usage`（`kernel/iface/src/model_stream.rs:25`）。
  **没有 `cached_tokens`，没有 `cost`**，且三个字段都是 Option（"不可得就不填"）。
- `ModelResponse.model` 明确写"服务端可能改写；实现不暴露时 `None`，不得伪造"
  （`kernel/iface/src/model.rs`）——这正是 C4"供应商未披露的模型变化标为无法检测"的先例。
- 脱敏：只有 `Secret<T>` 在 `Debug`/`Display` 打码（`mint/crates/mint-protocol/src/secret.rs`），
  **没有策略化 redact + 报告**。

**判定**：**部分满足**。观测值/模型身份有承载，证据封装与脱敏没有。

**动作（要改我们的 schema）**：
- `usage` 从 `{input_tokens, output_tokens, cached_tokens, cost?}` 改成
  **与上游同构**的 `{input_tokens, output_tokens, total_tokens, cached_tokens?, cost?}`，
  前三个字段名与可空性照抄上游；`cached_tokens` / `cost` 标为 additive 扩展并注明"上游暂无"。
- `cost` 建议**不要**进 v1 核心：价格表是外部事实、随时变，进来就得版本化价格，收益小于成本。
- `ModelResponse.model` 的"不得伪造"语义直接搬进 C4：`observed_model: Option<String>`，
  `None` 就是"无法检测"，不许填请求里的模型名。

### C5 `asset/v1`：不满足，但可借两阶段形状

**上游现状**：
- `ExtensionContract`：`on_assembly_intent(intent) -> AssemblyHandle` → `assembly_status` →
  `AssemblyState{Pending, Ready, Failed, RolledBack}` → `deactivate`。
  这是"一次装配"的生命周期，**没有版本、没有激活集合、没有期望当前版本**。
- `mint.lock`（`mint/crates/mint-pack/src/lib.rs:626`）：`LockPackage{name, version, source, integrity(h1:), cksum, deps, trust}`。
  它是**包管理器**的账本，不是 iface 契约，而且只记"装了什么"，不记"哪套在生效"。
- `LeaseStore` 有租约/代次，但语义是"谁持有"，不是"哪套资产在激活"。
- `PolicyContract.request_approval(ApprovalRequest{session, call, summary, timeout_ms})`：
  有超时，**没有一次性 nonce / 消费语义**。

**判定**：**不满足**，B 的判断成立。

**复核后的增量**：
- 两阶段（intent → handle → status）在上游已有先例，我们的 `prepare_release` / `commit`
  可以对着它讲，不必解释"为什么要分两步"；`RolledBack` 这个状态名也现成。
- C5 的"`authorization_ref` 只能使用一次、有 TTL"与上游 `request_approval` 的 `timeout_ms`
  不是一回事（前者是消费一次，后者是等多久），沟通时要把这两个概念分开问，否则会被答"我们已经有 timeout 了"。
- `expected_current` 的比较与写入必须在同一事务——上游 `session.lease_*` 有代次围栏（epoch fence），
  可以直接类比："我们需要的正是资产层的 epoch fence"。

### C6 `workspace-staging/v1`：不满足，且形态要改（并入 `iface-env`）

**上游现状**：
- `FsBackend` 仍是 4 个方法：`read_file` / `write_file` / `list_dir` / `stat`
  （`kernel/iface/src/env/fs_backend.rs:28`）。**没有 mkdir、没有 rename/原子替换、没有按名拒绝。**
- `EnvironmentCapabilities` 只有 4 个粗开关：`fs` / `exec` / `signals` / `streams`。
- 词法围栏**已经在契约层**：`PathUri` 拒绝 `..`、绝对路径以外的形态、控制字符、反斜杠，
  并做 `/` 折叠（`kernel/iface/src/env/path_uri.rs`）。
- 实现层有 root 围栏：`LocalFsBackend` 用 `canonicalize` 逐级回溯祖先做 symlink 逃逸检查
  （`kernel/runtime/src/env/local_fs.rs:98`），`write_file` 会顺手建父目录——**但不是原子替换**。

**判定**：**不满足**。B 说"最适合作为 `iface-env` 的增补"是对的，复核后更确信，并且有三条新理由：

1. 上游已经证明"窄能力契约"是可接受的：`ToolStaging` 只有 3 个同步方法，注释里写清了
   "只有装配器需要它，不该污染主契约"。我们要的东西同样窄，可以照这个风格提。
2. 上游有通用的能力协商：`ContractDescriptor.capabilities` + `require_capabilities`（fail-closed）。
   所以 B 里的 `StagingCaps` **不要自定义 struct**，改成能力标签
   （如 `env.fs.mkdir`、`env.fs.atomic-replace`、`env.fs.nofollow`），直接进 `capabilities`。
   这样"能力不足就拒绝"是上游现成的语义，不用另造。
3. `PathUri` 已经承担了词法围栏，C6 的"路径围栏"应表述为"**词法围栏已有，缺的是 fs 层的
   symlink nofollow 与原子替换的契约化**"，否则会被答"我们已经有 PathUri 了"。

**动作**：把 C6 从"新契约"改成"`iface-env` 的三方法增补 + 三条能力标签"，
收益是沟通成本减半，且不再需要解释"为什么不是 env 的一部分"。

### C7 `runtime-executor/v1`：语义有，接口无（重点，见 F.5）

**上游现状**：见 F.5 的三条执行面。一句话：**没有任何一个入口接受"调用方生成的执行 id"**，
也没有 `submit / status / result` 三段式；但 `RequestState`（含 `Unknown`）、
`operation.get` 统一作业视图、`idempotency_key` 强制、五类终止这些语义件都在。

**判定**：**部分满足**。B 的“DTO 与语义”设计可以保留，但**不能再说“cpmrt 已支持”**。

## F.5 `execution_id` 专章：把证据摊开

### F.5.1 我查了什么

| 查询 | 结果 |
| --- | --- |
| `grep -r "runtime-executor\|RuntimeExecutor" packages/agent-kernel` | 0 命中（master 工作区；`git log --all -S` 跨全部分支亦无） |
| `git log --all -S"RuntimeExecutor"` / `-S"execution_id"`（agent-kernel） | 仅命中 `ExecutionIdentity` 相关提交，无执行器契约 |
| `grep -r "execution_id\|execution-id\|executionId" mint/` | 0 命中 |
| `cpmrt 0.1.14 run --help` | 只有 `--cwd/--flavor/--approve/--json/--plain/--max-steps/--session/--input` |
| hub `mint/core` 版本列表 | 最新 `0.1.14`（`0.1.15` 不存在） |
| `grep -r "execution_id" apps/plugins/rsi-toolkit` | 只命中我们自己的草案（`contracts/proposed/runtime-executor.v1.*`，在 `iface/v2-m0-m1` 分支）与设计文档 |

**结论**：`execution_id` 是我们草案里的名字，上游没有对应物；`cpmrt` 也不接受这个参数。

### F.5.2 上游实际可用的三条执行面

| 面 | 入口 | 有调用方 id？ | 有 submit/status/result 分离？ | 取消应答 | 事件/结果 | 稳定性 |
| --- | --- | --- | --- | --- | --- | --- |
| headless `run` | `cpmrt run [--json] [--session]` | ✗（session id 由运行时生成） | ✗（一次跑完，同步等） | ✗（只能杀进程） | `--json` 每行一个 `EventRecord{v,seq,at,session,event,meta}`；退出码 0–8 | 未写进 ABI 文档 |
| ACP over stdio | `cpmrt acp`：`session/new` → `session/prompt` → `session/update` → `session/cancel` | ✗（session/new 服务端分配 id） | 半步（prompt 是长请求，update 是流） | 只有 `null` 或 `-32602 会话不存在`，**没有 already-terminal / unknown** | `PromptResult{stopReason}` + 通知流 | 协议版本 `protocolVersion`，`_meta` 可扩展 |
| Kernel L-C | `agentcpm-kernel`（**不是 cpmrt**）：`session.*` / `task.*` / `operation.*` / `interrupt.*` / `duplex` / `model.*` | 部分（`session.deliver` 必填 `idempotency_key`；`model` 会话用 `client_message_id`） | ✓（`operation.get` 统一作业视图） | 部分（`operation.cancel` **只支持 kind="tool"**，其余 `-32085`） | `RequestState` 八态（含 Unknown）+ 事件流 | L-C `abi_version` 1..=2，CHANGELOG 标 "additive / testing" |

补充两条容易误读的事实：

- `HandoffKernel` 的注释说 `operation.*` "V1 未实现 → -32085"（`kernel/iface/src/handoff.rs`），
  但 host 侧 `operation.get` 已经实现（投影 task/loop/env/model 四类作业，interrupt 返回 `unsupported`）、`operation.cancel` 只实现了 `kind="tool"`。
  **注释漂移**，以 host 代码为准。
- cpmrt 的外部 loop 协议（`loop/next`，`mint/crates/mint-core/src/loop_host.rs`）只传
  `turn`/`step`/`prompt`/`context`，**没有任何执行身份**。所以"M6 走 loop 路线"也需要先补这一层。

### F.5.3 判定与两条路线

**判定：不满足。** 但比 B 当时的判断要乐观——**缺的不是语义，是入口**：
`RequestState`、`Unknown` 不重放、`operation` 作业视图、`idempotency_key` 强制，上游全都有现成做法；
只差"task 级、调用方给 id"这一层壳。

**路线 A（现在就能做，不阻塞 M4）**：RSI 侧自带执行账本
- 我们生成 `execution_id`，自己持久化 `execution_id → (cpmrt 进程, session_id, 起止时间)`；
- 调 `cpmrt run --json` 或 ACP，把 `execution_id` 写进我们自己的记录与事件落盘；
- 取消 = 向子进程发终止信号 + 状态标 `unknown`（因为我们无法确认它停没停）；
- 代价：幂等只能做到"我们自己的表"级别，跨进程崩溃要靠对账（正好对应 `Unknown` 的语义）。
- 这条路线**不需要 cpmrt 改任何东西**，但必须老老实实把 `unknown` 当一等状态，不能假装成功。

**路线 B（M6，向上游提）**：把三个缺口变成三个具体诉求
1. `--execution-id <id>`（或 ACP `_meta.execution_id`），并在事件与结果里原样回显；
2. 取消返回三态：`cancelled` / `already-terminal` / `unknown`（对应上游 `InterruptOutcome`
   加一个 `Unknown` 变体，而不是我们另造一套）；
3. `run --json` 的 `EventRecord.v` 写进 ABI 文档，并给出 `v` 的兼容规则（现在有版本字段，但没承诺）。

**给 cpmrt 开发者的一段话（可直接贴）**：

> 我们需要"批处理式执行一个任务"：调用方生成 `execution_id`，用它做幂等键；
> 重复提交返回同一次执行，结果里回显同一个 id；提交后失联且无法确认终态时必须报 `unknown`，
> 不许猜；取消必须明确回答"已取消 / 本来就结束了 / 无法确认"。
> 现在 `cpmrt run` 一次跑完、没有 id 也没有取消应答；ACP 的 `session/cancel` 只有成功/会话不存在两态。
> 想确认：`run` 能否加 `--execution-id`（或 ACP `_meta.execution_id`）并回显？
> 取消能否升级成三态？`run --json` 的 `EventRecord` 会不会进 ABI 文档？

## F.6 修订后的沟通清单（替代 B.4 的 1–7 条）

| 优先级 | 对象 | 问题（修订版） | 依据的事实 | 期望的答案形态 |
| --- | --- | --- | --- | --- |
| 1 | cpmrt | 见 F.5.3 路线 B 的三条 | `run --help`、ACP `session/cancel`、`EventRecord.v` | 明确"做/不做/哪个版本" |
| 2 | iface-env | 能否加 `mkdir` / `atomic-replace` / `nofollow` 三个窄方法，能力用 `capabilities` 标签声明？远端环境谁保证原子性？ | `FsBackend` 4 方法、`EnvironmentCapabilities` 4 布尔、`ToolStaging` 先例 | 增补 or 拒绝 + 理由 |
| 3 | iface-policy | `request_approval` 能否支持**一次性消费 + TTL**（不是 `timeout_ms`）？ | `ApprovalRequest{timeout_ms}` 只表达等待时长 | 在 policy 侧补 or 由我们自带 receipt |
| 4 | mint memory | `MemoryProvider` 能否加"冻结快照 + 条目 revision"？还是我们必须自带 `index/v1`？ | `MemoryQuery`/`MemoryHit` 无快照、`consolidate` 会改库 | 扩展 or 明确分工 |
| 5 | iface / mint | 评测分数只支持标量还是多维？kernel 有没有内置评测计划？ | `kernel/iface` 零命中 eval | 路线图口径 |
| 6 | iface-model | `ModelUsage` 会不会加 `cached_tokens`？字段名以谁为准？脱敏规则谁定？ | 现为 input/output/total 三个 Option | 字段表 + owner |
| 7 | iface / cpmrt | 制品存储有没有规划？digest 用 `sha256:` 还是 `h1:`？大对象要不要流式？ | 无 blob 契约；mint 用两种 digest | 命名空间划分 |

保留 B.4 末尾的三条 Mint 平台确认项（`provides.interfaces` 语义、`mint add` 依赖展开、bundle 按平台分发），
复核未发现它们有变化。

## F.7 对我们自己文档与代码的修订项

1. **B.1 的"权威来源"条款要改**。现在是"线上 `agentcpm/iface-*@0.1.0` 固定 digest 为准"，
   但 hub 制品自 2026-10-27T15:37+0800 未更新，落后 master 至少 D93/D96 两个批次。
   建议改成："以 kernel repo 的 **release tag + commit** 为准，hub 制品必须由该 tag 重新生成，
   记录 `commit + digest` 两个坐标；两者不一致时以 commit 为准并提 issue。"
2. **`packages/kernel-iface/` 快照已同步（2026-10-29）**。10 个包逐字节对齐 `packages/agent-kernel/packages/iface-*`
   （22 个 trait / 44 个 `.rs` / 6292 行，`kind` 随之从 `iface` 改为上游的 `bundle`，并补上 `skills/<包名>/SKILL.md`）；
   同时修了 `publish-iface-online.sh` 的 `PKG_ROOT`/`MINT_BIN` 路径（原来指向不存在的目录，会全量 MISS）。
   注意：**本地已新于线上**，hub 上的 `0.1.0` 仍是同步前内容。
3. **C2 的实现位置要重估**：如果决定复用 `MemoryProvider`，`recall-selection` 必须显式锁快照；
   如果不能，就保持自有 `index/v1` 并在 `iface.toml` 里把 `consumes` / `proposes` 分开。
4. **C4 的 `usage` schema 改字段**（加 `total_tokens`，`cached_tokens`/`cost` 标扩展，`cost` 建议不进 v1）。
5. **C6 的 `StagingCaps` 改成能力标签**，走 `ContractDescriptor.capabilities`，
   不再自定义能力 struct。
6. **C7 的 DTO 保留，实现先走路线 A**；`Unknown` 必须是一等状态（与上游一致），
   不许用"退出码 0"冒充"执行成功"。

## F.8 待确认

- **`runtime-executor` 的来源**：我在 kernel 全仓、所有分支、hub、cpmrt 0.1.14 二进制里都没找到。
  如果你是在别的地方看到的（另一个仓库、另一份文档、或某人的口头同步），告诉我在哪，
  我再去核一遍——只要它不在这个 commit 上，C7 的判定就不变。
- **hub 重发策略**：同一个 `0.1.0` 重发会变 digest，等于换制品不换版本号。
  是"直接重发 0.1.0"还是"升 0.1.1"？这决定我们 M0 契约基线钉哪个。
- **cpmrt 0.1.15 计划**：如果 exec 协议在计划里，路线 B 的时间点就能对上门禁；否则 M6 必须自带账本。
