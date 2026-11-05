# Mint RSI Iteration Review

An independent agent reviewed the intended combined source, WorkBuddy v3
evidence, and terminal Job-Bench v1 evidence. No additional actionable
correctness, security or regression finding was reported. The audit did not
mutate product source, replay workers, call a model or rerun benchmarks. Only
this review document was updated after the final evidence inspection.

## Reviewed Changes

- Bounded public trajectory feedback and trusted operator execution caps.
- Actual Mint CLI native Skill loading and upstream benchmark bridge.
- Control Skill installation, actual MCP run proof and durable setting checks.
- Terminal-only review recovery with mutation and worker execution disabled.
- Pristine public Git baseline for WorkBuddy official patch capture.
- Bounded MCP status, truncation flags, durable cursor and full opt-out.

The latter two fixes were reviewed in `/private/tmp/rsi-toolkit-wb-fixed`, while
Job-Bench was measuring the frozen original source. They are now integrated in
the product. The Job-Bench frozen bridge hash remains
`00bc04fc6b5ba577fe60fce204a45aa554aad03bfe54fd0ff0ab6c36968ebe9c`;
the integrated bridge hash is
`64073042db4913b8a883eb60037b4582ddda1efc4c92e2a61dfce58c656376e3`.
The recorded experiment must be attributed to its frozen source, not the later
integrated source. No measurement-drift event was present in the Job-Bench run.

## Evidence Findings

The WorkBuddy recovery invoked only `skill_read self-evolve`,
`evolution__status(cursor=2202)` and `evolution__review`. Recovered run, event,
execution and version exports matched the original byte-for-byte. No replay or
new experiment occurred.

The public Git baseline commits only pristine archive files before staging
worker assets, excludes Skill paths from patch capture and does not load global
configuration or templates.

Compact status intentionally returns the latest 20 non-host summaries and
advances the durable high-water cursor. It reports truncation and offers
`compact=false`; the reviewer did not classify this documented summary behavior
as lost durable events. Consumers requiring all events must opt into full
retrieval.

## Job-Bench Terminal Audit

Evidence root:
`evidence/rsi-toolkit/rsi-benchmarks/2026-10-27/jobbench-v1`.
The durable run `run-931a5a78545d4d31855d9de3ebdd1e3d` completed with
`NO_IMPROVEMENT` and retained baseline
`v-83cf7021dc93459d9549043b50542bc7`.

The control-start NDJSON proves installed `self-evolve` loading and exactly one
successful `evolution__run`. Durable settings record two steps, one proposal per
step, ten maximum executions, 900-second worker timeout, 60 worker steps,
14,400-second wall time, and `MiniCPM-V-4.7-35B-A3B`.

All seven workers completed under Mint CLI 0.1.10. Each used a distinct fresh
workspace with the same eight public input files; only the staged Skill
differed. Raw NDJSON shows successful native `skill_read benchmark-worker`
before any task tool, with an exact recorded Skill body. All seven isolation
probes passed. Worker environments contained only the recorded runtime
allowlist, with no agent or operator token.

Both proposal calls used actual construct feedback. Step 0 received baseline
output and 32 bounded public tool events; step 1 received baseline and candidate
1 output and 32 events each. The second proposal adds CSV parsing and numeric
conversion guidance corresponding to observed parsing failures. Verification
feedback contained only score and status; hidden rubric criteria, judge output
and grading-file references were absent. Two distinct candidate versions were
evaluated; no duplicate event occurred.

All seven fresh judge directories produced scored results with all eight
rubrics accounted for and no reported judge issues. The upstream checkout was
at `fa03a17f9ff662f136798a274e10011c3aa00fd0`; every result recorded judge hash
`a9a21526cb23803a795c7e064772a1e32ce54b77673a3d288104930eba0339f4`
and rubric hash
`282ca1e5de459517cbd9e1b4e2746ddd9b11932354ed71f00937263e7da20291`.
The same model judged all executions with JSON transport mode. These are
weighted rubric points, not counts of passed tests:

| Version | Construct | Select | Audit |
| --- | --- | --- | --- |
| Baseline | 0/52 | 6/52 | 6/52 |
| Candidate 1 | 0/52 | 6/52 | Not selected |
| Candidate 2 | 6/52 | 0/52 | Not selected |
| Retained baseline | 0/52 | 6/52 | 6/52 |

Candidate 1 tied baseline on select and candidate 2 scored lower, so baseline
retention matches the frozen selection rule. Only baseline required an audit
execution, yielding seven workers in total. No candidate audit score is implied.

The original launcher summary remains failed because its terminal Mint review
received upstream HTTP 400 after successful Skill loading and status retrieval.
The durable experiment was already completed. Recovery
`control-review-recovery-1` subsequently completed using only `skill_read`,
`evolution__status(cursor=7041)` and `evolution__review`; it issued no run,
cancel or publish call. Its compact status returned no new events and the same
cursor. Run, manifest, event, execution, version, proposal-response and review
exports matched the originals byte-for-byte. This supports review recovery
without worker replay and preserves the original failure evidence.

## Claims Requiring Care

WorkBuddy has two actual proposal calls, one unique candidate and six fresh
executions. Select improves from 0/3 to 3/3; audit ties 3/3 to 3/3. There is no
demonstrated audit gain or held-out generalization. `NEEDS_REVIEW` means audit
did not regress after a select gain; it does not establish statistical benefit.

Job-Bench has two actual proposals, two distinct candidates and seven fresh
executions. Its outcome is `NO_IMPROVEMENT`; the construct gain of candidate 2
does not outweigh its select regression. Same-model rubric judging remains a
measurement limitation. Neither benchmark establishes held-out generalization,
statistical benefit or a full-suite benchmark result. The initial failed CLI
review and later successful read-only recovery must both remain explicit.

This final audit used existing raw evidence and did not run tests or benchmarks.
Product regression results and the final artifact manifest belong to the final
result report.
