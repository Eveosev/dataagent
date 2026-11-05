# dataagent-cli

统一 CLI 分发器包（`dataagent/cli`，`kind=bundle`，12-unified-cli-research §5.1）。

- `bin/dataagent`：POSIX sh 分发器，无 Python 依赖、无 `.mcp.json`。
  - `dataagent <data|app|gov> ...` → 定位 `<项目>/.mint/packages/dataagent/<layer>-layer@<ver>/`
    （`mint.lock` 版本优先，缺省取最高），exec `<包>/.venv/bin/python -m dataagent_<layer>.interfaces.cli`；
    exec 前按白名单清洗环境变量（§5.4，凭据不进入层进程）。
  - `dataagent link`：项目根生成自包含 `./dataagent`（供 `allow_prefixes` 与 Skill 引用）。
  - `dataagent setup`：对三层包 `uv sync --frozen`。
  - `dataagent doctor`：检查三层包、`.venv`、策略、data_root、执行模式；缺失退 3。
- `skills/dataagent-cli/SKILL.md`：Agent 用法。
- 三层不在一个进程加载（治理层锁 `duckdb<2`、`sqlglot<27`；应用层锁 duckdb 2.0.0、
  sqlglot 30.29），所以按层分发而不是合并入口。

依赖：`dataagent/{data,application,governance}-layer` 三个兄弟包（preset-s0 已带）。
本包本身零依赖；层内 `.venv` 由 MCP 首次拉起或 `dataagent setup` 建立（§5.2 方案 A）。

## 测试

`python3 -m unittest discover -s tests`（stdlib only）在临时 mint 布局上验证分发、
`link`、环境清洗与退出码。
