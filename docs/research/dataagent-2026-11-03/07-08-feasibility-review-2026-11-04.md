---
date: 2026-11-04
subject: 07 执行应用层与 08 评测治理层建设方案可行性评审
reviewed_versions: 07 v0.1；08 v0.1
kernel_verified: c1231abffd2cc2f701d300c8ec83654b024b76c1
method: 三个子 Agent 并行评审，主 Agent 交叉核查当前源码、契约、Catalog 与测试
verdict: 技术路线可行；补齐 S0 接缝后实施；当前版本不足以承诺完整业务验收与 Mint 安装复现
---

# 07 / 08 建设方案可行性评审

## 1. 结论与背景目标

**两份方案可以作为建设方向，尚不能直接作为 S0 闭环验收基线。** 不需要推翻 Python 核心、MCP 入口、Agent 侧推理、DuckDB、封闭表达式解释器或三层 bundle 的设计。主要问题是跨层内容协议、执行语义、治理执行点及真实验收事实尚未接通。

判断依据是 [00 总规划](00-pluggable-dataagent.md) 的三个目标：能力可选择、替换和组合；在 Mint GUI / TUI 中完成业务闭环，令才按制度提取、规则审核与交付效果验收；有效组合能沉淀为 Skill / Preset，供其他业务复用。S0 的要求是两族均在未见样本上验收、六类指标并报、显式报告未覆盖范围。

| 评审对象 | 可行性判断 | 可立即推进 | 宣称完成前须补齐 |
|---|---|---|---|
| 07 应用层 S0，13 原子 | 有条件可行，技术选型成熟 | 共享类型、表达式与 SQL 执行原型、交付模板 | 规则完整语义、SQL 与已绑定口径一致、跨层读写与证据回执 |
| 08 治理层 S0，6 原子 | 有条件可行，当前实施约定缺口较大 | 本地策略模型、确定性比较器、样本 manifest | 授权引导、约束落实、模型可见输出检查、正式判据入口、样本与真实运行对账 |
| 三层 S0，32 + 13 + 6 = 51 原子 | 主干覆盖合理 | 先冻结公共接缝，再分流实现 | 三个独立 MCP 进程互读引用，`enforce` 冷启动，两族真实 Agent 验收 |
| 阶段 2 / S1 | 路线图可行，尚不是逐项可执行规格 | 按实际业务选择能力组 | 各流补字段、依赖与验收；DA07.4 仍须等待动作网关和 P1 |
| 令才效果与 MintHub 复用 | 尚待实证 | 准备领域资产、脱敏样本、安装与替换试验 | 真实模型推理与未见样本效果、实际 Mint 安装复现，不能由模拟 proposal 或单元测试代替 |

三层 bundle 粒度本身符合总规划“编号不等于发布粒度”的约定。无需拆成一原子一包；但应证明至少一个后端实现可替换，替换后仍满足同一契约和验收。

下列 P1 表示“在宣称 S0 通过前必须解决”，不表示准备工作或受控原型不能开始。以下是方案缺口，其中提及当前代码是为了验证迁移前提；尚未实现的应用层、治理层不按现存代码缺陷计数。

## 2. 取证基线与实测

- 按根 `AGENTS.md` 先检查独立的 `packages/agent-kernel`：工作区干净，`git fetch origin --prune` 后发现落后 1 个提交，已 `git pull --ff-only` 到 **`c1231abffd2cc2f701d300c8ec83654b024b76c1`**；随后 `HEAD..@{u}` 为 0。
- `bash scripts/sync-iface-packages.sh --check` 通过：10 包与 `kernel/iface/src` 一致，coverage `total=64 mapped=55 allowlist=9 uncovered=0`。未使用历史 `packages/kernel-iface` 作基线。
- 契约包：`uv run --frozen pytest -o addopts='' -q` → **111 passed**。
- 数据层：同一命令在数据层目录执行 → **396 passed**。这是本轮明确返回计数的测试快照，不沿用 r5 旧评审的用例数和未修复状态。
- 契约 schema：`uv run --frozen python scripts/generate_schema.py --check` → **66 files OK**。
- 数据层 Catalog：`uv run --frozen python scripts/export_catalog_snapshot.py --check` → **32 atoms OK**。
- 本轮另做只读模型探测：`FieldValueStatus` 实际为 `extracted / missing / conflict / low_confidence`；向 `Assessment` 增加顶层 `evidence` 会被 `extra_forbidden` 拒绝。
- 本轮交叉复现实测：冻结集声明 100 个未见样本，报告只含一个未经 manifest 核实的 case、质量与覆盖分母为 1，现有 `validate_acceptance_report` 仍通过。详见 §10。

以上证明当前数据层和契约包具有可继续建设的基础，不证明尚未实现的 07 / 08 或业务效果通过。本轮未执行真实 Mint 安装、GUI/TUI 运行、模型推理或客户样本验收；未修改 07 / 08 原文和能力源码。按仓库要求快进更新了 agent-kernel，并新增本评审文件。

## 3. P1：共享存储尚未形成跨层内容协议

**位置：** [07 §2](07-application-layer-build-plan.md)，第 45–46 行；§3 第 73 行；§5.2 第 127 行。

方案规定三个 bundle 共用 `data_root`，按 digest 读取 `TableRef` / `DocumentRef`，同时禁止应用层、治理层导入数据层实现。但 digest 只定位字节，不定义字节内容的格式和语义。

当前表载荷是数据层私有 `TableData`（`packages/capabilities/dataagent-data/src/dataagent_data/contracts/layer.py:42`），读取器位于 `runtime/helpers.py:193`；文档内容及 AnchorResolver 也依赖数据层私有结构。只抽出 ContentStore、SQLite 和 AnchorResolver，会留下反向依赖或迫使新层复制私有格式。

这还影响数值正确性：`classify_table_rows` 标记 `row_meta`，不会删除合计行。把所有 `rows` 直接载入 DuckDB，可能把明细与合计重复求和。共享读取端口必须保留行角色、字段类型、行身份及来源映射，并明确 SQL 绑定选择哪些行。

**最小修订：** 步骤 0 增加版本化的表、文档、来源映射 codec 或读取端口；明确载荷版本、未知版本处理及迁移规则。可由 runtime 提供共享实现，或注入解析端口，无需把整个数据层迁入 core。三个独立进程应能在不导入对方包的情况下，消费同一引用并保留行角色和锚点。

## 4. P1：条件表达式尚未闭合为完整规则判定

**位置：** [07 §5.1](07-application-layer-build-plan.md)，第 114–118 行。

只写“RuleDefinition 的条件逐项编译为 AST”，未规定条件组合 `combination`、例外 `exceptions`、适用性和前置条件如何影响最终 `satisfied / violated / unknown / not_applicable`。这些信息已存在于 core `RuleDefinition`。普通条件计算正确，仍可能把例外对象判为违规，或把适用性未知当作适用。

第 116 行的 `FieldValue.status=unknown` 也与实际契约不同；输入状态是 `extracted / missing / conflict / low_confidence`，`unknown` 是后续逻辑或结论。

**最小修订：** 冻结规则执行顺序、三值真值表及四种 verdict 映射；定义每种字段状态、类型错误、例外、前置条件和适用性结论的处理。无法表达的分支保留不可自动判定原因。表达式、SQL、报告之间还应统一金额精度、单位、时区与日期边界。

**验收反例：** 例外生效、例外条件未知、适用性未知、前置证据缺失、冲突/低置信字段、条件组合中的 `not`，均不能静默转成确定的违规结论。

## 5. P1：SQL 只限制语法和访问，未约束已绑定口径

**位置：** [07 §4.1 / §5.2](07-application-layer-build-plan.md)，第 80–83、125–128 行。

`SELECT`、输入表集合和函数黑名单不能保证 SQL 执行了已经确认的指标。例如指标为“已批准记录的金额之和”，proposal 改成 `SUM(other_existing_column)` 或漏掉批准状态过滤，仍可能通过当前检查，输出却附原指标版本。

DA11.2.3 关注粒度与合并；DA11.5.5 对冻结样本验收。两者都不能代替每次即席查询对已绑定度量、固定过滤、时间和粒度的校验。

**最小修订：** S0 采用有限的结构化单表计划，绑定度量字段、聚合、维度、时间区间、过滤参数和选用行角色；工具据此编译 SQL，或核对 proposal SQL 中这些明确项。`blocking unresolved` 未解除时不进入执行。不能结构化的文本口径返回 `needs_input`，不要求证明任意自然语言与 SQL 等价。

**验收反例：** 使用另一个合法字段、丢固定过滤、改变去重方式、时间上下界错误、混入合计行。进程内 DuckDB 的取消、内存上限和配置锁定时机另做小型实证后固化。

## 6. P1：core 输出承载与证据解析尚未冻结

**位置：** [07 §4.2 / §5](07-application-layer-build-plan.md)，第 90–95、118、128、146 行；[08 §5.3](08-governance-layer-build-plan.md)，第 122–125 行。

`Assessment` 用 `basis_refs` 引用证据，没有顶层 `evidence`；`ComputedResult` 当前没有直接承载 SQL digest、输入版本和 EngineBinding 的专门字段。可以经证据/执行回执引用承载，但方案须指定唯一、可解析的路径。仅把 `ExecutableSpec` 和 `EngineBinding` 的类型名迁入 core，不足以接通 DA07 → DA11 → DA10。

当前 `dataagent-contracts/tests/test_s0_acceptance.py:77` 附近的 IO 清单还保留不同的 SQL/表达式输出形状；这些测试不能证明新方案输出与消费者兼容。

**最小修订：** 步骤 1 先冻结可执行输入输出模型，明确：结果表如何引用、`Assessment.basis_refs` 如何解析到持久化的 EvidenceRef、执行回执如何绑定输入/语义/SQL/引擎版本、DA11 和 DA10 如何解析。必要的共享引用字段按兼容规则追加，并同步 schema、IO 清单和 05。应用特有字段仍留在应用资产中。

## 7. P1：授权引导、约束执行与内核接线须具体化

**位置：** [08 §4.3 / §5.1](08-governance-layer-build-plan.md)，第 89–107 行；[07 §2](07-application-layer-build-plan.md)，第 47 行。

这里有三条必须同时接通的路径：

1. **首次授权与可信上下文。** 当前 CallContext 没有 `subject_ref`、`purpose`，方案却要求取主体和核用途。MCP 当前优先采用 `arguments.context`（`interfaces/mcp_server.py:72`）。若所有读取都先要求既有 AccessDecision，读取策略并首次产生 AccessDecision 的调用又会遇到引导环。05 允许 `authorization_ref` 是策略绑定，08 尚未定义该分支。
2. **允许附带的义务。** 复检只列 allow、期限、资源和用途，未说明何处落实 `field_constraints`、`row_constraints`、`masking_obligations`。当前表读取器返回整表；只检查 allow 会丢失受限访问的含义。派生表、画像、缓存和导出也需要重新授权或继承约束。
3. **内核豁免。** 第 91 行凭 `kernel_session_id` 和宿主声明便只检查决策存在，缺少 DA12 策略到 PolicyContract 的适配器、共同策略版本和可信证明。最新内核已把实际 `{tool,args}` 交给策略（`kernel/host/src/transport/policy/tool_request.rs:35`），问题并非看不到参数；这些参数仍须由适配器解释为 DataAgent 的资源、用途和约束。会话字段本身不能证明已做同等判定。

**最小修订：**

- S0 单用户可由可信宿主配置固定执行主体、作用域、用途和策略绑定，无需先建身份系统；调用参数不能覆盖这些权威值。决策须绑定本次主体、作用域、动作、用途及实际读取的资源闭包。
- 明确策略装载与首次判定的控制入口和允许范围，新增空目录直接 `enforce` 的首调用例。
- 在读取端口落实支持的行列过滤和脱敏；不能落实的约束拒绝。定义派生资源的来源与约束传播。
- P2 分别写明 mint-core 与 kernel 的执行点。内核豁免须以真实策略接线及可信调用证明通过验收为前提；尚无该路径时明确只支持 mint-core，并继续完整资源复检。

## 8. P1：外发检查必须覆盖完整模型可见输出

**位置：** [08 §4.3](08-governance-layer-build-plan.md)，第 90 行；[07 §4.1](07-application-layer-build-plan.md)，第 84 行。

当前工具通常直接生成两段式响应，没有调用 `InferencePort.infer`。例如 `preparation/extraction.py:303` 将原文写入 `issues[].inference_request`，又在 `data.candidate_spans` 中返回一份；`interfaces/mcp_server.py:140` 原样序列化整个结果。只在 InferencePort 或仅在 `inference_request` 字段检查，原文仍可通过普通 `data`、诊断或随后可读取的产物进入 Agent 上下文。

**最小修订：** 增加统一的模型可见输出交付边界，覆盖完整 CapabilityResult、错误/诊断、预览及后续可读产物；全部两段式 handler 迁入该路径。MCP 返回进入模型前完成检查；CLI 明确区分人用输出与供 Agent 消费的输出。目的模型由可信宿主提供，检查 `destination` 与实际模型一致；更换模型目的地须重新判定。

脱敏还有功能性前提：Agent 应能用脱敏候选完成任务，同时保留可核验的原文锚点。需定义脱敏内容与原始证据的映射，否则隐私检查通过后，proposal 的原文校验可能全部失败。

**验收反例：** `deny` 时完整序列化响应不含原文；`allow_masked` 时 `data`、issue、诊断均只呈现允许内容；目的模型不匹配时拒绝。已进入宿主其他上下文的数据仍需宿主自己的控制，组件不能据此承诺控制整个会话。

## 9. P1：判据正式生效入口缺少可调用合同

**位置：** [08 §5.2](08-governance-layer-build-plan.md)，第 114 行；§3 第 62 行；§1 S0 operation 表。

DA11.5.1 只创建 draft，验收只接受 active；方案要求“单独确认调用”，却未定义 operation、管理入口或注册表例外，也未定义如何核验确认记录。现有 CriteriaRef 只要求 active 时 `confirmation_ref` 非空，非空不等于有权确认。

**最小修订：** 指定确认入口的名称、输入、允许调用者、确认记录解析与版本冲突处理，并明确是 Catalog operation 还是独立管理接口。确认应绑定判据内容 digest 与 revision，生成新 revision，不能由修复流程改写原 active 版本。

**验收反例：** 伪造、过期或指向另一份判据的确认拒绝；有效确认后可从正常入口取得 active 判据并完成验收。

## 10. P1：未见样本验收必须与真实运行及观测对账

**位置：** [08 §4.2 / §5.2–5.3](08-governance-layer-build-plan.md)，第 83、115–128 行；阶段 2 第 150、152 行。

这里需要补两份最小合同：

- **样本资格与完整性。** 冻结清单不可变，暴露后台账变化；验收应按“冻结 manifest + 本次运行资格快照”计算，不能直接改写冻结集。每个 case 须核对成员资格、唯一性、输入版本和运行回执；遗漏、失败、超时、预算耗尽不能从分母消失。向修复方披露金标或足以反推金标的诊断后，也要登记暴露。
- **六类指标的事实来源。** Assessment、ComputedResult 和版本列表不能推导人工、模型计费或业务端到端时延。两段式工具单次 `finished_at-started_at` 不包含 Agent 推理。完整回归编排和持续改进可留在阶段 2，但 S0 必须接收最小运行清单与宿主观测回执。

**实测：** 本轮用 active 判据、100 个未见样本的 frozen EvaluationSetRef，构造仅一个 case、分母为 1、`run_ref=unverified-run` 的 pass 报告，`validate_acceptance_report` 仍通过。该函数（`core/evaluation.py:167–185`）只校验引用、状态、冻结、未见数量非零和 case 数量上限，不读取 manifest，也不验证实际执行。因此“通过 helper”只能是必要结构校验。

**最小修订：** S0 增加按 `run_id / case_id` 绑定的不可变运行清单，绑定候选实现、输入、判据、依赖与实际结果；宿主提供模型成本、人工事件及业务计时。缺结果补失败/未知项，缺观测写 `missing_records`，不可填零。明确观测缺失或样本不足时允许哪些结论，不能据此宣称六指标齐全或独立效果通过。

本地样本库的约定隔离已在方案中披露，是合理的 S0 限制；不要求为此先建设远程样本库。上述对账要求即使在本地也应成立。

## 11. P1：Mint 安装与共享配置须落实到独立制品

**位置：** [07 §3 / §9](07-application-layer-build-plan.md)，第 73、185–188 行；[08 §8](08-governance-layer-build-plan.md)，第 175–180 行。

三个 Mint bundle 依赖 contracts/runtime，不代表各自 `uv --project $PKG` 的 Python 环境自动拥有这些依赖。现数据层已有 staging + vendoring，专门解决发布后兄弟目录消失；07 / 08 没有明确沿用或替换方式，也未定义不同 bundle 自带不同 runtime 时的存储协议兼容性。

共享目录也需实际注入：Runtime 默认从 cwd 或 `DATAAGENT_WORKSPACE` / `DATAAGENT_DATA_ROOT` 解析。Mint 对 bundle 子进程清空环境，只继承基础变量和 `capabilities.env` 声明项（`mcp_loader.rs:383`、`mcp/client.rs:215`）。拟议 capabilities 尚未声明上述变量。默认同 cwd 可能工作，自定义目录不能据此成立。

**最小修订：**

1. 选择自包含 vendoring 或固定 wheel 的构建方案；每包固定 contracts/runtime 版本与 hash，提供共享存储格式兼容检查。
2. Preset 明确统一 workspace、data_root、策略和 enforcement 的注入方式，补对应 env 声明或显式启动配置；启动时校验配置一致。
3. 说明依赖预取与离线准备。`--frozen` 只禁止改锁文件，不保证依赖已存在；若承诺不联网运行，须在安装阶段准备 wheel/cache。
4. 在干净项目安装 Preset，经真实 Mint loader 拉起三个进程，再互读引用、执行两族链路。至少覆盖宿主 cwd 不同、自定义 data_root 和缺依赖场景。测试包直接依赖三份 Python 源码可作为一层验证，不能代替制品验证。

不要求 S0 已公开发布 MintHub，但可安装、可复现的本地制品试验应前置，避免最终才发现包边界不成立。

## 12. 范围统计与阶段 2 修订

总 Catalog 实测：

| 层 | 总原子 | FDE | 非 FDE | S0 | 按需 | S1 |
|---|---:|---:|---:|---:|---:|---:|
| 应用层 | 126 | 16 | 110 | 13 | 93 | 4 |
| 治理层 | 73 | 19 | 54 | 6 | 48 | 0 |

07 第 17 行把应用层排除的 FDE 写为 19，实际为 16。第 16 行“按需 90、S1 7”是把 Catalog 中按需的 DA07.4 三项后移到阶段 3；该实施安排合理，但要明确“计划阶段”与“Catalog 切片”的映射。无需因实施顺序变化直接修改生成物。

阶段 2 的“六流并行”“两流并行”应改为“前置依赖就绪的工作包并行”。主要依赖包括：DA05.3 等待 DA04.3；DA05.7 等待血缘类型和来源；DA12.4 等待 DA05.7；DA10.4 等待 DA12.5 和资产变更端口；方法评估等待 DA08 / DA09；DA07.2 等待可验证的隔离环境。夹具可支持开发，最终验收须换成真实生产者。

本轮不建议为凑齐 110 / 54 原子提前建设全部按需能力。先证明令才判定族与一个计算族应用的效果，再按缺口选取增量。

## 13. 建议实施顺序与通过门槛

| 波次 | 工作 | 并行边界 | 退出条件 |
|---|---|---|---|
| 0：冻结公共接缝 | 定 P2 的实际路径、授权引导；共享载荷与解析端口；S0 输入输出、执行回执、判据确认和运行清单 | 先明确共同合同，避免分别修改 core/runtime | 用两族完整样例能表示每一步及全部引用；不只有类型名称 |
| 1：运行时与安装骨架 | 抽 runtime、codec/读取端口；迁移数据层；三包独立构建、目录配置、最小策略与输出边界 | runtime 单一负责；制品与配置验证可同步准备 | 数据层既有门禁通过；空数据目录 enforce 能取首决策；真实 loader 启动三包并互读引用 |
| 2：S0 实现 | A 表达式/规则；B 需求绑定/SQL；C 访问/外发；D 判据/样本/验收 | 四条逻辑工作流，按可用 Agent 槽位分批；共同合同变更经单一负责人合并 | 各自反例通过，受限访问落实到实际数据，输出与证据可解析 |
| 3：交付与真实验收 | DA10 报告/工作簿；DA11 粒度与逐 case 对账；两族 Skill / Preset | 有固定输出后合流 | 真实 Agent 对未见样本执行；六类指标有事实或显式缺失；失败样本不漏；报告保持 unknown 与证据 |
| 4：复现与替换 | 干净 Mint 项目安装；替换至少一个后端；令才领域资产与样本复验 | 应用样本与后端验证可并行 | 无仓库兄弟路径依赖；无需为具体应用新增或修改 core；相同契约下结果与证据可复现，局限明确 |
| 5：按需与 S1 | 按依赖 DAG 选择增量能力 | 生产者先行；就绪工作包并行 | 对应业务验收通过；回写仍受 P1 / 动作网关约束 |

这一顺序保留两份方案的大部分技术选型和模块拆分，把最容易在联调时返工的接缝提前固定。S0 通过后，才能据业务样本效果判断是否扩大阶段 2 投入；当前没有足够实测依据给出可靠工期或业务准确率承诺。
