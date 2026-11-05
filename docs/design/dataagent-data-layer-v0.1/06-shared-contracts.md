# 共享输入输出契约 v0.1

本文件定义原子能力之间交换什么，以及实现应保持哪些含义。采用可序列化对象和资源引用作为边界；Python、HTTP、MCP 可以承载同一业务契约。这里的命名与结构是 DataAgent 自拟草案，尚未对应任何平台 iface，也不假设已有组件已经实现。

## 1. 调用和返回

所有能力采用同一个逻辑形式：

```text
invoke(operation, input, CallContext) -> CapabilityResult<T>
```

| 对象 | 字段草案 | 含义 |
| --- | --- | --- |
| `CallContext` | `request_id, task_ref?, scope_ref, authorization_ref, deadline?, budget?, expected_revision?, idempotency_key?` | 请求标识、任务关联、作用域和实际授权引用；预算、超时及写入并发控制按能力需要提供 |
| `CapabilityResult<T>` | `status, data?, issues[], execution_ref?, provenance[], completeness?, continuation?` | 业务结果与运行状态分开，携带缺口、实际执行依据及后续取数方式 |
| `Issue` | `code, message, severity, target?, source_anchor?, retryable, suggested_action?` | 错误或歧义可定位，调用方可决定补数、换实现、重规划或询问 |
| `ExecutionRef` | `invocation_id, implementation_ref, input_versions[], started_at, finished_at?, receipt_ref?` | 指向实际发生的调用；计划不作为已执行记录 |
| `Continuation` | `cursor?, job_ref?, subscription_ref?, resume_condition?` | 分页、异步作业或持续订阅的后续入口；不是将完整长任务塞进单次响应 |

`status` 暂定为 `ok / partial / needs_input / pending / failed`：`ok` 表示当前声明范围的能力执行成功，不意味着业务结论正确；`partial` 必须列缺口；`needs_input` 可以携带候选和澄清项；`pending` 必须有作业或等待引用。不能将空结果、权限拒绝、解析失败混成同一种 `[]`。

错误码先统一：`unauthorized, unsupported, invalid_input, version_conflict, not_found, source_changed, rate_limited, timeout, execution_unknown, dependency_unavailable`。对具有副作用的调用，`timeout` 或 `execution_unknown` 不允许默认重放；通过回执和幂等键查询、对账后决定下一步。

## 2. 引用、版本与内容

| 对象 | 最小信息 | 使用约定 |
| --- | --- | --- |
| `AssetRef` | `id, kind, scope_ref, revision, resolver, locator, digest?, media_type?` | 长期对象引用；`resolver/locator` 是受权限保护的解析描述，不是明文凭据或永久公开下载链接 |
| `ResourceRef` | `source_ref, native_id, kind, source_version?, metadata` | 源端资源身份；源端没有版本时明确缺失，不给它编造一个可重现版本 |
| `FileRef` | `AssetRef + filename?, size?, content_digest` | 已进入受控存储的原件；不依赖 Agent 进程的临时文件路径 |
| `ConnectionRef` | `id, source_type, endpoint_ref, credential_binding_ref?, capabilities_ref?, expires_at?` | 可解析的连接引用；进程内 socket/driver 对象由适配器管理，不跨 API 序列化 |
| `CredentialRef / CredentialBindingRef` | `secret_provider_ref, binding_id, allowed_target, expires_at?, revision` | 只传代理引用，日志、模型上下文及普通输出均不携带明文密钥 |
| `SchemaRef` | `AssetRef + fields[], keys[], native_schema_ref?, inference_basis?` | 字段用稳定 ID 与源路径；区分源端声明、样本推断与人工确认 |
| `SourceAnchor` | `source_ref, source_revision, selector, extraction_ref?` | selector 为 Excel sheet/cell、PDF page/bbox、JSON Pointer、记录键或文档字符区间；必须可回到相同源版本 |
| `SnapshotRef` | `asset_ref 或 source_ref + native_snapshot_token, captured_at, readable_range, retention?, replayability` | 真实副本或有效 as-of 访问机制；digest、时间戳本身不能保证历史重读 |

`revision` 是 DataAgent 资产修订，`source_version` 是源端版本，`digest` 校验内容，`effective_time` 是业务生效时间，四者分别表达。源端资源只能读最新时，其引用可被管理，但不能据此声明其内容不可变。所有写入类原子能力返回实际保存版本及回执；支持 `expected_revision` 做乐观并发检查。

对引用的按 ID 读取、按 revision 解析和容器分页由 Repository/Source 端口提供，是完成存储契约所必需的访问方法。它们不另增 DA 编号，也不承担语义召回或相关性排序；面向问题的检索仍由 DA05 提供。输入若收到版本化引用，实现必须校验实际读到的版本，不能用当前内容替代历史内容。

## 3. 结构化和非结构化数据

| 对象 | 最小信息 | 边界 |
| --- | --- | --- |
| `WorkbookRef` | 原文件引用、sheet 列表、单元格/合并/公式数据解析引用 | 区分公式表达式、缓存值与经过重算的值 |
| `TableRegion` | `source_anchor, cell_range 或 bbox, layout_ref, confidence?, alternatives?` | 表块候选，尚未必形成稳定字段和记录 |
| `TableRef` | `AssetRef, schema_ref, data_ref, row_identity?, source_map_ref, transform_ref?` | 可读取的表；来源映射与数据分存，避免将全量单元格血缘塞进响应 |
| `DataBatchRef` | `asset_ref, schema_ref?, source_ref, cursor?, row_count, completeness` | 有限的一批记录；小批可内联，大批返回引用，调用方采用相同 schema 解析 |
| `DocumentRef` | `AssetRef, content_type, blocks_ref, page_refs?, original_ref` | 文字、图像、嵌套文档均保留原内容类型，不强制转表 |
| `DocumentUnitRef` | `AssetRef, parent_document_ref, unit_type, content_ref, anchors[], context_refs[]` | 章节/条款/表格单元，拆分不丢父章节和跨块上下文 |
| `ExtractedRecordRef` | `AssetRef, target_schema_ref, values_ref, field_evidence_ref, issues[]` | 每个字段可关联多个原文锚点；缺失、冲突、低置信结果分别表达 |
| `ProfileRef` | `AssetRef, dataset_ref, field_stats_ref, method, sample_spec?, observed_at` | 精确统计和估计分开，保存采样范围、预算耗尽和访问限制 |
| `ChangeBatchRef` | `AssetRef, events_ref, source_partition, start_offset, end_offset, watermark_candidate` | 事件保留主键、操作类型、源版本和时间；水位候选不代表已提交 |
| `SubscriptionRef` | `subscription_id, source_ref, partitions, start_offsets, lease?, poll_ref, cancel_ref` | 生命周期由源适配器管理；下一批数据和取消有明确入口 |

`completeness` 至少表达：`extent（complete_in_declared_scope / page / sampled / truncated / unknown）`、声明的读取范围、实际行/页数、未完成原因、源端快照一致性。`complete_in_declared_scope` 也不等于企业全量数据。例如当前页完整、总分页未知，不得写为整个数据集完整。

解析和变换不覆盖原件。输出新数据引用及可追踪的来源映射；聚合、转置和嵌套展开可以有多对多来源关系，不能假定每个目标单元格只来自一个原始单元格。

## 4. 语义、候选和关系

| 对象 | 最小信息 | 边界 |
| --- | --- | --- |
| `SemanticDraft` | `draft_id, kind, definition, scope_ref, sources[], unresolved[], confidence?` | 模型生成/推断默认草案；`EntityDraft / MetricDraft / RuleDraft / RelationshipDraft` 等是它的特化 |
| `SemanticRef` | `AssetRef, semantic_kind, definition_ref, status, valid_time?, recorded_at, sources[]` | 按版本保存的定义；发布状态由治理控制，保存版本不等于认证口径 |
| `MappingDraft / MappingRef` | `semantic_ref, physical_refs[], path_or_binding, transform_ref?, valid_time?, sources[]` | 语义到表列、API、函数、文档的实现绑定，保留来源与未解析符号 |
| `Assessment` | `target_ref, verdict, basis_refs[], dependency_refs[], unknowns[], next_actions[]` | 可判定性、适用性、冲突、兼容检查等共用模式；判定词表由各能力定义 |
| `EvidenceRef` | `asset_ref, evidence_type, source_anchors[], obtained_by, verification_ref?` | 原文、计算结果或执行回执等实际依据；引用存在不自动证明可靠性 |
| `LineageEdge` | `from_ref, to_ref, edge_kind, basis, definition_or_run_ref, coverage` | `basis=declared / inferred / observed` 区分声明、静态推断、实际观测 |

关系采用共享标识，但不同含义分开保存和查询：

| 关系种类 | 例子 | 归属 |
| --- | --- | --- |
| 数据处理依赖 `data_dependency` | `orders.amount -> daily_sales.total` | DA02.7；描述表列及变换 |
| 业务定义依赖 `semantic_dependency` | “净收入”引用“含税收入”“税额” | DA03.7；描述定义派生 |
| 业务对象关系 `entity_relationship` | “客户拥有订单” | DA03.3；可带时态及基数 |
| 语义实现映射 `semantic_mapping` | “净收入”绑定某视图或接口结果 | DA03.6；连接语义与物理来源 |
| 产物来源 `artifact_provenance` | 本次报告使用哪些数据/口径/程序 | DA04.4.4；实际运行依据关联 |

v0.1 可在同一个关系存储后端中按类型分区，业务逻辑不得混用边类型；不要求先搭建图数据库。依赖边到具体资产版本，避免“对象名字没变”时误判上下游仍然有效。

草案构造、版本保存、正式发布是三个不同动作。多数 `define_*` 只返回草案；`save_semantic_objects` 负责持久化已允许保存的版本；正式发布复用治理机制。`confidence` 仅是带方法说明的估计，不充当自动认证门槛。

## 5. 轨迹、记忆与任务修订

| 对象 | 最小信息 | 边界 |
| --- | --- | --- |
| `TraceEventRef / CorrectionRef` | `event_id, task_ref, event_type, timestamp, actor_ref, payload_ref, source_revision?` | 保存实际事件，敏感参数受控保存；模型建议与已执行动作分开 |
| `MemoryCandidate / MemoryRef` | `kind, content_ref, scope_ref, applicability, dependencies[], validation_refs[], status, source_traces[]` | 原始轨迹提炼后仍是候选；共享范围与可信状态是两个维度 |
| `ArtifactRef` | `AssetRef, artifact_kind, content_ref, dependencies[], runtime_requirements?, validation_refs[], applicability` | 查询、程序、模型、模板及组合配置的通用保存对象，不等于安装包运行句柄 |
| `TaskContextRef` | `task_id, revision, selected_refs[], assumptions[], policy_refs[], parent_revision?, unresolved[]` | 本次任务选用版本与假设，允许有显式未固定项；不是客户环境全局配置 |
| `ValidationReportRef` | `AssetRef, criteria_ref, sample_set_ref, dependency_versions[], results_ref, limits` | 指向 DA11 的实际验证报告，记录开发/回归/验收样本角色 |
| `DeliveryRef` | `delivery_id, artifact_refs[], environment_refs[], ownership_ref, revision` | 交付清单与归属，正文和代码复用资产存储 |

经验的 `status` 暂用 `candidate / validated / active / deprecated`，与用户、任务、团队、企业等 `scope` 分开。是否晋升、何时生效受验证和既有授权策略控制；不固化为每一步必有人工签字。

## 6. 建模扩展对象

`ModelDraft` 保存事实/维度/主题模型、粒度和语义引用；`DataContractDraft/Ref` 保存字段、约束、时效要求；`TransformationDraft` 保存 SQL/程序引用、输入输出和依赖；`MaterializationReceipt` 保存实际写入目标、分区、行数、版本、作业、幂等与部分失败。三类草案不意味着物理数据已经创建，物化回执也不意味着业务验证通过。

## 7. 典型调用示例

下面只示意关键字段；字段名在实现前可以调整。

```json
{
  "operation": "extract_irregular_excel",
  "input": {
    "file_ref": {"id": "file:expense", "revision": "sha256:abc"},
    "sheets": ["报销明细"],
    "recovery_policy": "preserve_ambiguity"
  },
  "context": {
    "request_id": "req:parse-01",
    "task_ref": "task:a@r2",
    "scope_ref": "tenant:demo/project:expenses",
    "authorization_ref": "policy-binding:read-files"
  }
}
```

```json
{
  "status": "partial",
  "data": {
    "tables": [{"id": "table:expense-detail", "revision": "r1"}],
    "source_map_ref": "mapping:expense-cells@r1"
  },
  "issues": [{
    "code": "ambiguous_header",
    "message": "第 2 个表块有两个可能的表头，保留为候选",
    "severity": "warning",
    "target": "region:2",
    "retryable": false,
    "suggested_action": "补充表头提示或选择替代恢复实现"
  }],
  "provenance": [{"source_ref": "file:expense@sha256:abc"}],
  "completeness": {"extent": "truncated", "declared_scope": "报销明细全部表块", "reason": "region:2 未恢复"}
}
```

调用方可修改提示或更换实现后重试第 2 个表块；无需重新连接、重复解析全部文件，也不能把已经恢复的一张表等同于完整业务交付。
