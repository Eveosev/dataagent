"""Turn clause paragraphs into typed records anchored at exact text spans.

Institutional documents keep many rules in prose: one clause names several
standards in a single sentence and none of them sits in a table.  The agent
reads the disclosed clause candidates (D2b) and submits records for the task's
pinned target concept; this module never trusts that submission.  Every quote
must match the observed paragraph or page text verbatim at its cited position,
every property must belong to the concept and parse under its value type, and a
required attribute the clause never states stays an explicit coverage gap
instead of being invented.  Accepted records become a
``clause_records:<concept>`` record set with paragraph anchors, so the normal
mapping preview and materialization treat them like any other source rows.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from pydantic_core import to_jsonable_python

from dataagent_contracts.core.refs import SourceAnchor
from dataagent_ontology.mapping import _typed
from .discovery_evidence import _paragraph_text_fields


class ClauseValue(BaseModel):
    """One attribute of a clause record: a value plus its verbatim evidence."""

    model_config = ConfigDict(extra='forbid')

    property: str = Field(min_length=1, max_length=64)
    value: Any = Field(description='按本体属性值类型提交的值')
    quote: str = Field(min_length=1, max_length=2000)
    paragraph: int | None = Field(default=None, ge=1, description='docx 段落序号')
    page: int | None = Field(default=None, ge=1, description='PDF 页码')
    char_start: int | None = Field(default=None, ge=0,
                                   description='引文在该段落/页文本中的起始字符；省略时要求引文唯一')


class ClauseRecord(BaseModel):
    model_config = ConfigDict(extra='forbid')

    values: list[ClauseValue] = Field(min_length=1, max_length=64)


class ClauseReplayError(ValueError):
    """A recorded clause-record extraction no longer resolves.

    ``failures`` names each recorded property whose quote moved, so the intake
    service can explain in Chinese why a verified mapping must not be reused
    and send the agent back to ``intake_extract_records``.
    """

    def __init__(self, source_id, failures):
        self.source_id = source_id
        self.failures = list(failures)
        names = ', '.join(str(item.get('name')) for item in self.failures
                          if item.get('name')) or 'unknown field'
        super().__init__('记录的条款记录不再与原文一致: ' + names)


def clause_record_set_name(concept_name):
    return f'clause_records:{concept_name}'


class _TextUnits:
    """The verbatim text a quote is verified against: paragraphs or pages."""

    def __init__(self, profile):
        if profile.kind == 'docx':
            self.kind = 'docx'
            self.units = _docx_units(profile)
        elif profile.kind == 'pdf':
            self.kind = 'pdf'
            self.units = _pdf_units(profile)
        else:
            raise ValueError('条款记录需要 docx 或 PDF 观测')

    def locate(self, value):
        """Resolve one quote to (span key, selector, start, end, label)."""
        if self.kind == 'docx':
            paragraph = value.get('paragraph')
            if paragraph is None:
                raise ValueError('docx 条款值需要段落序号')
            unit = self.units.get(paragraph)
            if unit is None:
                raise ValueError(f'第 {paragraph} 段未在本任务观测到')
            unit_ref, text = unit
            label = f'第 {paragraph} 段'
            kind_key = ('docx', unit_ref)
        else:
            page = value.get('page')
            if page is None:
                raise ValueError('PDF 条款值需要页码')
            unit = self.units.get(page)
            if unit is None:
                raise ValueError(f'第 {page} 页未在本任务观测到')
            _, text = unit
            label = f'第 {page} 页'
            kind_key = ('pdf', page)
        quote = str(value.get('quote') or '')
        start = value.get('char_start')
        if start is not None:
            start = int(start)
        else:
            start = text.find(quote)
            if start < 0 or text.find(quote, start + 1) >= 0:
                raise ValueError(f'引文在{label}中不唯一或不存在，需提供 char_start')
        end = start + len(quote)
        if start > len(text) or end > len(text):
            raise ValueError(f'定位超出{label}原文范围')
        if text[start:end] != quote:
            raise ValueError(f'引文与{label}原文不一致')
        if self.kind == 'docx':
            selector = {'kind': 'text_span', 'unit_ref': unit_ref,
                        'char_start': start, 'char_end': end}
        else:
            selector = {'kind': 'pdf_text_span', 'page': page,
                        'char_start': start, 'char_end': end}
        return kind_key, selector, start, end, label


def _docx_units(profile):
    """{paragraph number: (unit_ref, text)} for every observed paragraph."""
    units = {}
    for paragraph in profile.metadata.get('paragraphs') or []:
        if (isinstance(paragraph, dict) and isinstance(paragraph.get('paragraph'), int)
                and isinstance(paragraph.get('text'), str)):
            number = paragraph['paragraph']
            units[number] = (paragraph.get('unit_ref') or f'paragraph:{number}',
                             paragraph['text'])
    return units


def _pdf_units(profile):
    units = {}
    for page in profile.metadata.get('pages') or []:
        if isinstance(page, dict) and isinstance(page.get('page'), int):
            units[page['page']] = (page['page'], page.get('text') or '')
    return units


def _require_disclosure(profile, allowed_fields, kind):
    """The paragraph text field itself must be allowed, as in D2b discovery."""
    text_fields = (_paragraph_text_fields(profile) if kind == 'docx' else ['text'])
    if allowed_fields is not None and not any(field in allowed_fields for field in text_fields):
        raise PermissionError('document text or derived field is outside model disclosure scope')


def _resolve(texts, raw_records, concept):
    """Validate every submitted value; returns per-record values plus shared spans."""
    resolved = []
    shared = {}
    for raw_values in raw_records:
        values, evidence, paragraphs, pages = {}, {}, set(), set()
        for raw in raw_values:
            prop = str(raw.get('property') or '')
            if not prop:
                raise ValueError('条款值缺少属性名')
            if prop not in concept.properties:
                raise ValueError(f'属性 {prop} 不在目标概念中')
            if prop in values:
                raise ValueError(f'同一条款记录里属性 {prop} 重复')
            kind_key, selector, start, end, label = texts.locate(raw)
            try:
                typed = _typed(raw.get('value'), concept.properties[prop].value_type)
            except (ValueError, ArithmeticError) as exc:
                raise ValueError(f'属性 {prop} 的值无法按目标类型解析: {exc}') from exc
            if typed is None:
                raise ValueError(f'属性 {prop} 的值不能为空')
            span = (*kind_key, prop, start, end)
            if span in shared:
                if shared[span]['value'] != typed:
                    raise ValueError(f'同一引文跨记录必须携带同一个值: {prop}')
                shared[span]['records'].append(len(resolved))
            else:
                shared[span] = {'property': prop, 'selector': selector,
                                'value': typed, 'records': [len(resolved)]}
            values[prop] = typed
            evidence[prop] = {'property': prop, 'value': to_jsonable_python(typed),
                              'quote': str(raw.get('quote')), 'char_start': start,
                              'char_end': end, 'selector': selector}
            if texts.kind == 'docx':
                evidence[prop]['paragraph'] = raw.get('paragraph')
                paragraphs.add(raw.get('paragraph'))
            else:
                evidence[prop]['page'] = raw.get('page')
                pages.add(raw.get('page'))
        missing = [field for field in concept.identity_fields if field not in values]
        if missing:
            raise ValueError('记录缺少身份字段: ' + ', '.join(missing))
        resolved.append({'values': values, 'evidence': evidence,
                         'paragraphs': paragraphs, 'pages': pages})
    return resolved, shared


def _build(profile, raw_records, concept, *, concept_name, ontology_revision,
           allowed_fields):
    texts = _TextUnits(profile)
    if not texts.units:
        raise ValueError('该来源观测不包含段落或页面文本')
    _require_disclosure(profile, allowed_fields, texts.kind)
    resolved, shared = _resolve(texts, raw_records, concept)
    set_name = clause_record_set_name(concept_name)
    rows, anchors, locations, fields = [], {}, [], []
    for record in resolved:
        for prop in record['values']:
            if prop not in fields:
                fields.append(prop)
    for index, record in enumerate(resolved):
        rows.append({prop: to_jsonable_python(value)
                      for prop, value in record['values'].items()})
        for prop, item in record['evidence'].items():
            anchors[f'{index}.{prop}'] = [SourceAnchor(
                source_ref=profile.source_id, source_revision=profile.source_revision,
                selector=dict(item['selector']))]
        if texts.kind == 'docx':
            numbers = sorted(record['paragraphs'])
            locations.append({'record': index, 'kind': 'clause', 'paragraphs': numbers,
                              'label': '、'.join(f'第 {number} 段' for number in numbers)})
        else:
            pages = sorted(record['pages'])
            locations.append({'record': index, 'kind': 'clause', 'pages': pages,
                              'label': '、'.join(f'第 {page} 页' for page in pages)})
    gaps = [{'record': index, 'property': prop}
            for index, record in enumerate(resolved)
            for prop, definition in sorted(concept.properties.items())
            if definition.required and prop not in record['values']]
    shared_spans = [{'property': entry['property'], 'selector': entry['selector'],
                     'value': to_jsonable_python(entry['value']),
                     'records': list(entry['records'])}
                    for entry in shared.values() if len(entry['records']) > 1]
    entry = {
        'name': set_name, 'kind': 'clause', 'concept': concept_name,
        'ontology_revision': ontology_revision,
        'fields': fields, 'record_indices': list(range(len(rows))),
        'count': len(rows), 'records': rows,
        'anchors': {key: [anchor.model_dump(mode='json') for anchor in values]
                    for key, values in anchors.items()},
        'record_locations': locations,
        'gaps': gaps, 'shared_spans': shared_spans,
    }
    updated = profile.model_copy(deep=True)
    updated.records = rows
    updated.fields = fields
    updated.anchors = anchors
    sets = dict(updated.metadata.get('record_sets') or {})
    sets[set_name] = entry
    summary = dict(updated.metadata.get('source_record_sets') or {})
    summary[set_name] = {'kind': 'clause', 'count': entry['count']}
    updated.metadata.update({
        'record_sets': sets, 'source_record_sets': summary,
        'record_locations': locations, 'selected_record_set': set_name,
        'field_stats': {field: {'missing_in_sample': sum(row.get(field) is None
                                                         for row in rows)}
                        for field in fields},
        'clause_records': {'concept': concept_name, 'ontology_revision': ontology_revision,
                           'record_set': set_name,
                           'records': [{'values': [record['evidence'][prop]
                                                  for prop in record['values']]}
                                       for record in resolved]},
    })
    return updated, {'record_set': set_name, 'count': entry['count'], 'fields': fields,
                     'gaps': gaps, 'shared_spans': shared_spans}


def extract_clause_records(profile, records, concept, *, concept_name,
                           ontology_revision, allowed_fields):
    """Validate agent-submitted clause records and install them as a record set.

    Returns ``(updated profile, summary)`` where the profile exposes the new
    ``clause_records:<concept>`` record set as its selected view, with one
    anchor per value pointing at the exact paragraph or page span.
    """
    raw = [[value.model_dump() for value in record.values] for record in records]
    return _build(profile, raw, concept, concept_name=concept_name,
                  ontology_revision=ontology_revision, allowed_fields=allowed_fields)


def replay_clause_records(profile, specs, concept, *, concept_name,
                          ontology_revision, allowed_fields):
    """Re-apply recorded clause records to a fresh probe of the same structure.

    Every recorded quote must still resolve at its recorded position.  If any
    quote moved, :class:`ClauseReplayError` is raised with a Chinese reason per
    failing property, so the caller can refuse mapping reuse and name the
    records that must be extracted again.
    """
    if (not isinstance(specs, dict) or specs.get('concept') != concept_name
            or specs.get('ontology_revision') != ontology_revision):
        raise ClauseReplayError(profile.source_id, [
            {'name': concept_name or '?',
             'reason': '记录时的目标概念或本体修订与当前任务不一致'}])
    texts = _TextUnits(profile)
    failures = []
    raw_records = []
    for spec in specs.get('records') or []:
        values = []
        for item in (spec.get('values') if isinstance(spec, dict) else None) or []:
            if not isinstance(item, dict) or not item.get('property') or not item.get('quote'):
                failures.append({'name': str(item.get('property') if isinstance(item, dict)
                                             else '?'),
                                 'reason': '记录的条款提取格式损坏'})
                continue
            prop = str(item['property'])
            if prop not in concept.properties:
                failures.append({'name': prop, 'reason': f'属性 {prop} 不在目标概念中'})
                continue
            try:
                texts.locate(item)
            except ValueError as exc:
                failures.append({'name': prop, 'reason': str(exc)})
                continue
            values.append({key: item.get(key)
                           for key in ('property', 'value', 'quote', 'paragraph',
                                       'page', 'char_start')})
        raw_records.append(values)
    if failures:
        raise ClauseReplayError(profile.source_id, failures)
    try:
        return _build(profile, raw_records, concept, concept_name=concept_name,
                      ontology_revision=ontology_revision, allowed_fields=allowed_fields)
    except PermissionError:
        raise ClauseReplayError(profile.source_id, [
            {'name': '?', 'reason': '段落文本不在披露范围内'}]) from None
    except ValueError as exc:
        raise ClauseReplayError(profile.source_id, [
            {'name': '?', 'reason': str(exc)}]) from exc
