#!/usr/bin/env python3
from pathlib import Path
from bs4 import BeautifulSoup
import json
p=Path('/home/ubuntu/upload/data.imf.org_en_Search-Results_t_coveob02de888_sort_relevancy_1787785018359.html'); out=Path('/home/ubuntu/CHAOS/campaigns/research_rounds/20260827_BROWSER_DEEP_RESEARCH/IMF_ITG_IMTS_LINK_ANALYSIS_V1.json'); soup=BeautifulSoup(p.read_text(errors='ignore'),'html.parser'); rows=[]
for a in soup.find_all('a'):
 t=' '.join(a.get_text(' ',strip=True).split()); h=a.get('href','')
 if any(k in (t+' '+h).lower() for k in ['international trade in goods','imts','trade in goods']): rows.append({'text':t,'href':h})
out.write_text(json.dumps({'html_path':str(p),'links':rows,'status':'html_inspection_complete'},ensure_ascii=False,indent=2)+'\n');print(json.dumps({'links':rows},ensure_ascii=False,indent=2))
