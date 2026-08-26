#!/usr/bin/env python3
from pathlib import Path
import json
p=Path('/home/ubuntu/CHAOS/campaigns/research_rounds/20260827_BROWSER_DEEP_RESEARCH/IMF_IMTS_STRUCTURE_RESPONSE.xml'); d=json.loads(p.read_text())['data']; wanted=['COUNTRY','INDICATOR','COUNTERPART','FREQ','FREQUENCY','TRADE']; out=[]
for c in d.get('codelists',[]):
 blob=(str(c.get('id',''))+' '+str(c.get('name',''))).upper()
 if any(x in blob for x in wanted):
  codes=[]
  for code in c.get('codes',[]): codes.append({'id':code.get('id'),'name':code.get('name'),'names':code.get('names')})
  out.append({'id':c.get('id'),'agencyID':c.get('agencyID'),'version':c.get('version'),'name':c.get('name'),'codes':codes[:500],'code_count':len(c.get('codes',[]))})
Path('/home/ubuntu/CHAOS/campaigns/research_rounds/20260827_BROWSER_DEEP_RESEARCH/IMF_IMTS_CODELISTS_V1.json').write_text(json.dumps({'codelists':out,'status':'codelists_extracted'},ensure_ascii=False,indent=2)+'\n'); print(json.dumps({'codelists':[(x['id'],x['code_count']) for x in out]},ensure_ascii=False,indent=2))
