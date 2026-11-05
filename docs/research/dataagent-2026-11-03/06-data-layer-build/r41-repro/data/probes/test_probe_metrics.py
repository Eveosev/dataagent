"""Probe: define_metric_formula semantic edge cases (run with tests/ on sys.path)."""
import sys
sys.path.insert(0, "/Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-data/tests")
from conftest import build_pdf, call, file_ref, workspace, runtime, ctx  # noqa: F401


def _page_text(runtime, document):
    return runtime.content.get_json(document.blocks_ref)["pages"][0]["text"]


def _metric(runtime, ctx, workspace, name, src, filters):
    build_pdf(workspace / name, [src])
    doc = call("parse_text_pdf", {"file_ref": file_ref(workspace, name)}, ctx, runtime).data.document
    text = _page_text(runtime, doc)
    anchor = {"source_ref": doc.original_ref.id, "source_revision": doc.original_ref.revision,
              "selector": {"kind": "pdf_text_span", "page": 1, "char_start": 0, "char_end": len(text)}}
    r = call("define_metric_formula", {"statement": src, "document_ref": doc, "sources": [anchor],
             "proposal": {"measure_field": "amount", "aggregation": "sum", "grain": "department",
                          "dimensions": ["department"], "unit": "CNY", "filters": filters}}, ctx, runtime)
    print(f"\nSRC={src!r} FILTERS={filters} -> {r.status.value}",
          [i.message[:110] for i in r.issues])
    return r


def test_or_source_conjunctive_filters(runtime, ctx, workspace):
    # source is a disjunction; two ANDed filters define an empty set
    r = _metric(runtime, ctx, workspace, "or.pdf",
                "Sum amount CNY for status = 'paid' or status = 'settled' by department.",
                ["status = 'paid'", "status = 'settled'"])
    print("OR->AND result:", r.status.value)


def test_not_negated_source(runtime, ctx, workspace):
    # source excludes paid, proposal includes paid
    _metric(runtime, ctx, workspace, "neg.pdf",
            "Sum amount CNY for all claims except status = 'paid' by department.",
            ["status = 'paid'"])


def test_formula_equals_false_positive(runtime, ctx, workspace):
    _metric(runtime, ctx, workspace, "fx.pdf",
            "Sum amount CNY by department where net = gross minus refunds.",
            [])
