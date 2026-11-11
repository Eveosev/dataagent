import {expect, test} from '@playwright/test';
import {execFileSync} from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import type {Discovery} from '../src/pages/DiscoveryPage';

const workspace=process.env.DATAAGENT_TEST_WORKSPACE;
const python=process.env.DATAAGENT_TEST_PYTHON;

function callTool(name:string, args:Record<string,unknown>){
 const request={jsonrpc:'2.0',id:1,method:'tools/call',params:{name,arguments:args}};
 const line=execFileSync(python!,['-m','dataagent_workbench.interfaces.mcp_server'],{
  cwd:workspace,input:JSON.stringify(request)+'\n',encoding:'utf8',
 });
 const {result}=JSON.parse(line);
 expect(result.isError).toBe(false);
 const summary=JSON.parse(result.content[0].text);
 return JSON.parse(fs.readFileSync(path.join(workspace!,summary.result_path),'utf8')).data;
}

test('SQLite 上传、工具提交本体草案、工作台审核',async({page})=>{
 test.skip(!workspace||!python,'run scripts/verify_browser.py to share the test workspace with MCP');
 const database=path.join(workspace!,'sales-discovery.db');
 fs.rmSync(database,{force:true});
 const sql=fs.readFileSync(path.resolve('../../dataagent-scenarios/fixtures/intake/sales-discovery.sql'));
 execFileSync('sqlite3',[database],{input:sql});
 await page.goto('/');
 await page.getByLabel('接入目标').fill('识别销售订单和订单明细');
 await page.getByLabel('选择材料').setInputFiles(database);
 await page.getByRole('radio',{name:'从数据库发现本体'}).check();
 await page.getByRole('button',{name:'开始接入'}).click();
 await expect(page.getByRole('heading',{name:'SQLite 本体发现'})).toBeVisible();
 await expect(page.getByRole('heading',{name:'来源证据'})).toBeVisible();
 await expect(page.getByText('观测值匹配',{exact:false})).toBeVisible();
 const session_id=new URLSearchParams(new URL(page.url()).hash.slice(1)).get('session');
 const request=callTool('intake_inference',{session_id}) as Discovery & {
  expected_revision:string;source_revision:string;
 };
 const fk=request.catalog!.relationships.find(link=>link.origin==='declared');
 callTool('ontology_discovery_propose',{
  session_id,expected_revision:request.expected_revision,
  proposal:{
   source_revision:request.source_revision,
   entities:[
    {name:'销售单',table:'doc_hdr',grain:'每个账簿内的一份销售单',identity:['book','doc_no']},
    {name:'销售明细',table:'doc_line',grain:'每份销售单的一条明细',identity:['book','doc_no','seq'],
     properties:[{name:'金额（分）',column:'cents'}]},
   ],
   relationships:[{name:'所属订单',evidence_id:fk!.id}],
  },
 });
 await expect(page.getByRole('heading',{name:'本体草案',exact:true})).toBeVisible();
 await expect(page.getByText('每份销售单的一条明细')).toBeVisible();
 await expect(page.getByText('所属订单')).toBeVisible();
 await page.getByRole('button',{name:'确认当前草案'}).click();
 await expect(page.getByText('已通过审核').first()).toBeVisible();
 await page.reload();
 await expect(page.getByText('已通过审核').first()).toBeVisible();
 await expect(page.getByText('待核对',{exact:true})).toBeVisible();
 if(process.env.DATAAGENT_SCREENSHOT)await page.screenshot({
  path:path.join(path.dirname(process.env.DATAAGENT_SCREENSHOT),'discovery-live.png'),fullPage:true,
 });
});
