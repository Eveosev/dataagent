---
name: dataagent-ocr
description: 为 DataAgent 配置、验证并固定 OCR 提供方（OpenAI 兼容接口，或 PaddleOCR / RapidOCR / EasyOCR / Tesseract 等需安装依赖的本地引擎）；处理换模型、质量下降与密钥轮换。首次使用 ocr_pdf / ocr_image 前、OCR 返回 ocr.not_configured / ocr.credentials / ocr.pin_mismatch、用户要求更换 OCR 模型、或质量判定为 degraded 时使用。
---

# DataAgent OCR 提供方

命令：`dataagent-ocr <子命令>`（等价 `python -m dataagent_ocr`）。每条命令输出一个 JSON；退出码 0 成功、1 失败、2 用法/配置错误、3 需要用户输入。配置写在 `<data_root>/ocr/`，密钥写在 `<data_root>/secrets/ocr/`（0600）。

## 固定规则（强制）

1. 已有固定的提供方（`status` 返回 `active`）时，**不配置、不验证、不切换**其他提供方，直接使用。
2. 只有两种情况可以更换：
   - 用户明确要求更换 OCR 模型/引擎：`verify ... --reason user_request --user-instruction "<用户原话>"`；
   - `quality` 判定为 `degraded`：先把 `reasons` 告诉用户，用户同意后 `verify ... --reason quality_degraded`。
3. 以下情况**不是**更换理由：网络超时、5xx、限流（`ocr.unavailable`，稍后重试）；密钥失效（`ocr.credentials`，向用户要新密钥后 `set-key` + `verify`）；单页识别差（用 `feedback` 记录，由质量判定决定）。
4. 密钥只经 `--api-key-stdin` 传入；不写进命令行参数、文件、日志或回复；不回显、不复述。
5. 本地引擎的安装计划必须先给用户看，用户同意后才 `engine install --confirm <plan_digest>`；系统级软件（`missing_system`）由用户安装或在用户批准后执行其 `install_hint`。

## 首次配置

先 `dataagent-ocr status`。返回 `ocr.not_configured` 时，问用户选哪条路线：

### A. OpenAI 兼容接口

向用户要：`base_url`（通常以 `/v1` 结尾）、模型名、api_key，以及服务部署在哪里：

| 用户回答 | `--deployment` | 含义 |
|-|-|-|
| 本机（localhost） | `local` | 图片不离开本机 |
| 公司私有部署 | `private_cloud` | 图片发往私有服务，需外发决策 |
| 第三方云服务 | `vendor_api` | 图片发往第三方，需外发决策 |

```bash
printf '%s\n' "$KEY" | dataagent-ocr configure-openai --profile <id> \
  --base-url <base_url> --model <model> --deployment <local|private_cloud|vendor_api> --api-key-stdin
```

`$KEY` 由用户在终端提供；你不要看到或保存它的值。服务不支持 JSON 输出时加 `--no-json-mode`（无文字框坐标）。

### B. 本地引擎（PaddleOCR 等）

1. `dataagent-ocr engine list` 查看内置配方（paddleocr、rapidocr、easyocr、tesseract）。
2. 用户要的引擎不在列表中：查该引擎**官方**文档或仓库，写 spec（字段见下），`engine spec --file spec.json [--adapter adapter.py]` 保存。
3. `engine plan <name>`：把 `steps`、`packages`、`docs`、`missing_system` 展示给用户。
4. 用户同意后：`engine install <name> --confirm <plan_digest>`。
5. `configure-engine --engine <name> [--lang <语言>]`。

spec 字段：`name`、`display_name`、`python`（如 `3.11`）、`packages`（纯 requirement，建议写死版本）、`index_url` / `extra_index_urls`（仅官方源）、`system_requirements[{name, check, install_hints}]`、`worker`（`builtin:<引擎>` 或 `adapter:<文件>.py`）、`default_lang`、`docs`（官方来源 URL，必填）、`license`、`notes`。

自写 adapter 遵循 worker 协议：stdin 每行一个请求 `{"id","op":"hello"|"recognize","image_b64","lang"}`，stdout 每行一个回复 `{"id","engine","engine_version"}` / `{"id","blocks":[{"text","bbox":[x0,y0,x1,y1],"confidence"}]}` / `{"id","error":{"code","message"}}`；日志写 stderr。禁止 `curl | sh`、禁止组件内 `sudo`。

### C. 已有命令行工具或 SDK

写一个符合上述 worker 协议的 adapter，`configure-command --profile <id> --argv-json '["python","adapter.py"]' --adapter adapter.py`。

## 测试调用并固定

```bash
dataagent-ocr verify --profile <id> [--sample <用户样例图> --expect <期望文本.txt>] [--egress-decision-ref <ref>]
```

- 内置探针是本地合成的英文/数字图片，不含用户数据。
- 强烈建议向用户要 1–3 张真实样例及其正确文本（`--expect` 文件），尤其是中文、表格、手写或低质量扫描；这是判断“该场景下效果”的唯一依据。
- 非 `local` 部署发送用户样例前需要外发决策（`--egress-decision-ref`）；`enforce` 模式下没有决策返回 `ocr.egress_required`，先走治理层授权或改用本地提供方。
- 通过（`status=ok`）即固定；把 `fixtures` 的分数、`digits_ok`、`confidence_source` 告诉用户。`confidence_source=none` 表示该服务不给置信度，数据层会把这些页标为待复核。
- 失败：把分数给用户看，调整配置或换提供方；不要降低阈值。

## 日常使用

- `ocr_pdf` / `ocr_image` 使用固定的提供方，无需每次配置。
- 复核时发现识别错误：`dataagent-ocr feedback --kind wrong_digits|missed_text|garbled|correction --pages <n> --document <id>`。
- 定期或用户抱怨效果时：`dataagent-ocr quality`。`degraded` 时把 `reasons` 告诉用户并询问是否更换；`ok` / `insufficient` 时保持现状。

## 更换提供方

1. 配置新 profile（新 id，路线 A/B/C）。
2. `verify --profile <新id> --reason user_request --user-instruction "<用户原话>"`，或 `--reason quality_degraded`。
3. 验证不通过时原提供方保持固定。

## 密钥轮换

`printf '%s\n' "$KEY" | dataagent-ocr set-key --profile <id> --api-key-stdin`，再 `verify --profile <id>`（同一 profile，原因自动为 `reverify`）。
