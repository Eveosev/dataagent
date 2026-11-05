---
name: code-landing-quality
description: Use when implementing a design/build plan in a local repository and the result must pass a quality gate, or when a Tester must accept one development round against the plan — 按方案开发、落地实现、代码质检、版本验收、Tester 评审、rubric 评分、轮次对比、rN-review. Runs plan checklist extraction, machine measurement, probe-based defect logging with P0/P1/P2 severity, hard-rule and defect gates, weighted rubric scoring, and round-to-round diff, all with file:line evidence.
---

# Code Landing Quality

Score one development round of a package against its plan with a fixed rubric. Two modes share the same rubric and scripts:

| Mode | Who | Goal | Procedure |
|-|-|-|-|
| Implement | developer | build against the checklist, self-check before handing over | this file, §Implement |
| Accept | Tester | independent acceptance of one round, compared with the previous round | [tester.md](references/tester.md) |

Default to the user's language. Every verdict must trace to a command, a probe, or `file:line`.

## Standard

- Rubric: `docs/standards/code-landing-rubric.json` (v2.1). The skill carries byte-identical copies in `references/rubric.json` and `scripts/score_landing.py`; `quality_run.py` reports drift between them, and the tests fail on it. If the repository has no `docs/standards/`, use the skill copies.
- Summary: [rubric.md](references/rubric.md). Probes: [probes.md](references/probes.md).
- A result is acceptable only when `total ≥ 80` and no gate fires. The gates:

| Gate | Trigger | Cap |
|-|-|-|
| GATE-RED | any hard rule red | 59 |
| GATE-P0 | open/partial P0 defect (P0 cannot be waived) | 59 |
| GATE-P1 | open/partial P1 defect | 79 |
| GATE-CHECKLIST | any checklist item not done (excluding na/waived) | 79 |
| GATE-UNKNOWN | any hard rule unknown | 89 |
| GATE-UNMEASURED | rule null, or 0/1 without evidence, or na outside the profile | 89 |
| GATE-NO-CHECKLIST / GATE-NO-DEFECTS | `checklist` / `defects` is null | 89 |

- The scorer rejects a result (exit 2, no score) when it contradicts itself: a hard rule disagrees with its mirror rule, an open P0/P1 defect is linked to a rule scored 1, L2.1=1 while the checklist is incomplete, or `rubric_version` differs from the rubric.
- Freeze before measuring: record `rubric_sha256`, plan version, and the source snapshot. Changing weights, caps or gates after seeing results requires a version bump and a full re-run.

## Result file

One JSON per package and round. Start from `score_landing.py --template`, then fill:

| Field | Content |
|-|-|
| `scope`, `profile`, `round`, `date`, `facts_ref` | package, `contracts`/`runtime`/`capability`/`service`, `rN`, date, e.g. `agent-kernel@<sha>` |
| `snapshot` | `snapshot.py` digest per package (written by `quality_run.py --fill`) |
| `rules` | `{"score": 1/0/null, "evidence": "...", "na_reason": "..."}` |
| `hard_rules` | `{"light": "green/red/unknown/na", "evidence": "..."}` |
| `checklist` | from `plan_checklist.py --into`; each item gets `verdict` + `evidence` |
| `defects` | list of `{id, severity, status, title, location, rules, repro{input,expected,actual}, fix_evidence, waiver}`; `[]` = reviewed, none found |

## Implement

1. **Inputs.** Read the plan; name the target package, its test command, the profile, and what is out of scope.
2. **Checklist.** `plan_checklist.py <plan.md> --out $TMPDIR/checklist.json`. Mark non-requirement items `na` with a reason instead of deleting them. Items carry stable ids (`5.2#3f9a1c`).
3. **Build item by item.** Write the failing test first where possible; record the implementing `file:line` per item as you go. If an item cannot be implemented as written, stop and report the conflict.
4. **Measure.** `quality_run.py --repo . --package <pkg> --fill <result.json>`. Do not hand-edit entries marked `measured_by: quality_run`.
5. **Probe your own work** with the categories in [probes.md](references/probes.md) that apply. Log what fails as defects; a known defect left out of `defects` is a false report.
6. **Score.** `score_landing.py --result <result.json>`. Hand over only with the score output, the result file, and `rN-fixes.md` listing what changed per checklist item and defect id.

## Accept

Follow [tester.md](references/tester.md): freeze inputs → `quality_run --fill` → checklist verdicts → probes and defects → re-run every previous defect → fill the remaining rules → score → `round_diff.py` → check the developer's claims → write `rN-review.md` in the plan's record directory and register it.

## Decision rules

| Situation | Action |
|-|-|
| Scorer exits 2 | Fix the contradiction in the result file; never quote a score from an invalid result |
| GATE-RED / GATE-P0 | Not acceptable. Fix, or (hard rules only) record a dated exemption |
| GATE-P1 / GATE-CHECKLIST | Not acceptable for this round; list the open items |
| GATE-UNKNOWN / UNMEASURED / NO-* | Measure, or report "not deliverable" with what is needed to measure |
| Only L-axis failures | Semantic defect, not a test gap |
| `round_diff` shows 回归 or 未复核 | Resolve before concluding; 未复核 means a previous defect was not re-run |
| Same snapshot, different verdict | Explain which judgement changed and why |

## Anti-patterns

- Editing the rubric, caps or gates to make a package pass. `--self-test` asserts the caps stay below the grade boundaries.
- Citing a plan or README as evidence for a code claim (the scorer warns on document-only evidence).
- Treating `status: ok` or a green test suite as proof of semantic correctness.
- Marking a rule `na` to shrink the denominator without showing that `applies_when` is false.
- Dropping a previous round's defect instead of re-running it.
- Scoring with `--skip-tests` / `--skip-dup`; such reports are flagged as unusable for acceptance.

## Scripts

| Script | Purpose |
|-|-|
| `scripts/plan_checklist.py` | plan → checklist with stable ids; `--into` merges into a result, `--previous` diffs plan revisions |
| `scripts/snapshot.py` | source-tree digest of a package |
| `scripts/quality_run.py` | tests, hygiene, bundle drift, duplication (package + sibling packages), complexity, size; `--fill` pre-fills A1.1/A5.x/D1 (and A10.1 when it fails); `--result` scores |
| `scripts/score_landing.py` | scorer (copy of `docs/standards/score_landing.py`); `--template`, `--result`, `--self-test` |
| `scripts/round_diff.py` | previous vs current round: defects, rules, checklist, regressions |

Complexity uses radon when installed; otherwise an AST implementation of radon's counting rules (matched radon 6.0.1 on 670 functions). All scripts use only the standard library.

```bash
python3 -m unittest discover -s skills/code-landing-quality/tests
python3 skills/code-landing-quality/scripts/score_landing.py --self-test
```

Example: “按 07 方案实现 DA06.3 的四个 operation，用 code-landing-quality 自检并给出 rubric 报告。” / “对 dataagent-application 做第 6 轮验收，和 r5 对比。”
