# dataagent-runtime

DataAgent 共享运行时（08-governance-layer-build-plan §2 / §4.3；07-application-layer-build-plan 步 0）。

三层（数据层、应用层、评测治理层）共用的最小运行时，不含任何业务原子：

| 模块 | 内容 |
|-|-|
| `ports` | `ContentStore`、`VersionedRepository`、`TraceRepository`、`InferencePort`、`AccessDecisionResolver`、`DecisionStore` |
| `adapters` | `LocalContentStore`（内容寻址）、`SqliteVersionedRepository`（显式修订 + 乐观并发）、`SqliteDecisionStore`（DA12.1 决策存取） |
| `registry` | `OperationSpec`、`operation` 装饰器、Catalog 一致性校验（规则同数据层 06 §4.1） |
| `invoke` | `invoke(operation, input, CallContext) -> CapabilityResult[T]`，入口前执行访问复检（§4.3） |
| `enforcement` | `enforcement = off / warn / enforce`；访问复检与外发检查钩子；内核路径判定 |
| `interfaces` | MCP（NDJSON JSON-RPC）与 CLI 骨架，由各层包提供注册表后复用 |

## 访问复检（08 §4.3）

`invoke` 读取输入资源前解析 `authorization_ref`：

- `AccessDecision` 存在、`allow`、未过期（`valid_until`）、`resource_ref` 覆盖本次输入、用途一致 → 放行；
- 否则在 `enforce` 模式返回 `failed`，code `da12.access_denied`；`warn` 模式附 warning 后继续；`off` 跳过；
- 经内核调用（`kernel_session_id` 存在且宿主声明 guard 生效）时只校验决策存在，以 guard 结论为准；无声明时按无内核路径处理，完整复检（08 §11）。

`authorization_ref` 既可以是已保存的 `AccessDecision.decision_id`，也可以是策略绑定
（`policy:<id>@<revision>`），后者经 `AccessDecisionResolver` 即时求值（解决首次授权的
引导环，07-08 评审 §7）。

## 外发检查（08 §4.3）

`InferencePort` 生成 `inference_request` 前要求覆盖其中全部内容的 `EgressDecision`：
`allow` 原样附带；`allow_masked` 只附 `masking_ref` 指向的脱敏内容；`deny` 或缺失时不附
内容并返回 `needs_input`，code `da12.egress_required`。由 `guarded_inference` 包装实现。

依赖：`dataagent-contracts`；不依赖任何层包。

## 统一 CLI 内核（12-unified-cli-research §5.3）

`interfaces/unified.py` 是三层共用的 argv 内核：`list`（每 op 一行：名称、能力编号、
是否复检、是否两段式）、`run <op>`（`--input-file` / `--set` / `--set-json` / `--file` /
`--ref` / `--proposal-file` / `--authorize` / `--detail`）、`<op> --help`（扁平参数表，
不输出 `$defs`）。stdout 摘要 ≤ 32 KiB（`status`、`issues`、`data`、句柄、`result_path`），
超限时按序裁剪（丢弃 `data`、截断 issues、裁剪 `inference_request` 内容），全文与输入快照
写 `<data_root>/results/<invocation_id>.json`。退出码：0 = ok/partial/
needs_input，1 = failed，2 = 用法或 schema 错误，3 = 环境缺失。主体与用途只取宿主环境
（`DATAAGENT_HOST_SUBJECT_REF` / `DATAAGENT_HOST_PURPOSE`），不接受参数。enforce 模式下，
未引用 egress 决策的 `inference_request` 内容键在输出前剥离（W0 接缝规格 §5）——
摘要与 `--detail full` 两条 stdout 通道一致剥离。

测试：`uv run --project . pytest`（或 `.venv/bin/python -m pytest`）。
