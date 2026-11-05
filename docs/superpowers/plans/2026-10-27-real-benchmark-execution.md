# Real Benchmark Execution Plan

**Goal:** Run actual Job-Bench and WorkBuddy tasks through the installed Mint CLI and retain solver artifacts plus upstream scoring outputs.

**Scope:** Start with two Job-Bench main tasks and WorkBuddy code/office tasks. Report the exact sampled population; expand only after the execution and judge paths are working. No fixture output counts as task execution.

## Verified Prerequisites

- Docker server 29.8.2 is reachable with local execution permissions.
- Harness2 source is checked out at `1cfe254e8d25b15f37048c3730134686abe60335` in `/private/tmp/rsi-harness2-official`.
- Mint CLI 0.1.10 and Core 0.1.6 are installed.
- Existing credentialless model proxy listens on `127.0.0.1:19091`, model `MiniCPM-V-4.7-35B-A3B`.
- Dataset revisions and archives remain frozen as documented in `docs/dev/rsi_toolkit/harness2-repro-research.md`.

## Execution

- [x] Recheck Docker and network with local permissions.
- [x] Download the fixed official Harness2 source and read its benchmark guide.
- [x] Prepare Job-Bench main workspaces with public inputs only; preserve rubric separately.
- [x] Prepare WorkBuddy code and office workspaces using the task Dockerfile and preserve hidden tests separately.
- [x] Run fresh Mint CLI sessions with a real model, bounded steps/time, no leaked credentials, and raw NDJSON evidence.
- [x] Run the upstream Job-Bench rubric judge and WorkBuddy test/scorer on resulting artifacts.
- [x] Distinguish model failures, infrastructure failures, numeric scores, and unscored cases.
- [x] Record commands, code/data hashes, model, runtime, usage, artifacts, judge inputs and outputs.
- [x] Write actual outcomes and their limits to a new Feishu document using existing document permissions.

## Evidence Rules

No agent sees the hidden rubric, tests, gold patch or prior score. Do not modify task input or scoring to obtain a pass. Any Mint executor adaptation, non-default model, native environment, selected subset or omitted score component is explicitly labeled. A sample score is never presented as a full-suite or official leaderboard score.

## Execution Ledger

- WorkBuddy code and office real Mint sessions started on 2026-10-27. Code reached `end_turn` after 8 steps and changed `asgiref/local.py`; official grading pending. Office remains running at this entry.
- Runtime preflight failures were recorded before model invocation: macOS MIME-file permission and Mint CLI stdin forwarding. The runner now explicitly passes the prompt and allows only the required system MIME file.
- Grading uses a workspace snapshot. Operator-generated `.rsi-runtime/`, `mint.toml`, and `mint.lock` are excluded from that snapshot with hashes recorded; original solver artifacts remain intact.
- Four samples are selected for this initial execution. Results will not establish full-suite performance or RSI improvement without paired baseline/candidate runs.
- Final measured scores: Job-Bench bookkeeping 6/52; support 14/56 with solver budget exhaustion; WorkBuddy code 1/3; office rule 82/109 with five LLM rubrics passed and original composite 0.8018. Bookkeeping required judge-only JSON request formatting after two preserved unscored attempts.
- Persistent evidence: `/Users/payne/Vibe/AgentOS/evidence/rsi-toolkit/real-benchmarks/2026-10-27/`; 181 files verified by SHA-256 manifest. Evidence is outside the publishable plugin directory. Proxy count advanced from 409 to 538 requests with no transport errors; counts include judging and invalid-response attempts.
- Final full service regression: 439 passed, 1 existing Starlette warning. An earlier run exposed an existing terminal-status/event publication race in controller drift history; isolated rerun and final suite passed. Raw evidence initially triggered a scanner false positive for task IDs and was moved outside product packaging without changing scanner or evidence.
- Feishu result document: https://modelbest.feishu.cn/docx/DdqrddJEQoIdsuxw8ZhcoMA3nNh
