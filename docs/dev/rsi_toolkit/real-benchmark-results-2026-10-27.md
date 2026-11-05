# Mint 真实 Benchmark 结果（2026-10-27）

本轮对四个实际任务运行了本机 Mint CLI 和真实模型，并调用上游评分器。之前的 fixture、manifest 和 smoke 记录不属于下表。四题为选定样本，不代表全量 benchmark 成绩，也没有测量 RSI 优化前后的增益。

## 实测结果

| Benchmark | 任务 | Solver 终态 | 上游评分 |
| --- | --- | --- | --- |
| Job-Bench main | `bookkeeping_accounting_and_auditing_clerks/task2` | completed，19 步，162.52 秒 | **6/52，11.54%** |
| Job-Bench main | `computer_user_support_specialists/task1` | failed，40 步预算耗尽，373.76 秒 | 实际产物 **14/56，25%** |
| WorkBuddy code | `bug_fix-easy-a_crash_in_local` | completed，8 步，28.19 秒 | **1/3，0.3333** |
| WorkBuddy office | `calendar-dida-sync-state` | completed，25 步，866.94 秒 | 规则 **82/109，0.7523**；LLM **5/5，1.0**；上游合成 **0.8018** |

WorkBuddy office 的 `deterministic_gated_pass=false`，仍有 27 项规则失败。合成分数不能解释为完整验收通过。不同 benchmark 的分数定义不同，不计算混合总平均。

## 运行条件

- Mint CLI `0.1.10`，Core `0.1.6-core`，真实模型 `MiniCPM-V-4.7-35B-A3B`。
- 每题固定 40 步、900 秒、单次输出上限 8192 tokens；支持任务为 `max_turn_requests`，其余三题自然 `end_turn`。进程退出码 0 不作为任务成功依据。
- Solver 使用 macOS arm64，四题均通过 Seatbelt 隔离预检；可写范围为单题公开工作区，网络仅可访问无凭证本地模型代理。隐藏 rubric/tests/gold 位于工作区外。
- WorkBuddy 评分使用未改动的上游 Dockerfile 构建的 linux/amd64 镜像，容器评分关闭网络。Office 使用原始 `RubricLLMJudgeRunner`、`PassRateScoringPolicy` 和 `finalize_score`，合成公式为 `0.8 × rule + 0.2 × llm`。
- Job-Bench 使用 Harness2 固定版本及其原始兼容 patch 后的上游 judge。会计题前两轮 judge JSON 无法解析，均保留为 unscored；第三轮仅在请求中加入 `response_format=json_object`，全部 8 项解析成功后才报告分数。答案、rubric、prompt 和评分函数未改变，响应未修写。
- 执行与裁判使用同一模型，存在相关误判风险。支持题有一条 rubric 的理由对缺失证据作宽松推断；保留官方原始分数并披露此风险，不能作为独立模型公允排名。
- Job-Bench 不能实时上网检索；操作员分别从 IRS/Cisco 官方网站获取公开参考放入工作区，来源及哈希保留。WorkBuddy solver 为本机环境，与 Linux grader 环境存在差异。

## 实际失败

- Code：两个隐藏测试失败，涉及部分迭代后遇到 shutdown `TypeError` 时未清理已经见过的 context。
- Office：27 项失败涉及状态字段、ID 分配、历史字段、无变更保留和摘要引用/计数等。运行中有 14 次长 `fs_write` 参数 JSON EOF，模型最终仍生成了三个目标文件。
- 会计：产物包含五个 sheet 和备忘录，但多源对账、支票差异、应计项目等 rubric 未通过，仅 1/8 rubric 通过。
- 支持：生成 DOCX、CSV、SQLite，SQLite `integrity_check=ok`，但模型用满 40 步。裁判发现跨源匹配、每日汇总与部门归因等错误，仅 2/8 rubric 通过。

## 轨迹与产物

持久证据根目录：`/Users/payne/Vibe/AgentOS/evidence/rsi-toolkit/real-benchmarks/2026-10-27/`，位于发布插件目录外。

- `summary.json`：四题 solver 终态、usage、耗时、正式评分和证据相对路径。
- `sha256-manifest.json`：归档文件 SHA-256 清单。
- `jobbench/*/solver/`：原始 NDJSON、隔离探针、前后哈希和二进制产物；`judge*`：全部评分尝试、原始响应和日志。
- `workbuddy/solver/`：两题原始轨迹与产物；`workbuddy/results/`：JUnit、规则脚本、原始测试结果、Office 裁判证据及合成评分。
- `runner-source/`、`runbooks/`：本次适配源码快照与复现说明；`environment/`：版本、二进制哈希、Docker 信息及代理请求计数。

评分副本排除了操作员/Mint 运行元数据 `.rsi-runtime/`、`.mint/`、`mint.toml`、`mint.lock`，逐文件排除来源和哈希均保留；原始 solver 文件没有删改。Code v1/v2 复评正确率相同。最早 MIME 预检失败的原探针在归档机制加入前被覆盖，只有工具日志保留该异常；后续启动失败和正式执行轨迹均已归档。

为避免将第三方隐藏测试、gold 或原始数据混入产品包，持久副本不包含注入测试后的 `graded-workspace`、原始数据集及 Job-Bench `RUBRICS.json`；原始授权本地数据和 grader 目录仍在机器上。详细原始裁判日志可能含 rubric 内容，仅保留在本地，不发布到 MintHub。

## 复现入口

- [Mint 执行命令](/Users/payne/Vibe/AgentOS/apps/plugins/rsi-toolkit/docs/benchmarks/mint-real-runbook.md)
- [Job-Bench 固定输入及 judge](/Users/payne/Vibe/AgentOS/apps/plugins/rsi-toolkit/docs/benchmarks/jobbench-real-runbook.md)
- [WorkBuddy 镜像、规则及模型评分](/Users/payne/Vibe/AgentOS/apps/plugins/rsi-toolkit/docs/benchmarks/workbuddy-real-runbook.md)

这四题已经验证真实执行和上游评分链路。后续若要证明 RSI 自进化收益，需要冻结任务及模型配置，分别执行基线和候选，再在隔离保留集比较；本轮分数不支持该结论。

## 交付校验

- 飞书结果文档：[Mint 真实 Benchmark 实测结果与复现记录](https://modelbest.feishu.cn/docx/DdqrddJEQoIdsuxw8ZhcoMA3nNh)，已创建在指定文件夹，使用既有文档权限。
- 持久证据 181 个文件逐一核验，清单 SHA-256：`519a51bd6f51d320b00b7646362493d49cd2e925a46181a2277289bc9dbb1540`。
- 模型代理请求从 409 增至 538（129 次，包含 solver、裁判及无效裁判响应的重试），转发错误增量为 0；不把代理计数单独作为任务成功证据。
- 最后完整 service 回归：439 passed，1 个既有 Starlette warning。一次较早执行暴露既有 controller 漂移终态先于事件写入的竞态，单测复跑和最后全套通过；本次 benchmark 采用直接 Mint → 上游评分器路径，不走该 controller。该竞态作为独立遗留风险保留。
- 本轮没有新增截图或录屏；执行证据为原始 NDJSON、工具结果、实际产物和原始评分记录。
- 独立审查未发现影响本轮实测的阻塞问题。后续复现仍需人工核对 patched judge 哈希和镜像 ID；Office LLM 评分脚本尚未强制拒绝覆盖已有评分，所以每轮须使用新 verifier 目录。本轮只运行一次 Office LLM judge，没有覆盖旧评分。
