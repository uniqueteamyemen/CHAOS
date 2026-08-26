#!/usr/bin/env python3
from pathlib import Path
import json
p=Path('/home/ubuntu/CHAOS/campaigns/research_rounds/20260827_BROWSER_DEEP_RESEARCH/IMF_IMTS_CODELISTS_V1.json'); d=json.loads(p.read_text()); wanted={'CL_IMTS_INDICATOR','CL_FREQ','CL_IMTS_COUNTRY'}
for c in d['codelists']:
 if c['id'] in wanted:
  print(c['id'],c['name'],c['code_count'])
  for x in c['codes'][:80]: print(' ',x['id'],x.get('name'),x.get('names',{}).get('en'))
