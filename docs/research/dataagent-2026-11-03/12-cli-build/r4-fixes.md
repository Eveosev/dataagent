# r4 修复记录：R13 基线建立（owner 批准）

## 背景

r2/r3 的唯一验收闸门是 **GATE-UNKNOWN（R13）**：仓库无已发布基线，按 [code-landing-rubric.md](../../standards/code-landing-rubric.md):279 恒记 unknown。r3 结束时开发者提交 owner 决策请求，两条清除路径：① 发布基线制品（Mint Hub 发布或初始化 git 仓库并打 tag）；② 标准 owner 出具带日期硬规则豁免。

**owner 于 2026-11-06 批准**（团队线程原文 "Approved"）。本走 ① 的 git 变体：Mint Hub 发布无本地 `publish` 命令且属方案范围外 Q3，git init + tag 可在本地完整执行并留下可复核证据。

## 本轮变更（产品代码零改动）

`dataagent-runtime` 快照与 r3 逐字节一致：`sha256:78c93a64776a5dbc4ad45fd9c3f9f849d5d105b300f08179445fcaa2f9e1f400`（67 文件，`snapshot.py` 复算）。

1. **初始化 git 仓库**（`/Users/payne/Vibe/AgentOS`，主分支 `main`，此前非 git 仓库）：
   - 新增根 `.gitignore`：只排除易变/生成/超大目录（`workspace/`、`scratch/`、`evidence/`、`.worktrees/`、`.venv/`、`node_modules/`、`__pycache__/`、`.mint/`、`.DS_Store` 等）；源码、docs、skills、apps、integrations 等全部入库。
   - 嵌套仓库（`packages/agent-kernel`、`apps/plugins/*`）以 gitlink 记录其 HEAD。
2. **基线 commit `fbe24d8f4263513a711fc96126ded588b9650f2c`**（11,785 个暂存路径）。
3. **标注 tag `dataagent-runtime-0.1.0`**：指向上述 commit，tag object `20022e0a962ecd42fd575bd9b8872ca2f11c3f99`（r5 更正，r4-review D11：本行原文误写 `8544568c…`——那是 03:42:32 创建、03:42:38 被重建取代的 unreachable 旧 tag，记录未同步）；tag message 记录 owner 批准、r3 快照 digest、R13 语义（自本 tag 起破坏性 API 变更必须升 major）。`git cat-file tag dataagent-runtime-0.1.0` 可复核。
4. **记录提交**：本目录 r4 记录 + 方案记录表 r4 行（tag 之后的第二个 commit，不影响 tag 指向）。

## R13 判 green 的证据链

- 基线存在：git tag `dataagent-runtime-0.1.0` → commit `fbe24d8`，tag 内 runtime 源码快照与 r3 验收态一致。
- semver 检查：本轮（r1–r3）相对 pre-CLI 状态（`/tmp/agentos-snapshots/pre-cli-20261106-013324.tar.gz`，r1 记录在案）**无破坏性变更**——旧 stdin JSON 模式与 `--list` 旧 JSON 输出保留，由 `dataagent-data/tests/test_interfaces.py::test_cli_success_and_failure` 等锁定（本轮复跑 16 passed，含 `--list` 32 ops）；新 argv 语法为增量。包版本维持 0.1.0 且从未发布，无「同版本不同制品」问题（r2 实跑 `uv build` 产 0.1.0 wheel）。

## 复跑命令

```sh
cd /Users/payne/Vibe/AgentOS
git cat-file tag dataagent-runtime-0.1.0            # 基线 tag 及其 message
git rev-parse dataagent-runtime-0.1.0^{commit}      # fbe24d8f4263513a711fc96126ded588b9650f2c
python3 skills/code-landing-quality/scripts/snapshot.py packages/capabilities/dataagent-runtime
# → dataagent-runtime sha256:78c93a64… 67 files（与 r3 一致）
(cd packages/capabilities/dataagent-runtime && .venv/bin/python -m pytest -p no:warnings)   # 102 passed
(cd packages/capabilities/dataagent-data && .venv/bin/python -m pytest tests/test_interfaces.py -p no:warnings)  # 16 passed（旧 wire 形状锁定）
python3 skills/code-landing-quality/scripts/score_landing.py --result docs/research/dataagent-2026-11-03/12-cli-build/r4-runtime.score.json
# 总分 93.1 / 100，A 可交付，可验收，无闸门；R13 green
```

## 遗留

- D2（CC>10 占比 25.68% > 7.3%）、D3（默认超时/在途取消）仍为 P2 未关闭，不影响闸门，留待后续轮。
- Mint Hub 正式发布（`dataagent/runtime` 包）仍属方案范围外 Q3；git tag 基线已满足 R13 对「已发布基线」的要求，Q3 发布后可再以 Hub 制品为准。
