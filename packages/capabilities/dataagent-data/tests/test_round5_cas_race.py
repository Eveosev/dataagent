"""Deterministic optimistic-concurrency regression for extraction schemas.

The Round 5 regression test synchronises only the *entry* to
``versions.current``; the storage layer check can then still win by timing on
the buggy pre-fix code.  This test forces both writers to observe ``r1``
*before* either one writes, which is exactly the lost-update interleaving
r4-review #10 described.  It must fail (both writers ``ok``) when the CAS is
missing and pass with exactly one ``version_conflict`` when it is present.
"""

from __future__ import annotations

import threading

from conftest import call

SCHEMA_ID = "xschema:cas-read-first"


def _field(field_id: str) -> dict:
    return {"field_id": field_id, "name": field_id, "path": field_id, "value_type": "money"}


def test_conflict_when_both_writers_read_expected_revision_first(runtime, ctx):
    call(
        "register_extraction_schema_version",
        {"schema_id": SCHEMA_ID, "fields": [_field("amount")]},
        ctx,
        runtime,
    )
    assert runtime.versions.current("extraction_schema", SCHEMA_ID)[0] == "r1"

    read_barrier = threading.Barrier(2, timeout=5)
    original_current = runtime.versions.current
    observed: list[str] = []

    def read_then_wait(kind: str, object_id: str):
        value = original_current(kind, object_id)  # both threads read r1 ...
        observed.append(value[0])
        read_barrier.wait()  # ... then hold until both have read, before either writes
        return value

    results: list[tuple[str, str | None]] = []

    def worker(index: int) -> None:
        try:
            result = call(
                "register_extraction_schema_version",
                {
                    "schema_id": SCHEMA_ID,
                    "fields": [_field(f"amount{index}")],
                    "change_note": f"writer {index}",
                    "expected_revision": "r1",
                },
                ctx,
                runtime,
            )
            results.append(
                (result.status.value, result.data.revision if result.data else None)
            )
        except Exception as exc:  # noqa: BLE001 - surfaced by the assertion below
            results.append(("exception", type(exc).__name__))

    runtime.versions.current = read_then_wait  # type: ignore[method-assign]
    try:
        threads = [threading.Thread(target=worker, args=(index,)) for index in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
    finally:
        runtime.versions.current = original_current  # type: ignore[method-assign]

    assert observed == ["r1", "r1"]
    assert sorted(status for status, _ in results) == ["failed", "ok"], results
    assert runtime.versions.revisions("extraction_schema", SCHEMA_ID) == ["r1", "r2"]
