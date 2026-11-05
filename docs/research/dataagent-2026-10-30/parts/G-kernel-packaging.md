# G — Kernel / MintHub 能力边界与 DataAgent 打包约束

> 调研日期：2026-10-30。只读本地仓库，未联网。基线：`packages/agent-kernel` HEAD `86ae83c`（CLI 0.1.13 / core 0.1.14）。
> **注意版本落差**：线上 0.1.11/0.1.12 的行为与此处源码不一致处已单独标注，正文引用默认指 HEAD 源码。

---

## 1. 结论摘要

1. **DataAgent 的正确载体是 `bundle`（能力入口）+ `preset`（组合）**，不是 `plugin`：`plugin` 必须声明 `subkind ∈ {wasm,native,js}`（`crates/mint-manifest/src/validate.rs:222-227`），Python 进程三者都不属于。
2. **`bundle` 在 HEAD 已能携带并拉起 stdio MCP server**：内核扫 `mint.lock` 内 bundle 包的 `.mcp.json`（`crates/mint-core/src/mcp_loader.rs:442`），按 `capabilities.exec`/`capabilities.env` 白名单校验后拉起并注册工具（同文件 `:188`、`:344`）。这条推翻了 10-28 文档"bundle 0.1 只装载 skills"的口径——但**只对达到该版本的 core 成立**；0.1.11 实测拒绝 bundle `capabilities.env`（`apps/plugins/ql-audit/README.md`「本机 Mint 0.1.11 不接受」、`docs/progress.md:34`）。
3. **`kind = mcp` 目前只是清单形态，内核不消费**：`Kind::Mcp` 只出现在 manifest/layout/validate（`layout.rs:167`、`validate.rs:416`），`mcp_loader` 只认 bundle 与项目配置。因此把 DataAgent 发成 `mcp` 包今天装得下、跑不起来。
4. **`kind = iface` 已在源码里落地但未发布**：枚举见 `lib.rs:50-53`，布局 `layout.rs:129-139`，校验 `validate.rs:393-415`（只要求 `provides.interfaces` 非空 + `src/` 或 `schema.json`）；十个 `agentcpm/iface-*` 仍发 `kind = "bundle"`（`packages/kernel-iface/iface-tool/mint.toml:4`）。
5. **`requires.interfaces` 有安装期 peer 校验**（`bins/mint/src/install/interfaces.rs:93`），但没有"实现是否符合契约"的校验，也没有 resolver 级约束。
6. **MCP 工具没有任何 CallCtx 透传**：`McpToolAdapter::call` 形参是 `_ctx`（`mcp/client.rs:562-566`），租户/会话身份只能由 server 启动参数固定。
7. **单次 MCP 请求硬超时 60s**（`mcp/transport.rs:24`），shell 上限 600s（`tools/builtin.rs:612`），内核无后台 job 原语——长任务必须由 server 自己做 job 化（先受理后轮询）。
8. **升级只动受管元数据，绝不迁用户数据**：`bins/mint/src/cmd/app_install/upgrade_workspace.rs:1`「Upgrade only managed metadata and packages, never copy the user's workspace」。迁移必须由包自己实现。

---

## 2. kind 能力矩阵（能力 × kind）

✅ 源码已实现　⚠️ 声明可得但无消费者/有硬限制　❌ 不支持

| kind | 运行时装载什么 | 声明 MCP 工具 | 注入提示词 | 带二进制/Python | 依赖与锁 | 关键硬约束（证据） |
|---|---|---|---|---|---|---|
| `skill` | 根 `SKILL.md` 一行摘要 + `skill_read` 正文（`mint-core/src/loader.rs:174-178`） | ❌ | ✅ | ⚠️ `scripts/` 可打但内核不执行 | 随包 | 只装一个技能；正文 32 KiB 上限（`loader.rs:14`；`layout.rs:154-165`） |
| `bundle` | `skills/*/SKILL.md`（`loader.rs:178-182`）+ `.mcp.json`（`mcp_loader.rs:442`） | ✅ | ✅ | ✅ 任意文件、保留 0755 | ✅ `[dependencies]` | `commands/`/`agents/`/`hooks` 声明无消费者（`host/load.rs:326-356` 只收 plugin/overlay）；`capabilities.exec` 必需 |
| `mcp` | 无（内核零引用） | ⚠️ 仅清单 | ❌ | — | ✅ | 需 `[mcp]`/`server.json`（`layout.rs:167-179`） |
| `preset` | `prompts/{slot}.md` 注入 + `preset.toml` 合并 `[packages]`/`[policy]`（`bins/mint/src/preset.rs:1-20`） | ❌ | ✅ | ❌ | ✅ 至少一个依赖（`validate.rs:422-431`） | `[policy]` 只能收紧；无代码、无入口 |
| `app` | 整棵成品树，交付的是 `bin/`+`packages/`+`mint.toml`+`mint.lock`（`layout.rs:187-201`） | 随内层包 | 随内层包 | ✅ | ✅ 自包含，`deps` 必须为空（`validate.rs:437-457`） | `layout="target"`、禁 `requires.api`；装完不再解析依赖 |
| `plugin/js` | `dist/index.js` 经 V8 host 提供 tools/hooks（`host/load.rs:139-158`） | ⚠️ 只能经 host 工具 | ❌ | ❌ 单文件 ESM，不带 `node_modules` | ✅ | 仅 std 档 + `js-host` 特性 + 项目已 `mint trust`（`host/load.rs:78-107`） |
| `plugin/native` | 内核不加载；`[provides] ui` 的界面包由 `mint` 拉起 | ❌ | ❌ | ✅ `bin/` | ✅ | 需 `layout="target"`+`requires.api`（`validate.rs:324-333`） |
| `plugin/wasm` | 内核不加载（`mint-wasm-host` 独立） | ❌ | ❌ | ✅ `dist/*.wasm` | ✅ | `layout="any"`；`flavors` 不得含 core |
| `overlay` | `overlay.toml` 或 `dist/index.js`：prompt/tool/ui 覆盖（`mint-core/src/overlay.rs:1-40`） | ❌ | ✅ | 仅 JS | ✅ | `provides` 只允许 D7 白名单（`validate.rs:326-372`） |
| `iface` | 不装载（纯形状） | ❌ | ⚠️ 允许带 skill | ✅ `src/`/`schema.json` | ⚠️ 无 | 未发布：0.1.11 报 `unknown variant iface` |
| `template` | ❌ 无 CLI 入口 | ❌ | ❌ | ❌ | ❌ | 只校验 `template/`（`layout.rs:182-186`） |
| `agent` | 项目清单本身 | — | — | — | — | 不发布（`lib.rs:62-63`） |

**三条最容易踩的边界**：(a) bundle 里的 `hooks/hooks.json` 会被打包、被翻译，但内核不加载；(b) `capabilities.fs.read` 写 `$PKG`/`$PKG_DATA` 在能力匹配里**不展开**（`sandbox/policy.rs:141-160`，MVP TODO），等于不匹配；(c) `streamable-http` 传输内核未启用（`mcp_loader.rs:328`），只能 stdio。

---

## 3. 运行与工具面机制

**MCP 注册链路**：`mint.lock` → 逐包读 `mint.toml` 判 `Kind::Bundle` → 读 `.mcp.json` → `$PKG` 替换为包目录（`mcp_loader.rs:483-487`）→ 项目信任门（`mcp_loader.rs:200-245`，未信任只 warn 不拉起）→ `capabilities.exec` basename 白名单 + `capabilities.env` 变量白名单（`:330-370`）→ 并发 spawn + `server/discover`（默认 10s，`timeout_s` 可覆盖）→ 工具名 `<server>__<tool>` 注册进 `ExtensionRegistry`。**bundle 的 MCP 子进程环境被清空**，只留 `BASELINE_ENV` + 声明变量（`client.rs:213-229`），这是防三方包读走 `MINT_MODEL_API_KEY` 的关键。

**审批模型**：MCP 工具的类别不是由 server 声明，而是**按工具名猜**——`search/list/get`→Search、`read/fetch`→Read（均 Allow），`create/write/edit`→Edit，`delete/remove`→Delete，`exec/run/shell`→Execute，其余→Other（`mcp/client.rs:706-725`）；Allow 的行不需要审批，其余走 `builtin_ruling`（`approval.rs:124-157`）。这意味着 **DataAgent 的只读工具应用 `get_/list_/search_` 命名，写入类必须用 `create_/write_/exec_` 前缀**，否则会被自动放行或误判为需审批。`ApprovalMemory` 以「工具名+完整参数」为键复用 AllowOnce/AllowAlways（`:160-199`）；`CoreGuard` 是原生硬闸（`hooks.rs:32-90`），管 `deny_paths`、`allow_programs`、read-only 与外部路径授权；ACP 模式下 Prompt 走 `session/request_permission`，headless 由 `--approve` 固定回答（`approval.rs:41-52`）。导出/写入仍受 `iface_policy` 的 `check`/`check_egress` 二次约束。

**长任务**：内核只有 turn 级 `max_steps`（默认 0 = 不限）与 `max_wall_ms`（默认 2h，`config.rs:40-42`），没有后台 job/子进程管理（`max_steps > 0` 才判停，`duplex.rs:912`）；shell 与 MCP 调用都是同步等待。所以 DataAgent 必须照抄 ql-audit 的形状：受理即返回 `job_id`，`job_get` 推进/查询，重活放 worker 子进程并持久化阶段（`apps/plugins/ql-audit/docs/design.md:35,41`；实现 `capabilities/policy-extract/src/index.mjs:27-29,157-158`）。提交结果未知时写 `unknown`、不自动重放。

**产物呈现**：MCP 结果只取文本（`McpContent::join_text`，`mcp/client.rs:575-589`），`isError` 直接转 `ToolError`；`SessionEvent` 里没有文件/附件事件（`mint-protocol/src/session.rs:364-441`），`ContentBlock` 只有 Text/Image(blob sha256)/Json（`:15-29`），shell 输出截断 32 KiB。**结论：产物必须以"路径 + digest + 摘要"的文本形式回给模型，GUI 只能按文本渲染**；需要图片时用内容寻址 blob。

---

## 4. 资产与版本化建议

| 资产 | 放哪 | 理由 |
|---|---|---|
| ontology / 语义层 schema、连接器声明、profile 归一器 | **包内**（`bundle` 的 `ontology/`、`schemas/`） | 随 lock 内容哈希固定；`mint pack` 只排 `.git/node_modules/target/.mint/credentials.toml/*.pem/.env*` 与符号链接（`layout.rs:9-22`；符号链接另由 `mint-pack/src/archive.rs:94-97` 跳过），其余原样入制品 |
| 运行期 job/产物/规则包 | **安装目录外**（显式 env 指向的工程目录或用户数据目录） | `.mint/packages/<scope>/<name>@<ver>/` 在升级时被整目录替换（`mint-protocol/src/dirs.rs:112-116`；`upgrade_workspace.rs:107`） |
| 凭据 | 只写环境变量引用 | 模型密钥解析顺序 = env > `~/.mint/credentials.toml`（`config.rs:7-8`）；安装器只写引用不写值（`rsi-toolkit/docs/design/mint-distribution-0.2.md`「writes only environment variable references」） |

`$PKG_DATA` 目前**只有规范、没有实现**（`docs/03-包规范-a.md:113` vs 全仓 grep 仅 `sandbox/policy.rs` 注释），不要依赖。建议 DataAgent 用 `DATAAGENT_PROJECT_ROOT` / `DATAAGENT_DATA_ROOT` 两个显式变量（同 ql-audit 的 `QL_AUDIT_*` 做法），并在启动时校验 `realpath` 是否落在允许目录内。迁移：每次运行把「包版本 + 制品 digest + 资产 digest + 配置指纹」写进 job，重启时指纹不一致就暂停要求显式迁移（`docs/dev/ql-audit/2026-10-30-minthub-modular-proposal.md:322-328`），不静默换版本。

---

## 5. 选型表与推荐

| 形态 | 交付内容 | 版本锁定 | 升级/迁移 | 适用与代价 | 判定 |
|---|---|---|---|---|---|
| **bundle-only** | `.mcp.json` + `capabilities.exec/env` + Skill + 资产 | 依赖 `[dependencies]` 逐条 | 单包替换，数据自理 | 一个能力入口；无组合视图，用户要自己装齐 | ⚠️ 备选 |
| **bundle + preset**（推荐） | 上面的 bundle ×N + `preset` 用 `=0.1.0` 钉死 | preset 精确锁 + `mint.lock` 内容哈希 | 一次 `mint add` 装齐，升级只动 lock | core 需达到支持 bundle `capabilities.env` 的版本；preset 不能带代码 | ✅ **推荐** |
| **app** | `mint unit build` 产出自包含树（`bin/`+`packages/`+lock） | lock 冻结，`deps=[]` | 只能整体换版，`--repair` 只修元数据 | 一键交付体验最好；但等于把运行时一起发，且要按 target 打包签名 | ⚠️ 需"开箱即用"时再上 |
| **plugin + skill** | JS 工具/覆盖 + Skill | 随包 | 热替换 | 仅 JS；Python 不可用；还要求 std + trust | ❌ 不适用 |

**推荐：`bundle`（能力入口，含 `.mcp.json`、`capabilities.exec=["python3"]`、`capabilities.env` 白名单、Skill）+ `preset`（组合与精确锁）+ 独立 `iface`-形态 bundle（只放 schema/fixtures，`provides.interfaces=["dataagent-*"]`）**。理由：Python 进程只符合 MCP 这条路；bundle 已能同时承载 Skill、资产与 stdio server；preset 是唯一能"一次装齐 + 精确锁版本"的声明式手段，且合并 `[policy]` 只能收紧不会放宽；iface 包给下游替换实现，不引入运行依赖。

**版本门槛**：把 `[requires] api` 与 core 下限提到支持 bundle `capabilities.env` 的版本（HEAD 0.1.14 支持，0.1.11 不支持，中间版本未测）；对旧版提供 legacy 路径——由显式 setup 脚本把绝对值入口写进工程 `.mcp.json`（ql-audit 已验证该退路，`README.md`「兼容构建」段；`scripts/install-local.mjs:40-60`）。

---

## 6. 未确认 / 风险清单（需找 Mint 团队确认）

1. **bundle `.mcp.json` + `capabilities.env` 的首个支持版本**：仓库 HEAD 有，0.1.11 明确拒绝；中间版本行为未测。
2. **`kind = mcp` 是否要接懒拉起**：若接，DataAgent 应改发 `mcp` 而非 `bundle`，两者不能同时声明。
3. **`$PKG_DATA` 何时实现**：现在包级可写数据目录无官方约定，只能靠自定义 env。
4. **60s MCP 请求超时是否可配**：`ToolSpec.timeout_hint_ms` 有字段，但 MCP 通路未使用；长查询必须 job 化。
5. **MCP 子进程无沙箱**（`client.rs:199-236` 直接 `Command::spawn`）：本机数据库/文件访问不受 CoreGuard 约束，边界靠 server 自身；企业部署是否要求加围栏。
6. **`MINT_EGRESS_AMBIENT=trusted-only` 会连 bundle 的 MCP 一起拒**（purpose `mcp.spawn:bundle`，`iface_adapters/policy.rs:204-220`）；默认 `allow` 则等于不设防，需要产品口径。
7. **`requires.interfaces` 只做 peer 存在性/版本证据校验**（`install/interfaces.rs:93-130`），不校验实现；`iface` kind 尚未发布。
8. **无安装钩子**：`pip`/`npm` 依赖、`.mcp.json` 写绝对入口都要显式 setup；`uninstall`/升级不清理数据（`ql-audit` 提案 `:311-328`）。
9. **工具类别靠名字猜**（`mcp/client.rs:706-725`）：命名不当的写工具会被当作只读自动放行；是否改成 server 显式声明 `ToolKind`（`ToolSpec.kind` 已有字段，MCP 侧未用）。
10. **打包无大小上限、无密钥扫描**（`docs/03-包规范-b.md:399` 自述「大小上限与密钥样式扫描未实现」）；只有 `MAX_FILES = 10_000`（`mint-pack/src/lib.rs:30`）。
11. **bundle 的 `commands/agents/hooks` 是死声明**：0.1 无对应扩展点（`docs/03-包规范-a.md:105`），不要写进对外承诺。
