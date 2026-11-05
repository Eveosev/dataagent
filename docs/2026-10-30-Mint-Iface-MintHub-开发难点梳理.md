# Mint / Iface / MintHub 开发难点梳理

> 整理：2026-10-30（Asia/Shanghai）。证据：`packages/agent-kernel` 的 10 天 git 史（近 700 个提交，全分支 726）、
> 本工作区 95 份文档、`workspace/` 下的实测与诊断记录。路径均相对 `/Users/payne/Vibe/AgentOS`。
>
> 状态口径：**已解决**（有代码/门禁/实测证据）、**部分解决**（主链路通但缺口明确）、
> **暂未解决**（缺陷单标 `待修`/`仅报告`，或实测仍可复现）。每条按「问题背景 — 影响范围 — 解决方法」写。
> 凡"代码核实"指读过实现；只引文档未读实现的会标注。
>
> **2026-11-02 更新**：文中引用的 `packages/kernel-iface/` 已冻结为 0.1.0 历史快照，勿作对比基线；
> iface 契约现以 `packages/agent-kernel/kernel/iface/src` 为权威源，可读副本为
> `packages/agent-kernel/packages/iface-*`（0.1.2）。对比前先同步 agent-kernel，见根 `README.md`。

---

## 0. 开发过程时间线

| 日期 | 主题 | 关键转折 |
|---|---|---|
| 10-21～10-22 | 文档与脚手架 | PRD/骨架先落；`mint-protocol`、`mint-api`、`manifest+pack`、CLI、`mint-core` 五块成形 |
| 10-23 | MintHub 与三端 | hub 服务端（axum + sqlx Any + object_store + rust-embed）、TUI、SPA、私服镜像、登录；同日进 CNAP/OBS 部署 |
| 10-24～10-25 | 安装器与发版 | `install.sh` / `app.yaml` 反复修，release 累到 seq39，0.1.12/0.1.8 产品线冻结 |
| 10-26 | kernel / mint 分家 | 拆出 `kernel/`，冻结 8 份 iface 契约 v0.1.0；8896 行 `transport.rs` 拆成 33 文件 |
| 10-27 | 契约治理 | D83「契约源唯一化」+ 契约源门禁、iface API 门禁、全双工；Mint 侧修 300 s 断连、token 估算、max_steps |
| 10-28～10-29 | 模型会话与定名 | D93/D96 模型会话 12 方法；`cpmrt` 定名（只改名未改制品）；refactor-v1 起基线 |
| 10-30 上半 | refactor-v1 一期 | R01–R32 按 `rv1/*` 分支并发 + 集成分支，accept 74/0/13 → 76/0/11 |
| 10-30 下半 | 二三期与闭环 | R07/R10/R12/R24/R28/R33/R34 合入，3804/0/26、accept 87/0/5；真模型 llama-server 接入又暴露探活与 turn-loop 新坑 |

返工密度本身就是证据：`docs/refactor-v1/PROGRESS.md` 被改 67 次（跨期账本）；
`kernel/host/src/transport/` 累计 93 次提交（绝对热点，也是它被拆成 33 文件的原因）；
`mint/crates/mint-core/src/` 56 次；`mint/hub` 23 次。

---

## 1. 一页速览

| ID | 难点 | 状态 |
|---|---|---|
| M-1 | 包管理器与运行时耦合，组件改名即启动失败 | 已解决 |
| M-2 | 改名只改一半：`core→std` 与 `mint-core→cpmrt` 都留下硬编码 | 部分解决 |
| M-3 | 分层口径半迁移，76 份文档混用旧名、9 份自相矛盾 | 部分解决 |
| M-4 | 11 个包类型装不下"纯契约包"，只能借 `skill`/`bundle` | 已绕过 |
| M-5 | 依赖解析从 BFS 改确定性回溯，冲突无法解释 | 已解决 |
| M-6 | 桌面 lock 漂移"拒绝正确但没有出路"，用户卡死 | 已解决 |
| M-7 | 验签与收据链三处静默降级（收据门、引导脚本、`.minisig`） | 部分解决 |
| M-8 | 发行批次不闭合：`stable` 是"每包最新"，组合出不可安装版本对 | 暂未解决 |
| M-9 | Mintfile/打包器与 CLI 的 lock·布局契约漂移，只能删字段绕过 | 暂未解决 |
| M-10 | 同版本异制品：版本号被当成制品身份 | 部分解决 |
| M-11 | 桌面 300 s 固定超时把长任务/等待审批判死 | 已解决 |
| M-12 | 上下文预算按"1 字节 = 1 token"估算，长会话被拒 | 已解决 |
| M-13 | 审批语义错位：超时当拒绝、子 Agent 钉成只读 | 已解决 |
| M-14 | 协议缺口（D-C5/C10/C11），且缺陷单状态滞后于代码 | 部分解决 |
| M-15 | `std` 制品实为 `core`，TUI 退出码 7，`doctor` 报"无问题" | 暂未解决 |
| M-16 | 嵌套 Seatbelt / full-access 让命令全部失败 | 已解决（沙箱仍 Partial） |
| M-17 | 出网管控 100% 失效 + principal 可伪造 | 已解决 |
| M-18 | 执行语义四缺陷、deadline 丢弃、BTL 不读 `job.input` | 已解决 |
| M-19 | `MutexGuard` 跨 `await`，列工具时阻塞 add/remove | 已解决 |
| M-20 | 基线 6 红 + 克隆 target 的 mtime 制造假绿 | 已解决 |
| M-21 | 探活写死 minicpm 网关，4 条验收长期全 SKIP | 已解决 |
| H-1 | 发布非原子：索引重建失败仍返回 200 | 部分解决 |
| H-2 | PENDING 版本号黑洞，无清理任务 | 暂未解决 |
| H-3 | 签名链只有一层，密钥仪式命令不存在 | 暂未解决 |
| H-4 | tag 三处真源，`set_tag` 对 latest/stable 假成功 | 暂未解决 |
| H-5 | OCI 兼容面形状乖离（mediaType/variant/错误体） | 暂未解决 |
| H-6 | 大制品全量入内存、无 Range、暂存落 `/tmp` | 暂未解决 |
| H-7 | 部署面把基础设施缺陷变成发布故障 | 已解决 |
| H-8 | 半成品接口返回 200 TODO，镜像漏包静默推进 | 暂未解决 |
| I-1 | 契约与实现两套类型宇宙，合规插件被判"未知 outcome" | 部分解决 |
| I-2 | `iface-loop` 是死契约，kernel 内 0 引用 | 暂未解决 |
| I-3 | `Kind::Iface` 不可达，10/10 包是 `bundle` | 暂未解决 |
| I-4 | `[requires]` 表达不了 interface 依赖，未知键被静默丢弃 | 已解决 |
| I-5 | 跨包依赖漂移，出现未声明的 session ↔ store 环 | 已解决 |
| I-6 | 契约包单独不可编译（`BoxFuture` 不在分发范围） | 部分解决 |
| I-7 | `schema.json` 不是 JSON Schema，方法名还与源码不一致 | 暂未解决 |
| I-8 | 消费方坐标失真，"谁在消费契约"不可核 | 暂未解决 |
| I-9 | 可替换性从"声称"到"实测"，过程中修 7 个真问题 | 已解决（余量见 I-11） |
| I-10 | 语义等价：判据可信，但分母只有 8/22 与 5/40 | 部分解决 |
| I-11 | 上游快跑 + 分发副本落后一代，README 却称"逐字节相同" | 部分解决 |
| I-12 | 门禁自身有 bug，逼人刷基线 | 已解决 |
| I-13 | epoch 围栏漏 `target_session`，契约语义静默失效 | 已解决 |
| I-14 | 版本协商机制在，分发链上是空的（D101 撤回映射） | 暂未解决 |
| I-15 | 10/10 契约包 `SKILL.md` 缺 frontmatter，装机即报错 | 暂未解决 |
| A-1 | 宿主能力面异构，适配器进程内、不可分发 | 部分解决 |
| A-2 | 能力/评测/经验契约缺失，不写 Python 跑不了实验 | 部分解决 |
| A-3 | 基础库包没有装配协议，应用只能自造 bootstrap | 已绕过 |
| A-4 | 装上后运行环境断裂：PATH、`${HOME}`、数据目录串用 | 已解决 |
| A-5 | 工具注册静默失败：装上了，会话里没有 | 已解决（0.1.1 起） |
| A-6 | 工具 schema 缺根类型 → 模型网关 400，工具没被调用 | 已解决（0.1.2） |
| A-7 | 审批按工具名猜类型，"命名即体验" | 暂未解决 |
| A-8 | 60 s 工具超时 / 50 MB 上传，只能作业化 | 已绕过 |
| A-9 | 多包版本漂移 + base 单点 + base 定位失败 | 已解决 |
| A-10 | 大证据反噬：869 KB status 打断 review | 已解决 |
| A-11 | 长任务没有增量事件，进度只能一次性拿全 | 暂未解决 |
| A-12 | 评测归因失败：同一 Skill 0/3 与 3/3 并存 | 暂未解决 |
| A-13 | `loaded=unverified`：发布成功无法证明宿主已加载 | 部分解决 |
| A-14 | 审计证据链被降级，无 `events.jsonl` / 无哈希链 | 暂未解决 |
| A-15 | 应用成品 `kind=app` 交付链未闭环 | 暂未解决 |
| A-16 | 打包器排除 `node_modules`、拒 `*.pem` | 已绕过 |

**一句话结论**：Mint 的难点集中在**分层与制品一致性**（文档/制品/档位三处漂移 + 分发不可重放）；
Iface 的难点集中在**契约有没有真实消费方**（形状对了但没人用，用了却不是同一套类型，副本还会悄悄落后）；
应用侧的难点集中在**装进别人运行时之后的语义断裂**（PATH、数据目录、审批、超时、版本、可观测性）。

---

## 2. Mint / MintHub

### 2.1 分层与命名

#### M-1 包管理器与运行时耦合，组件改名即启动失败

**问题背景**：早期 `mint start` 把官方组件名（core/gui/tui）写进启动路径，由 CLI 决定"启动哪个内核"。
组件一改名或调档（如 core 档改名 std），启动路径就指向不存在的名字。根因是把**分发**与**运行**放在同一层，
而 loop、会话、工具执行、审批都在运行时里。

**影响范围**：所有用 `mint start` 进入的用户；改名类故障是全量不可用，不是个别包失败。

**解决方法**：已解决。拆两层：`mint` 只做解析/验签/锁/安装/发布，`mint start` 仅转发给 `cpmrt`。
判据是"谁持有 loop、会话、工具执行、审批"——答案永远是 cpmrt
（`docs/dev/rsi_toolkit/2026-10-28-mint-platform-notes.md` §1；`mint/bins/mint/Cargo.toml:12`）。

#### M-2 改名只改一半：`core→std` 与 `mint-core→cpmrt` 都留下硬编码

**问题背景**：两次改名各留一半。① 0.1.7 起停发 core 档，但包名仍 `mint/core`、命令仍 `mint core`、
目录仍 `~/.mint/cores/{版本}-{档位}`，三处代码写死档位（`run.rs` 传 `core:true`、`init.rs` 写 `Flavor::Core`、
`install_core_for` 写 `"core"`）；`mint core install core@0.1.11` 去找 `core-aarch64` 制品得到 404——
**提示语本身指向已停发档位，用户照做再失败一次**；`mint install mint/core` 退化成 `core@stable`，
与 `INSTALL.md:37` 声称相反（`mint/docs/roadmap/2026-10-27-feedback-and-agentcpm-runtime.md:167-171`）。
② 运行时改名 `cpmrt`，但制品里仍是 `bin/mint-core`，`which cpmrt` 为空。

**影响范围**：所有按官方提示装内核/空目录起会话的新用户；CLI、提示语、Hub 页面、文档四条链同时错。
失败通常显式（exit 7 / 404），但"修一次漏三处"。

**解决方法**：部分解决。CLI 侧已收出唯一真值 `KERNEL_UNIT_NAME` / `published_flavors` / `kernel_install_hint`
（`mint/bins/mint/src/core.rs:25-80`），只对 `core.missing` 做 core→std 单向回退；core_anchors 9/9 + 临时
`MINT_HOME` 真机装成 0.1.11-std。**Hub 侧暂未解决**：`hub/server/src/api/packages.rs:24-27` 仍
`flavors.first().unwrap_or("core")` 且缺 scope，索引行 flavors 仍为空。`cpmrt` 制品改名同理未做。

#### M-3 分层口径半迁移，同文件两种模型并存

**问题背景**：cpmrt 拆分后，旧 PRD 仍把"L1 内核 Agent Core"写成 Mint 六层结构的一层、把包管理器放在"横切"。
全仓 76 份 Markdown 提旧名，其中 9 份"半迁移"——同一文件既有 `cpmrt` 又有 `Mint 内核`。

**影响范围**：读者无法判断哪句是现行事实；`mint --help` 首行、`mint/docs/README.md` 第一句都是入口级文本。

**解决方法**：部分解决。审计给出三类错法（概念错/入口表述过时/命名过时）与优先级：先修 9 份半迁移与 6 处
用户可见文案，不动 67 份历史 PRD（`docs/mint/2026-10-28-文档口径审计.md` §0–§3）。批量重写**暂未完成**。

### 2.2 分发：类型、解析、安装与可信链

#### M-4 11 个包类型装不下"纯契约包"

**问题背景**：要把 10 个 iface 契约包发到 MintHub，但 `Kind` 枚举 11 个值里没有 `iface`；
`plugin` 强制 `subkind ∈ {wasm,native,js}`（硬套等于说谎），`bundle` 要求 `skills/`/`commands/`/`agents/`/
`hooks/`/`.mcp.json` 之一。生产 Hub 实测 `unknown variant 'iface'`（400 `invalid_payload`），
只能先以 `kind="skill"` 变通，后改 `bundle` 并给每包补 `SKILL.md`。

**影响范围**：契约包的所有发现与消费路径；`Kind::Iface` 的 `validate.rs`/`layout.rs` 分支无包可达，是死代码。

**解决方法**：已绕过（`packages/iface-*/mint.toml:3`；`packages/kernel-iface/PACKAGING-NOTES.md` 首段）。
真正的 `Kind::Iface` **暂未解决**，需 Hub 升级 + 新版本号重发（`PUBLISH_REPORT.md:155-165`）。

#### M-5 依赖解析从 BFS 改确定性回溯

**问题背景**：BFS 遇到冲突只能说"无解"，无法指出是谁的约束；版本选择不稳定，同一清单可能解析出不同结果。

**影响范围**：所有多版本约束工程；CI 里 `mint lock --check` 的稳定性。

**解决方法**：已解决。候选最少优先、锁定版本优先、冲突换候选；错误列出每个请求者与约束；上限 100k 状态 / 10 秒。
`mint.lock` 增 `requires[]`、`artifacts`、`resolver="backtracking-v1"`，旧 lock 仍可读
（`mint/CHANGELOG.md` CLI 0.1.11 段）。

#### M-6 桌面 lock 漂移"拒绝正确但没有出路"

**问题背景**：同版本重装/升级 `agent-gui` 时，工作区 lock 还是 onboarding 的旧 `0.1.4-core`，成品冻结的是
`0.1.12-std`；安装器判"受管理的 Core 或包锁已变化；不会覆盖用户变更"直接拒绝，提示里**没有任何出路**。
用户侧表现为"装不上、也修不了"。

**影响范围**：已装用户的升级与修复路径；支持成本最高的一类问题。

**解决方法**：已解决。拆 `verify_workspace_identity`（项目名/版本/桌面元数据/档位，`[model]`/`[ui]` 不参与）与
`workspace_lock_matches`（只比 core + 包 pin）：身份一致但受管元数据漂移 → warn + `repair=true` 按成品重建
（模型配置与会话保留）；身份不一致仍拒绝，失败补 `.hint`。验证 app_install 52 测试 + 隔离 worktree `cargo check`
（commit `bb2d75f`；`mint/docs/roadmap/2026-10-26-desktop-upgrade.md:14`）。

#### M-7 验签与收据链三处静默降级

**问题背景**：三处各自成立、叠加起来让"验签"名存实亡。① **收据门**：`install.sh` 写 `installed_at`，
Rust `Receipt` 的 `at` 必填 → 反序列化失败 → `read_receipt()` 返回 `None` → `mint self update` 的
"非本渠道安装就拒绝"整条门失效、直接放行（`mint/docs/INSTALLER-DESIGN.md:62`）。
② **引导脚本**：`install.sh` 只有 HTTPS + `bootstrap-*.toml` 的 sha256，脚本自陈"未验证独立信任根、
索引或 minisign"，收据落 `"verification":"https-sha256","signature_verified":false`
（`hub/server/src/install.sh:41,189,649`）。③ **制品签名**：`.minisig` 缺失或取失败只做 sha256，
失败分支仅一句 `out::detail`；验证器还接受 5 种被签消息形态（制品原文、裸 hex、`hex\n`、`hex  file\n`、无换行）
× 全部公钥，任一命中即通过（`mint/bins/mint/src/verify.rs:171-195,266-288`）。

**影响范围**：所有 `curl | sh` 新用户与所有 `mint add`/`verify` 消费方；镜像或元数据同源被投毒即失守，
一次网络抖动就让制品级验签消失。全部静默，只能靠 dirhash 事后取证。

**解决方法**：部分解决。写端已双写 `at` 与 `installed_at`（`install.sh:649-650`），读端仍只有必填 `at`
（`bins/mint/src/cmd/self_update.rs:26-46`），**旧收据仍静默失效**；引导签名**暂未解决**，
现有边界缓解是元数据只从 Hub 取、两次 SHA256 + 布局校验 + 隔离 HOME 的 `--version` smoke、失败回滚恢复旧收据；
`.minisig` 降级按 T1 语义保留，**暂未解决**（文档把多形态写成优点，实际是把"签名消息口径不统一"转成验证器宽容）。

#### M-8 发行批次不闭合：`stable` 是"每包最新"，组合出不可安装版本对

**问题背景**：配方要求 `core>=0.1.1` 而线上 core `stable` 仍指 0.1.0；immutable CLI 0.1.1 的
`init --from mint/preset-*@=0.1.1` 先锁旧 core，再被兼容门拒绝（exit 3）——三个配方发后均真实复现。
另一例：`preset-default` 发布时其依赖 `mint/tui` 尚未构建（`mint/docs/roadmap/2026-10-25-component-release-queue.md:37`；
`PUBLISH_REPORT.md:84-85,99`）。

**影响范围**：新用户 onboarding 直接死；"只发配方"无法修好旧 CLI，发布流程却自认成功。

**解决方法**：暂未解决。文档明确"不能声称只发布配方已修复旧 CLI onboarding"，只给手工绕行
（`core install core@0.1.1 --use` + `add --force-preset`）；根因修复（`agentos.lock` 发行批次 + 索引 flavors 回填）
仍是 P2（`mint/docs/roadmap/2026-10-27-feedback-and-agentcpm-runtime.md:210-220`）。

#### M-9 Mintfile/打包器与 CLI 的 lock·布局契约漂移

**问题背景**：桌面打包器要求 lock 顶层只有 `v/core/package`，CLI 0.1.11 还写 `resolver`、`generated_at`；
`BUNDLE_FILES` 要求 `bin/mint-host`、`bin/mint-ax-helper`；冻结输入目录必须是
`packages/mint/<name>@<version>/`（`mint/docs/roadmap/2026-10-27-agent-gui-0.1.8-release.md:41-48`）。
Mintfile 的 `FROM mint/agent-gui:x` 只能复用基座 `.app`（不重建不重签），与基座共用 macOS bundle id，
改 UI 会在桌面校验失败（`mint/docs/units.md:162-168`）。

**影响范围**：`kind=app` 制品构建/发布；应用方一旦改 UI 就装不上。

**解决方法**：暂未解决（绕过而非修复）。在冻结输入里删两个信息性字段、按 `BUNDLE_FILES` 保留文件、
按约定命名目录，文档自标"下次发布前建议修"。

#### M-10 同版本异制品：版本号被当成制品身份

**问题背景**：线上 `provider-openai@0.1.0` 是 bundle，本地工作树被另一任务改成了 plugin-wasm；
发布 CLI 路径可被新构建覆盖，同版本并行 debug 构建不可比。于是安装方、发布方、审计方对"同一版本"
看到三种内容，只有 lock 与 dirhash 能分辨（`mint/docs/roadmap/2026-10-25-package-readiness.md:59`、
`2026-10-25-component-release-queue.md:5-9`）。

**影响范围**：所有"按版本号做断言"的验收与审计；同版本复现实验不成立。属静默——版本号没变，内容变了。

**解决方法**：部分解决（流程层）。冻结不可变副本 `target/frozen-0.1.1/{mint,mint-core,mint-gui}`
（独立 inode、SHA 与发布证据一致），只用冻结 CLI；发布体以归档内 `ManifestJson` 为身份，
`PackedArtifact::from_archive()` 复核每文件 SHA/大小/执行位/dirhash，不信旁置 `.sha256`
（`mint/docs/roadmap/build-release-contract.md`「验证和不可变性」）。
**制品层暂未解决**：没有"同版本不同形态一律拒绝"的规则。

### 2.3 运行时与桌面

#### M-11 桌面 300 s 固定超时把长任务判死

**问题背景**：GUI 的 `bridge.rs` 给每个 `session/prompt` 包了 `timeout(TURN_TIMEOUT=300s)`。
一个工具批次 + 等待审批超过 300 s，连接被 retire，用户看到"本轮超过最长等待时间…连接已断开"，
而 Core 仍在工作。根因是**超时所有权错位**：turn 预算应由 Core 持有（`max_wall_ms`、逐工具超时），
bridge 只是传输层。

**影响范围**：所有长任务、批量工具、需人工审批的桌面用户；表现为"看起来像崩溃"。

**解决方法**：已解决。删除 `TURN_TIMEOUT`/`PromptTimedOut`，直接 await；取消保留 5 s `CANCEL_TIMEOUT`，
Core 不确认时 `fail_connection` 重置 turn/审批/取消三态；paused time 覆盖 301 s/360 s/跨边界审批。
同批修的还有 `ui_steer` 形状（只回排队数 → 前端 `Boolean(result?.accepted)` 恒 `undefined`，
插话其实成功却提示"降级为排队"），改回 `contract::session::SteerResult`
（`mint/docs/roadmap/2026-10-27-session-disconnect-and-authorization.md`；缺陷单 D-G18）。

#### M-12 上下文预算按"1 字节 = 1 token"估算

**问题背景**：估算器把 1 byte 当 1 token，1 MiB 窗口只能用约四分之一；一次工具密集长会话直接以
"受保护的输入仍需约 931492 token / 输入预算 930611"失败——只差 881 就整轮拒绝。

**影响范围**：所有长会话；用户感受是"聊到一半突然不能继续"。

**解决方法**：已解决。改 `ascii/3 + non_ascii/2`（仍保守，用真实 usage 上调，留 5%）；
超预算时**降级而非失败**：折叠超限工具结果 → 收缩输出预留（下限 2048）→ 丢最老 turn（至少留一个）→ 才拒绝
（`mint/CHANGELOG.md:35`）。

#### M-13 审批语义错位

**问题背景**：三个错位叠加：(a) 审批超时与协议失败被记成"用户拒绝"；(b) 用户级 `full-access`+`never`
静默屏蔽 `--approve none|auto`，`mint chat` 等待审批 180 s 后中止；(c) 子 Agent 被钉成只读，
父会话目录授权不可见，委派任务一律失败。

**影响范围**：所有写操作审批、所有子 Agent 委派。

**解决方法**：已解决。超时/协议失败不计为拒绝，只有显式 always-reject 才记忆；`--approve` 不再被用户级配置覆盖；
子 Agent 继承父级 sandbox policy、读写根、执行模式与规则，父级 session 目录授权只读可见，
子级审批仍收紧（never prompts）（`mint/CHANGELOG.md:22,24`）。

#### M-14 协议缺口：真缺口只剩三条，缺陷单却停在旧状态

**问题背景**：缺陷单记了 12 条运行时缺陷。**核实后发现状态本身滞后**：`D-C7`（`end_session` 从不调用）、
`D-C8`（9 类事件不转发）、`D-C9`（不协商 `protocolVersion`）已在 `f87c099`（R11）修复，
`acp.rs:1432` 注释与 `lifecycle.rs` 的 `acp_shutdown_runs_end_session` 可证；`D-C12`（运行时零 iface 依赖）
也已不成立——`mint/crates/mint-core/Cargo.toml:13` 已依赖 `agentcpm-iface` 并 re-export 契约类型（R01）。
真正未修的只剩：`D-C5`（`_mint/duplex/*` 七个方法只有常量，实现整段被注释）、
`D-C10`（错误码体系失真：会话忙用 `-32004`、steer 队列满用 `-32002`）、
`D-C11`（`loop/step` 缺 iface 必需的 `execution` 与 `budget`，`messages` 用自造 `{role,text}`）。

**影响范围**：按缺陷单判断会重复修已修的问题、漏掉真问题；错误码不统一让客户端无法按 code 分流；
`loop/step` 缺幂等/预算字段，合规插件也无法做幂等判定。

**解决方法**：部分解决。三条真缺口**暂未解决**（D-C5 仅报告，属 F13/双工阶段；D-C10/C11 待修）。
**另一个难点是账本本身**：缺陷单、PRD、README 与代码存在双向漂移（既有"文档说已修、代码没修"，
也有"代码已修、文档没跟上"），见 §5 模式 1。

#### M-15 `std` 制品实为 `core`，`doctor` 报"无问题"

**问题背景**：官方 `0.1.14-std` 的 macOS arm64 制品里 cpmrt 实际编译为 `core`，没编入 js-host。
工程请求 `std`、lock 锁 `0.1.14-std`，但 TUI 启动 `cpmrt acp` 时在 ACP initialize 前退出 7；
TUI 进入 alternate screen 后只显示"内核已退出/EOF"（stderr 被重定向到日志）。
更麻烦的是 `doctor` 已读到 `{"requested_flavor":"std","compiled_flavor":"core","flavor_ready":false}`，
却只展示 version/api/sandbox，`problems=[]` 仍打印"没有发现问题"；`api=?` 是因为读了旧字段 `api`，
运行时实际返回 `abi.api_version`。

**影响范围**：所有按文档请求 `std` 的用户；诊断链路在第一现场给出相反结论，用户与支持人员同时被误导。

**解决方法**：暂未解决。只做了定位，未改产品源码（`workspace/mint-chat-diagnosis-20261030/README.md`）。
方向明确：`doctor` 把 flavor mismatch / `flavor_ready=false` 与 ACP initialize 探活纳入 problems；
且不能把所有 `false` 都判为编译故障（0.1.12/std 的 false 原因是 `host_not_probed`，实际握手可成功）。

#### M-16 嵌套 Seatbelt 与 full-access 让命令全部失败

**问题背景**：`FullAccess` 下 Seatbelt profile 为文件系统根发出 `path-ancestors` 选择器，
而 `sandbox-exec` 无法编译空祖先选择器（`/` 没有祖先）→ 每条命令都在 `sandbox_apply` 失败。
另一层：外层 Seatbelt 已生效时再叠内层，直接 `Operation not permitted`。

**影响范围**：所有切到 full-access 的桌面用户；所有依赖 shell 的任务；易误判为命令本身有问题。

**解决方法**：已解决。profile 不再为根发 `path-ancestors`，受保护密钥路径的尾部 deny 保留；
`nesting_refused()` 只认该内核签名，命中则显式降级并作为 warning Notice 暴露
（`info --json` 的 `sandbox.notice`），并明写"shell 读密钥的内层拦截不生效"；其余失败仍 fail-closed
（commit `06717b5`）。沙箱整体仍是 **Partial**，完整跨平台隔离与任意应用 CUA 未完成
（`mint/docs/roadmap/2026-10-26-runtime-gui-closeout.md`）。

### 2.4 可靠性与并发

#### M-17 出网管控 100% 失效 + principal 可伪造

**问题背景**：原实现"先 DNS 解析再判决"，被拒时连接已建立；身份取自可伪造的 `_meta.principal`
（默认硬编码 `"client"`）。也就是说策略看似执行、实际一条都没拦住。

**影响范围**：所有网络类工具的安全边界；引用该身份的审计与配额判定。

**解决方法**：已解决。统一 `runtime/src/egress.rs`：先判后解析 + DNS-rebinding 复判；
结构守卫测试"`TcpStream::connect` 只许出现在 `egress.rs`"；33 个 `policy_check` 调用点显式传 `RequestCtx`；
只采信传输层 attested principal（commit `286b9d2`）。

#### M-18 执行语义四缺陷、deadline 丢弃、BTL 不读 `job.input`

**问题背景**：三处独立缺陷。`tool.exec`（`52ffe61`）：排队任务取消后仍执行、同幂等键换参数返回旧结果
（未比 `args_digest`）、args 类型静默转换、running 早于后端调用。`model-stream`（`5a8c327`）：
`let _ = deadline_ms`，worker 固定 300 s，超时后迟到结果被当成功。`btl-stdio`（`53149b1`）：
经 kernel 跑的 `cpmrt run --kernel` 恒用 `--prompt`、不读 `job.input`——**答案与用户输入无关**，
由手工复现发现而非测试。

**影响范围**：取消/幂等/超时三类语义在最关键的执行路径上都不成立；BTL 是静默答错，最危险。

**解决方法**：已解决。共享 `AtomicBool` 取消位；`args_digest + principal` 校验 → `-32000 IDEMPOTENCY_CONFLICT`；
非字符串 args → `-32602`；`mark_tool_running` 前置；deadline 写进作业与任务，超时按 unknown 帧 + error 终态且禁重放；
BTL 抽 `job_from_reply` 纯函数（有 input / 缺省或空 / 无作业 三态）并加单测。

#### M-19 `MutexGuard` 跨 `await`

**问题背景**：`for client in self.clients.lock().await.values()` 把 tokio 锁持到每个 `list_tools().await` 结束。

**影响范围**：列工具期间 `add`/`remove` 全部阻塞；并发多 MCP server 时放大为整体卡顿。

**解决方法**：已解决。抽 `snapshot()`（`values().cloned().collect()`），锁外逐个 await（commit `ce0be46`）。

#### M-20 基线 6 红、克隆 target 的 mtime 制造假绿

**问题背景**：三个"环境问题被当成代码问题"的典型。6 条过时夹具（配置格式、`[provides] skills`、flavor 语义）
让 `cargo test --workspace` 总闸 exit=101；总闸还依赖 `web/dist`、`target/gui-resources` 等产物前置；
worktree 用 `cp -Rc` 克隆后产物 mtime 比源码新，cargo 判定新鲜——`cargo test` 绿但 clippy 报
`E0432 AllowTable` 找不到，一度被当成代码缺陷。

**影响范围**：所有人对"全绿"的信任；并行分支越多，假红/假绿越贵。

**解决方法**：已解决。只改 3 份夹具不削弱断言（`4ea5014`/`89f3d9d`/`34cb35d`）；BASELINE 登记产物前置步骤；
`touch` 全部 `*.rs/*.toml/Cargo.lock` 后全量复验，规则写进 BASELINE/COMMON（commit `d08e808`）。

#### M-21 探活写死 minicpm 网关，4 条验收长期全 SKIP

**问题背景**：`model_probe` 只认 `/api/status` 的 `runtime.running`；llama.cpp 没有该端点，
于是真模型用例 H-25/26/27/53 长期全 SKIP——4 条验收形同虚设，却一直显示"跳过"而非"失败"。

**影响范围**：真模型验收形同没有；SKIP 在报表里不如 FAIL 显眼，问题被长期掩盖。

**解决方法**：已解决。404 时回退 `GET /health`，新增 `ReadinessSource`，回包只增 `readiness_source`；
非 404 的非 2xx 仍 NotReady（不猜），回归用例钉住（commit `185b2b2`）。

### 2.5 MintHub

#### H-1 发布非原子：索引重建失败仍返回 200

**问题背景**：制品先写 blob（含 `.sha256`/`.minisig`），再开事务写 PUBLISHED，提交后才重建 `/index`；
重建失败只 `tracing::error!` 后仍返回 200 ok。`written` 收集了 blob 键却在 `:729` 被 `let _ = written;` 丢弃，
失败无补偿/删除（`mint/hub/server/src/service/publish.rs:722-730`）。

**影响范围**：所有 `mint publish` 与随后读 `/index`、`mint add`、镜像 `/-/changes` 的链路；
DB 与索引不一致期间客户端看不到新版本，响应却是成功。只能靠 `mint-hub reindex` 事后补。

**解决方法**：部分解决。索引被明确定义为派生物（`hub/server/src/index.rs:1-2`），`reindex` 全量重建
（`src/main.rs:137-143`），`reindex_reproduces_index_byte_for_byte` 通过
（`mint/REGISTRY_VERIFICATION_COMPLETE.md`）。**补偿逻辑暂未解决**，未排期。

#### H-2 PENDING 版本号黑洞，无清理任务

**问题背景**：占号事务先提交（`service/publish.rs:494-511`），之后崩溃/被杀，行停在 `pending`；
`insert_pending` 只对 `failed`/`yanked`/空 `row_json` 放行重发（`src/store/queries.rs:393-407`），
pending 永久 409 `version_taken`。全仓无 DELETE versions、无周期清理任务。

**影响范围**：发布者遇到一次 Pod 重启/SIGKILL 就永久失去该版本号。05 文档声称的"FAILED 30 天清理、
10 分钟快照签名、每日下载聚合"均无实现，`/-/snapshot.json`、`/-/snapshot/by-hash` 端点也不存在。

**解决方法**：暂未解决。需新增租约/回收任务与快照签名定时器，未排期；当前只能人工改库或换版本号。

#### H-3 签名链只有一层，密钥仪式命令不存在

**问题背景**：`KeysJson` 只有 `{v, keys[]}`，没有 `signatures` 字段（`mint/crates/mint-pack/src/lib.rs:525-543`）；
`Signer::keys_json()` 只输出当前一把 index key、无 expires/revoked（`hub/server/src/signer.rs:96-102`）；
`AppState::init` 每次启动用它覆盖 blob 里的 `-/keys`（`src/state.rs:76-86`）。
文档里的 `mint-hub sign --key`、`update-keys`、`verify-key`、`reindex --dry-run` 在 CLI 中都不存在
（`main.rs:33-75` vs `hub/docs/key-ceremony.md:211-213`）。

**影响范围**：整条信任链。客户端 `check_trust_root` 只判 keys 非空、过期只告警（`bins/mint/src/verify.rs:25-38`），
信任根实际退化为 HTTPS TOFU；换 `MINT_HUB_SIGNING_KEY` 而不 reindex，旧行 keyid 不在 `/-/keys`，
`verify_row` 直接失败——**全量包验签失败**。2/3 根签名、90 天轮换、新旧共存 30 天都无法执行。

**解决方法**：暂未解决。wire 类型缺字段 + 缺离线签名工具，属设计缺口；现有缓解只是 reindex 时按 keyid 差异重签
（`src/index.rs:60-71`）。

#### H-4 tag 三处真源，`set_tag` 对 latest/stable 假成功

**问题背景**：tag 同时存在于 `packages.tags`、`/meta/.../tags.json` 与读时重算（`src/api/units.rs:94-98`、
`src/index.rs:103-111`）。`set_tag` 不拒绝 latest/stable（`src/service/yank.rs:174-198`），
返回体带上用户刚写的值，但随后 `write_tags`→`retag_moving` 又覆盖它（yank.rs:219-223）——响应与落盘相反。

**影响范围**：控制台/CLI 打 tag 的用户；包详情页 `default_version` 用陈旧 `pkg.tags["stable"]`
（`src/api/packages.rs:110-115`），与单元面的实时计算可能给出不同版本——同一 tag 两个答案且无报错。

**解决方法**：暂未解决。V1 语义（`mint/docs/roadmap/2026-10-27-minthub-images.md` §6"latest/stable 不允许手工覆盖"）
未在写入侧落地。

#### H-5 OCI 兼容面形状乖离

**问题背景**：多制品 index 的 mediaType 是自定义 `application/vnd.oci.unit.index.v1+json`
（`crates/mint-pack/src/unit.rs:23`），文档写标准 `image.index.v1+json`；
flavor 被塞进 `platform.variant`（unit.rs:370-378，值 std/lite/core），同 os/arch 多条目在选择时歧义；
错误体只有 `{code, detail}`、缺 OCI 规定的 `message`（`src/api/units.rs:194-198`）。

**影响范围**：`/v2/` 只读兼容面与任何标准 OCI 客户端/podman；白名单校验 mediaType 时直接拒绝，
`variant=std` 非法。属"看起来 200、实际不可互操作"。

**解决方法**：暂未解决。需统一 mediaType 并迁移已发布 digest 语义（改字节 = 改 digest），未排期；
文档与代码孰为准也未定。

#### H-6 大制品全量入内存、无 Range、暂存落 `/tmp`

**问题背景**：请求体先流式落 spool，随后 `tokio::fs::read` 整包读进内存再解码（`src/api/publish.rs:52-77`）；
读路径 `Blob::get` 返回完整 `Bytes`（`src/blob.rs:98-105`），`/dl` 直接把整个制品作为 body
（`src/static_face.rs:128-151`），无 Range/流式/断点续传。cnap 只读根下 spool 只能落 `/tmp`
（`hub/deploy/app.yaml.tmpl:41-44`）。

**影响范围**：200 MiB 级 app/core 制品并发发布或下载时按份数吃内存；`/tmp` 撞 ephemeral storage 会连带影响 Pod；
弱网重试整包。

**解决方法**：暂未解决。需 presigned 直传 OBS + Range 透传，05 §3.3 只列为 V1；当前缓解是
`client_max_body_size 512m` + `proxy_request_buffering off`（`hub/deploy/ea-router-mint-hub.server:25-26`）。

#### H-7 部署面把基础设施缺陷变成发布故障

**问题背景**：OBS 必须 path-style，否则桶名不进主机名；`readyz` 的 blob 探针做写读
（`src/blob.rs:115-125`），Agency 未授 DeleteObject 时旧探针 DELETE 403 → readyz 持续 503 →
release seq13 ROLLOUT_FAILED；桶批下前用 `file:///tmp` 冒烟，Pod 重启制品即丢；
`SERVICE_VERSION` 平台保留旧值，`/healthz` 版本会骗人。

**影响范围**：整站可用性与制品持久性；`/readyz` 是发布门禁，探针写权限缺失 = 发布卡死。

**解决方法**：已解决。强制 path-style；探针改 PUT+GET 并 WARN；切桶前 `MINT_HUB_BLOB_PROBE` 预检
（`hub/deploy/README.md:88,222-223`），seq16 HEALTHY。

#### H-8 半成品接口返回 200 TODO，镜像漏包静默推进

**问题背景**：`/gh/*` 四条路由已挂生产路由表（`src/app.rs:124-127`），handler 恒返回
**200 + `{"status":"TODO(gh-proxy)"}`**（`src/api/gh.rs:19-40`），而 05 §3.6 详述了整套实现。
镜像侧：单包同步失败只 push 到 `errors`，seq 仍推进到最大条目（`src/mirror.rs:296-305`）。

**影响范围**：走 GitHub 代理的客户端拿到 200 当成功、解析失败或静默空版本；镜像漏包后除非 `--full`
或该包再次变更，永久缺失，仅日志可见。

**解决方法**：暂未解决。`TODO(gh-proxy)` 未排期；镜像"跳过并推进 seq"是 D12 有意权衡，缺补齐命令。

---

## 3. Iface

### 3.1 契约形状：从"写出来"到"能被消费"

#### I-1 契约与实现两套类型宇宙

**问题背景**：运行时曾**零 iface 依赖**，同名类型各写一套：`iface-store::EventRecord`、`iface-tool::ToolSpec`
与 `mint-protocol` 同名字段完全不相交；`_mint/loop/list` 与 `cpmrt loops --json` 两套形状且 `executable`
同名不同义。最直接的后果是 `D-C1`：契约 `StepOutcome` 五值是
`advanced/waiting-human/finished/failed/unknown`，运行时只认
`advanced/waiting-human/idle/finished/unknown` 且**不认 `failed`**——**完全合规的插件返回
`{"outcome":"failed"}` 会被判"未知的 StepOutcome"并回落内置 loop**。

**影响范围**：所有按契约实现的第三方 loop；失败语义在真实运行时不存在。

**解决方法**：部分解决。运行时已依赖 `agentcpm-iface` 并 re-export 契约类型（R01，`mint-core/Cargo.toml:13`）；
删掉 `loop_host.rs` 1341 行手抄副本（`2f0e3f8`）；解析层接受 `failed{code,message,stop_reason}`、
`idle` 降级为兼容。但 `loop/step` 仍缺 iface 必需的 `execution`/`budget`（D-C11），
错误码体系仍分家（D-C10）——**暂未解决**。

#### I-2 `iface-loop` 是死契约

**问题背景**：`agentcpm_iface::loop` 在 kernel 内 **0 引用**；唯一"消费方"是运行时自己重定义了一套
`LoopDescriptor`/`StepOutcome` 并已分叉。审计曾以"全仓引用 0"判其"误设、建议删除"，
但同一判据会把 9 个契约里的 7 个一起判死，于是 D75/D76 改为：跨进程 loop 走 L-C `loop/*`，
`iface-loop` 只面向进程内 Rust 实现，不做 wasm 化。

**影响范围**：所有"照 iface-loop 写实现"的第三方；契约描述了一个不存在的世界。
判定本身还反复过一次，下游难以据此决策。

**解决方法**：暂未解决（口径已定）。生产 `impl LoopContract` 仍不存在，适配器在 `.tmp/loop-adapter`；
多轮工具编排在 `rust-core` 未接。已做的是语义等价验证（I-10）与口径收敛
（`packages/kernel-iface/SUBSTITUTABILITY-SCORECARD.md` §4）。

#### I-3 `Kind::Iface` 不可达

**问题背景**：10 个契约包全是 `kind="bundle"`，而 `mint.toml` 注释与 PRD §5.4 都声称用 `Kind::Iface`；
`validate.rs`/`layout.rs` 的 iface 分支无包能走到——代码里有一条永远不执行的路。

**影响范围**：契约包发现路径（`inspect --abilities` 在 0.1.11 还没有）；按 PRD 写清单的下游会被拒。

**解决方法**：暂未解决（仅报告）。需 Mint 决策 + Hub 升级，短期用 `bundle + provides.interfaces` 承载
（缺陷单 D-I2；`DECISIONS.md:1824` 明写"仍是 bundle 过渡"）。

#### I-4 `[requires]` 表达不了 interface 依赖，未知键被静默丢弃

**问题背景**：跨包依赖只能写在 `schema.json` 的自定义 `contract_deps`，无门禁；`Requires` 无
`deny_unknown_fields`，写 `interfaces = [...]` 会被 serde **静默丢弃**——作者以为声明了，解析器没看见。

**影响范围**：所有多包契约组合；安装期完全无感，只在运行期缺类型时暴露。

**解决方法**：已解决（R16/D105）。`Requires` 加 `#[serde(deny_unknown_fields)]`，`interfaces` 升一等字段；
测试 `unknown_requires_fields_are_rejected`、`misspelled_requires_interface_key_is_rejected`。

#### I-5 跨包依赖漂移，出现未声明的 session ↔ store 环

**问题背景**：`iface-store` 声明 `contract_deps: []`，但源码 `use crate::session::NodeId`；
`iface-session/src/identity.rs` 用 `crate::env::EnvId` 也未声明。声明图与真实图不一致，
还形成未声明的 session ↔ store 环。副本 10 个 schema 里还有 5 个根本没有 `contract_deps` 键。

**影响范围**：契约包可组合性；按 `contract_deps` 做拓扑安装/加载的工具会得到错误顺序。

**解决方法**：已解决（R16/D105）。`NodeId` 移入 `iface-types`（`types/node.rs`），环拆成单向；
`contract_deps` 改为按源码 `crate::`/`super::` 真实引用**生成**，与 `mint.toml [requires].interfaces`
**双向核对**——`sync-iface-packages.sh --check` 的 `DEP_UNDECLARED`/`DEP_OVERDECLARED`、`check-content.py`、
`mint iface verify` 的 `schema.contract_deps` 三处同一规则。

#### I-6 契约包单独不可编译

**问题背景**：`BoxFuture` 定义在 `kernel/iface/src/lib.rs:40`（不在分发范围），10 个包的 `src/` 都用到却都没有；
摊平后的 `src/mod.rs` 也不是合法 crate root，`iface-loop/src/` 连 `mod.rs` 都没有。
`PACKAGING-NOTES.md:108-111` 自认"作为独立包并不编译"。mint 只校验目录形状、不编译，
直到用户 `cargo check` 才炸。

**影响范围**：第三方"拿一个包照着实现"，第一步就挂；"可替换"从入口断裂。

**解决方法**：部分解决。**上游已解决**：每包生成 `src/_base.rs`（`BoxFuture` + `ABI_VERSION`/`ERR_*`），
`iface-types` 以外 9 包再生成单包 `lib.rs` + `Cargo.toml`；`cargo check` 10/10
（`DECISIONS.md:1817-1819`）。**本工作区分发副本暂未解决**：`packages/kernel-iface/` 里一个生成物都没跟过来，
10/10 包与上游有差异（详见 I-11）。

#### I-7 `schema.json` 不是 JSON Schema，方法名还与源码不一致

**问题背景**：10/10 声明 draft-2020-12 却是自造键：全部无 `properties`、无 `$defs`；`types` 是字符串数组，
甚至写散文（`iface-store/schema.json:31-33` 的 `"Cursor(u64, 本包内部事件游标)"`）；`traits` 是斜杠串
（`"StoreContract": "append/read/checkpoint"`）。唯一机器读取点只判存在性
（`mint/crates/mint-manifest/src/layout.rs:131-136`）。由此派生命名漂移：`iface-policy/schema.json:46-47`
仍写 `authorize*` / `AuditSink — record`，源码是 `check`/`check_sync`/`check_egress`/`check_delegation`
与 `append`/`append_*`；`iface-session/schema.json:62` 列 `attach`/`detach`，源码无此二法；
`iface-store/README.md:42` 称 `Cursor` 是 `String`，实际 `u64`。

**影响范围**：字段级校验、跨语言 binding 生成、契约 diff 全为零；照文档写实现会编译不过，
代价全部前置给实现者。文件在、能解析，于是"看起来过了"，实际什么都没校验。

**解决方法**：暂未解决（仅报告 D-I7；命名漂移 D-I8/I9/I10 标"待修"）。要不要真 schema 是 Mint/kernel
共同决策；做则要接 `schemars` + `json-schema-diff` 门禁（`kernel-abi-input-20261026.md:28`）。
现有 `sync-iface-packages.sh` 只核对文件字节与依赖，不核对 schema 方法名与源码 trait 是否一致。

#### I-8 消费方坐标失真，"谁在消费契约"不可核

**问题背景**：`consumers` 是人工路径。10 包共 30 条坐标，6 条解析不到真实文件
（如 `kernel/runtime/src/env_codex.rs`、`kernel/runtime/src/tool.rs`，副本与上游都指错），
另 4 条是散文（`"kernel/host（装配入口）"`、`"所有 9 个 iface 模块"`）。
上游甚至把缺口写进机器字段：`iface-loop/schema.json` 的 `consumers` 第一条是整句
"Rust L-A 生产调用点未找到…不表示 dead contract"。

**影响范围**：全部契约"生产消费点"的证据链，直接决定可替换性判定（"接了缝 ≠ 有人用"）。
路径写错不报错，审计结论因此不可复现。

**解决方法**：暂未解决（D-I11 待修）。只在文档层补正，没有"消费者可解析性"门禁，答案只能 grep 现算。

### 3.2 可替换性与分发

#### I-9 8/8 契约有生产接缝，过程中修了 7 个真问题

**问题背景**：判定标准四条缺一不算：生产路径有 `dyn` 接缝、至少 2 个实现、有"同一调用方跑两实现"的可执行测试、
装配点在组合根。逐条核对发现契约面远小于宿主真实能力面（store 3 vs 12 方法），
**宿主对 8 个契约引用为 0**——契约写了但没人接。

**影响范围**：整个"可替换"叙事；宿主不消费，契约只是文档。

**解决方法**：已解决。8/8 有生产 `dyn` 接缝 + 替换测试（`iface-loop` 例外）；修掉 7 个真实问题：
契约面不足、宿主 0 引用、`session.deliver` 的 epoch 围栏从不执行、`LeaseGate` 每进程一次性缓存导致换手要重启、
exec-host 有一份更弱的重复实现、fire-and-forget 丢弃契约 future、`StepSemantics` 表达不了真实粒度
（新增 `HostRoundtrip`）。门禁 `check-replaceability.sh` 抓到过 2 次装配点泄漏，最终 allowlist 清零
（`kernel/docs/notes/kernel-iface-substitutability-final.md` §5–§6）。

#### I-10 语义等价：判据可信，但分母只有 8/22 与 5/40

**问题背景**：loop 契约要被第三方实现，"看起来一样"不算数。判据是同一批输入下契约驱动与原生 `drive_turn`
的 canonical trace 零差异，且比较器本身不能永远绿。问题在分母：scorecard 只覆盖 8 个原契约，
而契约面已 22 个 trait；loop 等价只跑 5/40 场景，因为 `StubHost` 是单元结构体、响应写死、
`HostModelTurn` 自陈"不声称 AgentLoop parity"；更根本的是 `LoopEvent` 只有 `{seq,kind}`，
载荷只能**绕过契约**从宿主交互取，"无损"仅指驱动层。

**影响范围**：所有"可替换性成立"的强度。不是静默失败，是"绿但窄"。

**解决方法**：部分解决。判据落地、负面控制（漏发 `tool.result`）2/5 且精确命中 `trace[8]/[9]`，
证明比较器可信；正例 5/5 零差异。**暂未解决**：补齐 40 条要接 rust-core 多轮编排 + PilotDeck 语义宿主，
`kernel-loop-equivalence-report.md:146` 明说"缺的是宿主能力而不是契约"；真实模型回归还出现过
"目标工具调用数 0"的失败记录（判失败、未改 SKIP）。

#### I-11 上游快跑 + 分发副本落后一代，README 却称"逐字节相同"

**问题背景**：契约权威源是 `kernel/iface/src`，分发靠"复制快照"而非"生成—校验"。
`packages/kernel-iface/README.md:3-6` 称每包与上游"逐字节相同"，但实测 `diff -rq` **10/10 包有差异**：
副本缺 `src/_base.rs`、`src/lib.rs`、`Cargo.toml`，缺 `iface-types/src/{node.rs,lineage.rs}` 与 `kit/`；
副本 `iface-types` 是 0.1.0，上游已 0.1.1，而 `iface-session/mint.toml:20` 精确钉 `=0.1.1`。
副本停在 R13 之后、R16 之前的中间态（`iface-loop/src/loop_.rs:40-46` 已有新载荷，`types` 却缺 `node.rs`）。

**影响范围**：全部 10 包与"第三方拿包—实现—编译"整链；也是唯一"文档明确说已做到、实测为假"的项。
装出的闭包版本对不上，行为与源码不一致。

**解决方法**：部分解决。上游已有 `scripts/sync-iface-packages.sh --check` 逐字节核对（`PKG DIFF`/`PKG MISSING`），
`coverage total=62 mapped=53 uncovered=0`、`--self-test 16/16`（`DECISIONS.md:1793-1830`）；
hub 制品也应改以 release tag + commit 为准（`F-upstream-delta-2026-10-29.md` F.1）。
**本工作区副本暂未重新同步**，那句"逐字节相同"今天为假；上游 0.1.0 制品也仍落后。

#### I-12 门禁自身有 bug，逼人刷基线

**问题背景**：`check-iface-api` 只比整行指纹，给既有 struct 补 `#[non_exhaustive]` 被判破坏性变更，
与 PRD"先收窄再加字段"两步法直接冲突；新增 trait 的方法曾被误报 13 条 FAIL；
同名不同义类型（`projection::SessionStatus` vs `handoff::SessionStatus`）按名字归并指纹后误报 8 条。

**影响范围**：门禁从"防退化"变成"逼人改基线"——一旦刷基线，门禁就失去意义。

**解决方法**：已解决。仅当 `ne=0→1` 且余行全同时降为 WARN，自测样本 9→11（`51dd31a`）；
新增 trait 方法误报修复（`af3f685`）；`projection` 侧改名 `SessionStatusProjection`，fail 8→0（`ed50b3d`）。

#### I-13 epoch 围栏漏 `target_session`

**问题背景**：`dispatch` 的围栏 hook 只读 `params.session_id`，而 `session.deliver` 的会话字段是 `target_session`，
于是该方法的围栏**从未执行**——旧推进者仍能投递（违反 D56），且报 `-32017` 而非 `-32010`。
跨 node 端到端实测才发现。

**影响范围**：跨节点会话交接的租约语义形同虚设；单机测试全绿。

**解决方法**：已解决。`fenced_session = session_id ?? target_session`，新增 H-40 三条断言（`fcdc19b`）。

#### I-14 版本协商机制在，分发链上是空的

**问题背景**：L-A 机制其实齐了——`ContractMeta`/`ContractDescriptor{name,version,capabilities}`/`is_compatible`/
`require_capabilities`，宿主启动期 fail-closed（`kernel/host/src/startup/contract_check.rs`）；
L-C 有 `abi_min` 逐方法校验（`transport/dispatch.rs:191-204`）。缺的是分发侧：
`provides.interfaces` 只透传不校验，`requires.interfaces` 长期不存在。
`D101`（`DECISIONS.md:1636-1651`）为保证线上可发布，**主动移除本批清单中的新增接口版本映射**，
并写明"旧 Hub 不因此具有新增的接口 ABI 版本校验能力"。

**影响范围**：第三方"声明实现 iface-env@0.1"无人能验证；解析成功、安装成功、语义不对。

**解决方法**：暂未解决。上游部分已解决（`Requires` 加 `deny_unknown_fields` + 依赖双向核对 + `mint iface verify`），
分发侧受制于线上 Hub 旧解析器拒收新字段。

#### I-15 10/10 契约包 `SKILL.md` 缺 frontmatter，装机即报错

**问题背景**：契约包改用 `kind="bundle"` 后，每个包都补了一份 `skills/<包名>/SKILL.md`——但 10 份都以 `#`
开头，缺 YAML frontmatter，而 loader 要求 `description` 字段。`iface-env` 还同时存在根 `SKILL.md`，
bundle 读的却是 `skills/` 下那份，于是"装机成功"之后技能加载直接报错。

**影响范围**：所有装契约包的用户；错误发生在安装后的加载阶段，`mint pack`/`inspect` 不拦，属"装上了才炸"。

**解决方法**：暂未解决（D-I6 待修）。需改 10 个 `SKILL.md` 的 frontmatter，并用 `mint pack` /
`mint inspect --abilities` 复验（`mint/docs/contract/2026-10-28-cpmrt-iface-defects.md:35`）。

---

## 4. 应用侧

> 范围：把能力做成 Mint 包/插件 → 经 Mint 安装进运行时 → 在 GUI/TUI/宿主里被 Agent 使用，
> 以及应用成品（`kind=app`）的构建与验收。样本：`rsi-toolkit`、`ql-audit`、PilotDeck。

#### A-1 宿主能力面异构，适配器进程内、不可分发

**问题背景**：同一套 RSI 要在 Claude Code / Codex / DeepSeek Harness / PilotDeck / Mint 上跑，能力面完全不同：
Claude 用 `UserPromptSubmit` 返回 `additionalContext`（>10k 字符转文件）；Codex 有 13 类 hook，但默认上下文阈值
约 2500 token、SessionEnd 最多 3 秒，且**含生命周期 hook 的插件不符合公共插件目录上架条件**；
DSH 是 `agent/pre-step` waterfall（每步都可能触发，含空消息续跑），持久化 zstd JSONL 格式 V4 而 README 还是 V3，
headless JSON 还有 8 KiB/32 KiB/深度 64 的截断。更根本的是适配器**进程内**：每接一个宿主都要改核心并发版。

**影响范围**：所有跨宿主接入；"装到各处"不成立，宿主升级即静默破坏采集。

**解决方法**：部分解决。方向是 out-of-process `rsi.harness/v1`（stdio JSON-RPC 或 HTTP）+ 能力握手 + 版本协商 +
conformance kit；首发收窄到"MCP 通用接入 + 一个自有宿主深适配 + 一个外部宿主验证"。
**协议本身暂未实现**（`docs/dev/rsi_toolkit/2026-10-27-host-hooks-and-adapter-review.md` §2；
`2026-10-27-pluggable-plugin-and-experience-feasibility.md` G2、§7.2）。

#### A-2 能力/评测/经验契约缺失

**问题背景**：差距 G3（经验面缺失）、G4（数据集/评测契约缺失）、G5（LLM-as-judge 缺失）叠加：
模式一（用户自己的数据集做评测）只能写 Python；模式二（日常轨迹学习）连数据结构都没有。
另有 G6（多轨迹支持度门槛）、G7（主动触发）、G8（召回质量与作用域）、G9（多宿主打包与许可）、
G10（多项目路由）。

**影响范围**：从"给开发者用的工具"到"给业务用的产品"的整段；也是"越用越好"无法证明的根因。

**解决方法**：部分解决。已冻结 `rsi.tasksuite/v1` + `rsi.evaluator/v1` 意图，judge 校准、分歧报告、
小样本不晋升写进风险缓解；P1 先做"用户数据集 + 确定性 verifier + LLM judge"闭环，P2 再做经验面。
judge 校准集与召回收益的 holdout 证明**暂未解决**。

#### A-3 基础库包没有装配协议，应用只能自造 bootstrap

**问题背景**：Mint 的 `[dependencies]` 只负责安装，没有跨包 import 契约。7 包路线（4 基础库 + 2 能力 + meta）下，
能力包必须自己定位并注入 4 个库：读 `mint.lock` → 校验包名/版本 → 校验 `integrity` h1 → 校验 `exports.json` API
→ 动态 import；工程根还得从安装路径反推（`apps/plugins/ql-audit/integrations/mint/src/binding.mjs:17-77`、
`src/project.mjs:6-12`）。

**影响范围**：所有 `mint add` 用户；失败多为显式（`PROJECT_ROOT_REQUIRED`/`CONFIG_REQUIRED`），
但 GUI 启动无终端可看。路径形状被硬编码为 `.mint/packages/<scope>/<name>@<ver>/dist/index.mjs`，
布局一改即 `CONFIG_REQUIRED`。

**解决方法**：已绕过。装配确实能起来（`workspace/offline-ql-test/mint.lock:75-160` 七包均带 h1，
`.mint/audit/egress.tsv:39-46` 有 `mcp.spawn:bundle`）；强制 `allowed_roots` 兜底。
**Mint 侧装配协议暂未解决**。

#### A-4 装上后运行环境断裂

**问题背景**：ql-audit 实测踩坑五连：(1) `capabilities.env` 在 bundle 上被拒；(2) `.mcp.json` 的 `${HOME}` 不展开；
(3) 包内 `certs/*.pem` 让 `mint pack` 失败；(4) `command: node` 在 CLI 下可用，改 `$PKG/bin/...` 后子进程 PATH
不含 nvm；(5) 默认数据目录 `$PILOT_HOME/ql-audit` 在 Mint 下会读到 **PilotDeck 的生产数据**。

**影响范围**：所有"一次开发、两个发行形态"的应用；(5) 是数据串用，用户无感但污染生产。

**解决方法**：已解决（逐条兜底）。启动器搜索 nvm/Homebrew/`/usr/local` 并给可行动错误；数据目录改 `~/.mint/ql-audit`，
测试用 `QL_AUDIT_DATA_DIR`；证书改 `.crt`；配置走"数据目录默认 + `config.json` 0600 原子写 + Keychain"
（`docs/architecture/2026-10-30-ql-audit-mint-plugin.md` §11.1 踩坑 1–7）。

#### A-5 工具注册静默失败：装上了，会话里没有

**问题背景**：0.1.0 只有 `provides.mcp_servers` 标签、无包内 `.mcp.json`，Core 不启动服务；
模型只能说"我没有这个工具"，用户无法区分装错/未启用。

**影响范围**：所有按 0.1.0 形态安装的用户；典型静默失败。

**解决方法**：已解决。0.1.1 起两个能力包自带 `.mcp.json`（只声明 `exec=["node"]`），实测自动注册
（`apps/plugins/ql-audit/docs/progress.md:11,15`）。遗留：设计要求的 `server/discover` 直接带 `tools`
未验证，已发布版对 discover 返回 `-32601`，靠 `initialize`/`tools/list` 回退（`.../src/server.mjs:218-222`）。

#### A-6 工具 schema 缺根类型 → 模型网关 400

**问题背景**：`job_get` 参数 schema 只写根 `oneOf`、缺 `type:"object"`；LLM-Center 对任何携带该工具目录的请求
直接 400，Mint 又隐藏上游错误体。界面只显示"模型错误"。

**影响范围**：整轮对话不可用；工具根本没被调用，属完全静默。

**解决方法**：已解决。补根对象类型并保留 `oneOf`（`.../src/server.mjs:12-20`），最小在线请求 400→200；
0.1.2 已发布，69/69 测试 + 真实模型两个 health（`apps/plugins/ql-audit/docs/release-0.1.2.md:7-19`）。

#### A-7 审批按工具名猜类型，"命名即体验"

**问题背景**：审批器只对名字含 `get`/`list` 的只读工具免审批。`ql_load_bill`/`ql_preflight`/`health`/
`extract_rules` 因名字不含这两个词被判 Other，每一步都弹审批；`ql_list_versions` 不触发。
headless 下实测两个 health 均 `reject_once`，`shell_exec` 也被拒。

**影响范围**：所有应用的工具设计；功能相同的两个工具，只因命名不同，体验差一个数量级。

**解决方法**：暂未解决。设计层靠命名规范（只读工具一律 `get_/list_`），plan-a 照做并通过测试；
已发布版仍叫 `health`。根治需 Mint 支持 `annotations.readOnlyHint`
（`docs/architecture/2026-10-30-ql-audit-mint-plugin.md` §9 风险 5、§11.1 踩坑 6）。

#### A-8 60 s 工具超时 / 50 MB 上传，只能作业化

**问题背景**：MCP 单请求 60 s 兜底、只保留 text、上传 50 MB；而制度 PDF 解析要 10 分钟。

**影响范围**：所有重 IO 应用（审计、解析、批处理）；同步实现会"调用了但拿不到结果"。

**解决方法**：已绕过。已发布版全 job 化：`extract_rules`/`audit_message` 快速返回 job，`job_get` 推进，
先落盘再远端（`apps/plugins/ql-audit/docs/design.md:22-26`）。代价是模型要学会轮询 job；
plan-a 仍同步 `ql_run_audit`，是 A 方案的实质失败点（`ql-audit-plan-a/README.md:89-95`）。

#### A-9 多包版本漂移 + base 单点 + base 定位失败

**问题背景**：ql-audit 拆 base/policy/review/meta 四包，policy/review 是薄包、依赖 base 的共享模块。
base 与薄包版本不匹配则行为不一致；base 是单点，bug 同时影响两个能力；启动器要在同 scope 同级目录里
用 `sort -V` 找 base，找不到就 127。

**影响范围**：所有多包组合应用；版本漂移静默（装得上、跑起来不对）。

**解决方法**：已解决。四包 lockstep + `=0.1.0` 精确锁；发布 train + 契约测试校验四包版本一致；
base 定位失败给 127 + 可行动文案，`QL_AUDIT_BASE_DIR` 供测试；base 独立测试/可回滚
（`docs/architecture/2026-10-30-ql-audit-mint-plugin.md` §9 风险 16/17/20、§10.1 决策 7）。

#### A-10 大证据反噬：869 KB status 打断 review

**问题背景**：两个实验的最终 Mint review 都因完整 status 超出模型上下文收到 HTTP 400，而实验本身已终态
（869117 字符）。编排层 summary 变 `failed`，但同文件 `decision`/执行数齐全——下游只读 status 会误判"实验无效"。

**影响范围**：证据越完整越难审查，正好撞上 RSI 主打的"可审计"。

**解决方法**：已解决（有代价）。默认 status 压到 ≤20000 序列化字符，返回截断标记与 durable cursor，
`compact=false` 取全量；原始证据不裁剪；只读恢复流程的导出与原始逐字节一致；原始失败 summary 故意不改写
（`docs/dev/rsi_toolkit/mint-rsi-iteration-review-2026-10-27.md:29-32,92-100`）。

#### A-11 长任务没有增量事件，进度只能一次性拿全

**问题背景**：`design.md:99-111` 设计了 `events(execution_id,cursor)`/`collect()`，落地契约只有同步
`execute(request, cancel_event)`（`service/connectors/common/host.py:15-18`），事件随结果一次性返回；
MCP bridge 只转发 `list_tools`/`call_tool`，不转发 server notification，进度没有下行通道。

**影响范围**：长任务（WorkBuddy office 单题 866.94 秒）期间，GUI/TUI 里的 Agent 与用户看不到任何进展。
不报错，只是无反馈。

**解决方法**：暂未解决。`rsi.host/v1` 是"一次同步执行、缺终态即失败"的模型，改成事件流要重写 Controller 的
run 生命周期与发布前漂移复核；当前用 bounded status 轮询（≤20000 字符、持久游标）替代
（`plugin-architecture.md:161`；`mint-rsi-iteration-results-2026-10-27.md:81`）。

#### A-12 评测归因失败：同一 Skill 0/3 与 3/3 并存

**问题背景**：WorkBuddy 候选在 construct 得 0/3，在后续全新执行得 3/3，基线审计也 3/3；Job-Bench 候选
construct 6/52、select 0/52。执行方差大于干预效应；construct/select/audit 还是同一任务的三个副本，
不是独立任务族；同模型裁判还有 self-preference。

**影响范围**：任何想从"分数涨了"推出"Skill 有效"的人；控制器仍输出 NEEDS_REVIEW，外部容易读成"验证通过"。

**解决方法**：暂未解决。已做的是不越界声明：select 平局保基线、audit 退化保基线、样本不足恒 insufficient，
把"审计未退化"与"审计提升"分写（`controller.py:646-648`；`acceptance.md:27-29`）。
真结论需多任务族配对统计，成本远超本轮预算。

#### A-13 `loaded=unverified`：发布成功无法证明宿主已加载

**问题背景**：服务只原子替换一个项目 Skill 文件并提交 release，`loaded` 恒为 `unverified`；
外部 smoke 成功也不回写。缺可靠的宿主加载回调，文件写入与行为生效是两类证据。

**影响范围**：所有把"发布"当完成信号的用户/自动化；台账看着成功，宿主可能仍在用旧 Skill。

**解决方法**：部分解决。拆三段证据——台账 applied、外部原生新会话读取、业务 smoke 分数（发布后两宿主均 1.0；
回滚负控后 Mint 0 / PilotDeck 1，差异照实保留）。字段保持 `unverified` 属有意的"不造假"。
多文件原子发布与同用户外部写者竞争**暂未解决**（`plugin-architecture.md:126-128`）。

#### A-14 审计证据链被降级

**问题背景**：设计 §6.3 要求 `.audit/events.jsonl` append-only、写失败 fail-closed；实际全仓无 `events.jsonl`，
plan-a 也自认"留痕写失败不阻断主结果"。替代物只有内容寻址产物 + `config_digest` + ruleset digest。

**影响范围**：无法证明"审的是哪份规则、哪次调用"；企业合规场景的前置条件。

**解决方法**：暂未解决。无事件流、无哈希链、无 verify；设计中的 append-only 语义未落地
（`apps/plugins/ql-audit-plan-a/CONTRACT.md:160`、`.../src/compose.mjs:31-40`）。

#### A-15 应用成品 `kind=app` 交付链未闭环

**问题背景**：目标链路是"外部源码 → 固定 revision → Mint agent 工程 → build/release → `kind=app` 制品 →
安装后 conformance"。实际：PilotDeck 只登记本地 checkout 与固定 revision，
`conformance/applications/pilotdeck/README.md` 仍是"预留……验证"占位；StaffDeck 未连接；
Mint 源码仓库也未连接（`workspace/projects.yaml` 里 `mint` 的 `path: null`、`status: pending-connection`）。

**影响范围**：应用侧"可交付成品"这一层；目前能证明"包能装、工具能调"，不能证明"成品能装、能升级、能卸载"。

**解决方法**：暂未解决。链路与判据已写清（`docs/architecture/package-layout.md`），真实构建/安装/conformance
还没有一次完整记录；`mint.toml` 仍用 `0.1.0-dev` + `kind="agent"` 表示未发布。

#### A-16 打包器排除 `node_modules`、拒 `*.pem`

**问题背景**：`mint pack` 排除 `node_modules`，而 bootstrap 依赖 `@iarna/toml`+`semver`；包内 `certs/*.pem`
让 pack 直接失败（"不得打进文件 certs/qlengine-ca.pem"），改 `.crt` 后通过。

**影响范围**：所有带 Node 依赖或自带 CA 的应用（内网 endpoint、自签证书）；装完起不来或发布被卡。

**解决方法**：已绕过。esbuild 把依赖打进 `dist`（`dist/capability.mjs` 158 KB 自包含），构建走 allowlist；
CA 用 `.crt`，CI 加检查。打包规则本身**暂未解决**（未区分公钥/私钥，也未提供 node_modules 的替代方案）。

---

## 5. 横切模式（比单条难点更值得复用）

1. **账本与代码双向漂移**。既有"文档说已修、代码没修"（M-2 的 Hub 侧、H-3 的仪式命令），
   也有"代码已修、账本没跟上"（M-14 的 D-C7/C8/C9、D-C12；I-11 的"逐字节相同"）。
   后者更危险：它让人重复修已修的问题，并让"缺陷单"从工具变成噪声。解法是**状态必须有可执行判据**
   （门禁/测试），不能只靠人工勾选。
2. **声明与证据分离，用等级而非形容词描述能力**。RSI 用 L0–L4 + 五标签（installed / executed / captured /
   injected / loaded-verified），缺一项只声明已达等级（`docs/architecture/rsi-toolkit-design.md:397-407`）；
   平台矩阵对三家宿主明写"能力具备、适配器未实现"；验收文档单列"公开边界"。这是对 M-2、I-11、A-13 的通用解。
3. **降级而不伪造：宁可 null 也不填 0**。`normalize_result` 对缺失终态/身份一律改 `result_unknown`；
   verifier 返回 `unscored` 时保留 reason、执行 completed 但无分；`unscored` 与 `task_failed` 分开。
4. **静默失败比报错更贵**。serde 丢 `interfaces`（I-4）、`filter_map` 丢无标题会话（D-G15）、
   `doctor` 在 flavor 不匹配时打印"没有发现问题"（M-15）、收据解析失败即跳过渠道门（M-7）、
   工具没注册（A-5）、schema 缺根类型（A-6）、`/gh/*` 200 TODO（H-8）——共同点是"用户以为成功了"。
5. **同一事实多真源**。300 s 超时在 Rust 与 curl 各写一份（D-G7）、32 MiB 文案与 `MAX_BYTES` 各自维护（D-G16）、
   tag 三处（H-4）、`/-/keys` 每次启动被覆盖（H-3）、spec 客户端与内核各有一套 `SessionStatus`（I-12）。
6. **门禁自己也会坏，也会假绿假红**。`ci/check-gui.sh` 因 fmt 失败、`ci/check.sh` 因 `redundant_clone` 失败
   （D-G1/D-G6）；`check-iface-api` 误报逼人刷基线（I-12）；基线 6 红让总闸 exit=101、mtime 让 cargo 假绿（M-20）。
   门禁需要被测试。
7. **"构建/测试通过 ≠ 可用"**。74 MB 二进制不等于 V8 插件可装载；jsdom/preview 不等于 native GUI；
   fake provider 不等于真连；69 条 mock 测试不等于有真实 PDF 闭环。验收必须分层记账
   （pureunit / fake / localrealcore / nativeGUI / realAPI），旧结果不能替代新制品。
8. **参数看起来生效其实没生效**。`--reasoning-budget 0` 对 MiniCPM5 的 chat template 无效、
   固定 system prompt 会让它改写答案；`deadline_ms` 解析后被 `let _ =` 丢掉（M-18）。
   只有真模型/真链路能证伪。

---

## 6. 仍未解决清单（按影响排序）

| 优先级 | 事项 | 类别 | 现状 |
|---|---|---|---|
| P0 | `std` 制品实为 `core`，`doctor` 报"无问题" | Mint | 已定位，未改代码 |
| P0 | 引导安装无签名 + 制品 `.minisig` 可静默降级 | Mint | 仅边界缓解 |
| P0 | 收据字段 `installed_at/at` 错位，self-update 渠道门失效 | Mint | 写端已改，读端未改 |
| P0 | 应用成品 `kind=app` 交付链未闭环 | 应用侧 | conformance 占位 |
| P1 | 签名链只有一层，密钥仪式不可执行 | MintHub | 设计缺口 |
| P1 | 发布非原子 + PENDING 黑洞 | MintHub | 索引可 reindex，占号无回收 |
| P1 | 发行批次不闭合（stable 组合出不可安装版本对） | Mint | 只有手工绕行 |
| P1 | 分发副本落后上游一代，README 称"逐字节相同" | Iface | 上游已修，副本未同步 |
| P1 | `Kind::Iface` / Hub 索引不支持契约包 | Mint/Iface | 仅报告 D-I2 |
| P1 | `iface-loop` 无生产实现 | Iface | 实验区适配器 |
| P1 | `schema.json` 不是真 schema + 方法名漂移 | Iface | 仅报告/待修 |
| P1 | 消费方坐标失真，可替换性证据链不可复现 | Iface | 待修 D-I11 |
| P1 | 版本协商分发侧为空（D101 撤回映射） | Iface | 受制于 Hub 旧解析器 |
| P1 | 跨宿主 harness 协议未实现 | 应用侧 | 只有设计 |
| P1 | 长任务无增量事件 | 应用侧 | 只有 bounded 轮询 |
| P1 | 评测归因失败（样本/任务族不足） | 应用侧 | 只做"不越界声明" |
| P2 | `cpmrt` 与 `mint-core` 名称不一致 | Mint | 待兼容发布 |
| P2 | Hub 侧档位默认仍 `core`、`flavors` 为空 | Mint | 未排期 |
| P2 | Mintfile/打包器 lock 布局契约漂移 | Mint | 删字段绕过 |
| P2 | 同版本异制品无拒绝规则 | Mint | 流程层已冻结 |
| P2 | tag 三处真源、`set_tag` 假成功 | MintHub | 未排期 |
| P2 | OCI 形状乖离、无 Range、全量入内存 | MintHub | 未排期 |
| P2 | `/gh/*` 返回 200 TODO、镜像漏包静默 | MintHub | 未排期 |
| P2 | 审批按名字猜类型 | 应用侧 | 需 `readOnlyHint` |
| P2 | 审计 `events.jsonl` 未落地 | 应用侧 | 设计降级 |
| P2 | 10/10 `SKILL.md` 缺 frontmatter，装机即报错 | Iface | 待修 D-I6 |
| P2 | 打包器按扩展名拒 `*.pem`、排除 `node_modules` | 应用侧 | 已绕过 |

---

## 7. 证据索引

- 缺陷单（最集中，但注意状态已滞后）：`packages/agent-kernel/mint/docs/contract/2026-10-28-cpmrt-iface-defects.md`
- 桌面端根因：`packages/agent-kernel/mint/docs/roadmap/2026-10-27-session-disconnect-and-authorization.md`
- 发布与验收：`packages/agent-kernel/mint/docs/roadmap/2026-10-26-runtime-gui-closeout.md`
- 变更记录：`packages/agent-kernel/mint/CHANGELOG.md`、`CHANGELOG-ABI.md`
- 平台事实与实测：`docs/dev/rsi_toolkit/2026-10-28-mint-platform-notes.md`
- 文档口径审计：`docs/mint/2026-10-28-文档口径审计.md`
- 可替换性：`packages/kernel-iface/SUBSTITUTABILITY-SCORECARD.md`、
  `packages/agent-kernel/kernel/docs/notes/kernel-iface-substitutability-final.md`
- 上游复核：`docs/dev/rsi_toolkit/iface-review/F-upstream-delta-2026-10-29.md`
- 应用侧实测：`docs/architecture/2026-10-30-ql-audit-mint-plugin.md` §9/§11、
  `workspace/mint-chat-diagnosis-20261030/README.md`
- 宿主能力核实：`docs/dev/rsi_toolkit/2026-10-27-host-hooks-and-adapter-review.md`
- MintHub：`packages/agent-kernel/mint/hub/server/README.md`、`hub/docs/key-ceremony.md`、
  `hub/deploy/README.md`、`mint/REGISTRY_VERIFICATION_COMPLETE.md`
