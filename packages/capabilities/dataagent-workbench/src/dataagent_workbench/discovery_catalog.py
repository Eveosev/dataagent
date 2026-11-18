"""Build table-shaped discovery evidence and cross-source link candidates.

Column evidence is normalized per source by ``discovery_evidence``.  This
module adds the relationship rules the SQLite discovery flow already used:
declared foreign keys for database sources, and observed-value candidates that
require an equal field affinity, a unique target key and an affine field name
-- coincidental value overlap (a code that just happens to equal a limit, or
numbering that overlaps) must not become a link.  Both single-column and
composite candidates allow partial coverage: at least two distinct source
combinations must match, and at least half of all source rows -- rows without a
complete combination count as not matched.  The candidate carries the coverage
(matched, unmatched and missing rows, rate, unmatched values) so the proposal
can judge the optional relationship.  Several matching targets are marked
ambiguous instead of being silently chosen.
"""
import re
from collections import defaultdict

from dataagent_ontology.identity import digest

from .discovery_evidence import (DOCUMENT_KINDS, _sample_value, affinity,  # noqa: F401
                                  collect_tables, is_blank, key_counts, scalar)

_NAME_NOISE = re.compile(r'[\s_/-]+')
# Partial-coverage gates and the disclosure bound for unmatched values.
_MIN_MATCHED_DISTINCT = 2
_MIN_ROW_RATE = 0.5
_MAX_UNMATCHED_VALUES = 5


def _name_key(name):
    """Field names compared modulo separators, so 费用类型 and /fee_type match."""
    return _NAME_NOISE.sub('', str(name)).casefold()


def _row_totals(table, columns):
    """Source rows split into complete combinations and rows without one.

    ``key_counts`` drops rows whose combination is incomplete or carried by a
    binary value; those rows are still source rows that did not match, so the
    rate and the coverage count them instead of inflating both.
    """
    skip_blank = table['_skip_blank']
    complete = missing = 0
    for row, binary in table['_rows']:
        if binary.intersection(columns):
            missing += 1
        elif skip_blank and any(is_blank(row.get(column)) for column in columns):
            missing += 1
        elif any(scalar(row.get(column)) is None for column in columns):
            missing += 1
        else:
            complete += 1
    return complete, missing


def _covers(source_keys, target_keys, missing_rows):
    """Whether a partially covered source column set can still be a link.

    At least two distinct source combinations must exist as target keys, and
    at least half of all source rows must match -- ``missing_rows`` are the
    source rows without a complete combination, which never reach
    ``source_keys`` but still did not match.
    """
    matched = source_keys.keys() & target_keys
    if len(matched) < _MIN_MATCHED_DISTINCT:
        return False
    total_rows = sum(source_keys.values()) + missing_rows
    matched_rows = sum(source_keys[key] for key in matched)
    return total_rows > 0 and matched_rows >= _MIN_ROW_RATE * total_rows


def _coverage(source_keys, target_keys, missing_rows):
    """The partial-coverage record a candidate carries for judgement."""
    matched = source_keys.keys() & target_keys
    matched_rows = sum(source_keys[key] for key in matched)
    total_rows = sum(source_keys.values()) + missing_rows
    unmatched = [key for key in source_keys if key not in target_keys]
    return {
        'matched_rows': matched_rows,
        'total_rows': total_rows,
        'rate': matched_rows / total_rows if total_rows else 0.0,
        'unmatched_distinct': len(unmatched),
        'unmatched_rows': total_rows - matched_rows,
        'missing_rows': missing_rows,
        # A key part is a (storage class, value) pair; disclose its value
        # truncated like a sample.
        'unmatched_values': [[_sample_value(part[1]) for part in key]
                             for key in unmatched[:_MAX_UNMATCHED_VALUES]],
    }


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

    totals_cache = {}

    def totals(table, columns):
        key = (table, tuple(columns))
        if key not in totals_cache:
            totals_cache[key] = _row_totals(tables[table], columns)
        return totals_cache[key]

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
            'coverage': _coverage(source_keys, target_keys, totals(source, source_cols)[1]),
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
            # Every affine target key column that holds at least one observed
            # value.  The field name is a hard condition for every pair: values
            # alone do not tell a referenced customer from a coincidental code,
            # in documents and plain tables alike.
            name = _name_key(column)
            candidates = {pair for value in observed
                          for pair in key_index.get((family, value), ())
                          if pair[0] != source and _name_key(pair[1]) == name}
            missing_rows = totals(source, columns)[1]
            alternatives = []
            for target, target_col in sorted(candidates):
                # Partial coverage: at least two matched distinct values and
                # at least half of all source rows; the candidate itself
                # carries the coverage for the proposal to judge.
                if not _covers(observed, counts(target, [target_col]).keys(), missing_rows):
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

    # Composite target keys are matched by column combination: the source must
    # carry one name-affine column per key column, and at least two distinct
    # combinations must exist as target keys with at least half the source
    # rows covered.  Unmatched rows do not discard the candidate; the coverage
    # record on the candidate lets the proposal keep it optional.
    composite_slots = defaultdict(list)
    for target, table in tables.items():
        for key in table['keys']:
            if len(key) < 2 or any(table['columns'][column]['affinity'] in {'blob', 'unknown'}
                                   for column in key):
                continue
            target_keys = counts(target, key).keys()
            for source, source_table in tables.items():
                if source == target:
                    continue
                source_cols = []
                for column in key:
                    affine = [candidate for candidate in source_table['columns']
                              if _name_key(candidate) == _name_key(column)]
                    if len(affine) != 1:
                        source_cols = None
                        break
                    source_cols.append(affine[0])
                if source_cols is None:
                    continue
                slot = (source, tuple(source_cols))
                if slot in declared_slots:
                    continue
                if any(set(source_cols) < set(existing) for existing in source_table['keys']):
                    continue  # a proper identity prefix is not reference evidence
                observed = counts(source, source_cols)
                if len(observed) < 2:
                    continue
                if not _covers(observed, target_keys, totals(source, source_cols)[1]):
                    continue
                composite_slots[slot].append(
                    relationship(source, source_cols, target, list(key), 'sample_supported'))
    for candidates in composite_slots.values():
        if len(candidates) > 1:
            for candidate in candidates:
                candidate['ambiguous'] = True
        if len(candidates) > inferred_limit:
            truncated = True
        else:
            relationships.extend(candidates)
            inferred_limit -= len(candidates)
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
        'documents': evidence['documents'],
        'source_revision': revision,
        'structure_fingerprint': evidence['structure_fingerprint'],
    }
