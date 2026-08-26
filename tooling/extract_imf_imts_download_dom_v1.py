#!/usr/bin/env python3
from pathlib import Path
from bs4 import BeautifulSoup
import json,re
src=Path('/home/ubuntu/upload/data.imf.org_en_datasets_IMF.STA_IMTS_1787786643195.html'); out=Path('/home/ubuntu/CHAOS/campaigns/research_rounds/20260827_BROWSER_DEEP_RESEARCH/IMF_IMTS_DOWNLOAD_DOM_ANALYSIS_V1.json'); text=src.read_text(errors='ignore'); soup=BeautifulSoup(text,'html.parser'); hits=[]
for tag in soup.find_all(['a','button','script','input']):
 s=' '.join(tag.get_text(' ',strip=True).split())+' '+str(tag.attrs)
 if any(k in s.lower() for k in ['download','imts','sdmx','api','csv']): hits.append({'tag':tag.name,'text':' '.join(tag.get_text(' ',strip=True).split())[:500],'attrs':{k:str(v)[:500] for k,v in tag.attrs.items() if k in ['href','src','data-testid','value','id','class','name']}})
urls=sorted(set(re.findall(r'https?://[^"\'<>\s]+',text)))
urls=[u for u in urls if any(k in u.lower() for k in ['imf','sdmx','api','download','imts'])]
res={'html_path':str(src),'relevant_tags':hits,'relevant_urls':urls,'status':'dom_analysis_complete'}; out.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n'); print(json.dumps({'tag_count':len(hits),'urls':urls},ensure_ascii=False,indent=2))
