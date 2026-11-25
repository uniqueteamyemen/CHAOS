from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path('/home/ubuntu/market_intelligence_workspace/catalog_first')
OUT = ROOT / 'workbook_profile.json'
profile: dict[str, object] = {}

wdi_dir = ROOT / 'staged/worldbank/wdi_csv'
wdi_series = pd.read_csv(wdi_dir / 'WDISeries.csv')
wdi_country = pd.read_csv(wdi_dir / 'WDICountry.csv')
with (wdi_dir / 'WDICSV.csv').open(encoding='utf-8-sig', errors='replace') as handle:
    header = handle.readline().rstrip('\n').split(',')
years = [int(value) for value in header if value.isdigit()]
profile['worldbank_wdi'] = {
    'series_metadata_rows': int(len(wdi_series)),
    'country_aggregate_rows': int(len(wdi_country)),
    'observation_table_years': [min(years), max(years)],
    'observation_columns': len(years),
    'observation_csv_size_bytes': (wdi_dir / 'WDICSV.csv').stat().st_size,
    'series_metadata_columns': list(wdi_series.columns),
    'country_metadata_columns': list(wdi_country.columns),
}

for path in sorted((ROOT / 'staged/imf/weo').glob('*.xlsx')):
    excel = pd.ExcelFile(path)
    sheets: dict[str, object] = {}
    for sheet in excel.sheet_names:
        frame = pd.read_excel(path, sheet_name=sheet)
        sheets[sheet] = {
            'rows': int(len(frame)),
            'columns': int(len(frame.columns)),
            'columns_preview': [str(value) for value in frame.columns[:12]],
            'columns_tail': [str(value) for value in frame.columns[-8:]],
        }
    profile[path.stem] = {'size_bytes': path.stat().st_size, 'sheets': sheets}

OUT.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(OUT)
print(json.dumps(profile, ensure_ascii=False, indent=2))
