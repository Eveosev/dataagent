"""Read domain definitions from explicit versioned assets."""
from pathlib import Path
from dataagent_contracts.ontology import OntologyRevision


def load_definition(path):
    return OntologyRevision.model_validate_json(Path(path).read_text())
