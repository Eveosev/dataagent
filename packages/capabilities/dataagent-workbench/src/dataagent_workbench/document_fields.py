"""Derive document fields from exact text spans in an observed source.

A PDF is one business document even when its facts sit on different pages: a
field may be associated with a row observed on another page, and the anchor
keeps the page it was read from.  The source structure fingerprint stays the
fingerprint of the source itself, so a mapping saved after text extraction is
still reusable for the next intake of the same structure.
"""

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


def _identity_names(profile, identity_fields):
    if identity_fields is not None:
        return [name for name in identity_fields
                if any(name in record for record in profile.records)]
    names = []
    for name in profile.fields:
        low = name.lower()
        if low in _IDENTITY_HINTS or low.endswith(('_number', '_no', '_id')):
            names.append(name)
    return names


def _move_conflict(profile, target_row, source_row, identity_fields):
    """Refuse a move whose rows point at different business documents."""
    target = profile.records[target_row]
    source = profile.records[source_row]
    for name in _identity_names(profile, identity_fields):
        target_value, source_value = target.get(name), source.get(name)
        if target_value not in (None, '') and source_value not in (None, ''):
            if str(target_value) != str(source_value):
                return f'{name} differs'
        elif source_value not in (None, '') and target_value in (None, ''):
            return f'source row is identified by {name} but target row is not'
    # A shared field with a different value is also evidence that the rows
    # describe different documents, even when neither carries a known key.
    for name, value in source.items():
        if name in target and str(target[name]) != str(value):
            return f'{name} differs'
    return None


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


def extract_fields(profile, fields, allowed_fields, *, remember=False, identity_fields=None):
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
        for row in moving:
            conflict = _move_conflict(profile, field.row, row, identity_fields)
            if conflict:
                raise ValueError('fields of different documents cannot be associated: ' + conflict)
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


def replay_fields(profile, specs, *, identity_fields=None):
    """Re-apply recorded extractions to a fresh probe of the same structure."""
    fields = []
    for spec in specs or []:
        try:
            fields.append(DocumentField(row=int(spec['row']), name=str(spec['name']),
                                        page=int(spec['page']), quote=str(spec['quote']),
                                        char_start=spec.get('char_start')))
        except (KeyError, TypeError, ValueError):
            return profile
    if not fields:
        return profile
    try:
        return extract_fields(profile, fields, None, remember=True,
                              identity_fields=identity_fields)
    except (ValueError, PermissionError):
        # A changed page or quote must not turn automatic reuse into a crash;
        # the preview will still report the missing values explicitly.
        return profile
