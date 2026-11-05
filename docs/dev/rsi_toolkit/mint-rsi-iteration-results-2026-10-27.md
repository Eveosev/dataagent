# Mint CLI RSI Iteration: 2026-10-27

## Scope

These experiments use actual Mint CLI 0.1.10 / Core 0.1.6 and
MiniCPM-V-4.7-35B-A3B. Mint reads the installed `self-evolve` Skill, starts RSI
over control MCP, and the controller launches fresh Mint workers with generated
native `benchmark-worker` Skills. The proposal model reads actual public
construct trajectories and scalar verifier results. Hidden rubric/test content
is excluded from workers and proposal feedback.

Each benchmark uses one selected public task with fresh construct/select/audit
replicas. This is task repair with repeated measurements, not disjoint tasks,
benchmark-wide results, or evidence of generalization. Earlier direct Mint
solves are reported separately and are not RSI iteration evidence.

## Results

Job-Bench v1 completed on `bookkeeping_accounting_and_auditing_clerks/task2`:

| Version | Construct | Select | Audit |
| --- | ---: | ---: | ---: |
| Baseline | 0/52 | 6/52 | 6/52 |
| Candidate 1 | 0/52 | 6/52 | Not selected |
| Candidate 2 | 6/52 | 0/52 | Not selected |

Both actual proposal calls generated different native Skills. Candidate 1 tied
the baseline on select and candidate 2 regressed, so the baseline remains the
selected version. Final decision: **`NO_IMPROVEMENT`**. Seven actual Mint workers
completed. Run: `run-931a5a78545d4d31855d9de3ebdd1e3d`. Candidate 2
added complex CSV parsing and numeric conversion guidance after reading public
construct tool failures; its construct gain did not transfer to its fresh
select execution.

WorkBuddy code task `bug_fix-easy-a_crash_in_local` completed:

| Version | Construct | Select | Audit |
| --- | ---: | ---: | ---: |
| Baseline | 0/3 | 0/3 | 3/3 |
| Candidate 1 | 0/3 | 3/3 | 3/3 |

Run: `run-d14a5aa3d1e447d4aff039b01ce2735a`.
Two real proposal calls produced one unique candidate. Proposal 2 repeated the
same Skill and generated `candidate.duplicate`, with no additional evaluation.
All six workers completed and proved successful native Skill loading. The
controller decision is `NEEDS_REVIEW`: select improved and audit did not regress.
Audit tied the baseline, so **no audit gain or stable improvement is established**.

Baseline ID: `v-fb16dab2510e47dfac941fa0be4914c8`.
Candidate ID: `v-eb44b37d0ea4483ba53647ac7048d42e`.
Candidate Skill SHA-256:
`0dbd8cd9d81720b8055ff2181a892235c26ee706da8b77af70f49e1bcca2ffaf`.

The candidate added workspace inspection, defensive cleanup guidance and
attribute checks based on the public task/trajectory. The identical Skill scored
0/3 on construct and 3/3 on later fresh runs, while baseline audit also reached
3/3. This is substantial execution variance; the procedure change cannot be
isolated as the cause of improvement from these samples. It has not been applied
to a live product or published as a validated improvement.

## Failures And Recovery

- WorkBuddy v1: actual baseline completed, but upstream patch preparation exited
  128 because the archive replica lacked the Git baseline created by the
  upstream Dockerfile. Recorded `unscored`; no candidate score.
- WorkBuddy v2: isolated source virtualenv symlink was denied by Seatbelt during
  preflight. No model request or RSI run occurred.
- Both Job-Bench v1 and WorkBuddy v3: all worker execution and grading completed. The original final
  Mint review failed with HTTP 400 after a full status response exceeded the
  model context. Original `summary.json` remains failed and unmodified.
- A fresh actual Mint session for each experiment subsequently loaded
  `self-evolve`, read status at cursor 7041 (Job-Bench) or 2202 (WorkBuddy), and
  read review through a service with mutation/worker execution
  disabled. `control-review-recovery-1/recovery.json` confirms no new runs and
  unchanged executions; its supplement records completed RSI. Original and
  recovered run/events/executions/versions exports are byte-identical.

The WorkBuddy fix initializes only pristine public files in Git before staging
operator Skills. The subsequent MCP fix bounds default status to 20000
serialized characters, preserves truncation metadata and durable cursor, and
offers `compact=false` for the complete response. Stored evidence is not pruned.
These fixes were integrated into the product after Job-Bench became terminal.
Historical measurement sources remain separate and unchanged.

## Reproduction And Evidence

[Runbook](/Users/payne/Vibe/AgentOS/apps/plugins/rsi-toolkit/docs/benchmarks/mint-rsi-iteration-runbook.md)
contains exact local input paths, fresh-run commands and replay-free review
recovery. Prepared manifests and pinned upstream dependencies can be recreated
using its linked preparation runbooks. The credentialless local proxy must be
available; its upstream provider weights/routing cannot be independently frozen.

Persistent evidence root:
`/Users/payne/Vibe/AgentOS/evidence/rsi-toolkit/rsi-benchmarks/2026-10-27/`.

| Directory | Contents |
| --- | --- |
| `jobbench-v1/` | Complete Job-Bench experiment, control/worker NDJSON and graders |
| `jobbench-v1/control-review-recovery-1/` | Successful read-only Mint review |
| `workbuddy-code-v1/`, `workbuddy-code-v2/` | Preserved failed/unscored attempts |
| `workbuddy-code-v3/` | Complete iteration and original final-review failure |
| `workbuddy-code-v3/control-review-recovery-1/` | Successful read-only Mint review |
| `source-snapshots/` | Frozen source differences used for actual measurements |
| `media/` | Screenshots and short, explicitly labeled evidence replay |

Public input snapshots, submitted output hashes, commands, versions, proposal
prompts/responses/usage and scalar scores are retained. Hidden grader logs remain
local audit material outside publishable Mint packages. Source and evidence
manifest verification passed for both terminal experiments: Job-Bench has seven
verified executions, two proposals and two unique candidates; WorkBuddy has six
verified executions, two proposals, one unique candidate and one duplicate.
The inventories contain 7603 and 3634 files respectively. The heuristic
credential scan found no matches. Public prepared inputs and original absolute
path provenance are archived under each experiment's `prepared-inputs/`.

## Code Verification

After integrating the public Git baseline and compact status fixes, the focused
controller/bridge tests passed: 40 passed. The stdlib offline audit tests passed:
5 passed. Final full product regression: **541 passed, 13 skipped**, one existing
Starlette deprecation warning. Report: `verification/product-pytest-final.xml`.
The earlier full-suite attempt is preserved as `verification/product-pytest.xml`
(539 passed, 13 skipped, one detached-child timing assertion failed). A controlled
startup delay reproduced that fixture race. Waiting for the real child readiness
before starting its measured timeout fixed only the test; both immediate and
delayed startup remain covered. Full Mint host tests: 29 passed. Details are in
`verification/mint-timeout-fixture-triage.md`.

An independent source and raw-evidence review found no additional actionable
issue. It verified the actual Mint control/worker calls, public input identity,
bounded proposal feedback, pinned scores, baseline retention and unchanged
review-recovery exports. See
[review](/Users/payne/Vibe/AgentOS/docs/dev/rsi_toolkit/mint-rsi-iteration-review-2026-10-27.md).

## Evaluation Limits

WorkBuddy uses unchanged upstream hidden rule tests in pinned Docker image
`sha256:629e71acc69a58797cd222d6b33ea4f6f1fc3bbd6f93d253776c2e6416710e1b`,
with network disabled during grading. Job-Bench uses the pinned weighted rubric
judge and a request-only JSON transport format constraint. The Job-Bench solver
and judge share a model; self-preference and correlated errors remain possible.
Neither Mint exit 0 nor a natural-language success claim is treated as a score.

## Delivery

[New Feishu RSI result document](https://modelbest.feishu.cn/docx/ODbIdm0Waoxf7jxgpu1coyT6nue)
is in the requested folder. It records the actual iteration results, failure
recovery, exact reproduction commands, and the limits of these measurements.

Local handoff files are in
`evidence/rsi-toolkit/rsi-benchmarks/2026-10-27/delivery/`:

- `rsi-toolkit-source.tar.gz`: 356 tracked or current untracked source files,
  including benchmark launchers and plugin packages. Ignored state, credentials,
  caches and benchmark data are excluded. `SOURCE-SHA256SUMS` verifies every file.
- `rsi_toolkit-0.1.0-py3-none-any.whl`: offline wheel build; its controller,
  evidence and MCP modules match the final source byte-for-byte.
- `manifest.json`: source, test, experiment and media artifact references.

The source archive represents the current working tree on base commit
`a9e536fc1bba53d287e6d75cce32600b0daadffc`; it includes uncommitted changes and
is identified by file hashes. It is a local code handoff, not a MintHub release.
The Python wheel contains the service; the source archive also contains Mint
plugin installation and benchmark reproduction code.

[Media index](/Users/payne/Vibe/AgentOS/docs/dev/rsi_toolkit/rsi-benchmark-process-media.md)
links ten PNG screenshots and a 17.76-second MP4. They replay saved actual
execution evidence and are explicitly labeled, not live recordings. Video
decoding and viewport checks passed; the browser-close promise timed out after
contexts/video had been saved, was bounded, and left no capture process.
