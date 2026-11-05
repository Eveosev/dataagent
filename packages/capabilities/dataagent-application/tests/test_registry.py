"""Registry / catalog consistency and MCP tool listing (07 §3, §11.1)."""

from __future__ import annotations

import dataagent_application as app
from dataagent_runtime.interfaces.mcp_server import tools_payload


def test_registry_matches_catalog_snapshot():
    app.validate_registry()  # raises on drift
    assert len(app.list_operations()) == 13


def test_catalog_source_files_match_modules():
    from dataagent_application.registry import load_catalog

    catalog = load_catalog()
    by_operation = {a["operation"]: a for a in catalog["atoms"]}
    for spec in app.list_operations():
        atom = by_operation[spec.operation]
        assert spec.source_file == atom["source_file"], spec.operation
        assert spec.capability_id == atom["id"], spec.operation


def test_mcp_tools_payload_lists_all_operations_with_annotations():
    tools = tools_payload(app.list_operations)
    names = {tool["name"] for tool in tools}
    assert len(tools) == 13
    assert "execute_duckdb_sql" in names
    for tool in tools:
        assert tool["inputSchema"]["required"]  # context always required
        annotations = tool["annotations"]
        assert annotations["openWorldHint"] is False
        assert "readOnlyHint" in annotations and "destructiveHint" in annotations
