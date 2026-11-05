# ql-audit → Mint 插件：调研与实施方案（模块化拆分）

> 状态：过期。本文为方案 A（四包），实现于 `apps/plugins/ql-audit-plan-a`；主线 `apps/plugins/ql-audit` 采用方案 B（7 包），设计与计划以 [`apps/plugins/ql-audit/docs/design.md`](../../apps/plugins/ql-audit/docs/design.md)、[`implementation-plan.md`](../../apps/plugins/ql-audit/docs/implementation-plan.md) 为准。

> 日期：2026-10-30  
> 基线代码：`/Users/payne/Vibe/AgentCPM-agent-evolution/products/ql-audit/`  
> 目标仓库：MintHub `https://mint-hub.ea.modelbest.co`  
> 实测环境：`mint` CLI 0.1.11、`mint core` 0.1.14（aarch64-apple-darwin）、Node.js 24.21.0  
> 本版重点：按 MintHub 基础插件思路，把单包 14 工具拆成 `base` + `policy` + `review` + `meta` 四包、三个 MCP 服务。  
> 与另一版 7–8 包提案的对比：[两版模块化方案对比](../dev/ql-audit/2026-10-30-modular-comparison.md)

---

## 0. 结论摘要

1. **形态仍是 `kind = "bundle"` + `.mcp.json`，但拆成“基础插件 + 两个能力插件 + 组合包”4 个包、3 个 MCP 服务。**
   - `lingcai/ql-audit-base`（基础插件）：配置、健康检查、规则目录只读，6 个工具；
   - `lingcai/ql-audit-policy`（制度侧）：制度 PDF → 规则版本，4 个工具，依赖 base；
   - `lingcai/ql-audit-review`（审核侧）：报文 + 规则 → 审核，4 个工具，依赖 base；
   - `lingcai/ql-audit`（组合包）：无 MCP，只依赖前三个并带总 SKILL，用于一键安装。

   共享代码（config、store、catalog、qlengine 客户端、MCP runtime）只在 base 维护一份；policy/review 的启动器调用 base 的同一套运行时，把 `policy|review` 作为组参数，只注册本组工具。只装制度侧时不会加载审核工具，反之亦然。
2. **14 个工具按服务拆分，总数不变。**
   - base 6：`ql_get_health`、`ql_get_config`、`ql_set_config`、`ql_list_versions`、`ql_list_scenes`、`ql_list_rules`；
   - policy 4：`ql_parse_policy`、`ql_get_parse_status`、`ql_resolve_parse`、`ql_list_parses`；
   - review 4：`ql_load_bill`、`ql_get_preflight`、`ql_run_audit`、`ql_get_result`。

   实际工具名带服务前缀，例如 `ql-audit-base__ql_get_health`、`ql-audit-policy__ql_parse_policy`、`ql-audit-review__ql_run_audit`；SKILL 必须写全名。
3. **RSI（规则优化）不暴露。** 它不属于用户要的两个能力，且多出 10 个工具、确认门禁与候选/度量语义。代码保留在 `core/` 但不注册工具、不写进 SKILL；如未来需要，另立 `lingcai/ql-audit-rsi` 依赖 base，不改变本组合包的工具面。
4. **iface 只做“语义/JSON 形状对齐”，不声称实现 Rust trait。** `iface-tool`/`iface-policy` 是内核侧 trait 契约（`parameters: Vec<u8>`、`ReviewVerdict` 等），JS/MCP 无法实现；且 `AuditSink` 在 iface-policy 包内未接线。本插件复用 `ReviewVerdict` 的稳定串、`ReviewPosition` 的语义、`ReviewAuditEvent` 的字段形状，留痕走自己的 append-only JSONL。
5. **产品决策：** 组合包名保持 `lingcai/ql-audit`（已确认）；本方案建议新增 `lingcai/ql-audit-base`、`lingcai/ql-audit-policy`、`lingcai/ql-audit-review` 三个子包；许可证全部保持 `AGPL-3.0-only`；RSI 不暴露；保留默认 endpoint，同时支持对话修改并本地持久化（v0.1 用 `config.json` 0600 原子写；SQLite 作为可选后端）。仍需确认：目标平台（macOS/Linux）、是否随包带内网 CA（公开分发不建议）、三个子包名与是否上架。
6. **实测暴露的 Mint 约束**（都已纳入设计）：
   - `kind = bundle` **不能声明 `capabilities.env`**；`.mcp.json` 里的 `${HOME}` 不会展开，数据目录必须由服务端用 `os.homedir()`/`MINT_HOME` 解析。
   - 包内出现 `*.pem` 会让 `mint pack` **直接失败**；CA 必须改成 `.crt`。
   - `command[0]` 的 basename 必须在 `capabilities.exec` 里；`$PKG` 在 command 与 args 中都会被替换。
   - MCP 工具的 `ToolKind` 由**工具名关键字**猜测（`get/list/search` → Search，`run` → Execute，其余 → Other）；Other/Execute 会触发审批。工具命名直接决定审批体验。
   - bundle 的 MCP 子进程**不被 capabilities 沙箱约束**；`net`/`exec` 是披露与准入声明，不是运行时隔离。
   - **多个 bundle 的 `.mcp.json` 会各自拉起一个 MCP 服务**；传递依赖也会装、也会加载。服务 ID 必须全局唯一，工具名变成 `<server_id>__<tool>`。
7. **模块化已做最小 POC（Mint core 0.1.14）**：三个 bundle（base/policy/review）通过 path 依赖安装，`mint add` 自动带入传递依赖 base；一次会话同时加载 3 个 MCP 服务，成功调用 `ql-audit-base__base_ping`、`ql-audit-policy__policy_ping`、`ql-audit-review__review_ping`。这验证了“共享 base + 两个能力服务”的运行时可行性；真实 ql-audit 工具的拆分实现尚未开始。

---

## 1. 目标与边界

### 1.1 两个核心能力

| # | 能力 | 实现包 | 输入 | 输出 |
|---|---|---|---|---|
| ① | 制度规则提取 | `lingcai/ql-audit-policy`（依赖 base） | 一个制度 PDF（也支持 `.docx/.md/.txt`） | 一个可审核的**规则版本**（`version_id`），含规则、前置条件、场景、可执行性 |
| ② | 报文审核 | `lingcai/ql-audit-review`（依赖 base） | 一个报销报文（JSON）+ 规则版本 | 审核结论、计数、逐条结果、Markdown 结果卡、可追溯的 run 记录 |
| 共享 | 配置/健康/规则目录 | `lingcai/ql-audit-base` | — | config、catalog 查询、健康状态 |

“提取相应规则”不只返回一段文本，而是产出 ql-audit 现有的 **catalog version**：每条规则带 `ql` 表达式、场景、前置条件、`compileOk/executable`，供能力②直接使用。

### 1.2 非目标（v0.1）

- 不做本地 PDF 文本抽取/OCR；PDF 解析仍由 Rulecraft V3 完成（本地只做上传、轮询、裁定、映射、编译、封版）。
- 不做 Web 面板/侧边栏；Mint 没有与 PilotDeck `web-plugin-host/v1` 等价的 UI 契约。交互走对话 + Markdown 结果卡。
- 不暴露 RSI 的 7 步闭环（数据集、轨迹、诊断、补丁、确认、应用、复测）；代码可保留在 `core/`，但不注册工具、不进入 SKILL。若未来需要，另立包或加显式开关。
- 不做规则在线编辑器；规则只读检视 + 版本追加。
- 不做多租户/多用户服务端；数据目录是单用户本地目录。

### 1.3 成功标准

1. 干净项目里 `mint add lingcai/ql-audit` 后，`mint run` 能加载 3 个 MCP 服务、14 个工具；`ql-audit-base__ql_get_health` 返回引擎与配置状态。
2. 只装 `lingcai/ql-audit-policy` 时，只加载 base + policy 两个服务、10 个工具；审核工具不存在。只装 `lingcai/ql-audit-review` 时对称，base + review 10 个工具。
3. 用真实制度 PDF 走完解析链，得到 `ready` 与新的 `version_id`；`ql-audit-base__ql_list_rules` 能看到提取出的规则。
4. 用真实报文走完审核链，得到 `counts`、`card` 与持久化的 `runs/<runId>/result.json`。
5. 审核结论能映射为 `approve / reject / needs-human / revise`，并有 append-only 留痕。
6. 安装包不含密钥、报文、`.pem`、`config.json`；数据文件 0600；日志不含报文内容与凭据。
7. `ql-audit-base__ql_get_config`/`ql_set_config` 能通过对话改 endpoint/CA，落盘 0600，下一次调用（包括 policy/review 服务）生效；密码不出现在参数/返回/日志。
8. 迁移后的 55 个既有测试全部通过，新增契约测试通过；4 个包能按 base→policy/review→meta 顺序 pack/publish。

---

## 2. 现状调研

### 2.1 ql-audit 的代码结构

`products/ql-audit/plugins/ql-audit/` 共 42 个文件、约 1.1 MB、**零第三方依赖**（`package.json` engines `node >=22.13 <23`，实测 Node 24 也可运行）。

| 模块 | 职责 | 与宿主的关系 |
|---|---|---|
| `server/audit.mjs`（294 行） | 纯函数：选规则、拼 batch、前置门控 + 后置判定、计数、结果卡、报文归一化、场景推荐、静态预检 | 无 |
| `server/service.mjs`（399 行） | 业务编排：配置、报文入库、版本合并、场景、预检、审核、run 历史、字段表 | 无（`createAuditService({dataDir})` 已依赖注入） |
| `server/parse.mjs`（232 行） | 解析 job 状态机、`.lock`、裁定重跑、后台建版本 | 无（远端 Rulecraft + 本地 fs） |
| `server/catalog-builder.mjs`（169 行） | 规则包 → 版本：逐条 `/compile`、可执行性判定、场景分组、`appendVersion` | 无（远端 qlengine `/compile`、`/health`） |
| `server/rulecraft.mjs`（62 行） | Rulecraft V3 客户端：multipart 上传、ingest 查询、规则拉取 | 远端 HTTPS + 自签 CA |
| `server/qlengine.mjs`（50 行） | qlengine 客户端：`/health`、`/compile`、`/execute/batch`，BasicAuth，自签 CA | 远端 HTTPS |
| `server/http.mjs`（48 行） | `expandHome`、`loadCa`、URL 拼接、超时与错误映射 | 无 |
| `server/json-scan.mjs`（42 行） | 自写 JSON 扫描器，返回首个语法错误偏移 | 无 |
| `mcp/server.mjs`（374 行） | 无依赖 stdio MCP（换行 JSON-RPC 2.0），当前 22 个工具 | 标准协议 |
| `server/host.mjs`、`server/main.mjs`、`server/app.mjs` | PilotDeck 宿主握手、身份头、HTTP RPC 路由、drain | **必须重写/删除** |
| `browser/index.mjs`（858 行） | PilotDeck Browser API v2 单文件面板 | **不复用** |
| `skills/ql-audit/SKILL.md`、`commands/*.md` | 对话流程与 slash 命令 | 需改工具名与交互方式 |
| `catalog/*.json` | 随包版本、字段别名表、未支持字段登记 | 原样随包 |

**可迁移内核约 2.4k 行纯 Node**：`audit.mjs + service.mjs + parse.mjs + catalog-builder.mjs + qlengine.mjs + rulecraft.mjs + http.mjs + json-scan.mjs`。宿主胶水（约 450 行）、面板（858 行）、PilotDeck 元数据属于重写面。

### 2.2 能力①：制度 PDF → 规则

#### Rulecraft V3 协议

- 缺省地址 `https://123.56.15.233/rulecraft`，CA `~/.config/harness/rulecraft-ca.pem`，项目缺省 `pilotdeck`。
- `POST /api/projects/{pid}/docs`：multipart，`file` + 可选 `resolutions`（全量裁定 JSON）→ 202 `{taskId, docId, status}`。
- `GET /api/projects/{pid}/ingest/{taskId}` → `{status, stage, progress, progressMessage, error, result}`。
- `GET /api/projects/{pid}/rules` → `{rules[], preconditions[]}`，是**整项目全量**，必须按 `docId` 过滤。
- 该客户端**不发认证头**，只走 HTTPS + 显式自签 CA；BasicAuth 只属于 qlengine。
- 支持 `.pdf/.docx/.md/.txt`；**PDF 解析完全在远端**，本地没有 PDF 库。

#### 状态机

```
running（排队/解析）
  ├─ 有未裁定项 → needs_resolution
  │     └─ resolve（全量裁定重提）→ running → ...
  ├─ 解析完成 → building（逐条 /compile，后台）
  │     ├─ 成功 → ready（追加 catalog version）
  │     └─ 失败 → failed / 留在 building 并按 30s 重试
  └─ 远端失败 → failed
```

关键行为：

- jobId = `YYYYMMDDTHHMMSS-<内容 sha256 前 8>`；同秒同文件重传 → 409 `PARSE_EXISTS`。
- 落盘 `<dataDir>/parses/<jobId>/{job.json, source.<ext>, .lock}`；`source.<ext>` 必须保留，裁定重跑要重读原文件。
- `.lock` 是 O_EXCL，20 分钟视为陈旧；拿不到锁时直接返回当前状态。
- 每次 `status` 查询推进一步；没有后台守护进程。最小轮询间隔 5 s；面板 10 s；解析约 10 分钟。
- 待澄清项来自 `envelope.result.deferred[]`，`options[0]` 是系统建议；必须全答或显式 `use_defaults`。
- 建版本：`rulecraft().rules()` → `toPackage()` 过滤本 `docId` → `buildVersion()` → `appendVersion(<dataDir>/catalog.json, version)`。
- 版本 id = `v-<treeHash8>-<YYYYMMDD>`；同 id 幂等覆盖，不删除旧版本（没有回滚 API）。

#### 规则产物

```json
{
  "id": "v-02482cdb-20261020",
  "name": "XXXX人寿报销手册 2026-02（2026-09-30 规则包）",
  "package": { "doc": "XXXX人寿报销手册", "treeHash": "02482cdb..." },
  "builtAt": "2026-10-20T09:05:36.076Z",
  "measurementVersion": "qlexpress4-4.1.3+3vl#7318b8b3411f",
  "scenes": [
    { "id": "common", "name": "发票/附件/表单-通用规则", "clausePrefixes": [], "categoryHints": [], "ruleKeys": ["..."] }
  ],
  "rules": {
    "<key>": {
      "id": "...",
      "name": "报销票据须为税务监制正式发票或行政事业单位收款收据",
      "clauseId": "...",
      "scene": "发票/附件/表单-通用规则",
      "action": "...",
      "assertText": "...",
      "errorMsg": "...",
      "preIds": ["..."],
      "ql": "...",
      "compileOk": true,
      "executable": true
    }
  },
  "preconditions": {
    "<key>": { "id": "...", "name": "...", "ql": "...", "assertText": "...", "errorMsg": "...", "compileOk": true }
  }
}
```

随包目录实测：1 个版本、446 条规则（394 条可执行；MANUAL 39、NO_QL 6、PRE_NOT_EXECUTABLE 7）、281 条前置、39 个场景；`fields.json` 365 个别名 + 39 个集合；`known-unsupported.json` 32 条。

### 2.3 能力②：报文 + 规则 → 审核

#### qlengine 协议

- `GET /health`（10 s）→ `{measurementVersion, ...}`。
- `POST /compile {ql}`（20 s）→ `{ok, errorCode?}`。
- `POST /execute/batch`（120 s）：
  ```json
  {
    "payload": "<归一化后的报文>",
    "fields": "<别名 → JSONPath[]>",
    "collections": "<别名 → JSONPath>",
    "mode": "both",
    "rules": [{ "key": "pre:<id>|rule:<id>", "ql": "..." }]
  }
  ```
  响应 `{measurementVersion, results:[{key, verdict, errorCode?, error?, missing?}]}`。
- 鉴权：有 username 时 `Authorization: Basic ...`；密码来自内存/config/钥匙串；头不落日志。
- TLS：显式 `ca:`，**不继承 `NODE_EXTRA_CA_CERTS`**；读不到 CA → `QLENGINE_CA_UNREADABLE`。

#### 判定表（`audit.mjs`）

| 情形 | 结果 | 计数 |
|---|---|---|
| 任一前置 `false` | 不适用 `inapplicable` | 不计入执行总数 |
| 前置执行异常 | 执行异常 `error` | errors |
| 任一前置 `null`（缺数据） | 需复核 `review`，**优先于后置结果** | failed（review） |
| 后置 `true` | 通过 `pass` | passed |
| 后置 `false` | 未通过 `fail` | failed |
| 后置 `null` | 未通过 `missing` | failed（missingData） |
| `PARSE/EVAL/INTERNAL` 等 errorCode | 执行异常 `error` | errors |
| 目录标不可执行 | 跳过 `skipped` | 不计入 |

- `counts = {passed, failed, review, missingData, errors, inapplicable, skipped}`，`failed = fail + missing + review`，`executed = passed + failed + errors`。
- `overall = failed + errors > 0 ? "不通过" : "通过"`。
- 引擎零结果 → 全部执行异常（`NO_RESULT`），**绝不误判通过**。
- 一次 `/execute/batch` 同时算前置与后置（`mode: "both"`），key 为 `pre:<id>` / `rule:<id>`。

#### 结果卡与留痕

- `renderCard(run, 'post'|'all')` 输出 Markdown：首行“单据编号… 审核结果…”，含执行统计、warning、数据缺口 Top8、规则表。
- `runs/<runId>/result.json` 0600；结果不含报文原文。
- `.ql-audit/calls.jsonl` 记录 op/endpointHost/billId/versionId/ruleCount/overall 等，**不含报文内容、金额、凭证、Authorization**。
- `runId` = `YYYYMMDDTHHMMSSmmm-<billId 前 8>[-n]`；多次审核同一单会生成多个 run（历史保留）。

### 2.4 可复用的契约资产

这些比代码更值得冻结：

| 资产 | 内容 | 迁移策略 |
|---|---|---|
| `ql-audit.catalog/v1` | `{protocol, versions:[...]}` | 原样保留；新增版本只追加 |
| `ql-audit.field-overlay/v1` | `{fields, collections, provenance[]}` | 文件保留，不启用（RSI 不暴露） |
| `ql-audit.rsi-datasets/v1` | 数据集格式 | 文件保留，不启用 |
| `runId` / `jobId` 正则 | 文件名与可读排序 | 保留 |
| 错误码集合 | `BILL_*`、`VERSION_*`、`QLENGINE_*`、`RULECRAFT_*`、`PARSE_*` | 保留并补 `STORE_*`、`CONFIG_*` |
| 22 个 MCP 工具名/schema | 现有对话契约 | 收敛为 14 个，保留语义 |
| 结果卡 Markdown 版式 | 人读输出 | 保留；模型原样展示 |
| 判定表 | 合规口径 | 原样保留，逐分支测试 |

### 2.5 必须重写/删除的部分

1. `host.mjs`/`main.mjs`：`PLUGIN_*` 环境、stdout `{ready,port,generation}` 握手、`host.drain`/`plugin.drained`。
2. `app.mjs`：`x-plugin-runtime-token/owner-id/generation` 三头校验、`/v1/*` 路由、base64 body。
3. `browser/index.mjs`：PilotDeck Browser API v2，Mint 无等价物。
4. `plugin.json`/`manifest.json`/`product.json`：PilotDeck 元数据与 `${pluginRoot}`/`${pilotHome}` 占位符。
5. `SKILL.md` 与 `commands/*.md`：`mcp__ql-audit__*` → `ql-audit-base__*` / `ql-audit-policy__*` / `ql-audit-review__*`（按能力归属）；`request_user_choice/form` → 对话提问。
6. `scripts/install-to-pilotdeck.mjs`、`plugins-shared/sync-shared.mjs`：PilotDeck 安装同步。

---

## 3. Mint 形态选型

### 3.1 候选形态

| 形态 | 说明 | 关键限制 |
|---|---|---|
| **bundle + `.mcp.json`（选）** | `kind="bundle"`，携带 skills/catalog/certs，启动 Node stdio MCP | 需要 Node；MCP 子进程不受沙箱约束 |
| `plugin` / `subkind="js"` | V8 isolate 里注册 JSON-Schema 工具 | 无 fs、`net.fetch` 默认关闭且 1 MiB、60 s 毒化、无自签 CA、不能带 skills |
| `plugin` / `subkind="native"` | 原生 sidecar + JSON-RPC | 当前 checkout **没有 native sidecar loader**；且 plugin 不能带 skills |
| WASM | wasm host | 当前未集成（`capabilities.rs` 明确未接） |
| `kind="mcp"` 单包 | 只装 MCP 服务 | 不能带 skills/catalog；可作为 v0.2 的服务形态（v0.1 先用 bundle） |
| 本地 PDF + 模型抽取 | 不依赖 Rulecraft | 质量/工作量不可控；PDF 版式与条款结构复杂 |

### 3.2 决策矩阵

| 需求 | bundle+MCP | plugin/js | native sidecar | wasm |
|---|---|---|---|---|
| 读取用户上传的 PDF（最大 50 MB） | ✅ Node fs | ❌ 无 fs；base64 受 1 MiB 限制 | ✅ | ❓ |
| 调远端 Rulecraft/qlengine + 自签 CA | ✅ Node https `ca:` | ❌ `net.fetch` 默认关闭、无自定义 CA、请求/响应 1 MiB | ✅ | ❓ |
| 解析 10 分钟 / 多次轮询 | ✅ 每轮一次 status | ❌ 单次 60 s 且超时毒化 isolate | ✅ | ❓ |
| 规则版本落盘 | ✅ fs | ❌ 只有会话级 store | ✅ | ❓ |
| 携带 skill/对话流程 | ✅ `skills/` | ❌ plugin 不能带 skill | ❌ | ❌ |
| 安装复杂度 | 低（Node） | 低 | 高（多平台制品） | 高 |
| 当前可用性 | **已实测** | 可用但能力不足 | **loader 不在当前 checkout** | 未集成 |

### 3.3 为什么是 bundle+MCP

- ql-audit 的 MCP 服务已经是**零依赖、标准 stdio MCP**，是现成资产；bundle 只负责把它装进 Mint。
- bundle 可以同时带 `skills/*/SKILL.md`、`catalog/`、`certs/`，这是 JS 插件和 native 插件都做不到的。
- bundle 之间可以用 `[dependencies]` 组合：Mint 会递归安装依赖，并加载**每个** bundle 的 `.mcp.json`；因此“共享 base + 两个能力服务”不需要改内核。
- 不需要改内核、不需要等 native loader、不需要多平台制品；`layout = "any"`。
- 实测已证明：Mint 能替换 `$PKG`、拉起 Node、注册带服务前缀的工具并完成真实审核；多 bundle/多 MCP 服务也已用最小 POC 跑通。

### 3.4 实测证据（2026-10-30）

先用一个最小 bundle（`mint.toml` + `.mcp.json` + `skills/ql-audit/SKILL.md` + `bin/ql-audit-mcp` + `certs/*.crt`）在 `/tmp` 项目实测。下面这段是最初的单包 POC，服务 ID 为 `ql-audit`；模块化后改名为 `ql-audit-base/policy/review`。

```text
mint 0.1.11
mint core 0.1.14 (aarch64-apple-darwin)
node v24.21.0

mint pack                         → local-ql-audit-poc-0.1.0.mint.tar.zst
mint add path:/tmp/ql-audit-poc   → 安装到 .mint/packages/local/ql-audit-poc@0.1.0
mint-core run --cwd ... --approve all "调用 ql_list_versions"
                                  → ql-audit__ql_list_versions
                                  → v-88371ec6-20261029、v-02482cdb-20261020
```

真实审核（Mint core 0.1.14 + 真实 qlengine + 真实报文，数据目录 `/tmp/ql-audit-real`）：

```text
ql-audit__ql_load_bill → billId: 0d70baf6244e, invoiceCount: 2
ql-audit__ql_audit     → run_id: 20261030T030925776-0d70baf6
                         overall: 不通过
                         counts: { passed: 0, failed: 49, review: 49, missingData: 0,
                                   errors: 0, inapplicable: 4, skipped: 4, executed: 49 }
                         card: Markdown 结果卡
```

> 这次用的是真实 qlengine 与真实报文；49 条“需复核”是因为该报文缺少附件/影像字段，不是插件缺陷。它验证了 BasicAuth、CA、`/execute/batch`、计数与结果卡全链路。

> 环境备注：本机 `0.1.14-std` 制品里的 `mint-core`/`cpmrt` 自报“编译档位 core”，`mint run` 以 `flavor=std` 启动会报 `此二进制不支持请求档位 std`；本次用 `mint-core 0.1.14` + 项目 `flavor=core` 完成验证。发布前需在正常的 `0.1.14-std` 环境复验 `mint run`，或等官方修复该制品。

**多包 / 多 MCP 服务 POC（`/tmp/ql-mod-poc`）**

三个最小 bundle，base 提供共享运行时，policy/review 通过 path 依赖 base，启动器从同级目录定位 base 并以组参数启动同一份 `server.mjs`：

```text
/tmp/ql-mod-poc/
├── base/    lingcai/ql-audit-base@0.1.0    .mcp.json → ql-audit-base
├── policy/  lingcai/ql-audit-policy@0.1.0  depends base; .mcp.json → ql-audit-policy
└── review/  lingcai/ql-audit-review@0.1.0  depends base; .mcp.json → ql-audit-review
```

```text
mint add path:/tmp/ql-mod-poc/policy
  → 安装 policy + 传递依赖 base（项目另声明 review，也一并安装）
  → .mint/packages/lingcai/{base,policy,review}@0.1.0

mint-core run --approve all "依次调用三个 ping"
  → ql-audit-base__base_ping   → base pong
  → ql-audit-policy__policy_ping → policy pong
  → ql-audit-review__review_ping → review pong
```

再加一个最小 meta 包（无 `capabilities`、无 `.mcp.json`、只带 `skills/`，依赖 base/policy/review）：`mint add` 后 lock 里 4 个包，会话仍只加载 3 个 MCP 服务，三个 ping 全部可用。这验证了组合包“零 MCP、零权限、只做依赖与 skill”的形态。

> 这个 POC 只验证“依赖安装 + 3 个 MCP 服务同时注册 + 同级 base 定位 + meta 组合”，不验证真实业务工具。它说明拆分不需要改 Mint 内核；真实工具拆分按 §7 实施。

### 3.5 实测发现的 Mint 约束

| 约束 | 现象 | 设计应对 |
|---|---|---|
| bundle 不能声明 `capabilities.env` | `mint pack` 报“kind = bundle 不得声明该权限” | 不声明 env；数据目录由服务端解析 |
| `${HOME}` 不展开 | 警告“capabilities.env 未声明这些变量”；值原样传入 | `.mcp.json` 不写 env；服务端用 `os.homedir()`/`MINT_HOME` |
| `*.pem` 让 pack 失败 | 报“不得打进文件 certs/xxx.pem” | CA 改名 `.crt`（PEM 内容不变） |
| `command[0]` 要在 `exec` 里 | 未声明时 MCP 不启动 | 每个包声明自己的启动器，如 `exec = ["ql-audit-policy", "node"]` |
| 工具名决定审批 | `ql_load_bill`/`ql_preflight`（Other）触发 Prompt；`ql_list_*`（Search）不触发 | 只读工具用 `get/list/read` 命名；写/外联工具保留 Other/Execute |
| bundle 的 MCP 子进程不受沙箱 | Node 以用户权限运行，`net` 只是声明 | 发布可信包、签名校验、企业允许列表；敏感场景用容器/VM |
| 技能必须 frontmatter | 缺 `---`/`description` 只警告不加载 | SKILL.md 首行 `---`，含 `name`/`description` |
| 默认数据目录 | 现有 MCP 用 `$PILOT_HOME/ql-audit`，会读到 PilotDeck 生产数据 | 改为 `~/.mint/ql-audit`，与 PilotDeck 隔离 |
| 多 bundle 的 `.mcp.json` 全部加载 | 一个项目装 3 个 bundle 就起 3 个 MCP 服务；服务 ID 不能重复 | 拆成 base/policy/review 三个唯一 ID；meta 不写 `.mcp.json` |
| 传递依赖会安装并加载 | `mint add policy` 自动装 base；base 的 `.mcp.json` 也会启动 | base 只放共享工具；policy/review 依赖它，不重复实现 |
| 工具名带服务前缀 | 实际是 `ql-audit-base__ql_get_health`，不是 `ql_get_health` | SKILL/契约测试写全名；错误提示带可用服务名 |
| bundle 技能从 lock 全量加载 | 装 policy 时 base 的 SKILL 也会注入 | base 放通用配置/隐私说明，policy/review 放各自流程 |
| 同级 base 定位 | policy/review 启动器需找到 base 安装目录 | 同 scope 同级目录 + `sort -V` 取最高；找不到时明确报错 |
| `server/discover` 要直接带 `tools` | Mint 先发 `server/discover`；只回 `protocolVersion` 时工具注册为 0，且不一定报错 | MCP 服务在 discover 结果里返回 `tools`（真实 ql-audit 已满足）；契约测试断言每个服务工具数 |

### 3.6 未来演进

- **v0.2**：若 Mint 落地 `kind = "mcp"` 独立包，base/policy/review 可改为 mcp 包，bundle 只做组合与 skill；工具契约不变。
- **v0.3**：Node SEA / Bun / Rust 单文件二进制，bundle 内按平台放 `bin/<triple>/` + 启动器；去掉 Node 依赖。
- **v0.3+**：若 Mint 落地 native sidecar loader，改 native 以获得 capabilities 沙箱；bundle 仍负责 skill 与依赖。
- **不优先**：WASM（当前未集成）、本地 PDF 抽取（质量与工作量不可控）。
- **RSI 不进入本插件工具面**：如未来要做，另立包（如 `lingcai/ql-audit-rsi`）或显式 opt-in，不改变 `lingcai/ql-audit` 的 14 工具契约。

---

## 4. 目标架构

### 4.1 组件图

按“一个共享运行时 + 三个 MCP 入口 + 一个组合包”组织。**业务代码只在 `lingcai/ql-audit-base` 里维护一份**；policy/review 包只有 `mint.toml`、`.mcp.json`、启动器和 SKILL，启动器定位 base 后以 `policy|review` 组参数复用同一份 `server.mjs`。

```text
┌────────────────────────────── Mint GUI / TUI ──────────────────────────────┐
│  ACP client（会话、审批、Markdown 渲染）                                    │
└───────────────────────────────────┬────────────────────────────────────────┘
                                    │ ACP
┌───────────────────────────────────▼────────────────────────────────────────┐
│ cpmrt / mint-core                                                           │
│  tool registry：                                                             │
│    ql-audit-base__*（6）  ql-audit-policy__*（4）  ql-audit-review__*（4）  │
└───────────────┬───────────────────────┬───────────────────────┬────────────┘
                │ stdio                 │ stdio                 │ stdio
┌───────────────▼──────────┐ ┌──────────▼───────────┐ ┌─────────▼────────────┐
│ ql-audit-base MCP        │ │ ql-audit-policy MCP  │ │ ql-audit-review MCP  │
│ group=base               │ │ group=policy         │ │ group=review         │
│ 配置/健康/catalog 只读   │ │ 制度 PDF→规则版本    │ │ 报文+规则→审核       │
└───────────────┬──────────┘ └──────────┬───────────┘ └─────────┬────────────┘
                │                       │                       │
                └───────────────────────┼───────────────────────┘
                                        ▼
                    lingcai/ql-audit-base 包内的唯一运行时
                    lib/mcp/server.mjs  base|policy|review
                    ┌──────────────────────────────────────────────┐
                    │ config / store / catalog / auth / http       │
                    │ rulecraft.mjs  qlengine.mjs                  │
                    │ parse.mjs  catalog-builder.mjs  audit.mjs    │
                    └───────┬───────────────────────┬──────────────┘
                            │ HTTPS+CA              │ HTTPS+CA+BasicAuth
                            ▼                       ▼
                    Rulecraft V3              qlengine
                    /docs /ingest /rules      /health /compile /execute/batch
                            │
                            ▼
                    ~/.mint/ql-audit/
                      config.json(0600) bills/ runs/ parses/
                      catalog.json .audit/events.jsonl
```

进程视角：

```text
base    bin/ql-audit-base    → node $PKG/lib/mcp/server.mjs base
policy  bin/ql-audit-policy  → 找同级 base → node $BASE/lib/mcp/server.mjs policy
review  bin/ql-audit-review  → 找同级 base → node $BASE/lib/mcp/server.mjs review
meta    （无 .mcp.json）      → 只装依赖 + 总 SKILL
```

- base 启动时只加载 `groups/base.mjs`；policy/review 同理，按 group 懒加载，避免每个进程都加载全部业务代码。
- 三个进程共享同一个 `~/.mint/ql-audit` 数据目录，通过原子写/文件锁协调；没有常驻守护进程。
- 组合包 `lingcai/ql-audit` 不写 `.mcp.json`，依赖三个子包；Mint 会加载子包的三个服务。
- policy/review 也可以单独安装：只装 policy 时只有 base+policy 两个服务（10 工具），只装 review 时对称。

### 4.2 解析时序

```text
用户 → Mint：上传制度 PDF
Mint → policy MCP：ql-audit-policy__ql_parse_policy { path }
MCP  → 磁盘：parses/<jobId>/source.pdf, job.json
MCP  → Rulecraft：POST /api/projects/{pid}/docs (multipart)
Rulecraft → MCP：202 { taskId, docId }
MCP  → Mint：{ job_id, status: "running", hint: "约 10 分钟" }

（用户过一会儿再问）

Mint → policy MCP：ql-audit-policy__ql_get_parse_status { job_id }
MCP  → Rulecraft：GET /ingest/{taskId}
Rulecraft → MCP：{ status: "needs_resolution", result.deferred: [...] }
MCP  → Mint：clarifications（问题、条款、引文、选项；options[0] 是建议）
用户 → Mint：逐项回答
Mint → policy MCP：ql-audit-policy__ql_resolve_parse { job_id, answers }
MCP  → Rulecraft：POST /docs（原文件 + 全量 resolutions）
... 重复直到 status = building / ready
MCP  → qlengine：逐条 POST /compile（并发 3，429 退避）
MCP  → 磁盘：catalog.json 追加 version
MCP  → Mint：{ status: "ready", version_id, rule_count, executable_count }
```

### 4.3 审核时序

```text
Mint → review MCP：ql-audit-review__ql_load_bill { path }（或 json）
MCP  → 磁盘：bills/<billId>.json（0600）
MCP  → Mint：{ billId, billNo, invoiceCount, duplicate }

Mint → base MCP：ql-audit-base__ql_list_versions
MCP  → Mint：版本列表（含随包 + 本地）

Mint → base MCP：ql-audit-base__ql_list_scenes { version_id, bill_id }
MCP  → Mint：场景列表（common 第一，recommended 启发式）

Mint → review MCP：ql-audit-review__ql_get_preflight { bill_id, version_id, scene_ids }
MCP  → 本地：静态扫描 QL 标识符
MCP  → Mint：{ summary: { rules, blocked, unmappedRules, ready }, missingAliases, ... }

Mint → review MCP：ql-audit-review__ql_run_audit { bill_id, version_id, scene_ids }
MCP  → qlengine：POST /execute/batch（一次，mode=both）
qlengine → MCP：{ measurementVersion, results: [...] }
MCP  → 本地：evaluate → counts/card；写 runs/<runId>/result.json + .audit/events.jsonl
MCP  → Mint：{ run_id, verdict, overall, counts, warning, card }

Mint → review MCP：ql-audit-review__ql_get_result { run_id }
MCP  → Mint：同一张 card（不调引擎、不重复留痕）
```

### 4.4 数据目录

```text
~/.mint/ql-audit/
├── config.json                 # 0600；ql_set_config 原子写；endpoint/caPath/username/keychainService/parse*
├── bills/
│   └── <billId>.json           # 0600；原始报文（去 BOM）
├── runs/
│   └── <runId>/result.json     # 0600；计数、规则结果、card；不含报文
├── parses/
│   └── <jobId>/
│       ├── job.json            # 状态机、裁定、taskId/docId
│       ├── source.<ext>        # 原文件，裁定重跑必需
│       └── .lock               # O_EXCL，20 分钟陈旧
├── catalog.json                # 本地追加的规则版本（与随包合并）
├── fields.overlay.json         # 文件保留，不启用（RSI 不暴露）
└── .audit/
    └── events.jsonl            # append-only；审核/解析留痕
```

原则：

- 目录 0700，文件 0600（沿用 ql-audit 的权限；`catalog.json` 也按 0600 写，规则正文可能含制度细节）。
- 不把报文、金额、发票号、凭据写进 `.audit/events.jsonl` 或 stderr。
- 错误消息截断 200 字符再落盘。
- 卸载插件不删除数据；提供手动清理说明（v0.2 可加 `ql_prune`）。

### 4.5 配置、修改与持久化

`config.json` 沿用现有字段，补 `version`：

```json
{
  "version": 1,
  "endpoint": "https://123.56.15.233:19999",
  "caPath": "",
  "username": "operator",
  "password": "",
  "keychainService": "qlengine-harness",
  "parseEndpoint": "https://123.56.15.233/rulecraft",
  "parseCaPath": "",
  "parseProject": "pilotdeck"
}
```

语义：

- `endpoint`/`parseEndpoint` 留空 → 用内置缺省；保留默认 endpoint（`123.56.15.233`）作为开箱配置，但允许改。
- `caPath`/`parseCaPath` 留空 → 默认 endpoint 用 `$PKG/certs/*.crt`；**自填 endpoint 时不套用内置 CA**，留空则用系统 CA（Node 默认信任链），避免把测试 CA 用到生产域名。
- `keychainService` 有值时优先读 macOS Keychain，并删除本地 `password`；工具只返回 `passwordSource: keychain|stored|none`。
- `engineConfigured` 改为“有 username 且有密码来源”，避免默认 endpoint 被误判为已配置。
- 凭据只能通过“编辑 0600 文件”或“Keychain”设置；**不要让用户在对话里贴密码**。
- 由于 bundle 不能声明 env，`QL_AUDIT_ENGINE_PASSWORD` 这类自定义环境变量在 Mint 下不可用；仅测试/命令行直跑时支持。

#### 对话修改

新增两个工具（详见 §5.3）：

| 工具 | 作用 | 审批 |
|---|---|---|
| `ql-audit-base__ql_get_config` | 读取非敏感配置、密码来源、数据目录、是否已配置；**永不返回密码** | 否 |
| `ql-audit-base__ql_set_config` | 修改 `endpoint`/`parse_endpoint`/`ca_path`/`parse_ca_path`/`username`/`keychain_service`/`parse_project`，至少改一项 | 是（Other） |

典型对话：

```text
用户：把 qlengine 地址改成 https://10.0.0.5:19999，CA 用 /etc/ql/ca.crt
Mint → base MCP：ql-audit-base__ql_set_config { endpoint: "https://10.0.0.5:19999", ca_path: "/etc/ql/ca.crt" }
MCP  → 磁盘：config.json（0600，tmp+rename）
MCP  → Mint：{ changed: ["endpoint","ca_path"], config: {...} }
Mint → base MCP：ql-audit-base__ql_get_health（验证连通与版本）
```

规则：

- `ql_set_config` 只接受非敏感字段；**不接受 `password`**。密码/密钥走 Keychain 或手动编辑 0600 文件。
- 采用 patch 语义：只覆盖提交的字段，保留未提交的 `password`/`keychainService`；改 endpoint 不会误删密码。
- URL 必须 `http(s)://`；`ca_path` 必须存在且可读；未知字段报 `INVALID_ARGUMENT`。
- 改 `endpoint`/`parse_endpoint` 且未同时给对应的 `ca_path`/`parse_ca_path` 时，清空旧 CA（回系统 CA），避免旧 CA 绑到新地址。
- 改 `keychain_service` 时删除本地 `password`，并返回 `passwordSource: "keychain"`。
- 改 endpoint 后若新环境账号不同，先改 `username`/`keychain_service`，再用 Keychain 写入新密码；工具不会自动迁移旧密码。
- 写入前校验，写入用 tmp+rename，失败返回 `CONFIG_WRITE_FAILED`，不留下半写文件。
- 修改后不自动重启 MCP；base/policy/review 三个服务都在下一次工具调用时读取新配置（`readConfig` 每次读文件），不缓存。

#### 持久化选型

v0.1 **用 `config.json`**，理由：

- 配置只有 9 个字段、单用户、写入频率低；JSON 可人工编辑/备份，排查问题直观。
- 不引入依赖；`node:sqlite` 在 Node 22 仍是 experimental，且 SQLite 对“9 个字段的配置”是过度设计。
- 现有 ql-audit 已经用 `config.json`，迁移成本最低。

抽象出 `ConfigStore` 接口（`read`/`write`/`patch`），v0.1 实现 `JsonConfigStore`。若后续需要多进程并发、查询 run 历史或审计事件，v0.2 可加 `SqliteStateStore`（`node:sqlite`，`~/.mint/ql-audit/state.db`）作为**可选**后端；`ql_get_config`/`ql_set_config` 的语义不变。

> 结论：满足“通过对话修改 + 本地持久化”；v0.1 落地为 `config.json`，SQLite 是后续可选实现，不是发布阻塞项。如果你希望 v0.1 直接上 SQLite，也可在 P1 用 `node:sqlite` 实现 `SqliteStateStore`；成本约 +0.5 天，工具契约不变。

### 4.6 CA 与打包

- 包内放 `certs/rulecraft-ca.crt`、`certs/qlengine-ca.crt`（PEM 内容，`.crt` 后缀）。
- **不要放 `.pem`**：`mint pack` 会直接失败。
- 这两个 CA 是当前测试环境的自签 CA；生产发布前替换为组织 CA，或在 `config.json` 指向外部 CA。
- **公开分发时不要把内网 CA 打进包**：CA 证书会暴露内网主机名/签发者；改为“首次配置时由用户指定 `caPath`”，或使用公网可信证书。内部分发/私有 MintHub 才可以随包带 CA。
- CA 是公开证书，不是密钥；但仍建议在 README 说明来源、有效期与替换方式。
- `mint pack` 还会排除 `node_modules/`、`.git/`、`target/`、`.mint/`、`credentials.toml`、`.env*`；本项目零依赖，不受影响。

### 4.7 并发与锁

- 多个 Mint 会话、以及 base/policy/review 三个 MCP 进程都会共享 `~/.mint/ql-audit`；所有写操作必须原子/加锁，不能依赖“只有一个进程”。
- 解析：`.lock` O_EXCL + 20 分钟陈旧回收；拿不到锁返回旧状态，不阻塞。
- 版本追加：`appendVersion` 同 id 先删后加 + tmp/rename 原子写；并发构建同一版本最终幂等。
- 审核：`runId` 带毫秒 + billId 前 8 + 序号，天然唯一；并发审核各自写自己的 run 目录。
- 配置写入：新增 `writeConfigAtomic`（tmp + rename，0600），避免半写。

---

## 5. 工具契约

### 5.1 14 个工具（3 个服务）与审批行为

Mint 的 MCP 客户端用工具名猜 `ToolKind`：`get/list/search` → Search（只读，自动放行）；`run` → Execute（Prompt）；其余 → Other（Prompt）。命名据此设计。**工具全名 = `<server_id>__<tool>`**，下表直接写全名。

| 服务 | # | 工具全名 | 作用 | 名字命中 | 预估 Kind | 审批 | iface effect |
|---|---|---|---|---|---|---|---|
| base | 1 | `ql-audit-base__ql_get_health` | qlengine 健康、版本漂移、配置状态 | get | Search | 否 | ReadOnly |
| base | 2 | `ql-audit-base__ql_get_config` | 读取非敏感配置与密码来源 | get | Search | 否 | ReadOnly |
| base | 3 | `ql-audit-base__ql_set_config` | 对话修改 endpoint/CA/用户名/项目 | — | Other | 是 | Advance |
| base | 4 | `ql-audit-base__ql_list_versions` | 规则版本列表（随包 + 本地） | list | Search | 否 | ReadOnly |
| base | 5 | `ql-audit-base__ql_list_scenes` | 场景列表 + 推荐 | list | Search | 否 | ReadOnly |
| base | 6 | `ql-audit-base__ql_list_rules` | 规则正文只读分页 | list | Search | 否 | ReadOnly |
| policy | 7 | `ql-audit-policy__ql_parse_policy` | 上传制度 PDF，建解析 job | — | Other | 是 | SideEffect |
| policy | 8 | `ql-audit-policy__ql_get_parse_status` | 查询/推进一步解析 job | get | Search | 否 | Advance（可能后台建版） |
| policy | 9 | `ql-audit-policy__ql_resolve_parse` | 提交裁定并重跑 | — | Other | 是 | SideEffect |
| policy | 10 | `ql-audit-policy__ql_list_parses` | 解析 job 列表 | list | Search | 否 | ReadOnly |
| review | 11 | `ql-audit-review__ql_load_bill` | 报文入库/归一化/去重 | — | Other | 是 | Advance |
| review | 12 | `ql-audit-review__ql_get_preflight` | 静态预检（不调引擎） | get | Search | 否 | ReadOnly |
| review | 13 | `ql-audit-review__ql_run_audit` | 调 qlengine 批量审核 | run | Execute | 是 | SideEffect |
| review | 14 | `ql-audit-review__ql_get_result` | 重渲染历史 run | get | Search | 否 | ReadOnly |

> 说明 1：`ql-audit-policy__ql_get_parse_status` 虽是“查询”，但会推进状态机并可能在后台建版本；这是现有 ql-audit 的设计（没有守护进程），命名保留 `get` 以避免每 10 秒一次审批。SKILL 必须明确这一点。

> 说明 2：base 的 3 个 catalog 只读工具被两个能力共用：policy 用它抽查抽出的规则，review 用它选版本、场景并做 preflight 前的确认。这是“共享模块”的主要收益之一。

> 说明 3：组合包 `lingcai/ql-audit` 不新增工具；安装它只是把 base/policy/review 三个服务一起装上。

### 5.2 通用约定

- 参数一律 **snake_case**；工具全名由 Mint 生成为 `<server_id>__<local_name>`。服务 ID 固定为 `ql-audit-base|policy|review`（可含 `-`），本地名保持 `^[a-z][a-z0-9_]{1,63}$`。
- 每个 MCP 服务只注册本组工具；base 的只读工具不在 policy/review 里重复注册。
- 参数 schema 使用 `type/properties/required/items/enum/description/additionalProperties`；不使用远程 `$ref`。
- 成功返回 `{ content: [{ type: "text", text: "<JSON 字符串>" }] }`。
- 失败返回 `{ isError: true, content: [{ type: "text", text: "<CODE>：<message>" }] }`；message 可读、可行动，不含凭据与报文正文。
- 不在工具参数里放 `session_id`/`call_id`/`turn`（iface `CallMeta` 由协议层注入）。
- 所有写盘/远端调用前先做参数校验；未知参数报 `INVALID_ARGUMENT`。
- 配置类工具**不接受、不返回密码**；只返回 `passwordSource`。
- 结果里的 `card` 是 Markdown；SKILL 要求原样展示，不改写计数。

### 5.3 关键 schema

> 下列标题用本地名；实际调用时按所属服务加前缀：配置/目录类加 `ql-audit-base__`，制度类加 `ql-audit-policy__`，审核类加 `ql-audit-review__`。

#### `ql_get_config`

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

返回（**无密码**）：

```json
{
  "config": {
    "version": 1,
    "endpoint": "https://123.56.15.233:19999",
    "endpoint_is_default": true,
    "parse_endpoint": "https://123.56.15.233/rulecraft",
    "parse_endpoint_is_default": true,
    "ca_path": "",
    "ca_path_source": "bundled",
    "parse_ca_path": "",
    "parse_ca_path_source": "bundled",
    "username": "operator",
    "keychain_service": "qlengine-harness",
    "password_source": "keychain",
    "parse_project": "pilotdeck",
    "engine_configured": true,
    "data_dir": "/Users/<user>/.mint/ql-audit"
  }
}
```

`ca_path_source`/`parse_ca_path_source` = `bundled | file | system`；`password_source` = `keychain | stored | none`。

#### `ql_set_config`

```json
{
  "type": "object",
  "properties": {
    "endpoint": { "type": "string", "description": "qlengine 地址，http(s)://..." },
    "parse_endpoint": { "type": "string", "description": "Rulecraft 地址，http(s)://..." },
    "ca_path": { "type": "string", "description": "qlengine CA 文件；空串=系统 CA" },
    "parse_ca_path": { "type": "string", "description": "Rulecraft CA 文件；空串=系统 CA" },
    "username": { "type": "string" },
    "keychain_service": { "type": "string", "description": "macOS Keychain service 名" },
    "parse_project": { "type": "string" }
  },
  "minProperties": 1,
  "additionalProperties": false
}
```

至少给一个字段（`minProperties: 1`）。返回：

```json
{
  "changed": ["endpoint", "ca_path"],
  "config": { "endpoint": "https://10.0.0.5:19999", "engine_configured": true, "password_source": "keychain" }
}
```

校验与副作用：

- URL 必须 `http(s)://`；`ca_path` 非空时必须存在且可读（空串=系统 CA）；`parse_project` 非空。
- 改 `endpoint`/`parse_endpoint` 且未同时给对应 CA → 清空旧 CA（回系统 CA），避免旧 CA 绑新地址。
- 改 `keychain_service` → 删除本地 `password`，`password_source` 变 `keychain`。
- 不接受 `password` 字段；出现即 `INVALID_ARGUMENT`；patch 语义，保留未提交字段。
- 原子写 `config.json`（tmp+rename，0600）；失败 `CONFIG_WRITE_FAILED`。
- 修改后下一次工具调用生效，不需要重启 MCP。

#### `ql_load_bill`

```json
{
  "type": "object",
  "properties": {
    "path": { "type": "string", "description": "报文 .json/.txt 的绝对路径" },
    "json": { "type": "string", "description": "报文 JSON 原文" }
  },
  "additionalProperties": false
}
```

二选一由实现校验；两个都给或都不给 → `INVALID_ARGUMENT`。返回：

```json
{ "billId": "0d70baf6244e", "billNo": "E703881786093676257", "invoiceCount": 2, "duplicate": false }
```

#### `ql_get_preflight`

```json
{
  "type": "object",
  "properties": {
    "bill_id": { "type": "string" },
    "version_id": { "type": "string" },
    "scene_ids": { "type": "array", "items": { "type": "string" } },
    "exclude_rules": { "type": "array", "items": { "type": "string" } }
  },
  "required": ["bill_id", "version_id"],
  "additionalProperties": false
}
```

返回：

```json
{
  "billId": "0d70baf6244e",
  "versionId": "v-02482cdb-20261020",
  "sceneIds": ["common"],
  "sceneNames": ["发票/附件/表单-通用规则"],
  "summary": { "rules": 53, "blocked": 53, "unmappedRules": 30, "ready": 0 },
  "missingAliases": [{ "alias": "attachmentInfo", "rules": 49 }],
  "unmappedAliases": [{ "alias": "paymentDiscountAmount", "rules": 3 }],
  "preMissingAliases": [],
  "postMissingAliases": [],
  "preUnmappedAliases": [],
  "postUnmappedAliases": [],
  "rules": [{ "ruleId": "...", "missing": ["..."], "unmapped": ["..."], "blocked": true }]
}
```

#### `ql_run_audit`

```json
{
  "type": "object",
  "properties": {
    "bill_id": { "type": "string" },
    "version_id": { "type": "string" },
    "scene_ids": { "type": "array", "items": { "type": "string" } },
    "exclude_rules": { "type": "array", "items": { "type": "string" } },
    "allow_drift": { "type": "boolean", "default": false }
  },
  "required": ["bill_id", "version_id"],
  "additionalProperties": false
}
```

返回：

```json
{
  "run_id": "20261029T163633406-0d70baf6",
  "verdict": "needs-human",
  "overall": "不通过",
  "counts": {
    "passed": 0, "failed": 49, "review": 49, "missingData": 0,
    "errors": 0, "inapplicable": 4, "skipped": 4, "executed": 49
  },
  "unknown": ["<review/missing 的规则 key>"],
  "warning": null,
  "card": "单据编号：...\n审核结果：不通过\n..."
}
```

#### `ql_parse_policy`

```json
{
  "type": "object",
  "properties": {
    "path": { "type": "string", "description": "制度文件绝对路径（.pdf/.docx/.md/.txt）" },
    "project": { "type": "string", "description": "可选；覆盖 config.parseProject" }
  },
  "required": ["path"],
  "additionalProperties": false
}
```

返回：

```json
{
  "job_id": "20261030T003000-ab12cd34",
  "filename": "报销手册.pdf",
  "status": "running",
  "hint": "解析约 10 分钟；稍后用 ql_get_parse_status 查询，不要连续轮询。"
}
```

#### `ql_get_parse_status`

```json
{
  "type": "object",
  "properties": {
    "job_id": { "type": "string" },
    "limit": { "type": "integer", "minimum": 1, "maximum": 200, "default": 20 }
  },
  "required": ["job_id"],
  "additionalProperties": false
}
```

返回（`needs_resolution`）：

```json
{
  "job_id": "20261030T003000-ab12cd34",
  "status": "needs_resolution",
  "round": 0,
  "filename": "报销手册.pdf",
  "doc_id": "...",
  "task_id": "...",
  "stage": "...",
  "progress": 0.42,
  "error": null,
  "clarification_counts": { "total": 3, "answered": 0, "remaining": 3 },
  "clarifications": [
    {
      "clarId": "...",
      "kind": "...",
      "question": "...",
      "clauseId": "...",
      "quote": "...",
      "options": ["系统建议", "其他"]
    }
  ],
  "version_id": null,
  "hint": "请让用户逐项回答；不要替用户选择。"
}
```

`ready` 时补 `version_id`、`rule_count`、`executable_count`、`scene_count`。

#### `ql_resolve_parse`

```json
{
  "type": "object",
  "properties": {
    "job_id": { "type": "string" },
    "answers": { "type": "object", "additionalProperties": { "type": "string" } },
    "use_defaults": { "type": "boolean", "default": false }
  },
  "required": ["job_id"],
  "additionalProperties": false
}
```

未答全且未 `use_defaults` → `isError: true`，文本含 `CLARIFICATIONS_UNANSWERED` 与 missing 列表。

### 5.4 结果信封与 verdict 映射

`verdict` 使用 `ReviewVerdict` 的稳定串，便于下游 agent/审计直接消费：

| 审核情形 | `verdict` | 理由 |
|---|---|---|
| `overall = 通过` 且 `executed > 0` | `approve` | 全部执行规则通过 |
| `counts.review > 0` | `needs-human` | 有规则缺数据，需人工复核（即使同时有 fail） |
| `counts.errors > 0` 且无 review | `revise` | 引擎/表达式错误，需修数据或规则后重跑 |
| `counts.failed > 0` 且无 review/errors | `reject` | 明确不通过 |
| `status = no_rules` 或 `executed = 0` | `needs-human` | 没有可执行规则，不能判通过 |
| `version drift` 且 `allow_drift=false` | 错误 `QLENGINE_VERSION_DRIFT` | fail-closed，不返回 verdict |

`unknown` 数组放 `review`/`missing` 的规则 key；对应 iface-tool 的 `ToolResult.unknown` 语义（“未知不得当成功/失败”）。

### 5.5 错误码

保留 ql-audit 现有码，补齐存储/漂移：

| 类别 | 码 |
|---|---|
| 参数 | `INVALID_ARGUMENT`、`INVALID_JSON` |
| 配置 | `CONFIG_INVALID`、`CONFIG_WRITE_FAILED`、`CA_UNREADABLE` |
| 报文 | `BILL_NOT_FOUND`、`BILL_TOO_LARGE`、`BILL_PARSE` |
| 规则库 | `VERSION_NOT_FOUND`、`SCENE_NOT_FOUND`、`RULE_NOT_FOUND` |
| 引擎 | `QLENGINE_NOT_CONFIGURED`、`QLENGINE_UNAUTHORIZED`、`QLENGINE_CA_UNREADABLE`、`QLENGINE_TLS`、`QLENGINE_TIMEOUT`、`QLENGINE_UNAVAILABLE`、`QLENGINE_RATE_LIMITED`、`QLENGINE_BAD_RESPONSE`、`QLENGINE_VERSION_DRIFT` |
| 解析 | `RULECRAFT_DOCUMENT_FORMAT_UNSUPPORTED`、`RULECRAFT_*`、`PARSE_EXISTS`、`PARSE_NOT_FOUND`、`PARSE_EMPTY`、`UNKNOWN_CLARIFICATION`、`CLARIFICATIONS_UNANSWERED` |
| 审核 | `AUDIT_NO_RULES`、`AUDIT_ENGINE_ERROR` |
| 存储 | `STORE_WRITE_FAILED`、`AUDIT_LOG_FAILED` |

`STORE_WRITE_FAILED`/`AUDIT_LOG_FAILED` 必须 fail-closed：不返回“成功”，并带 `run_id` 供重试。

---

## 6. 与 iface 对齐

### 6.1 iface 的真实边界（先避免误判）

- 10 个 iface 包是 **Rust trait + 类型形状契约**（22 trait / 44 文件 / 6292 行），全部 `use super::types::*`；`iface-policy/src/audit.rs` 还使用单体 crate 路径 `crate::policy::`，已知作为独立包不可编译。
- 包清单 `kind = "bundle"`（不是 `iface`）；`Kind::Iface` 在源码存在，但已发布 mint 0.1.11 拒绝该变体。契约身份靠 `[provides] interfaces` 声明。
- JS/MCP 插件**不能实现**这些 trait，也**不能声明 iface 依赖**：`Requires` 没有 `interfaces` 字段；唯一真实依赖机制是 `[dependencies]`。
- `ToolSpec` 有两套形状：iface-tool 的 `ToolSpec { name, description, parameters: Vec<u8> }`（内核 Rust 侧）vs 线上 `ToolSpec { name, description, input_schema: Value, kind, namespace, version, capabilities, timeout_hint_ms, max_retries }`。**同名不同字段，不能照抄**。
- `AuditSink` 在 `iface-policy` 包内**不可达**：`mod.rs` 没有 `pub mod audit;`，且 `AuditEvent` 有同名双定义。不要设计“实现 AuditSink”。
- `ReviewVerdict::Revise` 在 ACP 线上没有对应：`ApprovalDecision` 只有 `AllowOnce/AllowAlways/RejectOnce/RejectAlways/Cancelled`。必须显式降级。

### 6.2 映射表

| iface 概念 | 本插件落点 | 关系 |
|---|---|---|
| `iface-tool::ToolSpec` | MCP `tools/list` 的 `name/description/inputSchema` | 借用三元组语义，不实现 trait |
| `iface-tool::ToolResult { ok, bytes, unknown }` | `{ content, isError }` + `unknown[]` 字段 | 语义对齐；wire 上没有 `unknown` 字段 |
| `iface-tool::ToolContract::abort` | MCP 无标准取消；Mint 超时会丢弃请求 | **缺口**；用短调用 + 幂等重试缓解 |
| `iface-policy::ReviewVerdict` | `verdict` 字段：`approve/reject/needs-human/revise` | 直接用稳定串 |
| `iface-policy::ReviewPosition` | 审核 = `final-result`；解析不是审核位 | 语义借用；不声称运行时实现 |
| `iface-policy::ReviewRequest.subject_ref` | `bill/<billId>@sha256:<hash>`（≤256，无控制字符） | 字段形状对齐；正文另存 |
| `iface-policy::ReviewAuditEvent` | `.audit/events.jsonl` 的一行 | 字段形状对齐 |
| `iface-policy::AuditSink` | 自建 append-only JSONL sink | **不用 trait**（iface 未接线） |
| `iface-store::StoreContract` / `EventRecord` | `runs/`、`parses/`、`.audit/events.jsonl` | 概念对齐；无 cursor/checkpoint |
| `iface-context::TraceSink`“先写后执行” | 审核前先落盘报文；返回前先写事件 | 纪律对齐 |
| `iface-extension` `describe/status/deactivate` | bundle 加载/卸载；MCP `initialize`/`shutdown` | 概念对齐；无逐字对应 |
| `iface-loop::StepOutcome::WaitingHuman` | `verdict = needs-human` | 语义对齐 |
| `iface-types::Error { category, code, message }` | 错误码表 + 可读 message | 分类对齐 |
| `iface-types::CallMeta` | **不进工具 schema** | 遵守“CallMeta 不得进参数 schema” |

### 6.3 留痕事件

路径 `~/.mint/ql-audit/.audit/events.jsonl`，0600，append-only。每行：

```json
{
  "ts_ms": 1761744000000,
  "principal": "mint:payne",
  "session": "mcp",
  "call": "run-20261029T163633406-0d70baf6",
  "op": "audit.run",
  "decision": "needs-human",
  "reason": "49 rules need review",
  "position": "final-result",
  "subject": "bill/0d70baf6244e@sha256:...",
  "policy": "v-02482cdb-20261020",
  "correlation": "20261029T163633406-0d70baf6"
}
```

规则：

- `decision` 用 `ReviewVerdict::tag()` 的稳定串；`reason` 用 `reason()` 的语义。
- `subject` 只放 id/hash，不放报文正文；正文在 `bills/`。
- `session`/`call` 在 MCP stdio 下拿不到 Mint 的 session/call id，用 `"mcp"` 与服务端生成的 id；这是已知缺口。
- 写事件失败 → 返回 `AUDIT_LOG_FAILED`，不报告成功；已写的结果文件保留，重试幂等读取。
- 解析事件：`op = "policy.parse"`、`decision = "needs-human"|"approve"`、`position = "tool-params"`（解析不是内核审核位，仅借字段）。
- 配置变更：`op = "config.set"`，只记 `changed` 字段名与 endpoint host，不记密码；`decision = "approve"`。

### 6.4 已知缺口与降级

| 缺口 | 影响 | 降级 |
|---|---|---|
| MCP 无标准取消/进度 | 长调用只能等超时 | 解析拆成多次 status；审核 120 s 内完成 |
| MCP 不传 session/call id | 留痕无法关联 Mint 会话 | 记录 `mcp` + 生成的 call id；v0.2 用 Mint hook |
| `Revise` 线上不可表达 | 引擎错误只能 `needs-human`/`reject` | 用 `verdict = "revise"` 作为本插件扩展；SKILL 说明 |
| `AuditSink` 未接线 | 不能实现 iface trait | 自建 JSONL；字段对齐 |
| `ToolKind` 由名字猜 | 审批体验不可精确控制 | 命名规范 + README；上游建议支持 MCP `annotations.readOnlyHint` |
| 无 `checkpoint/verify` | 不能证明留痕未截断 | v0.2 加哈希链/`verify` 工具 |

### 6.5 明确不做

- 不写 `[provides] interfaces`：plugin/bundle 没有消费方，写了等于虚假声明。
- 不实现 `ToolContract`/`PolicyContract`/`AuditSink` 等 Rust trait。
- 不把 `ReviewPosition` 硬塞成“解析”的第 5 个位置。
- 不把 `session_id`/`call_id` 放进工具参数 schema。

---

## 7. 包与仓库布局

### 7.0 拆分方案对比

| 方案 | 形态 | 优点 | 缺点 | 结论 |
|---|---|---|---|---|
| A 单包 | 1 个 bundle / 1 个 MCP 服务 / 14 工具 | 最简单；启动少；审批面集中 | 只装一个能力也加载全部工具；共享只在代码内部，MintHub 无法复用 | v0 baseline，不选 |
| B 单服务 + 能力 skill | 1 个 MCP 服务 / 2 个 skill 包 | 只有一个进程；skill 可分开 | 工具面仍是 14 个；装制度侧也会看到审核工具，不是真正模块化 | 不选 |
| C 共享 base + 两个能力服务 + meta | 4 个 bundle / 3 个 MCP 服务 / 14 工具 | 共享代码一份；可单独装 policy 或 review；工具/审批/token 面按需加载；meta 一键装 | 4 个包、3 个进程；有 base 定位与版本锁问题 | **选 C** |
| D 两个能力包各自复制代码 | 2 个 bundle / 2 个 MCP 服务 | 包之间零依赖 | 两份 config/store/catalog/qlengine 实现，修 bug 要改两处；不可接受 | 不选 |

**共享模块与归属**

| 模块 | 代码位置 | base 服务 | policy 服务 | review 服务 | 说明 |
|---|---|---|---|---|---|
| 数据目录/权限/原子写/锁 | base `lib/store.mjs` | ✓ | ✓ | ✓ | 三进程共享 `~/.mint/ql-audit`；写操作必须原子/加锁 |
| config/凭据/CA | base `lib/config.mjs` | ✓ | ✓ | ✓ | 对话改配置后三个服务下一次调用都生效 |
| catalog 只读 | base `lib/catalog.mjs` | ✓ | ✓ | ✓ | 版本/场景/规则查询，两个能力都用到 |
| qlengine 客户端 | base `lib/qlengine.mjs` | ✓ health | ✓ compile | ✓ batch | 同一套 BasicAuth/CA/超时/重试 |
| MCP 协议/工具注册 | base `lib/mcp/` | ✓ | ✓ | ✓ | 启动器用组参数选组，避免重复实现 |
| Rulecraft 客户端 | base `lib/rulecraft.mjs` | — | ✓ | — | 只有制度侧用，但代码放 base 以保持单运行时 |
| catalog 构建 | base `lib/catalog-builder.mjs` | — | ✓ | — | 只有制度侧用 |
| 解析状态机 | base `lib/parse.mjs` | — | ✓ | — | 只有制度侧用 |
| 审核/预检/结果卡 | base `lib/audit.mjs` | — | — | ✓ | 只有审核侧用 |
| SKILL | 各包 `skills/` | base skill | policy skill | review skill | 按能力分开，模型只收到相关流程 |

> 代码都放 base 并不等于“所有代码每个进程都加载”：`groups/*.mjs` 按 group 懒加载，base 服务不会 import audit/parse；policy 不会 import audit；review 不会 import parse/Rulecraft。

选 C 的关键理由：两个能力确实共享 **config/凭据/CA、catalog、qlengine 客户端、MCP 协议层**；这些是高频变更、最容易出安全问题的部分。把它们收敛到 base，比“两个包各自实现”更稳；同时 policy/review 只装自己需要的工具，符合 MintHub 的模块化用法。

### 7.1 仓库布局（建议在 ql-audit 仓库内）

```text
products/ql-audit/
├── core/                         # 新增：纯 Node 业务内核（从 plugins/ql-audit/server 抽出）
│   ├── audit.mjs
│   ├── service.mjs
│   ├── parse.mjs
│   ├── catalog-builder.mjs
│   ├── rulecraft.mjs
│   ├── qlengine.mjs
│   ├── http.mjs
│   ├── json-scan.mjs
│   ├── config.mjs                # 新增：数据目录/CA/凭据/ConfigStore
│   └── mcp/                      # MCP 协议层 + 分组注册
│       ├── server.mjs            # 入口：base|policy|review
│       ├── groups/
│       │   ├── base.mjs          # 6 工具
│       │   ├── policy.mjs        # 4 工具
│       │   └── review.mjs        # 4 工具
│       └── protocol.mjs
├── plugins/ql-audit/             # PilotDeck 插件（保留，改为 import ../../core）
├── mint/                         # 四个 Mint 包的源目录
│   ├── base/
│   │   ├── mint.toml
│   │   ├── .mcp.json
│   │   ├── README.md
│   │   ├── LICENSE               # AGPL-3.0-only
│   │   ├── bin/ql-audit-base     # POSIX 启动器，0755
│   │   ├── lib/                  # stage 时从 core/ 复制；唯一运行时
│   │   ├── skills/ql-audit-base/SKILL.md
│   │   ├── certs/rulecraft-ca.crt
│   │   ├── certs/qlengine-ca.crt
│   │   └── catalog/{catalog,fields,known-unsupported}.json
│   ├── policy/
│   │   ├── mint.toml
│   │   ├── .mcp.json
│   │   ├── README.md
│   │   ├── LICENSE
│   │   ├── bin/ql-audit-policy   # 只定位 base 并 exec base 运行时
│   │   └── skills/ql-audit-policy/SKILL.md
│   ├── review/
│   │   ├── mint.toml
│   │   ├── .mcp.json
│   │   ├── README.md
│   │   ├── LICENSE
│   │   ├── bin/ql-audit-review
│   │   └── skills/ql-audit-review/SKILL.md
│   └── meta/
│       ├── mint.toml
│       ├── README.md
│       ├── LICENSE
│       └── skills/ql-audit/SKILL.md
├── scripts/
│   ├── stage-mint.mjs            # core + catalog + certs → dist/{base,policy,review,meta}
│   └── e2e-acceptance.mjs
└── tests/                        # 迁移后的 55 个测试 + 契约测试
```

**为什么业务代码只放 base**：

- 三个 MCP 服务共享 config/store/catalog/qlengine/rulecraft/MCP 协议层；如果 policy/review 各放一份，会出现三份实现和三套 bug。
- policy/review 包只保留“能力声明 + 启动器 + SKILL”，体积小、发布快；它们的 `bin/*` 定位同级 base，再 `exec` 同一份 `lib/mcp/server.mjs`。
- `stage-mint.mjs` 把 `core/` 复制到 `dist/base/lib/`，把 catalog/certs 复制到 `dist/base/`，把 mint 静态文件复制到各包；`dist/policy`、`dist/review` 不含 `lib/`。
- 这样 PilotDeck 插件与 Mint 仍共用 `core/`，只有一份业务代码。

### 7.2 `mint.toml`

**base（唯一共享运行时）**

```toml
[package]
name = "lingcai/ql-audit-base"
version = "0.1.0"
kind = "bundle"
description = "ql-audit 共享基础：配置、健康检查、规则目录只读（被 policy/review 依赖）"
license = "AGPL-3.0-only"
repository = "https://github.com/<org>/AgentCPM-agent-evolution"
keywords = ["audit", "rules", "catalog", "config", "qlengine"]

[provides]
mcp_servers = ["ql-audit-base"]
skills = ["ql-audit-base"]

[requires]
core = ">=0.1.14"

[capabilities]
exec = ["ql-audit-base", "node"]
net = ["https://*"]
fs_read = ["~/.mint/ql-audit/**"]
fs_write = ["~/.mint/ql-audit/**"]

[capabilities.reason]
exec = "启动 ql-audit-base MCP 服务（Node.js 启动器）"
net = "ql_get_health 访问用户可配置的 qlengine 地址"
fs_read = "读取 ~/.mint/ql-audit 下的配置与规则目录"
fs_write = "ql_set_config 原子写入 config.json"
```

**policy（制度侧，薄包）**

```toml
[package]
name = "lingcai/ql-audit-policy"
version = "0.1.0"
kind = "bundle"
description = "制度 PDF → 规则版本（依赖 ql-audit-base）"
license = "AGPL-3.0-only"
repository = "https://github.com/<org>/AgentCPM-agent-evolution"
keywords = ["policy", "pdf", "rules", "compliance", "rulecraft"]

[provides]
mcp_servers = ["ql-audit-policy"]
skills = ["ql-audit-policy"]

[dependencies]
"lingcai/ql-audit-base" = "=0.1.0"

[requires]
core = ">=0.1.14"

[capabilities]
exec = ["ql-audit-policy", "node"]
net = ["https://*"]
fs_read = ["~/.mint/ql-audit/**"]
fs_write = ["~/.mint/ql-audit/**"]

[capabilities.reason]
exec = "启动 ql-audit-policy MCP 服务（定位 base 运行时）"
net = "调用用户可配置的 Rulecraft 与 qlengine 地址"
fs_read = "读取 parses/ 与 catalog"
fs_write = "写入 parses/ 并追加 catalog 版本"
```

**review（审核侧，薄包）**

```toml
[package]
name = "lingcai/ql-audit-review"
version = "0.1.0"
kind = "bundle"
description = "报销报文 + 规则 → 审核结论（依赖 ql-audit-base）"
license = "AGPL-3.0-only"
repository = "https://github.com/<org>/AgentCPM-agent-evolution"
keywords = ["audit", "expense", "invoice", "compliance", "report"]

[provides]
mcp_servers = ["ql-audit-review"]
skills = ["ql-audit-review"]

[dependencies]
"lingcai/ql-audit-base" = "=0.1.0"

[requires]
core = ">=0.1.14"

[capabilities]
exec = ["ql-audit-review", "node"]
net = ["https://*"]
fs_read = ["~/.mint/ql-audit/**"]
fs_write = ["~/.mint/ql-audit/**"]

[capabilities.reason]
exec = "启动 ql-audit-review MCP 服务（定位 base 运行时）"
net = "调用用户可配置的 qlengine 地址"
fs_read = "读取 bills/catalog/config"
fs_write = "写入 bills/runs 与 .audit/events.jsonl"
```

**meta（组合包，无 MCP）**

```toml
[package]
name = "lingcai/ql-audit"
version = "0.1.0"
kind = "bundle"
description = "一键安装 ql-audit：制度 PDF 解析 + 报销报文审核（组合 base/policy/review）"
license = "AGPL-3.0-only"
repository = "https://github.com/<org>/AgentCPM-agent-evolution"
keywords = ["audit", "policy", "compliance", "rules", "expense"]

[provides]
skills = ["ql-audit"]

[dependencies]
"lingcai/ql-audit-base" = "=0.1.0"
"lingcai/ql-audit-policy" = "=0.1.0"
"lingcai/ql-audit-review" = "=0.1.0"

[requires]
core = ">=0.1.14"
```

注意：

- **exact pin（`=0.1.0`）**：v0.1 四个包 lockstep 发布；避免 policy/review 的启动器定位到不兼容的 base。后续若做独立版本，改 `^0.1` 并在启动器里做版本校验。
- 四个包都写 `license = "AGPL-3.0-only"`，各自带 `LICENSE`；meta 的依赖会带上子包的许可证。
- **base 不建议单独安装**：它只有配置/健康/catalog 查询，没有解析/审核能力；单独装 policy 或 review 时，Mint 会递归装上 base。
- **policy/review 可以单独安装**：各自带 base，工具面 10 个；这样制度团队不必看到审核工具，审核团队不必看到解析工具。
- **meta 是便利包，不是能力必需**：去掉它不影响 base/policy/review 单独安装；保留它是为了 MintHub 上一键装齐 14 工具。
- base/policy/review 都声明 `net = ["https://*"]`：三个进程各自可能发请求（base 健康检查、policy Rulecraft/qlengine、review qlengine）。这是披露，不是沙箱；MCP 子进程实际不受 `net` 限制。
- `fs_read`/`fs_write` 用 `~/.mint/ql-audit/**` 披露数据目录；`mint pack` 接受该写法（已实测最小包）。如果 Mint 后续校验绝对路径，改用 `$HOME/.mint/ql-audit/**` 或去掉 fs 声明并在 README 说明。
- meta **不写 `capabilities`**：它不启动进程，只组合依赖；安装确认会展示三个子包的权限。已用最小包实测：无 `capabilities`、无 `.mcp.json`、只带 `skills/` 的 bundle 可以 `mint pack`，不需要占位。
- `keywords` 每个包最多 5 个；meta 的 `keywords` 覆盖搜索入口，子包用能力词。
- 不写 `capabilities.env`（bundle 不允许）。

### 7.3 `.mcp.json`

```json
// mint/base/.mcp.json
{
  "mcpServers": {
    "ql-audit-base": {
      "command": "$PKG/bin/ql-audit-base",
      "args": [],
      "timeout_s": 30
    }
  }
}
```

```json
// mint/policy/.mcp.json
{
  "mcpServers": {
    "ql-audit-policy": {
      "command": "$PKG/bin/ql-audit-policy",
      "args": [],
      "timeout_s": 30
    }
  }
}
```

```json
// mint/review/.mcp.json
{
  "mcpServers": {
    "ql-audit-review": {
      "command": "$PKG/bin/ql-audit-review",
      "args": [],
      "timeout_s": 30
    }
  }
}
```

- **meta 不放 `.mcp.json`**；它的三个依赖各自带一个，Mint 会全部加载。
- 服务 ID 必须唯一：`ql-audit-base`、`ql-audit-policy`、`ql-audit-review`。不要用同一个 `ql-audit`，否则工具前缀冲突/覆盖。
- `$PKG` 在 command 与 args 中都会替换；不写 `env`（`${HOME}` 不展开）。
- `timeout_s` 30 s 足够 Node 启动；base 加载 catalog 只在首次工具调用时惰性读，不在启动时读。
- 工具调用超时仍是全局 `[core.loop] tool_timeout_ms`；大 PDF 需在项目里调大。

### 7.4 启动器

**base：`mint/base/bin/ql-audit-base`**

```sh
#!/bin/sh
set -eu
DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

NODE=${QL_AUDIT_NODE:-}
if [ -z "$NODE" ]; then
  NODE=$(command -v node 2>/dev/null || true)
fi
if [ -z "$NODE" ]; then
  for c in "$HOME/.nvm/versions/node"/*/bin/node            /opt/homebrew/bin/node /usr/local/bin/node /usr/bin/node; do
    [ -x "$c" ] && NODE=$c && break
  done
fi
if [ -z "$NODE" ]; then
  echo "ql-audit-base: 找不到 Node.js（需要 >= 22.13）" >&2
  exit 127
fi
exec "$NODE" "$DIR/lib/mcp/server.mjs" base
```

**policy：`mint/policy/bin/ql-audit-policy`**

```sh
#!/bin/sh
set -eu
DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

BASE=${QL_AUDIT_BASE_DIR:-}
if [ -z "$BASE" ]; then
  BASE=$(ls -d "$DIR"/../ql-audit-base@* 2>/dev/null | sort -V | tail -1)
fi
if [ -z "$BASE" ] || [ ! -f "$BASE/lib/mcp/server.mjs" ]; then
  echo "ql-audit-policy: 未找到 lingcai/ql-audit-base；请先安装 base" >&2
  exit 127
fi

NODE=${QL_AUDIT_NODE:-}
if [ -z "$NODE" ]; then
  NODE=$(command -v node 2>/dev/null || true)
fi
if [ -z "$NODE" ]; then
  for c in "$HOME/.nvm/versions/node"/*/bin/node            /opt/homebrew/bin/node /usr/local/bin/node /usr/bin/node; do
    [ -x "$c" ] && NODE=$c && break
  done
fi
if [ -z "$NODE" ]; then
  echo "ql-audit-policy: 找不到 Node.js（需要 >= 22.13）" >&2
  exit 127
fi
exec "$NODE" "$BASE/lib/mcp/server.mjs" policy
```

**review：`mint/review/bin/ql-audit-review`** 与 policy 相同，只把 `policy` 改成 `review`、错误前缀改成 `ql-audit-review`。

要点：

- `$DIR` 是包根（启动器在 `bin/` 下，所以 `dirname/..`）；`$DIR/../ql-audit-base@*` 是 Mint 的同 scope 安装布局（实测 `.mint/packages/lingcai/ql-audit-base@0.1.0`）。
- 用 `sort -V` 取最高版本；macOS 14 的 `sort` 支持 `-V`（已实测）。如果担心，可改成读 `mint.lock` 或按 `=0.1.0` 精确拼路径。
- 找不到 base 时 **明确报错并退出 127**，不要静默降级成“只有 policy 工具但所有调用失败”。
- `QL_AUDIT_BASE_DIR` / `QL_AUDIT_NODE` 只用于测试/故障排查，不是公开接口。
- Windows 不在 v0.1 范围；如支持，补 `.cmd`。

### 7.5 SKILL.md：四个 skill，而不是一个

Mint 的 loader 会扫描 `mint.lock` 里**所有** bundle 的 `skills/*/SKILL.md`，所以装 policy 时 base 的 skill 也会注入，装 meta 时四个 skill 都在。skill 名必须唯一，描述要能区分触发场景。

| skill | 所属包 | 触发 | 内容重点 |
|---|---|---|---|
| `ql-audit-base` | base | 配置 endpoint/CA、看健康、查规则版本/场景/规则 | 配置修改、隐私、工具全名前缀、把只读工具当“查看” |
| `ql-audit-policy` | policy | 导入制度、解析 PDF、看解析进度、回答澄清 | 一次只查一次 status、约 10 分钟、裁定纪律、ready 后抽查规则 |
| `ql-audit-review` | review | 审核报销报文/发票/费用 | load→list versions/scenes→preflight→run→card；verdict 语义 |
| `ql-audit` | meta | “报销审核全流程”“安装/使用 ql-audit” | 路由：制度侧用 policy，审核侧用 review；不重复流程细节 |

**共同硬约束**（每个 skill 都写，不能只写 meta）：

- 工具名必须写全名：`ql-audit-base__ql_get_health`、`ql-audit-policy__ql_parse_policy`、`ql-audit-review__ql_run_audit`。
- 不替用户回答澄清项；不把 `needs-human` 说成通过；不在对话里要密码。
- `card` 原样展示，不改写计数。
- 不连续轮询解析；一次 status 后告诉用户稍后再查。
- 不暴露 RSI 工具（本组合包没有）。

**policy skill 的结构**：

```markdown
---
name: ql-audit-policy
description: 导入制度 PDF/Word/Markdown，解析为可审核的规则版本；用户要“提取制度规则/导入制度/看解析进度”时使用。
---
# 制度 → 规则版本
1. ql-audit-policy__ql_parse_policy（path）
2. 告诉用户约 10 分钟；本轮结束
3. 用户回来后再 ql-audit-policy__ql_get_parse_status
4. needs_resolution → 逐项提问 → ql-audit-policy__ql_resolve_parse
5. ready → 展示 version_id / rule_count；建议 ql-audit-base__ql_list_rules 抽查
```

**review skill 的结构**：

```markdown
---
name: ql-audit-review
description: 用规则版本审核报销报文/发票；用户要“审核这张报文/报销单/发票”时使用。
---
# 报文审核
1. ql-audit-review__ql_load_bill（path 或 json）
2. ql-audit-base__ql_list_versions
3. ql-audit-base__ql_list_scenes（version_id + bill_id）
4. ql-audit-review__ql_get_preflight（可选，推荐）
5. ql-audit-review__ql_run_audit
6. 原样展示 card；解释 verdict
```

**base skill 的结构**：

```markdown
---
name: ql-audit-base
description: 查看/修改 ql-audit 的 endpoint、CA、用户名，检查 qlengine 健康，浏览规则版本/场景/规则；用户要“配置 ql-audit/看规则版本”时使用。
---
# 配置与目录
1. ql-audit-base__ql_get_config 先看当前值
2. ql-audit-base__ql_set_config 只改非敏感字段；不要传密码
3. ql-audit-base__ql_get_health 验证
4. 密码只引导用户用 Keychain 或编辑 0600 config.json
```

**meta skill** 只做路由和安装说明，不复制 policy/review 的逐步流程，避免模型收到四份重复指令。

### 7.6 构建与发布

```sh
# 1. 产出四个可打包目录
node scripts/stage-mint.mjs
# dist/base、dist/policy、dist/review、dist/meta

# 2. 逐个打包 + dry-run
for p in base policy review meta; do
  mint pack "dist/$p"
  mint publish "dist/$p" --dry-run
done

# 3. 按依赖顺序发布
mint publish dist/base
mint publish dist/policy
mint publish dist/review
mint publish dist/meta

# 4. 可选：给组合包打 latest
mint tag lingcai/ql-audit latest 0.1.0
```

发布前检查：

- [ ] 四个包 `README.md` 存在，≤64 KiB；各自带 `LICENSE`（AGPL-3.0-only）。
- [ ] base 制品含 `mint.toml`、`.mcp.json`、`bin/ql-audit-base`(0755)、`lib/`、`catalog/`、`certs/*.crt`、`skills/ql-audit-base/`；不含 `node_modules/`、`.pem`、`config.json`、`bills/`、`runs/`。
- [ ] policy/review 制品只含 `mint.toml`、`.mcp.json`、`bin/` 启动器、`skills/`、`README.md`、`LICENSE`；**不含 `lib/`、`catalog/`、`certs/`**（避免重复）。
- [ ] meta 制品只含 `mint.toml`、`skills/ql-audit/`、`README.md`、`LICENSE`；**不含 `.mcp.json`**。
- [ ] 三个 `.mcp.json` 的服务 ID 唯一；`command[0]` basename 都在各自 `capabilities.exec`。
- [ ] `[dependencies]` 的 base 版本是 `=0.1.0`，与 base 实际版本一致。
- [ ] `mint publish --dry-run` 输出 4 个制品，base 大小 <10 MB，policy/review/meta 各 <100 KB。
- [ ] 干净项目分别验证：只装 policy（10 工具）、只装 review（10 工具）、装 meta（14 工具）。
- [ ] 卸载/重装后数据保留；升级不覆盖 `config.json`。

### 7.7 版本与兼容

- v0.1 四个包 **lockstep**：`lingcai/ql-audit-base`、`lingcai/ql-audit-policy`、`lingcai/ql-audit-review`、组合包 `lingcai/ql-audit` 都是 `0.1.0`；policy/review/meta 对 base 用 `=0.1.0` 精确锁。
- 发布 train 规则：
  - 改 base（含工具 schema/运行时）→ base、policy、review、meta 全部升版并重发；
  - 只改 policy → policy + meta 升版；review 可不动；
  - 只改 review → review + meta 升版；policy 可不动；
  - 只改 meta 的 SKILL → 只升 meta。
- 工具 schema 变更遵循 semver：新增可选参数 minor；改必填/删字段 major；工具增删视为 major。
- 数据目录加 `config.version`；未来迁移只做向前兼容。
- 兼容性矩阵：Mint core ≥0.1.14（实测基线）、Node ≥22.13、macOS 14+（Keychain 路径）；Linux 未实测。0.1.6 的早期 POC 仅作历史记录。
- 如果未来要独立版本：把 base 依赖改成 `^0.1`，启动器按 `mint.lock` 锁定 base，而不是 `sort -V` 取最高；v0.1 不做，避免版本漂移。

---

## 8. 实施计划

### 8.1 阶段

| 阶段 | 工作 | 产出 | 预估 |
|---|---|---|---|
| P0 | 冻结契约与包拆分：14 工具/服务矩阵、依赖图、exact pin、目录布局 | `CONTRACT.md` + 4 个 `mint.toml` 骨架 | 1 天 |
| P1 | 抽 `core/` + base 运行时：config/store/catalog/protocol、`groups/base.mjs`、6 工具 | 可独立跑的 base 包 | 3 天 |
| P2 | policy：`groups/policy.mjs` 4 工具、base 定位启动器、SKILL | 可 `mint add` 的 policy 包 | 2 天 |
| P3 | review：`groups/review.mjs` 4 工具、启动器、SKILL | 可 `mint add` 的 review 包 | 2 天 |
| P4 | meta + 打包：stage 4 个 dist、README/LICENSE/certs、权限声明 | 4 个可 pack 目录 | 2 天 |
| P5 | 测试：55 个旧测试 + 契约/多包/真实 PDF/报文 | 绿色测试与验收记录 | 3 天 |
| P6 | 发布：4 包 pack/dry-run/publish/tag + 干净项目三模式复验 | MintHub 0.1.0 | 1 天 |
| P7 | 可选：native/SEA、本地 PDF、QL AST 预检、SQLite state store | v0.2+ | 另计 |

合计约 14 个工作日；比单包多约 2 天（多包打包、依赖/启动器/组合测试）。加缓冲按 **3 周（1 人）** 排。

### 8.2 任务清单

**P0 契约与拆分**

- [ ] 写 `CONTRACT.md`：3 个服务、14 个工具全名、参数、返回、错误码、verdict 映射、配置项、数据目录。
- [ ] 冻结分组：base 6（health/config/versions/scenes/rules）、policy 4、review 4；写明“为什么 `ql_list_*` 放 base”。
- [ ] 冻结包图：`meta → {base, policy, review}`、`policy/review → base`；exact pin `=0.1.0`。
- [ ] 冻结发布 train：base 改动四包齐发；policy/review 单侧改动只升自己 + meta。
- [x] 验证 meta 无 `capabilities`、无 `.mcp.json` 时 `mint pack` 可接受（最小包实测通过）；无需占位。
- [ ] 记录已确认决策：组合包 `lingcai/ql-audit`、三个子包名、AGPL-3.0-only、RSI 不暴露、默认 endpoint + 对话修改。

**P1 核心解耦 + base**

- [ ] 把 `server/*` 抽到 `core/`；PilotDeck 与 Mint 各自薄适配。
- [ ] `config.mjs`：数据目录、CA 默认值、原子写、0600、密码来源、`ConfigStore` 接口。
- [ ] 默认数据目录改 `~/.mint/ql-audit`；保留 `QL_AUDIT_DATA_DIR` 覆盖（测试/CLI）。
- [ ] 默认 CA 改 `$PKG/certs/*.crt`；自定义 endpoint 不套默认 CA（回系统 CA）。
- [ ] `engineConfigured` 改为“username + 密码来源”。
- [ ] `mcp/server.mjs` 支持 `base|policy|review` 参数，按组**动态 import**，不加载其他组。
- [ ] MCP 握手同时支持 `initialize` 与 `server/discover`；`server/discover` 结果**直接带 `tools`**，否则 Mint 会注册 0 个工具。
- [ ] `groups/base.mjs`：6 工具；`ql_list_versions/scenes/rules` 只读 catalog。
- [ ] base 启动器 + `.mcp.json`；base 单独 `mint add` 冒烟。
- [ ] RSI 代码保留但不注册工具、不写 SKILL。

**P2 policy**

- [ ] `groups/policy.mjs`：4 工具；复用 base 的 config/store/catalog/qlengine。
- [ ] `parse.mjs`、`catalog-builder.mjs`、`rulecraft.mjs` 从现有代码迁移；解析状态机/锁/裁定不变。
- [ ] policy 启动器：同级定位 base；找不到时报 `BASE_NOT_FOUND` 并退出 127。
- [ ] `skills/ql-audit-policy/SKILL.md`：全名工具、一次 status、约 10 分钟、裁定纪律。
- [ ] 只装 policy 的包组合测试：10 工具，无 `ql-audit-review__*`。

**P3 review**

- [ ] `groups/review.mjs`：4 工具；复用 base 的 config/store/catalog/qlengine。
- [ ] `audit.mjs`、preflight、normalization、verdict、card 从现有代码迁移。
- [ ] review 启动器：同级定位 base；错误文案区分“base 缺失”和“Node 缺失”。
- [ ] `skills/ql-audit-review/SKILL.md`：load→versions/scenes→preflight→run→card；verdict 语义。
- [ ] 只装 review 的包组合测试：10 工具，无 `ql-audit-policy__*`。

**P4 meta + 打包**

- [ ] meta `mint.toml`：依赖三个 exact pin；无 `.mcp.json`、无 capabilities。
- [ ] `skills/ql-audit/SKILL.md`：只做路由/安装说明，不复制子 skill 流程。
- [ ] `stage-mint.mjs`：`core/` → `dist/base/lib/`；catalog/certs → `dist/base/`；policy/review 只放薄文件；meta 只放 skill。
- [ ] 四个包各自 README/LICENSE；README 写清“装 meta / 只装 policy / 只装 review”的差异。
- [ ] base/policy/review 的 `capabilities` + `reason`；meta 权限为空。
- [ ] `mint pack` 四包冒烟；policy/review 制品断言不含 `lib/`/`catalog/`/`certs/`。

**P5 测试**

- [ ] 迁移 `audit.test.mjs`、`normalization.test.mjs`、`parse.test.mjs`、`server.test.mjs`（业务段）、`mcp.test.mjs`。
- [ ] 删除/改写 `json.test.mjs` 的 browser 副本断言、`server.test.mjs` 的身份/drain 段。
- [ ] 新增 `mint-contract.test.mjs`：3 个 server ID、14 个全名、schema、错误信封、verdict、`.mcp.json`/`capabilities.exec`、无 `.pem`、四个 SKILL frontmatter。
- [ ] 新增 `mint-packages.test.mjs`：依赖图、exact pin、meta 无 `.mcp.json`、policy/review 无业务代码。
- [ ] 新增 `base-locator.test.mjs`：base 存在/缺失/多版本；缺失返回 127 与可行动文案。
- [ ] 多进程测试：base 写 config 后 policy/review 读到新值；并发追加 catalog 不损坏。
- [ ] 真实 PDF 验收（手动，约 10 分钟）；真实报文审核验收。
- [ ] 干净项目三种安装复验；Node 缺失错误文案。

**P6 发布**

- [ ] 按 base→policy→review→meta 顺序 `mint pack`、`--dry-run`、`publish`、`tag`。
- [ ] 在干净机器/新用户下分别安装 meta、policy-only、review-only，确认工具数与数据目录权限。
- [ ] 发布说明：三个能力包的差异、限制、数据出境、License、依赖关系。

### 8.3 测试计划

| 层 | 内容 | 工具 |
|---|---|---|
| 单元 | 判定表每个分支、计数恒等式、归一化、场景推荐、preflight missing/unmapped | `node --test` |
| 状态机 | 解析 running→needs_resolution→building→ready/failed、裁定累积、锁、并发只建一次 | 假 Rulecraft/假 engine |
| 契约 | 3 个 server ID、14 个全名/schema、错误码、verdict、事件字段 | `node --test` |
| 包组合 | 只装 policy=10 工具、只装 review=10、装 meta=14；无交叉工具 | `mint add` + `mint-core` 冒烟 |
| 共享状态 | base 写 config 后 policy/review 读到；并发 catalog 追加 | 多进程测试 |
| 集成 | MCP stdio 全流程（load→preflight→audit→get_result；parse→status→resolve） | 假引擎/假 Rulecraft |
| 端到端 | 真实 Rulecraft + qlengine + 真实 PDF/报文 | 手动/验收脚本 |
| 打包 | 4 个 `mint pack` 内容、无 `.pem`、权限位、依赖版本 | shell |

### 8.4 验收清单

- [ ] 干净项目 `mint add lingcai/ql-audit`：加载 3 个服务、14 个工具；工具名全部为 `ql-audit-base__*`/`ql-audit-policy__*`/`ql-audit-review__*`。
- [ ] 只装 policy：10 工具，`ql-audit-review__*` 不存在；只装 review 对称。
- [ ] `ql-audit-base__ql_get_health`：配置正确时 `ok:true`；未配置时给出可行动提示。
- [ ] `ql-audit-base__ql_get_config`/`ql_set_config`：改 endpoint/CA 后落盘 0600；policy/review 下一次调用用新配置；密码不出现在参数/返回/日志。
- [ ] 真实 PDF：`ql-audit-policy__ql_parse_policy` → `needs_resolution`/`ready`；裁定后 `ready`；`version_id` 可在 `ql-audit-base__ql_list_versions` 看到；`ql-audit-base__ql_list_rules` 能抽查规则。
- [ ] 真实报文：`ql-audit-review__ql_load_bill` → `ql-audit-review__ql_get_preflight` → `ql-audit-review__ql_run_audit` → `ql-audit-review__ql_get_result`；`card` 一致；`runs/<runId>/result.json` 存在且 0600。
- [ ] `verdict` 与 `overall/counts` 一致；`needs-human` 不被说成通过。
- [ ] `.audit/events.jsonl` 有记录；不含报文/金额/凭据；写失败时返回 `AUDIT_LOG_FAILED`。
- [ ] base 缺失时 policy/review 启动器明确报错；不出现“工具在但全部调用失败”的静默状态。
- [ ] 55+ 测试全绿；4 个包 `mint pack`/`--dry-run` 通过；policy/review 无重复实现；meta 无 `.mcp.json`。
- [ ] 卸载重装数据保留；升级不覆盖 `config.json`。

### 8.5 发布清单

- [ ] 四个包各有 `README.md`、`LICENSE`、`CHANGELOG`（可选）。
- [ ] 替换 `mint.toml` 的 `repository` 占位符；逐包 `mint pack` 产物检查（见 7.6）。
- [ ] 版本号、tag、release notes；组合包 `lingcai/ql-audit` 打 `latest`。
- [ ] MintHub 页面：组合包写“一键安装”，子包写“可单独安装”；描述/关键词/支持联系人。
- [ ] 安全说明：数据出境、CA、凭据、无沙箱风险；三个进程共享数据目录。

---

## 9. 风险与对策

| # | 风险 | 影响 | 对策 |
|---|---|---|---|
| 1 | Rulecraft/qlengine 不可达、证书/凭据错误 | 两个能力都不可用 | `ql-audit-base__ql_get_health` 前置；错误码可行动；支持内网 endpoint/CA；README 故障排查 |
| 2 | 制度 PDF/报文出境到第三方 | 合规/隐私 | 默认地址写清楚；支持内网部署；发布前确认 DPA；README 显著提示 |
| 3 | Node 不在 GUI 的 PATH | 3 个 MCP 都起不来 | 三个启动器都搜索 nvm/Homebrew/`/usr/local`；明确报错；v0.3 单文件二进制 |
| 4 | 工具调用 60 s 超时 / 50 MB 上传 | 大 PDF 上传失败 | 文档指导 `[core.loop] tool_timeout_ms = 600000`；上传前检查大小；v0.2 流式/分片 |
| 5 | 审批弹窗过多 | 体验差、headless 被拒 | 只读工具 `get/list` 命名；写/外联保留审批；批量场景用 `--approve all`；上游建议支持 MCP annotations |
| 6 | MCP 子进程无沙箱 | 供应链/越权 | 只发布签名包；企业允许列表；代码评审；敏感场景容器/VM |
| 7 | `*.pem` 导致 pack 失败 | 发布阻塞 | CA 用 `.crt`；CI 检查 |
| 8 | bundle 不能声明 env | 配置/密钥注入受限 | 数据目录默认 + config.json + Keychain；测试用 `QL_AUDIT_DATA_DIR` |
| 9 | measurementVersion 漂移 | 审核结果偏差 | 默认 `allow_drift=false` 直接报错；提示重建 catalog 或显式放行 |
| 10 | 解析 10 分钟、无后台守护 | 用户以为卡住 | SKILL 明确“本轮结束，稍后再查”；status 返回 stage/progress/hint |
| 11 | 规则质量/澄清项多 | 版本不可用 | 强制人工裁定；`ql_list_rules` 抽查；空规则 `PARSE_EMPTY` |
| 12 | 上游 AGPL-3.0 | 发布/商用合规 | 四个包都保持 `AGPL-3.0-only`；各自带 `LICENSE`；README 源码地址；公开分发前法务复核 |
| 13 | 工具名/schema 漂移 | 旧提示词失效 | 契约测试锁 3 个 server ID + 14 个全名；semver；SKILL 与测试引用同一份工具清单，发布前校验 |
| 14 | 数据增长（bills/runs/parses） | 磁盘占用 | README 清理说明；v0.2 `ql_prune` |
| 15 | Windows 不支持 | 用户面窄 | v0.1 明确 macOS/Linux；Windows 后续补 `.cmd` |
| 16 | **多包版本漂移** | policy 找到不兼容 base，工具行为不一致 | v0.1 lockstep + exact pin `=0.1.0`；发布 train 规则；契约测试校验四包版本一致 |
| 17 | **base 定位失败** | policy/review MCP 起不来 | 同 scope 同级目录 + `sort -V`；`QL_AUDIT_BASE_DIR` 测试覆盖；缺失时 127 + 可行动文案；P5 专门测试 |
| 18 | **3 个 Node 进程内存/启动开销** | 比单包多约 2 个进程 | 按 group 懒加载，base 不在启动时读 catalog；实测内存；若超预算，v0.2 提供 `all` 组单服务模式 |
| 19 | **工具前缀变长、模型混用** | 模型调错服务或漏前缀 | SKILL 只写全名；每个服务的 `instructions` 只列本组工具；契约测试校验全名；必要时在 base 提供“工具索引”说明 |
| 20 | **base 单点故障** | base 的 bug 同时影响两个能力 | base 独立测试/版本；policy/review 精确锁 base；可回滚 base 版本；紧急时可临时把 base 的 group 代码内联到能力包（不推荐长期） |
| 21 | **安装确认展示三次权限** | 用户觉得吵 | meta 的 README 说明会装三个子包；子包权限逐项写 reason；v0.2 若支持包组合权限合并再优化 |

---

## 10. 决策记录

### 10.1 已确认（2026-10-30）

| # | 决策 | 结论 | 落地 |
|---|---|---|---|
| 1 | 包结构 | 组合包 `lingcai/ql-audit` 已确认；建议 4 个包：`lingcai/ql-audit-base`、`lingcai/ql-audit-policy`、`lingcai/ql-audit-review`、组合包 `lingcai/ql-audit` | 四个 `mint.toml`；meta 无 `.mcp.json`；policy/review 与 meta 精确锁 base；子包名待确认 |
| 2 | 许可证 | 四个包都保持 `AGPL-3.0-only` | 各自带 `LICENSE`；README 写源码地址与 AGPL 义务；`mint.toml` `license` |
| 3 | RSI | **不暴露** | `core/rsi/` 可保留，但不注册工具、不写 SKILL、不进入 14 工具契约；未来另立包或 opt-in |
| 4 | 默认 endpoint + 修改 | 默认保留 `123.56.15.233`；支持对话修改并本地持久化 | `ql-audit-base__ql_get_config`/`ql_set_config`；`config.json` 0600 原子写；SQLite 作为 v0.2 可选后端 |
| 5 | 共享模块 | config/store/catalog/qlengine/MCP 协议只在 base 维护一份；policy/review 是薄包 | 启动器定位 base + 组参数；policy/review 制品不含 `lib/` |
| 6 | 工具拆分 | base 6、policy 4、review 4，总数仍 14 | CONTRACT 冻结全名；每个服务只注册本组 |
| 7 | 版本策略 | v0.1 四包 lockstep；policy/review/meta 对 base 用 `=0.1.0` | 发布 train 见 §7.7；契约测试校验版本一致 |

### 10.2 仍需确认（有默认建议）

| # | 事项 | 建议 | 影响 |
|---|---|---|---|
| 1 | 目标平台 | macOS 14+ 优先；Linux 次之；Windows v0.1 不支持 | 启动器/Keychain/测试矩阵 |
| 2 | CA 分发 | 公开 MintHub 不随包带内网 CA；内部分发可带 `.crt` | 首次配置体验 vs 信息暴露 |
| 3 | 是否保留 PilotDeck 插件 | 保留，共用 `core/`；Mint 是第二发行形态 | 维护成本、代码同步 |
| 4 | 数据出境 | 默认地址已接受；README 显著提示，并提供内网 endpoint 配置 | 合规/隐私 |
| 5 | 子包是否单独上架 | 建议 4 个都上架：base 必须上架作为依赖，但页面标注“依赖包/不建议单独安装”；policy/review 可单独装；meta 一键装 | 搜索/安装体验；维护 4 个页面 |
| 6 | meta 无 capabilities 是否可 pack | 已实测可 pack（2026-10-30，最小包）；按无权限实现 | 组合包保持“零权限”；若后续版本收紧再补占位 |

> 这 6 项不阻塞 P0/P1；P3 打包前需要定 #1/#2/#5/#6，P6 发布前需要定 #3/#4。

---

## 11. 附录

### 11.1 实测记录

**环境**

```text
mint 0.1.11
mint core 0.1.14 aarch64-apple-darwin
node v24.21.0
macOS (darwin)
```

**最小 bundle**

```text
/tmp/ql-audit-poc/
├── mint.toml
├── .mcp.json
├── bin/ql-audit-mcp
├── mcp/server.mjs
├── skills/ql-audit/SKILL.md
└── certs/qlengine-ca.crt
```

`mint pack` 产物：

```text
local-ql-audit-poc-0.1.0.mint.tar.zst
```

包内文件：

```text
.mcp.json
certs/qlengine-ca.crt
manifest.json
mcp/server.mjs
mint.toml
skills/ql-audit/SKILL.md
```

**Mint 调用（单包 POC，core 0.1.14；服务 ID 为 `ql-audit`）**

```text
$ mint-core run --cwd /tmp/ql-audit-proj-014c --approve all --plain \
    "调用 ql-audit 的 ql_list_versions，只回版本 id。"
→ ql-audit__ql_list_versions
- v-88371ec6-20261029
- v-02482cdb-20261020
```

**真实审核（Mint core 0.1.14 + 真实 qlengine）**

```text
ql-audit__ql_load_bill → billId: 0d70baf6244e, invoiceCount: 2
ql-audit__ql_audit     → run_id: 20261030T030925776-0d70baf6
                         overall: 不通过
                         counts: { passed: 0, failed: 49, review: 49, missingData: 0,
                                   errors: 0, inapplicable: 4, skipped: 4, executed: 49 }
```

> 本机 `0.1.14-std` 制品的二进制自报“编译档位 core”；`mint run` 以 `flavor=std` 会报档位不匹配。因此用 `mint-core 0.1.14` + 项目 `flavor=core` 验证；正式验收需在正常 `0.1.14-std` 环境复验 `mint run`。

**踩坑记录**

1. `capabilities.env` 在 bundle 上被拒绝：`mint pack` 报“kind = bundle 不得声明该权限”。
2. `.mcp.json` 的 `${HOME}` 未展开：警告“capabilities.env 未声明这些变量，引用不展开”。
3. 包内 `certs/*.pem` 让 `mint pack` 失败：`不得打进文件 certs/qlengine-ca.pem`；改 `.crt` 后通过。
4. `command` 直接写 `node` 在 CLI 下可用；改成 `$PKG/bin/ql-audit-mcp` 后，子进程 PATH 不含 nvm，启动器必须搜索 Node。
5. 现有 MCP 服务默认数据目录是 `$PILOT_HOME/ql-audit`，在 Mint 下会读到 PilotDeck 的生产数据；必须改成 `~/.mint/ql-audit`。
6. `ql_load_bill`/`ql_preflight` 因名字不含 `get/list` 被判为 Other，触发审批；`ql_list_versions` 不触发。命名即体验。
7. 本机 `0.1.14-std` 制品二进制自报“编译档位 core”，`mint run` 以 `flavor=std` 报档位不匹配；改用 `mint-core 0.1.14` + 项目 `flavor=core` 完成验证。

**多包 POC（`/tmp/ql-mod-poc`）**

```text
base/    lingcai/ql-audit-base@0.1.0     .mcp.json → ql-audit-base
policy/  lingcai/ql-audit-policy@0.1.0   depends base; .mcp.json → ql-audit-policy
review/  lingcai/ql-audit-review@0.1.0   depends base; .mcp.json → ql-audit-review
```

```text
mint add path:/tmp/ql-mod-poc/policy
  → .mint/packages/lingcai/{base,policy,review}@0.1.0
mint-core run --approve all "依次调用三个 ping"
  → ql-audit-base__base_ping     → base pong
  → ql-audit-policy__policy_ping → policy pong
  → ql-audit-review__review_ping → review pong
```

另加一个最小 meta 包（只依赖 base/policy/review，无 `.mcp.json`、无 capabilities）：`mint add` 后 lock 4 个包，仍只加载 3 个 MCP 服务，三个 ping 全部可用。

> 最小 POC 验证了：传递依赖安装、三个 `.mcp.json` 同时加载、policy/review 同级定位 base、工具前缀正确、meta 零 MCP 组合。真实 14 工具拆分尚未实现。

### 11.2 参考文件

- ql-audit 现有代码：`products/ql-audit/plugins/ql-audit/`
  - `server/audit.mjs`、`server/service.mjs`、`server/parse.mjs`、`server/catalog-builder.mjs`
  - `mcp/server.mjs`、`skills/ql-audit/SKILL.md`
  - `catalog/catalog.json`、`catalog/fields.json`、`catalog/known-unsupported.json`
- 计划中的拆分（尚未创建）：
  - `products/ql-audit/core/`（唯一业务代码）
  - `products/ql-audit/mint/{base,policy,review,meta}/`
  - `products/ql-audit/scripts/stage-mint.mjs`
- iface 契约：`packages/agent-kernel/packages/iface-*`（权威源 `packages/agent-kernel/kernel/iface/src`；`packages/kernel-iface/` 为 0.1.0 历史快照，勿作基线）
  - `iface-tool/src/tool.rs`、`iface-policy/src/review.rs`、`iface-policy/src/audit.rs`
  - `iface-policy/src/mod.rs`（`AuditSink` 未接线）
  - `iface-context/src/trace.rs`、`iface-store/src/store.rs`
  - `PACKAGING-NOTES.md`（历史记录，现仅在 `packages/kernel-iface/`）
- Mint 内核/文档：`packages/agent-kernel/mint/`
  - `docs/03-包规范-a.md`、`docs/01-内核与三档发行-a.md`
  - `crates/mint-core/src/mcp_loader.rs`、`crates/mint-core/src/mcp/client.rs`
  - `crates/mint-core/src/mcp/types.rs`（`server/discover` 的 `DiscoverResult` 必须带 `tools`）
  - `crates/mint-core/src/approval.rs`、`crates/mint-core/src/config.rs`
  - `crates/mint-manifest/src/{mcp.rs,layout.rs,validate.rs}`
- 线上：MintHub `https://mint-hub.ea.modelbest.co`；Mint 指南 `https://mint.ea.modelbest.co/guide.html`
- 令才文档：`/Users/payne/Vibe/令才/project-docs/制度解析接口V3契约与联调手册.md`、`qlengine-架构与本机全流程.md`

### 11.3 术语

| 术语 | 含义 |
|---|---|
| bundle | Mint 声明式包，可带 skills/commands/agents/hooks/`.mcp.json`，`layout="any"` |
| MCP | Model Context Protocol；本插件用 stdio JSON-RPC |
| Rulecraft | 令才制度解析服务 V3；PDF→规则 |
| qlengine | QL 编译/执行服务；`/compile`、`/execute/batch` |
| catalog | 规则版本库，`ql-audit.catalog/v1` |
| verdict | 本插件对审核结论的稳定枚举：approve/reject/needs-human/revise |
| iface | AgentCPM 的 Rust trait 形状契约；本插件只做语义对齐 |
| ToolKind | Mint 对工具的分类（Read/Search/Edit/Execute/Other 等），影响审批 |
| base / policy / review | 三个 MCP 服务：共享基础 / 制度解析 / 报文审核 |
| meta | 组合包 `lingcai/ql-audit`，无 MCP，只依赖前三个并带总 SKILL |
| group | base 运行时按 `base|policy|review` 只注册本组工具的模式 |
