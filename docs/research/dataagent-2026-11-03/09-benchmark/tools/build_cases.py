#!/usr/bin/env python3
"""把 workspace/benchmark-data/ 的原始数据构建成规范化的 cases / expected。

用法（在仓库根目录）：
    python3 -I docs/research/dataagent-2026-11-03/09-benchmark/tools/build_cases.py --task B04
    python3 -I .../build_cases.py --task B04 --dry-run
    python3 -I .../build_cases.py --task B04 --limit 50

每个任务一个转换器：tools/converters/<TASK>.py，暴露 `build(ctx)`。
转换器只声明「用例长什么样」，切分、落盘、计数、manifest 回填由本脚本统一做。
manifest.build.content_digest 记录 cases、expected、fixtures 与来源目录实际数据文件内容的摘要；
摘要不变时重复构建保持原 revision / updated，内容变化才升版本。

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
DIGEST_VERSION = 3
DIGEST_PREFIX = f"benchmark-content-v{DIGEST_VERSION}"


def _update_tree_digest(digest, label: str, root: Path) -> None:
    """把 root 下所有文件的相对路径与内容写入摘要；空/缺失目录也计入。"""
    digest.update(label.encode("utf-8") + b"\0")
    if not root.exists():
        digest.update(b"<missing>\0")
        return
    files = sorted(
        (path for path in root.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(root).as_posix(),
    )
    if not files:
        digest.update(b"<empty>\0")
    for path in files:
        rel = path.relative_to(root).as_posix()
        data = path.read_bytes()
        digest.update(rel.encode("utf-8") + b"\0")
        digest.update(str(len(data)).encode("ascii") + b"\0")
        digest.update(data)


SOURCE_METADATA = {"FETCH.json"}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _update_source_digest(digest, source_id: str, root: Path | None) -> None:
    """把来源 id 与实际数据文件内容写入摘要，排除 FETCH.json 等抓取元数据。"""
    digest.update(b"source\0")
    digest.update(source_id.encode("utf-8") + b"\0")
    if root is None or not root.exists():
        digest.update(b"<missing>\0")
        return
    files = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if path.name in SOURCE_METADATA or ".git" in rel.parts:
            continue
        files.append((rel.as_posix(), path))
    files.sort(key=lambda item: item[0])
    if not files:
        digest.update(b"<empty>\0")
        return
    for rel, path in files:
        digest.update(rel.encode("utf-8") + b"\0")
        digest.update(_sha256_file(path).encode("ascii") + b"\0")


def dataset_content_digest(task_dir: Path) -> str:
    """只对 cases、expected、fixtures 的内容算摘要，用于旧 manifest 首次迁移比较。"""
    digest = hashlib.sha256()
    digest.update(b"benchmark-dataset-v1\0")
    dataset = task_dir / "dataset"
    _update_tree_digest(digest, "cases", dataset / "cases")
    _update_tree_digest(digest, "expected", dataset / "expected")
    _update_tree_digest(digest, "fixtures", dataset / "fixtures")
    return "sha256:" + digest.hexdigest()


def content_digest(task_dir: Path, sources: list[dict], source_paths: dict[str, Path]) -> str:
    """cases、expected、fixtures 与来源实际文件内容的稳定摘要。"""
    digest = hashlib.sha256()
    digest.update(DIGEST_PREFIX.encode("ascii") + b"\0")
    dataset = task_dir / "dataset"
    _update_tree_digest(digest, "cases", dataset / "cases")
    _update_tree_digest(digest, "expected", dataset / "expected")
    _update_tree_digest(digest, "fixtures", dataset / "fixtures")
    for source in sorted(sources, key=lambda item: item.get("name", "")):
        source_id = str(source.get("name"))
        _update_source_digest(digest, source_id, source_paths.get(source.get("name")))
    return "sha256:" + digest.hexdigest()


def _manifest_version(manifest: dict) -> int:
    build = manifest.get("build") or {}
    try:
        version = int(build.get("version", 0) or 0)
    except (TypeError, ValueError):
        version = 0
    if version > 0:
        return version
    revision = str(manifest.get("revision", ""))
    if revision.startswith("v0."):
        try:
            return max(0, int(revision[3:]))
        except ValueError:
            pass
    return 0


def split_of(key: str) -> str:
    h = int(hashlib.sha256(key.encode()).hexdigest()[:8], 16) % 100
    if h < RATIOS["development"]:
        return "development"
    if h < RATIOS["development"] + RATIOS["regression"]:
        return "regression"
    return "unseen_acceptance"


class Context:
    def __init__(self, task: dict, limit: int | None, dry: bool, previous_dataset_digest: str | None = None):
        self.task = task
        self.task_id = task["id"]
        self.task_dir = BASE / task["path"]
        self.dataset = self.task_dir / "dataset"
        self.limit = limit
        self.dry = dry
        self.previous_dataset_digest = previous_dataset_digest
        self.cases: dict[str, list[dict]] = {s: [] for s in SPLITS}
        self.sources: list[dict] = []
        self.source_paths: dict[str, Path] = {}
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
            # 仅记录 FETCH 元数据；content_digest 使用来源文件实际内容。
            "digest": meta.get("digest"),
            "revision": meta.get("resolved_revision"),
            "files": meta.get("files"),
            "mb": meta.get("mb"),
            "fetched_at": meta.get("fetched_at"),
        }
        self.sources.append(rec)
        self.source_paths[source_id] = RAW / entry["task"] / source_id
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
        digest = content_digest(self.task_dir, self.sources, self.source_paths)
        dataset_digest = dataset_content_digest(self.task_dir)
        previous_build = manifest.get("build") or {}
        previous_digest = previous_build.get("content_digest")
        previous_digest_version = previous_build.get("content_digest_version")
        previous_version = _manifest_version(manifest)
        today = date.today().isoformat()
        migrated = previous_digest is None or previous_digest_version != DIGEST_VERSION
        dataset_changed = (
            self.previous_dataset_digest is not None
            and self.previous_dataset_digest != dataset_digest
        )

        if migrated:
            if dataset_changed:
                # 首次引入摘要或摘要方案迁移时，旧 cases/expected/fixtures 已变化，按内容升版。
                build_no = previous_version + 1
                revision = f"v0.{build_no}"
                updated = today
                built_at = today
                changed = True
            else:
                # 内容未变，沿用原 revision，避免迁移本身制造新版本。
                build_no = previous_version
                revision = manifest.get("revision") or f"v0.{build_no}"
                updated = manifest.get("updated") or today
                built_at = previous_build.get("built_at") or today
                changed = False
        elif previous_digest != digest:
            build_no = previous_version + 1
            revision = f"v0.{build_no}"
            updated = today
            built_at = today
            changed = True
        else:
            build_no = previous_version
            revision = manifest.get("revision") or f"v0.{build_no}"
            updated = manifest.get("updated") or today
            built_at = previous_build.get("built_at") or today
            changed = False

        manifest.update(
            revision=revision,
            status="collecting",
            updated=updated,
            sources=self.sources,
            splits={
                s: {"count": stats["selected"][s], "frozen": False} for s in SPLITS
            },
        )
        build = {
            "version": build_no,
            "script": "tools/build_cases.py",
            "built_at": built_at,
            "policy": policy,
            "available": stats["available"],
            "selected": stats["selected"],
            "caps": stats["caps"],
        }
        build.update(extra or {})
        build["content_digest"] = digest
        build["content_digest_version"] = DIGEST_VERSION
        manifest["build"] = build
        manifest["notes"] = "由 build_cases.py 从 workspace/benchmark-data 构建；原始数据不入库"
        mpath.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        print(
            f"{self.task_id}: {stats['selected']} cases  building={build_no}  changed={changed}  "
            f"migrated={migrated}  dataset_changed={dataset_changed}  "
            f"digest={digest[:19]}  sources={len(self.sources)}"
        )


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

    previous_dataset_digest = None
    if not args.dry_run:
        manifest_path = BASE / task["path"] / "dataset" / "manifest.json"
        try:
            json.loads(manifest_path.read_text(encoding="utf-8"))
            previous_dataset_digest = dataset_content_digest(BASE / task["path"])
        except (OSError, json.JSONDecodeError):
            previous_dataset_digest = None

    if not args.keep and not args.dry_run:
        clean_outputs(task["path"] and BASE / task["path"])

    mod = load_converter(args.task)
    ctx = Context(task, args.limit, args.dry_run, previous_dataset_digest=previous_dataset_digest)
    payload = mod.build(ctx)
    stats = ctx.write()
    ctx.publish(stats, policy=payload.get("policy", ""), extra=payload.get("extra"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
