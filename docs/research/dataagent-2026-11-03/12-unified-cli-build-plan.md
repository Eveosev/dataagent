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
