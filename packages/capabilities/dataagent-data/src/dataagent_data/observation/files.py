"""Probe immutable file snapshots with exact source anchors, without semantic guesses."""
import csv
import hashlib
import io
import json
from pathlib import Path
import zipfile
from dataagent_contracts.core.refs import SourceAnchor
from dataagent_contracts.intake import SourceProfile, CoverageGap
from ..adapters.parsers.delimited import parse_delimited
from ..adapters.parsers.json_records import parse_json_records
from .documents import probe_document


def _safe_path(workspace, locator):
    requested=Path(locator)
    if requested.is_absolute() or '..' in requested.parts:
        raise PermissionError('source must be inside the selected workspace')
    workspace=Path(workspace).resolve()
    path=(workspace/requested).resolve()
    if not path.is_relative_to(workspace) or path.is_relative_to(workspace/'.mint'):
        raise PermissionError('source path escapes allowed workspace')
    return path


def probe_file(selection, ctx, *, workspace, budget_rows=200, engine=None):
    if selection.kind!='file' or not 1 <= budget_rows <= 10000:
        raise ValueError('file source and row budget 1..10000 required')
    path=_safe_path(workspace,selection.locator_ref)
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
    total=1;completed=[1];sampled=False
    def anchor(index,field,selector):
        anchors[f'{index}.{field}']=[SourceAnchor(source_ref=selection.source_id,source_revision=revision,selector=selector)]
    if suffix in {'.csv','.tsv'}:
        fields,rows,bad,encoding,delimiter=parse_delimited(payload,filename=path.name)
        raw=list(csv.reader(io.StringIO(payload.decode(encoding)),delimiter=delimiter))
        row_ids=[i for i,row in enumerate(raw[1:],2) if len(row)==len(fields)]
        sampled=len(rows)>budget_rows
        for index,row in enumerate(rows[:budget_rows]):
            records.append(dict(zip(fields,row)))
            for field in fields: anchor(index,field,{'kind':'record_key','keys':{'row':row_ids[index]},'field':field})
        metadata={'total_rows':len(rows),'quarantined_rows':bad,'encoding':encoding,'delimiter':delimiter}
        if bad:
            gaps=[CoverageGap(partition=b['row'],code='malformed_row') for b in bad]
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
        total=len(book.sheetnames);completed=[];total_rows=0
        def header_row_count(block,merged_ranges,origin_row,origin_col):
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
        try:
            for number,name in enumerate(book.sheetnames,1):
                sheet=sheet_grid(book,name)
                grid,row_offset,col_offset=trim_empty_edges_with_offset(sheet.rows)
                hint=int(selection.options['header_row']) if 'header_row' in selection.options else None
                if hint is not None and not 1<=hint<=sheet.max_row:
                    gaps.append(CoverageGap(partition=number,code='header_row_missing'));continue
                if not grid:
                    completed.append(number);continue
                # Bands separated by two or more blank rows are separate table
                # regions (merged headers, multi-region sheets); one blank row
                # stays inside its table so sparse sheets keep their records.
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
                for band_start,band_end in bands:
                    block_rows=grid[band_start:band_end+1]
                    dense=[row for row in block_rows if not row_is_empty(row)]
                    spans=[(box.min_col,box.max_col) for box in detect_regions(dense)]
                    if not spans:spans=[(0,max(len(row) for row in dense)-1)]
                    for min_col,max_col in spans:
                        block=[row[min_col:max_col+1] for row in block_rows]
                        origin_row=row_offset+band_start+1;origin_col=col_offset+min_col+1
                        if hint is not None and origin_row<=hint<origin_row+len(block):
                            # the caller pinned the header at an absolute sheet
                            # row; rows above it are layout, not a multi-row header
                            block=block[hint-origin_row:];origin_row=hint
                        detected=header_row_count(block,sheet.merged_ranges,origin_row,origin_col)
                        if detected>=len(block):
                            # header-only region (a lone title row, a header-only
                            # sheet, or header_row pinned at the region's last
                            # row): no data rows, skip instead of erroring
                            continue
                        recovered=recover_header_block(block,
                            header_rows=detected,
                            merged_ranges=sheet.merged_ranges,origin_row=origin_row,origin_col=origin_col)
                        if not recovered.columns:continue
                        for values,source_row in zip(recovered.rows,recovered.source_rows):
                            total_rows+=1
                            if len(records)>=budget_rows:sampled=True;continue
                            index=len(records)
                            records.append(dict(zip(recovered.columns,values)))
                            for col,field in enumerate(recovered.columns):
                                anchor(index,field,{'kind':'excel_cell','sheet':name,
                                    'range':f'{get_column_letter(origin_col+col)}{source_row}'})
                completed.append(number)
        finally:book.close()
        metadata={'total_rows':total_rows,'sheets':book.sheetnames,'formula_policy':'cached_values'}
    elif suffix in {'.json','.jsonl'}:
        parsed=parse_json_records(payload,fmt='jsonl' if suffix=='.jsonl' else 'json',records_path=selection.options.get('records_path'))
        raw=parsed['records'];sampled=len(raw)>budget_rows
        prefix=selection.options.get('records_path','')
        selected=None
        if parsed['format']=='json':
            selected=json.loads(payload)
            for token in prefix.split('/')[1:]:
                token=token.replace('~1','/').replace('~0','~')
                selected=selected[int(token)] if isinstance(selected,list) else selected[token]
        line_numbers=[n for n,line in enumerate(payload.decode('utf-8').splitlines(),1) if line.strip()]
        for i,record in enumerate(raw[:budget_rows]):
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
                    anchor(index,field,{'kind':'record_key','keys':{'line':line_numbers[i]},'field':field})
                else:
                    record_path=prefix+(f'/{i}' if isinstance(selected,list) else '')
                    anchor(index,field,{'kind':'json_pointer','pointer':record_path+field})
        metadata={'total_rows':len(raw),'format':parsed['format'],'records_path':selection.options.get('records_path','')}
    else:
        records,anchors,metadata,completed,gaps,issues=probe_document(snapshot,selection.source_id,revision,engine=engine)
        total=metadata.get('total_pages',metadata.get('total_blocks',1))
    fields=list(dict.fromkeys(k for row in records for k in row))
    if 'structure_fingerprint' not in metadata:
        metadata['structure_fingerprint']=hashlib.sha256(json.dumps({'kind':suffix,'fields':sorted(fields)},sort_keys=True).encode()).hexdigest()
    metadata.update({'snapshot_ref':str(snapshot.relative_to(workspace)),'extractor_version':'dataagent-probe@1',
        'field_stats':{k:{'missing_in_sample':sum(row.get(k) is None for row in records)} for k in fields}})
    return SourceProfile(source_id=selection.source_id,source_revision=revision,kind=suffix.lstrip('.'),
        records=records,fields=fields,anchors=anchors,metadata=metadata,total_partitions=total,
        completed_partitions=completed,gaps=gaps,issues=issues,sampled=sampled)
