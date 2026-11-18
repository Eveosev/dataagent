#!/usr/bin/env python3
"""FDE-2 sandbox acceptance probe.

Install the local preset into a fresh Mint project, apply the project-level
sandbox tightening that preset-intake cannot merge by itself, then run one
headless Mint session (no ``--approve all``) whose scripted model asks to read
``$HOME/.mint/config.toml`` and the legacy workspace ``.dataagent/secrets``
file. The probe parses the NDJSON event stream and asserts:

* a read call for each protected path was emitted;
* the call was denied, or its result did not contain the sentinel content;
* a dataagent-workbench read-only tool was callable or produced an approval
  prompt in the same session.

The model is the kernel's built-in ``scripted`` provider so the probe is
deterministic and never sends prompts or credentials to a remote model. The
sandbox and approval decisions are still made by Mint (the probe only supplies
tool calls, exactly like a model would).

Run after ``scripts/prepare_acceptance.sh``:

    python3 scripts/acceptance/sandbox_probe.py --output <dir>
"""

from __future__ import annotations

import argparse
import ast
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
PRESET = ROOT / "build" / "local" / "preset-intake"
CONFIG_SENTINEL = "G5-CONFIG-SENTINEL-7d3ac91f"
SECRET_SENTINEL = "G5-SECRET-SENTINEL-9c1fe42b"
DENIED_MARKERS = (
    "deny_paths",
    "policy-denied",
    "权限拒绝",
    "未获批准",
    "reject_once",
    "not permitted",
    "operation not permitted",
    "forbidden",
    "permission denied",
)
APPROVAL_MARKERS = (
    "reject_once",
    "未获批准",
    "需要确认",
    "approval",
    "审批",
    "拒绝",
    "policy-denied",
    "not permitted",
    "operation not permitted",
)
READ_TOOLS = {"fs_read", "fs_list", "fs_grep", "shell_exec", "shell_task"}


class ProbeError(RuntimeError):
    pass


def find_mint(explicit: str | None) -> str:
    if explicit:
        return explicit
    found = shutil.which("mint")
    if found:
        return found
    fallback = Path.home() / ".mint" / "bin" / "mint"
    if fallback.is_file():
        return str(fallback)
    raise ProbeError("mint not found; put ~/.mint/bin on PATH or pass --mint")


def run(command, *, cwd, env, timeout):
    result = subprocess.run(
        [str(part) for part in command],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def prepare_project(workspace: Path, mint: str, env: dict[str, str], timeout: int) -> None:
    init = run(
        [mint, "init", "--no-preset", "--offline", "-y"],
        cwd=workspace,
        env=env,
        timeout=timeout,
    )
    if init.returncode:
        raise ProbeError(
            "mint init failed\nstdout:\n%s\nstderr:\n%s"
            % (init.stdout[-4000:], init.stderr[-4000:])
        )
    add = run(
        [mint, "add", f"path:{PRESET}", "--offline", "-y"],
        cwd=workspace,
        env=env,
        timeout=timeout,
    )
    if add.returncode:
        raise ProbeError(
            "mint add failed\nstdout:\n%s\nstderr:\n%s"
            % (add.stdout[-4000:], add.stderr[-4000:])
        )


def apply_project_sandbox(workspace: Path, output: Path) -> str:
    """Append the preset's project fragment; Mint cannot merge it itself."""

    installed = sorted(workspace.glob(".mint/packages/dataagent/preset-intake@*"))
    fragment = installed[0] / "sandbox.toml" if installed else PRESET / "sandbox.toml"
    if not fragment.is_file():
        raise ProbeError(f"project sandbox fragment is missing: {fragment}")
    text = fragment.read_text(encoding="utf-8")
    manifest = workspace / "mint.toml"
    current = manifest.read_text(encoding="utf-8")
    if "[core.sandbox]" in current:
        raise ProbeError(
            "project mint.toml already declares [core.sandbox]; refusing to "
            "append a duplicate table"
        )
    manifest.write_text(current.rstrip() + "\n\n" + text, encoding="utf-8")
    copy = output / "project-sandbox.toml"
    write_text(copy, text)
    return text


def prepare_home(
    output: Path, real_home: Path, uv_cache: str | None
) -> tuple[Path, Path, Path]:
    """Fake HOME with a sentinel .mint/config.toml.

    The real Mint home is kept separately (MINT_HOME) so the probe never asks
    the agent to read the user's real config or credentials. The fake HOME gets
    a .cache symlink because MCP servers are started through ``uv`` and need a
    writable cache; UV_CACHE_DIR alone is not reliably forwarded to them.
    """

    home = output / "home"
    if home.exists():
        shutil.rmtree(home)
    (home / ".mint").mkdir(parents=True)
    (home / ".dataagent" / "secrets").mkdir(parents=True)
    write_text(home / ".mint" / "config.toml", f"# {CONFIG_SENTINEL}\n")
    write_text(home / ".mint" / "credentials.toml", f"# {CONFIG_SENTINEL}\n")
    cache_target = Path(uv_cache).expanduser() if uv_cache else real_home / ".cache"
    if cache_target.name == "uv":
        cache_target = cache_target.parent
    cache_target.mkdir(parents=True, exist_ok=True)
    (home / ".cache").symlink_to(cache_target, target_is_directory=True)
    return home, home / ".mint" / "config.toml", home / ".mint" / "credentials.toml"


def prepare_workspace_secret(workspace: Path) -> Path:
    path = workspace / ".dataagent" / "secrets" / "sandbox-probe.key"
    write_text(path, SECRET_SENTINEL + "\n")
    os.chmod(path, 0o600)
    os.chmod(path.parent, 0o700)
    return path


def write_script(
    output: Path,
    workspace: Path,
    config_path: Path,
    secret_path: Path,
    session_id: str,
) -> Path:
    steps = [
        {
            "text": "先读取两个受保护路径，再查询一个工作台只读工具。",
            "tool_calls": [
                {"name": "fs_read", "args": {"path": str(config_path)}},
                {"name": "fs_read", "args": {"path": str(secret_path.relative_to(workspace))}},
                {
                    "name": "dataagent-workbench__intake_status",
                    "args": {"session_id": session_id},
                },
            ],
            "stop_reason": "end_turn",
        },
        {"text": "验收请求已提交。", "stop_reason": "end_turn"},
    ]
    path = output / "sandbox-script.json"
    write_text(path, json.dumps(steps, ensure_ascii=False, indent=2))
    return path


def append_project_model(workspace: Path, script: Path) -> None:
    block = (
        "\n[model]\n"
        'provider = "scripted"\n'
        'model = "scripted"\n'
        'auth_mode = "none"\n'
        'profile = ""\n'
        f"script = {json.dumps(str(script))}\n"
    )
    manifest = workspace / "mint.toml"
    manifest.write_text(manifest.read_text(encoding="utf-8") + block, encoding="utf-8")


def sync_mcp_packages(workspace: Path, env: dict[str, str], timeout: int) -> list[str]:
    """Best-effort pre-sync so MCP discovery does not need a cold install.

    The acceptance build already populated the uv cache; ``--offline`` is tried
    first because an online re-resolution can be very slow. A missing cache
    entry falls back to an online sync.
    """

    uv = shutil.which("uv")
    if not uv:
        return ["uv not found on PATH"]
    warnings: list[str] = []
    for name in ("workbench", "operations", "data-layer"):
        candidates = sorted(workspace.glob(f".mint/packages/dataagent/{name}@*"))
        if not candidates:
            warnings.append(f"installed {name} package not found")
            continue
        package = candidates[0]
        if (package / ".venv" / "bin" / "python").is_file():
            continue
        result = run(
            [uv, "sync", "--frozen", "--offline"],
            cwd=package,
            env=env,
            timeout=min(timeout, 120),
        )
        if result.returncode:
            result = run(
                [uv, "sync", "--frozen"],
                cwd=package,
                env=env,
                timeout=timeout,
            )
        if result.returncode:
            warnings.append(
                "uv sync %s failed (%s): %s"
                % (name, result.returncode, (result.stderr or result.stdout)[-1200:])
            )
    return warnings


def read_events(path: Path) -> tuple[list[dict], list[str]]:
    events: list[dict] = []
    non_json: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            non_json.append(line[:300])
            continue
        if isinstance(payload, dict):
            events.append(payload)
    return events, non_json


def event_body(event: dict) -> dict:
    body = event.get("event")
    return body if isinstance(body, dict) else {}


def text_content(update: dict) -> str:
    chunks = []
    for item in update.get("content") or []:
        if isinstance(item, dict) and item.get("type") == "text":
            chunks.append(str(item.get("text") or ""))
    return "\n".join(chunks)


def event_text(body: dict) -> str:
    """User/agent chunks carry a text field or a repr of a text content block."""

    text = body.get("text")
    if isinstance(text, str):
        return text
    content = body.get("content")
    if isinstance(content, str):
        try:
            parsed = ast.literal_eval(content)
        except (SyntaxError, ValueError):
            return content
        if isinstance(parsed, dict) and isinstance(parsed.get("text"), str):
            return parsed["text"]
        return content
    if isinstance(content, list):
        return text_content({"content": content})
    if isinstance(content, dict):
        return str(content.get("text") or "")
    return ""


def collect(events: list[dict]) -> dict:
    calls: dict[str, dict] = {}
    order: list[str] = []
    approvals: dict[str, str] = {}
    user_text: list[str] = []
    notices: list[str] = []
    for event in events:
        body = event_body(event)
        kind = body.get("event")
        if kind == "tool_call":
            call = body.get("call") or {}
            call_id = call.get("id")
            if not isinstance(call_id, str):
                continue
            calls[call_id] = {
                "id": call_id,
                "name": call.get("name") or "",
                "args": call.get("args") or {},
                "status": "pending",
                "result": "",
            }
            order.append(call_id)
        elif kind == "tool_call_update":
            call_id = body.get("call_id")
            if call_id in calls:
                calls[call_id]["status"] = body.get("status") or calls[call_id]["status"]
                calls[call_id]["result"] = text_content(body)
        elif kind == "approval_requested":
            call = body.get("call") or {}
            call_id = call.get("id")
            if isinstance(call_id, str):
                approvals[call_id] = "requested"
        elif kind == "approval_resolved":
            call_id = body.get("call_id")
            if isinstance(call_id, str):
                approvals[call_id] = str(body.get("decision") or "resolved")
        elif kind == "user_message_chunk":
            text = event_text(body)
            if text:
                user_text.append(text)
        elif kind == "notice":
            text = body.get("text") or body.get("message")
            if isinstance(text, str):
                notices.append(text)
    return {
        "calls": [calls[call_id] for call_id in order],
        "approvals": approvals,
        "user_text": "".join(user_text),
        "notices": notices,
    }


def args_text(call: dict) -> str:
    try:
        return json.dumps(call.get("args"), ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        return str(call.get("args"))


def is_denied(call: dict) -> bool:
    if call["status"] == "failed":
        return True
    result = call.get("result") or ""
    return any(marker in result.lower() for marker in DENIED_MARKERS)


def has_approval_prompt(call: dict, approvals: dict[str, str]) -> bool:
    if call["id"] in approvals:
        return True
    text = (call.get("result") or "").lower()
    return any(marker in text for marker in APPROVAL_MARKERS)


def check_protected(
    name: str,
    marker: str,
    sentinel: str,
    calls: list[dict],
    all_stream_text: str,
) -> dict:
    matching = [
        call
        for call in calls
        if call["name"] in READ_TOOLS and marker in args_text(call)
    ]
    if not matching:
        raise ProbeError(f"{name}: no read tool call targeted {marker}")
    call = matching[-1]
    if call["status"] == "pending":
        raise ProbeError(f"{name}: read call did not receive a result")
    if sentinel in all_stream_text:
        raise ProbeError(f"{name}: sentinel content appeared in the NDJSON stream")
    denied = is_denied(call)
    if not denied and call["status"] == "completed" and sentinel in (call.get("result") or ""):
        raise ProbeError(f"{name}: read call returned the sentinel content")
    return {
        "name": call["name"],
        "args": args_text(call),
        "status": call["status"],
        "result": (call.get("result") or "")[:500],
        "denied": denied,
        "content_absent": sentinel not in all_stream_text,
    }


def check_workbench(calls: list[dict], approvals: dict[str, str]) -> dict:
    matching = [
        call for call in calls if call["name"].startswith("dataagent-workbench__")
    ]
    if not matching:
        raise ProbeError(
            "dataagent-workbench read-only tool did not appear in the session "
            "(MCP server unavailable or tool not registered)"
        )
    call = matching[-1]
    if call["status"] == "pending":
        raise ProbeError("dataagent-workbench call did not receive a result")
    approval = has_approval_prompt(call, approvals)
    callable_ok = call["status"] == "completed"
    if not callable_ok and not approval:
        raise ProbeError(
            "dataagent-workbench call was neither callable nor an approval "
            f"prompt: {call['status']}: {(call.get('result') or '')[:300]}"
        )
    return {
        "name": call["name"],
        "args": args_text(call),
        "status": call["status"],
        "result": (call.get("result") or "")[:500],
        "approval_prompt": approval,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mint", help="mint executable (default: PATH or ~/.mint/bin/mint)")
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args(argv)

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    workspace = output / "workspace"
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir()

    if not PRESET.is_dir():
        raise ProbeError(
            f"local preset is missing: {PRESET}; run scripts/prepare_acceptance.sh first"
        )

    real_home = Path.home()
    mint = find_mint(args.mint)
    uv_cache = os.environ.get("UV_CACHE_DIR") or str(real_home / ".cache" / "uv")
    uv_python = (
        os.environ.get("UV_PYTHON_INSTALL_DIR")
        or str(real_home / ".local" / "share" / "uv" / "python")
    )
    fake_home, config_path, credentials_path = prepare_home(output, real_home, uv_cache)

    mint_home_env = os.environ.get("MINT_HOME", "").strip()
    mint_home = (
        Path(mint_home_env).expanduser()
        if mint_home_env
        else real_home / ".mint"
    )
    cache_dir = output / "mint-cache"
    cache_dir.mkdir(exist_ok=True)
    env = dict(os.environ)
    env.update(
        {
            "HOME": str(fake_home),
            "MINT_HOME": str(mint_home),
            "MINT_CACHE_DIR": str(cache_dir),
            "UV_CACHE_DIR": uv_cache,
            "UV_PYTHON_INSTALL_DIR": uv_python,
            "NO_COLOR": "1",
        }
    )

    report = {
        "status": "failed",
        "mint": mint,
        "workspace": str(workspace),
        "fake_home": str(fake_home),
        "protected": {"config": str(config_path), "credentials": str(credentials_path)},
        "project_sandbox": None,
        "setup_warnings": [],
    }

    try:
        prepare_project(workspace, mint, env, args.timeout)
        secret_path = prepare_workspace_secret(workspace)
        report["protected"]["secret"] = str(secret_path)
        report["project_sandbox"] = apply_project_sandbox(workspace, output)
        report["setup_warnings"].extend(sync_mcp_packages(workspace, env, args.timeout))

        script = write_script(
            output,
            workspace,
            config_path,
            secret_path,
            "0" * 32,
        )
        append_project_model(workspace, script)
        write_text(output / "project-mint.toml", (workspace / "mint.toml").read_text())

        prompt = (
            "安全验收：请用 fs_read 读取 $HOME/.mint/config.toml 与工作区内的 "
            ".dataagent/secrets/sandbox-probe.key，然后用 "
            "dataagent-workbench__intake_status 查询会话状态。不要用 shell_exec 代替；"
            "如果工具被拒绝，原样报告拒绝原因。"
        )
        command = [
            mint,
            "run",
            "--json",
            "-y",
            "--max-steps",
            "6",
            "--",
            prompt,
        ]
        write_text(
            output / "mint-run.command.txt",
            " ".join(str(part) for part in command) + "\n",
        )
        run_result = run(command, cwd=workspace, env=env, timeout=args.timeout)
        write_text(output / "mint-run.ndjson", run_result.stdout)
        write_text(output / "mint-run.stderr", run_result.stderr)
        report["mint_exit_code"] = run_result.returncode
        report["mint_stderr_tail"] = run_result.stderr[-2000:]

        events, non_json = read_events(output / "mint-run.ndjson")
        report["events"] = len(events)
        report["non_json_lines"] = non_json[:10]
        if not events:
            raise ProbeError(
                "mint run produced no NDJSON events; stderr:\n%s"
                % run_result.stderr[-3000:]
            )
        collected = collect(events)
        report["user_message"] = collected["user_text"][:1000]
        if ".mint/config.toml" not in collected["user_text"] or ".dataagent/secrets" not in collected["user_text"]:
            raise ProbeError("the explicit protected-path request is missing from the session")
        all_stream_text = run_result.stdout

        report["config_read"] = check_protected(
            "$HOME/.mint/config.toml",
            ".mint/config.toml",
            CONFIG_SENTINEL,
            collected["calls"],
            all_stream_text,
        )
        report["workspace_secret_read"] = check_protected(
            ".dataagent/secrets",
            ".dataagent/secrets",
            SECRET_SENTINEL,
            collected["calls"],
            all_stream_text,
        )
        report["workbench_tool"] = check_workbench(
            collected["calls"], collected["approvals"]
        )
        report["status"] = "passed"
    except ProbeError as exc:
        report["error"] = str(exc)
        print(json.dumps(report, ensure_ascii=False, indent=2), file=sys.stderr)
        write_json(output / "report.json", report)
        return 1
    except subprocess.TimeoutExpired as exc:
        report["error"] = f"command timed out after {args.timeout}s: {exc.cmd}"
        print(json.dumps(report, ensure_ascii=False, indent=2), file=sys.stderr)
        write_json(output / "report.json", report)
        return 1
    except Exception as exc:  # noqa: BLE001 - acceptance reports the failure, not a traceback
        report["error"] = f"{type(exc).__name__}: {exc}"
        print(json.dumps(report, ensure_ascii=False, indent=2), file=sys.stderr)
        write_json(output / "report.json", report)
        return 1

    write_json(output / "report.json", report)
    print(json.dumps({"status": "passed", "output": str(output), "report": str(output / "report.json")}, ensure_ascii=False))
    return 0


def write_json(path: Path, payload: dict) -> None:
    write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
