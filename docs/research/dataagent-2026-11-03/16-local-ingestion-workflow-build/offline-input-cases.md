---
version: 2
date: 2026-11-18
dataagent_commit: 79d58fe
---

# 离线输入测试用例

从[本机工作台](local-offline-quickstart.md)或 [Mint](mint-offline-quickstart.md)任选入口。全部材料为合成数据。每个用例建一个任务，保存任务 ID、预览或草案引用。文件映射的共同终点是核对对象和来源证据后保存，SQLite 发现的终点是审核本体草案。

## 准备测试输入

在已创建的测试目录执行。每次从新目录开始，避免复用旧任务或样例数据库。`DATAAGENT_CHECKOUT` 和 `DATAAGENT_TEST` 由快速上手手册设置。

```sh
export FIXTURES="$DATAAGENT_CHECKOUT/packages/capabilities/dataagent-scenarios/fixtures/intake"
cd "$DATAAGENT_TEST"
DATAAGENT="./.mint/packages/dataagent/cli@0.1.0/bin/dataagent"

cp "$FIXTURES"/{invoices.csv,invoices.xlsx,invoices.json,invoice.pdf,scan.pdf,mixed.pdf} .
cp "$FIXTURES/p1-files/samples"/{invoices.tsv,invoices.jsonl} .

sqlite3 sales-discovery.db < "$FIXTURES/sales-discovery.sql"
sqlite3 invoice.db <<'SQL'
CREATE TABLE invoice (number TEXT PRIMARY KEY, amount INTEGER, currency TEXT);
INSERT INTO invoice VALUES ('INV-003', 1260, 'CNY');
SQL
```

TSV、JSONL 的样本和独立期望在 `packages/capabilities/dataagent-scenarios/fixtures/intake/p1-files/`：`samples/` 是材料，`expected/` 是逐字段期望和锚点。docx 目前没有放进 `p1-files`；用仓库内 `packages/capabilities/dataagent-data/tests/observation/test_docx_record_sets.py` 的 `build_invoice_docx` 构造同结构样本（标题「采购单」、3 行表格、末尾备注段），或直接使用财务提供的 Word 文件。`p1-files` 的 docx 样本与 `expected/` 待补（待确认）。

## 文件输入

在工作台上传对应文件并填写表中目标。Mint 可发送「用 dataagent-intake 接入当前项目的〈文件名〉，〈目标〉。完成表中核对步骤，打开工作台等我确认」。需要多源合并时，在同一任务同时提交两份材料。预览有多个对象时，用对象区域的左右箭头切换，再点 `amount` 查看对应来源。

| 用例 | 样例与目标 | 操作及通过条件 |
| --- | --- | --- |
| F01 CSV | `invoices.csv`，接入两张采购发票 | 绑定 `number`、`currency`。金额绑定 `amount_minor`，选择「分 → 元」。预览两个对象，`INV-001` 为 1260 CNY、`INV-002` 为 900 CNY。展开来源核对原值 126000，保存后刷新 |
| F02 Excel | `invoices.xlsx`，从有空行的工作表接入发票 | 按 F01 映射。工作表 `Invoices` 第 3 行为空。核对 `INV-002` 的金额证据在 `B4`，金额为 900 CNY |
| F03 JSON | `invoices.json`，从 JSON 数组接入一张发票 | 绑定 `/number`、`/currency`、`/amount_minor`，金额选择「分 → 元」。对象 `INV-001` 为 1260 CNY，金额证据定位到 `/0/amount_minor` |
| F04 文本 PDF | `invoice.pdf`，从第 1 页接入发票 | 按 F01 映射。点击 `amount`，核对第 1 页原图高亮、原文 126000 和预览 1260 CNY |
| F05 扫描 PDF | `scan.pdf`，识别图片中的发票字段 | 按 §启用本机 OCR 装好 OCR 后上传。检查第 1 页 OCR 文本包含 `INV-003`、`1260.00`、`CNY`。Mint 使用精确原文提取三字段，金额按元映射。固定提案验收预期保存一个对象并保留页和原文引用 |
| F06 缺文本页的 PDF | `mixed.pdf`，检查部分探查结果 | 用未启用 OCR 的测试目录上传。页面显示部分结果和第 2 页缺口。刚上传后的探查结果 `.dataagent/results/probe-*.json` 中，`completed_partitions` 为 `[1,3]` |
| F07 两份材料归并 | `invoices.csv` 和 `invoices.json`，核对同一张发票的两份来源 | 按 F01、F03 分别绑定。预览共两个对象。切换来源核对 `INV-001` 的 CSV 行和 JSON Pointer，金额均为 1260 CNY |
| F08 TSV | `p1-files/samples/invoices.tsv`，期望 `p1-files/expected/invoices.tsv.json` | 分隔符必须是制表符；`memo` 里有英文逗号加空格（`打印纸, 文具`），不能被嗅探成逗号分隔。绑定 `number`、`currency`，金额绑定 `amount_minor` 选「分 → 元」；`issue_date`、`vendor`、`memo` 在 `unmapped` 里设为 `extension` 保留。预览 3 个对象：`INV-011` 456.00、`INV-012` 1280.50、`INV-013` 99.00 CNY，金额锚点为第 2/3/4 行的 `amount_minor` |
| F09 JSONL | `p1-files/samples/invoices.jsonl`，期望 `p1-files/expected/invoices.jsonl.json` | 每行一个对象，共 3 条。绑定 `/number`、`/currency`、`/amount_minor`，金额选择「分 → 元」；嵌套 `/vendor/name`、`/vendor/tax_id` 在 `unmapped` 里设为 `extension` 保留，第 3 行的 `/remark` 只在第 3 行有锚点。预览 `INV-021` 320.00、`INV-022` 158.00、`INV-023` 2760.00 CNY；金额锚点带行号 1/2/3 和 JSON Pointer `/amount_minor` |
| F10 Word（docx） | 标题「采购单」+ 表头 `number`/`amount`/`currency` + 3 行数据 + 末尾「备注：发票登记表由财务复核。」；金额已是元 | 绑定 `number`、`amount`、`currency`，金额不做分转元。预览 3 个对象：`INV-301` 1260.00、`INV-302` 900.50、`INV-303` 3300.00 CNY。表头行不能成为第 4 个对象，备注段不能混进发票；表头是标签，段落是独立的记录集。金额锚点为 `table:1/row:2/col:2`，币种为 `table:1/row:2/col:3`。不应出现 `candidate:` 对象或 `number="number"` 的对象 |

F10 的样本构造见 `packages/capabilities/dataagent-data/tests/observation/test_docx_record_sets.py`：默认记录集是 `table:1`（3 条），段落是另一个记录集（2 条），表头不作为记录。网页上传框的 `accept` 目前不含 `.docx`（FDE-7 未修），文件选择器可能置灰；docx 用例从 Mint 聊天按工作区路径接入，或等上传框修复后再从网页选择。本机工作台可先用 `"$DATAAGENT" workbench intake --goal "接入 Word 发票登记表" --source invoice.docx` 建任务，再用 `"$DATAAGENT" workbench view <SESSION_ID>` 打开页面。

### 启用本机 OCR

F05 和 `mixed.pdf` 的扫描页需要已固定的本机引擎。先按 [Mint 手册 §1.3](mint-offline-quickstart.md#13-安装本机-ocr扫描件需要)生成验证目录，再在项目里安装：

```sh
export OCR_ROOT="$HOME/.dataagent/ocr-rapidocr/ocr"
"$DATAAGENT" setup --ocr-root "$OCR_ROOT"
"$DATAAGENT" doctor          # OCR 行变为 engine rapidocr ...，退出码 0
```

已有验证目录时只执行 `setup --ocr-root`。`setup` 会复制整个 OCR 目录到项目的 `.dataagent/ocr`，幂等；目标已有不同固定时拒绝替换。工作树回归用 `bash scripts/verify_local.sh --phase files --ocr-root "$OCR_ROOT"`，脚本自行复制 OCR 目录。

## 数据库和 API 输入

| 用例 | 入口与目标 | 操作及通过条件 |
| --- | --- | --- |
| D01 SQLite 映射 | 上传 `invoice.db`，或让 Mint 接入当前项目的 SQLite 发票表 | 在采购资料映射中绑定 `number`、`amount`、`currency` 同名字段，金额单位已经是元。预览 `INV-003` 为 1260 CNY，来源是 `invoice` 表，记录键是 `number=INV-003` |
| D02 SQLite 本体发现 | 上传 `sales-discovery.db`，选「从数据库发现本体」 | 看见 `party`、`doc_hdr`、`doc_line` 共 7 行。明细 → 订单是声明的复合外键，同值 3/3。订单 → 客户是观测值候选，同值 2/2。用 Mint 提案或固定提案验收脚本提交后，核对粒度和标识、确认草案并刷新 |
| D03 PostgreSQL（P1，不验收） | P1 范围外，用例保留作本机参考 | 映射 `number`、`amount`、`currency`，金额已是元。核对 `INV-003`、1260 CNY、日期 `2026-11-11` 的来源证据和 `invoice` 表主键，保存。M1 验收不包含本项 |
| D04 分页 REST | 已配置连接「测试发票 API」或 Mint 连接 ID `accounting` | 绑定 `/code`、`/amount`、`/currency`。金额使用十进制转换。核对两页、两个对象 `INV-003` 为 1260 CNY、`INV-004` 为 900 CNY。切到第二个对象核对 `/items/0/amount`，在探查结果的 `metadata.record_keys` 核对其页码为 2 |

### 连接配置位置

连接清单的唯一推荐位置是工作区根目录 `source-connections.json`。工作台按启动进程的 `--workspace`（默认当前目录）查找该文件，Mint 与 `dataagent workbench` 都适用；不要把它放到别处再靠 `export DATAAGENT_SOURCE_CONNECTIONS` 补救。

解析顺序：

1. 显式环境变量 `DATAAGENT_SOURCE_CONNECTIONS`（宿主透传用户设置时优先；安装包自带的 `.dataagent/source-connections.json` 会同时设 `DATAAGENT_SOURCE_CONNECTIONS_DEFAULT=1`，标记为打包默认，不会盖住工作区根目录）；
2. 工作区根目录 `source-connections.json`；
3. 工作区 `.dataagent/source-connections.json`（兼容旧位置）。

根目录与 `.dataagent` 同时存在时使用根目录文件并告警。`dataagent doctor` 打印清单路径和来源、已配置连接（名称、类型）以及每个凭据逻辑名的状态（可解析、缺失、权限不对、无效）；任一凭据不可解析时退出码 3 并给出修复提示。doctor 只报有无，不输出凭据值。

### 带 token 的 REST 样例

`credential_refs` 只存逻辑名。推荐用 macOS 钥匙串：

```sh
security add-generic-password -s dataagent -a invoice-api -w '<token>'
```

清单写 `"credential_refs":{"token":"keychain:dataagent/invoice-api"}`。也可以放文件，默认目录是 `$HOME/.dataagent/secrets`：

```sh
SECRETS="${DATAAGENT_SECRETS_DIR:-$HOME/.dataagent/secrets}"
mkdir -p "$SECRETS"
chmod 700 "$SECRETS"
printf '%s' '<token>' > "$SECRETS/invoice-api.key"
chmod 600 "$SECRETS/invoice-api.key"
```

`DATAAGENT_SECRETS_DIR` 是运维/测试覆盖项，必须是绝对路径；不设置时就是 `$HOME/.dataagent/secrets`。旧的工作区 `.dataagent/secrets` 仍可被读取，但会给出警告；新凭据不要放在工作区内。

文件样例的清单：

```sh
mkdir -p "$DATAAGENT_TEST/http-fixture"
cat > "$DATAAGENT_TEST/http-fixture/page1.json" <<'JSON'
{"version":"fixture-1","items":[{"code":"INV-003","amount":"1260.00","currency":"CNY"}],"next":"/page2.json"}
JSON
cat > "$DATAAGENT_TEST/http-fixture/page2.json" <<'JSON'
{"version":"fixture-1","items":[{"code":"INV-004","amount":"900.00","currency":"CNY"}],"next":null}
JSON
cat > "$DATAAGENT_TEST/source-connections.json" <<'JSON'
{
  "accounting": {
    "kind":"rest",
    "label":"测试发票 API",
    "locator":"http://127.0.0.1:8766/page1.json",
    "allowed_origins":["http://127.0.0.1:8766"],
    "options":{"records_path":"/items","keys":["/code"],"source_version_path":"/version","pagination":{"next_path":"/next"}},
    "credential_options":{"auth":"bearer"},
    "credential_refs":{"token":"file:invoice-api"}
  }
}
JSON
python3 -m http.server 8766 --bind 127.0.0.1 --directory "$DATAAGENT_TEST/http-fixture" &
REST_FIXTURE_PID=$!
```

三种逻辑名：

| 写法 | 解析位置 | 说明 |
| --- | --- | --- |
| `keychain:<service>/<account>` | macOS 钥匙串 `security find-generic-password` | 推荐；值不落工作区 |
| `file:<name>` | `$HOME/.dataagent/secrets/<name>.key` | 目录 0700、文件 0600；`<name>` 可含 `/` 分段，禁止越出该目录 |
| `env:<VAR>` | 启动进程的环境变量 | 宿主注入；只在启动进程内可见。统一 CLI 只透传 `DATAAGENT_*` 和标准变量，变量名建议用 `DATAAGENT_` 前缀；否则会被清理掉 |

`doctor` 对 `file:` 的修复提示目前仍写工作区 `.dataagent/secrets`；默认解析已经改为 `$HOME/.dataagent/secrets`，按本节的默认目录修复（提示文本待同步，待确认）。

REST bearer 只接受 `token`；basic 接受 `user`、`password`，并在 `credential_options` 给出 `"auth":"basic"` 和 user。PostgreSQL 接受 `user`、`password`，但 P1 不验收。上面的 `python3 -m http.server` 只是静态样例，不校验 `Authorization`；接入真实 REST 服务时，服务端必须校验 `Authorization: Bearer <token>`，否则 `credential_refs` 只表示「发送了凭据」，不构成鉴权保护。结束时停止测试服务 `kill "$REST_FIXTURE_PID"`。带第 2 页 429 的断点续跑由组合验收脚本覆盖。

启动工作台或 Mint 前，在工作区根目录运行 `"$DATAAGENT" doctor`，确认连接与凭据均可解析；不要先 `export DATAAGENT_SOURCE_CONNECTIONS` 绕开位置问题。

### 配置本机 PostgreSQL 样例（P1，不验收）

PostgreSQL 已移出 P1（06 Q12），本节仅保留为 P1 范围外的本机验证参考，不计入 M1 验收。`verify_local.sh --phase sources` 不带 `--postgres-locator` 时跳过该项。

使用已有的本机 PostgreSQL 测试实例。将 `LOCAL_TEST_POSTGRES_ADMIN` 设为可在独立测试库建表和授权的连接串，将 `LOCAL_TEST_POSTGRES` 设为同一库的环回连接串。在测试实例尚无该角色时，用管理员连接执行 `CREATE ROLE dataagent_reader LOGIN`。按本机认证设置提供该角色的凭据。

```sh
psql "$LOCAL_TEST_POSTGRES_ADMIN" -v ON_ERROR_STOP=1 <<'SQL'
CREATE TABLE invoice (number TEXT PRIMARY KEY, amount NUMERIC(12,2), currency TEXT, posted_on DATE);
INSERT INTO invoice VALUES ('INV-003', 1260.00, 'CNY', DATE '2026-11-11');
GRANT USAGE ON SCHEMA public TO dataagent_reader;
GRANT SELECT ON invoice TO dataagent_reader;
SQL
```

在 `source-connections.json` 根对象加入以下连接，保留同时测试的其他连接。将 `locator` 改为实际环回地址。需要密码时把密码写入 `$HOME/.dataagent/secrets/pg-reader.key`（0600），并在连接中加入 `"credential_refs":{"password":"file:pg-reader"}`；也可改用 `keychain:dataagent/pg-reader` 或 `"credential_refs":{"password":"env:DATAAGENT_PG_PASSWORD"}`。

```json
{
  "ledger": {
    "kind":"postgres",
    "label":"测试发票库",
    "locator":"postgresql://127.0.0.1:5432/dataagent_test",
    "scope":{"tables":["invoice"]},
    "credential_options":{"user":"dataagent_reader"}
  }
}
```

从工作区根目录启动工作台或 Mint。若测试角色可通过本机认证直接登录，可从工作树运行 `bash scripts/verify_local.sh --phase sources --postgres-locator "$LOCAL_TEST_POSTGRES"`。预期 CSV、SQLite、PostgreSQL、REST 对齐为一个 `INV-003`，REST 第 2 页重试后完成，第 1 页读取一次（P1 参考，不验收）。

## 保存被拦怎么办

保存返回 `preview contains unresolved issues` 时，按 `intake_propose` / `mapping_preview` 返回的 `issues`、`disposition_options` 和每条 issue 的 `actions` 处置。所有处置都要传最新 `expected_revision`；`intake_dispose` 的 `reason` 必填，`mapping_apply` 的 `reason` 建议填写并写入审计。

| 现象 | 工具与参数 | 结果 |
| --- | --- | --- |
| 空白页、读不到的分区（`ontology.incomplete_source`） | `intake_dispose`：`action="partition_not_applicable"`、`source_id`、`partition`、`reason` | 记一条分区处置，预览失效；用返回的 `session_revision` 重新提交映射生成预览 |
| 表头行或明显无关的记录（issue 带 `row`，且该行已进入 `profile.records`） | `intake_dispose`：`action="exclude_record"`、`source_id`、`record`（0 起，取 issue 的 `row`）、`reason` | 从该来源排除这一条记录，再重新提交映射 |
| 缺键记录（`candidate:`，如 3 条缺号记录） | `mapping_apply`：`decision` 不带 `changes`，顶层 `allow_partial=true`、`reason` | 无阻断对象进 `saved` 并发布；冲突/缺必填进 `suspended`；缺键记录进 `unidentified_records`，不挡其他对象。不要这些记录时逐条 `exclude_record` |
| 冲突值、必填缺失 | 打开 `workbench view`，在对象页选「纠正当前对象的值」，填属性、值、原因；冲突时按页面提示「已核对，重新提交」 | 纠正写入后重新校验；回聊天用 `intake_status` / `mapping_preview` 取最新修订 |
| 只想先保存无问题对象 | 同 `allow_partial` | 只发布 `saved`；`suspended`、`unidentified_records` 不发布 |

```json
{
  "session_id": "<session>",
  "expected_revision": "<最新修订>",
  "action": "partition_not_applicable",
  "source_id": "<来源>",
  "partition": 2,
  "reason": "第 2 页为空白页，财务确认不补"
}
```

```json
{
  "session_id": "<session>",
  "expected_revision": "<最新修订>",
  "action": "exclude_record",
  "source_id": "<来源>",
  "record": 0,
  "reason": "表头行，不是业务记录"
}
```

```json
{
  "session_id": "<session>",
  "expected_revision": "<最新修订>",
  "decision": {
    "preview_ref": "<preview>",
    "target_scope": "mapping",
    "decision": "save"
  },
  "allow_partial": true,
  "reason": "先保存无问题的发票；缺键记录和冲突项另列"
}
```

- 处置后预览会失效，必须重新 `intake_propose` / `intake_propose_sources`，不能拿旧 `preview_ref` 直接保存。
- 表头已经被正确识别为标签、没有进入 `profile.records` 时，不需要也不能按记录号排除；只有它被误当成记录并出现在 issue 里才用 `exclude_record`。
- `allow_partial` 至少要有 1 个无阻断对象，且不能有全局阻断（如未处置的分区缺口）；否则整批仍被拦。
- 工作台网页提供当前值纠正、这类来源的映射修订和本体草案，没有「标记空白页」「排除整页或整行」按钮；不要按页面文案编造入口。
- issue 没有 `actions`、`disposition_options` 也没有对应项时，直说没有这项处置；只能建议网页纠正或先保存无问题对象，两者都不适用时说明当前任务无法保存。

## 业务 API 和 GUI 操作

这两条用例使用合成报销系统。脚本在本机启动业务服务和临时数据库，提交固定工作流，并返回验收报告。

| 用例 | 从工作树执行 | 通过条件 |
| --- | --- | --- |
| W01 业务 API | `bash scripts/verify_local.sh --phase api-workflow` | 探查报销 API，创建草稿、提交并独立查询。业务单据进入 `waiting_approval`，工作流有两个动作回执 |
| W02 GUI 环境与对账 | `bash scripts/verify_local.sh --phase mixed-workflow` | 使用本机 Chrome、Node 和 Playwright。API 已提交但响应丢失时，浏览器按业务键读取同一单据，状态为 `waiting_approval`。提交派发一次，报告含浏览器证据 |

本机直接验证 API 和 GUI 探查时，从工作树运行下列现有用例。API 用例验证重启后恢复审批等待。GUI 用例观察采购单页面，核对 `Supplier` 控件和变更后新增的必填 `Cost center`，同时检查观察时没有创建单据。

```sh
OPS=packages/capabilities/dataagent-operations
uv run --offline --frozen --project "$OPS" python -m pytest \
  "$OPS/tests/test_api_workflow.py::test_approval_wait_survives_restart" \
  "$OPS/tests/test_gui_workflow.py::test_observes_real_page_and_detects_changed_required_field"
```

Mint 端到端发起工作流需要同一项目的业务环境配置和本机模型。装包验收覆盖固定工作流的执行和对账。
