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
from ..adapters.parsers.excel import dedupe_names
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
    if suffix not in {'.csv','.tsv','.json','.jsonl','.xlsx','.xlsm','.pdf'}:
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
        from openpyxl import load_workbook
        from openpyxl.utils import get_column_letter
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            if sum(i.file_size for i in archive.infolist()) > 256*1024*1024 or len(archive.infolist())>10000:
                raise ValueError('expanded workbook exceeds probe limit')
        book=load_workbook(snapshot,data_only=True,read_only=True)
        total=len(book.sheetnames);completed=[];total_rows=0
        try:
            for number,sheet in enumerate(book,1):
                header_row=int(selection.options.get('header_row',1))
                if not 1<=header_row<=sheet.max_row:
                    gaps.append(CoverageGap(partition=number,code='header_row_missing'));continue
                grid=sheet.iter_rows(values_only=True)
                header=next(row for i,row in enumerate(grid,1) if i==header_row)
                if sum(v is not None for v in header)<2 and sheet.max_column>1:
                    gaps.append(CoverageGap(partition=number,code='header_selection_required'));continue
                fields=dedupe_names(['' if x is None else str(x) for x in header])
                for rownum,row in enumerate(grid,header_row+1):
                    if all(x is None for x in row):continue
                    total_rows+=1
                    if len(records)>=budget_rows:sampled=True;continue
                    index=len(records)
                    records.append({k:v.isoformat() if hasattr(v,'isoformat') else v for k,v in zip(fields,row)})
                    for col,field in enumerate(fields,1):
                        anchor(index,field,{'kind':'excel_cell','sheet':sheet.title,'range':f'{get_column_letter(col)}{rownum}'})
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
        total=metadata['total_pages']
    fields=list(dict.fromkeys(k for row in records for k in row))
    metadata.update({'snapshot_ref':str(snapshot.relative_to(workspace)),'extractor_version':'dataagent-probe@1',
        'structure_fingerprint':hashlib.sha256(json.dumps({'kind':suffix,'fields':sorted(fields)},sort_keys=True).encode()).hexdigest(),
        'field_stats':{k:{'missing_in_sample':sum(row.get(k) is None for row in records)} for k in fields}})
    return SourceProfile(source_id=selection.source_id,source_revision=revision,kind=suffix.lstrip('.'),
        records=records,fields=fields,anchors=anchors,metadata=metadata,total_partitions=total,
        completed_partitions=completed,gaps=gaps,issues=issues,sampled=sampled)
