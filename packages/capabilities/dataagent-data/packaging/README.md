# packaging

| 文件 | 用途 |
|-|-|
| `catalog-snapshot.json` | 供检查的 Catalog 镜像；运行时使用 `src/dataagent_data/catalog-snapshot.json`（wheel 内可寻址） |
| `source-ref.toml` | 上游仓库、Catalog digest、包版本与运行时基线 |
| `bundle/` | `scripts/build_bundle.py` 生成的自包含 staging（不提交） |

## 为什么需要 staging

`dataagent-data` 在仓库内以 `path = "../dataagent-contracts"` 依赖契约包，便于联动开发。Mint bundle 会被解压成**一个目录**，兄弟路径不存在，因此发布前必须：

```bash
uv run python scripts/build_bundle.py          # 生成 packaging/bundle，vendoring contracts 并重写 pyproject
cd packaging/bundle
mint publish --dry-run                         # 或 mint publish
```

`build_bundle.py` 会：

1. 复制数据层与契约包源码到 staging；
2. 把 `pyproject.toml` 改为只依赖 PyPI 包（`pydantic`、`openpyxl`、`pdfplumber`），wheel 同时包含 `dataagent_data` 与 `dataagent_contracts`；
3. 跑 `uv lock`，固定依赖版本（可复现）；离线运行仍需本机 `uv` 缓存或预拉取依赖，`--frozen` 只禁止改锁文件；
4. 带上 `mint.toml`、`.mcp.json`、Skills 与打包快照。

> 在 staging 里跑过 `uv run` 后会生成 `.venv/`；Mint 打包会拒绝符号链接，发布前删除：`rm -rf packaging/bundle/.venv`。

发布前一致性门：

```bash
uv run python scripts/export_catalog_snapshot.py --check
uv run pytest
```
