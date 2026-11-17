# T25 跨源样本组与金标

DataAgent 卡片 T25（`docs/dataagent/07 MVP 实施文档.md`）的独立样本与金标。全部数据为合成数据。

- 金标 `gold.json` 是人工推理写成的，没有运行 DataAgent 的 probe、intake、verify 代码。
- 本体与身份规则读自 `dataagent@d2b883a`（分支 `feat/p1-intake`），只作文档阅读。

## 1. 文件

| 路径 | 内容 | sha256 |
|---|---|---|
| `samples/invoices.pdf` | 文本 PDF，9 页，每页一张发票 | `acd7b8eeb483bf1fbb74c78e4ba08bec589a9741cba83296df4c38fe07bada24` |
| `samples/ledger.db` | SQLite，`invoice` 表 8 行 | `ea3d3824993b6236773f73eb36384196494eb6ce2807836fc241fe2bca9cc8a2` |
| `samples/rest/page1.json` | REST 第 1 页，4 项 | `b3a62087f2440559f27bba14e140307465dd54464a13a670d5711f8440cbf80c` |
| `samples/rest/page2.json` | REST 第 2 页，4 项 | `be63be1fbb9b222d9ffef19ce6f7c081e76ff0a3301cfcf2b87d92f156825d7e` |
| `samples/rest/page3.json` | REST 第 3 页，2 项，`next` 为 null | `35384dd66800870a95c19acf291ea7c0daaf5afcdf3f8d926f68365eb6fc2281` |
| `samples/sources.md` | 三个来源的配置与绑定 | — |
| `gold.json` | 金标 | — |
| `gen/make_samples.py` | 生成三个样本 | — |
| `gen/check_gold.py` | 审核用交叉核对：直接读样本，核对金标覆盖每条记录、计数和冲突值 | — |

重新生成（PDF 用 `invariant=1`，字节可复现；SQLite 文件字节依赖 sqlite 版本，本机 3.54.0）：

```bash
cd <本目录>
uv run --offline --no-project --with reportlab python3 -I gen/make_samples.py samples   # reportlab 5.1.0
uv run --offline --no-project --with pdfplumber python3 -I gen/check_gold.py .          # 期望输出 ok: 27 records, 10 keyed objects, 3 keyless, 5 conflicts on 4 objects
```

## 2. 设计的情况

10 个单据号 `INV-2026-101`～`110`，另有 3 条缺键记录，三源共 27 条记录（PDF 9、SQLite 8、REST 10）。

| 情况 | 单据号 | 说明 |
|---|---|---|
| 三源一致 | 101、102、103 | 102 的金额写法不同（`1580.50`、REAL `1580.5`、`"1580.50"`），数值相同 |
| 两源一致 | 106 | SQLite + REST |
| 单源 | 108（PDF）、109（REST 第 3 页） | 不算冲突 |
| 金额冲突 | 104（SQLite 4880 vs 4800）、105（REST 2510 vs 2150） | 各 1 处 |
| 同号异对象 | 107（PDF 华信 vs REST 北明，金额都是 5400）、110（PDF+SQLite 青山 880 vs REST 华信 2300） | 107 冲突在 issuer；110 冲突在 amount 和 issuer |
| 缺键 | PDF 第 7 页、SQLite `id=7`、REST 第 2 页 `/items/2` | SQLite `id=7` 除 number 外与 101 完全相同，是陷阱 |

期望结果：

1. 有键对象 10 个；缺键候选 3 个（若实现把候选放进实例列表，实例数 13）。
2. 冲突 5 处（按「对象, 字段」去重），涉及 4 个对象：104、105、107、110。
3. 这 4 个对象保存必须被阻断；缺键记录单独报告、不并入任何对象。

## 3. 身份怎么定

- `procurement@1` 的 `identity_fields` 只有 `number`，说明是「在工作区采购资料范围内唯一的单据编号」。
- 所以系统无法把同号的两张单拆成两个对象。同号异对象建模为：一个对象键 + issuer（和金额）冲突 + 阻断保存，交给人裁决。期望行为是暴露冲突，不是自动拆分，也不是静默合并。
- 缺 `number` 的记录身份未定，不按开票方、日期、金额去猜。

## 4. 给审核人的假设

1. 三个来源都必须绑定 `issuer`。不绑时 107 会被静默合并，冲突数变成 3、冲突对象 3 个，金标认定为错误（J2）。
2. `posted_on` 不在本体里，日期差异只作证据，不计冲突。本体以后加 `posted_on` 时冲突数变 7，对象数不变（J4）。
3. 冲突按（对象, 字段）去重计数。104 的 4800/4880/4800 只算 1 处；实现若按问题事件计数，比对前要去重（J3）。
4. 阻断粒度：整批阻断或只拦冲突对象都算满足；任何冲突对象被保存、或冲突值被任选一个写入，都不满足（J5）。
5. REST 由验收脚本在环回地址按原样提供，路径 `/page1.json`～`/page3.json`，每个请求要求 `Authorization: Bearer <令牌>`。样本里没有令牌值，令牌按逻辑名注入。不带令牌应探查失败（401），不能当作空来源。
6. PDF 每页一条记录、`标签: 值` 格式、无表格线；整份 PDF 只有 ASCII 文本（reportlab 内置字体），开票方用英文名。
7. 所有金额都是元，币种都是 CNY；没有设计币种冲突。
8. PostgreSQL 不在本组（06 的 Q12）。

## 5. 这份金标能证明什么

- 能证明：给定这三份输入，跨源对齐后应得到的对象数、冲突处、阻断对象和缺键报告。
- 不能证明：DataAgent 实际是否这样做；那要靠 sources 阶段跑完后和本金标比对。`gen/check_gold.py` 只核对金标与样本自洽，不涉及 DataAgent 代码。
