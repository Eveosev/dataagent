---
name: dataagent-cli
description: 用统一 `dataagent` CLI 调用 DataAgent 三层能力（数据/应用/治理）时使用：list 看原子清单、run 加 --set/--file/--ref 调用、--authorize 取访问判定、gov confirm 与 policy apply 管理判据与策略。
---

# DataAgent 统一 CLI

三条通道（data/app/gov）经同一个 `dataagent` 命令进入；输出是摘要 JSON，全文在
`.dataagent/results/<invocation_id>.json`。安装后先 `dataagent link` 生成稳定的
`./dataagent`，再按下面用法调用。

## 常用命令

| 命令 | 作用 |
|-|-|
| `./dataagent doctor` | 检查三层包、`.venv`、策略、data_root、执行模式；缺失退 3 |
| `./dataagent setup` | 对三层包执行 `uv sync --frozen` 建 `.venv` |
| `./dataagent <layer> list` | 每个 op 一行：名称、能力编号、是否复检、是否两段式 |
| `./dataagent <layer> run <op> ...` | 调用原子 |
| `./dataagent <layer> <op> --help` | 扁平参数表 |

`<layer>` ∈ `data` / `app` / `gov`，op 名与 MCP 工具名相同。

## 参数（全部经 argv，不用管道或重定向）

| 参数 | 含义 |
|-|-|
| `--input-file <path>` | 完整输入对象（JSON） |
| `--set k=v` | 单字段，标量按 schema 转换类型 |
| `--set-json k=<json>` | 单字段 JSON（对象、数组、引用） |
| `--file <path>` | 由文件字节生成 FileRef 填入文件入参 |
| `--ref <field>=<id@revision>` | 用此前结果的句柄填引用入参 |
| `--proposal-file <path>` | 两段式第二阶段提案（JSON） |
| `--authorize` | 取最近的 allow AccessDecision 填 `authorization_ref` |
| `--detail full` | 直接输出全文（默认摘要） |

## 输出与退出码

- stdout 摘要：`status`、`issues`、`data`（关键输出）、`handles`（新对象 `id@revision`）、
  `result_path`；`needs_input` 时附 `inference_request` 与 `next_command`。
- 全文：`.dataagent/results/<invocation_id>.json`；输入快照在 `<id>.input.json`。
- 退出码：0 = ok/partial/needs_input；1 = failed；2 = 用法或 schema 错误；3 = 环境缺失。

## 典型链路

```sh
./dataagent data list
./dataagent data run parse_delimited_file --file orders.csv --authorize
./dataagent data run profile_table_structure --ref table_ref=<id@rev>
./dataagent gov run check_access_scope --set-json resource_ref='{"id":"file:*","revision":"*"}'
./dataagent gov policy apply policy.json
./dataagent gov confirm criteria.json
```

主体与用途只由宿主在 `mint run` 时设置（`DATAAGENT_HOST_SUBJECT_REF` /
`DATAAGENT_HOST_PURPOSE`），不接受参数传入。不要用 `env VAR=... ./dataagent ...`
的形式绕过：带 `env` 前缀的命令不会命中 `allow_prefixes` 免审批。
