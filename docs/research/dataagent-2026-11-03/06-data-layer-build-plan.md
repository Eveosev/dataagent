---
version: v0.3
date: 2026-11-04
status: 已实现；Round 17 已执行 tester r17 B1/B2/B3 修复；契约 117 / 数据层 560 测试通过（契约计数含 07/08 并发工作流新增）
kernel: agent-kernel@f0fa521
changes: 实施记录、评审与修复计划移至 06-data-layer-build/
---

# 数据层能力建设方案

## 1. 范围

| 项 | 内容 |
|-|-|
| 契约包 | `dataagent-contracts` core，37 个类型（35 个具体 + 2 个泛型；`ExecutableSpec`/`EngineBinding` 由 07 §4.2 迁入 core）（[05-contracts.md](05-contracts.md) §3.3–3.4） |
| 数据层原子 | S0 中属于数据层的全部原子，共 32 项：骨干 9、判定族 14、计算族 9（以总 Catalog 的 `s0_family` 为准） |
| 运行路径 | 一个 Python 核心库，加两个入口：MCP 入口供 Mint 与内核/CSP 使用；CLI 入口供人/脚本直接调用 |
| LLM 调用 | 在 Agent 侧完成；工具负责确定性部分 |
| 不含 | 修改 agent-kernel 仓库；发布到 MintHub；S0 中不属于数据层的原子（DA06/07/10/11/12） |

S0 数据层原子：

| 族 | 原子 | 数量 |
|-|-|-|
| 骨干 | DA01.4.1、01.4.3、01.4.4、01.4.5；DA01.5.1、01.5.2；DA04.1.1–1.3 | 9 |
| 判定族 | DA02.8.1、02.8.2；DA02.12.1、02.12.3、02.12.4；DA03.4.3；DA03.15.1–15.4；DA03.16.1–16.4 | 14 |
| 计算族 | DA01.4.2、01.4.6；DA02.1.1；DA02.2.1–2.3；DA02.4.1、02.4.3；DA03.4.1 | 9 |

## 2. 平台约束

| 约束 | 依据 |
|-|-|
| iface 只有 Rust 实现；`ToolCall.args`、`ToolResult.bytes` 是不透明字节 | `kernel/iface/src/tool.rs` |
| 所有 `tool.exec` 在内核里都是 `SideEffect`，组件不能声明只读 | `kernel/iface/src/session/effect.rs` |
| 内核 host 不支持 MCP | `kernel/host/src` 中没有 MCP 实现 |
| `command` 组件只能由管理员启动配置装配；launcher 写死只装 `tool-fs` | `kernel/host/src/transport/assembly/prepare.rs`；`mint/tools/scripts/mint-runtime-launch.sh:351-363` |
| mint-core 从 bundle 包的 `.mcp.json` 拉起程序，程序名须在 `capabilities.exec` 中声明 | `mint/crates/mint-core/src/mcp_loader.rs:324-345` |
| MCP 工具的读写类型按工具名猜测 | `mint/crates/mint-core/src/mcp/client.rs:706` |
| Python 组件无法使用内核的 `StoreContract` 和模型通道 | 内核只开放 L-C JSON-RPC、command、remote、WASM 四种接入 |

## 3. 包结构

新建两个包，都放在 `packages/capabilities/` 下。

```text
dataagent-contracts/
  pyproject.toml                # hatchling；仅依赖 pydantic>=2
  src/dataagent_contracts/core/{vocab,envelope,refs,data,semantics,task,evaluation,governance}.py
  schema/generated/             # 由类型生成的 JSON Schema
  examples/s0/                  # 05-contracts §3.5 示例及补充
  tests/                        # 往返序列化、枚举封闭、约束、示例校验、依赖方向

dataagent-data/
  mint.toml  .mcp.json  README.md  packaging/source-ref.toml
  skills/dataagent-judgment/SKILL.md
  skills/dataagent-compute/SKILL.md
  pyproject.toml  uv.lock       # 以本地路径依赖 dataagent-contracts
  src/dataagent_data/
    runtime/      # invoke、CallContext 校验、CapabilityResult 构造、错误映射、注册表
    ports/        # content、versioned、trace、inference
    adapters/     # storage/{local_content,sqlite}；parsers/{excel,delimited,json_records,pdf}；ocr/；inference/agent_provided.py
    ingestion/    # files.py、ocr.py
    preparation/  # regions.py、structure.py、profiles.py、documents.py、extraction.py
    semantics/    # metrics_rules.py、decidability.py、applicability.py
    memory/       # traces.py
    interfaces/   # mcp_server.py、cli.py
  tests/{contracts,ingestion,preparation,semantics,memory,interfaces,scenarios}/
  fixtures/
```

- 模块和文件布局按 [01-data-layer.md](01-data-layer.md) 的“代码实现”一节。
- 每个原子的 operation 名和源码文件，以[总 Catalog](catalog/atomic-capability-catalog.json) 为准。

## 4. 调用约定

### 4.1 核心

- 调用形式：`invoke(operation, input, CallContext) -> CapabilityResult[T]`，所有类型来自 `dataagent_contracts.core`。
- 运行时启动时读取包内快照 `src/dataagent_data/catalog-snapshot.json`（研究文档不随 bundle 发布），并校验：
  - 已实现函数的 `operation` 和 `source_file` 与快照一致；`source_file` 由 handler 的 `__module__` 推导，不能手写；
  - S0 数据层的 32 项全部已注册，且没有快照之外的注册项；
  - CI/发布前由 `scripts/export_catalog_snapshot.py --check` 保证快照与总 Catalog 逐项一致。
- 未实现的原子不对外暴露。

### 4.2 MCP 入口

- 协议：用标准库实现 NDJSON JSON-RPC，支持 `initialize`、`tools/list`、`tools/call`，写法参照 `mint/packages/mcp-client/README.md`。
- 工具：工具名就是 operation 名；`inputSchema` 由输入类型生成。
- `CallContext` 的来源：
  - 优先取参数里的 `context` 字段，其次取 MCP 的 `_meta`；
  - `kernel_session_id` 和 `kernel_call_id` 由调用方通过 `CallContext`（CLI）或 MCP `_meta.context` / `arguments.context` 透传，是轨迹自有字段；mint 0.1.16 的 MCP `CallMeta` 没有这两个字段，数据层不依赖它（若宿主使用 iface `CallMeta`，其 `session_id`/`call_id` 可作为来源）。
- 返回值：
  - 把 `CapabilityResult` 序列化成 text content 返回；
  - `status=failed` 时设置 `isError`；
  - `execution_unknown` 按原样返回，不重试。

### 4.3 CLI 入口

- 调用方式：`python -m dataagent_data.interfaces.cli <operation>`，stdin 传入 JSON，stdout 输出 `CapabilityResult`，失败时退出码非 0。
- CLI 不作为内核 `kind:"command"` 组件装配：`kernel/host/src/transport/service/command.rs` 在退出码非 0 时丢弃 stdout、只回传 stderr，会丢失结构化结果。内核/CSP 侧统一走 MCP，CLI 仅用于人/脚本直接调用。

### 4.4 路径与权限

- 文件输入只允许位于工作区内，并拒绝路径越界，做法参照 `mint/bins/mint-tool-fs/tests/tool.rs`。
- 组件不访问网络。
- `authorization_ref` 必填，并写入轨迹。访问判定由 DA12.1 负责。

## 5. Agent 侧推理

**涉及的原子**：DA02.8.1（可选）、DA02.12.1、DA03.4.1、DA03.4.3、DA03.15.1、DA03.16.1、DA03.16.2。

这些原子统一分两次调用：

1. **第一次调用不带 `proposal`。**
   - 工具准备确定性的上下文：候选片段及其 `SourceAnchor`、目标结构、JSON Schema、判定词表。
   - 返回 `status=needs_input`；`Issue` 中带 `suggested_action` 和 `inference_request`。
2. **Agent 按 Skill 的指导生成结果，带上 `proposal` 再调用同一个工具。** 工具依次：
   1. 校验结构；
   2. 逐个核对锚点在原文中是否存在；
   3. 没有依据的值降为 `missing` 或 `conflict`；
   4. 写入版本并返回。

`InferencePort` 首先实现 `agent_provided` 适配器，同时保留接口，以后可以接直连模型的适配器。

## 6. 存储与轨迹

| 端口 | 实现 | 说明 |
|-|-|-|
| ContentStore | 本地文件 | 按内容 digest 寻址，原子写入 |
| VersionedRepository | SQLite | 显式 revision，乐观并发 |
| TraceRepository | SQLite | 接口形状同内核 `StoreContract`：按会话命名空间，cursor 从 1 严格递增，只追加，按 `event_id` 去重，checkpoint digest |
| InferencePort | `agent_provided` | 见 §5 |

`data_root` 默认为工作区 `.dataagent/`，可配置。

### 6.1 内核 StoreContract 的可用性

| 项 | 现状（`agent-kernel@f0fa521`） | 依据 |
|-|-|-|
| 契约 | 已定义：`append`、`read`/`read_from`、`last_cursor`、`checkpoint`、`verify_checkpoint`、`create_session`、`list_sessions` | `kernel/iface/src/store.rs:119` |
| 内核内部使用 | host 写入会话、投递、中断等事件 | `transport/session_deliver.rs:282`、`interrupt_v2.rs:158`、`session_v2.rs:579` |
| L-C 对外方法 | 无 `store.append`/`store.read`；`store.set`/`store.get` 只在效果等级表中 | `transport/method_table.rs`；`session/effect.rs:107` |
| 间接写入 | `session.deliver` 只写固定 kind `message.delivered`，需幂等键，可能给绑定 loop 派作业 | `transport/session_deliver.rs` 头注释 |
| 读取 | `session.watch`、`session.stream_open` 读会话事件流，不能按组件 kind 查询 | `transport/method_table.rs` |
| 组件接入 | `command`：stdin/stdout，无回调；WASM：host-services 只有 `audit`；`local`：须为进程内 Rust 组件 | `service/command.rs`；`wasm-guest-sha256-host/wit/tool.wit` |
| Mint 路径 | mint-core / cpmrt 运行 MCP 组件，无 AgentOS 内核 | `mint/crates/mint-core/src/mcp_loader.rs` |
| 查询能力 | 会话内只追加日志；无跨会话、按 kind 的查询或索引 | `kernel/iface/src/store.rs` |
| 调用留痕 | 经内核的工具调用在执行前由 `TraceSink.record_input` 留痕 | `kernel/iface/src/trace.rs` |

### 6.2 轨迹实现

- 本地 TraceRepository 按 `StoreContract` 接口形状实现，切换到内核时只换适配器；当前实现为 SQLite `trace_events` + `checkpoints`，cursor 从 1 递增、`event_id` 去重、checkpoint 为按 kind 前缀的整体 digest。
- 无内核时 `kernel_cursor` 保持 `null`；`kernel_call_id` 写入事件 payload，供将来与 `TraceSink` 对齐。
- 事件携带 `kernel_session_id`、`kernel_call_id`；`authorization_ref` 一并写入事件 payload（G7），三个轨迹原子共用同一写入器。
- 轨迹表按任务流（`task_ref`）维护 cursor，另存 `kernel_session_id` 并建索引；`read_from(session_id)` 只读本会话（`session_id`）游标；跨任务的内核会话视图由 `read_by_kernel_session(kernel_session_id)` 提供，按全局 `seq` 分页（每任务 cursor 从 1 重启，不能用于跨会话分页）；`TraceRecord.seq` 即下一页游标。
- 写入内核后记录 `kernel_cursor`。
- 经内核调用时，DA04.1.2 只记数据层增量：输入版本、产出引用、锚点、`issues`，以 `kernel_call_id` 关联 `TraceSink` 记录，不重复记录调用本身。
- DA04.3 作用域记忆、DA05.3 历史召回所需的跨会话索引由应用层建设，不依赖内核存储。
- 内核提供组件事件接口（附录 A）后，DA04.1 写入内核；本地实现保留为无内核环境（mint-core）的适配器。

## 7. 第三方依赖

| 用途 | 依赖 | 许可 |
|-|-|-|
| 类型 | pydantic v2 | MIT |
| Excel | openpyxl | MIT |
| PDF 文本与坐标 | pdfplumber（含 pdfminer.six） | MIT |
| OCR（可选依赖组） | rapidocr-onnxruntime | Apache-2.0 |
| CSV、JSON | 标准库 | — |

- 未安装 OCR 依赖时，OCR 原子返回 `dependency_unavailable`。
- 本包许可为 Apache-2.0。

## 8. Mint 打包

| 项 | 内容 |
|-|-|
| kind | `bundle` |
| `.mcp.json` | `{"mcpServers":{"dataagent-data":{"command":"uv","args":["run","--frozen","--project","$PKG","python","-m","dataagent_data.interfaces.mcp_server"]}}}` |
| `[capabilities]` | `exec = ["uv"]`、`fs.read = ["*"]`、`fs.write = [".dataagent/**"]`，每项附 reason |
| `[metadata.runtime]` | `requires = ["python>=3.11", "uv"]` |
| `[package] license` | `Apache-2.0` |
| Skills | `dataagent-judgment`：判定族流程与两段式推理；`dataagent-compute`：计算族流程 |
| 验证 | `mint publish --dry-run`；在隔离的 `MINT_HOME` 中安装 |

## 9. 分步实施

| 步 | 内容 | 产出 |
|-|-|-|
| 0 | 按 AGENTS.md 检查 agent-kernel 是否最新（fetch、ff-only、`--check`）并记录 HEAD；确认 uv 与 python 可用 | 环境记录 |
| 1 | 契约包 core：37 个类型（35 具体 + 2 泛型；07 §4.2 迁入 `ExecutableSpec`/`EngineBinding` 后）、枚举、约束、schema 生成脚本、示例、测试 | `dataagent-contracts` |
| 2 | 数据层骨架：runtime、注册表、存储端口与适配器、MCP 与 CLI 入口 | 可启动的空服务 |
| 3 | 骨干 9 项 | 解析与轨迹 |
| 4 | 判定族 14 项 | 制度切分 → 字段抽取 → 规则 → 可判定性与适用性 |
| 5 | 计算族 9 项 | 不规则 Excel → 规整表 → 画像 → 指标定义 |
| 6 | Mint bundle：mint.toml、.mcp.json、Skills、README、source-ref | 可安装的包 |
| 7 | 设计文档回写：P5 注记；字段校准同步到 05 与总 Catalog | 文档与实现一致 |

## 10. 验证

1. **单元测试**：两个包都运行 `uv run pytest`，覆盖：
   - 契约的往返序列化、枚举封闭和约束；
   - 每个原子的单元测试；
   - 注册表与总 Catalog 的一致性。
2. **场景测试**：使用合成的中性夹具。
   - **判定族**：
     - 流程：制度 PDF 加单据 JSON → 条款单元 → 字段抽取（两段式；测试中模拟 Agent 提供 proposal）→ 规则草案 → 可判定性与适用性。
     - 检查：每个值都有锚点；`unknown` 不被折算；缺失值不补造。
   - **计算族**：
     - 流程：不规则工作簿（多行表头、合并单元格、合计行、1904 日期系统）→ 规整的 `TableRef` → 画像 → `MetricDefinition` 草案。
3. **入口黑盒测试**：
   - MCP：作为子进程运行，覆盖 `initialize`、`tools/list`（32 个工具）、`tools/call` 和错误映射。
   - CLI：通过 argv 加 stdin 调用，检查退出码，并验证路径越界被拒绝。
4. **Mint 验证**：
   - 运行 `mint publish --dry-run`；
   - 在隔离的 `MINT_HOME` 中安装，确认 mint-core 能加载 `.mcp.json` 并列出全部工具；
   - 条件允许时，用 `mint run --json` 跑一次脚本化调用。

## 11. 风险

| 风险 | 处理 |
|-|-|
| MCP 工具类型按名称猜测，多数 operation 会被判为 `Other`，在 mint-core 中每次调用都会弹审批 | 第 6 步实测后，再决定是否需要宿主侧放行配置 |
| rapidocr 模型约百 MB | 作为可选依赖组，默认不安装 |
| 内核桌面路径需要修改 agent-kernel 的启动组件配置 | 内核/CSP 侧走 MCP，不改内核；CLI 只供人/脚本直接调用（§4.3） |
| 内核组件事件接口未定 | 轨迹按 `StoreContract` 形状本地实现；附录 A 提交 agent-kernel 评审 |

## 12. 实施与评审记录

| 文件 | 轮次 | 日期 | 内容 | 测试（contracts / data） | 评分 | 原章节 |
|-|-|-|-|-|-|-|
| [r1-implementation.md](06-data-layer-build/r1-implementation.md) | 1 | 2026-11-03 | 落地范围、环境基线、验证命令、与方案的差异 | 111 / 187（计数随 Round 4.3 更新） | — | §12.1–12.4 |
| [r2-fixes.md](06-data-layer-build/r2-fixes.md) | 2 | 2026-11-03 | 轨迹字段、错误映射、源摘要、数值锚点、OCR、契约扩展 | — | — | §12.6 |
| [r3-fixes.md](06-data-layer-build/r3-fixes.md) | 3 | 2026-11-03 | 锚点取值校验与重定位、CLI 启动门、冷启动、打包 | 84 / 105 | — | §12.7 |
| [r3-review.md](06-data-layer-build/r3-review.md) | 3 评审 | 2026-11-03 | 9 个维度评分；问题 #1–#17 | 84 / 105 | 5.5 | §13 |
| [r4-fixes.md](06-data-layer-build/r4-fixes.md) | 4–4.3 | 2026-11-04 | 修复计划 8 项；Round 4 及 4.1–4.3 返修；已知限制 | 111 / 187 | — | §14、§12.8–12.11、§12.5 |
| [r4-review.md](06-data-layer-build/r4-review.md) | 4 评审 | 2026-11-04 | #1–#17 完成情况；新缺陷；代码质量；评分 | 111 / 187 | 6.5 | — |
| [r5-plan.md](06-data-layer-build/r5-plan.md) | 5 计划 | 2026-11-04 | 13 项修复与验收；门禁 | — | — | — |
| [r5-fixes.md](06-data-layer-build/r5-fixes.md) | 5 修复 | 2026-11-04 | B1–B3 阻断项、P1 锚点粒度、P2 轨迹/契约修复；回归与门禁 | 111 / 211 | — | — |
| [r5-independent-audit.md](06-data-layer-build/r5-independent-audit.md) | 5 评审 | 2026-11-04 | 独立复评 6.8；D1–D10 复现 | 111 / 187 | 6.8 | — |
| [r5-verifier-scorecard.md](06-data-layer-build/r5-verifier-scorecard.md) | 5 评审 | 2026-11-04 | 验收对照与评分 | 111 / 187 | 7.0 | — |
| [changes.md](../../../packages/capabilities/dataagent-data/evidence/round4/changes.md) | 6–11 | 2026-11-04 | 中文否定/预防动词逐轮修复；262 例回归；Tester 多轮复核 | 111 / 473 | — | — |
| [r12-fixes.md](06-data-layer-build/r12-fixes.md) | 12 | 2026-11-04 | Reviewer F1（英文预防动词）、F2（DA03.16.2 锚点校验）、F4（rule_ref@r1）；回归 493 | 111 / 493 | — | — |
| [r13-fixes.md](06-data-layer-build/r13-fixes.md) | 13 | 2026-11-04 | 独立评审 P1 阻断项 F1–F6（正文-来源绑定、界限/连接词/论元守门、无锚点 fail-closed、指标/范围逐项校验、目标 schema、轨迹身份与原子性）；F7–F10 记为限制 | 111 / 506 | 评审 6.8 / Tester 7.3 | — |
| [r14-fixes.md](06-data-layer-build/r14-fixes.md) | 14 | 2026-11-04 | Tester r13 两条阻断：F1 伪造 FileRef 身份（摘要派生 id 校验 + 身份不可变）、F2 英文情态类守门 | 111 / 520 | Tester 7.4（r15 复核） | — |
| [r15-fixes.md](06-data-layer-build/r15-fixes.md) | 15 | 2026-11-04 | Tester r15 P1：情态守门改按子句序列绑定（跨子句互换、整体丢弃均拒绝），片段引用豁免保留 | 111 / 532 | — | — |
| [r16-fixes.md](06-data-layer-build/r16-fixes.md) | 16 | 2026-11-04 | Reviewer r16 P1：R1 情态绑定到作用域内容、R2 比较/条件/连接结构绑定到命题（主语界限、if/then 方向、AND/OR 序列）、R6 异常映射收窄；R3/R4/R5 记为限制 | 111 / 548 | 评审 7.4 | — |
| [r17-fixes.md](06-data-layer-build/r17-fixes.md) | 17 | 2026-11-04 | Tester r17 阻断：B2 auto 判定的 basis_refs 必须可解析（伪造引用降级 needs_evidence 且不落库）、B3 切分/抽取截断改报 truncated、R4c 缓存无 prior_statement 时保守失效；B1 审计 manifest 重生成与 36→37 类型文档同步 | 117 / 560 | — | — |
| [r19-fixes.md](06-data-layer-build/r19-fixes.md) | 19 | 2026-11-05 | Reviewer r19 四类 P1 语义放行 F1–F4（适用范围否定/界限/连接词改写等）fail-closed | 117 / 581 | 评审 7.3 | — |
| [r20-fixes.md](06-data-layer-build/r20-fixes.md) | 20 | 2026-11-05 | Reviewer r20 N1/N2 指标校验绕过、N3/N4 片段标点与引号；N5/N6 未处理 | 117 / 596 | 评审 7.7 | — |
| [r21-fixes.md](06-data-layer-build/r21-fixes.md) | 21 | 2026-11-05 | Reviewer r21 F1–F4（引号字符串逗号、按谓词核对、`SqliteDatabase.session()`）、F5 文档漂移；§10.2 两条场景 | 117 / 621 | — | — |
| [r41-review.md](06-data-layer-build/r41-review.md) | 41 评审 | 2026-11-05 | 数据层与契约 core 完成度（S0 已完成 22 / 部分 10）；新缺陷 D1–D9、C1–C8；复现脚本 [r41-repro/](06-data-layer-build/r41-repro/) | 117 / 649 | — | — |

代码与测试注释中的 “06 §14 item N” 指 [r4-fixes.md](06-data-layer-build/r4-fixes.md) §1 第 N 项。证据日志：`packages/capabilities/dataagent-data/evidence/round4/`。

## 附录 A：内核组件事件接口提案

供 agent-kernel 评审，使进程外组件可在会话事件存储中追加和读取自身事件。

### A.1 方法

| 方法 | 效果等级 | 幂等 | 参数 | 返回 |
|-|-|-|-|-|
| `store.ext_append` | `Advance` | 幂等键必填 | `session`、`kind`、`payload`（JSON 或 base64）、`event_id`、`call_id?` | `cursor`、`ts_ms`；同 `event_id` 重复提交返回首次结果 |
| `store.ext_read` | `ReadOnly` | 是 | `session`、`kind_prefix`、`from`（含）、`limit` | `records[]`（`cursor`、`kind`、`payload`、`ts_ms`、`call_id?`）、`next_cursor?` |
| `store.ext_checkpoint` | `Advance` | 是 | `session`、`kind_prefix` | `checkpoint_id`、`cursor`、`digest` |

### A.2 约束

| 项 | 规则 |
|-|-|
| kind 命名空间 | 只允许 `ext.<component>.<event>`；`<component>` 由装配时登记的组件身份决定，组件不能写其他命名空间，不能写内核 kind |
| 授权 | 经 guard 检查 op `store.ext_append` / `store.ext_read`；`principal` 为组件身份；读取限于本组件命名空间及被授权的会话 |
| 存储 | 复用 `StoreContract::append`；cursor 与内核事件共用会话序列，`kind_prefix` 过滤在读取时进行 |
| 大小 | 单条 `payload` 上限（建议 64 KiB）；大内容存组件侧，事件只存引用与 digest |
| 留痕关联 | `call_id` 与 `TraceSink.record_input` 的 `CallMeta.call_id` 一致 |
| 完整性 | `verify_checkpoint` 对 ext 事件同样适用 |
| 接入方式 | L-C JSON-RPC；WASM host-services 增加同名函数；`command` 组件经 host 注入的会话令牌回调 L-C |

### A.3 不包含

跨会话查询、按内容索引、删除与改写。
