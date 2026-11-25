from __future__ import annotations

import csv
import json
import math
import re
import zipfile
from collections import defaultdict
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path('/home/ubuntu/market_intelligence_workspace/catalog_first')
OUT = ROOT / 'readiness_gate'
OUT.mkdir(exist_ok=True)

YEARS_PANEL = list(range(2000, 2025))
YEAR_COLS_WDI = [str(y) for y in range(1960, 2026)]
WDI_CODES = [
    'AG.LND.PRCP.MM', 'EG.USE.PCAP.KG.OE', 'FP.CPI.TOTL.ZG',
    'NE.EXP.GNFS.KD.ZG', 'NE.IMP.GNFS.KD.ZG', 'NY.GDP.MKTP.CD',
    'NY.GDP.MKTP.KD', 'NY.GDP.MKTP.KD.ZG', 'NY.GDP.PCAP.KD',
    'PA.NUS.PPP', 'SL.UEM.TOTL.ZS', 'SP.POP.TOTL'
]
WEO_CODES = ['NGDP_RPCH', 'PCPI', 'BCA_NGDPD', 'GGXWDG_NGDP', 'TM_RPCH', 'TX_RPCH', 'LUR', 'PPPEX']

MATRIX_FIELDS = [
    'dataset_id', 'source', 'variable_id', 'variable_name', 'definition', 'unit',
    'native_frequency', 'true_start_date', 'true_end_date', 'native_record_count',
    'native_entity_or_event_count', 'panel_start', 'panel_end', 'panel_active_entities',
    'panel_expected_cells', 'panel_observed_cells', 'panel_missing_cells',
    'panel_coverage_ratio', 'full_panel_entity_count', 'missing_gaps',
    'definition_methodology_shifts', 'provenance', 'status', 'notes'
]
coverage_rows: list[dict[str, object]] = []

def add(row: dict[str, object]) -> None:
    coverage_rows.append({field: row.get(field, '') for field in MATRIX_FIELDS})

def clean(value: object) -> str:
    if value is None:
        return ''
    if isinstance(value, float) and math.isnan(value):
        return ''
    return str(value).replace('\n', ' ').strip()

def selected_meta(meta: dict[str, dict[str, str]], code: str) -> dict[str, str]:
    return meta.get(code, {})

def panel_stats(groups: dict[str, dict[str, object]], code: str) -> dict[str, object]:
    g = groups.get(code, {'entities': set(), 'observed_cells': 0, 'full_entities': 0, 'year_counts': defaultdict(int), 'rows': 0})
    entities = g['entities']
    expected = len(entities) * len(YEARS_PANEL)
    observed = int(g['observed_cells'])
    return {
        'panel_active_entities': len(entities),
        'panel_expected_cells': expected,
        'panel_observed_cells': observed,
        'panel_missing_cells': expected - observed,
        'panel_coverage_ratio': round(observed / expected, 6) if expected else 0,
        'full_panel_entity_count': int(g.get('full_entities', 0)),
    }

def gap_text(stats: dict[str, object], extra: str = '') -> str:
    base = f"2000–2024 expected={stats['panel_expected_cells']}; observed={stats['panel_observed_cells']}; missing={stats['panel_missing_cells']}; coverage={stats['panel_coverage_ratio']}; full_25y_entities={stats['full_panel_entity_count']}"
    return base + (f'; {extra}' if extra else '')

# ---------- WDI metadata and coverage ----------
wdi_series_path = ROOT / 'staged/worldbank/wdi_csv/WDISeries.csv'
wdi_meta: dict[str, dict[str, str]] = {}
with wdi_series_path.open(encoding='utf-8-sig', errors='replace', newline='') as f:
    for row in csv.DictReader(f):
        code = clean(row.get('Series Code'))
        if not code:
            continue
        wdi_meta[code] = {
            'name': clean(row.get('Indicator Name')),
            'definition': clean(row.get('Long definition')) or clean(row.get('Short definition')),
            'unit': clean(row.get('Unit of measure')),
            'frequency': clean(row.get('Periodicity')) or 'Annual',
            'source': clean(row.get('Source')),
            'license': clean(row.get('License Type')),
            'method': 'Metadata fields: Statistical concept and methodology; Base Period; Limitations and exceptions; Other notes.'
        }

wdi_groups: dict[str, dict[str, object]] = {}
for code in WDI_CODES:
    wdi_groups[code] = {'entities': set(), 'observed_cells': 0, 'full_entities': 0, 'year_counts': defaultdict(int), 'rows': 0, 'entity_years': defaultdict(set), 'true_year_counts': defaultdict(int)}

wdi_usecols = ['Country Name', 'Country Code', 'Indicator Name', 'Indicator Code'] + YEAR_COLS_WDI
for chunk in pd.read_csv(ROOT / 'staged/worldbank/wdi_csv/WDICSV.csv', usecols=wdi_usecols, chunksize=50000, low_memory=False):
    chunk = chunk[chunk['Indicator Code'].isin(WDI_CODES)]
    if chunk.empty:
        continue
    for code, group in chunk.groupby('Indicator Code', sort=False):
        g = wdi_groups[str(code)]
        g['rows'] += len(group)
        # The downloaded WDI observation table is wide. This is only a raw presence calculation.
        observed = group[YEAR_COLS_WDI].notna()
        for idx, row in group.iterrows():
            entity = clean(row['Country Code'])
            if not entity:
                continue
            all_panel = observed.loc[idx, [str(y) for y in YEARS_PANEL]]
            any_panel = bool(all_panel.any())
            if any_panel:
                g['entities'].add(entity)
            if bool(all_panel.all()):
                g['full_entities'] += 1
            g['observed_cells'] += int(all_panel.sum())
            for y in YEARS_PANEL:
                if bool(all_panel.loc[str(y)]):
                    g['year_counts'][y] += 1
            for y in range(1960, 2026):
                if bool(observed.loc[idx, str(y)]):
                    g['true_year_counts'][y] += 1

for code in WDI_CODES:
    meta = selected_meta(wdi_meta, code)
    g = wdi_groups[code]
    true_years = [y for y, n in g['true_year_counts'].items() if n]
    stats = panel_stats(wdi_groups, code)
    add({
        'dataset_id': 'worldbank_wdi_bulk_csv', 'source': 'World Bank WDI', 'variable_id': code,
        'variable_name': meta.get('name', ''), 'definition': meta.get('definition', ''), 'unit': meta.get('unit', ''),
        'native_frequency': meta.get('frequency', 'Annual'), 'true_start_date': str(min(true_years)) if true_years else '',
        'true_end_date': str(max(true_years)) if true_years else '', 'native_record_count': g['rows'],
        'native_entity_or_event_count': len(g['entities']), 'panel_start': '2000', 'panel_end': '2024', **stats,
        'missing_gaps': gap_text(stats, 'country-year cells missing inside active-entity envelope; no filling applied'),
        'definition_methodology_shifts': meta.get('method', '') + ' No automated historical break detection was applied; revisions/source changes remain possible and require later metadata audit.',
        'provenance': f"raw={ROOT / 'raw/worldbank/wdi/WDI_CSV.zip'}; staged={ROOT / 'staged/worldbank/wdi_csv/WDICSV.csv'}; metadata={wdi_series_path}; manifest={ROOT / 'raw/manifest.sha256.txt'}",
        'status': 'downloaded/raw+staged', 'notes': f"WDI source={meta.get('source','')}; license={meta.get('license','')}"
    })

# WDI country metadata for geographic intersection.
wdi_country_meta = {}
with (ROOT / 'staged/worldbank/wdi_csv/WDICountry.csv').open(encoding='utf-8-sig', errors='replace', newline='') as f:
    for row in csv.DictReader(f):
        code = clean(row.get('Country Code'))
        if code:
            wdi_country_meta[code] = {'name': clean(row.get('Short Name')), 'region': clean(row.get('Region'))}

# ---------- IMF WEO current-vintage coverage and raw panel values ----------
weo_path = ROOT / 'staged/imf/weo/WEOApr2026all.xlsx'
weo = pd.read_excel(weo_path, sheet_name='Countries')
weo.columns = [str(c) for c in weo.columns]
weo_year_cols = [str(y) for y in range(1980, 2032) if str(y) in weo.columns]
weo_groups: dict[str, dict[str, object]] = {}
for code in sorted(weo['INDICATOR.ID'].dropna().astype(str).unique()):
    weo_groups[code] = {'entities': set(), 'observed_cells': 0, 'full_entities': 0, 'year_counts': defaultdict(int), 'rows': 0, 'true_year_counts': defaultdict(int)}
for code, group in weo.groupby('INDICATOR.ID', sort=False):
    code = str(code)
    g = weo_groups[code]
    g['rows'] += len(group)
    observed = group[weo_year_cols].notna()
    panel_cols = [str(y) for y in YEARS_PANEL if str(y) in weo.columns]
    panel_obs = group[panel_cols].notna()
    for idx, row in group.iterrows():
        entity = clean(row.get('COUNTRY.ID'))
        any_panel = bool(panel_obs.loc[idx].any())
        if entity and any_panel:
            g['entities'].add(entity)
        if bool(panel_obs.loc[idx].all()):
            g['full_entities'] += 1
        g['observed_cells'] += int(panel_obs.loc[idx].sum())
        for y in YEARS_PANEL:
            if str(y) in panel_obs.columns and bool(panel_obs.loc[idx, str(y)]):
                g['year_counts'][y] += 1
        for y in range(1980, 2032):
            if str(y) in observed.columns and bool(observed.loc[idx, str(y)]):
                g['true_year_counts'][y] += 1

weo_meta = {}
for code, group in weo.groupby('INDICATOR.ID', sort=False):
    code = str(code)
    desc = next((clean(x) for x in group['INDICATOR.Description'] if clean(x)), '')
    name = next((clean(x) for x in group['INDICATOR'] if clean(x)), '')
    unit = next((clean(x) for x in group['UNIT'] if clean(x)), '')
    freq = next((clean(x) for x in group['FREQUENCY'] if clean(x)), 'Annual')
    weo_meta[code] = {'name': name, 'definition': desc, 'unit': unit, 'frequency': freq}

for code in WEO_CODES:
    g = weo_groups[code]
    meta = weo_meta.get(code, {})
    true_years = [y for y, n in g['true_year_counts'].items() if n]
    stats = panel_stats(weo_groups, code)
    add({
        'dataset_id': 'imf_weo_apr2026_current', 'source': 'IMF WEO', 'variable_id': code,
        'variable_name': meta.get('name', ''), 'definition': meta.get('definition', ''), 'unit': meta.get('unit', ''),
        'native_frequency': meta.get('frequency', 'Annual'), 'true_start_date': str(min(true_years)) if true_years else '',
        'true_end_date': str(max(true_years)) if true_years else '', 'native_record_count': g['rows'],
        'native_entity_or_event_count': len(g['entities']), 'panel_start': '2000', 'panel_end': '2024', **stats,
        'missing_gaps': gap_text(stats, 'current-vintage country-year cells; no filling; 2025+ workbook values are not used in panel'),
        'definition_methodology_shifts': 'Current-vintage IMF WEO values may include revisions/estimates and the workbook contains projections after the historical/current boundary. No vintage consolidation or historical break detection applied.',
        'provenance': f"raw={ROOT / 'raw/imf/weo/WEOApr2026all.xlsx'}; staged={weo_path}; source_page=https://data.imf.org/en/datasets/IMF.RES:WEO",
        'status': 'downloaded/raw+staged', 'notes': 'Source workbook carries INDICATOR.Description, UNIT and FREQUENCY; country identifiers are IMF COUNTRY.ID.'
    })

# ---------- IMF historical forecasts coverage ----------
hist_path = ROOT / 'staged/imf/weo/WEOhistorical.xlsx'
hist_defs = {
    'ngdp_rpch': ('Real GDP growth', 'Percent'),
    'pcpi_pch': ('CPI inflation', 'Percent'),
    'bca_gdp_bp6': ('Current account balance, percent of GDP', 'Percent of GDP'),
}
for var, (name, unit) in hist_defs.items():
    sheet = pd.read_excel(hist_path, sheet_name=var)
    vintage_cols = [c for c in sheet.columns if re.match(r'^[SF]\d{4}' + re.escape(var) + '$', str(c))]
    nonnull = sheet[vintage_cols].notna()
    observed = int(nonnull.sum().sum())
    expected = len(sheet) * len(vintage_cols)
    missing = expected - observed
    years = sorted({int(re.search(r'(\d{4})', str(c)).group(1)) for c in vintage_cols})
    add({
        'dataset_id': 'imf_weo_historical_forecasts', 'source': 'IMF WEO', 'variable_id': var,
        'variable_name': name, 'definition': name + ' across Spring/Fall WEO vintages; two historical and six forecast years per publication.', 'unit': unit,
        'native_frequency': 'annual with Spring/Fall vintage dimension', 'true_start_date': str(min(years)) if years else '', 'true_end_date': str(max(years)) if years else '',
        'native_record_count': len(sheet), 'native_entity_or_event_count': sheet['ISOAlpha_3Code'].nunique(), 'panel_start': '', 'panel_end': '',
        'panel_active_entities': '', 'panel_expected_cells': expected, 'panel_observed_cells': observed, 'panel_missing_cells': missing,
        'panel_coverage_ratio': round(observed / expected, 6) if expected else 0, 'full_panel_entity_count': '',
        'missing_gaps': f"vintage-country cells expected={expected}; observed={observed}; missing={missing}; not a regular single series; no filling applied",
        'definition_methodology_shifts': 'IMF Info sheet explicitly warns of continual updates, splicing of structural breaks, staff estimates and differences from other official sources. Spring/Fall vintages are retained, not collapsed.',
        'provenance': f"raw={ROOT / 'raw/imf/weo/WEOhistorical.xlsx'}; staged={hist_path}; source_page=https://data.imf.org/en/datasets/IMF.RES:WEO",
        'status': 'downloaded/raw+staged', 'notes': f"vintage_columns={len(vintage_cols)}; original sheet rows={len(sheet)}"
    })

# ---------- EIA INTL: one row per actual catalogued series with data array ----------
def period_token(token: str, freq: str):
    token = str(token)
    try:
        if freq == 'A':
            return int(token[:4])
        if freq == 'M':
            return int(token[:6])
        if freq == 'Q':
            m = re.match(r'^(\d{4})Q([1-4])$', token)
            if m:
                return int(m.group(1)) * 4 + int(m.group(2))
            return int(token[:4]) * 4 + 1
    except Exception:
        return None
    return token

def missing_periods(periods: list[str], freq: str) -> int | str:
    vals = [period_token(x, freq) for x in periods if period_token(x, freq) is not None]
    if not vals:
        return 'not computable'
    lo, hi = min(vals), max(vals)
    return max(0, hi - lo + 1 - len(set(vals)))

eia_path = ROOT / 'staged/eia/intl/INTL.txt'
eia_count = 0
with eia_path.open(encoding='utf-8', errors='replace') as f:
    for line in f:
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        sid = clean(obj.get('series_id'))
        data = obj.get('data')
        if not sid or not isinstance(data, list):
            continue
        eia_count += 1
        freq = clean(obj.get('f')) or 'unknown'
        periods = [str(x[0]) for x in data if isinstance(x, list) and len(x) >= 2]
        values = [x for x in data if isinstance(x, list) and len(x) >= 2 and x[1] is not None]
        start = min(periods) if periods else clean(obj.get('start'))
        end = max(periods) if periods else clean(obj.get('end'))
        panel_periods = []
        if freq == 'A':
            panel_periods = [p for p in periods if re.match(r'^20\d{2}$', p) and 2000 <= int(p) <= 2024]
        panel_expected = 25 if panel_periods else 0
        # EIA series are often geography-specific; no cross-series common panel is inferred here.
        observed_panel = len(set(panel_periods))
        add({
            'dataset_id': 'eia_intl_bulk', 'source': 'EIA', 'variable_id': sid,
            'variable_name': clean(obj.get('name')), 'definition': clean(obj.get('name')), 'unit': clean(obj.get('units')),
            'native_frequency': {'A': 'annual', 'M': 'monthly', 'Q': 'quarterly'}.get(freq, freq),
            'true_start_date': start, 'true_end_date': end, 'native_record_count': len(values),
            'native_entity_or_event_count': clean(obj.get('geography')), 'panel_start': '2000' if freq == 'A' else '', 'panel_end': '2024' if freq == 'A' else '',
            'panel_active_entities': 1 if panel_periods else 0, 'panel_expected_cells': panel_expected, 'panel_observed_cells': observed_panel,
            'panel_missing_cells': panel_expected - observed_panel, 'panel_coverage_ratio': round(observed_panel / panel_expected, 6) if panel_expected else '',
            'full_panel_entity_count': 1 if observed_panel == 25 else 0,
            'missing_gaps': f"native-period gaps between first/last={missing_periods(periods, freq)}; annual 2000–2024 observed={observed_panel}/25" if periods else 'no data periods',
            'definition_methodology_shifts': 'EIA record retains source, frequency, update timestamp and copyright fields. No methodology-shift detection applied; series-specific revisions possible.',
            'provenance': f"raw={ROOT / 'raw/eia/INTL.zip'}; staged={eia_path}; official_bulk=https://www.eia.gov/opendata/index.php#bulk-downloads",
            'status': 'downloaded/raw+staged', 'notes': f"geography={clean(obj.get('geography'))}; last_updated={clean(obj.get('last_updated'))}; copyright={clean(obj.get('copyright'))}"
        })

# ---------- FRED selected series ----------
fred_defs = {
    'CPIAUCSL': ('Consumer Price Index for All Urban Consumers: All Items', 'CPI index, 1982–1984=100', 'monthly', 'FRED series-level metadata/copyright apply'),
    'DCOILWTICO': ('Crude Oil Prices: West Texas Intermediate (WTI), Cushing, Oklahoma', 'dollars per barrel', 'daily', 'FRED series-level metadata/copyright apply; business-day calendar')
}
for code, (name, unit, freq, terms) in fred_defs.items():
    path = ROOT / 'raw/fred' / f'{code}.csv'
    df = pd.read_csv(path)
    dates = pd.to_datetime(df['observation_date'], errors='coerce').dropna()
    vals = df[code].notna()
    actual_dates = dates[vals]
    add({
        'dataset_id': f'fred_{code.lower()}', 'source': 'FRED', 'variable_id': code, 'variable_name': name,
        'definition': name, 'unit': unit, 'native_frequency': freq,
        'true_start_date': actual_dates.min().date().isoformat() if len(actual_dates) else '', 'true_end_date': actual_dates.max().date().isoformat() if len(actual_dates) else '',
        'native_record_count': int(vals.sum()), 'native_entity_or_event_count': 1, 'panel_start': '', 'panel_end': '',
        'panel_active_entities': '', 'panel_expected_cells': '', 'panel_observed_cells': '', 'panel_missing_cells': '', 'panel_coverage_ratio': '', 'full_panel_entity_count': '',
        'missing_gaps': 'Monthly calendar gap check not converted into annual panel; daily WTI follows business-day calendar and weekends are not treated as missing observations.',
        'definition_methodology_shifts': 'Latest revised FRED graph series; not a historical-vintage replay. Use ALFRED for initial-release/vintage analysis. No transformations applied.',
        'provenance': f"raw={path}; checksum={ROOT / 'raw/fred_eia_sha256sums.txt'}; series_page=https://fred.stlouisfed.org/series/{code}",
        'status': 'downloaded/raw', 'notes': terms
    })

# ---------- NOAA selected stations, one variable row per station-element ----------
noaa_elements = ['PRCP', 'TMAX', 'TMIN', 'TAVG', 'SNOW', 'SNWD', 'EVAP']
noaa_selection = json.loads((ROOT / 'noaa_station_selection.json').read_text(encoding='utf-8'))
noaa_by_id = {x['id']: x for x in noaa_selection['stations']}
for path in sorted((ROOT / 'raw/noaa/ghcn_daily/stations').glob('*.csv')):
    station = path.stem
    df = pd.read_csv(path, low_memory=False)
    dates = pd.to_datetime(df['DATE'], errors='coerce')
    station_info = noaa_by_id.get(station, {})
    for element in noaa_elements:
        if element not in df.columns:
            continue
        present = df[element].notna() & dates.notna()
        if not present.any():
            continue
        d = dates[present]
        lo, hi = d.min().date(), d.max().date()
        expected_days = (hi - lo).days + 1
        observed_days = int(present.sum())
        add({
            'dataset_id': f'noaa_ghcn_daily_{station}', 'source': 'NOAA/NCEI GHCN-Daily', 'variable_id': f'{station}:{element}',
            'variable_name': f"{station_info.get('name','')} — {element}",
            'definition': f'GHCN-Daily station observation element {element}; station={station}; region={station_info.get("region","")}',
            'unit': 'PRCP: tenths of mm; TMAX/TMIN/TAVG: tenths of °C; SNOW/SNWD: tenths of mm; EVAP: tenths of mm (per GHCN-Daily README)',
            'native_frequency': 'daily', 'true_start_date': lo.isoformat(), 'true_end_date': hi.isoformat(), 'native_record_count': observed_days,
            'native_entity_or_event_count': 1, 'panel_start': '', 'panel_end': '', 'panel_active_entities': '', 'panel_expected_cells': expected_days,
            'panel_observed_cells': observed_days, 'panel_missing_cells': expected_days - observed_days, 'panel_coverage_ratio': round(observed_days / expected_days, 6), 'full_panel_entity_count': '',
            'missing_gaps': f'calendar days within element span={expected_days}; observed element days={observed_days}; calendar_missing={expected_days-observed_days}; station reporting gaps are not filled',
            'definition_methodology_shifts': 'GHCN-Daily attributes/quality flags remain in the raw file. Station history and source/quality flags may change; no homogenization or gap correction applied.',
            'provenance': f"raw={path}; selection={ROOT / 'noaa_station_selection.json'}; profile={ROOT / 'noaa_station_profile.json'}; README={ROOT / 'raw/noaa/ghcn_daily/readme.txt'}",
            'status': 'downloaded/raw', 'notes': f"coordinates={station_info.get('lat')},{station_info.get('lon')}; region selection is a reproducible small subset, not a global climate average"
        })

# ---------- UCDP event and conflict datasets: fields are irregular/event attributes, not annual series ----------
def profile_event_csv(dataset_id: str, source: str, path: Path, frequency: str, year_col: str, raw_path: Path, staged_path: Path, definition_note: str, version_note: str):
    header = pd.read_csv(path, nrows=0).columns.tolist()
    counts = {col: 0 for col in header}
    first_year = {col: None for col in header}
    last_year = {col: None for col in header}
    total = 0
    for chunk in pd.read_csv(path, chunksize=100000, dtype=str, low_memory=False):
        total += len(chunk)
        years = pd.to_numeric(chunk[year_col], errors='coerce') if year_col in chunk.columns else pd.Series([None] * len(chunk))
        for col in header:
            present = chunk[col].notna() & chunk[col].astype(str).str.strip().ne('')
            count = int(present.sum())
            counts[col] += count
            if count and year_col in chunk.columns:
                ys = years[present].dropna()
                if len(ys):
                    mn, mx = int(ys.min()), int(ys.max())
                    first_year[col] = mn if first_year[col] is None else min(first_year[col], mn)
                    last_year[col] = mx if last_year[col] is None else max(last_year[col], mx)
    for col in header:
        add({
            'dataset_id': dataset_id, 'source': source, 'variable_id': col, 'variable_name': col,
            'definition': f'{definition_note}; field={col}', 'unit': 'field-specific; see codebook', 'native_frequency': frequency,
            'true_start_date': str(first_year[col]) if first_year[col] is not None else '', 'true_end_date': str(last_year[col]) if last_year[col] is not None else '',
            'native_record_count': counts[col], 'native_entity_or_event_count': total, 'panel_start': '', 'panel_end': '',
            'panel_active_entities': '', 'panel_expected_cells': '', 'panel_observed_cells': '', 'panel_missing_cells': '', 'panel_coverage_ratio': '', 'full_panel_entity_count': '',
            'missing_gaps': f'irregular {frequency} records; field_nonnull={counts[col]}/{total}; annual calendar gap metric not applicable',
            'definition_methodology_shifts': version_note + ' No event-to-annual transformation, imputation or semantic recoding applied.',
            'provenance': f"raw={raw_path}; staged={staged_path}; official_source=https://ucdp.uu.se/downloads/",
            'status': 'downloaded/raw+staged', 'notes': 'Event/conflict attributes are not treated as regular annual time series.'
        })

profile_event_csv('ucdp_ged_global_v26_1', 'UCDP', ROOT / 'staged/ucdp/ged261/GEDEvent_v26_1.csv', 'daily/event', 'year', ROOT / 'raw/ucdp/ged261-csv.zip', ROOT / 'staged/ucdp/ged261/GEDEvent_v26_1.csv', 'UCDP GED georeferenced organized-violence event record', 'Version 26.1; event records include source/date precision/geography/death uncertainty fields; no methodology shift detection.')
profile_event_csv('ucdp_prio_armed_conflict_v26_1', 'UCDP/PRIO', ROOT / 'staged/ucdp/prio261/UcdpPrioConflict_v26_1.csv', 'annual conflict-year', 'year', ROOT / 'raw/ucdp/ucdp-prio-acd-261-csv.zip', ROOT / 'staged/ucdp/prio261/UcdpPrioConflict_v26_1.csv', 'UCDP/PRIO armed-conflict conflict-year record', 'Version 26.1; conflict-year coding and version history are source-defined; no event aggregation performed here.')

# ---------- GDELT reduced archive header-only coverage ----------
gdelt_zip = ROOT / 'raw/gdelt/GDELT.MASTERREDUCEDV2.1979-2013.zip'
with zipfile.ZipFile(gdelt_zip) as z:
    members = z.namelist()
    member = members[0]
    with z.open(member) as f:
        header = f.readline().decode('utf-8', errors='replace').rstrip('\r\n').split('\t')
for col in header:
    add({
        'dataset_id': 'gdelt_reduced_1979_2013', 'source': 'GDELT', 'variable_id': col, 'variable_name': col,
        'definition': f'GDELT reduced archive field {col}; codebook/header only in this gate', 'unit': 'field-specific; see GDELT documentation',
        'native_frequency': 'event/date-coded country-level reduced records', 'true_start_date': '1979-01-01', 'true_end_date': '2013-12-31',
        'native_record_count': '', 'native_entity_or_event_count': '', 'panel_start': '', 'panel_end': '', 'panel_active_entities': '', 'panel_expected_cells': '',
        'panel_observed_cells': '', 'panel_missing_cells': '', 'panel_coverage_ratio': '', 'full_panel_entity_count': '',
        'missing_gaps': 'not computed: 6.58 GB payload remains compressed and unextracted; no rows counted',
        'definition_methodology_shifts': 'Reduced country-level archive; date and news/event semantics require codebook review. No extraction, aggregation or transformation applied.',
        'provenance': f"raw={gdelt_zip}; checksum={ROOT / 'raw/gdelt/sha256sums.txt'}; official_source=https://www.gdeltproject.org/data.html",
        'status': 'downloaded/raw-compressed-only', 'notes': f'archive_member={member}; header extracted by streaming first line only'
    })

# Write variable-level matrix.
matrix_path = OUT / 'VARIABLE_LEVEL_COVERAGE_MATRIX.csv'
with matrix_path.open('w', encoding='utf-8', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=MATRIX_FIELDS)
    writer.writeheader()
    writer.writerows(coverage_rows)

# ---------- Build raw annual panel from WDI and IMF WEO, source-specific columns preserved ----------
# WDI selected values, no conversion. Keep all common entities with any selected observation.
wdi_panel_parts = []
for chunk in pd.read_csv(ROOT / 'staged/worldbank/wdi_csv/WDICSV.csv', usecols=['Country Name','Country Code','Indicator Name','Indicator Code'] + [str(y) for y in YEARS_PANEL], chunksize=50000, low_memory=False):
    sub = chunk[chunk['Indicator Code'].isin(WDI_CODES)].copy()
    if not sub.empty:
        wdi_panel_parts.append(sub)
wdi_selected = pd.concat(wdi_panel_parts, ignore_index=True)
wdi_long = wdi_selected.melt(id_vars=['Country Name','Country Code','Indicator Name','Indicator Code'], var_name='year', value_name='value')
wdi_long['year'] = wdi_long['year'].astype(int)
wdi_pivot = wdi_long.pivot_table(index=['Country Code','year'], columns='Indicator Code', values='value', aggfunc='first').reset_index()
wdi_names = wdi_selected[['Country Code','Country Name']].drop_duplicates('Country Code')
wdi_pivot = wdi_pivot.merge(wdi_names, on='Country Code', how='left')
wdi_pivot = wdi_pivot.rename(columns={'Country Code':'entity_code','Country Name':'wdi_entity_name'})
wdi_pivot = wdi_pivot.rename(columns={c: f'wdi__{c}' for c in WDI_CODES if c in wdi_pivot.columns})

# WEO selected values, no conversion. IMF country identifiers are kept separately from WDI names.
weo_sub = weo[weo['INDICATOR.ID'].astype(str).isin(WEO_CODES)].copy()
weo_long = weo_sub.melt(id_vars=['COUNTRY.ID','COUNTRY','INDICATOR.ID'], value_vars=[str(y) for y in YEARS_PANEL], var_name='year', value_name='value')
weo_long['year'] = weo_long['year'].astype(int)
weo_pivot = weo_long.pivot_table(index=['COUNTRY.ID','year'], columns='INDICATOR.ID', values='value', aggfunc='first').reset_index()
weo_names = weo_sub[['COUNTRY.ID','COUNTRY']].drop_duplicates('COUNTRY.ID')
weo_pivot = weo_pivot.merge(weo_names, on='COUNTRY.ID', how='left')
weo_pivot = weo_pivot.rename(columns={'COUNTRY.ID':'entity_code','COUNTRY':'imf_entity_name'})
weo_pivot = weo_pivot.rename(columns={c: f'imf__{c}' for c in WEO_CODES if c in weo_pivot.columns})

# Intersection is only identifier intersection; missing values stay missing and are explicitly measured in the matrix.
common_codes = sorted(set(wdi_pivot['entity_code'].dropna().astype(str)) & set(weo_pivot['entity_code'].dropna().astype(str)))
all_years = pd.DataFrame([(code, y) for code in common_codes for y in YEARS_PANEL], columns=['entity_code','year'])
panel = all_years.merge(wdi_pivot, on=['entity_code','year'], how='left').merge(weo_pivot, on=['entity_code','year'], how='left')
panel['wdi_entity_name'] = panel['wdi_entity_name'].fillna('')
panel['imf_entity_name'] = panel['imf_entity_name'].fillna('')
panel['entity_in_both_sources'] = True
panel_path = OUT / 'ANNUAL_PANEL_RAW_WDI_IMF_2000_2024.csv'
panel.to_csv(panel_path, index=False, encoding='utf-8')

# Panel-level intersection and readiness statistics.
wdi_entity_sets = []
for code in WDI_CODES:
    wdi_entity_sets.append(set(wdi_groups[code]['entities']))
weo_entity_sets = []
for code in WEO_CODES:
    weo_entity_sets.append(set(weo_groups[code]['entities']))
strict_wdi = set.intersection(*wdi_entity_sets) if wdi_entity_sets else set()
strict_weo = set.intersection(*weo_entity_sets) if weo_entity_sets else set()
strict_both = strict_wdi & strict_weo
panel_value_cols = [c for c in panel.columns if c.startswith('wdi__') or c.startswith('imf__')]
row_nonnull = panel[panel_value_cols].notna().sum(axis=1) if panel_value_cols else pd.Series(dtype=int)
readiness = {
    'gate_status': 'DATA_READINESS_GATE_ONLY',
    'experiment_run': False,
    'model_training_run': False,
    'transformations_applied': [],
    'imputation_applied': False,
    'source_reconciliation_applied': False,
    'panel_period': {'start': '2000', 'end': '2024', 'years': 25},
    'wdi_variable_count': len(WDI_CODES),
    'weo_variable_count': len(WEO_CODES),
    'wdi_entities_any_selected_variable': len(set().union(*(g['entities'] for g in wdi_groups.values()))),
    'weo_entities_any_selected_variable': len(set().union(*(g['entities'] for g in weo_groups.values()))),
    'identifier_intersection_any_selected_variable': len(common_codes),
    'strict_wdi_entities_complete_all_selected_variables_2000_2024': len(strict_wdi),
    'strict_weo_entities_complete_all_selected_variables_2000_2024': len(strict_weo),
    'strict_both_entities_complete_all_selected_variables_2000_2024': len(strict_both),
    'raw_panel_rows': int(len(panel)),
    'raw_panel_value_columns': panel_value_cols,
    'raw_panel_nonempty_value_cells': int(panel[panel_value_cols].notna().sum().sum()) if panel_value_cols else 0,
    'raw_panel_total_value_cells': int(len(panel) * len(panel_value_cols)),
    'raw_panel_missing_value_cells': int(panel[panel_value_cols].isna().sum().sum()) if panel_value_cols else 0,
    'common_entity_codes_sample': common_codes[:50],
    'strict_complete_entity_codes': sorted(strict_both),
    'panel_path': str(panel_path),
    'coverage_matrix_path': str(matrix_path),
    'raw_sources': {
        'wdi': str(ROOT / 'raw/worldbank/wdi/WDI_CSV.zip'),
        'imf_weo_current': str(ROOT / 'raw/imf/weo/WEOApr2026all.xlsx'),
        'imf_weo_historical': str(ROOT / 'raw/imf/weo/WEOhistorical.xlsx'),
    },
    'notes': 'Panel is a raw source-specific wide structure. WDI and IMF columns are not averaged or reconciled. Empty cells are observed missingness, not imputed values. Aggregates/entities enter only when their identifiers actually occur in the selected variables.'
}
(OUT / 'ANNUAL_PANEL_READINESS_SUMMARY.json').write_text(json.dumps(readiness, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

# Compact variable shortlist for human review.
shortlist = {
    'wdi_codes': WDI_CODES,
    'weo_codes': WEO_CODES,
    'source_specific_columns': [f'wdi__{x}' for x in WDI_CODES] + [f'imf__{x}' for x in WEO_CODES],
    'selection_rule': 'Catalog candidates only; explicit definitions/units and actual 2000–2024 coverage must be reviewed before any experiment.',
    'no_transformation': True,
    'no_experiment': True,
}
(OUT / 'FIRST_EXPERIMENTAL_MATRIX_CANDIDATES.json').write_text(json.dumps(shortlist, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'coverage_rows': len(coverage_rows), 'panel_rows': len(panel), 'common_entities': len(common_codes), 'strict_complete_entities': len(strict_both), 'outputs': [str(matrix_path), str(panel_path), str(OUT / 'ANNUAL_PANEL_READINESS_SUMMARY.json')]}, ensure_ascii=False, indent=2))
