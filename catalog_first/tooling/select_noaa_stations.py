from __future__ import annotations

import json
from pathlib import Path

ROOT = Path('/home/ubuntu/market_intelligence_workspace/catalog_first')
raw = ROOT / 'raw/noaa/ghcn_daily'
stations: dict[str, dict[str, object]] = {}
for line in (raw / 'ghcnd-stations.txt').read_text(encoding='ascii', errors='replace').splitlines():
    if len(line) < 72:
        continue
    sid = line[0:11].strip()
    try:
        lat = float(line[12:20])
        lon = float(line[21:30])
    except ValueError:
        continue
    stations[sid] = {'id': sid, 'lat': lat, 'lon': lon, 'name': line[41:71].strip()}

wanted = {'PRCP', 'TMAX', 'TMIN'}
coverage: dict[str, dict[str, object]] = {}
for line in (raw / 'ghcnd-inventory.txt').read_text(encoding='ascii', errors='replace').splitlines():
    parts = line.split()
    if len(parts) < 6:
        continue
    sid, _lat, _lon, element, start_text, end_text = parts[:6]
    if element not in wanted or sid not in stations:
        continue
    try:
        start = int(start_text)
        end = int(end_text)
    except ValueError:
        continue
    item = coverage.setdefault(sid, {'elements': {}, **stations[sid]})
    item['elements'][element] = {'start': start, 'end': end}

# Candidate targets are only a reproducible selection heuristic for a small pilot subset.
targets = {
    'north_america': (40.0, -100.0),
    'south_america': (-15.0, -60.0),
    'europe': (50.0, 10.0),
    'africa': (0.0, 20.0),
    'middle_east': (30.0, 45.0),
    'south_asia': (20.0, 78.0),
    'east_asia': (35.0, 135.0),
    'southeast_asia': (5.0, 105.0),
    'oceania': (-25.0, 135.0),
}

def distance(item: dict[str, object], target: tuple[float, float]) -> float:
    lat = float(item['lat'])
    lon = float(item['lon'])
    return (lat - target[0]) ** 2 + (lon - target[1]) ** 2

selected = []
for region, target in targets.items():
    eligible = []
    for item in coverage.values():
        elements = item['elements']
        if not wanted.issubset(elements):
            continue
        if all(elements[e]['start'] <= 2000 and elements[e]['end'] >= 2025 for e in wanted):
            eligible.append(item)
    if eligible:
        chosen = min(eligible, key=lambda item: distance(item, target))
        selected.append({'region': region, **chosen})

out = ROOT / 'noaa_station_selection.json'
out.write_text(json.dumps({'selection_rule': 'PRCP/TMAX/TMIN each cover 2000–2025; closest eligible station to regional target; TAVG not synthesized', 'stations': selected}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(out)
print(json.dumps({'count': len(selected), 'stations': selected}, ensure_ascii=False, indent=2))
