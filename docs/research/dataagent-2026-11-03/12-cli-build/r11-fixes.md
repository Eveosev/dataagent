---
round: r11
date: 2026-11-06
subject: D16 撤销：分发器不再解析 mint.lock
base: 3783d6b
kernel: agent-kernel@9602612626aaf8a6fedf5b2fcf99e09143df7ab8（fetch 后 behind=0；`sync-iface-packages.sh --check` 报漂移，本轮只引用 Mint 安装逻辑）
---

# r11 修复：D16 撤销

## 决定

D16（`mint.lock` pin 解析）撤销，不再作为缺陷跟踪。分发器按“每层唯一已装版本”定位层包。

| 依据 | 位置 |
|-|-|
| Mint 在改写锁的命令后删除与锁不一致的已装版本：`keep = lock_find(…).is_some_and(\|p\| p.version == inst.version)`，否则 `remove_dir_all` | `agent-kernel/mint/bins/mint/src/install.rs:970-980` |
| 调用点：add、remove、sync | `agent-kernel/mint/bins/mint/src/cmd/add.rs:334`、`:455`、`:514` |

Mint 管理的项目中每层只有一个版本目录，即锁定版本；解析 `mint.lock` 得到的版本与该目录一致。r6–r10 的 D16 修复（`bin/dataagent:94-569` 约 475 行 awk TOML 扫描器）对应的场景由 Mint 保证。

## 改动

| 文件 | 改动 |
|-|-|
| `packages/capabilities/dataagent-cli/bin/dataagent` | 删除 `pinned_version`、`pin_status`；新增 `installed_dirs`、`count_lines`；`resolve_dir` 与 `doctor_cmd` 按已装目录数判断；781 → 239 行 |
| `packages/capabilities/dataagent-cli/tests/test_dispatcher.py` | 删除锁解析用例 43 个（含 `LockDifferentialTests`、`RealMintLockDifferentialTests`）；新增 6 个；保留 11 个 |
| `packages/capabilities/dataagent-cli/README.md` | 版本定位说明 |
| `12-unified-cli-build-plan.md` | W3 版本定位说明；记录表 r11 行 |
| `12-unified-cli-research.md` | §5.1 分发规则 |

版本定位规则：

| 已装版本目录数 | 分发 | doctor |
|-|-|-|
| 1 | exec 该目录 `.venv/bin/python` | `package  dataagent/<pkg>: <dir>` |
| 0 | exit 3 `package dataagent/<pkg> is not installed` | exit 3 `MISSING` |
| >1 | exit 3 `<n> installed versions; run \`mint sync\``，不执行层进程 | exit 3 `<n> installed versions (run: mint sync)`；治理层多版本时跳过策略探针 |

`mint.lock` 的内容（含无法解析的锁）不影响分发。

## 验证

| 检查 | 结果 |
|-|-|
| `sh -n bin/dataagent` | 通过 |
| `python3 -I -m unittest discover -s tests`（`packages/capabilities/dataagent-cli`） | 21 个，通过（2 个真实 Mint 安装用例跳过，与 r10 相同） |
| 真实三层 `.venv`（临时布局，层包为符号链接） | `/bin/sh`、`/bin/dash` 下 `data list` exit 0 / 32 行，`doctor` exit 0；data-layer 两个版本时分发 exit 3、doctor exit 3；`gov run check_access_scope --set resource_ref=file@*` 后 `data run parse_delimited_file --file orders.csv --authorize` exit 0、`row_count=4` |

新增用例：

| 用例 | 断言 |
|-|-|
| `test_single_installed_version_is_used_without_reading_lock` | 锁写 0.9.9、已装 0.1.0 → exit 0，执行 0.1.0 |
| `test_unparseable_lock_is_ignored` | 锁内容非法 → exit 0 |
| `test_multiple_installed_versions_exit_3` | 两个版本 → exit 3，提示 `mint sync`，层进程未执行 |
| `test_layer_not_installed_exits_3` | 目标层未装 → exit 3 |
| `test_doctor_multiple_versions_exits_3` | doctor 报多版本，其它层照常检查 |
| `test_doctor_multiple_governance_versions_skips_policy_probe` | 治理层多版本 → 策略探针不运行，报 unavailable |

## 未处理

D2（复杂度）、D3（无默认 deadline）维持原状态。
