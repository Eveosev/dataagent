# Implementation Ledger

Plan: delivery-plan.md; architecture: plugin-architecture.md.
Execution authorized by user on 2026-10-27.

## Rulings

- Import the committed product subtree into the final product path now. The
  parent AgentOS workspace has no Git repository, so use a dedicated product
  repository on `codex/rsi-toolkit-delivery`. This isolates all writes from the
  dirty source host checkout and makes deliverable commits possible.
- Work concurrently on disjoint paths. The root owns integration and shared
  packaging; each implementation agent owns its assigned modules and tests.
- Keep legacy entry points available while introducing a host-neutral public
  orchestration entry point. Never claim the legacy paths inherit new controls
  until they are wired and tested.

## Interface / Ownership Check

| Work | Produces | Consumed by | Decision |
| --- | --- | --- | --- |
| Core | persistent experiments, release, control MCP | both hosts | host interface frozen in implementation briefs |
| Mint | host execute/cancel and package manifests | core | isolated files; root owns package dependencies |
| Bench | ledger cases and verifier | core + host smoke | public input separated from verifier data |
| Root | PilotDeck host adapter, launcher, packaging | end-to-end | no parallel edits to shared entry points |

## Tasks

- [x] Design and source research.
- [x] Import committed baseline into isolated product repository.
- [x] Core implementation and review; review fixes have focused regressions.
- [x] Mint adapter and package consumption, including real model tool/Skill calls.
- [x] Ledger benchmark and verifier; 9 ledger + 6 workflow cases.
- [x] PilotDeck adapter and packaging; stable main isolated real model calls.
- [x] Real model experiments and lifecycle verification.
- [x] Screenshots and recordings; cloud documentation created.
- [x] Final source/artifact archive upload, metadata readback and evidence download hash check.
- [x] Final code review, clean installation and artifact handoff.

## 2026-10-27 00:45 Snapshot (Asia/Shanghai)

Historical snapshot. Current status appears below; this section preserves the
observed state and must not be read as final acceptance.

- Source baseline tests: 177 passed. First integrated full regression: 278
  passed, one Starlette WSGI deprecation warning; further review fixes require
  a fresh final run.
- Product wheel built and installed in a separate clean venv. Both built-in
  benchmarks load from installed package data: ledger9/workflow6, no source cwd.
- Stable PilotDeck main cc7c4e6 isolated at port18987. Actual model read both
  plugin Skills and called capabilities/datasets/catalog/recall once each.
- Existing Rust18789 lacks required new_session and model-host routes. It was
  only probed; the user's existing service was not replaced.
- Mint CLI0.1.10/Core0.1.6 direct HTTP MCP is not enabled. Official SDK stdio
  bridge plus explicit .mcp.json was actually consumed. Real model read candidate
  Skill and called real RSI capabilities/datasets/catalog; final synthesis hit429.
- Full PilotDeck Default experiment is running with one genuine model proposal.
  Select score observed baseline2/3, candidate3/3; audit still running, no gain
  conclusion made. Mint OPRO baseline attempt stopped on upstream429, preserved.
- Review fixes include release-pointer atomicity, unknown-release recall denial,
  credential redaction, URL/redirect credential confinement, hardlink-safe staging,
  preserved unscored verifier details, preflight cancellation, bounded Mint drains.
- Real targets remain exploratory; live publish disabled until OS isolation is
  externally verified. Fixture release/rollback tests are not real-host proof.
- Cloud process log created and fetched back:
  https://modelbest.feishu.cn/docx/ChoXdLBeXorjGyxUK75cWylPn4d

## 2026-10-27 01:28 Snapshot (Asia/Shanghai)

- PilotDeck Default completed: real18executions, one proposal, select2/3 to3/3,
  audit3/3 each, NEEDS_REVIEW. The model returned prose plus a fenced Skill;
  this early candidate was read as task context, not yet validated as a native
  loadable Skill. Native candidate packaging is being corrected before release.
- Mint OPRO v3 completed: real15executions, one proposal, select3/3 ties3/3,
  baseline audit3/3; NO_IMPROVEMENT retains baseline, candidate audit not run.
- Mint Seatbelt wrapper passed17exact-policy checks and a real native
  skill_read/fs_write probe. Model proxy contains provider credentials;
  evaluated process receives none, reads workspace only, connects only proxy.
- First isolated experiment failed because Mint nested sandbox could not start.
  Trusted local user config disables only the inner policy; outer policy stays
  unchanged. Scripted native shell and all17outer probes then passed.
- Second isolated experiment ran18executions; candidate select3/3 vs2/3,
  baseline audit3/3. Last candidate audit failed upstream; no decision or release.
  Both failures retained. Proposal frontmatter parsing/native loading must be
  fixed and a new experiment run before operator approval can occur.
- Independent review fixed distinct recall-only runtime auth, runtime installer
  refusing control-project conversion, Gateway result_unknown preservation,
  secret-bearing baseline rejection, executable/Skill startup checks, and HTTPS
  outside loopback for proposal model URLs. Public-case byte preservation fix
  still in progress. Latest service suite before last fixes297passed.
- Sdist rebuild initially failed external benchmark paths. Custom build hook
  now supports checkout and unpacked sdist; rebuilt wheel clean-installed with
  both host imports, ledger9/workflow6 and license verified outside source cwd.
- Post-auth native stable PilotDeck loader/McpClient10checks pass; Mint actual
  runtime bridge/Skill scripted consumption passes with distinct runtime token.
- Viewer at http://127.0.0.1:18935 displays saved evidence, explicitly replay.
  Existing26second video and desktop/mobile screenshots will be refreshed after
  lifecycle verification. Cloud process update written and fetched revision4.

## 2026-10-27 01:50 Snapshot (Asia/Shanghai)

- Final native-Skill/parser fixes preserve public benchmark bytes and accepted
  candidate content. Configured credentials are rejected before raw CAS storage.
  Raw proposal is retained separately; JSON literal whitespace compatibility is
  tracked as learner.extraction.mode. Failed v3 remains failed in the archive.
- Full regression402passed/1Starlette warning; Node13passed; shared Skill render
  matched. Sdist-to-wheel build and a fresh wheel-only installation outside the
  checkout passed all adapter imports, ledger9/workflow6 and license checks.
- Post-auth real model plugin probes both completed: PilotDeck6native/MCP tool
  calls successful, Mint4successful. Native loader10checks and scripted runtime
  probe remain separately labeled.
- Isolated Mint Default v4 completed18real executions plus1real proposal:
  baseline construct3/3/select2/3/audit2/3; candidate3/3each. NEEDS_REVIEW,
  insufficient evidence, explicitly seeded negative-control baseline.
- Disposable lifecycle15steps passed: operator apply; exact native candidate
  body read and score1smoke on Mint/PilotDeck; role/expiry/replay/conflict denial;
  restart persistence; rollback hashes and both native baseline reads.
  Rollback task scores Mint0/PilotDeck1 are retained. Second-run admission,
  lineage and cancellation uses an explicitly marked PausedHost fixture.
- The core ledger keeps loaded=unverified. External native reads and behavior
  evidence do not rewrite it. No production project was published.
- Same frozen baseline/candidate PilotDeck18-case replay is running; no new
  proposal or publication. Final media recapture and cloud archive follow.

## 2026-10-27 02:25 Snapshot (Asia/Shanghai)

- Final Python gate434passed/1Starlette warning33.29s; Node16passed and shared
  Skill equality passed. Drift tests reproduced14failures before the fix;
  sixteen cases now cover execution, verifier, proposal, decision, approve,
  apply and recovery. Only observable frozen descriptions are checked.
- Same frozen PilotDeck comparison completed18executions, both assets scored
  3/3 on each split, unscored0/missing0. No observed improvement. Original
  execution source and final read-only preflight are both retained.
- Genuine OPRO second round run-59835b6f8be948d1a0a4cae2a4814612 completed:
  9real executions, one proposal, exact duplicate content, no new candidate
  version, NO_IMPROVEMENT. Baseline3/3each; parent lineage matched the reapplied
  v4 candidate. Scoped rollback restored original402cd145... baseline hash.
- Fresh final sdist-to-wheel build installed33dependencies offline in a new
  venv. Public installed CLI check/serve/readiness/authenticated API passed
  from external cwd; one genuine PilotDeck task scored1.0 and the explicit
  one-execution budget stopped before proposals. Test service stopped cleanly.
- Architecture, research and case-catalog cloud docs created and fetched back.
  Final media capture, archive checks and cloud artifact index are in progress.
  P0 functional acceptance is recorded in acceptance.md; AgentOS Kernel and
  official benchmark runs remain outside implemented first-release scope.

## 2026-10-27 02:30 Freeze (Asia/Shanghai)

- Strict select-regression and audit-regression publication rejection now have
  explicit new-control tests. Final Python436passed/1warning34.33s, Node16passed.
- Final viewer contains10records/85approvedfiles/0warnings at18935. Videos are
  39.72s and21.96s saved-event replays;32screenshots/layout checks,0browser
  errors and0externalrequests. Five exact private values across61files/API
  had no matches. All desktop/mobile views and video frames were inspected.
- Installed-wheel Python modules match90final source modules exactly. Local
  service restarted on18934with final code; private configuration remains local.
- Source freeze and credential-checked archive/upload follow. Functional gate
  status: full pass within acceptance.md's explicit first-release scope.

## 2026-10-27 02:36 Handoff (Asia/Shanghai)

- Committed clean product revision a9e536fc1bba53d287e6d75cce32600b0daadffc.
- Packaged source, full-history Git bundle, wheel/sdist, manifest and checksums;
  153selected evidence files,5knownprivatevalues scanned with0matches.
- All9artifacts uploaded to the requested folder; metadata requery passed.
  Folder listing needs an unavailable scope; no directory-list proof claimed.
  Evidence zip downloaded back and SHA256matched exactly.
- Final index: https://modelbest.feishu.cn/docx/CWQ3dKJ0xoui54xKn4BcpL4xncC
  Process doc revision6was appended. Separate architecture/research/case/
  acceptance docs and both videos are linked in that index.
- Parent handoff files record cloud completion after the source artifact freeze;
  product source snapshot intentionally retains its pre-upload progress stage.
