# 本地接入工作台

本地安装闭包由 `tools/build_bundle.py` 生成，`dataagent/preset-intake` 装入 workbench、data-layer、operations 与统一 CLI。文件接入与 API 工作流运行使用已安装的包。

工作区由当前操作系统用户持有。工作台固定工作区范围、主体和本地授权，不接受工具参数替换它们；该模式适合单用户本地开发，未提供跨用户托管授权。浏览器服务仅监听 loopback，认证仅保存在服务内存，浏览器通过一次性入口换取 HttpOnly Cookie；工作区不保存令牌。

命令：`dataagent workbench intake --goal 接入发票 --source invoice.csv`，返回持久任务和真实作业；`dataagent workbench status <任务ID>` 查询；`dataagent workbench view <任务ID>` 打开同一个任务。`dataagent setup/doctor` 准备并检查已安装包。

构建与验收从仓库根执行：

```sh
uv run --project packages/capabilities/dataagent-workbench python packages/capabilities/dataagent-workbench/tools/build_bundle.py --out build/local
bash scripts/verify_local.sh --phase bootstrap
```

## 来源连接

SQLite 使用工作区相对路径或上传文件。PostgreSQL 和 REST 使用宿主配置的连接 ID。在启动工作台或 MCP 进程时设置 `DATAAGENT_SOURCE_CONNECTIONS`，值为宿主 JSON 配置路径。配置以连接 ID 为键。

```json
{
  "ledger": {
    "kind": "postgres",
    "label": "发票数据库",
    "locator": "postgresql://127.0.0.1:5432/postgres",
    "scope": {"tables": ["invoice"]},
    "credential_env": {"user": "DATAAGENT_PG_USER", "password": "DATAAGENT_PG_PASSWORD"}
  },
  "accounting": {
    "kind": "rest",
    "label": "发票 API",
    "locator": "http://127.0.0.1:8000/invoices",
    "allowed_origins": ["http://127.0.0.1:8000"],
    "options": {"records_path": "/items", "source_version_path": "/version", "pagination": {"next_path": "/next"}}
  }
}
```

远端来源在任务中保存连接 ID。宿主在数据层调用时解析连接、读取范围与凭据，工作台页面只列出连接名和类型。版本化 REST 分页在遇到短暂故障时可通过「继续探查」读取未完成的页。使用 `DATAAGENT_OPERATIONS_CONFIG` 配置本地业务环境，工作台通过独立 Operations MCP 进程读写流程，配置示例见 [Operations](../dataagent-operations/README.md)。
