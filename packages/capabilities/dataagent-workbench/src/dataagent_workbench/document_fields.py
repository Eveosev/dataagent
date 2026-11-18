"""Derive document fields from exact text spans in an observed source.

A PDF may contain one or more business documents and a document's facts may sit
on different pages: a field may be associated with a row observed on another
page only when the span owner and the target row share document identity.  The
anchor keeps the page it was read from.  The source structure fingerprint stays
the fingerprint of the source itself, so a mapping saved after text extraction
is still reusable for the next intake of the same structure.  Reuse is only
claimed when every recorded span still resolves; a changed scan falls back to
a fresh extraction instead of presenting a reused mapping with missing values.
"""

import re

from pydantic import BaseModel, ConfigDict, Field

from dataagent_contracts.core.refs import SourceAnchor


class DocumentField(BaseModel):
    model_config = ConfigDict(extra='forbid')

    row: int = Field(ge=0)
    name: str = Field(min_length=1, max_length=64)
    page: int = Field(ge=1)
    quote: str = Field(min_length=1, max_length=2000)
    char_start: int | None = Field(default=None, ge=0)


def _span(field, pages):
    """Resolve the exact observed span, independent of the row's own page."""
    if field.page not in pages:
        raise ValueError('selected page was not observed in this document')
    text = pages[field.page]
    start = field.char_start
    if start is None:
        start = text.find(field.quote)
        if start < 0 or text.find(field.quote, start + 1) >= 0:
            raise ValueError('quote must occur exactly once or specify char_start')
    end = start + len(field.quote)
    if text[start:end] != field.quote:
        raise ValueError('quote does not match observed text')
    return start, end


def _same_span(anchor, page, start, end):
    selector = anchor.selector
    return (getattr(selector, 'page', None) == page
            and getattr(selector, 'char_start', None) == start
            and getattr(selector, 'char_end', None) == end)


_IDENTITY_HINTS = {
    'number', 'id', 'code', 'document_number', 'document_no', 'invoice_number',
    'invoice_no', 'bill_number', 'bill_no',
}
_IDENTITY_DOMAIN_WORDS = {'invoice', 'document', 'doc', 'bill'}
_IDENTITY_SUFFIX_WORDS = {'number', 'no', 'num'}


def _available_fields(profile):
    available = list(profile.fields)
    for record in profile.records:
        for name in record:
            if name not in available:
                available.append(name)
    return available


def _identity_kind(name):
    """Group raw field names that denote the same document identity.

    ``number``, ``invoice_no``, ``invoice_number`` and ``document_no`` all
    map to the same ``docno`` kind, so a mapping of ``invoice_no`` to the
    ontology's ``number`` is compared against a row that still uses
    ``number``.  Unrelated names (``currency_code``, ``seller_id``) keep their
    own kind.
    """
    name = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', '_', name)
    tokens = [token for token in re.split(r'[^a-z0-9]+', name.lower()) if token]
    if not tokens:
        return name.lower()
    rest = [token for token in tokens if token not in _IDENTITY_DOMAIN_WORDS]
    if rest and all(token in _IDENTITY_SUFFIX_WORDS for token in rest):
        return 'docno'
    if rest in (['id'], ['identifier']):
        return 'id'
    if rest == ['code']:
        return 'code'
    return ''.join(tokens)


def _identity_names(profile, identity_fields):
    """Raw fields that may carry a configured identity, including aliases."""
    available = _available_fields(profile)
    if identity_fields is not None:
        kinds = {_identity_kind(name) for name in identity_fields}
        return [name for name in available
                if name in identity_fields or _identity_kind(name) in kinds]
    names = []
    for name in available:
        low = name.lower()
        if (low in _IDENTITY_HINTS or low.endswith(('_number', '_no', '_id'))
                or _identity_kind(name) in {'docno', 'id'}):
            names.append(name)
    return names


def _identity_slots(profile, identity_fields, identity_aliases=None):
    """One slot per ontology identity property, with all raw aliases."""
    available = _available_fields(profile)
    aliases = identity_aliases or {}
    if identity_fields is None:
        groups = {}
        for name in _identity_names(profile, None):
            groups.setdefault(_identity_kind(name), []).append(name)
        return list(groups.values())
    slots = []
    for prop in identity_fields:
        names = []
        if prop in available:
            names.append(prop)
        raw_aliases = aliases.get(prop) or []
        if isinstance(raw_aliases, str):
            raw_aliases = [raw_aliases]
        for raw in raw_aliases:
            if raw in available and raw not in names:
                names.append(raw)
        kind = _identity_kind(prop)
        for raw in available:
            if raw not in names and _identity_kind(raw) == kind:
                names.append(raw)
        if not names:
            names = [prop]
        slots.append(names)
    return slots


def _row_identity(profile, row, identity_fields, identity_aliases=None):
    record = profile.records[row]
    identity = []
    for names in _identity_slots(profile, identity_fields, identity_aliases):
        values = sorted({str(record[name]) for name in names
                         if name in record and record[name] not in (None, '')})
        identity.append(tuple(values))
    return tuple(identity)


def _identity_values(identity):
    return [value for slot in identity for value in slot]


def _document_keys(profile, identity_fields, identity_aliases=None):
    keys = set()
    for row in range(len(profile.records)):
        identity = _row_identity(profile, row, identity_fields, identity_aliases)
        if any(identity):
            keys.add(identity)
    return keys


def _move_conflict(profile, target_row, source_row, identity_fields, identity_aliases=None):
    """Refuse a move whose rows point at different business documents."""
    target = profile.records[target_row]
    source = profile.records[source_row]
    target_identity = _row_identity(profile, target_row, identity_fields, identity_aliases)
    source_identity = _row_identity(profile, source_row, identity_fields, identity_aliases)
    if any(target_identity) and any(source_identity):
        if target_identity != source_identity:
            return 'document identity differs'
    elif any(source_identity) and not any(target_identity):
        return 'source row is identified but target row is not'
    # A shared field with a different value is also evidence that the rows
    # describe different documents, even when neither carries a known key.
    for name, value in source.items():
        if name in target and str(target[name]) != str(value):
            return f'{name} differs'
    return None


def _anchor_rows(profile, predicate):
    """Rows owning at least one anchor that matches the predicate."""
    rows = set()
    for key, anchors in profile.anchors.items():
        try:
            row = int(key.split('.', 1)[0])
        except (ValueError, IndexError):
            continue
        if 0 <= row < len(profile.records) and any(predicate(anchor) for anchor in anchors or []):
            rows.add(row)
    return rows


def _page_identity_values(profile, page_text, identity_fields, identity_aliases=None):
    values = set()
    names = _identity_names(profile, identity_fields)
    for slot in _identity_slots(profile, identity_fields, identity_aliases):
        for name in slot:
            if name not in names:
                names.append(name)
    for name in names:
        pattern = re.compile(
            rf'(?i)(?<![A-Za-z0-9_]){re.escape(name)}\s*[:：]\s*([^\s,;，。；]+)')
        for match in pattern.finditer(page_text or ''):
            value = match.group(1).strip().rstrip('.,;，。；:：')
            if value:
                values.add(value)
    return values


_DATE_VALUE = re.compile(
    r'^(?:\d{4}[-/.]\d{1,2}(?:[-/.]\d{1,2})?|\d{1,2}[-/.]\d{1,2}[-/.]\d{4})$')
# "Invoice BILL-B", "Invoice No. INV-B", "InvoiceINV-B" and similar lead-ins.
_DOCUMENT_CONTEXT = re.compile(
    r'(?i)\b(?:invoice|bill|document|doc)'
    r'(?:\s*(?:no\.?|number|reference|ref|#))?\s*[:：]?\s*'
    r'([A-Za-z0-9][A-Za-z0-9_/-]*)')


def _looks_like_date(value):
    return bool(_DATE_VALUE.match(str(value)))


def _identity_context_values(page_text, target_values):
    values = set()
    for match in _DOCUMENT_CONTEXT.finditer(page_text or ''):
        value = match.group(1).strip().rstrip('.,;，。；:：')
        if not re.search(r'[0-9_-]', value):
            continue
        if _looks_like_date(value) and value not in target_values:
            continue
        values.add(value)
    return values


def _identity_shape_values(value, page_text):
    """Find unlabeled values shaped like an invoice/document number.

    ``Invoice INV-B`` has no ``number:`` label, but ``INV-B`` shares the
    ``INV-`` prefix of the target ``INV-A`` and is therefore evidence of a
    different document.  Values without a separator (bare integers) are not
    shape-matched to avoid treating amounts or dates as identities.
    """
    match = re.match(r'^([A-Za-z0-9]+[-_/])([A-Za-z0-9][A-Za-z0-9_-]*)$', str(value))
    if not match:
        return set()
    prefix = match.group(1)
    pattern = re.compile(
        rf'(?<![A-Za-z0-9_-]){re.escape(prefix)}[A-Za-z0-9][A-Za-z0-9_-]*'
        rf'(?![A-Za-z0-9_-])')
    return {item.group(0) for item in pattern.finditer(page_text or '')}


def _require_page_identity(profile, target_row, page_text, identity_fields,
                           identity_aliases=None):
    page_values = _page_identity_values(profile, page_text, identity_fields,
                                        identity_aliases)
    target_values = set(_identity_values(
        _row_identity(profile, target_row, identity_fields, identity_aliases)))
    if not target_values:
        return
    evidence = set(page_values)
    for value in target_values:
        for found in _identity_shape_values(value, page_text):
            # A date on a continuation page is not another document number.
            if _looks_like_date(found) and found not in target_values:
                continue
            evidence.add(found)
    evidence.update(_identity_context_values(page_text, target_values))
    if evidence - target_values:
        raise ValueError('fields of different documents cannot be associated: '
                         'selected page identifies another document')


def _require_same_document(profile, target_row, source_row, identity_fields,
                           identity_aliases=None):
    conflict = _move_conflict(profile, target_row, source_row, identity_fields,
                              identity_aliases)
    if conflict:
        raise ValueError('fields of different documents cannot be associated: ' + conflict)
    if (not any(_row_identity(profile, source_row, identity_fields, identity_aliases))
            and len(_document_keys(profile, identity_fields, identity_aliases)) > 1):
        raise ValueError('fields of different documents cannot be associated: '
                         'source row has no document identity')


def _check_span_owner(profile, target_row, page, start, end, identity_fields,
                      page_text=None, identity_aliases=None):
    """Validate the document owning the selected span before adding a field.

    The source field name is deliberately irrelevant here: an optional field
    can be spelled differently (``Issuer`` vs ``issuer``) and a source row may
    carry its number as ``invoice_no`` rather than ``number``.  Anchors locate
    the row; canonical identity aliases compare the documents.
    """
    owners = _anchor_rows(profile, lambda anchor: _same_span(anchor, page, start, end))
    if owners:
        unverified = False
        for row in owners:
            if row != target_row:
                _require_same_document(profile, target_row, row, identity_fields,
                                       identity_aliases)
                if not any(_row_identity(profile, row, identity_fields, identity_aliases)):
                    unverified = True
        if unverified:
            _require_page_identity(profile, target_row, page_text, identity_fields,
                                   identity_aliases)
        return
    # No exact anchor: a page carrying rows from different documents is
    # ambiguous, so only accept it when every row on the page belongs to the
    # target document.
    page_rows = _anchor_rows(
        profile, lambda anchor: getattr(anchor.selector, 'page', None) == page)
    others = page_rows - {target_row}
    if others:
        for row in others:
            _require_same_document(profile, target_row, row, identity_fields,
                                   identity_aliases)
        _require_page_identity(profile, target_row, page_text, identity_fields,
                               identity_aliases)
        return
    _require_page_identity(profile, target_row, page_text, identity_fields,
                           identity_aliases)
    if len(profile.records) > 1:
        raise ValueError('fields of different documents cannot be associated: '
                         'selected span is not associated with a known document row')


def _drop_moved_rows(updated, moved):
    """Remove rows whose only fields were moved to another row, then renumber."""
    drop = {row for row in moved
            if not any(value not in (None, '') for value in updated.records[row].values())}
    if not drop:
        return {}
    keep = [index for index in range(len(updated.records)) if index not in drop]
    renumber = {old: new for new, old in enumerate(keep)}
    anchors = {}
    for key, value in updated.anchors.items():
        row, name = key.split('.', 1)
        old = int(row)
        if old in renumber:
            anchors[f'{renumber[old]}.{name}'] = value
    updated.records = [updated.records[index] for index in keep]
    updated.anchors = anchors
    return renumber


def extract_fields(profile, fields, allowed_fields, *, remember=False, identity_fields=None,
                   identity_aliases=None):
    if profile.kind != 'pdf':
        raise ValueError('exact text extraction requires a PDF observation')
    if allowed_fields is not None and (
        'text' not in allowed_fields or any(field.name not in allowed_fields for field in fields)
    ):
        raise PermissionError('document text or derived field is outside model disclosure scope')

    pages = {page['page']: page['text'] for page in profile.metadata.get('pages', [])}
    updated = profile.model_copy(deep=True)
    original_fields = set(profile.fields)
    resolved = []
    for field in fields:
        if field.row >= len(updated.records):
            raise ValueError('choose an observed row and a new field name')
        if field.name in updated.records[field.row]:
            raise ValueError('duplicate derived field')
        if any(item['row'] == field.row and item['name'] == field.name for item in resolved):
            raise ValueError('duplicate derived field')
        start, end = _span(field, pages)
        # An existing field name may be associated with another row of the same
        # document when that row holds exactly the observed span.  The field is
        # moved, so a page of the same document no longer stays an orphan row.
        moving = [row for row in range(len(profile.records)) if row != field.row
                  and profile.records[row].get(field.name) == field.quote
                  and any(_same_span(anchor, field.page, start, end)
                          for anchor in profile.anchors.get(f'{row}.{field.name}', []))]
        _check_span_owner(profile, field.row, field.page, start, end, identity_fields,
                          pages[field.page], identity_aliases)
        if field.name in original_fields and not moving:
            raise ValueError('choose an observed row and a new field name')
        resolved.append({'row': field.row, 'name': field.name, 'page': field.page,
                         'quote': field.quote, 'start': start, 'end': end,
                         'moving': moving})

    moved = set()
    for item in resolved:
        row = updated.records[item['row']]
        row[item['name']] = item['quote']
        if item['name'] not in updated.fields:
            updated.fields.append(item['name'])
        updated.anchors[f'{item["row"]}.{item["name"]}'] = [SourceAnchor(
            source_ref=profile.source_id, source_revision=profile.source_revision,
            selector={'kind': 'pdf_text_span', 'page': item['page'],
                      'char_start': item['start'], 'char_end': item['end']},
        )]
        moved.update(item['moving'])

    # Remove only fields that existed before this batch; a row may be a move
    # source for one field and the target for another in the same call.
    for source_row in moved:
        record = updated.records[source_row]
        for name in list(record):
            if name not in profile.records[source_row]:
                continue
            anchors = profile.anchors.get(f'{source_row}.{name}', [])
            if any(_same_span(anchor, item['page'], item['start'], item['end'])
                   for item in resolved for anchor in anchors):
                record.pop(name, None)
                updated.anchors.pop(f'{source_row}.{name}', None)

    renumber = _drop_moved_rows(updated, moved)

    if remember:
        recorded = []
        for spec in updated.metadata.get('derived_fields') or []:
            row = spec.get('row')
            if isinstance(row, int) and renumber and row not in renumber:
                continue
            recorded.append({**spec, 'row': renumber.get(row, row)
                             if isinstance(row, int) else row})
        for item in resolved:
            recorded.append({'row': renumber.get(item['row'], item['row']),
                             'name': item['name'], 'page': item['page'],
                             'quote': item['quote'], 'char_start': item['start']})
        updated.metadata['derived_fields'] = recorded
    return updated


class ReplayError(ValueError):
    """A recorded extraction no longer resolves against the fresh observation.

    ``failures`` names each recorded field that moved, so the intake service
    can explain why a verified mapping must not be reused.  Returning the
    unreplayed profile instead would let a changed scan be presented as a
    successful reuse whose preview silently lacks those fields.
    """

    def __init__(self, source_id, failures):
        self.source_id = source_id
        self.failures = list(failures)
        names = ', '.join(str(item.get('name')) for item in self.failures
                          if item.get('name')) or 'unknown field'
        super().__init__('recorded fields no longer resolve in the source: ' + names)


def replay_fields(profile, specs, *, identity_fields=None, identity_aliases=None):
    """Re-apply recorded extractions to a fresh probe of the same structure.

    Every recorded field must still resolve to its exact observed span.  If
    any field moved -- for example the second scan carries a new document
    number or amount -- :class:`ReplayError` is raised instead of returning
    the unreplayed profile, so the caller can fall back to ``intake_extract``.
    """
    fields = []
    failures = []
    pages = {page['page']: page['text'] for page in profile.metadata.get('pages', [])}
    for spec in specs or []:
        name = str(spec.get('name')) if isinstance(spec, dict) and spec.get('name') else '?'
        try:
            field = DocumentField(row=int(spec['row']), name=str(spec['name']),
                                  page=int(spec['page']), quote=str(spec['quote']),
                                  char_start=spec.get('char_start'))
        except (KeyError, TypeError, ValueError):
            failures.append({'name': name,
                             'page': spec.get('page') if isinstance(spec, dict) else None,
                             'reason': 'recorded extraction is malformed'})
            continue
        try:
            _span(field, pages)
        except ValueError as exc:
            failures.append({'name': field.name, 'page': field.page,
                             'reason': str(exc)})
            continue
        fields.append(field)
    if failures:
        raise ReplayError(profile.source_id, failures)
    if not fields:
        return profile
    try:
        return extract_fields(profile, fields, None, remember=True,
                              identity_fields=identity_fields,
                              identity_aliases=identity_aliases)
    except (ValueError, PermissionError) as exc:
        failures = [{'name': field.name, 'page': field.page, 'reason': str(exc)}
                    for field in fields]
        raise ReplayError(profile.source_id, failures) from exc
