"""Exchange a single DataAgent entity and row mapping with pinned Apache Ossie.

Ossie documents contain a portable projection. The optional DataAgent sidecar
retains the original contracts, evidence, and the projection's loss report.
Importing without the sidecar recognizes direct columns and ordered link paths.
Expressions and document locations are treated as input data.
"""

from collections import defaultdict
from collections.abc import Iterable
from copy import deepcopy
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from dataagent_contracts.ontology import (
    Assertion,
    EntityInstance,
    FieldBinding,
    MappingSpec,
    OntologyRevision,
    PropertyDefinition,
    RelationFact,
)
from dataagent_ontology.identity import digest

from ._ossie_schema import (
    OSSIE_COMMIT,
    OSSIE_VERSION,
    OssieValidationError,
    pointer,
    validate_ossie_documents,
)

__all__ = [
    "OSSIE_COMMIT", "OSSIE_VERSION", "SUPPORTED_SUBSET", "OssieExchange",
    "OssieImport", "OssieLoss", "OssieValidationError", "export_ossie", "import_ossie",
    "validate_ossie_documents",
]

SUPPORTED_SUBSET = (
    "one entity with scalar properties and ordered identity relationships",
    "ordered relation roles and single-dataset link paths rooted at the entity",
    "one logical dataset with direct source column expressions",
    "direct field bindings and flat identity referent mappings",
    "DataAgent contracts, evidence and extensions in a document-bound JSON sidecar",
)
_SCALARS = {
    "string": "String", "decimal": "Decimal", "integer": "Integer", "boolean": "Boolean",
    "date": "Date", "datetime": "DateTime", "reference": "String",
}
_PROPERTY_TYPES = {native: kind for kind, native in _SCALARS.items() if kind != "reference"}
_BUILT_INS = {*_PROPERTY_TYPES, "Float", "Any"}
_DATASET = "source_rows"
_IDENTIFIER = r'(?:[A-Za-z_][A-Za-z0-9_]*|"(?:[^"\x00-\x1f]|"")+")'
_COLUMN = re.compile(rf"(?P<column>{_IDENTIFIER})\Z")
_FIELD_REF = re.compile(rf"(?P<dataset>{_IDENTIFIER})\s*\.\s*(?P<field>{_IDENTIFIER})\Z")
_SQL_SPECIAL_VALUES = {
    "NULL", "TRUE", "FALSE", "UNKNOWN",
    "CURRENT_DATE", "CURRENT_TIME", "CURRENT_TIMESTAMP", "LOCALTIME", "LOCALTIMESTAMP",
    "CURRENT_USER", "SESSION_USER", "SYSTEM_USER", "USER", "CURRENT_SCHEMA", "CURRENT_CATALOG",
}


@dataclass(frozen=True)
class OssieLoss:
    code: str
    path: str
    detail: str
    preserved_in_sidecar: bool = False


@dataclass
class OssieExchange:
    ontology: dict
    semantic_model: dict
    mapping: dict
    sidecar: dict
    losses: list[OssieLoss]
    supported_subset: tuple[str, ...] = SUPPORTED_SUBSET


@dataclass
class OssieImport:
    ontology: OntologyRevision | None
    mapping: MappingSpec | None
    losses: list[OssieLoss]
    instances: list[EntityInstance] = field(default_factory=list)
    assertions: list[Assertion] = field(default_factory=list)
    facts: list[RelationFact] = field(default_factory=list)
    opaque_extensions: dict[str, list[dict]] = field(default_factory=dict)
    supported_subset: tuple[str, ...] = SUPPORTED_SUBSET


class _InstanceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    instance: EntityInstance
    decimal_fields: list[str]

    def restore(self) -> EntityInstance:
        values = self.instance.values.copy()
        for name in self.decimal_fields:
            try:
                value = Decimal(values[name])
            except (InvalidOperation, KeyError, TypeError) as exc:
                raise OssieValidationError(f"/sidecar/instances: invalid decimal field {name!r}") from exc
            if not value.is_finite():
                raise OssieValidationError(f"/sidecar/instances: nonfinite decimal field {name!r}")
            values[name] = value
        return self.instance.model_copy(update={"values": values})


class _Sidecar(BaseModel):
    model_config = ConfigDict(extra="forbid")
    format: Literal["dataagent.ossie.exchange"]
    version: Literal[1]
    ossie_commit: Literal[OSSIE_COMMIT]
    document_digests: dict[str, str]
    ontology: OntologyRevision
    mapping: MappingSpec
    instances: list[_InstanceRecord]
    assertions: list[Assertion]
    facts: list[RelationFact]
    losses: list[OssieLoss]


def _document_digests(ontology: dict, semantic_model: dict, mapping: dict) -> dict[str, str]:
    return {
        "ontology": digest(ontology),
        "semantic_model": digest(semantic_model),
        "mapping": digest(mapping),
    }


def _qualified_field(column: str) -> str:
    return f"{_DATASET}.{_quoted(column)}"


def _quoted(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _unquoted(name: str) -> str:
    if name.startswith('"'):
        return name[1:-1].replace('""', '"')
    return name


def _column_name_is_portable(name: str) -> bool:
    return 0 < len(name) <= 128 and _COLUMN.fullmatch(_quoted(name)) is not None


def _check_native_mapping(ontology: OntologyRevision, mapping: MappingSpec) -> None:
    if mapping.ontology_revision != f"{ontology.id}@{ontology.revision}":
        raise OssieValidationError("/mapping/ontology_revision does not match the DataAgent ontology")
    for name in mapping.bindings:
        if name not in ontology.properties:
            raise OssieValidationError(f"{pointer('mapping', 'bindings', name)} is not an ontology property")
    for name, bindings in mapping.relation_bindings.items():
        if name not in ontology.relations or set(bindings) != set(ontology.relations[name]):
            raise OssieValidationError(f"{pointer('mapping', 'relation_bindings', name)} has unknown or missing roles")


def _role_concepts(facts: Iterable[RelationFact], assertions: Iterable[Assertion]) -> dict:
    result = defaultdict(set)
    for fact in (*facts, *assertions):
        for role in fact.role_bindings:
            result[fact.relation, role.role].add(role.value_type)
    return result


def _definition_document(ontology, mapping, facts, assertions, loss):
    entity = ontology.entity_type
    if entity in _BUILT_INS:
        raise OssieValidationError("/ontology/entity_type collides with a built-in Ossie concept")
    properties = {}
    for name, prop in ontology.properties.items():
        if prop.required:
            loss("required_property", pointer("ontology", "properties", name, "required"),
                 "DataAgent required-field validation travels in the sidecar")
        if prop.value_type == "reference":
            loss("reference_as_string", pointer("ontology", "properties", name, "value_type"),
                 "DataAgent references are projected as opaque String values")
        concept = _SCALARS[prop.value_type]
        properties[name] = {
            "name": name, "roles": [{"concept": concept}], "multiplicity": "ManyToOne",
            "description": prop.description, "verbalizes": [f"{{{entity}}} has {name} {{{concept}}}"],
        }
        if prop.extensions:
            loss("dataagent_extensions", pointer("ontology", "properties", name, "extensions"),
                 "Property extensions travel in the sidecar")
    if ontology.extensions:
        loss("dataagent_extensions", "/ontology/extensions", "Ontology extensions travel in the sidecar")

    observed_types = _role_concepts(facts, assertions)
    relations = {}
    for name, roles in ontology.relations.items():
        path = pointer("ontology", "relations", name)
        bindings = mapping.relation_bindings.get(name)
        if name in properties:
            loss("relationship_name_collision", path, "Ossie uses one name per relationship in the entity")
            continue
        if bindings and bindings[roles[0]].source_field != "$entity":
            loss("unsupported_entity_role", path, "An Ossie relationship starts with its declaring entity")
            continue
        if roles[0] != entity:
            loss("implicit_entity_role", f"{path}/0", "Ossie names the implicit first role after the entity")
        ossie_roles = []
        for index, role in enumerate(roles[1:], 1):
            binding = bindings.get(role) if bindings else None
            types = observed_types[name, role]
            if binding and binding.source_field == "$entity":
                concept = entity
            elif len(types) == 1:
                concept = _SCALARS[next(iter(types))]
            elif not types and binding and binding.transform in ("decimal", "minor_to_major", "integer", "date", "datetime"):
                concept = _SCALARS["decimal" if binding.transform == "minor_to_major" else binding.transform]
            else:
                concept = "String"
                loss("unspecified_role_type", f"{path}/{index}", "The projection uses String for an unspecified role type")
            ossie_roles.append({"concept": concept, "name": role})
        # Ossie requires distinct effective role names, including the implicit first role.
        if any(role["name"] == entity for role in ossie_roles):
            loss("relationship_role_collision", path, "An additional role duplicates the implicit entity role name")
            continue
        relations[name] = {
            "name": name, "roles": ossie_roles,
            "verbalizes": [f"{{{entity}}} {name} " + " ".join(f"{{{role}}}" for role in roles[1:])],
        }
    component = {
        "concept": entity, "type": "EntityType", "identify_by": list(ontology.identity_fields),
        "relationships": [*properties.values(), *relations.values()],
    }
    return {"version": OSSIE_VERSION, "name": ontology.id, "ontology": [component]}, properties, relations


def _export_bindings(ontology, mapping, property_defs, relation_defs, loss):
    columns = {}

    def direct(binding, path):
        if binding.extensions:
            loss("dataagent_extensions", f"{path}/extensions", "Binding extensions travel in the sidecar")
        if binding.source_field == "$entity":
            loss("unsupported_entity_role", path, "Only the first relation role can reference the DataAgent entity")
            return None
        if not _column_name_is_portable(binding.source_field):
            loss("unsupported_column_name", f"{path}/source_field", "The source field is not a portable SQL identifier")
            return None
        columns[binding.source_field] = {"name": binding.source_field, "expression": {"sql": _quoted(binding.source_field)}}
        if binding.transform != "identity" or binding.options:
            loss("unsupported_transform", path, f"DataAgent transform {binding.transform!r} travels in the sidecar")
            return None
        return _qualified_field(binding.source_field)

    property_expressions = {}
    for name, binding in mapping.bindings.items():
        expression = direct(binding, pointer("mapping", "bindings", name))
        if expression is not None:
            property_expressions[name] = expression
    relation_nodes = []
    for name, bindings in mapping.relation_bindings.items():
        path = pointer("mapping", "relation_bindings", name)
        definition = relation_defs.get(name)
        if definition is None:
            loss("unsupported_relation_binding", path, "The relation definition travels in the sidecar")
            continue
        role_names = ontology.relations[name]
        root_binding = bindings[role_names[0]]
        if root_binding.extensions:
            loss("dataagent_extensions", f"{path}/{pointer(role_names[0]).lstrip('/')}/extensions",
                 "Binding extensions travel in the sidecar")
        if root_binding.transform != "identity" or root_binding.options:
            loss("unsupported_transform", pointer("mapping", "relation_bindings", name, role_names[0]),
                 "The entity role requires a direct DataAgent entity binding")
            continue
        objects = []
        for role, role_definition in zip(role_names[1:], definition["roles"], strict=True):
            expression = direct(bindings[role], pointer("mapping", "relation_bindings", name, role))
            if expression is not None:
                objects.append({"concept": role_definition["concept"], "expression": expression})
        if len(objects) != len(role_names) - 1:
            continue
        tail = {"object_mapping": objects[-1], "relationship": name}
        for obj in reversed(objects[:-1]):
            tail = {"object_mapping": obj, "children": [tail]}
        relation_nodes.append(tail)

    if any(name not in property_expressions for name in ontology.identity_fields):
        loss("unsupported_identity_mapping", "/mapping/bindings",
             "The Ossie mapping requires a direct binding for every identity property")
        return list(columns.values()), []

    identity_mapping = {"referent_mappings": [
        {"relationship": name, "expression": property_expressions[name]} for name in ontology.identity_fields
    ]}
    children = [
        {"object_mapping": {"concept": property_defs[name]["roles"][0]["concept"], "expression": expression},
         "relationship": name}
        for name, expression in property_expressions.items()
    ]
    concept_mapping = {
        "concept": ontology.entity_type,
        "object_mappings": [identity_mapping],
        "link_mappings": [{"object_mapping": identity_mapping, "children": children + relation_nodes}],
    }
    return list(columns.values()), [concept_mapping]


def export_ossie(
    ontology: OntologyRevision,
    mapping: MappingSpec,
    *,
    instances: Iterable[EntityInstance] = (),
    assertions: Iterable[Assertion] = (),
    facts: Iterable[RelationFact] = (),
    source: str | None = None,
) -> OssieExchange:
    """Project the supported subset and retain the original DataAgent JSON contracts."""
    _check_native_mapping(ontology, mapping)
    instances, assertions, facts = list(instances), list(assertions), list(facts)
    losses: list[OssieLoss] = []

    def loss(code, path, detail):
        losses.append(OssieLoss(code, path, detail, preserved_in_sidecar=True))

    definition, properties, relations = _definition_document(ontology, mapping, facts, assertions, loss)
    columns, concept_mappings = _export_bindings(ontology, mapping, properties, relations, loss)
    if source is None:
        losses.append(OssieLoss("logical_source_unbound", "/semantic_model/datasets/0/source",
                                "The logical source_rows dataset needs a consumer-provided physical source"))
    logical_model = {
        "version": OSSIE_VERSION,
        "name": f"{mapping.id}.logical",
        "datasets": [{"name": _DATASET, "source": source if source is not None else _DATASET, "fields": columns}],
    }
    document = {
        "version": OSSIE_VERSION, "name": mapping.id,
        "ontology_ref": {"name": definition["name"]},
        "semantic_model_ref": {"name": logical_model["name"]},
        "concept_mappings": concept_mappings,
    }
    for name in ("revision", "ontology_revision", "source_fingerprint", "scope", "identity_strategy", "validation_ref"):
        if getattr(mapping, name) is not None:
            loss("dataagent_mapping_metadata", pointer("mapping", name), "Mapping metadata travels in the sidecar")
    for name in mapping.unmapped:
        loss("dataagent_unmapped_disposition", pointer("mapping", "unmapped", name),
             "The unmapped source disposition travels in the sidecar")
    if mapping.extensions:
        loss("dataagent_extensions", "/mapping/extensions", "Mapping extensions travel in the sidecar")
    loss("dataagent_revision", "/ontology/revision", "The original ontology revision travels in the sidecar")
    for kind, evidence in (("instances", instances), ("assertions", assertions), ("facts", facts)):
        if evidence:
            loss("dataagent_evidence", pointer(kind), "Instance and evidence records travel in the sidecar")
    validate_ossie_documents(definition, logical_model, document)
    sidecar = _Sidecar(
        format="dataagent.ossie.exchange", version=1, ossie_commit=OSSIE_COMMIT,
        document_digests=_document_digests(definition, logical_model, document),
        ontology=ontology, mapping=mapping, assertions=assertions, facts=facts, losses=losses,
        instances=[
            _InstanceRecord(instance=instance, decimal_fields=[
                name for name, value in instance.values.items() if isinstance(value, Decimal)
            ])
            for instance in instances
        ],
    )
    return OssieExchange(definition, logical_model, document, sidecar.model_dump(mode="json"), losses)


def _opaque_extensions(document, kind):
    extensions = {}

    def collect(node, path):
        if "custom_extensions" in node:
            extensions[f"{path}/custom_extensions"] = deepcopy(node["custom_extensions"])
        for collection in ("datasets", "fields", "relationships", "metrics"):
            for index, item in enumerate(node.get(collection, [])):
                collect(item, f"{path}/{collection}/{index}")

    collect(document, pointer(kind))
    return extensions


def _unsupported_fields(node, path, supported, loss):
    for key, value in node.items():
        if key in supported:
            continue
        field_path = path + pointer(key)
        if key in {"requires", "derived_by"}:
            for index, expression in enumerate(value):
                loss("unsupported_expression", f"{field_path}/{index}", f"Expression kept opaque: {expression}")
        elif key == "custom_extensions":
            loss("opaque_vendor_extension", field_path, "Vendor data is available as opaque extensions")
        else:
            loss("unsupported_ossie_field", field_path, f"{key} has no DataAgent translation")


def _import_definition(document, entity_type, loss):
    _unsupported_fields(document, "/ontology", {"name", "version", "ontology"}, loss)
    components = document["ontology"]
    candidates = [(index, node) for index, node in enumerate(components)
                  if node["type"] == "EntityType" and (entity_type is None or node["concept"] == entity_type)]
    if len(candidates) != 1:
        loss("unsupported_entity_selection", "/ontology/ontology", "Select exactly one EntityType for import")
        return None, {}
    index, component = candidates[0]
    for other, node in enumerate(components):
        if index != other:
            loss("unsupported_concept", f"/ontology/ontology/{other}",
                 f"Concept {node['concept']!r} is outside the selected entity definition")
    path = f"/ontology/ontology/{index}"
    _unsupported_fields(component, path, {"concept", "type", "identify_by", "relationships"}, loss)
    identity = component.get("identify_by", [])
    entity = component["concept"]
    properties, relations, role_concepts = {}, {}, {}
    seen = set()
    for index, relation in enumerate(component.get("relationships", [])):
        name = relation["name"]
        rel_path = f"{path}/relationships/{index}"
        if name in seen:
            raise OssieValidationError(f"{rel_path}/name duplicates the relationship {name!r}")
        seen.add(name)
        roles = relation.get("roles", [])
        names = [entity, *(role.get("name", role["concept"]) for role in roles)]
        concepts = [entity, *(role["concept"] for role in roles)]
        _unsupported_fields(relation, rel_path,
                            {"name", "roles", "multiplicity", "description", "verbalizes"}, loss)
        if len(names) < 2 or len(set(names)) != len(names):
            loss("unsupported_relationship_roles", f"{rel_path}/roles",
                 "A DataAgent relation requires distinct ordered roles and arity of at least two")
            continue
        multiplicity = relation.get("multiplicity")
        if (len(roles) == 1 and concepts[1] in _PROPERTY_TYPES
                and multiplicity in {"ManyToOne", "OneToOne"}
                and ("name" not in roles[0] or name in identity)):
            properties[name] = PropertyDefinition(
                value_type=_PROPERTY_TYPES[concepts[1]], description=relation.get("description", ""),
            )
            if "name" in roles[0]:
                loss("unsupported_property_role_name", f"{rel_path}/roles/0/name",
                     "A DataAgent property does not name its value role")
            if multiplicity == "OneToOne":
                loss("unsupported_multiplicity", f"{rel_path}/multiplicity",
                     "The reverse uniqueness constraint has no DataAgent property equivalent")
        else:
            relations[name] = names
            loss("unsupported_role_concepts", f"{rel_path}/roles", "DataAgent relation definitions retain role names and order")
            if multiplicity:
                loss("unsupported_multiplicity", f"{rel_path}/multiplicity",
                     "DataAgent relation definitions do not enforce this multiplicity")
            if relation.get("description"):
                loss("unsupported_ossie_field", f"{rel_path}/description", "DataAgent relations do not carry descriptions")
        role_concepts[name] = concepts
        if relation["verbalizes"]:
            loss("unsupported_ossie_field", f"{rel_path}/verbalizes", "DataAgent does not import verbalization templates")

    if not identity or len(set(identity)) != len(identity) or any(name not in properties for name in identity):
        loss("unsupported_identity", f"{path}/identify_by", "Expected ordered identifiers backed by scalar properties")
        return None, {}
    ontology = OntologyRevision(
        id=document["name"], revision=f"ossie-{digest(document)}", entity_type=entity,
        properties=properties, identity_fields=identity, relations=relations,
    )
    return ontology, role_concepts


def _import_columns(document, loss):
    _unsupported_fields(document, "/semantic_model", {"name", "version", "datasets"}, loss)
    datasets = document["datasets"]
    if len(datasets) != 1:
        loss("unsupported_dataset_count", "/semantic_model/datasets", "Expected one logical dataset")
        return None, {}
    dataset = datasets[0]
    path = "/semantic_model/datasets/0"
    _unsupported_fields(dataset, path, {"name", "source", "fields"}, loss)
    columns = {}
    seen = set()
    for index, field in enumerate(dataset.get("fields", [])):
        field_path = f"{path}/fields/{index}"
        name = field["name"]
        if name in seen:
            raise OssieValidationError(f"{field_path}/name duplicates logical field {name!r}")
        seen.add(name)
        _unsupported_fields(field, field_path, {"name", "expression"}, loss)
        expression = field["expression"]
        sql = expression.get("sql", "").strip()
        if "dialects" in expression:
            loss("unsupported_expression", f"{field_path}/expression/dialects",
                 "Dialect expressions are kept opaque")
        if (_COLUMN.fullmatch(sql) is None or sql.upper() in _SQL_SPECIAL_VALUES
                or not _column_name_is_portable(_unquoted(sql))):
            loss("unsupported_expression", f"{field_path}/expression",
                 "A logical field must be a direct physical column for DataAgent import")
            continue
        columns[name] = _unquoted(sql)
    return dataset["name"], columns


def _matching_identifier(token, names):
    name = _unquoted(token)
    if token.startswith('"'):
        return name if name in names else None
    candidates = [candidate for candidate in names if candidate.upper() == name.upper()]
    return candidates[0] if len(candidates) == 1 else None


def _import_mapping(document, ontology, role_concepts, dataset, columns, fingerprint, loss):
    _unsupported_fields(document, "/mapping",
                        {"name", "version", "ontology_ref", "semantic_model_ref", "concept_mappings"}, loss)
    for reference in ("ontology_ref", "semantic_model_ref"):
        if "iri" in document[reference]:
            loss("document_location_ignored", f"/mapping/{reference}/iri", "The supplied document is used by name")
    if ontology is None or dataset is None:
        return None
    if not fingerprint:
        loss("source_fingerprint_required", "/mapping/source_fingerprint",
             "Supply the observed source fingerprint to construct a DataAgent mapping")
        return None

    def source_binding(expression, path):
        match = _FIELD_REF.fullmatch(expression.strip())
        if match and _matching_identifier(match["dataset"], [dataset]) == dataset:
            field_name = _matching_identifier(match["field"], columns)
            if field_name is not None:
                return FieldBinding(source_field=columns[field_name])
        loss("unsupported_expression", path, "Expected a qualified direct field backed by a physical column")
        return None

    def identity_mapping(node, path):
        if node.get("concept", ontology.entity_type) != ontology.entity_type:
            loss("unsupported_object_mapping", path, "Expected an object mapping for the selected entity")
            return None
        if "expression" in node:
            if "referent_mappings" in node or len(ontology.identity_fields) != 1:
                loss("unsupported_expression", f"{path}/expression",
                     "A simple object expression needs one declared identity property")
                return None
            value = source_binding(node["expression"], f"{path}/expression")
            return {ontology.identity_fields[0]: value} if value is not None else None
        referents = node["referent_mappings"]
        result = {}
        valid = True
        for index, referent in enumerate(referents):
            ref_path = f"{path}/referent_mappings/{index}"
            name = referent["relationship"]
            if "expression" not in referent or "referent_mappings" in referent:
                loss("unsupported_referent_mapping", ref_path, "Nested identity referents are outside the subset")
                valid = False
                continue
            value = source_binding(referent["expression"], f"{ref_path}/expression")
            if value is None or name in result:
                valid = False
                continue
            result[name] = value
        if not valid or set(result) != set(ontology.identity_fields):
            loss("unsupported_identity_mapping", path, "Expected one direct binding for each identity property")
            return None
        return result

    matching = []
    for index, concept in enumerate(document["concept_mappings"]):
        path = f"/mapping/concept_mappings/{index}"
        if concept["concept"] == ontology.entity_type:
            matching.append((concept, path))
        else:
            loss("unsupported_concept_mapping", path, f"Mapping for {concept['concept']!r} is outside the selected entity")
    if len(matching) != 1:
        loss("unsupported_concept_mapping", "/mapping/concept_mappings",
             "Expected one mapping for the selected entity")
        return None
    concept, path = matching[0]
    roots = concept.get("link_mappings", [])
    objects = concept.get("object_mappings", [])
    if len(objects) > 1:
        loss("unsupported_object_mapping", f"{path}/object_mappings", "Alternate identity mappings are outside the subset")
        return None
    identity = identity_mapping(objects[0], f"{path}/object_mappings/0") if objects else None
    if objects and identity is None:
        return None

    properties, relations = {}, {}
    declared = set()
    conflicts = set()

    def visit(node, path, bound, concepts):
        obj = node["object_mapping"]
        current = None
        if "referent_mappings" in obj or "expression" not in obj:
            loss("unsupported_object_mapping", f"{path}/object_mapping", "Expected a direct value expression")
        else:
            current = source_binding(obj["expression"], f"{path}/object_mapping/expression")
        values = [*bound, current]
        role_types = [*concepts, obj.get("concept")]
        name = node.get("relationship")
        if name is not None:
            expected = role_concepts.get(name, [])[1:]
            if name in declared:
                conflicts.add(name)
                loss("alternate_link_mapping", path, "Multiple patterns for the same relationship are outside the subset")
            declared.add(name)
            if (len(values) != len(expected) or not expected
                    or any(actual is not None and actual != wanted
                           for actual, wanted in zip(role_types, expected, strict=False))
                    or any(item not in _PROPERTY_TYPES for item in expected)):
                loss("unsupported_link_mapping", path, "Expected an ordered path of direct scalar role bindings")
            elif all(value is not None for value in values):
                if name in ontology.properties:
                    properties[name] = values[0]
                else:
                    first_role, *other_roles = ontology.relations[name]
                    relations[name] = {
                        first_role: FieldBinding(source_field="$entity"),
                        **dict(zip(other_roles, values, strict=True)),
                    }
        for index, child in enumerate(node.get("children", [])):
            visit(child, f"{path}/children/{index}", values, role_types)

    for index, root in enumerate(roots):
        root_path = f"{path}/link_mappings/{index}"
        root_identity = identity_mapping(root["object_mapping"], f"{root_path}/object_mapping")
        if root_identity is None:
            continue
        if identity is None:
            identity = root_identity
        if root_identity != identity:
            loss("alternate_link_mapping", root_path, "Link uses a different entity identity binding")
            continue
        if "relationship" in root:
            loss("unsupported_link_mapping", root_path, "DataAgent does not support unary links")
        for child_index, child in enumerate(root.get("children", [])):
            visit(child, f"{root_path}/children/{child_index}", [], [])
    if identity is None:
        loss("unsupported_identity_mapping", path, "No direct mapping for the entity's identity")
        return None
    for name, binding in identity.items():
        if name not in declared:
            properties[name] = binding
        elif name in properties and properties[name] != binding:
            conflicts.add(name)
            loss("alternate_link_mapping", pointer("mapping", "bindings", name),
                 "The identity object and property link bind different source fields")
    for name in conflicts:
        properties.pop(name, None)
        relations.pop(name, None)
    if any(name not in properties for name in ontology.identity_fields):
        # Without all parts of the identity, relation materialization could create candidate entities.
        relations.clear()
        loss("incomplete_identity_mapping", f"{path}/object_mappings",
             "Relation bindings were excluded because identity links are incomplete")
    return MappingSpec(
        id=document["name"], revision=f"ossie-{digest(document)}",
        ontology_revision=f"{ontology.id}@{ontology.revision}", source_fingerprint=fingerprint,
        bindings=properties, relation_bindings=relations,
    )


def import_ossie(
    ontology: dict,
    semantic_model: dict,
    mapping: dict,
    *,
    sidecar: dict | None = None,
    entity_type: str | None = None,
    source_fingerprint: str | None = None,
) -> OssieImport:
    """Validate and import a projection or recover its bound DataAgent records."""
    validate_ossie_documents(ontology, semantic_model, mapping)
    extensions = {
        **_opaque_extensions(semantic_model, "semantic_model"),
        **_opaque_extensions(mapping, "mapping"),
    }
    if sidecar is not None:
        try:
            native = _Sidecar.model_validate(sidecar)
        except ValidationError as exc:
            raise OssieValidationError(f"/sidecar: {exc}") from exc
        if native.document_digests != _document_digests(ontology, semantic_model, mapping):
            raise OssieValidationError("/sidecar/document_digests: digest differs from the supplied Ossie documents")
        if entity_type is not None and entity_type != native.ontology.entity_type:
            raise OssieValidationError("/sidecar/ontology/entity_type differs from the requested entity")
        if source_fingerprint is not None and source_fingerprint != native.mapping.source_fingerprint:
            raise OssieValidationError("/sidecar/mapping/source_fingerprint differs from the observed source")
        _check_native_mapping(native.ontology, native.mapping)
        return OssieImport(
            native.ontology, native.mapping, native.losses,
            instances=[record.restore() for record in native.instances],
            assertions=native.assertions, facts=native.facts, opaque_extensions=extensions,
        )

    losses: list[OssieLoss] = []

    def loss(code, path, detail):
        losses.append(OssieLoss(code, path, detail))

    definition, role_concepts = _import_definition(ontology, entity_type, loss)
    dataset, columns = _import_columns(semantic_model, loss)
    bindings = _import_mapping(mapping, definition, role_concepts, dataset, columns, source_fingerprint, loss)
    return OssieImport(definition, bindings, losses, opaque_extensions=extensions)
