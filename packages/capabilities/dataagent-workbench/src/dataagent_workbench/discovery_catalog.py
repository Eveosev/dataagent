"""Build table-qualified discovery evidence from an immutable SQLite profile."""
from collections import Counter, defaultdict
from string import ascii_lowercase, ascii_uppercase

from dataagent_ontology.identity import digest


SQLITE_CASE_FOLD = str.maketrans(ascii_uppercase, ascii_lowercase)


def affinity(declared_type):
    name = declared_type.upper()
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


def key_counts(rows, columns):
    counts = Counter()
    for row, binary_fields in rows:
        if binary_fields.intersection(columns):
            continue
        key = tuple(scalar(row.get(column)) for column in columns)
        if all(part is not None for part in key):
            counts[key] += 1
    return counts


def build_catalog(profile, allowed_fields):
    rows_by_table = defaultdict(list)
    binary_fields = profile.metadata.get('binary_fields', {})
    records = zip(profile.records, profile.metadata['record_keys'], strict=True)
    for index, (record, key) in enumerate(records):
        rows_by_table[key['table']].append((record, set(binary_fields.get(str(index), []))))
    tables = {}
    for descriptor in profile.metadata['tables']:
        name = descriptor['name']
        rows = rows_by_table[name]
        columns = {}
        for column in descriptor['columns']:
            field = column['name']
            if allowed_fields is not None and field not in allowed_fields:
                continue
            values = [(field in binary, row[field]) for row, binary in rows if row[field] is not None]
            samples = []
            if allowed_fields is not None:
                literals = [value for binary, value in values if not binary]
                samples = list(dict.fromkeys(value[:160] if isinstance(value, str) else value
                                             for value in literals))[:3]
            columns[field] = {
                **column, 'null_rows': len(rows) - len(values),
                'distinct_values': len({(binary, scalar(value)) for binary, value in values}),
                'samples': samples,
            }
        declared_keys = [descriptor['primary_key'], *descriptor.get('unique_keys', [])]
        keys = [list(key) for key in dict.fromkeys(tuple(key) for key in declared_keys)
                if key and all(c in columns for c in key)]
        tables[name] = {
            'name': name, 'rows_observed': len(rows), 'sampled': descriptor['sampled'],
            'columns': columns, 'keys': keys,
            'identity_keys': [key for key in keys if all(columns[c]['null_rows'] == 0 for c in key)],
        }

    cache = {}

    def counts(table, columns):
        key = table, tuple(columns)
        if key not in cache:
            cache[key] = key_counts(rows_by_table[table], columns)
        return cache[key]

    def relationship(source, source_cols, target, target_cols, origin):
        source_keys, target_keys = counts(source, source_cols), counts(target, target_cols)
        matched = source_keys.keys() & target_keys.keys()
        return {
            'id': digest([profile.source_revision, source, source_cols, target, target_cols, origin]),
            'origin': origin, 'source_table': source, 'source_columns': source_cols,
            'target_table': target, 'target_columns': target_cols,
            'comparison': 'exact_observed_values',
            'matched_rows': sum(source_keys[key] for key in matched),
            'checked_rows': sum(source_keys.values()),
            'matched_distinct_keys': len(matched),
            'sampled': tables[source]['sampled'] or tables[target]['sampled'],
            'cardinality': 'one_to_one' if any(set(key) <= set(source_cols) for key in tables[source]['keys'])
                           else 'many_to_one',
            'ambiguous': False,
        }

    relationships = []
    gaps = [{'table': gap.partition, 'code': gap.code} for gap in profile.gaps]
    declared_slots = set()
    descriptors = {table['name']: table for table in profile.metadata['tables']}
    identifiers = {name.translate(SQLITE_CASE_FOLD): name for name in descriptors}
    column_names = {
        name: {col['name'].translate(SQLITE_CASE_FOLD): col['name'] for col in table['columns']}
        for name, table in descriptors.items()
    }
    for source, descriptor in descriptors.items():
        for fk in descriptor.get('foreign_keys', []):
            source_cols = [column_names[source].get(col.translate(SQLITE_CASE_FOLD), col)
                           for col in fk['source_columns']]
            if not set(source_cols) <= tables[source]['columns'].keys():
                continue
            declared_slots.add((source, tuple(source_cols)))
            target = identifiers.get(fk['target_table'].translate(SQLITE_CASE_FOLD), fk['target_table'])
            target_cols = fk['target_columns']
            if target in descriptors:
                if all(col is None for col in target_cols):
                    target_cols = descriptors[target]['primary_key']
                else:
                    target_cols = [column_names[target].get(col.translate(SQLITE_CASE_FOLD), col)
                                   if col is not None else None for col in target_cols]
            if (target not in tables or len(source_cols) != len(target_cols)
                    or not set(target_cols) <= tables[target]['columns'].keys()):
                gaps.append({'table': source, 'code': 'declared_fk_target_outside_scope'})
                continue
            if not any(set(target_cols) == set(key) for key in tables[target]['keys']):
                gaps.append({'table': source, 'code': 'declared_fk_target_key_unverified'})
                continue
            relationships.append(relationship(source, source_cols, target, target_cols, 'declared'))

    # Candidate generation uses the observed key index. A shared ID alone is weak evidence.
    key_index = defaultdict(list)
    for target, table in tables.items():
        for columns in table['keys']:
            if len(columns) != 1:
                continue
            column = columns[0]
            type_family = affinity(table['columns'][column]['type'])
            if type_family == 'blob':
                continue
            for value in counts(target, columns):
                key_index[type_family, value].append((target, column))

    inferred_limit = 200
    truncated = False
    for source, table in tables.items():
        for column, evidence in table['columns'].items():
            columns = [column]
            if (source, (column,)) in declared_slots or columns in table['keys']:
                continue
            observed = counts(source, columns)
            if len(observed) < 2:
                continue
            family = affinity(evidence['type'])
            candidate_lists = [key_index.get((family, value), ()) for value in observed]
            smallest = min(candidate_lists, key=len)
            alternatives = []
            for target, target_col in smallest:
                if target == source or not observed.keys() <= counts(target, [target_col]).keys():
                    continue
                alternatives.append(relationship(source, columns, target, [target_col], 'sample_supported'))
            if len(alternatives) > 1:
                for candidate in alternatives:
                    candidate['ambiguous'] = True
            if len(alternatives) > inferred_limit:
                truncated = True
            else:
                relationships.extend(alternatives)
                inferred_limit -= len(alternatives)
    if truncated:
        gaps.append({'code': 'candidate_budget_exceeded'})
    return {
        'tables': list(tables.values()),
        'relationships': list({candidate['id']: candidate for candidate in relationships}.values()),
        'gaps': gaps,
    }
