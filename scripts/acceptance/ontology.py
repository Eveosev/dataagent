"""D7 phase: ontology discovery end to end, scored against a private gold set.

The phase runs on the same freshly installed workbench as the discovery phase:
the agent side goes through the installed MCP tools, the human side through the
installed loopback HTTP service and its local token.  Samples and the gold file
live under ``D7_GOLD_DIR`` (``samples/*`` plus ``gold.json``); they are copied
into the throw-away project under neutral names and never enter this checkout.
The scripted proposal reads only the observed catalog and the source bytes;
``gold.json`` is opened after the run, for scoring only.

Every check is reported by id with a pass/fail reason and the gold entry it
scores.  Reasons stay aggregate: no sample values, file names or business
terms are copied into the report.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import select
import shutil
import subprocess
import urllib.error
import urllib.request
import zipfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from xml.etree import ElementTree

from .common import call_workbench


GOLD_ENV = 'D7_GOLD_DIR'
W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
S = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
PKG = 'http://schemas.openxmlformats.org/package/2006/relationships'

# The ids every run must report.  A required check that does not pass makes the
# phase fail; --report-only still writes the report and exits zero for product
# failures.  Environment errors are separate (see SetupError).
CHECKS = [
    ('CHAIN.discovery', True, ['D7 §3']),
    ('CHAIN.review', True, ['D1']),
    ('CHAIN.publish', True, ['D1']),
    ('CHAIN.mapping', True, ['D4', 'C1', 'C2']),
    ('CHAIN.query', True, ['D4']),
    ('C1', True, ['C1']),
    ('C1.identity', True, ['C1', 'J1']),
    ('C1.properties', True, ['C1']),
    ('C1.types', True, ['C1']),
    ('C1.unit', True, ['C1', 'J2']),
    ('C1.forbidden', True, ['C1']),
    ('C2', True, ['C2']),
    ('C2.identity', True, ['C2', 'J3']),
    ('C2.properties', True, ['C2']),
    ('C2.types', True, ['C2', 'J6']),
    ('C2.forbidden', True, ['C2']),
    ('R1', True, ['R1']),
    ('R1.join', True, ['R1']),
    ('R1.coverage', True, ['R1', 'J4']),
    ('R1.forbidden', True, ['R1']),
    ('Q1', True, ['Q1']),
    ('E1', True, ['C1', 'C2', '证据指针']),
    ('N1', True, ['N1']),
    ('N1.evidence', True, ['N1']),
    ('N2', True, ['N2']),
    ('N2.rediscover', True, ['N2']),
    ('N3', True, ['N3']),
    ('N3.evidence', False, ['N3', 'J8']),
    ('N3.gate', True, ['N3']),
    ('N4', True, ['N4']),
    ('N4.property', True, ['N4']),
    ('N4.relation', True, ['N4']),
    ('N5', True, ['N5']),
    ('N6', True, ['N6']),
    ('N7', True, ['D1']),
    ('N8', True, ['D1']),
]

_NUMBER = re.compile(r'-?\d+(?:\.\d+)?')
_GROUPED_NUMBER = re.compile(r'-?\d{1,3}(?:,\d{3})+(?:\.\d+)?')
_DATE = re.compile(r'\d{4}-\d{2}-\d{2}')
_DATETIME = re.compile(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?')
_CELL = re.compile(r'^([A-Z]+)(\d+)$')
_UNIT_CELL = re.compile(r'^table:(\d+)/row:(\d+)/col:(\d+)$')

_DATE_FMT_IDS = set(range(14, 23)) | set(range(27, 37)) | set(range(45, 48)) | set(range(50, 59))

# Issue codes whose report ``reason`` is a workbench-authored Chinese summary.
# For any other code the workbench falls back to the raw issue ``detail``,
# which can be a Python exception string; that text must not reach the report.
_KNOWN_ISSUE_CODES = frozenset({
    'ontology.conflicting_values',
    'ontology.required_value_missing',
    'ontology.required_binding_missing',
    'ontology.identity_unresolved',
    'ontology.conversion_failed',
    'ontology.evidence_missing',
    'ontology.incomplete_source',
    'ontology.relation_unresolved',
    'ontology.correction_conflict',
    'ontology.no_records',
    'record_attribution_unverified',
})

_HELPER = r'''
import json, socket, sys
from dataagent_workbench.bootstrap import Workbench
from dataagent_workbench.interfaces.http_api import create_app
import uvicorn
wb = Workbench(sys.argv[1])
sock = socket.socket()
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(('127.0.0.1', 0))
sock.listen(128)
print(json.dumps({'url': 'http://127.0.0.1:%d' % sock.getsockname()[1], 'token': wb.token}), flush=True)
uvicorn.Server(uvicorn.Config(create_app(wb), log_level='critical', access_log=False, ws='none')).run(sockets=[sock])
'''


class SetupError(RuntimeError):
    """The environment cannot run the phase (missing input, service, ...)."""


class ToolRejected(RuntimeError):
    def __init__(self, payload):
        super().__init__('tool rejected')
        self.payload = payload if isinstance(payload, dict) else {}


class HttpError(RuntimeError):
    def __init__(self, status, payload):
        super().__init__('http %s' % status)
        self.status = status
        self.payload = payload if isinstance(payload, dict) else {}


def _text(node):
    return ''.join(part.text or '' for part in node.iter('{%s}t' % W))


def _cell_column(ref):
    match = _CELL.match(ref or '')
    if not match:
        return None
    number = 0
    for letter in match.group(1):
        number = number * 26 + ord(letter) - 64
    return number, int(match.group(2))


class SourceData:
    """The bytes behind one observed source, read without extra packages."""

    def __init__(self, path, kind):
        self.path = Path(path)
        self.kind = kind
        self.paragraphs = []
        self.tables = []
        self.sheets = {}
        self.cells = {}
        self.rows = {}
        if kind == 'file' and self.path.suffix.lower() == '.docx':
            self._read_docx()
        elif kind == 'file' and self.path.suffix.lower() in {'.xlsx', '.xlsm'}:
            self._read_xlsx()
        else:
            self._read_csv()

    def _read_docx(self):
        with zipfile.ZipFile(self.path) as archive:
            root = ElementTree.fromstring(archive.read('word/document.xml'))
        body = root.find('{%s}body' % W)
        for child in body if body is not None else []:
            tag = child.tag.rsplit('}', 1)[-1]
            if tag == 'p':
                self.paragraphs.append(_text(child))
            elif tag == 'tbl':
                rows = []
                for row in child.findall('{%s}tr' % W):
                    rows.append([_text(cell) for cell in row.findall('{%s}tc' % W)])
                self.tables.append(rows)

    def _read_xlsx(self):
        with zipfile.ZipFile(self.path) as archive:
            names = archive.namelist()
            shared = []
            if 'xl/sharedStrings.xml' in names:
                root = ElementTree.fromstring(archive.read('xl/sharedStrings.xml'))
                for item in root.findall('{%s}si' % S):
                    shared.append(''.join(part.text or '' for part in item.iter('{%s}t' % S)))
            date_styles = set()
            if 'xl/styles.xml' in names:
                root = ElementTree.fromstring(archive.read('xl/styles.xml'))
                custom = {}
                for fmt in root.iter('{%s}numFmt' % S):
                    custom[int(fmt.get('numFmtId', '0'))] = fmt.get('formatCode') or ''
                xfs = root.find('{%s}cellXfs' % S)
                if xfs is not None:
                    for index, xf in enumerate(xfs.findall('{%s}xf' % S)):
                        number = int(xf.get('numFmtId', '0'))
                        code = custom.get(number, '')
                        if number in _DATE_FMT_IDS or any(token in code.lower()
                                                         for token in ('y', 'd', 'h', 's')):
                            date_styles.add(index)
            workbook = ElementTree.fromstring(archive.read('xl/workbook.xml'))
            rels = {}
            if 'xl/_rels/workbook.xml.rels' in names:
                root = ElementTree.fromstring(archive.read('xl/_rels/workbook.xml.rels'))
                for rel in root:
                    rels[rel.get('Id')] = rel.get('Target')
            targets = {}
            for sheet in workbook.iter('{%s}sheet' % S):
                rid = sheet.get('{%s}id' % R)
                target = rels.get(rid, '')
                target = target.lstrip('/')
                if not target.startswith('xl/'):
                    target = 'xl/' + target
                targets[sheet.get('name')] = target
            for name, target in targets.items():
                root = ElementTree.fromstring(archive.read(target))
                matrix = []
                cells = {}
                for row in root.iter('{%s}row' % S):
                    values = []
                    for cell in row.findall('{%s}c' % S):
                        ref = cell.get('r')
                        value = self._xlsx_value(cell, shared, date_styles)
                        cells[ref] = value
                        position = _cell_column(ref)
                        if position is None:
                            continue
                        col, _ = position
                        while len(values) < col - 1:
                            values.append(None)
                        values.append(value)
                    matrix.append(values)
                self.sheets[name] = matrix
                self.cells[name] = cells

    @staticmethod
    def _xlsx_value(cell, shared, date_styles):
        kind = cell.get('t')
        value = cell.find('{%s}v' % S)
        if kind == 'inlineStr':
            return ''.join(part.text or '' for part in cell.iter('{%s}t' % S))
        if value is None:
            return None
        raw = value.text or ''
        if kind == 's':
            try:
                return shared[int(raw)]
            except (ValueError, IndexError):
                return raw
        if kind == 'b':
            return raw == '1'
        if kind == 'str':
            return raw
        try:
            number = float(raw)
        except ValueError:
            return raw
        style = int(cell.get('s', '0') or 0)
        if style in date_styles:
            base = datetime(1899, 12, 30)
            moment = base + timedelta(days=number)
            if number == int(number):
                return moment.date()
            return moment
        if number == int(number):
            return int(number)
        return number

    def _read_csv(self):
        with self.path.open(newline='', encoding='utf-8-sig') as handle:
            self.rows[self.path.stem] = list(csv.reader(handle))

    def matrix(self, table_name, partition=None):
        if self.kind == 'file' and self.path.suffix.lower() == '.docx':
            index = int(partition) - 1 if partition not in (None, '') else 0
            return self.tables[index] if 0 <= index < len(self.tables) else []
        if self.kind == 'file' and self.path.suffix.lower() in {'.xlsx', '.xlsm'}:
            return self.sheets.get(partition or table_name, [])
        return self.rows.get(table_name, [])

    def column_values(self, table_name, partition, columns):
        rows = self.matrix(table_name, partition)
        if not rows:
            return {name: [] for name in columns}
        header = [str(item).strip() if item is not None else '' for item in rows[0]]
        values = {name: [] for name in columns}
        for row in rows[1:]:
            for name in columns:
                if name not in header:
                    continue
                index = header.index(name)
                if index >= len(row):
                    continue
                value = row[index]
                if value is None or (isinstance(value, str) and not value.strip()):
                    continue
                values[name].append(value)
        return values

    def cell(self, selector):
        if not isinstance(selector, dict):
            return None
        kind = selector.get('kind')
        if kind == 'text_span':
            match = _UNIT_CELL.match(selector.get('unit_ref') or '')
            if not match:
                return None
            table, row, col = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
            if not (1 <= table <= len(self.tables)):
                return None
            grid = self.tables[table - 1]
            if not (1 <= row <= len(grid)) or not (1 <= col <= len(grid[row - 1])):
                return None
            return grid[row - 1][col - 1]
        if kind == 'excel_cell':
            return self.cells.get(selector.get('sheet'), {}).get(selector.get('range'))
        return None


def _sha256(path):
    return 'sha256:' + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _csv_has_key(path):
    with Path(path).open(newline='', encoding='utf-8-sig') as handle:
        rows = list(csv.reader(handle))
    if len(rows) < 2:
        return False
    header, data = rows[0], rows[1:]
    for width in range(1, len(header) + 1):
        from itertools import combinations
        for indexes in combinations(range(len(header)), width):
            seen = set()
            usable = True
            for row in data:
                key = tuple(row[index] if index < len(row) else '' for index in indexes)
                if any(not value.strip() for value in key):
                    usable = False
                    break
                seen.add(key)
            if usable and len(seen) == len(data):
                return True
    return False


def _xlsx_row_count(path):
    data = SourceData(path, 'file')
    return max((len(rows) for rows in data.sheets.values()), default=0)


@dataclass
class Sample:
    source_id: str
    path: Path
    kind: str = 'file'


@dataclass
class Inputs:
    root: Path
    policy: Path
    lines: Path
    changed: Path
    no_identity: Path
    overlap: Path


def _inputs(gold_dir):
    root = Path(gold_dir).expanduser()
    if not root.is_dir():
        raise SetupError('%s is not a directory' % GOLD_ENV)
    samples = root / 'samples'
    if not samples.is_dir() or not (root / 'gold.json').is_file():
        raise SetupError('%s must contain samples/ and gold.json' % GOLD_ENV)
    docs = sorted(samples.glob('*.docx'))
    sheets = sorted([p for p in samples.glob('*') if p.suffix.lower() in {'.xlsx', '.xlsm'}])
    csvs = sorted(samples.glob('*.csv'))
    if len(docs) != 1 or len(sheets) != 2 or len(csvs) != 2:
        raise SetupError('samples must contain one docx, two spreadsheets and two csv files')
    sheets.sort(key=_xlsx_row_count)
    no_identity = [path for path in csvs if not _csv_has_key(path)]
    if len(no_identity) != 1:
        raise SetupError('samples must contain exactly one csv without a unique key')
    overlap = [path for path in csvs if path != no_identity[0]]
    return Inputs(root=root, policy=docs[0], lines=sheets[0], changed=sheets[-1],
                  no_identity=no_identity[0], overlap=overlap[0])


class Results:
    def __init__(self):
        self.rows = {key: {'id': key, 'status': 'fail', 'reason': '尚未执行',
                           'gold': list(gold), 'required': required}
                     for key, required, gold in CHECKS}

    def set(self, key, status, reason):
        row = self.rows.get(key)
        if row is None:
            raise KeyError(key)
        row['status'] = status
        row['reason'] = reason

    def ok(self, key, reason='通过'):
        self.set(key, 'pass', reason)

    def na(self, key, reason):
        """A check the gold set explicitly allows this run not to exercise."""
        self.set(key, 'not_applicable', reason)

    def fail(self, key, reason):
        self.set(key, 'fail', reason)

    def pending(self, reason):
        for row in self.rows.values():
            if row['reason'] == '尚未执行':
                row['status'] = 'fail'
                row['reason'] = reason

    def checks(self):
        return [self.rows[key] for key, _, _ in CHECKS]

    def summary(self):
        checks = self.checks()
        total = len(checks)
        passed = sum(1 for item in checks if item['status'] == 'pass')
        failed = sum(1 for item in checks if item['status'] == 'fail')
        not_applicable = [item['id'] for item in checks
                          if item['status'] == 'not_applicable']
        # A not-applicable check is allowed by the gold set; it is reported
        # with its reason and excluded from the pass rate instead of counting
        # as a failure.
        evaluated = total - len(not_applicable)
        required_failed = [item['id'] for item in checks
                           if item['required'] and item['status'] == 'fail']
        return {
            'total': total, 'passed': passed, 'failed': failed,
            'not_applicable': len(not_applicable),
            'not_applicable_ids': not_applicable,
            'pass_rate': round(passed / evaluated, 4) if evaluated else 0.0,
            'pass_rate_percent': round(100.0 * passed / evaluated, 1) if evaluated else 0.0,
            'required_failed': required_failed,
        }


class Http:
    def __init__(self, url, token):
        self.url = url
        self.token = token

    def request(self, method, path, payload=None):
        data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode()
        request = urllib.request.Request(
            self.url + path, data=data, method=method,
            headers={'x-dataagent-token': self.token, 'content-type': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.status, json.loads(response.read() or b'{}')
        except urllib.error.HTTPError as exc:
            try:
                body = json.loads(exc.read() or b'{}')
            except ValueError:
                body = {}
            return exc.code, body

    def expect(self, method, path, payload=None):
        status, body = self.request(method, path, payload)
        if status != 200:
            raise HttpError(status, body)
        return body


@contextmanager
def _service(project):
    python, = (project / '.mint/packages/dataagent').glob('workbench@*/.venv/bin/python')
    process = subprocess.Popen([str(python), '-c', _HELPER, str(project)], cwd=project,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        ready, _, _ = select.select([process.stdout], [], [], 60)
        if not ready:
            raise SetupError('workbench HTTP service did not start')
        line = process.stdout.readline()
        if not line:
            error = process.stderr.read()[-2000:]
            raise SetupError('workbench HTTP service failed: %s' % error)
        data = json.loads(line)
        yield Http(data['url'], data['token'])
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def _norm(name):
    return re.sub(r'[\s_/-]+', '', str(name)).casefold()


def _infer_type(column, values):
    # An explicit observed/declared type is stronger evidence than affinity:
    # the sheet reader emits calendar cells as ISO text, whose storage
    # affinity is text while the column type is date.  Reading affinity first
    # used to turn such a date column into a decimal mapping.
    observed = str(column.get('type') or '').strip().lower()
    if observed in {'integer', 'int', 'bigint', 'smallint', 'tinyint'}:
        return 'integer'
    if observed in {'decimal', 'numeric', 'number', 'real', 'float', 'double'}:
        return 'decimal'
    if observed == 'boolean':
        return 'boolean'
    if observed == 'date':
        return 'date'
    if observed == 'datetime':
        return 'datetime'
    affinity = str(column.get('affinity') or '')
    if affinity == 'integer':
        return 'integer'
    if affinity in {'numeric', 'real'}:
        return 'decimal'
    if affinity == 'boolean':
        return 'boolean'
    texts = []
    for value in values:
        if isinstance(value, (date, datetime)):
            texts.append(value.isoformat())
        elif value is not None and str(value).strip():
            texts.append(str(value).strip())
    if texts and all(_DATETIME.fullmatch(item) or _DATE.fullmatch(item) for item in texts):
        return 'date'
    if texts and all(_NUMBER.fullmatch(item) for item in texts) and any('.' in item for item in texts):
        return 'decimal'
    return 'string'


def _choose_identity(table, types):
    keys = [list(key) for key in (table.get('identity_keys') or [])]
    if not keys:
        return []

    def score(key):
        measures = sum(1 for column in key if types.get(column) == 'decimal')
        numerics = sum(1 for column in key if types.get(column) in {'decimal', 'integer'})
        return len(key), measures, numerics

    return min(keys, key=score)


def _relation_affine(link):
    return all(_norm(left) == _norm(right) for left, right
               in zip(link.get('source_columns') or [], link.get('target_columns') or []))


def _unit_clause(catalog, sources, table, measure):
    """The clause that states the measurement basis for a measure column."""
    document = next((item for item in catalog.get('documents') or []
                     if item.get('source_id') == table.get('source_id')), None)
    if document is None:
        return None, ''
    source = sources.get(table.get('source_id'))
    if source is None:
        return None, ''
    paragraphs = source.paragraphs
    candidates = []
    for clause in document.get('clauses') or []:
        index = clause.get('paragraph')
        if not isinstance(index, int) or not (1 <= index <= len(paragraphs)):
            continue
        text = paragraphs[index - 1]
        if measure in text:
            candidates.append((clause, text))
    if not candidates:
        return None, ''
    clause, text = max(candidates, key=lambda item: len(item[1]))
    sentences = [part.strip() for part in text.split('。') if part.strip()]
    matching = [part for part in sentences if measure in part]
    sentence = max(matching, key=len) if matching else text
    return clause, sentence


def _relation_specs(relations, evidence_relations, catalog_links):
    """Every published relation with the evidence link behind it."""
    specs = []
    for name, definition in (relations or {}).items():
        if not isinstance(definition, dict):
            continue
        evidence = (evidence_relations or {}).get(name) or {}
        link = (catalog_links or {}).get(evidence.get('evidence_id')) or {}
        source_columns = evidence.get('source_columns') or []
        target_columns = evidence.get('target_columns') or []
        # Both sides of the join are compared at full length: zip() silently
        # truncates, so a four-against-three mapping used to pass as a
        # three-column join.  Unequal widths leave no pairs, which no gold
        # relation can match and which the width check counts as wrong.
        pairs = list(zip(source_columns, target_columns)) \
            if len(source_columns) == len(target_columns) else []
        specs.append({
            'name': name, 'definition': definition, 'evidence': evidence,
            'link': link, 'pairs': pairs,
            'subject': definition.get('subject_concept'),
            'object': definition.get('object_concept'),
        })
    return specs


def _gold_direction(gold_relations, c1, c2):
    first = (gold_relations or [{}])[0]
    if str(first.get('from') or '').startswith('C1') \
            and str(first.get('to') or '').startswith('C2'):
        return c1, c2
    return c2, c1


def _relation_coverage_ok(link):
    return bool(link) and link.get('matched_rows') == 16 \
        and link.get('checked_rows') == 20 \
        and link.get('matched_distinct_keys') == 12


def _relation_checks(specs, gold_relations, c1, c2):
    """Compare every published relation with every gold relation.

    Matching is one-to-one on concept endpoints, direction and the complete
    join-column tuple.  A gold relation with no counterpart, an extra
    published relation, a reversed relation or a wrong join all fail; scoring
    the first relation and ignoring the rest would hide exactly those cases.
    """
    expected_subject, expected_object = _gold_direction(gold_relations, c1, c2)
    used = set()
    unmatched = 0
    coverage_bad = 0
    for gold in gold_relations:
        expected = sorted(tuple(pair) for pair in gold.get('join') or [])
        match = next((index for index, spec in enumerate(specs)
                      if index not in used and spec['pairs']
                      and sorted(spec['pairs']) == expected
                      and spec['subject'] == expected_subject
                      and spec['object'] == expected_object), None)
        if match is None:
            unmatched += 1
            continue
        used.add(match)
        if not _relation_coverage_ok(specs[match]['link']):
            coverage_bad += 1
    extras = len(specs) - len(used)
    expected_widths = {len(gold.get('join') or []) for gold in gold_relations}
    wrong_direction = sum(1 for spec in specs
                          if spec['subject'] != expected_subject
                          or spec['object'] != expected_object)
    wrong_width = sum(1 for spec in specs
                      if expected_widths and len(spec['pairs']) not in expected_widths)
    no_evidence = sum(1 for spec in specs
                      if not spec['evidence'].get('evidence_id') or not spec['link'])
    claimed_full = sum(1 for spec in specs
                       if spec['link'].get('checked_rows')
                       and spec['link'].get('matched_rows')
                       == spec['link'].get('checked_rows'))
    fingerprints = [(spec['subject'], spec['object'], tuple(sorted(spec['pairs'])))
                    for spec in specs]
    duplicates = len(fingerprints) - len(set(fingerprints))
    complete = len(used) == len(gold_relations) and extras == 0
    checks = {}
    if len(specs) == len(gold_relations) and complete and not wrong_direction:
        checks['R1'] = (True, '关系端点与方向逐条符合金标（%d 条）' % len(specs))
    else:
        checks['R1'] = (
            False, '关系端点/方向/数量与金标不一致（发布 %d 条，匹配 %d 条）'
            % (len(specs), len(used)))
    if complete and not unmatched and not wrong_width:
        checks['R1.join'] = (True, '三列连接字段逐条与金标一一对应（%d 条）' % len(used))
    else:
        checks['R1.join'] = (
            False, '连接字段与金标不一一对应（未匹配 %d 条，列数不符 %d 条）'
            % (unmatched, wrong_width))
    if complete and not coverage_bad:
        checks['R1.coverage'] = (True, '逐条覆盖 16/20，标准端 12/12')
    else:
        checks['R1.coverage'] = (
            False, '关系覆盖不是 16/20 或标准端不是 12/12（不符 %d 条）'
            % (coverage_bad or max(1, unmatched)))
    forbidden = []
    if extras:
        forbidden.append('多出 %d 条金标之外的关系' % extras)
    if wrong_direction:
        forbidden.append('方向或端点不符合金标 %d 条' % wrong_direction)
    if wrong_width:
        forbidden.append('连接列数与金标不一致 %d 条' % wrong_width)
    if no_evidence:
        forbidden.append('关系缺少来源证据 %d 条' % no_evidence)
    if claimed_full:
        forbidden.append('声称 100%% 匹配 %d 条' % claimed_full)
    if duplicates:
        forbidden.append('重复关系 %d 条' % duplicates)
    if forbidden:
        checks['R1.forbidden'] = (False, '；'.join(forbidden))
    else:
        checks['R1.forbidden'] = (True, '未出现多余、反向、单列或 100% 匹配的关系')
    return checks


def _compare_value_types(gold_properties, by_column, definitions):
    """(failures, date-to-datetime deviations) for the published definition.

    J6 allows a ``date`` property to be published as ``datetime``; it stays a
    pass but is counted here so the report can record the deviation.
    """
    failures = []
    deviations = 0
    for item in gold_properties:
        name = by_column.get(item['name'])
        if name is None or name not in definitions:
            failures.append('missing')
            continue
        actual = definitions[name].get('value_type')
        expected = item['value_type']
        if expected == 'date' and actual in {'date', 'datetime'}:
            if actual == 'datetime':
                deviations += 1
            continue
        if actual != expected:
            failures.append('%s->%s' % (expected, actual))
    return failures, deviations


class Flow:
    def __init__(self, project, http, inputs, results, args):
        self.project = project
        self.http = http
        self.inputs = inputs
        self.results = results
        self.args = args
        self.sources = {}
        self.paths = {}
        self.deviations = []
        self.art = {'main': {}, 'n1': {}, 'n2': {}, 'n3': {},
                    'mapping': {}, 'query': {}, 'retire': {}}

    # ------------------------------------------------------------------ tools
    def call(self, operation, arguments):
        try:
            return call_workbench(self.project, operation, arguments)
        except AssertionError as exc:
            raise ToolRejected(_payload(exc)) from None

    def rejected(self, operation, arguments):
        try:
            return call_workbench(self.project, operation, arguments, error=True)
        except AssertionError:
            return None

    def status(self, session_id):
        return self.call('intake_status', {'session_id': session_id})

    def review(self, session_id, draft_ref):
        revision = self.status(session_id)['revision']
        return self.http.expect('POST', '/api/sessions/%s/discovery/review' % session_id,
                                {'expected_revision': revision, 'draft_ref': draft_ref,
                                 'decision': 'approve'})

    def candidate(self, session_id):
        return self.http.expect('GET', '/api/sessions/%s/publish/candidate' % session_id)

    def publish(self, session_id, candidate):
        return self.http.expect('POST', '/api/sessions/%s/publish/confirm' % session_id, {
            'candidate_ref': candidate['ref'], 'draft_ref': candidate['draft_ref'],
            'source_snapshot': candidate['source_snapshot'],
            'definition_digest': candidate['definition_digest'],
            'expected_revision': candidate['session_revision'],
            'confirmed': True, 'reason': 'D7 验收人工确认',
        })

    def ontologies(self, include_deactivated=True):
        return self.http.expect(
            'GET', '/api/ontologies' + ('?include_deactivated=true' if include_deactivated else ''))

    def entry(self, ontology_id):
        return next((item for item in self.ontologies()['ontologies']
                     if item.get('id') == ontology_id), None)

    # -------------------------------------------------------------- input map
    def prepare_sources(self):
        copies = [
            ('policy', self.inputs.policy, 'policy.docx'),
            ('lines', self.inputs.lines, 'records.xlsx'),
            ('n1', self.inputs.no_identity, 'no-identity.csv'),
            ('n3', self.inputs.overlap, 'overlap.csv'),
        ]
        for source_id, source, name in copies:
            target = self.project / name
            shutil.copy2(source, target)
            self.paths[source_id] = target
            self.sources[source_id] = SourceData(target, 'file')
        self.changed = self.project / 'records-changed.xlsx'
        shutil.copy2(self.inputs.changed, self.changed)
        self.digests = {source_id: _sha256(path) for source_id, path in self.paths.items()}

    # ------------------------------------------------------------------ plan
    def plan_for(self, request, source_ids, *, all_relations=False):
        catalog = request['catalog']
        entities = []
        names = {}
        types = {}
        units = {}
        for index, table in enumerate(catalog['tables'], 1):
            name = 'Concept%d' % index
            names[table['name']] = name
            source = self.sources[table['source_id']]
            values = source.column_values(table['name'], table.get('partition'),
                                          list(table['columns']))
            inferred = {column: _infer_type(evidence, values.get(column, []))
                        for column, evidence in table['columns'].items()}
            types[table['name']] = inferred
            identity = _choose_identity(table, inferred)
            properties = [{'column': column, 'name': column}
                          for column in table['columns'] if column not in identity]
            entity = {'table': table['name'], 'name': name,
                      'grain': '观测表的一行一个实例', 'identity': identity,
                      'properties': properties}
            measures = [column for column, kind in inferred.items() if kind == 'decimal']
            if measures and table.get('kind') in {'docx', 'table'}:
                clause, sentence = _unit_clause(catalog, self.sources, table, measures[0])
                if clause is not None:
                    entity['evidence_sections'] = [clause['ref']]
                    units[measures[0]] = sentence
            entities.append(entity)
        relationships = []
        for index, link in enumerate(catalog.get('relationships') or [], 1):
            if all_relations or _relation_affine(link):
                relationships.append({'evidence_id': link['id'],
                                      'name': 'Relation%d' % index})
        return {
            'source_revision': request['source_revision'],
            'entities': entities,
            'relationships': relationships,
        }, names, types, units

    def completion_for(self, draft, plan, names, types, units, ontology_id, *,
                       limit_string=False, extra_property=None, relations=None):
        tables = {item['name']: item for item in self._catalog['tables']}
        concepts = []
        for entity in draft['entities']:
            table = tables[entity['table']]
            properties = {}
            for column in table['columns']:
                kind = types[entity['table']][column]
                if limit_string and column in units and kind == 'decimal':
                    kind = 'string'
                properties[column] = {
                    'column': column, 'value_type': kind,
                    'required': int(table['columns'][column].get('blank_rows') or 0) == 0,
                    'description': units.get(column, ''),
                }
            measure_table = getattr(self, '_measure_table', None) or draft['entities'][0]['table']
            if extra_property and entity['table'] == measure_table:
                properties[extra_property] = {
                    'column': extra_property, 'value_type': 'string',
                    'required': False, 'description': '',
                }
            concepts.append({
                'entity': entity['name'], 'concept': entity['name'],
                'properties': properties, 'identity_fields': list(entity.get('identity') or []),
            })
        if relations is not None:
            relation_items = relations
        else:
            relation_items = [{
                'evidence_id': link['id'],
                'name': link.get('name') or 'Relation',
                'subject_concept': names[link['source_table']],
                'object_concept': names[link['target_table']],
                'roles': [names[link['source_table']], names[link['target_table']]],
            } for link in draft.get('relationships') or []]
        dispositions = []
        for name in draft.get('unresolved_tables') or []:
            dispositions.append({'kind': 'unresolved_table', 'ref': str(name),
                                 'action': 'exclude',
                                 'reason': 'D7 验收：该表不进入本次发布'})
        for link in draft.get('unresolved_relationships') or []:
            dispositions.append({'kind': 'unresolved_relationship', 'ref': str(link.get('id')),
                                 'action': 'exclude',
                                 'reason': 'D7 验收：列名语义不同、无其他字段佐证，不采纳'})
        for gap in draft.get('gaps') or []:
            dispositions.append({'kind': 'coverage_gap', 'ref': str(gap.get('ref')),
                                 'action': 'accept',
                                 'reason': 'D7 验收：候选键搜索有界，已知缺口接受'})
        return {
            'session_id': draft['ref'].split('@', 1)[0],
            'expected_revision': str(self.status(draft['ref'].split('@', 1)[0])['revision']),
            'draft_ref': draft['ref'], 'ontology_id': ontology_id,
            'title': 'D7 discovered ontology', 'concepts': concepts,
            'relations': relation_items, 'dispositions': dispositions,
        }

    # ---------------------------------------------------------------- stages
    def stage_n1(self):
        artifact = self.art['n1']
        try:
            started = self.call('intake_start', {
                'goal': 'D7 无可靠标识反例',
                'mode': 'ontology_discovery',
                'sources': [{'source_id': 'n1', 'kind': 'file',
                             'locator_ref': self.paths['n1'].name}],
            })
            session = started['session_id']
            request = self.call('intake_advance', {'session_id': session})
            artifact.update(session=session, request=request, catalog=request['catalog'])
            self._catalog = request['catalog']
            table, = request['catalog']['tables']
            artifact['table'] = table
            if not table.get('identity_keys') and not table.get('keys'):
                self.results.ok('N1.evidence',
                                '证据报告无无空值且唯一的候选键；%d 行未被去重' % table['rows_observed'])
            else:
                self.results.fail('N1.evidence', '证据仍给出候选键，未标为无可靠标识')
            plan, names, types, units = self.plan_for(request, ['n1'])
            artifact['plan'] = plan
            draft = self.call('ontology_discovery_propose', {
                'session_id': session,
                'expected_revision': request['expected_revision'],
                'proposal': plan,
            })
            artifact['draft'] = draft
            entity, = draft['entities']
            artifact['entity'] = entity
            if not entity.get('identity'):
                self.results.ok('N1', '草案身份为空并作为待决项；发布尝试需被阻断')
            else:
                self.results.fail('N1', '草案给出了身份字段')
            completion = self.completion_for(draft, plan, names, types, units,
                                             'd7-no-identity')
            payload = self.rejected('ontology_publish_prepare', completion)
            artifact['prepare_rejected'] = payload is not None
            if payload is None:
                self.results.fail('N1', '空身份仍生成了发布候选')
            if self.entry('d7-no-identity') is not None:
                self.results.fail('N1', '空身份仍写入了本体修订')
        except ToolRejected as exc:
            artifact['error'] = 'tool'
            self.results.fail('N1', '无可靠标识链路在工具层被拒（%s）' % _code(exc.payload))
        except HttpError as exc:
            self.results.fail('N1', '无可靠标识链路 HTTP 失败（状态 %s）' % exc.status)
            self.results.fail('N1.evidence', '无可靠标识链路未完成')

    def stage_main(self):
        artifact = self.art['main']
        try:
            started = self.call('intake_start', {
                'goal': 'D7 本体发现：标准与明细',
                'mode': 'ontology_discovery',
                'sources': [
                    {'source_id': 'policy', 'kind': 'file',
                     'locator_ref': self.paths['policy'].name},
                    {'source_id': 'lines', 'kind': 'file',
                     'locator_ref': self.paths['lines'].name},
                ],
            })
            session = started['session_id']
            request = self.call('intake_advance', {'session_id': session})
            artifact.update(session=session, request=request)
            self._catalog = request['catalog']
            tables = {table['name']: table for table in request['catalog']['tables']}
            if len(tables) == 2 and request['coverage'] == 'full':
                counts = sorted(table['rows_observed'] for table in tables.values())
                if counts == [12, 20]:
                    self.results.ok('CHAIN.discovery',
                                    '两份来源均被探查；表行数 12/20，覆盖 full')
                else:
                    self.results.fail('CHAIN.discovery', '表行数与金标不一致')
            else:
                self.results.fail('CHAIN.discovery', '未得到两份来源的完整证据')
            plan, names, types, units = self.plan_for(request, ['policy', 'lines'])
            artifact.update(plan=plan, names=names, types=types, units=units)
            artifact['keys'] = {table['name']: ('C1' if table.get('kind') == 'docx' else 'C2')
                                for table in request['catalog']['tables']}
            draft = self.call('ontology_discovery_propose', {
                'session_id': session,
                'expected_revision': request['expected_revision'],
                'proposal': plan,
            })
            artifact['draft'] = draft
            self._measure_table = self._measure_table_name(request['catalog'], types)
        except ToolRejected as exc:
            artifact['error'] = 'tool'
            self.results.fail('CHAIN.discovery', '发现链路被工具拒绝（%s）' % _code(exc.payload))
            self.results.fail('CHAIN.review', '发现链路未完成')

    @staticmethod
    def _measure_table_name(catalog, types):
        for table in catalog['tables']:
            if table.get('kind') == 'docx' and any(
                    kind == 'decimal' for kind in types[table['name']].values()):
                return table['name']
        return None

    def stage_candidate(self):
        artifact = self.art['main']
        if not artifact.get('draft'):
            self.results.fail('CHAIN.publish', '没有可补全的草案')
            return
        draft = artifact['draft']
        plan = artifact['plan']
        names, types, units = artifact['names'], artifact['types'], artifact['units']
        self._catalog = artifact['request']['catalog']
        try:
            completion = self.completion_for(draft, plan, names, types, units, 'expense-policy')
            try:
                artifact['candidate1'] = self.call('ontology_publish_prepare', completion)
                artifact['mode'] = 'gold'
                artifact['gold_error'] = None
            except ToolRejected as exc:
                detail = str(exc.payload.get('detail') or '')
                artifact['gold_error'] = _code(exc.payload)
                artifact['gold_detail'] = detail
                fallback = self.completion_for(draft, plan, names, types, units,
                                               'expense-policy', limit_string=True)
                artifact['candidate1'] = self.call('ontology_publish_prepare', fallback)
                artifact['mode'] = 'fallback'
            candidate = artifact['candidate1']
            artifact['candidate_body'] = self.candidate(artifact['session'])
            if candidate.get('state') == 'awaiting_human_confirmation':
                self.results.fail('CHAIN.publish',
                                  '候选已生成，发布尚未执行：等待 HTTP 人工确认（补全模式 %s）'
                                  % artifact['mode'])
            else:
                self.results.fail('CHAIN.publish', '候选状态不是等待人工确认')
        except ToolRejected as exc:
            artifact['error'] = 'tool'
            self.results.fail('CHAIN.publish', '补全被工具拒绝（%s）' % _code(exc.payload))
        except HttpError as exc:
            self.results.fail('CHAIN.publish', '补全 HTTP 失败（状态 %s）' % exc.status)

    def stage_n4_n5(self):
        artifact = self.art['main']
        if not artifact.get('candidate1'):
            self.results.fail('N4', '没有可篡改的候选')
            self.results.fail('N4.property', '没有可篡改的候选')
            self.results.fail('N4.relation', '没有可篡改的候选')
            self.results.fail('N5', '没有可尝试确认的候选')
            return
        draft = artifact['draft']
        plan = artifact['plan']
        names, types, units = artifact['names'], artifact['types'], artifact['units']
        before = self.candidate(artifact['session'])['ref']
        tampered = self.completion_for(draft, plan, names, types, units, 'expense-policy',
                                       limit_string=artifact.get('mode') == 'fallback',
                                       extra_property='__unobserved_attribute__')
        payload = self.rejected('ontology_publish_prepare', tampered)
        if payload is None:
            self.results.fail('N4.property', '虚构属性仍生成了候选')
        else:
            self.results.ok('N4.property', '虚构属性被发布前校验拒绝')
        tampered = self.completion_for(
            draft, plan, names, types, units, 'expense-policy',
            limit_string=artifact.get('mode') == 'fallback',
            relations=[{'evidence_id': '__missing_relationship_evidence__',
                        'name': 'RelationX',
                        'subject_concept': names[draft['entities'][0]['table']],
                        'object_concept': names[draft['entities'][-1]['table']],
                        'roles': ['from', 'to']}])
        payload = self.rejected('ontology_publish_prepare', tampered)
        if payload is None:
            self.results.fail('N4.relation', '无证据关系仍生成了候选')
        else:
            self.results.ok('N4.relation', '无证据关系被发布前校验拒绝')
        after = self.candidate(artifact['session'])['ref']
        if before == after:
            self.results.ok('N4', '提案/发布前校验拒绝无证据属性与关系，未写入新候选')
        else:
            self.results.fail('N4', '篡改请求产生了新候选')
        try:
            candidate = self.candidate(artifact['session'])
            payload = self.call('ontology_publish_confirm', {
                'session_id': artifact['session'],
                'candidate_ref': candidate['ref'],
                'draft_ref': candidate['draft_ref'],
                'source_snapshot': candidate['source_snapshot'],
                'definition_digest': candidate['definition_digest'],
                'expected_revision': candidate['session_revision'],
                'confirmed': True,
                'reason': 'D7 N5 agent tool attempt',
            })
            state = self.candidate(artifact['session'])
            if payload.get('human_confirmation_required') is True and state['state'] != 'published' \
                    and self.entry('expense-policy') is None:
                self.results.ok('N5', 'Agent 工具确认被拒，候选未发布且无本体修订')
            else:
                self.results.fail('N5', 'Agent 工具确认未被拒绝')
        except ToolRejected:
            state = self.candidate(artifact['session'])
            if state['state'] != 'published' and self.entry('expense-policy') is None:
                self.results.ok('N5', 'Agent 工具确认被拒，候选未发布且无本体修订')
            else:
                self.results.fail('N5', 'Agent 工具确认后出现发布结果')
        except HttpError as exc:
            self.results.fail('N5', 'Agent 工具确认 HTTP 失败（状态 %s）' % exc.status)

    def stage_n3(self):
        artifact = self.art['n3']
        try:
            started = self.call('intake_start', {
                'goal': 'D7 值重合反例',
                'mode': 'ontology_discovery',
                'sources': [
                    {'source_id': 'lines', 'kind': 'file',
                     'locator_ref': self.paths['lines'].name},
                    {'source_id': 'n3', 'kind': 'file',
                     'locator_ref': self.paths['n3'].name},
                ],
            })
            session = started['session_id']
            request = self.call('intake_advance', {'session_id': session})
            artifact.update(session=session, request=request)
            catalog = request['catalog']
            self._catalog = catalog
            tables = {table['name']: table for table in catalog['tables']}
            artifact['tables'] = tables
            plan, names, types, units = self.plan_for(request, ['lines', 'n3'],
                                                     all_relations=True)
            artifact.update(plan=plan, names=names, types=types, units=units)
            artifact['keys'] = {table['name']: ('C1' if table.get('kind') == 'docx' else 'C2')
                                for table in request['catalog']['tables']}
            draft = self.call('ontology_discovery_propose', {
                'session_id': session,
                'expected_revision': request['expected_revision'],
                'proposal': plan,
            })
            artifact['draft'] = draft
            draft = self.review(session, draft['ref'])
            artifact['draft'] = draft
            self._catalog = catalog
            completion = self.completion_for(draft, plan, names, types, units, 'overlap-check')
            candidate = self.call('ontology_publish_prepare', completion)
            artifact['candidate'] = candidate
            artifact['candidate_body'] = self.candidate(session)
            publication = self.publish(session, artifact['candidate_body'])
            artifact['published'] = publication
            entry = self.entry('overlap-check')
            if entry is not None:
                artifact['entry'] = entry
        except ToolRejected as exc:
            artifact['error'] = 'tool'
            self.results.fail('N3', '值重合反例链路被工具拒绝（%s）' % _code(exc.payload))
        except HttpError as exc:
            self.results.fail('N3', '值重合反例链路 HTTP 失败（状态 %s）' % exc.status)

    def stage_publish(self):
        artifact = self.art['main']
        if not artifact.get('candidate1') or not artifact.get('draft'):
            self.results.fail('N6', '没有 r1 候选')
            self.results.fail('CHAIN.publish', '发布未执行：没有可确认的 r1 候选')
            return
        draft = artifact['draft']
        plan = artifact['plan']
        names, types, units = artifact['names'], artifact['types'], artifact['units']
        self._catalog = artifact['request']['catalog']
        try:
            # Draft r1 is still pending after its candidate was prepared, so
            # the same task can produce draft r2; r2 is the revision a human
            # reviews and publishes.
            status = self.status(artifact['session'])
            draft2 = self.call('ontology_discovery_propose', {
                'session_id': artifact['session'],
                'expected_revision': str(status['revision']),
                'proposal': plan,
            })
            artifact['draft2'] = draft2
            draft2 = self.review(artifact['session'], draft2['ref'])
            artifact['draft2'] = draft2
            artifact['draft'] = draft2
            if draft2.get('state') == 'approved':
                self.results.ok('CHAIN.review', '草案 r2 经 HTTP 人工通道审核通过')
            else:
                self.results.fail('CHAIN.review', '草案 r2 审核未被记录为通过')
            fallback = artifact.get('mode') == 'fallback'
            completion = self.completion_for(draft2, plan, names, types, units,
                                             'expense-policy', limit_string=fallback)
            artifact['candidate2'] = self.call('ontology_publish_prepare', completion)
        except ToolRejected as exc:
            artifact['error'] = 'tool'
            self.results.fail('CHAIN.review', '草案 r2 提案/审核未完成（%s）' % _code(exc.payload))
            self.results.fail('N6', 'r2 提案/候选被拒（%s）' % _code(exc.payload))
            return
        except HttpError as exc:
            self.results.fail('CHAIN.review', '草案 r2 HTTP 失败（状态 %s）' % exc.status)
            self.results.fail('N6', 'r2 候选未完成')
            return
        try:
            # Send the old candidate with the *current* task revision so the
            # request reaches the candidate-staleness gate, not the task
            # revision check.
            c2 = self.candidate(artifact['session'])
            stale_status, stale_body = self.http.request(
                'POST', '/api/sessions/%s/publish/confirm' % artifact['session'], {
                    'candidate_ref': artifact['candidate1'].get('candidate_ref'),
                    'draft_ref': draft['ref'],
                    'source_snapshot': artifact['candidate1']['source_snapshot'],
                    'definition_digest': artifact['candidate1']['definition_digest'],
                    'expected_revision': c2['session_revision'],
                    'confirmed': True, 'reason': 'D7 N6 stale confirmation',
                })
            artifact['stale'] = (stale_status, stale_body)
            published = self.publish(artifact['session'], c2)
            artifact['published'] = published
            again_status, again_body = self.http.request(
                'POST', '/api/sessions/%s/publish/confirm' % artifact['session'], {
                    'candidate_ref': c2['ref'], 'draft_ref': c2['draft_ref'],
                    'source_snapshot': c2['source_snapshot'],
                    'definition_digest': c2['definition_digest'],
                    'expected_revision': c2['session_revision'],
                    'confirmed': True, 'reason': 'D7 N6 duplicate confirmation',
                })
            artifact['duplicate'] = (again_status, again_body)
            entry = self.entry('expense-policy')
            artifact['entry'] = entry
            if entry is not None and entry.get('ontology_revision') == '1':
                self.results.ok('CHAIN.publish', 'HTTP 人工确认发布成功，注册表只有一个修订')
            else:
                self.results.fail('CHAIN.publish', '发布后注册表修订不是 1')
            stale_detail = _detail(stale_body).lower()
            duplicate_detail = _detail(again_body).lower()
            stale_ok = stale_status == 409 and ('stale' in stale_detail or '过期' in stale_detail) \
                and 'task changed' not in stale_detail
            duplicate_ok = (again_status == 409
                            and ('already published' in duplicate_detail
                                 or '已发布' in duplicate_detail)) or (
                again_status == 200
                and again_body.get('publication_ref') == published.get('publication_ref'))
            if stale_ok and duplicate_ok and entry is not None \
                    and entry.get('ontology_revision') == '1':
                self.results.ok('N6', '过期候选与重复确认分别命中候选过期/已发布门禁，只有一个本体修订')
            else:
                self.results.fail('N6', '过期/重复确认未命中对应门禁或修订数不符合要求')
        except ToolRejected as exc:
            self.results.fail('N6', '确认链路被工具拒绝（%s）' % _code(exc.payload))
        except HttpError as exc:
            artifact['publish_error'] = (exc.status, _code(exc.payload))
            self.results.fail('N6', 'HTTP 确认失败（状态 %s）' % exc.status)
            self.results.fail('CHAIN.publish', 'HTTP 确认失败（状态 %s）' % exc.status)

    def stage_mapping(self):
        entry = self.entry('expense-policy')
        if entry is None or entry.get('state') != 'active':
            self.results.fail('CHAIN.mapping', '没有已发布的本体可供映射')
            for key in ('C1', 'C2', 'R1', 'R1.join', 'R1.coverage', 'R1.forbidden', 'Q1', 'E1'):
                self.results.fail(key, '本体未发布，映射/查询未执行')
            return
        concepts = {name: name for name in entry.get('concepts') or []}
        # Concept names are stable in this run: first table is the standard,
        # second table is the detail.  Map each target separately.
        names = self.art['main']['names']
        targets = {value: names.get(name) for name, value in
                   (self.art['main'].get('keys') or {}).items()}
        self.art['mapping'] = {}
        for key, concept in targets.items():
            if concept is None:
                self.results.fail('CHAIN.mapping', '缺少概念映射目标')
                continue
            try:
                started = self.call('intake_start', {
                    'goal': 'D7 映射保存 %s' % key, 'mode': 'mapping',
                    'sources': [{'source_id': 'source',
                                 'kind': 'file',
                                 'locator_ref': self.paths['policy' if key == 'C1' else 'lines'].name}],
                    'target': {'ontology_id': 'expense-policy', 'concept': concept},
                })
                session = started['session_id']
                request = self.call('intake_advance', {'session_id': session})
                target = request['allowed_target']
                source = request['sources'][0]
                properties = target['properties']
                bindings = {}
                for property_name, definition in properties.items():
                    if property_name not in source['fields']:
                        continue
                    bindings[property_name] = self._binding(definition, source, property_name)
                mapping = {
                    'id': 'candidate', 'revision': '1',
                    'ontology_revision': target['ontology_revision'],
                    'concept': target['concept'],
                    'source_fingerprint': source['structure_fingerprint'],
                    'bindings': bindings,
                }
                preview = self.call('intake_propose', {
                    'session_id': session,
                    'expected_revision': request['expected_revision'],
                    'proposal': mapping,
                })
                status = self.status(session)
                receipt = self.call('mapping_apply', {
                    'session_id': session,
                    'expected_revision': str(status['revision']),
                    'decision': {'preview_ref': preview['preview_ref'],
                                 'target_scope': 'mapping', 'decision': 'save'},
                })
                self.art['mapping'][key] = {
                    'session': session, 'preview': preview, 'receipt': receipt,
                    'issue_count': preview.get('issue_count'),
                }
            except ToolRejected as exc:
                self.art['mapping'][key] = {'error': _code(exc.payload),
                                            'issues': _issue_reasons(exc.payload)}
        mapped = [item for item in self.art['mapping'].values()
                  if item.get('receipt') and not item.get('issue_count')]
        if len(mapped) == 2:
            self.results.ok('CHAIN.mapping', '两个概念分别映射并保存成功')
        else:
            details = self._mapping_failure_details()
            self.results.fail(
                'CHAIN.mapping',
                '映射保存未全部成功' + ('（%s）' % '；'.join(details) if details else ''))
        self._query()

    def _mapping_failure_details(self):
        """Which target failed and the workbench's own issue codes/reasons.

        Only the stable machine code and the Chinese explanation are copied;
        object labels, source values and row numbers stay out of the report.
        """
        details = []
        for key in ('C1', 'C2'):
            item = self.art['mapping'].get(key) or {}
            if item.get('receipt') and not item.get('issue_count'):
                continue
            notes = item.get('issues') or []
            if notes:
                details.append('%s 映射保存未通过：%s' % (key, '；'.join(notes)))
            elif item.get('issue_count'):
                details.append('%s 预览仍有 %s 项阻断问题' % (key, item['issue_count']))
            elif item.get('error'):
                details.append('%s 映射保存未通过：%s' % (key, item['error']))
            else:
                details.append('%s 映射未执行' % key)
        return details

    def _mapping_note(self, key):
        item = (self.art.get('mapping') or {}).get(key) or {}
        notes = item.get('issues') or []
        if notes:
            return '（%s 映射保存未通过：%s）' % (key, '；'.join(notes))
        if item.get('error'):
            return '（%s 映射保存未通过：%s）' % (key, item['error'])
        return ''

    def _binding(self, definition, source, property_name):
        kind = definition.get('value_type')
        binding = {'source_field': property_name}
        if kind == 'integer':
            binding['transform'] = 'integer'
        elif kind == 'decimal':
            binding['transform'] = 'decimal'
        elif kind in {'date', 'datetime'}:
            samples = [row.get(property_name) for row in source.get('samples') or []
                       if row.get(property_name) is not None]
            sample = str(samples[0]) if samples else ''
            binding['transform'] = 'date' if kind == 'date' else 'datetime'
            if re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', sample):
                binding['options'] = {'format': '%Y-%m-%dT%H:%M:%S'}
            if kind == 'datetime':
                # A format only controls parsing; a naive datetime still needs
                # an explicit zone before materialization.
                binding.setdefault('options', {})['timezone'] = 'UTC'
        return binding

    def _query(self):
        collected = {}
        for key in ('C1', 'C2'):
            mapped = self.art['mapping'].get(key) or {}
            if not mapped.get('receipt'):
                continue
            concept = self.art['main']['names'].get(
                next((name for name, value in (self.art['main'].get('keys') or {}).items()
                      if value == key), None))
            try:
                page = self.call('ontology_query', {
                    'ontology_id': 'expense-policy',
                    'concept': concept,
                    'limit': 200,
                })
                collected[key] = page
                if key == 'C1':
                    collected['C1_filters'] = self._filtered_queries(concept, page)
            except ToolRejected:
                collected[key] = None
        self.art['query'] = collected
        if collected.get('C1') and collected.get('C2') \
                and collected['C1']['total'] and collected['C2']['total']:
            self.results.ok('CHAIN.query', '两个概念均从已发布快照查到实例')
        else:
            details = []
            for key in ('C1', 'C2'):
                if (collected.get(key) or {}).get('total'):
                    continue
                item = self.art['mapping'].get(key) or {}
                notes = item.get('issues') or []
                if notes:
                    details.append('%s 映射保存未通过：%s' % (key, '；'.join(notes)))
                else:
                    details.append('%s 没有可查询的已发布实例' % key)
            self.results.fail(
                'CHAIN.query',
                '按本体查询未返回已发布实例' + ('（%s）' % '；'.join(details) if details else ''))

    def _filtered_query(self, concept, where):
        try:
            return self.call('ontology_query', {
                'ontology_id': 'expense-policy',
                'concept': concept,
                'where': where,
                'limit': 200,
            })
        except ToolRejected:
            return None

    def _filtered_queries(self, concept, page):
        """Equality queries on the observed low-cardinality attributes.

        Q1 must go through the tool's attribute-filter path instead of
        scanning the whole concept.  Candidate attributes and values come only
        from the published page, never from gold.  One- and two-condition
        filters are both issued so the comparison can require an exact match;
        the result set is kept on the artifact for scoring.
        """
        definition = ((self.art['main'].get('candidate_body') or {})
                      .get('definition') or {}).get('concepts', {}).get(concept) or {}
        items = page.get('items') or []
        singles = []
        for name, spec in (definition.get('properties') or {}).items():
            if spec.get('value_type') != 'string':
                continue
            values = []
            for item in items:
                value = (item.get('values') or {}).get(name)
                if isinstance(value, str) and value.strip() and value not in values:
                    values.append(value)
            if not 1 < len(values) <= 4:
                continue
            for value in values:
                where = [{'property': name, 'op': 'eq', 'value': value}]
                filtered = self._filtered_query(concept, where)
                singles.append({'where': where, 'page': filtered,
                                'ids': _item_ids(filtered)})
        results = list(singles)
        pairs = []
        for index, left in enumerate(singles):
            for right in singles[index + 1:]:
                if not left['ids'] or not right['ids']:
                    continue
                if left['where'][0]['property'] == right['where'][0]['property']:
                    continue
                overlap = left['ids'] & right['ids']
                if not overlap or len(overlap) >= min(len(left['ids']), len(right['ids'])):
                    continue
                where = left['where'] + right['where']
                key = frozenset((item['property'], str(item['value'])) for item in where)
                pairs.append((len(overlap), sorted(key), where))
        pairs.sort(key=lambda item: (item[0], item[1]))
        for _, _, where in pairs[:6]:
            results.append({'where': where, 'page': self._filtered_query(concept, where)})
        return results

    def stage_retire(self):
        entry = self.entry('expense-policy')
        if entry is None or entry.get('state') != 'active':
            self.results.fail('N7', '没有可停用的已发布本体')
            self.results.fail('N8', '没有可停用的已发布本体')
            return
        before_query = dict(self.art['query'])
        try:
            retired = self.http.expect('POST', '/api/ontologies/expense-policy/retire', {
                'reason': 'D7 验收：停用当前指针',
                'expected_revision': entry.get('registry_revision'),
                'confirmed': True,
            })
            self.art['retire']['result'] = retired
            listing = self.ontologies()
            updated = next((item for item in listing['ontologies']
                            if item.get('id') == 'expense-policy'), None)
            self.art['retire']['entry'] = updated
            old = self.art['mapping'].get('C1', {})
            old_status = self.status(old['session']) if old.get('session') else None
            old_target = (old_status or {}).get('extensions', {}).get('dataagent.mapping_target')
            queries = {}
            for key in ('C1', 'C2'):
                if self.art['query'].get(key):
                    try:
                        queries[key] = self.call('ontology_query', {
                            'ontology_id': 'expense-policy',
                            'concept': self.art['main']['names'].get(
                                next((name for name, value in (self.art['main'].get('keys') or {}).items()
                                      if value == key), None)),
                            'limit': 200,
                        })
                    except ToolRejected:
                        queries[key] = None
            self.art['retire']['queries'] = queries
            new_start = self.call('intake_start', {
                'goal': 'D7 停用后回退', 'mode': 'mapping',
                'sources': [{'source_id': 'source', 'kind': 'file',
                             'locator_ref': self.paths['policy'].name}],
            })
            new_session = new_start['session_id']
            new_request = self.call('intake_advance', {'session_id': new_session})
            new_status = self.status(new_session)
            fallback = new_request.get('allowed_target') or {}
            fallback_target = (new_status.get('extensions') or {}).get('dataagent.mapping_target') or {}
            self.art['retire']['fallback'] = fallback
            self.art['retire']['fallback_target'] = fallback_target
            old_queries_ok = all(queries.get(key) and queries[key].get('total') ==
                                 (before_query.get(key) or {}).get('total')
                                 for key in ('C1', 'C2') if before_query.get(key))
            default_id = listing.get('default_ontology')
            new_id = fallback_target.get('ontology_id')
            new_rev = str(fallback_target.get('revision') or '')
            old_rev = str(old_target.get('revision') or '') if old_target else ''
            old_target_ok = bool(old_target) and old_target.get('ontology_id') == 'expense-policy' \
                and old_rev == str(entry.get('ontology_revision') or '') \
                and old_target.get('concept') in (entry.get('concepts') or [])
            new_target_ok = bool(default_id) and new_id == default_id \
                and new_id != 'expense-policy' and bool(new_rev) \
                and fallback.get('ontology_id') == new_id \
                and fallback.get('concept') == fallback_target.get('concept') \
                and str(fallback.get('ontology_revision') or '') == '%s@%s' % (new_id, new_rev)
            if updated and updated.get('state') == 'retired' and old_target_ok \
                    and new_target_ok and old_queries_ok:
                self.results.ok('N7', '停用后新任务固定默认本体；旧任务目标/修订固定，旧快照仍可查')
            else:
                self.results.fail('N7', '停用后的回退、目标固定或旧任务行为不符合要求')
            payload = self.rejected('intake_start', {
                'goal': 'D7 显式选择已停用本体', 'mode': 'mapping',
                'sources': [{'source_id': 'source', 'kind': 'file',
                             'locator_ref': self.paths['policy'].name}],
                'target': {'ontology_id': 'expense-policy', 'concept': entry.get('default_concept')},
            })
            if payload is not None:
                detail = str(payload.get('detail') or '')
                if 'retired' in detail.lower() or '停用' in detail:
                    self.results.ok('N8', '已停用本体不能被显式选为目标')
                else:
                    self.results.fail('N8', '显式选择已停用本体被拒，但原因不是停用')
            else:
                self.results.fail('N8', '已停用本体仍可被显式选为目标')
        except ToolRejected as exc:
            self.results.fail('N7', '停用链路被工具拒绝（%s）' % _code(exc.payload))
            self.results.fail('N8', '停用链路未完成')
        except HttpError as exc:
            self.results.fail('N7', '停用 HTTP 失败（状态 %s）' % exc.status)
            self.results.fail('N8', '停用链路未完成')

    def stage_n2(self):
        artifact = self.art['n2']
        try:
            started = self.call('intake_start', {
                'goal': 'D7 来源变更反例',
                'mode': 'ontology_discovery',
                'sources': [
                    {'source_id': 'policy', 'kind': 'file',
                     'locator_ref': self.paths['policy'].name},
                    {'source_id': 'lines', 'kind': 'file',
                     'locator_ref': self.paths['lines'].name},
                ],
            })
            session = started['session_id']
            request = self.call('intake_advance', {'session_id': session})
            artifact.update(session=session, request=request)
            self._catalog = request['catalog']
            plan, names, types, units = self.plan_for(request, ['policy', 'lines'])
            artifact.update(plan=plan, names=names, types=types, units=units)
            artifact['keys'] = {table['name']: ('C1' if table.get('kind') == 'docx' else 'C2')
                                for table in request['catalog']['tables']}
            draft = self.call('ontology_discovery_propose', {
                'session_id': session,
                'expected_revision': request['expected_revision'],
                'proposal': plan,
            })
            artifact['draft'] = draft
            draft = self.review(session, draft['ref'])
            artifact['draft'] = draft
            completion = self.completion_for(draft, plan, names, types, units,
                                             'expense-policy-n2')
            try:
                artifact['candidate'] = self.call('ontology_publish_prepare', completion)
                artifact['mode'] = 'gold'
            except ToolRejected:
                completion = self.completion_for(draft, plan, names, types, units,
                                                 'expense-policy-n2', limit_string=True)
                artifact['candidate'] = self.call('ontology_publish_prepare', completion)
                artifact['mode'] = 'fallback'
            pointer_before = self.ontologies().get('pointer')
            artifact['pointer_before'] = pointer_before
            original = self.digests['lines']
            shutil.copy2(self.changed, self.paths['lines'])
            changed_digest = _sha256(self.paths['lines'])
            artifact['digest_changed'] = original != changed_digest
            candidate = self.candidate(session)
            status, body = self.http.request(
                'POST', '/api/sessions/%s/publish/confirm' % session, {
                    'candidate_ref': candidate['ref'], 'draft_ref': candidate['draft_ref'],
                    'source_snapshot': candidate['source_snapshot'],
                    'definition_digest': candidate['definition_digest'],
                    'expected_revision': candidate['session_revision'],
                    'confirmed': True, 'reason': 'D7 N2 confirmation after source change',
                })
            artifact['confirm'] = (status, body)
            artifact['entry_after'] = self.entry('expense-policy-n2')
            artifact['pointer_after'] = self.ontologies().get('pointer')
            pointer_same = pointer_before == artifact['pointer_after']
            source_change = _is_source_change_rejection(body)
            artifact['confirm_reason'] = _detail(body)
            if status == 422 and artifact['entry_after'] is None \
                    and artifact.get('digest_changed') and pointer_same and source_change:
                self.results.ok('N2', '来源快照已变时确认被拒（原因为来源变更），未写本体修订，指针未变')
            elif status == 422 and not source_change:
                self.results.fail('N2', '确认被拒，但拒绝原因不是来源变更（%s）' % _code(body))
            else:
                self.results.fail('N2', '来源变更后的确认未被正确拒绝')
        except ToolRejected as exc:
            artifact['error'] = _code(exc.payload)
            self.results.fail('N2', '来源变更反例被工具拒绝（%s）' % _code(exc.payload))
        except HttpError as exc:
            artifact['error'] = 'http_%s' % exc.status
            self.results.fail('N2', '来源变更反例 HTTP 失败（状态 %s）' % exc.status)
        self._n2_rediscover()

    def _n2_rediscover(self):
        artifact = self.art['n2']
        try:
            started = self.call('intake_start', {
                'goal': 'D7 来源变更后重新探查',
                'mode': 'ontology_discovery',
                'sources': [
                    {'source_id': 'policy', 'kind': 'file',
                     'locator_ref': self.paths['policy'].name},
                    {'source_id': 'lines', 'kind': 'file',
                     'locator_ref': self.paths['lines'].name},
                ],
            })
            session = started['session_id']
            request = self.call('intake_advance', {'session_id': session})
            artifact['reprobe'] = request
            catalog = request['catalog']
            tables = {table['name']: table for table in catalog['tables']}
            line_table = next((table for table in tables.values()
                               if table['rows_observed'] == 21), None)
            if line_table is None:
                self.results.fail('N2.rediscover', '重新探查未得到 21 行')
                return
            original = self.art['main'].get('request', {}).get('catalog', {})
            original_tables = {table['name']: table for table in original.get('tables') or []}
            original_line = next((table for table in original_tables.values()
                                  if table['rows_observed'] == 20), None)
            identity_ok = original_line is not None and \
                sorted(map(tuple, original_line.get('identity_keys') or [])) == \
                sorted(map(tuple, line_table.get('identity_keys') or []))
            link = next((item for item in catalog.get('relationships') or []
                         if item.get('source_table') == line_table['name']
                         and item.get('checked_rows') == 21), None)
            if link is None:
                self.results.fail(
                    'N2.rediscover',
                    '结构为 21 行且身份不变，但复合关联未因部分覆盖生成候选（发布规则要求源值全部命中）')
            elif identity_ok and link.get('matched_rows') == 17 \
                    and link.get('matched_distinct_keys') == 12:
                self.results.ok('N2.rediscover', '重新探查 21 行、身份不变、关联覆盖 17/21')
            else:
                self.results.fail('N2.rediscover', '重新探查的行数/身份/覆盖与金标不一致')
        except ToolRejected as exc:
            self.results.fail('N2.rediscover', '重新探查被工具拒绝（%s）' % _code(exc.payload))

    # ---------------------------------------------------------------- scoring
    def score(self, gold):
        self.gold = gold
        self._score_concepts()
        self._score_relation()
        self._score_query()
        self._score_evidence()
        self._score_n3()

    def _concept_evidence(self, key):
        artifact = self.art['main']
        candidate = artifact.get('candidate_body')
        if not candidate:
            return None, None
        table_name = next((name for name, value in (artifact.get('keys') or {}).items()
                           if value == key), None)
        concept = artifact['names'].get(table_name)
        evidence = (candidate.get('evidence') or {}).get('concepts', {}).get(concept)
        definition = (candidate.get('definition') or {}).get('concepts', {}).get(concept)
        return evidence, definition

    def _gold_concept(self, key):
        return next(item for item in self.gold['concepts'] if item['key'] == key)

    def _score_concepts(self):
        for key in ('C1', 'C2'):
            gold = self._gold_concept(key)
            evidence, definition = self._concept_evidence(key)
            prefix = key
            if evidence is None or definition is None:
                reason = '没有已补全的候选概念'
                for suffix in ('', '.identity', '.properties', '.types', '.forbidden'):
                    self.results.fail(prefix + suffix, reason)
                if key == 'C1':
                    self.results.fail('C1.unit', reason)
                continue
            columns = {name: item.get('column') for name, item in
                       (evidence.get('properties') or {}).items()}
            by_column = {column: name for name, column in columns.items() if column}
            expected_columns = [item['name'] for item in gold['properties']]
            published = self.art['query'].get(key) or {}
            mapping_note = self._mapping_note(key)
            count = published.get('total')
            grain_ok = evidence.get('rows_observed') == gold['实例数'] and count == gold['实例数']
            source_ok = set(columns.values()) == set(expected_columns)
            if grain_ok and source_ok and evidence.get('grain'):
                self.results.ok(prefix, '粒度/来源/实例数与金标一致（%d 个实例）' % gold['实例数'])
            else:
                self.results.fail(prefix, '粒度/来源/实例数与金标不一致' + mapping_note)
            identity = set(evidence.get('identity_columns') or [])
            expected_identity = set(gold['身份']['fields'])
            if identity == expected_identity and len(identity) == len(gold['身份']['fields']):
                self.results.ok(prefix + '.identity', '身份字段集合与金标一致，复合身份未拆分')
            else:
                self.results.fail(prefix + '.identity', '身份字段集合与金标不一致')
            missing = [name for name in expected_columns if name not in by_column]
            if not missing and set(columns.values()) == set(expected_columns):
                self.results.ok(prefix + '.properties', '全部金标属性都由对应来源列支撑')
            else:
                self.results.fail(prefix + '.properties', '属性未覆盖全部金标来源列')
            type_failures, datetime_deviations = _compare_value_types(
                gold['properties'], by_column, definition.get('properties', {}))
            if datetime_deviations:
                self.deviations.append({
                    'check': prefix + '.types', 'gold': 'J6',
                    'note': '%d 个 date 属性的发布类型为 datetime（J6 允许，记偏差不判失败）'
                            % datetime_deviations,
                })
            if type_failures:
                self.results.fail(
                    prefix + '.types',
                    '值类型与金标不一致（%d 项）%s' % (len(type_failures), mapping_note))
            else:
                self.results.ok(prefix + '.types', '值类型与金标一致')
            forbidden = self._forbidden_concept(key, gold, evidence, definition, published)
            if forbidden:
                self.results.fail(prefix + '.forbidden', forbidden)
            else:
                self.results.ok(prefix + '.forbidden', '未出现金标禁止的身份、粒度或属性')
            if key == 'C1':
                self._score_unit(gold, evidence, definition)

    def _forbidden_concept(self, key, gold, evidence, definition, published):
        identity = set(evidence.get('identity_columns') or [])
        if key == 'C1':
            limit = next(item['name'] for item in gold['properties'] if item['value_type'] == 'decimal')
            if limit in identity:
                return '度量列被用作身份'
            if len(identity) != 3:
                return '身份不是三列组合'
            values = {row.get('values', {}).get(name) for row in (published.get('items') or [])
                      for name in [limit]}
            if not values:
                return '没有可核对的已发布实例'
        else:
            if len(identity) != 2:
                return '身份不是两列组合'
            amount = next((item['name'] for item in gold['properties']
                           if item['value_type'] == 'decimal'), None)
            if amount and amount in identity:
                return '度量列被用作身份'
            c1, _ = self._concept_evidence('C1')
            if c1 is not None and c1.get('table') == evidence.get('table'):
                return '两个概念来自同一张表，粒度被合并'
        source_columns = {item.get('column') for item in
                          (evidence.get('properties') or {}).values()}
        expected = {item['name'] for item in gold['properties']}
        if source_columns - expected:
            return '出现了来源表里没有的属性列'
        return ''

    def _score_unit(self, gold, evidence, definition):
        unit_property = next((item for item in gold['properties'] if item.get('unit')), None)
        if unit_property is None:
            self.results.fail('C1.unit', '金标未给出单位属性')
            return
        column = unit_property['name']
        name = next((key for key, item in (evidence.get('properties') or {}).items()
                     if item.get('column') == column), None)
        description = (definition.get('properties', {}).get(name) or {}).get('description', '') \
            if name else ''
        table = next((item for item in self.art['main']['request']['catalog']['tables']
                      if item['name'] == evidence.get('table')), None)
        source = self.sources.get(table.get('source_id')) if table else None
        clause, sentence = _unit_clause(self.art['main']['request']['catalog'],
                                        self.sources, table, column) if table else (None, '')
        cited = set((self.art['main'].get('draft') or {}).get('entities', [{}])[
            self._entity_index('C1')].get('evidence_sections') or [])
        paragraph = None
        for item in unit_property.get('evidence') or []:
            if isinstance(item.get('paragraph'), int):
                paragraph = item['paragraph']
        expected_ref = None
        if paragraph is not None:
            for clause_item in self.art['main']['request']['catalog'].get('documents', []):
                for entry in clause_item.get('clauses') or []:
                    if entry.get('paragraph') == paragraph + 1:
                        expected_ref = entry.get('ref')
        if sentence and sentence in description and expected_ref and expected_ref in cited:
            self.results.ok('C1.unit', '数值字段的单位口径写入了发布定义，草案引用了对应条款段落')
        else:
            self.results.fail('C1.unit', '数值字段的单位口径或条款段落引用缺失')

    def _entity_index(self, key):
        table = next((name for name, value in (self.art['main'].get('keys') or {}).items()
                      if value == key), None)
        for index, entity in enumerate((self.art['main'].get('draft') or {}).get('entities') or []):
            if entity.get('table') == table:
                return index
        return 0

    def _score_relation(self):
        artifact = self.art['main']
        candidate = artifact.get('candidate_body') or {}
        relations = (candidate.get('definition') or {}).get('relations') or {}
        evidence_relations = (candidate.get('evidence') or {}).get('relations') or {}
        catalog_links = {item['id']: item for item in
                         (artifact.get('request') or {}).get('catalog', {}).get('relationships', [])}
        gold_relations = list(self.gold.get('relations') or [])
        if not gold_relations:
            for key in ('R1', 'R1.join', 'R1.coverage', 'R1.forbidden'):
                self.results.fail(key, '金标没有关系期望')
            return
        if not relations:
            reason = '草案/候选没有关系（复合关联未由证据产出）'
            for key in ('R1', 'R1.join', 'R1.coverage', 'R1.forbidden'):
                self.results.fail(key, reason)
            return
        names = artifact.get('names') or {}
        by_key = {value: name for name, value in (artifact.get('keys') or {}).items()}
        c1 = names.get(by_key.get('C1'))
        c2 = names.get(by_key.get('C2'))
        if not c1 or not c2:
            for key in ('R1', 'R1.join', 'R1.coverage', 'R1.forbidden'):
                self.results.fail(key, '缺少 C1/C2 概念映射，无法核对关系')
            return
        specs = _relation_specs(relations, evidence_relations, catalog_links)
        checks = _relation_checks(specs, gold_relations, c1, c2)
        for key in ('R1', 'R1.join', 'R1.coverage', 'R1.forbidden'):
            passed, reason = checks[key]
            (self.results.ok if passed else self.results.fail)(key, reason)

    def _score_query(self):
        expectations = self.gold['query_expectations']
        q1_key = next((key for key in expectations if str(key).startswith('Q1')), None)
        expected = expectations.get(q1_key) or [] if q1_key else []
        if not expected:
            self.results.fail('Q1', '金标没有 Q1 期望')
            return
        evidence, _ = self._concept_evidence('C1')
        if not evidence:
            self.results.fail('Q1', '没有 C1 的候选证据')
            return
        by_column = {item.get('column'): name for name, item in
                     (evidence.get('properties') or {}).items()}
        filters = self.art['query'].get('C1_filters') or []
        exact = []
        for entry in filters:
            page = entry.get('page') or {}
            if not _filter_echo_ok(page, entry.get('where') or []):
                continue
            if page.get('total') != len(expected):
                continue
            matched = set()
            for item in page.get('items') or []:
                row = {column: item['values'].get(name)
                       for column, name in by_column.items() if name in item.get('values', {})}
                for index, wanted in enumerate(expected):
                    if _entry_matches(row, wanted):
                        matched.add(index)
            if len(matched) == len(expected):
                exact.append(entry)
        if exact:
            self.results.ok(
                'Q1',
                '属性条件查询（%d 项条件）命中金标 Q1 的全部实例，字段值一致'
                % len(exact[0]['where']))
        elif filters:
            self.results.fail(
                'Q1',
                '已下发 %d 组属性条件，但没有一组与金标 Q1 实例完全一致' % len(filters))
        else:
            self.results.fail('Q1', '没有下发属性过滤条件，无法覆盖属性条件查询路径')

    def _score_evidence(self):
        issues = []
        checked = 0
        for key in ('C1', 'C2'):
            page = self.art['query'].get(key)
            evidence, _ = self._concept_evidence(key)
            if not page or not evidence:
                issues.append('%s 无实例' % key)
                continue
            table = next((item for item in self.art['main']['request']['catalog']['tables']
                          if item['name'] == evidence.get('table')), None)
            if table is None:
                issues.append('%s 无来源表' % key)
                continue
            source = self.sources.get(table.get('source_id'))
            digest = self.digests.get(table.get('source_id'))
            if source is None:
                issues.append('%s 无来源文件' % key)
                continue
            by_column = {item.get('column'): name for name, item in
                         (evidence.get('properties') or {}).items()}
            for item in page.get('items') or []:
                for column, property_name in by_column.items():
                    anchors = (item.get('source_anchors') or {}).get(property_name) or []
                    if not anchors:
                        issues.append('missing')
                        continue
                    anchor = anchors[0]
                    if anchor.get('source_revision') != digest:
                        issues.append('digest')
                        continue
                    value = item.get('values', {}).get(property_name)
                    cell = source.cell(anchor.get('selector'))
                    checked += 1
                    if not _same_cell(value, cell):
                        issues.append('value')
        if not issues and checked:
            self.results.ok('E1', '%d 个属性锚点回放到同一值且绑定来源摘要' % checked)
        else:
            counts = {kind: issues.count(kind) for kind in ('missing', 'digest', 'value')}
            parts = []
            if counts['missing']:
                parts.append('缺少锚点 %d' % counts['missing'])
            if counts['digest']:
                parts.append('来源摘要不一致 %d' % counts['digest'])
            if counts['value']:
                parts.append('值与原文不一致 %d' % counts['value'])
            other = len(issues) - sum(counts.values())
            if other:
                parts.append('无实例或无来源 %d' % other)
            self.results.fail(
                'E1', '有锚点无法回放到同一值或来源摘要不一致（%d 处：%s）'
                % (max(1, len(issues)), '、'.join(parts)))

    def _value_overlap_pairs(self, tables):
        values = {}
        for name, table in tables.items():
            source = self.sources.get(table.get('source_id'))
            if source is None:
                continue
            table_name = table['name']
            if not source.matrix(table_name, table.get('partition')) and source.rows:
                table_name = next(iter(source.rows))
            values[name] = source.column_values(table_name, table.get('partition'),
                                                list(table['columns']))
        pairs = []
        names = list(values)
        for index, left in enumerate(names):
            for right in names[index + 1:]:
                for left_col, left_values in values[left].items():
                    left_set = {str(value) for value in left_values if value is not None}
                    for right_col, right_values in values[right].items():
                        right_set = {str(value) for value in right_values if value is not None}
                        if left_set & right_set:
                            pairs.append((left, left_col, right, right_col))
        return pairs

    def _score_n3(self):
        artifact = self.art['n3']
        if artifact.get('error'):
            self.results.fail('N3', '值重合反例未完成')
            self.results.fail('N3.evidence', '值重合反例未完成')
            self.results.fail('N3.gate', '错误跨来源关系处置门禁未执行')
            return
        draft = artifact.get('draft') or {}
        candidate = artifact.get('candidate_body') or artifact.get('candidate') or {}
        definition = candidate.get('definition') or {}
        tables = artifact.get('tables') or {}
        links = (artifact.get('request') or {}).get('catalog', {}).get('relationships') or []
        overlap = [link for link in links
                   if link.get('source_table') in tables and link.get('target_table') in tables]
        value_overlap = self._value_overlap_pairs(tables)
        relations = definition.get('relations') or {}
        concepts = definition.get('concepts') or {}
        sources = {name: (candidate.get('evidence') or {}).get('concepts', {}).get(name, {}).get('table')
                   for name in concepts}
        merged = len(set(sources.values())) != len(sources)
        published = artifact.get('entry') is not None
        if overlap:
            unresolved = {str(item.get('id')) for item in draft.get('unresolved_relationships') or []}
            excluded = {(item.get('kind'), item.get('ref')) for item in candidate.get('dispositions') or []}
            adopted = any(item.get('evidence_id') in {link['id'] for link in overlap}
                          for item in relations.values())
            if all(str(link['id']) in unresolved for link in overlap) \
                    and all(('unresolved_relationship', str(link['id'])) in excluded for link in overlap) \
                    and not adopted:
                self.results.ok('N3.evidence', '值重合候选被标为待核对/否决，未进入关系')
                self.results.ok('N3.gate', '错误跨来源关系候选被草案待决并在发布前排除')
            else:
                self.results.fail('N3.evidence', '值重合候选未被显式处置')
                self.results.fail('N3.gate', '错误跨来源关系候选未被待决或排除')
        else:
            # J8 allows the evidence layer to produce no value-overlap
            # candidate at all.  N3 then only requires that no wrong relation
            # was adopted and that the two sources stayed independent; the
            # disposition gate has nothing to exercise and is not applicable
            # instead of failed.
            if relations:
                self.results.fail('N3.evidence', '证据层未生成值重合候选，但草案/发布采纳了跨来源关系')
            elif value_overlap:
                self.results.ok('N3.evidence',
                                '源值存在重合，但证据层未生成关系候选（金标 J8 允许）；'
                                '草案与发布未采纳跨来源关系')
            else:
                self.results.ok('N3.evidence',
                                '证据层未生成值重合关系候选（金标 J8 允许）；草案与发布未采纳跨来源关系')
            reason = ('本次没有值重合关系候选，错误关系处置门禁未触发；'
                      '金标 J8 允许证据层无候选，记为 not_applicable')
            self.results.na('N3.gate', reason)
            artifact['gate_unverified'] = True
        if not relations and len(concepts) == 2 and not merged and published:
            if overlap:
                self.results.ok('N3', '第三个来源为独立概念，草案/已发布本体无跨来源关系')
            else:
                self.results.ok(
                    'N3', '证据层未生成值重合关联，草案与发布未采纳错误关系，来源未合并')
        elif not relations and len(concepts) == 2 and not merged:
            self.results.fail('N3', '值重合反例的对象未合并，但本次没有完成发布')
        else:
            self.results.fail('N3', '第三个来源被合并或出现跨来源关系')

    # ------------------------------------------------------------------- run
    def run(self):
        self.prepare_sources()
        self.stage_n1()
        self.stage_main()
        self.stage_candidate()
        self.stage_n4_n5()
        self.stage_n3()
        self.stage_publish()
        self.stage_mapping()
        self.stage_retire()
        self.stage_n2()


def _payload(exc):
    """The workbench payload carried by an exception.

    ``call_workbench`` raises ``AssertionError`` with either the raw MCP
    response envelope (``content[0].text`` is the JSON tool payload) or, on a
    failed result file, its issue list.  Callers need the payload itself:
    keeping the transport frame here made every mapping refusal look like
    ``invalid_input`` and hid the workbench's issue codes and reasons.
    """
    argument = exc.args[0] if exc.args else None
    if isinstance(argument, list):
        return {'issues': [item for item in argument if isinstance(item, dict)]}
    if not isinstance(argument, dict):
        return {}
    content = argument.get('content')
    if isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                continue
            text = block.get('text')
            if not isinstance(text, str):
                continue
            try:
                inner = json.loads(text)
            except ValueError:
                continue
            if isinstance(inner, dict):
                return inner
            if isinstance(inner, list):
                return {'issues': [item for item in inner if isinstance(item, dict)]}
    return argument


def _code(payload):
    if not isinstance(payload, dict):
        return 'unknown'
    return str(payload.get('error') or payload.get('code') or 'invalid_input')


def _detail(payload):
    if not isinstance(payload, dict):
        return ''
    return str(payload.get('detail') or '')


# The workbench's exact wordings for "the source changed since it was
# observed" (dataagent-workbench ontology_publish).  They are matched as
# whole phrases: a fuzzy "mentions source and something snapshot-ish" test
# also accepted ``source snapshot reference is missing``, which is a
# different defect and must fail N2.
_SOURCE_CHANGE_DETAILS = (
    'source changed since it was observed',
    'source snapshot changed',
    'source structure changed',
    'source observation changed',
    '来源已变更',
    '来源已变化',
)


def _is_source_change_rejection(payload):
    """Whether a refused confirmation names the source snapshot change.

    Only the exact change wordings above count.  A refusal for a stale
    candidate, a task-revision mismatch, a missing snapshot reference or an
    unreadable source is a different gate and must not pass N2.
    """
    text = _detail(payload).casefold()
    return any(phrase in text for phrase in _SOURCE_CHANGE_DETAILS)


def _issue_reasons(payload, limit=4):
    """The workbench's stable issue code plus its Chinese reason.

    Object labels and row numbers are deliberately dropped: the report must
    stay free of sample values while still naming what the save was blocked on.
    For an unknown code the workbench may have copied the raw exception detail
    into ``reason``; only the code is reported then, never the exception text.
    """
    reasons = []
    issues = payload.get('issues') if isinstance(payload, dict) else None
    for issue in issues or []:
        if not isinstance(issue, dict):
            continue
        code = str(issue.get('code') or '').strip()
        # Only the workbench's own summary reason is copied.  Raw ``detail``
        # can carry an exception string or a source value, so it never enters
        # the report; an unknown code gets a fixed placeholder instead.
        reason = str(issue.get('reason') or '').strip() if code in _KNOWN_ISSUE_CODES else ''
        if not reason:
            reason = '（未知问题码，原因未展示）' if code else '（未提供问题码）'
        text = ('%s %s' % (code, reason)).strip()
        if not text or text in reasons:
            continue
        reasons.append(text)
        if len(reasons) >= limit:
            break
    return reasons


def _number_text(value):
    if isinstance(value, str):
        text = value.strip()
        # Only a well-formed grouped number loses its thousands separators;
        # arbitrary text must still fail the decimal comparison.
        if _GROUPED_NUMBER.fullmatch(text):
            return text.replace(',', '')
    return str(value)


def _same_number(left, right):
    try:
        return Decimal(_number_text(left)) == Decimal(_number_text(right))
    except (InvalidOperation, ValueError):
        return False


def _is_number(value):
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float, Decimal)):
        return True
    if isinstance(value, str):
        text = value.strip()
        return bool(_NUMBER.fullmatch(text) or _GROUPED_NUMBER.fullmatch(text))
    return False


def _canonical_temporal(value):
    """Collapse the midnight form of a calendar value to its date.

    The Excel reader hands a date-only cell over as ``YYYY-MM-DDT00:00:00``
    while a mapped ``date`` property stores ``YYYY-MM-DD``; both denote the
    same cell value, so anchor replay compares them as one value.  A real time
    part is preserved.
    """
    if isinstance(value, datetime):
        return value.date().isoformat() if value.time() == time(0, 0) else value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        text = value.strip()
        if _DATETIME.fullmatch(text):
            try:
                parsed = datetime.fromisoformat(text)
            except ValueError:
                return value
            if parsed.time() == time(0, 0):
                return parsed.date().isoformat()
            return parsed.isoformat()
    return value


def _same_cell(value, cell):
    if cell is None:
        return False
    left = _canonical_temporal(value)
    right = _canonical_temporal(cell)
    if _is_number(left) or _is_number(right):
        return _same_number(left, right)
    return str(left) == str(right)


def _is_temporal_like(value):
    if isinstance(value, (date, datetime)):
        return True
    return isinstance(value, str) and bool(
        _DATE.fullmatch(value.strip()) or _DATETIME.fullmatch(value.strip()))


def _item_ids(page):
    if not isinstance(page, dict):
        return set()
    ids = set()
    for item in page.get('items') or []:
        key = item.get('id') or item.get('instance_id')
        if key is None:
            key = json.dumps(item.get('values') or {}, sort_keys=True, ensure_ascii=False)
        ids.add(str(key))
    return ids


def _filter_echo_ok(page, where):
    """The page echoes exactly the attribute conditions that were sent.

    Guards the Q1 check against a tool that ignores ``where`` and returns the
    whole concept; every returned instance must also satisfy the predicate.
    """
    if not isinstance(page, dict) or not where:
        return False
    echoed = page.get('filters') or []
    if len(echoed) != len(where):
        return False
    for condition in where:
        if not any(str(item.get('property')) == str(condition.get('property'))
                   and str(item.get('op')) == str(condition.get('op'))
                   and str(item.get('value')) == str(condition.get('value'))
                   for item in echoed if isinstance(item, dict)):
            return False
    for item in page.get('items') or []:
        values = item.get('values') or {}
        for condition in where:
            if str(values.get(condition.get('property'))) != str(condition.get('value')):
                return False
    return True


def _entry_matches(row, entry):
    for key, value in entry.items():
        if key in {'evidence', 'cell'}:
            continue
        actual = row.get(key)
        if _is_number(value):
            if not _same_number(actual, value):
                return False
        elif _is_temporal_like(actual) or _is_temporal_like(value):
            # A calendar value can arrive as ``YYYY-MM-DD`` or as its
            # midnight ``YYYY-MM-DDT00:00:00`` form; both are the same day.
            if _canonical_temporal(actual) != _canonical_temporal(value):
                return False
        elif str(actual) != str(value):
            return False
    return True


def apply(report, project, args, context):
    """Run the D7 phase and attach its checks to the report."""
    results = Results()
    gold_dir = os.environ.get(GOLD_ENV, '').strip()
    if not gold_dir:
        report['status'] = 'skipped'
        report['setup_error'] = True
        report['reason'] = '%s is not set' % GOLD_ENV
        report['checks'] = []
        report['summary'] = {'total': 0, 'passed': 0, 'failed': 0,
                             'not_applicable': 0, 'not_applicable_ids': [],
                             'pass_rate': 0.0, 'pass_rate_percent': 0.0,
                             'required_failed': []}
        return
    try:
        inputs = _inputs(gold_dir)
    except SetupError as exc:
        report['status'] = 'skipped'
        report['setup_error'] = True
        report['reason'] = str(exc)
        report['checks'] = []
        report['summary'] = {'total': 0, 'passed': 0, 'failed': 0,
                             'not_applicable': 0, 'not_applicable_ids': [],
                             'pass_rate': 0.0, 'pass_rate_percent': 0.0,
                             'required_failed': []}
        return
    try:
        with _service(project) as http:
            flow = Flow(project, http, inputs, results, args)
            flow.run()
        try:
            gold = json.loads((inputs.root / 'gold.json').read_text(encoding='utf-8'))
        except (OSError, ValueError) as exc:
            raise SetupError('gold.json is not readable') from exc
        flow.score(gold)
        if flow.deviations:
            report['deviations'] = flow.deviations
        if flow.art.get('n3', {}).get('gate_unverified'):
            report.setdefault('not_verified', []).append(
                'N3 wrong cross-source relationship disposition gate '
                '(not applicable: the evidence layer produced no candidate)')
    except SetupError as exc:
        report['status'] = 'failed'
        report['setup_error'] = True
        report['reason'] = str(exc)
        results.pending('环境不可用：%s' % type(exc).__name__)
    except Exception as exc:  # noqa: BLE001 - report-only must not hide a crash
        report['status'] = 'failed'
        report['script_error'] = type(exc).__name__
        report['reason'] = '脚本异常：%s' % type(exc).__name__
        results.pending('脚本异常：%s' % type(exc).__name__)
    for row in results.rows.values():
        if row['reason'] == '尚未执行':
            row['status'] = 'fail'
            row['reason'] = '本阶段未执行到该检查'
    checks = results.checks()
    summary = results.summary()
    report['checks'] = checks
    report['summary'] = summary
    report['status'] = 'passed' if summary['failed'] == 0 and not report.get('script_error') \
        and not report.get('setup_error') else ('failed' if not report.get('setup_error') else 'skipped')
    report['not_verified'] = [item for item in report.get('not_verified', [])
                              if item != 'model-generated ontology proposal'] + [
        'model-generated proposal quality (the proposal is scripted from evidence)',
        'browser UI rendering',
    ]
    report['gold'] = {'path_env': GOLD_ENV,
                      'entries': sorted({ref for item in checks for ref in item.get('gold') or []})}
