#!/usr/bin/env python3
from pathlib import Path
import json
p=Path('/home/ubuntu/CHAOS/campaigns/research_rounds/20260827_BROWSER_DEEP_RESEARCH/IMF_IMTS_STRUCTURE_RESPONSE.xml'); d=json.loads(p.read_text())['data']; out=[]
for ds in d.get('dataStructures',[]):
 for x in ds.get('dataStructureComponents',{}).get('dimensionList',{}).get('dimensions',[]): out.append({'id':x.get('id'),'position':x.get('position'),'conceptIdentity':x.get('conceptIdentity'),'localRepresentation':x.get('localRepresentation')})
# fallback recursive extraction if structure shape differs
def walk(x,path=''):
 if isinstance(x,dict):
  if ('position' in x and ('conceptIdentity' in x or 'id' in x)):
   out.append({'path':path,'id':x.get('id'),'position':x.get('position'),'conceptIdentity':x.get('conceptIdentity'),'localRepresentation':x.get('localRepresentation')})
  for k,v in x.items(): walk(v,path+'/'+k)
 elif isinstance(x,list):
  for i,v in enumerate(x): walk(v,f'{path}[{i}]')
if not out: walk(d)
Path('/home/ubuntu/CHAOS/campaigns/research_rounds/20260827_BROWSER_DEEP_RESEARCH/IMF_IMTS_DIMENSIONS_V1.json').write_text(json.dumps({'dataflow':'IMF.STA:IMTS(1.0.0)','dimensions':out,'status':'dimension_inspection_complete'},ensure_ascii=False,indent=2)+'\n'); print(json.dumps({'count':len(out),'dimensions':out[:80]},ensure_ascii=False,indent=2))
