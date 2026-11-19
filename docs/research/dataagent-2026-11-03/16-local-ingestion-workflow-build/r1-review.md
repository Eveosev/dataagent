---
round: m1-review
date: 2026-11-19
subject: M1 最小 MVP 范围（feat/p1-intake@99266984）
commit: 99266984a110ec7419c8e1bd58dc5c600d38a98a
verdict: 不可验收（浏览器 e2e 门禁不稳定：D1、D2）
---
# M1 独立评审

## 0. 结论

**结论：不可验收，缺陷 2 项（D1、D2），均转 S2（测试隔离与 flaky 计入门禁）。**

M1 六项能力的功能证据齐全：11 个包 1975 项测试通过、2 项跳过，安装产物的 bootstrap / files / sources / discovery / ontology 五个阶段全部通过，D7 本体发现链 36 项检查 35 项通过、1 项不适用。阻断验收的是浏览器 e2e 门禁不稳定：D1 是映射类用例读共享工作区的默认本体，并发下默认指针被其他用例移动；D2 是 `bad-input.spec.ts:45` 首轮 flaky，失败摘要未保留，不能归入 D1。两项都只能由 S2 修复后用连续两次 0 failed、0 flaky 复核。

这里的“齐全”指六项能力都有可复跑的自动化或 T50 证据，不等于每个入口都覆盖：M1-09 的含扫描件复用按矩阵记为部分通过；M1-10 在非 Kernel 布局的 `mint gui` 下已可见 56 个 DataAgent 工具，C-01/C-02 场景待验，打包版 `Mint Agent.app` 仍受 IF-13 阻断。

真实 Agent 运行的安全结论只对记录在案的会话成立：`$PRIVATE_DIR/d7-agent-run/` 的 8 轮未自确认、未越权读取原始材料；收口前的查询抽查 `$PRIVATE_DIR/m1-query-check/` 仍出现擦边读取旧结果与工作区材料、未用工具侧比较、技能注入不稳定、无原文核对入口（L1–L4，见 §4.3 与 §5），不能据此宣称“真实 Agent 不会读取文件”。

D1、D2 修复后连续两次 `verify_browser.py` 达到 0 failed、0 flaky，可改判为可验收。除 D1、D2 外，本评审未发现新的产品功能缺陷；已知限制见 §5。

## 1. 范围与基线

| 项 | 值 |
|---|---|
| 被测提交 | `99266984a110ec7419c8e1bd58dc5c600d38a98a` |
| 工作树 | `55dd1d9e72b516894c0b6a2e4c12c04445164933` |
| 集成分支 | `feat/p1-intake` |
| iface 基线 | `agent-kernel@ae6c3d549244030c790ca5a7e1713484edb7413d`（`packaging/iface-baseline.toml`） |
| 本机验收环境 | Mint CLI 0.1.31；RapidOCR 1.4.4；Chrome（Playwright 系统通道） |
| 评审边界 | 只复跑 M1 已合入卡与 T50；不改代码、测试、分支和 `.git` |

| 层 | 卡 | 合入 |
|---|---|---|
| 前置接入 | T10、T11a、T11c | `9824930d`、`4b41b6cc`、`da7291b7` |
| 文件与工作台 | T20、T21、T14、T13、T22、T23、T25、T26、T26b | `bc7b3c9d`、`3102be0a`、`2e5e24e2`、`f84a5144`、`20a1e27a`、`61f6febe`、`c9ef9147`、`1d1c6931`、`89928a01` |
| 评测与证据 | T30、T31、T32、T38、T50 | `9acb15ef`、`5715ef10`、`e026fd98`、`d2b883a0`、`170d4550` |
| D 线与修复 | D0–D7，R1、R2、W2、E1–E3、V1–V6、V1b、S1、CX1–CX3、D7b、X1–X4 | `34387594`–`99266984` |

T51 的状态以 [gui-channel-check](gui-channel-check.md) 的补充记录为准：非 Kernel 布局的 `mint gui` 冒烟得到 80 个工具，其中 DataAgent 56 个（workbench 13、data 32、operations 11），与 `mint run` 一致；C-01/C-02 尚未在该入口跑。打包版 `Mint Agent.app`（kernel-stdio-v1）看不到工具，仍是 IF-13，不挡 P1。

本轮不覆盖：V1.1–V1.15 全量 P1 验收、V1.16；GUI 的 C-01/C-02（T51，上述入口待跑）；默认审批与治理层（G1.5）；T52 体验观察；T15、T24；T34–T36 的令才 L2/L3；PostgreSQL 验收。

## 2. 复跑总表

| # | 命令 | 退出码 | 关键结果 |
|---|---|---|---|
| 1 | `bash scripts/test_all.sh` | 0 | 11 个包，1975 passed、2 skipped、3 warning；workbench 377 passed |
| 2 | `bash scripts/prepare_acceptance.sh` | 0 | 生成 `build/local`、前端静态资源与安装包 |
| 3 | `bash scripts/verify_local.sh --phase bootstrap --output <dir>` | 0 | `passed`；5 个包（cli、data-layer、workbench、operations、preset-intake）；安装目录无开发仓路径 |
| 4 | `bash scripts/verify_local.sh --phase files --ocr-root "$OCR_ROOT" --output <dir>` | 0 | `passed`；8 份文件样本 + docx + 30 MB 分段 |
| 5 | `bash scripts/verify_local.sh --phase sources --output <dir>` | 0 | `passed`；SQLite、REST token/分页/429、跨源冲突与部分保存 |
| 6 | `bash scripts/verify_local.sh --phase discovery --output <dir>` | 0 | `passed`；表格与文档的发现证据 |
| 7 | `D7_GOLD_DIR="$PRIVATE_DIR/d7-discovery" bash scripts/verify_local.sh --phase ontology --output <dir>` | 0 | `passed`；36 项检查 35 通过、1 不适用 |
| 8 | `$CAP/dataagent-workbench/.venv/bin/python scripts/verify_browser.py`（首轮） | 1 | 73 passed、1 failed、1 flaky、1 skipped；失败 `object-issues.spec.ts:176`，flaky `bad-input.spec.ts:45` |
| 9 | `$CAP/dataagent-workbench/.venv/bin/python scripts/verify_browser.py`（复跑） | 0 | 74 passed、1 flaky、1 skipped；flaky `dispositions.spec.ts:388`；恢复阶段 1 passed、1 skipped |

第 8、9 行的 flaky 是两次不同用例：首轮 `bad-input.spec.ts:45`（D2，失败摘要未保留），复跑 `dispositions.spec.ts:388`（D1）。首轮失败 `object-issues.spec.ts:176` 也在 D1。`verify_browser.py` 把 flaky 计为通过并以 0 退出，M1 收口不能只看退出码。

补充：`cd scripts/acceptance && uv run --no-project --with 'pytest>=8,<9' python -m pytest tests -q` 为 22 passed。

复跑环境说明：受限沙箱下把 `MINT_HOME`、`DATAAGENT_SECRETS_DIR` 指到临时目录，把 `UV_CACHE_DIR`、`npm_config_cache` 指到缓存目录；验收脚本、被测包和变量语义未改。`test_all` 的 2 个 skip 是需要真实 Mint/宿主凭据的用例。各阶段报告只写变量名和汇总值，不写业务值。

## 3. 按 M1 能力项

以下每项列出验收命令、本次结果和证据边界。自动化通过只证明脚本覆盖的路径与断言，不等于人工验收；TUI 的人工观察以 T50 为准，GUI 的对应场景尚未跑。

### 3.1 8 类本地文件、docx、SQLite、带 token REST

验收命令：`bash scripts/verify_local.sh --phase files --ocr-root "$OCR_ROOT"`；`bash scripts/verify_local.sh --phase sources`。

| 本次结果 | 能证明什么 | 不能证明什么 |
|---|---|---|
| 8 份文件样本 coverage 均为 full 或按预期 partial：CSV 2 行、TSV 3 行、XLSX 6 行、JSON 1 行、JSONL 3 行、文本 PDF 12 行、扫描 PDF 1 行；混排 PDF 第 1、3 页完成，第 2 页 `ocr_empty`，coverage=partial | 各文件类型的记录数、锚点数和缺口分区与验收期望一致；扫描 PDF 经 OCR 出数；混排缺口不被静默忽略 | 真实客户文件的版式、低质量扫描、超大表格的识别质量；TUI/GUI 的同一路径（TUI 见 T50，GUI 归 T51） |
| docx coverage=full，正文锚点 `paragraph:2`、表格锚点 `table:1/row:2/col:2`、2 条记录、6 个锚点 | Word 正文与表格均可探查，锚点能回到原文位置 | 复杂页眉页脚、文本框、跨页合并单元格 |
| 30 MB 样本：31,457,352 字节、164,698 行、8 次 advance、单次最长 0.85 秒、一次性 0.78 秒，抽样 2000 行/8000 锚点与一次性结果一致 | 分段探查可完成大文件，分段结果与一次性结果一致 | 宿主真实 60 秒超时、真实模型调用耗时、磁盘/内存压力下的上限 |
| SQLite 复合主键、冲突字段、缺键记录与期望一致；REST 第 1 页 1 次请求，第 2 页遇 429 后续跑完成，最终 3/3 页、来源 coverage=full；错误 token 返回 `authentication_failed`，未生成来源 | 结构化来源、分页、限流续跑与认证失败路径可复现 | PostgreSQL；真实第三方 API 的配额、重试头和分页约定 |

### 3.2 跨源对齐与非静默冲突

验收命令：同上 `--phase sources`。

| 本次结果 | 能证明什么 | 不能证明什么 |
|---|---|---|
| 13 个对象：10 个有键对象 + 3 个缺键候选；5 个冲突字段落在 4 个对象上；6 个冲突事件；保存被 `preview contains unresolved issues` 拦截，阶段停在 `preview`；部分保存只落 6 个无问题对象，4 个挂起、3 条未识别记录带来源定位 | 跨文件、SQLite、REST 能对齐到同一对象；冲突不被静默合并；缺键、冲突、部分保存三条路径都有可核对证据 | 真实业务中同名不同实体、跨业务域、多层父子关系的对齐准确率；PostgreSQL 与更多来源组合 |

### 3.3 工作台网页查看、纠正与保存

验收命令：`$CAP/dataagent-workbench/.venv/bin/python scripts/verify_browser.py`；工作台单测在 `test_all` 内。

| 本次结果 | 能证明什么 | 不能证明什么 |
|---|---|---|
| 复跑 74 passed、1 flaky、1 skipped；覆盖上传、探查、字段选择、分/元转换、预览、刷新恢复、聊天与页面并发、过期决定拒绝、对象页纠正、映射修订、来源预览、冲突核对、docx 表格、坏输入 | 网页主路径在真实后端上可走通；修改决定有版本冲突保护；刷新与服务重启后能恢复 | 稳定性未达标：首轮 1 failed + 1 flaky（`object-issues.spec.ts:176` 失败、`bad-input.spec.ts:45` flaky），复跑 1 flaky（`dispositions.spec.ts:388`），见 D1/D2；真人可用性、首次预览时间与完成时间归 T52 |
| 工作台单测 377 passed | 页面状态、接口契约、错误文案、并发与回滚在组件层有覆盖 | 浏览器渲染、真实用户操作、弱网与窄屏 |

### 3.4 单次工具调用 60 秒、分段续跑、映射复用

验收命令：`bash scripts/test_all.sh dataagent-workbench dataagent-data`；`--phase files`。

| 本次结果 | 能证明什么 | 不能证明什么 |
|---|---|---|
| 30 MB 样本 8 次 advance 完成，单次最长 0.85 秒，分段结果与一次性一致；files 阶段同时校验抽样记录和锚点 | 探查按分区落盘，超预算返回续跑点而不是整段重做；大文件不会在一次调用里做全量 | 宿主 60 秒硬超时、真实网络/OCR 抖动、模型在续跑间隙的决策质量 |
| `test_proposal_loop` 覆盖单来源、多来源、部分失败/429、扫描件变化；无变化复用、变化不复用，不复用时不静默沿用旧映射 | 映射复用有正反例，失败不会伪装成复用 | TUI 中含扫描件的组合（T50 C-03 未在 F6 修复后重跑）；真实用户对“复用/重建”的感知 |

### 3.5 凭据逻辑名注入与 doctor 检查

验收命令：`--phase sources`；`test_all` 内 `dataagent-data`、`dataagent-runtime`、`dataagent-cli` 的凭据与 doctor 测试。

| 本次结果 | 能证明什么 | 不能证明什么 |
|---|---|---|
| REST 连接只保存 `file:rest-token` 逻辑名；哨兵值扫描 0 命中；错误 token 路径请求 1 次后返回认证失败；doctor 输出 OCR 引擎、策略模式、连接数量，未输出密钥 | 凭据不进入连接清单、预览、日志和结果；错误凭据不会重试到成功；doctor 可核对 OCR 与连接状态 | 宿主级环境变量注入和进程隔离（IF-04/PR-3）；GUI 的 keychain 路径；默认审批开启后的行为；第三方服务端日志 |

### 3.6 本体发现 → 人工发布 → 映射 → 查询

验收命令：`D7_GOLD_DIR="$PRIVATE_DIR/d7-discovery" bash scripts/verify_local.sh --phase ontology`；`--phase discovery`；`$PRIVATE_DIR/d7-agent-run/` 与 `$PRIVATE_DIR/m1-query-check/` 的真实 Agent 记录。

| 本次结果 | 能证明什么 | 不能证明什么 |
|---|---|---|
| 36 项检查 35 通过、1 项不适用（N3.gate：本次证据层没有值重合关系候选，金标 J8 允许）；C1 12 个实例、C2 20 个实例、R1 覆盖 16/20、标准端 12/12、260 个属性锚点回放一致；发现→审核→发布→两概念映射→查询全链通过；停用后新任务回退内置本体（N7）、停用本体不能显式选为目标（N8） | D0–D7 的主链、人工确认门禁、身份/粒度/属性/关系约束、修订与停用回退都有脚本化证据；真实 Agent 在 `d7-agent-run` 与 `m1-query-check` 两个会话中走通查询 | 模型生成的提案质量（本轮提案由证据脚本生成）；真实制度文档的命名与单表单概念质量；GUI 渲染；跨业务域泛化；查询汇总的正确性（L1） |

## 4. FDE 两轮审核与真实 Agent 运行

### 4.1 数量与结论

FDE 两轮审核：第一轮（FDE 第 2 轮）15 项问题；第二轮（FDE 第 3 轮）复验 10 已解决、5 部分解决 + 新 11 项（影响 5、轻微 6）。复验的 5 项部分解决为 FDE2-04、FDE2-05、FDE2-06、FDE2-09、FDE2-13；新增 11 项为 FDE3-01 至 FDE3-11。相关报告与 followups 在 `$PRIVATE_DIR/fde-review-2/report.md`、`$PRIVATE_DIR/fde-review-3/report.md`、`$PRIVATE_DIR/followups.md`，本文件只记数量、结论和代码位置。

### 4.2 X1–X4 修复

| 卡 | 合入 | 覆盖 | 本轮核对 |
|---|---|---|---|
| X1 | `e7e3465` | 查询结果瘦身与跨字段比较、提案修订、空结果提示、skill 数字口径（FDE3-02/05/08/11，FDE3-01 查询侧） | 完整结果落 `result_path`；精简页低于内联阈值（查询 32 KB）时随响应内联，20 行约 21 KB 可内联，超过阈值仍落盘；跨字段比较、空结果与 skill 文案有单测 |
| X2 | `99266984` | 修订发布提示“需重连的概念”、日期格式、发现入口文案（FDE3-01 发布侧、FDE3-09、FDE3-10） | 发布页提示与日期格式单测通过；连续修订后的日期格式仍有残留，见 §5 |
| X3 | `2671da1` | 多源单任务来源与概念不符的整源拦截/来源级处置、根因计数、本体库排序与定位合并（FDE3-04、FDE2-06/13 余项） | `mapping-source-fit.spec.ts` 与来源处置用例通过；窄屏属性逐行定位仍未做，见 §5 |
| X4 | `a513263` | 沙箱拒绝 `.dataagent` 内容/数据库、验收时构建前端、审批文档（FDE3-03/06/07） | 沙箱拒绝用例通过；`prepare_acceptance.sh` 会构建前端；审批说明已入文档 |

### 4.3 真实 Agent 运行与收口前查询抽查

`$PRIVATE_DIR/d7-agent-run/` 记录了一次真实 Mint Agent 会话（8 轮，22:40–22:52）：走通发现、人工审核、发布、映射与查询；该会话记录范围内未自确认、未越权读取原始材料；Q1 对齐，C1/C2 身份与金标一致。该轮暴露的 E1/E2 已修复；仍记录了三项轻微摩擦：headless 人工通道 nonce、t6 文案拼写、单表单概念倾向。该记录不替代 TUI 人工验收，也不含业务值。

`$PRIVATE_DIR/m1-query-check/` 是收口前的查询抽查（同一提交、全新会话）：两问答对，但汇总数字出错（L1）；同口径合并问法 23 秒 / 8 步 / 72.6 万 input token（上一轮 86 秒 / 21 步 / 246 万），shell `jq` 0 次；20 行查询结果约 21 KB 内联（上一轮 465 KB 只能读文件）。该次抽查仍暴露四项限制：

- L1 工具侧比较未被采用：`ontology_query` 已支持 `where` 条件里的 `related_field` 跨字段比较（需配 `include_related`），Agent 仍全量拉取后在上下文里心算，汇总数字出错（与 FDE3-08 同类）。
- L2 擦边读文件：读取旧 `.dataagent/results`，并用 shell 解压读取工作区材料 docx 原件；`sandbox.toml` 的 `deny_paths` 不含材料目录，`.dataagent/results/` 为让 Agent 读取 `result_path` 仍保持可读。
- L3 技能注入不稳定：Mint 部分会话 `skill_read=0`，技能约束不总生效；候选 iface 缺口是技能常驻或工具级策略（08 文档 IF 表候选，待 payne）。
- L4 查询侧没有“核对制度原文”的入口，Agent 想核对条款时转去读原件。

因此，M1 的安全证据应表述为：凭据哨兵 0 命中，`d7-agent-run` 会话内未自确认；不能表述为“真实 Agent 不会读取工作区文件”。

### 4.4 已解决、部分解决与新缺陷的边界

- 已解决：FDE2-01、02、03、07、08、10、11、12、14、15，以及 X1–X4 覆盖的阻断/影响项。
- 部分解决：FDE2-04、05、06、09、13；残留分别在完整结果读取成本、单任务单目标、来源级处置余项、空结果提示、窄屏定位，见 §5。
- 新缺陷：FDE3-01 至 FDE3-11 均有对应改动或修复卡；其中 FDE3-09 的日期格式在连续修订下仍有残留。本轮没有做第四轮 FDE 复验，X1–X4 的有效性以单测、e2e 和脚本化验收为依据，不宣称 FDE 已复验通过。
- 收口前查询抽查的 L1–L4 是 FDE 两轮之后的新观察，未做修复或复验，按已知限制登记，不计入已解决。

## 5. 已知限制与后续

下表合并 FDE 两轮审核、X1–X4 核对与 `$PRIVATE_DIR/followups.md` 中仍有效的条目；私有证据只写目录名和聚合数。

| # | 限制 | 位置 | 影响 | 后续 |
|---|---|---|---|---|
| 1 | 一个任务固定一个目标本体/概念 | `packages/capabilities/dataagent-workbench/src/dataagent_workbench/session_service.py:59-78`；`intake_service.py:220-233` | 同任务多概念需要拆任务；FDE2-05 仍为部分解决 | 产品决策后再做多目标，不在 M1 阻断 |
| 2 | 完整查询结果落 `result_path`；精简页低于阈值（32 KB）内联，超过阈值只回路径，Agent 对完整结果的读取成本无上限 | `service_tools.py:252-265`；`query_service.py:562-570`；`inference_requests.py:13-25` | FDE2-04/09 的瘦身覆盖常见页，未解决大结果的读取与分页 | 后续加结果摘要/分页协议；T24 暂缓 |
| 3 | 窄屏下属性逐行定位未做 | `packages/capabilities/dataagent-workbench/web/src/pages/OntologyInstancesPage.tsx` | 小屏对象定位体验差；FDE2-13 部分解决 | 归 T52 体验观察 |
| 4 | 日期格式标记在后续保留 string 的修订中不延续 | `ontology_publish.py:345-360` | 连续修订后默认映射可能回退为带 `T00:00:00` 的字符串；FDE3-09 轻微 | X2 余项，随下次修订卡处理 |
| 5 | 文档发现披露按“任一记录集字段”判断段落 | `discovery_evidence.py:758-779`；`document_fields.py` 无 `_paragraph_text_fields` | 披露范围可能偏大；FDE3-08 相关 | 补段落字段白名单后再收紧 |
| 6 | governance 内置的 `dataagent_contracts/ontology.py` 与主 contracts 漂移 | `packages/capabilities/dataagent-governance/packaging/bundle/src/dataagent_contracts/ontology.py` | 仍是旧单概念形状；治理层导入可能拿到旧模型 | 重新生成 vendored bundle，加一致性测试 |
| 7 | headless 人工通道 nonce 摩擦 | `$PRIVATE_DIR/d7-agent-run/` 记录 | 真实 Agent 运行时多一步手工处理 | 归 T51/T52 的宿主体验 |
| 8 | 真实制度文档的模型命名与单表单概念倾向 | `$PRIVATE_DIR/d7-agent-run/` 记录 | 发现结果可用但命名不够业务化；FDE3-11 轻微 | 提示词/评审规则迭代，不作 M1 阻断 |
| 9 | `dataagent-operations` 的 API workflow 用例在负载下偶发 ReadTimeout | `packages/capabilities/dataagent-operations/tests/test_api_workflow.py` | 全量测试偶发变慢，不影响产品路径 | 调高超时或隔离慢用例 |
| 10 | T24 未做：推理请求在无允许字段时可能带前 5 行/PDF 摘录 | `inference_requests.py:13-25` | 披露面比最小化目标大 | T24 完成前不宣称最小披露 |
| 11 | L1 查询未用工具侧比较：全量拉取后心算，汇总数字出错 | `tool_schema.py:251`；`query_service.py:595` | 与 FDE3-08 同类；token 与时延高，结果可能出错 | 技能/提示词要求先构造 `related_field` 条件；后续加查询模板 |
| 12 | L2 擦边读文件：旧 `.dataagent/results`、工作区材料 docx 可被读取 | `packages/capabilities/dataagent-intake/sandbox.toml:50-58` | 材料原文与历史结果可能进入模型上下文 | 评估把材料目录加入 `deny_paths`；results 需保留可读，改用受控读取入口 |
| 13 | L3 技能注入不稳定：部分会话 `skill_read=0` | Mint 技能注入；08 文档 IF 表候选 | 技能约束不总生效，行为随会话漂移 | 技能常驻或工具级策略；待 payne 定 iface 缺口 |
| 14 | L4 查询侧无原文核对入口 | `tool_schema.py:251` 的查询工具只返回实例 | Agent 核对条款时转去读原件，触发 L2 | 增加条款/原文核对工具或在查询结果带条款引用 |
| 15 | 信任边界为本机单用户 `local-owner`；同用户 shell、工作区材料与旧结果不在文件工具防护范围 | `packages/capabilities/dataagent-workbench/src/dataagent_workbench/bootstrap.py:24-25`；`sandbox.toml:50-58` | 同机同用户进程可绕开工作台直接读文件；M1 不承诺多租户隔离 | 文档明示；多用户/共享工作区前补宿主级隔离 |

## 6. 缺陷清单

本节的 D1、D2 是本评审编号；T50 证据包里的 D1–D7 是另一套编号，引用时写“T50 缺陷”。

| ID | 级别 | 位置 | 现象与复现 | 影响 | 处理建议 |
|---|---|---|---|---|---|
| D1 | P1（阻断验收门禁） | `packages/capabilities/dataagent-workbench/web/tests/object-issues.spec.ts:176`；`dispositions.spec.ts:388`；`support.ts` 的 `pinBuiltinOntology`/`lockDefaultPointer` | 默认 4 worker 跑 `scripts/verify_browser.py`：首轮 `object-issues.spec.ts:176` 在重试后仍失败于“生成映射预览”不可用，页面提示 `ontology is retired for new tasks: sales-model`，目标下拉仍是“销售单据模型（默认）”；复跑时 `dispositions.spec.ts:388` 重试后通过。两个用例都依赖工作区默认本体，没有固定目标 | 同一 suite 两次结果不同，浏览器 e2e 不能作为稳定门禁；M1-07/08 的网页证据只能算“功能通过、门禁不稳定” | S2：所有映射类用例显式 `pinBuiltinOntology(page)`，或每个 worker 独立 workspace；把 flaky 计数纳入门禁（0 容忍）。不动产品代码即可修 |
| D2 | P1（门禁待查） | `packages/capabilities/dataagent-workbench/web/tests/bad-input.spec.ts:45` | 首轮 `verify_browser.py` 中“只有表头的文件直说没有数据行”为 1 flaky，重试后通过；未保留失败摘要。该用例只走到识别与探查失败，不涉及映射目标选择，D1 的共享默认本体解释不直接适用；不能排除共享工作区并发的间接影响 | 无法证明固定本体后即可达到 0 flaky；D2 与 D1 叠加使浏览器门禁的稳定性结论不成立 | S2 追查该用例的失败摘要与复现条件，与 D1 同一张卡收口；修复后连续两次 0 failed、0 flaky |

D1 的根因边界：`publish.spec.ts:127-139` 与 `browse.spec.ts:120-130` 在 `lockDefaultPointer` 内发布/停用并移动或清空注册表默认指针；`object-issues.spec.ts:176` 和 `dispositions.spec.ts:388` 没有调用 `pinBuiltinOntology`，读的是共享默认值。产品侧的停用回退由 ontology 阶段 N7 验证通过，因此这不是“停用后仍默认选中已停用本体”的产品缺陷，而是测试隔离缺陷。

D2 的边界：现有记录只有“1 flaky”，没有该用例的失败页、错误栈或 trace；不能把它归入 D1，也不能假定给映射类用例固定本体后就会消失。S2 需要先保留失败摘要或稳定复现，再决定修法。

复跑命令：

```bash
bash scripts/prepare_acceptance.sh
$CAP/dataagent-workbench/.venv/bin/python scripts/verify_browser.py
```

修复后连续跑两次，要求两次都是 0 failed、0 flaky；当前脚本把 flaky 计为通过并以 0 退出，M1 收口不能只看退出码。

## 7. 结论与建议

1. M1 六项能力的功能证据成立（GUI 的 C-01/C-02 与 M1-09 含扫描件复用除外），可以进入 T54 的合入准备；但**验收结论暂为不可验收**，原因是 D1、D2 使浏览器 e2e 门禁不稳定。S2 合入并连续两次 0 failed、0 flaky 后改判。
2. T51 不再整体外部阻断：非 Kernel 布局的 `mint gui` 已可见 56 个 DataAgent 工具，C-01/C-02 待跑；打包版 `Mint Agent.app` 仍按 IF-13 记为外部阻断，不挡 P1。
3. 建议开一张 S2 测试隔离与 flaky 计入门禁卡：给映射类用例固定内置本体或按 worker 隔离工作区，追查 `bad-input.spec.ts:45` 的 flaky，把 flaky 清单纳入 0 容忍门禁；不改产品逻辑。修复后由 T53 复跑两次并更新本文件结论。
4. 若 S2 在 T54 前未完成，T54 只能记“M1 合入”，不能记 P1 验收；§5 的 15 项限制继续留在 followups，不转成 M1 阻断项。
