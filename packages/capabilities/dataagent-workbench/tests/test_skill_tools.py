"""Every tool name a skill names must exist in ``tool_schema.TOOLS``.

Skills under ``packages/capabilities/*/skills`` are the only place the agent
learns workbench tool names from, so a typo there becomes a hallucinated tool.
A skill that references workbench tools at all may only name tools, tool
arguments and tool enum values that ``tool_schema`` actually declares; skills
of other packages that name no workbench tool are out of scope.
"""
from __future__ import annotations

import json
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


def test_query_comparison_and_evidence_bounds_are_part_of_the_skill():
    """FDE2-04/07/09: the skill must name the bounded way to answer."""
    skill = (REPOSITORY / 'packages/capabilities/dataagent-intake/skills/'
             'dataagent-intake/SKILL.md').read_text(encoding='utf-8')
    # FDE2-04: tool cannot answer -> say so, never compute by reading originals.
    assert '当前工具无法回答' in skill
    assert 'shell_exec' in skill and 'fs_read' in skill
    # FDE2-04: no per-turn workspace listing.
    assert '不在每轮开始列出工作区' in skill
    # FDE2-04: comparison questions use the ontology query surface.
    assert 'include_related' in skill
    for op in ('gt', 'gte', 'lt', 'lte'):
        assert op in skill
    # FDE2-07: publish prepare dispositions need an explicit user decision.
    assert 'accept' in skill and 'exclude' in skill
    assert '第 10 条' in skill
    # FDE3-02: the cross-field comparison is one tool call, not two reads.
    assert 'related_field' in skill
    assert 'comparison' in skill and 'uncomparable' in skill
    # FDE3-02: rows are slim; anchors are opt-in.
    assert 'detail="anchors"' in skill
    # FDE3-08: answer numbers come from the tool counts, never estimates.
    assert '计数字段' in skill and '不估算' in skill
    # FDE3-11: Chinese business names; column_N is not an identity field.
    assert '中文业务名' in skill and 'column_N' in skill
    # FDE3-11: no sub-agent spawning from the skill.
    assert 'spawn_agent' in skill

    schema = MODELS['ontology_query'].model_json_schema()
    assert 'include_related' in schema['properties']
    assert schema['properties']['detail']['enum'] == ['slim', 'anchors']
    condition = schema['$defs']['OntologyQueryCondition']
    assert set(condition['properties']['op']['enum']) == {
        'eq', 'in', 'contains', 'gt', 'gte', 'lt', 'lte'}
    assert {'property', 'field', 'related_field'} <= set(condition['properties'])
    evidence = MODELS['intake_inference'].model_json_schema()['properties']
    assert {'detail_table', 'detail_section', 'detail_offset', 'detail_limit'} <= set(evidence)


def test_skill_comparison_example_is_a_where_array():
    """The comparison example must be one where element, not three filters.

    A bare object after ``where`` is not a list; the MCP layer would not parse
    it as one cross-field condition.  The example is extracted from the skill
    and validated against the same model the tool schema declares.
    """
    skill = (REPOSITORY / 'packages/capabilities/dataagent-intake/skills/'
             'dataagent-intake/SKILL.md').read_text(encoding='utf-8')
    match = re.search(r'`where` 写 `(\[[^`]+\])`', skill)
    assert match, 'skill must show the comparison inside a where array'
    example = json.loads(match.group(1))
    assert isinstance(example, list) and len(example) == 1
    query = MODELS['ontology_query'].model_validate(
        {'ontology_id': 'demo', 'where': example})
    condition, = query.where
    assert condition.field == '金额'
    assert condition.related_field == '限额'
    assert condition.op == 'gt'
    assert condition.value is None
    # One cross-field comparison, not field=金额 + op=gt + related_field=限额.
    assert condition.property_name() == '金额'
    assert condition.related_name() == '限额'
