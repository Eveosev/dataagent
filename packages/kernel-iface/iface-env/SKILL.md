---
name: iface-env
description: AgentCPM 接口契约 iface-env（跨设备环境 / PathUri / FsBackend / ExecBackend）的引用与检查指引
---

# iface-env（接口契约）

本包是 AgentCPM 第 9 个接口契约 `iface-env` 的**随包文档 + 源码 + 机器可读 schema**。

## 何时用

- 你要实现一个「文件 / 执行后端」（本地、容器、远端、codex exec-server）→ 先读 `src/fs_backend.rs`、`src/exec_backend.rs` 的 trait 签名。
- 你要表达「这个路径属于哪台机器」→ 用 `src/path_uri.rs` 的 `PathUri`（`environment` + `path`），不要用裸字符串。
- 你要注册/发现环境 → 读 `schema.json` 的 `Environment` / `EnvironmentCapabilities` 形状。

## 文件

| 文件 | 内容 |
|---|---|
| `src/` | 契约 Rust 源码（verbatim 复制自 `kernel/iface/src/env/`，523 行） |
| `schema.json` | 机器可读：类型、字段、方法签名、错误码、不做什么、消费方 |
| `README.md` | 人类可读说明与 mint schema 限制 |

## 边界

只定义形状：不做安全通道、不做 overlay、不读文件系统、不启动进程。
