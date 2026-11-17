"""Acceptance phases used by scripts/verify_local.py."""

from . import api_workflow, bootstrap, discovery, files, mixed_workflow, sources

PHASES = {
    'bootstrap': bootstrap,
    'files': files,
    'sources': sources,
    'api-workflow': api_workflow,
    'mixed-workflow': mixed_workflow,
    'discovery': discovery,
}
