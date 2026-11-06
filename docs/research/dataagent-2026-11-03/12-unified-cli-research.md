---
version: v0.3
date: 2026-11-05
decision: 依赖环境采用方案 A，保留 MCP（§5.2）；MCP schema 压缩不在本方案范围，后续单列
subject: Mint 内 Agent 自装 DataAgent 并经 `dataagent` CLI 调用能力
kernel: agent-kernel@698ac1b（fetch 后 fast-forward；`sync-iface-packages.sh --check` 报 diff=11，本文只涉及 Mint 运行时，不引用 `packages/iface-*`）
mint: 0.1.26（源码 `mint/bins/mint/Cargo.toml:4` 与本机一致）
changes: 目标由“外层包装 mint run 的命令行”改为“Mint 内 Agent 使用的 CLI 通道与自装流程”
---

# Mint 内 Agent 的 DataAgent CLI 调研

## 1. 结论

| 问题 | 结论 |
|-|-|
| 目标 | Mint 里的 Agent ① 用 `mint add` 安装 DataAgent 及相关包；② 经 `shell_exec` 调用 `dataagent <层> <op>` 使用能力 |
| 是否有必要 | 有必要。CLI 可经 `allow_prefixes` 免审批调用（MCP 工具在 `--approve auto` 下多数被拒）、提供 FileRef 与句柄等便捷参数、自装后无需重启即可调用。Mint 每一步请求携带全部工具完整 schema（DataAgent 51 个工具实测约 254 KB）；保留 MCP 时这部分开销仍在（§5.2） |
| 当前 Mint 下能否走通 | 能，有前提：Mint 不把包的 `bin/` 加入 PATH，只能以路径调用；默认 Seatbelt 沙箱不允许执行 `uv`、读 `~/.cache/uv`、读 Homebrew 下的 Python，需要用户层配置放开 |
| Agent 自装 | 技术上可行，但需要 `~/.mint` 可写，Agent 因此能改用户配置、凭据与信任台账，属于自我提权；默认不应开放。装完后新 MCP 须重启会话，新 CLI 文件落盘即可调用 |
| 来源 | `dataagent/*` 在 Mint Hub 全部 404，只能 `mint add path:<绝对路径>` |
| 推荐 | 新增 `dataagent/cli` bundle：`bin/dataagent` 按层分发到兄弟包的 `.venv`；附 `dataagent-cli` Skill；preset 依赖它；安装由用户执行或经人工审批；向 Mint 提包 bin 入 PATH、Skill 包路径变量、Agent 安装意图、MCP 延迟加载等诉求 |
| 已定 | 保留 MCP（§5.2 方案 A），两条通道并存；MCP schema 压缩后续单列，不在本方案范围 |

## 2. 目标流程

| 步骤 | 主体 | 动作 | 当前 Mint 下的条件 |
|-|-|-|-|
| 1 | Agent | `mint add path:/abs/…/dataagent-s0 -y` | mint 二进制所在目录可读；`~/.mint`、`$TMPDIR` 可写；`network=true`；`mint add` 经审批或在用户层 `allow_prefixes` |
| 2 | Mint | 写 `mint.toml`、`mint.lock`、`.mint/packages/dataagent/*@<ver>/` | 项目内可写 |
| 3 | Agent | `fs_read` 新装的 `SKILL.md` 学习用法 | 文件落盘即可读；Skill 列表需 `_mint/package/reload` 或重启才出现在系统提示词 |
| 4 | Agent | `.mint/packages/dataagent/cli@<ver>/bin/dataagent link` 在项目根生成 `./dataagent` | 工作区可写 |
| 5 | Agent | `./dataagent data run parse_delimited_file --file orders.csv` | 包内 `.venv` 已存在，基础解释器目录在 `readable_roots`；命令命中 `allow_prefixes` 时免审批 |
| 6 | Agent | 读取输出摘要；需要全文时 `fs_read .dataagent/results/<id>.json` | 输出前 32 KiB 进入上下文 |

## 3. Mint 机制

路径相对 `packages/agent-kernel/mint/`。

### 3.1 shell_exec

| 项 | 事实 | 证据 |
|-|-|-|
| cwd | 项目根；`cwd` 参数取相对子目录 | `crates/mint-core/src/tools/builtin.rs:648-653` |
| 环境变量 | 不清空，继承 cpmrt 全部环境（含 `MINT_MODEL_API_KEY` 等）；`mint run` 只在 PATH 前加 mint 自身 bin；不注入包 `bin/`，无 `$PKG` | `crates/mint-core/src/sandbox/mod.rs:104-111`；`bins/mint/src/cmd/run.rs:896-905` |
| 超时 | 同步 `min(timeout_s≤600, tool_timeout_ms=60000)`，默认实际 60 s；`background:true` 不限时，用 `shell_task` 取结果 | `builtin.rs:663`、`:707`；`config.rs:46` |
| 输出 | 每路后端上限 1 MiB；拼成 exit code + stdout + stderr，保留前 32 KiB；非 0 退出记 `is_error` | `sandbox/mod.rs:44`、`:130-160`；`builtin.rs:21`、`:721-750` |
| 沙箱读写（macOS） | 先全拒；可读 `/System`、`/usr/{bin,lib,sbin,share}`、`/bin`、`/sbin`、工作区、`readable_roots`；可写工作区与 `writable_roots`；`deny_paths` 默认 `.env*`、`*.pem`、`*.key`。`$HOME`、`~/.cache`、`/opt/homebrew`、`/usr/local`、`$TMPDIR` 不可读写 | `sandbox/macos.rs:113-190`；`tools/paths.rs:119-153`；`config.rs:178-189` |
| 沙箱实测 | `/opt/homebrew/bin/uv` 126；`/usr/bin/python3` 失败；`~/.cache/uv` 拒；mint 二进制 126；uv 任一命令需写 `~/.cache/uv` | 按 `scoped_profile` 复刻的 profile 实测 |
| 网络 | 缺省 `WorkspaceWrite{network:false}`；只有用户层 `[core.sandbox] network = true` 能打开，项目层只能收紧；再过出网门（`MINT_EGRESS_AMBIENT`） | `mint-protocol/src/session.rs:263-269`；`mint-core/src/config/runtime.rs:62-106`；`egress.rs:418-454` |
| roots 写法 | 已存在的绝对路径，不能含 `~`、`$` | `config/runtime.rs:118-131` |

### 3.2 审批与规则

| 项 | 事实 | 证据 |
|-|-|-|
| 配置层 | 只有用户 `~/.mint/config.toml` 与项目 `mint.toml`；包不能声明 rules | `config.rs:452-466`、`:562-614` |
| `allow_prefixes` | 用户层设定，项目层取交集；须从命令开头按 token 命中，且命令中不得含 `; && \|\| \| & $( \` > <` 换行 | `approval.rs:59-123` |
| `deny_prefixes` / `deny_paths` | 只增不减；任意位置 token 窗口命中即拒 | `approval.rs:124-156` |
| `allow_programs` | 第一个 token 字符串全等，不取 basename | `hooks.rs:206-222`、`:336-352` |
| `--approve auto` | 未命中 `allow_prefixes` 的命令一律拒绝 | `bins/mint-core/src/lib.rs:501-520` |
| 包 `capabilities.exec` | 只用于拉起包内 `.mcp.json` 时校验程序名，与 shell_exec 无关 | `mcp_loader.rs:338-350` |

### 3.3 包、Skill 与工具

| 项 | 事实 | 证据 |
|-|-|-|
| 安装布局 | `<项目>/.mint/packages/<scope>/<name>@<version>/`，目录名含版本号 | `mint-protocol/src/dirs.rs:112-117` |
| 包内 `bin/` | 可放可执行文件，`[artifacts] bin` 校验存在且可执行；不进 PATH | `mint-manifest/src/layout.rs:447-470`；`bins/mint/src/cmd/unit_cmd.rs:195-226` |
| 变量替换 | 只有包内 `.mcp.json` 的 `command`/`args` 把 `$PKG` 换成包目录；SKILL.md 原文注入，无包路径变量；系统提示词只给工作区根 | `mcp_loader.rs:444-492`；`loader.rs:525-531`；`engine.rs:1812-1830` |
| Skill 加载 | 系统提示词每个 Skill 一行 `name: description`；正文经 `skill_read` 按需读取，上限 32 KiB；frontmatter `allowed_tools` 被读入但未执行 | `loader.rs:252-266`；`builtin.rs:756-806` |
| MCP 工具 | 每一步请求携带全部工具完整 schema（`req.tools = specs`），系统提示词再列一行；无延迟加载、无工具搜索；结果无专门截断，压缩时折叠超过 8K token 的结果 | `turn_services.rs:406-407`、`:464-467`；`prompt.rs:181-191`；`context_budget.rs:39-43` |
| MCP 审批分类 | 按工具名猜 kind（search/list/get、read/fetch、run/exec、其它），忽略服务端 `readOnlyHint`；Other / Execute 在 auto 下被拒 | `mcp/client.rs:702-733` |
| MCP 进程 | 无 OS 沙箱；bundle 来源服务清空环境，只留基础变量与 `capabilities.env` | `mcp/client.rs:200-235` |
| 内置工具 | `fs_*`、`shell_exec`、`shell_task`、`skill_read`、`web_fetch`、`todo`；无安装包工具 | `builtin.rs:96-133` |
| 热加载 | MCP 只在 `Agent::from_config` 装载；新包 MCP 须重启会话；Skill 需 ACP `_mint/package/reload`（Agent 无对应工具）；`mint add` 只提示“在跑的会话不会热加载” | `engine.rs:528-540`、`:1448-1476`；`acp.rs:1132-1147`；`bins/mint/src/cmd/add.rs:33-42` |
| 审计 | 两条通道都写 `SessionEvent::ToolCall` 到 `.mint/sessions/`；MCP 工具名为 `<server>__<tool>`，shell 只有命令字符串；出网审计 `.mint/audit/egress.tsv`；工作区可写，shell 可改审计文件 | `mint-protocol/src/session.rs:381-395`；`egress.rs:56-75` |
| 成品 CLI 协议 | `agent-package-cli/1` 只在 `mint dist` 产物中生成启动器，`mint add` 项目中不存在 | `mint-protocol/src/product_cli.rs:1-58`；`docs/contract/2026-10-29-product-cli-gap-reply.md` |

### 3.4 shell 中运行 `mint add`

| 项 | 事实 | 证据 |
|-|-|-|
| 写入 | 项目内 `mint.toml` / `mint.lock` / `.mint/` 可写；`~/.mint/{config.toml,trust.toml,cache,index}`、mint 二进制、`$TMPDIR` 默认不可读写 | `bins/mint/src/install.rs:570-616`、`:723-748`；`mint-protocol/src/dirs.rs:10-64` |
| 网络 | 拉 Hub 需用户层 `network=true`；path 包内的 registry 依赖仍需解析 | `cmd/add.rs:150-185` |
| 非交互 | stdin 为 null；未信任且无 `-y` 报 untrusted；带 `-y` 写 `trust.toml` 自我信任；声明 capabilities 而无 `-y` 退出 6 | `bins/mint/src/config.rs:628-668`；`verify.rs:336-411`；`cmd/add.rs:107-149` |
| 自修改保护 | 无：`mint.toml`、`.mint/` 不在 `deny_paths`，无检测；挡住 `~/.mint` 的只有 Seatbelt | `config.rs:178-189` |
| path 来源 | `--source-root` 只在 dry-run / plan-digest 模式可用，正式 apply 不对 path 来源做根约束；源目录须在沙箱内可读 | `cmd/add.rs:85-90`；`install/source_policy.rs:20-40` |
| Hub | `dataagent--{data-layer,application-layer,governance-layer,preset-s0}` 404；同规则下 `mint--core` 200 | 实测 `https://mint-hub.ea.modelbest.co/index/…` |

## 4. 通道对比

| 维度 | MCP（`dataagent-*__<op>`） | shell + `dataagent` CLI |
|-|-|-|
| 每步上下文 | 51 个工具完整 schema，实测 254,682 字节（数据层 188,575 / 应用层 35,505 / 治理层 30,602），另加 51 行工具列表 | 1 个 `shell_exec` schema + Skill 描述行；用法按需 `skill_read` |
| 审批 | 按工具名猜类别，忽略 `readOnlyHint`；auto 下多数被拒，无按工具放行规则 | 用户层 `allow_prefixes` 可让固定前缀、无操作符命令免审批 |
| 进程隔离 | 无 OS 沙箱；环境清空 | Seatbelt；环境原样继承（含凭据变量） |
| 输入 | JSON 参数，结构化 | argv；不能用管道或重定向（失去免审批） |
| 输出 | 无专门上限 | 前 32 KiB；须控制输出体积 |
| 审计 | 工具名带服务前缀 | 命令字符串，需从路径解析 |
| 安装后生效 | 重启会话 | 文件落盘即可 |
| 依赖 | Mint 拉起 `uv run`（沙箱外），首次建 `.venv` | 复用包内 `.venv`；无 `.venv` 时需 uv，受沙箱限制 |

DataAgent 数据层 MCP 输入 schema 大，因为每个工具内联完整的 `$defs`（FileRef、TableRef、CallContext 等）。

## 5. 设计

### 5.1 包

| 包 | 内容 |
|-|-|
| `dataagent/cli`（新增，`kind=bundle`） | `bin/dataagent`：POSIX sh 或仅用标准库的 Python 分发器；`skills/dataagent-cli/SKILL.md`；`[artifacts] bin = "dataagent"`；无 Python 依赖、无 `.mcp.json` |
| `dataagent/{data,application,governance}-layer` | 保持现有 bundle；各层 CLI 增加 §5.3 的参数与输出约定 |
| `dataagent/preset-s0` | 增加对 `dataagent/cli` 的依赖 |

分发规则：`dataagent <layer> …` → 定位 `<项目>/.mint/packages/dataagent/<layer>-layer@<ver>/`（唯一已装版本；Mint 在改锁的命令后删除与锁不一致的版本，`mint/bins/mint/src/install.rs:970-980`）→ exec `<包>/.venv/bin/python -m dataagent_<layer>.interfaces.cli …`。不在一个进程内加载三层：治理层锁 `duckdb<2`、`sqlglot<27`，应用层 bundle 锁 duckdb 2.0.0、sqlglot 30.29。

### 5.2 依赖环境

定案：方案 A（2026-11-05）。MCP 与 CLI 两条通道并存。

| 方案 | 做法 | 代价 |
|-|-|-|
| A 保留 MCP（采用） | 三层 bundle 保留 `.mcp.json`；会话启动时 Mint 在沙箱外 `uv run`，建好 `.venv`；CLI 复用 | 仍承担每步 254 KB schema |
| B 关闭层 MCP | 层 bundle 不声明 MCP，或项目层禁用；`dataagent setup` 执行 `uv sync --frozen` 建 `.venv` | `setup` 需 uv 可执行、`~/.cache/uv` 可写、联网：由用户在沙箱外执行一次，或用户层放开对应 roots |
| C 自带解释器与 wheel | bundle 内置离线 wheel 与 Python | 包体积大；跨平台制品 |

采用方案 A 后各通道的作用：

| 通道 | 作用 |
|-|-|
| MCP | 结构化调用；会话启动时建立 `.venv`；Mint 之外的宿主（Claude Code、内核 / CSP） |
| CLI | 免审批的固定前缀调用；FileRef 与句柄等便捷参数；自装后不重启即可调用；人工调试与 CI |

CLI 不减少 Mint 内的上下文开销。MCP schema 压缩后续单列，不在本方案范围；测算如下（紧凑 JSON 计）：

| 层 | 工具数 | 现状（字节） | 去除 `title` 与 `extensions` 后 | 降幅 |
|-|-|-|-|-|
| 数据层 | 32 | 171,318 | 111,460 | 35% |
| 应用层 | 13 | 31,259 | 23,592 | 25% |
| 治理层 | 6 | 27,743 | 18,871 | 32% |
| 合计 | 51 | 230,320 | 153,923 | 33% |

数据层 `$defs` 合计 145,777 字节，去重后只有 26,218 字节（41 个定义）：MCP 每个工具的 inputSchema 独立，不能跨工具共享定义，重复来自各工具内联同一批类型。进一步压缩方向：CallContext 只经 `_meta` 传入、不进 inputSchema；深层引用类型（FileRef、TableRef 等）在 MCP 侧声明为不透明对象并附一行说明，完整结构由 `dataagent <layer> <op> --help` 提供。

### 5.3 命令

| 命令 | 作用 |
|-|-|
| `dataagent link` | 在项目根生成 `./dataagent`，路径稳定，供 `allow_prefixes` 与 Skill 引用 |
| `dataagent setup` / `doctor` | 建 `.venv`；检查三层包、`.venv`、策略、data_root、执行模式 |
| `dataagent <layer> list` | 每个 op 一行：名称、能力编号、是否复检、是否两段式 |
| `dataagent <layer> <op> --help` | 参数表（由 inputSchema 生成，扁平展示，不输出 `$defs`） |
| `dataagent <layer> run <op> [参数]` | 调用原子 |
| `dataagent gov confirm <file>` | 判据确认 |
| `dataagent policy apply <file>` | 写入访问策略 |

`<layer>` 为 `data` / `app` / `gov`；`<op>` 与 MCP tool 名相同。

参数（全部经 argv，不依赖 stdin）：

| 参数 | 含义 |
|-|-|
| `--input-file <path>` | 完整输入对象 |
| `--set k=v` / `--set-json k=<json>` | 单字段覆盖，按 inputSchema 转换类型；优先于 `--input-file` |
| `--file <path>` | 由文件字节生成 FileRef 填入本原子的文件入参 |
| `--ref <field>=<id@revision>` | 以短句柄引用此前结果（表、文档、规则），由 CLI 从 data_root 解析为完整对象 |
| `--authorize` | 先取 AccessDecision 填入 `authorization_ref` |
| `--proposal-file <path>` | 两段式第二阶段提案 |

输出：

| 项 | 规则 |
|-|-|
| stdout | 摘要 JSON：`status`、`issues`、关键输出字段、新产生对象的句柄（`id@revision`）、`result_path`；控制在 32 KiB 内 |
| 全文 | 写入 `.dataagent/results/<invocation_id>.json`；`--detail full` 时直接输出 |
| 两段式 | `needs_input` 时输出 `inference_request` 与建议的下一条命令 |
| 退出码 | 0 = ok / partial / needs_input；1 = failed；2 = 用法或 schema 错误；3 = 环境缺失（包、`.venv`、策略） |

### 5.4 身份与安全

| 问题 | 事实 | 设计 |
|-|-|-|
| 主体与用途 | shell 环境继承 cpmrt 环境；工作区内文件 Agent 可改 | 主体与用途只取启动 `mint run` 时用户设置的 `DATAAGENT_HOST_SUBJECT_REF` / `DATAAGENT_HOST_PURPOSE`；不读工作区配置、不接受参数；用户层 `allow_prefixes` 只放行 `./dataagent`，带 `env` 前缀或操作符的命令须审批 |
| 访问控制边界 | Agent 可用 `cat`（缺省免审批前缀）直接读工作区文件 | shell 场景下 Mint 沙箱是数据边界，DA12.1 是策略记录与审计；需要 DA12.1 作为边界时，把源数据放在工作区外、经 `readable_roots` 只给 dataagent 访问不可行（沙箱按进程不按程序），须由宿主或 MCP 通道承担 |
| 凭据 | shell 子进程可见 `MINT_MODEL_API_KEY` 等 | CLI 启动时清除与 DataAgent 无关的环境变量后再 exec 层进程 |
| 模型可见输出 | CLI 输出直接进入模型上下文 | 外发检查（W0 §5）在 CLI 输出前执行，与 MCP 通道一致 |
| 自装提权 | `mint add` 需 `~/.mint` 可写 | 默认由用户执行安装；Agent 自装只在人工审批（`--approve` 非 auto）下进行，且用户层不永久放开 `~/.mint` 写权限 |

### 5.5 用户层配置样例

```toml
# ~/.mint/config.toml
[core.sandbox]
policy = "workspace-write"
network = false
readable_roots = ["/opt/homebrew"]   # .venv 指向的基础解释器所在目录；用 uv 管理的 Python 时改为其绝对路径

[rules]
allow_prefixes = ["ls", "cat", "git status", "./dataagent"]
```

启动：`DATAAGENT_HOST_SUBJECT_REF=user:alice DATAAGENT_HOST_PURPOSE=monthly_report mint run`。

## 6. 外部参照

| 结论 | 来源 |
|-|-|
| 有 CLI 时优先 CLI，避免逐工具清单开销（该宿主已对 MCP 默认延迟加载） | [Claude Code costs](https://code.claude.com/docs/en/costs) |
| 代码执行 / 按需披露替代全量工具定义：150,000 → 2,000 token 案例 | [Code execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp) |
| Tool Search：77K → 8.7K token | [Advanced tool use](https://anthropic.com/engineering/advanced-tool-use) |
| 实测对比结论不一：一组 CLI 显著省 token（作者销售 MCP 网关），一组两者成功率相同 | [Scalekit](https://www.scalekit.com/blog/mcp-vs-cli-use)、[Zechner](https://mariozechner.at/posts/2025-08-15-mcp-vs-cli/) |
| MCP 适合鉴权、审计、非 shell 客户端；CLI 继承宿主权限 | [Firecrawl](https://www.firecrawl.dev/blog/mcp-vs-cli)、[MCP tools spec](https://modelcontextprotocol.io/specification/2025-06-18/server/tools) |
| 同一包提供 CLI + MCP + Skill | [Wren CLI](https://docs.getwren.ai/oss/reference/cli)、[Databricks aitools](https://docs.databricks.com/aws/en/dev-tools/cli/reference/aitools-commands) |
| 从 tool schema 生成 CLI 与 SKILL.md | [FastMCP generate-cli](https://gofastmcp.com/cli/generate-cli) |
| 工具按工作流设计、命名空间、concise / detailed 返回 | [Writing tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents) |
| 子命令发现与冲突报告 | [kubectl plugins](https://kubernetes.io/docs/tasks/extend-kubectl/kubectl-plugins/)、[cargo external tools](https://doc.rust-lang.org/cargo/reference/external-tools.html) |
| stdout 只放结果、日志写 stderr、非零码映射失败类型 | [clig.dev](https://clig.dev/)、[dbt exit codes](https://docs.getdbt.com/reference/exit-codes) |

## 7. 向 Mint 的诉求

| 编号 | 诉求 | 作用 |
|-|-|-|
| M1 | 已装包的 `[artifacts] bin` 加入 shell_exec 的 PATH | 裸调 `dataagent`，不需 `link` |
| M2 | SKILL.md 与系统提示词提供包根路径变量 | Skill 不写死含版本号的路径 |
| M3 | 包在 `mint add` 时声明建议的 `allow_prefixes` 与 `readable_roots`，经用户确认后写入用户层 | 免手工配置 |
| M4 | 面向 Agent 的安装意图工具（经审批调用 `mint add`），替代 shell 中执行并放开 `~/.mint` | 消除自装提权 |
| M5 | Agent 可调用的包重载（对应 `_mint/package/reload`），并支持新包 MCP 热加载 | 自装后无需重启 |
| M6 | MCP 工具延迟加载或工具搜索；尊重 `readOnlyHint` | 降低 MCP 通道上下文开销与审批误判 |
| M7 | shell_exec 可选清空环境、按白名单透传 | 不向子进程泄露凭据 |
| M8 | 项目级“保留 Skill、禁用 MCP”的包配置 | §5.2 方案 B |

## 8. 待决

| 编号 | 问题 | 选项 |
|-|-|-|
| Q1 | 依赖环境方案 | 已定：A，保留 MCP（§5.2） |
| Q2 | Agent 自装的授权方式 | 用户执行；人工审批下 Agent 执行；等 M4 |
| Q3 | 是否发布到 Mint Hub | 发布后 `mint add dataagent/preset-s0`，去掉 path 依赖 |
| Q4 | MCP 通道是否保留 | 已定：两条通道并存 |
| Q6 | MCP schema 压缩 | 后续单列：只去 `title` 与 `extensions`（约 33%）；或同时把 CallContext 移出 inputSchema、深层引用类型改为不透明对象 |
| Q5 | 治理层与应用层依赖对齐 | 放开治理层 `duckdb<2`、`sqlglot<27`（08 r41 S5） |
