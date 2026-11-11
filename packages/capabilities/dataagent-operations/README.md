# DataAgent Operations

本地 API 环境探查与持久工作流。环境文档、业务状态、流程候选、验证报告、运行控制点、等待和动作回执通过独立 MCP 进程提供给工作台。

## 宿主配置

| 变量 | 内容 |
| --- | --- |
| `DATAAGENT_OPERATIONS_CONFIG` | 宿主维护的 JSON 文件绝对路径 |
| `DATAAGENT_OPERATIONS_DB` | Operations SQLite 数据库绝对路径 |
| `DATAAGENT_OPERATIONS_WORKBENCH_DB` | 可选的工作台 SQLite 数据库绝对路径，提供同作用域的 `goal` 记录 |

配置包含 `scope_ref`、`authorization_ref`、`environments` 和可选的 `work_specs`。每个环境以环境 ID 为键，固定 `base_url`、`tenant`、`operations`，可指定 `openapi_path`、`business_key_prefix` 和宿主管理的 `headers`。每个操作以 OpenAPI `operationId` 为键，固定 HTTP 方法和路径。工作流参数使用发现的 OpenAPI 3.1 JSON Schema。连接器接受同源、已配置的路径，使用本地 schema 引用。

读取操作可使用 `business_key_parameter` 注入当前业务键。按业务对象 ID 读取时配置 `record_lookup`、`collection_pointer` 和 `record_id_parameter`，连接器通过业务键查到对象 ID 并核验返回的对象。写入操作必须声明 `effect`，其中包含动作语义、业务键查询、成功判据和适用的前置条件。由宿主注入业务键、查询获得的对象 ID 或稳定请求键。

| 对账证据 | 动作状态和推进条件 |
| --- | --- |
| 当前业务对象满足成功判据 | `applied`，保存远端响应或对账观察作为回执 |
| 远端提供该动作未生效的确定证据，且支持同键幂等 | `not_applied`，下一次推进可在有效授权下重新派发原请求 |
| 找到业务对象且已观察到部分效果 | `partial`，继续查询或由人处理 |
| 业务键缺失、请求超时或现有状态不足以判定 | `unknown`，继续查询 |

`definitive_not_applied` 仅用于能够证明原请求未生效的查询字段。草稿状态本身无法证明正在处理的提交请求已终止。SQLite 先保存 `in_flight` 再发送 HTTP 请求。派发权和撤权在 SQLite 中串行检查。进程结束后，仍在传输或结果未知的请求保持待对账。

## 调用顺序

```bash
uv run --frozen python -m dataagent_operations mcp
uv run --frozen python -m dataagent_operations call environment_discover <<'JSON'
{"environment_id":"test-orders"}
JSON
```

| MCP 工具 | 输入和用途 |
| --- | --- |
| `environment_discover` | `environment_id`，读取 API 描述并进行按键查询探查 |
| `workflow_draft` | `work_spec_id`、`snapshot_id`、可选 `run_id`，生成结构化推理请求 |
| `workflow_submit_proposal` | `draft_id`、`spec`，保存候选和校验报告 |
| `workflow_start` | `proposal_id`、`business_key`、`inputs`，校验并启动精确候选 |
| `workflow_advance` | `run_id`、可选 `max_steps`，推进至等待、人工输入、对账或终点 |
| `workflow_status` | `run_id`，读取当前控制点与业务证据引用 |
| `workflow_control` | `run_id`、`command`、可选 `values`，暂停、恢复、取消或补充输入 |
| `workflow_actions` / `workflow_waits` | `run_id`，读取动作账本和等待记录 |

MCP 使用 DataAgent `CallContext` 与 `CapabilityResult`。CLI 的 `call` 从标准输入读取工具参数并使用宿主配置的调用范围。宿主使用 `uv run --frozen python -m dataagent_operations revoke` 撤销当前授权。

工作流采用有限有向图。参数可以引用 `/inputs`、`/business_key` 或所有入路径都已完成的 `/steps/<step_id>`。等待和核验条件读取新的 API 结果，条件路径以 `/response/` 开头。待审批、通过和驳回分别使用目标系统的实际状态。WorkSpec 可通过 `constraints.workflow_verification` 固定终点允许的 API 查询、条件和验收项索引。

[订单场景](tests/conftest.py)提供宿主配置和七类步骤的示例。[API 用例](tests/test_api_workflow.py)和[恢复用例](tests/test_recovery.py)使用本地回环业务系统。

## 浏览器观察与对账

环境可配置 `browser`，提供本机 Node 与 Playwright 模块的绝对路径、Chrome channel、允许导航的 `pages` 和附加的只读 `read_resources`。环境限定为本机 IPv4 环回服务。调用 `environment_observe_web` 读取页面控件、版本和截图引用，调用 `environment_web_observation` 读取已保存观察。

宿主可在 `browser.lookups` 为页面配置业务键查询参数、行、键和状态定位。设置动作的 `effect.browser_lookup_page` 后，若 API 查询仍无法确认生效，运行器可从唯一可见的业务键和状态收集回执。页面观察只允许配置内的 GET 和 HEAD，请求保持原动作键，页面对账不会再次派发写入。浏览器及混合通道配置见 [对账用例](tests/test_channel_switch.py)。
