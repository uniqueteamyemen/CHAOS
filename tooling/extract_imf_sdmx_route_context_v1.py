#!/usr/bin/env python3
from pathlib import Path
import json
p=Path('/tmp/imf_imts_chunks/%5B%5B...path%5D%5D-2fbb0793b68a6110.js'); t=p.read_text(errors='ignore'); terms=['https://api.imf.org/external/sdmx/3.0/data/dataflow/','https://api.imf.org/external/sdmx/3.0/structure/dataflow/','dataflow/IMF.STA','IMF.STA:IMTS','datasetUrn']
res={}
for term in terms:
 i=t.find(term); res[term]=t[max(0,i-1800):i+3000] if i>=0 else None
Path('/home/ubuntu/CHAOS/campaigns/research_rounds/20260827_BROWSER_DEEP_RESEARCH/IMF_SDMX_ROUTE_CONTEXT_V1.json').write_text(json.dumps({'chunk':str(p),'contexts':res},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:(len(v) if v else None) for k,v in res.items()},ensure_ascii=False,indent=2))
