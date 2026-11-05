from html.parser import HTMLParser
import urllib.request, concurrent.futures, json, pathlib, re, datetime
P=pathlib.Path(__file__).parent
class Extract(HTMLParser):
 def __init__(self):super().__init__();self.skip=0;self.text=[];self.links=[];self.meta=[]
 def handle_starttag(self,t,a):
  d=dict(a)
  if t in ['script','style','svg','noscript']:self.skip+=1
  if t in ['p','div','h1','h2','h3','h4','li','tr','section','br','table']:self.text.append('\n')
  if t=='a' and d.get('href'):self.links.append(d['href'])
  if t=='meta':self.meta.append(d)
 def handle_endtag(self,t):
  if t in ['script','style','svg','noscript'] and self.skip:self.skip-=1
  if t in ['p','div','h1','h2','h3','h4','li','tr','section','table']:self.text.append('\n')
 def handle_data(self,s):
  if not self.skip:self.text.append(s)
def fetch(item):
 name,url,kind=item
 out={'id':name,'url':url,'source_type':kind,'access_date':'2026-10-31 Asia/Shanghai'}
 try:
  req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (research; public documentation)'})
  r=urllib.request.urlopen(req,timeout=35);s=r.read().decode('utf-8','replace');out.update(status=r.status,final_url=r.url,bytes=len(s))
  suffix='.md' if '.md' in r.url or 'text/markdown' in r.headers.get('content-type','') else '.html'
  (P/('competitors-'+name+suffix)).write_text(s)
  if suffix=='.html':
   p=Extract();p.feed(s);text=re.sub(r'\n[ \t\n]+','\n',''.join(p.text));out['meta']=p.meta
   (P/('competitors-'+name+'-links.json')).write_text(json.dumps(p.links,ensure_ascii=False,indent=2))
  else:text=s
  (P/('competitors-'+name+'.txt')).write_text(text)
 except Exception as e:out['error']=str(e)
 print(json.dumps({k:v for k,v in out.items() if k!='meta'},ensure_ascii=False),flush=True)
 return out
items=[
('snow-analyst','https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst','technical-doc'),
('snow-agents','https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents','technical-doc'),
('snow-evals','https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst-evaluations','technical-doc'),
('genie-intro','https://docs.databricks.com/aws/en/genie-agents/','technical-doc'),
('genie-tuning','https://docs.databricks.com/aws/en/genie-agents/tune-quality','technical-doc'),
('genie-setup','https://docs.databricks.com/aws/en/genie-agents/set-up','technical-doc'),
('genie-feedback','https://docs.databricks.com/aws/en/genie-agents/monitor','technical-doc'),
('genie-files','https://docs.databricks.com/aws/en/genie-agents/file-upload','technical-doc'),
('looker','https://cloud.google.com/looker/docs/conversational-analytics-overview','technical-doc'),
('fabric','https://learn.microsoft.com/en-us/fabric/data-science/concept-data-agent','technical-doc'),
('spotter','https://www.thoughtspot.com/product/spotter','marketing'),
('spotter-docs','https://docs.thoughtspot.com/cloud/latest/spotter','technical-doc-candidate'),
('hex-agent','https://learn.hex.tech/docs/explore-data/notebook-view/notebook-agent','technical-doc'),
('hex-evals','https://learn.hex.tech/docs/agent-management/evals','technical-doc'),
('hex-governed','https://learn.hex.tech/docs/agent-management/governed-mode','technical-doc'),
('hex-context','https://learn.hex.tech/docs/agent-management/context-studio','technical-doc'),
('hex-files','https://learn.hex.tech/docs/connect-to-data/upload-files','technical-doc'),
('julius','https://julius.ai/','marketing'),
('julius-docs','https://julius.ai/docs','technical-doc-candidate'),
('quickbi','https://help.aliyun.com/zh/quick-bi/user-guide/smart-q-home-page','technical-doc'),
('quickbi-prepare','https://help.aliyun.com/zh/quick-bi/user-guide/prepare-data','technical-doc'),
('quickbi-monitor','https://help.aliyun.com/zh/quick-bi/user-guide/ask-the-number-of-operations','technical-doc'),
('finechat','https://help.fanruan.com/finebi7.0/doc-view-2572.html','technical-doc'),
('chatgpt-docs','https://learn.chatgpt.com/docs','technical-doc'),
('chatgpt-usecases','https://learn.chatgpt.com/use-cases','official-usecases'),
('search-adoption','https://www.bing.com/search?q=Databricks+Genie+customer+engineering+blog+accuracy+feedback','search'),
('search-feedback','https://www.bing.com/search?q=Snowflake+Cortex+Analyst+Genie+user+incorrect+answers+community','search'),
('search-openai','https://www.bing.com/search?q=site%3Alearn.chatgpt.com+data+analysis+files','search')]
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:results=list(ex.map(fetch,items))
(P/'competitors-source-index.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
