"""Probe immutable file snapshots with exact source anchors, without semantic guesses.

Long probes are split into durable segments.  Each call handles at most one
segment (rows, worksheets/table regions or document pages/blocks).  When work
remains, the returned ``SourceProfile`` carries ``metadata.resume`` with the
next cursor and a ``time_budget_exceeded`` gap.  The caller passes that profile
back as ``previous``; the next segment continues from the cursor and keeps the
records/anchors already produced instead of rebuilding them.
"""
import csv
import hashlib
import io
import json
from pathlib import Path
import time
import zipfile
from dataagent_contracts.core.refs import SourceAnchor
from dataagent_contracts.intake import SourceProfile, CoverageGap
from ..adapters.parsers.delimited import parse_delimited
from ..adapters.parsers.json_records import parse_json_records
from .documents import _build_record_sets, probe_document


BUDGET_GAP = 'time_budget_exceeded'
DEFAULT_SEGMENT_ROWS = 2000
DEFAULT_SEGMENT_PAGES = 10
DEFAULT_SEGMENT_BLOCKS = 200
DEFAULT_SEGMENT_SHEETS = 5


def _outside_workspace(locator, resolved, workspace):
    return PermissionError(
        f'source file is not inside the workspace: {locator!r} resolves to '
        f'{str(resolved)!r}; workspace is {str(workspace)!r}')


def _safe_path(workspace, locator):
    workspace=Path(workspace).resolve()
    requested=Path(locator)
    if requested.is_absolute():
        # A dropped file arrives as an absolute path.  Accept it only when it
        # resolves back inside the workspace, and carry on with the equivalent
        # workspace-relative locator.
        resolved=requested.resolve()
        try:
            requested=resolved.relative_to(workspace)
        except ValueError:
            raise _outside_workspace(locator, resolved, workspace) from None
    elif '..' in requested.parts:
        resolved=(workspace/requested).resolve()
        if not resolved.is_relative_to(workspace):
            raise _outside_workspace(locator, resolved, workspace)
        raise PermissionError('source must be inside the selected workspace')
    path=(workspace/requested).resolve()
    if not path.is_relative_to(workspace):
        raise _outside_workspace(locator, path, workspace)
    if path.is_relative_to(workspace/'.mint'):
        raise PermissionError('source path escapes allowed workspace')
    return path


def _expired(deadline):
    return deadline is not None and time.monotonic() >= deadline


def _resume(previous, revision, kind):
    """The prior profile only resumes the same immutable snapshot and format."""
    if previous is None or previous.source_revision != revision or previous.kind != kind:
        return None
    state = previous.metadata.get('resume')
    return state if isinstance(state, dict) else None


def _carry(previous):
    if previous is None:
        return [], {}, [], []
    error=(previous.metadata.get('probe_error')
           if isinstance(previous.metadata,dict) else None)
    failure=error.get('code') if isinstance(error,dict) else None
    gaps=[gap for gap in previous.gaps
          if gap.code not in {BUDGET_GAP,failure}]
    return (list(previous.records), dict(previous.anchors),
            list(previous.completed_partitions), gaps)


def _positive_int(value, default, maximum):
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
        return default
    return value


def select_record_set(profile, name=None):
    """Return a profile view restricted to one Word record set.

    A .docx profile exposes independent record sets in
    ``metadata.record_sets`` (``paragraphs`` and ``table:<n>``).  The default
    is the table set with the most data rows; ``name=None`` selects it.  Pass
    ``'paragraphs'`` explicitly to work with prose records, or ``'all'`` to
    keep every record.  Non-Word profiles pass through unchanged.
    """
    metadata = profile.metadata if isinstance(profile.metadata, dict) else {}
    sets = metadata.get('record_sets')
    if not isinstance(sets, dict) or not sets:
        if name not in (None, '', 'all'):
            raise ValueError('the source profile has no selectable record sets')
        return profile
    chosen = name or metadata.get('default_record_set')
    if chosen in (None, '', 'all'):
        return profile.model_copy(update={
            'metadata': {**metadata, 'selected_record_set': 'all'}})
    if chosen not in sets:
        available = ', '.join(sorted(sets))
        raise ValueError(f'unknown record set {chosen!r}; available: {available}')
    indices = [index for index in sets[chosen].get('record_indices', [])
               if isinstance(index, int) and 0 <= index < len(profile.records)]
    index_map = {old: new for new, old in enumerate(indices)}
    records = [profile.records[index] for index in indices]
    anchors = {}
    for key, values in profile.anchors.items():
        head, separator, field = key.partition('.')
        if not separator:
            continue
        try:
            old_index = int(head)
        except ValueError:
            continue
        if old_index in index_map:
            anchors[f'{index_map[old_index]}.{field}'] = list(values)
    locations = []
    for location in metadata.get('record_locations', []):
        if not isinstance(location, dict):
            continue
        old_index = location.get('record')
        if isinstance(old_index, int) and old_index in index_map:
            item = dict(location)
            item['record'] = index_map[old_index]
            locations.append(item)
    fields = list(dict.fromkeys(field for row in records for field in row))
    selected_sets, default = _build_record_sets(
        records, locations, metadata.get('tables', []))
    summary = {set_name: {
        'kind': entry.get('kind'), 'count': entry.get('count'),
        'headers': list(entry.get('headers', [])),
    } for set_name, entry in sets.items()}
    selected_metadata = {
        **metadata, 'record_locations': locations,
        'selected_record_set': chosen, 'source_record_sets': summary,
        'field_stats': {field: {'missing_in_sample': sum(row.get(field) is None
                                                         for row in records)}
                        for field in fields},
    }
    if selected_sets:
        selected_metadata['record_sets'] = selected_sets
        selected_metadata['default_record_set'] = default
    return profile.model_copy(update={
        'records': records, 'fields': fields, 'anchors': anchors,
        'metadata': selected_metadata})


def probe_file(selection, ctx, *, workspace, budget_rows=200, engine=None,
               previous=None, deadline=None, segment_rows=DEFAULT_SEGMENT_ROWS,
               segment_pages=DEFAULT_SEGMENT_PAGES,
               segment_blocks=DEFAULT_SEGMENT_BLOCKS,
               segment_sheets=DEFAULT_SEGMENT_SHEETS):
    if selection.kind!='file' or not 1 <= budget_rows <= 10000:
        raise ValueError('file source and row budget 1..10000 required')
    segment_rows=_positive_int(segment_rows, DEFAULT_SEGMENT_ROWS, 100000)
    segment_pages=_positive_int(segment_pages, DEFAULT_SEGMENT_PAGES, 1000)
    segment_blocks=_positive_int(segment_blocks, DEFAULT_SEGMENT_BLOCKS, 100000)
    segment_sheets=_positive_int(segment_sheets, DEFAULT_SEGMENT_SHEETS, 1000)
    requested_record_set=selection.options.get('record_set')
    if requested_record_set is not None and not isinstance(requested_record_set, str):
        raise ValueError('record_set option must be a string')
    requested_record_set=requested_record_set or None
    workspace=Path(workspace).resolve()
    path=_safe_path(workspace,selection.locator_ref)
    locator_ref=path.relative_to(workspace).as_posix()
    with path.open('rb') as f:
        payload=f.read(32*1024*1024+1)
    if len(payload)>32*1024*1024:
        raise ValueError('file exceeds 32 MiB local probe limit')
    suffix=path.suffix.lower()
    if suffix not in {'.csv','.tsv','.json','.jsonl','.xlsx','.xlsm','.pdf','.docx'}:
        raise ValueError('unsupported source format')
    digest=hashlib.sha256(payload).hexdigest();revision='sha256:'+digest
    root=Path(workspace)/'.dataagent/content';root.mkdir(parents=True,exist_ok=True)
    snapshot=root/(digest+suffix)
    if not snapshot.exists(): snapshot.write_bytes(payload)
    records,anchors,metadata,gaps,issues=[],{},{},[],[]
    total=1;completed=[1];sampled=False;resume=None
    kind=suffix.lstrip('.')
    if suffix in {'.csv','.tsv'}:
        fields,rows,bad,encoding,delimiter=parse_delimited(payload,filename=path.name)
        raw=list(csv.reader(io.StringIO(payload.decode(encoding)),delimiter=delimiter))
        row_ids=[i for i,row in enumerate(raw[1:],2) if len(row)==len(fields)]
        prior=_resume(previous,revision,kind)
        records,anchors,completed,gaps=_carry(previous if prior else None)
        start=int(prior.get('next_row',0)) if prior else 0
        start=max(0,min(start,len(records),len(rows),budget_rows))
        records=records[:start]
        limit=min(len(rows),budget_rows)
        sampled=len(rows)>budget_rows
        processed=start
        while processed<limit and processed-start<segment_rows:
            # Always finish one chunk so every call makes durable progress.
            if processed>start and _expired(deadline):break
            step=min(segment_rows-(processed-start),limit-processed)
            for index in range(processed,processed+step):
                row=rows[index]
                records.append(dict(zip(fields,row)))
                for field in fields:
                    anchors[f'{index}.{field}']=[SourceAnchor(source_ref=selection.source_id,
                        source_revision=revision,selector={'kind':'record_key',
                        'keys':{'row':row_ids[index]},'field':field})]
            processed+=step
        partial=processed<min(len(rows),budget_rows)
        if partial:
            completed=[]
            gaps.append(CoverageGap(partition=1,code=BUDGET_GAP))
            resume={'kind':'file','format':'csv','next_row':processed}
        else:
            completed=[1]
            gaps.extend(CoverageGap(partition=b['row'],code='malformed_row') for b in bad)
        metadata={'total_rows':len(rows),'quarantined_rows':bad,'encoding':encoding,'delimiter':delimiter}
    elif suffix in {'.json','.jsonl'}:
        parsed=parse_json_records(payload,fmt='jsonl' if suffix=='.jsonl' else 'json',
            records_path=selection.options.get('records_path'))
        raw=parsed['records']
        prefix=selection.options.get('records_path','')
        selected=None
        if parsed['format']=='json':
            selected=json.loads(payload)
            for token in prefix.split('/')[1:]:
                token=token.replace('~1','/').replace('~0','~')
                selected=selected[int(token)] if isinstance(selected,list) else selected[token]
        line_numbers=[n for n,line in enumerate(payload.decode('utf-8').splitlines(),1) if line.strip()]
        prior=_resume(previous,revision,kind)
        records,anchors,completed,gaps=_carry(previous if prior else None)
        start=int(prior.get('next_row',0)) if prior else 0
        start=max(0,min(start,len(raw),budget_rows))
        limit=min(len(raw),budget_rows)
        sampled=len(raw)>budget_rows
        processed=start
        while processed<limit and processed-start<segment_rows:
            # Always finish one chunk so every call makes durable progress.
            if processed>start and _expired(deadline):break
            step=min(segment_rows-(processed-start),limit-processed)
            for i in range(processed,processed+step):
                record=raw[i]
                if not isinstance(record,dict):
                    gaps.append(CoverageGap(partition=i,code='record_not_object'));continue
                flat={}
                def walk(value,prefix=''):
                    if isinstance(value,dict) and value:
                        for key,item in value.items():walk(item,prefix+'/'+str(key).replace('~','~0').replace('/','~1'))
                    else:flat[prefix or '/']=value
                walk(record);index=len(records);records.append(flat)
                for field in flat:
                    if parsed['format']=='jsonl':
                        anchors[f'{index}.{field}']=[SourceAnchor(source_ref=selection.source_id,
                            source_revision=revision,selector={'kind':'record_key',
                            'keys':{'line':line_numbers[i]},'field':field})]
                    else:
                        record_path=prefix+(f'/{i}' if isinstance(selected,list) else '')
                        anchors[f'{index}.{field}']=[SourceAnchor(source_ref=selection.source_id,
                            source_revision=revision,selector={'kind':'json_pointer',
                            'pointer':record_path+field})]
            processed+=step
        partial=processed<min(len(raw),budget_rows)
        if partial:
            completed=[]
            gaps.append(CoverageGap(partition=1,code=BUDGET_GAP))
            resume={'kind':'file','format':'json','next_row':processed}
        else:
            completed=[1]
        metadata={'total_rows':len(raw),'format':parsed['format'],
            'records_path':selection.options.get('records_path','')}
    elif suffix in {'.xlsx','.xlsm'}:
        from openpyxl.utils import get_column_letter
        from openpyxl.utils.cell import range_boundaries
        from ..adapters.parsers.excel import (open_workbook,row_is_empty,sheet_grid,
            trim_empty_edges_with_offset)
        from ..preparation.regions import detect_regions
        from ..preparation.structure import recover_header_block
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            if sum(i.file_size for i in archive.infolist()) > 256*1024*1024 or len(archive.infolist())>10000:
                raise ValueError('expanded workbook exceeds probe limit')
        book=open_workbook(snapshot,data_only=True)
        try:
            sheets=list(book.sheetnames)
            total=len(sheets)
            prior=_resume(previous,revision,kind)
            records,anchors,completed,gaps=_carry(previous if prior else None)
            total_rows=int(previous.metadata.get('total_rows',0)) if prior else 0
            hint=int(selection.options['header_row']) if 'header_row' in selection.options else None
            sheet_index=int(prior.get('next_sheet',0)) if prior else 0
            span_index=int(prior.get('next_span',0)) if prior else 0
            sheet_index=max(0,min(sheet_index,total))
            first_sheet=sheet_index
            sampled=bool(prior and previous.sampled)
            partial=False
            while sheet_index<total and sheet_index-first_sheet<segment_sheets:
                number=sheet_index+1
                name=sheets[sheet_index]
                sheet=sheet_grid(book,name)
                grid,row_offset,col_offset,grid_error=_xlsx_layout(sheet,hint,
                    trim_empty_edges_with_offset)
                if grid_error:
                    gaps.append(CoverageGap(partition=number,code=grid_error))
                    sheet_index+=1;span_index=0;continue
                spans=_xlsx_spans(grid,row_is_empty,detect_regions)
                if not grid:
                    completed.append(number)
                    sheet_index+=1;span_index=0;continue
                while span_index<len(spans):
                    if span_index>0 and _expired(deadline):
                        partial=True;break
                    block_rows=grid[spans[span_index][0]:spans[span_index][1]+1]
                    records,anchors,total_rows,sampled=_xlsx_span(
                        name,sheet,spans[span_index],block_rows,row_offset,col_offset,
                        hint,selection,revision,records,anchors,total_rows,budget_rows,
                        sampled,get_column_letter,range_boundaries,recover_header_block)
                    span_index+=1
                if partial:break
                completed.append(number)
                sheet_index+=1;span_index=0
            if sheet_index<total:
                partial=True
            if partial:
                current=min(sheet_index+1,total) if total else 1
                gaps.append(CoverageGap(partition=current,code=BUDGET_GAP))
                completed=[value for value in completed if value<current]
                resume={'kind':'file','format':'xlsx','next_sheet':sheet_index,
                    'next_span':span_index}
            metadata={'total_rows':total_rows,'sheets':sheets,'formula_policy':'cached_values'}
        finally:
            book.close()
    else:
        records,anchors,metadata,completed,gaps,issues=probe_document(
            snapshot,selection.source_id,revision,engine=engine,previous=previous,
            deadline=deadline,segment_pages=segment_pages,segment_blocks=segment_blocks,
            known_fields=selection.options.get('known_fields'))
        total=metadata.get('total_pages',metadata.get('total_blocks',1))
        if isinstance(metadata.get('resume'),dict):resume=metadata['resume']
    fields=list(dict.fromkeys(k for row in records for k in row))
    if 'structure_fingerprint' not in metadata:
        metadata['structure_fingerprint']=hashlib.sha256(json.dumps({'kind':suffix,'fields':sorted(fields)},sort_keys=True).encode()).hexdigest()
    metadata.update({'locator_ref':locator_ref,'snapshot_ref':str(snapshot.relative_to(workspace)),'extractor_version':'dataagent-probe@1',
        'field_stats':{k:{'missing_in_sample':sum(row.get(k) is None for row in records)} for k in fields}})
    if resume is not None:
        metadata['resume']=resume
        if requested_record_set:
            metadata['requested_record_set']=requested_record_set
    profile=SourceProfile(source_id=selection.source_id,source_revision=revision,kind=suffix.lstrip('.'),
        records=records,fields=fields,anchors=anchors,metadata=metadata,total_partitions=total,
        completed_partitions=completed,gaps=gaps,issues=issues,sampled=sampled)
    if requested_record_set and resume is None:
        profile=select_record_set(profile,requested_record_set)
    return profile


def _xlsx_layout(sheet, hint, trim_empty_edges_with_offset):
    """Return the trimmed sheet grid and the table regions for one worksheet."""
    if hint is not None and not 1<=hint<=sheet.max_row:
        return None,0,0,'header_row_missing'
    grid,row_offset,col_offset=trim_empty_edges_with_offset(sheet.rows)
    return grid,row_offset,col_offset,None


def _xlsx_spans(grid, row_is_empty, detect_regions):
    """Bands separated by two or more blank rows, split by dense column runs."""
    bands=[];start=None;blanks=0
    for index,row in enumerate(grid):
        if not row_is_empty(row):
            if start is None:start=index
            blanks=0
        else:
            blanks+=1
            if start is not None and blanks>=2:
                bands.append((start,index-blanks));start=None
    if start is not None:bands.append((start,len(grid)-1))
    spans=[]
    for band_start,band_end in bands:
        block_rows=grid[band_start:band_end+1]
        dense=[row for row in block_rows if not row_is_empty(row)]
        regions=[(box.min_col,box.max_col) for box in detect_regions(dense)]
        if not regions:regions=[(0,max(len(row) for row in dense)-1)]
        spans.extend((band_start,band_end,min_col,max_col) for min_col,max_col in regions)
    return spans


def _header_row_count(block,merged_ranges,origin_row,origin_col,range_boundaries,recover_header_block):
    # The header-row heuristic runs on a merge-expanded copy: the sparse
    # sub-header row of a merged header block (不含税/税额 under a merged
    # 金额（分）) would otherwise be read as a data row.
    expanded=[list(row) for row in block]
    width=max(len(row) for row in expanded)
    for row in expanded:row.extend([None]*(width-len(row)))
    for cell_range in merged_ranges or []:
        try:min_col,min_row,max_col,max_row=range_boundaries(cell_range)
        except Exception:continue
        top,left=min_row-origin_row,min_col-origin_col
        if top<0 or left<0 or top>=len(expanded) or left>=width:continue
        value=expanded[top][left]
        if value in (None,''):continue
        for row in range(top,min(max_row-origin_row+1,len(expanded))):
            for column in range(left,min(max_col-origin_col+1,width)):
                if expanded[row][column] in (None,''):
                    expanded[row][column]=value
    return recover_header_block(expanded).header_rows


def _xlsx_span(name,sheet,span,block_rows,row_offset,col_offset,hint,selection,revision,
               records,anchors,total_rows,budget_rows,sampled,get_column_letter,
               range_boundaries,recover_header_block):
    """Append one table region's records; resume is always at a region boundary."""
    band_start,band_end,min_col,max_col=span
    block=[row[min_col:max_col+1] for row in block_rows]
    origin_row=row_offset+band_start+1;origin_col=col_offset+min_col+1
    if hint is not None and origin_row<=hint<origin_row+len(block):
        # the caller pinned the header at an absolute sheet row; rows above it
        # are layout, not a multi-row header
        block=block[hint-origin_row:];origin_row=hint
    detected=_header_row_count(block,sheet.merged_ranges,origin_row,origin_col,
        range_boundaries,recover_header_block)
    if detected>=len(block):
        # header-only region (a lone title row, a header-only sheet, or
        # header_row pinned at the region's last row): no data rows
        return records,anchors,total_rows,sampled
    recovered=recover_header_block(block,header_rows=detected,
        merged_ranges=sheet.merged_ranges,origin_row=origin_row,origin_col=origin_col)
    if not recovered.columns:
        return records,anchors,total_rows,sampled
    for values,source_row in zip(recovered.rows,recovered.source_rows):
        total_rows+=1
        if len(records)>=budget_rows:
            sampled=True;continue
        index=len(records)
        records.append(dict(zip(recovered.columns,values)))
        for col,field in enumerate(recovered.columns):
            anchors[f'{index}.{field}']=[SourceAnchor(source_ref=selection.source_id,
                source_revision=revision,selector={'kind':'excel_cell','sheet':name,
                'range':f'{get_column_letter(origin_col+col)}{source_row}'})]
    return records,anchors,total_rows,sampled
