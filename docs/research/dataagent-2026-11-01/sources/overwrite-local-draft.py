from pathlib import Path
import json,re,html,xml.etree.ElementTree as ET,subprocess
base=Path('docs/research/dataagent-2026-11-01')
j=json.loads((base/'sources/feishu-before-local-overwrite.json').read_text()); assert j['ok']
d=j['data']['document']; r=ET.fromstring('<root>'+d['content']+'</root>')
idx=next(i for i,e in enumerate(r) if e.tag=='h1' and ''.join(e.itertext())=='Module')
assert idx+1<len(r)
md=(base/'02-atomic-capabilities-revised.md').read_text()
md=re.sub(r'^---\n.*?\n---\n','',md,flags=re.S)
md=re.sub(r'^\s*# [^\n]+\n','',md,count=1).strip()
def inline(s):
 s=html.escape(s,quote=False)
 s=s.replace('&lt;br&gt;', '<br/>')
 s=re.sub(r'\*\*(.+?)\*\*',r'<b>\1</b>',s)
 return re.sub(r'`([^`]+)`',r'\1',s)
lines=md.splitlines(); out=[];i=0
while i<len(lines):
 line=lines[i].strip()
 if not line:i+=1;continue
 if line.startswith('|'):
  rows=[]
  while i<len(lines) and lines[i].strip().startswith('|'):
   row=[c.strip() for c in lines[i].strip().strip('|').split('|')]
   if not all(re.fullmatch(r':?-+:?',c) for c in row):rows.append(row)
   i+=1
  width=len(rows[0]);assert all(len(a)==width for a in rows)
  out.append('<table><thead><tr>'+''.join('<th><p>'+inline(c)+'</p></th>' for c in rows[0])+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td><p>'+inline(c)+'</p></td>' for c in row)+'</tr>' for row in rows[1:])+'</tbody></table>')
  continue
 m=re.match(r'^(#{2,3}) (.+)',line)
 if m:out.append(f'<h{len(m[1])}>'+inline(m[2])+f'</h{len(m[1])}>')
 else:out.append('<p>'+inline(line)+'</p>')
 i+=1
x=''.join(out);ET.fromstring('<root>'+x+'</root>')
path=base/'sources/local-simplified-module.xml';path.write_text(x)
plan={'revision':d['revision_id'],'start':r[idx+1].get('id'),'end':r[-1].get('id'),'prefix_ids':[e.get('id') for e in list(r)[:idx+1]]}
(base/'sources/local-simplified-patch-plan.json').write_text(json.dumps(plan))
preflight=base/'sources/local-simplified-preflight.xml';preflight.write_text('<title>Pluggable DataAgent</title><h1>Module</h1>'+x)
p=subprocess.run(['lark-cli','docs','+script','--command','parse','--content','@./'+str(preflight)],capture_output=True,text=True,check=True)
v=json.loads(p.stdout);assert v['ok'] and v['data']['assessment']['status']=='passed',v
print('preflight passed',plan,'chars',len(x),'modules',len(re.findall(r'<h3>DA\d{2}｜',x)))
