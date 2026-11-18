---
version: 1
date: 2026-11-18
status: 证据摘要
card: T50
---

# Mint TUI 证据包摘要

按 [05 §4.2](<../../../dataagent/05 分期路线与 MVP 范围.md>) 在全新工作区跑 C-01、C-02、C-03。证据包在仓外：`/Users/payne/Vibe/dataagent-private/t50/evidence/`（`manifest.json` 列出 188 个文件及 sha256），本篇只做摘要。

## 1. 结论

| 场景 | 结论 | 关键证据 |
| --- | --- | --- |
| C-01 文件接入 | 部分通过 | 3 份 PDF + 1 个 Excel 的任务保存被拦（混排 PDF 第 3 页成孤儿记录，见 D6）；去掉混排 PDF 的 3 份材料任务完成网页纠正 → 回聊天保存，得到 `release:edf13c90…@1` |
| C-02 数据库和 API | 通过 | 13 个对象（10 有键 + 3 缺键），冲突 5 处 / 4 个对象，与金标一致；保存被拦；令牌哨兵 0 命中 |
| C-03 二次接入 | 部分通过 | 单来源 Excel `mapping_reused=true`；不含扫描件的多来源组合 `mapping_reused=true`；含扫描件的组合不复用（D3）；C-02 组合首次就不能保存，无从复用 |

M1-09、M2-06 都未达到「已验证」条件，原因见 §7。

## 2. 环境与做法

| 项 | 值 |
| --- | --- |
| 代码 | DataAgent `feat/p1-intake`，`bash scripts/prepare_acceptance.sh` 构建于 `f84a514`；运行期间分支前进到 `3d3bef2`，新增提交只改文档和 `09-benchmark/tools`，`packages/`、`scripts/` 无变化 |
| 构建产物 | `build/local/manifest.json` sha256 `14e2c681…f5d`；工作区装 5 个包，均为 0.1.0（integrity 见证据包 `versions.json`） |
| Mint | CLI `mint 0.1.31`；core 0.1.47 std（NDJSON `session_info_update` 与 `mint.lock` 一致）；模型 `deepseek-v4.1-flash-mb` |
| 工作区 | `/Users/payne/Vibe/dataagent-private/t50/ws`：`mint init --no-preset --offline -y` → `mint add path:build/local/preset-intake` → `dataagent setup --ocr-root $OCR_ROOT`；doctor 报 `rapidocr-local 1.4.4`，verification `ocrv-fe5ffe0473924e23` |
| 驱动方式 | TUI 需要 TTY，改用同一内核的 `mint run --json -y --approve all [--session <id>] "<话术>"`，一轮一次调用，同一会话用 `--session` 续接；每轮 NDJSON、stderr、话术、解析摘要在 `turns/` |
| 审批策略 | `--approve all`，运行时 `approval_policy=never`，所有工具（含 `shell_exec`）自动放行。默认策略（`--approve auto`，`on-request`）无人值守时拒绝 DataAgent 工具：11-17 预演会话 `s_f62ac3592d5c` 的 `intake_start` 被 `reject_once`（证据包 `approval-default-rehearsal.txt`），即已知缺口 G1.5 / IF-01 |
| 网页 | Playwright（系统 Chrome，headless）脚本 `tools/web.cjs`；截图 63 张、webm 录像 5 段 |
| 网页入口 | 工作台用一次性 nonce 换 cookie，nonce 只经 `webbrowser.open` 发出、60 秒过期。做法：用 `BROWSER=tools/capture-browser.sh` 重启工作台服务（同解释器、同工作目录），驱动脚本调 `/local/open` 取新 nonce 后打开；校验 `/local/open` 返回的 URL 与 Agent 报的 URL 一致（重启服务后端口变化的那一次除外） |
| 输入 | 全部合成：`fixtures/intake/{invoice.pdf,scan.pdf,mixed.pdf,invoices.xlsx}`、`cross-source/samples/{invoices.pdf,ledger.db,rest/page1-3.json}`；新造 `invoices-w2.xlsx`（同表头，INV-004 158000、INV-005 72000，sha256 `4b1e06e0…7e2b`） |

## 3. C-01 文件接入

Mint 会话 `s_ae2a8f89b8b2`（轮 t_1–t_6）。拖入用「绝对路径 + 话术」模拟。

| 轮 | 用户 | Agent 做了什么 | 结果 |
| --- | --- | --- | --- |
| t_1 | 4 个绝对路径 + 「把这些采购单接进来」 | `intake_start`（绝对路径）→ `intake_advance` 全部 `source_unreadable`；改相对路径重建任务 `cc8be250`；`intake_extract` 拆扫描件 OCR 粘连（3 次失败 2 次）；3 次 `intake_propose_sources`；`workbench_view`；7 次 `shell_exec` 读原件和 `.dataagent/results` | 模型网络错误，退出码 4，无最终回复 |
| t_2 | 继续 | 为排错自建任务 `a8c0dd00`（3 份）和 `e4e7c23a`（混排 PDF），未经要求对 `a8c0dd00` 执行 `mapping_apply` 保存 | 得到 `release:7ff97919…@1`；问「第 3 页的 CNY 是不是 INV-002 的币种」 |
| t_3 | 是，先别保存，打开工作台 | `workbench_view cc8be250` | 列出待核对：元/分换算（按 `amount_minor` 判为分）、扫描件拆分、混排 PDF 孤儿记录 |
| 网页 | — | 对象页 4 个对象：INV-001、INV-003、INV-002 金额均有原图与高亮；第 4 个是 `candidate:<hash>`，无来源定位；对 INV-002 币种做当前值纠正 | 纠正记录写入，重验提示 `required property remains unresolved` |
| t_4 | 纠正过了，保存四份材料的任务 | 重新 `intake_propose_sources`（生成新预览，网页纠正随之丢失，见 D2）→ `mapping_apply` | 被拒：`preview contains unresolved issues` |
| t_5 | 混排 PDF 先不接，用其余 3 份新建任务，打开工作台 | 新任务 `20cf026a`，`intake_extract` + `intake_propose_sources`，`workbench_view` | 3 个对象，0 问题，未保存；未复用 `a8c0dd00` 已存映射（D3） |
| 网页 | — | 3 个对象逐个点金额：invoice.pdf 第 1 页高亮、scan.pdf 第 1 页高亮、Excel `Invoices · B4` 单元格选中；把 INV-003 金额 1260.00 纠正为 1250.00 | 状态「已纠正」，`review_state=unreviewed` |
| t_6 | 以这次为准，保存 | `mapping_preview` → `mapping_apply`（`preview_ref 0dc0a3cc…@3`）→ `intake_status` | `saved`，`release:edf13c9006983cd2edcd6daeb0da516f62d8dcb58523f4570d375edd98a3c26d@1`；发布预览 `@4` 里 INV-003 为 1250.00 并带纠正记录 |

| 05 §4.2 期望 | 结果 | 依据 |
| --- | --- | --- |
| 只问影响结果的歧义 | 通过 | 只问了混排 PDF 第 3 页币种归属；元/分在 t_3 列为「最需要你确认的判断」，没有无关提问。偏差：t_2 未经要求保存（A1） |
| 网页能点开每个金额看到原图高亮 | 通过 | `screenshots/c01b-03-obj{1,2,3}-amount.png`、`c01-tour-03-obj*-amount.png`；多来源对象只显示第一个来源的高亮，Excel 定位以文字给出 |
| 纠正 1 处后保存，得到发布引用 | 4 份材料失败；3 份材料通过 | 4 份：D6 + D2；3 份：`c01b-05-corrected.png`、`turns/c01-6.ndjson`、`workbench-tasks.json` |

Mint 会话里的 M1-04/05/06 复验（07 卡 T21 移来的部分）：文本 PDF 第 1 页原图与高亮、扫描 PDF（RapidOCR）INV-003 / 1260.00 / CNY 与高亮、Excel `B4` 定位都已看到；混排 PDF 第 2 页报 `incomplete_source`，第 3 页的币种成了无编号记录（D6）。

## 4. C-02 数据库和 API

Mint 会话 `s_40631a670edf`（t_1–t_3），任务 `6d2d1f0ce36e4aceb92902fac71da199`。

- 连接配置：`.dataagent/source-connections.json` 的 `invoice-api`（`kind=rest`，`credential_refs.token=file:rest-token`，令牌是只写在 `.dataagent/secrets/` 的哨兵值）；本机 REST 服务按 `scripts/acceptance/sources.py` 的规则要求 `Authorization: Bearer`，无令牌返回 401（`c02-setup.txt`）。
- 话术：「c02/invoices.pdf 是采购单，c02/ledger.db 是发票 SQLite 库，发票 API 已经配成连接 invoice-api（带 token）。把发票库和发票 API 对到采购单上。」

| 轮 | Agent 做了什么 | 结果 |
| --- | --- | --- |
| t_1 | `intake_start`（file + sqlite + rest `invoice-api`）→ `intake_advance` → `intake_propose_sources`（三源 decimal，绑定 issuer）→ `mapping_preview` → `workbench_view`；另有 9 次 `shell_exec`：解码 PDF 流、`sqlite3` 读库、`curl` 直连 API（401）；`fs_read` 读连接清单 | 13 个对象、13 条问题；列出 5 个待拍点，未保存 |
| 网页 | 13 个对象逐个点 amount、issuer，截图 26 张 | 冲突字段显示「未解决」；REST 第 2、3 页记录的来源行高亮错位（D4）；SQLite 定位显示 `[object Object]`（D5） |
| t_2 | 用户「先按现在的结果保存一版」→ `mapping_apply` | 被拒：`preview contains unresolved issues` |
| t_3 | 用户选「排除无号记录再存」→ Agent 查 schema 后说明映射不支持按行排除 | 停在预览，未保存 |

| 05 §4.2 期望 | 结果 | 依据 |
| --- | --- | --- |
| 同一单据号各来源合并为 1 个对象 | 通过 | 10 个有键对象 + 3 个缺键候选 = 13，与 `cross-source/gold.json` 的 J7 一致；INV-2026-101 带 PDF 第 1 页、SQLite id=1、REST `/items/0` 三处证据 |
| 金额冲突被标出，保存被拦 | 通过 | `conflicting_values`：104、105、110 的 amount，107、110 的 issuer，去重后 5 处 / 4 个对象（金标 J3）；`mapping_apply` 被拒。拒绝信息不点名对象（D7）；同一预览里还有缺键记录，本会话没有单独证明「只有冲突时」也被拦 |
| REST 令牌不出现在会话、日志、结果里 | 通过 | `sentinel-scan.json`：工作区 6270 个文件（含 `.mint/sessions`、`.dataagent/results`、`content`、`runtime/workbench.log`）、证据目录 172 个文件（含全部 NDJSON）0 命中；`~/.mint` 运行期间无文件变动；阳性对照（密钥文件）命中。REST 访问日志：三页各 200 一次，另有 Agent `curl` 的 1 次 401 |

## 5. C-03 二次接入

| 步 | 会话 / 任务 | 输入 | 结果 |
| --- | --- | --- | --- |
| 基线 | `s_dc6a0d4499a4` / `699a8539` | 第一周 `c01/invoices.xlsx` 单独接入，用户预先同意保存 | `release:fcc0ce73…@1`（C-01 只存过组合映射，单来源复用需要这次基线） |
| 单来源 | `s_7c73e3652385` t_1 / `f257ccc3` | 「第二周的采购单 Excel 到了：c03/invoices-w2.xlsx … 接进来」 | `intake_advance` 直接进 `preview`；预览 `e000c7fc…@1` 的 `mapping_reused=true`，只含 INV-004 1580、INV-005 720；Agent 未经要求保存（A1），`release:4726f98f…@1` |
| 多来源（含扫描件） | `s_7c73e3652385` t_2 / `69a0b4c6` | invoice.pdf + scan.pdf + invoices-w2.xlsx，与 `20cf026a` 同结构 | `intake_advance` 返回 `needs_input`，`mapping_reused=false`（D3）；Agent 用 `sqlite3` 读内部库 `.dataagent/db/workbench.sqlite3` 抄回上周映射（A2），未经要求保存，`release:0fdfaf98…@1` |
| 多来源基线 | `s_8bef0d683a48` t_1 / `2e3b8920` | invoice.pdf + invoices.xlsx，用户预先同意保存 | `release:30a82d9a…@1` |
| 多来源（不含扫描件） | `s_8bef0d683a48` t_2 / `60c700d0` | invoice.pdf + invoices-w2.xlsx | 直接进 `preview`，`mapping_reused=true`，3 个对象（INV-001 来自未变的 PDF，INV-004、INV-005 为新数据）；Agent 指出 INV-001 重复并等用户决定，未保存 |

| 05 §4.2 期望 | 结果 |
| --- | --- |
| 单来源复用已验证映射，只展示新数据 | 通过 |
| 同样组合的多来源复用 | 不含扫描件通过；含需 `intake_extract` 的扫描件失败（D3）；C-02 组合首次保存即被拦，无已验证映射，未验证 |

## 6. 缺陷与体验问题

代码位置基于 `f84a514`。

| 编号 | 问题 | 复现 | 观察 / 期望 | 位置 |
| --- | --- | --- | --- | --- |
| D1 | 工作区内的绝对路径被拒，提示误导 | `intake_start` 的 `locator_ref` 用 `/…/t50/ws/c01/invoice.pdf` | 四个来源都 `source_unreadable`，`source must be inside the selected workspace`；拖入文件给的就是绝对路径。期望：工作区内绝对路径归一化为相对路径，或提示「请用相对路径」 | `packages/capabilities/dataagent-data/src/dataagent_data/observation/files.py:31-34` |
| D2 | 重新提案会丢掉网页上的当前值纠正，且无人告知 | `cc8be250`：网页纠正 INV-002 币种（预览 `038baab7…@2` 带纠正）→ Agent 再调 `intake_propose_sources` | 新预览 `cac542cb…@1` 无纠正记录，Agent 回复未提及。期望：带上未失效的纠正，或明确告知需重做 | `packages/capabilities/dataagent-workbench/src/dataagent_workbench/intake_service.py:442-475` |
| D3 | 含 `intake_extract` 字段的来源组合不能复用 | 保存 `invoice.pdf + scan.pdf + xlsx` 后，同组合再接入 | 已验证映射按提取后指纹存（`41158657…`），新探查得到提取前指纹（`a78b47ab…`），键对不上；提取指纹还依赖提取步骤（同样三字段分两次提取得 `9c6804ad…`）。期望：扫描件组合也能 `mapping_reused=true` | `…/dataagent_workbench/document_fields.py:63-64`；`intake_service.py:283-290`、`:522` |
| D4 | REST 分页记录的来源行高亮错位 | C-02 对象页点 INV-2026-109（REST 第 3 页 `/items/0`） | 来源表高亮第 1 行（INV-2026-101）；对象详情只写 `/items/0/amount`，看不出是第几页。JSON Pointer 按页从 0 计，页面只比对 selector，不比对 `source_revision` | `…/dataagent-data/src/dataagent_data/observation/http.py:113-116`；`…/dataagent-workbench/web/src/pages/ObjectPage.tsx:109-110` |
| D5 | SQLite 定位显示 `[object Object]` | C-02 对象页任一 SQLite 证据 | `table = invoice · primary_key = [object Object]` | `…/dataagent-workbench/web/src/client.ts:33-35` |
| D6 | 跨页单据被拆成两条记录，无法合并 | C-01 `mixed.pdf`（第 1 页 number + amount_minor，第 3 页 currency） | 第 3 页成为无编号候选，`identity_unresolved` 等 5 条问题阻断保存；`intake_extract` 拒绝跨页：`selected page does not belong to the observed row`。期望：可把第 3 页字段归到第 1 页记录，或给出可操作的出路 | `…/dataagent_workbench/document_fields.py:43` |
| D7 | 保存被拒和预览摘要不点名对象 | C-02 `mapping_apply`；`mapping_preview` | 只返回 `preview contains unresolved issues`；摘要只有 `code`、`target`，没有对象。Agent 因此误判阻断原因（t_2 说是缺键记录，t_1 把 107 也算成金额冲突）。金标 J5 要求「点名这些对象的冲突字段」 | `…/dataagent-ontology/src/dataagent_ontology/service.py:96`；`…/dataagent_workbench/service_tools.py:83-87` |
| U1 | 缺键候选对象难读 | C-01、C-02 对象页 | 名称是 `candidate:<64 位哈希>`；无来源定位时左栏仍显示第一个来源的页面 | `ObjectPage.tsx:108` |
| U2 | 英文原始报错 | 网页纠正后重验 | 红条 `required property remains unresolved` | `…/dataagent_ontology/corrections.py:52` |
| U3 | 待核对清单只显示前 5 条且不带对象 | C-02 13 条问题 | 显示 5 条，均为 `属性 · code` | `ObjectPage.tsx` 中 `view.issues.slice(0,5)` |
| U4 | 纠正值的来源显示为内部路径 | 保存后 INV-003 amount | `— · /decision/changes/value` | `ObjectPage.tsx` 证据列 |
| U5 | Agent 无法列出已配置连接 | C-02 | 工具里没有列连接名的入口，Agent 直接 `fs_read .dataagent/source-connections.json`（只有逻辑名，无令牌值） | `…/dataagent_workbench/tool_schema.py:62-65` |

Agent 与技能行为（不是组件缺陷，影响验收口径）：

| 编号 | 问题 | 出现位置 |
| --- | --- | --- |
| A1 | 用户只说「接进来」时也保存 | C-01 t_2（排错任务 `a8c0dd00`，多出一份发布）；C-03 单来源、含扫描件多来源两次。技能第 4 步写的是「用户要求保存」 |
| A2 | 绕过工作台读原件和内部状态 | `shell_exec` 解 PDF 流、`sqlite3` 读来源库和 `.dataagent/db/workbench.sqlite3`、`curl` 直连 REST、`view_image` 读 `.dataagent/content`、`fs_read` 读连接清单。`--approve all` 下全部放行；技能写了「不要用 shell 绕过工作台校验」 |
| A3 | 单轮成本高 | 输入 token 每轮 19 万至 279 万，C-01 t_1 174 万、C-03 含扫描件那轮 279 万 |

## 7. M1-09、M2-06

| 编号 | 「已验证」条件 | 本次满足的部分 | 未满足 |
| --- | --- | --- | --- |
| M1-09 Mint TUI 复用与保存 | V1.4：发起、网页纠正、返回聊天保存、发布引用、审批策略；复跑时核对任务、发布、工具轨迹 | 发起、网页纠正、回聊天保存、发布引用、工具轨迹齐全（3 份材料任务）；单来源和不含扫描件的多来源 `mapping_reused=true` | 交互式 TUI 未操作、无终端录屏；审批策略只能用 `--approve all`（G1.5）；C-01 原样 4 份材料保存失败（D6）；含扫描件组合不复用（D3）。建议登记「部分通过」 |
| M2-06 来源权限和用户入口 | 从 Mint 双端发起数据库和 API 接入 | TUI 一端：同一 Mint 会话用 SQLite 路径和连接 ID `invoice-api` 发起，令牌哨兵 0 命中 | GUI 一端未做（T51 外部阻断）；Agent 能直接读连接清单并直连 API（A2、U5）。建议登记「部分通过（TUI）」 |

## 8. 未验证及原因

| 项 | 原因 |
| --- | --- |
| 交互式 TUI 与终端录屏 | 本机会话没有 TTY；用同一内核的 `mint run --json` 代替，只有网页的 Playwright 录像 |
| 「拖入」动作本身 | 用话术里写绝对路径模拟 |
| Agent 自己发出的一次性网页入口 | nonce 在 Agent 回合中途发出、60 秒过期，改由驱动脚本调 `/local/open` 取新入口；c01-1 那次 `workbench_view` 由 Agent 启动的服务在本机默认浏览器打开过一次 |
| 「只有冲突、无缺键记录」时的保存阻断 | C-02 样本三源都有缺键记录，映射不支持按行排除 |
| C-02 组合的二次接入 | 首次保存按设计被拦，没有已验证映射 |
| 默认审批策略下走完场景 | 默认策略拒绝 DataAgent 工具（G1.5 / IF-01），只引用预演证据 |
| Mint GUI | 属 T51 |

## 9. 证据包目录

`/Users/payne/Vibe/dataagent-private/t50/evidence/`：

| 路径 | 内容 |
| --- | --- |
| `turns/<场景>-<轮>.{ndjson,stderr,prompt.txt,cmd.txt,summary.json}`、`turns/index.json` | 14 轮的原始事件流、话术、命令与退出码、工具摘要 |
| `mint-sessions/s_*.jsonl` | 5 个 Mint 会话记录（来自 `ws/.mint/sessions`） |
| `screenshots/`、`screenshots/*-web-log.json`、`video/*/` | 网页截图、逐步观察记录、录像 |
| `workbench-tasks.json` | 11 个任务的阶段、发布引用、预览修订、`mapping_reused`、纠正记录（只读导出） |
| `sentinel-scan.json`、`rest-access.log`、`c02-setup.txt` | 哨兵扫描、REST 访问记录、401 校验 |
| `versions.json`、`doctor.txt`、`approval-default-rehearsal.txt` | 版本、doctor 输出、默认审批拒绝证据 |
| `tools/`、`fixtures/` | 驱动脚本、网页计划、第二周 Excel |
| `manifest.json` | 文件清单与 sha256 |
