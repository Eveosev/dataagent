# ql-audit 模块化：两版方案对比

> 日期：2026-10-30  
> 对比对象：
> - **A（本仓方案）**：[ql-audit → Mint 插件：调研与实施方案（模块化拆分）](../../architecture/2026-10-30-ql-audit-mint-plugin.md)
> - **B（另一版提案）**：[ql-audit 接入 MintHub：模块化优化方案](2026-10-30-minthub-modular-proposal.md)

## 0. 结论

**两版不是同一层级：A 是“3 周内可发布的运行时拆分”，B 是“可被其他插件复用的领域平台”。**

- 如果目标是把两个能力尽快装进 MintHub，并满足已确认的“对话改配置、本地持久化、RSI 不暴露”，**选 A**；但必须补 B 指出的两个关键点：**RuleSet 文件交接**与 **`trueMeans/action/gates` 语义**。
- 如果目标从第一天就是“其他 MintHub 插件也能复用规则核心、引擎客户端、任务产物”，**选 B**；但要先做 bootstrap/preset/env 的 M0/M1 spike，预算按 **6–10 周+**，不能按 3 周排。
- 我的建议是 **A 作为 v0.1，吸收 B 的契约与 RuleSet 思想；v0.2 再抽 B 的独立库包**。不建议首版直接上 7–8 个包。

## 1. 两句话

**A：4 个包、3 个 MCP 服务。**
`base` 是唯一运行时，带 6 个配置/目录工具；`policy`、`review` 是薄包，启动器定位 base，用组参数复用同一份 `server.mjs`；`lingcai/ql-audit` 是无 MCP 的组合包。共享 `~/.mint/ql-audit` 与现有 catalog/version 模型。

**B：7–8 个包、2 个 MCP 服务。**
`ql-audit-iface`、`ruleset-core`、`qlengine-client`、`task-artifacts` 是不启动进程的基础库；`policy-extract`、`message-audit` 各自带 MCP 入口，通过自定义 bootstrap 从 `mint.lock` 解析并注入库依赖；`ql-audit` 是 `preset`。规则以不可变 RuleSet 文件 + digest 交接，两个能力各自持有数据目录。

## 2. 结构对比

| 维度 | A：4 包 | B：7–8 包 | 判断 |
|---|---|---|---|
| 包数 | 4 | 7（最小主线）/ 8（含业务 profile） | A 少，发布/维护简单 |
| MCP 服务 | 3：base、policy、review | 2：policy_extract、message_audit | B 更贴近“只有两个能力” |
| 基础包是否对模型可见 | 是，base 6 个工具 | 否，基础库不注册工具 | B 工具面更干净 |
| 业务工具数 | 14 | 约 8（5 + 3） | B 更聚焦；A 多出配置/目录工具 |
| 共享方式 | 同一运行时 executable，组参数切换 | ESM 库 + 自定义 bootstrap 注入 | A 简单；B 更可复用 |
| 规则交接 | 本地 catalog + `version_id` | 不可变 RuleSet 文件 + `ruleset.digest` | B 可跨工程、可校验 |
| 数据目录 | 全局 `~/.mint/ql-audit` | 按能力/工程 `.ql-audit/policy-extract/`、`.ql-audit/message-audit/` | B 隔离好；A 方便全局版本列表 |
| 跨工程审核 | 不支持 | 支持（传规则文件） | B 明显更强 |
| 契约 | 现有 `ql-audit.catalog/v1` + `CONTRACT.md` | 新增 `ql-audit-iface` 领域契约 + conformance fixtures | B 更严格 |
| 语义修正 | 继承现有审核语义 | 显式 `trueMeans=violation\|compliant`、`action`、`gates[].expect` | B 更正确；A 有缺口 |
| 配置方式 | 对话工具 `ql_get_config`/`ql_set_config` | 环境变量/配置文件；未列对话工具 | A 符合已确认需求；B 需补 |
| 组合方式 | bundle meta（无 MCP，有总 SKILL） | preset（无 MCP，无总 SKILL） | 两者都可行；preset 更语义化，meta 可带总 skill |
| 版本 | 4 包 lockstep + exact pin | 基础包独立 semver + API/RuleSet schema | B 灵活但矩阵大 |
| Mint 0.1.14 证据 | 已做多包/3 服务/meta/preset POC | preset 机制已在本机 POC 验证；B 的 7 包 bootstrap 未验证 | A 证据更足 |
| 估算 | 约 14 个工作日 / 3 周 | 约 6–10 周+（1 人，按模块粗估） | A 适合先上线 |

## 3. 关键差异

### 3.1 进程与工具面

A 的 base 是一个真实的 MCP 服务，因此装 policy 时也会看到 `ql-audit-base__*` 的 6 个工具。好处是配置、健康、版本/场景/规则查询只实现一次；代价是“第三组工具”出现在用户面前，严格说不是“只有两个能力”，而且工具全名较长（SKILL 更啰嗦）。

B 把基础能力做成库，不启动服务、不注册工具；模型只看到 `policy_extract__*` 与 `message_audit__*`，更符合“两个能力”的产品表达，工具名也更短。代价是配置入口没有着落：B 没有 `ql_get_config`/`ql_set_config`，而这是你已经确认的需求；要满足它，B 要么增加第三个配置服务，要么在两个能力里重复注册配置工具，两者都会破坏“只有两个服务”的简洁性。

**结论**：如果“两个能力”指模型可见工具面，B 更纯；如果包含“对话改配置”，A 更完整。

### 3.2 规则交接

A 的 policy 把规则追加进共享 `catalog.json`，review 用 `version_id` 读取。优点是复用现有实现、版本列表自然；缺点是 review 依赖 policy 进程的本地状态，跨工程/跨机器要复制整个数据目录，且无法用 digest 证明“审核用的是哪份规则”。

B 让 policy 产出不可变 `ruleset.json`（含 schema、来源、字段快照、digest），review 直接接收 `rules:{path,digest}`，校验后复制进自己的产物库。它更贴近“输入一个报文和规则”的字面要求，也能在第二个干净工程复现审核。

**结论**：B 的 RuleSet 交接是实质优势，建议 A 在 v0.1 或 v0.1.5 吸收：policy 增加 `ruleset_path`/`digest` 导出，review 增加可选 `ruleset_path` 输入；`version_id` 保留为本地快捷方式。

### 3.3 契约与语义

A 的契约主要是工具 schema + 现有 catalog 协议；`CONTRACT.md` 会写 verdict/错误码，但没有独立的领域契约包，也没有把 `trueMeans/action/gates` 固化成 fixtures。

B 的 `ql-audit-iface` 明确 RuleSet/AuditResult/FieldProfile/Job/EnginePort/ArtifactRef，并把 `trueMeans=violation|compliant`、`action=reject|warn|manual`、`gates[].expect`、覆盖计数写成公共 conformance。它还指出一个现有实现的真实风险：旧规则里可能混用“true=违规”和“true=合规”，旧审核统一 true=通过会得出错误结论。

**结论**：这是 B 最有价值的部分，优先级高于包拆分。无论选 A 还是 B，都应把 `trueMeans/action/gates` 写进契约和测试；否则包拆得再漂亮，审核结论仍可能错。B 还把审核做成 job（`audit_message` 快速返回 job_id），比 A 的同步 `ql_run_audit` 更能扛大报文/超时；A 需要保留长时间执行风险说明，或后续改成 job。

### 3.4 Mint 装配

A 依赖 Mint 已实测的能力：bundle 的 `.mcp.json`、传递依赖、多个服务、meta/preset 组合。policy/review 启动器只需在同 scope 同级目录找 base，逻辑约 20 行；版本用 `=0.1.0` 锁死。

B 依赖一个**自定义 bootstrap**：读 `QL_AUDIT_PROJECT_ROOT`、解析 `mint.lock`、按包名/版本定位安装目录、校验 `exports.json`、用文件 URL 导入 ESM、按拓扑注入。它更严谨，但这不是 Mint 原生能力，属于新增分发协议；需要自己处理 TOML 解析、semver、路径越界、重复版本、integrity 校验。

B 还写了“声明过的环境变量应包含工程根、配置路径及 secret 引用”。但 0.1.14 的 bundle **不能声明 `capabilities.env`**，`.mcp.json` 的 `${HOME}` 也不展开；工程根/配置 env 只能由宿主或用户外部注入。GUI 从 Finder 启动时，这个假设未必成立，需要额外验证。

**结论**：A 的装配更“贴 Mint 现有能力”，B 的装配更“自己造一层”。两者都能跑，但 B 的启动失败面更大。

### 3.5 配置与数据

A 用一份 `~/.mint/ql-audit/config.json`（0600），base 写、policy/review 读；对话改 endpoint/CA 立即生效。全局版本列表和 run 历史在一个地方，用户体验简单。

B 让两个能力各自持有数据目录和配置，避免“两个进程共同改写一个 catalog”；但用户要在两个地方配置 Rulecraft/qlengine，且没有明确的对话配置工具。项目级 `.ql-audit/` 更适合多工程/复现，但跨工程共享规则需要传文件。

**结论**：A 的配置体验更好，B 的数据隔离/复现更好。v0.1 可以保留 A 的全局配置，但把“规则导出文件”做成可移植产物；v0.2 再拆数据目录。

### 3.6 复用与扩展

A 的 base 是 ql-audit 专用运行时；其他插件最多依赖它的包并定位 `lib/`，没有稳定的库导出协议。它解决了“两个能力复用”，但没有解决“MintHub 其他插件复用”。

B 的 `ruleset-core`、`qlengine-client`、`task-artifacts`、`ql-audit-iface` 是真正的公共库，未来规则编辑器、RSI、其他审核产品可以直接依赖。B 的 `message-profile-<business>` 也把字段/归一化从通用能力中拆出来，适合多业务。但 `ruleset-core`/`qlengine-client` 这类通用名需要明确 scope（例如 `lingcai/...`）和 AGPL 归属，否则容易和别人的包重名。

**结论**：如果“模块化”的目标包含生态复用，B 明显更强；如果只要求两个能力之间复用，A 足够。

## 4. 各自优势与代价

### A 的优势

- 3 周可交付；复用现有 `catalog/parse/audit`，改动集中在工具层与包布局。
- 已在 Mint core 0.1.14 上验证多包、3 服务、meta、preset、base 定位。
- 配置/健康/目录工具体验完整，符合已确认的“对话修改 + 本地持久化”。
- 包少、进程少、发布顺序简单；policy/review 制品不含业务代码，升级不易漂移。

### A 的代价

- 共享 catalog / `version_id`，跨工程审核弱；review 不能直接吃外部规则文件。
- base 是对模型可见的第三个服务；工具面 14 个，比 B 多。
- 没有独立领域契约包，`trueMeans/gates` 语义未固化，存在继承旧 bug 的风险。
- 审核 `ql_run_audit` 是同步调用，受全局工具超时限制；B 的 job 化审核更稳。
- 其他 MintHub 插件难以复用 base 的代码。

### B 的优势

- 库级复用，基础包可被其他插件/未来 RSI/编辑器使用。
- 只有两个模型可见服务；基础包零工具、零常驻进程。
- 不可变 RuleSet + digest，支持跨工程/跨机器审核与可追溯。
- 领域契约 + conformance，能修正 `trueMeans/action/gates` 等语义问题。
- 独立版本、可替换引擎/规则核心；业务 profile 可拆分。

### B 的代价

- 7–8 个包、独立版本矩阵、4 个基础库的文档/测试/发布成本。
- 自定义 bootstrap + `exports.json` 不是 Mint 原生能力；路径、semver、integrity、TOML 解析都要自己保证。
- `capabilities.env` 限制与“显式工程根/env”的假设冲突，需要外部注入或额外验证。
- 没有对话配置工具，和已确认需求不一致；补的话又要增加服务或重复工具。
- 估算 6–10 周+，首版风险明显高于 A。
- `ruleset-core`/`qlengine-client` 等公共包名较通用，需要确定 scope/所有权；不是只改 `mint.toml` 的问题。

## 5. 需要先验证的点

如果考虑 B，先做 M0/M1 spike，不要直接铺 7 个包：

1. **bootstrap**：在 Mint 0.1.14 干净工程里，从 `mint.lock` 定位 4 个基础包并导入 ESM；验证 base 包无 `.mcp.json`、只带 `exports.json`/`dist` 时可安装。
2. **env**：验证 bundle 不能声明 `capabilities.env` 时，`QL_AUDIT_PROJECT_ROOT`/配置路径如何可靠传入；GUI 从 Finder 启动也要覆盖。
3. **preset**：`kind=preset` + 两个能力 bundle 是否只加载两个 MCP 服务；preset 不带总 skill 是否可接受。
4. **配置**：B 的两个能力如何满足“对话改 endpoint/CA”；是加配置工具、加第三个服务，还是接受配置文件方式。
5. **语义**：用真实规则验证 `trueMeans` 混用；先写失败用例，再改审核器。

A 需要补的验证/设计：

1. **RuleSet 导出/导入**：policy 产出文件 + digest；review 接受 `ruleset_path`，不再只依赖本地 `version_id`。
2. **`trueMeans/action/gates`**：写进 `CONTRACT.md` 和 fixtures，修审核器；这是正确性问题，不是可选项。
3. **base 定位/版本**：`=0.1.0` + 同级目录；缺 base/多版本要有测试。
4. **preset vs meta**：preset 已验证可装 3 个服务；如果不需要总 skill，建议用 preset 替代 meta bundle，语义更干净。

## 6. 推荐路径

### v0.1：A + 三个吸收

保持 4 包结构，但做三件事：

1. **RuleSet 文件交接**：`policy` 的 `ql_parse_policy`/`ql_get_parse_status` 返回 `ruleset_path` + `ruleset_digest`；`review` 的 `ql_run_audit` 增加可选 `ruleset_path`/`ruleset_digest`，与 `version_id` 二选一。这样既保留本地 catalog 便利，又能跨工程审核。
2. **语义契约**：把 `trueMeans/action/gates`、覆盖计数、`needs-human` 规则写进 `CONTRACT.md` 和测试；修现有审核器的“true=通过”假设。
3. **组合包用 preset**：`lingcai/ql-audit` 改为 `kind=preset`（已验证可装 3 个服务）；如果确实需要总 SKILL，再加一个 `ql-audit-workflow` skill 包，或保留 meta bundle 作为例外。

这样 v0.1 仍是 3 周级，但补上了 B 最重要的两个正确性/可移植性优点。

### v0.2：按 B 的方向抽库

等出现第二个消费者（规则编辑器、RSI、其他审核产品）时，再拆：

- `ql-audit-iface`：RuleSet/AuditResult/FieldProfile/Job/EnginePort/ArtifactRef + fixtures；
- `ruleset-core`：校验、门控图、digest、字段快照；
- `qlengine-client`：health/compile/executeBatch；
- `task-artifacts`：原子任务/产物/锁/恢复；
- `policy-extract`/`message-audit` 改为显式 bootstrap 装配；
- `message-profile-<business>` 可选。

这时再承担 7–8 包的版本矩阵和 bootstrap 成本，收益（生态复用）才真实。

## 7. 一句话决策

- **要快、要稳、要满足已确认的配置体验 → A（4 包），补 RuleSet + 语义契约。**
- **要平台化、跨工程规则包、其他插件复用 → B（7–8 包），先做 M0/M1 spike，预算 6–10 周+。**
- **不建议**：首版直接上 B 的全部包，却没有验证 bootstrap/env/preset/配置这四件事。
