"""Versioned table payload codec (07 W1a): decode, row roles, unknown versions."""

from __future__ import annotations

import pytest

from dataagent_runtime.adapters.local_content import LocalContentStore
from dataagent_runtime.errors import CapabilityError
from dataagent_runtime.ports.tabular import decode_table, decode_table_payload


@pytest.fixture()
def store(tmp_path):
    return LocalContentStore(tmp_path / "content")


def _payload(**overrides):
    payload = {
        "sheet": "Sheet1",
        "columns": [
            {"name": "Region", "field_id": "region", "value_type": "string"},
            {"name": "Amount", "field_id": "amount", "value_type": "number", "unit": "CNY"},
        ],
        "rows": [
            ["north", 100],
            ["south", 200],
            ["TOTAL", 300],
        ],
        "row_meta": [
            {"role": "detail", "reason": ""},
            {"role": "detail", "reason": ""},
            {"role": "total", "reason": "grand total row"},
        ],
    }
    payload.update(overrides)
    return payload


def test_decode_version_one_preserves_columns_rows_and_roles():
    table = decode_table_payload(_payload())
    assert table.version == 1
    assert table.field_ids == ("region", "amount")
    assert table.row_roles == ("detail", "detail", "total")
    assert table.rows[2] == ("TOTAL", 300)
    assert table.row_dict(1) == {"region": "south", "amount": 200}


def test_detail_rows_exclude_totals_so_aggregates_do_not_double_count():
    table = decode_table_payload(_payload())
    # The counterexample: summing every row would count the total twice.
    assert sum(table.rows[i][1] for i in range(len(table.rows))) == 600
    assert sum(table.rows[i][1] for i in table.detail_rows()) == 300
    assert table.non_detail_summary() == {"total": 1}


def test_row_meta_defaults_to_detail_when_absent():
    payload = _payload()
    del payload["row_meta"]
    table = decode_table_payload(payload)
    assert table.row_roles == ("detail", "detail", "detail")


def test_unknown_payload_version_is_rejected_with_clear_error():
    with pytest.raises(CapabilityError) as exc:
        decode_table_payload(_payload(payload_version=2))
    assert "unsupported table payload version: 2" in exc.value.message


def test_non_versioned_non_table_payload_is_rejected():
    with pytest.raises(CapabilityError) as exc:
        decode_table_payload({"hello": "world"})
    assert "unrecognised table payload" in exc.value.message


def test_malformed_rows_are_rejected():
    with pytest.raises(CapabilityError):
        decode_table_payload(_payload(rows=[["only-one-cell"]]))
    with pytest.raises(CapabilityError):
        decode_table_payload(_payload(row_meta=[{"role": "detail"}]))
    with pytest.raises(CapabilityError):
        decode_table_payload(_payload(row_meta=[{"role": "weird"}] * 3))


def test_decode_table_via_content_store(store, tmp_path):
    digest = store.put(_payload())

    class Ref:
        data_ref = digest

    table = decode_table(store, Ref())
    assert table.detail_rows() == [0, 1]

    class Missing:
        data_ref = "sha256:" + "0" * 64

    with pytest.raises(CapabilityError) as exc:
        decode_table(store, Missing())
    assert "table content missing" in exc.value.message


def test_schema_fields_shape():
    table = decode_table_payload(_payload())
    fields = table.schema_fields()
    assert fields[0] == {
        "field_id": "region",
        "name": "Region",
        "path": "region",
        "value_type": "string",
        "nullable": True,
        "unit": None,
    }
    assert fields[1]["unit"] == "CNY"
