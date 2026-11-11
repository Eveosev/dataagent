"""Derive document fields from exact text spans in an observed source."""

from pydantic import BaseModel, ConfigDict, Field

from dataagent_contracts.core.refs import SourceAnchor
from dataagent_ontology.identity import digest


class DocumentField(BaseModel):
    model_config = ConfigDict(extra='forbid')

    row: int = Field(ge=0)
    name: str = Field(min_length=1, max_length=64)
    page: int = Field(ge=1)
    quote: str = Field(min_length=1, max_length=2000)
    char_start: int | None = Field(default=None, ge=0)


def extract_fields(profile, fields, allowed_fields):
    if profile.kind != 'pdf':
        raise ValueError('exact text extraction requires a PDF observation')
    if allowed_fields is not None and (
        'text' not in allowed_fields or any(field.name not in allowed_fields for field in fields)
    ):
        raise PermissionError('document text or derived field is outside model disclosure scope')

    pages = {page['page']: page['text'] for page in profile.metadata.get('pages', [])}
    updated = profile.model_copy(deep=True)
    original_fields = set(profile.fields)
    for field in fields:
        if field.row >= len(updated.records) or field.name in original_fields:
            raise ValueError('choose an observed row and a new field name')
        row = updated.records[field.row]
        if field.name in row:
            raise ValueError('duplicate derived field')
        same_page = any(
            getattr(anchor.selector, 'page', None) == field.page
            for key, anchors in profile.anchors.items()
            if key.startswith(f'{field.row}.')
            for anchor in anchors
        )
        if not same_page or field.page not in pages:
            raise ValueError('selected page does not belong to the observed row')

        text = pages[field.page]
        start = field.char_start
        if start is None:
            start = text.find(field.quote)
            if start < 0 or text.find(field.quote, start + 1) >= 0:
                raise ValueError('quote must occur exactly once or specify char_start')
        end = start + len(field.quote)
        if text[start:end] != field.quote:
            raise ValueError('quote does not match observed text')

        row[field.name] = text[start:end]
        if field.name not in updated.fields:
            updated.fields.append(field.name)
        updated.anchors[f'{field.row}.{field.name}'] = [SourceAnchor(
            source_ref=profile.source_id, source_revision=profile.source_revision,
            selector={'kind': 'pdf_text_span', 'page': field.page,
                      'char_start': start, 'char_end': end},
        )]
    updated.metadata['structure_fingerprint'] = digest([
        profile.metadata['structure_fingerprint'], 'document-fields', sorted(updated.fields),
    ])
    return updated
