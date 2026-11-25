from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path('/home/ubuntu/market_intelligence_workspace/catalog_first')
raw = ROOT / 'raw'
results: list[dict[str, object]] = []

for path in sorted((raw / 'fred').glob('*.csv')):
    with path.open(encoding='utf-8-sig', errors='replace', newline='') as handle:
        reader = csv.reader(handle)
        header = next(reader)
        rows = list(reader)
    dates = [row[0] for row in rows if row and row[0] and row[0] != 'DATE']
    results.append({
        'dataset_id': f'fred_{path.stem.lower()}',
        'source': 'FRED',
        'path': str(path),
        'years': f'{min(dates)[:4]}–{max(dates)[:4]}' if dates else None,
        'frequency': 'series page metadata required; inferred from date spacing',
        'variables_or_series': 1,
        'records_or_rows': len(rows),
        'columns': len(header),
        'size_bytes': path.stat().st_size,
        'license_status': 'series-level copyright/use notes apply; review source metadata',
        'access_method': 'public fredgraph.csv download',
        'downloaded': True,
        'notes': f'header={header}',
    })

for path in sorted((raw / 'eia').glob('*.zip')):
    results.append({
        'dataset_id': f'eia_{path.stem.lower()}',
        'source': 'EIA',
        'path': str(path),
        'years': 'catalog-dependent; series metadata inside JSONL',
        'frequency': 'catalog-dependent',
        'variables_or_series': 'inspect JSONL objects',
        'records_or_rows': 'inspect JSONL objects',
        'columns': 'JSON objects',
        'size_bytes': path.stat().st_size,
        'license_status': 'EIA free/open data; verify current reuse policy',
        'access_method': 'official EIA bulk ZIP',
        'downloaded': True,
        'notes': 'Raw ZIP retained; staged JSONL profile is separate.',
    })

out = ROOT / 'fred_eia_profile.json'
out.write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(out)
print(json.dumps(results, ensure_ascii=False, indent=2))
