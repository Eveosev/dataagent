# T25 来源配置

三个来源放进同一个接入任务，目标本体 `procurement@1`。三源金额都已是元，都用十进制转换（`decimal`），不用「分 → 元」。

## 1. PDF：`invoices.pdf`

- 类型：`file`，locator 为文件名 `invoices.pdf`。
- 结构：文本 PDF，9 页，每页一张发票，字段写成 `标签: 值` 一行一个；没有表格线。
- 记录：每页一条，共 9 条。第 7 页没有 `number:` 行（缺键）。
- 绑定：`number` ← `number`；`amount` ← `amount`（元，形如 `1260.00`，`decimal`）；`currency` ← `currency`；`issuer` ← `issuer`。
- `posted_on` 不在本体里，留作未映射字段。

## 2. SQLite：`ledger.db`

- 类型：`sqlite`，locator 为 `ledger.db`，表 `invoice`。
- 结构：`invoice(id INTEGER PRIMARY KEY, number TEXT, issuer TEXT, posted_on TEXT, amount NUMERIC, currency TEXT)`，8 行。
- 记录键：业务键是 `number`（可为空，所以不是主键）；`id` 只是行号，不参与身份。`id=7` 的 `number` 为 NULL（缺键）。
- 绑定：`number` ← `number`；`amount` ← `amount`（元，整数或 REAL，如 `1580.5`，`decimal`）；`currency` ← `currency`；`issuer` ← `issuer`。

## 3. REST：`rest/page1.json`、`page2.json`、`page3.json`

- 类型：`rest`，通过 `DATAAGENT_SOURCE_CONNECTIONS` 配置连接，例如连接 ID `accounting`：

```json
{
  "accounting": {
    "kind": "rest",
    "label": "T25 发票 API",
    "locator": "<环回地址>/page1.json",
    "allowed_origins": ["<环回地址>"],
    "credential_options": {"auth": "bearer"},
    "credential_env": {"token": "<令牌逻辑名对应的环境变量>"},
    "options": {
      "records_path": "/items",
      "keys": ["/code"],
      "source_version_path": "/version",
      "pagination": {"next_path": "/next"}
    }
  }
}
```

- 服务：验收脚本在环回地址上按原样返回三页 JSON，路径 `/page1.json`、`/page2.json`、`/page3.json`（`next` 是根路径相对链接，第 3 页 `next` 为 `null`）。每个请求都要求 `Authorization: Bearer <令牌>`，缺失或不符返回 401。本目录不含任何令牌值。
- 版本：三页 `version` 都是 `t25-fixture-1`。
- 记录：`/items` 下每项一条，4 + 4 + 2 = 10 条。第 2 页 `/items/2` 没有 `code` 键（缺键）。
- 绑定：`number` ← `/code`；`amount` ← `/amount`（元，十进制字符串，`decimal`）；`currency` ← `/currency`；`issuer` ← `/issuer`。

## 必须绑定 issuer

`INV-2026-107` 的两条记录金额相同，只有 `issuer` 不同。三个来源都不绑 `issuer` 时，这对同号异对象会被静默合并，冲突数与金标不符（见 `gold.json` 的 J2）。
