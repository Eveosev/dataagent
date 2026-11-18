"""Build table-shaped discovery evidence and cross-source link candidates.

Column evidence is normalized per source by ``discovery_evidence``.  This
module adds the relationship rules the SQLite discovery flow already used:
declared foreign keys for database sources, and observed-value candidates that
require an equal field affinity, a unique target key and at least two distinct
non-null source values that all match.  Several matching targets are marked
ambiguous instead of being silently chosen.
"""
from collections import defaultdict

from dataagent_ontology.identity import digest

from .discovery_evidence import affinity, collect_tables, key_counts  # noqa: F401


def build_catalog(profiles, allowed_fields=None):
    if hasattr(profiles, 'source_id'):
        profiles = [profiles]
    profiles = list(profiles)
    if allowed_fields is not None and not isinstance(allowed_fields, dict):
        values = set(allowed_fields)
        allowed_fields = {profile.source_id: values for profile in profiles}
    evidence = collect_tables(profiles, allowed_fields)
    tables = {table['name']: table for table in evidence['tables']}
    revision = evidence['source_revision']

    cache = {}

    def counts(table, columns):
        key = (table, tuple(columns))
        if key not in cache:
            cache[key] = key_counts(tables[table]['_rows'], columns,
                                    skip_blank=tables[table]['_skip_blank'])
        return cache[key]

    def relationship(source, source_cols, target, target_cols, origin):
        source_keys, target_keys = counts(source, source_cols), counts(target, target_cols)
        matched = source_keys.keys() & target_keys.keys()
        return {
            'id': digest([revision, source, source_cols, target, target_cols, origin]),
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
    gaps = list(evidence['gaps'])
    for link in evidence['declared']:
        source, target = link['source_table'], link['target_table']
        if source not in tables or target not in tables:
            continue
        if not any(set(link['target_columns']) == set(key) for key in tables[target]['keys']):
            continue
        relationships.append(relationship(source, link['source_columns'], target,
                                          link['target_columns'], 'declared'))

    # Candidate generation uses the observed key index. A shared ID alone is weak evidence.
    key_index = defaultdict(list)
    for target, table in tables.items():
        for columns in table['keys']:
            if len(columns) != 1:
                continue
            column = columns[0]
            if column not in table['columns']:
                continue
            type_family = table['columns'][column]['affinity']
            if type_family in {'blob', 'unknown'}:
                continue
            for value in counts(target, columns):
                key_index[type_family, value].append((target, column))

    declared_slots = evidence['declared_slots']
    inferred_limit = 200
    truncated = False
    for source, table in tables.items():
        for column, column_evidence in table['columns'].items():
            columns = [column]
            if (source, (column,)) in declared_slots or columns in table['keys']:
                continue
            family = column_evidence['affinity']
            if family in {'blob', 'unknown'}:
                continue
            observed = counts(source, columns)
            if len(observed) < 2:
                continue
            candidate_lists = [key_index.get((family, value), ()) for value in observed]
            smallest = min(candidate_lists, key=len)
            alternatives = []
            for target, target_col in smallest:
                if target == source or not observed.keys() <= counts(target, [target_col]).keys():
                    continue
                alternatives.append(relationship(source, columns, target, [target_col],
                                                 'sample_supported'))
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

    public_tables = [{key: value for key, value in table.items()
                      if not key.startswith('_')} for table in evidence['tables']]
    return {
        'tables': public_tables,
        'relationships': list({candidate['id']: candidate
                               for candidate in relationships}.values()),
        'gaps': gaps,
        'sources': evidence['sources'],
        'source_revision': revision,
        'structure_fingerprint': evidence['structure_fingerprint'],
    }
