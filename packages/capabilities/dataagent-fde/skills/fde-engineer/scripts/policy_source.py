"""Read a selected policy and check exact citations against the same file revision."""

import argparse
import hashlib
import json
import sys
from pathlib import Path


class SourceError(ValueError):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def load_source(path, expected_digest):
    if path.suffix.lower() not in {".md", ".markdown", ".txt"}:
        raise SourceError("unsupported", "请用宿主的原生阅读工具打开此格式。")
    try:
        if not path.is_file():
            raise SourceError("unreadable", "找不到可读的普通文件，请核对附件或路径。")
        raw = path.read_bytes()
    except OSError as exc:
        raise SourceError("unreadable", str(exc)) from exc
    digest = hashlib.sha256(raw).hexdigest()
    if expected_digest is not None and expected_digest != digest:
        raise SourceError("source_changed", "这份文件与提取时的版本不同，请重新读取并核对引文。")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise SourceError("unsupported", "文件不是 UTF-8 文本，请用宿主阅读工具打开。") from exc
    if "\x00" in text:
        raise SourceError("unsupported", "文件含二进制内容，请用宿主阅读工具打开。")
    if not text.strip():
        raise SourceError("empty_source", "文件里没有可提取的正文。")
    return digest, text.splitlines()


def read(args):
    paths = list(dict.fromkeys(args.sources))
    if not paths:
        return {"status": "need_source"}
    if len(paths) > 1:
        return {"status": "choose_source", "choices": [str(path) for path in paths]}
    if args.start_line < 1 or args.limit < 1:
        raise SourceError("invalid_request", "起始行和每页行数须为正整数。")
    if args.start_line > 1 and not args.digest:
        raise SourceError("invalid_request", "请用首页的 digest 续读。")
    path = paths[0]
    digest, lines = load_source(path, args.digest)
    if args.start_line > len(lines):
        raise SourceError("invalid_request", "起始行超出原文范围。")
    end = min(args.start_line - 1 + args.limit, len(lines))
    return {
        "status": "ready", "source": str(path), "digest": digest, "total_lines": len(lines),
        "lines": [{"number": i, "text": lines[i - 1]} for i in range(args.start_line, end + 1)],
        "next_line": end + 1 if end < len(lines) else None,
    }


def read_evidence(stream):
    try:
        items = json.load(stream)
    except (ValueError, UnicodeError) as exc:
        raise SourceError("invalid_request", "引文必须是 JSON 数组。") from exc
    if not isinstance(items, list) or not items:
        raise SourceError("invalid_request", "至少需要一条引文。")
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            raise SourceError("invalid_request", "引文必须含 id、line、quote。")
        key, line, quote = (item.get(field) for field in ("id", "line", "quote"))
        if not isinstance(key, str) or not key.strip() or key in seen:
            raise SourceError("invalid_request", "每段引文需要唯一的非空 id。")
        if type(line) is not int or line < 1:
            raise SourceError("invalid_request", "line 必须是从 1 开始的行号。")
        if not isinstance(quote, str) or not quote.strip() or quote.startswith("\n") or quote.endswith("\n"):
            raise SourceError("invalid_request", "quote 必须包含非空原文且首尾无换行。")
        seen.add(key)
    return items


def verify(args):
    digest, lines = load_source(args.source, args.digest)
    verified, unresolved = [], []
    for item in read_evidence(sys.stdin):
        start, quote = item["line"], item["quote"]
        end = start + quote.count("\n")
        if end <= len(lines) and quote in "\n".join(lines[start - 1:end]):
            verified.append({"id": item["id"], "line": start, "end_line": end, "quote": quote})
        else:
            unresolved.append({"id": item["id"], "line": start, "reason": "所选版本的指定位置没有这段引文。"})
    return {
        "status": "needs_review" if unresolved else "verified",
        "source": str(args.source), "digest": digest, "verified": verified, "unresolved": unresolved,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    reader = commands.add_parser("read", help="Choose a source or read its numbered lines")
    reader.add_argument("sources", nargs="*", type=Path)
    reader.add_argument("--start-line", type=int, default=1)
    reader.add_argument("--limit", type=int, default=80)
    reader.add_argument("--digest", help="Digest returned by the first read")
    checker = commands.add_parser("verify", help="Check JSON citations from stdin")
    checker.add_argument("source", type=Path)
    checker.add_argument("--digest", required=True)
    args = parser.parse_args()
    try:
        result = read(args) if args.command == "read" else verify(args)
    except SourceError as exc:
        result = {"status": exc.status, "message": str(exc)}
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] in {"ready", "need_source", "choose_source", "verified"} else 1


if __name__ == "__main__":
    sys.exit(main())
