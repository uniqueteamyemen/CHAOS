#!/usr/bin/env python3
from pathlib import Path
import json
p=Path('/tmp/imf_imts_chunks/%5B%5B...path%5D%5D-2fbb0793b68a6110.js'); t=p.read_text(errors='ignore'); terms=['https://api.imf.org/external/sdmx/3.0/data/dataflow/','https://api.imf.org/external/sdmx/3.0/structure/dataflow/']
res={}
for term in terms:
 out=[]; start=0
 while True:
  i=t.find(term,start)
  if i<0: break
  out.append({'offset':i,'context':t[max(0,i-2500):i+5000]}); start=i+len(term)
 res[term]=out
Path('/home/ubuntu/CHAOS/campaigns/research_rounds/20260827_BROWSER_DEEP_RESEARCH/IMF_SDMX_ALL_CONTEXTS_V1.json').write_text(json.dumps({'chunk':str(p),'contexts':res},ensure_ascii=False,indent=2)+'\n'); print(json.dumps({k:[x['offset'] for x in v] for k,v in res.items()},ensure_ascii=False,indent=2))
