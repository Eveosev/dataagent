from pathlib import Path
import pytest
from conftest import build_pdf_pages, build_xlsx
from dataagent_contracts.intake import SourceSelection
from dataagent_data.observation.files import probe_file


def selection(name):
    return SourceSelection(source_id='f',kind='file',locator_ref=name)


def test_mixed_pdf_retains_successful_pages(workspace,ctx):
    build_pdf_pages(workspace/'in.pdf',[['Invoice: INV-1','Amount: 1260.00'],[],['Currency: CNY']])
    profile=probe_file(selection('in.pdf'),ctx,workspace=workspace)
    assert profile.coverage=='partial'
    assert profile.completed_partitions==[1,3]
    assert profile.gaps[0].partition==2
    assert profile.records[0]['Invoice']=='INV-1'
    anchor=profile.anchors['0.Amount'][0]
    assert anchor.selector.page==1
    assert anchor.source_revision==profile.source_revision


def test_scanned_page_without_engine_is_not_empty_success(workspace,ctx):
    from PIL import Image
    Image.new('RGB',(200,300),'white').save(workspace/'scan.pdf','PDF')
    profile=probe_file(selection('scan.pdf'),ctx,workspace=workspace)
    assert profile.coverage=='partial'
    assert profile.gaps[0].code=='ocr_engine_missing'
    assert profile.completed_partitions==[]


def test_cross_page_table_has_anchors(workspace,ctx):
    # Distinct lines and page provenance must survive even when table grouping is uncertain.
    build_pdf_pages(workspace/'tables.pdf',[
        ['Item: A','Amount: 100.00'],['Item: B','Amount: 200.00']])
    profile=probe_file(selection('tables.pdf'),ctx,workspace=workspace)
    assert [r['Amount'] for r in profile.records]==['100.00','200.00']
    assert [profile.anchors[f'{i}.Amount'][0].selector.page for i in range(2)]==[1,2]


def test_sampled_table_is_not_full_coverage(workspace,ctx):
    (workspace/'in.csv').write_text('id,amount\na,100\nb,200\nc,300\n')
    profile=probe_file(selection('in.csv'),ctx,workspace=workspace,budget_rows=2)
    assert profile.coverage=='sampled'
    assert len(profile.records)==2
    assert profile.metadata['total_rows']==3
    assert profile.anchors['1.amount'][0].selector.keys=={'row':3}


def test_excel_preserves_sheet_cell_and_sparse_rows(workspace,ctx):
    build_xlsx(workspace/'in.xlsx',{'Invoices':[['id','amount'],['A',100],[],['B',200]]})
    profile=probe_file(selection('in.xlsx'),ctx,workspace=workspace)
    assert [r['id'] for r in profile.records]==['A','B']
    assert profile.anchors['1.amount'][0].selector.range=='B4'


def test_merged_headers_and_second_region_probe_as_two_tables(workspace,ctx):
    from datetime import date
    from openpyxl import Workbook
    wb=Workbook();ws=wb.active;ws.title='报销明细'
    ws.append(['发票号','开票日期','供应商','金额（分）',None,'币种'])
    ws.append([None,None,None,'不含税','税额',None])
    ws.append(['INV-1',date(2026,11,10),'甲',100,10,'CNY'])
    ws.append(['INV-2',date(2026,11,11),'乙',200,20,'CNY'])
    ws.append([]);ws.append([])  # two blank rows separate the table regions
    ws.append(['报销单号','发票号','费用类别','报销金额（分）'])
    ws.append(['EXP-1','INV-1','办公用品',110])
    for block in ['A1:A2','B1:B2','C1:C2','D1:E1','F1:F2']:
        ws.merge_cells(block)
    wb.save(workspace/'regions.xlsx')
    profile=probe_file(selection('regions.xlsx'),ctx,workspace=workspace)
    assert profile.coverage=='full' and profile.completed_partitions==[1] and profile.gaps==[]
    # The merged header resolves to parent/child columns; the sub-header row
    # and the second region's header row are not records.
    assert profile.records==[
        {'发票号':'INV-1','开票日期':'2026-11-10T00:00:00','供应商':'甲',
         '金额（分） / 不含税':100,'金额（分） / 税额':10,'币种':'CNY'},
        {'发票号':'INV-2','开票日期':'2026-11-11T00:00:00','供应商':'乙',
         '金额（分） / 不含税':200,'金额（分） / 税额':20,'币种':'CNY'},
        {'报销单号':'EXP-1','发票号':'INV-1','费用类别':'办公用品','报销金额（分）':110}]
    assert profile.metadata['total_rows']==3
    assert profile.anchors['0.金额（分） / 税额'][0].selector.range=='E3'
    assert profile.anchors['1.开票日期'][0].selector.range=='B4'
    assert profile.anchors['2.报销金额（分）'][0].selector.range=='D8'
    assert [a[0].selector.sheet for a in profile.anchors.values()]==['报销明细']*16


def test_header_row_option_selects_the_header(workspace,ctx):
    build_xlsx(workspace/'in.xlsx',{'S':[['skip','col'],['id','amount'],['A',1]]})
    chosen=selection('in.xlsx').model_copy(update={'options':{'header_row':2}})
    profile=probe_file(chosen,ctx,workspace=workspace)
    assert [r['id'] for r in profile.records]==['A']
    assert profile.anchors['0.amount'][0].selector.range=='B3'


def test_header_only_regions_are_skipped_not_an_error(workspace,ctx):
    # A header-only sheet and a lone title row each form a 1-row region with
    # no data rows; both must be skipped instead of raising CapabilityError.
    build_xlsx(workspace/'headers.xlsx',{'S':[['id','amount']]})
    only_headers=probe_file(selection('headers.xlsx'),ctx,workspace=workspace)
    assert only_headers.coverage=='full' and only_headers.completed_partitions==[1]
    assert only_headers.records==[] and only_headers.metadata['total_rows']==0
    build_xlsx(workspace/'title.xlsx',{'S':[['id','amount'],[],[],['2026 报销明细']]})
    with_title=probe_file(selection('title.xlsx'),ctx,workspace=workspace)
    assert with_title.coverage=='full' and with_title.gaps==[]
    assert with_title.records==[] and with_title.metadata['total_rows']==0


def test_header_row_pinned_at_last_row_yields_no_records(workspace,ctx):
    build_xlsx(workspace/'in.xlsx',{'S':[['skip','col'],['id','amount']]})
    chosen=selection('in.xlsx').model_copy(update={'options':{'header_row':2}})
    profile=probe_file(chosen,ctx,workspace=workspace)
    assert profile.coverage=='full' and profile.records==[]


def test_path_escape_and_content_mismatch_are_rejected(workspace,ctx,tmp_path):
    (tmp_path/'outside.csv').write_text('id\nx\n')
    (workspace/'link.csv').symlink_to(tmp_path/'outside.csv')
    for name in ['../outside.csv','link.csv',str(tmp_path/'outside.csv')]:
        with pytest.raises((ValueError,PermissionError)):
            probe_file(selection(name),ctx,workspace=workspace)
    (workspace/'fake.pdf').write_bytes(b'not a PDF')
    with pytest.raises(Exception):
        probe_file(selection('fake.pdf'),ctx,workspace=workspace)


def test_absolute_path_inside_workspace_is_normalized(workspace,ctx):
    (workspace/'nested').mkdir()
    (workspace/'nested'/'in.csv').write_text('id,amount\nA,100\n')
    absolute=str((workspace/'nested'/'in.csv').resolve())
    dotted=str(workspace/'nested'/'..'/'nested'/'in.csv')
    for locator in (absolute,dotted):
        profile=probe_file(selection(locator),ctx,workspace=workspace)
        assert profile.records==[{'id':'A','amount':'100'}]
        assert profile.metadata['locator_ref']=='nested/in.csv'
        assert not Path(profile.metadata['snapshot_ref']).is_absolute()


def test_absolute_path_outside_workspace_names_the_workspace(workspace,ctx,tmp_path):
    outside=tmp_path/'outside.csv';outside.write_text('id\nx\n')
    (workspace/'alias.csv').symlink_to(outside)
    for locator in (str(outside.resolve()),str(workspace/'alias.csv'),'../outside.csv'):
        with pytest.raises(PermissionError) as error:
            probe_file(selection(locator),ctx,workspace=workspace)
        message=str(error.value)
        assert 'not inside the workspace' in message
        assert str(workspace.resolve()) in message


def test_json_pointer_preserves_root_and_selected_array(workspace,ctx):
    (workspace/'object.json').write_text('{"amount":"100"}')
    obj=probe_file(selection('object.json'),ctx,workspace=workspace)
    assert obj.anchors['0./amount'][0].selector.pointer=='/amount'
    (workspace/'nested.json').write_text('{"items":[{"amount":"100"},{"amount":"200"}]}')
    s=selection('nested.json').model_copy(update={'options':{'records_path':'/items'}})
    nested=probe_file(s,ctx,workspace=workspace)
    assert nested.anchors['1./amount'][0].selector.pointer=='/items/1/amount'


def test_installed_ocr_without_active_pin_does_not_break_csv(workspace,ctx):
    import json, os, subprocess, sys
    (workspace/'in.csv').write_text('id,amount\nA,100\n')
    ocr_src=Path(__file__).resolve().parents[3]/'dataagent-ocr/src'
    assert (ocr_src/'dataagent_ocr/adapter.py').is_file()
    result=subprocess.run([sys.executable,'-m','dataagent_data.observation.cli','--workspace',str(workspace)],
        input=json.dumps({'source':selection('in.csv').model_dump(),'context':ctx.model_dump(mode='json')}),
        capture_output=True,text=True,env={**os.environ,'PYTHONPATH':str(ocr_src)})
    assert result.returncode==0,result.stderr
    profile=json.loads((workspace/json.loads(result.stdout)['result_path']).read_text())
    assert profile['records']==[{'id':'A','amount':'100'}]


def test_real_ruled_tables_on_two_pages_preserve_cell_boxes(workspace,ctx):
    path=workspace/'ruled.pdf'
    build_pdf_pages(path,[['number     amount','INV-A      100.00'],['number     amount','INV-B      200.00']])
    # Insert a 2x2 ruled grid in each content stream, maintaining the PDF xref.
    import re
    payload=path.read_text()
    grid='0.5 w 68 730 m 280 730 l S 68 750 m 280 750 l S 68 778 m 280 778 l S 68 730 m 68 778 l S 160 730 m 160 778 l S 280 730 m 280 778 l S\n'
    objects=re.findall(r'(?s)\d+ 0 obj\n(.*?)\nendobj',payload)
    for i,obj in enumerate(objects):
        if 'stream\n' in obj:
            old=re.search(r'(?s)stream\n(.*?)\nendstream',obj)[1]
            number,amount=('INV-A','100.00') if 'INV-A' in old else ('INV-B','200.00')
            cells=[(72,760,'number'),(180,760,'amount'),(72,740,number),(180,740,amount)]
            new=grid+'\n'.join(f'BT /F1 12 Tf {x} {y} Td ({text}) Tj ET' for x,y,text in cells)
            objects[i]=re.sub(r'/Length \d+',f'/Length {len(new.encode())}',obj.replace(old,new))
    out=b'%PDF-1.4\n';offsets=[0]
    for i,obj in enumerate(objects,1):offsets.append(len(out));out+=f'{i} 0 obj\n{obj}\nendobj\n'.encode()
    xref=len(out);out+=f'xref\n0 {len(objects)+1}\n0000000000 65535 f \n'.encode()
    for off in offsets[1:]:out+=f'{off:010d} 00000 n \n'.encode()
    out+=f'trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode()
    path.write_bytes(out)
    profile=probe_file(selection('ruled.pdf'),ctx,workspace=workspace)
    assert len(profile.metadata['tables'])==2
    assert [r['number'] for r in profile.records]==['INV-A','INV-B']
    assert [profile.anchors[f'{i}.number'][0].selector.page for i in range(2)]==[1,2]
    assert profile.anchors['0.number'][0].selector.kind=='pdf_bbox'
