"""Turn clause paragraphs into typed records anchored at exact text spans.

Institutional documents keep many rules in prose: one clause names several
standards in a single sentence and none of them sits in a table.  The agent
reads the disclosed clause candidates (D2b) and submits records for the task's
pinned target concept; this module never trusts that submission.  Every quote
must match the observed paragraph or page text verbatim at its cited position,
every property must belong to the concept and parse under its value type, and
a required attribute the clause never states stays an explicit coverage gap
instead of being invented.  Numbers, amounts and dates must equal what their
own quote parses to, and one source span must carry the same value no matter
which record or property cites it.  Accepted records become a
``clause_records:<concept>`` record set with paragraph anchors, so the normal
mapping preview and materialization treat them like any other source rows.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_core import to_jsonable_python

from dataagent_contracts.core.refs import SourceAnchor
from dataagent_ontology.mapping import _typed
from .discovery_evidence import _paragraph_text_fields

# Value types whose submitted value must equal the quote's own parse: a
# quote of 800 cannot carry a submitted value of 900.
_VERIFIED_QUOTE_TYPES = frozenset({'decimal', 'integer', 'date', 'datetime'})


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


class RecordSpan(BaseModel):
    """The character range one record is attributed to, within one unit."""

    model_config = ConfigDict(extra='forbid')

    paragraph: int | None = Field(default=None, ge=1, description='docx 段落序号')
    page: int | None = Field(default=None, ge=1, description='PDF 页码')
    char_start: int = Field(ge=0, description='区间起始字符（含）')
    char_end: int = Field(ge=1, description='区间结束字符（不含）')

    @model_validator(mode='after')
    def check_span(self):
        if self.char_end <= self.char_start:
            raise ValueError('record_span 的字符区间不能为空')
        if self.paragraph is None and self.page is None:
            raise ValueError('record_span 需要 docx 段落序号或 PDF 页码')
        if self.paragraph is not None and self.page is not None:
            raise ValueError('record_span 只能声明段落序号或页码之一')
        return self


class ClauseRecord(BaseModel):
    model_config = ConfigDict(extra='forbid')

    record_span: RecordSpan = Field(description='该记录归属的字符区间（同一段落/页内）')
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

    def locate_span(self, span):
        """Resolve one record_span to (unit key, start, end) in observed text."""
        if self.kind == 'docx':
            paragraph = span.get('paragraph')
            if paragraph is None:
                raise ValueError('docx 记录区间需要段落序号')
            unit = self.units.get(paragraph)
            if unit is None:
                raise ValueError(f'第 {paragraph} 段未在本任务观测到')
            unit_ref, text = unit
            key = ('docx', unit_ref)
            label = f'第 {paragraph} 段'
        else:
            page = span.get('page')
            if page is None:
                raise ValueError('PDF 记录区间需要页码')
            unit = self.units.get(page)
            if unit is None:
                raise ValueError(f'第 {page} 页未在本任务观测到')
            _, text = unit
            key = ('pdf', page)
            label = f'第 {page} 页'
        try:
            start, end = int(span['char_start']), int(span['char_end'])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError('record_span 需要字符起止') from exc
        if not 0 <= start < end <= len(text):
            raise ValueError(f'记录区间超出{label}原文范围')
        return key, start, end


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
    """The paragraph text field itself must be allowed, as in D2b discovery.

    口径（payne 2026-11-18 口径 A，映射路径与发现路径一致）：工作区没有
    model-context.json（``allowed_fields=None``）表示本机所有者模式，放行；
    有显式策略时必须包含段落文本字段，否则 PermissionError。
    """
    text_fields = (_paragraph_text_fields(profile) if kind == 'docx' else ['text'])
    if allowed_fields is not None and not any(field in allowed_fields for field in text_fields):
        raise PermissionError('document text or derived field is outside model disclosure scope')


def _resolve(texts, raw_records, concept):
    """Validate every submitted value; returns per-record values plus shared spans.

    A span is identified by its source position (unit plus character range)
    only: the same span cited by different records or different properties
    must carry the same value, and spans cited by more than one record are
    marked as shared evidence.  Each record also declares the record_span it
    is attributed to; quote attribution against that span is checked
    separately and reported as per-record issues instead of a rejection.
    """
    resolved = []
    shared = {}
    for raw_record in raw_records:
        record_span = raw_record.get('record_span') or {}
        record_key, record_start, record_end = texts.locate_span(record_span)
        values, evidence, paragraphs, pages = {}, {}, set(), set()
        for raw in raw_record.get('values') or []:
            prop = str(raw.get('property') or '')
            if not prop:
                raise ValueError('条款值缺少属性名')
            if prop not in concept.properties:
                raise ValueError(f'属性 {prop} 不在目标概念中')
            if prop in values:
                raise ValueError(f'同一条款记录里属性 {prop} 重复')
            kind_key, selector, start, end, label = texts.locate(raw)
            value_type = concept.properties[prop].value_type
            try:
                typed = _typed(raw.get('value'), value_type)
            except (ValueError, ArithmeticError) as exc:
                raise ValueError(f'属性 {prop} 的值无法按目标类型解析: {exc}') from exc
            if typed is None:
                raise ValueError(f'属性 {prop} 的值不能为空')
            if value_type in _VERIFIED_QUOTE_TYPES:
                # A number, amount or date must be what its own quote says.
                try:
                    quoted = _typed(raw.get('quote'), value_type)
                except (ValueError, ArithmeticError) as exc:
                    raise ValueError(
                        f'属性 {prop} 的引文无法按目标类型解析，请引用数值或日期本身') from exc
                if quoted != typed:
                    raise ValueError(f'属性 {prop} 的提交值与引文不一致：'
                                     f'引文为 {quoted}，提交为 {typed}')
            span = (*kind_key, start, end)
            entry = shared.get(span)
            if entry is None:
                shared[span] = {'selector': selector, 'value': typed,
                                'records': [len(resolved)], 'properties': [prop]}
            else:
                if entry['value'] != typed:
                    raise ValueError(f'同一引文必须携带同一个值: {prop}')
                if len(resolved) not in entry['records']:
                    entry['records'].append(len(resolved))
                if prop not in entry['properties']:
                    entry['properties'].append(prop)
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
        blank = [field for field in concept.identity_fields
                 if isinstance(values[field], str) and not values[field].strip()]
        if blank:
            raise ValueError('身份字段的值不能为空: ' + ', '.join(blank))
        resolved.append({'values': values, 'evidence': evidence,
                         'paragraphs': paragraphs, 'pages': pages,
                         'span': (record_key, record_start, record_end),
                         'record_span': record_span})
    return resolved, shared


def _within(quote, record_span):
    return (quote[0] == record_span[0]
            and record_span[1] <= quote[1] and quote[2] <= record_span[2])


def _attribution_issues(resolved, shared):
    """Per-record quote attribution against each record's declared span.

    Non-shared quotes must fall inside the record's own record_span; a shared
    quote may sit outside it, but only in the same unit, before the span and
    without a nearer same-property shared quote in between.  Overlapping
    record_spans in one unit leave both records unverified.  Violations are
    returned as per-record issues -- the batch itself is not rejected, so the
    other records still reach the preview and can be saved.
    """
    flagged = {}

    def flag(index, prop, reason):
        item = flagged.setdefault(index, {'target': prop, 'reasons': []})
        detail = f'{prop}：{reason}' if prop else reason
        if detail not in item['reasons']:
            item['reasons'].append(detail)

    for index, record in enumerate(resolved):
        record_span = record['span']
        for other in range(index):
            other_span = resolved[other]['span']
            if (other_span[0] == record_span[0]
                    and other_span[1] < record_span[2] and record_span[1] < other_span[2]):
                flag(index, None, '记录区间与其他记录的区间重叠')
                flag(other, None, '记录区间与其他记录的区间重叠')
        for prop, item in record['evidence'].items():
            selector = item['selector']
            unit = (('docx', selector['unit_ref']) if 'unit_ref' in selector
                    else ('pdf', selector['page']))
            cited = (*unit, selector['char_start'], selector['char_end'])
            entry = shared.get(cited)
            if entry is not None and len(entry['records']) > 1:
                if _within((unit, selector['char_start'], selector['char_end']), record_span):
                    continue
                if unit != record_span[0] or selector['char_end'] > record_span[1]:
                    flag(index, prop, '共享引文须与记录区间同段且在其之前')
                    continue
                candidates = [key for key, other in shared.items()
                              if len(other['records']) > 1 and prop in other['properties']
                              and (key[0], key[1]) == unit and key[3] <= record_span[1]]
                if candidates and max(candidates, key=lambda key: key[2]) != cited:
                    flag(index, prop, '共享引文不是就近的同类值')
            elif not _within((unit, selector['char_start'], selector['char_end']),
                             record_span):
                flag(index, prop, '引文落在记录区间之外')
    return [{'record': index, 'target': item['target'],
             'reason': '；'.join(item['reasons'])}
            for index, item in sorted(flagged.items())]


def _build(profile, raw_records, concept, *, concept_name, ontology_revision,
           allowed_fields):
    texts = _TextUnits(profile)
    if not texts.units:
        raise ValueError('该来源观测不包含段落或页面文本')
    _require_disclosure(profile, allowed_fields, texts.kind)
    resolved, shared = _resolve(texts, raw_records, concept)
    attribution = _attribution_issues(resolved, shared)
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
    shared_spans = [{'properties': list(entry['properties']), 'selector': entry['selector'],
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
        'attribution_issues': attribution,
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
                           'records': [{'record_span': record['record_span'],
                                        'values': [record['evidence'][prop]
                                                   for prop in record['values']]}
                                       for record in resolved]},
    })
    return updated, {'record_set': set_name, 'count': entry['count'], 'fields': fields,
                     'gaps': gaps, 'shared_spans': shared_spans,
                     'attribution_issues': attribution}


def extract_clause_records(profile, records, concept, *, concept_name,
                           ontology_revision, allowed_fields):
    """Validate agent-submitted clause records and install them as a record set.

    Returns ``(updated profile, summary)`` where the profile exposes the new
    ``clause_records:<concept>`` record set as its selected view, with one
    anchor per value pointing at the exact paragraph or page span.
    """
    raw = [{'record_span': record.record_span.model_dump(),
            'values': [value.model_dump() for value in record.values]}
           for record in records]
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
        record_span = spec.get('record_span') if isinstance(spec, dict) else None
        if not isinstance(record_span, dict):
            failures.append({'name': '?', 'reason': '记录的条款提取格式损坏'})
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
        raw_records.append({'record_span': record_span or {}, 'values': values})
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
