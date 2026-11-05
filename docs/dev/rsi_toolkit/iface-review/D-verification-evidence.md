---
title: 附录 D：核验证据
date: 2026-10-28
status: reference
parent: ../2026-10-28-iface-plans-review.md
---

# 附录 D：核验证据

本附录属于 [IFace 两方案评审](../2026-10-28-iface-plans-review.md)。

> **2026-11-02 更新**：`packages/kernel-iface` 已冻结为 0.1.0 历史快照，勿作对比基线；iface 契约现以
> `packages/agent-kernel/kernel/iface/src` 为权威源，可读副本为 `packages/agent-kernel/packages/iface-*`（0.1.2）。
> 对比前先同步 agent-kernel，见 AgentOS 根 `README.md`。

**核验基线**
- RSI：`apps/plugins/rsi-toolkit` v0.2.0（`44235f1`）
- `packages/kernel-iface`：v0.1.0 快照
- 本机：`mint 0.1.11`，Core 0.1.6 与 0.1.12-std
- MintHub：2026-10-28 公开索引，共 77 个包

**核验方式**
全程只读：读源码，跑 `--help`，检索二进制中的字符串，对 MintHub 发 GET 请求，对已缓存的包执行 `tar -t`。没有执行安装、登录或发布。

源码路径相对于 `apps/plugins/rsi-toolkit/service/`。

## D.1 kernel-iface 实况

**结构与版本**
- 共 10 个包：`iface-types` 加 9 个契约，版本都是 0.1.0。
- 每个包含 `mint.toml`、`README.md`、`schema.json`、`src/*.rs`。
- 没有 `Cargo.toml`，没有 serde，没有 Python binding，也没有 JSON-RPC wire schema。
- `schema.json` 只记录方法名字符串，例如 `"StoreContract": "append/read/checkpoint"`。

**各 trait 的真实方法**

| iface | trait 方法 |
| --- | --- |
| store | `append` / `read(session, from, limit)` / `checkpoint` |
| session | `create` / `advance` / `suspend` / `resume` / `archive` / `generation` / `drain_inbox` |
| policy | `check` / `record_audit` / `request_approval`，外加默认拒绝的 `check_egress` / `check_delegation` / `review` |
| loop | `describe` / `step` / `interrupt` / `status` |
| model | `call` / `capabilities` |
| context | `assemble` / `rebuild_capabilities` / `trace_input` |
| tool | `register` / `list` / `invoke` / `abort` |
| extension | `describe` / `on_assembly_intent` / `assembly_status` / `deactivate` |
| env | `FsBackend`：`read_file` / `write_file` / `list_dir` / `stat`；`ExecBackend`：`exec`（同步）/ `signal` / `terminate` |

**文档与 trait 的漂移**
- 顶层 README 列出的以下方法，在源码中都不存在：
  - session 的 `facts/list_ids/count`
  - store 的 `read_from/last_cursor/verify/node`
  - policy 的 `check_sync`
- `iface-policy` 的 schema 写的是 `authorize*`，trait 实际叫 `check*`。
- `iface-session` 的 schema 写了 `attach/detach`，trait 里没有这两个方法。
- 本地 `mint.toml` 写的是 `kind = "iface"`，这要依赖一个本地修改、未提交的 mint 分支（`PACKAGING-NOTES.md:150-190`）。线上制品实际是 `kind = "bundle"`，`provides = {interfaces, skills}`，并附带 `skills/<名>/SKILL.md`。

**共享类型**：`iface-types` 已经提供以下类型，新契约应直接复用：
- `Error { category, code, message }`
- `RequestState`（含 `Unknown`）
- `Verdict`（`Completed/Incomplete/Unknown`）
- `CallMeta`

## D.2 Mint 与 MintHub 实况

**CLI 0.1.11**

- **cpmrt**：`which cpmrt` 找不到。
- **kind 枚举**：`core host plugin overlay bundle skill mcp preset template app agent`，其中没有 `iface`。用 `kind=iface` 调 MintHub 搜索 API，直接报错。
- **plugin 的 subkind**：`wasm / native / js`。
- **`provides` 的强类型字段**：`tools / skills / presets / templates / mcp_servers / commands / agents / hooks / ui / runtime_capabilities`。没有 `interfaces` 和 `loops`，这两个键只会被原样透传，不做校验。
- **`requires` 字段**：只有 `api / flavors / wasm_api / capabilities`，没有 `requires.interfaces`。
- **子命令**：
  - `mint pull` 存在，会递归拉取依赖。
  - `mint inspect` 只有 `--remote`，没有 `--abilities`。
  - `mint loop` 不存在。
- **`mint run --json`**：headless 执行内核，输出 NDJSON，最后一行固定是 `done`。

**本机运行时**

- `~/.mint/cores/` 下有 `0.1.6-core`（默认）和 `0.1.12-std`。
- 0.1.12 的二进制是 `mint-core`、`mint-host`、`mint-ax-helper`，其中检索不到 `loop/next`、`[loop]`、`cpmrt`。

**MintHub 线上**

- `agentcpm/` 下有 10 个 `iface-*` 包，都是 `bundle 0.1.0`。例如 `iface-store`：`"provides":{"interfaces":["store"],"skills":["iface-store"]}`。
- 唯一真正的 loop 实现是 `pengchunyi1/graph-loop`：`plugin/native`，`provides = {"loops":["graph"], "component_protocols":["agentcpm-graph-loop/1"]}`，按平台分发制品。它没有声明 `interfaces`，也不依赖 `agentcpm/iface-loop`。
- `wujiahe/knowledge-local` 是 `plugin/native`，能力声明为 `exec: ["node", "$PKG/bin/agentcpm-knowledge"]`。这说明 native 包可以通过启动器拉起一个解释器。
- 线上已有 4 个 `kind=mcp` 的包。
- 没有任何 rsi 包。

**官网文档**

- **Loop 部分**：
  - 走 stdio 行分隔 JSON-RPC，握手用 `initialize`，单步用 `loop/next`，返回 `answer` 或 `stop`。
  - 出错时只 warn，并回退到内置 loop。
  - 没有定义请求结构、取消确认和重入语义。
- **原文**：“`provides.loops / provides.protocols / provides.interfaces` 是包的权利声明，声明不等于启用”。
- **契约包部分**：“只定义形状，不含实现，也不带运行时依赖”，示例命令是 `mint pull agentcpm/iface-loop`。
- **未涉及的内容**：Python 或 sidecar 组件、storage 和 memory 的 iface、推荐的包粒度。

## D.3 方案中平台说法的核对

| 说法 | 结论 |
| --- | --- |
| A：CLI 0.1.11，没有 cpmrt | 属实 |
| A：旧 mint-core 0.1.6 | 部分过时：本机还装了 0.1.12-std，默认仍是 0.1.6 |
| A：IFace 方法映射表 | 准确。store 和 extension 的链接指向结构体，trait 实际在 L15 和 L32 |
| B：`kind=iface` 被拒，线上是 bundle 加 `provides.interfaces` | 属实，还应补上 `skills/` 和 `provides.skills` |
| B：契约用 `pull` | 与文档示例一致；“不能用 add”是推断 |
| B：bundle 只装载 `skills/` | 与文档原话一致；线上有 bundle 声明了 `mcp_servers`，但未验证是否被装载 |
| B：没有 `requires.interfaces` | 属实 |
| B：Python sidecar 不能用 plugin | 过严：native 加启动器有先例 |
| 平台笔记：mcp 是“路线图” | 过时：线上已有 4 个 mcp 包 |
| B：`<iface>.data` 命名 | 自创约定。Mint 不校验，也不赋予任何语义 |

## D.4 两份方案共同遗漏的源码阻塞（详细）

1. **评测器指纹绑定了模块路径。**
   - [`evaluator_fingerprint`](../../../../apps/plugins/rsi-toolkit/service/rsi/evaluation.py#L257) 把 `type(evaluator).__module__ + "." + __qualname__` 算进哈希。
   - `qualification_matches`（`:352`）要求哈希完全相等。
   - 类一换命名空间，已有的 qualification 就全部失效，campaign 会退回 `needs_qualification`；re-export 也解决不了。
   - `verifier_description`（`control/evidence.py:81`）同样带模块名，搬动后 `_check_measurement`（`control/controller.py:288`）会把正在运行的 run 判为漂移。
2. **包初始化文件预先导入。**
   - `rsi/__init__.py` 会预先导入 `store` 和 `experience`。
   - `control/__init__.py` 会预先导入 `Controller`，进而带进全部 harness learner、`harness.store.db` 和 yaml。
   - 实测：只导入 `rsi.promotion`，就会加载 35 个项目模块外加 jsonschema；导入 26 行的 `control.redaction`，会加载 28 个模块。
3. **包级循环依赖。** `rsi.store` 依赖 `toolkit.contracts`，而 `toolkit/suite_verifier.py:8` 依赖 `rsi.evaluation`。
4. **依赖声明与代码不符。**
   - evaluation-kit 和 component-runner 都没有用到 measurement-evidence。
   - evaluation-kit 实际依赖的是 paired-evidence（`rsi/evaluation.py:16`）。
   - recall-selection 导入了 `rsi.experience.RecallPolicy` 和 `rsi.store`（`rsi/policy.py:10-11`）。
   - component-runner 写死了 `runpy.run_module('rsi.worker')` 和 `RSI_ROOT`（`rsi/components.py:175-176`、`:334-335`）。
5. **13 个模块之外的职责。**
   - `Host` Protocol 和 `normalize_result`（`connectors/common/host.py`）
   - schema loader（`toolkit/contracts.py`）
   - trace 归一（`toolkit/m0_legacy.py:86-138`）
   - `Store.backup/restore`（`rsi/store.py:575-617`）
   - control 平面运行时依赖的 `benchmarks`
   - 另一套 staging：`MintHost._stage`（`connectors/mint/host.py:76-101`）
6. **存储层不足以支撑工作单元（UoW）。**
   - `0001_core.sql` 一次建出全部表，这个文件名已经记录在用户库里。
   - `Store.tx` 嵌套时没有 savepoint，也没有锁，并且用了 `check_same_thread=False`。
   - 应用层有 3 处直接写 SQL（`experience.py:134`、`:215`，`campaign.py:95`）。
7. **规模失衡。** 13 个模块合计约 2,350 行，只占七个顶层包约 18,650 行的 13%。

## D.5 方案 A 已确认的缺口

| 缺口 | 证据 |
| --- | --- |
| `ingest_trace` 跨多个事务，先查后写 | `rsi/experience.py:214-243`；去重检查在 `:134`、`:215`，都在事务外 |
| `CampaignService.release` 没有认证、TTL 和一次性消费 | `rsi/campaign.py:83-101` |
| `put_release_set` 不切换 `asset_release` | `rsi/store.py:550-554`；`rollback_release_set` 没有使用 `approval_ref`（`:562-572`） |
| 召回使用 latest index | `rsi/runtime.py:49` |
| `execution_id` 没有统一校验 | `rsi/evaluation.py:421-426` |
| Selector 回退为 `lexical-fallback` | `rsi/policy.py:60-70`；`timeout_ms`、`min_corpus` 只做了解析，从未执行 |

## D.6 方案 A 的事实偏差与模块规模

**事实偏差**
- `Store` 共 44 个方法（B 写的是约 50 个）。
- 资产区间 `store.py:452-572` 中混入了 `put_component/put_promotion/get_promotion`（516-537）。
- `History` 在 L17，不在 L18。
- `create_bank` 结束于 339 行。
- evaluation 的实际区间是 18-391。
- promotion 的区间漏了 11-12 行的 `PromotionError`。

**模块规模（约数）**

| 模块 | 规模 |
| --- | --- |
| storage-sqlite | 75 行 |
| content-store | 90 行 |
| workspace-assets | 48 行 |
| model-client | 61 行 |
| measurement-evidence | 125 行 |
| trace-archive | 44 行，另加 66 行 loader |
| experience-ledger | 290 行 |
| lexical-recall | 186 行 |
| recall-selection | 94 行 |
| evaluation-kit | 410 行 |
| paired-evidence | 61 行 |
| component-runner | 576 行 |
| asset-ledger | 95 行 |

**第三方依赖**：`pyproject.toml` 声明了 pyyaml、jsonschema、mcp、openpyxl、uvicorn、websockets。本机 venv 里的编译型扩展有 `rpds`（经 jsonschema 引入）、`pydantic_core`（经 mcp 引入）、`_yaml`。
