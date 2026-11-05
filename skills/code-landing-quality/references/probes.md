# 探针库

按规则列出探针类别。每个探针记录 **输入 / 期望 / 实际 / 位置**；失败的探针同时登记为缺陷（见 [tester.md](tester.md) §4）。示例取自 DataAgent 的历次评审，换项目时替换示例，类别不变。

## L2.2 对抗负例

适用类别 ≥8 时至少测 8 类，其中 ≥2 类为本轮新构造（上一轮报告中没有的输入）。

| # | 类别 | 构造方法 | 示例 |
|-|-|-|-|
| 1 | 方向反转 | 比较方向、包含关系取反 | 锚点 `above 5000`，提案 `below 5000` / `less than 5000` |
| 2 | 丢弃约束 | 提案省略锚点里的数值或条件 | 锚点 `above 5000 … approval`，提案只写 `approval` |
| 3 | 截断冒充 | 用来源的前缀、子串或部分 token 冒充完整值 | `Acm` 对 `Acme Inc.`；来源 `1000USD`，提案 `1000` |
| 4 | 格式走私 | 引号、千分位、全角/曲引号、大小写改变语义 | `'12,34'` → `'1234'`；`'Paid'` 当作 `'paid'` |
| 5 | Decoy 满足 | 附带一个合规成分通过检查，交付另一个成分 | `SELECT region, 0 AS total, sum(amount) AS decoy …` |
| 6 | 包装变换 | CTE、子查询、别名、CAST 包装后交付不同的值 | `WITH ok AS (SELECT … sum(amount) AS total …) SELECT region, 0 AS total FROM ok` |
| 7 | 条件中性化 | 恒真谓词、OR 中性化、窗口端点外移 | `WHERE approved OR 1=1`；`time >= '2025-12-31'` |
| 8 | 结构位移 | 让解析把数据并入表头，或丢掉片段 | `[["name","q1","q2"],["Alice",None,None],["Bob",1,2]]` |
| 9 | 类型混淆 | 非布尔值进入逻辑运算、缺字段节点、超深嵌套 | `and(True,"s")`；`{"op":"field"}`；3000 层嵌套 |
| 10 | 编码与字符集 | 非 UTF-8、BOM、CJK 与 ASCII 紧邻 | cp1252 的 `région`；`身份证11010519491231002X` |

期望：拒绝，或返回 `needs_input`/`partial` 并带可识别的 issue code。“返回 `ok` 且 issues 为空”就是失败。

## L2.3 校验对象 = 交付对象

| 探针 | 方法 |
|-|-|
| 逐跳比对 | 沿“校验 → 物化 → 交付/落库/外发”，在每一跳取出对象并计算 digest，digest 必须一致 |
| 旁路投影 | 校验通过后，检查交付列是否就是被校验的列（对应 L2.2 #5、#6） |
| 裁剪生效 | 决策约束 `[region, amount]` 时，外发 payload 不得含其他字段 |

## L2.4 边界与未知

| 输入 | 期望 |
|-|-|
| `None` / 缺字段 | 显式 `unknown` 或 issue，不折算为 `false`/0 |
| 空集 | 计入 `unanalysed` 或返回 issue，不当作通过 |
| 除零 | 显式分支 |
| 阈值 0 | `pass_rate >= 0.0` 不得恒真；唯一用例失败时必须判失败 |
| 全部 unknown | `report_separately` 时 unknown 不进分母 |
| 单元素、最大值 | 结果正确且有测试 |

## L2.5 执行侧复检

伪造上游产物并直接调用执行入口，例如构造 `ExecutableSpec(sql="SELECT region, sum(amount)*2 …")`，附带自报的 `semantic_versions`。期望执行侧拒绝，或因缺少不可伪造的生成回执而拒绝。

## L3.1 路径门禁

每类入口（MCP、CLI、库函数）各测四类：

| 类别 | 输入 |
|-|-|
| 绝对路径 | `/etc/passwd` |
| 穿越 | `../../outside.txt`、`a/../../b` |
| 符号链接越界 | 工作区内放一个链接，指向工作区外 |
| 前缀混淆 | 工作区 `/ws`，输入 `/ws-other/x` |

## L3.2 访问判定

- 统计读取型 operation 中声明了资源字段的比例，期望 100%。
- 资源无法映射时，期望 fail closed。
- 策略为 `allow table` + `deny table:salaries` 时读取 `salaries`，期望拒绝（不得用合成资源 `table@*` 求值）。

## L3.3 外发与脱敏

| 场景 | off | warn | enforce |
|-|-|-|-|
| 缺决策 | 放行 | 放行并带 warning | 不发送 |
| `allow_masked` | — | — | 内容确实被替换，而不只是记录了 mask_id |
| `field_constraints` | — | — | payload 按本次决策裁剪 |

敏感识别必测：身份证号紧邻 CJK 字符、`+86` 前缀、`138-0013-8000`、按空格分组的卡号。

## L3.4 决策不可自证

- 在 `arguments.context` 中自填 `subject_ref` / `purpose`，期望不被采信。
- 内容中自报 `sheet` / 类型，期望不被当作来源。
- 绕过 API 直接往决策库插入一条决策，期望被检测或无效。
- 调用方自报 purpose 字符串读取金标，期望按身份拒绝。

## L3.5 执行白名单

`ATTACH`、`COPY … TO`、`PRAGMA`、`INSTALL`/`LOAD`、`read_csv('/etc/…')`、多语句 `SELECT 1; DROP …`、DDL，以及通过标识符拼接注入（例如 `field_id = 'x"; CREATE TABLE pwn(a int); --'`）。期望全部阻断。

## L4 健壮性

| 规则 | 探针 | 期望 |
|-|-|-|
| L4.1 | ≥10MB xlsx、≥100 页 PDF、100 万行 CSV、单行 1MB | 返回超限 issue 或流式处理，RSS 有上界 |
| L4.2 | `max_seconds=0.01` 跑一次重查询或解析 | 按时返回 `timeout`，后台工作确实停止（连接与线程已释放） |
| L4.3 | ≥2 进程或 ≥10 线程，同时带 `expected_revision=r1` 写入 | 只有一个成功，其余返回 `version_conflict`；revision 与 cursor 连续、不重复 |

## L1 能力面

- 用 `tools/list` 或 `--list` 的结果与 Catalog 做双向差集，期望两边都为空。
- Catalog、snapshot、接口列表三方的 id / operation / source_file 全等。
- 字段消费：逐个修改输入模型的字段，输出必须随之变化，否则该字段属于未消费声明。

## L5 测试有效性

- 按入口列出负例，每个入口至少 1 个，且断言错误码（只断言异常类型不算）。
- 抽查主链路的断言：只断言 `status == "ok"` 的不算。
- 至少 1 条测试经真实子进程（stdio MCP 或 CLI）运行。

## L6.2 文档一致

随机抽 5 条可验证的声称（计数、状态、路径、命令），逐条复跑。
