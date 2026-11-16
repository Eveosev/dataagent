---
version: v0.1
date: 2026-11-05
stage: S0
kernel: agent-kernel@c1231ab（本地 HEAD，未 fetch；各包 source-ref 记为 f0fa521）
mint: 0.1.26
tests: contracts 117 / runtime 75 / data 649 / application 201 / governance 117 / scenarios 12
basis: 06-data-layer-build/r41-review.md；07-application-layer-build/r41-review.md；08-governance-layer-build/r41-review.md
---

# S0 阶段报告

## 1. 整体进展

### 1.1 范围

| 层 | 设计原子 | S0 原子 | S0 已注册 | S0 之外已实现 |
|-|-|-|-|-|
| 数据层（DA01–DA04、DA13） | 165 | 32 | 32 | 0 |
| 执行应用层（DA05–DA10） | 126 | 13 | 13 | 0 |
| 评测与治理层（DA11–DA12） | 73 | 6 | 6 | 0（DA12.1.2、DA12.1.3 有内部函数，未注册） |
| 持续运行与 FDE（DA14–DA18） | 94 | 0 | 0 | 0 |
| 合计 | 458 | 51 | 51 | 0 |

设计（总规划、四层方案、契约、Catalog、W0 接缝规格）已完成。代码只覆盖 S0；按需、S1、S2、FDE 均未开始。

### 1.2 包

| 包 | 形态 | 内容 | 测试 | 状态 |
|-|-|-|-|-|
| `dataagent-contracts` | Python 库 | 37 个 S0 类型、13 个枚举、68 个 JSON Schema | 117 | 齐全；schema 与模型不等价，版本规则未落实 |
| `dataagent-runtime` | Python 库 | invoke、注册表、存储端口与适配器、复检与外发钩子、表 codec | 75 | 齐全；复检与外发钩子 fail-open；自身 bundle 落后于 src |
| `dataagent-data` | Mint bundle | 数据层 32 项 | 649 | 22 已完成 / 10 部分完成 |
| `dataagent-application` | Mint bundle | 执行应用层 13 项 | 201 | 5 已完成 / 8 部分完成 |
| `dataagent-governance` | Mint bundle | 评测与治理层 6 项 | 117 | 1 已完成 / 5 部分完成 |
| `dataagent-s0` | Mint preset | 组合三个 bundle 与两条端到端 Skill | — | 可本地装；依赖为仓库相对路径 |
| `dataagent-scenarios` | 测试包 | 跨层与三进程 MCP 场景 | 12 | 两族各一条链到验收报告；中间步骤覆盖不全 |

`contracts` 与 `runtime` 已 vendoring 进三个 bundle，不单独安装。

### 1.3 S0 部分完成项

| 层 | 原子 | 缺口 |
|-|-|-|
| 数据层 | DA01.4.6、DA02.1.1、DA02.2.1 | 经 `workbook_ref` / `region` 入口读文件不做访问复检 |
| 数据层 | DA01.5.1、DA01.5.2 | 未装 OCR 引擎，调用返回 `dependency_unavailable`；只有桩引擎测试 |
| 数据层 | DA03.4.1 | 来源谓词校验不识别 or / except / 否定 |
| 数据层 | DA03.15.2–15.4 | 直接信任调用方传入的 Assessment |
| 执行应用层 | DA06.1.2 | 过滤输出不能被 DA06.3.1 消费 |
| 执行应用层 | DA06.3.1、DA07.1.3 | 口径校验可绕过；超时路径失效 |
| 执行应用层 | DA06.3.5 | 不支持的条件按 true 编入 |
| 执行应用层 | DA07.5.2 | 截断后总体结论可为 pass |
| 执行应用层 | DA07.10.1 | wheel 校验和不可验证 |
| 执行应用层 | DA10.1.1、DA10.3.3 | 公式注入；html / docx 丢依据段 |
| 评测与治理层 | DA11.5.1 | 确认人自报、过期确认被接受 |
| 评测与治理层 | DA11.5.5 | 报告泄漏金标；剔除样本退出分母；空金标判 pass |
| 评测与治理层 | DA11.5.6 | 按 revision 字符串去重 |
| 评测与治理层 | DA12.1.1、DA12.1.4 | 见 1.4 |

### 1.4 阻断项

未修复前不能做 S0 验收，不能处理真实敏感数据。编号对应三份 r41 评审。

| 编号 | 问题 | 位置 |
|-|-|-|
| X1 | 主体与用途由调用方在 `context` 中自报；`subject_ref` 为空时跳过主体比对；三个 bundle 均未注入 `DATAAGENT_HOST_*` | 08 r41 §1 |
| X2 | 复检只检查 `resource_fields` 声明的字段：应用层 13 项与数据层 10 项未声明；`policy:` 授权按 `table@*` 求值，绕过显式 deny | 08 r41 §1 |
| X3 | 应用层 bundle 未注入 enforce，在 preset 中以 warn 运行 | 08 r41 §1 |
| X4 | 外发检查只认 `content` 键；数据层未接入；中文语境身份证与带分隔符号码漏检 | 08 r41 §1 |
| X5 | 字段 / 行约束与脱敏义务不执行 | 08 r41 §1 |
| D1、D2 | 备选入口字段与 label revision 绕过数据层复检 | 06 r41 §3 |
| A1–A4 | 口径校验绕过；无访问复检；固定过滤不闭合；不支持条件按 true | 07 r41 §4 |
| G1–G3 | 验收报告泄漏金标、剔除样本退出分母、空金标判 pass | 08 r41 §2.6 |

### 1.5 未验证

| 项 | 现状 |
|-|-|
| `mint add` 真实安装 | 离线 `mint pack` 四包成功，数据层 `mint publish --dry-run` 通过；`mint add` 需先写 `~/.mint/trust.toml`，未在本机完成 |
| mint-core 按 bundle `.mcp.json` 拉起 MCP、`mint run` | 未验证 |
| 三个 MCP 共享 `<workspace>/.dataagent/` | bundle 未注入 `DATAAGENT_DATA_ROOT`，取决于 Mint 拉起子进程的 cwd |
| 真实 OCR 引擎 | 未安装 rapidocr |
| 发布到 Mint Hub | 未发布；preset 依赖为 path |

### 1.6 阶段结论与下一步

当前状态可用于演示、联调和原子级功能验证，不可用于验收和真实数据。

| 顺序 | 工作 | 关闭 |
|-|-|-|
| 1 | 宿主权威：主体为空即拒；三个 `.mcp.json` 注入 `DATAAGENT_HOST_*`、enforce、`DATAAGENT_DATA_ROOT` | X1、X3 |
| 2 | 复检 fail-closed：注册时校验 `resource_fields`；应用层补声明；数据层补备选字段；label revision 不跳过闭包；删除 `policy:` 引导分支 | X2、D1、D2、A2 |
| 3 | 外发检查覆盖 W0 §5 全部内容键，数据层接入；敏感识别补中文与分隔符 | X4 |
| 4 | 验收防操纵：notes 不含金标、空金标判 fail、剔除样本留在分母 | G1–G3 |
| 5 | 应用层：执行前复核口径；不支持条件返回 `needs_input` | A1、A3、A4 |
| 6 | 制品：经 Mint loader 安装后跑端到端；preset 改版本约束并发布 | 1.5 |

## 2. Mint 本地测试流程

### 2.1 前提

| 项 | 要求 |
|-|-|
| mint | 0.1.26（`mint doctor` 无问题） |
| uv、Python | bundle `.mcp.json` 以 `uv run --frozen --project $PKG` 拉起；Python ≥ 3.11；本机 uv 缓存无依赖时首次拉起需联网 |
| 仓库 | `/Users/payne/Vibe/AgentOS` 存在；preset 依赖指向 `packages/capabilities/dataagent-*/packaging/bundle` |
| 模型 | `mint config edit` 或桌面设置中配置一次 |

### 2.2 新建 workspace 并安装

```bash
mkdir -p ~/dataagent-e2e && cd ~/dataagent-e2e
mint init --no-preset --offline -y        # 写 mint.toml、AGENTS.md、skills/，记录项目信任
mint add path:../../../packages/capabilities/dataagent-s0 -y
mint list                                  # 预期 4 个包：preset-s0、data-layer、application-layer、governance-layer
mint inspect dataagent/data-layer --abilities
```

只装单个层时，把 `path:` 换成 `packages/capabilities/dataagent-{data,application,governance}/packaging/bundle`。

### 2.3 预置访问策略

MCP 与 CLI 都没有配置策略的入口；不预置时 enforce 下首次 `check_access_scope` 无可用策略，后续读取全部被拒。在 workspace 根目录执行：

```bash
/Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-governance/.venv/bin/python -I - <<'EOF'
from pathlib import Path
from dataagent_governance.contracts import EgressRule, PolicyDocument, PolicyRule
from dataagent_governance.runtime import GovernanceRuntime
ws = Path.cwd()
rt = GovernanceRuntime.create(workspace_root=ws, data_root=ws / ".dataagent")
print(rt.policy.save(PolicyDocument(
    policy_id="tenant:default", revision="r1",
    rules=[PolicyRule(rule_id="allow-e2e", effect="allow", subjects=["user:alice"],
                      resources=["file", "table", "doc", "rule"], purposes=["monthly_report"])],
    egress_rules=[EgressRule(rule_id="local-ok", effect="allow", deployments=["local"])],
)))
EOF
```

预期输出 `tenant:default@r1`，生成 `.dataagent/db/governance.sqlite3` 与 `decisions.sqlite3`。

### 2.4 测试数据

| 类型 | 用途 | 来源 |
|-|-|-|
| CSV | DA01.4.3、计算族 | 自建 `orders.csv`；`packages/capabilities/dataagent-data/fixtures/claims.csv` |
| JSON | DA01.4.4 | `packages/capabilities/dataagent-data/fixtures/expense.json` |
| 规整 xlsx | DA01.4.1、DA01.4.6 | 自建；含公式单元格一张 |
| 不规则 xlsx | DA01.4.2、DA02.1.1、DA02.2.x | 自建：多行表头、合并单元格、合计行、一页多表 |
| 文本 PDF | DA01.4.5、判定族 | 自建：含金额、审批人、日期的报销单 |
| 扫描 PDF / 图片 | DA01.5.x | 装 rapidocr 后使用 |

测试文件放在 workspace 根目录，只用脱敏或合成数据。

### 2.5 启动

```bash
mint chat                    # 终端界面
mint run -y "按 dataagent-s0-compute 技能，统计 orders.csv 中各地区订单金额合计并出验收报告"
```

这两条命令尚未在本机验证（1.5）。首次启动后先确认三个 MCP 服务都已列出工具：数据层 32、应用层 13、治理层 6。

对 Agent 的固定说明：

- 调用上下文 `context` 填 `request_id`、`scope_ref=tenant:demo`、`authorization_ref`、`subject_ref=user:alice`、`purpose=monthly_report`（X1 修复前身份由调用方提供）。
- 读任何文件或表之前先调 `check_access_scope`，用返回的 `decision.decision_id` 作为后续调用的 `authorization_ref`。
- 计算族在 `parse_*` 之后调 `classify_table_rows`（Skill 未列出，见 08 r41 §4）。
- 判定族在抽取之后调 `define_business_rules`（Skill 未列出）。

### 2.6 调用约定

| 项 | 规则 |
|-|-|
| CallContext 必填 | `request_id`、`scope_ref`、`authorization_ref`；缺任一项返回 `invalid_input`（`invalid CallContext`） |
| 授权 | `check_access_scope{resource_ref: "file@*"}` 等得到 `decision_id`（`ad:…`）；数据层读取时作为 `authorization_ref` |
| 两段式 | 第一次不带 `proposal` → `needs_input`，`issues[0].inference_request` 给出 kind、instruction 与候选；Agent 推理后带 `proposal` 再调 |
| 外发 | enforce 下两段式请求的内容需 EgressDecision 覆盖：`check_model_context_egress{content_refs, destination, access_decision_ref}` 得 `decision_id`，作为 `egress_decision_ref` 回传；无覆盖时返回 `da12.egress_required` 且请求内容被剥离 |
| 结果 | `status ∈ ok / partial / needs_input / failed`；`deny`、验收 `fail` 是 `status=ok` 的业务结论 |

### 2.7 验收判据确认

确认只能经 CLI，确认人来自环境变量：

```bash
DATAAGENT_WORKSPACE=$PWD DATAAGENT_DATA_ROOT=$PWD/.dataagent DATAAGENT_CONFIRMERS=user:boss \
  /Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-governance/.venv/bin/python -I \
  -m dataagent_governance.interfaces.cli confirm-criteria criteria.json
```

### 2.8 结果检查

| 位置 | 内容 |
|-|-|
| `.dataagent/content/` | 内容寻址对象（表、文档块、报告） |
| `.dataagent/db/dataagent.sqlite3` | 版本库、轨迹 |
| `.dataagent/db/decisions.sqlite3` | AccessDecision、EgressDecision |
| `.dataagent/db/governance.sqlite3` | 策略、判据 |
| `.dataagent/vault/` | 验收样本与金标 |

`.dataagent/` 应只有一套；出现多套或数据层报找不到 decision，说明三个 MCP 未共享 data_root。

### 2.9 已知限制

| 现象 | 原因 | 处理 |
|-|-|-|
| 应用层访问不通过只告警 | X3 | 观察即可；专项测试用 2.10 的 CLI 方式设 enforce |
| 合计行被计入求和 | Skill 漏 `classify_table_rows` | 按 2.5 说明 |
| 扫描件失败 | 无 OCR 引擎 | 用文本 PDF |
| 判据激活失败 | 只能 CLI 确认 | 按 2.7 |
| 换用户身份仍可读取 | X1 | 不作为通过依据 |

### 2.10 不经 Mint 的原子调用

原子级测试不需要 Agent 与 Mint，直接调各包 CLI（stdin 为 `{"...input...", "context": {...}}`，stdout 为 CapabilityResult JSON；退出码 0 = ok / partial / needs_input，1 = failed，2 = 用法错误）。

```bash
cd ~/dataagent-e2e
export DATAAGENT_WORKSPACE=$PWD DATAAGENT_DATA_ROOT=$PWD/.dataagent DATAAGENT_ENFORCEMENT_MODE=enforce
CAP=/Users/payne/Vibe/AgentOS/packages/capabilities
export CTX='{"request_id":"req:1","scope_ref":"tenant:demo","authorization_ref":"seed","subject_ref":"user:alice","purpose":"monthly_report"}'

# da <layer> <operation> '<input json>'：把 $CTX 并入 context 后调用
da() { echo "$3" | python3 -I -c 'import json,sys,os;d=json.load(sys.stdin);d["context"]=json.loads(os.environ["CTX"]);print(json.dumps(d))' \
  | $CAP/dataagent-$1/.venv/bin/python -I -m dataagent_$1.interfaces.cli "$2"; }

# fr <file>：按文件字节生成 FileRef（id 由 digest 派生）
fr() { python3 -I -c 'import hashlib,json,sys;n=sys.argv[1];b=open(n,"rb").read();d="sha256:"+hashlib.sha256(b).hexdigest()
print(json.dumps({"id":"file:"+d[7:23],"kind":"file","scope_ref":"tenant:demo","revision":d,"resolver":"workspace","locator":n,"digest":d,"content_digest":d}))' "$1"; }

# 授权 → 解析 → 行分类
AD=$(da governance check_access_scope '{"resource_ref":"file@*"}' | python3 -I -c 'import json,sys;print(json.load(sys.stdin)["data"]["decision"]["decision_id"])')
TD=$(da governance check_access_scope '{"resource_ref":"table@*"}' | python3 -I -c 'import json,sys;print(json.load(sys.stdin)["data"]["decision"]["decision_id"])')
CTX=${CTX/seed/$AD} da data parse_delimited_file "{\"file_ref\":$(fr orders.csv)}" > parsed.json
T=$(python3 -I -c 'import json;print(json.dumps(json.load(open("parsed.json"))["data"]["table"]))')
CTX=${CTX/seed/$TD} da data classify_table_rows "{\"table_ref\":$T}"
```

以上序列在临时 workspace 中实测：`parse_delimited_file` → ok、`row_count=3`；同一调用用 `authorization_ref=seed` → `failed / da12.access_denied`；`classify_table_rows`、`profile_table_structure` → ok；`acquire_and_align_engine{engine_id:"duckdb"}` → ok、`installed_version=2.0.0`；`ocr_image` → `failed / dependency_unavailable`；`define_business_rules` 第一次调用 → `needs_input / da03.inference_required`。

两段式原子在 enforce 下需要 2.6 的外发决策，且 `content_refs` 须是内容寻址对象。原子级测试两段式时把 `DATAAGENT_ENFORCEMENT_MODE` 设为 `warn`；外发闭环按 `packages/capabilities/dataagent-scenarios/tests/test_s0_mcp_e2e.py` 的判定族链路测试。

## 3. 原子测试方法

### 3.1 层级

| 层级 | 方式 | 覆盖 |
|-|-|-|
| L1 包内测试 | 各包 `.venv/bin/python -m pytest -p no:cacheprovider -o addopts=''`（直接 `.venv/bin/pytest` 在 application / governance 有 collection error） | 已有 1171 例 |
| L2 原子 CLI | 2.10 的 `da` / `fr` | 本节逐项方法 |
| L3 端到端 | Mint workspace 中 Agent 按 Skill 调用（第 2 节）；`dataagent-scenarios` 三进程 MCP 测试 | 两族链路 |

### 3.2 每个原子的检查项

| 检查 | 方法 | 通过标准 |
|-|-|-|
| 正例 | 按 3.4–3.6 的输入调用 | `status=ok`（或表中注明的 `partial` / `needs_input`），输出字段齐全，与输入数据一致 |
| 契约反例 | 删一个必填输入；或加一个未知字段 | `failed / invalid_input`；治理层 6 项当前忽略未知字段（G10） |
| 访问反例（实测见 2.10）  | 仅对“复检=是”的原子：`authorization_ref` 改为 `seed` 或另一主体的 decision | `failed / da12.access_denied`，`data=null` |
| 两段式 | 仅对“两段式=是”的原子：不带 `proposal` 调用；再带 `proposal` 调用 | 第一次 `needs_input` 且有 `inference_request`；第二次 `ok`，或提案与来源不一致时 `partial` 并列出 unresolved |
| 落库 | 写入类原子（W）调用后查 2.8 的存储 | 有对应版本或对象；同一输入重复调用不产生冲突的第二份 |
| 已知缺陷复测 | 用 r41 评审的复现输入 | 修复前与评审记录一致；修复后应改为拒绝或降级 |

“两段式”的提案格式以“参考测试”列中的测试文件为准。

### 3.3 输入来源

| 产物 | 生产原子 | 消费原子 |
|-|-|-|
| `FileRef` | `fr`（2.10） | DA01.x |
| `TableRef`（`data.table` / `data.tables[]`） | DA01.4.1–4.3、DA02.2.x | DA02.2.x、DA02.4.x、DA06.x、DA07.x、DA11.2.3 |
| `TableRegion`（`data.regions[]`） | DA02.1.1、DA01.4.2 | DA02.2.1 |
| `DocumentRef`（`data.document`） | DA01.4.5、DA01.5.x | DA02.8.x、DA02.12.x、DA03.4.x、DA03.16.x |
| `ExtractionSchemaRef` | DA02.12.4 | DA02.12.1 |
| `MetricDefinition` / `RuleDefinition`（`data.draft`） | DA03.4.1 / DA03.4.3 | DA06.1.1、DA06.3.1 / DA06.3.5 |
| `RequirementSpec`（`data.requirement`） | DA06.1.1 | DA06.1.3、DA06.1.4、DA06.3.1 |
| `ExecutableSpec`（`data.spec`） | DA06.3.1 / DA06.3.5 | DA07.1.3 / DA07.5.x、DA11.2.3 |
| `ComputedResult`（`data.result`） | DA07.1.3 | DA10.1.1、DA11.5.5 |
| `Assessment` | DA03.15.1、DA07.5.x | DA03.15.2–15.4、DA11.5.5 |
| AccessDecision / EgressDecision | DA12.1.1 / DA12.1.4 | 所有读取与两段式原子 |

### 3.4 数据层

复检=是：输入中 `resource_fields` 声明的字段会做访问复检。W：写入类。

| 原子 | operation | 必填输入 | 复检 | 两段式 | W | 正例 | 专项反例 | 参考测试 |
|-|-|-|-|-|-|-|-|-|
| DA01.4.1 | `parse_regular_excel` | `file_ref`（规整 xlsx） | 是 | 否 | 是 | `tables[]` 每张表列数、行数与原表一致；`source_content_digest` 等于文件 sha256 | 非 xlsx 文件 → failed；含公式单元格时按 `formula_policy` 处理 | `test_round4_acceptance_gaps.py`、`test_round4_structure.py` |
| DA01.4.2 | `extract_irregular_excel` | `file_ref`（不规则 xlsx） | 是 | 否 | 是 | `regions[]` 与 `tables[]` 对应各块；多行表头恢复为单层列 | 无法确定的结构进入 `ambiguities`，不静默猜测 | `test_w0_field_identity.py`、`test_ingestion.py` |
| DA01.4.3 | `parse_delimited_file` | `file_ref`（CSV） | 是 | 否 | 是 | orders.csv：`row_count=3`、`bad_rows=[]` | 列数不齐的行进入 `bad_rows`；GBK 文件 `encoding` 正确 | `test_interfaces.py`、`test_ingestion.py` |
| DA01.4.4 | `parse_json_records` | `file_ref`（JSON / JSONL） | 是 | 否 | 是 | expense.json：`batch`、`fields` 与记录一致 | `records_path` 指向不存在路径 → failed | `test_round4_unit_anchors.py`、`test_ingestion.py` |
| DA01.4.5 | `parse_text_pdf` | `file_ref`（文本 PDF） | 是 | 否 | 是 | `document.page_count` 等于页数；块文本含原文金额 | 扫描件：不得以空文本 ok 返回 | `test_round14_tester_findings.py`、`test_round13_reviewer_findings.py` |
| DA01.4.6 | `inspect_workbook_calc_state` | `file_ref` 或 `workbook_ref` | 是（仅 `file_ref`） | 否 | 否 | 含未重算公式的 xlsx：`state` 标出需重算 | D1：`{workbook_ref:{file_ref:<未授权文件>}}` 当前 ok，修复后应拒 | `test_round4_storage.py` |
| DA01.5.1 | `ocr_pdf` | `file_ref`（扫描 PDF） | 是 | 否 | 是 | 装 rapidocr 后：`document` 有块与置信度 | 未装引擎 → `failed / dependency_unavailable`（当前行为） | `test_round2_repair.py` |
| DA01.5.2 | `ocr_image` | `file_ref`（图片） | 是 | 否 | 是 | 同上；低置信块进入 `low_confidence_blocks` | 同上 | `test_round2_repair.py`、`test_round4_unit_anchors.py` |
| DA02.1.1 | `detect_workbook_regions` | `file_ref` 或 `workbook_ref` | 是（仅 `file_ref`） | 否 | 否 | 一页多表：`regions[]` 数量与边界正确 | D1 同 DA01.4.6 | `test_preparation.py` |
| DA02.2.1 | `recover_headers` | `region` 或 `table_ref` | 是（仅 `table_ref`） | 否 | 是 | 多行表头：`columns` 合并为单层，`header_rows` 正确 | D1：经 `region.workbook_ref` 读未授权文件当前 ok | `test_round4_storage.py` |
| DA02.2.2 | `expand_merged_cells` | `table_ref` | 是 | 否 | 是 | 合并单元格展开，`expanded_ranges` 列出范围 | `allow_propagation=false` 时不向下填充 | `test_round4_acceptance_gaps.py`、`test_round4_structure.py` |
| DA02.2.3 | `classify_table_rows` | `table_ref` | 是 | 否 | 是 | 合计行、小计行的 `roles` 不是 detail | 无合计行的表全部为 detail | `test_scenarios.py` |
| DA02.4.1 | `profile_table_structure` | `table_ref` | 是 | 否 | 是 | `profile` 含行数、空值率；`fields` 与列一致 | `budget_rows` 小于行数时标明抽样 | `test_round4_storage.py`、`test_enforcement_gate.py` |
| DA02.4.3 | `infer_field_types` | `table_ref` 或 `profile_ref` | 是 | 否 | 否 | 数值、日期、文本列类型正确 | 混合类型列进入 `conflicts` | `test_preparation.py`、`test_scenarios.py` |
| DA02.8.1 | `segment_document` | `document_ref` | 是 | 否 | 是 | `units` 覆盖全文、顺序正确 | `max_units` 小于实际单元数 → 报 truncated | `test_round4_unit_anchors.py`、`test_round17_tester_findings.py` |
| DA02.8.2 | `maintain_source_anchors` | `anchors`、`current_revision` | 是（`document_ref`） | 否 | 是 | 文档改版后锚点重映射，生成 `mapping_version_ref` | 原文已删除的锚点不得映射到其它位置 | `test_round4_unit_anchors.py`、`test_documents.py` |
| DA02.12.4 | `register_extraction_schema_version` | `fields` | 否 | 否 | 是 | 返回 `schema_id`、`revision`、`digest` | 过期 `expected_revision` 应报冲突 | `test_documents.py`、`test_round5_regressions.py` |
| DA02.12.1 | `extract_fields_to_schema` | `document_ref`（+ `target_schema_ref`） | 是 | 是 | 是 | 第二阶段 `record` 字段值均可在原文找到 | 提案值不在原文 → 不作为 extracted | `test_round4_unit_anchors.py`、`test_documents.py` |
| DA02.12.3 | `anchor_extracted_values` | `record`、`document_ref` | 是 | 否 | 是 | `mappings` 给出每个值的原文位置 | 原文找不到的值进入 `unlocated` | `test_anchor_value_acceptance.py` |
| DA03.4.1 | `define_metric_formula` | `statement`（+ `sources` / `document_ref`） | 是（`document_ref`） | 是 | 是 | 第二阶段 `draft` 的聚合、过滤与来源一致 | D5：来源含 or / except 时提案合取过滤当前 ok，修复后应 partial | `test_w0_field_identity.py`、`test_semantics.py` |
| DA03.4.3 | `define_business_rules` | `statement` | 是（`document_ref`） | 是 | 是 | 第一阶段 `needs_input / da03.inference_required`；第二阶段 `draft` 条件与原文一致 | 提案改动否定、情态、界限 → partial 且不落库 | `test_semantics.py`、`test_round6_reviewer_findings.py` |
| DA03.15.1 | `assess_automatic_decidability` | `requirement_ref`、`statement` | 否 | 是 | 是 | `verdict` 为 auto 时 `basis_refs` 可解析、`unknowns` 为空 | 伪造 `basis_refs` → 降级 needs_evidence 且不落库 | `test_semantics.py` |
| DA03.15.2 | `identify_evidence_or_human_gaps` | `assessment`（来自 15.1） | 否 | 否 | 否 | `gaps` 与 `unknowns` 对应，`routes` 给出补证或人工 | D4：伪造 auto + unknowns 当前 gaps=0 | `test_scenarios.py`、`test_semantics.py` |
| DA03.15.3 | `mark_automation_coverage` | `requirements` | 否 | 否 | 否 | `total = covered + needs_evidence + human` | D4：伪造 auto 当前计入 covered | `test_scenarios.py` |
| DA03.15.4 | `resolve_decidability_cache` | `prior`、`current_dependencies` | 否 | 否 | 否 | 依赖未变 → `hit=true`；变化 → `hit=false` 并列 `changed_dependencies` | D4：调用方伪造 `previous_dependencies` 当前 hit=true | `test_round17_tester_findings.py`、`test_semantics.py` |
| DA03.16.1 | `define_rule_applicability` | `rule_ref` | 是（`document_ref`） | 是 | 是 | `scope_expression` 与原文适用范围一致 | 提案改写否定、界限或连接词 → partial | `test_scenarios.py`、`test_semantics.py` |
| DA03.16.2 | `define_rule_preconditions` | `rule_ref` | 是（`document_ref`） | 是 | 是 | `draft` 条件有锚点；带 `facts` 时 `evaluation` 给出满足情况 | 无锚点条件 → 不判 satisfied | `test_round12_reviewer_findings.py`、`test_semantics.py` |
| DA03.16.3 | `normalize_precondition_references` | `conditions` | 否 | 否 | 否 | 同义引用按 `synonyms` 归一，`mapping` 正确 | `conflicts` 当前恒为 `[]`（已知） | `test_semantics.py` |
| DA03.16.4 | `resolve_unknown_applicability` | `applicability` | 否 | 否 | 否 | 证据齐全 → 明确 verdict | `missing_evidence` 非空 → unknown 且列 `next_actions` | `test_semantics.py` |
| DA04.1.1 | `append_task_event` | `task_ref`、`event_id`、`actor_ref` | 否 | 否 | 是 | 返回 `event_id`、`timestamp`、`payload_ref`（实测 ok） | X2：enforce + 伪造授权当前 ok；同一 `event_id` 不产生两条不同记录 | `test_traces.py`、`test_round13_reviewer_findings.py` |
| DA04.1.2 | `append_invocation_record` | `task_ref`、`invocation_id`、`operation`、`capability_id`、`implementation_ref`、`started_at` | 否 | 否 | 是 | 记录可按 `task_ref` 读回 | 缺 `started_at` → invalid_input | `test_traces.py` |
| DA04.1.3 | `append_user_correction` | `task_ref`、`target_ref`、`explanation`、`scope_ref` | 否 | 否 | 是 | 返回含 `old_value` / `new_value` 的更正记录 | 无 `scope_ref` → invalid_input | `test_trace_acceptance.py`、`test_round2_repair.py` |

### 3.5 执行应用层

应用层 13 项均未声明 `resource_fields`，访问反例当前全部放行（A2）；修复后按 3.2 访问反例测试。

| 原子 | operation | 必填输入 | 两段式 | W | 正例 | 专项反例 | 参考测试 |
|-|-|-|-|-|-|-|-|
| DA06.1.1 | `bind_metrics_and_dimensions` | `statement`（+ `table_ref`、`metrics`） | 是 | 否 | 第二阶段 `requirement` 中指标与维度 id 均来自候选列表 | 提案引用候选外 id → 拒绝；enforce 无外发决策 → `da12.egress_required` | `test_planning_requirements.py`、`test_r40_egress_content_binding.py` |
| DA06.1.2 | `parse_time_and_filters` | `statement` | 是 | 否 | `time_range` 端点与原句一致；`filters` 引用 field_id | 无法解析的部分进入 `unresolved`；A3：输出过滤交 DA06.3.1 当前不可满足 | `test_planning_requirements.py` |
| DA06.1.3 | `identify_calculation_ambiguities` | `statement` | 是 | 否 | 缺时间边界、单位时 `ambiguities` 含 `time_boundary`、`unit` | 无歧义语句不产生 blocking 项 | `test_planning_requirements.py` |
| DA06.1.4 | `generate_clarification_questions` | `requirement` | 是 | 否 | 每个 blocking 歧义对应一个 `questions` 项 | blocking 未答 → `needs_input`，`still_blocking` 非空 | `test_planning_requirements.py` |
| DA06.3.1 | `generate_single_table_sql` | `table_ref`（+ `requirement`、`metrics`） | 是 | 否 | 第二阶段 `spec` 的聚合、度量列、固定过滤与口径一致 | r20–r32 走私形状 → failed；A1：不传 `requirement` 当前跳过校验 | `test_planning_expressions.py`、`test_r40_egress_content_binding.py` |
| DA06.3.5 | `generate_function_expressions` | `rule`（+ `fields`） | 是 | 否 | 第二阶段 `spec` 的布尔结构与 `rule.combination` 真值表一致 | A4：声明 unsupported 的条件当前按 true 编入 | `test_planning_expressions.py`、`test_r38_egress_binding.py` |
| DA07.1.3 | `execute_duckdb_sql` | `spec`（+ `table_refs`） | 否 | 否 | `result.value` 与手算一致；`row_count`、`truncated` 正确 | `read_csv('/etc/passwd')` 等外部访问 → 拒绝；A1：伪造 spec 当前可执行；A5：`max_seconds=1` 长查询当前返回 `execution_unknown` | `test_execution_sql.py` |
| DA07.10.1 | `acquire_and_align_engine` | `engine_id`（`duckdb` / `expression`） | 否 | 否 | `installed_version` 与锁定版本一致（实测 duckdb 2.0.0） | `expected_version` 不一致 → `failed / da07.engine_version_mismatch`（实测）；A10：传 `wheel_digest` 当前返回 `da07.engine_digest_unavailable` | `test_execution_sql.py`、`test_interfaces.py` |
| DA07.5.1 | `evaluate_scalar_expression` | `spec`（+ `record`） | 否 | 否 | 满足 → pass，不满足 → fail | 字段 missing → unknown；`applicable=false` → 不判 pass；A12：`and("张三")` 当前 pass | `test_execution_expressions.py` |
| DA07.5.2 | `evaluate_table_expression` | `spec`、`table_ref` | 否 | 否 | `verdicts` 逐行正确，`counts` 合计等于行数 | A6：`max_rows` 截断后总体 verdict 当前可为 pass | `test_execution_expressions.py` |
| DA10.1.1 | `build_result_workbook` | `result`（来自 DA07.1.3） | 否 | 是 | `sheets` 含三张表，数值与 `result` 一致 | A8：`=` 开头的字符串当前写成公式 | `test_presentation.py` |
| DA10.3.1 | `compose_document_report` | `title`、`conclusion` | 否 | 是 | `markdown` 含结论、各节与依据 | section 引用不存在的 `evidence_refs` → 拒绝 | `test_presentation.py` |
| DA10.3.3 | `export_report_format` | `format`（+ `report_ref` 或 `draft`） | 否 | 是 | md / html / docx 均生成 `asset` | A11：html / docx 当前缺依据段 | `test_presentation.py` |

### 3.6 评测与治理层

| 原子 | operation | 必填输入 | 复检 | 两段式 | W | 正例 | 专项反例 | 参考测试 |
|-|-|-|-|-|-|-|-|-|
| DA12.1.1 | `check_access_scope` | `resource_ref`（如 `file@*`、`table@*`、`rule:<id>@<digest>`） | 否 | 否 | 是 | 策略内主体与用途 → `decision.decision=allow`，有 `decision_id`（实测） | 策略外主体 → deny / indeterminate；X1：省略 `subject_ref` 当前放行；X2：`policy:` 开头的授权当前绕过 deny | `governance/test_access.py` |
| DA12.1.4 | `check_model_context_egress` | `content_refs`、`destination`、`access_decision_ref` | 否 | 否 | 是 | local 部署 → allow，有 `decision_id` | vendor_api + 敏感内容 → allow_masked 或 deny；X4：中文身份证、带分隔手机号当前漏检 | `governance/test_access.py`、`governance/test_r24_fixes.py` |
| DA11.5.1 | `draft_acceptance_criteria` | 无（建议 `delivery_target`） | 否 | 是 | 第二阶段 `criteria` 为 draft；经 2.7 确认后为 active | 第一阶段当前以 `invalid_input` 码返回 `needs_input`（G9）；G5：过期确认、自报确认人当前被接受 | `evaluation/test_criteria.py`、`governance/test_r24_fixes.py` |
| DA11.5.6 | `isolate_acceptance_samples` | `cases`、`group_keys` | 否 | 否 | 是 | `freeze=true` 后 `evaluation_set` 冻结，同组样本不跨集 | G6：label revision 相同的不同样本当前被去重 | `governance/test_r24_fixes.py`、`evaluation/test_acceptance.py` |
| DA11.5.5 | `evaluate_business_acceptance` | `criteria_ref`（active）、`evaluation_set_ref`（frozen）、`deliveries` | 否 | 否 | 否 | 交付正确 → `report` 总体 pass；错误 → fail | draft 判据 / 未冻结集合 → 拒绝；G1：notes 当前含金标；G2：剔除样本当前退出分母；G3：空金标当前 pass | `evaluation/test_acceptance.py`、`scenarios/test_s0_end_to_end.py` |
| DA11.2.3 | `check_result_grain_and_merge` | `spec`、`input_tables`、`output_table`、`declared_grain` | 是（`input_tables`、`output_table`） | 否 | 否 | 输出行数与声明粒度一致 → pass | Join 导致行数膨胀 → fail；X5：带列约束的决策当前仍读出受限列；G7：Join 书写顺序影响判定 | `evaluation/test_computation.py`、`scenarios/test_s0_end_to_end.py` |

### 3.7 链路测试

| 链路 | 顺序 | 通过标准 |
|-|-|-|
| 计算族 | DA12.1.1 → DA01.4.3 / 4.1 / 4.2 → DA02.2.3 → DA02.4.3 → DA03.4.1 → DA06.1.1 → DA06.1.2 → DA06.1.3 / 1.4 → DA06.3.1 → DA07.10.1 → DA07.1.3 → DA11.2.3 → DA11.5.1（+ 2.7 确认）→ DA11.5.6 → DA11.5.5 → DA10.1.1 / DA10.3.1 / DA10.3.3 | 交付值等于手算值；合计行不计入；验收报告 pass；报告含依据 |
| 判定族 | DA12.1.1 → DA01.4.5 → DA02.8.1 → DA02.12.4 → DA02.12.1 → DA02.12.3 → DA03.4.3 → DA03.16.1 / 16.2 → DA03.15.1 → DA12.1.4 → DA06.3.5 → DA07.10.1 → DA07.5.1 / 5.2 → DA11.5.1 → DA11.5.6 → DA11.5.5 → DA10.3.1 / DA10.3.3 | 每条判定可追溯到原文锚点；缺字段的记录判 unknown 并按 `unknown_policy` 计分 |
| 轨迹 | 每步调用后 DA04.1.2；用户更正时 DA04.1.3 | 轨迹可按 `task_ref` 完整读回 |

每条链路至少各跑一次负例：未授权读取、交付错误值、缺字段记录、vendor_api 外发。
