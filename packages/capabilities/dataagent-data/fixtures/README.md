# fixtures

合成、中性的测试夹具，不含真实客户数据。

| 文件 | 用途 |
|-|-|
| `claims.csv` | CSV 解析与坏行/编码测试的基线 |
| `expense.json` | 嵌套 JSON 记录、DataBatchRef 与字段路径测试的基线 |

工作簿与 PDF 夹具由 `tests/conftest.py` 的 `build_xlsx` / `build_pdf` 生成，避免把二进制和特定 openpyxl/pdfplumber 版本绑定。
