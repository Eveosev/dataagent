from __future__ import annotations

import os
import stat

import pytest

from dataagent_runtime.policy import secrets


def test_file_ref_roundtrip_keeps_directory_and_file_private(tmp_path):
    ref = secrets.store_file_secret(tmp_path, "ocr/rest-token", "  sentinel-value  \n")
    assert ref == "file:ocr/rest-token"
    path = tmp_path / "secrets" / "ocr" / "rest-token.key"
    assert path.read_text() == "sentinel-value"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE((tmp_path / "secrets").stat().st_mode) == 0o700
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert secrets.resolve(ref, tmp_path) == "sentinel-value"


def test_env_and_keychain_refs_are_logical_names(tmp_path, monkeypatch):
    monkeypatch.setenv("T14_TOKEN", "env-value")
    assert secrets.resolve("env:T14_TOKEN", tmp_path) == "env-value"
    monkeypatch.delenv("T14_TOKEN")
    with pytest.raises(secrets.SecretUnavailable, match="T14_TOKEN"):
        secrets.resolve("env:T14_TOKEN", tmp_path)

    class Result:
        returncode = 0
        stdout = "keychain-value\n"

    monkeypatch.setattr(secrets.subprocess, "run", lambda *a, **k: Result())
    assert secrets.resolve("keychain:svc/account", tmp_path) == "keychain-value"


@pytest.mark.parametrize(
    "ref",
    [
        "plain:secret",
        "file:../outside",
        "file:/etc/passwd",
        "file:",
        "env:not-a-name",
        "keychain:no-slash",
        "keychain:service/account/extra",
        "sentinel-value",
    ],
)
def test_unsupported_references_do_not_echo_the_value(ref):
    with pytest.raises(secrets.InvalidSecretRef) as exc:
        secrets.validate_ref(ref)
    assert "sentinel-value" not in str(exc.value)


def test_file_ref_cannot_escape_secrets_directory(tmp_path):
    outside = tmp_path / "outside.key"
    outside.write_text("outside-value")
    os.chmod(outside, 0o600)
    base = tmp_path / "secrets"
    base.mkdir()
    os.chmod(base, 0o700)
    (base / "link.key").symlink_to(outside)
    with pytest.raises(secrets.SecretUnavailable, match="outside"):
        secrets.resolve("file:link", tmp_path)


def test_secrets_directory_symlink_is_rejected(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    os.chmod(outside, 0o700)
    (outside / "token.key").write_text("outside-value")
    os.chmod(outside / "token.key", 0o600)
    (root / "secrets").symlink_to(outside)
    with pytest.raises(secrets.SecretUnavailable, match="symlink"):
        secrets.resolve("file:token", root)
    with pytest.raises(secrets.SecretUnavailable, match="symlink"):
        secrets.store_file_secret(root, "other", "value")


def test_file_and_directory_permissions_are_enforced(tmp_path):
    ref = secrets.store_file_secret(tmp_path, "token", "value")
    path = tmp_path / "secrets" / "token.key"
    os.chmod(path, 0o644)
    with pytest.raises(secrets.SecretUnavailable, match="readable by other users"):
        secrets.resolve(ref, tmp_path)
    os.chmod(path, 0o600)
    os.chmod(tmp_path / "secrets", 0o755)
    with pytest.raises(secrets.SecretUnavailable, match="directory"):
        secrets.resolve(ref, tmp_path)


def test_missing_empty_and_redact(tmp_path):
    with pytest.raises(secrets.SecretUnavailable, match="missing"):
        secrets.resolve("file:absent", tmp_path)
    with pytest.raises(secrets.SecretUnavailable, match="empty"):
        secrets.store_file_secret(tmp_path, "empty", "   ")
    assert secrets.redact("before sentinel after", "sentinel") == "before *** after"
    assert secrets.redact("nothing", None) == "nothing"
