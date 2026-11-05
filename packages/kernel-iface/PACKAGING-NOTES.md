# iface 包 Mint 化：试点（iface-env）+ 9 包打包矩阵

> 目录说明：本记录随接口包迁移到 `AgentOS/packages/kernel-iface/`。文中 `repos/agent-kernel/...` 等路径是当时验证时的历史路径；在当前工作区执行时，以本目录和 `workspace/projects.yaml` 为准。

> **2026-10-29 状态更新（先读这条）**：本文 §1/§3 关于 `kind="iface"` 的结论已被上游改变——
> `ee00617`（2026-10-27）起，10 个包改用 **`kind = "bundle"`** 发布（bundle 要求 `skills/` 等形态字段之一，
> 因此每包新增 `skills/<包名>/SKILL.md`，并在 `provides.skills` 声明）；hub 上现存 `agentcpm/iface-*@0.1.0`
> 的 `kind` 实测就是 `bundle`。本文的 kind 分析与 `Kind::Iface` 提案仍有参考价值，但**不再描述当前制品形态**。
> 2026-10-29 本目录已按 kernel master `d950766` 重新同步（22 个 trait / 44 文件 / 6292 行），详见 `README.md`。

- 日期：2026-10-26
- 执行：teammate `model-runtime`（task-62）
- 用户问题：「目前哪些 iface 包准备好了？可以 push 到 mint hub 上？」
- **一句话回答**：**9 个契约在代码里都就绪，且技术上"能 push"——但 mint 没有 iface 这个 kind（也没有 `provides.interfaces` 进索引），所以今天只能以 `kind="skill"` 的**变通形态**发出去 1 个试点（已实测打通）；要"正当地"发，需要 mint 侧加 `Kind::Iface`（或 `Subkind::Iface`）+ `Provides.interfaces` 进索引。**

## 0. 试点结论（iface-env，全链路真实验过）

| 环节 | 结果 | 耗时 |
|---|---|---|
| 建包 `repos/agent-kernel/packages/iface-env/` | `mint.toml` + `SKILL.md` + `README.md` + `schema.json` + `src/`(6 文件 523 行) | — |
| `mint publish` → 本机 MintHub | **✓ 成功**，`seq 6`，`agentcpm/iface-env@0.1.0` | **0.140 s** |
| hub 可见 | `mint search iface` → `agentcpm/iface-env skill 0.1.0` ✓ | — |
| 空工程 `mint add agentcpm/iface-env` | **✓ 从 registry 下载安装**（`^0.1.0` 写进 mint.toml） | **0.258 s** |
| 内容断言 | 安装 12 个文件；**6 个 `src/*.rs` 与源仓库 shasum 逐一相同**；`schema.json` 可解析；`manifest.json` 有 dirhash | — |
| 安装体量 | 56 KB | — |

**发到哪**：本机 MintHub（`http://127.0.0.1:8788`，`mint-hub` standalone：SQLite + blob）。发布产物含 **minisign 签名**（`sig.keyid=713d5a50bc7eebe4` + `trusted comment`）、`cksum`(sha256)、`integrity`(sha512 h1)。

## 1. mint 的 kind 现实（硬事实，全部来自源码）

`crates/mint-manifest/src/lib.rs` 的 `Kind` 枚举 = **11 个**：
`core / host / plugin / overlay / bundle / skill / mcp / preset / template / app / agent`（+ 不发布的 `Agent`）。
`Subkind` = **3 个**：`wasm / native / js`。

**没有 `iface`**（既没有 `Kind::Iface`，也没有 `Subkind::Iface`）。

### 1.1 为什么不能直接用 `kind="plugin"`（最像的那个）

- `plugin` 强制要求 `subkind`：源码 `crates/mint-manifest/src/validate.rs:119`
  `(Kind::Plugin, None) => missing(&mut errs, kind, "subkind（wasm / native / js）")`。
- 实测报错：`kind = Plugin 缺少 subkind（wasm / native / js）`。
- iface 契约**既不是 wasm、也不是 native 二进制、也不是 js**——硬套任何一个都是**说谎**，所以不走。

### 1.2 逐个 kind 的"能不能装一个纯契约包"（源码 + 实测）

| kind | 硬性要求（validate.rs / layout.rs） | 能装 iface 纯契约包？ |
|---|---|---|
| `core` / `host` / `app` | 需要 `bin/mint-core`（或 mint-host）；app 还要 `packages/`+项目 mint.toml | ✗ |
| `plugin` | **必须** subkind ∈ {wasm,native,js}；wasm 要 `dist/*.wasm`、native 要 `bin/` 可执行、js 要 `dist/index.js` | ✗（语义说谎） |
| `overlay` | 要 `dist/index.js`；provides 限 D7 白名单 | ✗ |
| `bundle` | 要 `skills/`/`commands/`/`agents/`/`hooks/hooks.json`/`.mcp.json` 之一（实测报过） | ✗ |
| `skill` | 要根目录 `SKILL.md`；`provides.skills` ≤1 | **✓（唯一可行，见 §2）** |
| `mcp` | 要 `[mcp]` 节或 `server.json`/`.mcp.json` | ✗ |
| `preset` | 要非空 `[dependencies]` + `provides.presets` | ✗ |
| `template` | 要 `template/` 目录 + `provides.templates` | ✗ |

**结论：11 个 kind 里，只有 `skill` 能承载一个"纯文档+源码+schema"的包**（因为它唯一的硬要求是一份 `SKILL.md`，而契约文档天然可以写成 SKILL.md）。这是我选它做试点的原因，**不是因为它语义正确**。

## 2. 试点的实际形态（变通，已标注）

```toml
# packages/iface-env/mint.toml
[package]
name = "agentcpm/iface-env"
version = "0.1.0"
kind = "skill"            # ← 变通：mint 无 iface kind
description = "AgentCPM iface-env：第 9 个接口契约（EnvId/Environment/PathUri/FsBackend/ExecBackend）——只定义形状，不做实现"
license = "Apache-2.0"
keywords = ["iface", "env", "contract", "cross-device", "path-uri"]   # 上限 5（实测超了会报错）

[provides]
interfaces = ["env"]      # ← 我们的意图声明；mint schema 里没有这个字段
skills = ["iface-env"]    # ← skill kind 的硬要求

[requires]
api = ">=0.1"             # 必须是 semver VersionReq（写 "agentcpm-lc>=2" 会 TOML/版本解析失败，实测）
```

包内容：`mint.toml`、`SKILL.md`（契约使用指引）、`README.md`、`schema.json`（机器可读：类型/字段/方法签名/错误码/不做什么/消费方）、`src/`（verbatim 复制 `kernel/iface/src/env/` 6 文件 523 行）。

### 2.1 字段级"保留/丢弃"实测（很关键）

| 位置 | `provides.interfaces` | 说明 |
|---|---|---|
| 源码 `mint.toml` | ✓ 有 | 我们写的 |
| **打包内 `manifest.json`**（`mint pack` 产物） | **✓ 保留了** `provides: {"skills":["iface-env"],"interfaces":["env"]}` | 因为 `Provides` 有 `other` map 兜未知键（`validate.rs` 里 `pv.other.keys()` 可证） |
| **hub meta / 索引**（`/meta/agentcpm/iface-env/0.1.0.json`） | **✗ 丢了**（meta 只有 `kind/vers/deps/api/capabilities/cksum/integrity/sig/...`，无 provides.interfaces） | 索引 schema 没这个字段 → `mint search`/`info`/依赖解析**都看不到**它是 iface 契约 |

**这就是"能发但发不正"的精确位置**：装下来的人（读 tarball 内 manifest.json）能看到 `interfaces`；但 registry 侧、搜索侧、解析侧看不到。

## 3. 9 个 iface 的打包矩阵

iface 测试基线：**55 passed**（`cargo test -p agentcpm-iface`）。所有 9 个模块都遵循同一形状：`//!` 文档 + `pub struct/enum` + `pub trait`，且**统一 `use super::types::*`**（`SessionId`/`TurnId`/`Cursor`/`Error`/`ErrorCategory`/`BoxFuture` 都在 `types/`，694 行）。

| # | iface 模块 | 行数(文件数) | 契约要点 | 依赖 | kind 适配 | 今天能发？ |
|---|---|---|---|---|---|---|
| 1 | `env`（`iface-env`） | 523 (6) | EnvId/Environment/PathUri/FsBackend/ExecBackend | `types` | skill（变通） | **✓ 已发（试点）** |
| 2 | `session` | 925 (9) | 会话生命周期/attach/drain_inbox | `types` | skill（变通） | ✓ 同构，可发 |
| 3 | `policy` | 527 (4) | Guard 判决/Scope/Decision + egress/delegation/review | `types` | skill | ✓ 可发 |
| 4 | `model` | 27 (1) | ModelRequest/ModelResponse/ModelContract | `types` | skill | ✓ 可发（小） |
| 5 | `store` | 24 (1) | EventRecord/只追加/检查点 | `types` | skill | ✓ 可发（小） |
| 6 | `tool` | 35 (1) | ToolContract/调用形状 | `types` | skill | ✓ 可发（小） |
| 7 | `context` | 27 (1) | 上下文/压缩边界 | `types` | skill | ✓ 可发（小） |
| 8 | `loop_` | 33 (1) | LoopContract/interrupt 签名 | `types` | skill | ✓ 可发（小） |
| 9 | `extension` | 38 (1) | L-B 扩展契约（WIT 草稿） | `types` | skill | ✓ 可发，但内容最薄（草稿） |
| — | `types`（共享） | 694 (2) | SessionId/TurnId/Cursor/Error/BoxFuture… | — | **必须一起发或做依赖** | 关键前置 |

**"9 个里今天能发几个"——诚实结论：9 个都能以 `skill` 变通形态发（试点已证明链路口径），但 0 个能"正当"发（无 kind）。** 且这 9 个包**都不能单独自洽**——它们都 `use super::types::*`，所以正确做法是：
- 先发 **`agentcpm/iface-types`**（1 个共享类型包），其余 9 个声明依赖它；或
- 每个包冗余带上 `types/`（体积小、无依赖，但 9 份重复）。
实测我这份试点的 `src/mod.rs` 里仍是 `use crate::types::{Error, ErrorCategory};` → **作为独立包并不编译**（诚实标注：这是形态 A 的已知缺口，见 §5）。

## 4. 批量发布步骤（试点已跑通，可复制）

```bash
cd /Users/luyaxi/AgentCPM && source scripts/env.sh
export MINT_BIN=$PWD/.tmp/mint-target/release/mint MINT_HUB_URL=http://127.0.0.1:8788 MINT_HOME=$PWD/.tmp/mint-hub/home
repos/agent-kernel/scripts/mint-adapter/local-hub-up.sh start     # 幂等，hub :8788

# 每个 iface 包（示例：env 已发；其余同构）
( cd repos/agent-kernel/packages/iface-env && "$MINT_BIN" publish -y )   # 0.14 s
"$MINT_BIN" search iface                                                 # 可见性
mkdir -p /tmp/consumer && cd /tmp/consumer && "$MINT_BIN" init --offline --no-preset -y .
"$MINT_BIN" add agentcpm/iface-env -y                                     # 0.26 s，从 registry 装
```

批量时建议脚本化：`for m in env session policy model store tool context loop extension; do (cd packages/iface-$m && mint publish -y); done`（**需先补 `types` 依赖**，见 §3）。

## 5. 需要 mint 侧改什么（这是"能不能正当发"的唯一阻塞）

**最小改动（推荐，二选一）**：
1. `Kind::Iface` 变体（`as_str() = "iface"`）+ 在 `validate.rs` 给 `(Kind::Iface, None)` 一条规则：要求 `provides` 里至少一个 interface 名，且**不要求** subkind / bin / dist；
2. 或 `Subkind::Iface` + 放开 `(Kind::Plugin, None)` 的硬校验（把 iface 视作 plugin 的一个子类）。

**再加一条（必要）**：`Provides.interfaces: Vec<String>` 进结构体 + 进 **hub 索引 meta**（否则搜索/解析仍看不到），并让 `mint info` 显示它。

**可选**：`mint requires` 支持 `interfaces = ["env"]`（消费方声明"我需要 iface-env ≥0.1"），这样 iface 包之间能形成真实依赖图。

## 6. 未做 / 限制

1. **真实远端 MintHub**：只在**本机** hub（:8788）验证；`mint-hub.ea.modelbest.co` 需要管理员令牌与网络，未发（也未验证线上对 `agentcpm/` scope 的政策）。
2. **签名校验未闭环**：publish **确实签了**（minisign，`sig.keyid=713d5a50bc7eebe4`），但**消费侧（`mint add`/`agentcpm`）没有验证策略**，更没接到 kernel 的 delivery 校验——"有签名 ≠ 验签名"。
3. **9 个里只发了 1 个**（env）；其余 8 个是"同构可发"，未逐个 publish（时间盒）。
4. **`types` 依赖未解决**：试点的 `src/` 不自洽（依赖 `crate::types`），需 `agentcpm/iface-types` 或冗余携带。
5. **版本策略未定**：现全部 `0.1.0`；契约变更（如 PathUri 语义调整）如何升版、如何让旧消费方 fail-closed，未定。
6. **`mint` 的 `--frozen`/`vendor` 离线形态未验证**（本试点走 registry 在线拉取）。
7. **未改 mint 源码**（遵守约束）；上面 §5 的改动只是**建议**，需要 mint 维护方（用户/mint owner）拍板。

## 7. 一句话给用户

- **现在能发吗**：能，但只能伪装成 `skill`；今天已成功发 1 个（`agentcpm/iface-env@0.1.0`），全链路 0.4 s 级。
- **发到哪**：本机 MintHub 已验证；线上 hub 需要令牌 + 发布策略确认。
- **缺什么**：mint 的 `Kind` 里加一个 `iface`（或把 `Subkind` 加 `iface`），并把 `provides.interfaces` 放进 hub 索引；否则"发出去的 iface 包"在 registry 里看不出是 iface。

---

# 追加（2026-10-26 晚 · D72 落地）：iface 已"正当化"，不再需要 skill 变通

用户拍板 **B（正当化）**。mint 侧已改（`repos/mint`，未 commit，待 Lead 单独提交）。

## 1. ⚠️ 先更正本 note 前面的一处错误结论

前面 §2.1 写"`provides.interfaces` 在 hub 索引 meta 里丢了"——**这条结论是错的**，特此更正：
- 实测（直查 hub SQLite `versions.publish_json`）：`{"interfaces":["env"],"skills":["iface-env"]}` **一直在**；
- `VersionMeta.provides` 是 `Option<serde_json::Value>`，`from_publish` 原样带出 → `/meta/...json` 里 **本来就有** `provides`；
- 我当时用了 `curl ... | head -40` 截断输出 + 一次读到 `null` 的采样，误判成"索引丢掉该字段"。**错在我的观测，不在 mint。**

真正缺的只有两处（现在都已补）：
1. **没有 `Kind::Iface`** —— iface 只能伪装成 skill/plugin、语义不对；
2. **`[provides] interfaces` 不是一等字段**（靠 `Provides.other` flatten 兜底）——能跑，但无类型、无校验、无文档；
3. 附带：`mint search` 表格不显示 interfaces（只有 `info` 显示）。**注：`mint info` 当时已能显示** `提供 {"interfaces":["env"],...}`。

## 2. mint 侧改动（4 个文件，最小侵入）

| 文件 | 改动 |
|---|---|
| `crates/mint-manifest/src/lib.rs` | `Kind` 新增 **`Iface`**（`as_str()="iface"`，serde 自动接受 `"iface"`）；`Provides` 新增一等字段 **`interfaces: Vec<String>`**（`#[serde(default, skip_serializing_if="Vec::is_empty")]`；wire 形状与原先落在 `other` 时完全一致 → 旧包可解析） |
| `crates/mint-manifest/src/validate.rs` | 新增 `Kind::Iface` 分支：**要求** `[provides] interfaces` 非空、名字非空且不含空白；**不要求** subkind / bin / dist / template / layout；禁止 `provides.ui`；iface 归入"不执行代码"集合（不得声明运行时权限） |
| `crates/mint-manifest/src/layout.rs` | 新增 `Kind::Iface` 分支：**只要求根目录有 `mint.toml`**，任意附加内容（`src/`、`schema.json`…）都允许 |
| `crates/mint-manifest/tests/iface_kind.rs`（新，7 测试） | 正例（无形态字段可过 / 多 interface）、反例（缺 interfaces、空名、含空白、声明 ui、声明 capabilities）、向后兼容（`other` 兜底仍在、旧 kind 行为不变） |

**hub 侧零改动**：因为 `VersionMeta.provides` 本来就是 `Option<Value>` 原样透传，`kind` 也是原样透传 → `kind="iface"` 与 `interfaces` 自动出现在 `/meta`、`search`、`info`（实测见 §3）。**这就是"索引"之前看似缺字段的真正原因：字段一直在，是 kind 没被承认。**

## 3. 落地验收（全部实测）

| 验收项 | 结果 |
|---|---|
| `kind="iface"` 能 publish | ✓ `agentcpm/iface-env@0.1.0`（**0.113 s**），hub seq 6 |
| hub `/meta` 带 kind + interfaces | ✓ `kind = iface`，`provides = {"interfaces": ["env"]}` |
| `mint search` 显示 | ✓ 表格"类型"列 = **`iface`** |
| `mint info` 显示 | ✓ `(Iface)` + `提供 {"interfaces":["env"]}` |
| 空 root `mint add`（kind=iface） | ✓ **0.253 s**，装 12 文件（与 manifest 一致） |
| 批量：4 个包从 registry 装成功 | ✓ `iface-env` / `iface-types` / `iface-session` / `iface-policy`，`mint list` 全部 **类型=iface / T1 / registry+http://127.0.0.1:8788/index/**，合计 **1.06 s** |
| 旧 kind 零回归 | ✓ `mint-manifest` 68+9+8+3+7(新)=**95 passed**；`mint-pack` 34；`mint-cli` 3+17+…全绿；**新增失败 0** |

已发布的 4 个 iface 包（本机 hub）：`agentcpm/iface-env`（env）、`agentcpm/iface-types`（types，共享类型 694 行）、`agentcpm/iface-session`（session 925 行）、`agentcpm/iface-policy`（policy 527 行）。

## 4. 两个**既有**测试失败（与本次改动无关，已用 stash 证明）

| 测试 | 现象 | 证明 |
|---|---|---|
| `mint-manifest --test packages::official_and_demo_packages_validate` | `packages/overlay-zh-formal` 缺 `dist/index.js`（dist 是构建产物，clean clone 里本来就没有） | `git stash` 掉我全部改动后**同样失败** |
| `mint-hub --test site::site_host_serves_static_site_and_registry_host_serves_hub` | 静态站点 host 分流 | 开工前 baseline 即失败 |

## 5. 仍未做 / 下一步

1. **`Requires.interfaces`**（消费方声明"我要 iface-env ≥0.1"）未做——目前 iface 包之间没有依赖语义。
2. **`mint search` 表格列**未加 `interfaces`（只有 `info` 有）；如需搜索侧一眼看到 `[iface: env]`，要动 `hub/server` 的 search 响应 + CLI 表格（本时间盒内未做）。
3. 其余 5 个 iface（extension/tool/loop/context/model/store）未发；步骤同 §3 的 `mk()` 脚本（`kind=iface` + `interfaces=[名字]` + 复制 src + publish）。
4. **线上 hub 未发**（仍需管理员令牌 + 发布策略）；**签名仍未被消费侧校验**（publish 有 minisign，`add` 不验）。
5. mint 改动**未 commit**（按约束留给 Lead）。

---

# 追加（2026-10-26 深夜 · task-66）：10 个 iface 包**齐套**

用户要求「先把包都补齐」。9 个 iface 契约 + 共享 `types` = **10 个包，形状完全一致**。

## 1. 10 包清单（`repos/agent-kernel/packages/`）

| 包 | interface 名 | src 文件数 | src 行数 | 包体量 | 对应 kernel 源 |
|---|---|---:|---:|---:|---|
| `iface-types` | `types` | 2 | 694 | 52K | `kernel/iface/src/types/`（共享类型，被其余 9 个引用） |
| `iface-session` | `session` | 9 | 925 | 80K | `kernel/iface/src/session/` |
| `iface-policy` | `policy` | 4 | 527 | 56K | `kernel/iface/src/policy/`（含 egress/delegation/review） |
| `iface-env` | `env` | 6 | 523 | 60K | `kernel/iface/src/env/` |
| `iface-extension` | `extension` | 1 | 38 | 24K | `kernel/iface/src/extension.rs` |
| `iface-tool` | `tool` | 1 | 35 | 24K | `kernel/iface/src/tool.rs` |
| `iface-loop` | `loop` | 1 | 33 | 24K | `kernel/iface/src/loop_.rs`（Rust 关键字 `loop` → `r#loop`，包内保留 `src/loop_.rs` verbatim 同源，README 已说明映射） |
| `iface-context` | `context` | 1 | 27 | 24K | `kernel/iface/src/context.rs` |
| `iface-model` | `model` | 1 | 27 | 24K | `kernel/iface/src/model.rs` |
| `iface-store` | `store` | 1 | 24 | 24K | `kernel/iface/src/store.rs` |
| **合计** | — | **27** | **2853** | **~390K** | — |

**体量结论：没有任何包超过 1MB**（最大 `iface-session` 80K，最小 24K）；打包产物（`mint pack`）4–16KB。

## 2. 统一包形状（10 个 × 5 项，逐一核过）

```
iface-<x>/
├── mint.toml      # kind="iface" / provides.interfaces=["<x>"] / requires.api=">=0.1"
├── README.md      # 契约摘要 + 为何是 iface + 与 kernel/iface 的对应关系（+ loop 的文件名映射说明）
├── schema.json    # 机器可读：types / traits(方法) / 错误码 / 消费方 / source(files,lines)
├── .gitignore     # dist/（mint publish/pack 产物）
└── src/           # 从 kernel/iface/src verbatim 复制（sha 同源）
```

`schema.json` 统一 11 个顶层键：`$schema / title / version / description / lineage / spec / iface / types / traits / consumers / source`。
（`iface-env` 另有 task-62 遗留的 `SKILL.md`：那是 `kind="skill"` 变通时期的文档，已在 `eaf87c2` 提交。
D72 后它不再必需，但删除会动到已提交内容、且它本身是无害的契约说明，**故保留**（10 包的 5 项标准形状仍一致，env 多一个额外文档）。）

## 3. 本地验收（全部实测，hub 仅本地）

| 验收项 | 结果 |
|---|---|
| 起本机 hub | ✓ `127.0.0.1:8788`（`mint-hub` standalone，SQLite+blob） |
| **publish 10 包** | **10/10 成功**，seq 6–15，**合计 0.934 s** |
| `mint search iface` | **共 10 个（10 显示）**，类型列全部 `iface`；`/-/v1/search` API：`total=10, kind=iface=10` |
| 空工程 `mint add`（≥3） | ✓ `iface-env` + `iface-types` + `iface-session` 全装成功，**合计 0.688 s**；`mint list` 三行均 `类型=iface / T1 / registry+http://127.0.0.1:8788/index/` |
| `mint pack` 逐包 | **10/10 OK**（说明：`pack` 没有 `--dry-run` 标志——那是 `publish` 的；用 `mint pack --out <tmp>` 实跑等价验证，产物 4–16KB，包目录无残留） |
| hub 已停 | ✓ `local-hub-up.sh stop` 后 **8788/8787 端口无监听、无 mint-hub 进程**（用户明确要求） |
| 产物清理 | ✓ 所有 `packages/iface-*/dist/` 与临时工程目录已删 |

## 4. 线上待发（等用户给令牌）

- 10 个包已 `kind=iface` 且本地 publish/search/add/pack 全绿，**只差发布到线上 MintHub**（`https://mint-hub.ea.modelbest.co`）。
- 需要：**API 令牌** + 确认线上对 `agentcpm/` scope 的发布策略（线上此前只有验收包）。
- 发布命令（令牌到位后）：
  ```bash
  export MINT_HUB_URL=https://mint-hub.ea.modelbest.co
  mint login --registry "$MINT_HUB_URL" --token-stdin    # 令牌从 stdin
  for d in repos/agent-kernel/packages/iface-*; do (cd "$d" && mint publish -y); done
  mint search iface     # 应显示 10 个 iface
  ```
- 仍未做：**签名未被消费侧校验**（publish 产 minisign，`mint add`/`agentcpm` 都不验）——发线上前值得先定这条策略。
