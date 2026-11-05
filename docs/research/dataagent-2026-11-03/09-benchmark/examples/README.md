# examples：填写样板

两个文件对应一份用例与一份记分卡，用来对齐字段形状，**不参与任何统计**（`check.py` 只扫 `tasks/*/dataset/cases/`）。

| 文件 | 对应 schema |
|-|-|
| `case.B01-mhdr-0001.json` | `schema/case.schema.json` |
| `scorecard.md` 中的示例（在 `monitor/scorecard-template.md` §4） | `schema/scorecard.schema.json` |

## 约定

- `case_id` 与文件名一致，序号 4 位从 0001 起，不回收。
- `inputs[].ref` 相对 `dataset/`，`expected.ref` 指向 `expected/`，金标不进 `fixtures/`。
- `evidence` 用 `文件#定位` 形式：表格到单元格区间，文档到页与块，序列到窗口区间。
- `tags` 供分层报分用（表头行数、语言、版面类型、领域），新增 tag 先在本文件登记再使用。
- `annotation.adjudicated=false` 的用例不进 `unseen_acceptance`。
