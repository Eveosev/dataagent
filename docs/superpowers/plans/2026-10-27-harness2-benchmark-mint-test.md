# Harness2 Benchmark Mint Test Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 接入 Job-Bench 与 WorkBuddy-Bench 的本地可复现 benchmark preparation/run manifests，使用多个 Mint CLI 实例执行受控测试，并把完整证据同步到飞书文档。

**Architecture:** 两个 benchmark 各自负责读取本机数据、冻结版本/哈希、生成 task manifest 和结果记录；共享 RSI/Mint runner 只消费统一的 manifest，不把第三方数据复制进发布包。Mint 测试使用独立 disposable project、Mint home、端口和 evidence 目录并行运行，统一保存命令、环境、日志、摘要和 credential scan。

**Tech Stack:** Python 3.13, existing RSI Toolkit service, Mint CLI 0.1.10/Core 0.1.6, parquet/tarfile/hashlib, JSONL evidence, lark-cli/Feishu document API.

**Spec:** `docs/dev/rsi_toolkit/benchmark-brief.md`, `apps/plugins/rsi-toolkit/docs/design/benchmark-gap-analysis.md`, Harness2 `docs/BENCHMARKS.md` (Job-Bench and WorkBuddy-Bench).

## Global Constraints

- 数据源仅读取 `/Users/payne/Datasets/job-bench` 和 `/Users/payne/Datasets/workbuddy-bench`，不把原始第三方数据复制到产品发布包。
- 官方 benchmark、本地准备、Mint smoke、模型真实得分必须分开标注。
- 所有运行必须记录代码版本、数据哈希、Mint/服务版本、命令、配置、耗时和失败分类。
- 任何未运行或未完成的任务使用 `unscored`，不填充虚构零分。
- 证据目录和飞书内容必须经过凭据扫描。

## Review Focus

- Parquet/tar 数据结构变化：索引器应给出明确 schema 错误。
- 归档校验失败：SHA256 不一致时必须阻止运行。
- Docker/GUI 不可用：准备阶段可完成，执行阶段应记录 infrastructure/unscored。
- 多 Mint 实例相互污染：每个实例必须拥有独立 HOME/MINT_HOME/project/port/evidence。
- 结果缺字段或模型未执行：报告中不能把准备结果冒充 benchmark 分数。

### Task 1: Job-Bench local adapter

**Files:** `service/benches/jobbench/`, `conformance/benchmark/jobbench*`, `docs/benchmarks/jobbench*`

- [ ] 读取 `tasks.parquet`/`easy.parquet`，生成冻结 task manifest、split 计数和 SHA256。
- [ ] 提供 `--dataset-root`, `--split`, `--limit`, `--output` 命令；输出 JSONL/JSON summary。
- [ ] 对缺失列、不存在的 task 文件、重复 task_id 和无效 rubric 失败。
- [ ] 用本机数据测试索引和 deterministic rerun。

### Task 2: WorkBuddy-Bench local adapter

**Files:** `service/benches/workbuddy/`, `conformance/benchmark/workbuddy*`, `docs/benchmarks/workbuddy*`

- [ ] 校验 `SHA256SUMS` 并读取四个 tar.gz 的 dataset.toml/task.toml/instruction.md 元数据。
- [ ] 提供 `--dataset-root`, `--subset`, `--limit`, `--output` 命令；输出归档哈希、task 计数和 task manifest。
- [ ] 对 checksum/schema/任务目录缺失失败。
- [ ] 用本机数据测试索引和 deterministic rerun。

### Task 3: Unified Mint evidence runner

**Files:** `conformance/benchmark/run_mint_benchmarks.py`, `docs/benchmarks/mint-runbook.md`, `evidence/harness2/`

- [ ] 接受 benchmark manifest 和 disposable project/root 参数，生成不含凭据的 run manifest。
- [ ] 为每个实例使用独立 `MINT_HOME`, `HOME`, project, service port, output directory。
- [ ] 支持 `--prepare-only`（默认）和显式 `--execute`；执行失败分类为 infrastructure/unscored。
- [ ] 可并行启动两个 Mint CLI 子进程并保留 stdout/stderr/exit code/versions。
- [ ] 运行 credential scan 和 manifest self-check。

### Task 4: Report and Feishu synchronization

**Files:** `docs/benchmarks/harness2-mint-report.md`, `docs/dev/rsi_toolkit/harness2-benchmark-report.md`, optional `scripts/publish_feishu_harness2.py`

- [ ] 汇总 Job-Bench、WorkBuddy-Bench、Mint smoke 和差距。
- [ ] 记录每条复现命令、路径、哈希、结果和未完成原因。
- [ ] 使用 lark-cli 在用户指定云盘位置创建/更新飞书文档；上传证据目录或链接。
- [ ] 飞书内容与本地报告一致，完成后再报告 URL。

## Acceptance

- [ ] 两个 adapter 定向测试通过。
- [ ] 两个 benchmark 在本机数据上生成稳定 manifest。
- [ ] 至少两个隔离 Mint CLI 实例完成 prepare/smoke，日志和版本可复现。
- [ ] 真实模型或 Docker 未运行时明确记录为 unscored/prepare-only。
- [ ] 本地报告和飞书文档包含相同的 commit/hash/命令/结果。
