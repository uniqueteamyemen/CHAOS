#!/usr/bin/env python3
from pathlib import Path
import json
D=json.loads(Path('/home/ubuntu/CHAOS/campaigns/research_rounds/20260827_BROWSER_DEEP_RESEARCH/IMF_IMTS_CODELISTS_V1.json').read_text())
for c in D['codelists']:
 if c['id']=='CL_IMTS_COUNTRY':
  for x in c['codes']:
   s=(str(x.get('id'))+' '+str(x.get('name'))+' '+str(x.get('names',{}).get('en'))).lower()
   if any(k in s for k in ['world','united states','usa','all countries','world']): print(x)
