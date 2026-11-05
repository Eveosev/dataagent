#!/usr/bin/env python3
"""按 datasets.lock.json 下载各任务的数据源到 workspace/benchmark-data/。

用法（在仓库根目录）：
    python3 -I docs/research/dataagent-2026-11-03/09-benchmark/tools/fetch.py --dry-run
    python3 -I .../fetch.py                        # 下载全部 available
    python3 -I .../fetch.py --task B05             # 只下某一任务
    python3 -I .../fetch.py --only dabstep,bright
    python3 -I .../fetch.py --force                # 覆盖已完成的源
    python3 -I .../fetch.py --hash                 # 额外算每文件 sha256（慢）

产出：
    workspace/benchmark-data/<task>/<source-id>/          原始数据
    workspace/benchmark-data/<task>/<source-id>/FETCH.json 来源、版本、大小、文件数、digest
    workspace/benchmark-data/fetch-report.json            汇总
    workspace/benchmark-data/_logs/<source-id>.log        下载日志

gated / registration 类型的源不会尝试下载，只打印 remedy；补齐后改 status 再重跑。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parents[3]
LOCK = BASE / "datasets.lock.json"


def now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def sh(cmd: list[str], cwd: Path, log: Path, timeout: int) -> tuple[int, str]:
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as fh:
        fh.write(f"\n$ {' '.join(cmd)}\n")
        fh.flush()
        try:
            proc = subprocess.run(cmd, cwd=cwd, stdout=fh, stderr=subprocess.STDOUT, timeout=timeout)
            return proc.returncode, ""
        except subprocess.TimeoutExpired:
            return 124, f"timeout after {timeout}s"
        except FileNotFoundError as exc:
            return 127, str(exc)


def hf_sha(repo: str, kind: str) -> str | None:
    api = "https://huggingface.co/api/" + ("datasets/" if kind == "dataset" else "models/") + repo
    try:
        with urllib.request.urlopen(api, timeout=30) as r:
            return json.load(r).get("sha")
    except Exception:
        return None


def git_head(path: Path) -> str | None:
    try:
        return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return None


def tree_stats(path: Path, do_hash: bool) -> tuple[int, int, str]:
    files = 0
    total = 0
    digest = hashlib.sha256()
    for p in sorted(path.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(path)
        size = p.stat().st_size
        files += 1
        total += size
        digest.update(f"{rel}\0{size}\0".encode())
        if do_hash:
            h = hashlib.sha256()
            with p.open("rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    h.update(chunk)
            digest.update(h.digest())
    return files, total, "sha256:" + digest.hexdigest()


def load_report() -> dict:
    p = ROOT / "workspace" / "benchmark-data" / "fetch-report.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"version": "v0.1", "sources": {}}


def write_report(rep: dict) -> None:
    p = ROOT / "workspace" / "benchmark-data" / "fetch-report.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fetch_one(src: dict, raw_root: Path, *, force: bool, do_hash: bool, dry: bool, timeout: int) -> dict:
    sid, task, kind = src["id"], src["task"], src["kind"]
    target = raw_root / task / sid
    meta_path = target / "FETCH.json"
    log = raw_root / "_logs" / f"{sid}.log"
    record = {
        "id": sid,
        "task": task,
        "kind": kind,
        "locator": src["locator"],
        "revision_requested": src.get("revision"),
        "license": src.get("license"),
        "target": str(target.relative_to(ROOT)),
        "status": "pending",
    }

    if src["status"] != "available":
        record["status"] = src["status"]
        record["remedy"] = src.get("remedy")
        return record

    if meta_path.exists() and not force:
        old = json.loads(meta_path.read_text(encoding="utf-8"))
        if old.get("status") == "ok":
            old["status"] = "cached"
            return old

    if dry:
        est = src.get("est_mb")
        record["status"] = "dry-run"
        record["est_mb"] = est
        print(f"  would fetch {sid:20s} {kind:12s} -> {record['target']}"
              + (f"  ~{est:.0f} MB" if est else ""))
        return record

    target.mkdir(parents=True, exist_ok=True)
    started = time.time()
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(f"# fetch {sid} at {now()}\n", encoding="utf-8")

    if kind == "hf_dataset":
        if shutil.which("hf") is None:
            record.update(status="failed", error="找不到 hf CLI")
            return record
        cmd = ["hf", "download", src["locator"], "--repo-type", "dataset",
               "--local-dir", str(target), "--revision", src.get("revision") or "main"]
        for pattern in src.get("include") or []:
            cmd += ["--include", pattern]
        code, err = sh(cmd, ROOT, log, timeout)
        record["resolved_revision"] = hf_sha(src["locator"], "dataset")
    elif kind == "url_zip":
        archive = target.parent / f".{sid}.zip"
        code, err = sh(["curl", "-L", "--fail", "--retry", "3", "--progress-bar",
                        "-o", str(archive), src["locator"]], ROOT, log, timeout)
        if code == 0:
            try:
                with zipfile.ZipFile(archive) as zf:
                    zf.extractall(target)
                archive.unlink()
            except Exception as exc:  # noqa: BLE001
                code, err = 1, f"unzip failed: {exc}"
        record["resolved_revision"] = None
    elif kind == "git":
        if (target / ".git").exists():
            cmd = ["git", "-C", str(target), "fetch", "--depth", "1", "origin"]
            code, err = sh(cmd, ROOT, log, timeout)
        else:
            cmd = ["git", "clone", "--depth", "1"]
            if src.get("revision"):
                cmd += ["--branch", src["revision"]]
            cmd += [src["locator"], str(target)]
            code, err = sh(cmd, ROOT, log, timeout)
        record["resolved_revision"] = git_head(target)
    else:
        record.update(status="failed", error=f"未支持的 kind: {kind}")
        return record

    if code != 0:
        record.update(status="failed", error=err or f"exit {code}", log=str(log.relative_to(ROOT)))
        return record

    files, total, digest = tree_stats(target, do_hash)
    record.update(
        status="ok",
        files=files,
        bytes=total,
        mb=round(total / 1e6, 1),
        digest=digest,
        digest_mode="sha256(per-file)" if do_hash else "sha256(list+size)",
        elapsed_s=round(time.time() - started, 1),
        fetched_at=now(),
        log=str(log.relative_to(ROOT)),
    )
    if kind == "git" and (target / ".git").exists():
        record["digest"] = digest  # 仓库用文件树 digest，未算 commit 之外的历史
    meta_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return record


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", help="只处理某任务，如 B05")
    ap.add_argument("--only", help="逗号分隔的 source id")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--hash", action="store_true", help="计算每文件 sha256（慢但可核验）")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--timeout", type=int, default=7200, help="单个源超时秒数，默认 7200")
    args = ap.parse_args()

    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    raw_root = ROOT / lock["raw_root"]
    only = {s.strip() for s in args.only.split(",")} if args.only else None

    todo = [s for s in lock["sources"] if (args.task is None or s["task"] == args.task)
            and (only is None or s["id"] in only)]
    if not todo:
        print("没有匹配的数据源", file=sys.stderr)
        return 1

    report = load_report()
    results = []
    for i, src in enumerate(todo, 1):
        print(f"[{i}/{len(todo)}] {src['task']} {src['id']} ({src['kind']})")
        rec = fetch_one(src, raw_root, force=args.force, do_hash=args.hash, dry=args.dry_run, timeout=args.timeout)
        results.append(rec)
        report["sources"][src["id"]] = rec
        if not args.dry_run:
            write_report(report)
        print(f"    -> {rec.get('status')}"
              + (f" {rec.get('mb')} MB / {rec.get('files')} files" if rec.get("mb") else "")
              + (f"  remedy: {rec.get('remedy')}" if rec.get("remedy") else "")
              + (f"  error: {rec.get('error')}" if rec.get("error") else ""))

    ok = [r for r in results if r.get("status") in {"ok", "cached"}]
    print(f"\n完成 {len(ok)}/{len(results)}；报告 {raw_root.relative_to(ROOT)}/fetch-report.json")
    if not args.dry_run:
        report["updated"] = now()
        write_report(report)
    return 0 if len(ok) == len([r for r in results if r.get("status") != "gated"]) else 1


if __name__ == "__main__":
    sys.exit(main())
