# dataagent-s0（S0 组合预设）

`kind = "preset"` 的组合包（08 §8）：安装后把 DataAgent S0 的三个 bundle
装配为一个工作区——

| 依赖 | 内容 |
|-|-|
| `dataagent/data-layer` | 32 个数据层原子（解析、规整、画像、抽取、规则、可判定性、指标、轨迹） |
| `dataagent/application-layer` | 13 个应用层原子（需求绑定、表达式、SQL、引擎对齐、报告） |
| `dataagent/governance-layer` | 6 个评测治理层原子（访问判定、外发控制、判据、样本、验收、粒度） |

附两条端到端 Skill：

- `dataagent-s0-judgment`（判定族）：访问判定 → 接入 → 抽取或规整 → 规则 →
  判定 → 验收 → 报告；
- `dataagent-s0-compute`（计算族）：访问判定 → 接入 → 指标与规整 → SQL 执行 →
  粒度与合并检查 → 验收 → 报告。

## 执行模式（08 §4.3、§11）

`[packages]` 环境注入只在项目清单（`kind = agent`）里合法，preset 不能携带；
enforce 姿态由 bundle 自己的 `.mcp.json` 交付——Mint 内核清空 MCP 子进程环境，
服务描述符的 `env` 映射是唯一注入通道（W0 §6）：

- **治理层 bundle**：`.mcp.json` 以 `DATAAGENT_ENFORCEMENT_MODE=enforce` 拉起
  MCP——治理层是策略判定点，按 S0 验收姿态运行。
- **数据层 bundle**：`.mcp.json` 同样注入 enforce——读取输入资源前做 DA12.1
  访问复检（决策缺失/过期/不覆盖/用途不符均拒绝，code `da12.access_denied`）。
  开发进程内缺省仍是 `warn`（08 §11：先 warn 统计未通过调用）。需要 warn/off
  的宿主在项目根 `.mcp.json` 用同名服务覆盖（项目级优先，包内声明被忽略）。
- AccessDecision 存放在共享 `data_root/db/decisions.sqlite3`：Mint 工作区内
  三个 MCP 共享缺省 `<workspace>/.dataagent/`，治理层 `check_access_scope`
  产出的 `decision_id` 可直接作为数据层调用的 `authorization_ref`。

## 安装

三个 bundle 尚未发布到 Mint 仓库（hub 404），版本约束无法解析，因此
`[dependencies]` 以 path 指向同仓的三个 `packaging/bundle`；发布后改为
`"dataagent/<层> = "^0.1.0"` 即可。本地安装（离线）：

```bash
mint init --no-preset --offline -y
mint add path:packages/capabilities/dataagent-s0 --offline -y
# 已安装 dataagent/preset-s0 + data/governance-layer + dataagent/data-layer
#   + dataagent/application-layer（共 4 个包）
```

跨层端到端测试见 `packages/capabilities/dataagent-scenarios/`（仅测试包，按
Skill 顺序经真实 MCP 子进程调用三个 bundle，数据层服务在测试中以
`DATAAGENT_ENFORCEMENT_MODE=enforce` 运行）。
