# packaging

- `catalog-snapshot.json`：由 `scripts/export_catalog_snapshot.py` 从权威
  Catalog 导出的 6 个 S0 原子快照（id / operation / source_file），供
  注册表门禁校验；`--check` 可校验是否过期。
- `source-ref.toml`：来源快照（上游、Catalog 与两个包的版本）。
- `bundle/`：`scripts/build_bundle.py` 产出的自包含 Mint bundle，内嵌
  contracts + runtime + governance 三个 src 树。
