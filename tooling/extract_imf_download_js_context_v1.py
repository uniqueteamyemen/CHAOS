#!/usr/bin/env python3
from pathlib import Path
import json
p=Path('/tmp/imf_imts_chunks/%5B%5B...path%5D%5D-2fbb0793b68a6110.js'); t=p.read_text(errors='ignore'); terms=['DownloadSidebar','downloadDataset','DatasetButtons','/Components/DatasetButtons','downloadUrl','downloadURL','download']
out={}
for term in terms:
 pos=[]; start=0
 while True:
  i=t.find(term,start)
  if i<0: break
  pos.append(t[max(0,i-700):i+1400]); start=i+len(term)
  if len(pos)>=20: break
 out[term]=pos
Path('/home/ubuntu/CHAOS/campaigns/research_rounds/20260827_BROWSER_DEEP_RESEARCH/IMF_IMTS_DOWNLOAD_JS_CONTEXT_V1.json').write_text(json.dumps({'chunk':str(p),'bytes':p.stat().st_size,'contexts':out},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:len(v) for k,v in out.items()},ensure_ascii=False,indent=2))
