from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path('/home/ubuntu/market_intelligence_workspace/catalog_first')
result: dict[str, object] = {}
series = pd.read_csv(ROOT / 'staged/worldbank/wdi_csv/WDISeries.csv')
license_counts = series['License Type'].fillna('<blank>').value_counts().to_dict() if 'License Type' in series else {}
result['worldbank_wdi'] = {
    'license_type_counts': {str(key): int(value) for key, value in license_counts.items()},
    'sample_series': series[['Series Code', 'Indicator Name', 'Periodicity', 'Unit of measure', 'Source', 'License Type']].head(20).fillna('').to_dict(orient='records'),
}
for path in sorted((ROOT / 'staged/imf/weo').glob('*.xlsx')):
    excel = pd.ExcelFile(path)
    if 'Info' in excel.sheet_names:
        info = pd.read_excel(path, sheet_name='Info', header=None)
        result[path.stem] = {'info_rows': info.fillna('').astype(str).values.tolist()[:30]}
    else:
        result[path.stem] = {'info_rows': [], 'sheet_names': excel.sheet_names, 'note': 'No Info sheet in this vintage workbook'}
(ROOT / 'catalog_metadata_extract.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(ROOT / 'catalog_metadata_extract.json')
