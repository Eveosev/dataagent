---
round: r1
date: 2026-11-06
scope: W1 dataagent-ocr 包
kernel: agent-kernel@96026126（拉取前 29dd1b76，落后 16；sync-iface-packages --check 报上游 iface-* 漂移 diff=11，OCR 不涉及 iface）
---

# r1 W1 实现记录

## 产出

| 路径 | 内容 |
|-|-|
| `packages/capabilities/dataagent-ocr/src/dataagent_ocr/` | 模块见方案 §10 |
| `packages/capabilities/dataagent-ocr/skills/dataagent-ocr/SKILL.md` | 首次配置、测试调用、固定规则、更换、密钥轮换、依赖型引擎调研与安装 |
| `packages/capabilities/dataagent-ocr/tests/` | 38 项测试；本地 OpenAI 兼容服务替身、worker 替身 |
| `packages/capabilities/dataagent-ocr/uv.lock` | 联网解析（离线缓存缺 `pydantic-core 2.50.4`） |

## 测试

`uv run pytest`：38 passed。

| 文件 | 覆盖 |
|-|-|
| `test_openai_compat.py` | 块与坐标、logprobs 置信度、服务拒绝 logprobs 回退、文本模式、围栏 JSON、格式错误、401 不重试且不泄露密钥、5xx/429 重试、持续失败、路径错误、越界 bbox、token 不能重建内容时不映射、`base_url` 含凭据拒绝 |
| `test_cli_flow.py` | 配置 → 验证 → 固定 → 状态；密钥文件 0600 与 `.gitignore`；固定引擎符合数据层协议；验证失败不固定；更换须 `user_request` + 原话或 `quality_degraded` + degraded 判定，且在测试调用前拒绝；同 profile 换模型视为更换；密钥轮换保持固定；错误密钥为 needs_input；手改 profile 使固定失效；`enforce` 下用户样例无外发决策拒绝、有决策通过；`local` 部署免外发检查 |
| `test_engines.py` | 内置配方；拒绝非 requirement 字符串（环境标记、`-e`、选项、shell）；计划 digest 稳定、缺系统依赖拒绝安装；确认 digest 不符时不执行任何步骤；锁文件内容；调研 spec + adapter；PaddleOCR 3.x / 2.x 结果解析；command worker 端到端（含非协议 stdout 行） |
| `test_quality_and_secrets.py` | 判定 insufficient → ok → degraded；无置信度页不计低置信；窗口只计近期页；数字组必须一致；密钥引用与权限检查 |

## 真实引擎冒烟

数据根 `AgentOS/scratch/ocr-smoke/.dataagent`（已忽略）。

| 步 | 结果 |
|-|-|
| `engine plan rapidocr` | 退出码 3，输出 `plan_digest` |
| `engine install rapidocr --confirm <digest>` | 退出码 0；Python 3.11.16；`rapidocr-onnxruntime==1.4.4`、`onnxruntime==1.31.1`；`lock_digest` 写入 |
| `configure-engine --engine rapidocr` | `rapidocr@r1` |
| `verify --profile rapidocr` | 探针 0.9571、`digits_ok=true`、`confidence_source=engine`、固定理由 `initial_setup` |
| 数据层 `_pages_to_content(load_active_engine(...), [probe])` | `isinstance(engine, OcrEngine)`；`OcrInfo(engine_ref="engine:rapidocr", engine_version="1.4.4|rapidocr@r1:e509187363b3", mean_confidence=0.9859)`；无 issue |

## 实现中修复

| 问题 | 位置 | 修复 |
|-|-|-|
| worker 客户端用 `select` 等待 fd 但经文本包装器 `readline` 读取；横幅与回复同一块到达时回复滞留在缓冲区，`select` 一直等到超时 | `providers/worker.py` | 改为 `os.read` 读 fd、自管行缓冲 |
| `ProfileStore.event(kind, **fields)` 与字段 `kind=` 冲突 | `profiles.py` | 事件名参数改为仅位置参数 |
| RapidOCR 1.4.4 无 `__version__`，引擎版本记为 `unknown` | `workers/engine_worker.py` | 回退到 `importlib.metadata.version` |

## 已知事项

| 项 | 说明 |
|-|-|
| RapidOCR 英文行丢空格 | `DATAAGENTOCRPROBE`、`TOTALAMOUNT12,345.67`；探针比值 0.9571 仍过线，数字组完整。引擎行为，不在适配层补空格 |
| 内置探针只有英文与数字 | Pillow 默认字体无 CJK 字形；中文场景依赖用户样例（SKILL 要求） |
| 未用真实 OpenAI 兼容服务验证 | 协议行为由本地替身覆盖；W4 用用户提供的端点验证 |
| 数据层未接入 | W2；当前需调用方设置 `runtime.ocr_engine = load_active_engine(data_root)` |
