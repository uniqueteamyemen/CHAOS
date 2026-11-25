from __future__ import annotations

import csv
import json
import re
from pathlib import Path

ROOT = Path('/home/ubuntu/market_intelligence_workspace/catalog_first')
OUT = ROOT / 'FIRST_MATRIX_CANDIDATES.json'

# WDI metadata: select by explicit names, not by assuming all indicators are relevant.
wdi_path = ROOT / 'staged/worldbank/wdi_csv/WDISeries.csv'
wdi_matches = []
patterns = {
    'output_activity': r'GDP|gross domestic product|economic growth|industrial',
    'prices_purchasing_power': r'Consumer price|inflation|PPP|purchasing power',
    'trade_flows': r'trade|exports|imports',
    'energy_environment': r'energy|CO2|carbon|renewable|precipitation|temperature|forest|water',
    'population_social': r'population|unemployment|labor force|urban',
}
with wdi_path.open(encoding='utf-8-sig', errors='replace', newline='') as f:
    reader = csv.DictReader(f)
    for row in reader:
        text = ' '.join(str(row.get(k, '') or '') for k in ('Indicator Name', 'Short definition', 'Long definition', 'Topic')).strip()
        for role, pattern in patterns.items():
            if re.search(pattern, text, flags=re.I):
                wdi_matches.append({
                    'role': role,
                    'series_code': row.get('Series Code'),
                    'indicator_name': row.get('Indicator Name'),
                    'unit': row.get('Unit of measure'),
                    'periodicity': row.get('Periodicity'),
                    'source': row.get('Source'),
                    'license_type': row.get('License Type'),
                })
                break

# Show a compact shortlist based on exact names/codes commonly useful for the first matrix.
preferred_codes = {
    'NY.GDP.MKTP.KD', 'NY.GDP.MKTP.CD', 'NY.GDP.PCAP.KD', 'NY.GDP.MKTP.KD.ZG',
    'FP.CPI.TOTL.ZG', 'PA.NUS.PPP', 'NE.TRD.GNFS.KD.ZG', 'NE.EXP.GNFS.KD.ZG', 'NE.IMP.GNFS.KD.ZG',
    'EG.USE.PCAP.KG.OE', 'EN.ATM.CO2E.PC', 'SP.POP.TOTL', 'SL.UEM.TOTL.ZS', 'AG.LND.PRCP.MM'
}
shortlist = [x for x in wdi_matches if x['series_code'] in preferred_codes]

# EIA: scan JSONL without materializing the full file, preserving only matching metadata.
eia_matches = []
for line in (ROOT / 'staged/eia/intl/INTL.txt').open(encoding='utf-8', errors='replace'):
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        continue
    sid = obj.get('series_id') or obj.get('seriesId') or obj.get('series')
    name = str(obj.get('name') or obj.get('series_name') or obj.get('title') or '')
    units = str(obj.get('units') or obj.get('unit') or '')
    freq = obj.get('f') or obj.get('frequency')
    if not sid or not name:
        continue
    if re.search(r'energy consumption|total energy|petroleum|crude oil|natural gas|coal|electricity|CO2|carbon|GDP', name, flags=re.I):
        eia_matches.append({'series_id': sid, 'name': name, 'units': units, 'frequency': freq, 'start': obj.get('start'), 'end': obj.get('end'), 'last_updated': obj.get('last_updated')})

# Keep deterministic examples rather than claiming this is the whole EIA selection.
eia_examples = eia_matches[:100]

out = {
    'selection_status': 'candidate catalog only; no experiment run',
    'period_target': '2000–2024 annual primary panel; native monthly/daily/event streams remain separate',
    'wdi_preferred_code_shortlist': shortlist,
    'wdi_role_match_count': {role: sum(1 for x in wdi_matches if x['role'] == role) for role in patterns},
    'eia_match_count': len(eia_matches),
    'eia_examples_first_100': eia_examples,
    'required_next_step': 'coverage matrix by selected variable and entity; verify actual non-null coverage before any inference',
}
OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(OUT)
print('WDI shortlist:', len(shortlist))
for item in shortlist:
    print(item['series_code'], '|', item['indicator_name'], '|', item['unit'], '|', item['license_type'])
print('WDI role match counts:', out['wdi_role_match_count'])
print('EIA matches:', len(eia_matches))
print('EIA first examples:')
for item in eia_examples[:20]:
    print(item)
