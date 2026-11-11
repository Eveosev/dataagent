"""Validate documents with the pinned Apache Ossie schema closure."""

from functools import cache
from importlib.resources import files
import json

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


OSSIE_COMMIT = "d700cdeac41d15a7004eb2f9b0b38a2b1d517a18"
OSSIE_VERSION = "0.3.0.dev0"
_SCHEMA_PATHS = {
    "ontology": "ontology/ontology.json",
    "semantic_model": "core-spec/ossie-schema.json",
    "mapping": "ontology/mapping.json",
}
_UPSTREAM_RAW = "https://raw.githubusercontent.com/apache/ossie/main/"


class OssieValidationError(ValueError):
    """The documents or their DataAgent sidecar violate the exchange contract."""


def pointer(*parts: str | int) -> str:
    return "".join("/" + str(part).replace("~", "~0").replace("/", "~1") for part in parts)


@cache
def _validators() -> dict[str, Draft202012Validator]:
    schema_dir = files(__package__).joinpath("schemas")
    schemas = {
        key: json.loads(schema_dir.joinpath(path.rsplit("/", 1)[-1]).read_text(encoding="utf-8"))
        for key, path in _SCHEMA_PATHS.items()
    }
    registry = Registry()
    for key, schema in schemas.items():
        Draft202012Validator.check_schema(schema)
        resource = Resource.from_contents(schema)
        registry = registry.with_resource(schema["$id"], resource)
        registry = registry.with_resource(_UPSTREAM_RAW + _SCHEMA_PATHS[key], resource)
    return {
        key: Draft202012Validator(schema, registry=registry)
        for key, schema in schemas.items()
    }


def validate_ossie_documents(ontology: dict, semantic_model: dict, mapping: dict) -> None:
    documents = {"ontology": ontology, "semantic_model": semantic_model, "mapping": mapping}
    for kind, validator in _validators().items():
        error = next(validator.iter_errors(documents[kind]), None)
        if error is not None:
            raise OssieValidationError(f"{pointer(kind, *error.absolute_path)}: {error.message}")
    for ref, document in (("ontology_ref", ontology), ("semantic_model_ref", semantic_model)):
        if mapping[ref]["name"] != document["name"]:
            raise OssieValidationError(f"/mapping/{ref}/name does not match the supplied document")
