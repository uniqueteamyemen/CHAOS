from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

path = Path('/home/ubuntu/market_intelligence_workspace/catalog_first/staged/eia/intl/INTL.txt')
series = []
categories = 0
invalid = 0
with path.open(encoding='utf-8', errors='replace') as handle:
    for line in handle:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            invalid += 1
            continue
        if 'series_id' in obj:
            series.append(obj)
        elif 'category_id' in obj:
            categories += 1

freq = Counter(str(x.get('f', '')) for x in series)
years = []
for x in series:
    for key in ('start', 'end'):
        val = str(x.get(key, ''))
        if val[:4].isdigit():
            years.append(int(val[:4]))
summary = {
    'path': str(path),
    'size_bytes': path.stat().st_size,
    'jsonl_lines_nonempty': sum(1 for _ in path.open(encoding='utf-8', errors='replace') if _.strip()),
    'series_objects': len(series),
    'category_objects': categories,
    'invalid_json_lines': invalid,
    'frequency_codes': dict(freq),
    'series_year_range': [min(years), max(years)] if years else None,
    'sample_series': [
        {k: x.get(k) for k in ('series_id', 'name', 'units', 'f', 'description', 'source', 'start', 'end', 'last_updated')}
        for x in series[:10]
    ],
}
out = path.parents[2] / 'eia_intl_profile.json'
out.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(out)
print(json.dumps(summary, ensure_ascii=False, indent=2))
