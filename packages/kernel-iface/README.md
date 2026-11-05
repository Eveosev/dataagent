# AgentCPM iface 契约包（v0.1.0，内容同步至 kernel master `d950766`）

> ⚠ **已废弃（2026-11-02）**：本目录是 **0.1.0 冻结快照**，不再是 iface 契约的对比基线。
> 现行位置：权威源 `packages/agent-kernel/kernel/iface/src`，可读分发包 `packages/agent-kernel/packages/iface-*`（0.1.2）。
> 详见 [DEPRECATED.md](DEPRECATED.md)；对比流程见 AgentOS 根 `README.md`「iface 契约：位置与对比流程」。
> 下文保留 2026-10-29 当时的同步记录，仅作发布史证据。

> 位置：`AgentOS/packages/kernel-iface/`。2026-10-29 按 kernel master 重新同步：
> 每个包的 `src/` 与 `packages/agent-kernel/packages/iface-*` **逐字节相同**，
> 而后者由 kernel 的 `scripts/sync-iface-packages.sh --check` 保证与 `kernel/iface/src` 逐文件一致
> （10 包 / coverage total=44 mapped=44 allowlist=9 uncovered=0）。

## 这是什么

Kernel 的 **9 个 iface 契约** + 共享 `types`，共 **10 个 mint 包**。
规模：**22 个 `pub trait` / 44 个 `.rs` / 6292 行**。

每个包 = `mint.toml` + `README.md` + `schema.json`（类型/方法/错误码/消费方）+ `src/`（verbatim 自 `kernel/iface/src/`）
+ `skills/<包名>/SKILL.md`。

**关于 `kind`**：mint 没有 `iface` 这个 kind（见 `PACKAGING-NOTES.md` §1）。2026-10-27 起改用
`kind = "bundle"` 发布（`bundle` 的硬要求是 `skills/` 等形态字段之一，因此每包附一份 SKILL.md）；
契约身份仍由 `provides.interfaces` 声明。hub 上现存制品也是 `kind = "bundle"`。

| 包 | interface | src 模块 | 说明 |
|---|---|---|---|
| iface-types | types | `mod` `interrupt` `loop_payload` `model` `version` | 共享类型（SessionId/TurnId/Cursor/Error/BoxFuture…）+ 契约版本治理（`ContractMeta`/`ContractDescriptor`/`is_compatible`）；其余 9 个都依赖 |
| iface-session | session | `mod` `effect` `epoch` `handoff` `header` `identity` `lease` `node` `placement` `seq` `tenant` `view` | 会话创建/推进/恢复/归档 + 跨宿主交接（`HandoffKernel`）+ 推进权租约（`LeaseStore`）+ 读视图 |
| iface-store | store | `store` `event_io` | 事件存储 append/read/checkpoint/verify + 事件读写游标（`EventIo`） |
| iface-policy | policy | `mod` `audit` `delegation` `egress` `review` | 策略判决、出网/委派/撤销审计（`AuditSink`）、审核位（`ReviewVerdict`） |
| iface-extension | extension | `extension` | 扩展点契约（describe/on_assembly_intent/status/deactivate） |
| iface-tool | tool | `tool` | 工具注册/列表/执行 + 装配期暂存（`ToolStaging`） |
| iface-model | model | `model` `model_session` `model_stream` `capabilities` `config` `event` `input` `operations` `types` | 模型调用 + 流式（D93）+ 模型会话（D96，`client_message_id` 幂等） |
| iface-context | context | `context` `trace` | 上下文组装 + 留痕能力面（`TraceSink`） |
| iface-loop | loop | `loop_` | 执行边界与交接能力声明（进程内 Rust 实现；跨进程走 L-C） |
| iface-env | env | `mod` `environment` `exec_backend` `fs_backend` `id` `path_uri` | Environment / PathUri / FsBackend / ExecBackend（仍是 4 个 fs 方法，无 mkdir/原子替换） |

## 与线上制品的差异（重要）

hub 上的 `agentcpm/iface-*@0.1.0` 发布于 **2026-10-27T15:37Z**，内容对应本次同步**之前**的版本，
缺 D93（模型流式）与 D96（模型会话）两批契约。本目录已更新，**线上没有**。
在重新发布之前，不要把 hub 制品当作这里内容的等价物；发布后需要重新记录 digest。

## 怎么发到 Mint Hub
需要 hub 令牌（角色 `ea-mint:operator` 或 `ea-mint:admin`）：
```bash
export MINT_TOKEN='mint_...'
bash publish-iface-online.sh --check   # 自检（可达性 + 登录）
bash publish-iface-online.sh           # 发布 10 个包（幂等：已存在记 SKIP）
```

## 可替换性证据
见 `SUBSTITUTABILITY-SCORECARD.md`：8/8 原契约有生产 dyn 接缝 + "同一调用方跑两实现"的替换测试。
注意该记分板只覆盖 8 个原契约；2026-10-29 同步新增的 12 个 trait（handoff/lease/trace/audit/
model_session/model_stream/tool staging/version 等）不在其覆盖范围。

## 注意
- `iface-loop` 是**进程内 Rust** 契约；跨进程/跨语言 loop 走 L-C `loop/*`（D76：不做 wasm 化）。
- 发布门禁（规范 v9.9）：对外发布须声明"已被 ≥2 个实现验证"，目前 store/policy/extension/tool/model/context/env 满足；
  session 为 1 实现 + 测试替身；发布时可标注"内部预览"。
