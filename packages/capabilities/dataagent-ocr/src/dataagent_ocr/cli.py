"""``dataagent-ocr`` command line (driven by the dataagent-ocr SKILL).

Every command prints one JSON object on stdout. Exit codes: 0 ok,
1 failed (verification failed, provider unavailable), 2 usage/config error,
3 needs input (credentials, confirmation, egress decision, switch reason).
Secrets are read from stdin (``--api-key-stdin``) and never echoed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from dataagent_runtime.runtime import resolve_roots

from dataagent_ocr import egress, engines, probe, quality, secrets, verify
from dataagent_ocr.adapter import load_active_engine
from dataagent_ocr.errors import ConfigError, NotConfigured, OcrError
from dataagent_ocr.profiles import (
    CommandConfig,
    EngineConfig,
    OcrProfile,
    OpenAICompatConfig,
    ProfileStore,
    default_deployment,
    sha256_hex,
    validate_profile_id,
)
from dataagent_ocr.providers import build_provider


def _out(payload: dict[str, Any], code: int = 0) -> int:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return code


def _error(exc: OcrError) -> int:
    code = 3 if exc.needs_input else (2 if isinstance(exc, ConfigError) else 1)
    return _out({"status": "needs_input" if exc.needs_input else "failed", "error": exc.to_dict()}, code)


def _root(args) -> Path:
    _, data_root = resolve_roots(None, args.data_root)
    return data_root


def _key_ref(args, data_root: Path, profile_id: str) -> str | None:
    chosen = [bool(args.api_key_stdin), bool(args.api_key_env), bool(args.api_key_keychain), bool(args.no_api_key)]
    if sum(chosen) != 1:
        raise ConfigError(
            "choose exactly one of --api-key-stdin, --api-key-env, --api-key-keychain, --no-api-key"
        )
    if args.no_api_key:
        return None
    if args.api_key_env:
        return secrets.validate_ref(f"env:{args.api_key_env}")
    if args.api_key_keychain:
        return secrets.validate_ref(f"keychain:{args.api_key_keychain}")
    value = sys.stdin.readline()
    return secrets.store_file_secret(data_root, f"ocr-{profile_id}", value)


def _save(store: ProfileStore, profile: OcrProfile) -> int:
    stored, created = store.save(profile)
    return _out(
        {
            "status": "ok",
            "profile": stored.summary(),
            "created_revision": created,
            "next": f"verify --profile {stored.ref}",
        }
    )


def cmd_configure_openai(args) -> int:
    data_root = _root(args)
    store = ProfileStore(data_root)
    pid = validate_profile_id(args.profile)
    key_ref = _key_ref(args, data_root, pid)
    cfg = OpenAICompatConfig(
        base_url=args.base_url,
        model=args.model,
        api_key_ref=key_ref,
        deployment=args.deployment or default_deployment(args.base_url),
        timeout_s=args.timeout,
        max_tokens=args.max_tokens,
        json_mode=not args.no_json_mode,
        logprobs=args.logprobs,
    )
    return _save(store, OcrProfile(profile_id=pid, kind="openai_compat", openai_compat=cfg, note=args.note))


def cmd_set_key(args) -> int:
    data_root = _root(args)
    store = ProfileStore(data_root)
    profile = store.get(validate_profile_id(args.profile))
    if profile.kind != "openai_compat":
        raise ConfigError(f"{profile.ref} is not an openai_compat profile")
    key_ref = _key_ref(args, data_root, profile.profile_id)
    updated = profile.model_copy(
        update={"openai_compat": profile.openai_compat.model_copy(update={"api_key_ref": key_ref})}
    )
    stored, created = store.save(updated)
    store.event("key_set", profile=stored.ref, key_ref=key_ref)
    return _out({"status": "ok", "profile": stored.summary(), "created_revision": created, "next": f"verify --profile {stored.ref}"})


def cmd_configure_engine(args) -> int:
    data_root = _root(args)
    store = ProfileStore(data_root)
    lock = engines.read_lock(data_root, args.engine)
    spec = engines.EngineSpec.model_validate(lock["spec"])
    cfg = EngineConfig(
        engine=args.engine,
        lock_digest=lock["lock_digest"],
        worker_digest=engines.current_worker_digest(data_root, spec),
        lang=args.lang or spec.default_lang,
        timeout_s=args.timeout,
    )
    pid = validate_profile_id(args.profile or args.engine)
    return _save(store, OcrProfile(profile_id=pid, kind="engine", engine=cfg, note=args.note))


def cmd_configure_command(args) -> int:
    data_root = _root(args)
    store = ProfileStore(data_root)
    argv = json.loads(args.argv_json)
    if not isinstance(argv, list) or not all(isinstance(a, str) for a in argv):
        raise ConfigError("--argv-json must be a JSON array of strings")
    adapter_digest = None
    adapter_path = None
    if args.adapter:
        path = Path(args.adapter).resolve()
        adapter_path, adapter_digest = str(path), "sha256:" + sha256_hex(path.read_bytes())
    cfg = CommandConfig(argv=argv, adapter_path=adapter_path, adapter_digest=adapter_digest, timeout_s=args.timeout)
    pid = validate_profile_id(args.profile)
    return _save(store, OcrProfile(profile_id=pid, kind="command", command=cfg, note=args.note))


def _samples(args) -> list[probe.Fixture]:
    if len(args.sample) != len(args.expect):
        raise ConfigError("each --sample needs a matching --expect (text file with the exact expected transcription)")
    out = []
    for image, expected in zip(args.sample, args.expect):
        image_bytes = Path(image).read_bytes()
        out.append(
            probe.Fixture(
                fixture=f"sample:{Path(image).name}",
                image=image_bytes,
                expected=Path(expected).read_text(encoding="utf-8"),
            )
        )
    return out


def cmd_verify(args) -> int:
    data_root = _root(args)
    store = ProfileStore(data_root)
    profile = store.resolve(args.profile)
    samples = _samples(args)
    # Decide the pin policy before calling anything, so a refused switch costs no tokens.
    reason, evidence = (None, None) if args.no_pin else verify.authorize_pin(
        store, profile, reason=args.reason, user_instruction=args.user_instruction
    )
    provider = build_provider(data_root, profile)
    warnings: list[str] = []
    try:
        if samples and provider.remote:
            warnings += egress.check(
                data_root,
                destination=provider.destination(),
                content_refs=[egress.content_ref("sample", s.image) for s in samples],
                decision_ref=args.egress_decision_ref,
            )
        result = verify.run_verification(store, profile, provider, samples)
    finally:
        provider.close()
    payload: dict[str, Any] = {
        "status": "ok" if result.passed else "failed",
        "verification": result.model_dump(mode="json"),
        "warnings": warnings,
    }
    if not samples:
        payload["warnings"].append(
            "only the synthetic English probe was used; verify with a sample from the user's own documents (--sample/--expect)"
        )
    if result.passed and not args.no_pin:
        pinned = verify.pin(store, profile, result, reason=reason, evidence=evidence)
        payload["pinned"] = pinned.model_dump(mode="json")
    elif not result.passed:
        payload["next"] = "show the fixture scores to the user; fix the configuration or choose another provider"
    return _out(payload, 0 if result.passed else 1)


def cmd_status(args) -> int:
    data_root = _root(args)
    store = ProfileStore(data_root)
    payload: dict[str, Any] = {
        "data_root": str(data_root),
        "profiles": [p.summary() for p in store.list_profiles()],
        "engines": engines.installed_engines(data_root),
    }
    try:
        pin, profile, verification = store.load_pinned()
        payload["active"] = {
            **pin.model_dump(mode="json"),
            "profile": profile.summary(),
            "verification": {
                "id": verification.verification_id,
                "at": verification.at,
                "scores": [{"fixture": f.fixture, "score": f.score, "digits_ok": f.digits_ok} for f in verification.fixtures],
                "confidence_source": verification.confidence_source,
                "reported_model": verification.reported_model,
            },
            "quality": quality.evaluate(store, profile).model_dump(mode="json"),
        }
        payload["status"] = "ok"
        return _out(payload)
    except OcrError as exc:
        payload["status"] = "needs_input"
        payload["error"] = exc.to_dict()
        return _out(payload, 3)


def cmd_recognize(args) -> int:
    data_root = _root(args)
    engine = load_active_engine(data_root)
    image = Path(args.image).read_bytes()
    warnings: list[str] = []
    try:
        if engine.remote:
            warnings += egress.check(
                data_root,
                destination=engine.destination(),
                content_refs=[egress.content_ref("image", image)],
                decision_ref=args.egress_decision_ref,
            )
        blocks = engine.recognize(image, lang=args.lang)
    finally:
        engine.close()
    return _out(
        {
            "status": "ok",
            "engine_ref": engine.engine_ref,
            "engine_version": engine.engine_version,
            "confidence_source": engine.last_confidence_source,
            "drift": engine.drift,
            "warnings": warnings,
            "text": "\n".join(b.text for b in blocks),
            "blocks": [b.__dict__ for b in blocks],
        }
    )


def cmd_feedback(args) -> int:
    data_root = _root(args)
    store = ProfileStore(data_root)
    pin, profile, _ = store.load_pinned()
    quality.record_feedback(
        store,
        quality.Feedback(profile=profile.ref, kind=args.kind, pages=args.pages, document=args.document, note=args.note),
    )
    verdict = quality.evaluate(store, profile)
    return _out({"status": "ok", "quality": verdict.model_dump(mode="json")})


def cmd_quality(args) -> int:
    data_root = _root(args)
    store = ProfileStore(data_root)
    _, profile, _ = store.load_pinned()
    verdict = quality.evaluate(store, profile)
    payload = {"status": "ok", "quality": verdict.model_dump(mode="json")}
    if verdict.status == "degraded":
        payload["next"] = (
            "tell the user the evidence and ask whether to choose another OCR provider; "
            "do not switch without the user's approval"
        )
    return _out(payload)


def cmd_engine(args) -> int:
    data_root = _root(args)
    if args.engine_cmd == "list":
        return _out(
            {
                "status": "ok",
                "recipes": {name: {"display_name": s.display_name, "packages": s.packages, "docs": s.docs, "notes": s.notes} for name, s in engines.RECIPES.items()},
                "installed": engines.installed_engines(data_root),
            }
        )
    if args.engine_cmd == "spec":
        spec = engines.EngineSpec.model_validate_json(Path(args.file).read_text(encoding="utf-8"))
        adapter = Path(args.adapter).read_bytes() if args.adapter else None
        path = engines.save_spec(data_root, spec, adapter)
        return _out({"status": "ok", "spec": str(path), "spec_digest": spec.digest(), "next": f"engine plan {spec.name}"})
    spec = engines.load_spec(data_root, args.name)
    if args.engine_cmd == "plan":
        plan = engines.plan_install(data_root, spec)
        payload = {"status": "needs_input", "plan": plan.to_dict(), "spec": spec.model_dump(mode="json")}
        payload["next"] = (
            "show the steps, packages, sources and missing system requirements to the user; "
            f"after approval run: engine install {spec.name} --confirm {plan.plan_digest}"
        )
        return _out(payload, 3)
    lock = engines.install(data_root, spec, confirm=args.confirm)
    return _out(
        {
            "status": "ok",
            "engine": spec.name,
            "lock_digest": lock["lock_digest"],
            "python": lock["python"],
            "packages": lock["freeze"],
            "next": f"configure-engine --engine {spec.name} --profile {spec.name}",
        }
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dataagent-ocr", description=__doc__)
    parser.add_argument("--data-root", help="override DATAAGENT_DATA_ROOT / <workspace>/.dataagent")
    sub = parser.add_subparsers(dest="cmd", required=True)

    def key_options(p):
        p.add_argument("--api-key-stdin", action="store_true", help="read the key from one line of stdin")
        p.add_argument("--api-key-env", metavar="VAR")
        p.add_argument("--api-key-keychain", metavar="SERVICE/ACCOUNT")
        p.add_argument("--no-api-key", action="store_true", help="endpoint without authentication")

    p = sub.add_parser("configure-openai", help="OpenAI-compatible OCR endpoint")
    p.add_argument("--profile", required=True)
    p.add_argument("--base-url", required=True, help="e.g. https://host/v1")
    p.add_argument("--model", required=True)
    p.add_argument("--deployment", choices=["local", "private_cloud", "vendor_api"])
    p.add_argument("--timeout", type=float, default=120.0)
    p.add_argument("--max-tokens", type=int, default=4096)
    p.add_argument("--no-json-mode", action="store_true", help="plain-text transcription (no boxes)")
    p.add_argument("--logprobs", choices=["auto", "on", "off"], default="auto")
    p.add_argument("--note")
    key_options(p)
    p.set_defaults(func=cmd_configure_openai)

    p = sub.add_parser("set-key", help="rotate the api key of an openai_compat profile")
    p.add_argument("--profile", required=True)
    key_options(p)
    p.set_defaults(func=cmd_set_key)

    p = sub.add_parser("configure-engine", help="profile for an installed local engine")
    p.add_argument("--engine", required=True)
    p.add_argument("--profile")
    p.add_argument("--lang")
    p.add_argument("--timeout", type=float, default=300.0)
    p.add_argument("--note")
    p.set_defaults(func=cmd_configure_engine)

    p = sub.add_parser("configure-command", help="profile for a custom worker command")
    p.add_argument("--profile", required=True)
    p.add_argument("--argv-json", required=True)
    p.add_argument("--adapter", help="adapter file whose digest is bound into the profile")
    p.add_argument("--timeout", type=float, default=300.0)
    p.add_argument("--note")
    p.set_defaults(func=cmd_configure_command)

    p = sub.add_parser("verify", help="test call; pins the profile when it passes")
    p.add_argument("--profile", required=True, help="profile id or id@rN")
    p.add_argument("--sample", action="append", default=[], help="user sample image")
    p.add_argument("--expect", action="append", default=[], help="expected transcription text file for the sample")
    p.add_argument("--egress-decision-ref", help="EgressDecision covering the samples (non-local providers)")
    p.add_argument("--reason", choices=["user_request", "quality_degraded"])
    p.add_argument("--user-instruction", help="the user's own words asking to change the OCR model")
    p.add_argument("--no-pin", action="store_true", help="verify only")
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("status")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("recognize", help="run the pinned provider on one image")
    p.add_argument("image")
    p.add_argument("--lang")
    p.add_argument("--egress-decision-ref")
    p.set_defaults(func=cmd_recognize)

    p = sub.add_parser("feedback", help="record review findings about the pinned provider")
    p.add_argument("--kind", required=True, choices=["correction", "missed_text", "garbled", "wrong_digits", "ok"])
    p.add_argument("--pages", type=int, default=1)
    p.add_argument("--document")
    p.add_argument("--note")
    p.set_defaults(func=cmd_feedback)

    p = sub.add_parser("quality", help="evaluate the pinned provider's quality verdict")
    p.set_defaults(func=cmd_quality)

    p = sub.add_parser("engine", help="dependency-based engines")
    esub = p.add_subparsers(dest="engine_cmd", required=True)
    esub.add_parser("list")
    e = esub.add_parser("spec", help="save a researched engine spec")
    e.add_argument("--file", required=True)
    e.add_argument("--adapter")
    e = esub.add_parser("plan")
    e.add_argument("name")
    e = esub.add_parser("install")
    e.add_argument("name")
    e.add_argument("--confirm", required=True, help="plan_digest the user approved")
    p.set_defaults(func=cmd_engine)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except OcrError as exc:
        return _error(exc)
    except (ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
        return _out({"status": "failed", "error": {"code": "ocr.usage", "message": f"{type(exc).__name__}: {exc}"}}, 2)


if __name__ == "__main__":
    sys.exit(main())
