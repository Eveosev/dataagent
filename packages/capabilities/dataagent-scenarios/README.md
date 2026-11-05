# dataagent-scenarios

仅测试包（08 §8）。依赖数据层、应用层、评测治理层三个包，以
`enforcement = enforce` 运行跨层链路与端到端组合（S0 Preset
`dataagent-s0` 的三条 bundle 场景）。

- `test_data_layer_gate.py`：08 §10.2 —— enforce 模式下数据层 32 个原子全部
  真实经过访问复检（`dataagent_scenarios.gate` 组合 DA12.1 复检 + 数据层
  invoke）：有覆盖决策时到达数据层处理器，伪造授权在读取前被拒。
- `test_cross_layer.py`：数据层解析产出 TableRef → 治理层访问判定 → 粒度合并
  检查 → 判据与样本 → 端到端验收报告。
- `test_s0_mcp_e2e.py`：三个 bundle 以真实 MCP 子进程按 Skill 顺序驱动
  （访问判定 → 接入与抽取 → 引擎与两段式 → 验收准备），治理层以
  `DATAAGENT_ENFORCEMENT_MODE=enforce` 运行。
