---
round: 3
date: 2026-11-03
tests: contracts 84 / data 105
---

# Round 3 修复

| 项 | 修复 |
|-|-|
| DA02.12.3 锚点取值校验 | 过滤已有锚点时同时要求 `anchor_invalid_reason == ""` 与 `anchor_value_mismatch == ""`；无支持锚点后按数值整词（`Decimal` token）重定位，仍失败才降为 `missing` + `unlocated` + `da02.anchor_not_found`，message 带 mismatch 原因；混合锚点只保留支持取值的那一个 |
| 锚点重定位 | 新增 `find_value_span`：数值按 `_NUMBER_TOKEN` 逐 token 与 `Decimal` 比较，`999` 不再命中 `1999`；非数值回退 `find_text_span`。`test_documents` 的 `5800` 回找路径保持 |
| 测试 | 新增 4 个锚点用例（整词边界、混合锚点、千分位、`¥5,800.00` 表面形式）；新增 CLI Catalog 拦截与 `execution_unknown` 映射用例；`dataagent-data` 105 passed、`dataagent-contracts` 84 passed、schema 66 files、snapshot 32 atoms |
| CLI 启动门 | `main()` 在解析参数前调用 `validate_registry()`，Catalog 快照不一致时写 stderr 并退出 1，与 MCP 入口对齐；正常 `--list` 仍为 32 |
| 部署 | `.mcp.json` 增加 `timeout_s = 120`；实测空 `UV_CACHE_DIR` + 无 `.venv` 的 bundle 冷启动 `initialize + tools/list` 为 19.1s（Round 3 历史值；Round 4 实测见 [Round 4](r4-fixes.md) §6） |
| 打包 | `build_bundle.py` 的 `copytree` 忽略 `__pycache__` / `*.pyc`；重建后 staging 69 个文件、0 个 `.pyc`，`mint publish --dry-run` 仍通过；`mint.toml` 描述改为“MCP 入口，CLI 仅本地调试/黑盒验收” |
| 文档 | 统一 `06` 的测试计数（84/105）与[实现基线](r1-implementation.md) §3 一致；修正 `kernel_session_id` / `kernel_call_id` 的 `CallMeta` 表述；`packaging/README.md` 说明 `--frozen` 只锁版本、不等于离线 |
