"""Durable intake coordination over isolated probes and validated ontology proposals."""
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from pydantic_core import to_jsonable_python
from dataagent_contracts.core.refs import SourceAnchor
from dataagent_contracts.intake import CoverageGap, SourceProfile
from dataagent_contracts.ontology import Assertion, MappingPreview, MappingSpec, RoleBinding
from dataagent_runtime.ports.workbench_store import Write,VersionConflict
from dataagent_ontology.facts import relation_key
from dataagent_ontology.identity import digest
from dataagent_ontology.mapping import _typed
from .adapters.layer_client import DataLayerProbeError, LayerClient,installed_data_package
from .inference_requests import mapping_request
from .document_fields import ReplayError, extract_fields, replay_fields
from .clause_records import (ClauseReplayError, extract_clause_records as build_clause_records,
                             replay_clause_records)
from .ontology_discovery import is_discovery
from .session_service import mapping_target


BUDGET_GAP = 'time_budget_exceeded'
_REST_RETRY_GAPS = {'connection_failed','rate_limited','http_error'}
_MIN_SEGMENT_SECONDS = 0.25
_MAX_SEGMENTS = 500
_DEFAULT_BUDGET_SECONDS = 50.0
_BUDGET_CAP_SECONDS = 50.0
_MAX_BUDGET_RESERVE_SECONDS = 5.0
_BUDGET_RESERVE_RATIO = 0.1
_MIN_PROBE_SECONDS = 0.01

_PREVIEW_BLOCK_DETAIL = 'preview contains unresolved issues'
_REPLAY_FAILED = 'intake.mapping_replay_failed'
_PENDING_CORRECTIONS = 'intake.pending_corrections'
_DISPOSITIONS = 'intake.dispositions'
_INHERITABLE_CORRECTIONS = 'intake.inheritable_corrections'
_PARTIAL_SAVE = 'intake.partial_save'
_BLOCKING_ENTITY_ISSUES = {
    'ontology.conflicting_values', 'ontology.required_value_missing',
    'ontology.conversion_failed', 'ontology.evidence_missing',
    'ontology.correction_conflict', 'ontology.relation_unresolved',
}
_GLOBAL_BLOCKING_ISSUES = {
    'ontology.required_binding_missing', 'ontology.no_records',
}
_RESOLVABLE_ISSUES = {
    'ontology.conflicting_values', 'ontology.required_value_missing',
    'ontology.conversion_failed',
}
# Row-level problems that one mapping defect can repeat across many rows.
# They are counted once per (code, property, source) and carry the affected
# row count separately; the web groups them with the same key (FDE2-06).
# A missing required value also collapses to one root cause per column: the
# per-row list stays on the preview for locating and correcting each object,
# only the root-cause count stops reading "131 项根因" (FDE2-06 余项).
_ROW_LEVEL_ISSUE_CODES = frozenset({
    'ontology.conversion_failed', 'ontology.identity_unresolved',
    'ontology.required_value_missing', 'ontology.evidence_missing',
    'record_attribution_unverified',
})
# FDE3-04: a proposed or observed source that clearly cannot carry the task's
# target concept (no identity column, most required properties unbindable).
_SOURCE_CONCEPT_MISMATCH = 'ontology.source_concept_mismatch'
# Source-column names that commonly carry the same concept slot.  This is a
# deliberately small, conservative vocabulary used only to avoid excluding a
# source whose column is an alias rather than the exact property name.  Exact
# (normalised) names always win; these never override an observed exact match.
_FIELD_ALIASES = {
    'amount': (
        'amount', 'amountminor', 'amountcents', 'amountincents', 'total',
        'totalamount', 'grossamount', 'netamount', 'taxamount',
        '金额', '报销金额', '含税金额', '价税合计', '总额', '费用金额'),
    'currency': ('currency', 'ccy', 'currencycode', '币种', '币别', '货币'),
    'party': (
        'issuer', 'supplier', 'customer', 'party', 'partyno', 'payee',
        '供应商', '客户', '开票方', '销售方', '收款方'),
    'date': ('date', 'invoicedate', 'expensedate', 'occurredat',
             '日期', '时间', '开票日期', '发生日期'),
    'quantity': ('quantity', 'qty', '数量'),
    'identity': (
        'number', 'no', 'id', 'code', 'docno', 'documentno', 'orderno',
        'invoiceno', 'billno', 'bookno', 'serialno', 'seq', 'sequence',
        '单号', '单据号', '单据编号', '报销单号', '发票号', '编号', '凭证号',
        '序号', '行号'),
}


def _field_key(name):
    """A comparison key that ignores casing and separators, but keeps CJK."""
    return ''.join(char for char in str(name).lower() if char.isalnum())


def _field_kind(name):
    """The concept slot a source column plausibly carries, if recognisable."""
    key = _field_key(name)
    for kind, aliases in _FIELD_ALIASES.items():
        for alias in aliases:
            alias_key = _field_key(alias)
            if key == alias_key or (not alias_key.isascii() and alias_key in key):
                return kind
    # Common identity suffixes not covered by the fixed vocabulary: the
    # target concept's own property may be ``standard_no``/``line_no`` while
    # the source calls the column ``number`` or ``单据编号``.
    if key.endswith(('no', 'number', 'code', '编号', '号')):
        return 'identity'
    return ''
_ISSUE_REASONS = {
    'ontology.conflicting_values': '各来源的字段值不一致',
    'ontology.required_value_missing': '缺少必填值',
    'ontology.required_binding_missing': '必填属性没有映射',
    'ontology.identity_unresolved': '缺少单据号，无法确定对象',
    'ontology.conversion_failed': '值无法按目标类型转换',
    'ontology.evidence_missing': '值没有来源定位',
    'ontology.incomplete_source': '来源未完整读取',
    'ontology.source_unmapped': '该来源未用于当前映射',
    'ontology.source_concept_mismatch': '该来源与目标概念不符',
    'ontology.relation_unresolved': '关联字段不完整',
    'ontology.correction_conflict': '网页纠正无法沿用',
    'ontology.no_records': '没有可映射的记录',
    'record_attribution_unverified': '该记录的引文归属未核实',
}


class PreviewBlocked(ValueError):
    """A save was refused; ``issues`` names affected objects and reasons.

    The detail string stays the stable contract expected by existing callers
    while the structured list carries the object-level explanation.
    """

    def __init__(self, issues):
        self.issues = list(issues)
        super().__init__(_PREVIEW_BLOCK_DETAIL)


def _rest_retryable(profile):
    return (profile.kind == 'rest' and profile.coverage == 'partial'
            and profile.metadata.get('source_version') is not None
            and profile.metadata.get('row_offset') == 0 and bool(profile.metadata.get('cursor'))
            and all(gap.code in _REST_RETRY_GAPS for gap in profile.gaps))


def _resumable(profile):
    """True when the profile carries a checkpoint produced by a segment budget."""
    state = profile.metadata.get('resume') if isinstance(profile.metadata, dict) else None
    return (isinstance(state, dict)
            and any(gap.code == BUDGET_GAP for gap in profile.gaps))


def _failure_state(profile):
    """Return (error, attempts, retryable) for a persisted failure, if any."""
    metadata = profile.metadata if isinstance(profile.metadata, dict) else {}
    error = metadata.get('probe_error')
    if not isinstance(error, dict):
        return None
    attempts = metadata.get('probe_attempts', 1)
    attempts = attempts if isinstance(attempts, int) else 1
    return error, attempts, bool(error.get('retryable'))


def _retryable_failure(profile):
    """A coded, transient failure may be probed again a bounded number of times."""
    state = _failure_state(profile)
    return bool(state and state[2] and state[1] < 2)


def _exhausted_failure(profile):
    """A failure that must not be retried automatically any more."""
    state = _failure_state(profile)
    return bool(state and (not state[2] or state[1] >= 2))


def _segment_budget(value):
    try:
        seconds = _DEFAULT_BUDGET_SECONDS if value is None else float(value)
    except (TypeError, ValueError):
        seconds = _DEFAULT_BUDGET_SECONDS
    # The host gives a tool call 60s. Keep the configured allowance at 50s or
    # less; _probe_deadline spends part of it on persistence/transport.
    return min(_BUDGET_CAP_SECONDS, max(0.1, seconds))


def _probe_deadline(seconds):
    """Wall deadline for probe work, reserving time to persist the result.

    The reserve grows with the allowance up to a fixed cap, so a small
    configured budget still performs useful work while a 50s budget leaves
    enough room for profile/session writes and the MCP round trip.
    """
    budget = min(_BUDGET_CAP_SECONDS, max(0.1, float(seconds)))
    reserve = min(_MAX_BUDGET_RESERVE_SECONDS, budget * _BUDGET_RESERVE_RATIO)
    return time.monotonic() + max(_MIN_PROBE_SECONDS, budget - reserve)


def _deadline_key(profile):
    state = profile.metadata.get('resume') if isinstance(profile.metadata, dict) else None
    return (json.dumps(state, sort_keys=True, default=str),
            len(profile.records), tuple(profile.completed_partitions))


class IntakeService:
    def __init__(self,wb):
        self.wb=wb
        self.budget_seconds=_segment_budget(os.environ.get('DATAAGENT_INTAKE_BUDGET_SECONDS'))

    def _profiles(self,session):
        out=[]
        for key,ref in session.selected_versions.items():
            if not key.startswith('profile:'):continue
            id,rev=ref.rsplit('@',1)
            row=self.wb.store.get('profile',id,rev,scope=self.wb.scope)
            if row is None:raise ValueError('selected source observation missing')
            out.append(SourceProfile.model_validate(row['body']))
        return out

    def _target(self,session):
        """(ontology, concept name, concept definition) fixed on this task.

        The builtin definition remains the default target for tasks that
        predate pinned targets or were started without one.
        """
        wb=self.wb
        ext=mapping_target(session)
        if ext is not None:
            ontology=wb.ontology.definition(f"{ext['ontology_id']}@{ext['revision']}",wb.ctx)
            name,concept=ontology.resolve_concept(ext.get('concept',''))
        else:
            ontology=wb.definition
            name,concept=ontology.resolve_concept()
        return ontology,name,concept

    def _source_descriptors(self, session):
        """Stable source identity shown next to original values and positions."""
        return {source.source_id: {
            'source_id': source.source_id, 'kind': source.kind,
            'locator_ref': source.locator_ref,
            'source_name': str(source.options.get('display_name') or source.locator_ref),
        } for source in session.sources}

    @staticmethod
    def _selector_location(selector):
        if not isinstance(selector, dict):
            return ''
        parts = []
        if selector.get('page') is not None:
            parts.append(f'第 {selector["page"]} 页')
        keys = selector.get('keys')
        if isinstance(keys, dict):
            if keys.get('row') is not None:
                parts.append(f'第 {keys["row"]} 行')
            primary = keys.get('primary_key')
            if isinstance(primary, dict):
                parts.append('主键 ' + ', '.join(f'{key}={value}' for key, value in primary.items()))
        if selector.get('pointer'):
            parts.append(str(selector['pointer']))
        if selector.get('range'):
            parts.append(str(selector['range']))
        if selector.get('char_start') is not None:
            parts.append(f'字符 {selector.get("char_start")}–{selector.get("char_end")}')
        return ' · '.join(parts)

    def conflict_details(self, session, body):
        """Per-source original values and positions for every conflict field.

        The preview keeps one assertion per source record.  Conflict issues only
        say that values differ, so the web page and the agent report need this
        projection to show e.g. pdf=4800.00 (page 4) next to sqlite=4880 (row 4).
        """
        if not body:
            return []
        sources = self._source_descriptors(session)
        labels = self._object_labels(session, body)
        details = []
        for issue in body.get('issues') or []:
            if issue.get('code') != 'ontology.conflicting_values':
                continue
            entity_id, target = issue.get('entity_id'), issue.get('target')
            if not entity_id or not target:
                continue
            grouped = {}
            for assertion in body.get('assertions') or []:
                if assertion.get('relation') != target:
                    continue
                roles = {role.get('role'): role.get('value')
                         for role in assertion.get('role_bindings') or []}
                if roles.get('subject') != entity_id:
                    continue
                for anchor in assertion.get('source_anchors') or []:
                    source_id = anchor.get('source_ref')
                    info = sources.get(source_id)
                    if info is None:
                        info = {'source_id': source_id, 'source_name': '用户纠正',
                                'locator_ref': source_id, 'kind': 'correction'}
                    entry = grouped.setdefault(source_id, {
                        'source_id': source_id, 'source_name': info['source_name'],
                        'locator_ref': info['locator_ref'], 'kind': info['kind'],
                        'value': to_jsonable_python(roles.get('value')), 'values': [],
                        'locations': []})
                    value = to_jsonable_python(roles.get('value'))
                    if value not in entry['values']:
                        entry['values'].append(value)
                    location = self._selector_location(anchor.get('selector') or {})
                    if location and location not in entry['locations']:
                        entry['locations'].append(location)
            details.append({'entity_id': entity_id, 'object': labels.get(entity_id),
                            'field': target,
                            'reason': _ISSUE_REASONS.get('ontology.conflicting_values'),
                            'values': list(grouped.values())})
        return details

    def _disposition_row(self, session):
        ref = session.selected_versions.get('dispositions')
        if not ref:
            return None, None
        try:
            disposition_id, revision = ref.rsplit('@', 1)
        except ValueError:
            return None, None
        row = self.wb.store.get('disposition', disposition_id, revision, scope=self.wb.scope)
        return (row, revision) if row is not None else (None, None)

    def disposition_entries(self, session):
        row, _ = self._disposition_row(session)
        return list(row['body'].get('entries') or []) if row is not None else []

    def _mapped_source_ids(self, session):
        """Sources a proposal has already pinned a mapping revision on.

        The web regenerates a preview from this durable scope instead of
        silently adding sources the agent never mapped (FDE2-05).
        """
        return {key.split(':', 1)[1] for key in session.selected_versions
                if key.startswith('mapping:')}

    def _active_preview_body(self, session):
        """The stored body of the preview the session currently points at."""
        ref = session.selected_versions.get('preview')
        if not ref:
            return None
        try:
            preview_id, revision = ref.rsplit('@', 1)
        except ValueError:
            return None
        row = self.wb.store.get('preview', preview_id, revision, scope=self.wb.scope)
        return row['body'] if row is not None else None

    def _preview_source_ids(self, session):
        """Sources the active preview actually maps, or None without a preview.

        A source may have an older ``mapping:<source>`` entry and still be left
        out of the latest preview (an agent submitted a narrower proposal).
        Whether it is "used by the current mapping" must follow the preview the
        operator is looking at, not the historical scope, or the source-level
        issue would name a source that ``dispose`` then refuses.
        """
        body = self._active_preview_body(session)
        return set((body.get('source_revisions') or {})) if body is not None else None

    def _selected_mappings(self, session):
        """The mapping specs the task pinned for each mapped source.

        The web keeps regenerating from this durable scope; exposing the specs
        also keeps the agent's bindings and transforms after a disposition
        invalidated the preview, instead of silently falling back to default
        same-name bindings (FDE2-05 regeneration).
        """
        mappings = {}
        for key, ref in session.selected_versions.items():
            if not key.startswith('mapping:'):
                continue
            try:
                mapping_id, revision = ref.rsplit('@', 1)
            except ValueError:
                continue
            row = self.wb.store.get('mapping', mapping_id, revision, scope=self.wb.scope)
            if row is not None:
                mappings[key.split(':', 1)[1]] = row['body']
        return mappings

    def _ignored_source_ids(self, session):
        """Sources an audited disposition removed from this task's scope."""
        return {entry.get('source_id') for entry in self.disposition_entries(session)
                if entry.get('action') == 'ignore_source'}

    @staticmethod
    def _available_properties(concept, fields, bindings=None):
        """Properties the observed columns can plausibly serve.

        Exact (normalised) names win first; a small alias vocabulary then fills
        the remaining identity/required slots one column at a time.  A proposal
        binding can add evidence for a non-identity property whose column name
        is outside the vocabulary; an omission never removes a column that was
        observed.  Identity columns are judged from the source's own names (or
        the alias vocabulary): a proposal must not be able to invent an
        identity column a source does not have.
        """
        remaining = set(fields)
        available = set()
        by_key = {}
        for field in remaining:
            by_key.setdefault(_field_key(field), field)
        # The fit check only needs identity and required slots; optional
        # properties must not consume a column a required slot could use.
        required = [name for name, definition in concept.properties.items()
                    if definition.required]
        needed = [*concept.identity_fields,
                  *(name for name in required if name not in concept.identity_fields)]
        for name in needed:
            field = by_key.pop(_field_key(name), None)
            if field is not None:
                available.add(name)
                remaining.discard(field)
        # Identity first, then required: when one alias column could fill two
        # slots, the object-naming slot gets it.
        for name in needed:
            if name in available:
                continue
            kind = _field_kind(name)
            if not kind:
                continue
            match = next((field for field in remaining
                          if _field_kind(field) == kind), None)
            if match is not None:
                available.add(name)
                remaining.discard(match)
        # A proposal that names a source column is evidence for a required
        # property whose name is outside the alias vocabulary.  The reverse is
        # deliberately not true: an omitted binding never hides a column the
        # structure check found, and identity columns are not supplemented
        # from bindings.
        for name, binding in (bindings or {}).items():
            if name in concept.properties and name not in concept.identity_fields \
                    and binding and binding.source_field in fields:
                available.add(name)
        return available

    @staticmethod
    def _source_matches_concept(concept, profile, bindings=None):
        """False only when the source structure cannot carry the concept.

        FDE3-04: a limit-table document proposed into an expense-line task used
        to turn every one of its rows into an unidentified object plus a
        missing-value problem.  The check looks at the observed columns (with
        explicitly bound non-identity columns as extra evidence): a column
        that exists but was omitted from the proposal stays in the preview and
        is reported as an unbound required property, while a source that has
        no identity column (or cannot supply more than half of the required
        properties) is held out.  Alias names such as 单据编号/金额/币种 count
        as the matching slot; exact names always win.
        """
        fields = set(profile.fields or [])
        if not fields:
            # Nothing was observed (a header-only file yields no fields): the
            # source is empty and its own problems (no records, unread) speak
            # for it; there is nothing to judge a concept mismatch against.
            return True
        available = IntakeService._available_properties(concept, fields, bindings)
        identity = list(concept.identity_fields)
        # Every identity field is needed to name an object.  A source that
        # supplies only part of a composite identity cannot name the object;
        # an omission of an observed column is a mapping gap, not a mismatch.
        if identity and not set(identity) <= available:
            return False
        required = [name for name, definition in concept.properties.items()
                     if definition.required]
        if not required:
            return True
        # A source without the majority of required columns cannot carry the
        # concept; one missing required column is still a real, incomplete
        # mapping with a per-column problem to correct.
        return 2 * sum(1 for name in required if name in available) > len(required)

    def _source_scope_issues(self, session, used, proposals=None):
        """One source-level issue per observed source outside the preview.

        A source left out of the proposal keeps ``source_unmapped``; one that
        clearly cannot carry the target concept (identity column missing,
        most required properties unbindable) is named as a mismatch instead,
        so the page offers "this task does not use the source" and never an
        "include in mapping" escape (FDE3-04).
        """
        ignored = self._ignored_source_ids(session)
        _, _, concept = self._target(session)
        issues = []
        for profile in self._profiles(session):
            if profile.source_id in used or profile.source_id in ignored:
                continue
            proposal = (proposals or {}).get(profile.source_id)
            if not self._source_matches_concept(
                    concept, profile,
                    proposal.bindings if proposal is not None else None):
                issues.append({'code': _SOURCE_CONCEPT_MISMATCH,
                               'source_id': profile.source_id,
                               'detail': '该来源缺少任务目标概念的身份字段，'
                                         '或必需属性大多无法绑定'})
            else:
                issues.append({'code': 'ontology.source_unmapped',
                               'source_id': profile.source_id})
        return issues

    @staticmethod
    def _deduped_issues(issues):
        """One problem per row and root cause.

        A value that fails conversion also leaves the required property
        missing on the same row and column; reporting both doubles the count
        (20 rows read as 40 problems) without adding information.
        """
        failed = {(issue.get('source_id'), issue.get('row'), issue.get('target'))
                  for issue in issues
                  if issue.get('code') == 'ontology.conversion_failed'
                  and issue.get('row') is not None}
        return [issue for issue in issues
                if not (issue.get('code') == 'ontology.required_value_missing'
                        and (issue.get('source_id'), issue.get('row'),
                             issue.get('target')) in failed)]

    @classmethod
    def _issue_groups(cls, issues):
        """Collapse per-row problems into root causes plus an affected-row count.

        Two rows failing the same column conversion are one mapping defect, so
        the cause count is one and the row count is two.  Non-row problems stay
        one entry each.  The web uses the same grouping key, and the per-row
        list is still returned separately for locating and correcting values.
        """
        deduped = cls._deduped_issues(issues)
        groups, by_key = [], {}
        for issue in deduped:
            row = issue.get('row')
            code = issue.get('code')
            if code not in _ROW_LEVEL_ISSUE_CODES:
                groups.append(dict(issue))
                continue
            key = (code, issue.get('target'), issue.get('source_id'))
            entry = by_key.get(key)
            if entry is None:
                entry = dict(issue)
                entry['rows'] = []
                entry['row_count'] = 0
                by_key[key] = entry
                groups.append(entry)
            if row is not None and row not in entry['rows']:
                entry['rows'].append(row)
                entry['row_count'] += 1
        return groups, cls._issue_row_count(deduped)

    @staticmethod
    def _issue_row_count(issues):
        """Distinct (source, row) pairs, accepting per-row or grouped entries."""
        rows = set()
        for issue in issues:
            source = issue.get('source_id')
            grouped = issue.get('rows')
            if isinstance(grouped, list) and grouped:
                for row in grouped:
                    if row is not None:
                        rows.add((source, row))
            elif issue.get('row') is not None:
                rows.add((source, issue.get('row')))
        return len(rows)

    @classmethod
    def _session_issues(cls, issues):
        """The root-cause list stored on the session for ``intake_status``.

        Its length is the unified root-cause count; the stored preview keeps
        the per-row list so every row can still be located and corrected.
        """
        return cls._issue_groups(issues)[0]

    @staticmethod
    def _clause_record_source(profile):
        """True when the profile's selected rows come from clause extraction.

        Clause rows are verified text spans, not table records: they have no
        header-like or filler row to drop.  Decide by the source's record-set
        type rather than by one issue code, so every problem on such a row is
        handled by correcting/re-extracting the clause record.
        """
        metadata = profile.metadata if isinstance(profile.metadata, dict) else {}
        selected = str(metadata.get('selected_record_set') or '')
        if selected.startswith('clause_records:'):
            return True
        sets = metadata.get('record_sets')
        entry = sets.get(selected) if isinstance(sets, dict) else None
        return isinstance(entry, dict) and entry.get('kind') == 'clause'

    @staticmethod
    def _suspected_irrelevant_row(profile, row):
        """True when one source record reads like the header or like filler.

        ``exclude_record`` is the audited way to drop a header row that the
        probe kept as data.  A real row with a bad value must not be offered
        that escape hatch (FDE2-06), so only records whose values are the
        column names themselves, or entirely blank, qualify.
        """
        if not isinstance(row, int) or isinstance(row, bool) \
                or not 0 <= row < len(profile.records):
            return False
        record = profile.records[row]
        if not isinstance(record, dict):
            return True
        fields = {str(name).strip().casefold() for name in profile.fields or []}
        values = [str(value).strip().casefold() for value in record.values()
                  if value not in (None, '')]
        if not values:
            return True
        return len(values) > 1 and all(value in fields for value in values)

    def disposition_options(self, session, body=None):
        """Audited actions that can clear a blocking source issue.

        The save rejection and the preview expose the same options so the web
        page or the agent can offer a concrete next step instead of only saying
        that the preview still has issues.
        """
        options = []
        done = {(entry.get('source_id'), entry.get('action'),
                 entry.get('partition'), entry.get('record'))
                for entry in self.disposition_entries(session)}
        names = {key: value['source_name'] for key, value in
                 self._source_descriptors(session).items()}
        for profile in self._profiles(session):
            for gap in profile.gaps:
                if gap.code == 'key_missing':
                    continue
                key = (profile.source_id, 'partition_not_applicable', gap.partition, None)
                if key in done:
                    continue
                options.append({'action': 'partition_not_applicable',
                                'source_id': profile.source_id,
                                'source_name': names.get(profile.source_id, profile.source_id),
                                'partition': gap.partition, 'gap': gap.code,
                                'reason_hint': '确认该分区为空或不适用'})
        if body:
            profiles = {profile.source_id: profile
                        for profile in self._profiles(session)}
            ignored = self._ignored_source_ids(session)
            for issue in body.get('issues') or []:
                if issue.get('code') in {'ontology.source_unmapped',
                                         _SOURCE_CONCEPT_MISMATCH}:
                    # The source-level escape hatch: record an audited decision
                    # that this task does not use the source at all.  The wire
                    # action stays ``partition_not_applicable`` with no
                    # partition (the tool schema's literal), marked with
                    # ``scope`` so the page shows one button per source.
                    source_id = issue.get('source_id')
                    if source_id in ignored:
                        continue
                    options.append({'action': 'partition_not_applicable',
                                    'scope': 'source', 'partition': None,
                                    'source_id': source_id,
                                    'source_name': names.get(source_id, source_id),
                                    'reason_hint': '本任务不使用该来源'})
                    continue
                if issue.get('code') not in {'ontology.identity_unresolved',
                                             'ontology.required_value_missing',
                                             'ontology.conversion_failed',
                                             'record_attribution_unverified'}:
                    continue
                source_id, row = issue.get('source_id'), issue.get('row')
                if source_id is None or row is None:
                    continue
                profile = profiles.get(source_id)
                if profile is None:
                    continue
                # FDE2-06: only a row that itself reads like the header (or is
                # entirely blank) may be excluded; a real data row with a bad
                # value must be corrected or re-mapped instead.  Clause rows
                # are never exclusion candidates: a missing required value or
                # an unverified quote is a real clause record to correct or
                # re-extract, not an irrelevant table row.  Gate by the
                # source/record-set type, not by one issue code, so a failed
                # conversion and the required gap it causes cannot reopen the
                # row escape.
                if self._clause_record_source(profile):
                    continue
                if not self._suspected_irrelevant_row(profile, row):
                    continue
                key = (source_id, 'exclude_record', None, row)
                if key in done:
                    continue
                options.append({'action': 'exclude_record', 'source_id': source_id,
                                'source_name': names.get(source_id, source_id),
                                'record': row, 'reason_hint': '排除表头行或明显无关的记录'})
        unique = []
        for option in options:
            if option not in unique:
                unique.append(option)
        return unique

    def dispose(self, session_id, disposition, expected_revision, ctx):
        """Record an audited source disposition and invalidate the preview.

        ``partition_not_applicable`` acknowledges an unread/blank partition and
        ``exclude_record`` removes one source row.  A source that the task's
        mapping does not use can be dropped as a whole (``ignore_source``);
        over the wire that arrives as ``partition_not_applicable`` without a
        partition, because the tool schema's literal has no third action.  The
        disposition record is a new revision with who/when/why; the next
        proposal rebuilds a preview with the disposition applied.
        """
        if not str(getattr(disposition, 'reason', '') or '').strip():
            raise ValueError('处置原因不能为空')
        wb = self.wb
        session = wb.sessions.get(session_id, ctx)
        if session.revision != expected_revision:
            raise VersionConflict('session changed; reload before disposing')
        source = next((item for item in session.sources
                       if item.source_id == disposition.source_id), None)
        if source is None:
            raise ValueError('source is not part of this task')
        profile = next((item for item in self._profiles(session)
                        if item.source_id == disposition.source_id), None)
        if profile is None:
            raise ValueError('source has no observation in this task')
        action = disposition.action
        if action == 'exclude_record' and self._clause_record_source(profile):
            raise ValueError('条款记录不能按无关行排除；请纠正值或重新提取条款记录')
        source_level = action == 'ignore_source' or (
            action == 'partition_not_applicable' and disposition.partition is None)
        entry = {'action': 'ignore_source' if source_level else action,
                 'source_id': disposition.source_id,
                 'reason': disposition.reason}
        if source_level:
            # Ignore a source only when the preview under review does not map
            # it; an older mapping entry alone does not keep it in use.  A
            # source the active preview itself flags as not matching the
            # concept stays ignorable: the wrong mapping must not pin it into
            # the task (FDE3-04).
            active = self._preview_source_ids(session)
            used = active if active is not None else self._mapped_source_ids(session)
            if disposition.source_id in used:
                body = self._active_preview_body(session)
                flagged = body is not None and any(
                    issue.get('code') == _SOURCE_CONCEPT_MISMATCH
                    and issue.get('source_id') == disposition.source_id
                    for issue in body.get('issues') or [])
                if not flagged:
                    raise ValueError('source is used by the current mapping; '
                                     'dispose a partition or a record instead')
        elif action == 'partition_not_applicable':
            partition = disposition.partition
            observed = {gap.partition for gap in profile.gaps}
            observed.update(profile.completed_partitions)
            if partition not in observed:
                raise ValueError('partition is not part of the source observation')
            entry['partition'] = partition
        elif action == 'exclude_record':
            record = disposition.record
            if not isinstance(record, int) or isinstance(record, bool):
                raise ValueError('exclude_record needs a record index')
            if not 0 <= record < len(profile.records):
                raise ValueError('record index is outside the source observation')
            entry['record'] = record
            entry['record_values'] = dict(profile.records[record])
        else:
            raise ValueError('unknown disposition action')
        prior, prior_revision = self._disposition_row(session)
        entries = list(prior['body'].get('entries') or []) if prior is not None else []
        duplicate = [item for item in entries
                     if item.get('action') == entry['action']
                     and item.get('source_id') == entry['source_id']
                     and item.get('partition') == entry.get('partition')
                     and item.get('record') == entry.get('record')]
        if duplicate:
            raise ValueError('this disposition is already recorded')
        decision_id = uuid4().hex
        recorded_at = datetime.now(timezone.utc).isoformat()
        entry.update({'decision_ref': decision_id + '@1',
                      'subject_ref': ctx.subject_ref, 'recorded_at': recorded_at})
        entries.append(entry)
        body = {'session_id': session.id, 'entries': entries}
        revision = str(int(prior_revision) + 1) if prior_revision else '1'
        versions = dict(session.selected_versions)
        if 'preview' in versions:
            versions['corrections_from'] = versions['preview']
        versions.pop('preview', None)
        versions['dispositions'] = f'{session.id}@{revision}'
        updated = wb.sessions.update(session.id, expected_revision, {
            'phase': 'needs_input', 'selected_versions': versions,
            'issues': [], 'next_actions': ['propose_mapping'],
        }, ctx, extra_writes=[
            Write('disposition', session.id, wb.scope, body, prior_revision),
            Write('review', decision_id, wb.scope, {
                'decision': {'preview_ref': session.selected_versions.get('preview'),
                             'target_scope': 'mapping', 'decision': 'save',
                             'changes': {'disposition': entry}},
                'subject_ref': ctx.subject_ref, 'recorded_at': recorded_at}),
        ])
        return {'session_id': session.id, 'session_revision': updated.revision,
                'disposition_ref': versions['dispositions'], 'entry': entry,
                'entries': entries,
                'disposition_options': self.disposition_options(updated)}

    def _dispositions_for_preview(self, session, body=None):
        entries = self.disposition_entries(session)
        if not entries and body:
            entries = list((body.get('extensions') or {}).get(_DISPOSITIONS) or [])
        return entries

    def partial_plan(self, session, body):
        """Split a preview into saved, suspended and unidentified records.

        Only objects with no object-level blocking issue are saved.  Conflicted
        or required-value-missing objects are suspended with their reasons;
        identity-unresolved candidates are reported separately and never block
        the other objects.
        """
        _, _, concept = self._target(session)
        labels = self._object_labels(session, body)
        sources = self._source_descriptors(session)
        instances = {instance['id']: instance for instance in body.get('instances') or []}
        keyed, unidentified = {}, []
        for entity_id, instance in instances.items():
            values = instance.get('values') or {}
            keys = [values.get(field) for field in concept.identity_fields]
            if entity_id.startswith('candidate:') or any(value in (None, '') for value in keys):
                anchors = [anchor for field_anchors in (instance.get('source_anchors') or {}).values()
                           for anchor in field_anchors]
                source_ids = sorted({anchor.get('source_ref') for anchor in anchors
                                     if anchor.get('source_ref') is not None})
                shape = [{'source_id': source_id,
                          'source_name': sources.get(source_id, {}).get('source_name', source_id),
                          'locations': []} for source_id in source_ids]
                by_source = {item['source_id']: item for item in shape}
                for anchor in anchors:
                    source_id = anchor.get('source_ref')
                    if source_id not in by_source:
                        continue
                    location = self._selector_location(anchor.get('selector') or {})
                    if location and location not in by_source[source_id]['locations']:
                        by_source[source_id]['locations'].append(location)
                unidentified.append({
                    'entity_id': entity_id, 'object': labels.get(entity_id),
                    'sources': shape, 'values': to_jsonable_python(values),
                    'reason': _ISSUE_REASONS.get('ontology.identity_unresolved'),
                    'unresolved': list(instance.get('unresolved') or []),
                })
            else:
                keyed[entity_id] = instance
        issues_by_entity = {entity_id: [] for entity_id in keyed}
        global_issues = []
        incomplete_sources = {}
        entity_sources = {}
        for entity_id, instance in keyed.items():
            entity_sources[entity_id] = {anchor.get('source_ref')
                for field_anchors in (instance.get('source_anchors') or {}).values()
                for anchor in field_anchors if anchor.get('source_ref')}
        for issue in self._deduped_issues(body.get('issues') or []):
            code = issue.get('code')
            if code == 'ontology.identity_unresolved':
                continue
            entity_id = issue.get('entity_id')
            if entity_id in issues_by_entity:
                issues_by_entity[entity_id].append(issue)
            elif code == 'ontology.incomplete_source':
                incomplete_sources.setdefault(issue.get('source_id'), []).append(issue)
            elif code in _GLOBAL_BLOCKING_ISSUES:
                global_issues.append(issue)
            elif entity_id is not None:
                # A keyless candidate keeps its object-level issues in the
                # unidentified record, not in the saved/suspended split.
                continue
            elif issue.get('row') is not None and issue.get('source_id') is not None:
                global_issues.append(issue)
            else:
                global_issues.append(issue)
        for source_id, issues in incomplete_sources.items():
            affected = [entity_id for entity_id, source_ids in entity_sources.items()
                        if source_id in source_ids]
            for entity_id in affected:
                issues_by_entity[entity_id].extend(issues)
            if not affected:
                # No object carries an anchor from that source; the source-level
                # issue must still block a partial release.
                global_issues.extend(issues)
        for entity_id, instance in keyed.items():
            targeted = {issue.get('target') for issue in issues_by_entity[entity_id]}
            for prop in instance.get('unresolved') or []:
                if prop not in targeted:
                    issues_by_entity[entity_id].append({
                        'code': 'ontology.required_value_missing', 'target': prop,
                        'entity_id': entity_id,
                    })
        saved, suspended = [], []
        for entity_id, instance in keyed.items():
            reasons = []
            seen = set()
            for issue in issues_by_entity[entity_id]:
                key = (issue.get('code'), issue.get('target'))
                if key in seen:
                    continue
                seen.add(key)
                # User-facing reason stays Chinese; the raw parser/exception
                # text goes to its own field so a page can tuck it into a
                # collapsible detail instead of showing it inline.
                entry = {'code': issue.get('code'), 'field': issue.get('target'),
                         'reason': _ISSUE_REASONS.get(issue.get('code'))
                         or '该项未通过核对'}
                if issue.get('detail'):
                    entry['detail'] = str(issue.get('detail'))
                reasons.append(entry)
            item = {'entity_id': entity_id, 'object': labels.get(entity_id),
                    'values': to_jsonable_python(instance.get('values') or {})}
            if reasons:
                suspended.append({**item, 'reasons': reasons})
            else:
                saved.append(item)
        return {'saved': saved, 'suspended': suspended,
                'unidentified_records': unidentified,
                'blocking': [{'code': issue.get('code'), 'target': issue.get('target'),
                              'source_id': issue.get('source_id')}
                             for issue in global_issues]}

    def _store_profile(self,session,versions,source,profile,ctx):
        wb=self.wb
        key='profile:'+source.source_id
        pid=session.id+':'+source.source_id
        previous_revision=versions[key].rsplit('@',1)[1] if key in versions else None
        revision=str(int(previous_revision)+1) if previous_revision else '1'
        versions[key]=pid+'@'+revision
        versions.pop('preview',None)
        return wb.sessions.update(session.id,session.revision,{'selected_versions':versions},ctx,
            extra_writes=[Write('profile',pid,wb.scope,profile.model_dump(mode='json'),previous_revision)])

    def _failure_profile(self,source,previous,*,code,detail,retryable):
        """Persist the evidence observed so far plus an explicit failure gap."""
        code=str(code or 'probe_failed')
        detail=str(detail)[:500]
        attempts=(int(previous.metadata.get('probe_attempts',0))+1
                  if previous is not None and isinstance(previous.metadata.get('probe_attempts',0),int)
                  else 1)
        if previous is not None:
            records=list(previous.records);anchors=dict(previous.anchors)
            completed=list(previous.completed_partitions);total=previous.total_partitions
            sampled=previous.sampled;issues=list(previous.issues)
            metadata=dict(previous.metadata)
            # Keep an in-flight checkpoint: a transient failure while a
            # segment is being continued must not throw away completed rows.
            gaps=[gap for gap in previous.gaps if gap.code != code]
            if not isinstance(previous.metadata.get('resume'),dict):
                metadata.pop('resume',None)
                gaps=[gap for gap in gaps if gap.code != BUDGET_GAP]
            revision=previous.source_revision;kind=previous.kind
        else:
            records=[];anchors={};completed=[];total=None;sampled=False;issues=[]
            metadata={'structure_fingerprint':digest([self.wb.scope,source.source_id,'unprobed'])}
            gaps=[];revision='sha256:'+digest([self.wb.scope,source.source_id,'probe-failed'])
            kind=Path(source.locator_ref).suffix.lstrip('.') if source.kind=='file' else source.kind
        partition=1
        state=previous.metadata.get('resume') if previous is not None else None
        if isinstance(state,dict):
            partition=(state.get('next_row') or state.get('next_page')
                       or state.get('next_block') or state.get('next_sheet') or 1)
            if not any(gap.code==BUDGET_GAP for gap in gaps):
                gaps.append(CoverageGap(partition=partition,code=BUDGET_GAP))
        gaps.append(CoverageGap(partition=partition,code=code,detail=detail[:200]))
        metadata.update({'probe_error':{'code':code,'detail':detail,
                                         'retryable':bool(retryable)},
                         'probe_attempts':attempts,
                         'structure_fingerprint':metadata.get('structure_fingerprint')
                             or digest([self.wb.scope,source.source_id,'unprobed'])})
        fields=list(dict.fromkeys(key for row in records for key in row))
        return SourceProfile(source_id=source.source_id,source_revision=revision,kind=kind,
            records=records,fields=fields,anchors=anchors,metadata=metadata,
            total_partitions=total,completed_partitions=completed,gaps=gaps,
            sampled=sampled,issues=issues),attempts

    def advance(self,session_id,ctx):
        wb=self.wb;s=wb.sessions.get(session_id,ctx)
        if s.phase == 'saved':return s
        prior_profiles = {profile.source_id: profile for profile in self._profiles(s)}
        if is_discovery(s) and prior_profiles and s.phase != 'probing' and 'retry_probe' not in s.next_actions:
            return s
        if s.phase == 'preview' and not any(_rest_retryable(profile) or _resumable(profile) for profile in prior_profiles.values()):
            return s
        if s.phase == 'needs_input' and 'retry_probe' not in s.next_actions:
            # A completed or permanently failed observation must not be probed
            # again just because the agent asked advance once more.  A newly
            # registered verified mapping is still picked up here.
            if s.next_actions == ['repair_source']:
                return s
            if not any(_resumable(profile) for profile in prior_profiles.values()):
                profiles=list(prior_profiles.values())
                if (not is_discovery(s) and profiles and not s.issues
                        and all(profile.coverage=='full' for profile in profiles)):
                    self._reuse_verified_mapping(s,profiles,ctx)
                    # Reload even when reuse was refused: the refusal records
                    # the fields that must be extracted again.
                    return wb.sessions.get(s.id,ctx)
                return s
        client=wb.layer_client or LayerClient(installed_data_package(wb.workspace))
        versions=s.selected_versions.copy()
        job=wb.store.current('job',s.job_ref,scope=wb.scope)
        s=wb.sessions.update(s.id,s.revision,{'phase':'probing','issues':[]},ctx,
            extra_writes=[Write('job',s.job_ref,wb.scope,{**job['body'],'state':'running'},job['revision'])])
        errors=[];budget_exhausted=False;probed_any=False
        deadline=_probe_deadline(self.budget_seconds)
        for source in s.sources:
            if budget_exhausted:break
            previous = prior_profiles.get(source.source_id)
            if previous is not None and (_exhausted_failure(previous)
                    or not (_rest_retryable(previous) or _resumable(previous)
                            or _retryable_failure(previous))):
                continue
            selection = source
            if is_discovery(s):
                selection = source.model_copy(update={'options': {**source.options, 'sample_strategy': 'per_table'}})
            segments=0;last_progress=None
            while True:
                remaining=deadline-time.monotonic()
                if remaining <= _MIN_SEGMENT_SECONDS and (probed_any or segments):
                    budget_exhausted=True
                    break
                try:
                    profile=(client.probe(selection,ctx,wb.workspace,previous=previous,
                                          budget_seconds=max(remaining,0.05))
                             if previous is not None
                             else client.probe(selection,ctx,wb.workspace,
                                               budget_seconds=max(remaining,0.05)))
                except (DataLayerProbeError,ValueError,OSError,TimeoutError) as exc:
                    if isinstance(exc,DataLayerProbeError):
                        code,retryable=exc.code,bool(exc.retryable)
                    else:
                        # The data layer was never reached (for example the
                        # selected connection is not configured).  The agent
                        # can correct the selection, but only for one retry.
                        code,retryable='probe_failed',True
                    detail=str(exc)[:500]
                    profile,attempts=self._failure_profile(source,previous,
                        code=code,detail=detail,retryable=retryable)
                    errors.append({'code':'intake.probe_failed','source_id':source.source_id,
                        'target':source.source_id,'detail':detail,'error_code':str(code),
                        'attempts':attempts,'retryable':retryable})
                    s=self._store_profile(s,versions,source,profile,ctx)
                    probed_any=True
                    break
                probed_any=True
                s=self._store_profile(s,versions,source,profile,ctx)
                previous=profile
                segments+=1
                if _rest_retryable(profile) or not _resumable(profile):
                    break
                progress=_deadline_key(profile)
                if last_progress == progress:
                    errors.append({'code':'intake.probe_stalled','source_id':source.source_id,
                        'detail':'probe returned the same checkpoint without progress',
                        'retryable':False,'attempts':segments})
                    break
                last_progress=progress
                if segments >= _MAX_SEGMENTS:
                    errors.append({'code':'intake.probe_segment_limit','source_id':source.source_id,
                        'detail':'segment limit reached in one advance','retryable':False,
                        'attempts':segments})
                    break
                if time.monotonic() >= deadline:
                    budget_exhausted=True
                    break
        job=wb.store.current('job',s.job_ref,scope=wb.scope)
        profiles=self._profiles(s)
        resumable=any(_resumable(profile) for profile in profiles)
        exhausted=any(_exhausted_failure(profile) for profile in profiles)
        retryable_errors=[error for error in errors
                          if error.get('retryable') and error.get('attempts',1) < 2]
        permanent_errors=[error for error in errors if not error.get('retryable')]
        retry=(not exhausted and not permanent_errors
               and (bool(retryable_errors) or resumable or budget_exhausted
                    or not profiles
                    or any(_rest_retryable(profile) for profile in profiles)))
        if exhausted:
            next_action='select_source' if is_discovery(s) else 'repair_source'
        elif errors and not retry:
            next_action='select_source' if is_discovery(s) else 'repair_source'
        elif retry:
            next_action='retry_probe'
        elif is_discovery(s):
            next_action='propose_discovery' if profiles[0].metadata.get('tables') else 'select_source'
        else:
            next_action='propose_mapping'
        s=wb.sessions.update(s.id,s.revision,{'phase':'needs_input','issues':errors,
            'next_actions':[next_action]},ctx,
            extra_writes=[Write('job',s.job_ref,wb.scope,{**job['body'],'state':'needs_input','checkpoint':'profiles'},job['revision'])])
        if (not is_discovery(s) and profiles and not errors and not retry
                and all(profile.coverage=='full' for profile in profiles)):
            self._reuse_verified_mapping(s,profiles,ctx)
            return wb.sessions.get(s.id,ctx)
        return s

    def _fingerprints(self,profiles):
        """Order-independent fingerprint set identifying the source combination."""
        return sorted({profile.metadata['structure_fingerprint'] for profile in profiles})

    def _verified_mapping_keys(self,ontology,concept_name,profiles):
        wb=self.wb
        revision=f'{ontology.id}@{ontology.revision}'
        keys=[digest([wb.scope,self._fingerprints(profiles),revision,concept_name])]
        # Older builds cached without the concept component.
        keys.append(digest([wb.scope,self._fingerprints(profiles),revision]))
        if len(profiles)==1:
            keys.append(digest([wb.scope,profiles[0].metadata['structure_fingerprint'],revision]))
        return keys

    @staticmethod
    def _mapping_body(mapping):
        ignored={'id','revision','scope'}
        return {key:value for key,value in mapping.model_dump(mode='json').items() if key not in ignored}

    def _same_mapping(self,left,right):
        return self._mapping_body(left)==self._mapping_body(right)

    def _cached_sources(self,body):
        records=body.get('sources')
        if records is not None:
            if not isinstance(records,list):return None
            try:
                return [{'source_id':record.get('source_id'),'locator_ref':record.get('locator_ref'),
                         'kind':record.get('kind'),'mapping':MappingSpec.model_validate(record['mapping']),
                         'derived_fields':record.get('derived_fields'),
                         'clause_records':record.get('clause_records')}
                        for record in records]
            except (AttributeError,KeyError,TypeError,ValueError):return None
        mappings=body.get('mappings')
        if mappings is None and 'mapping' in body:mappings=[body['mapping']]
        if not isinstance(mappings,list):return None
        try:
            return [{'source_id':None,'locator_ref':None,'kind':None,'mapping':MappingSpec.model_validate(mapping)}
                    for mapping in mappings]
        except (TypeError,ValueError):return None

    def _group_mappings(self,profiles,records,sources):
        """Pair every source in one fingerprint group, refusing gaps or conflicts."""
        used=set()
        proposals={}
        for profile in profiles:
            selection=sources.get(profile.source_id)
            by_id=[index for index,record in enumerate(records)
                   if record['source_id'] is not None and record['source_id']==profile.source_id]
            by_locator=[]
            if selection is not None:
                by_locator=[index for index,record in enumerate(records)
                            if record['locator_ref'] is not None and record['locator_ref']==selection.locator_ref
                            and record['kind']==selection.kind]
            if len(by_id)>1 or len(by_locator)>1:return None
            if by_id:
                record=records[by_id[0]]
                if record['locator_ref'] is not None or record['kind'] is not None:
                    if (selection is None or record['locator_ref']!=selection.locator_ref
                            or record['kind']!=selection.kind):return None
            if by_id and by_locator and by_id[0]!=by_locator[0]:return None
            matches=by_id or by_locator
            if not matches or matches[0] in used:return None
            used.add(matches[0])
            proposals[profile.source_id]=records[matches[0]]['mapping']
        return proposals if len(used)==len(records) else None

    def _reuse_verified_mapping(self,session,profiles,ctx):
        # A cached mapping covers every observed source.  Reusing it after an
        # audited "this task does not use the source" decision would map the
        # removed material again behind the operator's back (FDE2-05).
        if self._ignored_source_ids(session):return False
        ontology,concept_name,_=self._target(session)
        for key in self._verified_mapping_keys(ontology,concept_name,profiles):
            cached=self.wb.store.current('verified_mapping',key,scope=self.wb.scope)
            if cached is None:continue
            session,profiles,failures=self._replay_derived_fields(session,profiles,cached,ctx)
            if failures:
                # One unresolved field is enough: reusing the mapping would
                # present a preview that silently misses that value.  Keep the
                # session in needs_input and name the fields to extract again.
                self._record_replay_failure(session,failures,ctx)
                return False
            if self._reuse_cached_mapping(session,profiles,cached,ctx):
                return True
        return False

    def _match_cached_profile(self,record,profiles,sources):
        """Find the fresh profile described by one cached source record."""
        source_id=record.get('source_id')
        locator,kind=record.get('locator_ref'),record.get('kind')
        if source_id in profiles:
            selection=sources.get(source_id)
            if locator is not None and (selection is None or selection.locator_ref!=locator
                                        or selection.kind!=kind):
                return None
            return profiles[source_id]
        matches=[profile for profile in profiles.values()
                 if sources.get(profile.source_id) is not None
                 and sources[profile.source_id].locator_ref==locator
                 and sources[profile.source_id].kind==kind]
        return matches[0] if len(matches)==1 else None

    def _replay_derived_fields(self,session,profiles,cached,ctx):
        """Restore text-extracted fields and clause records before reusing a verified mapping.

        The fingerprint deliberately ignores extracted fields.  Replaying the
        recorded exact spans keeps a reusable mapping executable instead of
        submitting bindings for fields the fresh probe has not produced.

        Returns ``(session, profiles, failures)``.  When the recorded quote of
        any field cannot be relocated in the new original, no replay is
        persisted and ``failures`` explains why reuse must be refused.
        """
        records=self._cached_sources(cached['body'])
        if not records:return session,profiles,[]
        current={profile.source_id:profile for profile in profiles}
        sources={source.source_id:source for source in session.sources}
        updates={}
        failures=[]
        for record in records:
            specs=record.get('derived_fields')
            clause=record.get('clause_records')
            if not specs and not clause:continue
            profile=self._match_cached_profile(record,current,sources)
            if profile is None:
                failures.append({'source_id':record.get('source_id'),
                                 'fields':[],
                                 'detail':'cached source no longer matches the observation'})
                continue
            if profile.source_id in updates:continue
            updated=profile
            try:
                if specs:
                    updated=replay_fields(updated,specs,
                                          identity_fields=tuple(self._target(session)[2].identity_fields))
                if clause:
                    ontology,concept_name,concept=self._target(session)
                    allowed=(None if self.wb.allowed_model_fields is None
                             else self.wb.allowed_model_fields.get(profile.source_id,[]))
                    updated,_=replay_clause_records(updated,clause,concept,
                        concept_name=concept_name,
                        ontology_revision=f'{ontology.id}@{ontology.revision}',
                        allowed_fields=allowed)
            except (ReplayError,ClauseReplayError) as exc:
                failures.append({'source_id':profile.source_id,
                                 'fields':exc.failures,
                                 'detail':str(exc),
                                 'next_action':'intake_extract_records' if clause else 'intake_extract'})
                continue
            if updated.model_dump(mode='json')!=profile.model_dump(mode='json'):
                updates[profile.source_id]=updated
        if failures:
            # Never persist a partial replay: a later successful extraction
            # must report all derived fields as freshly located.
            return session,profiles,failures
        if not updates:return session,profiles,[]
        versions=dict(session.selected_versions)
        writes=[]
        for source_id,updated in updates.items():
            ref=versions.get('profile:'+source_id)
            if ref is None:continue
            profile_id,revision=ref.rsplit('@',1)
            versions['profile:'+source_id]=f'{profile_id}@{int(revision)+1}'
            writes.append(Write('profile',profile_id,self.wb.scope,
                                updated.model_dump(mode='json'),revision))
        if not writes:return session,profiles,[]
        session=self.wb.sessions.update(session.id,session.revision,
            {'selected_versions':versions},ctx,extra_writes=writes)
        return session,self._profiles(session),[]

    def _record_replay_failure(self,session,failures,ctx):
        """Leave the task in needs_input with the reason reuse was refused.

        The issue is the stable hand-off to ``intake_extract``: after new
        quotes are extracted, that call clears the issue and the agent can
        submit a fresh proposal.
        """
        issues=[issue for issue in session.issues
                if issue.get('code')!=_REPLAY_FAILED]
        for failure in failures:
            fields=failure.get('fields') or []
            names=[str(item.get('name')) for item in fields if item.get('name')]
            detail=failure.get('detail') or 'recorded fields no longer resolve in the source'
            if names and not all(name in detail for name in names):
                detail=f'{detail}: {", ".join(names)}'
            issues.append({'code':_REPLAY_FAILED,
                           'source_id':failure.get('source_id'),
                           'target':failure.get('source_id'),
                           'detail':detail,'fields':fields,
                           'next_action':failure.get('next_action') or 'intake_extract'})
        next_action=next((failure.get('next_action') for failure in failures
                          if failure.get('next_action')),'intake_extract')
        return self.wb.sessions.update(session.id,session.revision,
            {'issues':issues,'next_actions':[next_action]},ctx)

    @staticmethod
    def _replay_failure(session):
        """The recorded reason a verified mapping was not reused, if any."""
        return next((issue for issue in session.issues
                     if issue.get('code')==_REPLAY_FAILED),None)

    def _reuse_cached_mapping(self,session,profiles,cached,ctx):
        records=self._cached_sources(cached['body'])
        if not records or len(records)!=len(profiles):return False
        groups={}
        for record in records:groups.setdefault(record['mapping'].source_fingerprint,[]).append(record)
        if sorted(groups)!=self._fingerprints(profiles):return False
        sources={source.source_id:source for source in session.sources}
        proposals={}
        for fingerprint,group in groups.items():
            current=[profile for profile in profiles
                     if profile.metadata['structure_fingerprint']==fingerprint]
            if len(current)!=len(group):return False
            if len(group)==1:
                proposals[current[0].source_id]=group[0]['mapping']
            elif all(self._same_mapping(record['mapping'],group[0]['mapping']) for record in group[1:]):
                proposals.update({profile.source_id:record['mapping']
                                  for profile,record in zip(current,group)})
            else:
                matched=self._group_mappings(current,group,sources)
                if matched is None:return False
                proposals.update(matched)
        if len(profiles)==1:
            self.submit_proposal(session.id,proposals[profiles[0].source_id],session.revision,ctx,
                                 reused=True,source_id=profiles[0].source_id)
        else:
            self.submit_source_proposals(session.id,proposals,session.revision,ctx,reused=True)
        return True

    def inference_request(self,session_id,ctx):
        s=self.wb.sessions.get(session_id,ctx)
        profiles = self._profiles(s)
        if is_discovery(s):
            request=self.wb.discovery.request(s, profiles)
            if profiles:
                request['resume']=profiles[0].metadata.get('resume')
            request['issues']=list(s.issues)
            return request
        ontology,concept_name,_=self._target(s)
        request=mapping_request(s, profiles, ontology, self.wb.allowed_model_fields, concept_name)
        # The agent needs the failure code and the continuation point on the
        # same request that tells it to retry, not only in an internal log.
        request['issues']=list(s.issues)
        request['dispositions']=self.disposition_entries(s)
        request['disposition_options']=self.disposition_options(s)
        failure=self._replay_failure(s)
        if failure is not None:
            # A mapping was not reused because the new original moved some of
            # the recorded spans.  Say so on the same payload the agent sees,
            # and point at intake_extract instead of a fresh proposal built on
            # a profile that still lacks those values.
            request['mapping_reused']=False
            request['mapping_reuse_reason']=failure.get('detail')
            request['mapping_reuse_blocked']={
                'source_id':failure.get('source_id'),
                'fields':failure.get('fields') or [],
                'next_action':failure.get('next_action') or 'intake_extract'}
        for item,profile in zip(request.get('sources',[]),profiles):
            item['completed_partitions']=profile.completed_partitions
            item['total_partitions']=profile.total_partitions
            item['resume']=profile.metadata.get('resume')
        return request

    def extract_document_fields(self, session_id, source_id, fields, expected_revision, ctx):
        wb = self.wb
        session = wb.sessions.get(session_id, ctx)
        if session.revision != expected_revision:
            raise VersionConflict('session changed; reload source excerpts')
        key = 'profile:' + source_id
        ref = session.selected_versions.get(key)
        if ref is None:
            raise ValueError('source has no observation in this task')
        profile_id, revision = ref.rsplit('@', 1)
        record = wb.store.get('profile', profile_id, revision, scope=wb.scope)
        profile = SourceProfile.model_validate(record['body'])
        allowed = None if wb.allowed_model_fields is None else wb.allowed_model_fields.get(source_id, [])
        _, _, concept = self._target(session)
        updated = extract_fields(profile, fields, allowed, remember=True,
                                 identity_fields=tuple(concept.identity_fields))
        versions = dict(session.selected_versions)
        if 'preview' in versions:
            # Re-proposing after extraction must still find the web corrections
            # that were applied to the preview being replaced.
            versions['corrections_from'] = versions['preview']
        versions.pop('preview', None)
        versions[key] = f'{profile_id}@{int(revision) + 1}'
        wb.sessions.update(session_id, expected_revision, {
            'phase': 'needs_input', 'selected_versions': versions,
            'issues': [], 'next_actions': ['propose_mapping'],
        }, ctx, extra_writes=[
            Write('profile', profile_id, wb.scope, updated.model_dump(mode='json'), revision),
        ])
        return self.inference_request(session_id, ctx)

    def extract_clause_records(self, session_id, source_id, records, expected_revision, ctx):
        """Turn disclosed clause text into anchored records for the pinned concept.

        The agent submits one record per rule instance read from the clause
        candidates; the service re-verifies every quote against the observed
        paragraph or page text, keeps missing required attributes as explicit
        gaps and installs the records as the source's
        ``clause_records:<concept>`` record set so a normal mapping proposal
        can bind them.
        """
        wb = self.wb
        session = wb.sessions.get(session_id, ctx)
        if is_discovery(session):
            raise ValueError('clause records need a mapping intake with a pinned target concept')
        if session.revision != expected_revision:
            raise VersionConflict('session changed; reload clause candidates')
        key = 'profile:' + source_id
        ref = session.selected_versions.get(key)
        if ref is None:
            raise ValueError('source has no observation in this task')
        profile_id, revision = ref.rsplit('@', 1)
        record = wb.store.get('profile', profile_id, revision, scope=wb.scope)
        profile = SourceProfile.model_validate(record['body'])
        allowed = None if wb.allowed_model_fields is None else wb.allowed_model_fields.get(source_id, [])
        ontology, concept_name, concept = self._target(session)
        updated, summary = build_clause_records(
            profile, records, concept, concept_name=concept_name,
            ontology_revision=f'{ontology.id}@{ontology.revision}', allowed_fields=allowed)
        versions = dict(session.selected_versions)
        if 'preview' in versions:
            versions['corrections_from'] = versions['preview']
        versions.pop('preview', None)
        versions[key] = f'{profile_id}@{int(revision) + 1}'
        wb.sessions.update(session_id, expected_revision, {
            'phase': 'needs_input', 'selected_versions': versions,
            'issues': [], 'next_actions': ['propose_mapping'],
        }, ctx, extra_writes=[
            Write('profile', profile_id, wb.scope, updated.model_dump(mode='json'), revision),
        ])
        request = self.inference_request(session_id, ctx)
        request['clause_records'] = summary
        return request

    def _prior_preview(self, session):
        """Load the newest preview that still carries web corrections or pending ones."""
        for key in ('preview', 'corrections_from'):
            ref = session.selected_versions.get(key)
            if not ref:
                continue
            try:
                preview_id, revision = ref.rsplit('@', 1)
            except ValueError:
                continue
            row = self.wb.store.get('preview', preview_id, revision, scope=self.wb.scope)
            if row is None:
                continue
            body = row['body']
            pending = (body.get('extensions') or {}).get(_PENDING_CORRECTIONS)
            if body.get('corrections') or pending:
                return ref, body
        return None, None

    def _object_label(self, instance, names, identity_fields):
        values = instance.get('values') or {}
        keys = [str(values[field]) for field in identity_fields
                if values.get(field) not in (None, '')]
        if keys:
            return ' · '.join(keys)
        for anchors in (instance.get('source_anchors') or {}).values():
            for anchor in anchors or []:
                selector = anchor.get('selector') or {}
                source_id = anchor.get('source_ref')
                display = names.get(source_id, source_id or '来源')
                where = []
                if selector.get('page') is not None:
                    where.append(f'第 {selector["page"]} 页')
                row_keys = selector.get('keys')
                if isinstance(row_keys, dict) and row_keys.get('row') is not None:
                    where.append(f'第 {row_keys["row"]} 行')
                elif selector.get('range'):
                    where.append(str(selector['range']))
                suffix = ' ' + ' '.join(where) if where else ''
                return f'未识别单据（{display}{suffix}）'
        return '未识别单据'

    def _object_labels(self, session, body):
        names = {source.source_id: str(source.options.get('display_name') or source.locator_ref)
                 for source in session.sources}
        identity_fields = self._target(session)[2].identity_fields
        return {instance['id']: self._object_label(instance, names, identity_fields)
                for instance in body.get('instances', []) if instance.get('id')}

    def issue_summary(self, session, body):
        """Name the affected object and the reason for every preview issue."""
        labels = self._object_labels(session, body)
        names = {source.source_id: str(source.options.get('display_name') or source.locator_ref)
                 for source in session.sources}
        conflicts = {(item['entity_id'], item['field']): item
                     for item in self.conflict_details(session, body)}
        actions = self.disposition_options(session, body)
        summary = []
        # One entry per row and root cause: a failed conversion already
        # explains the required value missing on the same row and column.
        for issue in self._deduped_issues(body.get('issues') or []):
            code = str(issue.get('code') or '')
            label = issue.get('object') or labels.get(issue.get('entity_id'))
            if (issue.get('row') is not None
                    and str(issue.get('entity_id') or '').startswith('candidate:')):
                label = f'第 {int(issue["row"]) + 1} 行'
            if label is None and issue.get('source_id') is not None:
                source_id = issue['source_id']
                label = '来源 ' + names.get(source_id, source_id)
            if label is None and issue.get('row') is not None:
                label = f'第 {int(issue["row"]) + 1} 行'
            # The list always shows a Chinese reason.  Raw parser/exception
            # text is often a Python exception or an invalid source value; it
            # stays in the expandable detail instead of becoming the reason.
            reason = _ISSUE_REASONS.get(code) or '该项未通过核对'
            item = {'code': code, 'target': issue.get('target'),
                    'object': label or '全部对象',
                    'reason': reason}
            if issue.get('detail') and str(issue['detail']) != reason:
                item['detail'] = str(issue['detail'])
            for key in ('entity_id', 'row', 'source_id'):
                if key in issue:
                    item[key] = issue[key]
            conflict = conflicts.get((issue.get('entity_id'), issue.get('target')))
            if conflict is not None:
                item['values'] = conflict['values']
            if code == 'ontology.incomplete_source':
                item['actions'] = [option for option in actions
                                   if option['action'] == 'partition_not_applicable'
                                   and option['source_id'] == issue.get('source_id')]
            elif code in {'ontology.source_unmapped', _SOURCE_CONCEPT_MISMATCH}:
                item['actions'] = [option for option in actions
                                   if option.get('scope') == 'source'
                                   and option['source_id'] == issue.get('source_id')]
            elif code in {'ontology.identity_unresolved',
                          'ontology.required_value_missing',
                          'ontology.conversion_failed'}:
                item['actions'] = [option for option in actions
                                   if option['action'] == 'exclude_record'
                                   and option.get('source_id') == issue.get('source_id')
                                   and option.get('record') == issue.get('row')]
            summary.append(item)
        return summary

    def _refresh_preview(self, body, concept):
        fields = MappingPreview.model_fields
        data = {key: value for key, value in body.items() if key in fields}
        # The stored body is JSON; restore typed business values on a copy so
        # callers see the same decimals/integers the first materialization
        # produced without changing what is persisted.
        instances = []
        for instance in data.get('instances', []):
            instance = dict(instance)
            values = dict(instance.get('values') or {})
            for prop, definition in concept.properties.items():
                if values.get(prop) is None:
                    continue
                try:
                    values[prop] = _typed(values[prop], definition.value_type)
                except (ValueError, ArithmeticError):
                    pass
            instance['values'] = values
            instances.append(instance)
        if instances:
            data['instances'] = instances
        return MappingPreview.model_validate(data)

    def _carry_corrections(self, session, body):
        """Re-apply web corrections to a freshly prepared preview.

        Valid corrections stay in the new preview with their manual evidence.
        A correction that can no longer be applied is reported as an explicit
        issue instead of being dropped silently.
        """
        prior_ref, prior = self._prior_preview(session)
        if prior is None:
            return prior_ref, [], [], []
        # A legacy preview may reference a prior preview through
        # corrections_from instead of carrying pending conflicts itself.
        bodies = []
        extra_ref = session.selected_versions.get('corrections_from')
        if extra_ref and extra_ref != prior_ref:
            try:
                preview_id, revision = extra_ref.rsplit('@', 1)
            except ValueError:
                pass
            else:
                row = self.wb.store.get('preview', preview_id, revision, scope=self.wb.scope)
                if row is not None:
                    bodies.append(row['body'])
        bodies.append(prior)
        # Pending conflicts must survive every subsequent proposal until they
        # are applied or explicitly replaced.  Aggregate by decision_ref so a
        # partially applied batch cannot hide the rest on the next round.
        collected = {}
        prior_labels = {}
        for source in bodies:
            prior_labels.update(self._object_labels(session, source))
            for correction in (*((source.get('extensions') or {}).get(_PENDING_CORRECTIONS) or []),
                               *(source.get('corrections') or [])):
                key = correction.get('decision_ref') or digest(correction)
                collected[key] = correction
        applied, conflicts, unresolved = self._apply_corrections(
            session, body, list(collected.values()), prior_labels)
        return prior_ref, applied, conflicts, unresolved

    def _apply_corrections(self, session, body, corrections, prior_labels):
        """Apply retained/inherited corrections and rebuild the affected preview evidence."""
        _, _, concept = self._target(session)
        mapping = body.get('mapping') or {}
        instances = {instance['id']: instance for instance in body.get('instances', [])}
        applied, conflicts, unresolved = [], [], []
        for correction in corrections:
            label_hint = correction.get('object_label')
            correction = {key: value for key, value in correction.items()
                          if key != 'object_label'}
            entity_id = correction.get('entity_id')
            prop = correction.get('property')
            definition = concept.properties.get(prop) if isinstance(prop, str) else None
            target = instances.get(entity_id)
            label = (prior_labels.get(entity_id) or label_hint
                     or entity_id or '未知对象')
            if target is None:
                conflicts.append((label, prop, '纠正对象在新预览中不存在', entity_id))
                unresolved.append({**correction, 'object_label': label})
                continue
            if definition is None:
                conflicts.append((label, prop, '目标属性不在当前本体中', entity_id))
                unresolved.append({**correction, 'object_label': label})
                continue
            if prop in concept.identity_fields:
                conflicts.append((label, prop, '身份字段纠正会改变对象标识，需要在网页重新核对', entity_id))
                unresolved.append({**correction, 'object_label': label})
                continue
            try:
                value = _typed(correction.get('value'), definition.value_type)
            except (ValueError, ArithmeticError):
                conflicts.append((label, prop, '纠正值无法按目标类型解析', entity_id))
                unresolved.append({**correction, 'object_label': label})
                continue
            if value is None:
                conflicts.append((label, prop, '纠正值不能为空', entity_id))
                unresolved.append({**correction, 'object_label': label})
                continue
            target.setdefault('values', {})[prop] = to_jsonable_python(value)
            target['unresolved'] = [item for item in target.get('unresolved', []) if item != prop]
            evidence = SourceAnchor(
                source_ref=str(correction.get('decision_ref') or 'correction').rsplit('@', 1)[0] or 'correction',
                source_revision='1', selector={'kind': 'json_pointer',
                                               'pointer': '/decision/changes/value'},
            )
            anchors = target.setdefault('source_anchors', {}).setdefault(prop, [])
            evidence_body = evidence.model_dump(mode='json')
            if evidence_body not in anchors:
                anchors.append(evidence_body)
            applied.append((correction, target, prop, value, evidence))
        if applied:
            touched = {(correction.get('entity_id'), correction.get('property'))
                       for correction, _, _, _, _ in applied}
            selected = [fact for fact in body.get('facts', [])
                        if not (fact.get('relation') in concept.properties
                                and any((role.get('value'), fact.get('relation')) in touched
                                        for role in fact.get('role_bindings', [])
                                        if role.get('role') == 'subject'))]
            bindings = mapping.get('bindings') or {}
            relation_bindings = mapping.get('relation_bindings') or {}
            for correction, target, prop, value, evidence in applied:
                entity_id = target['id']
                roles = [RoleBinding(role='subject', value=entity_id, value_type='reference'),
                         RoleBinding(role='value', value=value,
                                     value_type=concept.properties[prop].value_type)]
                relations = [(prop, roles)]
                binding = bindings.get(prop)
                for fact in list(selected):
                    role_map = relation_bindings.get(fact['relation'], {})
                    changed = [role for role, item in role_map.items()
                               if binding is not None and item == binding]
                    refers = any(role.get('value_type') == 'reference'
                                 and role.get('value') == entity_id
                                 for role in fact.get('role_bindings', []))
                    if changed and refers:
                        roles = [RoleBinding.model_validate({**role, 'value': value}
                                                            if role['role'] in changed else role)
                                 for role in fact['role_bindings']]
                        relations.append((fact['relation'], roles))
                        selected.remove(fact)
                decision_ref = str(correction.get('decision_ref') or f'correction:{prop}@1')
                for relation, relation_roles in relations:
                    fact_id = relation_key(self.wb.scope, relation, relation_roles)
                    assertion_id = 'assertion:' + digest([fact_id, decision_ref])
                    assertion = Assertion(
                        id=assertion_id, scope=self.wb.scope,
                        ontology_revision=body['ontology_revision'], relation=relation,
                        role_bindings=relation_roles, source_anchors=[evidence],
                        mapping_revision=f'{mapping["id"]}@{mapping["revision"]}',
                        extractor_version='user_correction',
                        extensions={'review.decision': decision_ref},
                    )
                    if not any(item.get('id') == assertion_id
                               for item in body.setdefault('assertions', [])):
                        body['assertions'].append(assertion.model_dump(mode='json'))
                    selected = [fact for fact in selected if fact['id'] != fact_id]
                    selected.append({'id': fact_id, 'relation': relation,
                                     'role_bindings': [role.model_dump(mode='json')
                                                       for role in relation_roles],
                                     'assertion_refs': [assertion_id]})
            body['facts'] = selected
            body['corrections'] = [correction for correction, _, _, _, _ in applied]
            corrected = {(correction.get('entity_id'), correction.get('property'))
                         for correction, _, _, _, _ in applied}
            still_unresolved = {prop for instance in body.get('instances', [])
                                for prop in instance.get('unresolved', [])}
            def replaced(issue):
                key = (issue.get('entity_id'), issue.get('target'))
                if issue.get('entity_id') is not None:
                    return key in corrected
                return issue.get('target') not in still_unresolved
            body['issues'] = [issue for issue in body.get('issues', [])
                              if not (issue.get('code') in _RESOLVABLE_ISSUES
                                      and replaced(issue))]
        for label, prop, reason, entity_id in conflicts:
            issue = {'code': 'ontology.correction_conflict',
                     'target': prop or 'unknown', 'object': label, 'detail': reason}
            if entity_id is not None:
                issue['entity_id'] = entity_id
            body.setdefault('issues', []).append(issue)
        extensions = dict(body.get('extensions') or {})
        if unresolved:
            extensions[_PENDING_CORRECTIONS] = unresolved
        else:
            extensions.pop(_PENDING_CORRECTIONS, None)
        if extensions:
            body['extensions'] = extensions
        else:
            body.pop('extensions', None)
        if applied or conflicts:
            content = {key: body[key] for key in
                       ('ontology_revision', 'mapping', 'source_revisions', 'instances', 'issues')}
            if body.get('extensions'):
                content['extensions'] = body['extensions']
            body['digest'] = digest(content)
        return applied, conflicts, unresolved

    def _inheritable_corrections(self, session, body):
        """Corrections from older tasks over the exact same source revisions.

        A correction is inheritable only when its origin preview was built from
        the same ``source_id -> source_revision`` mapping and the original
        object evidence still resolves in the current preview.  Superseded or
        adoption-only entries are not offered.
        """
        if not body:
            return []
        current_ref = session.selected_versions.get('preview')
        current_sources = body.get('source_revisions') or {}
        current_instances = {instance['id']: instance
                             for instance in body.get('instances') or []}
        current_keys = {(correction.get('entity_id'), correction.get('property'))
                        for correction in (*((body.get('extensions') or {}).get(_PENDING_CORRECTIONS) or []),
                                           *(body.get('corrections') or []))}
        _, _, concept = self._target(session)

        def anchor_keys(instance, source_ids, prop=None):
            anchors = instance.get('source_anchors') or {}
            groups = [anchors.get(prop) or []] if prop is not None else list(anchors.values())
            keys = set()
            for group in groups:
                for anchor in group:
                    if not isinstance(anchor, dict) or anchor.get('source_ref') not in source_ids:
                        continue
                    keys.add((anchor.get('source_ref'), anchor.get('source_revision'),
                              json.dumps(anchor.get('selector'), sort_keys=True, default=str)))
            return keys

        found = {}
        cursor = 0
        while True:
            rows = self.wb.store.query('preview', self.wb.scope, cursor=cursor, limit=500)
            for row in rows:
                old_ref = f"{row['id']}@{row['revision']}"
                if old_ref == current_ref:
                    continue
                old = row['body']
                old_sources = old.get('source_revisions') or {}
                # Source identity matters as much as the revision value: two
                # different sources can share a revision digest, and dropping
                # one of them must invalidate an inherited correction.
                if not old_sources or old_sources != current_sources:
                    continue
                if old.get('ontology_revision') != body.get('ontology_revision'):
                    continue
                old_instances = {instance['id']: instance
                                 for instance in old.get('instances') or []}
                latest = {}
                for correction in (*((old.get('extensions') or {}).get(_PENDING_CORRECTIONS) or []),
                                   *(old.get('corrections') or [])):
                    if correction.get('entity_id') is not None and correction.get('property') is not None:
                        latest[(correction['entity_id'], correction['property'])] = correction
                for (entity_id, prop), correction in latest.items():
                    if (entity_id, prop) in current_keys:
                        continue
                    if entity_id not in current_instances:
                        continue
                    if prop not in concept.properties or prop in concept.identity_fields:
                        continue
                    if str(correction.get('reason') or '').startswith('撤销纠正'):
                        continue
                    try:
                        value = _typed(correction.get('value'),
                                       concept.properties[prop].value_type)
                    except (ValueError, ArithmeticError):
                        continue
                    if value is None:
                        continue
                    instance = old_instances.get(entity_id)
                    current_instance = current_instances.get(entity_id)
                    if instance is None or current_instance is None:
                        continue
                    old_evidence = anchor_keys(instance, set(old_sources), prop)
                    current_evidence = anchor_keys(current_instance, set(current_sources), prop)
                    if old_evidence:
                        if not old_evidence <= current_evidence:
                            continue
                    else:
                        # Missing-value corrections are anchored by the
                        # object's identity evidence rather than the property.
                        old_evidence = anchor_keys(instance, set(old_sources))
                        current_evidence = anchor_keys(current_instance, set(current_sources))
                        if not old_evidence or not old_evidence <= current_evidence:
                            continue
                    values = instance.get('values') or {}
                    label = ' · '.join(str(values[field]) for field in concept.identity_fields
                                       if values.get(field) not in (None, ''))
                    found[(entity_id, prop)] = {
                        'decision_ref': correction.get('decision_ref'),
                        'preview_ref': old_ref,
                        'entity_id': entity_id,
                        'object': label or entity_id,
                        'property': prop,
                        'value': to_jsonable_python(value),
                        'reason': correction.get('reason'),
                        'source_revisions': old_sources,
                    }
            if len(rows) < 500:
                break
            cursor += 500
        return sorted(found.values(), key=lambda item: (str(item['object']), item['property']))

    def inheritance_hint(self, session, body):
        corrections = self._inheritable_corrections(session, body)
        if not corrections:
            return None
        return {'count': len(corrections),
                'message': f'旧任务有 {len(corrections)} 处纠正，可继承',
                'operations': ['intake_inherit'],
                'corrections': corrections}

    def inherit_corrections(self, session_id, expected_revision, decision_refs, ctx):
        wb = self.wb
        session = wb.sessions.get(session_id, ctx)
        if session.revision != expected_revision:
            raise VersionConflict('session changed; reload before inheriting corrections')
        ref = session.selected_versions.get('preview')
        if not ref:
            raise ValueError('generate a preview before inheriting corrections')
        preview_id, revision = ref.rsplit('@', 1)
        row = wb.store.get('preview', preview_id, revision, scope=wb.scope)
        if row is None:
            raise ValueError('selected preview is missing')
        body = row['body']
        candidates = self._inheritable_corrections(session, body)
        if decision_refs:
            by_ref = {item['decision_ref']: item for item in candidates}
            missing = [ref for ref in decision_refs if ref not in by_ref]
            if missing:
                raise ValueError('correction is not inheritable: ' + ', '.join(missing))
            selected = [by_ref[ref] for ref in decision_refs]
        else:
            selected = candidates
        if not selected:
            return {'session_id': session.id, 'session_revision': session.revision,
                    'preview_ref': ref, 'inherited_count': 0, 'inherited': [],
                    'inheritance': None}
        corpus = {}
        for correction in (*((body.get('extensions') or {}).get(_PENDING_CORRECTIONS) or []),
                           *(body.get('corrections') or [])):
            key = (correction.get('entity_id'), correction.get('property'))
            if correction.get('decision_ref'):
                corpus[key] = correction
        prior_labels = {item['entity_id']: item['object'] for item in candidates}
        for item in selected:
            correction = {key: value for key, value in item.items()
                          if key in {'decision_ref', 'entity_id', 'property', 'value', 'reason'}}
            correction['inherited_from'] = {'preview_ref': item['preview_ref'],
                                            'source_revisions': item['source_revisions']}
            corpus[(correction['entity_id'], correction['property'])] = correction
        applied, conflicts, _ = self._apply_corrections(session, body,
                                                        list(corpus.values()), prior_labels)
        if not applied:
            detail = '; '.join(reason for _, _, reason, _ in conflicts)
            raise ValueError('inherited corrections cannot be applied: ' + detail)
        body['inheritance'] = self.inheritance_hint(session, body)
        if body['inheritance'] is None:
            body.pop('inheritance', None)
        # An older stored preview may predate the deduplicated list; inheriting
        # must not write the duplicate rows back into the session count.
        body['issues'] = self._deduped_issues(body.get('issues') or [])
        body['revision'] = str(int(revision) + 1)
        decision_id = uuid4().hex
        recorded_at = datetime.now(timezone.utc).isoformat()
        review_decision = {'preview_ref': ref, 'target_scope': 'instance', 'decision': 'save',
                           'changes': {'inherited': [item['decision_ref'] for item in selected]}}
        wb.sessions.update(session.id, expected_revision, {
            'phase': 'preview', 'selected_versions': {
                **session.selected_versions, 'preview': preview_id + '@' + body['revision']},
            'issues': self._session_issues(body.get('issues') or []),
            'next_actions': ['review_mapping'],
        }, ctx, extra_writes=[
            Write('preview', preview_id, wb.scope, body, revision),
            Write('review', decision_id, wb.scope, {
                'decision': review_decision, 'subject_ref': ctx.subject_ref,
                'recorded_at': recorded_at}),
        ])
        return {'session_id': session.id,
                'session_revision': wb.sessions.get(session.id, ctx).revision,
                'preview_ref': preview_id + '@' + body['revision'],
                'inherited_count': len(applied),
                'inherited': [correction for correction, _, _, _, _ in applied],
                'inheritance': body.get('inheritance')}

    def _clause_attribution_issues(self,session,body):
        """Preview issues for clause records whose quote attribution failed.

        Extraction already verified every quote against the observed text;
        attribution (which record a quote belongs to) is softer: a record whose
        non-shared quotes fall outside its declared record_span, whose span
        overlaps another record's, or whose shared quote is not the nearest
        same-property value is listed here instead of blocking the batch.  A
        record excluded by an audited disposition is no longer listed.  When
        no preview instance is uniquely identified by the record's own spans,
        the issue carries no entity_id and blocks the whole batch: a partial
        release must not save a record whose attribution is unverified.
        """
        issues=[]
        excluded={}
        for entry in self.disposition_entries(session):
            if entry.get('action')=='exclude_record':
                excluded.setdefault(entry.get('source_id'),set()).add(entry.get('record'))
        instances=body.get('instances') or []
        for profile in self._profiles(session):
            name=profile.metadata.get('selected_record_set') or ''
            if not str(name).startswith('clause_records:'):continue
            entry=(profile.metadata.get('record_sets') or {}).get(name) or {}
            for item in entry.get('attribution_issues') or []:
                row=item.get('record')
                if not isinstance(row,int) or row in excluded.get(profile.source_id,()):
                    continue
                issue={'code':'record_attribution_unverified',
                       'target':item.get('target'),'row':row,
                       'source_id':profile.source_id,
                       'detail':item.get('reason') or _ISSUE_REASONS['record_attribution_unverified']}
                entity=self._row_instance(instances,entry,row)
                if entity is not None:issue['entity_id']=entity
                issues.append(issue)
        return issues

    @staticmethod
    def _row_instance(instances,entry,row):
        """The one preview instance this record's own anchors identify.

        A span shared by several records proves nothing about which record
        became which instance, so only spans cited by this record alone count
        here.  When no instance carries them, or more than one does, the
        caller must not guess: the issue stays without an entity_id and
        blocks the whole batch instead of suspending one object.
        """
        cited_by={}
        for key,anchors in (entry.get('anchors') or {}).items():
            row_key=key.split('.',1)[0]
            for anchor in anchors or []:
                selector=anchor.get('selector') or {}
                cited_by.setdefault((anchor.get('source_ref'),
                    json.dumps(selector,sort_keys=True,default=str)),set()).add(row_key)
        own={selector for selector,rows in cited_by.items() if rows=={str(row)}}
        if not own:return None
        matched=set()
        for instance in instances:
            anchors=[anchor for field in (instance.get('source_anchors') or {}).values()
                     for anchor in field or []]
            if any((anchor.get('source_ref'),
                json.dumps(anchor.get('selector') or {},sort_keys=True,default=str))
                in own for anchor in anchors):
                matched.add(instance.get('id'))
        return matched.pop() if len(matched)==1 else None

    def _prune_stale_source_draft(self,session,source_ids):
        """Drop draft bindings for sources the latest proposal no longer maps.

        A page that edited a source before an agent narrowed the mapping scope
        leaves that source in ``ui_draft``.  Keeping it would make the final
        save reject the preview even though the narrowed preview is clean.
        """
        wb=self.wb
        draft=wb.store.current('ui_draft',session.id,scope=wb.scope)
        if not draft:return None,None
        body=dict(draft['body'])
        source_bindings=body.get('source_bindings')
        if not isinstance(source_bindings,dict):return None,None
        kept={key:value for key,value in source_bindings.items() if key in source_ids}
        if kept==source_bindings:return None,None
        body['source_bindings']=kept
        revision=str(int(draft['revision'])+1)
        return (Write('ui_draft',session.id,wb.scope,body,draft['revision']),
                session.id+'@'+revision)

    @staticmethod
    def _proposal_source(proposal,profiles,source_id=None):
        """The single source a standalone proposal names, if it names one.

        A fingerprint alone cannot tell two materials with the same structure
        apart.  An explicit ``intake.source_id`` extension (or a source id in
        the proposal id) pins the intended source; without one the caller must
        use the per-source endpoint instead of mapping every match.
        """
        explicit=source_id or (proposal.extensions or {}).get('intake.source_id')
        if explicit is None and proposal.id in {profile.source_id for profile in profiles}:
            explicit=proposal.id
        if explicit is None:return None
        matches=[profile for profile in profiles if profile.source_id==explicit]
        if not matches:raise ValueError('proposal names a source outside this task')
        if matches[0].metadata.get('structure_fingerprint')!=proposal.source_fingerprint:
            raise ValueError('proposal source fingerprint does not match the named source')
        return matches[0]

    def submit_proposal(self,session_id,proposal,expected_revision,ctx,*,reused=False,source_id=None):
        wb=self.wb;s=wb.sessions.get(session_id,ctx)
        if is_discovery(s):
            raise ValueError('use ontology_discovery_propose for this intake')
        if s.revision!=expected_revision:raise VersionConflict('session changed; reload proposal inputs')
        ontology,concept_name,concept=self._target(s)
        if proposal.ontology_revision!=f'{ontology.id}@{ontology.revision}':raise ValueError('target ontology outside task')
        try:
            named,_=ontology.resolve_concept(proposal.concept)
        except KeyError as exc:raise ValueError(f'unknown concept in ontology {ontology.id}: {proposal.concept}')from exc
        if named!=concept_name:raise ValueError('target concept outside task')
        profiles=self._profiles(s)
        ignored=self._ignored_source_ids(s)
        named_source=self._proposal_source(proposal,profiles,source_id)
        if named_source is not None:
            if named_source.source_id in ignored:
                raise ValueError('source is disposed as not used')
            observations=[named_source]
        else:
            matches=[profile for profile in profiles
                     if profile.metadata['structure_fingerprint']==proposal.source_fingerprint]
            if not matches:raise ValueError('proposal does not match a selected source')
            # A disposed source cannot be materialized again, but it must not
            # turn an otherwise unambiguous active source into an ambiguity.
            observations=[profile for profile in matches if profile.source_id not in ignored]
            if not observations:raise ValueError('source is disposed as not used')
            if len(observations)>1:
                raise ValueError('proposal matches multiple sources; name one with extensions.intake.source_id')
        mid=s.id+':mapping'
        prior=wb.store.current('mapping',mid,scope=wb.scope)
        revision=str(int(prior['revision'])+1) if prior else '1'
        proposal=proposal.model_copy(update={'id':mid,'revision':revision,'scope':wb.scope})
        # FDE3-04: a source that clearly cannot carry the task's concept (no
        # identity column, most required properties unbindable) is held out of
        # the preview instead of flooding it with unidentified objects and
        # per-row missing values; it keeps one source-level issue and the
        # audited "this task does not use the source" way out.
        covering={observation.source_id:proposal for observation in observations}
        observations=[observation for observation in observations
            if self._source_matches_concept(concept,observation,proposal.bindings)]
        preview,body=wb.ontology.prepare_preview(proposal,observations,ctx,
            dispositions=self.disposition_entries(s))
        # Keep the per-row, same-row deduplicated list on the preview so every
        # row stays locatable; the session stores the same problems collapsed
        # to root causes so intake_status counts a column defect once (FDE2-06).
        body['issues']=self._deduped_issues([*(body.get('issues') or []),
            *self._source_scope_issues(
                s,{observation.source_id for observation in observations},covering),
            *self._clause_attribution_issues(s,body)])
        body['mapping_reused']=reused
        prior_ref,_,conflicts,pending=self._carry_corrections(s,body)
        hint=self.inheritance_hint(s,body)
        if hint:body['inheritance']=hint
        else:body.pop('inheritance',None)
        preview=self._refresh_preview(body,concept)
        # One revision entry per mapped source: the durable scope the web
        # regenerates from, so an unmapped material stays unmapped instead of
        # flooding the next preview with its rows (FDE2-05). Replace the whole
        # scope (not just add): after a narrower proposal a stale key would
        # make the web re-include the source the agent just removed.
        versions={key:value for key,value in s.selected_versions.items()
                  if not key.startswith('mapping:')}
        versions.update({'preview':preview.id+'@1','mapping':mid+'@'+revision})
        for observation in observations:
            versions[f'mapping:{observation.source_id}']=mid+'@'+revision
        if prior_ref and pending:versions['corrections_from']=prior_ref
        else:versions.pop('corrections_from',None)
        draft_write,draft_ref=self._prune_stale_source_draft(
            s,{observation.source_id for observation in observations})
        if draft_ref:versions['draft']=draft_ref
        writes=[Write('preview',preview.id,wb.scope,body),
                Write('mapping',mid,wb.scope,proposal.model_dump(mode='json'),prior['revision'] if prior else None)]
        if draft_write:writes.append(draft_write)
        wb.sessions.update(s.id,s.revision,{'phase':'preview','selected_versions':versions,
            'issues':self._session_issues(preview.issues),
            'next_actions':['review_mapping']},ctx,extra_writes=writes)
        return preview

    def submit_source_proposals(self, session_id, proposals, expected_revision, ctx, *, reused=False):
        wb = self.wb
        session = wb.sessions.get(session_id, ctx)
        if is_discovery(session):
            raise ValueError('use ontology_discovery_propose for this intake')
        if session.revision != expected_revision:
            raise VersionConflict('session changed; reload proposal inputs')
        all_profiles = self._profiles(session)
        selected = {source.source_id for source in session.sources}
        # A proposal may cover a subset of the task's sources: the others keep
        # one source-level issue instead of having every row mapped (FDE2-05).
        if (not proposals or not set(proposals) <= selected
                or {profile.source_id for profile in all_profiles} != selected):
            raise ValueError('provide one mapping for each observed source')
        if self._ignored_source_ids(session) & set(proposals):
            raise ValueError('source is disposed as not used')
        observations = [profile for profile in all_profiles if profile.source_id in proposals]
        ontology, concept_name, concept = self._target(session)
        # FDE3-04: proposals covering a source that clearly cannot carry the
        # task's concept are held out of the preview (one source-level issue
        # instead of every row becoming an unidentified object).  Their mapping
        # rows are still written for audit, but they pin no ``mapping:`` scope
        # so the web rebuild cannot quietly map the material again.
        mismatched = {profile.source_id for profile in observations
                      if not self._source_matches_concept(
                          concept, profile, proposals[profile.source_id].bindings)}
        materialized = [profile for profile in observations
                        if profile.source_id not in mismatched]
        if {proposal.ontology_revision for proposal in proposals.values()} != {f'{ontology.id}@{ontology.revision}'}:
            raise ValueError('target ontology outside task')
        for proposal in proposals.values():
            try:
                named, _ = ontology.resolve_concept(proposal.concept)
            except KeyError as exc:
                raise ValueError(f'unknown concept in ontology {ontology.id}: {proposal.concept}') from exc
            if named != concept_name:
                raise ValueError('target concept outside task')
        if len({proposal.identity_strategy for proposal in proposals.values()}) != 1:
            raise ValueError('all mappings must use the same identity strategy')
        # The submitted proposals are the task's current mapping scope. Drop
        # keys from earlier, wider proposals so the web cannot rebuild a
        # preview that silently maps a source the agent left out.
        versions = {key:value for key,value in session.selected_versions.items()
                    if not key.startswith('mapping:')}
        writes = []
        mappings = {}
        for index, profile in enumerate(all_profiles):
            key = profile.source_id
            if key not in proposals:
                continue
            mapping_id = f'{session.id}:source-mapping:{index}'
            current = wb.store.current('mapping', mapping_id, scope=wb.scope)
            revision = str(int(current['revision']) + 1) if current else '1'
            mapping = proposals[key].model_copy(update={'id': mapping_id, 'revision': revision, 'scope': wb.scope})
            mappings[key] = mapping
            if key not in mismatched:
                versions['mapping:'+key] = f'{mapping_id}@{revision}'
            writes.append(Write('mapping', mapping_id, wb.scope, mapping.model_dump(mode='json'),
                                current['revision'] if current else None))
        # The preview's own mapping record must name a source actually
        # materialised; a mismatched first proposal only supplies the shared
        # concept/revision fields when every source is held out.
        primary = next((mappings[key] for key in mappings if key not in mismatched), None)
        if primary is None:
            primary = next(iter(mappings.values()))
        preview, body = wb.ontology.prepare_preview(
            primary, materialized, ctx,
            source_mappings={key: value for key, value in mappings.items()
                              if key not in mismatched},
            dispositions=self.disposition_entries(session))
        # Same outward list as the session/status path: one issue per row and
        # root cause, so every count reports the same number (FDE2-06).
        body['issues'] = self._deduped_issues([
            *(body.get('issues') or []),
            *self._source_scope_issues(session, {profile.source_id for profile
                                                  in materialized}, proposals),
            *self._clause_attribution_issues(session, body)])
        body['mapping_reused'] = reused
        prior_ref,_,conflicts,pending=self._carry_corrections(session,body)
        hint=self.inheritance_hint(session,body)
        if hint:body['inheritance']=hint
        else:body.pop('inheritance',None)
        preview=self._refresh_preview(body, concept)
        versions.update(preview=preview.id+'@1', mapping=f'{primary.id}@{primary.revision}')
        if prior_ref and pending:versions['corrections_from']=prior_ref
        else:versions.pop('corrections_from',None)
        draft_write,draft_ref=self._prune_stale_source_draft(
            session,{profile.source_id for profile in materialized})
        if draft_ref:versions['draft']=draft_ref
        if draft_write:writes.append(draft_write)
        wb.sessions.update(session_id, expected_revision, {
            'phase': 'preview', 'selected_versions': versions,
            'issues': self._session_issues(preview.issues),
            'next_actions': ['review_mapping'],
        }, ctx, extra_writes=[*writes, Write('preview', preview.id, wb.scope, body)])
        return preview

    def apply(self,session_id,decision,expected_revision,ctx,*,allow_partial=False,reason=''):
        wb=self.wb;s=wb.sessions.get(session_id,ctx)
        if s.revision!=expected_revision or s.selected_versions.get('preview')!=decision.preview_ref:
            raise VersionConflict('decision does not target the active task preview')
        id,rev=decision.preview_ref.rsplit('@',1)
        active=wb.store.get('preview',id,rev,scope=wb.scope)
        draft=wb.store.current('ui_draft',s.id,scope=wb.scope)
        if decision.target_scope=='mapping' and decision.decision=='save' and draft and active:
            from dataagent_contracts.ontology import FieldBinding
            def normalize(bindings):
                return {k:FieldBinding.model_validate(v).model_dump(mode='json',exclude_defaults=True,exclude_none=True) for k,v in bindings.items()}
            current=active['body']
            source_mappings=(current.get('extensions') or {}).get('intake.source_mappings', {})
            # The latest proposal owns the source scope.  A draft binding for
            # a source outside it is stale (the narrowing proposal prunes it,
            # but an older page can still race a write) and must not block the
            # clean preview from being saved.
            if any(key in source_mappings
                   and normalize(bindings)!=normalize(source_mappings[key]['bindings'])
                   for key,bindings in draft['body'].get('source_bindings', {}).items()):
                raise VersionConflict('draft changed; generate a new preview before saving')
            if 'bindings' in draft['body'] and normalize(draft['body']['bindings'])!=normalize(current['mapping']['bindings']):
                raise VersionConflict('draft changed; generate a new preview before saving')
        # A whole-batch save names the affected objects instead of only saying
        # that the preview still has issues.  With allow_partial the unblocked
        # objects are released, while conflicted/required-missing objects and
        # identity-unresolved records are returned as pending lists.
        if (decision.decision=='save' and not decision.changes and active
                and active['body'].get('issues')):
            plan=self.partial_plan(s,active['body'])
            if allow_partial and plan['saved'] and not plan['blocking']:
                receipt,writes=wb.ontology.prepare_partial_save(
                    decision,rev,ctx,plan=plan,reason=reason)
                audit=(receipt.extensions or {}).get('intake.partial_save') or {}
                versions={**s.selected_versions,'preview':id+'@'+receipt.revision,
                          'release':audit.get('release_ref')}
                job=wb.store.current('job',s.job_ref,scope=wb.scope)
                writes.append(Write('job',s.job_ref,wb.scope,{**job['body'],
                    'state':'completed','checkpoint':'partial_save',
                    'result_ref':audit.get('release_ref')},job['revision']))
                wb.sessions.update(s.id,s.revision,{'phase':'saved',
                    'selected_versions':versions,'next_actions':receipt.revalidate},
                    ctx,extra_writes=writes)
                return receipt
            raise PreviewBlocked(self.issue_summary(s,active['body']))
        receipt,writes=wb.ontology.prepare_review(decision,rev,ctx)
        preview_write=next(w for w in writes if w.kind=='preview')
        body=preview_write.body
        versions={**s.selected_versions,'preview':id+'@'+receipt.revision}
        phase='preview'
        if body['review_state']=='approved':
            selected={source.source_id for source in s.sources}
            # A source an audited disposition removed from the task no longer
            # needs its own mapping; every other source still does.
            missing=selected-set(body['source_revisions'])-self._ignored_source_ids(s)
            if missing:raise ValueError('remaining sources require separate mapping')
            release,release_writes=wb.ontology.release_writes(body,id,rev,decision.preview_ref)
            writes=[w for w in writes if w.kind!='preview']+release_writes
            versions['release']=release.id+'@'+release.revision
            phase='saved'
            mapping=body['mapping']
            source_mappings=(body.get('extensions') or {}).get('intake.source_mappings') or {}
            selections={source.source_id:source for source in s.sources}
            profiles={profile.source_id:profile for profile in self._profiles(s)}
            def record(source_id,locator_ref,kind,item):
                entry={'source_id':source_id,'locator_ref':locator_ref,'kind':kind,'mapping':item}
                profile=profiles.get(source_id) if source_id else None
                if profile is not None and profile.metadata.get('derived_fields'):
                    # Keep the exact text spans so the next intake can rebuild
                    # fields that the source structure alone cannot reproduce.
                    entry['derived_fields']=profile.metadata['derived_fields']
                if profile is not None and profile.metadata.get('clause_records'):
                    # The same for clause records: the quotes and positions are
                    # what a later intake replays against a fresh observation.
                    entry['clause_records']=profile.metadata['clause_records']
                return entry
            if source_mappings:
                records=[record(source_id,selections[source_id].locator_ref,
                                selections[source_id].kind,item)
                         for source_id,item in source_mappings.items() if source_id in selections]
            else:
                # A single mapping with more sources in the task names the one
                # source it actually covered, so the cached record stays
                # matchable after a source-level disposition removed the rest.
                mapped=selected & set(body['source_revisions'])
                source=selections.get(next(iter(mapped))) if len(mapped)==1 else None
                records=[record(source.source_id if source else None,
                                source.locator_ref if source else None,
                                source.kind if source else None,mapping)]
            if len(records)==len(selected-self._ignored_source_ids(s)):
                fingerprints=sorted({record['mapping']['source_fingerprint'] for record in records})
                ontology,concept_name,_=self._target(s)
                key=digest([wb.scope,fingerprints,f'{ontology.id}@{ontology.revision}',concept_name])
                cached=wb.store.current('verified_mapping',key,scope=wb.scope)
                entry={'source_fingerprints':fingerprints,'sources':records,'release_ref':versions['release']}
                if len(records)==1:entry['mapping']=records[0]['mapping']
                writes.append(Write('verified_mapping',key,wb.scope,entry,cached['revision'] if cached else None))
            job=wb.store.current('job',s.job_ref,scope=wb.scope)
            writes.append(Write('job',s.job_ref,wb.scope,{**job['body'],'state':'completed','result_ref':versions['release']},job['revision']))
        wb.sessions.update(s.id,s.revision,{'phase':phase,'selected_versions':versions,
            'next_actions':receipt.revalidate},ctx,extra_writes=writes)
        return receipt

    def view(self,session_id,ctx):
        wb=self.wb;s=wb.sessions.get(session_id,ctx)
        body=None
        if 'preview' in s.selected_versions:
            id,rev=s.selected_versions['preview'].rsplit('@',1)
            row=wb.store.get('preview',id,rev,scope=wb.scope)
            body=row['body'] if row else None
        if body is not None:
            # The stored preview keeps the machine codes; the view adds the
            # affected object labels and reasons, and never truncates the list.
            # ``issue_count`` is the root-cause count; ``issue_item_count`` is
            # the per-row list kept for locating/correcting each affected row.
            body=dict(body)
            body['conflicts']=self.conflict_details(s,body)
            summary=self.issue_summary(s,body)
            groups,row_count=self._issue_groups(body.get('issues') or [])
            body['issues']=summary
            body['issue_count']=len(groups)
            body['issue_row_count']=row_count
            body['issue_item_count']=len(summary)
            body['object_labels']=self._object_labels(s,body)
            body['object_count']=len(body.get('instances',[]))
            body['dispositions']=self.disposition_entries(s)
            body['disposition_options']=self.disposition_options(s,body)
            hint=body.get('inheritance') or self.inheritance_hint(s,body)
            if hint:body['inheritance']=hint
            else:body.pop('inheritance',None)
        draft=self.wb.store.current('ui_draft',s.id,scope=wb.scope)
        profiles = self._profiles(s)
        failure = self._replay_failure(s)
        ontology,concept_name,_=self._target(s)
        return {'session':s.model_dump(mode='json'),'profiles':[p.model_dump(mode='json') for p in profiles],
            'discovery':wb.discovery.state(s, profiles),
            'ontology':ontology.model_dump(mode='json'),'ontology_concept':concept_name,'preview':body,
            'draft':draft['body'] if draft else {},
            # Mapping specs per source for the web's regenerate step (FDE2-05).
            'mappings':self._selected_mappings(s),
            'issue_count':body['issue_count'] if body else len(s.issues),
            'issue_row_count':(body['issue_row_count'] if body else
                self._issue_row_count(s.issues)),
            'dispositions':self.disposition_entries(s),
            'disposition_options':self.disposition_options(s,body),
            'conflicts':body.get('conflicts',[]) if body else [],
            'inheritance':body.get('inheritance') if body else None,
            'mapping_reused':bool(body and body.get('mapping_reused')) and failure is None,
            'mapping_reuse_reason':failure.get('detail') if failure else None}

    def save_draft(self,session_id,draft,expected_revision,ctx):
        wb=self.wb;s=wb.sessions.get(session_id,ctx)
        prior=wb.store.current('ui_draft',s.id,scope=wb.scope)
        revision=str(int(prior['revision'])+1) if prior else '1'
        return wb.sessions.update(s.id,expected_revision,
            {'selected_versions':{**s.selected_versions,'draft':s.id+'@'+revision}},ctx,
            extra_writes=[Write('ui_draft',s.id,wb.scope,draft,prior['revision'] if prior else None)])

    def revalidate(self,session_id,expected_revision,ctx):
        from dataagent_ontology.corrections import revalidate_corrections
        from dataagent_contracts.ontology import MappingPreview
        wb=self.wb;s=wb.sessions.get(session_id,ctx)
        if s.revision!=expected_revision:raise VersionConflict('session changed')
        id,rev=s.selected_versions['preview'].rsplit('@',1)
        row=wb.store.get('preview',id,rev,scope=wb.scope)
        if row['body']['review_state']!='needs_revalidation':raise ValueError('preview does not need correction validation')
        body=revalidate_corrections(row['body'],self._target(s)[0],wb.scope)
        # Revalidation may re-add the required gap next to the same failed
        # conversion; keep the stored preview and the session on one list.
        body['issues']=self._deduped_issues(body.get('issues') or [])
        next_rev=str(int(rev)+1);body['revision']=next_rev
        wb.sessions.update(s.id,s.revision,{'selected_versions':{**s.selected_versions,'preview':id+'@'+next_rev},
            'issues':self._session_issues(body['issues']),
            'next_actions':['review_mapping']},ctx,
            extra_writes=[Write('preview',id,wb.scope,body,rev)])
        fields=MappingPreview.model_fields
        return MappingPreview.model_validate({k:v for k,v in body.items() if k in fields})
