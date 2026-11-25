from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path('/home/ubuntu/market_intelligence_workspace/catalog_first')
paths = sorted((ROOT / 'staged/ucdp').rglob('*.csv'))
results = []
for path in paths:
    with path.open(encoding='utf-8-sig', errors='replace', newline='') as handle:
        reader = csv.reader(handle)
        header = next(reader)
        rows = list(reader)
    data = rows
    year_columns = []
    for idx, name in enumerate(header):
        if name.lower() in {'year', 'year_start', 'year_end', 'date_start', 'date_end', 'date'}:
            year_columns.append(idx)
    numeric_years = []
    for row in data:
        for idx in year_columns:
            if idx < len(row):
                value = row[idx].strip()[:4]
                if value.isdigit() and 1800 <= int(value) <= 2100:
                    numeric_years.append(int(value))
    results.append({
        'path': str(path),
        'size_bytes': path.stat().st_size,
        'rows': len(data),
        'columns': len(header),
        'header': header,
        'detected_year_range': [min(numeric_years), max(numeric_years)] if numeric_years else None,
    })
output = ROOT / 'ucdp_profile.json'
output.write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(output)
print(json.dumps(results, ensure_ascii=False, indent=2))
