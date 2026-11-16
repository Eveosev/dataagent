"""Build a provider from a stored profile, checking every binding first."""

from __future__ import annotations

from pathlib import Path

from dataagent_ocr import engines, secrets
from dataagent_ocr.errors import PinMismatch
from dataagent_ocr.profiles import OcrProfile, sha256_hex
from dataagent_ocr.providers.openai_compat import OpenAICompatProvider
from dataagent_ocr.providers.worker import WorkerClient, WorkerProvider
from dataagent_ocr.types import OcrProvider


def build_provider(data_root: Path, profile: OcrProfile, **openai_kwargs) -> OcrProvider:
    data_root = Path(data_root)
    tag = f"{profile.ref}:{profile.config_digest()[7:19]}"
    if profile.kind == "openai_compat":
        cfg = profile.openai_compat
        key = secrets.resolve(cfg.api_key_ref, data_root) if cfg.api_key_ref else None
        return OpenAICompatProvider(profile, key, **openai_kwargs)
    if profile.kind == "engine":
        cfg = profile.engine
        lock = engines.read_lock(data_root, cfg.engine)
        if lock["lock_digest"] != cfg.lock_digest:
            raise PinMismatch(
                f"engine {cfg.engine} was reinstalled after the profile was created",
                action="configure the engine profile again and verify",
            )
        spec = engines.EngineSpec.model_validate(lock["spec"])
        if engines.current_worker_digest(data_root, spec) != cfg.worker_digest:
            raise PinMismatch(f"worker for {cfg.engine} changed", action="reinstall or reconfigure, then verify")
        client = WorkerClient(
            engines.worker_argv(data_root, spec, lang=cfg.lang or spec.default_lang),
            cwd=engines.engine_dir(data_root, cfg.engine),
            timeout_s=cfg.timeout_s,
        )
        return WorkerProvider(client, engine_ref=f"engine:{cfg.engine}", version_tag=tag, lang=cfg.lang)
    cfg = profile.command
    if cfg.adapter_path:
        path = Path(cfg.adapter_path)
        if not path.is_file() or "sha256:" + sha256_hex(path.read_bytes()) != cfg.adapter_digest:
            raise PinMismatch(f"adapter {cfg.adapter_path} changed or is missing", action="reconfigure and verify")
    client = WorkerClient(list(cfg.argv), timeout_s=cfg.timeout_s)
    return WorkerProvider(client, engine_ref=f"command:{profile.profile_id}", version_tag=tag)


__all__ = ["build_provider", "OpenAICompatProvider", "WorkerClient", "WorkerProvider"]
