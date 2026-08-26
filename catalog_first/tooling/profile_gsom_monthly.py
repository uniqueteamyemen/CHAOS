from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT=Path('/home/ubuntu/market_intelligence_workspace/catalog_first')
ELEMENTS=['PRCP','TAVG','TMAX','TMIN']
results=[]
all_values=[]
for path in sorted((ROOT/'raw/noaa/gsom_monthly/stations').glob('*.csv')):
    with path.open(encoding='utf-8-sig',errors='replace',newline='') as f:
        reader=csv.DictReader(f)
        rows=list(reader)
        header=reader.fieldnames or []
    dates=[r.get('DATE','') for r in rows if r.get('DATE')]
    element_counts={e:sum(1 for r in rows if str(r.get(e,'')).strip()) for e in ELEMENTS if e in header}
    results.append({
      'station_id':path.stem,'path':str(path),'rows':len(rows),'columns':len(header),'size_bytes':path.stat().st_size,
      'true_start_date':min(dates) if dates else '','true_end_date':max(dates) if dates else '',
      'frequency':'monthly','element_nonnull_counts':element_counts,
      'source':'NOAA/NCEI GSOM monthly','license_note':'NOAA/NCEI public data; cite GSOM DOI/documentation',
    })
    all_values.extend((path.stem,r) for r in rows)
profile={
 'dataset_id':'noaa_gsom_monthly_selected_stations','source':'NOAA/NCEI GSOM v1','version':'GSOM monthly catalog product',
 'stations':results,'station_count':len(results),'total_rows':sum(x['rows'] for x in results),'total_size_bytes':sum(x['size_bytes'] for x in results),
 'scope':'Nine stations selected earlier by reproducible regional coverage rule; native monthly files; no daily-to-monthly conversion.',
 'elements_in_scope':ELEMENTS,'official_url':'https://www.ncei.noaa.gov/access/search/datasets/global-summary-of-the-month/',
 'raw_directory':str(ROOT/'raw/noaa/gsom_monthly/stations'),'checksum_manifest':str(ROOT/'raw/noaa/gsom_monthly/stations/sha256sums.txt')
}
(ROOT/'gsom_monthly_profile.json').write_text(json.dumps(profile,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(profile,ensure_ascii=False,indent=2))
