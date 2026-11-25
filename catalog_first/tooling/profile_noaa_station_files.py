from __future__ import annotations

import csv
import json
from collections import Counter

ELEMENT_COLUMNS = ('PRCP', 'TMAX', 'TMIN', 'TAVG', 'SNOW', 'SNWD', 'AWND', 'EVAP', 'ACMC', 'ACMH', 'ACSC', 'ACSH', 'DAPR', 'MDPR', 'MDSF', 'WESD', 'WESF', 'WDFG', 'WSFG', 'WT01', 'WT02', 'WT03', 'WT04', 'WT05', 'WT06', 'WT07', 'WT08', 'WT09', 'WT10', 'WT11', 'WT16', 'WT18', 'WT19', 'WT21', 'WT22')
from pathlib import Path

ROOT = Path('/home/ubuntu/market_intelligence_workspace/catalog_first')
station_map = json.loads((ROOT / 'noaa_station_selection.json').read_text(encoding='utf-8'))
by_id = {item['id']: item for item in station_map['stations']}
results = []
for path in sorted((ROOT / 'raw/noaa/ghcn_daily/stations').glob('*.csv')):
    station_id = path.stem
    with path.open(encoding='utf-8-sig', errors='replace', newline='') as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    dates = [r.get('DATE', '') for r in rows if r.get('DATE')]
    elements = {element: sum(1 for r in rows if (r.get(element) or '').strip()) for element in ELEMENT_COLUMNS}
    elements = {element: count for element, count in elements.items() if count}
    results.append({
        'dataset_id': f'noaa_ghcn_daily_{station_id}',
        'source': 'NOAA GHCN-Daily',
        'path': str(path),
        'station_id': station_id,
        'region': by_id.get(station_id, {}).get('region'),
        'station_name': by_id.get(station_id, {}).get('name'),
        'latitude': by_id.get(station_id, {}).get('lat'),
        'longitude': by_id.get(station_id, {}).get('lon'),
        'years': f'{min(dates)[:4]}–{max(dates)[:4]}' if dates else None,
        'frequency': 'daily',
        'rows': len(rows),
        'columns': len(reader.fieldnames or []),
        'elements': elements,
        'size_bytes': path.stat().st_size,
        'license_status': 'NOAA/NCEI electronic downloads generally free; cite dataset and review use constraints',
        'downloaded': True,
    })
out = ROOT / 'noaa_station_profile.json'
out.write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(out)
print(json.dumps(results, ensure_ascii=False, indent=2))
