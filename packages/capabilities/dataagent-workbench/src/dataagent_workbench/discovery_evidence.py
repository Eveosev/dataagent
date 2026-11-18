"""Normalize observed sources into table-shaped discovery evidence.

Every supported table source -- database tables, delimited/JSON record sets,
REST record pages and Excel table regions -- is described with the same shape
the SQLite discovery evidence already used: columns with an inferred type and
affinity, null rates, observed distinct counts, candidate keys, controlled
samples and explicit coverage.  Document sources contribute their table record
sets (G4) plus section structure and numbered clause candidates, all with
paragraph or in-page anchors.  Cross-source link candidates are produced by
``discovery_catalog`` from these tables.
"""
from collections import Counter, defaultdict
from itertools import combinations
import re
from string import ascii_lowercase, ascii_uppercase

from dataagent_ontology.identity import digest


DB_KINDS = frozenset({'sqlite', 'postgres'})
SHEET_KINDS = frozenset({'xlsx', 'xlsm'})
FLAT_KINDS = frozenset({'csv', 'tsv', 'json', 'jsonl', 'rest'})
DOCUMENT_KINDS = frozenset({'pdf', 'docx'})
TABLE_KINDS = DB_KINDS | SHEET_KINDS | FLAT_KINDS

SQLITE_CASE_FOLD = str.maketrans(ascii_uppercase, ascii_lowercase)
_CELL = re.compile(r'^([A-Z]+)([0-9]+)$')
_MAX_SAMPLES = 3
_MAX_KEY_COLUMNS = 12
_MAX_KEY_WIDTH = 5
_MAX_KEY_COMBINATIONS = 5000
_MAX_INFERRED_KEYS = 20
_SAMPLE_LIMIT = 160


def affinity(declared_type):
    """The SQLite type affinity rule, shared by declared and observed types."""
    name = (declared_type or '').upper()
    if 'INT' in name:
        return 'integer'
    if any(token in name for token in ('CHAR', 'CLOB', 'TEXT')):
        return 'text'
    if not name or 'BLOB' in name:
        return 'blob'
    if any(token in name for token in ('REAL', 'FLOA', 'DOUB')):
        return 'real'
    return 'numeric'


def scalar(value):
    # Keep storage classes separate. BLOBs and other encoded values have no match evidence.
    return (type(value).__name__, value) if isinstance(value, (str, int, float)) else None


def is_blank(value):
    """A missing value for key purposes: SQL NULL or an empty/whitespace string."""
    return value is None or (isinstance(value, str) and not value.strip())


def key_counts(rows, columns, *, skip_blank=False):
    """Count observed key tuples; rows with a binary value have no match evidence."""
    counts = Counter()
    for row, binary_fields in rows:
        if binary_fields.intersection(columns):
            continue
        if skip_blank and any(is_blank(row.get(column)) for column in columns):
            continue
        key = tuple(scalar(row.get(column)) for column in columns)
        if all(part is not None for part in key):
            counts[key] += 1
    return counts


def _observed_type(values):
    names = {type(value).__name__ for value in values}
    if not names:
        return '', 'unknown'
    if names == {'int'}:
        return 'integer', 'integer'
    if names == {'bool'}:
        return 'boolean', 'boolean'
    if names <= {'int', 'float', 'Decimal'}:
        return ('numeric', 'numeric') if 'int' in names else ('real', 'real')
    if names <= {'str'}:
        return 'text', 'text'
    if names <= {'bytes', 'bytearray', 'memoryview'}:
        return 'blob', 'blob'
    return 'mixed', 'unknown'


def _sample_value(value):
    if isinstance(value, str):
        return value[:_SAMPLE_LIMIT]
    if isinstance(value, (bool, int, float)):
        return value
    return None


def _value_key(value):
    item = scalar(value)
    return item if item is not None else ('other', type(value).__name__, repr(value)[:80])


def _column_evidence(field, declared, rows, allowed):
    non_null = [(field in binary, row.get(field)) for row, binary in rows
                if row.get(field) is not None]
    null_rows = len(rows) - len(non_null)
    blank_rows = sum(1 for row, _ in rows if is_blank(row.get(field)))
    distinct_values = len({(binary, scalar(value)) for binary, value in non_null})
    values = [value for _, value in non_null]
    if 'type' in declared:
        observed_type = declared.get('type') or ''
        type_family = affinity(observed_type)
        type_origin = 'declared'
    else:
        observed_type, type_family = _observed_type(values)
        type_origin = 'observed'
    samples = []
    if allowed is not None:
        seen = set()
        for binary, value in non_null:
            if binary:
                continue
            literal = _sample_value(value)
            if literal is None:
                continue
            key = _value_key(literal)
            if key in seen:
                continue
            seen.add(key)
            samples.append(literal)
            if len(samples) >= _MAX_SAMPLES:
                break
    return {
        **declared,
        'name': field,
        'type': observed_type,
        'type_origin': type_origin,
        'affinity': type_family,
        'nullable': declared.get('nullable', blank_rows > 0),
        'null_rows': null_rows,
        'blank_rows': blank_rows,
        'null_rate': null_rows / len(rows) if rows else 0.0,
        'distinct_values': distinct_values,
        'unique': bool(rows) and blank_rows == 0 and distinct_values == len(rows),
        'samples': samples,
    }


def _inferred_keys(columns, rows):
    """Candidate keys under the observed rule: no blank value and all rows distinct.

    Every single-column key is returned.  Independent minimal composites are
    also searched: combinations containing an already found key are skipped, so
    a unique surrogate does not hide a business key.  The search is bounded and
    reports whether a bound cut the space, so callers can disclose the gap
    instead of implying no key.
    """
    search = {'max_columns': _MAX_KEY_COLUMNS, 'max_width': _MAX_KEY_WIDTH,
              'max_combinations': _MAX_KEY_COMBINATIONS, 'truncated': False}
    if len(rows) < 2:
        return [], search
    singles = [field for field, column in columns.items()
               if column['blank_rows'] == 0 and column['distinct_values'] == len(rows)]
    keys = [[field] for field in singles]
    if len(keys) >= _MAX_INFERRED_KEYS:
        search['truncated'] = True
        return keys, search
    single_fields = set(singles)
    usable = [field for field in columns
              if columns[field]['blank_rows'] == 0 and field not in single_fields]
    if len(usable) > _MAX_KEY_COLUMNS:
        usable = usable[:_MAX_KEY_COLUMNS]
        search['truncated'] = True
    if len(usable) > _MAX_KEY_WIDTH:
        search['truncated'] = True
    examined = 0
    for width in range(2, min(_MAX_KEY_WIDTH, len(usable)) + 1):
        stopped = False
        for fields in combinations(usable, width):
            if examined >= _MAX_KEY_COMBINATIONS:
                search['truncated'] = True
                stopped = True
                break
            examined += 1
            if any(set(key) <= set(fields) for key in keys):
                continue
            if len(key_counts(rows, list(fields), skip_blank=True)) == len(rows):
                keys.append(list(fields))
                if len(keys) >= _MAX_INFERRED_KEYS:
                    search['truncated'] = True
                    return keys, search
        if stopped:
            break
    return keys, search


def _selector_value(anchor, key):
    selector = anchor.get('selector') if isinstance(anchor, dict) else anchor.selector
    if isinstance(selector, dict):
        return selector.get(key)
    return getattr(selector, key, None)


def _excel_position(profile, index, record):
    sheet = row = None
    columns = []
    for field in record:
        for anchor in profile.anchors.get(f'{index}.{field}') or []:
            if _selector_value(anchor, 'kind') != 'excel_cell':
                continue
            cell = _selector_value(anchor, 'range') or ''
            match = _CELL.match(cell)
            if not match:
                continue
            if sheet is None:
                sheet = _selector_value(anchor, 'sheet')
            if row is None:
                row = int(match.group(2))
            column = 0
            for letter in match.group(1):
                column = column * 26 + ord(letter) - ord('A') + 1
            columns.append(column)
            break
    if columns:
        return sheet, row, min(columns), max(columns)
    return sheet, row, None, None


def _excel_regions(profile):
    """Split worksheet rows into table regions by sheet, column span, header and row band.

    Side-by-side regions can share a sheet and an identical header; the column
    span from the cell anchors keeps them apart.
    """
    buckets = {}
    order = []
    for index, record in enumerate(profile.records):
        sheet, row, first, last = _excel_position(profile, index, record)
        signature = (sheet, first, last, tuple(record.keys()))
        if signature not in buckets:
            buckets[signature] = []
            order.append(signature)
        buckets[signature].append((row, index, record))
    regions = []
    for signature in order:
        entries = buckets[signature]
        named_rows = [entry for entry in entries if entry[0] is not None]
        unnamed = [entry for entry in entries if entry[0] is None]
        named_rows.sort(key=lambda entry: (entry[0], entry[1]))
        current = []
        for entry in named_rows:
            if current and entry[0] - current[-1][0] >= 3:
                regions.append((signature[0], current))
                current = []
            current.append(entry)
        if current:
            regions.append((signature[0], current))
        if unnamed:
            regions.append((signature[0], sorted(unnamed, key=lambda entry: entry[1])))
    return regions


def _table(base, source_id, kind, rows, columns, keys, *, sampled, coverage,
           key_origin, partition=None, rows_total=None, key_search=None):
    identity_keys = [key for key in keys
                     if all(columns[column]['blank_rows'] == 0 for column in key)]
    table = {
        'name': base,
        'source_id': source_id,
        'kind': kind,
        'partition': partition,
        'rows_observed': len(rows),
        'rows_total': rows_total,
        'sampled': bool(sampled),
        'coverage': coverage,
        'columns': columns,
        'keys': keys,
        'identity_keys': identity_keys,
        'key_origin': key_origin,
        '_base': base,
        '_rows': rows,
        '_skip_blank': kind not in DB_KINDS,
    }
    if key_search is not None:
        table['key_search'] = key_search
    return table


def _database_tables(profile, allowed):
    descriptors = profile.metadata.get('tables')
    if not isinstance(descriptors, list):
        return []
    record_keys = profile.metadata.get('record_keys')
    record_keys = record_keys if isinstance(record_keys, list) else []
    binary_fields = profile.metadata.get('binary_fields')
    binary_fields = binary_fields if isinstance(binary_fields, dict) else {}
    rows_by_table = defaultdict(list)
    for index, record in enumerate(profile.records):
        key = record_keys[index] if index < len(record_keys) else None
        if not isinstance(key, dict) or not isinstance(key.get('table'), str):
            continue
        rows_by_table[key['table']].append(
            (record, set(binary_fields.get(str(index), []) or [])))
    tables = []
    for descriptor in descriptors:
        if not isinstance(descriptor, dict) or not descriptor.get('name'):
            continue
        name = descriptor['name']
        rows = rows_by_table.get(name, [])
        columns = {}
        for column in descriptor.get('columns') or []:
            field = column.get('name') if isinstance(column, dict) else None
            if not field or (allowed is not None and field not in allowed):
                continue
            columns[field] = _column_evidence(field, column, rows, allowed)
        declared_keys = [descriptor.get('primary_key') or [],
                         *(descriptor.get('unique_keys') or [])]
        keys = [list(key) for key in dict.fromkeys(tuple(key) for key in declared_keys)
                if key and all(column in columns for column in key)]
        sampled = bool(descriptor.get('sampled'))
        coverage = 'sampled' if sampled else profile.coverage
        tables.append(_table(name, profile.source_id, profile.kind, rows, columns, keys,
                             sampled=sampled, coverage=coverage, key_origin='declared',
                             partition=descriptor.get('schema')))
    return tables


def _sheet_tables(profile, allowed):
    tables = []
    regions = _excel_regions(profile)
    per_sheet = Counter(sheet for sheet, _ in regions)
    ordinals = Counter()
    for sheet, entries in regions:
        ordinals[sheet] += 1
        rows = [(record, set()) for _, _, record in entries]
        columns = {}
        for _, _, record in entries:
            for field in record:
                if field in columns or (allowed is not None and field not in allowed):
                    continue
                columns[field] = _column_evidence(field, {}, rows, allowed)
        keys, key_search = _inferred_keys(columns, rows)
        label = sheet or 'sheet'
        base = (label if per_sheet[sheet] == 1
                else f'{label}#{ordinals[sheet]}')
        tables.append(_table(base, profile.source_id, profile.kind, rows, columns, keys,
                             sampled=profile.sampled, coverage=profile.coverage,
                             key_origin='observed', partition=sheet,
                             key_search=key_search))
    return tables


def _flat_table(profile, allowed):
    fields = []
    for field in profile.fields or []:
        if field not in fields and (allowed is None or field in allowed):
            fields.append(field)
    for record in profile.records:
        for field in record:
            if field not in fields and (allowed is None or field in allowed):
                fields.append(field)
    rows = [(record, set()) for record in profile.records]
    columns = {field: _column_evidence(field, {}, rows, allowed) for field in fields}
    keys, key_search = _inferred_keys(columns, rows)
    total_rows = profile.metadata.get('total_rows')
    total_rows = total_rows if isinstance(total_rows, int) else None
    return [_table(profile.source_id, profile.source_id, profile.kind, rows, columns, keys,
                   sampled=profile.sampled, coverage=profile.coverage, key_origin='observed',
                   rows_total=total_rows, key_search=key_search)]


# Numbered clause leads: 「第一条」, 「1.」 and 「（一）」.  The number itself is
# the clause identity; the rest of the paragraph is its content.
_CLAUSE_NUMBER = (r'(?:第[一二三四五六七八九十百千零〇两\d]+条|\d{1,3}[.、．](?!\d)'
                  r'|[（(][一二三四五六七八九十\d]{1,4}[)）])')
_CLAUSE_LINE = re.compile(r'(?m)^' + _CLAUSE_NUMBER)
_CLAUSE_START = re.compile(_CLAUSE_NUMBER)


def _anchor(profile, selector):
    return {'source_ref': profile.source_id, 'source_revision': profile.source_revision,
            'selector': selector}


def _dedupe_names(names):
    """Deterministic collision-free header names, in the data layer's style."""
    used = set()
    out = []
    for index, raw in enumerate(names):
        base = re.sub(r'\s+', ' ', str(raw or '').strip()) or f'column_{index + 1}'
        name, suffix = base, 2
        while name in used:
            name = f'{base}_{suffix}'
            suffix += 1
        used.add(name)
        out.append(name)
    return out


def _docx_paragraphs(profile):
    paragraphs = profile.metadata.get('paragraphs')
    for paragraph in paragraphs if isinstance(paragraphs, list) else []:
        if (isinstance(paragraph, dict) and isinstance(paragraph.get('paragraph'), int)
                and isinstance(paragraph.get('text'), str)):
            yield paragraph


def _docx_sections(paragraphs, profile, disclose):
    """Heading hierarchy with the paragraph range each section covers."""
    root, stack = [], []
    for paragraph in paragraphs:
        number, text = paragraph['paragraph'], paragraph['text']
        if not text.strip():
            continue
        level = paragraph.get('heading_level')
        if isinstance(level, int) and 1 <= level <= 6:
            while stack and stack[-1]['level'] >= level:
                stack.pop()
            section = {
                'level': level, 'paragraph': number,
                'title': _sample_value(text) if disclose else None,
                'anchor': _anchor(profile, {'kind': 'text_span',
                                            'unit_ref': paragraph.get('unit_ref'),
                                            'char_start': 0, 'char_end': len(text)}),
                'paragraph_range': [number, number],
                'sections': [],
            }
            (stack[-1]['sections'] if stack else root).append(section)
            stack.append(section)
        for section in stack:
            section['paragraph_range'][1] = number
    return root


def _docx_clauses(paragraphs, profile, disclose):
    clauses = []
    for paragraph in paragraphs:
        text = paragraph['text']
        match = _CLAUSE_START.match(text)
        if not match:
            continue
        clauses.append({
            'number': match.group(0), 'paragraph': paragraph['paragraph'],
            'anchor': _anchor(profile, {'kind': 'text_span',
                                        'unit_ref': paragraph.get('unit_ref'),
                                        'char_start': match.start(), 'char_end': match.end()}),
            'text': _sample_value(text) if disclose else None,
        })
    return clauses


def _docx_tables(profile, allowed):
    """One evidence table per Word table record set; paragraphs stay prose."""
    sets = profile.metadata.get('record_sets')
    tables = []
    if not isinstance(sets, dict):
        return tables
    for name in sorted(sets):
        entry = sets[name]
        if not isinstance(entry, dict) or entry.get('kind') != 'table':
            continue
        records = [row for row in entry.get('records') or [] if isinstance(row, dict)]
        rows = [(row, set()) for row in records]
        fields = [field for field in (entry.get('fields') or
                                      dict.fromkeys(key for row in records for key in row))
                  if allowed is None or field in allowed]
        columns = {field: _column_evidence(field, {}, rows, allowed) for field in fields}
        if not columns:
            continue
        keys, key_search = _inferred_keys(columns, rows)
        tables.append(_table(name, profile.source_id, profile.kind, rows, columns, keys,
                             sampled=profile.sampled, coverage=profile.coverage,
                             key_origin='observed', partition=entry.get('table'),
                             key_search=key_search))
    return tables


def _pdf_pages(profile, disclose):
    """Text pages as top-level sections, with in-page clause candidates."""
    sections, clauses = [], []
    pages = profile.metadata.get('pages')
    for page in pages if isinstance(pages, list) else []:
        if not isinstance(page, dict) or not isinstance(page.get('page'), int):
            continue
        number, text = page['page'], page.get('text') or ''
        sections.append({
            'level': 1, 'page': number,
            'anchor': _anchor(profile, {'kind': 'pdf_text_span', 'page': number,
                                        'char_start': 0, 'char_end': len(text)}),
        })
        for match in _CLAUSE_LINE.finditer(text):
            clauses.append({
                'number': match.group(0), 'page': number,
                'anchor': _anchor(profile, {'kind': 'pdf_text_span', 'page': number,
                                            'char_start': match.start(),
                                            'char_end': match.end()}),
            })
    return sections, clauses


def _pdf_tables(profile, allowed):
    """One evidence table per detected PDF table, named by its page."""
    tables = []
    grouped = defaultdict(list)
    entries = profile.metadata.get('tables')
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict):
            continue
        raw, page = entry.get('rows'), entry.get('page')
        if not isinstance(raw, list) or len(raw) < 2 or not isinstance(page, int):
            continue
        header = _dedupe_names(['' if value is None else str(value) for value in raw[0]])
        rows = []
        for values in raw[1:]:
            if not isinstance(values, list):
                continue
            record = dict(zip(header, values))
            if any(value not in (None, '') for value in record.values()):
                rows.append((record, set()))
        fields = [field for field in header if allowed is None or field in allowed]
        columns = {field: _column_evidence(field, {}, rows, allowed) for field in fields}
        if not columns:
            continue
        keys, key_search = _inferred_keys(columns, rows)
        grouped[page].append((rows, columns, keys, key_search))
    for page in sorted(grouped):
        entries = grouped[page]
        for ordinal, (rows, columns, keys, key_search) in enumerate(entries, 1):
            base = f'page:{page}' + (f'#{ordinal}' if len(entries) > 1 else '')
            tables.append(_table(base, profile.source_id, profile.kind, rows, columns, keys,
                                 sampled=profile.sampled, coverage=profile.coverage,
                                 key_origin='observed', partition=page,
                                 key_search=key_search))
    return tables


def _document_tables(profile, allowed):
    if profile.kind == 'docx':
        return _docx_tables(profile, allowed)
    return _pdf_tables(profile, allowed)


def _paragraph_text_fields(profile):
    """The field names G4's paragraphs record set uses for paragraph text."""
    sets = profile.metadata.get('record_sets')
    entry = sets.get('paragraphs') if isinstance(sets, dict) else None
    fields = entry.get('fields') if isinstance(entry, dict) else None
    if isinstance(fields, list) and fields:
        return [field for field in fields if isinstance(field, str)]
    return ['text']


def _document_evidence(profile, allowed):
    """Section structure and clause candidates; text only under a disclosure.

    A configured policy alone is not consent to publish prose: the paragraph
    text field itself must be allowed -- a policy of table columns only keeps
    titles and clause text hidden.  Disclosed text is truncated like a table
    sample; structure and anchors are always given.
    """
    disclose = (allowed is not None
                and any(field in allowed for field in _paragraph_text_fields(profile)))
    record_sets = []
    if profile.kind == 'docx':
        paragraphs = list(_docx_paragraphs(profile))
        sections = _docx_sections(paragraphs, profile, disclose)
        clauses = _docx_clauses(paragraphs, profile, disclose)
        sets = profile.metadata.get('record_sets')
        for name, entry in sorted((sets or {}).items()):
            if isinstance(entry, dict):
                record_sets.append({'name': name, 'kind': entry.get('kind'),
                                    'count': entry.get('count')})
    else:
        sections, clauses = _pdf_pages(profile, disclose)
        for table in _pdf_tables(profile, allowed):
            record_sets.append({'name': table['_base'], 'kind': 'table',
                                'count': table['rows_observed']})
    return {'source_id': profile.source_id, 'kind': profile.kind,
            'sections': sections, 'clauses': clauses, 'record_sets': record_sets}


def _profile_tables(profile, allowed):
    if profile.kind in DB_KINDS:
        return _database_tables(profile, allowed)
    if profile.kind in SHEET_KINDS:
        return _sheet_tables(profile, allowed)
    if profile.kind in FLAT_KINDS:
        return _flat_table(profile, allowed)
    if profile.kind in DOCUMENT_KINDS:
        return _document_tables(profile, allowed)
    return []


def _assign_names(tables):
    counts = Counter(table['_base'] for table in tables)
    for table in tables:
        table['name'] = (table['_base'] if counts[table['_base']] == 1
                         else f'{table["source_id"]}::{table["_base"]}')


def _declared_links(profiles, tables, gaps):
    by_source = defaultdict(list)
    for table in tables:
        by_source[table['source_id']].append(table)
    links = []
    slots = set()
    for profile in profiles:
        if profile.kind not in DB_KINDS:
            continue
        descriptors = profile.metadata.get('tables')
        if not isinstance(descriptors, list):
            continue
        source_tables = by_source[profile.source_id]
        names = {table['_base']: table['name'] for table in source_tables}
        tables_by_name = {table['name']: table for table in source_tables}
        column_names = {}
        for descriptor in descriptors:
            if not isinstance(descriptor, dict) or not descriptor.get('name'):
                continue
            column_names[descriptor['name']] = {
                column['name'].translate(SQLITE_CASE_FOLD): column['name']
                for column in descriptor.get('columns') or []
                if isinstance(column, dict) and column.get('name')}
        identifiers = {name.translate(SQLITE_CASE_FOLD): name for name in names}
        for descriptor in descriptors:
            if not isinstance(descriptor, dict) or not descriptor.get('name'):
                continue
            source_base = descriptor['name']
            source = names.get(source_base)
            if source is None:
                continue
            table = tables_by_name[source]
            for foreign_key in descriptor.get('foreign_keys') or []:
                if not isinstance(foreign_key, dict):
                    continue
                source_columns = [
                    column_names[source_base].get(column.translate(SQLITE_CASE_FOLD), column)
                    for column in foreign_key.get('source_columns') or []]
                if not source_columns or not set(source_columns) <= table['columns'].keys():
                    continue
                slots.add((source, tuple(source_columns)))
                target_base = identifiers.get(
                    str(foreign_key.get('target_table', '')).translate(SQLITE_CASE_FOLD),
                    foreign_key.get('target_table'))
                if target_base not in names:
                    gaps.append({'source_id': profile.source_id, 'table': source,
                                 'code': 'declared_fk_target_outside_scope'})
                    continue
                target_columns = list(foreign_key.get('target_columns') or [])
                if not target_columns or all(column is None for column in target_columns):
                    target_columns = list(
                        next((descriptor.get('primary_key') or [] for descriptor in descriptors
                              if descriptor.get('name') == target_base), []))
                else:
                    target_columns = [
                        column_names[target_base].get(column.translate(SQLITE_CASE_FOLD), column)
                        if column is not None else None for column in target_columns]
                target = names[target_base]
                target_table = tables_by_name[target]
                if (len(source_columns) != len(target_columns)
                        or not set(target_columns) <= target_table['columns'].keys()):
                    gaps.append({'source_id': profile.source_id, 'table': source,
                                 'code': 'declared_fk_target_outside_scope'})
                    continue
                if not any(set(target_columns) == set(key) for key in target_table['keys']):
                    gaps.append({'source_id': profile.source_id, 'table': source,
                                 'code': 'declared_fk_target_key_unverified'})
                    continue
                links.append({'source_table': source, 'source_columns': source_columns,
                              'target_table': target, 'target_columns': target_columns})
    return links, slots


def _coverage(profiles):
    coverages = [profile.coverage for profile in profiles]
    if all(value == 'full' for value in coverages):
        return 'full'
    if 'partial' in coverages:
        return 'partial'
    if 'sampled' in coverages:
        return 'sampled'
    return 'unknown'


def _revision(profiles):
    if len(profiles) == 1:
        return profiles[0].source_revision
    return 'sha256:' + digest([[profile.source_id, profile.source_revision,
                                profile.metadata.get('structure_fingerprint')]
                               for profile in profiles])


def _fingerprint(profiles):
    if len(profiles) == 1:
        return profiles[0].metadata.get('structure_fingerprint')
    return digest([[profile.source_id, profile.metadata.get('structure_fingerprint')]
                   for profile in profiles])


def _source_entry(profile, tables):
    names = [table['name'] for table in tables if table['source_id'] == profile.source_id]
    total_rows = profile.metadata.get('total_rows')
    return {
        'source_id': profile.source_id,
        'kind': profile.kind,
        'source_revision': profile.source_revision,
        'coverage': profile.coverage,
        'sampled': bool(profile.sampled),
        'total_partitions': profile.total_partitions,
        'completed_partitions': list(profile.completed_partitions),
        'rows_total': total_rows if isinstance(total_rows, int) else None,
        'tables': names,
    }


def _source_gaps(profile, tables):
    names = {table['_base']: table['name'] for table in tables
             if table['source_id'] == profile.source_id}
    flat_tables = [table['name'] for table in tables if table['source_id'] == profile.source_id]
    out = []
    for gap in profile.gaps:
        if profile.kind in DB_KINDS:
            table = names.get(str(gap.partition))
        elif profile.kind in FLAT_KINDS and len(flat_tables) == 1:
            table = flat_tables[0]
        else:
            table = None
        out.append({'source_id': profile.source_id, 'table': table,
                    'partition': gap.partition, 'code': gap.code})
    return out


def _normalize_allowed(profiles, allowed_fields):
    if allowed_fields is None:
        return None
    if isinstance(allowed_fields, dict):
        return {profile.source_id: allowed_fields.get(profile.source_id, set())
                for profile in profiles}
    values = set(allowed_fields)
    return {profile.source_id: values for profile in profiles}


def collect_tables(profiles, allowed_fields):
    """Return table evidence plus declared links for every profile in one task."""
    profiles = list(profiles)
    allowed = _normalize_allowed(profiles, allowed_fields)
    tables = []
    documents = []
    for profile in profiles:
        scope = None if allowed is None else allowed.get(profile.source_id, set())
        tables.extend(_profile_tables(profile, scope))
        if profile.kind in DOCUMENT_KINDS:
            documents.append(_document_evidence(profile, scope))
    _assign_names(tables)
    gaps = []
    for profile in profiles:
        gaps.extend(_source_gaps(profile, tables))
    for table in tables:
        search = table.get('key_search') or {}
        if search.get('truncated'):
            gaps.append({'source_id': table['source_id'], 'table': table['name'],
                         'code': 'key_search_truncated'})
    links, slots = _declared_links(profiles, tables, gaps)
    sources = [_source_entry(profile, tables) for profile in profiles]
    return {
        'tables': tables,
        'sources': sources,
        'gaps': gaps,
        'declared': links,
        'declared_slots': slots,
        'documents': documents,
        'source_revision': _revision(profiles),
        'structure_fingerprint': _fingerprint(profiles),
        'coverage': _coverage(profiles),
    }
