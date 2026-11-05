---
name: dataagent-acceptance
description: 用 DataAgent 评测治理层定义业务验收判据、隔离验收样本并完成端到端验收。涉及 DA11.5.1、DA11.5.5、DA11.5.6、DA11.2.3 时使用。
---

# DataAgent 验收与评测

验收是"先冻结标准，再 unseen 样本上打分"。不要边修边改判据。

## 推荐链路

1. `draft_acceptance_criteria`：两段式。第一次不带 `proposal` 拿判据上下文（交付目标字段、现有判据版本、样本概况）；第二次带 `proposal`（`family`、`expected_outputs`、`evidence_requirements`、`unknown_policy`、`thresholds`、`strata`、容差）。
2. 确认：`draft` 不会自动生效。由有权主体经 CLI 管理入口 `confirm-criteria` 激活（确认记录绑定判据 digest 与 revision，产生新 revision）。修复流程不能改写已 active 的判据。
3. `isolate_acceptance_samples`：按分组键（实体、时间段、来源簇）整组划分 `development / regression / unseen_acceptance`；内容指纹去重，近重复跨组会告警；确认后 `freeze`。
4. `evaluate_business_acceptance`：只用 `unseen_acceptance` 样本；逐样本按判据比较，产出 `AcceptanceReport`（逐样本 `CaseResult`、六类指标、分层差异、覆盖范围、limits）。
5. `check_result_grain_and_merge`：计算族交付先查粒度——粒度键唯一性、Join 基数与行数膨胀、聚合前后度量守恒、分页回执完整性。

## 规则

- 判据状态只有 `draft` 与 `active`；验收只接受 `active` 且评测集已 `freeze`。
- 失败、超时、预算耗尽的样本计入分母；`unknown` 按 `unknown_policy` 计分；缺依据判 `fail`（`evidence_missing`）。
- 源端无总量或一致快照时对应项记 `unknown`，不以行数接近判定合并正确。
- 金标只经 `evaluate_business_acceptance` 读取；其他读取记入暴露台账，样本降为 `regression`，需补充独立样本。
- 本地样本库是约定隔离，不是安全边界；报告 `limits` 已注明，强隔离需接远程验收执行器（阶段 2）。

## 常见坑

- 用 `draft` 判据直接跑验收会被拒（`validate_acceptance_report` 校验 active + frozen + unseen）。
- 同一分组键的样本必须整组进同一角色；跨组近重复要检查告警。
- `pass_rate` 阈值必须在 [0,1]；计算族容差是 `tolerance_relative` / `tolerance_absolute`。

## 工具入口

- MCP：`dataagent-governance`；CLI：`python -m dataagent_governance.interfaces.cli <operation>`。
- 所有 `context` 必填 `request_id / scope_ref / authorization_ref`；主体与用途由可信宿主固定，调用参数不可覆盖。
