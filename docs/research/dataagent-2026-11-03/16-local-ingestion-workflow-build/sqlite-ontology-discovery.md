---
version: 1
date: 2026-11-12
status: 本地可验收
kernel_commit: 663e2a33fb5c0517e78c1a329beee8032e261a70
---

# SQLite 本体发现

单个 SQLite 来源进入只读探查后，Agent 根据表、列、键、样本统计和业务目标提出实体、每行粒度、标识、属性与关系。用户在同一任务的工作台查看证据、确认或退回草案。

| 步骤 | 接口 | 产物 |
| --- | --- | --- |
| 发起 | `intake_start`，`mode=ontology_discovery`，一个 `kind=sqlite` 来源 | 任务、作业和业务目标 |
| 探查 | `intake_advance`、`intake_inference` | 表结构、主键和唯一键、字段分布、关系证据、覆盖和精确来源修订 |
| 提案 | `ontology_discovery_propose` | 已校验的草案、扩展列、未建模表和待核对关系 |
| 审核 | 工作台「确认当前草案」或「退回草案」 | 草案引用、决定和审核时的任务修订 |

## 证据规则

- 复合外键保持列顺序，省略目标列时按目标主键展开。声明来源与样本同值数分别记录。样本按实际存储类型和值比较，SQLite 排序规则和隐式转换由数据库负责。
- 未声明关联从相同字段亲和性、唯一目标键和观测值重合中生成单列候选。至少两个不同非空值全部同值匹配才进入候选。多个目标吻合时标记歧义。
- 发现任务按表分配读取预算，记录完整、抽样或缺口。含观测空值的唯一键仍可用于关系证据，实体标识须使用没有观测空值的键。
- Agent 默认收到字段统计与关系计数。按来源明确允许的字段可返回有长度限制的字面样本。二进制值不参与样本匹配或模型披露。
- 草案绑定不可变探查修订。审核提交同时比对任务和草案修订。确认保存发现草案，实例生成和本体发布使用后续独立流程。

目录采集、逐表语义提案、再校验关系的顺序参考 NVIDIA 的 [表语义处理](https://github.com/NVIDIA/auto-ontology/blob/fc43a82600e18b19d159c52023f54f5572f537ac/auto_ontology/semantic/visit_enter.py#L813-L856) 与 [外键候选处理](https://github.com/NVIDIA/auto-ontology/blob/fc43a82600e18b19d159c52023f54f5572f537ac/auto_ontology/semantic/semantic_fk.py#L466-L529)。

## 验收

| 场景 | 证据 |
| --- | --- |
| 离线 Mint 装包后的工具链 | `bash scripts/verify_local.sh --phase discovery` 用 [合成销售库](../../../../packages/capabilities/dataagent-scenarios/fixtures/intake/sales-discovery.sql) 探查 3 张表、7 行。明细 → 订单有声明证据，同值 3/3。订单 → 客户由值重合产生候选，同值 2/2。公开工具接收并保存 3 个实体、2 条关系的固定草案 |
| 工作台审核 | `scripts/verify_browser.py` 在 Chrome 上传同一 SQLite，读取表和关系证据。公开 MCP 工具提交后自动显示草案。确认后刷新，决定和待核对项均保留 |
| 歧义与拒绝 | 组件测试覆盖两个同样吻合的客户表、空键、虚构字段和关系、二进制与 Base64 文本冲突、空库、生成列和过期提案 |
| 本机模型 | `mint model status --offline` 未发现托管模型部署。本轮使用固定结构化提案，Mint TUI 和原生 GUI 的模型推理待本机模型就绪后复验 |

[SQLite 测试用例](offline-input-cases.md#数据库和-api-输入) · [Mint 操作步骤](mint-offline-quickstart.md#2-从-tui-或原生-gui-操作)
