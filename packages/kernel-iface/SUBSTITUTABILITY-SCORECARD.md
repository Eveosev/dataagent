# iface 可替换性 — 最终记分板（2026-10-27，HEAD `3da9d7c`）

> **2026-10-29 范围说明**：本目录已按 kernel master `d950766` 同步，契约面从 10 个 trait 增至 22 个。
> 本记分板仍只覆盖 **8 个原契约**；新增的 handoff / lease / trace / audit / model_session / model_stream /
> tool staging / version 等 trait 的替换性未在本表中评估。

> 用户问题（定调）：「**这个问题我觉得是 iface 设计的最基本的问题，不能影响其他基于 iface 的包实现**」
> 本文是**答案的实测版**：8 个 iface 契约是否真的"换实现不影响依赖方"。
> 判定标准（规范 v9.9 §可替换性契约 / D73）：
> **① 生产路径存在 `dyn` 接缝 ② 至少 2 个实现 ③ 有"同一调用方跑两实现"的可执行测试 ④ 装配点在组合根**（缺一不算）。

## 0. 结论

**8/8 契约已具备生产 `dyn` 接缝 + 替换测试**（`iface-loop` 例外，见 §4）。
全量 CI 绿：**A5 49/0/0**、iface 67 / core 96 / runtime 270 / host 196 测试全绿、
`clippy -D warnings` 0、`conventions` 0 fail、`error-codes --strict` 通过、`replaceability fail=0`。

## 1. 记分板（生产 dyn 接缝 / 实现数 / 替换测试）

| 契约 | 生产 dyn 接缝 | 生产实现 | 替换测试（同一调用方跑两实现） | 判定 |
|---|---|---|---|---|
| **StoreContract** | **13** | 3（CoreStore / InMemoryStore / ContractEventIo 桥） | `runtime/tests/store_substitution.rs`（file↔memory，含 D74 Pending 反例） | ✅ |
| **PolicyContract** | **4** | 1 + 测试替身（DenyAll/AllowAll） | `runtime/tests/policy_substitution.rs`（+ `check`/`check_sync` 同判决、Pending 反例） | ✅ |
| **ExtensionContract** | **7** | 2（BasicExtension / NoopExtension） | `runtime/tests/extension_seam.rs`（+ 启动期生产消费点） | ✅ |
| **ToolContract** | **3** | 3（BasicTools / WasmTool / ComponentTool） | `runtime/tests/wiring.rs`（model/tool 章节） | ✅ |
| **ModelContract** | **11** | 4（Scripted / Echo / OpenAi / ModelGateway） | `runtime/tests/model_seam.rs`（5 条含工厂 fail-closed） | ✅ |
| **SessionContract** | **2** | 1 + FakeSessions | `runtime/tests/session_substitution.rs`（4 条含 `Ok(None)` vs `-32085` 可区分） | ✅ |
| **ContextContract** | **2** | 2（BasicContext / NoopContext） | `runtime/tests/context_seam.rs`（2）+ **host 级 1 条**（生产路径真实调用） | ✅ |
| **iface-env**（Fs/Exec） | **2 + 2** | 1 + 1（LocalFs / LocalExec） | `exec-host` 5 条（改动前为零）+ `../` 逃逸被拒 | ✅ |
| ~~iface-loop~~ | 实验区 2 | **0 生产**（sidecar 适配器在 `.tmp/loop-adapter`） | `notes/kernel-loop-equivalence-report.md`：**5/5 零差异 + 负面控制精确命中** | ⚠️ §4 |

## 2. 每个接缝的"装配点唯一性"（D73 条件④）

全部落在组合根，`replaceability` 门禁持续守护：

| 接缝 | 组合根位置 |
|---|---|
| store | `transport/store_facade.rs`（`StoreBundle::file/memory`，唯一 `new(具体)` 处） |
| policy | `startup/policy_factory.rs` |
| extension | `startup/kernel.rs::Kernel::start`（`BasicExtension` 实例化） |
| model | `runtime::model::factory::from_choice`（runtime 内组合点） |
| session | `startup/session_factory.rs` |
| context | `startup/context_factory.rs` |
| env | `runtime::env::local_backends`（让 `exec-host` 二进制不 import 具体类型） |
| A2A 插件 | `startup/a2a.rs::build_a2a_service` |

## 3. 生产消费点（"接了缝"≠"有人用"，逐条给证据）

| 契约 | 生产消费点 |
|---|---|
| store | 宿主全部事件/会话/租约写入（M-c：`core_bridge` 缺口 13→0，`root()` 移除） |
| policy | `transport/policy.rs::policy_check` —— **28 个授权闸门唯一漏斗**，换接缝时 28 处调用点**一行未改**；`guard.authorize` 在宿主 **1→0** |
| extension | `startup/kernel.rs::declared_contract()` → `describe()` → `validate_contract()` **启动期 fail-closed 判决** |
| model | `gateway/state.rs::register_contract` → `gateway/backend.rs::ContractBackend`（`complete()` 生产路径） |
| session | `transport/session_projection.rs`（`known_session`/`session_facts` 兜底）+ `session.rs::session_list` |
| context | `transport/session_v2.rs::347`：`session.get{view:"spec"}` 的 `capabilities[]` + `capabilities_from` |
| env | `host/src/bin/exec-host.rs`：4 个 L-C 作业（fs.read/write/list、exec.run）全部走契约 |

## 4. `iface-loop` 的诚实说明（口径已定，见 D75/D76 + 规范 §6.8）

- **D75：保留**（§1.4「核外 loop 经接口契约和适配层接入」+ §6.8「iface-loop 承载执行边界与交接能力声明」）；
  审计曾以"全仓引用 0"判其"误设"，**该结论已作废**（同一判据会把 9 个契约里的 7 个一起判死）。
- **D76：分层**——跨进程 loop（Node/Python/sidecar）一律走 **L-C `loop/*`**；`iface-loop` 只面向**进程内 Rust 实现**；
  **不做 wasm 化**（制品体积/执行模型/工具链三条理由）。
- **实测（`.tmp/loop-adapter` + `notes/kernel-loop-equivalence-report.md`）**：Rust sidecar 适配器 **11 单测**；
  **经 `LoopContract` 驱动 vs 原生 `drive_turn` 的 canonical trace 5/5 零差异**；
  **负面控制（漏发 `tool.result`）2/5 + 精确命中缺失字段** ⇒ 比较器不是永远绿。
- **仍未做**：生产 `impl LoopContract`（适配器在实验区）、多轮工具编排在 `rust-core`（未接）、真实 provider。

## 5. 过程中修掉的真实问题（不是"设计完就好了"）

| # | 问题 | 处理 |
|---|---|---|
| 1 | **契约面远小于宿主真实能力面**（store 3 vs 12 方法） | 契约补齐到 10；数据模型唯一化（`Record↔EventRecord` 唯一转换 + 往返测试） |
| 2 | **宿主对 8 个契约引用为 0** | 本轮逐条接缝（本文 §1） |
| 3 | **`session.deliver` 的 epoch 围栏从不执行**（跨 node 实测发现） | 修 `dispatch.rs` hook（`target_session`），加 A5 H-40 |
| 4 | **`LeaseGate` 每进程一次性缓存 → 换手要重启** | 增量重放 + 文件锁（std `File::try_lock`，零新依赖）；e2e **②e 由 FAIL→PASS** |
| 5 | **exec-host 有一份更弱的重复实现**（无 canonicalize/无输出上限/无超时） | 改走 `Arc<dyn FsBackend/ExecBackend>`，删掉 78 行 ad-hoc |
| 6 | **fire-and-forget 丢弃契约 future**（`let _ = store.create_session(...)`） | M-c 已结构性修复；本轮**显式化**调用 + 2 条回归测试钉住 |
| 7 | **`StepSemantics` 表达不了真实粒度**（适配器实测"一次 host 往返"） | 新增 `HostRoundtrip` + "声明粒度可更细"规则 |

## 6. 门禁（防退化，全部在 CI）

| 门禁 | 守护什么 | 曾抓到 |
|---|---|---|
| `error-codes --strict` | 错误码禁止段/登记/唯一 | env 的 8 个越界码 |
| `conventions`（**含 tests/**，263+ 文件） | 行数/lib.rs/文档头/禁名 | 829 行测试文件 |
| `check-replaceability.sh` | 具体类型直连 / 契约成熟度 / 装配点唯一性 | **2 次装配点泄漏**（store_facade 首版、policy 首版） |
| A5（49 例） | 端到端行为 | — |

**门禁转 `--strict` 的条件**：`allowlist` 清零（当前 3 条）+ 连续 2 次 CI 绿。3 条豁免均为 `model/lease` 具体类型的下一批债务。

## 7. 剩余（诚实）

| # | 未做 | 影响 |
|---|---|---|
| 1 | `ModelContract` 的 host 启动链未接（工厂在 runtime，`ModelSettings→ModelChoice` 映射未做） | 契约已可替换，但宿主仍走既有 model 选择路径 |
| 2 | `BasicContext` 仍依赖具体 `KernelStore`；宿主生产接缝暂为 `NoopContext`（能力清单为空） | context 接缝"通了但空"——建议 follow-up：改 `BasicContext::new(Arc<dyn StoreContract>, Arc<dyn ToolContract>, TraceSink)` |
| 3 | `iface-loop` 无生产实现（适配器在实验区） | 见 §4 |
| 4 | `ContractBackend` executor 为阻塞式（poll+sleep） | 接真异步实现（流式/远程）时需专用线程驱动，note 已记录 |
| 5 | 3 条 `replaceability` allowlist（model/lease 具体类型） | 下一批清理后门禁可转 strict |
| 6 | `trace_input` 与 `record_trace_input` 口径重叠 | 统一后避免重复写事件 |

## 8. 一句话总结

> **可替换性从"设计声称"变成了"实测成立"**：8/8 契约有生产 `dyn` 接缝，每个都有"同一调用方跑两实现"的测试，
> 装配点唯一且有 CI 门禁守护；过程中发现并修掉了 7 个真实问题（契约面不足、围栏失效、缓存不一致、重复实现、丢 future…）。
> 剩下的不是"能不能换"，而是"换上去之后由谁消费"——即 §7 的消费面与异步执行模型两件事。
