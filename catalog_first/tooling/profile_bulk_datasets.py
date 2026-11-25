from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd

ROOT = Path('/home/ubuntu/market_intelligence_workspace/catalog_first')
OUT = ROOT / 'HISTORICAL_DATASET_ACQUISITION_INVENTORY.csv'
rows: list[dict[str, object]] = []


def add(dataset_id: str, source: str, path: str, years: str, frequency: str, variables: str, records: str, size: int, license_status: str, access: str, downloaded: str, notes: str) -> None:
    rows.append({
        'dataset_id': dataset_id,
        'source': source,
        'path': path,
        'years': years,
        'frequency': frequency,
        'variables_or_series': variables,
        'records_or_rows': records,
        'size_bytes': size,
        'license_status': license_status,
        'access_method': access,
        'downloaded': downloaded,
        'notes': notes,
    })

wdi_dir = ROOT / 'staged/worldbank/wdi_csv'
wdicountry = pd.read_csv(wdi_dir / 'WDICountry.csv')
wdiseries = pd.read_csv(wdi_dir / 'WDISeries.csv')
wdicsv = wdi_dir / 'WDICSV.csv'
# Stream the large table: count rows and derive min/max year from headers without loading it all.
with wdicsv.open(encoding='utf-8-sig', errors='replace', newline='') as handle:
    reader = csv.reader(handle)
    header = next(reader)
    year_columns = [column for column in header if column.isdigit()]
    row_count = sum(1 for _ in reader)
add(
    'worldbank_wdi_bulk_csv', 'World Bank WDI', str(wdicsv),
    f'{min(year_columns)}–{max(year_columns)}' if year_columns else '', 'annual',
    str(len(wdiseries)), str(row_count), wdicsv.stat().st_size,
    'World Bank terms/license not captured in local provenance; verify before redistribution',
    'bulk CSV zip downloaded from official WDI page', 'yes',
    f'{len(wdicountry)} country/aggregate rows in WDICountry.csv; {len(wdiseries)} series metadata rows; raw zip remains under raw/',
)
add(
    'worldbank_wdi_bulk_excel', 'World Bank WDI', str(ROOT / 'staged/worldbank/wdi_excel/WDIEXCEL.xlsx'),
    'catalog-dependent; inspect workbook metadata', 'annual', 'workbook sheets', 'workbook',
    (ROOT / 'staged/worldbank/wdi_excel/WDIEXCEL.xlsx').stat().st_size,
    'World Bank terms/license not captured in local provenance; verify before redistribution',
    'bulk Excel zip downloaded from official WDI page', 'yes', 'Excel mirror of WDI bulk data; kept as separate artifact.',
)

for path in sorted((ROOT / 'staged/imf/weo').glob('*.xlsx')):
    xl = pd.ExcelFile(path)
    details = []
    for sheet in xl.sheet_names:
        frame = pd.read_excel(path, sheet_name=sheet, nrows=4)
        details.append(f'{sheet}:{frame.shape[1]} columns')
    add(
        f'imf_{path.stem.lower()}', 'IMF WEO', str(path), '1980–present plus projections in current vintage', 'annual',
        '; '.join(details), 'workbook; inspect rows', path.stat().st_size,
        'IMF terms/license not captured in local provenance; verify before redistribution',
        'official downloadable Excel linked from IMF WEO page', 'yes',
        'Preserve as vintage-specific workbook; separate historical observations from projections during analysis.',
    )

fields = ['dataset_id', 'source', 'path', 'years', 'frequency', 'variables_or_series', 'records_or_rows', 'size_bytes', 'license_status', 'access_method', 'downloaded', 'notes']
with OUT.open('w', encoding='utf-8', newline='') as handle:
    writer = csv.DictWriter(handle, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
print(OUT)
print(f'rows={len(rows)}')
