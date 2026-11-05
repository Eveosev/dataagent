"""r40 F1: a content ref is covered by its *content address*, not its id.

The r38/r39 binding only digested the inline ``content`` payload; a request
that carried caller free text under other model-visible keys could cite a
clean ref (a bound table, a stored rule) and smuggle fresh text next to it
once an operation projected it. Operations now cite every caller-supplied
section by content address (``<any id>@sha256:<digest of the bytes>``), so
the gate must treat such a ref as covered whenever the decision covers
those bytes under *any* id — the id is presentation, the revision is what
was approved. Label revisions (``r1``) still need exact-string coverage.
"""

from __future__ import annotations

from dataagent_contracts.core import (
    EgressDecision,
    EgressOutcome,
    ModelDestination,
    VersionedRef,
)

from dataagent_runtime.adapters.local_content import canonical_bytes, digest_bytes
from dataagent_runtime.enforcement import egress_check

CLEAN_CONTENT = "raw text with 13800138000"
CLEAN_DIGEST = digest_bytes(canonical_bytes(CLEAN_CONTENT))
OTHER_CONTENT = "different caller text"
OTHER_DIGEST = digest_bytes(canonical_bytes(OTHER_CONTENT))

DESTINATION = {"model_ref": "model:llm", "deployment": "vendor_api"}


def _decision(content_refs, decision_id="ed:1"):
    return EgressDecision(
        decision_id=decision_id,
        content_refs=content_refs,
        destination=ModelDestination(model_ref="model:llm", deployment="vendor_api"),
        decision=EgressOutcome.allow,
        access_decision_ref="ad:1",
    )


def test_content_ref_is_covered_by_its_address_under_any_id():
    # the decision covered the bytes as table:orders@sha256:<d>; the request
    # cites them as content:<x>@sha256:<d> — same bytes, so covered
    decision = _decision([VersionedRef(id="table:orders", revision=CLEAN_DIGEST)])
    request = {
        "content_refs": [f"caller:statement@{CLEAN_DIGEST}"],
        "destination": DESTINATION,
        "egress_decision_ref": "ed:1",
    }
    outcome = egress_check(request, get_egress=lambda ref: decision)
    assert outcome.allowed, outcome.reasons


def test_content_ref_with_an_uncovered_address_denies():
    # a fresh caller statement is different bytes: no covered id, and its
    # digest is not among the decision's content addresses
    decision = _decision([VersionedRef(id="table:orders", revision=CLEAN_DIGEST)])
    request = {
        "content_refs": [f"caller:statement@{OTHER_DIGEST}"],
        "destination": DESTINATION,
        "egress_decision_ref": "ed:1",
    }
    outcome = egress_check(request, get_egress=lambda ref: decision)
    assert not outcome.allowed
    assert any("does not cover" in r for r in outcome.reasons)


def test_label_revision_still_needs_exact_coverage():
    # r1 is not an address: only the exact string counts
    decision = _decision([VersionedRef(id="rule:x", revision="r1")])
    request = {
        "content_refs": ["req:x@r1"],
        "destination": DESTINATION,
        "egress_decision_ref": "ed:1",
    }
    outcome = egress_check(request, get_egress=lambda ref: decision)
    assert not outcome.allowed
    ok = egress_check(
        dict(request, content_refs=["rule:x@r1"]), get_egress=lambda ref: decision
    )
    assert ok.allowed


def test_mixed_refs_need_every_one_covered():
    decision = _decision(
        [
            VersionedRef(id="table:orders", revision=CLEAN_DIGEST),
            VersionedRef(id="rule:x", revision="r1"),
        ]
    )
    request = {
        "content_refs": [f"table:orders@{CLEAN_DIGEST}", "rule:x@r1", f"s@{OTHER_DIGEST}"],
        "destination": DESTINATION,
        "egress_decision_ref": "ed:1",
    }
    outcome = egress_check(request, get_egress=lambda ref: decision)
    assert not outcome.allowed
    assert any(f"s@{OTHER_DIGEST}" in r for r in outcome.reasons)
