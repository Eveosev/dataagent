"""Document probe retains successful pages and explicit OCR/coverage gaps."""
import io
import re
from dataagent_contracts.core.refs import SourceAnchor
from dataagent_contracts.intake import CoverageGap
from ..adapters.parsers.pdf import parse_pdf


def probe_document(path, source_id, revision, *, engine=None, max_pages=200):
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
            pages.append({'page':page.page,'text':text,'method':method,
                'width':page.width,'height':page.height,
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
