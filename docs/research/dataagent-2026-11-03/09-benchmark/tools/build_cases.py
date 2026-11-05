#!/usr/bin/env python3
"""把 workspace/benchmark-data/ 的原始数据构建成规范化的 cases / expected。

用法（在仓库根目录）：
    python3 -I docs/research/dataagent-2026-11-03/09-benchmark/tools/build_cases.py --task B04
    python3 -I .../build_cases.py --task B04 --dry-run
    python3 -I .../build_cases.py --task B04 --limit 50

每个任务一个转换器：tools/converters/<TASK>.py，暴露 `build(ctx)`。
转换器只声明「用例长什么样」，切分、落盘、计数、manifest 回填由本脚本统一做。

依赖：文本类源用标准库；parquet 源需要 workspace/benchmark-data/.pydeps（fetch.py 说明里给安装命令）。
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import sys
from datetime import date
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parents[3]
LOCK = BASE / "datasets.lock.json"
RAW = ROOT / "workspace" / "benchmark-data"
DEPS = RAW / ".pydeps"
SPLITS = ("development", "regression", "unseen_acceptance")
RATIOS = {"development": 60, "regression": 20, "unseen_acceptance": 20}
DEFAULT_CAPS = {"development": 120, "regression": 60, "unseen_acceptance": 60}


def split_of(key: str) -> str:
    h = int(hashlib.sha256(key.encode()).hexdigest()[:8], 16) % 100
    if h < RATIOS["development"]:
        return "development"
    if h < RATIOS["development"] + RATIOS["regression"]:
        return "regression"
    return "unseen_acceptance"


class Context:
    def __init__(self, task: dict, limit: int | None, dry: bool):
        self.task = task
        self.task_id = task["id"]
        self.task_dir = BASE / task["path"]
        self.dataset = self.task_dir / "dataset"
        self.limit = limit
        self.dry = dry
        self.cases: dict[str, list[dict]] = {s: [] for s in SPLITS}
        self.sources: list[dict] = []
        self.notes: list[str] = []
        self._pending: dict[str, str] = {}

    # ---- 元数据 ----
    def source(self, source_id: str) -> dict:
        lock = json.loads(LOCK.read_text(encoding="utf-8"))
        entry = next((s for s in lock["sources"] if s["id"] == source_id), None)
        if entry is None:
            raise KeyError(f"datasets.lock.json 中没有 {source_id}")
        fetch = RAW / entry["task"] / source_id / "FETCH.json"
        meta = json.loads(fetch.read_text(encoding="utf-8")) if fetch.exists() else {}
        rec = {
            "name": source_id,
            "locator": entry["locator"],
            "license": entry.get("license"),
            "digest": meta.get("digest"),
            "revision": meta.get("resolved_revision"),
            "files": meta.get("files"),
            "mb": meta.get("mb"),
            "fetched_at": meta.get("fetched_at"),
        }
        self.sources.append(rec)
        return rec

    def raw_path(self, source_id: str, *parts: str) -> Path:
        return RAW / self.task_id / source_id / Path(*parts)

    def bench(self, source_id: str, *parts: str) -> str:
        return f"bench://{source_id}/" + "/".join(str(p) for p in parts)

    # ---- 落盘 ----
    def add(
        self,
        *,
        source: str,
        seq: int,
        inputs: list[dict],
        expected: dict,
        evidence: list[str] | None = None,
        tags: list[str] | None = None,
        gold: dict | None = None,
        split_key: str | None = None,
    ) -> None:
        case_id = f"{self.task_id}-{source}-{seq:04d}"
        split = split_of(split_key or case_id)
        payload = {
            "case_id": case_id,
            "task_id": self.task_id,
            "split_role": split,
            "inputs": inputs,
            "expected": {"kind": "inline", "ref": f"expected/{case_id}.json"},
            "evidence": evidence or [],
            "tags": tags or [],
            "source": source,
            "license": None,
            "fingerprint": None,
            "annotation": {"status": "reviewed", "annotators": ["external"], "adjudicated": False},
        }
        self.cases[split].append(
            {
                "case": payload,
                "gold": {**(gold or {}), "case_id": case_id, "expected": expected},
            }
        )

    def fixture(self, name: str, text: str) -> str:
        """登记小文本输入，返回 case 内的相对引用；只写被选中的用例（write 时落盘）。"""
        rel = f"fixtures/{name}"
        self._pending[rel] = text
        return rel

    # ---- 输出 ----
    def write(self) -> dict:
        caps = dict(DEFAULT_CAPS)
        if self.limit:
            caps = {s: max(1, self.limit // 3) for s in SPLITS}
        selected = {}
        available = {s: len(v) for s, v in self.cases.items()}
        for split in SPLITS:
            items = sorted(self.cases[split], key=lambda c: c["case"]["case_id"])
            if len(items) > caps[split]:
                # 按哈希序截取，避免偏向编号靠前的样本
                items = sorted(items, key=lambda c: hashlib.sha256(c["case"]["case_id"].encode()).hexdigest())[: caps[split]]
                items.sort(key=lambda c: c["case"]["case_id"])
            selected[split] = len(items)
            if self.dry:
                continue
            cdir = self.dataset / "cases" / split
            edir = self.dataset / "expected"
            cdir.mkdir(parents=True, exist_ok=True)
            edir.mkdir(parents=True, exist_ok=True)
            for it in items:
                cid = it["case"]["case_id"]
                for inp in it["case"]["inputs"]:
                    rel = inp.get("ref", "")
                    if rel in self._pending:
                        fp = self.dataset / rel
                        fp.parent.mkdir(parents=True, exist_ok=True)
                        fp.write_text(self._pending[rel], encoding="utf-8")
                (cdir / f"{cid}.json").write_text(
                    json.dumps(it["case"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
                (edir / f"{cid}.json").write_text(
                    json.dumps(it["gold"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
        return {"selected": selected, "available": available, "caps": caps}

    def publish(self, stats: dict, policy: str, extra: dict | None = None) -> None:
        if self.dry:
            print(json.dumps({"selected": stats["selected"], "available": stats["available"]}, ensure_ascii=False))
            return
        mpath = self.dataset / "manifest.json"
        manifest = json.loads(mpath.read_text(encoding="utf-8"))
        build_no = int(manifest.get("build", {}).get("version", 0)) + 1
        manifest.update(
            revision=f"v0.{build_no}",
            status="collecting",
            updated=date.today().isoformat(),
            sources=self.sources,
            splits={
                s: {"count": stats["selected"][s], "frozen": False} for s in SPLITS
            },
        )
        manifest["build"] = {
            "version": build_no,
            "script": "tools/build_cases.py",
            "built_at": date.today().isoformat(),
            "policy": policy,
            "available": stats["available"],
            "selected": stats["selected"],
            "caps": stats["caps"],
            **(extra or {}),
        }
        manifest["notes"] = "由 build_cases.py 从 workspace/benchmark-data 构建；原始数据不入库"
        mpath.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        print(f"{self.task_id}: {stats['selected']} cases  building={build_no}  sources={len(self.sources)}")


def clean_outputs(task_dir: Path) -> None:
    fx = task_dir / "dataset" / "fixtures"
    if fx.exists():
        for p in fx.glob("*"):
            if p.is_file():
                p.unlink()
    for split in SPLITS:
        d = task_dir / "dataset" / "cases" / split
        if d.exists():
            for p in d.glob("*.json"):
                p.unlink()
    e = task_dir / "dataset" / "expected"
    if e.exists():
        for p in e.glob("*.json"):
            p.unlink()


def load_converter(task_id: str):
    path = BASE / "tools" / "converters" / f"{task_id}.py"
    if not path.exists():
        raise SystemExit(f"缺少转换器 {path}")
    spec = importlib.util.spec_from_file_location(f"conv_{task_id}", path)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(DEPS))
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--limit", type=int, help="每任务的粗糙上限（三等分到 split）")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--keep", action="store_true", help="不清空旧用例，只追加")
    args = ap.parse_args()

    registry = json.loads((BASE / "registry.json").read_text(encoding="utf-8"))
    task = next((t for t in registry["tasks"] if t["id"] == args.task), None)
    if task is None:
        raise SystemExit(f"未知任务 {args.task}")

    if not args.keep and not args.dry_run:
        clean_outputs(task["path"] and BASE / task["path"])

    mod = load_converter(args.task)
    ctx = Context(task, args.limit, args.dry_run)
    payload = mod.build(ctx)
    stats = ctx.write()
    ctx.publish(stats, policy=payload.get("policy", ""), extra=payload.get("extra"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
