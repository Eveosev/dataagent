"""The probe CLI resolves logical credential names in its own process."""

import pytest

from dataagent_contracts.intake import CoverageGap, SourceProfile, SourceSelection
from dataagent_data.observation import cli
from dataagent_runtime.policy import secrets

SENTINEL = "T14-SENTINEL-5f0c9a7d2b8e4c61"


def _rest():
    return SourceSelection(source_id="api", kind="rest", locator_ref="http://127.0.0.1:9/invoices")


def _profile(*, gaps=(), issues=()):
    return SourceProfile(
        source_id="api", source_revision="sha256:" + "0" * 64, kind="rest",
        records=[{"/id": 1}], fields=["/id"], anchors={}, total_partitions=1,
        completed_partitions=[] if gaps else [1], gaps=list(gaps), issues=list(issues),
        metadata={"structure_fingerprint": "sha256:" + "1" * 64},
    )


def test_file_reference_is_resolved_only_inside_probe(workspace, ctx, monkeypatch):
    ref = secrets.store_file_secret(workspace / ".dataagent", "rest-token", SENTINEL)
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


def test_file_reference_is_scoped_to_workspace_not_data_root_env(workspace, ctx, tmp_path, monkeypatch):
    inside = secrets.store_file_secret(workspace / ".dataagent", "rest-token", "INSIDE-VALUE")
    outside = tmp_path / "outside"
    secrets.store_file_secret(outside, "rest-token", SENTINEL)
    monkeypatch.setenv("DATAAGENT_DATA_ROOT", str(outside))
    seen = {}

    def fake_probe(selection, ctx, **options):
        seen.update(options)
        return _profile()

    monkeypatch.setattr("dataagent_data.observation.http.probe_rest", fake_probe)
    cli.probe(_rest(), ctx, workspace, {
        "allowed_origins": ["http://127.0.0.1:9"],
        "credential_options": {"auth": "bearer"},
        "credential_refs": {"token": inside},
    })
    assert seen["credentials"]["token"] == "INSIDE-VALUE"
    assert seen["credentials"]["token"] != SENTINEL
