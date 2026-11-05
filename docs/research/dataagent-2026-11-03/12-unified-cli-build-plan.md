# 统一 CLI 实现计划（r1）

- 版本：r1（2026-11-06）
- 依据：[12-unified-cli-research.md](12-unified-cli-research.md) v0.3 §5（W0 契约以本文冻结的 r1 范围为准：stdin 旧模式保留，`--list` 旧 JSON 输出保留，`list` 为新格式）
- 目标包：`dataagent-runtime`（内核）、三层 `interfaces/cli.py`（接入）、`dataagent-cli`（新分发器包）、`dataagent-s0`（依赖）
- 范围外：MCP schema 压缩（§5.2 已定后续单列）、Mint Hub 发布（Q3）、治理/应用依赖对齐（Q5）

## W1 共享内核实现（dataagent-runtime）

- 内核按 inputSchema 解析 argv 参数：`--input-file`、`--set k=v`（按 schema 转换类型）、`--set-json k=<json>`（优先于 `--input-file`）、`--file <path>`（由文件字节生成 FileRef 填入文件入参）、`--ref <field>=<id@revision>`（从 data_root 的 results 解析为完整对象）、`--proposal-file`（两段式第二阶段提案）、`--authorize`（先取 AccessDecision 填入 `authorization_ref`）。
- `<op> --help` 输出扁平参数表（由 inputSchema 生成，不输出 `$defs`）。
- `list` 每个 op 一行：名称、能力编号、是否复检（resource_fields）、是否两段式。
- stdout 摘要 JSON：`status`、`issues`、关键输出字段、新产生对象句柄（`id@revision`）、`result_path`；控制在 32 KiB 内；全文写 `.dataagent/results/<invocation_id>.json`；`--detail full` 直接输出全文。
- `needs_input` 时输出 `inference_request`（另存 `.dataagent/results/<invocation_id>.inference_request.json`）与建议的下一条命令。
- 输出前做外发检查（W0 §5：enforce 模式下无 egress 决策引用时剥离 `inference_request` 内容键，与 MCP 通道一致）。
- 退出码 0 = ok/partial/needs_input；1 = failed；2 = 用法或 schema 错误；3 = 环境缺失（registry/catalog 校验失败）。
- 身份与用途只取 `DATAAGENT_HOST_SUBJECT_REF` / `DATAAGENT_HOST_PURPOSE`（§5.4），不接受参数覆盖。

## W2 三层接入实现

- 数据层、应用层、治理层 `interfaces/cli.py` 接入内核：`list`、`run <op>`、`<op> --help` 与旧 stdin 模式并存；改完重建 bundle，`test_bundle_sync` 通过。
- 治理层增加 `confirm <file>`（判据确认，确认人仍来自 `DATAAGENT_CONFIRMERS`）与 `policy apply <file>`（写入访问策略到版本库）。

## W3 分发器包实现

- 新增 `packages/capabilities/dataagent-cli`（`kind=bundle`）：`bin/dataagent` POSIX sh 分发器，按层定位 `.mint/packages/dataagent/<layer>-layer@<ver>/`（mint.lock 优先，缺省取最高版本），exec `<包>/.venv/bin/python -m dataagent_<layer>.interfaces.cli`；启动时按白名单清洗环境变量后 exec（§5.4）。
- `dataagent link` 在项目根生成 `./dataagent`；`dataagent setup` 对三层执行 `uv sync --frozen`；`dataagent doctor` 检查三层包、`.venv`、策略、data_root、执行模式（缺失退 3）。
- `skills/dataagent-cli/SKILL.md` 用法文档；mint.toml 声明 `[artifacts] bin = "dataagent"`，无 Python 依赖、无 `.mcp.json`。
- `dataagent-s0` mint.toml 增加 `dataagent/cli` 依赖（path 指向包根，无构建步骤）。

## W4 测试与交付

- 内核单测（参数解析、类型转换、句柄解析、摘要上限、退出码、needs_input 建议、外发剥离）。
- 三层 CLI 冒烟测试与既有套件全绿；分发器脚本在临时 mint 布局下的功能测试。
- 源码快照 + rubric 评分（code-landing-quality r1）。

## 记录

| 轮次 | 记录 | 结果 |
|-|-|-|
| r1 | [r1-fixes.md](12-cli-build/r1-fixes.md)（实现）/ [r1.score.json](12-cli-build/r1.score.json)（自评）/ [r1-review.md](12-cli-build/r1-review.md)（验收） | 不可验收：59.0（E），GATE-RED（D1 重复率 13.84%）+ GATE-CHECKLIST（摘要 32 KiB、输出前外发检查 2 项 partial），7 条 P2 |
| r2 | [r2-fixes.md](12-cli-build/r2-fixes.md)（修复）/ [r2-runtime.score.json](12-cli-build/r2-runtime.score.json)（自评）/ [r2-review.md](12-cli-build/r2-review.md)（验收） | 不可验收：功能面 W1–W4 全通过（101/654/203/121/12 全绿，D1→2.21%，D5/D7 修复），但自评把 R13 记 na 违反 rubric「无基线记 unknown」，独立评分 89.0（B）+ GATE-UNKNOWN；新增 D8（`--file` 缺文件 traceback）、D9（`confirm` 非法载荷 traceback）两条 P2；D2 partial、D3 open |
| r3 | [r3-fixes.md](12-cli-build/r3-fixes.md)（修复）/ [r3-runtime.score.json](12-cli-build/r3-runtime.score.json)（自评） | 仍不可验收：D8/D9 修复（结构化 exit 2，无 traceback；102/654/203/123/12 全绿，无回归），R13 更正为 unknown（自评 89.0 / B / GATE-UNKNOWN，与 Tester 同构）；唯一闸门 GATE-UNKNOWN 的清除需 owner 决策（发布基线制品或带日期豁免）——已提交 |
| r4 | [r4-fixes.md](12-cli-build/r4-fixes.md)（基线建立）/ [r4-runtime.score.json](12-cli-build/r4-runtime.score.json)（自评）/ [r4-review.md](12-cli-build/r4-review.md)（验收） | 不可验收：R13 基线已验证（tag `dataagent-runtime-0.1.0` 实际 ref `20022e0a` → commit `fbe24d8`，tag 内 runtime 快照 `78c93a64…` 与 r3 逐字节一致，tag 后无产品变更；102/654/203/123/12 全绿），但独立探针新增 P1 D10（`--set` 不支持 anyOf/$ref 标量，63 字段/30 ops，含 `check_access_scope.resource_ref`）+ 清单 `#ceedd2` partial → GATE-P1/GATE-CHECKLIST，79.0（C）；另 D11（r4 记录引用失效 tag object `8544568c`）、D2 partial、D3 open |
| r5 | [r5-fixes.md](12-cli-build/r5-fixes.md)（修复）/ [r5-runtime.score.json](12-cli-build/r5-runtime.score.json)（自评）/ [r5-review.md](12-cli-build/r5-review.md)（验收） | 可验收：D10 fixed（`_resolve_kind` 解析 anyOf/$ref/$defs，三层 121 标量字段/44 ops 判型通过；gov `--set resource_ref=table@*` → exit 0 allow、data `--set delimiter=,` → exit 0；非法 enum/ref/int/bool 仍 exit 2）+ D11 fixed（r4 记录 tag object 更正为 `20022e0a`，带审计标注）→ `#ceedd2` done；106/654/203/123/12 全绿；R13 仍 green（tag 后改动为增量、无破坏性变更）；独立评分 93.1（A）/ 无闸门；D2 partial、D3 open 留待后续轮 |
| r6 | [r6-fixes.md](12-cli-build/r6-fixes.md)（修复）/ [r6-runtime.score.json](12-cli-build/r6-runtime.score.json)（自评）/ [r6-review.md](12-cli-build/r6-review.md)（独立验收）/ [r6-tester-runtime.score.json](12-cli-build/r6-tester-runtime.score.json)（独立评分） | 不可验收：111/654/203/123/15 全绿，D12–D15 原探针 fixed、D5 40 KiB 单句柄通过；但 D5 精确边界 JSON 32768 B + 换行 → stdout 32769 B 仍 partial（P1），新增 P1 D16（存在 mint.lock 但该层无 pin 被误拒 exit 3；同输入 pre-r6 exit 0；doctor 仍 exit 0）→ #99a1de/#b9b374 partial；独立评分 79.0（C）/ GATE-P1 + GATE-CHECKLIST，自评 93.1 不成立；D2 partial（28.24%）、D3 open；截图工具失败，视觉验收 unverified |
| r7 | [r7-fixes.md](12-cli-build/r7-fixes.md)（修复）/ [r7-runtime.score.json](12-cli-build/r7-runtime.score.json)（自评）/ [r7-review.md](12-cli-build/r7-review.md)（独立验收）/ [r7-tester-runtime.score.json](12-cli-build/r7-tester-runtime.score.json)（独立评分） | 不可验收：79.0（C），GATE-P1 D16 + GATE-CHECKLIST #b9b374——D5 fixed（真实 stdout 32767→32768 不截断、32768→277 截断）、D16 partial（无 pin 回退与 doctor/dispatch 一致性已修；compact/缩进合法 TOML pin 仍被忽略，锁 0.2.0 未装时 exit 0 执行 0.1.0，r6 同输入 exit 3）、D2 partial（28.32%）、D3 open。r6-review 两项阻断修复——r6-review 两项阻断修复——D16（`pinned_version` 无该层 pin/版本不可读 → return 1；`resolve_dir`/`doctor_cmd` 同序消费：pin 已装→pin，无 pin→最高已装，pin 未装→exit 3；`/tmp/r7-mint` 真实三层 venv：仅 pin governance 时 `data list` exit 0 / 32 行，doctor 同绿，D13 语义保持 exit 3）、D5 收口（`fits` 计入 print 换行，上限=整条 stdout 行 ≤32 KiB；真实子进程实测：恰 32,768 B JSON r6 为 32,769 B → r7 241 B，少 1 字节不截断且 stdout 恰 32,768 B）；112/654/203/123/17 全绿；自评 93.1（A）无闸门；D2 partial（28.32%）、D3 open 留待后续轮 |
| r8 | [r8-fixes.md](12-cli-build/r8-fixes.md)（修复）/ [r8-runtime.score.json](12-cli-build/r8-runtime.score.json)（自评）/ [r8-review.md](12-cli-build/r8-review.md)（独立验收）/ [r8-tester-runtime.score.json](12-cli-build/r8-tester-runtime.score.json)（独立评分） | 可验收：**93.1（A）/ 无闸门**。D16 fixed——`pinned_version` 改 POSIX awk TOML 子集解析（standard/compact/缩进/字面/制表符/注释/`[package]` 均与 `tomllib` 同解析），三态出口 0 pin / 1 无该层条目（回退最高已装）/ 2 不可读（fail-closed），`pin_status` 以 `\|\|` 捕获防 `if` 条件吞 die；独立 `/tmp/r8-tester` 真实三层（wrapper 记录实际 exec 目录）28+7 组合：七种写法 pin 0.1.0 双版本已装 → dispatch/doctor 均 exec 0.1.0（r7 为 0.2.0）；四类写法 pin 0.2.0 未装 → dispatch exit 3 未执行 + doctor exit 3 `MISSING pinned`；无 version/坏引号/裸数字 → 双双 exit 3 `LOCK unreadable`；无锁/空锁/仅他层 pin → 回退 0.2.0；CRLF/version-first/无尾换行同样正确；r7/r8 同输入对照 r7 exit 0 执行 0.1.0 → r8 exit 3。D5 保持 fixed（32 KiB 上限：32767→32768 不截断、32768→285 截断）。五套 112/654/203/123/23 全绿；16 条缺陷全量复核，无回归/未复核；D2 partial（28.32%，runtime 源零改动）、D3 open 为非阻断 P2；R13 green 维持。此结论被下述同快照补充评审推翻。 |
| r8 补充评审 | [r8-reviewer-supplement.md](12-cli-build/r8-reviewer-supplement.md) / [独立评分](/Users/payne/.dsh/state/agent-teamwork/team/r8-reviewer-evidence/runtime.score.json) / [复现证据](/Users/payne/.dsh/state/agent-teamwork/team/r8-reviewer-evidence/) | **不可验收：79.0（C）/ GATE-P1（D16、D17）+ GATE-CHECKLIST**。相同 runtime/cli 源快照：新增 P1 D17——真实 Mint 0.1.26 的 CLI/preset path 依赖解析双双 exit1，CLI `[artifacts]` 缺必填 `layout`，安装链路阻断；D16 partial——`[[package.requires]]` 依赖边被误认不可读 pin，合法真实包条目被误拒（同输入 r7 exit0/32行→r8 exit3），引号键/转义 name 的 pin0.1.0 被忽略而 exec0.2.0；实际 Mint list 对嵌套锁正确识别0.1.0，非仅 tomllib 推断。五套112/654/203/123/23仍全绿，D5精确stdout32768边界保持fixed，D2/D3仍P2；视觉截图失败，unverified。 |
| r9 | [r9-fixes.md](12-cli-build/r9-fixes.md)（修复）/ [r9-runtime.score.json](12-cli-build/r9-runtime.score.json)（自评） | 修复 r8 补充评审两项 P1：D17 fixed——CLI `mint.toml [artifacts]` 补必填 `layout="any"`，真实 Mint 0.1.26 `mint init`+`mint add <preset path> --offline -y` exit 0 安装 dataagent/{preset-s0,cli,data-layer,application-layer,governance-layer}@0.1.0，`mint lock --dry-run --offline -y` exit 0（r8 同链路清单解析即 exit 1 `missing field layout`）；D16 收口——`pinned_version` awk 解析器表作用域感知（仅 `[[package]]`/`[package]` 条目为 pin，`[[package.requires]]` 依赖边与 `[core]`/`[package.artifacts.*]` 子表忽略）+ 引号键（`"name"`/`'name'`）+ basic 字符串完整转义（`\\ \" \b \f \n \r \t \uXXXX \UXXXXXXXX`）+ 闭引号后仅许空白/注释否则不可读、name 解析失败 fail-closed；reviewer 24 组合 lock_probe 原脚本全 PASS（引号键/`\u002f` name/`\u002e` version pin 0.1.0 双版本已装 → dispatch/doctor 均 exec 0.1.0，r8 为绕过/误拒；requires 边前置/仅依赖边 → pin/回退语义正确，r8 为双双 exit 3；行尾残留 INVALID → exit 3，r8 为执行）；真实 Mint 生成锁（[core]/requires/artifacts 子表形态）dispatch exit 0 exec 0.1.0；r8/r9 同输入对照见 r9-fix-evidence/D16_pre_post_control.txt；五套 112/654/203/123/36 全绿（cli 23→36：+9 D16 回归 +4 D17 清单/真实 Mint 安装回归）；自评 93.1（A）无闸门，round_diff r8→r9 无退化；D2 partial（28.32%）、D3 open 留待后续轮 |
| r9 独立验收 | [评审](<12-cli-build/r9-review.md>) / [独立评分](<12-cli-build/r9-reviewer-runtime.score.json>) / [机器报告](<12-cli-build/r9-reviewer-runtime.quality.md>) / [证据](</Users/payne/.dsh/state/agent-teamwork/team/r9-reviewer-evidence/>) | **不可验收：79.0（C）/ GATE-P1 D16 + GATE-CHECKLIST #b9b374**。D17已关闭（真实Mint安装五包、installed三层frozen环境/doctor/list/parse通过），D16原24/24通过但补充等价24项20失败：quoted/escaped表头、escaped键、inline package数组pin0.1被忽略而exec0.2；multiline pin误拒；quoted表头missing pin同输入r8exit3→r9exit0exec0.2，确认fail-open回归。五套112/654/203/123/36全绿；D5真实stdout32767→32768不截断、32768→339截断保持fixed；D2/D3仍P2。真实浏览器截图已捕获CLI原样stdout；原生终端/桌面截图因display不可用未验证。 |
| r10 | [r10-fixes.md](12-cli-build/r10-fixes.md)（修复）/ [r10-runtime.score.json](12-cli-build/r10-runtime.score.json)（自评） | 修复 r9 独立验收 P1 D16 残余：`pinned_version` 由逐行正则/切片改为**单遍字符级 TOML 扫描器**（POSIX awk + LC_ALL=C，镜像 stdlib tomllib 文法）——表头与键是完整解码的点路径（quoted/literal/escaped 表头与键寻址同一张表），值覆盖 basic/literal、单行/多行 `"""…"""`/`'''…'''`（前导换行裁剪、`\` 续行）、inline table 与数组（可跨行、可含注释）、数字/布尔/日期不透明 token，根级 `package = [{…}]` 与 `[[package]]` 是同一数组，tomllib 重复键/覆写规则以键路径注册表复刻；任何不可解析或不可排除 pin 的锁一律 exit 2 fail-closed。r9-review 原探针 lock_probe 24/24 + 补充等价 lock_edges 24/24 全 PASS（真实 Mint 0.1.26 逐例复核 pin 0.1.0）；r8/r9/r10 同输入 missing-pin 对照 42 组合中 r10 全部 exit 3 未执行（14 个失败全归属 r8/r9 bin）；tomllib 随机差分 1500 合法锁 0 失败 + 600 无效锁全 fail-closed；cli 36→58；五套 112/654/203/123/58 全绿；自评 93.1（A）无闸门；D2 partial（28.32%）、D3 open 留待后续轮 |
