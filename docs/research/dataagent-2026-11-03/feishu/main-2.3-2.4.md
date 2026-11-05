## 2.3 平台对接待决

实现前须定案。内核依据：`agent-kernel@f0fa521`，权威源 `kernel/iface/src`。

| 编号 | 待决项 | 当前做法（v0.1） | 内核 / Mint 事实 | 选项 | 建议 | 最晚定案 |
|-|-|-|-|-|-|-|
| P1 | 写通道怎么强制 | Python `action_gateway.py`，靠端口约定 | `EffectLevel::SideEffect`；guard 为单一门 | A 进程隔离：写后端凭据只发给网关进程；B 语言隔离：Rust 网关；C 只靠约定 | **A**，语言可后定；拒绝 C | S1 回写之前 |
| P2 | 数据访问判定与内核 guard | DA12.1 自出 `AccessDecision`，多点复检 | guard 单一门、fail-closed（`kernel/core/src/guard/`） | A 单闸门；B 双闸门；C guard 判定 + DA12.1 策略源，复检只用于不经内核的路径 | **C**：经内核的调用以 guard 为准；缓存命中、导出、离线索引由 DA12.1 复检；两路共用同一策略版本 | S0 之前 |
| P3 | 档位与审批映射 | 自拟 `ApprovalRequestRef` | `ApprovalRequest` 仅 4 字段；`ReviewPosition` 四段 | A 扩充内核字段；B 证据包外置，`summary` 携带 `EvidencePackageRef` | **B**；A0→ReadOnly，A1→Advance + Plan 审查，A2→SideEffect + ToolParams 审查 | S1 之前 |
| P4 | 组合清单与发布格式 | 自拟 `component-specs` / `presets` YAML，一层一工作区 | `kind = "skill"`（`SKILL.md`）、`kind = "preset"`（`[dependencies]` + `preset.toml`）；`AssemblyIntent.payload` 承载声明式装配数据；`mint.toml` 有 `license` 与 `[capabilities]` | A 沿用 Mint 包格式；B 自拟；C 自拟后转换 | **A**：DA18.6 产出 skill 包，DA18.7 产出 preset 包，运行时组合参数序列化进 `AssemblyIntent.payload`；开发期可一层一工作区 | 首次发布 MintHub 之前 |
| P5 | 轨迹与记忆存储 | 自建 SQLite `TraceRepository` | `StoreContract` 游标为会话内 | A 轨迹落 `StoreContract`、作用域记忆自建；B 全部自建 | **A**：DA04.1 经适配器写入 `StoreContract`；DA04.3 先自建并冻结 `Scope` 形状 | S0 期间 |
| P6 | 编队与接管 | 未用内核原语 | `DelegationGrant`、`Lease`、`BlockedOnItem` | A 机制归 OS；B 能力层自建 | **A**：DA14.6、DA14.7、DA16.1 引用内核原语，能力层只做角色与子目标划分 | S2 之前 |
| P7 | 存储后端 | SQLite 起步，端口可替换 | — | — | 维持；DA17.5.2 环境预检检查并发、保留、审计要求是否超出 SQLite | 部署前 |

## 2.4 跨层契约

各层所引“总体跨层约定”即本节。

1. **契约包。** 共享类型提取为独立包 `dataagent-contracts`（第 0 层）。数据层、应用层、治理层、运行层只依赖它，互不导入对方实现。数据层 `src/dataagent_data/contracts/` 中的公共部分迁入该包，各层 `contracts/` 只保留本层特有类型。
2. **包内范围：**
   - 调用封套：`CallContext`、`CapabilityResult`、`Issue`、`ExecutionRef`、`Continuation`；
   - 引用：`AssetRef`、`ResourceRef`、`SnapshotRef`、`SourceAnchor`、`EvidenceRef`、`TaskContextRef`、`DeliveryRef`；
   - 统一词表：`LifecycleStatus`、`ActionTier`、`AccessDecision`、`ComponentMeta`（含 `license`）。
3. **`LifecycleStatus`：** `draft → candidate → validated → active → deprecated / invalidated / rejected`。经验用 `candidate/validated/active/deprecated`；治理资产用 `draft/validated/active/deprecated/invalidated`；程序用 `draft/validated/rejected`，是否已执行记为执行记录属性，不作为状态。
4. **依赖方向：** contracts ← data ← application；治理层、运行层只依赖 contracts，以及经端口注入的实现。
5. **类型完整度门槛：** 进入某个切片（§4.1）的原子，其输入输出类型必须在 contracts 中有字段定义；只有名字的类型不得进入切片验收。
6. **schema：** 先写类型、再生成 schema（`contracts/generated/`），不手写第二份。

类型与字段明细见 [05-contracts.md](https://modelbest.feishu.cn/docx/VavsdOWFeoLBFrxOt9JcjAsInDe)。
