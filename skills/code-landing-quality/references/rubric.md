# Rubric field guide

Canonical source: `docs/standards/code-landing-rubric.json` (v2.1); full explanation in `docs/standards/code-landing-rubric.md`. If this page and the JSON disagree, the JSON wins.

## Axes

| Group | Axis | Weight | What it measures |
|-|-|-|-|
| Code | A1 规模与重复率 | 6 | ≤3% duplicated lines (package + sibling packages); no whole-file copies |
| Code | A2 依赖与独立性 | 6 | direction, acyclicity, no ad-hoc copies |
| Code | A3 抽象度 | 4 | public surface smaller than internals |
| Code | A4 内聚 | 4 | module/function size, single responsibility |
| Code | A5 复杂度 | 7 | CC>10 ≤7.3% of LOC, CC>25 ≤1.1%, no >300-line function |
| Code | A6 功能自足 | 5 | runnable examples/fixtures, documented test command |
| Info | A7 契约面 | 0 | public surface facts only |
| Code | A8 可替换性 | 4 | port boundary + golden tests |
| Code | A9 可装载性 | 6 | manifest check, real pack, payload match |
| Code | A10 错误语义 | 5 | no bare except, registry consistency |
| Code | A11 演进性 | 4 | version single-source, in release list |
| Code | A12 契约对齐 | 4 | contracts referenced, not shadow-copied |
| Landing | L1 能力面落地 | 6 | all operations reachable, three-way manifest match |
| Landing | L2 语义正确性 | 12 | checklist done, adversarial probes, no decoy |
| Landing | L3 安全与治理 | 12 | path/access/egress/decision/whitelist |
| Landing | L4 健壮性与资源 | 6 | budgets, interruptible timeout, concurrency |
| Landing | L5 测试有效性 | 6 | negative cases, business assertions, real samples |
| Landing | L6 发布与溯源 | 3 | source-ref, docs match code |

45 binary rules, weights sum to 100. Machine-filled by `quality_run.py --fill`: A1.1, A5.1, A5.2, A5.3, D1, and A10.1 when it fails.

## Hard rules

| ID | Rule | Failure | Mirror rule |
|-|-|-|-|
| R01 | 强制面不依赖实现包 | red | A2.1 (red ⇒ 0) |
| R03 | 包级依赖无环 | red | A2.2 (equivalent) |
| D1 | 重复率 ≤3.0% | red | A1.1 (equivalent) |
| V1 | 版本单一事实源 | red | A11.1 (equivalent) |
| E1 | 错误码 registry 一致；无 registry 记 na | red | A10.2 (equivalent) |
| R13 | 破坏性变更升 major；无基线记 unknown | unknown | — |
| R14 | 契约不被影子复制；vendored 必须有同步门禁 | red | A12.1 + A12.2 (equivalent) |

A light without evidence counts as unknown. A light that contradicts its mirror rule invalidates the result.

## Gates

| Gate | Trigger | Cap |
|-|-|-|
| GATE-RED | hard rule red | 59 |
| GATE-P0 | open/partial P0 | 59 |
| GATE-P1 | open/partial P1 | 79 |
| GATE-CHECKLIST | checklist item partial/not_done/unjudged | 79 |
| GATE-UNKNOWN | hard rule unknown | 89 |
| GATE-UNMEASURED | rule null / no evidence / na outside profile | 89 |
| GATE-NO-CHECKLIST | `checklist: null` | 89 |
| GATE-NO-DEFECTS | `defects: null` | 89 |

## Severity

| Level | Definition |
|-|-|
| P0 | wrong result delivered as success (silent error); a security/governance gate can be bypassed by the caller; data loss or corruption; main path unusable |
| P1 | a MUST is unmet but the failure is visible; concurrency/resource/timeout defect under specific conditions; a client following the contract fails |
| P2 | robustness, maintainability, doc drift; no effect on correctness or safety |

Defect status: `open`, `partial` (counts as open), `fixed` (needs `fix_evidence`), `waived` (needs `waiver{by,date,reason}`; not allowed for P0).

## Profiles and na

A rule may be `na` only if it has `allow_na`, it is in the chosen profile's `may_na`, and `na_reason` shows its `applies_when` condition is false.

| Profile | Applies to | may_na |
|-|-|-|
| contracts | type/schema library, no operation entry | A10.2, L1.*, L2.3, L2.5, L3.*, L4.*, L5.3 |
| runtime | shared runtime, no business operation | A10.2, L1.*, L2.5, L3.5, L4.1 |
| capability | package exposing operations | A10.2, L2.3, L2.5, L3.*, L4.* |
| service | independently deployed service | same as capability |

## Evidence grades

- **A** — standard text, quoted verbatim after checking the source.
- **B** — empirical direction or number, but not a hard standard, or ported across languages.
- **C** — vendor default, second-hand claim, or unsupported convention.
- **D** — pure judgement; must remain visible in the report.

The scorer prints the grade mix of judged weight and warns when C+D exceeds 50%.

## Grades

| Score | Grade | Meaning |
|-|-|-|
| ≥90 | A | deliverable |
| 80–89 | B | acceptable with a known-gap list |
| 70–79 | C | demo only |
| 60–69 | D | internal integration only |
| <60 | E | not acceptable |

Acceptance is `total ≥ 80` **and** no gate fired. The weighted score ranks results within one rubric version; it never overrides a gate.
