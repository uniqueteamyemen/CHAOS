#!/usr/bin/env python3
import csv, json, hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
raw=ROOT/'data/raw/financial_world_bank_v1/WB_FS_AST_PRVT_GD_ZS_2000_2024.json'
out=ROOT/'data/raw/financial_world_bank_v1/WB_FS_AST_PRVT_GD_ZS_2000_2024.csv'
payload=json.loads(raw.read_text())
rows=[]
for item in payload[1]:
    country=item.get('country') or {}
    region=item.get('region') or {}
    value=item.get('value')
    if not item.get('date') or value is None or not country.get('id') or region.get('id') in {'NA',''}:
        continue
    rows.append({'entity_code':country['id'],'entity_name':country.get('value',''),'year':int(item['date']),'value':float(value)})
rows.sort(key=lambda r:(r['entity_code'],r['year']))
with out.open('w',newline='',encoding='utf-8') as h:
    w=csv.DictWriter(h,fieldnames=['entity_code','entity_name','year','value']); w.writeheader(); w.writerows(rows)
summary={'source_url':'https://api.worldbank.org/v2/country/all/indicator/FS.AST.PRVT.GD.ZS?format=json&per_page=20000&date=2000:2024','indicator':'FS.AST.PRVT.GD.ZS','indicator_name':'Domestic credit to private sector (% of GDP)','lastupdated':payload[0].get('lastupdated'),'rows':len(rows),'entities':len({r['entity_code'] for r in rows}),'raw_sha256':hashlib.sha256(raw.read_bytes()).hexdigest()}
(ROOT/'data/raw/financial_world_bank_v1/MANIFEST.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False))
