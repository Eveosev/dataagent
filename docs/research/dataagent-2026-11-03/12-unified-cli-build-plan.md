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
| r8 | [r8-fixes.md](12-cli-build/r8-fixes.md)（修复）/ [r8-runtime.score.json](12-cli-build/r8-runtime.score.json)（自评） | D16 收口（送审中）：`pinned_version` 改 POSIX awk TOML 子集解析（表头切分 + name/version 键值，接受 compact `name="…"`、缩进 `  name = "…"`、字面 `'…'` 字符串与行尾注释，`tomllib` 等价），三态出口 0 pin / 1 无该层条目（回退最高已装，D16 无 pin 语义保留）/ 2 条目版本不可读；`pin_status` 以 `\|\|` 捕获（die 置于 if 条件内会被 set -e 条件豁免吞掉 → 实测即 fail-open，注释明示禁止）；`resolve_dir` 对 2 die exit 3、pin 未装仍 D13 exit 3 不回退；`doctor_cmd` 对 2 记 `LOCK unreadable` + status=3 + continue，策略探针不回退。黑盒（`/tmp/r8-mint` 真实三层，wrapper 解释器记录实际 exec 目录）：标准/compact/缩进/字面 pin 0.1.0 双版本已装 → dispatch/doctor 均 0.1.0（r7 为 0.2.0）；compact/缩进/标准 pin 0.2.0 未装 → dispatch exit 3 未执行、doctor exit 3；无 version 字段 → 双双 exit 3；r7/r8 同输入对照见 `r8-fix-evidence/D16_pre_post_control.txt`。回归：`test_lock_unreadable_pin_falls_back` fail-open 预期改正为 fail-closed，+5 矩阵回归（cli 17→23）；112/654/203/123/23 全绿，runtime 源零改动（快照 `8a7692b4` 与 r7 一致）；自评 93.1（A）无闸门；D2 partial（28.32%）、D3 open 留待后续轮 |
