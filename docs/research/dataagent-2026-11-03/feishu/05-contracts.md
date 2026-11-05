```yaml
version: v0.1
date: 2026-11-03
status: 设计草案
```

<callout emoji="📌">
**通用性原则**：契约包服务于通用能力，不服务于某个具体项目。具体项目都是建立在通用能力之上的**应用**，例如令才（制度提取与规则审核）、报表问数、合同条款核查。应用选择能力、提供领域资产，但不改变契约。

**进展：**设计草案，尚未创建代码。字段在 S0 实现时校准；校准结果以生成的 schema 为准，本文同步修订。
</callout>


---

## 1. 背景

### 1.1 应用级能力协议

```text
具体应用（令才、报表问数、合同条款核查 …）   ← 选择能力、提供领域资产，不改契约
Agent 工具 / Mint 包接口        ← 由契约包生成 schema
DataAgent 能力层（data / application / governance / operations）
dataagent-contracts
  ├─ core       S0 起：调用封套、数据与证据引用、LifecycleStatus、AccessDecision、ComponentMeta
  ├─ action     S1 起（FDE）：ActionTier、ActionContractRef、EvidencePackageRef、DelegationRef、ApprovalRequestRef
  └─ delivery   S2 起（FDE）：EnvironmentDefaultsRef、DeliveryRef
AgentOS 内核 iface（OS 级原语）
```

- **应用级**：内核 iface 面向 OS 级，即会话、效果等级、审批、委派、事件存储、装配。契约包面向应用级：数据、证据、语义对象怎么引用，能力怎么调用、怎么返回，状态与授权怎么表达。
- **能力协议，**由三部分组成

| 部分 | 回答的问题 | 代表类型 |
|-|-|-|
| 调用协议 | 任意能力怎么调、怎么返回部分完成、未知、需补输入 | `CallContext`、`CapabilityResult`、`Issue`、`Completeness` |
| 数据与证据引用 | 数据、版本、证据怎么寻址、怎么固定、怎么回到原文 | `AssetRef`、`FileRef`、`SourceAnchor`、`EvidenceRef`、`TaskContextRef` |
| 治理词表 | 状态、授权、档位、许可全局只有一种说法 | `LifecycleStatus`、`AccessDecision`、`ActionTier`、`ComponentMeta` |

- **原则：**iface基于git version =  `agent-kernel@f0fa521`， 路径`kernel/iface/src`。

| 契约包 | 内核原语 | 关系 | 阶段 |
|-|-|-|-|
| `CallContext.kernel_session_id / kernel_call_id` | `SessionId`、`CallId`（见 `ApprovalRequest`） | 能力经内核工具调用时携带，供轨迹与审批关联 | S0 |
| `TraceEventRef`（DA04.1） | `StoreContract::append/read`，游标为会话内；内核未向组件开放 | S0 按其接口形状本地实现，内核提供组件事件接口后切换；跨会话索引由应用层自建（附录 A P5） | S0 |
| `AccessDecision` | 内核 guard（单一门、fail-closed） | guard 是经内核调用的执行点，`AccessDecision` 是策略结论；不经内核的路径由 DA12.1 复检（附录 A P2） | S0 |
| `ActionTier` | `EffectLevel{ReadOnly, Advance, SideEffect}` + `ReviewPosition{Input, Plan, ToolParams, FinalResult}` | A0→ReadOnly；A1→Advance + Plan 审查；A2→SideEffect + ToolParams 审查 | S1 |
| `ApprovalRequestRef` | `ApprovalRequest{session, call, summary, timeout_ms}` | 证据包外置为 `EvidencePackageRef`，`summary` 携带其引用（附录 A P3） | S1 |
| `DelegationRef` | `DelegationGrant{grant_id, scope, depth_remaining, expires_at_ms, parent_grant}` | 引用内核 grant，应用层只补业务范围说明 | S1 |
| 等待、接管 | `BlockedOnItem`、`Lease` | DA14.6/14.7 引用内核原语（附录 A P6） | S2 |
| 组合清单 | `AssemblyIntent{session, act, payload}` | 运行时组合参数序列化进 `payload`（附录 A P4） | S1 |

### 1.2 从 DataAgent 到 FDE Agent：

- **S0（DataAgent 期）**：只建 core，支撑通用只读证据闭环（§3.1）。
- **S1（FDE 起步）**：加 action，支持契约下的写动作和审批。
- **S2（FDE 运行与移交）**：加 delivery，支持环境默认版本、部署与交付清单。
- **不变量**：进入 FDE 阶段不修改 core 任何已有字段的含义。所以 S0 产出的 `EvidenceRef`、`SourceAnchor`、`AcceptanceReport`，

### 1.3 平台与应用

| 角色 | 负责 | 不负责 |
|-|-|-|
| 平台（DataAgent 通用能力 + 契约包） | 能力与契约、闭环族、验收机制、版本与治理 | 某个行业或客户的规则、指标、判据 |
| 应用（令才、报表问数等） | 选择闭环族与启用的原子；提供领域资产：规则文本、指标定义、抽取结构、验收判据、样本；交付形态 | 修改 core 契约或新增能力编号 |

领域资产在契约里以通用类型的**实例**出现：一条报销规则是 `SemanticDraft{kind=rule}`，一个经营指标是 `SemanticDraft{kind=metric}`，一份单据字段结构是 `ExtractionSchemaRef` 引用的资产，一套验收口径是 `CriteriaRef`。应用越多，资产越多，但契约不随之变化；这是检验契约是否通用的标准。

---

## 2. 设计规则

### 2.1 准入规则

1. **跨层**：至少两层之间交换的类型才进包；单层内部类型留在该层 `contracts/`。
2. **跨应用**：新增 core 类型或字段，须有至少两个应用或两个闭环族需要；单一应用的结构作为领域资产或扩展字段。
3. **只含类型**：类型定义、枚举、校验约束、序列化；不含行为、存储、模型调用、网络访问。
4. **阶段**：类型归入 core、action 或 delivery，取决于首次使用它的切片。
5. **扩展字段**：`extensions: map[str,json]`，键带应用命名空间，如 `app.lingcai.voucher_type`。通用能力不依赖扩展字段，扩展字段不设必填。
6. **完整度**：进入切片的原子，其输入输出类型须有字段定义。

### 2.2 模块与依赖方向

| 模块 | 内容 | 依赖 |
|-|-|-|
| `core.vocab` | 枚举 | 无 |
| `core.envelope` | 调用封套 | vocab、refs |
| `core.refs` | 引用、版本、锚点 | vocab |
| `core.data` | 表、批次、文档、文档单元、抽取记录 | refs |
| `core.semantics` | 语义草案（规则、指标）、判定、计算结果、证据 | refs、data |
| `core.task` | 任务上下文、轨迹事件、纠正 | refs |
| `core.evaluation` | 判据、评测集、验收报告、指标束 | refs、task |
| `core.governance` | 访问决策、外发决策、组件元数据 | refs、vocab |
| `action.*`（S1） | 见 §4.1 | core |
| `delivery.*`（S2） | 见 §4.2 | core、action |

- 各层能力包只依赖 `dataagent-contracts` 和端口注入的实现，层间不互相导入。
- 契约包不依赖能力包、应用或内核 crate；与内核的对应关系见 §1.1 内核映射表，由适配器实现。

### 2.3 版本与兼容

- 语义化版本；S0 冻结为 `0.1.x`。
- 次版本只追加，0.x 期间同样执行：可新增类型、可选字段、开放枚举值；修改字段含义、删除字段、可选改必填为破坏性变更。
- action 进包为 `0.2.0`，delivery 为 `0.3.0`，均不改动 core。
- 能力包与 Mint 包声明契约包版本范围，声明方式随附录 A P4 定案。
- schema `$id` 含版本，如 `dataagent-contracts/0.1/core/CapabilityResult`。

### 2.4 序列化与命名

| 项 | 约定 |
|-|-|
| 载体 | JSON（UTF-8）；Python、HTTP、MCP 承载同一结构 |
| 字段名 | `snake_case`；可选字段标 `?`，缺省为 `null` 或省略 |
| 标识 | 不透明字符串，带种类前缀，如 `file:…`、`doc:…`、`task:…` |
| 版本化引用 | `VersionedRef`，序列化为 `"<id>@<revision>"` |
| 时间 | RFC 3339，带时区 |
| 大内容 | 经 `AssetRef` 等引用传递；小结构内联，上限见各类型 |
| 枚举 | 封闭枚举遇未知值时反序列化失败；开放枚举的扩展值带命名空间前缀，如 `da02.ambiguous_header` |
| 敏感信息 | 无明文凭据字段；日志与 `Issue.message` 同样适用 |

---

## 3. S0 明细

### 3.1 S0：通用只读证据闭环

**目标**：把文件、文档或记录变成带依据、可验收的结论；只读，不写回源系统。

| 闭环族 | 问题 | 典型输入 | 典型输出 | 应用示例 |
|-|-|-|-|-|
| **判定族** | 记录是否符合规范性条款，依据是什么 | 规范性文本（制度、合同、规程）+ 记录（单据、工单、日志） | 逐条判定（满足/违反/未知/不适用）+ 条款与字段依据 | 令才（制度提取与规则审核）、合同条款核查、合规巡检 |
| **计算族** | 指标或问题在数据上的结果，口径与来源 | 表格、记录 + 指标定义或问题 | 计算结果 + 口径、粒度、过滤、来源 | 文件即席分析、报表问数、经营指标核对 |

```text
                       ┌─ 判定族：文档切分 → 字段抽取 → 规则草拟 → 可判定性/适用性 ─┐
接入解析（骨干）──────┤                                                          ├─ 表达生成 → 执行求值 → 验收 → 报告（骨干）
                       └─ 计算族：表块恢复 → 画像 → 指标定义 → 需求绑定与澄清 ────┘
贯穿（骨干）：轨迹记录、访问与模型外发判定
```

必需原子 51 项，同组其余原子按需启用：

| 部分 | 原子 | 数量 |
|-|-|-|
| **骨干** | 接入：DA01.4.1、01.4.3、01.4.4、01.4.5、01.5.1、01.5.2（按输入类型启用）；轨迹：DA04.1.1–1.3；表达与执行：DA06.3.5、DA07.5.1、07.5.2、DA07.10.1；交付：DA10.3.1、10.3.3；验收：DA11.5.1、11.5.5、11.5.6；访问：DA12.1.1、12.1.4 | 20 |
| **判定族增量** | DA02.8.1、02.8.2；DA02.12.1、02.12.3、02.12.4；DA03.4.3；DA03.15.1–15.4；DA03.16.1–16.4 | 14 |
| **计算族增量** | DA01.4.2、01.4.6；DA02.1.1；DA02.2.1–2.3；DA02.4.1、02.4.3；DA03.4.1；DA06.1.1–1.4；DA06.3.1；DA07.1.3；DA11.2.3；DA10.1.1 | 17 |

### 3.2 S0 core 类型总览

| 模块 | 类型 | 产出（S0） | 消费（S0） | 族 |
|-|-|-|-|-|
| envelope | `CallContext`、`CapabilityResult<T>`、`Issue`、`ExecutionRef`、`Continuation`、`Completeness`、`Budget` | 全部原子 | 全部原子 | 骨干 |
| refs | `VersionedRef`、`AssetRef`、`FileRef`、`SourceAnchor`、`Selector` | DA01.4、DA01.5 | 全部 | 骨干 |
| data | `SchemaRef`、`TableRef`、`DataBatchRef`、`DocumentRef` | DA01.4、DA01.5、DA02.2、DA07.1.3、DA07.5.2 | DA02、DA03、DA06、DA07、DA10、DA11 | 骨干 |
| data | `DocumentUnitRef`、`ExtractedRecordRef`、`FieldValue` | DA02.8、DA02.12 | DA03.4.3、DA06.3.5、DA07.5、DA11.5 | 判定 |
| semantics | `SemanticDraft`、`EvidenceRef` | DA03.4、DA07、DA02.12.3 | DA06、DA07、DA10、DA11.5.5 | 骨干 |
| semantics | `RuleDefinition`、`Assessment<V>` | DA03.4.3、DA03.15、DA03.16、DA07.5 | DA06.3.5、DA07.5、DA10.3、DA11.5.5 | 判定 |
| semantics | `MetricDefinition`、`ComputedResult` | DA03.4.1、DA07.1.3、DA07.5.2 | DA06.1、DA06.3.1、DA10.1.1、DA10.3、DA11.2.3、DA11.5.5 | 计算 |
| task | `TaskContextRef`、`TraceEventRef`、`CorrectionRef` | DA04.1 | 全部（任务关联）、DA11.5（纠正转样本） | 骨干 |
| evaluation | `CriteriaRef`、`EvaluationSetRef`、`AcceptanceReport`、`CaseResult`、`MetricBundle` | DA11.5.1、11.5.5、11.5.6 | DA10.3、S1 的 DA18.7 | 骨干 |
| governance | `AccessDecision`、`EgressDecision`、`ComponentMeta` | DA12.1.1、DA12.1.4 | 全部读取与模型调用；`ComponentMeta` 自 S1 起由 DA05.8、DA18.7 使用 | 骨干 |
| vocab | 见 §3.4 | — | — | 骨干 |

共 36 个类型；`FieldSpec`、`RuleCondition`、`OcrInfo` 等内嵌结构不单独计数。

### 3.3 字段定义

> 类型记法：`str`、`int`、`float`、`bool`、`datetime`（RFC 3339）、`json`（任意 JSON 值）、`list[T]`、`map[str,T]`；`?` 为可选。所有类型可带 `extensions: map[str,json]?`（§2.1 第 5 条），表中不列。

#### 3.3.1 调用封套（`core.envelope`）

调用形式：`invoke(operation, input, CallContext) -> CapabilityResult<T>`。

**`CallContext`**

| 字段 | 类型 | 说明 |
|-|-|-|
| `request_id` | str | 每次调用唯一；重试沿用同一值 |
| `scope_ref` | str | 租户/项目作用域 |
| `authorization_ref` | str | 适用的 `AccessDecision.decision_id` 或策略绑定；引用本身不授予权限 |
| `requester_ref` | str? | 请求者。S0 单用户可省略；S1 起与 Agent 身份取权限交集 |
| `task_ref` | VersionedRef? | 任务及其修订（`TaskContextRef`） |
| `kernel_session_id` | str? | 经内核调用时的 `SessionId` |
| `kernel_call_id` | str? | 经内核调用时的 `CallId` |
| `deadline` | datetime? | 超时点 |
| `budget` | Budget? | 资源预算 |
| `expected_revision` | str? | 写入类能力的乐观并发检查 |
| `idempotency_key` | str? | 副作用请求的去重键；S0 只读，通常不用 |

**`Budget`**：`max_seconds?: int`、`max_rows?: int`、`max_tokens?: int`、`max_cost?: float`、`currency?: str`。超出时返回 `partial` 或 `failed`，原因写入 `Completeness.reason`。

**`CapabilityResult<T>`**

| 字段 | 类型 | 说明 |
|-|-|-|
| `status` | CapabilityStatus | 能力运行状态，不代表业务结论正确 |
| `data` | T? | 业务输出；`failed` 时可为空 |
| `issues` | list\[Issue\] | 错误、歧义、缺口 |
| `execution_ref` | ExecutionRef? | 实际发生的调用 |
| `provenance` | list\[VersionedRef\] | 实际读取的输入版本 |
| `completeness` | Completeness? | 处理范围的完整性 |
| `continuation` | Continuation? | 分页、作业或订阅的后续入口 |

约束：
- `partial` ⇒ `issues` 非空，或 `completeness.extent` 不为 `complete_in_declared_scope`。
- `pending` ⇒ `continuation.job_ref` 必填。
- `needs_input` ⇒ 至少一个 `Issue` 带 `suggested_action` 或 `alternatives`；计算族的口径澄清（DA06.1.3/1.4）用此状态。
- 空结果、权限拒绝、解析失败分别表达，不共用空 `data`。

**`Issue`**

| 字段 | 类型 | 说明 |
|-|-|-|
| `code` | str（开放） | 标准错误码（§3.4 `StandardErrorCode`），或带命名空间的能力码，如 `da02.ambiguous_header` |
| `severity` | Severity | `info / warning / error` |
| `message` | str | 人可读说明，不含敏感值 |
| `target` | str? | 出问题的对象或区域 |
| `source_anchor` | SourceAnchor? | 原文位置 |
| `retryable` | bool | 原样重试是否可能成功 |
| `suggested_action` | str? | 下一步：补数、换实现、澄清等 |
| `alternatives` | list\[json\]? | 候选值或候选解释 |

**`ExecutionRef`**

| 字段 | 类型 | 说明 |
|-|-|-|
| `invocation_id` | str | 调用实例标识，DA04.1.2 据此记录 |
| `operation` | str | operation 名，如 `extract_fields_to_schema` |
| `capability_id` | str | 能力编号，如 `DA02.12.1` |
| `implementation_ref` | str | 实现组件与版本，如 `dataagent-data/extraction@0.1.3#llm-structured` |
| `input_versions` | list\[VersionedRef\] | 实际读到的输入版本 |
| `started_at` | datetime | — |
| `finished_at` | datetime? | — |
| `receipt_ref` | str? | 后端回执；模型调用记录模型与提示版本 |

**`Continuation`**：`cursor?: str`、`job_ref?: str`、`subscription_ref?: str`、`resume_condition?: str`。

**`Completeness`**

| 字段 | 类型 | 说明 |
|-|-|-|
| `extent` | CompletenessExtent | 见 §3.4 |
| `declared_scope` | str | 声明的处理范围，如“文档第 1–48 页”“工作表全部表块” |
| `observed` | map\[str,int\]? | 实际处理量，如 `{"pages": 46, "units": 212}` |
| `reason` | str? | 未完成原因 |
| `snapshot_consistent` | bool? | 读取期间源是否一致 |

#### 3.3.2 引用与锚点（`core.refs`）

**`VersionedRef`**：`id: str`、`revision: str`，序列化为 `"<id>@<revision>"`。

**`AssetRef`**

| 字段 | 类型 | 说明 |
|-|-|-|
| `id` | str | 稳定标识 |
| `kind` | str（开放） | `file / document / document_unit / table / batch / extracted_record / semantic_draft / computed_result / report / evaluation_set …` |
| `scope_ref` | str | 作用域 |
| `revision` | str | 资产修订 |
| `resolver` | str | 解析器标识，受权限保护 |
| `locator` | str | 解析描述；非明文凭据，非公开下载链接 |
| `digest` | str? | 内容校验，如 `sha256:…` |
| `media_type` | str? | MIME 类型 |

`revision`（资产修订）、`ResourceRef.source_version`（源端版本，S0 不用）、`digest`（内容校验）、`effective_time`（业务生效时间，见 `SemanticDraft`）分别表达。

**`FileRef`**：`AssetRef` 字段，加 `filename?: str`、`size_bytes?: int`、`content_digest: str`（必填）。受控存储中的原件；S0 的文件输入均为 `FileRef`。

**`SourceAnchor`**

| 字段 | 类型 | 说明 |
|-|-|-|
| `source_ref` | str | 原件或文档 id |
| `source_revision` | str | 须可回到同一版本 |
| `selector` | Selector | 位置 |
| `extraction_ref` | str? | 产生锚点的调用（`ExecutionRef.invocation_id`） |

**`Selector`**：按 `kind` 区分的联合类型。

| `kind` | 字段 | 用途 |
|-|-|-|
| `pdf_bbox` | `page: int`、`bbox: [x0, y0, x1, y1]`、`unit: "pt"` | 条款、扫描页位置（判定族） |
| `pdf_text_span` | `page: int`、`char_start: int`、`char_end: int` | 文本型 PDF 原文区间（判定族） |
| `text_span` | `unit_ref: str`、`char_start: int`、`char_end: int` | 文档单元内区间（判定族） |
| `json_pointer` | `pointer: str` | JSON 记录字段（两族） |
| `excel_cell` | `sheet: str`、`range: str` | 工作表单元格或区域（计算族） |
| `record_key` | `keys: map[str,json]` | 按键定位表中的行（计算族） |

#### 3.3.3 数据与文档（`core.data`）

**`SchemaRef`**

| 字段 | 类型 | 说明 |
|-|-|-|
| `asset` | AssetRef | — |
| `fields` | list\[FieldSpec\] | `FieldSpec = {field_id, name, path, value_type, nullable?, unit?}`；`path` 为源路径，如 JSON Pointer 或列位置 |
| `keys` | list\[list\[str\]\] | 候选键（`field_id` 列表）；复合键保留全部列 |
| `inference_basis` | `declared / inferred / confirmed` | 源端声明、样本推断或人工确认 |

**`TableRef`**：`asset: AssetRef`、`schema_ref: VersionedRef`、`data_ref: str`、`row_identity?: list[str]`、`source_map_ref?: str`、`transform_ref?: str`。计算族中用于 DA01.4/DA02.2 的规整表和 DA07 的结果表。

**`DataBatchRef`**

| 字段 | 类型 | 说明 |
|-|-|-|
| `asset` | AssetRef | — |
| `schema_ref` | VersionedRef? | — |
| `source_ref` | str | 来源文件或资源 |
| `row_count` | int | — |
| `completeness` | Completeness | — |
| `cursor` | str? | 后续读取 |
| `inline_rows` | list\[map\[str,json\]\]? | 内联上限 500 行，超出只给引用 |

**`DocumentRef`**

| 字段 | 类型 | 说明 |
|-|-|-|
| `asset` | AssetRef | — |
| `original_ref` | VersionedRef | 原件 `FileRef` |
| `content_type` | `pdf_text / pdf_scanned / image / json / text` | 封闭枚举 |
| `blocks_ref` | str | 文字块与坐标 |
| `page_count` | int? | — |
| `ocr` | OcrInfo? | OCR 产出：`{engine_ref, engine_version, mean_confidence, low_confidence_pages: list[int]}` |

**`DocumentUnitRef`**（判定族）

| 字段 | 类型 | 说明 |
|-|-|-|
| `asset` | AssetRef | — |
| `parent_document_ref` | VersionedRef | — |
| `unit_type` | `chapter / section / clause / item / table / paragraph` | 开放枚举 |
| `ordinal_path` | str | 文档内层级路径，如 `"3.12.2"` |
| `title` | str? | — |
| `content_ref` | str | 单元正文 |
| `anchors` | list\[SourceAnchor\] | 至少一个；跨页时多个 |
| `context_refs` | list\[str\] | 父章节、引用条款等上下文单元 |

**`ExtractedRecordRef`**（判定族）

| 字段 | 类型 | 说明 |
|-|-|-|
| `asset` | AssetRef | — |
| `document_ref` | VersionedRef | 被抽取的文档 |
| `target_schema_ref` | VersionedRef | 抽取结构版本（DA02.12.4 `ExtractionSchemaRef`），由应用提供 |
| `fields` | list\[FieldValue\] | 内联；超过 200 个字段改用 `values_ref` |
| `values_ref` | str? | 外置引用 |
| `issues` | list\[Issue\] | 记录级问题 |

**`FieldValue`**

| 字段 | 类型 | 说明 |
|-|-|-|
| `field_id` | str | 目标结构字段 |
| `status` | FieldValueStatus | `extracted / missing / conflict / low_confidence` |
| `value` | json? | `missing` 时为空 |
| `value_type` | str | `string / number / date / money / bool / enum …` |
| `unit` | str? | 币种、计量单位 |
| `confidence` | {score: float, method: str}? | 带方法说明的估计，不作认证门槛 |
| `evidence` | list\[SourceAnchor\] | `extracted` 时至少一个 |
| `alternatives` | list\[json\]? | `conflict` 时的候选值 |

#### 3.3.4 语义、判定、计算与证据（`core.semantics`）

**`SemanticDraft`**：DA03 产出，DA06/DA07 消费。S0 使用 `kind = rule`（判定族）和 `kind = metric`（计算族）。

| 字段 | 类型 | 说明 |
|-|-|-|
| `draft_id` | str | — |
| `revision` | str | — |
| `kind` | `rule / metric / entity / relationship / dimension` | 后三种的字段随后续切片补 |
| `definition` | RuleDefinition \| MetricDefinition | 按 `kind` 取结构 |
| `scope_ref` | str | — |
| `sources` | list\[SourceAnchor\] | 定义出处（条款原文、口径说明、历史报表），至少一个 |
| `status` | LifecycleStatus | S0 为 `draft` 或 `validated` |
| `effective_time` | {from?: datetime, to?: datetime}? | 业务生效时间 |
| `unresolved` | list\[str\] | 未决问题 |

**`RuleDefinition`**（判定族）

| 字段 | 类型 | 说明 |
|-|-|-|
| `statement` | str | 规则原文或忠实转述 |
| `conditions` | list\[RuleCondition\] | `RuleCondition = {condition_id, text, referenced_fields: list[str], anchors: list[SourceAnchor]}` |
| `combination` | str | 条件组合，如 `"all(c1, c2) and not c3"`，只引用 `condition_id` |
| `exceptions` | list\[{text, anchors}\] | 例外条款 |
| `applicability_ref` | str? | DA03.16 适用范围 |
| `precondition_refs` | list\[str\] | DA03.16 前置条件 |
| `decidability_ref` | str? | DA03.15 判定结果 |

**`MetricDefinition`**（计算族）

| 字段 | 类型 | 说明 |
|-|-|-|
| `statement` | str | 业务口径表述 |
| `measure` | {field\_ref: str, aggregation: Aggregation} | 度量字段与聚合 |
| `filters` | list\[{text, referenced\_fields: list\[str\]}\] | 口径过滤 |
| `dimensions` | list\[str\] | 允许的切分维度 |
| `time` | {time\_field: str, grain?: str, calendar\_ref?: str}? | 时间字段、粒度、业务日历 |
| `unit` | str? | — |
| `grain` | str | 结果粒度，如“每月每门店” |
| `additivity` | `additive / semi_additive / non_additive` | 可加性 |
| `depends_on` | list\[VersionedRef\] | 依赖的基础指标 |
| `certified_ref` | str? | 外部认证定义，经 DA06.8 委托编译（S0 不启用） |

两类定义均不含可执行表达式；表达式与 SQL 由 DA06.3 生成，类型为应用层 `ExecutableSpec`。

**`Assessment<V>`**（判定族）：可判定性、适用性、规则求值、冲突检查共用。

| 字段 | 类型 | 说明 |
|-|-|-|
| `assessment_id` | str | — |
| `target_ref` | VersionedRef | 被判定对象，如规则或“规则 × 记录” |
| `verdict` | V | 能力定义的封闭枚举 |
| `basis_refs` | list\[str\] | `EvidenceRef.id` |
| `dependency_refs` | list\[VersionedRef\] | 依赖的原文、映射、语义、工具、模型版本；任一变化即重评（DA03.15.4） |
| `unknowns` | list\[str\] | 判定缺少的信息 |
| `next_actions` | list\[str\] | 补证、等待或转人工 |

| 能力 | `V` 取值 |
|-|-|
| DA03.15 可判定性 | `auto / needs_evidence / needs_human` |
| DA03.16 适用性 | `applies / not_applies / unknown` |
| DA07.5 规则求值 | `satisfied / violated / unknown / not_applicable` |

`unknown` 保留为 `unknown`，进入补证或人工流程（DA03.16.4）。

**`ComputedResult`**（计算族）

| 字段 | 类型 | 说明 |
|-|-|-|
| `result_id` | str | — |
| `target_ref` | VersionedRef | 指标定义或问题 |
| `form` | `scalar / table` | — |
| `value` | json? | `scalar` 时的值 |
| `table_ref` | VersionedRef? | `table` 时的结果表 |
| `unit` | str? | — |
| `grain` | str | 实际结果粒度 |
| `filters_applied` | list\[str\] | 实际生效的过滤 |
| `time_range` | {from?: datetime, to?: datetime}? | — |
| `semantic_versions` | list\[VersionedRef\] | 指标定义版本 |
| `assumptions` | list\[str\] | 澄清前采用的默认假设 |
| `certified` | bool | 是否经认证定义编译；S0 为 `false` |
| `evidence_refs` | list\[str\] | 至少含一条 `computation_result` |
| `completeness` | Completeness | 计算覆盖的数据范围 |

**`EvidenceRef`**（两族共用）

| 字段 | 类型 | 说明 |
|-|-|-|
| `id` | str | — |
| `evidence_type` | EvidenceType | `source_text / extracted_value / computation_result / execution_receipt / human_judgment` |
| `source_anchors` | list\[SourceAnchor\] | 原文或数据位置 |
| `value` | json? | 小值内联 |
| `obtained_by` | str | `ExecutionRef.invocation_id` 或人工主体 |
| `verification_ref` | str? | 核验记录 |

S1 的 `EvidencePackageRef` 聚合 `EvidenceRef`。

#### 3.3.5 任务与轨迹（`core.task`）

**`TaskContextRef`**

| 字段 | 类型 | 说明 |
|-|-|-|
| `task_id` | str | — |
| `revision` | str | 口径或数据变化时生成新修订 |
| `parent_revision` | str? | — |
| `selected_refs` | list\[VersionedRef\] | 选用的输入、语义定义、判据、引擎版本 |
| `assumptions` | list\[str\] | 显式假设 |
| `policy_refs` | list\[str\] | 适用策略 |
| `unresolved` | list\[str\] | 未固定项 |

**`TraceEventRef`**：按内核 `StoreContract` 接口形状存储；内核提供组件事件接口后写入内核（附录 A P5）。

| 字段 | 类型 | 说明 |
|-|-|-|
| `event_id` | str | 去重键 |
| `task_ref` | VersionedRef | — |
| `event_type` | TraceEventType | `task_state / invocation / correction / decision / note` |
| `timestamp` | datetime | — |
| `actor_ref` | str | 人或 Agent 主体 |
| `payload_ref` | str | 受控保存的载荷 |
| `invocation_ref` | str? | 对应的 `ExecutionRef.invocation_id` |
| `kernel_call_id` | str? | 对应内核调用的 `CallId`；经内核调用时与 `TraceSink` 写前留痕关联 |
| `kernel_cursor` | int? | 写入内核存储后返回的游标；本地实现时为空 |

**`CorrectionRef`**：继承 `TraceEventRef`（`event_type = correction`），加 `target_ref: VersionedRef`、`field_id?: str`、`old_value?: json`、`new_value?: json`、`explanation: str`、`scope_ref: str`。DA11.5.2 将其转为评测样本。

#### 3.3.6 评测与验收（`core.evaluation`）

**`CriteriaRef`**：判据内容由应用提供。

| 字段 | 类型 | 说明 |
|-|-|-|
| `id` | str | — |
| `revision` | str | — |
| `status` | LifecycleStatus | `draft` 或 `active`；正式验收只用 `active` |
| `owner_ref` | str | 有权主体 |
| `confirmation_ref` | str? | 确认记录，`active` 时必填 |
| `expected_outputs` | str | 预期结果，如“每条记录对每条适用规则给出判定及依据”“每个指标给出数值、口径与来源” |
| `evidence_requirements` | list\[str\] | 必需证据，如“判定定位到条款和字段”“数值可回溯到源单元格” |
| `unknown_policy` | `count_as_fail / report_separately` | UNKNOWN 计分方式 |
| `thresholds` | map\[str,float\] | 如 `{"accuracy": 0.95, "coverage": 0.9}` |
| `valid_from` | datetime? | — |

**`EvaluationSetRef`**

| 字段 | 类型 | 说明 |
|-|-|-|
| `id` | str | — |
| `revision` | str | 冻结后不可变 |
| `frozen` | bool | — |
| `split_manifest_ref` | str | 每个样本的 `split_role` 与分组键 |
| `counts` | map\[SplitRole,int\] | 各角色样本数 |
| `exposure_ledger_ref` | str | 暴露台账；修复方看过的样本降为回归样本 |

**`AcceptanceReport`**：DA11.5.5 产出，两族共用。

| 字段 | 类型 | 说明 |
|-|-|-|
| `id` | str | — |
| `criteria_ref` | VersionedRef | `active` 版本 |
| `evaluation_set_ref` | VersionedRef | 已冻结，只用 `unseen_acceptance` 样本 |
| `target_ref` | VersionedRef | 被验收的交付或组合 |
| `dependency_versions` | list\[VersionedRef\] | 判据、样本、语义定义、引擎、模型版本 |
| `overall` | Verdict | — |
| `cases` | list\[CaseResult\] | `CaseResult = {case_id, verdict: Verdict, evidence_refs: list[str], notes?}`；超过 1000 条改用 `cases_ref` |
| `cases_ref` | str? | — |
| `metrics` | MetricBundle | — |
| `coverage_scope` | str | 验收覆盖范围，含未覆盖的输入类型和不可判定项 |
| `limits` | list\[str\] | 局限 |
| `run_ref` | str | `ExecutionRef.invocation_id` |

验收报告不构成发布或访问许可。

**`MetricBundle`**：六类指标同时报告；失败、超时、预算耗尽的样本计入分母。

| 字段 | 类型 | 说明 |
|-|-|-|
| `quality` | list\[{name, value: float, numerator?: int, denominator: int}\] | 判据定义的质量指标，如判定准确率、数值误差 |
| `coverage` | {covered: int, total: int} | — |
| `unknown` | {count: int, rate: float} | — |
| `human` | {count: int, minutes?: float} | 人工介入 |
| `cost` | {amount: float, currency: str}? | — |
| `latency_ms` | {p50: float, p95: float} | — |
| `strata` | list\[{key: str, metrics: map\[str,float\]}\]? | 分层结果 |
| `missing_records` | list\[str\] | 缺失的计费或人工记录 |

#### 3.3.7 治理（`core.governance`）

**`AccessDecision`**：DA12.1.1 产出。

| 字段 | 类型 | 说明 |
|-|-|-|
| `decision_id` | str | 由 `CallContext.authorization_ref` 引用 |
| `policy_ref` | VersionedRef | 策略及版本 |
| `subject_ref` | str | 执行主体 |
| `requester_ref` | str? | 请求者；S1 起与执行主体取交集 |
| `action` | str | S0 为 `read` |
| `resource_ref` | VersionedRef | — |
| `purpose` | str | 用途 |
| `decision` | AccessOutcome | `allow / deny / indeterminate`；`indeterminate` 按拒绝处理 |
| `field_constraints` | list\[str\]? | 可见字段 |
| `row_constraints` | str? | 行过滤 |
| `masking_obligations` | list\[str\] | 脱敏义务 |
| `valid_until` | datetime | — |
| `reasons` | list\[str\] | — |

**`EgressDecision`**：DA12.1.4 产出；两族都会把文档、记录或表样本送入模型，S0 必需。与访问判定分别进行。

| 字段 | 类型 | 说明 |
|-|-|-|
| `decision_id` | str | — |
| `content_refs` | list\[VersionedRef\] | 送入模型的内容 |
| `destination` | {model\_ref: str, deployment: `local / private_cloud / vendor_api`, terms\_ref?: str} | 模型与部署位置 |
| `decision` | EgressOutcome | `allow / allow_masked / deny` |
| `visible_fields` | list\[str\]? | — |
| `masking_ref` | str? | 脱敏后内容 |
| `access_decision_ref` | str | 依据的 `AccessDecision` |
| `receipt_ref` | str? | 外发回执 |

**`ComponentMeta`**：S0 定义，S1 起由 DA05.8、DA18.7 使用。

| 字段 | 类型 | 说明 |
|-|-|-|
| `component_id` | str | — |
| `version` | str | — |
| `capability_ids` | list\[str\] | 实现的能力编号 |
| `operations` | list\[str\] | — |
| `implementation_ref` | str | — |
| `license` | str | SPDX 表达式 |
| `weights_license` | str? | 模型权重许可 |
| `data_license` | str? | 附带数据许可 |
| `distribution` | list\[`internal / customer_site / minthub_public`\] | 允许的分发场景 |
| `requires_contracts` | str | 契约包版本范围，如 `>=0.1.0,<0.2.0` |
| `runtime_requirements` | list\[str\] | — |

### 3.4 枚举（`core.vocab`）

| 枚举 | 取值 | 封闭/开放 |
|-|-|-|
| `CapabilityStatus` | `ok / partial / needs_input / pending / failed` | 封闭 |
| `StandardErrorCode` | `unauthorized / unsupported / invalid_input / version_conflict / not_found / source_changed / rate_limited / timeout / execution_unknown / dependency_unavailable` | 封闭；能力码用命名空间 |
| `Severity` | `info / warning / error` | 封闭 |
| `CompletenessExtent` | `complete_in_declared_scope / page / sampled / truncated / unknown` | 封闭 |
| `FieldValueStatus` | `extracted / missing / conflict / low_confidence` | 封闭 |
| `Aggregation` | `sum / count / count_distinct / avg / min / max / custom` | 开放；`custom` 附说明 |
| `EvidenceType` | `source_text / extracted_value / computation_result / execution_receipt / human_judgment` | 开放 |
| `TraceEventType` | `task_state / invocation / correction / decision / note` | 开放 |
| `Verdict` | `pass / fail / unknown / not_applicable` | 封闭 |
| `SplitRole` | `development / regression / unseen_acceptance` | 封闭 |
| `LifecycleStatus` | `draft / candidate / validated / active / deprecated / invalidated / rejected` | 封闭 |
| `AccessOutcome` | `allow / deny / indeterminate` | 封闭 |
| `EgressOutcome` | `allow / allow_masked / deny` | 封闭 |

`LifecycleStatus` 子集：

| 对象 | 子集 |
|-|-|
| 经验 | `candidate / validated / active / deprecated` |
| 治理资产 | `draft / validated / active / deprecated / invalidated` |
| 程序 | `draft / validated / rejected`；执行情况记在执行记录上 |
| 语义草案（S0） | `draft / validated` |
| 判据 | `draft / active` |

### 3.5 S0 类型流

```text
骨干入口：FileRef ──DA01.4/01.5──▶ DocumentRef | TableRef | DataBatchRef        （CallContext / CapabilityResult / ExecutionRef 贯穿）

判定族：DocumentRef ──DA02.8──▶ DocumentUnitRef[] ──DA03.4.3──▶ SemanticDraft{rule: RuleDefinition}
        DocumentRef ──DA02.12──▶ ExtractedRecordRef{FieldValue[] + SourceAnchor}
        DA03.15 / DA03.16 ──▶ Assessment<可判定性 | 适用性>
        DA06.3.5 → DA07.5 ──▶ Assessment<satisfied | violated | unknown | not_applicable> + EvidenceRef[]

计算族：TableRef ──DA02.1/02.2/02.4──▶ 规整 TableRef + SchemaRef ──DA03.4.1──▶ SemanticDraft{metric: MetricDefinition}
        问题 ──DA06.1──▶（应用层 RequirementSpec；歧义 → CapabilityResult.needs_input）
        DA06.3.1 → DA07.1.3 ──▶ ComputedResult + EvidenceRef[computation_result]

骨干出口：DA11.5.5 ──▶ AcceptanceReport{CaseResult[], MetricBundle}；DA10.3 / DA10.1.1 ──▶ 报告或工作簿（ArtifactRef，应用层）
贯穿：DA04.1 ──▶ TraceEventRef；DA12.1 ──▶ AccessDecision、EgressDecision
```

示例数据为示意。

示例一（判定族，DA02.12.1）：部分完成的抽取记录。

```json
{
  "status": "partial",
  "data": {
    "asset": {"id": "rec:r-0042", "kind": "extracted_record", "scope_ref": "tenant:demo/project:p1",
              "revision": "r1", "resolver": "store", "locator": "records/r-0042"},
    "document_ref": "doc:r-0042@r1",
    "target_schema_ref": "xschema:record@v3",
    "fields": [
      {"field_id": "amount", "status": "extracted", "value": 5800, "value_type": "money", "unit": "CNY",
       "confidence": {"score": 0.97, "method": "llm-structured+regex-check"},
       "evidence": [{"source_ref": "file:r-0042", "source_revision": "sha256:9f1c",
                     "selector": {"kind": "json_pointer", "pointer": "/body/total"}}]},
      {"field_id": "approver_level", "status": "missing", "value_type": "enum", "evidence": []}
    ],
    "issues": []
  },
  "issues": [{"code": "da02.field_missing", "severity": "warning", "message": "未找到审批人级别字段",
              "target": "approver_level", "retryable": false, "suggested_action": "补充附件或转人工"}],
  "execution_ref": {"invocation_id": "inv:7a1", "operation": "extract_fields_to_schema", "capability_id": "DA02.12.1",
                    "implementation_ref": "dataagent-data/extraction@0.1.0#llm-structured",
                    "input_versions": ["doc:r-0042@r1", "xschema:record@v3"],
                    "started_at": "2026-11-03T10:02:11+08:00", "finished_at": "2026-11-03T10:02:14+08:00"},
  "provenance": ["doc:r-0042@r1"],
  "completeness": {"extent": "complete_in_declared_scope", "declared_scope": "目标结构 v3 的 18 个字段"}
}
```

示例二（判定族，DA07.5.1）：前置条件缺失时的规则求值。

```json
{
  "assessment_id": "asmt:rule12-r0042",
  "target_ref": "rule:rule-12@r2",
  "verdict": "unknown",
  "basis_refs": ["ev:amount-r0042"],
  "dependency_refs": ["rule:rule-12@r2", "rec:r-0042@r1", "engine:expr@1.4.2"],
  "unknowns": ["precondition:approver_level 缺失"],
  "next_actions": ["DA03.16.4 补证或转人工"]
}
```

示例三（计算族，DA07.1.3）：带默认假设的月度指标。

```json
{
  "result_id": "res:m-revenue-2026-10",
  "target_ref": "metric:monthly_net_revenue@r1",
  "form": "scalar",
  "value": 1284500.0,
  "unit": "CNY",
  "grain": "全部门店 × 月",
  "filters_applied": ["status != 'refunded'"],
  "time_range": {"from": "2026-10-01T00:00:00+08:00", "to": "2026-11-01T00:00:00+08:00"},
  "semantic_versions": ["metric:monthly_net_revenue@r1"],
  "assumptions": ["“上月”按自然月解释，未使用财务日历"],
  "certified": false,
  "evidence_refs": ["ev:sql-run-91"],
  "completeness": {"extent": "complete_in_declared_scope", "declared_scope": "sales.xlsx 明细表 2026-10 全部行",
                   "observed": {"rows": 18234}}
}
```

### 3.6 留在各层的 S0 类型

| 层 | 类型 | 跨层形式 |
|-|-|-|
| 数据层 | `WorkbookRef`、`WorkbookCalcState`、`TableRegion`、`ProfileRef`、`ExtractionSchemaRef`（全文）、`GapPlan`、`CoverageMap`、`ApplicabilityDraft` | `VersionedRef`、`TableRef`、`Assessment` |
| 执行应用层 | `RequirementSpec`、`Ambiguity`、`LogicalPlan`、`ExecutableSpec`（SQL / 表达式 AST）、`EngineBinding`、`ReportDraft` | `ComputedResult`、`Assessment`、`AssetRef` |
| 评测与治理层 | `AcceptanceCriteriaDraft`、`EvaluationCaseDraft`、`GrainMergeReport`、`SensitivityReport`、`MaskedArtifactRef` | `CriteriaRef`、`AcceptanceReport` |

类型被第二层消费时，按 §2.3 迁入 core。

### 3.7 core 预留类型

S0 不用、字段待补：`ResourceRef`、`ConnectionRef`、`CredentialBindingRef`、`SnapshotRef`、`SemanticRef`、`MappingRef`、`LineageEdge`、`ArtifactRef`、`MemoryRef`、`ValidationReportRef`，以及 `SemanticDraft` 的 `entity / relationship / dimension` 定义结构。字段草案见[数据层共享输入输出契约](https://modelbest.feishu.cn/docx/NXe7dMEEQoJ5wqxcPsRczoebn4d)。

---

## 4. S1 / S2 预留

### 4.1 action（S1，`0.2.0`）

前提：附录 A P1、P3、P4 已定。

| 类型 | 用途 | 内核映射 |
|-|-|-|
| `ActionTier` | A0 读 / A1 提议 / A2 执行 | `EffectLevel` + `ReviewPosition` |
| `ActionContractRef` | 已发布动作契约（DA15.2） | — |
| `EvidencePackageRef` | 审批证据包：`EvidenceRef`、影响评估、预演差异 | 由 `ApprovalRequest.summary` 引用 |
| `ApprovalRequestRef / ApprovalDecision` | 审批请求与结论 | `ApprovalRequest` |
| `DelegationRef` | 委托范围与期限；有效权限 = 请求者 ∩ Agent | `DelegationGrant` |
| `ActionReceipt / ReconciliationReport` | 执行回执与对账；结果未知时不重放 | — |
| `ImpactAssessment` | DA12.11 执行前影响评估 | — |

两族共用 action 类型：判定族回写结论（如退回记录、标注状态），计算族写入目标表或报表。

### 4.2 delivery（S2，`0.3.0`）

前提：附录 A P6、P7 已定。

| 类型 | 用途 |
|-|-|
| `EnvironmentDefaultsRef` | DA17.2 环境默认版本组合 |
| `DeliveryRef` | 交付清单与归属 |
| `InstanceRef / HealthReport` | DA17.5 部署实例与健康检查 |
| `WaitRef` | DA14.6 等待点，引用内核 `BlockedOnItem` |

---

## 5. 代码组织（拟议）

```text
packages/capabilities/dataagent-contracts/
├── pyproject.toml                 # 仅依赖类型与校验库
├── src/dataagent_contracts/
│   ├── core/
│   │   ├── vocab.py               # §3.4 枚举
│   │   ├── envelope.py            # CallContext、CapabilityResult、Issue、ExecutionRef、Continuation、Completeness、Budget
│   │   ├── refs.py                # VersionedRef、AssetRef、FileRef、SourceAnchor、Selector
│   │   ├── data.py                # SchemaRef、TableRef、DataBatchRef、DocumentRef、DocumentUnitRef、ExtractedRecordRef、FieldValue
│   │   ├── semantics.py           # SemanticDraft、RuleDefinition、MetricDefinition、Assessment、ComputedResult、EvidenceRef
│   │   ├── task.py                # TaskContextRef、TraceEventRef、CorrectionRef
│   │   ├── evaluation.py          # CriteriaRef、EvaluationSetRef、AcceptanceReport、MetricBundle
│   │   └── governance.py          # AccessDecision、EgressDecision、ComponentMeta
│   ├── action/                    # S1
│   └── delivery/                  # S2
├── schema/generated/              # 由类型生成的 JSON Schema
├── examples/s0/                   # §3.5 示例，作为 schema 校验夹具
└── tests/                         # 往返序列化、枚举封闭、约束规则、示例校验
```

- 建模库：可导出 JSON Schema 的类型库，如 pydantic v2；S0 实现时选定。
- 发布形态：随附录 A P4 定案；此前作为各层工作区的本地依赖。
- 应用资产（规则、指标、抽取结构、判据、样本）由应用维护。

---

## 6. S0 契约验收

先于能力实现完成：

1. **可解析**：§3.1 的 51 项原子，输入输出类型均解析到 core 类型或本层有字段的类型。
2. **schema**：§3.3 全部类型可生成 JSON Schema；`examples/s0/` 全部通过校验。
3. **约束测试**：`CapabilityResult` 状态约束、`FieldValue` 证据约束、`AcceptanceReport` 判据与样本约束、`AccessDecision` 的 `indeterminate` 按拒绝处理。
4. **枚举**：封闭枚举遇未知值失败；开放枚举扩展值带命名空间。
5. **依赖方向**：静态检查层间无互相导入，契约包不导入能力包或应用。
6. **敏感值**：无明文凭据字段；示例与测试数据不含真实客户数据。
7. **通用性**：判定族、计算族各至少一个应用样本走通 §3.5，无需新增或修改 core 类型；应用特有信息只出现在 `extensions` 或领域资产中。

## 7. 待决与风险

| 项 | 说明 | 依赖 |
|-|-|-|
| 字段校准 | 字段在 `0.1.x` 冻结前按 S0 实现校准 | S0 实现 |
| 通用性验证 | 两族各一个应用样本时，单一应用结构可能被误当通用；冻结前用第三个应用复核 | 应用样本 |
| 定义粒度 | `RuleDefinition` 条件为文本加字段引用；`MetricDefinition` 只覆盖单度量聚合；需要时按追加规则扩展 | DA06.3、DA07.10 |
| 内核映射 | S0 依赖 `SessionId`、`CallId`、`StoreContract`；guard 与 `AccessDecision` 的分工随 P2 定案 | 附录 A P2、P5 |
| 契约包膨胀 | 新增类型须说明跨哪两层、服务哪两个应用或族 | 评审流程 |
| 版本纪律 | CI 做 schema 兼容性检查 | 工具链 |

---

## 附录 A：平台对接待决（P1–P7）

本地优化版建议，未在总规划定案。

实现前须定案。内核依据：`agent-kernel@f0fa521`，权威源 `kernel/iface/src`。

| 编号 | 待决项 | 当前做法 | 内核 / Mint 事实 | 选项 | 建议 | 最晚定案 |
|-|-|-|-|-|-|-|
| P1 | 写通道怎么强制 | Python `action_gateway.py`，靠端口约定 | `EffectLevel::SideEffect`；guard 为单一门 | A 进程隔离：写后端凭据只发给网关进程；B 语言隔离：Rust 网关；C 只靠约定 | **A**，语言可后定；拒绝 C | S1 回写之前 |
| P2 | 数据访问判定与内核 guard | DA12.1 自出 `AccessDecision`，多点复检 | guard 单一门、fail-closed（`kernel/core/src/guard/`） | A 单闸门；B 双闸门；C guard 判定 + DA12.1 策略源，复检只用于不经内核的路径 | **C**：经内核的调用以 guard 为准；缓存命中、导出、离线索引由 DA12.1 复检；两路共用同一策略版本 | S0 之前 |
| P3 | 档位与审批映射 | 自拟 `ApprovalRequestRef` | `ApprovalRequest` 仅 4 字段；`ReviewPosition` 四段 | A 扩充内核字段；B 证据包外置，`summary` 携带 `EvidencePackageRef` | **B**；A0→ReadOnly，A1→Advance + Plan 审查，A2→SideEffect + ToolParams 审查 | S1 之前 |
| P4 | 组合清单与发布格式 | 自拟 `component-specs` / `presets` YAML，一层一工作区 | `kind = "skill"`（`SKILL.md`）、`kind = "preset"`（`[dependencies]` + `preset.toml`）；`AssemblyIntent.payload` 承载声明式装配数据；`mint.toml` 有 `license` 与 `[capabilities]` | A 沿用 Mint 包格式；B 自拟；C 自拟后转换 | **A**：DA18.6 产出 skill 包，DA18.7 产出 preset 包，运行时组合参数序列化进 `AssemblyIntent.payload`；开发期可一层一工作区 | 首次发布 MintHub 之前 |
| P5 | 轨迹与记忆存储 | 自建 SQLite `TraceRepository` | `StoreContract` 已定义，仅内核内部使用：L-C 无组件可用的 append/read，command/WASM 组件拿不到存储句柄，mint-core 路径无内核；会话内游标，无跨会话查询；工具调用由 `TraceSink.record_input` 写前留痕 | A 轨迹落 `StoreContract`、作用域记忆自建；B 全部自建 | **A**，分两步：S0 先按 `StoreContract` 接口形状本地实现 DA04.1，事件携带 `kernel_session_id`/`kernel_call_id`，经内核调用时 DA04.1.2 只记数据层增量；内核提供组件事件接口（`store.ext_append`/`store.ext_read`，见 \[06-data-layer-build-plan.md\](06-data-layer-build-plan.md) 附录 A）后切换适配器。DA04.3 自建并冻结 `Scope` 形状 | 内核接口：S1 之前 |
| P6 | 编队与接管 | 未用内核原语 | `DelegationGrant`、`Lease`、`BlockedOnItem` | A 机制归 OS；B 能力层自建 | **A**：DA14.6、DA14.7、DA16.1 引用内核原语，能力层只做角色与子目标划分 | S2 之前 |
| P7 | 存储后端 | SQLite 起步，端口可替换 | — | — | 维持；DA17.5.2 环境预检检查并发、保留、审计要求是否超出 SQLite | 部署前 |

## 附录 B：全局切片（S0–S2）

本地优化版建议，未在总规划定案；S0 的契约明细见本文 §3。

切片按业务闭环定义，各层文档中的切片为层内细化。验收看实际业务输出、拒绝与未知项处理、可接管性；后一切片不要求前一切片的能力全部完成。

| 切片 | 目标 | 能力范围 | 入口条件 | 退出（验收）条件 |
|-|-|-|-|-|
| **S0 通用只读证据闭环** | 文件、文档或记录 → 带依据、可验收的结论；只读，不写回源系统 | 骨干：DA01.4/01.5、DA04.1、DA06.3.5、DA07.5、DA07.10.1、DA10.3、DA11.5、DA12.1；判定族增量：DA02.8、DA02.12、DA03.4.3、DA03.15、DA03.16；计算族增量：DA01.4.2/4.6、DA02.1/02.2/02.4、DA03.4.1、DA06.1、DA06.3.1、DA07.1.3、DA11.2.3、DA10.1.1 | 附录 A P2、P5 已定；契约包 core 字段完整（本文 §3） | 判定族、计算族各用至少一个应用样本，在未见验收样本上按 DA11.5.5 端到端验收；报告列出未覆盖范围与不可判定项；六类指标并报；任何应用都不需要修改 core |
| **S1 组合沉淀与回写** | S0 有效组合发布为 Mint 包；结论经审批回写源系统 | DA18.6/18.7（产出 Mint skill/preset 包）、DA05.8；DA15 A0/A1/A2、DA16.2、DA07.7/07.8、DA14.6 | 附录 A P1、P3、P4 已定；S0 通过验收 | 包能从 MintHub 安装并复现 S0 结果；回写全部经 DA07.7，执行结果未知时只对账；审批证据可审计 |
| **S2 持续运行与移交** | 客户环境长期运行并移交客户 | DA17.2/17.5、DA14.2/14.8、DA18.1–18.5、DA11.7/11.9 | 附录 A P6、P7 已定；S1 通过验收 | 影子运行与人工结果的差异在约定范围内；按环节放权；与 DA02.15 基线同口径比较 |

未列入切片的能力组为“按需”，如 DA09、DA13、DA02.13–15、DA12.9。

**切片与应用**：切片定义通用能力范围。应用按闭环族选择增量原子，提供领域资产（规则、指标、判据、样本）；新增 core 契约或能力编号须有至少两个应用或两层需要。

| 闭环族 | 回答的问题 | 应用示例 |
|-|-|-|
| 判定族 | 这些记录是否符合这些规范性条款，依据是什么 | 令才（制度提取与规则审核）、合同条款核查、合规巡检 |
| 计算族 | 这个指标或问题在这些数据上的结果是多少，口径与来源是什么 | 文件即席分析、报表问数、经营指标核对 |

## 附录 C：来源

源文件：AgentOS 仓库 `docs/research/dataagent-2026-11-03/05-contracts.md`，经 `tools/to_feishu.py` 转换。
