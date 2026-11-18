from copy import deepcopy
from decimal import Decimal
import json

import pytest

from dataagent_contracts.ontology import Assertion, EntityInstance, MappingSpec, OntologyRevision, RelationFact


@pytest.fixture
def definition():
    return OntologyRevision(
        id="purchasing", revision="8", entity_type="PurchaseOrder",
        properties={
            "company": {"value_type": "string", "required": True},
            "number": {"value_type": "string", "required": True},
            "total": {"value_type": "decimal", "description": "Billed total"},
        },
        identity_fields=["company", "number"],
        relations={"payment": ["PurchaseOrder", "currency", "business_date"]},
        extensions={"domain.policy": {"record": "purchasing"}},
    )


@pytest.fixture
def mapping():
    return MappingSpec(
        id="vendor-file", revision="3", ontology_revision="purchasing@8",
        source_fingerprint="file-schema",
        bindings={
            "company": {"source_field": "business.unit"},
            "number": {"source_field": 'Order "No."'},
            "total": {"source_field": "minor", "transform": "minor_to_major"},
        },
        relation_bindings={"payment": {
            "business_date": {"source_field": "booked_on"},
            "PurchaseOrder": {"source_field": "$entity"},
            "currency": {"source_field": "ccy"},
        }},
        unmapped={"private_notes": "exclude"},
    )


def test_documents_preserve_composite_identity_and_native_nary_order(definition, mapping):
    from dataagent_ontology.adapters.ossie import export_ossie, import_ossie

    exchange = export_ossie(definition, mapping)
    component = exchange.ontology["ontology"][0]
    assert component["identify_by"] == ["company", "number"]
    payment = next(item for item in component["relationships"] if item["name"] == "payment")
    assert [role["name"] for role in payment["roles"]] == ["currency", "business_date"]
    concept = exchange.mapping["concept_mappings"][0]
    assert concept["object_mappings"][0]["referent_mappings"] == [
        {"relationship": "company", "expression": 'source_rows."business.unit"'},
        {"relationship": "number", "expression": 'source_rows."Order ""No."""'},
    ]
    terminal = next(node for node in concept["link_mappings"][0]["children"]
                    if node.get("relationship") is None)
    assert terminal["object_mapping"]["expression"] == 'source_rows."ccy"'
    assert terminal["children"][0]["relationship"] == "payment"
    assert terminal["children"][0]["object_mapping"]["expression"] == 'source_rows."booked_on"'
    assert {item.path for item in exchange.losses if item.code == "unsupported_transform"} == {
        "/mapping/bindings/total",
    }
    assert "private_notes" not in {field["name"] for field in exchange.semantic_model["datasets"][0]["fields"]}

    received = import_ossie(
        exchange.ontology, exchange.semantic_model, exchange.mapping,
        source_fingerprint="target-file-schema",
    )
    assert received.ontology.identity_fields == ["company", "number"]
    assert received.ontology.relations["payment"] == ["PurchaseOrder", "currency", "business_date"]
    assert received.mapping.bindings["company"].source_field == "business.unit"
    assert received.mapping.bindings["number"].source_field == 'Order "No."'
    assert "total" not in received.mapping.bindings
    assert received.mapping.relation_bindings["payment"]["PurchaseOrder"].source_field == "$entity"
    assert received.mapping.relation_bindings["payment"]["business_date"].source_field == "booked_on"
    assert received.mapping.source_fingerprint == "target-file-schema"


def test_json_sidecar_preserves_evidence_extensions_and_exact_amount(definition, mapping):
    from dataagent_ontology.adapters.ossie import export_ossie, import_ossie

    anchor = {"source_ref": "file", "source_revision": "sha", "selector": {
        "kind": "excel_cell", "sheet": "Orders", "range": "C4",
    }}
    amount = Decimal("123456789012345678901234567890.09")
    instance = EntityInstance(
        id="entity:42", scope="tenant", entity_type="PurchaseOrder",
        values={"company": "ACME", "number": "001", "total": amount},
        source_anchors={"total": [anchor]}, extensions={"source.unmapped": {"memo": ["raw"]}},
    )
    assertion = Assertion(
        id="assertion:42", scope="tenant", ontology_revision="purchasing@8", relation="payment",
        role_bindings=[
            {"role": "PurchaseOrder", "value": "entity:42", "value_type": "reference"},
            {"role": "currency", "value": "CNY"},
            {"role": "business_date", "value": "2026-11-01", "value_type": "date"},
        ],
        source_anchors=[anchor], mapping_revision="vendor-file@3", extractor_version="1",
        business_time="2026-11-01", extensions={"review.trace": {"decision": "manual"}},
    )
    fact = RelationFact(
        id="fact:42", relation=assertion.relation, role_bindings=assertion.role_bindings,
        assertion_refs=[assertion.id],
    )
    exchange = export_ossie(definition, mapping, instances=[instance], assertions=[assertion], facts=[fact])
    received = import_ossie(
        exchange.ontology, exchange.semantic_model, exchange.mapping,
        sidecar=json.loads(json.dumps(exchange.sidecar)),
    )
    assert received.ontology == definition
    assert received.mapping == mapping
    assert received.instances == [instance]
    assert received.instances[0].values["total"].as_tuple() == amount.as_tuple()
    assert received.assertions == [assertion]
    assert received.facts == [fact]


def test_opaque_native_expressions_never_become_executable_field_bindings(definition, mapping):
    from dataagent_ontology.adapters.ossie import export_ossie, import_ossie

    exchange = export_ossie(definition, mapping)
    exchange.ontology["requires"] = ["COUNT[PurchaseOrder] > 0"]
    root = exchange.mapping["concept_mappings"][0]["link_mappings"][0]
    property_node = next(node for node in root["children"] if node.get("relationship") == "number")
    property_node["object_mapping"]["expression"] = 'CONCAT(source_rows."Order ""No.""", \'suffix\')'
    field = next(field for field in exchange.semantic_model["datasets"][0]["fields"]
                 if field["name"] == "ccy")
    field["expression"] = {"dialects": [{"dialect": "OTHER", "expression": "vendor code"}]}
    exchange.mapping["custom_extensions"] = [{"vendor_name": "OTHER", "data": "opaque payload"}]

    received = import_ossie(
        exchange.ontology, exchange.semantic_model, exchange.mapping, source_fingerprint="target-file-schema",
    )
    assert "number" not in received.mapping.bindings
    assert "payment" not in received.mapping.relation_bindings
    assert any(loss.path == "/ontology/requires/0" for loss in received.losses)
    assert any(loss.code == "unsupported_expression" and loss.path.endswith("/object_mapping/expression")
               for loss in received.losses)
    assert any(loss.code == "unsupported_expression" and loss.path.startswith("/semantic_model/datasets/")
               for loss in received.losses)
    assert received.opaque_extensions["/mapping/custom_extensions"] == [
        {"vendor_name": "OTHER", "data": "opaque payload"},
    ]


def test_nested_schema_references_validate_locally_and_reject_invalid_mapping(definition, mapping):
    from dataagent_ontology.adapters.ossie import OssieValidationError, export_ossie, import_ossie

    exchange = export_ossie(definition, mapping)
    invalid_mapping = deepcopy(exchange.mapping)
    invalid_mapping["concept_mappings"][0]["link_mappings"][0]["object_mapping"]["typo"] = True
    with pytest.raises(OssieValidationError, match="object_mapping"):
        import_ossie(exchange.ontology, exchange.semantic_model, invalid_mapping)

    invalid_mapping = deepcopy(exchange.mapping)
    invalid_mapping["semantic_model_ref"]["name"] = "other"
    with pytest.raises(OssieValidationError, match="semantic_model_ref"):
        import_ossie(exchange.ontology, exchange.semantic_model, invalid_mapping)


def test_sidecar_rejects_an_edit_to_the_bound_documents(definition, mapping):
    from dataagent_ontology.adapters.ossie import OssieValidationError, export_ossie, import_ossie

    exchange = export_ossie(definition, mapping)
    exchange.ontology["description"] = "Changed since the sidecar was created"
    with pytest.raises(OssieValidationError, match="sidecar.*digest"):
        import_ossie(exchange.ontology, exchange.semantic_model, exchange.mapping, sidecar=exchange.sidecar)


def test_concepts_shaped_single_concept_exports_the_resolved_definition():
    """A new-style definition keeps its concept in ``concepts``, not at the top."""
    from dataagent_contracts.ontology import ConceptDefinition
    from dataagent_ontology.adapters.ossie import (
        OssieValidationError, export_ossie, import_ossie,
    )

    definition = OntologyRevision(
        id="purchasing", revision="9",
        concepts={"PurchaseOrder": ConceptDefinition(
            entity_type="PurchaseOrder",
            properties={
                "company": {"value_type": "string", "required": True},
                "number": {"value_type": "string", "required": True},
                "total": {"value_type": "decimal", "description": "Billed total"},
            },
            identity_fields=["company", "number"],
        )},
        relations={"payment": ["PurchaseOrder", "currency", "business_date"]},
    )
    mapping = MappingSpec(
        id="vendor-file", revision="3", ontology_revision="purchasing@9",
        concept="PurchaseOrder", source_fingerprint="file-schema",
        bindings={
            "company": {"source_field": "business.unit"},
            "number": {"source_field": "order_no"},
            "total": {"source_field": "minor", "transform": "minor_to_major"},
        },
        relation_bindings={"payment": {
            "PurchaseOrder": {"source_field": "$entity"},
            "currency": {"source_field": "ccy"},
            "business_date": {"source_field": "booked_on"},
        }},
    )

    exchange = export_ossie(definition, mapping)
    component = exchange.ontology["ontology"][0]
    assert component["concept"] == "PurchaseOrder"
    assert component["identify_by"] == ["company", "number"]
    assert {item["name"] for item in component["relationships"]} == {
        "company", "number", "total", "payment"}
    concept = exchange.mapping["concept_mappings"][0]
    assert concept["concept"] == "PurchaseOrder"
    assert concept["object_mappings"][0]["referent_mappings"] == [
        {"relationship": "company", "expression": 'source_rows."business.unit"'},
        {"relationship": "number", "expression": 'source_rows."order_no"'},
    ]

    received = import_ossie(
        exchange.ontology, exchange.semantic_model, exchange.mapping,
        sidecar=json.loads(json.dumps(exchange.sidecar)),
        entity_type="PurchaseOrder",
    )
    assert received.ontology == definition
    assert received.mapping == mapping

    with pytest.raises(OssieValidationError, match="not an ontology property"):
        export_ossie(definition, mapping.model_copy(update={
            "bindings": {**mapping.bindings,
                         "secret": {"source_field": "hidden"}},
        }))


def test_standalone_mapping_uses_column_aliases_and_skips_sql_special_values():
    from dataagent_ontology.adapters.ossie import import_ossie

    ontology = {
        "version": "0.3.0.dev0", "name": "ExpenseClaims", "ontology": [{
            "concept": "ExpenseClaim", "type": "EntityType", "identify_by": ["id"],
            "relationships": [
                {"name": "id", "roles": [{"concept": "Integer"}], "multiplicity": "OneToOne", "verbalizes": []},
                {"name": "total", "roles": [{"concept": "Decimal"}], "multiplicity": "ManyToOne", "verbalizes": []},
                {"name": "submitted", "roles": [{"concept": "Date"}], "multiplicity": "ManyToOne", "verbalizes": []},
            ],
        }],
    }
    model = {
        "version": "0.3.0.dev0", "name": "ExpenseTables", "datasets": [{
            "name": "EXPENSES", "source": "FINANCE.CLAIMS", "fields": [
                {"name": "CODE", "expression": {"sql": "claim_no"}},
                {"name": "AMOUNT", "expression": {"sql": "claimed_total"}},
                {"name": "NOW", "expression": {"sql": "CURRENT_DATE"}},
            ],
        }],
    }
    mapping = {
        "version": "0.3.0.dev0", "name": "expense-claims",
        "ontology_ref": {"name": "ExpenseClaims"},
        "semantic_model_ref": {"name": "ExpenseTables"},
        "concept_mappings": [{
            "concept": "ExpenseClaim",
            "link_mappings": [{
                "object_mapping": {"expression": "expenses.code"},
                "children": [
                    {"object_mapping": {"expression": "expenses.amount"}, "relationship": "total"},
                    {"object_mapping": {"expression": "expenses.now"}, "relationship": "submitted"},
                ],
            }],
        }],
    }
    received = import_ossie(ontology, model, mapping, source_fingerprint="observed-expense-schema")
    assert {name: binding.source_field for name, binding in received.mapping.bindings.items()} == {
        "id": "claim_no", "total": "claimed_total",
    }
    assert any(loss.path == "/semantic_model/datasets/0/fields/2/expression" for loss in received.losses)
