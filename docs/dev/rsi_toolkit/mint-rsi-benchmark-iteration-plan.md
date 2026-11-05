# Mint CLI RSI Benchmark Iteration

## Goal

Mint CLI loads the installed `self-evolve` Skill and calls RSI Toolkit MCP to
start a real experiment. RSI analyzes actual worker trajectories, makes two
native Skill proposal calls, evaluates unique candidates with fresh Mint CLI sessions and the
upstream benchmark verifier, then retains the selected version or the baseline.

The previous four direct Mint runs are separate measurements and do not count
as RSI iterations.

## Experiment Scope

| Benchmark | Public Task | Verification |
| --- | --- | --- |
| Job-Bench main | bookkeeping_accounting_and_auditing_clerks/task2 | Pinned upstream weighted rubric judge, JSON transport mode |
| WorkBuddy code | bug_fix-easy-a_crash_in_local | Official rule functions and hidden tests in a pinned Docker image |

For each task, construct/select/audit are independent fresh executions of the
same underlying task. This is task repair with repeated measurements, not a
disjoint task split or evidence of generalization. Two proposal steps use only
construct execution feedback; select chooses a winner before audit is run.
Ties retain baseline. Audit regression retains baseline. No live product Skill
is automatically published or replaced.

## Constraints

- Use installed Mint CLI 0.1.10 and Core 0.1.6, with an explicit prompt argument.
- Use the existing credentialless MiniCPM model proxy; never copy provider keys.
- Controller agents receive a target-scoped agent token, never an operator token.
- Workers read only pristine public inputs, native Skill, and installed runtimes.
- Hidden tests, rubrics, and grader output remain outside solver workspaces.
- Proposal feedback contains bounded public tool events and numeric verification,
  never hidden rubric/test details.
- Record raw NDJSON, Skill hashes/diffs, proposal lineage, scores, artifacts,
  process status, runtime identities, and exact source hashes.
- Evidence lives outside the publishable plugin directory.
- Failed, timed-out, unscored, and duplicate attempts remain explicit.

## Implementation Tasks

- [x] Controller: bounded actual trajectory feedback, operator-configured budgets,
  honest verifier metadata, atomic terminal drift evidence.
- [x] Benchmark bridge: fresh binary input staging, native Skill loading proof,
  actual Mint CLI host, and upstream per-execution grading.
- [x] Launcher: install bundle in a disposable private Mint project; Mint invokes
  `evolution__run`; wait for completion; Mint invokes status/review; export evidence.
- [x] Run two real proposal steps for each selected task and audit the evidence.
- [x] Publish a new Feishu result document using existing document permissions.

## Ownership And Interfaces

`service/control/controller.py` accepts optional operator execution caps. Existing
defaults stay unchanged. `conformance/benchmark/rsi_benchmark.py` provides
`build_experiment(...) -> (cases, host, verifier)`.
`conformance/benchmark/run_rsi_benchmarks.py` owns the real CLI control workflow
and reproducible experiment export. The controller must not be started through a
Python `run()` fallback if the Mint Skill/MCP call fails.

## Verification And Review

Focused tests cover trusted budgets, bounded feedback with hidden criteria
excluded, pristine public staging, Skill load proof, real protocol parsing, and
MCP invocation evidence. Run the service suite once the changes are integrated.
Review source and raw real-run artifacts independently before reporting results.

## Progress

2026-10-27: Three implementation agents dispatched for controller, bridge, and
launcher. Existing branch `codex/rsi-toolkit-delivery` reused; previous untracked
benchmark adapters preserved. Local model proxy ready at request count 538.

Controller and bridge source frozen for real execution. Focused integration:
41 passed, 1 opt-in skip. Full service suite with authorized loopback sockets:
480 passed, 1 skipped, 1 existing Starlette warning. Independent review dispatched.

Both v1 control agents proved installed `self-evolve` loading and exactly one
`evolution__run`, with requested settings durably checked. WorkBuddy v1 stopped
unscored because the upstream verifier requires a Git baseline, initialized by
the upstream Dockerfile but missing from our archive-only replica. Its result
and Mint review are preserved. WorkBuddy v2 stopped before model calls because
the isolated source copy used a virtualenv symlink that Seatbelt denied. The
fix is being tested in an isolated source copy while Job-Bench v1 continues on
its frozen original source. Latest complete regression: 532 passed, 12 skipped;
separate opt-in actual Mint CLI/MCP fixture test: 7 passed.

2026-10-27 20:54 Asia/Shanghai: WorkBuddy v3 controller completed with two real
proposal calls and one unique candidate; proposal 2 was a duplicate. Six fresh
workers scored baseline construct/select/audit=0/0/1 and candidate=0/1/1.
Selection improved but audit tied, so no audit gain is claimed. The first final
Mint review failed with HTTP 400 after an 869117-character status response.
The terminal experiment was reviewed using actual Mint CLI through a read-only
recovery service at cursor 2202. No new run or execution was created; exported
run/events/executions/versions match the original. Original failed summary is
preserved and a recovery supplement records completion.

Ruling: keep compact MCP status as the default, with explicit truncation flags,
the durable high-water cursor and compact=false for full retrieval. This fixes
the observed model context overflow while preserving complete stored evidence;
consumers needing every event must request the full response.

The compact response fix and WorkBuddy pristine Git baseline fix remain in the
isolated source copy until Job-Bench v1 reaches terminal state. An independent
read-only review found no additional actionable issue in the intended combined
source. Job candidate 1 construct/select=0/6 out of 52, equal to baseline; the
second real proposal is executing. No terminal outcome is inferred.

New result document, created in the requested folder with existing permissions:
https://modelbest.feishu.cn/docx/ODbIdm0Waoxf7jxgpu1coyT6nue

Runbook: apps/plugins/rsi-toolkit/docs/benchmarks/mint-rsi-iteration-runbook.md.
Media script: docs/dev/rsi_toolkit/capture-rsi-benchmark-process.mjs; all media
are labeled evidence replay, not live screen recording.

Before syncing the isolated fixes, the product regression tests reproduced the
original behavior: `test_control_mcp_status.py` plus the WorkBuddy Git-baseline
test returned 3 failed, 1 passed. The two size assertions observed 2117315 and
19003685 serialized characters, and pristine Git lookup exited 128. This is the
RED evidence; implementation remains frozen until Job terminal.

2026-10-27 21:20 Asia/Shanghai: Job-Bench v1 completed with two unique candidates
and seven fresh Mint workers. Baseline construct/select/audit=0/52,6/52,6/52;
candidate 1=0/52,6/52; candidate 2=6/52,0/52. Final NO_IMPROVEMENT retains
baseline. Its original final Mint review also hit the unbounded status/context
failure. Read-only review recovery completed at cursor 7041 with no new run or
execution. The original summary remains unchanged. Both experiment offline
audits passed (13 total workers, four actual proposal calls). The combined
source fixes are now integrated; 40 focused tests passed. Final full regression
and a detached-child test scheduling investigation are tracked in the result
report. Historical source snapshots are retained separately.

Final verification: 541 passed, 13 skipped, one existing Starlette warning.
The detached-child fixture race was reproduced with a controlled startup delay
and fixed by synchronizing readiness in the test only; the original failing
report remains preserved. Independent terminal Job-Bench evidence review found
no additional actionable issue. A cached offline wheel build completed.
