"""The probe CLI resolves logical credential names in its own process."""

import pytest

from dataagent_contracts.intake import CoverageGap, SourceProfile, SourceSelection
from dataagent_data.observation import cli
from dataagent_runtime.policy import secrets

SENTINEL = "T14-SENTINEL-5f0c9a7d2b8e4c61"


@pytest.fixture()
def home(tmp_path, monkeypatch):
    """An isolated HOME so default file: secrets never touch the real one."""

    path = tmp_path / "home"
    path.mkdir()
    monkeypatch.setenv("HOME", str(path))
    monkeypatch.delenv("DATAAGENT_SECRETS_DIR", raising=False)
    return path


def _rest():
    return SourceSelection(source_id="api", kind="rest", locator_ref="http://127.0.0.1:9/invoices")


def _profile(*, gaps=(), issues=()):
    return SourceProfile(
        source_id="api", source_revision="sha256:" + "0" * 64, kind="rest",
        records=[{"/id": 1}], fields=["/id"], anchors={}, total_partitions=1,
        completed_partitions=[] if gaps else [1], gaps=list(gaps), issues=list(issues),
        metadata={"structure_fingerprint": "sha256:" + "1" * 64},
    )


def test_file_reference_is_resolved_only_inside_probe(workspace, ctx, home, monkeypatch):
    ref = secrets.store_file_secret(workspace / ".dataagent", "rest-token", SENTINEL)
    assert (home / ".dataagent" / "secrets" / "rest-token.key").is_file()
    seen = {}

    def fake_probe(selection, ctx, **options):
        seen.update(options)
        return _profile()

    monkeypatch.setattr("dataagent_data.observation.http.probe_rest", fake_probe)
    profile = cli.probe(_rest(), ctx, workspace, {
        "allowed_origins": ["http://127.0.0.1:9"],
        "credential_options": {"auth": "bearer"},
        "credential_refs": {"token": ref},
    })
    assert seen["credentials"] == {"auth": "bearer", "token": SENTINEL}
    assert SENTINEL not in profile.model_dump_json()


def test_missing_reference_fails_without_echoing_the_name_or_value(workspace, ctx):
    with pytest.raises(ValueError, match="credential is unavailable") as exc:
        cli.probe(_rest(), ctx, workspace, {
            "allowed_origins": ["http://127.0.0.1:9"],
            "credential_refs": {"token": "file:missing"},
        })
    assert "missing" not in str(exc.value)
    assert SENTINEL not in str(exc.value)


def test_plaintext_credentials_are_rejected(workspace, ctx):
    with pytest.raises(ValueError, match="plaintext"):
        cli.probe(_rest(), ctx, workspace, {"credentials": {"token": SENTINEL}})
    with pytest.raises(ValueError, match="plaintext"):
        cli.probe(_rest(), ctx, workspace, {"credential_options": {"token": SENTINEL}})


def test_rest_401_is_reported_as_authentication_failure(workspace, ctx, monkeypatch):
    def fake_probe(selection, ctx, **options):
        return _profile(
            gaps=[CoverageGap(partition=1, code="http_error")],
            issues=[{"code": "http_error", "partition": 1, "status": 401}],
        )

    monkeypatch.setattr("dataagent_data.observation.http.probe_rest", fake_probe)
    profile = cli.probe(_rest(), ctx, workspace, {"allowed_origins": ["http://127.0.0.1:9"]})
    assert [gap.code for gap in profile.gaps] == ["authentication_failed"]
    assert profile.coverage == "partial"


def test_env_reference_is_resolved_inside_probe(workspace, ctx, monkeypatch):
    monkeypatch.setenv("T14_TOKEN_ENV", SENTINEL)
    seen = {}

    def fake_probe(selection, ctx, **options):
        seen.update(options)
        return _profile()

    monkeypatch.setattr("dataagent_data.observation.http.probe_rest", fake_probe)
    profile = cli.probe(_rest(), ctx, workspace, {
        "allowed_origins": ["http://127.0.0.1:9"],
        "credential_options": {"auth": "bearer"},
        "credential_refs": {"token": "env:T14_TOKEN_ENV"},
    })
    assert seen["credentials"]["token"] == SENTINEL
    assert SENTINEL not in profile.model_dump_json()


def test_default_secret_directory_wins_over_workspace_copy(
        workspace, ctx, tmp_path, home, monkeypatch):
    data_root = workspace / ".dataagent"
    legacy_ref = secrets.store_file_secret(
        data_root, "rest-token", "WORKSPACE-VALUE", scope="workspace")
    other_root = tmp_path / "outside"
    data_root_ref = secrets.store_file_secret(
        other_root, "rest-token", "DATA-ROOT-VALUE", scope="workspace")
    ref = secrets.store_file_secret(other_root, "rest-token", SENTINEL)
    assert legacy_ref == data_root_ref == ref == "file:rest-token"
    assert (home / ".dataagent" / "secrets" / "rest-token.key").is_file()
    assert (data_root / "secrets" / "rest-token.key").is_file()
    assert (other_root / "secrets" / "rest-token.key").is_file()
    monkeypatch.setenv("DATAAGENT_DATA_ROOT", str(other_root))
    seen = {}

    def fake_probe(selection, ctx, **options):
        seen.update(options)
        return _profile()

    monkeypatch.setattr("dataagent_data.observation.http.probe_rest", fake_probe)
    cli.probe(_rest(), ctx, workspace, {
        "allowed_origins": ["http://127.0.0.1:9"],
        "credential_options": {"auth": "bearer"},
        "credential_refs": {"token": ref},
    })
    # G5: the external default wins; neither data-root copy is consulted.
    assert seen["credentials"]["token"] == SENTINEL
    assert seen["credentials"]["token"] != "WORKSPACE-VALUE"
    assert seen["credentials"]["token"] != "DATA-ROOT-VALUE"


def test_workspace_file_reference_is_a_read_only_fallback(
        workspace, ctx, home, monkeypatch):
    data_root = workspace / ".dataagent"
    ref = secrets.store_file_secret(
        data_root, "rest-token", "LEGACY-VALUE", scope="workspace")
    assert (data_root / "secrets" / "rest-token.key").is_file()
    assert not (home / ".dataagent" / "secrets" / "rest-token.key").exists()
    seen = {}

    def fake_probe(selection, ctx, **options):
        seen.update(options)
        return _profile()

    monkeypatch.setattr("dataagent_data.observation.http.probe_rest", fake_probe)
    with pytest.warns(secrets.LegacySecretLocationWarning, match="legacy"):
        cli.probe(_rest(), ctx, workspace, {
            "allowed_origins": ["http://127.0.0.1:9"],
            "credential_options": {"auth": "bearer"},
            "credential_refs": {"token": ref},
        })
    assert seen["credentials"]["token"] == "LEGACY-VALUE"


def test_probe_failure_payload_classifies_missing_dependency():
    try:
        try:
            raise ModuleNotFoundError("No module named 'docx'")
        except Exception as exc:
            raise ValueError("invalid .docx file: ModuleNotFoundError") from exc
    except ValueError as exc:
        payload = cli._error_payload(exc)
    assert payload["code"] == "dependency_missing"
    assert payload["retryable"] is False
    assert "docx" in payload["detail"]


def test_probe_failure_payload_marks_timeouts_retryable():
    payload = cli._error_payload(TimeoutError("segment budget expired"))
    assert payload["code"] == "probe_timeout"
    assert payload["retryable"] is True
