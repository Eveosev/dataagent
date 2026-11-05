---
name: dataagent-access
description: 用 DataAgent 治理层做访问判定与模型上下文外发判定。涉及 DA12.1.1、DA12.1.4、访问复检、脱敏外发时使用。
---

# DataAgent 访问与外发

执行权限与"数据可进入模型上下文"是两次独立判定，不要合并。

## 调用时机

1. **读取任何资源前**：先 `check_access_scope`（主体、资源、动作、用途），拿到 `AccessDecision`；其 `decision_id` 就是后续调用的 `authorization_ref`。
2. **生成 `inference_request` 前**：先 `check_model_context_egress`（内容引用、`destination`、依据的 `AccessDecision`），拿到 `EgressDecision`；`inference_request` 必须引用其 `decision_id`。
3. 运行时复检：`enforcement = enforce` 时，`invoke` 读输入资源前会复核决策存在、`allow`、未过期、资源覆盖、用途一致；不满足返回 `da12.access_denied`。外发缺失或 `deny` 时内容被剥离并返回 `da12.egress_required`。

## 规则

- 主体与用途取自 `CallContext`（可信宿主固定）；调用参数不能覆盖。
- 无匹配规则得 `indeterminate`，按拒绝处理；显式 `deny` 优先于任何 `allow`。
- 敏感识别是确定性的：身份证号、手机号、邮箱、银行卡号（校验位）+ 策略声明字段名。
- `vendor_api` 且内容含敏感字段时至少 `allow_masked`：`inference_request` 只附 `masking_ref` 指向的脱敏内容；`deny` 时不含内容。
- 脱敏产物内容寻址保存；`MaskedArtifactRef.entries` 保留原文值 digest，可核验而不泄露。
- 经内核调用且宿主声明 guard 生效时只校验决策存在；无声明按无内核路径完整复检。

## 常见坑

- 拿 `deny` 决策当 `access_decision_ref` 去做外发判定会被拒。
- 决策过期（`valid_until`）后复检失败；需要重新 `check_access_scope`。
- 换目标模型（`model_ref` / `deployment`）须重新判定外发。

## 工具入口

- MCP：`dataagent-governance`；CLI：`python -m dataagent_governance.interfaces.cli <operation>`。
