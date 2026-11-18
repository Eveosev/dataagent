# tools/tests

`set_baseline.py` 的自测，全部在临时目录构造假 run，不读写真实 `tasks/` 与 `registry.json`。

## 运行

```bash
cd docs/research/dataagent-2026-11-03/09-benchmark
uv run --offline --with pytest pytest -q tools/tests harness/tests -k baseline
```

uv 缓存不可写时设 `UV_CACHE_DIR=<可写目录>`；离线运行要求该目录已有 pytest 缓存。

已装 pytest 时也可以直接用系统 Python：

```bash
python3 -m pip install -r tools/tests/requirements.txt
python3 -m pytest -q tools/tests harness/tests -k baseline
```

系统 Python 受 PEP 668 管理时，用临时 venv：

```bash
python3 -m venv /tmp/t37-pytest
/tmp/t37-pytest/bin/pip install -r tools/tests/requirements.txt
/tmp/t37-pytest/bin/python -m pytest -q tools/tests harness/tests -k baseline
```

没有 pytest 时走 unittest：

```bash
python3 -I tools/tests/test_set_baseline.py
```
