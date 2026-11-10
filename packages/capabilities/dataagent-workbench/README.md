# 本地接入工作台

本地安装闭包由 `tools/build_bundle.py` 生成；`dataagent/preset-intake` 装入 workbench、data-layer 与统一 CLI。安装后无需访问开发仓。

工作区由当前操作系统用户持有。工作台固定工作区范围、主体和本地授权，不接受工具参数替换它们；该模式适合单用户本地开发，未提供跨用户托管授权。浏览器服务仅监听 loopback，令牌保存在 `.dataagent/runtime/workbench.token`，不放入工具输出。

命令：`dataagent workbench intake --goal 接入发票 --source invoice.csv`，返回持久任务和真实作业；`dataagent workbench status <任务ID>` 查询；`dataagent workbench view <任务ID>` 打开同一个任务。`dataagent setup/doctor` 准备并检查已安装包。

构建与验收从仓库根执行：

```sh
uv run --project packages/capabilities/dataagent-workbench python packages/capabilities/dataagent-workbench/tools/build_bundle.py --out build/local
bash scripts/verify_local.sh --phase bootstrap
```

功能与验收范围以实施记录为准；bootstrap 验证本地安装、任务和重启读取，不代表文件处理或 TUI/GUI 已通过。
