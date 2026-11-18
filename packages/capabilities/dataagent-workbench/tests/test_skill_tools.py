"""Every tool name a skill names must exist in ``tool_schema.TOOLS``.

Skills under ``packages/capabilities/*/skills`` are the only place the agent
learns workbench tool names from, so a typo there becomes a hallucinated tool.
A skill that references workbench tools at all may only name tools, tool
arguments and tool enum values that ``tool_schema`` actually declares; skills
of other packages that name no workbench tool are out of scope.
"""
from __future__ import annotations

import re
from pathlib import Path

from dataagent_workbench.tool_schema import MODELS, TOOLS

REPOSITORY = Path(__file__).resolve().parents[4]
SKILLS = sorted(REPOSITORY.glob('packages/capabilities/*/skills/**/SKILL.md'))

# intake_start, mapping_apply, … -> {intake, mapping, …}: the first segment of
# a workbench tool name; a snake_case token starting with one of these looks
# like a tool reference and must resolve.
TOOL_NAMES = {tool['name'] for tool in TOOLS}
TOOL_PREFIXES = {name.split('_', 1)[0] for name in TOOL_NAMES}

IDENTIFIER = re.compile(r'\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b')


def schema_names(model) -> set[str]:
    """Collect every property name and enum value of one input schema."""
    names: set[str] = set()

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key == 'properties' and isinstance(value, dict):
                    names.update(value)
                if key == 'enum' and isinstance(value, list):
                    names.update(str(item) for item in value)
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(model.model_json_schema())
    return names


# Tools, their argument names and their enum values (modes, dispositions,
# workflow operations, …) are the identifiers a skill may legitimately name.
ALLOWED = TOOL_NAMES | set().union(*(schema_names(model) for model in MODELS.values()))


def test_skills_were_found():
    assert SKILLS, 'no skill files found; the glob in this test went stale'


def test_skill_tool_names_exist_in_tool_schema():
    checked, missing = [], []
    for path in SKILLS:
        tokens = set(IDENTIFIER.findall(path.read_text(encoding='utf-8')))
        if not tokens & TOOL_NAMES:
            continue  # a skill that names no workbench tool is out of scope
        checked.append(path)
        unknown = sorted(
            token for token in tokens
            if token.split('_', 1)[0] in TOOL_PREFIXES and token not in ALLOWED)
        if unknown:
            missing.append(f'{path.relative_to(REPOSITORY)}: {", ".join(unknown)}')
    assert checked, 'no skill references workbench tools; the check went stale'
    assert not missing, (
        '技能里出现 tool_schema 不存在的工具名:\n' + '\n'.join(missing))
