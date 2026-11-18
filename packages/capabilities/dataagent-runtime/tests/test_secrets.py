from __future__ import annotations

import os
import stat
import warnings

import pytest

from dataagent_runtime.policy import secrets


@pytest.fixture()
def home(tmp_path, monkeypatch):
    path = tmp_path / "home"
    path.mkdir()
    monkeypatch.setenv("HOME", str(path))
    monkeypatch.delenv("DATAAGENT_SECRETS_DIR", raising=False)
    return path


@pytest.fixture()
def data_root(tmp_path):
    return tmp_path / "workspace" / ".dataagent"


def test_default_file_ref_is_outside_the_workspace(home, data_root):
    ref = secrets.store_file_secret(None, "ocr/rest-token", "  sentinel-value  \n")
    assert ref == "file:ocr/rest-token"
    assert secrets.secrets_dir() == home / ".dataagent" / "secrets"
    path = home / ".dataagent" / "secrets" / "ocr" / "rest-token.key"
    assert path.read_text() == "sentinel-value"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(path.parent.parent.stat().st_mode) == 0o700
    assert secrets.resolve(ref) == "sentinel-value"


def test_store_default_secret_is_the_external_location(home):
    ref = secrets.store_default_secret("rest-token", "value")
    assert ref == "file:rest-token"
    assert (home / ".dataagent" / "secrets" / "rest-token.key").is_file()
    assert not (home / ".dataagent" / "secrets" / "rest-token.key").is_symlink()


def test_legacy_workspace_secret_still_resolves_with_warning(home, data_root):
    ref = secrets.store_file_secret(
        data_root, "rest-token", "legacy-value", scope="workspace"
    )
    path = data_root / "secrets" / "rest-token.key"
    assert path.read_text() == "legacy-value"
    with pytest.warns(secrets.LegacySecretLocationWarning, match="legacy"):
        assert secrets.resolve(ref, data_root) == "legacy-value"
    assert not (home / ".dataagent" / "secrets" / "rest-token.key").exists()


def test_external_default_wins_over_the_legacy_workspace_copy(home, data_root):
    secrets.store_file_secret(
        data_root, "rest-token", "legacy-value", scope="workspace"
    )
    secrets.store_default_secret("rest-token", "external-value")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assert secrets.resolve("file:rest-token", data_root) == "external-value"
    assert not [
        warning
        for warning in caught
        if issubclass(warning.category, secrets.LegacySecretLocationWarning)
    ]


@pytest.mark.parametrize("root_name", [".dataagent", "custom-data", "workspace"])
def test_any_data_root_defaults_outside(home, tmp_path, root_name):
    root = tmp_path / "workspace" / root_name
    root.mkdir(parents=True)
    ref = secrets.store_file_secret(root, "token", "value")
    assert (home / ".dataagent" / "secrets" / "token.key").is_file()
    assert not (root / "secrets").exists()
    assert secrets.resolve(ref, root) == "value"


def test_secrets_dir_always_means_the_default_directory(home, data_root):
    assert secrets.secrets_dir() == home / ".dataagent" / "secrets"
    assert secrets.secrets_dir(data_root) == home / ".dataagent" / "secrets"
    assert (
        secrets.workspace_secrets_dir(data_root)
        == data_root / "secrets"
    )


def test_workspace_scope_is_explicit_and_requires_a_root(home, data_root):
    ref = secrets.store_file_secret(
        data_root, "token", "value", scope="workspace"
    )
    assert (data_root / "secrets" / "token.key").is_file()
    with pytest.raises(secrets.InvalidSecretRef, match="data_root"):
        secrets.store_file_secret(None, "token", "value", scope="workspace")
    with pytest.raises(secrets.InvalidSecretRef, match="scope"):
        secrets.store_file_secret(None, "token", "value", scope="elsewhere")


def test_env_and_keychain_refs_are_logical_names(home, data_root, monkeypatch):
    monkeypatch.setenv("T14_TOKEN", "env-value")
    assert secrets.resolve("env:T14_TOKEN", data_root) == "env-value"
    monkeypatch.delenv("T14_TOKEN")
    with pytest.raises(secrets.SecretUnavailable, match="T14_TOKEN"):
        secrets.resolve("env:T14_TOKEN", data_root)

    class Result:
        returncode = 0
        stdout = "keychain-value\n"

    monkeypatch.setattr(secrets.subprocess, "run", lambda *a, **k: Result())
    assert secrets.resolve("keychain:svc/account", data_root) == "keychain-value"


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
    assert "keychain:" in (exc.value.action or "")


def test_file_ref_cannot_escape_the_default_secrets_directory(home):
    outside = home / "outside.key"
    outside.write_text("outside-value")
    os.chmod(outside, 0o600)
    base = home / ".dataagent" / "secrets"
    base.mkdir(parents=True)
    os.chmod(base, 0o700)
    (base / "link.key").symlink_to(outside)
    assert base.resolve() == base
    with pytest.raises(secrets.SecretUnavailable, match="outside"):
        secrets.resolve("file:link")


def test_legacy_secrets_directory_symlink_is_rejected(home, data_root):
    outside = home / "outside"
    outside.mkdir()
    os.chmod(outside, 0o700)
    (outside / "token.key").write_text("outside-value")
    os.chmod(outside / "token.key", 0o600)
    data_root.mkdir(parents=True)
    (data_root / "secrets").symlink_to(outside)
    with pytest.raises(secrets.SecretUnavailable, match="symlink"):
        secrets.resolve("file:token", data_root)
    with pytest.raises(secrets.SecretUnavailable, match="symlink"):
        secrets.store_file_secret(data_root, "other", "value", scope="workspace")


def test_file_and_directory_permissions_are_enforced(home):
    ref = secrets.store_default_secret("token", "value")
    path = home / ".dataagent" / "secrets" / "token.key"
    os.chmod(path, 0o644)
    with pytest.raises(secrets.SecretUnavailable, match="readable by other users"):
        secrets.resolve(ref)
    os.chmod(path, 0o600)
    os.chmod(home / ".dataagent" / "secrets", 0o755)
    with pytest.raises(secrets.SecretUnavailable, match="directory"):
        secrets.resolve(ref)


def test_missing_empty_and_redact(home, data_root):
    with pytest.raises(secrets.SecretUnavailable, match="missing") as exc:
        secrets.resolve("file:absent", data_root)
    assert "keychain:" in (exc.value.action or "")
    with pytest.raises(secrets.SecretUnavailable, match="empty"):
        secrets.store_default_secret("empty", "   ")
    assert secrets.redact("before sentinel after", "sentinel") == "before *** after"
    assert secrets.redact("nothing", None) == "nothing"
