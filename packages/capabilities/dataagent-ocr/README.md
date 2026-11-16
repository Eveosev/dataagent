# dataagent-ocr

DataAgent 的 OCR 提供方组件：配置、凭据、测试调用与固定、质量监测与重选、依赖型引擎安装。数据层 `ocr_pdf`（DA01.5.1）/ `ocr_image`（DA01.5.2）经 `runtime.ocr_engine` 使用固定的提供方。方案见 `docs/research/dataagent-2026-11-03/13-ocr-component-plan.md`。

## 提供方

| kind | 运行位置 | 置信度 | 外发 |
|-|-|-|-|
| `openai_compat` | `{base_url}/chat/completions`，图片以 `data:` URL 发送 | `logprobs`（服务支持时），否则无 | `deployment ≠ local` 需 EgressDecision |
| `engine` | `<data_root>/ocr/engines/<name>/.venv` 子进程 | 引擎分数 | 否 |
| `command` | 自定义 worker 子进程 | adapter 给出 | 否 |

## 使用

```bash
uv sync --frozen --extra dev
printf '%s\n' "$KEY" | uv run dataagent-ocr configure-openai --profile vl --base-url https://host/v1 --model <model> --deployment vendor_api --api-key-stdin
uv run dataagent-ocr verify --profile vl --sample invoice.png --expect invoice.txt --egress-decision-ref <ref>
uv run dataagent-ocr status
```

```python
from dataagent_ocr import load_active_engine
runtime.ocr_engine = load_active_engine(runtime.data_root)   # 未固定时抛 OcrError（needs_input）
```

依赖型引擎：`engine list` → `engine plan <name>` → 用户确认 → `engine install <name> --confirm <plan_digest>` → `configure-engine --engine <name>` → `verify`。

## 测试

`uv run pytest`（38 项；不联网，OpenAI 兼容服务与 worker 均为本地替身）。
