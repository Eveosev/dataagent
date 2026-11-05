"""Shared fixtures: local runtime, CallContext, stored tables."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dataagent_contracts.core import CallContext, TableRef, VersionedRef  # noqa: E402

from dataagent_application import helpers  # noqa: E402


@pytest.fixture()
def runtime(tmp_path, monkeypatch):
    monkeypatch.setenv("DATAAGENT_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("DATAAGENT_WORKSPACE", str(tmp_path))
    from dataagent_runtime.runtime import Runtime, reset_default_runtime

    reset_default_runtime()
    rt = Runtime.create(workspace_root=tmp_path, data_root=tmp_path / "data")
    yield rt
    reset_default_runtime()


@pytest.fixture()
def ctx():
    return CallContext(
        request_id="req-1",
        scope_ref="scope-1",
        authorization_ref="authz-1",
    )


def store_table(runtime, columns, rows, row_meta=None, *, sheet="S1"):
    """Store a version-1 table payload and return a TableRef (data-layer shape)."""

    payload = {
        "sheet": sheet,
        "columns": columns,
        "rows": rows,
        "row_meta": row_meta or [{"role": "detail", "reason": ""} for _ in rows],
    }
    digest = runtime.content.put(payload)
    asset = helpers.asset_for(digest, "table", "scope-1")
    return TableRef(
        asset=asset,
        schema_ref=VersionedRef(id="schema:x", revision="r1"),
        data_ref=digest,
        row_identity=[columns[0]["field_id"]] if columns else None,
    )


@pytest.fixture()
def expense_table(runtime):
    """Region/amount table with a grand-total row that must not double count."""

    return store_table(
        runtime,
        columns=[
            {"name": "Region", "field_id": "region", "value_type": "string"},
            {"name": "Amount", "field_id": "amount", "value_type": "number", "unit": "CNY"},
        ],
        rows=[
            ["north", 100],
            ["south", 200],
            ["TOTAL", 300],
        ],
        row_meta=[
            {"role": "detail", "reason": ""},
            {"role": "detail", "reason": ""},
            {"role": "total", "reason": "grand total"},
        ],
    )
