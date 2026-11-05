"""r38 F3: an official file read of a registered gold digest is an exposure.

``read_file_ref`` verifies the bytes it returns against the cited digest;
when those bytes are a registered gold expectation (a governance sample
set sharing the same ``data_root``), the read records an exposure in the
cross-layer ledger — the case can no longer be accepted as unseen.
"""

from __future__ import annotations

import json

from conftest import write_file

from dataagent_runtime.adapters.gold_ledger import GoldExposureLedger

from dataagent_data.helpers import read_file_ref


GOLD_ROWS = [
    {"record_key": "c1", "rule_id": "rule:limit", "expected_verdict": "pass"}
]


def _register_gold(runtime, payload: bytes) -> str:
    """Register a gold expectation in the shared ledger, governance-style.

    The bytes land in the shared content store under the same digest the
    workspace file hashes to — exactly what ``register_file_ref`` stages —
    so the ledger key is the digest the official read verifies.
    """

    digest = runtime.content.put(payload)
    ledger = GoldExposureLedger(runtime.data_root / "vault")
    ledger.register(digest, set_id="set:gold", case_id="c1")
    return digest


def test_file_read_of_registered_gold_records_exposure(runtime, workspace):
    import hashlib

    payload = json.dumps(GOLD_ROWS).encode("utf-8")
    name = write_file(workspace, "gold.json", payload)
    digest = "sha256:" + hashlib.sha256(payload).hexdigest()
    assert digest == _register_gold(runtime, payload)

    from dataagent_contracts.core import FileRef

    ref = FileRef(
        id=f"file:{digest[7:23]}",
        kind="file",
        scope_ref="tenant:test/project:p1",
        revision=digest,
        resolver="workspace",
        locator=name,
        digest=digest,
        media_type="application/json",
        filename="gold.json",
        size_bytes=len(payload),
        content_digest=digest,
    )

    ledger = GoldExposureLedger(runtime.data_root / "vault")
    assert digest not in ledger.exposed_digests()

    data = read_file_ref(runtime, ref)
    assert data == payload  # the read succeeds — it is an official read

    assert digest in ledger.exposed_digests()
    entries = ledger.exposures(digest)
    assert entries and entries[0]["purpose"] == "file-read"
    assert entries[0]["accessed_by"] == ref.id


def test_file_read_of_ordinary_content_records_nothing(runtime, workspace):
    payload = b'{"public": true}'
    name = write_file(workspace, "public.json", payload)
    import hashlib

    digest = "sha256:" + hashlib.sha256(payload).hexdigest()

    from dataagent_contracts.core import FileRef

    ref = FileRef(
        id=f"file:{digest[7:23]}",
        kind="file",
        scope_ref="tenant:test/project:p1",
        revision=digest,
        resolver="workspace",
        locator=name,
        digest=digest,
        media_type="application/json",
        filename="public.json",
        size_bytes=len(payload),
        content_digest=digest,
    )
    read_file_ref(runtime, ref)
    assert GoldExposureLedger(runtime.data_root / "vault").exposed_digests() == set()
