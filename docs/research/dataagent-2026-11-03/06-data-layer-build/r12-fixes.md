# Round 12 修复：Reviewer F1/F2/F4（2026-11-04）

来源：独立评审报告 `dataagent-review/review-report.md`（综合 7.7/10，判 FAIL）。
本轮只修复阻断与入口级缺陷，未改契约、注册表、CLI/MCP 入口和其余原子。

## F1（P0）英文预防动词造成静默反向

- 位置：`src/dataagent_data/runtime/anchors.py`
- 根因：`avoid/prevent/refrain from/prohibit/forbid` 等英文预防动词不在 `_NEGATION`，比较分析也没有英文预防分支。锚点
  `Expenses should avoid exceeding 5000 CNY` 被读成 `upper 5000`，反向条件
  `exceeding 5000 CNY` 被接受，语义正确的 `not exceeding 5000 CNY` 反被拒绝。
- 修复：
  - `_EN_PREVENTIVE_PATTERN` 识别英文预防动词（含 `-s/-ed/-ing` 和
    `forbidden/banning/barring/stopping/guard against/protect against` 等形态）。
  - `_english_preventive_scope` 把前置动词按反向消费（`avoid exceeding` → `lower`，
    `prevent falling below` → `upper`），并识别后置被动式（`should be avoided`、
    `is prohibited` → 反向）。
  - 同一作用域出现两个预防动词或“否定词 + 预防动词”（`avoid and prevent`、
    `do not avoid`、`should not be avoided`）时判 ambiguous，fail-closed。
  - `_has_negation` 只在预防动词确实作用于比较时计入否定极性；`to avoid fraud`、
    `avoidance costs`、`prevention costs` 等不误判。
- 回归：`tests/test_round12_reviewer_findings.py` 覆盖解析、`anchor_supports_text`、
  `define_business_rules` 三层，以及不过度拒绝的反例。

## F2（P1）DA03.16.2 不校验前置条件锚点

- 位置：`src/dataagent_data/semantics/applicability.py`
- 根因：`define_rule_preconditions` 直接把 `proposal.conditions` 写入草案，不创建
  `AnchorResolver`，输入也没有 `document_ref`；伪造的 `page=999`、不存在的
  `source_ref` 仍返回 `ok`，并可依 `facts` 得出 `satisfied`。
- 修复：
  - 输入新增可选 `document_ref`；handler 创建 `AnchorResolver`，逐个核对条件锚点的
    源版本、存在性和 `anchor_supports_text`。
  - 无有效锚点的条件保留在草案中但清空 anchors、加入 `unknowns`，其求值强制为
    `unknown`；不再保存伪造锚点。带 `document_ref` 但条件无锚点时同样降级。
  - 有 issue 时整体返回 `partial`，不再返回 `ok`。
  - 保留旧调用兼容性：既无 `document_ref` 也无 anchors 时行为不变。
- F4 一并修复：`rule_ref` 允许契约规范的 `<id>@<revision>` 形式，draft id 使用
  `@` 前的 id 部分，不再触发 `execution_unknown`。

## 验证

| 检查 | 结果 |
|-|-|
| 契约测试 | 111 passed |
| 数据层全量 | 493 passed（473 + 20 个 Round 12 用例） |
| bundle 全量套件 | 493 passed |
| Reviewer F1 探针 | 反向条件 `needs_input + da02.anchor_value_mismatch`；正确条件 `ok` |
| Reviewer F2 探针 | 伪造锚点 `partial + da02.anchor_not_found + da03.unanchored_condition`，`anchors=[]`、`unknown` |
| `rule_ref='draft:rule:abc@r1'` | `ok`，draft_ref id 为 `draft:rule:abc:<uuid>` |
| `verify_local.sh` | exit 0（见 `evidence/round4/verify_local.log`；冷启动 3.25 s） |

## 未修复（记录为限制）

- F3（P2）：DA03.16.1 的 `scope_expression` 仍只检查来源存在性，不校验文本支持。
- F5（P2）：DA03.15.1 的 `basis_refs` 仍只判空，不解析 `EvidenceRef` 存在性；数据层没有
  EvidenceRef 仓库，需应用层补解析。
- F6/F7 的代码卫生与文档回写：本轮只更新了计划状态、本记录和
  `rule-decision-code-inventory.md` 的过时条目，未做死代码/长函数清理。
