"""Document probe retains successful pages and explicit OCR/coverage gaps.

PDF pages and Word body blocks are both exposed as ``SourceProfile``
partitions. Word anchors are character spans inside stable unit refs:
``paragraph:<n>`` for a body paragraph and
``table:<t>/row:<r>/col:<c>`` for a table cell (all 1-based).  Merged cells
are expanded; an expanded cell keeps the anchor of the cell that owns the
value, and the merge geometry is reported in metadata.
"""
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile
from dataagent_contracts.core.refs import SourceAnchor
from dataagent_contracts.intake import CoverageGap
from ..adapters.parsers.excel import dedupe_names
from ..adapters.parsers.pdf import parse_pdf


_DOCX_MAX_EXPANDED_BYTES = 256 * 1024 * 1024
_DOCX_MAX_ENTRIES = 10_000


def probe_document(path, source_id, revision, *, engine=None, max_pages=200):
    """Dispatch a document snapshot to the Word or PDF probe."""
    if Path(path).suffix.lower() == ".docx":
        return probe_docx(path, source_id, revision)
    return _probe_pdf(path, source_id, revision, engine=engine, max_pages=max_pages)


def _probe_pdf(path, source_id, revision, *, engine=None, max_pages=200):
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        total = len(pdf.pages)
    selected = min(total,max_pages)
    content, issues = parse_pdf(path,page_range=f'1-{selected}')
    records, anchors, pages, completed, gaps, tables = [], {}, [], [], [], []
    with pdfplumber.open(path) as pdf:
        for page in content.pages:
            text, method, blocks = page.text, 'text', []
            if not text.strip() and engine is not None:
                try:
                    image=pdf.pages[page.page-1].to_image(resolution=144).original
                    buffer=io.BytesIO();image.save(buffer,format='PNG')
                    blocks=engine.recognize(buffer.getvalue(),lang=None)
                    text='\n'.join(b.text for b in blocks)
                    method='ocr'
                except Exception as exc:
                    gaps.append(CoverageGap(partition=page.page,code='ocr_failed',detail=type(exc).__name__))
            block_evidence = []
            if method == 'text':
                block_evidence = [b.model_dump(mode='json') for b in page.blocks]
            else:
                offset = 0
                for block in blocks:
                    end = offset + len(block.text)
                    if block.bbox:
                        block_evidence.append({'text': block.text, 'bbox': [float(x)/2 for x in block.bbox],
                                               'char_start': offset, 'char_end': end})
                    offset = end + 1
            pages.append({'page':page.page,'text':text,'method':method,
                'width':page.width,'height':page.height,
                'blocks':block_evidence,
                'extractor':getattr(engine,'engine_version','pdfplumber') if method=='ocr' else 'pdfplumber'})
            if not text.strip():
                if not any(g.partition==page.page for g in gaps):
                    gaps.append(CoverageGap(partition=page.page,code='ocr_engine_missing' if engine is None else 'ocr_empty'))
                continue
            completed.append(page.page)
            record, spans = {}, {}
            for match in re.finditer(r'^\s*([^:\n：]{1,80})\s*[:：]\s*(.+?)\s*$',text,re.M):
                key=match[1].strip()
                if key in record:
                    issues.append({'code':'intake.repeated_label','page':page.page,'field':key})
                    continue
                record[key]=match[2]
                spans[key]=(match.start(2),match.end(2))
            if not record:
                record={'text':text};spans={'text':(0,len(text))}
            has_tables=False
            if method=='text':
                try:
                    from ..adapters.parsers.excel import dedupe_names
                    for table in pdf.pages[page.page-1].find_tables():
                        rows=table.extract()
                        tables.append({'page':page.page,'rows':rows,'bbox':list(table.bbox),
                            'anchor':SourceAnchor(source_ref=source_id,source_revision=revision,
                                selector={'kind':'pdf_bbox','page':page.page,'bbox':table.bbox}).model_dump(mode='json')})
                        if not rows or len(rows)<2:continue
                        fields=dedupe_names([str(v or '') for v in rows[0]])
                        for rownum,row in enumerate(rows[1:],1):
                            if not any(v is not None for v in row):continue
                            index=len(records);records.append(dict(zip(fields,row)))
                            has_tables=True
                            for col,field in enumerate(fields):
                                box=table.rows[rownum].cells[col]
                                if box is not None:
                                    anchors[f'{index}.{field}']=[SourceAnchor(source_ref=source_id,source_revision=revision,
                                        selector={'kind':'pdf_bbox','page':page.page,'bbox':box})]
                except Exception as exc:
                    issues.append({'code':'intake.table_probe_failed','page':page.page,'detail':type(exc).__name__})
            if not has_tables or 'text' not in record:
                index=len(records);records.append(record)
                for key,(start,end) in spans.items():
                    anchors[f'{index}.{key}']=[SourceAnchor(source_ref=source_id,source_revision=revision,
                        selector={'kind':'pdf_text_span','page':page.page,'char_start':start,'char_end':end})]
            if method=='ocr' and any(getattr(b,'confidence',0)<.6 for b in blocks):
                issues.append({'code':'intake.low_ocr_confidence','page':page.page})
    if selected < total:
        gaps.append(CoverageGap(partition=f'{selected+1}-{total}',code='page_budget_exceeded'))
    return records,anchors,{'pages':pages,'tables':tables,'total_pages':total},completed,gaps,issues


def _check_docx_archive(path):
    """Reject non-zip and non-Word containers before python-docx reads them."""
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            names = {info.filename for info in infos}
            expanded = sum(info.file_size for info in infos)
    except (OSError, zipfile.BadZipFile) as exc:
        raise ValueError('not a valid .docx file (expected a zip archive)') from exc
    if '[Content_Types].xml' not in names or 'word/document.xml' not in names:
        raise ValueError('not a valid .docx file (missing Word document parts)')
    if len(infos) > _DOCX_MAX_ENTRIES or expanded > _DOCX_MAX_EXPANDED_BYTES:
        raise ValueError('expanded .docx exceeds probe limit')


def _iter_body_blocks(document):
    """Yield body paragraphs and tables in document order.

    Headers and footers live outside ``w:body`` and are intentionally ignored.
    Content controls are unwrapped so their paragraphs/tables keep their
    document-order numbering.
    """
    from docx.oxml.ns import qn
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    def walk(parent):
        for child in parent.iterchildren():
            if child.tag == qn('w:p'):
                yield 'paragraph', Paragraph(child, document)
            elif child.tag == qn('w:tbl'):
                yield 'table', Table(child, document)
            elif child.tag == qn('w:sdt'):
                content = child.find(qn('w:sdtContent'))
                if content is not None:
                    yield from walk(content)
            elif child.tag == qn('w:customXml'):
                yield from walk(child)

    yield from walk(document.element.body)


def _paragraph_style(paragraph):
    try:
        style = paragraph.style
        return getattr(style, 'name', '') or '', getattr(style, 'style_id', '') or ''
    except Exception:  # noqa: BLE001 - a missing style is not a parse failure
        return '', ''


def _heading_level(paragraph, style_name, style_id):
    """Return the 1-based heading level from a Word style or outline level."""
    from docx.oxml.ns import qn
    for value in (style_name, style_id):
        value = (value or '').strip()
        if re.match(r'^(?:heading|标题)', value, re.I):
            digits = re.search(r'(\d+)\s*$', value)
            return int(digits.group(1)) if digits else 1
    pPr = paragraph._p.pPr
    outline = pPr.find(qn('w:outlineLvl')) if pPr is not None else None
    if outline is not None:
        try:
            return int(outline.get(qn('w:val'))) + 1
        except (TypeError, ValueError):
            pass
    return None


def _cell_text(tc, table):
    from docx.table import _Cell
    return _Cell(tc, table).text


def _table_grid(table):
    """Expand a Word table into a rectangular grid and merge geometry.

    ``values[r][c]`` is the displayed value, ``origins[r][c]`` is the
    ``(row, col)`` cell that owns it (different from ``(r, c)`` only for a
    merged continuation position), and ``merges`` uses 1-based coordinates.
    """
    from docx.oxml.ns import qn

    values, origins = [], []
    merges = {}
    vertical = {}
    for row_index, tr in enumerate(table._tbl.tr_lst):
        row_values, row_origins = [], []
        column = 0
        for tc in tr.tc_lst:
            tcPr = tc.tcPr
            span, vmerge = 1, None
            if tcPr is not None:
                grid_span = tcPr.find(qn('w:gridSpan'))
                if grid_span is not None:
                    try:
                        span = max(1, int(grid_span.get(qn('w:val')) or 1))
                    except (TypeError, ValueError):
                        span = 1
                marker = tcPr.find(qn('w:vMerge'))
                if marker is not None:
                    vmerge = marker.get(qn('w:val')) or 'continue'
            text = _cell_text(tc, table)
            if vmerge == 'restart':
                origin = (row_index, column)
                for offset in range(span):
                    vertical[column + offset] = (origin, text)
                merges[origin] = {'row': row_index + 1, 'col': column + 1,
                                  'row_span': 1, 'col_span': span}
            elif vmerge == 'continue' and column in vertical:
                origin, text = vertical[column]
                merge = merges.setdefault(origin, {'row': origin[0] + 1, 'col': origin[1] + 1,
                                                   'row_span': 1, 'col_span': span})
                merge['row_span'] = max(merge['row_span'], row_index - origin[0] + 1)
                merge['col_span'] = max(merge['col_span'], span)
                for offset in range(span):
                    vertical[column + offset] = (origin, text)
            else:
                origin = (row_index, column)
                if span > 1:
                    merges[origin] = {'row': row_index + 1, 'col': column + 1,
                                      'row_span': 1, 'col_span': span}
            for _ in range(span):
                row_values.append(text)
                row_origins.append(origin)
            column += span
        values.append(row_values)
        origins.append(row_origins)
    width = max((len(row) for row in values), default=0)
    for row_index, row in enumerate(values):
        while len(row) < width:
            row.append(None)
            origins[row_index].append((row_index, len(row) - 1))
    return values, origins, [merges[key] for key in sorted(merges)]


def _docx_fingerprint(paragraph_structure, table_structure):
    """Hash structure only: paragraph styles/levels plus table geometry."""
    payload = {'kind': 'docx', 'paragraphs': paragraph_structure, 'tables': table_structure}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def probe_docx(path, source_id, revision):
    """Extract body paragraphs/headings and tables from a .docx snapshot."""
    _check_docx_archive(path)
    try:
        import docx
        document = docx.Document(str(path))
    except Exception as exc:  # noqa: BLE001 - report a corrupt package as a clear error
        raise ValueError(f'invalid .docx file: {type(exc).__name__}') from exc

    blocks = list(_iter_body_blocks(document))
    total = len(blocks)
    records, anchors, units = [], {}, {}
    record_locations, paragraphs_meta, tables_meta = [], [], []
    paragraph_structure, table_structure = [], []
    completed, gaps, issues = [], [], []
    paragraph_number = 0
    table_number = 0

    for block_number, (kind, block) in enumerate(blocks, 1):
        try:
            if kind == 'paragraph':
                paragraph_number += 1
                style_name, style_id = _paragraph_style(block)
                level = _heading_level(block, style_name, style_id)
                paragraph_structure.append({'style': style_name, 'heading_level': level})
                text = block.text
                if not text.strip():
                    completed.append(block_number)
                    continue
                unit_ref = f'paragraph:{paragraph_number}'
                units[unit_ref] = text
                paragraphs_meta.append({'paragraph': paragraph_number, 'style': style_name,
                                        'heading_level': level, 'unit_ref': unit_ref, 'text': text})
                index = len(records)
                records.append({'text': text})
                anchors[f'{index}.text'] = [SourceAnchor(source_ref=source_id, source_revision=revision,
                    selector={'kind': 'text_span', 'unit_ref': unit_ref,
                              'char_start': 0, 'char_end': len(text)})]
                record_locations.append({'record': index, 'kind': 'paragraph',
                                         'paragraph': paragraph_number, 'unit_ref': unit_ref})
            else:
                table_number += 1
                values, origins, merges = _table_grid(block)
                row_count = len(values)
                column_count = max((len(row) for row in values), default=0)
                table_structure.append({'row_count': row_count, 'column_count': column_count,
                                        'merges': merges})
                # A one-row table has no header to spare: keep its cells as a
                # synthetic-column record instead of silently dropping text.
                header_row = 1 if row_count > 1 else 0
                if row_count > 1:
                    headers = dedupe_names(['' if value is None else str(value) for value in values[0]])
                else:
                    headers = dedupe_names([f'column_{index + 1}' for index in range(column_count)])
                tables_meta.append({'table': table_number, 'row_count': row_count,
                                    'column_count': column_count, 'header_row': header_row,
                                    'headers': headers, 'merges': merges, 'rows': values})
                for row_index, row in enumerate(values):
                    for column_index, value in enumerate(row):
                        if value in (None, '') or origins[row_index][column_index] != (row_index, column_index):
                            continue
                        units[f'table:{table_number}/row:{row_index + 1}/col:{column_index + 1}'] = value
                for row_index in range(header_row, row_count):
                    row = values[row_index]
                    if all(value in (None, '') for value in row):
                        continue
                    index = len(records)
                    records.append({field: (None if value == '' else value)
                                    for field, value in zip(headers, row)})
                    record_locations.append({'record': index, 'kind': 'table',
                                             'table': table_number, 'row': row_index + 1})
                    for column_index, field in enumerate(headers):
                        value = row[column_index] if column_index < len(row) else None
                        if value in (None, ''):
                            continue
                        origin_row, origin_column = origins[row_index][column_index]
                        unit_ref = (f'table:{table_number}/row:{origin_row + 1}'
                                    f'/col:{origin_column + 1}')
                        anchors[f'{index}.{field}'] = [SourceAnchor(source_ref=source_id,
                            source_revision=revision,
                            selector={'kind': 'text_span', 'unit_ref': unit_ref,
                                      'char_start': 0, 'char_end': len(value)})]
            completed.append(block_number)
        except Exception as exc:  # noqa: BLE001 - a bad block must not abort the document
            gap_code = 'docx_block_failed'
            gaps.append(CoverageGap(partition=block_number, code=gap_code,
                                    detail=type(exc).__name__))
            issues.append({'code': 'intake.docx_block_failed', 'block': block_number,
                           'kind': kind, 'detail': type(exc).__name__})

    metadata = {
        'format': 'docx',
        'paragraphs': paragraphs_meta,
        'tables': tables_meta,
        'units': units,
        'record_locations': record_locations,
        'paragraph_count': paragraph_number,
        'table_count': table_number,
        'total_blocks': total,
        'structure_fingerprint': _docx_fingerprint(paragraph_structure, table_structure),
    }
    return records, anchors, metadata, completed, gaps, issues
