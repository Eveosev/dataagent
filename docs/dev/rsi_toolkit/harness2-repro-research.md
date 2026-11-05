# Harness2 关联 benchmark：可复现链路与本地数据核验

日期：2026-10-27（Asia/Shanghai）  
范围：JobBench 与 WorkBuddy-Bench；只做来源、schema、verifier、运行条件和 Mint CLI 复现设计。  
本页没有把第三方数据复制到产品目录，也没有声称已经跑出 Harness2 或模型分数。

## 1. 证据边界

Harness2 参考版本固定为 `google-research/harness2` commit
`1cfe254e8d25b15f37048c3730134686abe60335`（现有项目研究记录中的
Harness2 0.1.0）。参考文档为：

- [Harness2 BENCHMARKS.md](https://github.com/google-research/harness2/blob/1cfe254e8d25b15f37048c3730134686abe60335/docs/BENCHMARKS.md)
- [Harness2 EXPERIMENTS.md](https://github.com/google-research/harness2/blob/1cfe254e8d25b15f37048c3730134686abe60335/docs/EXPERIMENTS.md)
- [Job-Bench/job-bench-eval](https://github.com/Job-Bench/job-bench-eval)
- [Tencent/workbuddy-bench](https://github.com/Tencent/workbuddy-bench)

本机本轮无法解析 `raw.githubusercontent.com`，因此没有重新下载远程
`BENCHMARKS.md`；上面的 Harness2 命令和评分语义来自项目已有的固定研究记录，
本地数据结构、版本和哈希由下面的只读检查得到。重新发布报告时应把远程文档
快照或固定 commit 一并保存。

当前环境的实际限制：

| 检查项 | 观察 | 影响 |
| --- | --- | --- |
| Mint CLI | `mint 0.1.10`（`/Users/payne/.mint/bin/mint`） | 可执行本地包安装和 headless smoke |
| Harness2 命令 | `harness2`、`harness2-setup`、`harness2-check`、`harness2-judge`、`harness2-report` 均不在 PATH | 不能把本轮 Mint smoke 当成 Harness2 正式成绩 |
| Docker | Docker CLI 存在；访问 `/Users/payne/.docker/run/docker.sock` 返回 permission denied | WorkBuddy 需要容器，当前主机只能完成数据准备或记录 infrastructure/unscored |
| JobBench 数据 | 已下载完整仓库，含 `dataset/`、`dataset_easy/` 和两个 Parquet | 可做本地索引、哈希、schema 和 Mint prepare-only |
| WorkBuddy 数据 | 四个 v1.0 tar.gz 与 `SHA256SUMS` 已下载 | 可校验归档和读取 task metadata；不能绕过 Docker 直接声称执行 |

## 2. 本地数据冻结

### 2.1 JobBench

路径：`/Users/payne/Datasets/job-bench`。仓库当前 `main` 与
`origin/main` 一致，commit 为 `d43a66575635da0d3f6cb9a20976dc1a60f3ffc9`。

| 文件/目录 | 事实 |
| --- | --- |
| `tasks.parquet` | 65 行，SHA-256 `985f5581f665e73bd4a3e21441219e5ebf306ed99a457c8f66880b71ede05f78` |
| `easy.parquet` | 63 行，SHA-256 `0cae350c6df420bc26beceb1c24071b52c02af11221ca5a4c3ee82ccad2bde70` |
| `dataset/` | 35 个 occupation 目录、65 个 task 目录；main split |
| `dataset_easy/` | 35 个 occupation 目录、63 个 task 目录；easy split |
| README | SHA-256 `6793a68d3dac7c0deccd174a85d724e614706049f7579aaac9efe86da79be291` |

任务目录结构：

```text
<split-folder>/<occupation>/taskN/
├── RUBRICS.json
├── task_card.md
├── task_folder/
│   ├── TASK_INSTRUCTIONS.txt
│   └── starter files ...
└── files_required_to_search/       # main only
```

两个 Parquet split 共享列：

| 列 | 含义 | 运行时用途 |
| --- | --- | --- |
| `task_id` | `<occupation>__taskN` | 稳定 task identity；报告中保留 |
| `occupation` | 职业目录名 | domain/分层统计 |
| `task_num` | 职业内序号 | 目录与索引一致性检查 |
| `prompt` | `TASK_INSTRUCTIONS.txt` 内容 | 交给 agent 的公开任务输入 |
| `reference_files` | `task_folder/` 起始文件列表 | 构造任务 workspace |
| `reference_file_urls` | Hugging Face 文件 URL | 来源追踪，不在受限执行时联网 |
| `reference_file_hf_uris` | `hf://datasets/...` URI | 来源追踪 |
| `rubric_json` | `RUBRICS.json` 原文 | judge 输入；必须与 agent evidence 隔离 |
| `task_card` | `task_card.md` 原文 | 任务说明/审计，不应误当 hidden label |

`main` 的额外 `files_required_to_search/` 是任务要求 agent 通过搜索发现的资料；
`easy` 没有该目录。两个 split 使用相同 occupation 与 `task1`/`task2`/`task3`
命名，但同一槽位的内容可能不同，不能按 `task_id` 做“easy 是 main 的简化版”
推断。

JobBench 的评分是 rubric 加权的专业任务评分；未完成或没有有效 judge 结果的
任务必须单独记为 `unscored`。它没有统一的文件输出 schema：每个 task 的
`TASK_INSTRUCTIONS.txt` 决定交付物（经常是 XLSX、DOCX、CSV 或报告），所以
RSI adapter 必须保存完整 task prompt、产物路径和 judge 输入，而不能只记录一
个文本答案。

### 2.2 WorkBuddy-Bench

路径：`/Users/payne/Datasets/workbuddy-bench`。仓库 `main` 与 `origin/main`
一致，commit 为 `3e8ad839685c589d83a1dd60fe2d15eabb75f27a`。

四个归档均通过根目录 `SHA256SUMS` 校验：

| subset | 归档 | task 数 | SHA-256 |
| --- | --- | ---: | --- |
| code | `wb-bench-code-v1.0.tar.gz` | 80 | `f60394e44341f45f66af17ba69efc51ceadc61f17c08aa89e4af35b51f6f34e1` |
| office | `wb-bench-office-v1.0.tar.gz` | 50 | `89d4480b483ca2e0555ba96cc7d73c16c78802b17cd822044d5f7f27ab0558bf` |
| security | `wb-bench-sec-v1.0.tar.gz` | 60 | `f615f55b2ce68294eca6bef658d3a135978ca1e7f00b8e712292a2738f79c3f3` |
| web | `wb-bench-web-v1.0.tar.gz` | 70 | `bf4e0258501a7007d547eeb5f3e9cfb7dd648feaaa4f3dbc23dbae87758e0b66` |

`SHA256SUMS` 本身的 SHA-256 为
`10bba6e880f70d3041aebb2248f35620a8a1d1227a7cb7e0e1c70d49f59fbf47`。

code/office/web 归档的共同任务布局为：

```text
wb-bench-<subset>-v1.0/
├── dataset.toml
├── shared/verifier/ ...
└── tasks/<task-id>/
    ├── instruction.md
    ├── task.toml
    ├── environment/
    │   ├── Dockerfile
    │   ├── docker-compose.yaml
    │   └── workspace.tar.gz
    └── tests/ ...
```

三个 subset 的 `dataset.toml` 都声明 `schema = "workbuddy.dataset.v1"`、
`version = "1.0"`，并使用 `workbuddy.verifier.v1` 的 `CompositeVerifier`。
任务 `task.toml` 的稳定字段包括 `task.name`、`metadata.category`、
`metadata.difficulty`、`metadata.complexity`（code/office/web 可能略有差异）、
`verifier.timeout_sec`、`agent.timeout_sec` 和容器资源。每次 rollout 应使用新
容器，workspace 由 `environment/workspace.tar.gz` 展开；结果由 verifier 读取并
写出 `score.json`。

security 是不同评分路径：它声明 task-native scorer，通常由
`tests/test.sh`/`scoring.py` 写 `reward.json`，verifier 网络为 no-network，agent
网络按 allowlist；不使用 WorkBuddy 的 LLM/diff judge。现有 Harness2 参考命令
只覆盖 office、web、code，不能把 security 归档直接塞入同一 runner 期待得到
可比结果。除非 Harness2 新版本明确支持 security，否则将 security 标为
`unsupported-by-harness2`。

## 3. Harness2 参考运行链路

以下命令是固定 commit 的 Harness2 文档链路，适用于有 Linux/Python 3.12、
Harbor/Docker、模型和凭据的专用 runner。当前 macOS 主机仅把它们作为复现模板；
没有安装 Harness2 时不得执行 `harness2-report` 作为本项目结果。

### 3.1 JobBench（Harness2 默认 main split）

```bash
# 在 Harness2 checkout 中，先完成项目自己的依赖安装
harness2-setup jb
harness2-check --bench jb

# 先 dry-run/小样本，再正式 refinement
harness2 --bench jb --k 1 --mode parallel --max-tasks 1 --dry-run
harness2 --bench jb --k 1 --mode parallel --max-tasks 1
harness2-judge --bench jb --k 1 --mode parallel
harness2-report --bench jb --k 1 --mode parallel
```

顺序模式只将 `--mode parallel` 换成 `--mode sequential`。Harness2 setup 默认
从 Hugging Face 下载 **main** 数据，并在
`dependencies/job-bench-eval/dataset/main/.harness2-download.json` 记录下载时
解析到的 revision；报告必须携带这个 revision。`easy` 是本地仓库提供的额外
smoke split，不是 Harness2 文档默认命令的隐式替代；若适配器支持 easy，必须
显式写入 manifest 的 `split = "easy"` 并单独统计。

JobBench 的 rubric 在 Hugging Face 公开可取。正式评估前应在执行器网络层阻断
`huggingface.co`、`hf.co`、`*.hf.co`，并保留阻断策略作为 evidence；不能只依赖
agent prompt 要求“不上网”。

### 3.2 WorkBuddy-Bench（Harness2 支持 office/web/code）

```bash
docker info
harness2-setup wb --subset office
harness2-check --bench wb --subset office
harness2 --bench wb --subset office --k 1 --mode parallel
harness2-judge --bench wb --subset office --k 1 --mode parallel
harness2-report --bench wb --subset office --k 1 --mode parallel
```

把 `office` 替换为 `web` 或 `code` 可分别运行；不指定 subset 的 setup 会一次
安装这三个 subset。WorkBuddy setup 会安装 pinned Harbor runtime、adapter、
mount/credential/transport patch，按 `SHA256SUMS` 校验归档，再构建 harness
image。任务从 `task.toml` 与 `instruction.md` 发现，fresh container per
rollout；improver 不接收 verifier 输出，缺少 `score.json` 的任务保持
`unscored`。Codex 宿主若使用 Harness2 参考桥接，需另起：

```bash
harness2-bridge --host 0.0.0.0
```

WorkBuddy 数据仓库带 Tencent 特定 license，使用前必须在专用 runner 阅读上游
license；本地归档的 README 标记为 `license: other`/`license_name: tencent`。

### 3.3 不能横比的项目

| 维度 | JobBench | WorkBuddy-Bench | 结论 |
| --- | --- | --- | --- |
| 任务输入 | 职业 prompt + 可检索资料 +多格式交付物 | Docker workspace + repo/web/office/security 任务 | 不共享输入 schema |
| 评分 | occupation task 的加权 rubric，常由 judge 解释产物 | code/office/web CompositeVerifier；security task-native `reward.json` | 分数尺度和失败语义不同，不合并均值 |
| 执行 | 文档处理依赖，默认 main | 每 rollout 新 Docker/Harbor 容器；部分任务 public network | 宿主、网络和资源预算不同 |
| 递归 | Harness2 `k` 次 candidate/refinement | 同上，subset 还会改变任务域 | 比较时固定 `k`、mode、seed、executor、subset |
| 数据冻结 | setup 时解析 HF revision | 本地 v1.0 tar + SHA256SUMS | 版本字段不同，必须分别记录 |
| 奖励可见性 | rubric 公开，需阻断 HF | verifier 结果应只进 judge，improver 不可读 | 公开 rubric/网络会泄漏答案，不能只看分数 |
| 当前本机 | 可准备、可索引 | Docker socket 权限失败 | 本轮不能产生官方可比分数 |

## 4. Mint CLI 隔离运行模板

Mint CLI 本身不是 Harness2 judge。这里的目标是把 RSI Toolkit 的 `self-evolve`
Skill/MCP 入口以两个相互隔离的 Mint headless 进程跑 smoke，并将每次尝试写成
可审计 evidence。每个实例都必须拥有独立 `HOME`、`MINT_HOME`、Mint project、
服务端口和 evidence 目录；token 只通过父进程环境或私有临时文件注入，不能写入
manifest、prompt、stdout 或飞书。

```bash
set -euo pipefail

ROOT=/Users/payne/Vibe/AgentOS
PLUGIN="$ROOT/apps/plugins/rsi-toolkit"
MINT=/Users/payne/.mint/bin/mint
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
OUT=/private/tmp/rsi-harness2-mint/$STAMP
mkdir -p "$OUT"

run_mint_case() {
  id="$1"; benchmark="$2"; endpoint="$3"; port="$4"
  home="$OUT/$id/home"; project="$OUT/$id/project"; ev="$OUT/$id/evidence"
  mkdir -p "$home" "$ev"

  env HOME="$home" MINT_HOME="$home/.mint" \
    "$MINT" init "$project" --name "local/rsi-harness2-$id" --no-preset \
    >"$ev/init.stdout" 2>"$ev/init.stderr"
  (
    cd "$project"
    env HOME="$home" MINT_HOME="$home/.mint" "$MINT" add \
      "$PLUGIN/plugins/mint/rsi-toolkit" \
      >"$ev/add.stdout" 2>"$ev/add.stderr"
    env HOME="$home" MINT_HOME="$home/.mint" "$MINT" tree \
      >"$ev/tree.txt" 2>"$ev/tree.stderr"
    env HOME="$home" MINT_HOME="$home/.mint" \
      RSI_CONTROL_MCP_URL="$endpoint" RSI_AGENT_TOKEN="<inherited-secret>" \
      "$MINT" run --json --yes --approve none --max-steps 8 \
      "Use the self-evolve Skill. Run one $benchmark smoke case only. Record the final status and artifact path." \
      >"$ev/events.ndjson" 2>"$ev/run.stderr"
  )
  env HOME="$home" MINT_HOME="$home/.mint" "$MINT" --version >"$ev/mint.version"
  printf '%s\n' "$id $benchmark $port" >"$ev/instance.txt"
}

# Start the RSI service/bridge before these calls. Use distinct endpoint ports.
run_mint_case jobbench job-bench http://127.0.0.1:19100/mcp/control 19100 &
pid_job=$!
run_mint_case workbuddy workbuddy-office http://127.0.0.1:19101/mcp/control 19101 &
pid_wb=$!
wait "$pid_job"; wait "$pid_wb"
```

`RSI_AGENT_TOKEN="<inherited-secret>"` 是模板占位符，真实运行时通过未落盘的
环境继承或权限为 0600 的临时文件读取；证据只记录变量名和 token fingerprint。
两个 benchmark 的任务 manifest 也要分别生成，不能让一个 Mint project 同时读
JobBench rubric 和 WorkBuddy tests。

Mint 事件流用 `--json` 输出 NDJSON，最后一行应为 `done`。检查至少包括：

```bash
tail -n 1 "$OUT/jobbench/evidence/events.ndjson"
tail -n 1 "$OUT/workbuddy/evidence/events.ndjson"
```

缺 `done`、进程非零退出、MCP transport 断流或服务不可用均归为
`unscored`/`infrastructure`，不能降级为任务失败 0 分。

## 5. Evidence schema

每个实例必须至少保存以下文件；路径均在独立 `OUT/<instance_id>/` 下。

```text
manifest.json          # 机器可读冻结输入与命令
dataset.json           # task ids、split/subset、来源和摘要 hash
mint.version
command.txt            # shell 逐字命令（secret 已替换）
init.stdout / *.stderr
events.ndjson           # Mint --json 原始事件流
result.json             # 归一化终态，不覆盖原始事件
sha256sums.txt
credential-scan.json
```

`manifest.json` 建议 schema：

```json
{
  "schema": "rsi.harness2.mint-evidence/v1",
  "run_id": "20261027T000000Z",
  "instance_id": "jobbench-main-001",
  "benchmark": "jobbench",
  "split_or_subset": "main",
  "task_ids": ["occupation__task1"],
  "dataset_root": "/Users/payne/Datasets/job-bench",
  "dataset_commit": "d43a66575635da0d3f6cb9a20976dc1a60f3ffc9",
  "dataset_hashes": {"tasks.parquet": "sha256:..."},
  "harness2_commit": "1cfe254e8d25b15f37048c3730134686abe60335",
  "mint_cli": "0.1.10",
  "mint_core": "record actual installed value",
  "project_root": "/private/tmp/.../project",
  "mint_home": "/private/tmp/.../home/.mint",
  "endpoint": {"host": "127.0.0.1", "port": 19100, "path": "/mcp/control"},
  "argv": ["mint", "run", "--json", "--yes", "--approve", "none"],
  "env_names": ["RSI_CONTROL_MCP_URL", "RSI_AGENT_TOKEN"],
  "started_at": "2026-10-27T00:00:00Z",
  "finished_at": "2026-10-27T00:00:00Z",
  "exit_code": 0,
  "terminal_event": "done",
  "status": "unscored",
  "score": null,
  "score_kind": "unscored",
  "verifier": "jobbench weighted rubric / pending judge",
  "network_policy": "record actual policy",
  "credential_scan": "passed",
  "reproduction": "command.txt"
}
```

状态枚举：

| `status` | 使用条件 |
| --- | --- |
| `completed` | 正常退出、终态事件完整、独立 verifier/judge 有分数 |
| `task_failed` | agent 正常执行且 verifier 明确判定任务失败 |
| `unscored` | 无 judge、无终态、取消、输出缺失或仅完成准备 |
| `infrastructure` | Docker/Harbor/服务/依赖不可用 |
| `transport` | MCP/NDJSON/bridge 断流或协议错误 |

`score = null` 是有意的：准备阶段、Mint smoke 或基础设施失败都不能填充虚构
零分。正式报告应同时保留任务总数、已评分数量、unscored 数量和覆盖率。

## 6. 报告与复核规则

1. 先发布 `dataset.json` 和 `manifest.json`，再启动 Mint；输入 hash 变更就新建
   `run_id`，不能覆盖旧 evidence。
2. baseline 和 RSI candidate 必须使用相同 task ids、模型、`k`、mode、seed、
   资源预算和网络策略；只比较配对 case，不能将 JobBench 与 WorkBuddy 的分数
   直接求平均。
3. JobBench 的 rubric、WorkBuddy 的 tests/ground truth 和 `score.json` 不进入
   `self-evolve` Skill 的 evidence；agent 只读公开任务输入与允许的工作区。
4. 每次发布到飞书的内容只上传脱敏摘要、命令、哈希、终态和结果链接；原始
   `events.ndjson` 若含用户文件或模型输出，应留在受控本地 evidence 目录。
5. 若执行器或 Docker 不满足条件，报告“prepare-only / unscored”，并附上失败
   命令和错误分类；不要以本地 synthetic ledger 或 WorkBuddy task metadata
   的读取成功替代官方 benchmark 分数。

