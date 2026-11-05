# r5 修复记录：r4-review 阻塞项处置

## 背景

r4 验收（[r4-review.md](r4-review.md)）判不可验收 79.0（C），两个闸门均源于同一根因：

- **GATE-P1（D10）**：`--set` 只认 schema 属性的字面 `type`（`unified.py:158` 原实现），`anyOf`（可选标量 `str | None` 等）与 `$ref`（`VersionedRef` 字符串形、枚举）标量一律拒为 "field is not a scalar"。独立探针统计 63 字段/30 ops，含 7 个必填字段（`check_access_scope.resource_ref` 等）。
- **GATE-CHECKLIST（`#ceedd2` partial）**：计划 W1 要求「`--set k=v`（按 schema 转换类型）」，上列字段不成立。

另有新 P2 **D11**（非闸门，一并修复）：r4 记录引用的 tag object `8544568c…` 是被重建取代的 unreachable 旧 tag，实际 ref 为 `20022e0a…`。

改动前快照：`/tmp/agentos-snapshots/pre-r5-20261106-035810.tar.gz`；改动后 `dataagent-runtime@sha256:de2beca17c0508e8b1057f248f7faf2a9ae95ade04de16903fbb7850b3c79b1b`（67 文件）。

## D10 fixed（P1 → 关闭，`#ceedd2` → done）

**方案**：类型判定从「读字面 `type`」升级为「解析 schema 结构」——新增 `_resolve_kind(prop, defs)`（`unified.py:164-209`）：

1. `$ref` → 在 `$defs` 内解析目标；字符串形模型（`VersionedRef`：`type: string` + pattern）与字符串枚举（`TraceEventType`：`enum` 全字符串）解析为 `string`，对象模型（`FileRef` 等）返回 None（仍拒，走 `--file`/`--ref`）；
2. `anyOf` → 递归各变体，忽略 `{"type": "null"}`；恰好一种标量类型则取之（`str | None` → `string`、`int | None` → `integer`、`bool | None` → `boolean`、`$ref | null` → 跟随 `$ref`）；数组/对象变体与其他类型混合 → None（拒绝）；
3. 无任何结构键（`type`/`enum`/`anyOf`/`$ref`/`items`/…）的属性（pydantic 对 `Any` 的渲染，带或不带 `title`/`default`）→ `string`（裸字符串是合法 JSON 值）；
4. 递归深度上限 8，防自引用循环。

`_coerce`（`--set`）与 `_op_help`（`--help` 参数表）统一改走 `_resolve_kind`：

- `--set`：解析出的标量类型照常转型（integer/number/boolean 转换、string 原样传给 pydantic——句柄/枚举校验由 `model_validate` 承接，非法值 exit 2 `schema error`）；
- `--help`：标量字段渲染实际类型（`<string>`/`<integer>`/`<boolean>`），不再显示 `<object>`/`<VersionedRef>`（review 给出的 P1 降级条件之一）；非标量字段仍显示 `$ref` 名（如 `<FileRef>`），与 `--file`/`--ref`/`--set-json` 的分工一致。

`_build_payload` 相应从收 `properties` 改为收整个 schema（属性 + `$defs`）；原 `_schema_properties` 收敛进调用点。

**测试**（`tests/test_unified_cli.py`，runtime 102 → 106 passed）：

- `test_run_set_resolves_anyof_and_ref_scalars`：一轮 6 字段（`resource_ref`/`delimiter`/`budget_rows`/`flag`/`event_type`/`note`）全部 `--set` 成功且值型正确；
- `test_run_set_ref_scalar_bad_value_is_usage_error`：`$ref` 字符串形标量的非法值（无 `@` 的句柄、非整数）→ exit 2；
- `test_run_set_still_rejects_non_scalar_anyof`：`anyOf [array, null]` 仍拒（`--set-json`）；
- `test_op_help_resolves_scalar_kinds`：help 显示 `<string>`/`<integer>`/`<boolean>`，无 `<VersionedRef>`。

**黑盒复现（review §8 两例）**：

```sh
# gov：必填 VersionedRef 字段
(cd packages/capabilities/dataagent-governance && .venv/bin/python -m dataagent_governance.interfaces.cli \
   policy apply <policy.json> && \
 DATAAGENT_HOST_SUBJECT_REF=user:alice DATAAGENT_HOST_PURPOSE=monthly_report \
 .venv/bin/python -m dataagent_governance.interfaces.cli run check_access_scope --set resource_ref='table@*')
# r4: exit 2 usage error → r5: exit 0，data.decision = ad:… allow（AccessDecision 铸出）

# data：anyOf 标量
(cd packages/capabilities/dataagent-data && .venv/bin/python -m dataagent_data.interfaces.cli \
   run parse_delimited_file --file sales.csv --set delimiter=,)
# r4: exit 2 → r5: exit 0，data.delimiter = ","，table 句柄正常返回
```

受影响面复测（按 review 探针方法，对三层每个无字面 `type` 的属性调 `_resolve_kind`）：**71 字段/33 ops** 现可 `--set`（data 45/17、app 19/12、gov 7/4，覆盖 review 统计的 63/30 全集及枚举联合）；其余（数组/对象/ref 模型）保持拒绝，属 `--file`/`--ref`/`--set-json` 的既有分工。7 个必填字段全部验证：模型级 `model_validate({name: "table:x@r1", …})` 通过，`check_access_scope.resource_ref` 端到端 exit 0。

## D11 fixed（P2 → 关闭）

`r4-fixes.md:17` 与 `r4-runtime.score.json` `hard_rules.R13` 的 tag object 由 `8544568c…` 更正为实际 ref **`20022e0a962ecd42fd575bd9b8872ca2f11c3f99`**，两处均带「r5 更正（r4-review D11）」标注保留审计痕迹（不静默改史）。基线本身未动：`git rev-parse dataagent-runtime-0.1.0` == `20022e0a…`，`^{commit}` == `fbe24d8`（未变）。本轮及后续记录一律以 `git rev-parse` 实测值为准。

## 其余缺陷（与前几轮处置一致，非本轮闸门）

- **D2 partial**：CC>10 LOC 占比 25.77% → 26.56%（新增 `_resolve_kind` CC=17 的分支；CC>25 仍 0.0%，A5.2 达标）。A5.1 的存量组合复杂度留待后续轮。
- **D3 open**：默认超时/在途取消属方案范围外（12 方案 W1 未含超时项），维持 open。

## 分发同步

- 四包 vendored `unified.py` 字节同步（runtime/data/application/governance 的 `packaging/bundle`，`diff -rq` 全一致）；runtime `test_bundle_sync` 2 passed，三层全量测试通过即含各自的 bundle 一致性门禁。

## 复跑命令与结果

```sh
cd /Users/payne/Vibe/AgentOS
(cd packages/capabilities/dataagent-runtime && .venv/bin/python -m pytest -p no:warnings)      # 106 passed（+4）
(cd packages/capabilities/dataagent-data && .venv/bin/python -m pytest -p no:warnings)         # 654 passed
(cd packages/capabilities/dataagent-application && .venv/bin/python -m pytest -p no:warnings)  # 203 passed
(cd packages/capabilities/dataagent-governance && .venv/bin/python -m pytest -p no:warnings)   # 123 passed
(cd packages/capabilities/dataagent-cli && python3 -m unittest discover -s tests)              # 12 OK
python3 skills/code-landing-quality/scripts/quality_run.py --repo . \
  --package packages/capabilities/dataagent-runtime \
  --fill docs/research/dataagent-2026-11-03/12-cli-build/r5-runtime.score.json \
  --out    docs/research/dataagent-2026-11-03/12-cli-build/r5-runtime.quality.md
# 测试 106/0/0；重复率 2.17%（53/2447）；吞错 0/0；CC>10 26.56%、CC>25 0.0%；bundle 一致
(cd packages/capabilities/dataagent-runtime && uv lock --check && uv build -o /tmp/da-runtime-dist-r5)
# lock rc=0（Resolved 13）；wheel 22→19 个 .py 含 interfaces/unified.py，0 .pyc
python3 skills/code-landing-quality/scripts/score_landing.py \
  --result docs/research/dataagent-2026-11-03/12-cli-build/r5-runtime.score.json
# 总分 93.1 / 100，A 可交付，可验收；闸门：无（D10 fixed、#ceedd2 done、D11 fixed）
python3 skills/code-landing-quality/scripts/round_diff.py \
  docs/research/dataagent-2026-11-03/12-cli-build/r4-tester-runtime.score.json \
  docs/research/dataagent-2026-11-03/12-cli-build/r5-runtime.score.json
# 79(C, GATE-P1+GATE-CHECKLIST) → 93.1(A, 无闸门)；D10/D11 open→fixed；L2.1/L6.2 0→1；无退化、无未复核
```

## 遗留

- D2（CC>10 占比）partial、D3（默认超时）open，均 P2 非闸门，留待后续轮（处置同 r2–r4）。
- 基线 tag 仍仅本地（无 remote/制品库），owner 2026-11-06 批准的路径；后续破坏性 API 变更须升 major。
