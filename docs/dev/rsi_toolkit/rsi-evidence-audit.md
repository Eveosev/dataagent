# Real RSI Evidence Audit

Run from `/Users/payne/Vibe/AgentOS` after the selected experiment is terminal and its final source snapshot has been saved. The script uses only Python's standard library and makes no network or model calls.

```sh
python3 docs/dev/rsi_toolkit/audit_rsi_evidence.py \
  --experiment-root evidence/rsi-toolkit/rsi-benchmarks/2026-10-27/workbuddy-code-v3 \
  --experiment-root evidence/rsi-toolkit/rsi-benchmarks/2026-10-27/jobbench-v1 \
  --archive-public-inputs
```

Each experiment receives `evidence-audit.json` and `artifact-manifest.json`. The audit refuses active controller state before inventorying artifacts. It checks raw Mint NDJSON and exported executions for a completed first `skill_read`, exact Skill content hashes, equal public input snapshots, and agreement with the upstream verifier score. It records proposal calls, unique candidates, duplicate events, and unchanged recovery exports.

The artifact manifest contains relative paths, byte counts, and SHA-256 hashes. It excludes audit outputs, sockets, SQLite WAL/SHM files, caches, and symlink targets. A heuristic credential scan reports file paths and finding categories without printing matched values. This is not a guarantee against every possible secret format.

`--archive-public-inputs` retains the frozen prepared manifest, public prompt, input hashes, and public task inputs under `prepared-inputs/`. Original absolute paths remain in the archived manifest and provenance. Create a new prepared manifest with relocated public inputs for a rerun; do not change frozen evidence. Hidden rubrics and upstream hidden tests are not copied by this option.

Offline auditing uses the saved exports, controller CAS, worker snapshots, and verifier summaries. A fresh execution still needs Mint CLI/Core, Python dependencies, a model proxy, upstream grader code and hidden inputs, and the pinned Docker image for WorkBuddy. The audit report lists temporary source paths that remain external dependencies.

Focused tests:

```sh
python3 -m unittest discover -s docs/dev/rsi_toolkit -p test_audit_rsi_evidence.py -v
```

Both terminal audits on 2026-10-27 passed. WorkBuddy v3: six verified executions;
two proposal model calls, one candidate version, one duplicate event. Baseline
construct/select/audit scores were `0/0/1`; winner scores were `0/1/1`.
Job-Bench v1: seven verified executions; two proposal calls and two unique
candidates; final `NO_IMPROVEMENT`, baseline `0/52,6/52,6/52` retained. Both
read-only recovery exports are unchanged and credential scans found no matches.
The manifests inventory 3634 WorkBuddy files and 7603 Job-Bench files. These are
replicas of one public task per benchmark and do not establish held-out
improvement.
