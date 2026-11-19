"""Read-only queries over published ontology instances.

The only source is a ``release`` record.  A release points at the exact
preview revision it published; instances are read from that frozen revision,
never from ``current``, the fact table or a task's in-memory state.  A partial
release carries only the saved objects, which are recovered from the release
marker written next to that exact preview and verified against the release
digest before any row is returned.

Queries keep the workbench's existing authority check and disclosure scope:
the caller must be the local workspace owner, and values bound to source
fields outside ``allowed_model_fields`` are not returned.
"""
from __future__ import annotations

import base64
import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from itertools import permutations
from typing import Any, Iterable, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from dataagent_contracts.ontology import (
    ConceptDefinition, OntologyRevision, RelationDefinition,
)
from dataagent_ontology.identity import digest
from dataagent_ontology.registry import entry_row, parse_entry


MAX_LIMIT = 200
DEFAULT_LIMIT = 50
_READ_LIMIT = 1000
# Related reports describe the returned page only (cursor pagination is the
# unit the caller sees), and both lists are bounded so one page cannot emit an
# unbounded payload.  A page has at most MAX_LIMIT rows, one missing entry per
# row, so the missing cap only matters if the page limit grows.
_MAX_RELATED_MISSING = MAX_LIMIT
_MAX_RELATED_CANDIDATES = 20
# Relations are materialized as role values, so a composite target identity is
# usually carried as one joined string (a ``combine`` binding).  Well-known
# separators are tried instead of asking the caller to repeat the binding.
_RELATED_SEPARATORS = ('|', ',', '/', '·', '-', ' ', '_', '\t', '::',
                       '\x1f', '\x01', '')


_ORDERED_TYPES = frozenset({'decimal', 'integer', 'date'})
_ORDERED_OPS = frozenset({'gt', 'gte', 'lt', 'lte'})
# A dict carrying any of these keys is one condition object, not a shorthand
# map of property names to equality values.  ``field`` is the MCP-facing alias
# of ``property``; ``op``/``related_field`` only occur in condition objects.
_CONDITION_KEYS = frozenset({'property', 'field', 'op', 'related_field'})


def _is_condition_object(value: dict) -> bool:
    return bool(_CONDITION_KEYS.intersection(value))


class OntologyQueryCondition(BaseModel):
    """One attribute predicate.

    ``gt``/``gte``/``lt``/``lte`` compare by value and are accepted only for
    ``decimal``, ``integer`` and ``date`` properties; other comparisons keep
    the string/array semantics.

    ``field`` is accepted as an alias for ``property``.  A condition carrying
    ``related_field`` compares the property against the named property of the
    object fetched through ``include_related`` (for example amount gt limit);
    that form takes no ``value`` and is only accepted for ordered types.
    """
    model_config = ConfigDict(extra='forbid')

    property: str | None = Field(default=None,
        description='概念已定义的属性名（与 field 二选一）')
    field: str | None = Field(default=None,
        description='property 的别名（与 property 二选一）')
    op: Literal['eq', 'in', 'contains', 'gt', 'gte', 'lt', 'lte'] = Field(
        default='eq', description='比较方式；gt/gte/lt/lte 只用于 decimal/integer/date 属性')
    value: Any = Field(default=None, description='比较值；in 必须是数组')
    related_field: str | None = Field(default=None,
        description='与关联对象的该属性比较（需同时给 include_related；只用于 '
                    'decimal/integer/date，如 {"property":"amount","op":"gt",'
                    '"related_field":"limit"}）；可写 related.limit')

    @model_validator(mode='after')
    def _check_shape(self):
        if bool(self.property) == bool(self.field):
            raise ValueError('exactly one of property or field is required')
        if self.related_field is not None:
            if not self.related_name():
                raise ValueError('related_field must name an attribute')
            if self.op not in _ORDERED_OPS:
                raise ValueError(
                    'related_field comparison only supports gt/gte/lt/lte')
            if self.value is not None:
                raise ValueError(
                    'related_field compares against the related object; omit value')
        return self

    def property_name(self) -> str:
        return str(self.property or self.field or '').strip()

    def related_name(self) -> str:
        text = str(self.related_field or '').strip()
        if text.startswith('related.'):
            return text[len('related.'):]
        return text


class OntologyQueryRelated(BaseModel):
    """Read one related object along a published relation for every row."""
    model_config = ConfigDict(extra='forbid')

    relation: str = Field(min_length=1, description='本体已发布的关系名')
    fields: list[str] = Field(default_factory=list, max_length=50,
        description='要带回的关联对象属性；留空时只带身份字段')


class OntologyQuery(BaseModel):
    """Input of the ``ontology_query`` read-only tool."""
    model_config = ConfigDict(extra='forbid')

    ontology_id: str = Field(min_length=1, description='本体 ID（必填）')
    concept: str | None = Field(default=None,
        description='概念名；多概念本体必填，单概念可省略')
    revision: str | None = Field(default=None,
        description='本体修订号（如 "1" 或 "sales-model@1"）；缺省用注册表当前修订')
    where: list[OntologyQueryCondition] = Field(default_factory=list, max_length=50,
        description='属性条件，多个条件按与（AND）组合；支持 eq/in/contains/gt/gte/lt/lte；'
                    '对比关联属性用 {"property":"amount","op":"gt","related_field":"limit"}')
    include_related: OntologyQueryRelated | None = Field(default=None,
        description='沿已发布关系带回关联对象的指定属性；每条结果附 related，未命中为 null 并计数；'
                    'related_field 比较必须同时给这一项')
    detail: Literal['slim', 'anchors'] = Field(default='slim',
        description='slim（默认）每行只带实例 id、属性值、来源一句话定位、release_ref 与所属任务；'
                    'anchors 额外带逐属性来源锚点（按需取）')
    limit: int = Field(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT,
        description='本页条数，最大 200')
    cursor: str | None = Field(default=None, description='上一页返回的 next_cursor')

    @field_validator('where', mode='before')
    @classmethod
    def _where_shorthand(cls, value):
        """Accept one condition object or a property->value equality map."""
        if value is None:
            return []
        if isinstance(value, dict):
            if _is_condition_object(value):
                return [value]
            return [{'property': name, 'op': 'eq', 'value': item}
                    for name, item in value.items()]
        return value


class OntologyInstancesSummary(BaseModel):
    """Input of the ``ontology_instances_summary`` read-only tool."""
    model_config = ConfigDict(extra='forbid')

    ontology_id: str | None = Field(default=None,
        description='只汇总该本体；缺省列出所有未停用本体')
    include_deactivated: bool = Field(default=False,
        description='是否包含已停用本体（默认不列）')


def parse_where(text: str | None) -> list[OntologyQueryCondition]:
    """Decode the HTTP ``where=`` parameter.

    Accepted forms are a JSON array of condition objects, one condition
    object, or an object mapping a property name to an equality value.
    """
    if text is None:
        return []
    if not isinstance(text, str) or not text.strip():
        raise ValueError('where must be a JSON object or array')
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError('where must be valid JSON') from exc
    if isinstance(data, dict):
        if _is_condition_object(data):
            return [OntologyQueryCondition.model_validate(data)]
        return [OntologyQueryCondition(property=name, op='eq', value=value)
                for name, value in data.items()]
    if isinstance(data, list):
        return [OntologyQueryCondition.model_validate(item) for item in data]
    raise ValueError('where must be a JSON object or array')


def parse_related(text: str | None = None, relation: str | None = None,
                  fields: str | None = None) -> OntologyQueryRelated | None:
    """Decode the HTTP ``include_related`` parameter.

    ``include_related`` is a JSON object or relation name.  ``related`` plus
    ``related_fields`` (comma separated) is the plain query-string form.
    """
    if text:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError('include_related must be valid JSON') from exc
        if isinstance(data, str):
            data = {'relation': data}
        if not isinstance(data, dict):
            raise ValueError('include_related must be a JSON object or relation name')
        return OntologyQueryRelated.model_validate(data)
    if relation:
        names = [item.strip() for item in (fields or '').split(',') if item.strip()]
        return OntologyQueryRelated(relation=relation, fields=names)
    if fields:
        raise ValueError('related_fields requires related')
    return None


def _encode_cursor(key: tuple[str, str]) -> str:
    raw = json.dumps(list(key), separators=(',', ':')).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip('=')


def _decode_cursor(cursor: str) -> tuple[str, str]:
    try:
        padded = cursor + '=' * (-len(cursor) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded.encode()))
    except (ValueError, TypeError) as exc:
        raise ValueError('invalid cursor') from exc
    if (not isinstance(data, list) or len(data) != 2
            or not all(isinstance(part, str) for part in data)):
        raise ValueError('invalid cursor')
    return data[0], data[1]


def _coerce(value: Any, value_type: str) -> Any:
    """Compare stored JSON values and query values on the ontology's terms."""
    if value is None:
        return None
    try:
        if value_type == 'decimal':
            return Decimal(str(value))
        if value_type == 'integer':
            if isinstance(value, bool):
                raise ValueError('boolean is not an integer')
            number = Decimal(str(value))
            if number != number.to_integral_value():
                raise ValueError('not an integer')
            return int(number)
        if value_type == 'boolean':
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                lowered = value.strip().lower()
                if lowered in {'true', '1', 'yes'}:
                    return True
                if lowered in {'false', '0', 'no'}:
                    return False
            raise ValueError('not a boolean')
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f'query value {value!r} does not match {value_type}') from exc
    return str(value)


def _order(value: Any, value_type: str, *, query: bool = False) -> Any:
    """The ordered value of a comparison on the ontology's terms.

    Only ``decimal``, ``integer`` and ``date`` properties are ordered.  A
    stored value that does not parse never matches; a query value that does
    not parse is an input error the caller can fix.
    """
    if value is None:
        return None
    try:
        if value_type == 'decimal':
            return Decimal(str(value))
        if value_type == 'integer':
            if isinstance(value, bool):
                raise ValueError('boolean is not an integer')
            number = Decimal(str(value))
            if number != number.to_integral_value():
                raise ValueError('not an integer')
            return int(number)
        if value_type == 'date':
            text = str(value).strip()
            try:
                return date.fromisoformat(text)
            except ValueError:
                return datetime.fromisoformat(text).date()
        raise ValueError('comparison is only supported on decimal/integer/date')
    except (InvalidOperation, TypeError, ValueError) as exc:
        if query:
            raise ValueError(
                f'query value {value!r} does not match ordered {value_type}'
            ) from exc
        return None


def _matches(actual: Any, expected: Any, op: str, value_type: str) -> bool:
    if op == 'eq':
        if isinstance(expected, list):
            return any(_matches(actual, item, 'eq', value_type) for item in expected)
        return _coerce(actual, value_type) == _coerce(expected, value_type)
    if op == 'in':
        if not isinstance(expected, list):
            raise ValueError('in requires a JSON array')
        return any(_coerce(actual, value_type) == _coerce(item, value_type)
                   for item in expected)
    if op == 'contains':
        if expected is None:
            raise ValueError('contains requires a value')
        if isinstance(actual, str):
            return str(expected) in actual
        if isinstance(actual, list):
            return expected in actual
        return False
    if op in {'gt', 'gte', 'lt', 'lte'}:
        if expected is None or isinstance(expected, list):
            raise ValueError('%s requires a single value' % op)
        left = _order(actual, value_type)
        right = _order(expected, value_type, query=True)
        if left is None or right is None:
            return False
        return {'gt': left > right, 'gte': left >= right,
                'lt': left < right, 'lte': left <= right}[op]
    raise ValueError(f'unknown comparison: {op}')


def _comparison_type(left: str, right: str) -> str:
    """A common ordered type for ``property op related_field``.

    Two numeric types compare as decimals so an integer column can be compared
    with a decimal limit; dates only compare with dates.
    """
    if left == 'date' or right == 'date':
        if left != right:
            raise ValueError(
                'date cannot be compared with %s; both sides must be dates'
                % (right if left == 'date' else left))
        return 'date'
    if left not in _ORDERED_TYPES or right not in _ORDERED_TYPES:
        raise ValueError('comparison is only supported on decimal/integer/date')
    return 'decimal' if 'decimal' in {left, right} else 'integer'


def _revision_key(value: str):
    try:
        return (1, int(str(value)))
    except (TypeError, ValueError):
        return (0, str(value))


def _norm_scalar(value: Any) -> str:
    """A comparison form for numbers; text stays exactly as observed."""
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, str):
        return value.strip()
    try:
        number = Decimal(str(value).strip())
        if number.is_finite():
            return format(number.normalize(), 'f')
    except (InvalidOperation, TypeError, ValueError):
        pass
    return str(value).strip()


def _identity_keys(values: dict, concept: ConceptDefinition) -> set[str]:
    """Joined forms of one object's identity, for relation-role matching.

    A composite identity reaches a relation fact as one ``combine`` value, so
    every common separator (and the reversed field order) is tried.  Missing
    identity parts produce no key at all.
    """
    parts = [values.get(field) for field in concept.identity_fields]
    if not parts or any(part is None or
                        (isinstance(part, str) and not part.strip())
                        for part in parts):
        return set()
    if len(parts) == 1:
        return {str(parts[0]).strip(), _norm_scalar(parts[0])}
    orders = [parts]
    if len(parts) <= 3:
        for order in permutations(parts):
            if list(order) != parts:
                orders.append(list(order))
    keys = set()
    for order in orders:
        raw = [str(part).strip() for part in order]
        numeric = [_norm_scalar(part) for part in order]
        for separator in _RELATED_SEPARATORS:
            keys.add(separator.join(raw))
            keys.add(separator.join(numeric))
    return keys


def _binding_hits(binding: dict, instance_id: str, current_keys: set[str]) -> bool:
    value = binding.get('value')
    if value is None:
        return False
    if str(value).strip() == str(instance_id):
        return True
    return str(value).strip() in current_keys or _norm_scalar(value) in current_keys


def _target_ids(binding: dict, targets: dict) -> list[str]:
    """Target ids a relation fact's role value resolves to, if any."""
    value = binding.get('value')
    if value is None:
        return []
    raw = targets['raw']
    candidates = set()
    text = str(value).strip()
    if text in raw:
        candidates.add(text)
    for key in {text, _norm_scalar(value)}:
        candidates.update(targets['index'].get(key) or [])
    return [item for item in candidates if item in raw]


class QueryService:
    """Published-instance reads shared by the MCP tool and the HTTP API."""

    def __init__(self, wb):
        self.wb = wb
        self.store = wb.store
        self.scope = wb.scope

    # ------------------------------------------------------------- authority
    def check(self, ctx):
        self.wb.ontology.check(ctx)

    # ---------------------------------------------------------------- registry
    def ontologies(self, ctx, *, include_deactivated: bool = False):
        """Ontology registry plus published-instance counts (workbench view).

        The service default is D4's active-only view.  The HTTP registry passes
        ``include_deactivated=true`` explicitly to preserve D1's contract of
        listing retired entries with their state.
        """
        self.check(ctx)
        data = self.wb.ontology.registry(ctx)
        if not include_deactivated:
            data['ontologies'] = [
                item for item in data.get('ontologies') or []
                if item.get('state') == 'active']
        data['include_deactivated'] = include_deactivated
        stats = self._stats()
        for item in data.get('ontologies') or []:
            entry_stats = stats.get(item.get('id'), {})
            concepts = list(item.get('concepts') or [])
            counts = {name: 0 for name in concepts}
            current = {name: 0 for name in concepts}
            for name, count in (entry_stats.get('concepts') or {}).items():
                counts.setdefault(name, 0)
                counts[name] = count
            revision_stats = (entry_stats.get('revisions') or {}).get(
                item.get('ontology_revision'), {})
            for name, count in (revision_stats.get('concepts') or {}).items():
                current.setdefault(name, 0)
                current[name] = count
            release_time = entry_stats.get('last_published_at')
            item['deactivated'] = item.get('state') != 'active'
            item['instance_counts'] = counts
            item['published_instance_count'] = sum(counts.values())
            item['current_revision_instance_counts'] = current
            item['last_published_at'] = release_time
            item['last_published_at_source'] = 'release' if release_time else None
            item['last_published_at_note'] = '未知' if not release_time else None
            item['last_published_at_unknown'] = not bool(release_time)
            item['latest_release_ref'] = entry_stats.get('latest_release_ref')
        return data

    # ----------------------------------------------------------------- summary
    def summary(self, request: OntologyInstancesSummary | dict | None, ctx):
        self.check(ctx)
        request = (request if isinstance(request, OntologyInstancesSummary)
                   else OntologyInstancesSummary.model_validate(request or {}))
        registry = self.wb.ontology.registry(ctx)
        entries = list(registry.get('ontologies') or [])
        if request.ontology_id:
            entries = [item for item in entries
                       if item.get('id') == request.ontology_id]
            if not entries:
                raise KeyError('ontology not registered: %s' % request.ontology_id)
        elif not request.include_deactivated:
            entries = [item for item in entries if item.get('state') == 'active']
        stats = self._stats()
        items = []
        for entry in entries:
            ontology_id = entry.get('id')
            entry_stats = stats.get(ontology_id, {})
            revision = entry.get('ontology_revision')
            revision_stats = (entry_stats.get('revisions') or {}).get(revision, {})
            release_time = entry_stats.get('last_published_at')
            published_at = release_time
            published_source = 'release' if release_time else None
            concepts = []
            names = list(entry.get('concepts') or [])
            for name in (entry_stats.get('concepts') or {}):
                if name not in names:
                    names.append(name)
            for name in names:
                concept_time = (entry_stats.get('concept_times') or {}).get(name)
                current_count = (revision_stats.get('concepts') or {}).get(name, 0)
                concept = {
                    'concept': name,
                    'published_instances': (entry_stats.get('concepts') or {}).get(name, 0),
                    'current_revision_instances': current_count,
                    'last_published_at': concept_time,
                    'last_published_at_note': '未知' if not concept_time else None,
                    'last_published_at_unknown': not bool(concept_time),
                }
                hint = (self._older_revision_hint(ontology_id, revision, name)
                        if current_count == 0 else None)
                if hint is not None:
                    concept['hint'] = hint
                concepts.append(concept)
            item = {
                'ontology_id': ontology_id,
                'title': entry.get('title') or ontology_id,
                'origin': entry.get('origin'),
                'state': entry.get('state'),
                'deactivated': entry.get('state') != 'active',
                'revision': revision,
                'default_concept': entry.get('default_concept'),
                'is_default': entry.get('is_default', False),
                'concepts': concepts,
                'published_instances': entry_stats.get('count', 0),
                'current_revision_instances': revision_stats.get('count', 0),
                'last_published_at': published_at,
                'last_published_at_source': published_source,
                'last_published_at_note': '未知' if not published_at else None,
                'last_published_at_unknown': not bool(published_at),
                'latest_release_ref': entry_stats.get('latest_release_ref'),
                'revisions': {
                    rev: {
                        'published_instances': value.get('count', 0),
                        'concepts': value.get('concepts') or {},
                        'last_published_at': value.get('last_published_at'),
                    }
                    for rev, value in (entry_stats.get('revisions') or {}).items()
                },
            }
            if item['current_revision_instances'] == 0 and item['published_instances']:
                hint = self._older_revision_total_hint(
                    ontology_id, revision, entry_stats)
                if hint is not None:
                    item['hint'] = hint
            items.append(item)
        return {
            'ontologies': items,
            'default_ontology': registry.get('default_ontology'),
            'pointer': registry.get('pointer'),
            'include_deactivated': request.include_deactivated,
            'published_instance_count': sum(item['published_instances'] for item in items),
        }

    # ------------------------------------------------------------------- query
    def query(self, request: OntologyQuery | dict, ctx):
        """The model-facing query result (slim rows unless ``detail=anchors``)."""
        response = self._query_full(request, ctx)
        detail = response.pop('_detail')
        return self._render(response, detail)

    def query_with_artifacts(self, request: OntologyQuery | dict, ctx):
        """Return (model result, complete result) for one query.

        The MCP transport stores the complete result (anchor detail included)
        in its result file and inlines the slim model result when it fits, so
        an agent never has to read the file just to see the rows.
        """
        response = self._query_full(request, ctx)
        detail = response.pop('_detail')
        model = self._render(response, detail)
        # Always a separate object: service_tools attaches the full payload to
        # the model result, and sharing the same dict would create a cycle.
        full = self._render(response, 'anchors')
        return model, full

    def _query_full(self, request: OntologyQuery | dict, ctx):
        self.check(ctx)
        request = (request if isinstance(request, OntologyQuery)
                   else OntologyQuery.model_validate(request))
        entry = parse_entry(entry_row(self.store, self.scope, request.ontology_id))
        if entry is None:
            current = self.store.current('ontology', request.ontology_id, scope=self.scope)
            if current is None:
                raise KeyError('ontology not registered: %s' % request.ontology_id)
            state = 'active'
            default_revision = current['revision']
        else:
            state = entry.state
            default_revision = entry.ontology_revision
        revision, definition = self._definition(
            request.ontology_id, request.revision or default_revision)
        concept_name, concept = self._concept(definition, request.concept)
        comparison_conditions = [condition for condition in request.where
                                 if condition.related_field is not None]
        if comparison_conditions and request.include_related is None:
            raise ValueError(
                'related_field requires include_related naming the relation to compare through')
        related = self._related_spec(
            definition, concept_name, request.include_related,
            extra_fields=[condition.related_name()
                          for condition in comparison_conditions])
        self._validate_conditions(request.where, concept, related)

        cursor_key = _decode_cursor(request.cursor) if request.cursor else None
        session_index = self._session_index()
        releases = list(self._releases(request.ontology_id, revision))
        targets = (self._related_targets(releases, definition, related)
                   if related is not None else None)
        # Facts stay grouped by the release that carried them.  An instance is
        # matched against its own release first; facts from another release of
        # the same ontology revision are only a fallback.
        related_facts = {}
        relation_hidden = False
        if related is not None:
            seen_facts = set()
            for release, snapshot in releases:
                release_ref = release['ref']
                hidden_relations = self._hidden_relations(snapshot['body'])
                facts = []
                for fact in snapshot['body'].get('facts') or []:
                    if fact.get('relation') != related['relation']:
                        continue
                    if fact.get('relation') in hidden_relations:
                        relation_hidden = True
                        continue
                    fact_key = fact.get('id') or json.dumps(
                        fact, sort_keys=True, ensure_ascii=False, default=str)
                    if fact_key in seen_facts:
                        continue
                    seen_facts.add(fact_key)
                    facts.append(fact)
                related_facts[release_ref] = facts
        items = []
        warnings = []
        instances_by_key = {}
        for release, snapshot in releases:
            release_ref = release['ref']
            hidden = self._hidden_properties(snapshot['body'])
            concept_by_entity = {
                item.entity_type: name for name, item in definition.concepts.items()
            }
            task = (session_index.get(release_ref) or [{}])[0]
            for instance in snapshot['instances']:
                instance_concept = concept_by_entity.get(instance.get('entity_type'))
                if instance_concept is None:
                    if len(definition.concepts) == 1:
                        instance_concept = concept_name
                    else:
                        warnings.append({
                            'code': 'ontology.instance_concept_unknown',
                            'release_ref': release_ref,
                            'instance_id': instance.get('id'),
                        })
                        continue
                if instance_concept != concept_name:
                    continue
                values, anchors = self._disclosed(instance, hidden)
                if not self._conditions_match(values, request.where, concept):
                    continue
                item = {
                    'concept': instance_concept,
                    'revision': revision,
                    'instance_id': instance.get('id'),
                    'values': values,
                    'source_refs': sorted({
                        anchor.get('source_ref') for items in anchors.values()
                        for anchor in items if anchor.get('source_ref')
                    }),
                    'source_anchors': anchors,
                    'release_ref': release_ref,
                    'release_digest': release['digest'],
                    'partial_release': snapshot['partial'],
                    'session_id': task.get('session_id') or '',
                    'task': task.get('task') or '',
                    'deactivated': state != 'active',
                    'unresolved': list(instance.get('unresolved') or []),
                }
                items.append(item)
                instances_by_key[(release_ref, instance.get('id'))] = (
                    instance, concept)
        items.sort(key=lambda item: (item['release_ref'], item['instance_id'] or ''))
        if cursor_key is not None:
            items = [item for item in items
                     if (item['release_ref'], item['instance_id'] or '') > cursor_key]
        # Resolve the related object once per candidate row.  Comparison needs
        # it before pagination so ``total`` counts the rows that actually
        # satisfy the cross-field predicate.
        related_cache = {}
        if related is not None:
            # Without a cross-field predicate only the page needs the related
            # object; a comparison filters before pagination, so it resolves
            # every candidate row.
            wanted = items if comparison_conditions else items[:request.limit]
            for item in wanted:
                key = (item['release_ref'], item['instance_id'])
                instance, item_concept = instances_by_key[key]
                related_cache[key] = self._related_for(
                    instance=instance, concept=item_concept, spec=related,
                    facts=related_facts, release_ref=item['release_ref'],
                    targets=targets)
        comparison = None
        comparison_hidden = set()
        if comparison_conditions:
            before = len(items)
            kept, comparison, comparison_hidden = self._apply_related_conditions(
                items, request.where, concept, related, related_cache)
            items = kept
            comparison['evaluated'] = before
        total = len(items)
        page = items[:request.limit]
        has_more = len(items) > len(page)
        next_cursor = (_encode_cursor((page[-1]['release_ref'],
                                       page[-1]['instance_id'] or ''))
                       if has_more and page else None)
        # Related lookups and their reports describe this page only.  Computing
        # them before pagination made page 2 repeat page 1's counts and could
        # grow ``related_missing`` with every row of the revision.
        related_matched = related_missing = related_ambiguous = 0
        related_missing_items = []
        # Comparison resolves candidates before pagination; a hidden field can
        # leave no page row at all.  Carry its warning up from the candidates
        # instead of reporting it only when a page row happens to survive.
        hidden_related_fields = set(comparison_hidden)
        if related is not None:
            for name in sorted(hidden_related_fields):
                warnings.append({
                    'code': 'ontology.related_field_hidden',
                    'relation': related['relation'],
                    'property': name,
                    'detail': '该属性不在披露范围内，未带回，也未参与跨字段比较',
                })
            for item in page:
                related_value, status, hidden_fields = related_cache[
                    (item['release_ref'], item['instance_id'])]
                item['related'] = related_value
                if status == 'ambiguous':
                    related_ambiguous += 1
                elif related_value is None:
                    related_missing += 1
                    if len(related_missing_items) < _MAX_RELATED_MISSING:
                        related_missing_items.append({
                            'release_ref': item['release_ref'],
                            'instance_id': item['instance_id'],
                            'values': item['values'],
                        })
                else:
                    related_matched += 1
                for name in hidden_fields:
                    if name not in hidden_related_fields:
                        hidden_related_fields.add(name)
                        warnings.append({
                            'code': 'ontology.related_field_hidden',
                            'relation': related['relation'],
                            'property': name,
                            'detail': '该属性不在披露范围内，未带回',
                        })
            if relation_hidden:
                warnings.append({
                    'code': 'ontology.related_relation_hidden',
                    'relation': related['relation'],
                    'detail': '该关系的角色来源字段不在披露范围内，关联未使用',
                })
        response = {
            '_detail': request.detail,
            'ontology_id': request.ontology_id,
            'ontology_revision': '%s@%s' % (request.ontology_id, revision),
            'revision': revision,
            'concept': concept_name,
            'entity_type': concept.entity_type,
            'ontology_state': state,
            'deactivated': state != 'active',
            'items': page,
            'count': len(page),
            'total': total,
            'limit': request.limit,
            'has_more': has_more,
            'next_cursor': next_cursor,
            'filters': [self._condition_dump(condition) for condition in request.where],
            'warnings': warnings,
        }
        if total == 0:
            hint = self._older_revision_hint(request.ontology_id, revision, concept_name)
            if hint is not None:
                response['hint'] = hint
        if related is not None:
            response.update({
                'include_related': {
                    'relation': related['relation'],
                    'fields': list(related['fields']),
                    'target_concept': related['target_concept'],
                    'direction': 'subject_to_object' if related['forward']
                                 else 'object_to_subject',
                },
                'related_stats': {
                    'relation': related['relation'],
                    'matched': related_matched,
                    'missing': related_missing,
                    'ambiguous': related_ambiguous,
                },
                'related_missing': related_missing_items,
                'related_missing_count': related_missing,
                'related_missing_truncated': (
                    len(related_missing_items) < related_missing),
            })
        if comparison is not None:
            response['comparison'] = comparison
        return response

    # ------------------------------------------------------- payload rendering
    @staticmethod
    def _condition_dump(condition: OntologyQueryCondition) -> dict:
        data = {'property': condition.property_name(), 'op': condition.op,
                'value': condition.value}
        if condition.related_field is not None:
            data['related_field'] = condition.related_name()
        return data

    def _render(self, response: dict, detail: str) -> dict:
        """Replace full rows with the requested row detail."""
        data = {key: value for key, value in response.items() if key != 'items'}
        data['detail'] = detail
        data['items'] = [self._render_item(item, detail)
                         for item in response.get('items') or []]
        return data

    def _render_item(self, item: dict, detail: str) -> dict:
        slim = {
            'instance_id': item['instance_id'],
            'concept': item['concept'],
            'revision': item['revision'],
            'values': item['values'],
            'release_ref': item['release_ref'],
            'session_id': item['session_id'],
            'task': item['task'],
            'partial_release': item['partial_release'],
            'deactivated': item['deactivated'],
            'unresolved': list(item.get('unresolved') or []),
        }
        if detail == 'anchors':
            slim['source_refs'] = list(item.get('source_refs') or [])
            slim['source_anchors'] = item['source_anchors']
        else:
            slim['source'] = self._compact_sources(item.get('source_anchors') or {})
        if 'related' in item:
            slim['related'] = item['related']
        return slim

    @staticmethod
    def _compact_sources(anchors: dict) -> list[dict]:
        """One-line source locations, grouped by source and property.

        Full anchors repeat the same selector, source revision and extraction
        reference for every property; the compact form keeps only the location
        fields a reader needs and names the properties that share a location.
        """
        groups: dict[Any, dict] = {}
        for name, entries in anchors.items():
            for anchor in entries:
                source_ref = anchor.get('source_ref')
                group = groups.setdefault(source_ref, {
                    'source_ref': source_ref, 'locations': {}})
                location = QueryService._compact_location(anchor)
                bucket = group['locations'].setdefault(name, [])
                if location not in bucket:
                    bucket.append(location)
        return list(groups.values())

    @staticmethod
    def _compact_location(anchor: dict) -> dict:
        selector = anchor.get('selector') or {}
        location = {}
        for key in ('page', 'paragraph', 'line'):
            if selector.get(key) is not None:
                location[key] = selector[key]
        kind = selector.get('kind')
        if kind == 'record_key':
            keys = selector.get('keys') or {}
            if keys.get('row') is not None:
                location['row'] = keys['row']
            elif keys.get('line') is not None:
                location['line'] = keys['line']
            elif keys:
                location['kind'] = 'record_key'
                location['keys'] = keys
        elif kind == 'excel_cell':
            for key in ('sheet', 'range'):
                if selector.get(key) is not None:
                    location[key] = selector[key]
        elif kind == 'text_span':
            for key in ('unit_ref', 'char_start', 'char_end'):
                if selector.get(key) is not None:
                    location[key] = selector[key]
        elif kind == 'json_pointer':
            location['kind'] = 'json_pointer'
            if selector.get('pointer') is not None:
                location['pointer'] = selector['pointer']
            # REST 分页把 1 起的响应页号放在 extensions，不随 selector 平铺；
            # 精简定位仍要保留，否则实例页只剩指针、看不出第几页。
            extensions = selector.get('extensions')
            if (isinstance(extensions, dict)
                    and extensions.get('dataagent.page') is not None):
                location.setdefault('page', extensions['dataagent.page'])
        elif kind:
            location['kind'] = kind
        return {key: value for key, value in location.items()
                if value is not None}

    # ------------------------------------------------------------------ helper
    def _definition(self, ontology_id: str, revision: str):
        text = str(revision)
        if '@' in text:
            requested_id, revision = text.rsplit('@', 1)
            if requested_id != ontology_id:
                raise ValueError('revision belongs to another ontology: %s' % text)
        row = self.store.get('ontology', ontology_id, revision, scope=self.scope)
        if row is None:
            raise KeyError('ontology revision not found: %s@%s'
                           % (ontology_id, revision))
        return revision, OntologyRevision.model_validate(row['body'])

    @staticmethod
    def _concept(definition: OntologyRevision, name: str | None):
        if name:
            try:
                return definition.resolve_concept(name)
            except KeyError:
                raise ValueError('unknown concept in ontology %s: %s'
                                 % (definition.id, name)) from None
        if len(definition.concepts) != 1:
            raise ValueError(
                'ontology %s defines %d concepts; name one'
                % (definition.id, len(definition.concepts)))
        return definition.resolve_concept()

    @staticmethod
    def _validate_conditions(conditions: Iterable[OntologyQueryCondition],
                             concept: ConceptDefinition,
                             related: dict | None = None):
        for condition in conditions:
            if condition.property_name() not in concept.properties:
                raise ValueError(
                    'property %r is not defined on concept %r'
                    % (condition.property_name(), concept.entity_type))
            value_type = concept.properties[condition.property_name()].value_type
            if condition.op == 'in' and not isinstance(condition.value, list):
                raise ValueError('in requires a JSON array')
            if condition.op == 'contains' and condition.value is None:
                raise ValueError('contains requires a value')
            if condition.related_field is not None:
                if related is None:
                    raise ValueError(
                        'related_field requires include_related naming the relation')
                target = related['target_definition']
                if condition.related_name() not in target.properties:
                    raise ValueError(
                        'related_field %r is not defined on related concept %r'
                        % (condition.related_name(), target.entity_type))
                if condition.op not in _ORDERED_OPS:
                    raise ValueError(
                        'related_field comparison only supports gt/gte/lt/lte')
                _comparison_type(
                    value_type,
                    target.properties[condition.related_name()].value_type)
                continue
            if condition.op in {'gt', 'gte', 'lt', 'lte'}:
                if value_type not in {'decimal', 'integer', 'date'}:
                    raise ValueError(
                        'comparison %s is only supported on decimal/integer/date '
                        'properties; %r is %s'
                        % (condition.op, condition.property_name(), value_type))
                if condition.value is None or isinstance(condition.value, list):
                    raise ValueError('%s requires a single value' % condition.op)
                # Parse the comparison value before any instance is read.  An
                # empty page must still reject ``gt "not-a-number"`` instead
                # of silently returning no rows.
                _order(condition.value, value_type, query=True)

    @staticmethod
    def _conditions_match(values: dict, conditions: Iterable[OntologyQueryCondition],
                          concept: ConceptDefinition):
        for condition in conditions:
            if condition.related_field is not None:
                continue
            value_type = concept.properties[condition.property_name()].value_type
            if not _matches(values.get(condition.property_name()), condition.value,
                            condition.op, value_type):
                return False
        return True

    @staticmethod
    def _compare_related(values: dict, related_fields: dict,
                         conditions: list[OntologyQueryCondition],
                         concept: ConceptDefinition,
                         target: ConceptDefinition):
        """Whether every related-field predicate holds for one row.

        Returns ``(matched, reason)``.  ``reason`` distinguishes a false
        predicate (a normal non-match that is dropped silently) from a row
        that cannot be compared because the related object or its value is
        missing.
        """
        for condition in conditions:
            left = values.get(condition.property_name())
            right = related_fields.get(condition.related_name())
            if left is None or right is None:
                return False, 'missing_value'
            value_type = _comparison_type(
                concept.properties[condition.property_name()].value_type,
                target.properties[condition.related_name()].value_type)
            left_order = _order(left, value_type)
            right_order = _order(right, value_type)
            if left_order is None or right_order is None:
                return False, 'uncomparable'
            holds = {'gt': left_order > right_order,
                     'gte': left_order >= right_order,
                     'lt': left_order < right_order,
                     'lte': left_order <= right_order}[condition.op]
            if not holds:
                return False, 'not_matched'
        return True, ''

    def _apply_related_conditions(self, items, conditions, concept, related,
                                  related_cache):
        """Filter rows by the cross-field predicates and count the rest."""
        predicates = [condition for condition in conditions
                      if condition.related_field is not None]
        target = related['target_definition']
        kept = []
        matched = missing = ambiguous = uncomparable = hidden = 0
        hidden_names = set()
        missing_items = []
        for item in items:
            related_value, status, hidden_fields = related_cache[
                (item['release_ref'], item['instance_id'])]
            if status == 'ambiguous':
                ambiguous += 1
                continue
            if status != 'matched' or related_value is None:
                missing += 1
                missing_items.append(self._missing_stub(item, 'related_missing'))
                continue
            # The disclosure layer drops hidden fields before they reach here.
            # Comparing a missing key would look like a normal predicate miss,
            # so report the row as uncomparable and carry the field name up to
            # the response warning.
            hidden_predicates = {
                condition.related_name() for condition in predicates
            }.intersection(hidden_fields or ())
            if hidden_predicates:
                hidden_names.update(hidden_predicates)
                hidden += 1
                uncomparable += 1
                missing_items.append(
                    self._missing_stub(item, 'related_field_hidden'))
                continue
            holds, reason = self._compare_related(
                item['values'], related_value.get('fields') or {},
                predicates, concept, target)
            if holds:
                kept.append(item)
                matched += 1
            elif reason in {'missing_value', 'uncomparable'}:
                uncomparable += 1
                missing_items.append(self._missing_stub(item, reason))
            # reason == 'not_matched' is a normal predicate miss: drop it.
        first = predicates[0]
        comparison = {
            'field': first.property_name(),
            'op': first.op,
            'related_field': first.related_name(),
            'relation': related['relation'],
            'conditions': [
                {'property': condition.property_name(), 'op': condition.op,
                 'related_field': condition.related_name()}
                for condition in predicates],
            'matched': matched,
            'missing': missing,
            'uncomparable': uncomparable,
            'ambiguous': ambiguous,
            'hidden': hidden,
            'hidden_fields': sorted(hidden_names),
            'missing_items': missing_items[:_MAX_RELATED_MISSING],
            'missing_truncated': len(missing_items) > _MAX_RELATED_MISSING,
        }
        return kept, comparison, hidden_names

    @staticmethod
    def _missing_stub(item: dict, reason: str) -> dict:
        return {
            'release_ref': item['release_ref'],
            'instance_id': item['instance_id'],
            'values': item['values'],
            'reason': reason,
        }

    @staticmethod
    def _related_spec(definition: OntologyRevision, concept_name: str,
                      request: OntologyQueryRelated | None,
                      extra_fields: Iterable[str] = ()):
        """Resolve a published relation into a traversal in one direction."""
        if request is None:
            return None
        relation = definition.relations.get(request.relation)
        if relation is None:
            raise ValueError('unknown relation in ontology %s: %s'
                             % (definition.id, request.relation))
        if not isinstance(relation, RelationDefinition):
            raise ValueError('relation %r has no endpoint concepts' % request.relation)
        if relation.subject_concept == concept_name:
            forward = True
            target_concept = relation.object_concept
        elif relation.object_concept == concept_name:
            forward = False
            target_concept = relation.subject_concept
        else:
            raise ValueError('relation %r does not touch concept %r'
                             % (request.relation, concept_name))
        if not target_concept:
            raise ValueError('relation %r has no endpoint concepts' % request.relation)
        try:
            target_name, target = definition.resolve_concept(target_concept)
        except (KeyError, ValueError):
            raise ValueError('relation %r names an unknown concept: %s'
                             % (request.relation, target_concept)) from None
        fields = list(dict.fromkeys(request.fields)) or list(target.identity_fields)
        for field in extra_fields:
            if field not in fields:
                fields.append(field)
        for field in fields:
            if field not in target.properties:
                raise ValueError(
                    'property %r is not defined on related concept %r'
                    % (field, target.entity_type))
        roles = relation.roles
        return {
            'relation': request.relation,
            'fields': fields,
            'target_concept': target_name,
            'target_definition': target,
            'subject_role': roles[0],
            'object_role': roles[-1],
            'forward': forward,
        }

    def _related_targets(self, releases, definition: OntologyRevision, spec: dict):
        """Index every published target object by its identity key.

        A relation fact may point at an object published by a different task
        of the same ontology revision, so the index spans releases.  Identity
        values used only for matching stay internal; output uses the disclosed
        values of the release that carried the target.
        """
        concept_by_entity = {
            item.entity_type: name for name, item in definition.concepts.items()
        }
        target = spec['target_definition']
        raw, disclosed, hidden, index = {}, {}, {}, {}
        for release, snapshot in releases:
            release_hidden = self._hidden_properties(snapshot['body'])
            for instance in snapshot['instances']:
                name = concept_by_entity.get(instance.get('entity_type'))
                if name is None and len(definition.concepts) == 1:
                    name = next(iter(definition.concepts))
                if name != spec['target_concept']:
                    continue
                instance_id = instance.get('id')
                values = instance.get('values') or {}
                raw[instance_id] = values
                disclosed[instance_id] = {
                    key: value for key, value in values.items()
                    if key not in release_hidden
                }
                hidden[instance_id] = release_hidden
                for key in _identity_keys(values, target):
                    index.setdefault(key, []).append(instance_id)
        return {'raw': raw, 'disclosed': disclosed, 'hidden': hidden,
                'index': index}

    def _related_for(self, *, instance: dict, concept: ConceptDefinition, spec: dict,
                     facts: dict, release_ref: str, targets: dict):
        """Return (related|null, status, requested fields hidden by policy).

        ``facts`` maps a release ref to the facts that release carried.  The
        instance's own release is authoritative: facts from the other releases
        of the same ontology revision are only a fallback.  Every matching fact
        in the chosen group contributes target ids; two or more distinct
        targets are declared ambiguous instead of picking one arbitrarily.
        """
        values = instance.get('values') or {}
        instance_id = instance.get('id')
        current_keys = _identity_keys(values, concept)
        current_keys.add(str(instance_id))
        source_role = spec['subject_role'] if spec['forward'] else spec['object_role']
        target_role = spec['object_role'] if spec['forward'] else spec['subject_role']
        own = facts.get(release_ref) or []
        others = [fact for ref, group in facts.items() if ref != release_ref
                  for fact in group]
        for group in (own, others):
            target_ids = set()
            for fact in group:
                bindings = {binding.get('role'): binding
                            for binding in fact.get('role_bindings') or []}
                source_binding = bindings.get(source_role)
                target_binding = bindings.get(target_role)
                if source_binding is None or target_binding is None:
                    continue
                if not _binding_hits(source_binding, instance_id, current_keys):
                    continue
                target_ids.update(_target_ids(target_binding, targets))
            if not target_ids:
                continue
            candidates = sorted(target_ids)
            if len(candidates) > 1:
                listed = candidates[:_MAX_RELATED_CANDIDATES]
                return ({'relation': spec['relation'],
                         'target_instance_id': None,
                         'fields': {},
                         'ambiguous': True,
                         'candidates': listed,
                         'candidates_truncated': len(listed) < len(candidates)},
                        'ambiguous', [])
            target_id = candidates[0]
            disclosed = targets['disclosed'].get(target_id) or {}
            hidden = targets['hidden'].get(target_id) or set()
            fields, hidden_fields = {}, []
            for name in spec['fields']:
                if name in disclosed:
                    fields[name] = disclosed[name]
                elif name in hidden:
                    hidden_fields.append(name)
                else:
                    fields[name] = None
            return ({'relation': spec['relation'],
                     'target_instance_id': target_id,
                     'fields': fields,
                     'ambiguous': False},
                    'matched', hidden_fields)
        return None, 'missing', []

    def _hidden_relations(self, preview_body: dict) -> set[str]:
        """Relations whose role source fields lie outside the disclosure scope.

        A relation fact is materialized from the fields its role conversions
        read.  Joining two objects through a field outside
        ``allowed_model_fields`` and then returning the far object's fields
        would disclose that hidden link, so such facts are not usable by
        ``include_related`` at all.  ``choose`` reads its condition and both
        branches, not the nominal ``source_field``.
        """
        allowed = self.wb.allowed_model_fields
        if allowed is None:
            return set()
        hidden = set()
        for source_id, mapping in self._mapping_pairs(preview_body):
            allow = set(allowed.get(source_id, []))
            for relation, roles in (mapping.get('relation_bindings') or {}).items():
                for binding in (roles or {}).values():
                    if any(field != '$entity' and field not in allow
                           for field in self._binding_source_fields(binding)):
                        hidden.add(relation)
        return hidden

    def _all(self, kind: str):
        rows = []
        cursor = 0
        while True:
            batch = self.store.query(kind, self.scope, cursor=cursor, limit=_READ_LIMIT)
            rows.extend(batch)
            if len(batch) < _READ_LIMIT:
                return rows
            cursor += len(batch)

    def _releases(self, ontology_id: str, revision: str):
        expected = '%s@%s' % (ontology_id, revision)
        for row in self._all('release'):
            ref = '%s@%s' % (row['id'], row['revision'])
            snapshot = self._snapshot(row['body'])
            if snapshot is None:
                continue
            if snapshot['body'].get('ontology_revision') != expected:
                continue
            yield {'ref': ref, 'digest': row['body'].get('digest', '')}, snapshot

    def _snapshot(self, release: dict):
        """Load the frozen preview revision and prove the returned objects.

        The release points at the pre-save revision.  For a partial save the
        release marker (``release_ref``) lives on the next revision of the
        same preview and carries the saved object ids; the saved subset must
        reproduce the release digest.  If neither the full snapshot nor a
        recoverable saved subset reproduces the digest, the release is not
        trusted and is skipped instead of leaking suspended objects.
        """
        preview_ref = release.get('preview_ref')
        if not isinstance(preview_ref, str) or '@' not in preview_ref:
            return None
        preview_id, preview_revision = preview_ref.rsplit('@', 1)
        row = self.store.get('preview', preview_id, preview_revision, scope=self.scope)
        if row is None:
            return None
        body = row['body']
        instances = list(body.get('instances') or [])
        # The release writes its marker on the immediate next revision of the
        # same preview.  Read that exact revision, never ``current``: a later
        # correction/re-publish may append more revisions and move the marker
        # away, but this release's saved manifest stays frozen here.
        marker_revision = None
        try:
            marker_revision = str(int(preview_revision) + 1)
        except (TypeError, ValueError):
            pass
        marker = (self.store.get('preview', preview_id, marker_revision,
                                 scope=self.scope)
                  if marker_revision is not None else None)
        marker_body = marker['body'] if marker is not None else {}
        release_ref = '%s@%s' % (release.get('id'), release.get('revision'))
        partial = False
        published_at = _release_time(release, body, marker_body, release_ref)
        if marker_body.get('release_ref') == release_ref:
            audits = marker_body.get('partial_save') or []
            if audits:
                saved = audits[-1].get('saved') or []
                saved_ids = {item.get('entity_id') for item in saved
                             if item.get('entity_id')}
                candidates = [item for item in instances
                              if item.get('id') in saved_ids]
                if self._digest_matches(body, candidates, partial=True,
                                        release=release):
                    instances = candidates
                    partial = True
                elif not self._digest_matches(body, instances, partial=False,
                                              release=release):
                    return None
            elif not self._digest_matches(body, instances, partial=False,
                                          release=release):
                return None
        elif not self._digest_matches(body, instances, partial=False, release=release):
            # The marker revision is gone; only the unmodified full snapshot
            # is safe to return.
            return None
        return {
            'body': body,
            'instances': instances,
            'partial': partial,
            'published_at': published_at,
        }

    @staticmethod
    def _digest_matches(body: dict, instances: list, *, partial: bool,
                        release: dict) -> bool:
        content = {
            key: body.get(key)
            for key in ('ontology_revision', 'mapping', 'source_revisions')
        }
        content['instances'] = instances
        content['issues'] = [] if partial else (body.get('issues') or [])
        if body.get('extensions'):
            content['extensions'] = body['extensions']
        return digest(content) == release.get('digest')

    def _session_history(self, row):
        """Every stored revision of one session, oldest first.

        A task can publish again after its first release.  ``current`` then
        names only the newest release; the earlier release is still tied to
        the task by the historical session revision that selected it.
        """
        try:
            last = int(row['revision'])
        except (TypeError, ValueError):
            return [(row['revision'], row['body'])]
        revisions = []
        for number in range(1, last + 1):
            historical = self.store.get('session', row['id'], str(number),
                                        scope=self.scope)
            if historical is not None:
                revisions.append((historical['revision'], historical['body']))
        return revisions or [(row['revision'], row['body'])]

    def _session_index(self):
        index = {}
        for row in self._all('session'):
            tasks = {}
            for revision, body in self._session_history(row):
                release_ref = (body.get('selected_versions') or {}).get('release')
                if not release_ref:
                    continue
                goal_ref = str(body.get('goal_ref') or '')
                if goal_ref not in tasks:
                    task = ''
                    if '@' in goal_ref:
                        goal_id, goal_revision = goal_ref.rsplit('@', 1)
                        goal = self.store.get('goal', goal_id, goal_revision,
                                              scope=self.scope)
                        if goal is not None:
                            task = (goal['body'] or {}).get('goal') or ''
                    tasks[goal_ref] = task
                index.setdefault(release_ref, []).append({
                    'session_id': row['id'], 'task': tasks[goal_ref],
                    'phase': body.get('phase'),
                    'session_revision': revision,
                })
        return index

    @staticmethod
    def _mapping_pairs(preview_body: dict):
        """Every (source id, mapping) pair carried by one preview body.

        Multi-source saves keep one mapping per source in the preview
        extension; a single-source body stores its mapping directly.  When the
        source cannot be identified the id is ``None``, which makes the
        disclosure lookup treat the fields as not allowed.
        """
        extensions = preview_body.get('extensions') or {}
        mappings = extensions.get('intake.source_mappings') or {}
        if mappings:
            return list(mappings.items())
        if preview_body.get('mapping'):
            sources = list((preview_body.get('source_revisions') or {}).keys())
            return [(sources[0] if len(sources) == 1 else None,
                     preview_body['mapping'])]
        return []

    @staticmethod
    def _binding_source_fields(binding: dict) -> list[str]:
        """Record fields a mapping conversion depends on for disclosure.

        ``combine`` additionally reads ``options.fields`` and ``choose`` reads
        its condition and both branches (``source_field`` itself is not used
        by ``choose``).  The declared ``source_field`` stays in the set so a
        hidden declared field never becomes usable merely because a conversion
        leaves it unread.
        """
        transform = binding.get('transform', 'identity')
        options = binding.get('options') or {}
        fields = [binding.get('source_field')]
        if transform == 'combine':
            fields += list(options.get('fields') or [])
        elif transform == 'choose':
            fields += [options.get('when_field'), options.get('then_field'),
                       options.get('else_field')]
        return [field for field in fields if field]

    def _hidden_properties(self, preview_body: dict) -> set[str]:
        """Properties whose source fields are outside the model disclosure scope."""
        allowed = self.wb.allowed_model_fields
        if allowed is None:
            return set()
        hidden = set()
        for source_id, mapping in self._mapping_pairs(preview_body):
            allow = set(allowed.get(source_id, []))
            for name, binding in (mapping.get('bindings') or {}).items():
                if any(field not in allow
                       for field in self._binding_source_fields(binding)):
                    hidden.add(name)
        return hidden

    @staticmethod
    def _disclosed(instance: dict, hidden: set[str]):
        values = {name: value for name, value in
                  (instance.get('values') or {}).items() if name not in hidden}
        anchors = {
            name: list(items) for name, items in
            (instance.get('source_anchors') or {}).items() if name not in hidden
        }
        return values, anchors

    @staticmethod
    def _locations(anchors: dict):
        locations = []
        for name, items in anchors.items():
            for anchor in items:
                selector = anchor.get('selector') or {}
                location = {
                    'property': name,
                    'source_ref': anchor.get('source_ref'),
                    'source_revision': anchor.get('source_revision'),
                    'selector': selector,
                    'extraction_ref': anchor.get('extraction_ref'),
                }
                for key in ('page', 'paragraph', 'line'):
                    if selector.get(key) is not None:
                        location[key] = selector[key]
                if selector.get('kind') == 'record_key':
                    row = (selector.get('keys') or {}).get('row')
                    if row is not None:
                        location['row'] = row
                if selector.get('kind') == 'excel_cell':
                    location['sheet'] = selector.get('sheet')
                    location['range'] = selector.get('range')
                if selector.get('kind') == 'text_span':
                    location['unit_ref'] = selector.get('unit_ref')
                    location['char_start'] = selector.get('char_start')
                    location['char_end'] = selector.get('char_end')
                locations.append(location)
        return locations

    def _audit_times(self):
        """Map release refs to timestamps recorded by publication audits."""
        times = {}
        for row in self._all('review'):
            body = row['body']
            recorded_at = body.get('recorded_at')
            if not recorded_at:
                continue
            refs = []
            audit = body.get('partial_save')
            if isinstance(audit, dict) and audit.get('release_ref'):
                refs.append(audit['release_ref'])
            decision = body.get('decision')
            sources = [body]
            if isinstance(decision, dict):
                sources.append(decision)
            for source in sources:
                for key in ('release_ref', 'result_ref'):
                    if source.get(key):
                        refs.append(source[key])
            for ref in refs:
                times.setdefault(ref, recorded_at)
        return times

    def _older_revision_hint(self, ontology_id: str, revision: str,
                             concept: str) -> dict | None:
        """Point at the newest older revision that still has this concept's rows.

        A new ontology revision starts with no published instances until a task
        maps into it.  Reporting zero alone reads as "there is no data", so the
        count of the newest older revision travels with the empty page.
        """
        entry = self._stats().get(ontology_id) or {}
        current_key = _revision_key(revision)
        current = (entry.get('revisions') or {}).get(revision) or {}
        if (current.get('concepts') or {}).get(concept, 0):
            # The revision does have rows; an empty filtered page is a filter
            # result, not an unconnected revision.
            return None
        older = []
        for rev, data in (entry.get('revisions') or {}).items():
            if rev == revision or _revision_key(rev) >= current_key:
                continue
            count = (data.get('concepts') or {}).get(concept, 0)
            if count:
                older.append((rev, count))
        if not older:
            return None
        older_revision, count = max(older, key=lambda item: _revision_key(item[0]))
        return {
            'reason': '新修订尚未接入',
            'revision': revision,
            'concept': concept,
            'older_revision': older_revision,
            'count': count,
        }

    def _older_revision_total_hint(self, ontology_id: str, revision: str,
                                   entry_stats: dict) -> dict | None:
        """The ontology-level form of :meth:`_older_revision_hint`."""
        current_key = _revision_key(revision)
        older = []
        for rev, data in (entry_stats.get('revisions') or {}).items():
            if rev == revision or _revision_key(rev) >= current_key:
                continue
            if data.get('count'):
                older.append((rev, data['count']))
        if not older:
            return None
        older_revision, count = max(older, key=lambda item: _revision_key(item[0]))
        return {
            'reason': '新修订尚未接入',
            'revision': revision,
            'older_revision': older_revision,
            'count': count,
        }

    def _stats(self):
        """Aggregate published instances by ontology, revision and concept."""
        definitions = {}
        stats = {}
        audit_times = self._audit_times()
        for row in self._all('release'):
            ref = '%s@%s' % (row['id'], row['revision'])
            snapshot = self._snapshot(row['body'])
            if snapshot is None:
                continue
            body = snapshot['body']
            ontology_revision = body.get('ontology_revision') or ''
            if '@' not in ontology_revision:
                continue
            ontology_id, revision = ontology_revision.rsplit('@', 1)
            cache_key = (ontology_id, revision)
            if cache_key not in definitions:
                definition_row = self.store.get('ontology', ontology_id, revision,
                                                scope=self.scope)
                definitions[cache_key] = (
                    OntologyRevision.model_validate(definition_row['body'])
                    if definition_row is not None else None)
            definition = definitions[cache_key]
            by_entity = (
                {item.entity_type: name for name, item in definition.concepts.items()}
                if definition is not None else {})
            entry = stats.setdefault(ontology_id, {
                'count': 0, 'concepts': {}, 'concept_times': {},
                'revisions': {}, 'last_published_at': None,
                'latest_release_ref': None,
            })
            revision_entry = entry['revisions'].setdefault(revision, {
                'count': 0, 'concepts': {}, 'last_published_at': None,
            })
            published_at = snapshot.get('published_at') or audit_times.get(ref)
            for instance in snapshot['instances']:
                concept = by_entity.get(instance.get('entity_type'),
                                        instance.get('entity_type') or '')
                if not concept:
                    continue
                entry['count'] += 1
                entry['concepts'][concept] = entry['concepts'].get(concept, 0) + 1
                revision_entry['count'] += 1
                revision_entry['concepts'][concept] = (
                    revision_entry['concepts'].get(concept, 0) + 1)
                if published_at:
                    entry['concept_times'][concept] = max(
                        entry['concept_times'].get(concept) or '', published_at)
                    entry['last_published_at'] = max(
                        entry['last_published_at'] or '', published_at)
                    revision_entry['last_published_at'] = max(
                        revision_entry['last_published_at'] or '', published_at)
            if entry['latest_release_ref'] is None or (
                    published_at or '') >= (entry['last_published_at'] or ''):
                entry['latest_release_ref'] = ref
        return stats


def _release_time(release: dict, frozen_body: dict, marker_body: dict,
                  release_ref: str):
    """Best available publish time.

    D1 release records carry no timestamp.  Partial saves write one in their
    audit; the release and preview extension slots are honoured for hosts that
    add one.  When none exists the summary reports ``null`` rather than
    inventing a time.
    """
    for source in (release.get('extensions'), frozen_body.get('extensions'),
                   marker_body.get('extensions')):
        if isinstance(source, dict) and source.get('dataagent.published_at'):
            return source['dataagent.published_at']
    for key in ('published_at', 'created_at'):
        if release.get(key):
            return release[key]
    for key in ('published_at', 'created_at'):
        if marker_body.get(key):
            return marker_body[key]
    if marker_body.get('release_ref') == release_ref:
        audits = marker_body.get('partial_save') or []
        if audits and audits[-1].get('recorded_at'):
            return audits[-1]['recorded_at']
    return None
