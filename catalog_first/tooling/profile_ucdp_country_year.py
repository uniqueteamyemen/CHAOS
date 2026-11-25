from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path('/home/ubuntu/market_intelligence_workspace/catalog_first')
path = ROOT / 'staged/ucdp/country_year261/OrganizedViolenceCYDataSet26_1.csv'
with path.open(encoding='utf-8-sig', errors='replace', newline='') as f:
    reader = csv.DictReader(f)
    rows = list(reader)
    header = reader.fieldnames or []

years=[]
countries=set()
nonempty={col:0 for col in header}
for row in rows:
    if row.get('year'):
        try: years.append(int(row['year']))
        except ValueError: pass
    for key in ('country','country_id','country_code','gwno_location','location'):
        if row.get(key): countries.add(row[key])
    for col in header:
        if str(row.get(col,'')).strip(): nonempty[col]+=1
profile={
 'dataset_id':'ucdp_country_year_organized_violence_v26_1',
 'source':'UCDP', 'version':'26.1', 'path':str(path), 'size_bytes':path.stat().st_size,
 'rows':len(rows), 'columns':len(header), 'header':header,
 'year_range':[min(years),max(years)] if years else [], 'distinct_location_like_values':len(countries),
 'nonempty_counts':nonempty,
 'raw_zip':str(ROOT/'raw/ucdp/country_year261/organizedviolencecy-261-csv.zip'),
 'codebook':str(ROOT/'raw/ucdp/country_year261/UCDP_OrganizedViolenceCY_Codebook_261.pdf'),
}
out=ROOT/'ucdp_country_year_profile.json'
out.write_text(json.dumps(profile,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(profile,ensure_ascii=False,indent=2))
