from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path('/home/ubuntu/market_intelligence_workspace')
OUT = ROOT / 'existing_dataset_inventory.csv'
rows: list[dict[str, object]] = []


def add(path: Path, dataset_class: str, source: str, years: str = '', frequency: str = '', records: str = '', variables: str = '', status: str = '', access: str = '', notes: str = '') -> None:
    rows.append({
        'path': str(path),
        'source': source,
        'dataset_class': dataset_class,
        'years_or_window': years,
        'native_frequency': frequency,
        'record_count_or_scope': records,
        'variable_count_or_scope': variables,
        'file_size_bytes': path.stat().st_size if path.exists() else 0,
        'status': status,
        'access_observed': access,
        'notes': notes,
    })

# Existing campaign raw files are the evidence for what was actually acquired.
for path in sorted((ROOT / 'campaign' / 'raw').rglob('*')):
    if not path.is_file() or path.name.endswith('.request.txt') or path.name.endswith('.sha256') or path.name == 'manifest.sha256.txt':
        continue
    if path.suffix == '.json':
        try:
            payload = json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            add(path, 'raw_json_unparsed', 'unknown', status='captured_raw', notes='JSON parse failed; raw retained')
            continue
        if path.name.startswith('worldbank_'):
            data = payload[1] if isinstance(payload, list) and len(payload) > 1 and isinstance(payload[1], list) else []
            indicator = path.stem.replace('worldbank_WLD_', '').replace('worldbank_wld_', '')
            add(path, 'continuous_index', 'World Bank WDI', '2000–2025', 'annual', str(len(data)), '1', 'captured_raw', 'public API', f'indicator label from filename: {indicator}; values untouched')
        elif path.name.startswith('un_comtrade_'):
            data = payload.get('data', []) if isinstance(payload, dict) else []
            add(path, 'trade_flow', 'UN Comtrade', '2022', 'annual', str(len(data)), 'trade dimensions in payload', 'captured_raw', 'public preview API', 'bounded preview probe, not bulk history')
        elif path.name == 'usgs.json':
            series = payload.get('value', {}).get('timeSeries', []) if isinstance(payload, dict) else []
            obs = sum(len(block.get('value', [])) for item in series for block in item.get('values', []))
            add(path, 'continuous_index', 'USGS NWIS', '2000-01-01–2025-12-31', 'daily_values', str(obs), str(len(series)), 'captured_raw', 'public API', 'site/parameter metadata retained')
        elif path.name == 'imf.json':
            values = payload.get('values', {}) if isinstance(payload, dict) else {}
            indicator = values.get('NGDP_RPCH', {}) if isinstance(values, dict) else {}
            years = sorted({str(year) for series in indicator.values() if isinstance(series, dict) for year in series})
            add(path, 'macro_panel', 'IMF DataMapper', f'{years[0]}–{years[-1]}' if years else '', 'annual', str(sum(len(series) for series in indicator.values() if isinstance(series, dict))), str(len(indicator)), 'captured_raw', 'public DataMapper endpoint', 'raw contains historical and forecast years; derived matrix capped historical view at 2025')
        else:
            add(path, 'raw_json', 'unknown', status='captured_raw', notes='raw JSON retained; source classification requires review')
    elif path.suffix == '.csv':
        try:
            with path.open(encoding='utf-8', errors='replace', newline='') as handle:
                sample = handle.read(4096)
                handle.seek(0)
                rows_csv = list(csv.reader(handle))
            add(path, 'csv_response_or_dataset', 'FRED or NOAA', '', '', str(max(0, len(rows_csv) - 1)), str(len(rows_csv[0]) if rows_csv else 0), 'captured_raw', 'response/archival path', f'first bytes: {sample[:80]!r}')
        except Exception:
            add(path, 'raw_csv_unparsed', 'unknown', status='captured_raw', notes='CSV parse failed; raw retained')
    elif path.suffix == '.txt':
        add(path, 'metadata_or_exception', 'GDELT/NOAA', status='captured_raw_or_exception', notes=path.name)
    else:
        add(path, 'raw_binary', 'unknown', status='captured_raw', notes=path.name)

# Structural workspace files that are datasets or experiment artifacts.
for path in sorted((ROOT / 'structural_engine' / 'derived').glob('*')):
    if not path.is_file():
        continue
    if path.name == 'annual_observed_matrix.csv':
        with path.open(encoding='utf-8', newline='') as handle:
            data = list(csv.DictReader(handle))
        add(path, 'derived_analytical_matrix', 'derived from World Bank raw captures', '2000–2025', 'annual', str(len(data)), str(len(data[0]) - 1 if data else 0), 'derived_not_raw', 'local', 'inner observed rows only; no imputation')
    else:
        add(path, 'derived_artifact', 'local experiment', status='derived_not_raw', notes='not a source dataset')

fields = ['path', 'source', 'dataset_class', 'years_or_window', 'native_frequency', 'record_count_or_scope', 'variable_count_or_scope', 'file_size_bytes', 'status', 'access_observed', 'notes']
with OUT.open('w', encoding='utf-8', newline='') as handle:
    writer = csv.DictWriter(handle, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
print(OUT)
print(f'rows={len(rows)}')
