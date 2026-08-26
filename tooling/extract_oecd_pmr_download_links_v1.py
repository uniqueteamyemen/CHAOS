#!/usr/bin/env python3
from pathlib import Path
from bs4 import BeautifulSoup
import json,re
p=Path('/home/ubuntu/upload/data-explorer.oecd.org_vis_tenant_archive_df_ds__DisseminateArchiveDMZ_df_id__DF_PMR_df_ag__OECD_dq__1787784348811.html')
out=Path('/home/ubuntu/CHAOS/campaigns/research_rounds/20260827_BROWSER_DEEP_RESEARCH/OECD_PMR_DOWNLOAD_LINK_ANALYSIS_V1.json')
soup=BeautifulSoup(p.read_text(errors='ignore'),'html.parser'); links=[]
for a in soup.find_all('a'):
 t=' '.join(a.get_text(' ',strip=True).split()); h=a.get('href','')
 if any(x in (t+' '+h).lower() for x in ['csv','download','pmr']):links.append({'text':t,'href':h})
result={'html_path':str(p),'candidate_links':links,'status':'html_inspection_complete'};out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False,indent=2))
