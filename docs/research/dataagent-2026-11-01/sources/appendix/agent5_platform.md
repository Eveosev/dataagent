---
title: "DataAgent 横切工程能力、交付形态与可插拔契约"
description: "为《DataAgent 模块化能力拆分调研报告》提供 AgentOS/DataAgent 边界、能力单元 manifest 字段、交付形态对照与外部证据"
date: 2026-11-01
timezone: Asia/Shanghai
status: evidence-report
scope: "2025–2026 官方文档与公开研究；仓库内 Kernel iface / Mint 清单事实"
covers: [runtime, context, sandbox, observability, guardrails, hitl, delivery, cost]
---

# DataAgent 横切工程能力、交付形态与可插拔契约

> 证据口径：**[F] 事实** = 抓取到的官方文档原文或仓库源码；**[I] 推断** = 基于事实的设计建议，未被任何官方文档直接支持。
> 所有网页访问日期均为 **2026-11-01**（Asia/Shanghai）。仓库事实对应 `packages/agent-kernel` HEAD `86ae83c`（2026-10-30）。
> 本文不声称任何 DataAgent 模块已实现或已评测；不把厂商宣称当准确率，不把"能执行"当"业务正确"。

---

## 0. 结论先行

1. **横切能力已经在收敛成"元数据 + 结构化结果 + 可观测事件"三件套。** Agent Skills 用 `name/description` 做发现（约 100 tokens/个），MCP 用 `inputSchema/outputSchema/annotations` 描述工具，OpenAI 用 `_meta` 描述 UI/鉴权/调用态。DataAgent 若自造一套描述格式，会同时失去三家的宿主兼容性。[F: R1/R6/R10]
2. **Kernel 该提供的是"机制"，DataAgent 该提供的是"语义与正确性"。** 仓库现状已经划出这条线：`PolicyContract`（含 egress/delegation/approval）、`ToolContract`、`ContextContract`、`TraceSink`、`ExecBackend` 都在 iface；语义层、NL2SQL、ontology、指标口径不在。[F: 仓库]
3. **"只读 SQL"不是安全边界。** DuckDB 的 `enable_external_access` 默认 `true`，SQLite CLI 提供 `readfile()/writefile()`，PostgreSQL `COPY TO PROGRAM` 可执行服务器端命令（受角色限制）。沙盒、出网管制、扫描量上限必须由运行时提供，不能靠 SQL 关键字审查。[F: R30–R33]
4. **HITL 不能由模型自报置信度驱动。** 可用的触发信号是：副作用等级、证据缺口、预算耗尽、权限拒绝、结果不可复算。MCP 的 elicitation 已把"表单/URL 两种澄清"和"不得收集凭据"写成协议约束。[F: R8]
5. **交付形态会反向改写能力拆分。** Google Sheets 自定义函数不能申请个人数据授权，且只有把引用区域作为参数传入才会重算——这直接否决"会话权限透传 + 每次实时调模型"的实现方式，要求交付层产出可复算产物 + 显式刷新。[F: R41]

---

## 1. Agent 运行时与编排

### 1.1 事实

| 主题 | 官方事实 | 来源 |
| --- | --- | --- |
| Skills 结构 | `SKILL.md` + YAML frontmatter，必填 `name`（≤64 字符，小写/数字/连字符，禁用 `anthropic`/`claude`）与 `description`（非空，≤1024 字符，禁 XML 标签） | R1 |
| 渐进披露 | L1 元数据常驻（约 100 tokens/技能）；L2 `SKILL.md` 正文在触发时加载（<5k tokens）；L3 `references/`、`assets/`、`scripts/` 按需读取，未读不计费；脚本只把输出放进上下文 | R1 |
| Skill 执行环境 | API 侧 Skills 运行在**无网络、不可安装运行时包**的沙盒容器内，且依赖 code execution tool | R1 |
| OpenAI 插件形态 | 插件 = Skills（可选）+ MCP server（可选）+ 可选 UI + 生命周期 hooks；最小形态优先 | R9 |
| OpenAI 工具元数据 | 工具描述符 `_meta` 承载 `ui.resourceUri`（MCP Apps 标准键）、`openai/outputTemplate`（兼容别名）、`ui.visibility`、`toolInvocation/invoking|invoked`（≤64 字符）、`fileParams`、`securitySchemes`、`openai/profile` | R10 |
| 副作用标注 | `readOnlyHint` / `destructiveHint` / `openWorldHint` 被列为**必填**；写操作若不可逆须 `destructiveHint: true`，且"可撤销"本身不足以设为 false | R10/R12 |
| 结果分层 | `structuredContent` 与 `content` 进入对话记录；工具结果的 `_meta` **只给组件、不给模型** | R10 |
| MCP 工具契约 | `name`、`title`、`description`、`icons`、`inputSchema`、`outputSchema`、`annotations`；`inputSchema` 必须是合法 JSON Schema（默认 2020-12）；annotations **必须视为不可信**，除非来自可信服务器 | R6 |
| MCP 协议形态 | 2026-07-28 起**移除协议级会话**与 `initialize` 握手：每个请求在 `_meta` 携带版本与客户端能力；新增 `server/discover`；`resultType` 必填；服务端主动请求改为 MRTR（`input_required` + `inputResponses` 重试） | R4/R5 |
| MCP 缓存 | `tools/list`、`resources/read` 等结果新增必填 `ttlMs` 与 `cacheScope`（`public`/`private`） | R5 |
| MCP 授权 | OAuth 2.1 资源服务器模型，`resource` 参数（RFC 8707）绑定受众；优先 CIMD，DCR 降级；PKCE S256 | R7/R11 |
| 安全责任 | 服务端 MUST 校验输入、做访问控制、限流、清洗输出；客户端 SHOULD 对敏感操作二次确认、调用前展示输入、校验结果、超时、审计 | R6 |
| 命名冲突 | 工具名仅在同一 server 内唯一；聚合多 server 的客户端应加前缀消歧（Mint 已用 `<server>__<tool>`） | R6 / 仓库 |

### 1.2 对 DataAgent 的推论

- **[I] 能力单元的描述就是 API。** `description` 决定路由与触发（Anthropic 明确 "model matches your request against description"），DataAgent 的"问数/探查/对账"三类单元如果描述都写"分析数据"，模型必然误触发。建议 manifest 强制 `description` 同时包含"做什么 + 何时用 + 何时不要用"。
- **[I] 副作用等级必须是声明式字段，不是运行时猜。** 仓库现状 `effect_for_op(unknown) → SideEffect`（fail-closed）与 OpenAI 的 `destructiveHint` 是同一思路；DataAgent 的"写回语义层/发布指标/导出到外部"应各自声明等级。
- **[I] 不能依赖连接级会话状态。** MCP 2026-07-28 已无 `Mcp-Session-Id`，跨调用状态要由服务端签发 handle 并作为普通参数传递。DataAgent 若把"当前任务数据空间"放在 MCP 连接上，会在新协议下失效。
- **[I] 子代理不是越多越好。** 官方口径是子代理用大量 token 探索、只回传约 1,000–2,000 tokens 的摘要。DataAgent 的"探查子代理 + 语义子代理 + 验证子代理"应各自有明确的回传 schema，否则主代理上下文会被摘要噪声占满。[F: R22]

---

## 2. 上下文工程

### 2.1 事实

| 主题 | 事实 | 来源 |
| --- | --- | --- |
| 上下文退化 | Chroma 2025-07-14 报告：评测 18 个模型（含 GPT-4.1、Claude 4、Gemini 2.5、Qwen3），输入越长性能越不稳定；needle-question 语义相似度越低，退化越快；干扰项与结构化 haystack 都会加剧 | R21 |
| 注意力预算 | Anthropic：context rot 普遍存在；transformer 的 n² 关系使上下文是"有限资源、边际收益递减"；目标是"最小的高信号 token 集" | R22 |
| 长任务三手段 | compaction（总结后重开窗口，先最大化召回再提精度）、结构化笔记（外部记忆）、多代理（子代理回传 1–2k tokens） | R22 |
| 工具结果清理 | 官方称"最安全、最轻的压缩"是清除历史工具结果 | R22 |
| JIT 检索 | 保留轻量标识（路径/查询/链接），运行时按需加载；混合策略（预热 + 自主探索）常见 | R22 |
| 记忆工具 | 基于文件的 memory 目录，跨会话持久；写入什么由代理决定，支持 JIT 读回 | R23 |
| 缓存 | Anthropic：默认 5 分钟 TTL，读 0.1×、5 分钟写 1.25×、1 小时写 2×；OpenAI：缓存输入折扣最高 95%，30 分钟基础覆盖 / 12 小时延长，按 `cached_tokens` 计量 | R24/R25 |

### 2.2 建议的上下文预算模型 [I]

| 预算项 | 建议上限 | 理由 |
| --- | --- | --- |
| 系统提示 + 工具定义 | ≤ 15% | 工具膨胀是最常见失败模式；工具应"自包含、低重叠"（R22） |
| 注入的 schema/语义 | ≤ 20%，且按需分层（库→表→列→指标） | 全库 DDL 注入既贵又稀释注意力；与 context rot 结论一致 |
| 证据/查询结果 | ≤ 35%，只放摘要 + 引用 | 大结果走 artifact，模型只读 schema/摘要/样本（与 MintHost 组合建议一致） |
| 会话历史 | ≤ 20%，超出触发 compaction | 官方 compaction 与工具结果清理 |
| 预留输出/推理 | ≥ 10% | 避免截断导致重试 |

- **[I] 可引用的量化边界不存在。** Chroma 未给出"多少 token 以下安全"的阈值，Anthropic 也只说"performance gradient rather than a hard cliff"。任何"必须 <32k"的说法都是外推。报告中应写成"随长度单调退化 + 需按任务实测"，而不是引用一个魔法数字。
- **[I] 语义注入的优先级应由"证据强度"决定**（已发布指标 > 人工确认映射 > 历史 SQL > 模型猜测），并把该排序写入 manifest 的 `context_policy`，否则不同 cell 会各自发明一套。

---

## 3. 沙盒执行

### 3.1 事实

| 主题 | 事实 | 来源 |
| --- | --- | --- |
| Firecracker | 基于 KVM 的 microVM，定位是"multitenant 容器与函数的安全、快速替代"，宣称提升安全性、降低启动时间 | R26 |
| gVisor | 应用内核（application kernel），在应用与宿主 OS 之间提供强隔离，可与 Docker/Kubernetes 集成 | R27 |
| Daytona | 沙盒默认是 Linux 容器，提供独立内核、文件系统、网络栈与分配的 vCPU/RAM/磁盘；容器启动 <90ms；另有 VM/GPU/macOS 沙盒；支持 auto-stop/auto-pause/auto-archive/auto-delete 与 wall-clock TTL、快照、预热池 | R28 |
| E2B | 面向 AI agent 的沙盒 SDK（"安全执行代码、处理数据"），提供快照能力；**本次抓取未取得其隔离底层与启动时延原文** | R29（部分） |
| 资源配额 | 仓库 `ExecRequest` 只有 `program/args/cwd/env/timeout_ms`，**无 CPU/内存/磁盘/网络字段**；`EnvironmentCapabilities` 只有 fs/exec/signals/streams 四开关 | 仓库 |
| DuckDB | `enable_external_access` **默认 `true`**（允许加载扩展、COPY TO/FROM、CSV 读取、pandas replacement scans）；另有 `allowed_paths`、`allowed_directories`、`disabled_filesystems`、`lock_configuration` | R30 |
| SQLite | CLI 提供 `readfile(X)` / `writefile(X,Y)` 扩展函数，可读写任意可达文件 | R31 |
| PostgreSQL | `COPY ... TO PROGRAM` 由**服务器**执行命令；仅超级用户或被授予 `pg_read_server_files`/`pg_write_server_files`/`pg_execute_server_program` 的角色可用；文件路径以服务器视角解析 | R32 |
| BigQuery | on-demand 模式"限制成本的唯一方式是项目级/用户级每日配额"；按扫描 TiB 计费 | R33 |

### 3.2 "只读 SQL 不等于安全"的风险矩阵 [I]

| 风险 | 具体路径 | 现有机制能否挡住 | 建议控制点 |
| --- | --- | --- | --- |
| 读本地文件 | DuckDB `read_csv('/etc/passwd')`、`read_text`；SQLite `readfile()`；PG `pg_read_file` | 不能（默认允许外部访问） | 沙盒文件系统白名单 + `disabled_filesystems` + 只挂载任务数据空间 |
| 读云元数据/内网 | DuckDB `httpfs` 读 `http://169.254.169.254/...`；PG `dblink`/`postgres_fdw` | 不能 | 网络出口默认拒绝 + 显式域名白名单 + 禁 link/foreign scan |
| 数据外泄 | 把查询结果拼进 URL/HTTP 请求；`COPY TO PROGRAM` 调 curl | 不能 | egress 判决（仓库 `check_egress`）+ 结果体积上限 + 出网内容审计 |
| 高成本查询 | 大表笛卡尔积、重复扫描、无分区过滤 | 不能 | 扫描字节上限（`maximum_bytes_billed` 类）、超时、EXPLAIN 成本门禁 |
| 写入/破坏 | `COPY TO PROGRAM`、`ATTACH` 建库、`INSTALL` 扩展 | 部分（角色限制） | 只读账号 + 语句白名单 + 只读挂载 |
| 结果集爆炸 | 亿行结果拉回内存 | 不能 | 行数/字节上限 + 强制聚合/分页 + 只返回摘要 |

- **[I] 关键结论：SQL 审查是"策略"，沙盒与配额才是"边界"。** 报告应明确要求：任何执行 SQL/Python 的 cell 必须在 `ExecBackend` 之上叠加 (a) 文件系统白名单、(b) 出口拒绝默认、(c) 扫描量/时长/行数三重预算、(d) 只读凭据。仓库当前 `ExecRequest` 缺配额字段，是需要在 Kernel 侧补的缺口（推断，需 owner 确认设计意图）。
- **[I] "只读账号"只降低写风险，不降低读风险。** 读权限越大，泄露面越大；行列权限必须在查询改写层（RLS/视图）落地，而不是在提示词里要求模型"不要查敏感列"。

---

## 4. 可观测与评测

### 4.1 事实

| 平台/标准 | 数据模型与关键字段 | 来源 |
| --- | --- | --- |
| OTel GenAI | agent span 体系：`create_agent`、`invoke_agent`、`invoke_workflow`、`plan`、`execute_tool`、`load_skill`；属性含 `gen_ai.operation.name`、`gen_ai.agent.name/id`、`gen_ai.conversation.id`、`gen_ai.tool.name/type/call.id/call.arguments/call.result`、`gen_ai.skill.name/source.uri`、`gen_ai.input.messages`/`output.messages`、`gen_ai.usage.*`（含 `cache_read.input_tokens`）、`gen_ai.data_source.id` | R15 |
| OTel MCP | `mcp.method.name`、`mcp.protocol.version`、`mcp.session.id`、`mcp.resource.uri`、`mcp.request.id`，以及 client/server 的 operation/session duration 指标 | R16 |
| LangSmith | run（最小工作单元）→ trace（一次操作）→ thread（多轮）→ trajectory（扁平消息序列）；单 trace 上限 25,000 runs；支持 feedback/tags/metadata | R17 |
| Langfuse | observation（span/generation/event）→ trace → session；trace 级属性复制到每条 observation；OTel 兼容，可多目的地 | R18 |
| Braintrust | span 类型：`eval`/`task`/`llm`/`function`/`tool`/`score`/`classifier`；trace 由 `root_span_id` 标识；score 含 scorer 名与判定理由 | R19 |
| Arize Phoenix | OTel/OpenInference 语义，span kind + attributes，支持数据集与实验 | R20 |
| 仓库 trace | `TraceSink.record_input`（act 前原子落盘）、`record_branch`（压缩边界/子代理派生）；`AuditEvent{session, call, op, decision, reason}` | 仓库 |

### 4.2 复盘 DataAgent 错误所需的 trace 字段 [I]

| 层次 | 必录字段 | 为什么必需 |
| --- | --- | --- |
| 请求 | `conversation.id`、`turn`、用户主体、租户、渠道、locale、时区 | 同一问题在不同时区/主体下答案不同，缺了就不可复现 |
| 规划 | `plan` span、步骤类型、候选假设、被放弃的分支 | 错误常来自"选了错的计划"，只看最终 SQL 无法归因 |
| 检索 | 查询串、命中对象 ID + 版本、召回分数、ACL 判定、是否截断 | 区分"没召回"与"召回了但没用" |
| 语义 | `semantic_version`、指标公式版本、as-of、适用规则 ID | 口径错误与数据错误必须分开 |
| 查询 | 方言、SQL 文本、绑定参数、计划哈希、扫描字节、行数、耗时、是否命中缓存 | 成本与正确性都要能重放 |
| 工具 | `gen_ai.tool.name`、参数、结果摘要、`mcp.method.name`、server 版本 | 跨 server 的工具行为差异 |
| 模型 | `gen_ai.request.model`、输入/输出/cache token、finish reason、是否降级 | 区分模型退化与数据退化 |
| 交付 | artifact ID、行数、公式模式、导出/分享范围 | "结果对但交付错"是常见事故 |
| 判定 | 校验项通过/失败、证据缺口、HITL 结论、审批人 | 复盘需要知道"当时是否有人看过" |

- **[I] 建议直接采用 `gen_ai.*` / `mcp.*` 词典，不另造 `dataagent.*` 顶层命名空间。** 领域字段放 `data.*` 前缀（如 `data.sql`, `data.as_of`, `data.semantic_version`, `data.bytes_billed`），这样能同时进 LangSmith/Langfuse/Phoenix/Braintrust，而不被单一厂商锁定。
- **[I] trace 与 audit 要分离。** trace 用于调试（可采样、可含敏感摘要），audit 用于合规（不可采样、必须完整、写入即不可改）。仓库把 `AuditSink` 放在 policy、`TraceSink` 放在 context，正是这个分工。

---

## 5. 护栏

### 5.1 事实

| 主题 | 事实 | 来源 |
| --- | --- | --- |
| 风险分类 | OWASP LLM Top 10 (2025)：LLM01 Prompt Injection、LLM02 Sensitive Information Disclosure、LLM06 Excessive Agency、LLM10 Unbounded Consumption | R34 |
| 致命三要素 | 私有数据 + 不可信内容 + 对外通信，三者同时具备即可被利用外泄 | R35 |
| 注入缓解 | Spotlighting：用标记/编码/数据标记让模型区分来源，实验把攻击成功率从 >50% 降到 <2%，对任务效果影响小 | R36 |
| 系统级防御 | CaMeL：从可信查询提取控制流/数据流，使不可信数据无法影响程序流；用 capability 阻止未授权数据流外泄；AgentDojo 上 77% 任务可证明安全（无防御 84%） | R37 |
| 插件侧要求 | 假设注入一定到达服务端；服务端校验所有输入；不可逆操作需人工确认；不鼓励在描述里写破坏性用法；日志脱敏、只存关联 ID | R12/R13 |
| 澄清协议 | elicitation 分 `form`（客户端内联、扁平对象、可校验）与 `url`（敏感交互不经客户端）；**禁止用 form 收集凭据**；客户端必须显示是哪个 server 在要数据、允许修改后提交 | R8 |
| 审批 | `PolicyContract.request_approval` 是"唯一合法阻塞路径"，默认 `NeedsHuman`（fail-closed）；`ReviewVerdict` 表达审阅位 | 仓库 |
| 预算 | `Budget`/cost 目前不在 Kernel iface；Mint 的 `Capabilities` 九类只覆盖 fs/net/exec/env/model/secrets/ui/memory，无成本类 | 仓库 |

### 5.2 防御层次 [I]

| 层 | 手段 | 能挡住 | 挡不住 |
| --- | --- | --- | --- |
| L0 数据边界 | 只读凭据、RLS/视图、行列权限、值索引 ACL | 越权查询 | 有权限范围内的滥用 |
| L1 内容标记 | spotlighting / 结构化分隔 / 表名与单元格转义 | 单元格/文档注入 | 高能力模型的多步推理注入 |
| L2 工具约束 | 参数化、语句白名单、结果行数上限、禁 DDL/DML | 破坏性语句 | 合法语句的高成本组合 |
| L3 沙盒 | 无网络/白名单、只读挂载、资源配额 | 文件读取、SSRF、挖矿 | 沙盒内合法计算泄露 |
| L4 出口管制 | egress 判决、域名白名单、体积上限、DLP | 外泄 | 低带宽逐次渗出 |
| L5 人审 | 按副作用/风险分级审批 | 高影响动作 | 审批疲劳导致的橡皮图章 |
| L6 检测 | 注入分类器、异常查询检测、成本告警 | 已知模式 | 新型注入 |

- **[I] 对 DataAgent 最现实的三条硬约束**：(1) 任何"读数据 + 能出网"的组合必须拆开或强制审批（致命三要素）；(2) 值索引/样本/缓存必须继承源表 ACL，否则等于自建了一个绕过权限的副本；(3) 成本攻击要用"扫描字节 + 并发 + 时长"三重上限，而不是只限 token。
- **[I] 不要把"注入检测"当主防线。** CaMeL 的结论是：即使模型被攻破，只要控制流/数据流被系统层约束，仍可保证安全；这比"训练模型识别注入"更可验证。

---

## 6. 人机协同（HITL）

### 6.1 事实

| 主题 | 事实 | 来源 |
| --- | --- | --- |
| 澄清协议 | MCP elicitation：`form` 模式 schema 仅支持扁平对象，格式含 `email/uri/date/date-time`；`url` 模式用于敏感交互；客户端 MUST 明示请求方并允许复核 | R8 |
| 审批交互 | OpenAI 插件：破坏性/不可逆操作须宿主显式确认；`destructiveHint` 是宿主决定是否弹确认的依据 | R10/R12 |
| 长任务暂停 | LangGraph `interrupt()`：保存图状态、无限期等待，`Command` 恢复；要求 thread_id、副作用幂等、不得包 try/except、不得重排 interrupt 顺序 | R38 |
| 仓库能力 | `ApprovalRequest{session, call, summary, timeout_ms}`，超时默认拒绝；`ReviewRequest/ReviewVerdict/ReviewPosition` | 仓库 |

### 6.2 必须 HITL 的条件 [I]

| 条件 | 触发信号 | 交互形态 |
| --- | --- | --- |
| 不可逆副作用 | 写回、发布指标、发消息、导出到外部 | 阻塞审批 + 影响面预览 |
| 口径歧义影响结果 | 同一问题绑定到 ≥2 个指标/时间口径，且结果差异 > 阈值 | 结构化澄清（选项 + 默认值 + 影响说明） |
| 证据不足 | 关键表未探查、值匹配置信度低、结果为空但预期非空 | 澄清或"带限制的回答" |
| 权限拒绝 | `Decision::Deny`/`NeedsHuman` | 请求授权或降级到聚合结果 |
| 预算耗尽 | 扫描量/时长/token 触顶 | 询问是否追加预算 |
| 结果不可复算 | 依赖非确定性函数/外部实时数据 | 标注 + 要求确认 |
| 高风险域 | 财务披露、合规报表、对外发布 | 强制双人审阅 |

- **[I] 置信度表达应是"证据账本"，不是百分比。** 模型自报 0.87 既不可校准也不可审计。建议输出：已覆盖对象/未覆盖对象、关键假设、口径版本、数据 as-of、失败校验项。这比"置信度 87%"更能支撑审阅。
- **[I] 澄清要有预算。** 官方 Skills 建议在"输入不完整时触发追问"，但没有无限追问的机制；DataAgent 应限制单轮澄清次数（如 ≤2 次），超出则给出"最可能解释 + 明确标注"的回答。

---

## 7. 交付形态与反向要求

### 7.1 事实

| 形态 | 事实 | 来源 |
| --- | --- | --- |
| Slack | Block Kit：blocks + elements + composition objects，JSON 描述；单条消息最多 50 blocks，modal/Home tab 最多 100 | R39 |
| Teams / M365 Copilot | 声明式代理的 action 支持 MCP 与 API 插件；API 插件依赖 OpenAPI 描述；插件 manifest 声明能力；MCP 插件默认**运行时动态发现工具**，也可在 manifest 固定工具集 | R40 |
| Excel | 官方 custom functions 文档可访问，但正文未能抽取（见不确定项）；Anthropic 提供 xlsx 预置 Skill，用于表格读写与公式 | R45/R1 |
| Google Sheets | Apps Script 自定义函数：不能使用 `NOW()`/`RAND()` 等易变函数作参数（会永久 Loading）；**只有把引用单元格/区域直接作为参数传入才会重算**，否则要编辑函数或改引用值；自定义函数从不申请个人数据授权，只能调用无个人数据的服务 | R41 |
| 嵌入式 BI | Power BI embedded：`App-owns-data`（对客户）与 `User-owns-data`（对内部）两种模型；secure embed 为 iframe/URL，查看者需相应许可证 | R42 |
| Chat 内 UI | ChatGPT 支持 MCP Apps UI 标准；工具可在无 UI 时返回结构化结果，UI 仅在有检查/比较/编辑需求时添加 | R9 |

### 7.2 交付形态 × 能力要求

| 形态 | 时延预算（建议） | 权限/身份 | 结果承载 | 可复算要求 | 对拆分的反向要求 |
| --- | --- | --- | --- | --- | --- |
| 嵌入式 BI（iframe/SDK） | 首屏 p95 ≤3s；缓存命中 ≤800ms | 必须透传查看者身份 + RLS；不能共用服务账号 | 图表/表格组件 + 数据快照 ID | 需可按快照重放 | 查询与渲染解耦；cell 必须支持"只取数不解释"；缓存键含主体与 ACL |
| Slack | 首条响应 ≤5s（含"正在查询"占位） | workspace/user 绑定；链接鉴权 | 摘要 + 图表图片 + 深链 | 深链回到可复算页面 | cell 要支持"摘要模式"（≤50 blocks）；长任务必须异步 + 回帖 |
| Teams / Copilot | 同 Slack；插件调用受宿主超时约束 | Entra ID；插件 manifest 声明 scope | Adaptive Card / 结构化结果 | 同 Slack | 需同时提供 OpenAPI 与 MCP 两种描述（R40） |
| Excel | 交互式 ≤2s/批 | 文件级权限；不能假设会话身份 | 单元格值/公式 + 源查询引用 | **公式必须可复算**；值需带 lineage | 交付 cell 要能输出"公式 + 参数 + 数据引用"，而不是只输出数字 |
| Google Sheets | 自定义函数受 30s 级限制 | **不能申请个人数据授权** | 值/二维数组 | 只有传入引用区域才重算 | 必须提供"显式刷新"入口 + 结果快照；不能依赖会话权限 |
| API / Headless | p95 ≤2s（同步）/ 异步任务 | OAuth/JWT；租户隔离 | JSON + artifact 引用 | 请求需含 `as_of`/版本 | cell 必须有稳定 JSON schema 与错误码；不能只返回自然语言 |
| 报告 / 幻灯片 | 生成 ≤60s；可后台 | 生成者权限 + 分享范围 | 文件 + 证据附录 | 需保留生成参数与数据版本 | 需要"装配"型 cell（模板 + 数据 + 叙述），而非单一问答 cell |
| Chat 内 UI（MCP Apps） | 首帧 ≤1.5s | 宿主 OAuth；CSP 限制 | 组件 + `structuredContent` | 组件需能重取数据 | 工具必须无 UI 也可用（headless 优先，R9） |

- **[I] 最强的一条反向约束来自 Sheets/Excel**：电子表格要求"值可复算、刷新可控、权限不随会话走"。这意味着 DataAgent 的交付层不能是"模型生成一段文字/一张图"，而必须是**带参数与数据引用的产物**（SQL + 快照 + 公式）。这一条会直接改变 DA09 的模块边界。
- **[I] 第二强的是嵌入式 BI**：它要求低时延与权限透传，意味着"每次提问都跑一遍完整 agent 循环"不可行，必须支持"语义计划直出 + 缓存 + 仅对异常走 agent"。

---

## 8. 成本与性能

### 8.1 事实

| 手段 | 事实 | 来源 |
| --- | --- | --- |
| 提示缓存 | Anthropic 读 0.1×、5 分钟写 1.25×、1 小时写 2×，默认 5 分钟；OpenAI 折扣最高 95%，30 分钟/12 小时两档 | R24/R25 |
| 缓存计量 | OpenAI 暴露 `cached_tokens`、`cache_write_tokens`，建议按用户/工作区/天统计命中率 | R25 |
| 模型路由 | RouteLLM：用偏好数据训练路由器在强/弱模型间选择，某些场景成本降低 2 倍以上而不损质量 | R43 |
| 成本上限 | BigQuery on-demand 只能靠每日配额硬限制；按扫描 TiB 计费 | R33 |
| 长任务 | 子代理回传 1–2k tokens；compaction 降低重复上下文 | R22 |
| 流式 | 仓库 `ModelContract` 已有 `model_stream`（D93）；MCP 有 progress/cancellation 模式 | 仓库/R5 |

### 8.2 建议 [I]

| 层 | 手段 | 预期收益 | 风险 |
| --- | --- | --- | --- |
| 语义缓存 | 规范化问题 + 语义版本 + ACL 作为键，缓存"计划"而非"答案" | 高（重复问题多） | 口径变更后脏读；必须绑定 `semantic_version` |
| 结果缓存 | 按 (SQL 哈希, as-of, 主体) 缓存结果摘要 | 中高 | 数据新鲜度；需 TTL + 显式刷新 |
| 预聚合/物化 | 高频指标走物化视图/语义层 | 高 | 维护成本；口径漂移 |
| 模型路由 | 规划/澄清用小模型，SQL 生成/验证用强模型 | 中 | 路由错误导致质量下降；需按任务评测 |
| 提示缓存 | schema/语义前缀稳定化、工具顺序确定 | 中高 | 前缀一变全失效 |
| 流式 | 先出计划/进度，再出结果 | 体验 | 不能改善总时延 |

- **[I] 成本预算必须是一等字段。** 现有 `ExecRequest` 只有超时，`Capabilities` 没有成本类；建议在 cell manifest 中声明 `budget{ tokens, usd, wall_ms, bytes_scanned, rows }`，由运行时扣减并在耗尽时走 fallback，而不是让模型"自己注意节省"。

---

## 9. 三栏划分：AgentOS / DataAgent / 共同契约

> 判据：**AgentOS 提供"谁能运行、在哪里运行、以什么上限运行、如何被观察"；DataAgent 提供"数据是什么意思、什么算对"；契约是两者之间唯一的窄腰。**
> "现有对应物"列给出仓库中已存在的 trait/字段，便于直接落位；标 `缺` 表示需要新增。

| # | 能力域 | 应由 AgentOS 提供 | 应由 DataAgent 提供 | 共同定义契约 | 现有对应物 |
| --- | --- | --- | --- | --- | --- |
| 1 | 会话与回合 | 创建/推进/恢复/归档、跨宿主交接、推进权租约 | 任务完成条件、证据清单、as-of、可复现状态 | 会话快照需含 `semantic_version`/`as_of`/`evidence_ids` | `SessionContract`、`HandoffKernel`、`LeaseStore` |
| 2 | 执行循环与规划 | loop 边界、取消、超时、子代理派生留痕 | 分析计划 schema、假设、方法选择、停止条件 | `PlanStep` schema + 子代理回传上限 | `iface-loop`、`TraceSink.record_branch` |
| 3 | 模型调用 | 调用/流式/会话幂等、能力声明、路由与降级 | 任务级模型要求（上下文、工具调用、结构化输出）、领域 few-shot | `ModelRequirement`（min_context、tools、json_schema、latency_class） | `ModelContract`、`model_stream`、`capabilities` |
| 4 | 工具注册与 MCP | 注册/列出/调用/中止、装配回滚、传输与授权、命名消歧 | 语义工具（指标查询、值检索、SQL 执行）、返回证据 | `ToolDescriptor` 扩展：`data_scope`、`cost_model`、`evidence_type`、`side_effect` | `ToolContract`、`ToolStaging`、`mint mcp` |
| 5 | Skills/提示资产 | 装载、渐进披露、版本与作用域、权限提示 | 具体 `SKILL.md`（问数流程、口径解释、失败处理） | frontmatter（name/description）+ `eval_refs` + `requires` | `mint kind=skill`、`[provides] skills` |
| 6 | 上下文组装 | 组装/重建/留痕、compaction、工具结果清理、预算执行 | schema/语义注入策略、证据优先级、领域截断规则 | `ContextPolicy`（各段配额、优先级、可丢弃性） | `ContextContract`、`TraceSink` |
| 7 | 记忆与会话状态 | 记忆存储、TTL、作用域、加密 | 业务事实候选（pending/verified）、失效条件、冲突处理 | `MemoryRecord{type, scope, ttl, source, confidence_basis}` | `memory` 能力类、`SessionContract` |
| 8 | 检索基础设施 | 通用索引/搜索接口、权限过滤钩子、新鲜度 | 类型化索引（表/列/值/指标/规则/历史 SQL）、ACL 继承 | `RetrievalHit{object_id, version, acl, as_of, score, truncated}` | `缺`（建议新增 `iface-retrieval`） |
| 9 | 语义层/指标 | 版本化存储、审批流、发布状态机 | 指标定义、维度、时间、规则、冲突解决 | `SemanticRevision` + `PublishState` | `ReviewVerdict` + `store` |
| 10 | NL2SQL/查询计划 | 执行沙盒、策略闸门、取消 | 方言、绑定、成本估算、有界修复、解释 | `QueryPlan{bound_objects, semantic_version, sql, params, cost_estimate}` | `ExecBackend` + `PolicyContract` |
| 11 | SQL/代码执行 | 沙盒、文件系统、网络、资源配额、只读挂载 | 语句白名单、扫描量上限、结果行数、只读账号 | `ExecutionRequest{identity, limits{cpu,mem,net,bytes}, timeout}` + `ExecutionReceipt` | `ExecBackend`、`ExecRequest`（缺配额） |
| 12 | 权限判定 | 判决、egress、委派上限、审计 | 数据权限矩阵（行列/值/导出/跨境）、purpose | `DataAccessRequest{subject, object, columns, row_filter, purpose}` | `PolicyContract`、`check_egress`、`delegation_limits` |
| 13 | 审批/HITL | 阻塞通道、超时默认拒绝、审阅位、UI 承载 | 风险分级、审阅材料（口径/SQL/影响面） | `ApprovalRequest` 扩展 `risk_class` + `evidence_bundle` | `request_approval`、`ReviewVerdict` |
| 14 | 审计与 trace | 留痕、导出、采样、脱敏、OTel 映射 | 领域字段（sql/plan/as_of/row_count/bytes_billed） | span 属性词典 + 脱敏策略 | `TraceSink`、`AuditSink`、OTel semconv |
| 15 | 评测 | harness、数据集存储、回归门禁、报告 | 题集、业务断言、golden SQL/结果、切片 | `EvalCase{fixture, subject, expected, tolerance, budget}` | `cases.json` 约定、`mint` 生命周期 |
| 16 | 成本预算 | 计量（token/时长/字节）、限额、告警 | 查询成本模型、预聚合、缓存键设计 | `CostBudget` + `CostReceipt` | `缺`（Capabilities 无成本类） |
| 17 | Artifact/渲染 | 存储、版本、权限、引用、分享 | 表格/图表/报告模板、公式模式、刷新策略 | `ArtifactManifest{kind, source_query, refresh, formula_mode}` | `artifact_manifest`（kernel host） |
| 18 | 渠道适配 | 身份透传、卡片渲染、文件上传下载 | 渠道特定结果形态（Block Kit 摘要、Sheet 公式、嵌入式快照） | `ChannelCapability{latency, interactive, recompute, auth_mode}` | `缺` |
| 19 | 连接器 | 凭据保管、网络出口、审计 | 方言、元数据抓取、采样、快照 | `SourceProfile`（见 10.3） | `mint mcp` + `secrets` |
| 20 | 打包与分发 | kind/registry/兼容矩阵/签名 | cell 组合（preset）、领域包、迁移 | `cell.toml` + lock + digest | `mint.toml`、`compat` |
| 21 | 领域资产治理 | 审批与版本机制 | ontology/指标/规则/题集的 owner 与生命周期 | 发布状态机 + 回滚 | `ReviewVerdict` |
| 22 | 注入防线 | 沙盒、出口管制、审批、检测钩子 | 内容标记（spotlighting）、表名/单元格转义、结果最小化 | 检索结果的 `trust_label` | `PolicyContract` + `ContextContract` |

**边界判断的三条经验规则** [I]：
1. 如果一件事的正确答案与"客户业务口径"有关 → DataAgent。
2. 如果一件事的正确答案与"安全/资源/身份"有关 → AgentOS。
3. 如果两边都必须知道 → 只共享 schema 与错误码，不共享实现。

---

## 10. 能力单元 manifest 字段建议

### 10.1 设计原则

- 与仓库现有 `mint.toml` 对齐（`[package]`/`[requires]`/`[provides]`/`[capabilities]`），**只增不改**，避免出现第二套清单。
- 每个字段必须能被至少一个消费者使用：安装器（校验/展示）、编排器（路由/预算）、执行器（权限/沙盒）、观测（trace/评测）、审阅 UI。没有消费者的字段不进 manifest。
- 声明式优先：能声明的不要运行时猜；不能声明的（如"结果是否正确"）必须挂评测集，而不是写形容词。

### 10.2 字段表

| 字段 | 类型 | 必填 | 为什么必需 | 主要消费者 |
| --- | --- | --- | --- | --- |
| `cell.id` | string（`da07.nlsql`） | 是 | 稳定标识，用于依赖、trace、评测与缓存键；改名即破坏兼容 | 安装器/编排/观测 |
| `cell.version` | semver | 是 | 语义化版本 + 兼容矩阵的基础；行为变更必须升版 | 安装器/兼容检查 |
| `cell.kind` | `cell`/`domain-pack`/`preset`/`app` | 是 | 决定安装布局与是否可发布（对齐 mint `Kind`） | 安装器 |
| `cell.title` / `description` | string | 是 | 模型按 description 触发（Skills 事实），也是市场展示；必须含"何时不用" | 模型/用户/市场 |
| `cell.owner` / `status` | string / `draft|preview|stable|deprecated` | 是 | 责任人与成熟度；避免"草案被当稳定依赖" | 治理/市场 |
| `io.inputs` / `io.outputs` | JSON Schema `$ref` | 是 | 结构化输入输出是跨语言、跨宿主复用的前提（MCP `inputSchema/outputSchema`） | 编排/校验/UI |
| `io.result_type` | `answer|artifact|evidence|plan` | 是 | 决定交付渲染与是否需要复算；避免"返回一段文字"冒充分析结果 | 交付层 |
| `io.determinism` | `deterministic|seeded|nondeterministic` | 是 | 决定能否缓存、能否进 Sheets/Excel 公式、能否作为证据 | 缓存/交付/审计 |
| `deps.cells` / `deps.tools` / `deps.models` | 版本约束列表 | 是 | 组合与替换的最小单位；缺依赖必须安装期失败而非运行期崩 | 安装器/编排 |
| `deps.data_sources` | `SourceProfile` 引用 | 条件 | 数据源方言与能力决定 SQL 生成与成本估算 | 规划/执行 |
| `permissions.fs/net/exec/env/secrets/model/ui/memory` | 与 mint `[capabilities]` 同构 | 是 | 安装期展示 + 运行期强制；已有九类，直接复用 | 安装器/沙盒/策略 |
| `permissions.data_scope` | `{catalog, tables, columns, row_filter, subject}` | 是 | 只读账号仍可越权读；数据范围必须在查询改写层强制 | 策略/执行 |
| `permissions.side_effect` | `read|compute|write|external_send` | 是 | 决定审批与沙盒等级（对齐 `destructiveHint`、`effect_for_op`） | 策略/审批 |
| `permissions.egress` | 域名/协议白名单 | 是 | 致命三要素的"对外通信"闸门；默认拒绝 | 策略/网络 |
| `budget.tokens/usd/wall_ms/bytes_scanned/rows` | 数值 + 单位 | 是 | 成本攻击与超时的主要防线；无预算的 cell 不应上线 | 执行/计量 |
| `budget.on_exhausted` | `fail|partial|fallback` | 是 | 预算是常态而非异常，必须定义耗尽行为 | 编排 |
| `sla.latency_p50/p95` | ms | 是 | 交付形态反向要求（嵌入式/Sheets 与报告不同） | 路由/交付 |
| `sla.success_rate` / `sla.freshness` | 比率 / 时长 | 是 | 让"可用"可被验收，而不是靠感觉 | 评测/运营 |
| `quality.metrics` | `[{name, threshold, slice}]` | 是 | 准确率必须分切片（按问题类型/表/权限）声明 | 评测/门禁 |
| `eval.dataset` / `eval.cases` / `eval.baseline` | 引用 + 版本 | 是 | 没有评测集的 cell 不可升级为 stable | CI/回归 |
| `fallback.chain` | `[{condition, to, user_note}]` | 是 | 失败是常态：语义计划→NL2SQL→澄清→带限制回答 | 编排 |
| `observability.spans` | span 名列表 | 是 | 保证 trace 结构一致，才能跨 cell 聚合 | 观测 |
| `observability.attributes` | 必录属性（`gen_ai.*`/`mcp.*`/`data.*`） | 是 | 缺字段就无法复盘（见 4.2） | 观测/审计 |
| `observability.redaction` | 规则 | 是 | 结果含 PII/凭据时必须脱敏后入 trace | 合规 |
| `evidence.contract` | 需返回的证据项 | 是 | "答案 + 证据"是 DataAgent 与通用 agent 的分界 | 交付/审阅 |
| `compat.api` / `compat.mcp` / `compat.manifest` | 版本范围 | 是 | 协议演进快（MCP 2026-07-28 已破坏性变更），必须显式声明 | 安装器 |
| `governance.review` / `changelog` / `digest` | 引用 + 哈希 | 是 | 供应链与责任链；与 Mint 的 digest 机制一致 | 治理/分发 |

### 10.3 三个跨 cell 的公共 schema（建议独立成契约包）

| Schema | 关键字段 | 为什么独立 |
| --- | --- | --- |
| `SourceProfile` | source_id、dialect、结构指纹、表/列/约束、采样策略、完整性标记、采集时间、授权范围 | 连接器与 SQL 生成、成本估算共享；不应由每个 cell 自定义 |
| `QueryPlan` | 绑定对象、语义版本、时间解释、参数、join 路径、SQL/DSL、成本估算、待澄清项 | 语义层与执行层之间唯一的可审阅产物 |
| `ResultArtifact` | 查询/快照 ID、schema、行数、截断标记、digest、受控引用、权限、统计摘要 | 交付与审计共享；决定"能否复算" |

### 10.4 示例（节选）

```toml
[cell]
id = "da07.nlsql"
version = "0.3.0"
kind = "cell"
title = "受控 NL2SQL"
description = "把已绑定指标/维度的问题编译为只读 SQL 并执行。仅在语义计划无法覆盖时使用；无行级权限或跨租户问题时不要使用。"
owner = "data-platform"
status = "preview"

[io]
inputs = "schema://da07/query_request.v2.json"
outputs = "schema://da07/query_result.v3.json"
result_type = "evidence"
determinism = "seeded"

[deps]
cells = ["da05.semantic@^0.2", "da06.retrieval@^0.1"]
tools = ["sql.execute@^1"]
data_sources = ["source://warehouse/main"]

[permissions]
fs.read = []
net = []
exec = ["sql.execute"]
env = ["WAREHOUSE_DSN"]
secrets = ["warehouse_ro"]
model = true
memory = ["task"]
data_scope = { catalog = "analytics", tables = "allowlist://da07/tables.json", row_filter = "rls:subject", subject = "user" }
side_effect = "read"
egress = []

[budget]
tokens = 60000
usd = 0.25
wall_ms = 45000
bytes_scanned = "20GiB"
rows = 50000
on_exhausted = "partial"

[sla]
latency_p50 = 3500
latency_p95 = 9000
success_rate = 0.97
freshness = "15m"

[quality]
metrics = [
  { name = "execution_accuracy", threshold = 0.82, slice = "golden_sql" },
  { name = "result_match", threshold = 0.75, slice = "business_assertion" },
]

[eval]
dataset = "eval://da07/golden@2026-10"
cases = "cases.json"
baseline = "0.3.0-rc.2"

[fallback]
chain = [
  { condition = "no_semantic_plan", to = "da07.nlsql", user_note = "使用受控 SQL 生成" },
  { condition = "ambiguous_binding", to = "hitl.clarify", user_note = "需要确认口径" },
  { condition = "budget_exceeded", to = "answer.partial", user_note = "已达查询预算，返回部分结果" },
]

[observability]
spans = ["invoke_agent", "plan", "execute_tool"]
attributes = ["gen_ai.request.model", "gen_ai.usage.input_tokens", "data.sql", "data.as_of", "data.bytes_billed", "data.row_count"]
redaction = "pii:mask"
```

### 10.5 与现有清单的映射

| 建议字段 | 现有落点 | 处理方式 |
| --- | --- | --- |
| `cell.id/version/kind/title/description` | `mint.toml [package]` | 直接复用，`kind` 增加 `cell`/`domain-pack` 子类 |
| `deps.*` | `[dependencies]`、`[requires] api` | 复用；新增 cell 级依赖 |
| `permissions.*` | `[capabilities]` 九类 + `reason` | 复用；新增 `data_scope`/`side_effect`/`egress` |
| `budget/sla/quality/eval/fallback` | 无 | 新增段；建议进 `mint` 校验，缺失则拒绝 `stable` |
| `io.*` | 无（`ComponentContract` 只有 name/version/requires_api） | 新增；`schema.json` 约定可复用 |
| `observability.*` | `TraceSink` 只有 input/branch | 新增属性词典；不改变 trace 存储 |
| `compat.*` | `[requires] api`、`compat` 模块 | 扩展 `mcp`/`manifest` 版本 |
| `governance.digest` | Mint 制品 digest | 复用 |

- **[I] 不要新增第二套清单格式。** 仓库已有 `mint.toml`、`schema.json`、`bundle.json`、`cases.json` 四件套；能力单元 manifest 应是 `mint.toml` 的扩展段，否则安装器、hub、CI 都要改两遍。
- **[I] `cases.json` 已经在做"评测 + 安装生命周期"混合断言**（level L0、driver、expect、covers）。建议把业务评测用例放独立 `eval/`，`cases.json` 只保留安装/分发断言，避免"安装通过 = 质量通过"的误读。[F: 仓库 `cases.json`；I: 拆分建议]

---

## 11. 事实 / 推断 / 不确定项

### 11.1 明确属于事实（可引用）

- Skills 三级披露与 token 量级、`SKILL.md` 字段约束、API 侧 Skills 沙盒无网络。[R1]
- MCP 2026-07-28 无状态化、`_meta`、MRTR、`ttlMs/cacheScope`、工具字段与 annotations 不可信。[R4/R5/R6]
- OpenAI 插件形态、`_meta` 字段、三个 `*Hint` 必填、结果 `_meta` 不进模型上下文。[R9/R10/R12]
- OTel GenAI 的 `plan`/`execute_tool`/`load_skill` span 与 `gen_ai.skill.*` 属性。[R15/R16]
- LangSmith 25k runs/trace；Braintrust span 类型；Langfuse observation/trace/session 模型。[R17–R19]
- Chroma 18 模型 context rot 结论。[R21]
- DuckDB 默认 `enable_external_access=true`；SQLite `readfile/writefile`；PG `COPY TO PROGRAM` 角色限制；BigQuery 只能靠配额限成本。[R30–R33]
- Spotlighting 与 CaMeL 的实验数字。[R36/R37]
- Sheets 自定义函数的重算与授权限制；Slack 50/100 blocks；Teams MCP/API 插件与动态发现。[R39–R41]
- 仓库 iface 的 trait 清单、`Capabilities` 九类、`ExecRequest` 无配额、`cases.json` 结构。[仓库]

### 11.2 明确属于推断（不可当事实引用）

- 三栏划分的具体归属、manifest 字段集合、预算/时延数值、预算模型百分比。
- "只读 SQL 风险矩阵"的具体攻击路径组合（组件能力是事实，组合利用是推断）。
- "能力单元 = 可插拔 cell"的粒度建议（是否按 DA01–DA12 一模块一 cell，本文不建议）。
- 交付形态的时延预算与"HITL 必须触发"的阈值。
- 对 Mint/Kernel 需要新增字段的判断（属设计建议，需 owner 确认）。

### 11.3 不确定项（单列）

| # | 不确定项 | 现状 | 影响 | 建议动作 |
| --- | --- | --- | --- | --- |
| U1 | MCP 2026-07-28 的实际生态采纳度 | 规范已发布且为破坏性变更，但客户端/服务器需 dual-era 兼容 | 若客户环境仍是 2025-11-25，能力单元不能假设无状态 | 在 `compat.mcp` 声明双版本；按目标宿主实测 |
| U2 | OpenAI "Plugins" 与旧 "Apps SDK" 的迁移边界 | 文档已统一到 Plugins，旧 `_meta` 键仍保留为兼容别名 | 旧集成可能继续工作但不再推荐 | 以 `ui.resourceUri`/`ui.visibility` 为主，旧键仅兼容 |
| U3 | E2B 的隔离底层与启动时延 | 本次仅抓取到产品页与 SDK 文档，未取得 Firecracker/时延原文 | 不能把 E2B 与 Daytona 的隔离强度等同 | 需要一次针对性验证（控制台/文档/压测） |
| U4 | Excel custom functions 的重算语义 | 文档页可访问但正文未抽取成功 | 影响 Excel 交付的"可复算"设计 | 用实测工作簿验证重算与异步行为 |
| U5 | 语义缓存/结果缓存的真实命中率与收益 | 无公开可引用数据 | 成本模型不能承诺收益 | 先在单租户做 A/B，记录命中率与脏读率 |
| U6 | context rot 对新模型的外推 | 报告测试于 2025-07，未覆盖 2026 新模型 | 不能据此设定统一 token 上限 | 用目标模型在目标任务上重测退化曲线 |
| U7 | Kernel 是否需要新增 `iface-retrieval` / 成本预算契约 | 仓库无对应 trait；`ExecRequest` 无配额 | 影响 3.2/8.2 的落地路径 | 先以 cell 层实现，验证 ≥2 消费者后再进 iface |
| U8 | `mint` 是否已有 `iface` kind | 源码 `Kind` 含 `Iface`（D72），但 `packages/kernel-iface/README.md` 写"mint 没有 iface 这个 kind" | 打包方式可能不一致 | 由 Mint owner 澄清并更新文档 |
| U9 | HITL 的"必须触发"阈值 | 无行业统一标准 | 过严导致审批疲劳，过松导致事故 | 用历史事故回放校准阈值 |
| U10 | DA01–DA12 与本表 22 行的映射 | 本文按能力域划分，未逐条映射到 72 个二级能力 | 报告合并时可能出现双重编号 | 在报告附录做一次映射表 |

---

## 12. 引用（访问日期均为 2026-11-01）

| 编号 | 来源 | URL | 用于 |
| --- | --- | --- | --- |
| R1 | Anthropic, Agent Skills overview | https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview | 渐进披露、字段约束、沙盒 |
| R2 | Anthropic, Skill authoring best practices | https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices | 描述写法（未逐段引用） |
| R3 | Anthropic Engineering, Equipping agents with Agent Skills | https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills | 设计背景 |
| R4 | MCP Specification 2026-07-28 | https://modelcontextprotocol.io/specification/2026-07-28 | 协议形态 |
| R5 | MCP Key Changes 2026-07-28 | https://modelcontextprotocol.io/specification/2026-07-28/changelog | 无状态、MRTR、缓存字段 |
| R6 | MCP Tools | https://modelcontextprotocol.io/specification/2026-07-28/server/tools | 工具字段、annotations、安全 |
| R7 | MCP Authorization | https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization | OAuth 2.1、资源指示器 |
| R8 | MCP Elicitation | https://modelcontextprotocol.io/specification/2026-07-28/client/elicitation | 澄清协议与敏感信息 |
| R9 | OpenAI, Plugin architecture | https://developers.openai.com/plugins/concepts/plugins | 插件形态 |
| R10 | OpenAI, Plugin reference | https://developers.openai.com/plugins/reference | `_meta`、annotations、结果分层 |
| R11 | OpenAI, Plugin authentication | https://developers.openai.com/plugins/build/auth | CIMD/DCR/PKCE |
| R12 | OpenAI, Plugin guidelines | https://developers.openai.com/plugins/plugin-guidelines | 描述一致性、destructiveHint |
| R13 | OpenAI, Security & Privacy | https://developers.openai.com/plugins/guides/security-privacy | 注入假设、日志脱敏 |
| R14 | OpenAI, Build skills | https://developers.openai.com/plugins/build/skills | `SKILL.md`、依赖声明 |
| R15 | OTel GenAI semconv（agent spans） | https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-agent-spans.md | span 与属性 |
| R16 | OTel GenAI semconv（MCP） | https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/mcp.md | MCP 属性 |
| R17 | LangSmith, Observability concepts | https://docs.langchain.com/langsmith/observability-concepts | run/trace/thread/trajectory |
| R18 | Langfuse, Data model | https://langfuse.com/docs/observability/data-model | observation/trace/session |
| R19 | Braintrust, Tracing | https://www.braintrust.dev/docs/guides/traces | span 类型 |
| R20 | Arize Phoenix, What are traces | https://docs.arize.com/phoenix/tracing/concepts-tracing | OTel/OpenInference |
| R21 | Chroma, Context Rot（2025-07-14） | https://research.trychroma.com/context-rot | 长度退化实验 |
| R22 | Anthropic, Effective context engineering（2025-09-29） | https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents | 注意力预算、compaction、子代理 |
| R23 | Anthropic, Memory tool | https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool | 文件式记忆 |
| R24 | Anthropic, Prompt caching | https://platform.claude.com/docs/en/build-with-claude/prompt-caching | 0.1×/1.25×/2×、TTL |
| R25 | OpenAI, Prompt caching | https://platform.openai.com/docs/guides/prompt-caching | 95% 折扣、30 分钟/12 小时 |
| R26 | Firecracker README | https://github.com/firecracker-microvm/firecracker | microVM 定位 |
| R27 | gVisor docs | https://gvisor.dev/docs/ | 应用内核隔离 |
| R28 | Daytona, Sandboxes | https://www.daytona.io/docs/en/sandboxes/ | <90ms、TTL/自动停止 |
| R29 | E2B docs | https://e2b.dev/docs | 沙盒 SDK（部分） |
| R30 | DuckDB configuration | https://duckdb.org/docs/2.0/configuration/overview.html | `enable_external_access` 默认值 |
| R31 | SQLite CLI | https://sqlite.org/cli.html | `readfile/writefile` |
| R32 | PostgreSQL COPY | https://www.postgresql.org/docs/current/sql-copy.html | `COPY TO PROGRAM` 与角色 |
| R33 | BigQuery cost best practices | https://cloud.google.com/bigquery/docs/best-practices-costs | 按 TiB 计费、配额 |
| R34 | OWASP LLM Top 10 (2025) | https://genai.owasp.org/llm-top-10/ | LLM01/02/06/10 |
| R35 | Simon Willison, Lethal trifecta | https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/ | 三要素外泄 |
| R36 | Hines et al., Spotlighting | https://arxiv.org/abs/2403.14720 | 注入成功率 >50%→<2% |
| R37 | Debenedetti et al., CaMeL | https://arxiv.org/abs/2503.18813 | 77% vs 84%、capability |
| R38 | LangGraph, Interrupts | https://docs.langchain.com/oss/python/langgraph/interrupts | 持久化暂停/恢复 |
| R39 | Slack, Block Kit | https://docs.slack.dev/block-kit/ | 50/100 blocks |
| R40 | Microsoft, MCP and API plugins | https://learn.microsoft.com/en-us/microsoft-365-copilot/extensibility/overview-api-plugins | 插件 manifest、动态发现 |
| R41 | Google, Sheets custom functions | https://developers.google.com/apps-script/guides/sheets/functions | 重算与授权限制 |
| R42 | Microsoft, Power BI embedded | https://learn.microsoft.com/en-us/power-bi/developer/embedded/embedded-analytics-power-bi | app-owns-data/user-owns-data |
| R43 | Ong et al., RouteLLM | https://arxiv.org/abs/2406.18665 | >2× 成本下降 |
| R44 | MCP Versioning | https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning | modern/legacy/dual-era |
| R45 | Microsoft, Excel custom functions | https://learn.microsoft.com/en-us/office/dev/add-ins/excel/custom-functions-overview | 仅确认页面存在，正文未抽取 |
| R46 | Mint manifest（源码） | `packages/agent-kernel/mint/crates/mint-manifest/src/lib.rs`（Kind:44、Capabilities:501） | 包类型、九类权限 |
| R47 | Kernel iface（源码） | `packages/kernel-iface/iface-{session,store,policy,tool,model,context,env,extension,loop,types}/src` | trait 与字段 |
| R48 | RSI bundle/cases 约定 | `scratch/rsi-build/rsi-iface-data/{bundle.json,cases.json}` | 制品与用例格式 |

---

## 13. 可直接写进报告的 5 条结论

1. **能力单元的"描述"就是路由契约**：Skills 以约 100 tokens 的 `name/description` 做发现，触发后再加载 <5k tokens 正文；DataAgent 的 cell 若不能在一句话里说清"做什么/何时用/何时不用"，就不具备可组合性。[R1]
2. **工具必须自带副作用与开放世界标注，且标注不可信**：MCP 要求 `annotations` 视为不可信输入，OpenAI 把 `readOnlyHint/destructiveHint/openWorldHint` 列为必填；宿主据此决定审批与渲染。DataAgent 应把"读/算/写/外发"四级副作用写进 manifest，而不是靠运维约定。[R6/R10/R12]
3. **MCP 已进入无状态时代**：2026-07-28 移除协议级会话与 `initialize`，每个请求自带版本与能力，跨调用状态须由服务端签发 handle；任何依赖连接状态的能力单元都会在新协议下失效。[R4/R5/R44]
4. **只读 SQL 不是安全边界**：DuckDB 默认允许外部访问、SQLite CLI 可读写文件、PG 可 `COPY TO PROGRAM`（受角色限制）、BigQuery 只能靠配额限成本；必须"沙盒 + 出口管制 + 扫描量上限 + 只读账号"四件套，SQL 关键字审查只能算策略。[R30–R33]
5. **交付形态反向定义拆分**：Sheets 自定义函数不能申请个人数据授权、且只有传入引用区域才重算；嵌入式 BI 要求权限透传与低时延。因此交付层必须产出"可复算产物 + 显式刷新"，而不能假设会话权限与实时模型调用。[R41/R42]

---

## 14. 与现有 DataAgent 模块草案的接口

本文不改变 `DA01–DA12` 的领域划分，只补三件事：

1. **为每个 DA 模块提供一张"横切依赖卡"**：它需要哪些 AgentOS 机制（沙盒/审批/trace/预算）、它对外暴露哪些 cell。
2. **把 DA11（验证与治理）与 DA12（评测与演进）从"模块"提升为"横切门禁"**：它们不该是链路末端的两个模块，而应是每个 cell 的 manifest 字段（`quality`/`eval`/`evidence`）。
3. **把 DA09（交付）拆成"产物生成"与"渠道适配"两层**：前者属 DataAgent，后者属 AgentOS 的 channel adapter，否则每接一个渠道就要改一次分析逻辑。
