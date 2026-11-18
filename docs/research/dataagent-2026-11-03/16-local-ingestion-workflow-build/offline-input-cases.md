---
version: 1
date: 2026-11-12
---

# 离线输入测试用例

从[本机工作台](local-offline-quickstart.md)或 [Mint](mint-offline-quickstart.md)任选入口。全部材料为合成数据。每个用例建一个任务，保存任务 ID、预览或草案引用。文件映射的共同终点是核对对象和来源证据后保存，SQLite 发现的终点是审核本体草案。

## 准备测试输入

在已创建的测试目录执行。每次从新目录开始，避免复用旧任务或样例数据库。

```sh
export FIXTURES="$DATAAGENT_CHECKOUT/packages/capabilities/dataagent-scenarios/fixtures/intake"
cd "$DATAAGENT_TEST"
cp "$FIXTURES"/{invoices.csv,invoices.xlsx,invoices.json,invoice.pdf,scan.pdf,mixed.pdf} .
sqlite3 sales-discovery.db < "$FIXTURES/sales-discovery.sql"
sqlite3 invoice.db <<'SQL'
CREATE TABLE invoice (number TEXT PRIMARY KEY, amount INTEGER, currency TEXT);
INSERT INTO invoice VALUES ('INV-003', 1260, 'CNY');
SQL
```

## 文件输入

在工作台上传对应文件并填写表中目标。Mint 可发送「用 dataagent-intake 接入当前项目的〈文件名〉，〈目标〉。完成表中核对步骤，打开工作台等我确认」。需要多源合并时，在同一任务同时提交两份材料。预览有多个对象时，用对象区域的左右箭头切换，再点 `amount` 查看对应来源。

| 用例 | 样例与目标 | 操作及通过条件 |
| --- | --- | --- |
| F01 CSV | `invoices.csv`，接入两张采购发票 | 绑定 `number`、`currency`。金额绑定 `amount_minor`，选择「分 → 元」。预览两个对象，`INV-001` 为 1260 CNY、`INV-002` 为 900 CNY。展开来源核对原值 126000，保存后刷新 |
| F02 Excel | `invoices.xlsx`，从有空行的工作表接入发票 | 按 F01 映射。工作表 `Invoices` 第 3 行为空。核对 `INV-002` 的金额证据在 `B4`，金额为 900 CNY |
| F03 JSON | `invoices.json`，从 JSON 数组接入一张发票 | 绑定 `/number`、`/currency`、`/amount_minor`，金额选择「分 → 元」。对象 `INV-001` 为 1260 CNY，金额证据定位到 `/0/amount_minor` |
| F04 文本 PDF | `invoice.pdf`，从第 1 页接入发票 | 按 F01 映射。点击 `amount`，核对第 1 页原图高亮、原文 126000 和预览 1260 CNY |
| F05 扫描 PDF | `scan.pdf`，识别图片中的发票字段 | 装好下节的 OCR 目录后上传。检查第 1 页 OCR 文本包含 `INV-003`、`1260.00`、`CNY`。Mint 使用精确原文提取三字段，金额按元映射。固定提案验收预期保存一个对象并保留页和原文引用 |
| F06 缺文本页的 PDF | `mixed.pdf`，检查部分探查结果 | 用未启用 OCR 的测试目录上传。页面显示部分结果和第 2 页缺口。刚上传后的探查结果 `.dataagent/results/probe-*.json` 中，`completed_partitions` 为 `[1,3]` |
| F07 两份材料归并 | `invoices.csv` 和 `invoices.json`，核对同一张发票的两份来源 | 按 F01、F03 分别绑定。预览共两个对象。切换来源核对 `INV-001` 的 CSV 行和 JSON Pointer，金额均为 1260 CNY |

F05 使用已验收的本机 OCR 目录。该目录包含 `active.json`、引擎及验证记录。将 `LOCAL_OCR_DIR` 设为该目录。本工作树若保留了`.superpowers/sdd/16-local-ingestion-workflow-build-plan/acceptance/files.json`及其测试项目，可复用报告中 `project` 下的 `.dataagent/ocr`。首次在测试目录启用时，运行下面的命令。随后重启工作台，使用新任务上传扫描件。

```sh
test -f "$LOCAL_OCR_DIR/active.json" &&
mkdir -p "$DATAAGENT_TEST/.dataagent" &&
cp -R "$LOCAL_OCR_DIR" "$DATAAGENT_TEST/.dataagent/ocr"
```

Mint 固定提案复跑命令为 `bash scripts/verify_local.sh --phase files --ocr-root "$LOCAL_OCR_DIR"`，从工作树执行。该脚本自行复制 OCR 目录。

## 数据库和 API 输入

| 用例 | 入口与目标 | 操作及通过条件 |
| --- | --- | --- |
| D01 SQLite 映射 | 上传 `invoice.db`，或让 Mint 接入当前项目的 SQLite 发票表 | 在采购资料映射中绑定 `number`、`amount`、`currency` 同名字段，金额单位已经是元。预览 `INV-003` 为 1260 CNY，来源是 `invoice` 表，记录键是 `number=INV-003` |
| D02 SQLite 本体发现 | 上传 `sales-discovery.db`，选「从数据库发现本体」 | 看见 `party`、`doc_hdr`、`doc_line` 共 7 行。明细 → 订单是声明的复合外键，同值 3/3。订单 → 客户是观测值候选，同值 2/2。用 Mint 提案或固定提案验收脚本提交后，核对粒度和标识、确认草案并刷新 |
| D03 PostgreSQL（P1，不验收） | P1 范围外，用例保留作本机参考 | 映射 `number`、`amount`、`currency`，金额已是元。核对 `INV-003`、1260 CNY、日期 `2026-11-11` 的来源证据和 `invoice` 表主键，保存。M1 验收不包含本项 |
| D04 分页 REST | 已配置连接「测试发票 API」或 Mint 连接 ID `accounting` | 绑定 `/code`、`/amount`、`/currency`。金额使用十进制转换。核对两页、两个对象 `INV-003` 为 1260 CNY、`INV-004` 为 900 CNY。切到第二个对象核对 `/items/0/amount`，在探查结果的 `metadata.record_keys` 核对其页码为 2 |

### 连接配置位置

连接清单的唯一推荐位置是工作区根目录 `source-connections.json`。工作台按启动进程的 `--workspace`（默认当前目录）查找该文件，Mint 与 `dataagent workbench` 都适用；安装包只把 `.dataagent/source-connections.json` 当作兜底，不覆盖工作区根目录的清单。

解析顺序：

1. 显式环境变量 `DATAAGENT_SOURCE_CONNECTIONS`（宿主透传用户设置时优先）；
2. 工作区根目录 `source-connections.json`；
3. 工作区 `.dataagent/source-connections.json`（兼容旧位置）。

根目录与 `.dataagent` 同时存在时使用根目录文件并告警。`dataagent doctor` 打印清单路径、已配置连接（名称、类型）和每个凭据逻辑名的状态（可解析、缺失、权限不对）；任一凭据缺失时退出码非 0 并给出修复命令。doctor 只报有无，不输出凭据值。

### 带 token 的 REST 样例

token 只保存在 `.dataagent/secrets/invoice-api.key`：目录 0700、文件 0600。清单以 `file:invoice-api` 引用该逻辑名，凭据值不写进清单。

```sh
mkdir -p "$DATAAGENT_TEST/http-fixture" "$DATAAGENT_TEST/.dataagent/secrets"
chmod 700 "$DATAAGENT_TEST/.dataagent/secrets"
cat > "$DATAAGENT_TEST/http-fixture/page1.json" <<'JSON'
{"version":"fixture-1","items":[{"code":"INV-003","amount":"1260.00","currency":"CNY"}],"next":"/page2.json"}
JSON
cat > "$DATAAGENT_TEST/http-fixture/page2.json" <<'JSON'
{"version":"fixture-1","items":[{"code":"INV-004","amount":"900.00","currency":"CNY"}],"next":null}
JSON
printf '%s' '<token>' > "$DATAAGENT_TEST/.dataagent/secrets/invoice-api.key"
chmod 600 "$DATAAGENT_TEST/.dataagent/secrets/invoice-api.key"
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

`credential_refs` 使用逻辑名：`env:<VAR>` 读启动进程的环境变量，`keychain:<service>/<account>` 读 macOS 钥匙串，`file:<name>` 读 `.dataagent/secrets/<name>.key`。REST bearer 只接受 `token`；basic 接受 `user`、`password`，并在 `credential_options` 给出 `"auth":"basic"` 和 user。PostgreSQL 接受 `user`、`password`。钥匙串写入示例：`security add-generic-password -s dataagent -a invoice-api -w '<token>'`。

上面的 `python3 -m http.server` 只是静态样例，不校验 `Authorization`；它用于验证 locator、分页和清单结构。接入真实 REST 服务时，服务端必须校验 `Authorization: Bearer <token>`，否则 `credential_refs` 只表示“发送了凭据”，不构成鉴权保护。结束时停止测试服务 `kill "$REST_FIXTURE_PID"`。带第 2 页 429 的断点续跑由组合验收脚本覆盖。

启动工作台或 Mint 前先在工作区根目录运行 `dataagent doctor`，确认连接与凭据均可解析。显式导出 `DATAAGENT_SOURCE_CONNECTIONS="$DATAAGENT_TEST/source-connections.json"` 仍可作为覆盖，但不是必须。

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

在 `source-connections.json` 根对象加入以下连接，保留同时测试的其他连接。将 `locator` 改为实际环回地址。需要密码时把密码写入 `.dataagent/secrets/pg-reader.key`（0600），并在连接中加入 `"credential_refs":{"password":"file:pg-reader"}`；也可改用 `"credential_refs":{"password":"env:DATAAGENT_PG_PASSWORD"}`。

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
