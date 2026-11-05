# S0 示例

所有文件均由 `tests/test_examples.py` 以对应的 core 类型校验：

| 文件 | 类型 |
|-|-|
| `extraction-partial.json` | `CapabilityResult[ExtractedRecordRef]` |
| `assessment-unknown.json` | `Assessment[str]` |
| `computed-result.json` | `ComputedResult` |
| `needs-input.json` | `CapabilityResult[dict]`（两段式推理首次调用） |
| `semantic-draft-rule.json` | `SemanticDraft` |
