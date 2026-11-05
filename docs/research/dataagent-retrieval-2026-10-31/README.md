# DataAgent 自适应检索专题 · 2026-10-31

本专题深化[前轮综合报告](../dataagent-landscape-2026-10-31/00-synthesis.md)的“新问题如何找到相关业务逻辑、表列、值和方法”。重点是：用户从值、列或规则开始提问时，如何避免固定检索顺序过早锁定范围，并根据新证据补查、验证或澄清。

| 文档 | 主要内容 |
| --- | --- |
| [00 · 综合讨论与建议](00-adaptive-retrieval.md) | 入口、下一动作、停止三个问题；多类型对象与反向关系；混合策略、工具契约、难点与控制变量评测 |
| [01 · 产品与工程实践](01-industry-practice.md) | Genie、Snowflake、ThoughtSpot、Hex、LinkedIn、Ramp、LangChain/Hex 的具体检索、导航、验证机制和证据边界 |
| [02 · 论文与方法](02-methods-and-papers.md) | CHESS、RSL-SQL、ReFoRCE、APEX-SQL、RAT-SQL、Spider-Agent；明确论文版本，并核查官方代码中的顺序与反馈 |
| [03 · 源码机制](03-code-patterns.md) | Wren、SuperSonic、DB-GPT、Vanna、MCP Toolbox 的工具签名、调用顺序、状态回注、版本、权限与许可 |

核心判断：**发现入口和下一步动作可以动态变化，必要证据、权限、版本和预算应由明确契约约束。** 多入口召回、双向合并、条件探索、模型选工具是不同机制；不能仅凭“Agent”名称推断它们同时存在。00 中的组合方案是研究建议，未实现或验证其收益。

三个子 Agent 分别研究产品、论文与源码，再交叉审核综合报告。研究方式为官方正文阅读与固定提交的静态代码检查；没有连接业务数据库、租户测试、执行第三方仓库或运行 benchmark，也未把不同条件的成绩拼成排行榜。

来源账本与离线缓存：

- [产品文档与访问记录](sources/products-source-index.json)：包含成功、复用缓存与失败记录；文档事实和客户自述分别标识。
- [论文版本、代码提交与正文校验](sources/papers-manifest.json)：论文使用明确 arXiv 版本，实现按固定 commit 引用。
- [源码抓取与 SHA-256](sources/code-fetch-manifest.json)：记录文件路径、固定 URL、成功内容的哈希和非关键抓取失败。

评测背景复用[前轮 benchmark 核验](../dataagent-2026-10-30/03-benchmarks-and-evaluation.md)。本专题新增的对照建议见 00 §7，重点分离索引覆盖、反馈纠错与动态调度各自带来的变化。
