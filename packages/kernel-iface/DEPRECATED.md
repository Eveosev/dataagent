# ⚠ DEPRECATED：iface 契约包 0.1.0 历史快照

- 状态：**已废弃（deprecated）**，只读保留，不再更新
- 废弃日期：2026-11-02
- 快照内容：`agentcpm/iface-*` 共 10 包，版本 **0.1.0**，同步至 kernel master `d950766`（2026-10-29 打包）
- 规模：44 个 `.rs` / 6292 行 / 22 个 `pub trait`

## 现在应该去哪里

| 用途 | 位置 |
| --- | --- |
| 读/改契约（唯一权威源） | `packages/agent-kernel/kernel/iface/src/` |
| 读分发包（10 个 iface 包，含 `schema.json`/`README`/`SKILL.md`） | `packages/agent-kernel/packages/iface-*`（0.1.2） |
| 校验分发件与权威源是否一致 | `packages/agent-kernel/scripts/sync-iface-packages.sh --check` |
| 发布到 Mint Hub | `packages/agent-kernel/scripts/publish-iface-mint-hub.sh` |

`packages/agent-kernel` 是独立 git 仓库，**任何与 Mint 制品或 iface 契约的对比之前**，先同步它：

```bash
cd packages/agent-kernel
git fetch origin --prune
test "$(git rev-list --count HEAD..@{u})" -eq 0 || git pull --ff-only
bash scripts/sync-iface-packages.sh --check
```

流程与理由见 AgentOS 根 [`README.md`](../../README.md)「iface 契约：位置与对比流程」。

## 为什么废弃

`packages/agent-kernel/packages/iface-*` 是本目录的**严格超集**，且已向前演进（0.1.0 → 0.1.2）：

| 指标 | 本目录（0.1.0） | agent-kernel/packages（0.1.2） |
| --- | --- | --- |
| `.rs` 文件 / 行数 | 44 / 6292 | 73 / 8113 |
| `pub trait` | 22 | 28 |
| 全局 `pub` 声明（去重） | 303 | 340 |
| 旧版本有、新版本缺失的声明 | — | **0** |
| 独立 crate 构建（`Cargo.toml` + `lib.rs`） | 无 | 有 |

逐项核对方式（在 `packages/` 下执行，只读）：

```bash
# 全树 API 差集应为空
comm -23 \
  <(grep -rhoE '^\s*pub (struct|enum|trait|fn|type|const) [A-Za-z0-9_]+' $(find kernel-iface -path '*/src/*' -name '*.rs') | sort -u) \
  <(grep -rhoE '^\s*pub (struct|enum|trait|fn|type|const) [A-Za-z0-9_]+' $(find agent-kernel/packages -path '*/src/*' -name '*.rs') | sort -u)
```

当时确认过的位移（不是删除）：

- `iface-model/src/{capabilities,config,event,input,operations,types}.rs` → `agent-kernel/packages/iface-model/src/model_session/*.rs`（逐字节相同）
- `NodeId` / `LOCAL_NODE` / `MAX_NODE_ID_LEN`：`iface-session/src/node.rs` → `iface-types/src/node.rs`，`session::node::*` 保留 `pub use` 别名
- `ContextSnapshot` / `ContextContract`：`iface-context/src/context.rs` → `context/contract.rs`

## 本目录里还有什么不在新树中

仅 4 个非契约文件，且都有替代：

| 文件 | 状况 |
| --- | --- |
| `README.md`（本目录索引） | 0.1.0 专用说明，已由本文取代 |
| `PACKAGING-NOTES.md` | 2026-10 的 Mint 打包试点记录；现行流程见 `publish-iface-mint-hub.sh` |
| `SUBSTITUTABILITY-SCORECARD.md` | 只覆盖 8 个原契约；相关证据散在 `agent-kernel/kernel/docs/notes/` |
| `publish-iface-online.sh` | 被 `agent-kernel/scripts/publish-iface-mint-hub.sh`（179 行）取代 |

## 与线上制品的关系

Mint Hub 上 `agentcpm/iface-*@0.1.0` 发布于 2026-10-27T15:37Z，**早于**本快照（缺 D93 模型流式、D96 模型会话）。
三方都不等价：`hub@0.1.0` ⊂ `本快照@0.1.0` ⊂ `agent-kernel/packages@0.1.2`。引用线上制品前先核对 digest。

## 保留 / 删除建议

- 需要追溯 0.1.0 发布史时保留本目录；否则可整目录删除。
- 删除前建议把 `PACKAGING-NOTES.md` 与 `SUBSTITUTABILITY-SCORECARD.md` 归档到 `packages/agent-kernel/docs/`。
- **不要**在本目录继续修改契约内容：改动会在下一次 `sync-iface-packages.sh --check` 中被判为漂移。
