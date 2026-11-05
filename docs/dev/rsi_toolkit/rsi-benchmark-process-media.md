# Real Benchmark RSI Process Media

Evidence root:
`/Users/payne/Vibe/AgentOS/evidence/rsi-toolkit/rsi-benchmarks/2026-10-27/`.

These captures show the real benchmark RSI process, independently of
the earlier synthetic ledger viewer. They are **evidence replay, not live screen
recording**. The snapshot time is visible in the static HTML and saved projection.

## Final Snapshot

Final capture time: **2026-10-27T13:25:48.553Z** (21:25:48 Asia/Shanghai).
The final snapshot includes Job-Bench v1 completed with `NO_IMPROVEMENT`,
WorkBuddy code v1 unscored, WorkBuddy code v2 startup failure, and WorkBuddy code
v3 completed with `NEEDS_REVIEW`. It shows the
installed control agent's completed `skill_read self-evolve` and `evolution__run`
calls, baseline worker `skill_read benchmark-worker`, execution states, saved
scalar scores, and candidate Skill differences when a candidate exists.

Job-Bench has seven saved worker executions and two candidates; WorkBuddy v3
has six executions and one candidate. Both original orchestration summaries
retain their failed final-review status. Each separate
`control-review-recovery-1` records completed real Mint `skill_read`, status and
review inspection, with no new runs or worker replay and unchanged executions.
The replay displays original failure and recovery separately. These are saved
process states, not a claim that either benchmark was rerun during capture.

Media directory:
`/Users/payne/Vibe/AgentOS/evidence/rsi-toolkit/rsi-benchmarks/2026-10-27/media/`.

- [final-process.html](../../../evidence/rsi-toolkit/rsi-benchmarks/2026-10-27/media/final-process.html): standalone report, no server required.
- [final-projection.json](../../../evidence/rsi-toolkit/rsi-benchmarks/2026-10-27/media/final-projection.json): bounded fields used by the report.
- `final-desktop-*.png`, `final-mobile-*.png`: ten process screenshots. Desktop
  captures are 1440 x 1000; mobile captures are complete 390px-wide reports.
- [final-process.mp4](../../../evidence/rsi-toolkit/rsi-benchmarks/2026-10-27/media/final-process.mp4), `.webm`: saved-evidence replay, **17.76 seconds**. MP4 is H.264, 1440 x 900, 444 frames, without audio.
- [final-capture-report.json](../../../evidence/rsi-toolkit/rsi-benchmarks/2026-10-27/media/final-capture-report.json): exact snapshot time, run IDs, statuses, screenshot
  paths, layout checks and replay duration.

The earlier `current-*` snapshot is preserved separately. Final capture used
Node 22.23.3, local Chrome, Playwright and ffmpeg. All eight desktop/mobile layout
checks reported document width equal to viewport width; page errors were empty.
Desktop states, candidate views, mobile heading layout and decoded MP4 frames
were visually checked; ffmpeg decoded the complete MP4 without errors. A mobile
duplicate fixed watermark was hidden to prevent heading overlap; the page header
retains the explicit evidence-replay label. Chrome's close promise timed out
after both contexts and video had been saved; the bounded shutdown is recorded
as `timed_out_after_contexts_saved`, independently of page/layout checks.

### Final SHA-256 Inventory

Every filename below is relative to the absolute media directory above.

| File | SHA-256 |
| --- | --- |
| `final-process.mp4` | `0b6e242c5f6713a12f980497b1ef9ab048eb078a54e5c55066f9c79b1a849fee` |
| `final-process.webm` | `c690fac67e6c00229cae7e123cb47685f06ff3c3dd048d5c261c71afe5a05e78` |
| `final-process.html` | `053c7fa0901502c8318996faddc9cb4a5ab898a87ea2e34eb4cb47716455002d` |
| `final-projection.json` | `4ef01f052cb3e2474e8a4ea816a5e2acd88c29a5c09a7e0299175daaef785b9e` |
| `final-capture-report.json` | `6e69a901f28c82010a47e217c1a744e88d61ae238c963bf1a9afd2bdf69a6261` |
| `final-desktop-jobbench-v1.png` | `81b1819fca3214d9780a20c070fcfa1fabf471d28f94df00054d1322e2830a1d` |
| `final-desktop-jobbench-v1-candidate.png` | `e44fc6de77800b637867596afdae5d4a63f4562111e13f13685e6493b97fbbfe` |
| `final-desktop-workbuddy-code-v1.png` | `8361196d0b69ff7cbf78feea40fdf40e3cdd2dd1b96a525ab51bc136f7a12a4f` |
| `final-desktop-workbuddy-code-v2.png` | `b3e2ab48299c118fe7ecabb6467ae5ebc16fbe5ae04099d574e937639cf96450` |
| `final-desktop-workbuddy-code-v3.png` | `a32ba21fbb6f56d64916eda965aab4e858d46ded7f6bf95d45836e40398b046d` |
| `final-desktop-workbuddy-code-v3-candidate.png` | `b929f796ded20a32541eb99786c2678d00b3bb627902f6bc732f4c8d337ec89d` |
| `final-mobile-jobbench-v1.png` | `2ff673eee912ee71a78c471d205917d0d7b898ae54001001d07f0ac8727097e3` |
| `final-mobile-workbuddy-code-v1.png` | `b9787cb83ad2332329032fea7e591dfb784b5fa8f0f066d8943027f313f19de4` |
| `final-mobile-workbuddy-code-v2.png` | `b9787cb83ad2332329032fea7e591dfb784b5fa8f0f066d8943027f313f19de4` |
| `final-mobile-workbuddy-code-v3.png` | `b9787cb83ad2332329032fea7e591dfb784b5fa8f0f066d8943027f313f19de4` |

## Evidence Boundary

The generator reads approved summaries, installed-control NDJSON tool events,
worker NDJSON tool names, exported run/version/execution JSON, and read-only
controller SQLite/CAS records while a run is active. CAS bytes are checked
against their SHA-256 references. It projects public tool names and only the
`self-evolve` / `benchmark-worker` Skill labels, version metadata, bounded
candidate Skill text/diffs, scalar scores, and terminal statuses.

It does not read judge rubric logs, gold answers, hidden tests, or raw judge
responses. Raw tool output, command arguments, environment, session identifiers,
credentials, and user workspace paths are excluded. No model call, experiment
restart, controller mutation, or existing-viewer change is performed.

Construct, select and audit reuse the same selected task in these experiments.
Scores describe same-task repair only; they do not establish generalization or
a full benchmark result. Pending/missing verification stays unscored.

## Reproduce

From `/Users/payne/Vibe/AgentOS`:

```sh
/Users/payne/.nvm/versions/node/v22.23.3/bin/node docs/dev/rsi_toolkit/capture-rsi-benchmark-process.mjs --record
/Users/payne/.nvm/versions/node/v22.23.3/bin/node docs/dev/rsi_toolkit/capture-rsi-benchmark-process.mjs --final --record
```

The final command writes separate `final-*` files after the selected runs and
review recovery finish. The screenshot runner uses local Chrome and ffmpeg; all report content
is local and no external browser requests are permitted.
