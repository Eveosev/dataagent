# dataagent-data

DataAgent 数据层 S0 实现：32 个原子能力，两个入口（MCP / CLI）。

- 契约：`dataagent-contracts` core（开发时路径依赖，bundle 时 vendoring）。
- 存储：内容按 digest 寻址；版本用 SQLite 显式 revision；轨迹 append-only。
- 无网络调用；OCR 为可选依赖，缺失时返回 `dependency_unavailable`。

## 原子分布

| 族 | 模块 | 原子 |
|-|-|-|
| 骨干（9） | `ingestion/files.py`、`ingestion/ocr.py`、`memory/traces.py` | `parse_regular_excel`、`parse_delimited_file`、`parse_json_records`、`parse_text_pdf`、`ocr_pdf`、`ocr_image`、`append_task_event`、`append_invocation_record`、`append_user_correction` |
| 判定族（14） | `preparation/documents.py`、`preparation/extraction.py`、`semantics/metrics_rules.py`、`semantics/decidability.py`、`semantics/applicability.py` | 文档切分、锚点维护、字段抽取/锚定/schema 版本、业务规则、可判定性 4 项、适用性 4 项 |
| 计算族（9） | `ingestion/files.py`、`preparation/regions.py`、`preparation/structure.py`、`preparation/profiles.py`、`semantics/metrics_rules.py` | `extract_irregular_excel`、`inspect_workbook_calc_state`、区域检测、表头恢复、合并展开、行分类、画像、类型推断、指标定义 |

operation 名即函数名；`source_file` 由注册表从 handler 模块推导，并与包内 `src/dataagent_data/catalog-snapshot.json`（由总 Catalog 生成）逐项校验。

## 运行

```bash
uv sync --extra dev
uv run pytest
uv run python -m dataagent_data.interfaces.cli --list
uv run python -m dataagent_data.interfaces.cli parse_regular_excel   # stdin JSON
uv run python -m dataagent_data.interfaces.mcp_server                # NDJSON JSON-RPC
```

### 发布门禁前提

`scripts/verify_local.sh` 同时运行本包与 `dataagent-contracts` 的 pytest。两包的
pytest（及 contracts 的 jsonschema）都在可选 `dev` extra 中，冻结锁默认不安装；
门禁开头会显式检查并在缺失时直接失败（而不是中段才以晦涩错误暴露），修复命令：

```bash
(cd packages/capabilities/dataagent-data && uv sync --frozen --extra dev)
(cd packages/capabilities/dataagent-contracts && uv sync --frozen --extra dev)
```

环境变量：

| 变量 | 默认 | 说明 |
|-|-|-|
| `DATAAGENT_WORKSPACE` | 当前目录 | 文件输入根；绝对路径、`..`、符号链接越界一律拒绝 |
| `DATAAGENT_DATA_ROOT` | `<workspace>/.dataagent` | 内容库、SQLite 版本库、轨迹库；临时渲染文件在 `scratch/` |
| `DATAAGENT_CATALOG_SNAPSHOT` | 包内 `src/dataagent_data/catalog-snapshot.json` | 覆盖 Catalog 快照路径（测试/诊断用） |

## CLI 协议

```bash
echo '{"input": {...}, "context": {"request_id":"r1","scope_ref":"tenant:t","authorization_ref":"policy:p"}}' \
  | python -m dataagent_data.interfaces.cli parse_delimited_file
```

- stdout 只有一行 `CapabilityResult` JSON；`status=failed` 退出码 1，用法错误退出码 2。
- `context` 也可与业务字段平铺在同一对象中（除 `context` 外的键视为输入）。
- CLI 的失败退出码与内核 `command` 传输不兼容（`kernel/host/src/transport/service/command.rs` 在退出码非 0 时丢弃 stdout，只回传 stderr）；内核/CSP 侧一律走 MCP，CLI 只供人/脚本直接调用。

## MCP 协议

标准库实现的 NDJSON JSON-RPC：`initialize`、`tools/list`、`tools/call`、`ping`。

- 工具名 = operation 名；`inputSchema` 由输入模型生成，并附加 `context` 对象。
- `context` 优先取 `arguments.context`，其次 `params._meta.context` 或含三个必填键的 `_meta`。
- 返回值是 text content（`CapabilityResult` JSON）；`status=failed` 时 `isError=true`。
- 坏 JSON 返回 `-32700`，服务不退出；未知方法 `-32601`。
- 进程启动时校验注册表与 Catalog 快照；不一致直接退出并写 stderr。

## 两段式推理

`extract_fields_to_schema`、`define_metric_formula`、`define_business_rules`、`assess_automatic_decidability`、`define_rule_applicability`、`define_rule_preconditions` 使用两段式：

1. 不带 `proposal` 调用 → `needs_input`，`issues[].inference_request` 给出候选片段、锚点、目标 schema/词表。
2. 带 `proposal` 再调 → 工具校验结构、逐条核对锚点；无依据的值降为 `missing`/`conflict`，绝不保留为 `extracted`。

`Issue.inference_request` 是相对 05 设计稿的字段校准，已回写 `docs/research/dataagent-2026-11-03/05-contracts.md` §3.3。

## 存储

| 端口 | 本地实现 | 说明 |
|-|-|-|
| `ContentStore` | `adapters/storage/local_content.py` | `sha256:<hex>` 寻址，临时文件 + `os.replace` 原子写 |
| `VersionedRepository` | `adapters/storage/sqlite.py` | 显式 revision，`expected_revision` 冲突返回 `version_conflict` |
| `TraceRepository` | 同上 | 按任务流 + `event_id` 去重，cursor 从 1 递增，链式 checkpoint digest；`kernel_session_id` 另建索引；`read_from(task_ref)` 只读任务流游标，跨任务的内核会话视图用 `read_by_kernel_session`；版本与轨迹写入用 `BEGIN IMMEDIATE` 串行化，冲突返回 `version_conflict` |
| `InferencePort` | `ports/inference.py` | 仅定义协议；当前推理在 Agent 侧完成 |

## Mint bundle

```bash
uv run python scripts/build_bundle.py          # staging + uv lock
cd packaging/bundle && mint publish --dry-run  # 校验清单并打包
```

`packaging/bundle/` 是自包含 staging：包含 `dataagent_contracts` 源码、数据层源码、快照、Skills 与 `.mcp.json`，不依赖仓库里的兄弟目录。发布前先跑：

```bash
uv run python scripts/export_catalog_snapshot.py --check
```

## 许可

Apache-2.0。
