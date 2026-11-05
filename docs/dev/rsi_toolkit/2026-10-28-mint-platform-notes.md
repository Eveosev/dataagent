# Mint 平台笔记：事实、命令与差异

配套主方案：[`2026-10-28-iface-modularization-and-minthub.md`](2026-10-28-iface-modularization-and-minthub.md)

本页是**证据层**：Mint/MintHub 的真实行为、可复制的命令、以及文档与已发布 CLI 的差异。
采集时间 2026-10-28，环境 `mint 0.1.11`。凡标「实测」的都跑过，标「文档」的来自官网原文未在本机验证。

> **采集方式**：`mint.ea.modelbest.co` 是静态站（`#docs` 是页内 `<section>`，正文全在 HTML 里）；
> `mint-hub.ea.modelbest.co/docs` 是 React SPA，正文打进 `assets/DocsPage-*.js` 的模板字符串。
> 浏览器工具对这两个域名会因"解析到非公网 IP"而拒绝，但 `curl` 可达——**用 `curl`，不要用网页抓取工具**。

---

## 1. 四层分工

| 层 | 负责 | 对应命令 / 进程 |
| --- | --- | --- |
| **AgentOS**（对外名待定） | 顶层发行组合：运行时、界面、技能、配置打成一份可交付产品 | `mint install mint/agent-gui` |
| **cpmrt** | 运行时：会话、Agent loop、模型调用、工具执行与审批、插件监管、ACP | `mint start` 转发给它 |
| **AgentCPM kernel** | 机制契约层：`iface`、常驻宿主、loop 协议；**不依赖 mint** | 由 cpmrt 链接，不单独提供命令 |
| **Mint / MintHub** | 包管理与分发：解析、验签、安装、锁、发布、分发 | `mint` CLI / `mint-hub` |

官方理由：**"包管理器不该知道怎么跑 Agent"**。以前 `mint start` 把官方组件名写进启动路径，
组件一改名启动就坏（core 档改名 std 的故障就是这个根因）。现在"装归 Mint、跑归 cpmrt"。

**命名规则**：`cpmrt` 与 AgentCPM kernel 同源品牌（AgentCPM runtime）；`mint-core` 是更早的旧名，
只作历史兼容。**但制品还没改**——见 §8。

---

## 2. 包类型

官网列 10 种；已发布 CLI 的枚举 11 种（多一个 `agent`）。**没有 `iface`**。

| kind | 说明 | 状态 |
| --- | --- | --- |
| `core` | 运行时本体，按档位 × 平台分发，多版本并存于 `~/.mint/cores/` | 已发（`mint/core` 0.1.12） |
| `host` | std 档的独立 V8 进程 `mint-host`，承载 JS 插件 | 路线图 |
| `plugin` | `native` 独立进程 / `wasm` 组件 / `js` 插件 | 已发（`mint/gui`、`mint/tui`） |
| `overlay` | 叠在覆盖链上，**只能收紧不能放宽** | 路线图 |
| `bundle` | 识别 Claude Code / Codex 的 `plugin.json`；**0.1 只装载 `skills/`** | 已发 |
| `skill` | `SKILL.md` + 脚本与参考资料，注入提示词 | 已发 |
| `mcp` | `server.json` 子集或 `.mcp.json`；仓库只存声明，首次调用时拉起 | 路线图 |
| `preset` | 依赖清单 + 名字，`mint init --preset` / `mint add` 合并进项目 | 已发 |
| `app` | 按锁文件收齐的成品；**不等于 macOS `.app`** | 已发（`mint/agent-gui` 0.1.8） |
| `template` | `mint init --template` 展开目录骨架，**不执行代码** | 路线图 |
| `agent` | 仅 CLI 枚举有，官网未列 | 源工程用，不作发行 |

---

## 3. 契约包（iface）的官方用法

> "MintHub 上还有一组**契约包（iface）**……**只定义形状，不含实现，也不带运行时依赖**。"

```sh
mint pull agentcpm/iface-loop          # 只写本机单元库，不改项目 mint.toml
mint inspect agentcpm/iface-loop --abilities
```

三个可直接采纳的结论：

1. **消费用 `pull` 不用 `add`**——`pull` 不碰项目清单，符合"契约是参考资料"的定位。
2. **契约包不带运行时依赖**——不能在下游实现里写成 `[dependencies]` 硬依赖。
3. **发现靠 `inspect --abilities`**——但 0.1.11 没有这个选项（§8）。

---

## 4. 单元（unit）

- 每个已发布版本投影成**不可变单元**：`tag` / 精确版本 / `digest` 解析到同一份内容；**digest 永久稳定，tag 会移动**。
- 线上传输格式是 **OCI image manifest**（实测 `mediaType = application/vnd.oci.image.manifest.v1+json`）。
- **不是容器镜像**：本机没有容器运行时，不启动 rootfs。
- 命令：`mint pull` / `mint units`（原 `mint images`）/ `mint inspect` / `mint vendor`。
- **Mintfile**：Dockerfile 风格的声明式构建清单，描述一个 Agent 由哪些配方、内核档位、界面与包组成；
  产出制品写入本机单元库，可发布。

---

## 5. Loop 契约（`provides.loops`）

| 环节 | 机制 |
| --- | --- |
| 声明 | 单元声明 `provides.loops` / `provides.protocols` / `provides.interfaces`——**声明不等于启用**，只是权利声明 |
| 启用 | `mint loop use <id>` 写进项目 `[loop] selected`（可 review、可提交，不联网、不安装、不启动） |
| 拉起 | 运行时读 `[loop] selected`，拉起该单元 `bin/` 里的可执行文件 |
| 协议 | **stdio 行分隔 JSON-RPC**，形状按 `iface-loop` 契约（`describe`/`step`/`interrupt`/`status`）；**线上方法名**是 `initialize`（握手）与 `loop/next`（步进） |
| 应答 | 插件回 `{action:{type:"answer"|"stop"}}` |
| 失败回退 | 缺入口、拉起失败、握手超时、退出码非 0、协议非法 → 只 `warn` 并回退内置 turn loop，该轮照常；**用户主动取消不算失败、不回落** |
| 超时 | 默认 10 s，项目 `[loop] timeout_ms` 可调 |
| 总开关 | 用户级 `[loop] enabled = false` 整体关闭外部 loop，项目里的 `selected` 不能再打开 |

**与 rsi 的关系**：`rsi.host/v1` 是"一次同步执行、结果未知永不重放"；loop 是"逐步驱动、失败可回退"。
**语义相反**，不要把 `rsi-host` 实现成 loop 单元。

---

## 6. 发布流程

| 步骤 | 命令 / 要求 |
| --- | --- |
| 建令牌 | ea-auth 登录控制台「令牌」页，勾选 **`publish-new`** + **`publish-update`**；明文只显示一次；个人机与 CI 分别签发 |
| 登录 | `mint login`，令牌经**标准输入**（粘贴后回车、Ctrl+D 结束）；不进命令参数、不提交 |
| 本地检查 | `mint publish --dry-run` —— **只做本地检查，不上传，也不验证远端发布权限** |
| 上传 | `mint publish`；版本不可重复发布 |
| 命名 | `<你的用户名>/<包名>`；`mint/` 是官方命名空间；**已有包的新版本还需包 owner 权限**，令牌作用域不能替代包归属 |
| 传输 | 走 CLI + 个人令牌，**不用 SSH，不把浏览器会话当发布凭证** |

**错误码**：`401` 令牌过期/吊销/仓库不匹配；`403` 缺发布作用域/包归属/官方权限；`409` 版本已存在。
**不要用管理员令牌绕过包归属检查。**

---

## 7. 签名、锁、档位、私服

- `mint.lock` 记每个包的版本、来源、内容哈希、制品 `sha256`；**索引行与制品用 minisign 签名，
  `mint` 装前逐项校验，被改过的制品直接拒绝**（实测装前校验存在，不需要显式 `mint verify`）。
- 三档 `core` / `lite` / `std` **只差 JS 宿主**，同一份源码按 feature 构建；包声明支持的档位，
  `cpmrt` **按声明降级而不是报错**。现在发 `core`；`std` 在 V1；`lite`（进程内 QuickJS）在 V2。
- 私服：`mint-hub serve` 是**一个二进制**，起来就是本机仓库（SQLite + 本地盘）；企业私服用同一镜像。

---

## 8. 文档 vs 已发布 CLI 0.1.11

| 文档描述 | 实测 | 影响 |
| --- | --- | --- |
| `mint inspect <单元> --abilities` | ❌ 无此选项（只有 `--remote`） | 契约包的官方发现路径当前不可用 |
| `mint loop use/show` | ❌ `unrecognized subcommand 'loop'`（提示 `logout`） | loop 契约本期无法验证 |
| `mint install <包>` 装 unit | ⚠️ 有，但语义是"安装已发布组件 / 完整桌面 Agent" | 按实际 CLI 写文档 |
| `mint pull` / `mint units` / `inspect --remote` | ✅ | 契约包可用 `pull` |
| `mint publish --dry-run` | ✅ | 但不验远端权限 |
| `provides.interfaces` | ⚠️ `mint info` 有；`mint inspect --remote` **只给 OCI annotations** | 发现只能靠 `info` 或装后读 `manifest.json` |
| 运行时叫 `cpmrt` | ❌ `mint/core@0.1.12` 产物内是 `bin/mint-core`、`bin/mint-host`；`which cpmrt` 为空 | **文档改名、制品未改** |

`mint/cli` 的最新发布版本就是 0.1.11（`0.1.0`…`0.1.11`，`latest`/`stable` 都是它），
而 `mint/core` 已到 0.1.12——**文档先行，CLI 未跟上**。

---

## 9. 实测命令（可复制）

```bash
# 版本与单元
mint --version                       # mint 0.1.11
mint --json info mint/cli            # versions/tags，latest = 0.1.11
mint --offline --json info mint/core # kind=core, 0.1.12, 25.1 MB, std-aarch64-apple-darwin

# 契约包
mint --json info agentcpm/iface-tool
# {"kind":"bundle","provides":{"interfaces":["tool"],"skills":["iface-tool"]},
#  "api":">=0.1","sig":{"keyid":"b2bb91162bcfac7d"}}

mint --json inspect agentcpm/iface-loop --remote | jq 'keys'
# ["annotations","deps","digest","event","kind","mediaType","name","platforms",
#  "reference","size","v","version"]
# kind=bundle, mediaType=application/vnd.oci.image.manifest.v1+json, 无 provides

# 本地打包（kind="iface" 会被拒）
cd packages/kernel-iface/iface-tool && mint --offline pack .
# 错误：unknown variant `iface`, expected one of `core`, `host`, `plugin`,
#      `overlay`, `bundle`, `skill`, `mcp`, `preset`, `template`, `app`, `agent`

# 运行时产物内容
MINT_HOME=/tmp/_mh mint pull mint/core -y
tar --zstd -tf /tmp/_mh/units/blobs/sha256/*/[0-9a-f]* | head
# manifest.json  README.md  bin/mint-ax-helper  bin/mint-core  bin/mint-host  mint.toml
```

**隔离技巧**：`export MINT_HOME=/abs/scratch/_mint`，避免动 `~/.mint`（沙箱下直接写 `~/.mint` 会
`Operation not permitted`）。

---

## 10. 生态现状（2026-10-28）

`https://mint-hub.ea.modelbest.co/-/v1/search?text=<q>`，npm 风格，全仓 **77 个包**。

| 包 | kind | 版本 |
| --- | --- | --- |
| `mint/core` | core | 0.1.12 |
| `mint/cli` | core | 0.1.11 |
| `mint/agent-gui` | app | 0.1.8 |
| `mint/gui` / `mint/tui` | plugin | 0.1.8 / 0.1.4 |
| `mint/skill-code-review` | skill | 0.1.0 |
| `wujiahe/preset-staffdeck-agent` | preset | 0.4.1 |
| `wujiahe/employee-management-mcp` | mcp | — |
| `agentcpm/iface-*`（10 个） | bundle | 0.1.0 |

**未取证**（不要当已知）：`mint publish` 的真实上传（无令牌）、loop 的真实握手（CLI 无 `loop`）、
Mintfile 构建、`mint vendor` 离线形态、Windows / Linux 行为。
