# dataagent-governance

DataAgent 评测与治理层（08-governance-layer-build-plan）。S0 交付 6 个原子：

| 原子 | operation | 模块 |
|-|-|-|
| DA11.5.1 业务验收判据定义 | `draft_acceptance_criteria` | `evaluation/criteria_samples.py` |
| DA11.5.5 端到端业务验收 | `evaluate_business_acceptance` | `evaluation/criteria_samples.py` |
| DA11.5.6 验收样本隔离 | `isolate_acceptance_samples` | `evaluation/criteria_samples.py` |
| DA12.1.1 访问范围检查 | `check_access_scope` | `governance/access.py` |
| DA12.1.4 模型上下文可见性与外发控制 | `check_model_context_egress` | `governance/access.py` |
| DA11.2.3 结果粒度与合并检查 | `check_result_grain_and_merge` | `evaluation/computation.py` |

## 调用约定

- `invoke(operation, input, CallContext) -> CapabilityResult[T]`；MCP 工具名 = operation。
- 业务结论与运行状态分开：`deny`、验收 `fail` 都是 `status=ok` 的业务结论；策略不可取得时 `indeterminate`，按拒绝处理。
- 主体与用途取自 `CallContext`（可信宿主固定，调用参数不可覆盖）。
- `check_access_scope` 产出的 `decision_id` 可作为后续调用的 `authorization_ref`；`check_model_context_egress` 产出的 `decision_id` 是 `inference_request` 必须引用的外发凭证。

## 判据确认（管理入口）

`draft_acceptance_criteria` 只产出 `draft`；转 `active` 经
`python -m dataagent_governance.interfaces.cli confirm-criteria`（可信宿主路径，非 MCP 工具）。
确认记录绑定判据内容 digest 与 revision，伪造、过期或指向他份判据的确认一律拒绝。

## 打包

Mint `kind = "bundle"`，名称 `dataagent/governance-layer`；依赖
`dataagent-contracts`、`dataagent-runtime`；不导入 `dataagent_data`、`dataagent_application`。
执行其他层能力经 MCP 客户端适配器（阶段 2，DA11.4）。
