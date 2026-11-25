from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT=Path('/home/ubuntu/market_intelligence_workspace/catalog_first')
path=ROOT/'staged/eia/intl/INTL.txt'
# Select only country-specific series where the name exposes a clear country and annual frequency.
keywords=['energy consumption per capita','energy consumption per gdp','total energy consumption','petroleum consumption','natural gas consumption','coal consumption','electricity generation','CO2 emissions']
name_counts=Counter()
examples=defaultdict(list)
country_codes=['CHN','IND','USA','DEU','SAU','IRN','ZAF','BRA','MEX','TUR']
selected=[]
for line in path.open(encoding='utf-8',errors='replace'):
    try: obj=json.loads(line)
    except json.JSONDecodeError: continue
    sid=str(obj.get('series_id',''))
    if not sid or obj.get('f')!='A' or not isinstance(obj.get('data'),list): continue
    name=str(obj.get('name',''))
    low=name.lower()
    matches=[k for k in keywords if k in low]
    if not matches: continue
    for k in matches:
        name_counts[k]+=1
        if len(examples[k])<10: examples[k].append({'series_id':sid,'name':name,'units':obj.get('units'),'geography':obj.get('geography'),'start':obj.get('start'),'end':obj.get('end')})
    # Keep country-specific (not regional aggregate) examples for selected key concepts.
    if str(obj.get('geography','')).strip() in country_codes:
        if ('energy consumption per capita' in low or 'energy consumption per gdp' in low) and 'world' not in low:
            selected.append({'series_id':sid,'name':name,'units':obj.get('units'),'frequency':obj.get('f'),'start':obj.get('start'),'end':obj.get('end'),'data_points':len(obj['data']),'geography':obj.get('geography'),'last_updated':obj.get('last_updated')})
out={'annual_keyword_counts':dict(name_counts),'examples':dict(examples),'selected_country_examples':selected}
(ROOT/'eia_annual_selection_scan.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('keyword counts:',dict(name_counts))
for k,items in examples.items():
 print('\n',k)
 for x in items: print(x)
print('\nselected country examples:',len(selected))
for x in selected[:80]: print(x)
