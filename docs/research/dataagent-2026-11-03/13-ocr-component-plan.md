---
version: v0.1
date: 2026-11-06
status: W1 已实现（dataagent-ocr 包，38 项测试；RapidOCR 真实安装与验证通过）；W2 数据层接入、W3 Mint 打包待实施
kernel: agent-kernel@96026126
package: packages/capabilities/dataagent-ocr
---

# OCR 组件方案

## 1. 范围

| 项 | 内容 |
|-|-|
| 原子 | DA01.5.1 扫描 PDF OCR（`ocr_pdf`）、DA01.5.2 图片 OCR（`ocr_image`），实现在 `dataagent-data/src/dataagent_data/ingestion/ocr.py` |
| 现有接缝 | `OcrEngine` 协议（`engine_ref`、`engine_version`、`recognize(image_bytes, lang) -> blocks[text, bbox, confidence]`）；`runtime.ocr_engine` 注入；未注入时尝试 `rapidocr_onnxruntime`（可选依赖 `ocr`），缺失返回 `dependency_unavailable` |
| 本方案 | 新包 `dataagent-ocr`：提供方配置、凭据存储、测试调用与固定、质量监测与重选、依赖型引擎安装；产出符合 `OcrEngine` 的已固定引擎，两个原子的输入输出不变 |
| 不在范围 | 版面分析、表格结构还原、手写体专项、多页批量并发 |

## 2. 提供方类型

| kind | 运行位置 | 依赖 | 置信度来源 | 外发 | 适用 |
|-|-|-|-|-|-|
| `openai_compat` | `POST {base_url}/chat/completions` | 无（标准库 `urllib`） | token `logprobs` → 每行 `exp(平均 logprob)`；服务不支持时无 | `deployment ≠ local` 需 EgressDecision | OpenAI、vLLM / SGLang 部署的视觉语言模型、厂商兼容模式接口 |
| `engine` | `<data_root>/ocr/engines/<name>/.venv` 中的 worker 子进程 | 引擎自带，隔离在独立 venv | 引擎分数 | 否 | PaddleOCR、RapidOCR、EasyOCR、Tesseract、经调研接入的其他引擎 |
| `command` | 自定义 worker 子进程 | 用户或 Agent 提供的 adapter | adapter 给出 | 否 | 商业 SDK、已有命令行工具 |

置信度不可得时 `confidence = None`，不推断。接入数据层时以 `0.0` 传入（页面被标为低置信待复核），`confidence_source` 区分“未提供”与“确实低”（W2 写入契约）。

## 3. 生命周期

```text
unconfigured ──configure──▶ configured(profile@rN) ──verify 通过──▶ active（固定）
                                   ▲                                   │
                                   └──── 新 profile + 合法理由 ◀── degraded / 用户要求
```

| 规则 | 内容 |
|-|-|
| 固定对象 | `active.json` 绑定 `profile@rN`、`config_digest`、通过的 `verification_id` |
| `config_digest` | profile 中影响识别结果的全部字段：kind、`base_url`、`model`、`deployment`、`prompt_version`、请求参数、引擎 `lock_digest` 与 `worker_digest`、adapter digest、质量策略。不含密钥值、密钥引用、revision、时间、备注 |
| 加载校验 | 每次加载重算 digest，须等于 pin 与 verification 中的值；手改 profile、引擎锁变化（重装后版本或 spec 不同）、改 worker / adapter 均使固定失效（`ocr.pin_mismatch`），须重新验证 |
| 首次固定 | 无 active 时验证通过即固定，理由 `initial_setup` |
| 同一配置重验 | 同 profile、同 digest（如密钥轮换）验证通过即更新，理由 `reverify` |
| 更换 | 不同 profile 或同 profile 改了 digest（换模型、换地址）只接受两种理由 |
| 理由 `user_request` | 须附用户原话（`--user-instruction`），记为 evidence |
| 理由 `quality_degraded` | 当场重算当前固定 profile 的质量判定，须为 `degraded`，判定 id 记为 evidence |
| 拒绝 | 其他情况返回 `ocr.switch_refused`；在任何测试调用之前拒绝 |
| 验证失败 | 不固定，原固定保持 |

不触发更换的情况：

| 情况 | 返回 | 处理 |
|-|-|-|
| 401 / 403 | `ocr.credentials`（needs_input） | 向用户要新密钥 → `set-key` → `verify` |
| 超时、连接失败、429、5xx | 重试 `max_retries` 次（退避 0.5/1/2 s）后 `ocr.unavailable` | 稍后重试 |
| 400 / 404 / 422 | `ocr.config` | 检查 `base_url`（通常以 `/v1` 结尾）与模型名 |
| 服务返回的 `model` 与固定时不同 | 记 `model_drift` 事件 | 告知用户；是否更换由用户决定 |
| 单页识别差 | — | `feedback` 记录，进入质量判定 |

## 4. 存储

| 路径（`<data_root>` 下） | 内容 |
|-|-|
| `ocr/profiles/<id>/r<N>.json` | profile 修订，不可改写；内容相同不产生新修订 |
| `ocr/verifications/<vid>.json` | 每次测试调用的分数、图片与期望文本 digest、延迟、`reported_model`、`system_fingerprint`、`confidence_source`、引擎版本 |
| `ocr/active.json` | 固定记录：profile、digest、verification、理由、evidence、上一个固定 |
| `ocr/quality/usage.jsonl`、`feedback.jsonl`、`verdict.json` | 质量信号与判定 |
| `ocr/events.jsonl` | 审计：保存、验证、固定、反馈、判定变化、模型漂移、引擎安装 |
| `ocr/engines/<name>/` | `spec.json`（调研所得）、`.venv/`、`worker.py` 或 adapter、`engine.lock.json` |
| `secrets/ocr/<name>.key` | 密钥文件；目录 0700、文件 0600，原子写；`secrets/.gitignore` 为 `*` |

密钥引用：

| 形式 | 解析 | 用途 |
|-|-|-|
| `file:<name>` | `secrets/ocr/<name>.key`；权限含 group/other 位时拒绝 | 默认；用户经 `--api-key-stdin` 输入 |
| `env:<VAR>` | 调用时读环境变量 | 宿主注入；Mint 清空子进程环境，仅在宿主显式注入时可用 |
| `keychain:<service>/<account>` | macOS `security find-generic-password -w`，只读 | 用户自建条目 |
| Mint `capabilities.secrets` | 经 `credential.provider` 取逻辑名（agent-kernel `PLAN-2026-11-05` 记 secret-broker 生产链部分完成） | W3 接入，形式 `mint:<逻辑名>` |

密钥不进入 profile、digest、事件、CLI 输出、错误文本；HTTP 错误详情经 `redact` 处理。

## 5. OpenAI 兼容协议

| 项 | 内容 |
|-|-|
| 端点 | `{base_url}/chat/completions`，`Authorization: Bearer <key>`（无密钥时省略） |
| 请求 | `temperature=0`；`max_tokens`；system 为 `ocr-blocks-v1` 指令；user 为“图片尺寸 W×H、语言提示”文本 + `image_url`（`data:image/png;base64,...`） |
| JSON 模式 | `response_format={"type":"json_object"}`，要求 `{"blocks":[{"text","bbox":[x0,y0,x1,y1]}]}`，每行一个块、阅读顺序、像素坐标 |
| 文本模式 | `--no-json-mode`：逐行纯文本，无坐标；用于不支持 `response_format` 的服务 |
| 解析 | 接受代码围栏包裹的 JSON；bbox 越界（>2% 容差）、非有限值、反向坐标置空；不符合协议时按行保留文本并记 `format_error` |
| logprobs | `auto`：请求 `logprobs=true`，服务以 400 拒绝时去掉重发；token 拼接须与内容逐字一致，否则不映射 |
| 指令约束 | 原样转写，不翻译、不纠错、不概括、不补字；保留数字、标点、单位、币种符号 |

## 6. 测试调用（验证）

| 夹具 | 内容 | 通过条件 |
|-|-|-|
| `builtin:probe-v1` | 本地用 Pillow 渲染的英文大写与数字（发票号 `2026-1106-0042`、金额 `12,345.67`、日期 `2026-11-06`），不含用户数据 | `difflib` 比值 ≥ `probe_min_score`（0.90）且数字组按序全部出现且无 `format_error` |
| `sample:<文件名>` | 用户样例图 + 期望文本文件 | 比值 ≥ `sample_min_score`（0.90）且数字组全部出现 |

- 全部夹具通过才固定。
- 内置探针只覆盖英文与数字；中文、表格、手写、低质量扫描须用用户样例判断场景效果。CLI 在无样例时输出提醒。
- 非 `local` 部署发送用户样例前做外发检查（§9）；内置探针为合成图，不做外发检查。

## 7. 质量监测与重选

| 信号 | 来源 | 计入条件 |
|-|-|-|
| `empty` | 每页识别结果无文本 | 全部提供方 |
| `low_confidence` | 页平均置信度 < `low_confidence`（0.6） | 仅有置信度的页 |
| `format_error` | 模型未按协议输出 | `openai_compat` JSON 模式 |
| 复核反馈 | `feedback --kind wrong_digits / missed_text / garbled / correction` | 人工或 Agent 复核发现 |

判定（固定 `profile@rN` 最近 `window_pages`=50 页；反馈取同一时间段）：

| 结果 | 条件 |
|-|-|
| `degraded` | 反馈错误页数 ≥ `correction_pages`（3）；或页数 ≥ `min_pages`（20）且 空页率 ≥ 15% / 格式错误率 ≥ 10% / 低置信页率 ≥ 30% |
| `insufficient` | 页数 < `min_pages` 且无反馈 |
| `ok` | 其他 |

`degraded` 只提出重选：继续使用当前提供方，Agent 把 `reasons` 告诉用户，用户同意后才以 `quality_degraded` 固定新的提供方。阈值随 profile 的 `quality` 字段进入 `config_digest`。

## 8. 依赖型引擎

流程：

| 步 | 命令 | 产物 / 校验 |
|-|-|-|
| 1 选择 | `engine list` | 内置配方 |
| 2 调研（非内置） | Agent 查官方文档 → `engine spec --file spec.json [--adapter x.py]` | `ocr/engines/<name>/spec.json`、adapter；事件记录 `docs` |
| 3 计划 | `engine plan <name>` | `steps`（`uv venv --python X`、`uv pip install ...`）、缺失系统依赖与安装提示、`plan_digest`；退出码 3 等待确认 |
| 4 确认安装 | `engine install <name> --confirm <plan_digest>` | digest 不符或缺系统依赖则拒绝；执行步骤；`uv pip freeze`；复制 worker；`--selftest`；写 `engine.lock.json`（`lock_digest` 覆盖 spec、计划、Python 版本、平台、freeze、worker digest） |
| 5 配置 | `configure-engine --engine <name> [--lang]` | profile 绑定 `lock_digest`、`worker_digest` |
| 6 验证固定 | `verify --profile <name>` | 同 §6 |

EngineSpec 字段：

| 字段 | 约束 |
|-|-|
| `name` | `[a-z0-9][a-z0-9_-]{0,31}` |
| `python` | 小版本，如 `3.11` |
| `packages` | 纯 requirement 说明符；拒绝 `-e`、`--` 选项、环境标记、URL、shell 元字符 |
| `index_url` / `extra_index_urls` | 仅官方源 |
| `system_requirements[]` | `name`、`check`（argv）、`install_hints{darwin, linux}`；组件只检查，不安装 |
| `worker` | `builtin:{paddleocr,rapidocr,easyocr,tesseract}` 或 `adapter:<file>.py` |
| `docs` | 官方来源 URL，调研依据 |

内置配方：

| 引擎 | packages | worker 解析 | 备注 |
|-|-|-|-|
| `paddleocr` | `paddlepaddle`、`paddleocr` | 3.x `PaddleOCR(...).predict(ndarray)` → `res.rec_texts / rec_scores / rec_boxes`；2.x `ocr(img, cls=True)` → `[poly, (text, score)]`；输入转 BGR；关闭文档方向、去畸变、文本行方向三个附加模型 | 首次运行下载模型；GPU 版需自写 spec 指向 Paddle 官方源 |
| `rapidocr` | `rapidocr-onnxruntime` | `RapidOCR()(png)` → `[box, text, score]`；兼容 2.x 对象输出 | |
| `easyocr` | `easyocr` | `Reader(langs).readtext` | 安装 PyTorch，体积大 |
| `tesseract` | `pytesseract`、`pillow` | `image_to_data` 按行合并 | 系统依赖 `tesseract`（`brew install tesseract tesseract-lang` / `apt-get install tesseract-ocr tesseract-ocr-chi-sim`） |

Worker 协议（JSON lines，stdin/stdout，日志写 stderr）：

| 请求 | 回复 |
|-|-|
| `{"id","op":"hello"}` | `{"id","engine","engine_version"}` |
| `{"id","op":"recognize","image_b64","lang"}` | `{"id","blocks":[{"text","bbox","confidence"}]}` |
| 任意失败 | `{"id","error":{"code":"engine_missing"|"bad_request"|"engine_error","message"}}` |

worker 以引擎 venv 的解释器 `-I` 运行，只继承 `PATH/HOME/LANG/LC_ALL/TMPDIR`；客户端按 fd 读取并跳过非协议行。

调研约束（SKILL 执行）：只采用官方文档与仓库；版本写死；禁止 `curl | sh`；组件内不执行 `sudo`；系统级安装由用户执行或经用户批准。

## 9. 外发与权限

| 场景 | 规则 |
|-|-|
| `deployment = local`（`base_url` 主机为 `localhost` / `127.0.0.1` / `::1` 时默认） | 不做外发检查 |
| `private_cloud` / `vendor_api` | 页面图片按内容地址 `sha256:<hex>` 引用，经 `dataagent_runtime.enforcement.egress_check` 校验 EgressDecision（`destination.model_ref = openai_compat:<model>`，`deployment` 同 profile） |
| 模式 | `enforce` 拒绝（`ocr.egress_required`，不发请求）；`warn` 发送并返回警告；`off` 跳过 |
| 本地引擎 / command | 不外发；安装时联网下载包与模型 |

W3 Mint 打包声明：

| capability | 值 | 理由 |
|-|-|-|
| `net` | 用户配置的 OCR 端点；安装期包索引 | 远端 OCR 与引擎安装 |
| `secrets` | `dataagent.ocr.api_key` | OpenAI 兼容端点密钥 |
| `exec` | `uv`、`<data_root>/ocr/engines/*/.venv/bin/python` | 建引擎环境、运行 worker |
| `fs.write` | `.dataagent/ocr/**`、`.dataagent/secrets/**` | 配置、固定、质量记录、引擎环境、密钥 |

## 10. 包结构

| 模块 | 职责 |
|-|-|
| `types.py` | `OcrBlock`、`RecognizeResult`、`OcrProvider` 协议 |
| `errors.py` | 错误码：`not_configured`、`not_verified`、`pin_mismatch`、`credentials`、`config`、`unavailable`、`egress_required`、`switch_refused`、`install_refused`、`engine_missing` |
| `secrets.py` | 密钥引用的存取与脱敏 |
| `profiles.py` | profile 模型、`config_digest`、`ProfileStore`（修订、验证、固定、事件） |
| `providers/openai_compat.py` | 请求构造、重试、解析、logprobs 映射 |
| `providers/worker.py` | worker 客户端与提供方适配 |
| `providers/__init__.py` | 由 profile 构建提供方，校验引擎锁与 adapter digest |
| `workers/engine_worker.py` | 独立 worker 脚本（标准库 + 引擎包），安装时复制进引擎目录 |
| `engines.py` | EngineSpec、内置配方、计划、安装、锁 |
| `probe.py` | 探针渲染与打分 |
| `verify.py` | 测试调用、固定策略 |
| `quality.py` | 使用记录、反馈、判定 |
| `egress.py` | 外发检查 |
| `adapter.py` | `load_active_engine(data_root)` → 符合 `OcrEngine` 的 `PinnedOcrEngine`，逐页记录质量信号 |
| `cli.py` | `dataagent-ocr` 命令 |
| `skills/dataagent-ocr/SKILL.md` | Agent 对话流程 |

CLI：

| 命令 | 作用 |
|-|-|
| `status` | 固定、profile、验证分数、质量判定、已装引擎 |
| `configure-openai` | `--base-url --model --deployment` + `--api-key-stdin / --api-key-env / --api-key-keychain / --no-api-key` |
| `set-key` | 密钥轮换 |
| `configure-engine` / `configure-command` | 本地引擎 / 自定义 worker |
| `verify` | 测试调用；通过即按 §3 固定；`--sample/--expect`、`--egress-decision-ref`、`--reason`、`--user-instruction`、`--no-pin` |
| `recognize` | 用固定提供方识别一张图（调试） |
| `feedback` / `quality` | 复核反馈 / 质量判定 |
| `engine list / spec / plan / install` | 依赖型引擎 |

退出码：0 成功；1 失败；2 用法或配置错误；3 需要输入。

## 11. 数据层接入（W2）

| 项 | 改动 |
|-|-|
| 引擎解析 | `ingestion/ocr.py::_engine`：`runtime.ocr_engine` → `dataagent_ocr.load_active_engine(runtime.data_root)` → `RapidOcrEngine.create()`；全部失败时 `dependency_unavailable`，action 指向 SKILL `dataagent-ocr` |
| 未就绪 | `OcrError.needs_input` 映射为 `needs_input`，issue 码 `da01.ocr_not_ready`，附 `ocr.*` 原码 |
| 外发 | `OcrPdfInput` / `OcrImageInput` 增可选 `egress_decision_ref`；远端提供方在渲染页面后、调用前对源文件 `content_digest` 做 §9 检查 |
| issue | `da01.ocr_quality_degraded`（判定为 degraded 时 warning，建议告知用户）、`da01.ocr_model_drift`、`da01.ocr_confidence_unavailable` |
| 契约 | `OcrInfo` 增 `confidence_source`、`profile_ref`（`dataagent-contracts` 小版本升级，按 05 准入规则） |
| 依赖与打包 | `dataagent-data` 依赖 `dataagent-ocr`（path）；`build_bundle.py` vendoring 增加 `dataagent_ocr`；重建 bundle，`test_bundle_sync` 通过 |
| Catalog | DA01.5 增原子：DA01.5.3 OCR 提供方配置与固定、DA01.5.4 OCR 质量监测与重选、DA01.5.5 OCR 引擎安装；改 `tools/build.py` 后重新生成 `catalog/` 与 00–04 |

## 12. 实施步骤

| 步 | 内容 | 状态 |
|-|-|-|
| W1 | `dataagent-ocr` 包、SKILL、测试 | 已完成：38 项测试；RapidOCR 经 plan → install → configure → verify 真实跑通（Python 3.11.16、`rapidocr-onnxruntime==1.4.4`、`onnxruntime==1.31.1`，探针 0.9571、数字组全对）；固定引擎经数据层 `_pages_to_content` 产出 `OcrInfo(engine_ref="engine:rapidocr", mean_confidence=0.9859)` |
| W2 | §11 数据层接入与契约 | 待实施 |
| W3 | Mint 打包（§9 capability、SKILL 随 bundle 分发、`mint:` 密钥来源）；统一 CLI 增 `dataagent ocr` 路由 | 待实施 |
| W4 | 真实 OpenAI 兼容服务验证（用户提供端点）；中文样例集纳入 09-benchmark B02 | 待实施 |

## 13. 记录

实施、评审与修复记录写入 [13-ocr-build/](13-ocr-build/)。

| 轮次 | 文件 | 内容 |
|-|-|-|
| r1 | [r1-implementation.md](13-ocr-build/r1-implementation.md) | W1 实现、测试与真实引擎冒烟记录 |
