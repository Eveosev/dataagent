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
from datetime import date, datetime, timedelta
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
    ('N4', True, ['N4']),
    ('N4.property', True, ['N4']),
    ('N4.relation', True, ['N4']),
    ('N5', True, ['N5']),
    ('N6', True, ['N6']),
    ('N7', True, ['D1']),
    ('N8', True, ['D1']),
]

_NUMBER = re.compile(r'-?\d+(?:\.\d+)?')
_DATE = re.compile(r'\d{4}-\d{2}-\d{2}')
_DATETIME = re.compile(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?')
_CELL = re.compile(r'^([A-Z]+)(\d+)$')
_UNIT_CELL = re.compile(r'^table:(\d+)/row:(\d+)/col:(\d+)$')

_DATE_FMT_IDS = set(range(14, 23)) | set(range(27, 37)) | set(range(45, 48)) | set(range(50, 59))

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
        required_failed = [item['id'] for item in checks
                           if item['required'] and item['status'] == 'fail']
        return {
            'total': total, 'passed': passed, 'failed': failed,
            'pass_rate': round(passed / total, 4) if total else 0.0,
            'pass_rate_percent': round(100.0 * passed / total, 1) if total else 0.0,
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


class Flow:
    def __init__(self, project, http, inputs, results, args):
        self.project = project
        self.http = http
        self.inputs = inputs
        self.results = results
        self.args = args
        self.sources = {}
        self.paths = {}
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
    def plan_for(self, request, source_ids):
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
            if _relation_affine(link):
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
        except Exception as exc:  # noqa: BLE001 - a check, not a crash
            artifact['error'] = type(exc).__name__
            self.results.fail('N1', '无可靠标识链路未完成（%s）' % type(exc).__name__)
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
        except Exception as exc:  # noqa: BLE001
            artifact['error'] = type(exc).__name__
            self.results.fail('CHAIN.discovery', '发现链路未完成（%s）' % type(exc).__name__)
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
                                  '候选已生成，等待网页人工确认（补全模式 %s）' % artifact['mode'])
            else:
                self.results.fail('CHAIN.publish', '候选状态不是等待人工确认')
        except ToolRejected as exc:
            artifact['error'] = 'tool'
            self.results.fail('CHAIN.publish', '补全被工具拒绝（%s）' % _code(exc.payload))
        except Exception as exc:  # noqa: BLE001
            artifact['error'] = type(exc).__name__
            self.results.fail('CHAIN.publish', '补全未完成（%s）' % type(exc).__name__)

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
        try:
            tampered = self.completion_for(draft, plan, names, types, units, 'expense-policy',
                                           limit_string=artifact.get('mode') == 'fallback',
                                           extra_property='__unobserved_attribute__')
            payload = self.rejected('ontology_publish_prepare', tampered)
            if payload is None:
                self.results.fail('N4.property', '虚构属性仍生成了候选')
            else:
                self.results.ok('N4.property', '虚构属性被发布前校验拒绝')
        except Exception as exc:  # noqa: BLE001
            self.results.fail('N4.property', '虚构属性校验未完成（%s）' % type(exc).__name__)
        try:
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
        except Exception as exc:  # noqa: BLE001
            self.results.fail('N4.relation', '无证据关系校验未完成（%s）' % type(exc).__name__)
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
        except Exception as exc:  # noqa: BLE001
            self.results.fail('N5', 'Agent 工具确认未完成（%s）' % type(exc).__name__)

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
            plan, names, types, units = self.plan_for(request, ['lines', 'n3'])
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
        except Exception as exc:  # noqa: BLE001
            artifact['error'] = type(exc).__name__
            self.results.fail('N3', '值重合反例链路未完成（%s）' % type(exc).__name__)

    def stage_publish(self):
        artifact = self.art['main']
        if not artifact.get('candidate1') or not artifact.get('draft'):
            self.results.fail('N6', '没有 r1 候选')
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
        except Exception as exc:  # noqa: BLE001
            artifact['error'] = type(exc).__name__
            self.results.fail('CHAIN.review', '草案 r2 提案/审核未完成（%s）' % type(exc).__name__)
            self.results.fail('N6', 'r2 候选未完成（%s）' % type(exc).__name__)
            return
        try:
            # The candidate endpoint returns the current candidate; the
            # first attempt is recovered from its recorded summary.
            stale_status, stale_body = self.http.request(
                'POST', '/api/sessions/%s/publish/confirm' % artifact['session'], {
                    'candidate_ref': artifact['candidate1'].get('candidate_ref'),
                    'draft_ref': draft['ref'],
                    'source_snapshot': artifact['candidate1']['source_snapshot'],
                    'definition_digest': artifact['candidate1']['definition_digest'],
                    'expected_revision': artifact['candidate1']['session_revision'],
                    'confirmed': True, 'reason': 'D7 N6 stale confirmation',
                })
            artifact['stale'] = (stale_status, stale_body)
            c2 = self.candidate(artifact['session'])
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
            stale_ok = stale_status == 409
            duplicate_ok = again_status == 409 or (
                again_status == 200 and again_body.get('publication_ref') == published.get('publication_ref'))
            if stale_ok and duplicate_ok and entry is not None \
                    and entry.get('ontology_revision') == '1':
                self.results.ok('N6', '过期候选被拒，重复确认被拒或幂等，只有一个本体修订')
            else:
                self.results.fail('N6', '过期/重复确认或修订数不符合要求')
        except ToolRejected as exc:
            self.results.fail('N6', '确认链路被工具拒绝（%s）' % _code(exc.payload))
        except HttpError as exc:
            artifact['publish_error'] = (exc.status, _code(exc.payload))
            self.results.fail('N6', 'HTTP 确认失败（状态 %s）' % exc.status)
            self.results.fail('CHAIN.publish', 'HTTP 确认失败（状态 %s）' % exc.status)
        except Exception as exc:  # noqa: BLE001
            artifact['publish_error'] = type(exc).__name__
            self.results.fail('N6', '确认链路未完成（%s）' % type(exc).__name__)
            self.results.fail('CHAIN.publish', '发布未完成（%s）' % type(exc).__name__)

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
                self.art['mapping'][key] = {'error': _code(exc.payload)}
            except Exception as exc:  # noqa: BLE001
                self.art['mapping'][key] = {'error': type(exc).__name__}
        mapped = [item for item in self.art['mapping'].values()
                  if item.get('receipt') and not item.get('issue_count')]
        if len(mapped) == 2:
            self.results.ok('CHAIN.mapping', '两个概念分别映射并保存成功')
        else:
            self.results.fail('CHAIN.mapping', '映射保存未全部成功')
        self._query()

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
            elif kind == 'datetime':
                binding['options'] = {'timezone': 'UTC'}
        return binding

    def _query(self):
        collected = {}
        for key, concept in (('C1', self.art['mapping']['C1']), ('C2', self.art['mapping']['C2'])):
            if not concept.get('receipt'):
                continue
            try:
                page = self.call('ontology_query', {
                    'ontology_id': 'expense-policy',
                    'concept': self.art['main']['names'].get(
                        next((name for name, value in (self.art['main'].get('keys') or {}).items()
                              if value == key), None)),
                    'limit': 200,
                })
                collected[key] = page
            except ToolRejected:
                collected[key] = None
            except Exception:  # noqa: BLE001
                collected[key] = None
        self.art['query'] = collected
        if collected.get('C1') and collected.get('C2') \
                and collected['C1']['total'] and collected['C2']['total']:
            self.results.ok('CHAIN.query', '两个概念均从已发布快照查到实例')
        else:
            self.results.fail('CHAIN.query', '按本体查询未返回已发布实例')

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
                    except Exception:  # noqa: BLE001
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
            if updated and updated.get('state') == 'retired' \
                    and listing.get('default_ontology') == 'procurement' \
                    and old_target and old_target.get('ontology_id') == 'expense-policy' \
                    and old_queries_ok:
                self.results.ok('N7', '停用后新任务回退内置本体，旧任务目标与已发布快照保持')
            else:
                self.results.fail('N7', '停用后的回退或旧任务行为不符合要求')
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
        except Exception as exc:  # noqa: BLE001
            self.results.fail('N7', '停用链路未完成（%s）' % type(exc).__name__)
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
            if status == 422 and artifact['entry_after'] is None \
                    and artifact.get('digest_changed'):
                self.results.ok('N2', '来源快照已变时确认被拒，未写本体修订，指针未变')
            else:
                self.results.fail('N2', '来源变更后的确认未被正确拒绝')
        except ToolRejected as exc:
            artifact['error'] = _code(exc.payload)
            self.results.fail('N2', '来源变更反例被工具拒绝（%s）' % _code(exc.payload))
        except Exception as exc:  # noqa: BLE001
            artifact['error'] = type(exc).__name__
            self.results.fail('N2', '来源变更反例未完成（%s）' % type(exc).__name__)
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
        except Exception as exc:  # noqa: BLE001
            self.results.fail('N2.rediscover', '重新探查未完成（%s）' % type(exc).__name__)

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
            count = published.get('total')
            grain_ok = evidence.get('rows_observed') == gold['实例数'] and count == gold['实例数']
            source_ok = set(columns.values()) == set(expected_columns)
            if grain_ok and source_ok and evidence.get('grain'):
                self.results.ok(prefix, '粒度/来源/实例数与金标一致（%d 个实例）' % gold['实例数'])
            else:
                self.results.fail(prefix, '粒度/来源/实例数与金标不一致')
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
            type_failures = []
            for item in gold['properties']:
                name = by_column.get(item['name'])
                if name is None or name not in definition.get('properties', {}):
                    type_failures.append('missing')
                    continue
                actual = definition['properties'][name].get('value_type')
                expected = item['value_type']
                if expected == 'date' and actual in {'date', 'datetime'}:
                    continue
                if actual != expected:
                    type_failures.append('%s->%s' % (expected, actual))
            if type_failures:
                self.results.fail(prefix + '.types', '值类型与金标不一致（%d 项）' % len(type_failures))
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
            self.results.ok('C1.unit', '限额单位口径写入了发布定义，草案引用了对应条款段落')
        else:
            self.results.fail('C1.unit', '限额单位口径或条款段落引用缺失')

    def _entity_index(self, key):
        table = next((name for name, value in (self.art['main'].get('keys') or {}).items()
                      if value == key), None)
        for index, entity in enumerate((self.art['main'].get('draft') or {}).get('entities') or []):
            if entity.get('table') == table:
                return index
        return 0

    def _score_relation(self):
        artifact = self.art['main']
        draft = artifact.get('draft') or {}
        candidate = artifact.get('candidate_body') or {}
        relations = (candidate.get('definition') or {}).get('relations') or {}
        evidence_relations = (candidate.get('evidence') or {}).get('relations') or {}
        catalog_links = {item['id']: item for item in
                         (artifact.get('request') or {}).get('catalog', {}).get('relationships', [])}
        gold = self.gold['relations'][0]
        if not relations:
            reason = '草案/候选没有关系（复合关联未由证据产出）'
            for key in ('R1', 'R1.join', 'R1.coverage', 'R1.forbidden'):
                self.results.fail(key, reason)
            return
        name, definition = next(iter(relations.items()))
        evidence = evidence_relations.get(name) or {}
        link = catalog_links.get(evidence.get('evidence_id')) or {}
        by_key = {value: name for name, value in (artifact.get('keys') or {}).items()}
        c1 = artifact['names'].get(by_key.get('C1'))
        c2 = artifact['names'].get(by_key.get('C2'))
        if definition.get('subject_concept') == c2 and definition.get('object_concept') == c1:
            self.results.ok('R1', '关系端点为明细→标准，方向正确')
        else:
            self.results.fail('R1', '关系端点或方向与金标不一致')
        pairs = list(zip(evidence.get('source_columns') or [], evidence.get('target_columns') or []))
        expected_pairs = [tuple(pair) for pair in gold['join']]
        if sorted(pairs) == sorted(expected_pairs):
            self.results.ok('R1.join', '三列连接字段一一对应')
        else:
            self.results.fail('R1.join', '连接字段不是金标的三列组合')
        coverage = gold['coverage']
        if link.get('matched_rows') == 16 and link.get('checked_rows') == 20 \
                and link.get('matched_distinct_keys') == 12:
            self.results.ok('R1.coverage', '覆盖 16/20，标准端 12/12')
        else:
            self.results.fail('R1.coverage', '覆盖不是 16/20 或标准端不是 12/12')
        forbidden = ''
        if len(pairs) != 3:
            forbidden = '连接不是三列组合'
        elif definition.get('subject_concept') == c1 and definition.get('object_concept') == c2:
            forbidden = '方向反过来'
        elif link.get('matched_rows') == link.get('checked_rows'):
            forbidden = '声称 100% 匹配'
        if forbidden:
            self.results.fail('R1.forbidden', forbidden)
        else:
            self.results.ok('R1.forbidden', '未出现单列/反向/100% 匹配')

    def _score_query(self):
        gold = self.gold['query_expectations']
        expected = gold.get('Q1 列出一类城市住宿标准') or []
        page = self.art['query'].get('C1')
        evidence, _ = self._concept_evidence('C1')
        if not expected:
            self.results.fail('Q1', '金标没有 Q1 期望')
            return
        if not page or not evidence:
            self.results.fail('Q1', '没有 C1 的已发布查询结果')
            return
        by_column = {item.get('column'): name for name, item in
                     (evidence.get('properties') or {}).items()}
        matched = []
        for item in page.get('items') or []:
            row = {column: item['values'].get(name)
                   for column, name in by_column.items() if name in item.get('values', {})}
            for entry in expected:
                same = True
                for key, value in entry.items():
                    if key == 'evidence':
                        continue
                    actual = row.get(key)
                    if key == '限额':
                        if not _same_number(actual, value):
                            same = False
                    elif str(actual) != str(value):
                        same = False
                if same:
                    matched.append((item, row))
                    break
        found = set()
        for _, row in matched:
            for entry in expected:
                if all(_same_number(row.get(key), value) if key == '限额'
                       else str(row.get(key)) == str(value)
                       for key, value in entry.items() if key != 'evidence'):
                    found.add(str(entry.get('职级')))
        if len(matched) == len(expected) and len(found) == len(expected):
            self.results.ok('Q1', '查询返回两类城市住宿标准，限额值符合金标')
        else:
            self.results.fail('Q1', '查询结果与金标 Q1 不一致')

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
            self.results.fail('E1', '有锚点无法回放到同一值或来源摘要不一致（%d 处）' % max(1, len(issues)))

    def _score_n3(self):
        artifact = self.art['n3']
        if artifact.get('error'):
            self.results.fail('N3', '值重合反例未完成')
            self.results.fail('N3.evidence', '值重合反例未完成')
            return
        draft = artifact.get('draft') or {}
        candidate = artifact.get('candidate_body') or artifact.get('candidate') or {}
        definition = candidate.get('definition') or {}
        tables = artifact.get('tables') or {}
        links = (artifact.get('request') or {}).get('catalog', {}).get('relationships') or []
        overlap = [link for link in links
                   if link.get('source_table') in tables and link.get('target_table') in tables]
        if overlap:
            unresolved = {str(item.get('id')) for item in draft.get('unresolved_relationships') or []}
            excluded = {(item.get('kind'), item.get('ref')) for item in candidate.get('dispositions') or []}
            adopted = any(item.get('evidence_id') in {link['id'] for link in overlap}
                          for item in (definition.get('relations') or {}).values())
            if all(str(link['id']) in unresolved for link in overlap) \
                    and all(('unresolved_relationship', str(link['id'])) in excluded for link in overlap) \
                    and not adopted:
                self.results.ok('N3.evidence', '值重合候选被标为待核对/否决，未进入关系')
            else:
                self.results.fail('N3.evidence', '值重合候选未被显式处置')
        else:
            self.results.ok('N3.evidence', '证据层没有值重合候选（允许），草案未采纳')
        relations = definition.get('relations') or {}
        concepts = definition.get('concepts') or {}
        sources = {name: (candidate.get('evidence') or {}).get('concepts', {}).get(name, {}).get('table')
                   for name in concepts}
        merged = len(set(sources.values())) != len(sources)
        if not relations and len(concepts) == 2 and not merged and artifact.get('entry'):
            self.results.ok('N3', '保修工单为独立概念，草案/已发布本体无跨来源关系')
        else:
            self.results.fail('N3', '保修工单被合并或出现跨来源关系')

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
    if exc.args and isinstance(exc.args[0], dict):
        return exc.args[0]
    return {}


def _code(payload):
    if not isinstance(payload, dict):
        return 'unknown'
    return str(payload.get('error') or payload.get('code') or 'invalid_input')


def _same_number(left, right):
    try:
        return Decimal(str(left)) == Decimal(str(right))
    except (InvalidOperation, ValueError):
        return False


def _same_cell(value, cell):
    if cell is None:
        return False
    if isinstance(cell, datetime):
        cell = cell.date().isoformat()
    elif isinstance(cell, date):
        cell = cell.isoformat()
    if isinstance(value, (int, float, Decimal)) or (isinstance(value, str) and _NUMBER.fullmatch(value)):
        return _same_number(value, cell)
    return str(value) == str(cell)


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
