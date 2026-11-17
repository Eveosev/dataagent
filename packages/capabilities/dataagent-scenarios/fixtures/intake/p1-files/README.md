# T21 样本与独立期望文件

T21「files 阶段扩到 8 类样本」的测试输入和手写期望。全部是合成数据（发票、报销明细，金额单位 CNY），不含真实客户信息。

- 期望文件按原件手工编写，没有运行 DataAgent 的 probe、抽取或 verify 脚本。
- 只为校准混排 PDF 第 3 页的退化程度跑过原始 RapidOCR 引擎（见下文「第 3 页 OCR 校准」）；期望值没有取自 OCR 输出。
- 读过的代码只用来确认字段名和选择器形状：`dataagent-data/.../observation/{files.py,documents.py}`、`dataagent-contracts/src/dataagent_contracts/{intake.py,core/refs.py}`，基于 `dataagent@bc7b3c9`（分支 feat/p1-intake）。
- 未看实现方（zcode）的 diff 或输出。

## 目录

```
samples/    8 个样本，每类 1 个
expected/   每个样本 1 份期望：<样本文件名>.json
gen/        生成脚本；sweep.sh、calibrate_ocr.py 只用于第 3 页 OCR 校准；
            gen/out/page3-scan.png 是混排 PDF 第 3 页的 JPEG 前预览图，给评审看
```

## 样本清单

| 类 | 样本 | 来源 | 要验的点 | sha256 |
|---|---|---|---|---|
| CSV | `invoices.csv` | 原样复制 fixtures/intake | 2 行，行号锚点 | `36f4d5b041650c46a41a967a92ea9ac462aaca1e3c0c03dea4a8bbd9dc701c4f` |
| TSV | `invoices.tsv` | 新建，`gen/make_tsv_jsonl.py` | 3 行 6 列，中文供应商；memo 列含「, 」，分隔符必须识别为制表符 | `39a573ca8004d6a905572a50877e54f41c842c14f8cf74fa41f351271e62dd4d` |
| Excel | `invoices-regions.xlsx` | 新建，`gen/make_xlsx.py` | 一张表两个表区；表区 1 两行合并表头 | `1fb2e6eea5f68ccded7909903453d8b26b01fa9db8bc6f65535c343564964312` |
| JSON | `invoices.json` | 原样复制 fixtures/intake | 根数组，JSON Pointer `/0/amount_minor` | `83df661713b923cd4c62f120ac6c52052ac7268a9d1a385fe015c7b6b1fae793` |
| JSONL | `invoices.jsonl` | 新建，`gen/make_tsv_jsonl.py` | 3 行；嵌套 vendor 对象；第 3 行多一个 remark 字段；金额是 JSON 数字 | `d873acee69e126f1fe68e2e498940492dc1c836656fcd62dd15f52cf747c668b` |
| 文本 PDF | `invoice-lines.pdf` | 新建，`gen/make_text_pdf.py` | 2 页；10 行明细表从第 1 页跨到第 2 页，第 2 页重复表头；合计在第 2 页 | `c02fd122d7b11799d82c48e6facbc7777ea1e2016263ae62e7179ad23d0191bc` |
| 扫描 PDF | `scan.pdf` | 原样复制 fixtures/intake | 1 页纯图片，INV-003 / 1260.00 CNY | `9f7aceaa32779e1e65ae6da48b9699ebf856a2dac4990977db7ba0f382f7e788` |
| 混排 PDF | `mixed-pages.pdf` | 新建，`gen/make_mixed_pdf.py` | 第 1 页文本；第 2 页失败页；第 3 页低置信度扫描页 | `c0418f7e29897e52ae98ff4b31d34fcf85b7fc36d347b726a85827c59c146650` |

总大小约 50 KB。

## 难点样本怎么构造

1. **合并表头**（`invoices-regions.xlsx`，表 `报销明细`）
   - 合并区：`A1:A2` 发票号、`B1:B2` 开票日期、`C1:C2` 供应商、`F1:F2` 币种（纵向）；`D1:E1` 金额（分）（横向），下面 `D2` 不含税、`E2` 税额。
   - 数据行 3–5，开票日期是真 Excel 日期单元格（格式 yyyy-mm-dd），无公式。
2. **多表区**（同一张表）
   - 表区 1 `A1:F5`；第 6、7 行空；表区 2 `A8:D11`（单行表头，4 列）。
   - 两表能互相对账：不含税 + 税额 = 同发票号的报销金额，方便抽查有没有串行。
3. **跨页表**（`invoice-lines.pdf`）
   - 带边框线的 5 列表：第 1 页行 1–6，第 2 页重复表头 + 行 7–10，表下 `total_amount_minor: 340200`。
   - 每行 qty × unit_price_minor = amount_minor，10 行之和 = 340200。
4. **失败页**（`mixed-pages.pdf` 第 2 页）
   - 无文本层；只有一张 DCTDecode 图片，流内容是 JFIF 头 + 2048 个随机字节（种子固定），不是合法 JPEG。
   - 用 pdfium 渲染该页得到纯白页面（仅用于确认样本本身，是通用渲染库，不是 DataAgent 代码）。
5. **低置信度页**（`mixed-pages.pdf` 第 3 页）
   - 灰度 JPEG（质量 20）：字 150 / 底 198 的低对比、旋转 1.8°、高斯模糊 1.6、±28 噪点、缩放到一半再放大；金额那一行有一道浅色扫描条纹。
   - v2 起金额整行印得更淡（字 165，模拟打印头磨损），专门把这一行的 OCR 置信度压到 0.6 以下。
   - 人眼可读：`Invoice INV-203`、`Date: 2026-11-09`、`Amount: 4?80.00 CNY`；金额第三位在淡印和条纹下人眼也不易分清 8 和 6，真值以生成脚本为准（4580.00）。

## 第 3 页 OCR 校准

实现方用本机 RapidOCR 实测 v1 样本，三行置信度都高于 0.6（`documents.py:85` 的阈值），`intake.low_ocr_confidence` 不触发，同时金额被读成 4560.00。v2 只改第 3 页，第 1、2 页内容不变。

- 引擎：`/Users/payne/Vibe/dataagent-private/ocr-local/ocr/engines/rapidocr-local/.venv`，rapidocr-onnxruntime 1.4.4、onnxruntime 1.31.1，`RapidOCR()` 默认参数（与 DataAgent 引擎 worker 构造方式相同；默认 `text_score=0.5`，低于 0.5 的行会被丢掉）。
- 渲染：第 3 页按 144 dpi 渲染成 PNG（pypdfium2 `scale=2`，并用 pdfplumber `to_image(resolution=144)` 以 PNG 字节送入引擎复核，两种结果一致）。没有运行 DataAgent 的 probe、intake 或 verify。
- 命令：`bash gen/sweep.sh '<PARAMS 覆盖 JSON>' <标签>`；它在临时目录生成样本、渲染第 3 页、调用 `gen/calibrate_ocr.py`。

| 版本 | 改动 | Invoice 行 | Date 行 | Amount 行 |
|---|---|---|---|---|
| v1 | — | 0.858 | 0.950 | 0.864（读成 4560.00） |
| v2 | `amount_fg=165` | 0.852 | 0.946 | **0.557**（读成 4560.00） |

扫过的其他参数：整体降低对比、加大模糊或噪点时，结果在「仍 ≥ 0.6」和「整行被丢弃」之间跳变，且常把 Invoice、Date 行一起拖坏；只让金额行变淡最可控，`amount_fg` 163–166 落在 0.52–0.58，165 居中。第 2 页复测仍无任何文字（渲染为纯白）。

校准只用来调样本。期望文件里的值仍按原件手写，只更新了 sha256、第 3 页版面描述和判断依据里的校准说明。

## 期望文件格式

每份 `expected/<样本>.json` 的主要字段：

- `coverage`、`total_partitions`、`completed_partitions`、`gaps`（含 `reason` 类别和可接受的 `accepted_codes`）：files 阶段直接比对的部分。PDF 有 `with_ocr` / `without_ocr` 两套，验收按 `--ocr-root` 运行，以 `with_ocr` 为准。
- `records`（或 Excel 的 `tables[].records`、文本 PDF 的 `document_fields` + `logical_table.records`）：每条记录的字段值和锚点。
- 锚点写法：
  - CSV/TSV：`{row, field}`，row 是文件物理行号，表头为第 1 行；
  - Excel：`{sheet, cell}`，另附 `ref` = `报销明细!D3`；
  - JSON：`{pointer}`；JSONL：`{line, pointer}`；
  - PDF：`{page, snippet}`，值必须是 snippet 的子串。
- `anchor_coverage`：每份写明应有的锚点个数，口径是「每条记录的每个非空字段都有锚点」（PRD V1.1）。
- `must_not_appear_as_records`：不应被当成数据行的内容（子表头、重复表头、空行、版面文字）。
- `判断依据`：期望里带主观判断的地方，写明理由和可以不同意的替代口径。

## 生成方式

```bash
bash /Users/payne/Vibe/dataagent-private/t21-fixtures/gen/build_all.sh [DATAAGENT_CHECKOUT]
```

- 默认 `DATAAGENT_CHECKOUT=/Users/payne/Vibe/AgentCPM-OS/projects/dataagent`，从它的 `packages/capabilities/dataagent-scenarios/fixtures/intake/` 复制 csv、json、scan.pdf。
- 新样本命令（均离线，包来自 uv 缓存）：
  - `python3 -I gen/make_tsv_jsonl.py samples`（只用标准库）
  - `uv run --offline --no-project --with openpyxl==3.1.5 python -I gen/make_xlsx.py samples`
  - `uv run --offline --no-project --with reportlab==5.1.0 python -I gen/make_text_pdf.py samples`
  - `uv run --offline --no-project --with pillow==13.0.0 python -I gen/make_mixed_pdf.py samples`（字体 `/System/Library/Fonts/Supplemental/Arial.ttf`；PDF 对象手工拼写，不依赖 PDF 库）
- 输出可复现：连续两次运行 sha256 一致。xlsx 重新打包时固定了 zip 时间戳和 core.xml 时间；reportlab 用 `invariant=1`；随机数都有固定种子。
- 样本自检只用了 pypdf 抽文本层、pypdfium2 渲染预览、openpyxl 读单元格，用来确认原件是我想要的样子；期望文件里的值都是对着原件手写的。

## 需要评审确认的假设

1. **低置信度页的口径**（`mixed-pages.pdf.json` 判断依据 3、4）：期望第 3 页算完成页、值带第 3 页锚点、issues 里有 `intake.low_ocr_confidence`；值只做软比对。另一种口径是把它记成缺口（gap_pages [2,3]）。
2. **第 3 页校准窗口很窄**：已按下节校准到金额行 0.557，但 RapidOCR 会丢弃 < 0.5 的行，可用窗口只有 0.5–0.6。换引擎版本、渲染分辨率或 onnxruntime 后需复测；金额行消失就减轻退化，回到 ≥ 0.6 就加重，都改 `gen/make_mixed_pdf.py` 的 `PARAMS["amount_fg"]` 重做样本，不改期望。
3. **失败页缺口代码**：接受 `ocr_empty` 或 `ocr_failed`，只硬比页码 2。
4. **Excel 默认探查应为 full**（`invoices-regions.xlsx.json` 判断依据 1）：若团队裁定多表区必须由用户选区域，默认结果应为 `header_selection_required` 缺口、partial。合并表头字段名的拼法不验，按 `header_cells` 对列。
5. **跨页表放在文本 PDF**：按派单说明放在 `invoice-lines.pdf`；T21 卡片原文把跨页表列在混排 PDF 下，评审可决定混排 PDF 是否还要加一张。
6. **文本 PDF 的 record_count**：期望 11（发票级字段 1 条 + 明细 10 条）；按页各出一条键值记录（12 条）也可接受，比对器应按「字段 + 锚点页码」比。
7. **CSV/TSV 行号口径**：row 是含表头的文件物理行号（数据从第 2 行起）。
8. **原有 `invoice.pdf`、`invoices.xlsx`、`mixed.pdf` 未纳入**：它们分别被新的 `invoice-lines.pdf`、`invoices-regions.xlsx`、`mixed-pages.pdf` 取代为本类代表；M1-04 依赖的 `invoice.pdf`（126000）是否保留在 files 阶段由实现方决定。
